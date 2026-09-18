"""Per-command connection revalidation and scoped Moodle execution."""
from moodle_cli.client.http import MoodleHTTPClient
from .secrets import TokenCipher
from .cache import CourseCache
from .scope import MoodleScope
from .sync import sync_course
from .writes import FORUM_WRITES, verify_forum_target, write_forum
from .reads import execute_read
from .scoped_reads import SCOPED_READS, execute_scoped_read

# These require no foreign resource resolution. Remaining reads are registered
# after their course/resource lineage guards are implemented.
SELF_READS = frozenset({'site.info','site.functions','user.me','enrol.my-courses',
                       'course.list','course.search','course.timeline','calendar.upcoming','grade.overview','message.list','message.conversations','message.unread','content.types'})


class MoodleRuntime:
    def __init__(self, store, *, cipher=None, cache_root=None, context=None):
        self.store=store
        self._cipher=cipher
        self.cache_root=cache_root
        self.context=context if context is not None else {}

    def snapshot(self):
        snap=self.store.snapshot()
        record=snap['record']
        if not record:
            raise PermissionError('Connect your Moodle account in the Moodle page first')
        snap['policy'].require_connection_url(record['base_url'])
        return snap

    def available(self):
        try:
            snap=self.snapshot()
        except PermissionError:
            return set()
        keys=SELF_READS | SCOPED_READS
        try:
            snap['policy'].require_write('forum')
            keys=keys | FORUM_WRITES
        except PermissionError:
            pass
        try:
            snap['policy'].require_write('grade')
            keys=keys | {'assign.grade'}
        except PermissionError:
            pass
        return {'moodle.'+key for key in keys} | {'moodle.sync','moodle.cache.show','moodle.import.file'}

    def prepare_grade(self, params):
        from .assessment import grade_review
        snap=self.snapshot()
        snap['policy'].require_write('grade')
        record=snap['record']
        if self.context.get('generation') != snap['generation']:
            raise PermissionError('Select the instructor course again after reconnecting')
        token=(self._cipher or TokenCipher()).decrypt(record['token_encrypted'],organization_id=self.store.organization_id,
            owner_id=self.store.owner_id,base_url=record['base_url'])
        with MoodleHTTPClient(record['base_url'],token,readonly=True) as client:
            review=grade_review(client,params,owner_moodle_id=record['moodle_user_id'],context=self.context)
        current=self.snapshot()
        if current['generation']!=snap['generation'] or current['policy']!=snap['policy']:
            raise PermissionError('Moodle connection changed during assessment review')
        return dict(review, connection_generation=snap['generation'])

    def execute(self, key, params, *, confirmed=False, review=None):
        snap=self.snapshot()
        record=snap['record']
        cipher=self._cipher or TokenCipher()
        token=cipher.decrypt(record['token_encrypted'],organization_id=self.store.organization_id,
                             owner_id=self.store.owner_id,base_url=record['base_url'])
        if key not in SELF_READS | SCOPED_READS | FORUM_WRITES | {'sync','cache.show','assign.grade','import.file'}:
            raise PermissionError('This Moodle command requires a verified course/resource scope')
        if self.context.get('generation') != snap['generation']:
            self.context.clear();self.context['generation']=snap['generation']
        if key=='import.file':
            if confirmed is not True:
                raise PermissionError('Importing a Moodle document requires explicit confirmation')
            proof=self.context.get('files',{}).get(params['file_id'])
            if not proof or proof['course_id']!=self.context.get('course_id'):
                raise PermissionError('List files in the selected instructor course before importing')
            with MoodleHTTPClient(record['base_url'],token,readonly=True) as client:
                files=execute_scoped_read(client,'file.list',proof['listing'],owner_moodle_id=record['moodle_user_id'],context=self.context)
            current=next((f for f in files if f.get('file_id')==params['file_id']),None)
            if current!=proof['file']:
                raise PermissionError('Moodle file changed or disappeared; list it again before approval')
            from .documents import download_file
            result=download_file(record['base_url'],token,current,single_file=params['single_file'])
            current=self.snapshot()
            if current['generation']!=snap['generation'] or current['policy']!=snap['policy']:
                raise PermissionError('Moodle connection changed during download; import cancelled')
            return result
        if key=='assign.grade':
            from .assessment import save_grade
            snap['policy'].require_write('grade')
            if confirmed is not True or not review:
                raise PermissionError('Grade saving requires teacher review and explicit confirmation')
            fresh=self.prepare_grade(params)
            if fresh!=review:
                raise PermissionError('Submission or proposal changed; review the updated proposal before saving')
            with MoodleHTTPClient(record['base_url'],token,readonly=False) as client:
                return save_grade(client,params)
        if key in FORUM_WRITES:
            snap['policy'].require_write('forum')
            if confirmed is not True:
                raise PermissionError('Moodle forum writes require explicit user confirmation')
            with MoodleHTTPClient(record['base_url'],token,readonly=True) as client:
                verify_forum_target(client,key,params,owner_moodle_id=record['moodle_user_id'],context=self.context)
            current=self.snapshot()
            if current['generation']!=snap['generation'] or current['policy']!=snap['policy']:
                raise PermissionError('Moodle connection changed before write; nothing posted')
            with MoodleHTTPClient(record['base_url'],token,readonly=False) as client:
                return write_forum(client,key,params)
        cache=CourseCache(self.store.organization_id,self.store.owner_id,base_url=record['base_url'],
                          moodle_user_id=record['moodle_user_id'],root=self.cache_root)
        with MoodleHTTPClient(record['base_url'],token,readonly=True) as client:
            if key=='sync':
                result=sync_course(client,cache,params['course_id'],params.get('section'))
            elif key=='cache.show':
                MoodleScope(client,record['moodle_user_id']).require_teacher(params['course_id'])
                result=cache.show(params['course_id'],params['section'])
            elif key in SCOPED_READS:
                result=execute_scoped_read(client,key,params,owner_moodle_id=record['moodle_user_id'],context=self.context)
            elif key in {'course.list','course.search'}:
                from .reads import plain
                result=plain(list(MoodleScope(client,record['moodle_user_id']).own_courses().values()))
                if key=='course.search':
                    query=params['query'].casefold()
                    result=[c for c in result if query in c['fullname'].casefold() or query in c['shortname'].casefold()]
            else:
                result=execute_read(client,key,params,owner_moodle_id=record['moodle_user_id'])
        # Do not return data into a turn after credentials or policy were revoked
        # while an external read was in flight.
        current=self.snapshot()
        if current['generation']!=snap['generation'] or current['policy']!=snap['policy']:
            raise PermissionError('Moodle connection changed during this command; result withheld')
        return result


def attach_to_agent(agent, store):
    """Refresh only appended dynamic facts; leave the pinned prefix intact."""
    from .contract import command_specs
    from .policy import MoodleConfigurationError
    runtime=MoodleRuntime(store,context=agent.skill_state.setdefault('moodle_context',{}))
    try:
        keys=runtime.available()
        snapshot=runtime.snapshot() if keys else None
    except (MoodleConfigurationError,PermissionError):
        keys,snapshot=set(),None
    agent.skill_state['integrations']=['moodle'] if keys else []
    agent.shell.moodle=runtime
    if hasattr(agent.shell, 'knowledge'): agent.shell.knowledge['moodle']=runtime
    allowed=agent.shell.allowed_commands
    if allowed is not None:
        agent.shell.allowed_commands={key for key in allowed if not key.startswith('moodle.')} | keys
    facts=None
    if snapshot:
        record=snapshot['record']
        facts={'base_url':record['base_url'],'username':record['username'],
               'pack_version':getattr(getattr(agent,'pack',None),'version',None),
               'generation':snapshot['generation'],'commands':sorted(keys),'model':agent.model,'provider':getattr(getattr(agent,'llm_client',None),'_lamb_aac_driver',{}).get('provider','unknown'),'forum_write': 'moodle.forum.post' in keys,'grade_write': 'moodle.assign.grade' in keys}
    state=agent.skill_state
    if state.get('moodle_capability')==facts: return
    state['moodle_capability']=facts
    if facts:
        access="forum writes require explicit approval" if facts["forum_write"] else "read-only"
        if facts["grade_write"]: access += "; grade writes require submission/proposal review and explicit approval"
        line=f"Moodle: {facts['base_url']} as {facts['username']}, {access}. AAC driver provider: {facts['provider']}; model: {agent.model}. Student names, posts and grades sent to this driver reach that provider. A hosted provider receives them off premises; a local deployment keeps them on premises."
        references=[spec.reference() for key,spec in command_specs().items() if 'moodle.'+key in keys]
        references += ['Select context with moodle course get COURSE_ID before activity or individual queries. A course ID in a learning scenario is a suggestion, not permission.',
                       'moodle import file FILE_ID --to kb ID | --single-file (confirmation required; use file_id from moodle file list, not a local path)',
                       'moodle sync COURSE_ID [--section course|forums|assignments|enrolment|calendar]',
                       'moodle cache show COURSE_ID --section course|forums|assignments|enrolment|calendar']
        pack=getattr(agent,'pack',None)
        if pack:
            from lamb.aac.skill_loader import list_skills
            workflows=[s for s in list_skills(pack.skills_dir) if s.get('requires_integration')=='moodle']
            references += ['Load the appropriate workflow with lamb skill load ID before acting:'] + [s['id']+': '+s['description'] for s in workflows]
        text=line+'\nOnly these Moodle commands are currently available:\n'+'\n\n'.join(references)
    else:
        text='Moodle is disconnected or disabled. Previously supplied Moodle commands are unavailable.'
    agent.conversation.append({'role':'user','content':'[System: Moodle capability update]\n'+text})


def integrations_for(auth):
    """Public capability discovery uses connection metadata, never decrypts tokens."""
    from .router import database
    from .store import ConnectionStore
    from .policy import MoodleConfigurationError
    try:
        runtime=MoodleRuntime(ConnectionStore(database(),auth.organization['id'],auth.user['id']))
        return ['moodle'] if runtime.available() else []
    except (PermissionError, RuntimeError, MoodleConfigurationError):
        return []
