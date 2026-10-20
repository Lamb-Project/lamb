"""Document read cancellation and source-course authority (#528, #529)."""
import asyncio
import threading
from types import SimpleNamespace as N
from unittest.mock import patch
import pytest

def test_cancelled_document_read_does_not_start_helper():
    from lamb.moodle.runtime import MoodleRuntime
    from lamb.moodle.policy import MoodlePolicy
    from lamb.moodle import runtime as rt
    cancel=threading.Event(); cancel.set()
    record={'base_url':'https://m.example','moodle_user_id':9,'token_encrypted':'test'}
    store=N(organization_id=1,owner_id=2,snapshot=lambda: {'policy':MoodlePolicy(True,'https://m.example'), 'record':record, 'generation':1})
    runtime=MoodleRuntime(store,cipher=N(decrypt=lambda *a,**kw:'dummy'),context={'generation':1,'document_scope':'c','course_id':50},owner_email='owner@example.test')
    with patch.object(rt,'MoodleHTTPClient'), patch('lamb.moodle.reading.read_source',return_value={'read_id':'dummy'}) as read:
        try: runtime.execute('file.read',{'source_ref':'mf_x'},cancel=cancel)
        except (InterruptedError, asyncio.CancelledError): pass
        read.assert_not_called()


def test_readback_binding_follows_document_course_not_latest_selection(tmp_path):
    from lamb.aac.liteshell.shell import LiteShell
    from lamb.moodle import reading
    snapshot={'kind':'document_read','scope':'conversation','source':{'course_id':10,'title':'Private course A','filename':'a.txt'},'passages':[{'id':i,'page':i,'heading':None,'text':'private text '*100} for i in range(1,160)], 'overview':{'outline':[]}}
    runtime=N(context={'course_id':20,'document_scope':'conversation'},result_binding=lambda:{'generation':1,'base_url':'https://m.example','moodle_user_id':9})
    def execute(key,params,**kw):
        with patch.object(reading,'load',return_value=snapshot), patch('lamb.aac.helper_model.helper_target',return_value={'provider':'fake','model':'fake'}), patch.object(reading,'helper_call',return_value='supported summary '*400):
            return reading.followup(runtime,None,{},key,params,None,'owner@example.test')
    runtime.execute=execute
    shell=LiteShell('', 'dummy','owner@example.test',1,user_id=2,moodle=runtime)
    command = 'moodle read summary read-1'
    result=asyncio.run(shell.execute(command))
    assert result.success and result.data['filename']=='a.txt'
    from lamb.aac.result_store import encode, RESULT_BYTES
    assert len(encode(result.to_dict())) > RESULT_BYTES  # causes private AAC result caching
    from lamb.aac.result_store import ResultStore
    store = ResultStore(1, 2, root=tmp_path.resolve() / 'results')
    with patch('lamb.aac.result_store.ResultStore', return_value=store):
        projected = shell.model_result(command, result.to_dict())
    assert projected['context_result']['stored']
    saved = store.read(projected['context_result']['result_id'])
    # Exercise the same current-authority check used by generic result readback.
    # Course A has now been revoked, while B remains available.
    from lamb.moodle.runtime import MoodleRuntime
    from lamb.moodle import runtime as rt
    checked = []
    def require_teacher(course):
        checked.append(course)
        if course == 10:
            raise PermissionError('Source course access revoked')
        return course
    validator = MoodleRuntime(N(), cipher=N(decrypt=lambda *a, **kw: 'dummy'))
    validator.result_binding = runtime.result_binding
    validator.available = lambda: {'moodle.read.summary'}
    validator.snapshot = lambda: {'record': {'base_url': 'https://m.example', 'moodle_user_id': 9, 'token_encrypted': 'dummy'}}
    validator.store = N(organization_id=1, owner_id=2)
    with patch.object(rt, 'MoodleHTTPClient'), patch.object(rt, 'MoodleScope') as scope:
        scope.return_value.require_teacher.side_effect = require_teacher
        try:
            validator.validate_result_binding(saved['origin']['moodle'], 'moodle.read.summary')
        except PermissionError:
            pass
    assert saved['origin']['moodle']['course_id'] == 10 and checked == [10]


@pytest.mark.parametrize('key', ['file.read', 'page.read', 'book.read', 'read.summary', 'read.ask', 'read.verbatim'])
def test_legacy_document_cache_binding_is_rejected(key):
    from lamb.moodle.runtime import MoodleRuntime
    runtime = MoodleRuntime(N())
    with pytest.raises(PermissionError, match='source-course'):
        runtime.validate_result_binding({'course_id': 20}, 'moodle.' + key)


@pytest.mark.parametrize('operation', ['overview', 'read.summary', 'read.ask'])
def test_cancellation_during_helper_stops_remaining_chunks(operation):
    from lamb.moodle import reading
    cancel = threading.Event()
    passages = [{'id': i, 'page': i, 'heading': None, 'text': 'x' * 1500} for i in range(1, 150)]
    snapshot = {'source': {'course_id': 10, 'title': 'Lesson', 'filename': 'lesson.txt'}, 'passages': passages}
    def answer(*args, **kwargs):
        cancel.set()
        return 'partial answer'
    with patch.object(reading, 'helper_call', side_effect=answer) as helper, \
            patch.object(reading, 'load', return_value=snapshot), \
            patch('lamb.aac.helper_model.helper_target', return_value={'provider': 'fake', 'model': 'fake'}):
        with pytest.raises(InterruptedError):
            if operation == 'overview':
                reading.overview({}, 'Lesson', passages, cancel=cancel)
            else:
                reading.followup(N(), None, {}, operation, {'read_id': 'r1', 'question': 'What?'}, None, 'owner', cancel=cancel)
        assert helper.call_count == 1


@pytest.mark.parametrize('stage', ['materialize', 'convert', 'helper'])
def test_cancelled_source_read_does_not_publish_snapshot(stage):
    from lamb.moodle import reading
    from lamb.moodle.documents import Download
    from unittest.mock import Mock
    cancel = threading.Event()
    results = Mock()
    source = {'kind': 'file', 'course_id': 50, 'module_id': 7, 'title': 'l1.txt'}
    def stop(value):
        cancel.set()
        return value
    material = (Download('l1.txt', b'Lesson', 'text/plain'), {}, {})
    converted = ([(1, None, 'Lesson')], {}, 1)
    with patch.object(reading, 'resolve_source', return_value=(source, None)), \
            patch.object(reading, 'materialize', side_effect=lambda *a, **k: stop(material) if stage == 'materialize' else material), \
            patch.object(reading, 'convert', side_effect=lambda *a: stop(converted) if stage == 'convert' else converted), \
            patch('lamb.aac.helper_model.helper_target', return_value={'provider': 'fake', 'model': 'fake'}), \
            patch.object(reading, 'helper_call', side_effect=lambda *a, **k: stop('{}')) as helper:
        with pytest.raises(InterruptedError):
            reading.read_source(N(context={'document_scope': 'c'}), None, {'base_url': 'https://m.example', 'moodle_user_id': 9},
                                'token', 'file.read', {'source_ref': 'mf_x'}, results, 'owner', cancel=cancel)
        results.save.assert_not_called()
        assert helper.call_count == (1 if stage == 'helper' else 0)


@pytest.mark.parametrize('command', [
    'moodle file read mf_x', 'moodle page read mp_x', 'moodle book read mb_x',
    'moodle read summary r1', 'moodle read ask r1 "Question?"',
    'moodle read verbatim r1 --passages p1',
])
def test_all_document_results_bind_to_source_not_selected_course(command):
    from lamb.aac.liteshell.shell import LiteShell
    runtime = N(context={'course_id': 20}, result_binding=lambda: {'generation': 1},
                execute=lambda *a, **k: {'source': {'course_id': 10}})
    result = asyncio.run(LiteShell('', 'token', 'owner', 1, user_id=2, moodle=runtime).execute(command))
    assert result.success
    assert result.result_binding == {'generation': 1, 'course_id': 10, 'document_scope_version': 1}
