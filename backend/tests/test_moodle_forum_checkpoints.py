import os
from unittest.mock import patch
import pytest
from lamb.moodle.analytics.forum_checkpoints import ForumCheckpoints
from lamb.moodle.analytics.forum_state import initial_cursor
from lamb.moodle.results import ResultStore
from lamb.private_storage import file_lock, atomic_json
from lamb.storage_lifecycle import OwnerStorage
from tests.test_moodle_forum_state import page


def store(tmp_path, **changes):
    params = dict(organization_id=1,owner_id=2,base_url='https://fixture.test',
                  moodle_user_id=3,generation='one',root=tmp_path/'moodle')
    params.update(changes)
    return ForumCheckpoints(ResultStore(**params))


def test_durable_page_roundtrip_and_replay(tmp_path):
    s=store(tmp_path); record=s.create({'cursor':initial_cursor(7,8,9)})
    identity=record['id']; expiry=record['expires_at']
    updated=s.acknowledge_page(identity,0,page(),expected_revision=0)
    fresh=store(tmp_path)
    assert fresh.read(identity)==updated
    assert fresh.acknowledge_page(identity,0,page(),expected_revision=0)==updated
    assert fresh.read(identity)['revision']==1
    assert updated['expires_at']==expiry
    assert os.stat(s.folder).st_mode & 0o777 == 0o700
    assert os.stat(s._path(identity)).st_mode & 0o777 == 0o600
    with pytest.raises(ValueError,match='advanced'):
        fresh.acknowledge_page(identity,2,page((3,),more=False),expected_revision=0)
    final=fresh.acknowledge_page(identity,2,page((3,),more=False),expected_revision=1)
    assert final['state']['cursor']['done'] and final['revision']==2


@pytest.mark.parametrize('changes', [{'owner_id':9},{'organization_id':2},
    {'base_url':'https://other.test'},{'moodle_user_id':4},{'generation':'two'}])
def test_foreign_binding_denied_before_page_ack(tmp_path,changes):
    s=store(tmp_path); saved=s.create({'cursor':initial_cursor(7,8,9)})
    with pytest.raises(PermissionError):
        store(tmp_path,**changes).acknowledge_page(saved['id'],0,page(),expected_revision=0)
    assert s.read(saved['id'])==saved


def test_lost_fsync_response_reuses_saved_page(tmp_path):
    s=store(tmp_path); saved=s.create({'cursor':initial_cursor(7,8,9)})
    with patch('lamb.private_storage.sync_directory',side_effect=OSError()):
        with pytest.raises(ValueError):s.acknowledge_page(saved['id'],0,page(),expected_revision=0)
    fresh=store(tmp_path)
    assert fresh.read(saved['id'])['revision']==1
    with patch('lamb.moodle.analytics.forum_checkpoints.sync_directory') as sync:
        assert fresh.acknowledge_page(saved['id'],0,page(),expected_revision=0)['revision']==1
    sync.assert_called_once_with(fresh.folder)
    with patch('lamb.moodle.analytics.forum_checkpoints.sync_directory',side_effect=OSError('PRIVATE PATH')):
        with pytest.raises(ValueError,match='durability') as error:
            fresh.acknowledge_page(saved['id'],0,page(),expected_revision=0)
        assert 'PRIVATE PATH' not in str(error.value)
    assert fresh.read(saved['id'])['revision']==1


def test_failed_atomic_replace_keeps_prior_state(tmp_path):
    s=store(tmp_path); saved=s.create({'cursor':initial_cursor(7,8,9)})
    with patch('lamb.private_storage.os.replace',side_effect=OSError()):
        with pytest.raises(ValueError):s.acknowledge_page(saved['id'],0,page(),expected_revision=0)
    assert s.read(saved['id'])==saved


def test_bounds_lock_and_expiry(tmp_path):
    s=store(tmp_path); saved=s.create({'cursor':initial_cursor(7,8,9)})
    with s.execution_lock():
        with pytest.raises(ValueError):s.acknowledge_page(saved['id'],0,page(),expected_revision=0)
    for _ in range(3):s.create({})
    with pytest.raises(ValueError,match='quota'):s.create({})
    with pytest.raises(ValueError,match='storage limit'):
        s.replace(saved['id'],{'oversized':'x'*s.max_bytes},expected_revision=0)
    atomic_json(s._path(saved['id']),dict(saved,expires_at=1))
    with pytest.raises(PermissionError):s.read(saved['id'])


def test_lifecycle_inspects_only_sizes_and_removes_only_expired(tmp_path):
    s=store(tmp_path)
    with patch('lamb.moodle.analytics.checkpoints.time.time',return_value=100):
        expired=s.create({'cursor':initial_cursor(7,8,9)})
    live=s.create({'private_author_ids':[98765]})
    owner=OwnerStorage(1,2,root=tmp_path)
    inventory=owner.inspect()['stores']['forum_analytics_runs']
    assert inventory['records']==2 and inventory['quota_bytes']==4*s.max_bytes
    assert '98765' not in str(inventory)
    assert owner.clean()['removed_records']==1
    assert not s._path(expired['id']).exists() and s.read(live['id'])==live


def test_unverifiable_expiry_is_preserved_and_unreadable(tmp_path):
    s=store(tmp_path);record=s.create({})
    atomic_json(s._path(record['id']),dict(record,expires_at='unknown'))
    with pytest.raises(PermissionError):s.read(record['id'])
    with pytest.raises(ValueError,match='expiry'):OwnerStorage(1,2,root=tmp_path).clean()
    assert s._path(record['id']).exists()


def test_thousand_posts_recover_in_new_workers(tmp_path):
    s=store(tmp_path);record=s.create({'cursor':initial_cursor(7,8,9)})
    for after in range(0,1000,200):
        source=page(tuple(range(after+1,after+201)),through=1000,more=after<800)
        for row in source['posts']:row.update(created=100,modified=100)
        s=store(tmp_path)
        record=s.acknowledge_page(record['id'],after,source,expected_revision=record['revision'])
        assert len(record['state']['cursor']['records'])==after+200
        assert store(tmp_path).acknowledge_page(record['id'],after,source,
            expected_revision=record['revision']-1)==record
    assert record['state']['cursor']['done'] and record['revision']==5
