"""Per-command connection revalidation and scoped Moodle execution."""
from moodle_cli.client.http import MoodleHTTPClient
from .secrets import TokenCipher
from .cache import CourseCache
from .scope import MoodleScope
from .sync import sync_course
from .writes import FORUM_WRITES, verify_forum_target, write_forum
from .reads import execute_read
from .scoped_reads import SCOPED_READS, execute_scoped_read
from .task_contract import task_specs
from .document_contract import document_specs, IMPORT_KEYS

# These have no caller-supplied foreign resource target. Category/cohort
# catalogues contain metadata only, not membership: Moodle enforces category
# visibility and cohort view/manage permissions for the connected account.
SELF_READS = frozenset({'site.info','site.functions','user.me','enrol.my-courses',
                       'course.list','course.search','course.categories','cohort.list','course.timeline','calendar.upcoming','grade.overview','message.list','message.conversations','message.unread','content.types'})


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

    def result_binding(self):
        """Credential-free binding for generic AAC result snapshots."""
        snap = self.snapshot()
        policy = snap['policy']
        return {'generation':snap['generation'], 'base_url':snap['record']['base_url'],
                'moodle_user_id':snap['record']['moodle_user_id'],
                'policy':{'enabled':policy.enabled, 'mode':policy.mode,
                          'write_groups':sorted(policy.write_groups), 'allow_grade_write':policy.allow_grade_write}}

    def validate_result_binding(self, binding, key):
        expected = {k:v for k,v in binding.items() if k not in {'course_id', 'course_ids'}}
        if self.result_binding() != expected or key not in self.available():
            raise PermissionError('Moodle snapshot is no longer accessible; run a fresh read')
        courses = binding.get('course_ids', binding.get('course_id'))
        if courses:
            snap = self.snapshot(); record = snap['record']
            token = (self._cipher or TokenCipher()).decrypt(record['token_encrypted'],
                organization_id=self.store.organization_id, owner_id=self.store.owner_id, base_url=record['base_url'])
            try:
                with MoodleHTTPClient(record['base_url'], token, readonly=True) as client:
                    scope = MoodleScope(client, record['moodle_user_id'])
                    for course in courses if isinstance(courses, (tuple, list)) else [courses]:
                        scope.require_teacher(course)
            except Exception as error:
                from .forum_activity import transient_failure
                if transient_failure(error):
                    raise ConnectionError('Moodle is temporarily unavailable. Retry this saved read when it recovers.') from None
                raise
        if self.result_binding() != expected:
            raise PermissionError('Moodle connection changed; snapshot withheld')

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
        return {'moodle.'+key for key in keys | task_specs().keys() | document_specs().keys()} | {'moodle.sync','moodle.cache.show','moodle.import.file'}

    def task(self, key, params, *, cancel=None, progress=None, full=False):
        if key in {'chart.list', 'chart.read'}:
            from .charts import ChartStore
            binding = self.result_binding()
            charts = ChartStore(self)
            if key == 'chart.list':
                data = charts.listing(params.get('offset', 0))
            else:
                data = dict(charts.read(params['chart_id']), evidence_kind='saved_snapshot', refreshed=False)
            if self.result_binding() != binding:
                raise PermissionError('Moodle connection changed; snapshot withheld')
            return data
        from .forum_activity import GuardedClient
        from .runs import RunStore
        from .results import ResultStore, summary, evidence_page
        snap = self.snapshot()
        record = snap['record']
        def revalidate():
            current = self.snapshot()
            if current['generation'] != snap['generation'] or current['policy'] != snap['policy']:
                raise PermissionError('Moodle connection changed during this task; result withheld')
        token = (self._cipher or TokenCipher()).decrypt(record['token_encrypted'],
            organization_id=self.store.organization_id, owner_id=self.store.owner_id, base_url=record['base_url'])
        results = ResultStore(self.store.organization_id, self.store.owner_id, base_url=record['base_url'],
            moodle_user_id=record['moodle_user_id'], generation=snap['generation'], root=self.cache_root)
        with MoodleHTTPClient(record['base_url'], token, readonly=True, timeout=15) as raw:
            client = GuardedClient(raw, revalidate=revalidate, cancel=cancel)
            if key == 'chart.submissions':
                from .charts import chart_task
                return chart_task(self, client, record['moodle_user_id'], params, progress=progress)
            if key in {'news', 'continue'}:
                return RunStore(results).execute(client, record['moodle_user_id'],
                    params=params if key == 'news' else None,
                    result_id=params.get('result_id') if key == 'continue' else None,
                    progress=progress)
            if key == 'runs':
                client.checkpoint()
                return RunStore(results).listing()
            if key == 'evidence':
                identity = params['result_id']
                snapshot = results.read(identity)
                # Fresh instructor verification before releasing previously stored
                # content, including after roles change without reconnecting.
                scope = MoodleScope(client, record['moodle_user_id'])
                for course in snapshot['courses']:
                    if course['forums']:
                        scope.require_teacher(course['id'])
                client.checkpoint()
                if full:
                    from .forum_activity import preview
                    # Keep original HTML only in private storage. The viewer uses
                    # plain text and never parses source HTML (even in an inert DOM).
                    snapshot['posts'] = [{**{k: v for k, v in p.items() if k != 'source'},
                        'subject_text': preview(p['source'].get('subject', ''), 1000)[0],
                        'message_text': preview(p['source'].get('message', ''), 2 * 1024 * 1024)[0]}
                        for p in snapshot['posts']]
                    return {'result_id': identity, 'snapshot': snapshot, 'base_url': record['base_url']}
                return evidence_page(identity, snapshot, params.get('offset', 0))
        raise ValueError('Unknown Moodle task')

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

    def prepare_import(self, key, params):
        from .imports import prepare
        snap = self.snapshot(); record = snap['record']
        if self.context.get('generation') != snap['generation']:
            raise PermissionError('List sources again after reconnecting')
        token = (self._cipher or TokenCipher()).decrypt(record['token_encrypted'],
            organization_id=self.store.organization_id, owner_id=self.store.owner_id, base_url=record['base_url'])
        with MoodleHTTPClient(record['base_url'], token, readonly=True) as client:
            review = prepare(self, client, record, token, key, params)
        current = self.snapshot()
        if current['generation'] != snap['generation'] or current['policy'] != snap['policy']:
            raise PermissionError('Moodle connection changed during import review')
        return review

    def execute(self, key, params, *, confirmed=False, review=None, cancel=None, progress=None):
        if key in task_specs():
            return self.task(key, params, cancel=cancel, progress=progress)
        snap=self.snapshot()
        record=snap['record']
        cipher=self._cipher or TokenCipher()
        token=cipher.decrypt(record['token_encrypted'],organization_id=self.store.organization_id,
                             owner_id=self.store.owner_id,base_url=record['base_url'])
        if key not in SELF_READS | SCOPED_READS | FORUM_WRITES | {'sync','cache.show','assign.grade'} | document_specs().keys():
            raise PermissionError('This Moodle command requires a verified course/resource scope')
        if self.context.get('generation') != snap['generation']:
            self.context.clear();self.context['generation']=snap['generation']
        if key in document_specs():
            with MoodleHTTPClient(record['base_url'], token, readonly=True) as client:
                if key.startswith('folder.'):
                    from .folders import listing, inventory, load_batch, status, confirm_folder
                    if key == 'folder.list':
                        result = listing(client, record, self.context, params['course_id'])
                    elif key == 'folder.inspect':
                        result = inventory(self, client, record, params)[0]
                    else:
                        ticket = load_batch(self, params['batch_id'])
                        MoodleScope(client, record['moodle_user_id']).require_teacher(ticket['review']['source']['course_id'])
                        current_status = status(self, ticket)
                        if key == 'folder.status' or current_status['status'] == 'completed': result = current_status
                        else:
                            if confirmed is not True: raise PermissionError('Continuing a folder batch requires approval')
                            result = confirm_folder(self, client, record, token, ticket['params'], ticket['review'], resume=True)
                elif key in {'page.list', 'book.list'}:
                    from .document_sources import list_activities
                    result = list_activities(client, key.split('.')[0], params['course_id'],
                        record['moodle_user_id'], record['base_url'], self.context)
                elif key == 'import.list':
                    from .imports import store_for_runtime, public_receipt, same_import_account
                    result = [public_receipt(r) for r in store_for_runtime(self).list('receipts')
                              if same_import_account(r['binding'], self.result_binding())]
                elif key == 'import.check':
                    from .imports import check
                    result = check(self, client, record, token, params)
                elif key == 'import.finish':
                    from .imports import ResumeImport, load_receipt, store_for_runtime
                    if confirmed is not True: raise PermissionError('Finishing a replacement requires approval')
                    receipt = load_receipt(self, params['import_id'])
                    MoodleScope(client, record['moodle_user_id']).require_teacher(receipt['source']['course_id'])
                    result = ResumeImport(receipt, store_for_runtime(self))
                else:
                    from .imports import confirm
                    if confirmed is not True: raise PermissionError('Importing a Moodle document requires explicit confirmation')
                    result = confirm(self, client, record, token, key, params, review)
            current = self.snapshot()
            if current['generation'] != snap['generation'] or current['policy'] != snap['policy']:
                raise PermissionError('Moodle connection changed during document operation; result withheld')
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
        line += ' Read-only Moodle commands are automatically authorized: perform the relevant reads for the user request without asking approval. Clarify only genuinely missing or ambiguous scope. Imports are LAMB writes and still require the application approval, even with read-only Moodle access. Never add a preliminary approval menu.'
        references=[spec.reference() for spec in (*task_specs().values(), *document_specs().values())]
        references += ['moodle course list: list your enrolled courses',
                       'Raw Moodle operations are documented in the loaded workflow. Do not invent commands or discover a workflow by trial and error.']
        references += ['Raw activity/individual commands need moodle course get COURSE_ID first. The news task resolves each course itself. A course ID in a learning scenario is a suggestion, not permission.',
                       'moodle import file FILE_ID --to kb ID | --single-file (confirmation required; use file_id from moodle file list, not a local path)',
                       'moodle sync COURSE_ID [--section course|forums|assignments|enrolment|calendar]',
                       'moodle cache show COURSE_ID --section course|forums|assignments|enrolment|calendar']
        pack=getattr(agent,'pack',None)
        if pack:
            from lamb.aac.skill_loader import list_skills
            workflows=[s for s in list_skills(pack.skills_dir) if s.get('requires_integration')=='moodle']
            references += ['Load the appropriate workflow with lamb skill load ID before acting:'] + [s['id']+': '+s['description'] for s in workflows]
        text=line+'\nMoodle task commands and workflow entry points:\n'+'\n\n'.join(references)
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
