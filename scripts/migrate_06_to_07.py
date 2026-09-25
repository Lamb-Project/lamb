#!/usr/bin/env python3
"""Copy stopped 0.6 stores into empty 0.7 volumes; never start services or remove data."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from contextlib import closing

STORES = {
    'lamb-data': 'lamb_v4.db',
    'openwebui-data': 'open-webui/backend/data',
    'kb-data': 'lamb-kb-server-stable/backend/data',
    'kb-static': 'lamb-kb-server-stable/backend/static',
    'library-manager-data': 'library-manager/data',
    'lamb-static': 'backend/static',
}


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def inventory(root):
    result = {}
    for p in sorted(root.rglob('*')):
        if p.is_symlink() or not (p.is_dir() or p.is_file()):
            raise ValueError(f'Unsupported symlink/special file: {p}')
        if p.is_file():
            digest = hashlib.sha256()
            with p.open('rb') as f:
                for block in iter(lambda: f.read(1024 * 1024), b''):
                    digest.update(block)
            result[str(p.relative_to(root))] = {'sha256': digest.hexdigest(), 'bytes': p.stat().st_size}
    return result


def sqlite_checks(root):
    """Check a disposable copy: SQLite may recover WAL and rewrite its sidecars."""
    result = {}
    for original in sorted(root.rglob('*')):
        if not original.is_file():
            continue
        with original.open('rb') as f:
            if f.read(16) != b'SQLite format 3\x00':
                continue
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / original.name
            for suffix in ('', '-wal', '-shm', '-journal'):
                source = Path(str(original) + suffix)
                if source.exists():
                    shutil.copy2(source, Path(str(p) + suffix))
            with closing(sqlite3.connect(str(p))) as db:
                if db.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                    raise ValueError(f'SQLite integrity failed: {original.relative_to(root)}')
                tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
                counts = {name: db.execute('SELECT count(*) FROM "' + name.replace('"', '""') + '"').fetchone()[0]
                          for name in tables}
                result[str(original.relative_to(root))] = {'integrity': 'ok', 'table_rows': counts}
    return result


def worker(plan, library_owner):
    staged = {}
    database_sources = {}
    # All sources and destinations pass preflight before the first copy.
    with tempfile.TemporaryDirectory() as tmp:
        for i, (key, source) in enumerate(plan.items()):
            dst = Path(f'/dst/{i}')
            if any(dst.iterdir()):
                raise ValueError(f'Refusing populated destination: {key}')
            src = Path(f'/src/{i}')
            if source is None:
                src = Path(tmp) / key
                src.mkdir()
            elif key == 'lamb-data':
                database = src / Path(source).name
                if not database.is_file() or database.is_symlink():
                    raise ValueError('Missing regular LAMB database')
                for suffix in ('', '-wal', '-shm', '-journal'):
                    file = Path(str(database) + suffix)
                    if file.exists():
                        with file.open('rb') as f:
                            digest = hashlib.file_digest(f, 'sha256').hexdigest()
                        database_sources[file] = digest
                selected = Path(tmp) / key
                selected.mkdir()
                for suffix in ('', '-wal', '-shm', '-journal'):
                    file = Path(str(database) + suffix)
                    if file.is_symlink():
                        raise ValueError(f'Symlink database file: {file}')
                    if file.exists():
                        shutil.copy2(file, selected / ('lamb_v4.db' + suffix))
                src = selected
            hashes = inventory(src)
            checks = sqlite_checks(src)
            if key == 'lamb-data' and 'lamb_v4.db' not in checks:
                raise ValueError('LAMB source is not a valid SQLite database')
            staged[key] = (src, dst, hashes, checks)
        result = {}
        for key, (src, dst, hashes, checks) in staged.items():
            shutil.copytree(src, dst, dirs_exist_ok=True)
            if inventory(dst) != hashes or inventory(src) != hashes:
                raise ValueError(f'File hash mismatch: {key}')
            if sqlite_checks(dst) != checks:
                raise ValueError(f'SQLite preservation mismatch: {key}')
            owner = library_owner if key == 'library-manager-data' else (0, 0)
            for path in [dst, *dst.rglob('*')]:
                os.chown(path, *owner)
            result[key] = {'files': hashes, 'sqlite': checks, 'owner': owner, 'verified': True}
        for file, digest in database_sources.items():
            with file.open('rb') as f:
                if hashlib.file_digest(f, 'sha256').hexdigest() != digest:
                    raise ValueError('LAMB database source changed during migration')
        return result


def sources(root, overrides):
    plan = {key: str((root / rel).resolve()) for key, rel in STORES.items()}
    if overrides:
        unknown = set(overrides) - set(STORES)
        if unknown:
            raise ValueError(f'Unknown stores: {sorted(unknown)}')
        plan.update(overrides)
    for key, source in plan.items():
        if source is None:
            if key not in {'library-manager-data', 'lamb-static'}:
                raise ValueError(f'Cannot omit required store: {key}')
            continue
        p = Path(source)
        if not p.is_absolute() or ',' in source or p.is_symlink():
            raise ValueError(f'Use an absolute, non-symlink path without commas: {key}')
        if not (p.is_file() if key == 'lamb-data' else p.is_dir()):
            raise ValueError(f'Missing source: {key}: {p}')
        plan[key] = str(p.resolve())
    return plan


def ensure_stopped(plan, projects, volumes):
    ids = run('docker', 'ps', '-q').split()
    if not ids:
        return
    for c in json.loads(run('docker', 'inspect', *ids)):
        if (c.get('Config', {}).get('Labels') or {}).get('com.docker.compose.project') in projects:
            raise ValueError(f'Stop project container first: {c["Name"]}')
        for mount in c.get('Mounts', []):
            if mount.get('Name') in volumes:
                raise ValueError(f'Destination volume is in use: {c["Name"]}')
            if mount.get('Type') == 'bind':
                bound = Path(mount['Source']).resolve()
                for source in filter(None, plan.values()):
                    p = Path(source).resolve()
                    if p == bound or bound in p.parents or p in bound.parents:
                        raise ValueError(f'Source is mounted by running container: {c["Name"]}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--sources', type=Path, help='JSON overrides keyed by volume logical name; null explicitly declares an absent optional store')
    parser.add_argument('--legacy-project', required=True)
    parser.add_argument('--project-name', required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--library-owner', required=True, help='Numeric UID:GID of appuser in the target Library Manager image')
    parser.add_argument('--helper-image', default='python:3.12-slim')
    args = parser.parse_args()
    if not re.fullmatch(r'\d+:\d+', args.library_owner):
        parser.error('--library-owner must be numeric UID:GID')
    library_owner = tuple(map(int, args.library_owner.split(':')))
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]*', args.project_name):
        parser.error('Invalid Compose project name')
    if args.manifest.exists():
        parser.error('Use a fresh manifest path')
    plan = sources(args.source_root.resolve(), json.loads(args.sources.read_text()) if args.sources else {})
    volumes = [args.project_name + '_' + key for key in plan]
    projects = {args.project_name, args.legacy_project}
    ensure_stopped(plan, projects, volumes)
    # Exclusively reserve the journal before touching destination volumes.
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(args.manifest, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    report = {'status': 'incomplete', 'sources': plan, 'volumes': volumes,
              'legacy_project': args.legacy_project, 'project_name': args.project_name}
    with os.fdopen(fd, 'w') as f:
        json.dump(report, f, indent=2)
    try:
        command = ['docker', 'run', '--rm', '--network=none', '--read-only', '--tmpfs', '/tmp',
                   '--mount', f'type=bind,src={Path(__file__).resolve()},dst=/migrate.py,readonly']
        for i, ((key, source), volume) in enumerate(zip(plan.items(), volumes)):
            run('docker', 'volume', 'create', volume)
            command += ['--mount', f'type=volume,src={volume},dst=/dst/{i},volume-nocopy']
            if source is not None:
                mount = str(Path(source).parent) if key == 'lamb-data' else source
                command += ['--mount', f'type=bind,src={mount},dst=/src/{i},readonly']
        ensure_stopped(plan, projects, volumes)
        command += [args.helper_image, 'python', '/migrate.py', '--worker', json.dumps(plan), json.dumps(library_owner)]
        report['stores'] = json.loads(run(*command))
        ensure_stopped(plan, projects, volumes)
        report['helper_image_id'] = run('docker', 'image', 'inspect', '--format', '{{.Id}}', args.helper_image)
        report['status'] = 'verified'
    except Exception as exc:
        report['error'] = str(exc)
        raise
    finally:
        args.manifest.write_text(json.dumps(report, indent=2) + '\n')
    print(f'Verified all stores. Services remain stopped. Manifest: {args.manifest}')


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--worker':
        print(json.dumps(worker(json.loads(sys.argv[2]), json.loads(sys.argv[3]))))
    else:
        main()
