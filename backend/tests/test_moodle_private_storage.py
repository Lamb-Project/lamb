from pathlib import Path
import pytest
from lamb.moodle.storage import migrate_legacy_cache


def test_migration_archives_exact_bytes_outside_static_and_is_repeatable(tmp_path):
    legacy = tmp_path / 'static/public/.moodle'
    source = legacy / '1/7/course-cache/2.json'
    source.parent.mkdir(parents=True); source.write_bytes(b'{"private":"fixture"}')
    target = tmp_path / 'data/moodle'
    migrate_legacy_cache(legacy, target)
    assert not legacy.exists()
    dest = target / 'legacy-cache-archive/1/7/course-cache/2.json'
    assert dest.read_bytes() == b'{"private":"fixture"}'
    assert dest.stat().st_mode & 0o777 == 0o600
    assert not (target / '1/7/course-cache/2.json').exists()  # not a fresh cache
    migrate_legacy_cache(legacy, target)


def test_migration_fails_closed_on_conflict_or_symlink_and_retains_original(tmp_path):
    legacy = tmp_path / 'static/.moodle'; legacy.mkdir(parents=True)
    (legacy / 'old.json').write_text('original')
    archive = tmp_path / 'data/legacy-cache-archive'; archive.mkdir(parents=True)
    (archive / 'old.json').write_text('different')
    with pytest.raises(ValueError): migrate_legacy_cache(legacy, tmp_path / 'data')
    assert (legacy / 'old.json').read_text() == 'original'
    (legacy / 'link').symlink_to(tmp_path / 'outside')
    with pytest.raises(ValueError): migrate_legacy_cache(legacy, tmp_path / 'other')
    assert legacy.exists()
