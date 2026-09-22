"""Recover a lost publication response without duplicating or changing evidence."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from unittest.mock import patch
import uuid
import os
import pytest

from lamb.moodle.charts import ChartStore
from tests.test_moodle_charts import runtime, snapshot


def test_reserved_publication_reuses_exact_snapshot_even_at_quota(tmp_path):
    store=ChartStore(runtime(tmp_path));identity=str(uuid.uuid4());data=snapshot();binding={'course_id':2}
    assert store.save(data,binding,publication_id=identity)==identity
    with patch('lamb.moodle.charts.MAX_CHARTS',1):
        assert store.save(data,binding,publication_id=identity)==identity
        with pytest.raises(ValueError,match='storage is full'):store.save(data,binding)
    assert len(list(store.root.glob('*.json')))==1


@pytest.mark.parametrize('change',['snapshot','binding','command','type'])
def test_existing_publication_never_overwrites_conflicting_evidence(tmp_path,change):
    store=ChartStore(runtime(tmp_path));identity=str(uuid.uuid4());data=snapshot();binding={'course_id':2}
    store.save(data,binding,publication_id=identity)
    original=store.read(identity);other=deepcopy(data);changed_binding=dict(binding);command='moodle.chart.submissions'
    if change=='snapshot':other['rows'][0]['submitted']=99
    if change=='binding':changed_binding['course_id']=3
    if change=='command':command='moodle.analytics.run'
    if change=='type':other['coverage']['complete']=1
    with pytest.raises(ValueError,match='conflicts'):
        store.save(other,changed_binding,command=command,publication_id=identity)
    assert store.read(identity)==original


def test_retry_revalidates_current_permissions(tmp_path):
    rt=runtime(tmp_path);store=ChartStore(rt);identity=str(uuid.uuid4());data=snapshot()
    store.save(data,{'course_id':2},publication_id=identity)
    rt.validate_result_binding=lambda *_:(_ for _ in ()).throw(PermissionError('Revoked'))
    with pytest.raises(PermissionError,match='Revoked'):store.save(data,{'course_id':2},publication_id=identity)


def test_failure_before_replace_leaves_no_partial_chart(tmp_path):
    store=ChartStore(runtime(tmp_path));identity=str(uuid.uuid4());data=snapshot()
    with patch('lamb.private_storage.os.replace',side_effect=OSError()):
        with pytest.raises(OSError):store.save(data,{'course_id':2},publication_id=identity)
    assert not list(store.root.glob('*.json')) and not list(store.root.glob('.pending-*'))
    assert store.save(data,{'course_id':2},publication_id=identity)==identity


def test_failure_after_replace_recovers_same_id(tmp_path):
    store=ChartStore(runtime(tmp_path));identity=str(uuid.uuid4());data=snapshot()
    with patch('lamb.private_storage.sync_directory',side_effect=OSError()):
        with pytest.raises(OSError):store.save(data,{'course_id':2},publication_id=identity)
    with patch('lamb.moodle.charts.sync_directory',side_effect=OSError()):
        with pytest.raises(OSError):store.save(data,{'course_id':2},publication_id=identity)
    assert store.save(data,{'course_id':2},publication_id=identity)==identity
    assert len(list(store.root.glob('*.json')))==1


def test_concurrent_retries_publish_only_one_chart(tmp_path):
    store=ChartStore(runtime(tmp_path));identity=str(uuid.uuid4());data=snapshot()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:store.save(data,{'course_id':2},publication_id=identity),range(2)))
    assert results==[identity,identity] and len(list(store.root.glob('*.json')))==1


def test_corrupt_or_symlinked_publication_is_not_replaced(tmp_path):
    store=ChartStore(runtime(tmp_path));identity=str(uuid.uuid4());data=snapshot()
    store.save(data,{'course_id':2},publication_id=identity)
    path=store.root/(identity+'.json');path.write_text('broken')
    with pytest.raises(PermissionError):store.save(data,{'course_id':2},publication_id=identity)
    assert path.read_text()=='broken'
    target=tmp_path/'target';target.write_text('keep');path.unlink();path.symlink_to(target)
    with pytest.raises(PermissionError):store.save(data,{'course_id':2},publication_id=identity)
    assert target.read_text()=='keep'


def test_cleanup_removes_stale_atomic_temporary_not_durable_chart(tmp_path):
    from lamb.storage_lifecycle import OwnerStorage, TEMP_TTL
    rt=runtime(tmp_path);rt.cache_root=tmp_path/'moodle'
    store=ChartStore(rt);identity=store.save(snapshot(),{'course_id':2})
    temporary=store.root/'.pending-interrupted';temporary.write_text('unfinished')
    os.utime(temporary,(1,1))
    chart=store.root/(identity+'.json');os.utime(chart,(1,1))
    report=OwnerStorage(1,1,root=tmp_path).clean(now=TEMP_TTL+2)
    assert report['removed_records']==1 and not temporary.exists()
    assert chart.exists() and store.read(identity)['chart_id']==identity
