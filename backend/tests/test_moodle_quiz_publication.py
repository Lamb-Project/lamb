import json
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from lamb.moodle.analytics.quiz_run import start, publish
from lamb.moodle.analytics.quiz_state import advance_cursor
from lamb.moodle.charts import ChartStore, render_svg
from tests.test_moodle_quiz_run import store
from tests.test_moodle_quiz_state import page


def fixture(tmp_path, language='en'):
    s = store(tmp_path)
    record = start(s, 9, 7, policy='all_finished', language=language, tz='Europe/Madrid')
    state = record['state']
    response = page()
    response.update(throughid=2, has_more=False)
    response['attempts'][0]['userid'] = 91234561
    response['attempts'][1].update(userid=91234562, sumgrades=None)
    state.update(started_at='2026-09-23T10:00:00+00:00', completed_at='2026-09-23T10:01:00+00:00',
        done=True, cursor=advance_cursor(state['cursor'], 0, response),
        context={'students': [91234561, 91234562, 91234563], 'private_extra': 'PRIVATE_SENTINEL'})
    s.replace(record['id'], state, expected_revision=0)
    binding = {'generation': 'one', 'base_url': 'https://fixture.test', 'moodle_user_id': 3}
    rt = SimpleNamespace(cache_root=tmp_path/'moodle', store=SimpleNamespace(organization_id=1, owner_id=2),
        result_binding=lambda: dict(binding), validate_result_binding=lambda *args: None)
    return s, rt, SimpleNamespace(checkpoint=lambda: None), record['id']


@pytest.mark.parametrize('language', ['en', 'es', 'ca', 'eu'])
def test_localized_aggregate_projection_and_idempotent_save(tmp_path, language):
    s, rt, client, identity = fixture(tmp_path, language)
    result = publish(s, rt, client, identity)
    saved = ChartStore(rt).read(result['chart_id'])
    assert saved['language'] == language and saved['timezone'] == 'Europe/Madrid'
    assert saved['as_of_local'] == '2026-09-23T12:01:00+02:00'
    assert saved['quiz_scopes'] == [{'course_id': 9, 'quiz_id': 7, 'group_id': 0}]
    assert saved['metrics']['selected_attempts'] == 2 and saved['metrics']['ungraded_selected_attempts'] == 1
    assert sum(row['value'] for row in saved['rows']) == 1 and saved['rows'][0]['value'] == 1
    assert saved['coverage']['complete'] is False and saved['coverage']['collection_complete'] is True
    assert saved['metrics']['pass_percent'] is None
    encoded = json.dumps(saved)
    for private in ('9123456', 'PRIVATE_SENTINEL', 'userid', 'timemodified', 'fingerprint'):
        assert private not in encoded
    assert publish(s, rt, client, identity) == result
    assert len(list(ChartStore(rt).root.glob('*.json'))) == 1
    assert '<svg' in render_svg(saved)


def test_lost_save_response_and_failed_ack_recover_same_snapshot(tmp_path):
    s, rt, client, identity = fixture(tmp_path)
    original = ChartStore.save
    def fail_after_save(*args, **kwargs):
        original(*args, **kwargs)
        raise OSError('Lost response')
    with patch.object(ChartStore, 'save', fail_after_save), pytest.raises(OSError):
        publish(s, rt, client, identity)
    frozen = s.read(identity)['state']['publication']
    replace = s.replace
    def fail_ack(key, state, **kwargs):
        if state.get('published'):
            raise OSError('Lost acknowledgement')
        return replace(key, state, **kwargs)
    with patch.object(s, 'replace', fail_ack), pytest.raises(OSError):
        publish(s, rt, client, identity)
    result = publish(s, rt, client, identity)
    assert result['chart_id'] == frozen['id']
    assert len(list(ChartStore(rt).root.glob('*.json'))) == 1


def test_revocation_and_connection_change_deny_publication(tmp_path):
    s, rt, client, identity = fixture(tmp_path)
    publish(s, rt, client, identity)
    def deny(*args):
        raise PermissionError('Revoked')
    rt.validate_result_binding = deny
    with pytest.raises(PermissionError):
        publish(s, rt, client, identity)
    rt.result_binding = lambda: {'generation': 'other'}
    with pytest.raises(PermissionError, match='another connection'):
        publish(s, rt, client, identity)


@pytest.mark.parametrize('defect', ['unfinished', 'reversed_time', 'naive_time'])
def test_unfinished_or_invalid_interval_cannot_publish(tmp_path, defect):
    s, rt, client, identity = fixture(tmp_path)
    record = s.read(identity); state = record['state']
    if defect == 'unfinished':
        state['cursor']['done'] = False
    elif defect == 'reversed_time':
        state['completed_at'] = '2026-09-22T00:00:00+00:00'
    else:
        state['completed_at'] = '2026-09-23T10:01:00'
    s.replace(identity, state, expected_revision=record['revision'])
    with pytest.raises(ValueError):
        publish(s, rt, client, identity)
    assert not list((tmp_path/'moodle'/'charts').glob('**/*.json'))
