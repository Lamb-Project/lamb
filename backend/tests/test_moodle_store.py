import json
import sqlite3
from types import SimpleNamespace
import pytest
from lamb.moodle.store import ConnectionStore, ConnectionConflict

@pytest.fixture
def stores(tmp_path):
    path=tmp_path/'fixture.db'
    with sqlite3.connect(path) as c:
        c.executescript('CREATE TABLE organizations(id INTEGER PRIMARY KEY, config TEXT,status TEXT,updated_at INTEGER);CREATE TABLE Creator_users(id INTEGER PRIMARY KEY,organization_id INTEGER,user_config TEXT,updated_at INTEGER);')
        config={'moodle':{'enabled':True,'base_url':'https://moodle.test'},'other':'preserve'}
        for org in (1,2): c.execute('INSERT INTO organizations VALUES(?,?,?,0)',(org,json.dumps(config),'active'))
        for owner,org in [(7,1),(8,1),(9,2)]:c.execute('INSERT INTO Creator_users VALUES(?,?,?,0)',(owner,org,json.dumps({'preferences':{'theme':'dark'}})))
    db=SimpleNamespace(table_prefix='',get_connection=lambda:sqlite3.connect(path))
    return db,ConnectionStore(db,1,7)


def record():
    return {'base_url':'https://moodle.test','moodle_user_id':70,'username':'fixture','token_encrypted':'ciphertext','connected_at':'now'}


def test_save_disconnect_preserve_other_config_and_isolation(stores):
    db,store=stores;snap=store.snapshot()
    result=store.save(record(),expected_generation=snap['generation'],expected_policy=snap['policy'])
    assert 'token_encrypted' not in result
    assert store.snapshot()['record']['token_encrypted']=='ciphertext'
    assert ConnectionStore(db,1,8).snapshot()['record'] is None
    assert ConnectionStore(db,2,9).snapshot()['record'] is None
    with pytest.raises(PermissionError):ConnectionStore(db,2,7).snapshot()
    store.disconnect()
    assert store.snapshot()['record'] is None
    with db.get_connection() as c:
        user=json.loads(c.execute('SELECT user_config FROM Creator_users WHERE id=7').fetchone()[0])
    assert user['preferences']=={'theme':'dark'}
    assert 'ciphertext' not in json.dumps(user)


def test_inflight_connect_cannot_resurrect_after_disconnect(stores):
    _,store=stores;snap=store.snapshot();store.disconnect()
    with pytest.raises(ConnectionConflict):store.save(record(),expected_generation=snap['generation'],expected_policy=snap['policy'])


def test_policy_change_during_exchange_blocks_save(stores):
    db,store=stores;snap=store.snapshot();store.configure({'enabled':False})
    with pytest.raises(ConnectionConflict):store.save(record(),expected_generation=snap['generation'],expected_policy=snap['policy'])
    with db.get_connection() as c:
        org=json.loads(c.execute('SELECT config FROM organizations WHERE id=1').fetchone()[0])
    assert org['other']=='preserve'
    assert not store.snapshot()['policy'].enabled
    assert ConnectionStore(db,2,9).snapshot()['policy'].enabled
