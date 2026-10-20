"""Bounded pre-plugin repairs; no external services or real student data."""
import json
import uuid
from unittest.mock import Mock, patch

import pytest

from lamb.moodle.scoped_reads import execute_scoped_read
from lamb.moodle.runs import RunStore
from lamb.moodle.results import ResultStore
from lamb.private_storage import atomic_json, data_root, file_lock
from lamb.storage_lifecycle import OwnerStorage
from tests.test_moodle_tasks import PARAMS


def evidence(tmp_path):
    return ResultStore(1, 7, base_url='https://example.invalid', moodle_user_id=70,
                       generation=1, root=tmp_path/'moodle')


def test_roster_minimized_before_model_readback():
    with patch('lamb.moodle.scoped_reads.MoodleScope') as scope:
        scope.return_value.require_teacher.return_value = 7
        scope.return_value.class_roster.return_value = {
            8:{'id':8,'fullname':'Student','email':'private@example.invalid','username':'private',
               'roles':[{'id':5,'shortname':'student','name':'Student'}], 'lastaccess':123,'groups':[2]},
            9:{'id':9,'fullname':'Teacher','roles':[{'shortname':'teacher'}]}}
        value = execute_scoped_read(Mock(readonly=True), 'enrol.list-users',
            {'course_id':7,'role':'student'}, owner_moodle_id=70, context={})
    assert value == [{'id':8,'fullname':'Student','roles':[{'shortname':'student'}]}]


@pytest.mark.parametrize('raw', [b'{}', b'not-json', b'[]', b'{"expires_at":true}',
    b'{"expires_at":NaN,"last_result":null,"working":null,"next_results":{}}',
    b'{"expires_at":1,"last_result":null,"working":null,"next_results":[]}'])
def test_malformed_run_preserved_and_other_work_can_proceed(tmp_path, raw):
    results = evidence(tmp_path)
    first = results.save({'original':'keep'})
    path = results.folder/(first+'.json')
    saved = json.loads(path.read_text()); saved['expires_at'] = 1
    atomic_json(path, saved)
    original = path.read_bytes()
    runs = RunStore(results)
    with runs.lock():
        corrupt = runs.folder/(str(uuid.uuid4())+'.json')
        corrupt.write_bytes(raw)
        created = runs.create(PARAMS)
    second = results.save({'new':'allowed below quota'})
    cleaned = OwnerStorage(1,7,root=tmp_path).clean()
    assert cleaned['unreadable_runs_preserved'] == 1
    assert corrupt.read_bytes() == raw and path.read_bytes() == original
    assert results.read(second) == {'new':'allowed below quota'}
    assert runs.read(created['id'])['state']['steps'] == 0
    with pytest.raises(PermissionError): runs.read(corrupt.stem)


def test_unknown_references_never_evict_at_quota(tmp_path, monkeypatch):
    results = evidence(tmp_path)
    first = results.save({'keep':True})
    runs = RunStore(results)
    with runs.lock(): atomic_json(runs.folder/(str(uuid.uuid4())+'.json'), {})
    monkeypatch.setattr('lamb.moodle.results.MAX_RESULTS', 1)
    with pytest.raises(ValueError, match='preserved unreadable references'):
        results.save({'must not evict':True})
    assert results.read(first) == {'keep':True}


def test_corrupt_runs_still_count_against_run_quota(tmp_path, monkeypatch):
    runs = RunStore(evidence(tmp_path))
    monkeypatch.setattr('lamb.moodle.runs.MAX_RUNS', 1)
    with runs.lock():
        path = runs.folder/(str(uuid.uuid4())+'.json')
        atomic_json(path, {})
        with pytest.raises(ValueError, match='administrator'):
            runs.create(PARAMS)
    assert json.loads(path.read_text()) == {}


def test_unsafe_link_remains_denied(tmp_path):
    results = evidence(tmp_path); runs = RunStore(results)
    target = tmp_path/'outside.json'; target.write_text('{}')
    with runs.lock():
        (runs.folder/(str(uuid.uuid4())+'.json')).symlink_to(target)
        with pytest.raises(RuntimeError, match='Unsafe'): runs.create(PARAMS)
    with pytest.raises(ValueError, match='Unsafe'): results.save({})
    assert target.read_text() == '{}'


def test_lock_contention_is_transient_and_retry_does_not_need_redesign(tmp_path):
    runs = RunStore(evidence(tmp_path))
    with file_lock(runs.folder, blocking=False):
        with pytest.raises(ValueError, match='already running'):
            with runs.lock(): pass
    with runs.lock(): created = runs.create(PARAMS)
    assert runs.read(created['id'])['id'] == created['id']
    OwnerStorage(1,7,root=tmp_path).clean()
    assert runs.read(created['id'])['id'] == created['id']


def test_storage_root_contract_stays_explicit(tmp_path, monkeypatch):
    monkeypatch.delenv('LAMB_DB_PATH', raising=False)
    with pytest.raises(ValueError, match='absolute'): data_root()
    monkeypatch.setenv('LAMB_DB_PATH', 'relative')
    with pytest.raises(ValueError, match='absolute'): data_root()
    monkeypatch.setenv('LAMB_DB_PATH', str(tmp_path/'private'))
    assert data_root() == tmp_path/'private'
