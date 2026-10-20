import json
from pathlib import Path
import pytest
from lamb.moodle.cache import CourseCache, CacheConflict


def cache(root,org=1,owner=7,uid=70):
    return CourseCache(org,owner,base_url='https://moodle.test',moodle_user_id=uid,root=root)


def test_sections_keep_independent_times_previous_snapshot_and_deltas(tmp_path):
    c=cache(tmp_path)
    c.update(10,{'forums':[{'id':1,'discussions':[{'id':100,'discussion':11}]}],
                 'course':{'id':10,'fullname':'Demo'}},synced_at='2026-09-18T10:00:00+00:00')
    c.update(10,{'forums':[{'id':1,'discussions':[{'id':100,'discussion':11},{'id':101,'discussion':12}]}]},synced_at='2026-09-18T11:00:00+00:00')
    state=c.read(10)
    assert state['sections']['course']['synced_at']=='2026-09-18T10:00:00+00:00'
    assert state['sections']['forums']['previous']['data'][0]['discussions']==[{'id':100,'discussion':11}]
    text=c.show(10,'forums');assert text.startswith('Synced at: 2026-09-18T11:00:00+00:00\n')
    delta=json.loads(text.split('\n',1)[1])['delta']
    assert delta['new']==1 and delta['unit']=='discussions' and not delta['baseline']
    assert not (tmp_path/'1/7/course-cache/10.json').stat().st_mode & 0o077


def test_owner_org_and_reconnected_source_are_separate(tmp_path):
    c=cache(tmp_path);c.update(10,{'course':{'id':10}})
    assert not cache(tmp_path,owner=8).read(10)['sections']
    assert not cache(tmp_path,org=2).read(10)['sections']
    other=cache(tmp_path,uid=80)
    with pytest.raises(CacheConflict):other.read(10)
    other.update(10,{'forums':[]})
    assert set(other.read(10)['sections'])=={'forums'}


def test_older_sync_cannot_overwrite_newer_and_failed_write_leaves_valid_state(tmp_path,monkeypatch):
    c=cache(tmp_path);c.update(10,{'calendar':[]},synced_at='2026-09-18T12:00:00+00:00')
    with pytest.raises(CacheConflict):c.update(10,{'calendar':[{'id':1}]},synced_at='2026-09-18T11:00:00+00:00')
    import lamb.moodle.cache as module
    def fail(*args):raise OSError('fixture failure')
    monkeypatch.setattr(module.os,'replace',fail)
    with pytest.raises(OSError):c.update(10,{'calendar':[{'id':2}]},synced_at='2026-09-18T13:00:00+00:00')
    assert c.read(10)['sections']['calendar']['data']==[]
    assert not list(tmp_path.rglob('.write-*'))


def test_cache_rejects_paths_and_symlinks(tmp_path):
    c=cache(tmp_path)
    for value in ['../10',True,0,-1]:
        with pytest.raises(ValueError):c.read(value)
    c.update(10,{'enrolment':[]})
    path=tmp_path/'1/7/course-cache/20.json';path.symlink_to(tmp_path/'1/7/course-cache/10.json')
    with pytest.raises(ValueError):c.read(20)
