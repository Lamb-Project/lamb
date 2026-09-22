import json
import os
from unittest.mock import patch
import pytest

from lamb.moodle.analytics.checkpoints import CompletionCheckpoints, MAX_CHECKPOINT_BYTES, MAX_CHECKPOINTS
from lamb.moodle.results import ResultStore
from lamb.private_storage import file_lock, atomic_json
from lamb.storage_lifecycle import OwnerStorage


def store(tmp_path, **changes):
    params=dict(organization_id=1,owner_id=2,base_url='https://fixture.test',moodle_user_id=3,generation='one',root=tmp_path/'moodle')
    params.update(changes)
    return CompletionCheckpoints(ResultStore(**params))


def test_roundtrip_revision_expiry_and_private_modes(tmp_path):
    s=store(tmp_path)
    state={'students':[1,2],'next_student':0,'rows':[]}
    saved=s.create(state)
    state['students'].append(99)
    assert s.read(saved['id'])['state']['students']==[1,2]
    next_state=dict(saved['state'],next_student=1)
    updated=s.replace(saved['id'],next_state,expected_revision=0)
    assert updated['revision']==1 and updated['expires_at']==saved['expires_at']
    assert s.read(saved['id'])==updated
    assert os.stat(s.folder).st_mode & 0o777==0o700
    assert os.stat(s._path(saved['id'])).st_mode & 0o777==0o600
    with pytest.raises(ValueError,match='advanced'):s.replace(saved['id'],next_state,expected_revision=0)
    assert s.read(saved['id'])==updated


@pytest.mark.parametrize('changes',[{'generation':'two'},{'moodle_user_id':4},{'base_url':'https://other.test'},
    {'organization_id':2},{'owner_id':4}])
def test_other_connections_and_owners_cannot_read_or_replace(tmp_path,changes):
    s=store(tmp_path); saved=s.create({'students':[100]})
    other=store(tmp_path,**changes)
    with pytest.raises(PermissionError):other.read(saved['id'])
    with pytest.raises(PermissionError):other.replace(saved['id'],{},expected_revision=0)
    assert s.read(saved['id'])==saved


def test_failed_replace_preserves_last_durable_revision(tmp_path):
    s=store(tmp_path);saved=s.create({'next_student':0})
    with patch('lamb.private_storage.os.replace',side_effect=OSError('private-path')):
        with pytest.raises(ValueError,match='recover the stored revision'):
            s.replace(saved['id'],{'next_student':1},expected_revision=0)
    assert s.read(saved['id'])==saved
    assert not list(s.folder.glob('.pending-*'))


def test_failure_after_replace_can_be_recovered_without_stale_overwrite(tmp_path):
    s=store(tmp_path); saved=s.create({'next_student':0})
    with patch('lamb.private_storage.sync_directory',side_effect=OSError()):
        with pytest.raises(ValueError):s.replace(saved['id'],{'next_student':1},expected_revision=0)
    recovered=s.read(saved['id'])
    assert recovered['revision']==1 and recovered['state']['next_student']==1
    with pytest.raises(ValueError,match='advanced'):s.replace(saved['id'],{},expected_revision=0)


def test_quota_does_not_evict_existing_recovery_handles(tmp_path):
    s=store(tmp_path); runs=[s.create({}) for _ in range(MAX_CHECKPOINTS)]
    with pytest.raises(ValueError,match='quota'):s.create({})
    assert all(s.read(run['id'])==run for run in runs)


def test_oversize_update_leaves_existing_state_intact(tmp_path):
    s=store(tmp_path); saved=s.create({})
    with pytest.raises(ValueError,match='storage limit'):
        s.replace(saved['id'],{'large':'x'*MAX_CHECKPOINT_BYTES},expected_revision=0)
    assert s.read(saved['id'])==saved


def test_busy_store_rejects_parallel_access(tmp_path):
    s=store(tmp_path); saved=s.create({})
    with file_lock(s.folder):
        with pytest.raises(ValueError,match='busy'):s.read(saved['id'])
        with pytest.raises(ValueError,match='busy'):s.replace(saved['id'],{},expected_revision=0)


def test_expiry_inspection_and_cleanup_leave_live_runs(tmp_path):
    s=store(tmp_path)
    with patch('lamb.moodle.analytics.checkpoints.time.time',return_value=100):old=s.create({'students':[99]})
    live=s.create({'students':[100]})
    with pytest.raises(PermissionError):s.read(old['id'])
    owner=OwnerStorage(1,2,root=tmp_path)
    inventory=owner.inspect()['stores']['completion_runs']
    assert inventory['records']==2 and inventory['quota_bytes']==MAX_CHECKPOINTS*MAX_CHECKPOINT_BYTES
    assert 'students' not in str(inventory)
    result=owner.clean()
    assert result['removed_records']==1
    assert s.read(live['id'])==live
    assert not s._path(old['id']).exists()


def test_symlink_record_cannot_read_or_replace_target(tmp_path):
    s=store(tmp_path); saved=s.create({})
    target=tmp_path/'target.json';atomic_json(target,saved)
    path=s._path(saved['id']);path.unlink();path.symlink_to(target)
    with pytest.raises(PermissionError):s.read(saved['id'])
    with pytest.raises(PermissionError):s.replace(saved['id'],{},expected_revision=0)
    assert json.loads(target.read_text())==saved


@pytest.mark.parametrize('expiry',[None,True,float('nan'),'tomorrow'])
def test_unverifiable_expiry_is_not_readable_or_cleaned(tmp_path,expiry):
    s=store(tmp_path); saved=s.create({});saved['expires_at']=expiry
    atomic_json(s._path(saved['id']),saved)
    with pytest.raises(PermissionError):s.read(saved['id'])
    with pytest.raises(ValueError,match='expiry'):OwnerStorage(1,2,root=tmp_path).clean()
    assert s._path(saved['id']).exists()


def test_500_learner_disk_checkpoints_recover_in_a_new_store_instance(tmp_path):
    from lamb.moodle.analytics.completion_state import initial_cursor, advance_cursor
    from tests.test_moodle_completion_state import row, response
    s=store(tmp_path)
    saved=s.create(initial_cursor(range(1,501),[row(10),row(20)]))
    identity=saved['id']
    for start in range(1,501,17):
        # Simulate a new worker with only the durable recovery handle.
        s=store(tmp_path); durable=s.read(identity); working=durable['state']
        for learner in range(start,min(start+17,501)):
            working=advance_cursor(working,learner,response((learner-1)%4))
        updated=s.replace(identity,working,expected_revision=durable['revision'])
        # A lost response cannot let the old worker overwrite newer progress.
        with pytest.raises(ValueError,match='advanced'):
            s.replace(identity,working,expected_revision=durable['revision'])
        assert store(tmp_path).read(identity)==updated
    final=store(tmp_path).read(identity)['state']
    assert final['next_student']==500
    for counts in final['rows']:
        assert [counts[key] for key in ('incomplete','complete','complete_pass','complete_fail')]==[125]*4
        assert counts['overall_complete']==375
