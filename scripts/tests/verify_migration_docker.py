#!/usr/bin/env python3
"""Opt-in disposable Docker copy rehearsal. Keeps fixture files and volumes for inspection.

This is a synthetic fixture, NOT the real-v0.6 Linux release acceptance gate.
"""
import argparse
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys

SCRIPT=Path(__file__).parents[1]/'migrate_06_to_07.py'
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--work-dir', type=Path, required=True)
p.add_argument('--project-prefix', required=True)
a=p.parse_args()
a.work_dir.mkdir(parents=True, exist_ok=False)
root=a.work_dir/'source';root.mkdir()
for rel in ['open-webui/backend/data','lamb-kb-server-stable/backend/data','lamb-kb-server-stable/backend/static','library-manager/data','backend/static']:
    folder=root/rel;folder.mkdir(parents=True);(folder/'preserved.txt').write_text(rel+'\n')
# Snapshot a WAL database with committed rows absent from the checkpointed main file.
live=a.work_dir/'live.db';db=sqlite3.connect(live)
db.execute('PRAGMA journal_mode=WAL');db.execute('PRAGMA wal_autocheckpoint=0')
db.execute('CREATE TABLE users(id INTEGER)');db.execute('INSERT INTO users VALUES (42)');db.commit()
for suffix in ['', '-wal', '-shm']:
    shutil.copy2(Path(str(live)+suffix), root/('lamb_v4.db'+suffix))
db.close()

def invoke(project, name, success):
    cmd=[sys.executable,str(SCRIPT),'--source-root',str(root),'--legacy-project',a.project_prefix+'-old',
         '--project-name',project,'--library-owner','999:999','--manifest',str(a.work_dir/(name+'.json'))]
    r=subprocess.run(cmd,capture_output=True,text=True)
    (a.work_dir/(name+'.log')).write_text(r.stdout+r.stderr)
    assert (r.returncode==0)==success, r.stderr
    return json.loads((a.work_dir/(name+'.json')).read_text()) if (a.work_dir/(name+'.json')).exists() else None

project=a.project_prefix+'-copy'
report=invoke(project,'copy',True)
assert report['stores']['lamb-data']['sqlite']['lamb_v4.db']['table_rows']['users']==1
assert 'lamb_v4.db-wal' in report['stores']['lamb-data']['files']
assert len(report['stores'])==6
# Appuser can actually write the migrated library volume.
subprocess.run(['docker','run','--rm','--user','999:999','--mount',f'type=volume,src={project}_library-manager-data,dst=/data',
                'python:3.12-slim','python','-c',"from pathlib import Path;Path('/data/owner-proof').write_text('ok')"],check=True)
assert invoke(project,'repeat-refused',False)['status']=='incomplete'
# A populated LAST destination must block copying into every earlier destination.
blocked=a.project_prefix+'-blocked'
subprocess.run(['docker','volume','create',blocked+'_lamb-static'],check=True,capture_output=True)
subprocess.run(['docker','run','--rm','--mount',f'type=volume,src={blocked}_lamb-static,dst=/data',
                'python:3.12-slim','python','-c',"from pathlib import Path;Path('/data/keep').write_text('original')"],check=True)
assert invoke(blocked,'late-populated-refused',False)['status']=='incomplete'
r=subprocess.run(['docker','run','--rm','--mount',f'type=volume,src={blocked}_lamb-data,dst=/data,readonly',
                  'python:3.12-slim','python','-c',"from pathlib import Path;assert not list(Path('/data').iterdir())"],check=True)
# A running old-project container must fail before any journal/copy starts.
cid=subprocess.check_output(['docker','run','-d','--rm','--label','com.docker.compose.project='+a.project_prefix+'-old',
                             'python:3.12-slim','python','-c','import time;time.sleep(120)'],text=True).strip()
try:
    assert invoke(a.project_prefix+'-running','running-refused',False) is None
finally:
    subprocess.run(['docker','stop',cid],check=True,capture_output=True)
print('PASS: six-store hash copy, WAL row recovery, appuser write, populated/late-populated refusal, running-project refusal')
print('Retained synthetic fixtures and volumes with prefix:',a.project_prefix)
