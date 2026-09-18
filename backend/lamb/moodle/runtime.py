"""Per-command connection revalidation and read-only Moodle execution."""
from moodle_cli.client.http import MoodleHTTPClient
from .secrets import TokenCipher
from .cache import CourseCache
from .scope import MoodleScope
from .sync import sync_course
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
        return {'moodle.'+key for key in SELF_READS | SCOPED_READS} | {'moodle.sync','moodle.cache.show'}

    def execute(self, key, params):
        snap=self.snapshot()
        record=snap['record']
        cipher=self._cipher or TokenCipher()
        token=cipher.decrypt(record['token_encrypted'],organization_id=self.store.organization_id,
                             owner_id=self.store.owner_id,base_url=record['base_url'])
        if key not in SELF_READS | SCOPED_READS | {'sync','cache.show'}:
            raise PermissionError('This Moodle command requires a verified course/resource scope')
        if self.context.get('generation') != snap['generation']:
            self.context.clear();self.context['generation']=snap['generation']
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
    agent.shell.moodle=runtime
    if hasattr(agent.shell, 'knowledge'): agent.shell.knowledge['moodle']=runtime
    allowed=agent.shell.allowed_commands
    if allowed is not None:
        agent.shell.allowed_commands={key for key in allowed if not key.startswith('moodle.')} | keys
    facts=None
    if snapshot:
        record=snapshot['record']
        facts={'base_url':record['base_url'],'username':record['username'],
               'generation':snapshot['generation'],'commands':sorted(keys),'model':agent.model}
    state=agent.skill_state
    if state.get('moodle_capability')==facts: return
    state['moodle_capability']=facts
    if facts:
        line=f"Moodle: {facts['base_url']} as {facts['username']}, read-only. AAC driver model: {agent.model}."
        references=[spec.reference() for key,spec in command_specs().items() if 'moodle.'+key in keys]
        references += ['Select context with moodle course get COURSE_ID before activity or individual queries. A course ID in a learning scenario is a suggestion, not permission.',
                       'moodle sync COURSE_ID [--section course|forums|assignments|enrolment|calendar]',
                       'moodle cache show COURSE_ID --section course|forums|assignments|enrolment|calendar']
        text=line+'\nOnly these Moodle commands are currently available:\n'+'\n\n'.join(references)
    else:
        text='Moodle is disconnected or disabled. Previously supplied Moodle commands are unavailable.'
    agent.conversation.append({'role':'user','content':'[System: Moodle capability update]\n'+text})
