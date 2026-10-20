"""Rebuildable per-course cache, separate from user-authored learning scenarios."""
import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .policy import canonical_base_url

from .storage import private_root

ROOT = private_root()
SECTIONS = frozenset({'course', 'forums', 'assignments', 'enrolment', 'calendar'})


class CacheConflict(ValueError):
    pass


def positive_id(value):
    if isinstance(value, bool) or not str(value).isdigit() or int(value) < 1:
        raise ValueError('Moodle cache identifiers must be positive integers')
    return str(int(value))


def now():
    return datetime.now(timezone.utc).isoformat()


class CourseCache:
    def __init__(self, organization_id, owner_id, *, base_url, moodle_user_id, root=None):
        self.root = Path(root) if root is not None else ROOT
        self.org, self.owner = positive_id(organization_id), positive_id(owner_id)
        self.source = {'base_url':canonical_base_url(base_url), 'moodle_user_id':int(positive_id(moodle_user_id))}

    @contextmanager
    def locked(self, course_id):
        course = positive_id(course_id)
        folder = self.root / self.org / self.owner / 'course-cache'
        for path in (self.root, self.root/self.org, self.root/self.org/self.owner, folder):
            if path.is_symlink(): raise ValueError('Unsafe Moodle cache storage')
            path.mkdir(mode=0o700,parents=True,exist_ok=True)
        fd = os.open(folder / '.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd,'a') as handle:
            fcntl.flock(handle,fcntl.LOCK_EX)
            path = folder / (course + '.json')
            if path.is_symlink(): raise ValueError('Unsafe Moodle cache storage')
            state = json.loads(path.read_text()) if path.exists() else {
                'schema_version':1, 'moodle_course_id':int(course), 'source':self.source, 'sections':{}}
            if state.get('schema_version') != 1 or state.get('moodle_course_id') != int(course):
                raise ValueError('Unsupported Moodle cache schema')
            yield path, state

    def read(self, course_id):
        with self.locked(course_id) as (_,state):
            if state['source'] != self.source:
                raise CacheConflict('Cached course belongs to another Moodle connection. Refresh the course.')
            return state

    def update(self, course_id, sections, *, synced_at=None):
        if not sections or set(sections) - SECTIONS:
            raise ValueError('Select a supported Moodle cache section')
        stamp = synced_at or now()
        parsed = datetime.fromisoformat(stamp)
        if parsed.tzinfo is None: raise ValueError('Moodle sync time requires a timezone')
        stamp = parsed.astimezone(timezone.utc).isoformat()
        with self.locked(course_id) as (path,state):
            if state['source'] != self.source:
                # Reconnecting to another account/site must not reuse its derived data.
                state['source'], state['sections'] = self.source, {}
            for section,data in sections.items():
                old = state['sections'].get(section)
                if old and old['synced_at'] >= stamp:
                    raise CacheConflict('A newer course sync was saved. Read the current cache before refreshing.')
                state['sections'][section] = {'synced_at':stamp, 'data':data,
                    'previous':{'synced_at':old['synced_at'],'data':old['data']} if old else None}
            fd,name = tempfile.mkstemp(dir=path.parent,prefix='.write-')
            try:
                with os.fdopen(fd,'w') as out:
                    json.dump(state,out,ensure_ascii=False);out.flush();os.fsync(out.fileno())
                os.replace(name,path)
                directory_fd=os.open(path.parent,os.O_RDONLY)
                try: os.fsync(directory_fd)
                finally: os.close(directory_fd)
            finally:
                if os.path.exists(name): os.unlink(name)
            return state

    def show(self, course_id, section):
        if section not in SECTIONS: raise ValueError('Select a supported Moodle cache section')
        item=self.read(course_id)['sections'].get(section)
        if item is None: raise ValueError('This section has not been synced. Run moodle sync first.')
        return f"Synced at: {item['synced_at']}\n" + json.dumps({
            'section':section, 'source':self.source, 'data':item['data'],
            'delta':section_delta(section,item)},ensure_ascii=False)


def section_delta(section, item):
    previous=item['previous']
    result={'since':previous['synced_at'] if previous else None, 'baseline':previous is None}
    def identities(data):
        if section == 'forums':
            return {str(d.get('discussion') or d['id']) for f in data for d in f.get('discussions',[])}
        if section == 'assignments':
            return {(str(a['id']),str(s['id'])) for a in data for s in a.get('submissions',[])}
        if isinstance(data,list): return {str(row['id']) for row in data if 'id' in row}
        return set()
    current=identities(item['data']);before=identities(previous['data']) if previous else set()
    result.update(new=len(current-before) if previous else 0, removed=len(before-current) if previous else 0)
    result['unit']={'forums':'discussions','assignments':'submissions'}.get(section,'items')
    return result
