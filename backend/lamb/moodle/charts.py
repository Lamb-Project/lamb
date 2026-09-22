"""Bounded, deterministic assignment chart pilot. No student-level records retained."""
import fcntl
import json
import os
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .scope import MoodleScope
from .storage import ensure_private, private_root
from .forum_activity import TaskCancelled, TaskLimit, preview

MAX_ASSIGNMENTS = 20
MAX_CHARTS = 100
MAX_BYTES = 128 * 1024
RENDER_LOCK = threading.Lock()
LABELS = {
 'en': ['Assignment submissions', 'Submitted', 'Outstanding', 'Assignment', 'Course deadline', 'Deadline status', 'Open', 'Course deadline passed', 'Not yet open', 'No deadline', 'Unavailable', 'Counts of submissions, not learning. Outstanding includes drafts. Individual extensions and overrides were not checked; outstanding does not necessarily mean late.'],
 'es': ['Entregas de tareas', 'Entregadas', 'Pendientes', 'Tarea', 'Fecha límite del curso', 'Estado del plazo', 'Abierto', 'Plazo del curso vencido', 'Todavía no abierto', 'Sin fecha límite', 'No disponible', 'Recuentos de entregas, no de aprendizaje. Las pendientes incluyen borradores. No se han comprobado las prórrogas ni las excepciones individuales; pendiente no significa necesariamente atrasada.'],
 'ca': ['Lliuraments de tasques', 'Lliurades', 'Pendents', 'Tasca', 'Data límit del curs', 'Estat del termini', 'Obert', 'Termini del curs vençut', 'Encara no obert', 'Sense data límit', 'No disponible', 'Recomptes de lliuraments, no d’aprenentatge. Els pendents inclouen esborranys. No s’han comprovat les pròrrogues ni les excepcions individuals; pendent no significa necessàriament fora de termini.'],
 'eu': ['Zereginen entregak', 'Entregatuta', 'Zain', 'Zeregina', 'Ikastaroko epea', 'Epearen egoera', 'Irekita', 'Ikastaroko epea amaituta', 'Oraindik ireki gabe', 'Eperik gabe', 'Ez dago erabilgarri', 'Entrega kopuruak, ez ikaskuntza. Zain daudenek zirriborroak barne hartzen dituzte. Ez dira banakako luzapenak edo salbuespenak egiaztatu; zain egoteak ez du nahitaez berandu esan nahi.'],
}


def submission_snapshot(client, owner_id, course_id, *, tz='UTC', language='en', progress=None):
    zone = ZoneInfo(tz)
    scope = MoodleScope(client, owner_id)
    course_id = scope.require_teacher(course_id)
    started = int(time.time())
    response = client.call('mod_assign_get_assignments', courseids=[course_id])
    courses = response.get('courses', [])
    if response.get('warnings') or len(courses) != 1 or int(courses[0]['id']) != course_id:
        raise ValueError('Moodle assignment inventory is incomplete; no chart was produced')
    assignments = courses[0]['assignments']
    if len({int(a['id']) for a in assignments}) != len(assignments):
        raise ValueError('Moodle returned duplicate assignments')
    rows = []
    for index, assignment in enumerate(assignments[:MAX_ASSIGNMENTS]):
        client.checkpoint()
        aid = int(assignment['id'])
        row = {'id': aid, 'name': preview(assignment['name'], 160)[0], 'status': 'unavailable',
               'submitted': None, 'outstanding': None, 'participants': None,
               'deadline': None, 'deadline_status': None, 'reason': None, 'reason_code': None}
        try:
            if assignment.get('teamsubmission', 1):
                row['reason_code'] = 'team'
                raise ValueError('Team submissions are outside this pilot')
            result = client.call('mod_assign_get_submission_status', assignid=aid, userid=owner_id, groupid=0)
            summary = result.get('gradingsummary')
            if result.get('warnings') or not summary:
                row['reason_code'] = 'summary'
                raise ValueError('All-groups grading summary unavailable')
            if not summary['submissionsenabled']:
                row['reason_code'] = 'offline'
                raise ValueError('Online submissions are disabled')
            total, submitted = summary['participantcount'], summary['submissionssubmittedcount']
            if any(type(n) is not int or n < 0 for n in (total, submitted)) or submitted > total:
                row['reason_code'] = 'counts'
                raise ValueError('Inconsistent Moodle counts; retry the chart')
            due, opens = int(assignment['duedate']), int(assignment['allowsubmissionsfromdate'])
            status = 'not_open' if opens > started else 'no_deadline' if not due else 'deadline_passed' if due < started else 'open'
            row.update(status='ok', submitted=submitted, outstanding=total-submitted, participants=total,
                       deadline=datetime.fromtimestamp(due, zone).isoformat() if due else None, deadline_status=status)
        except (TaskCancelled, TaskLimit):
            raise
        except PermissionError:
            # Includes changed connection/policy: withhold the entire result.
            raise
        except Exception as exc:
            row['reason_code'] = row['reason_code'] or 'unavailable'
            row['reason'] = str(exc) if type(exc) is ValueError else 'Moodle grading summary could not be read'
        rows.append(row)
        if progress: progress(index + 1, min(len(assignments), MAX_ASSIGNMENTS))
    client.checkpoint()
    labels = LABELS[language]
    return {'recipe': 'assignment-submissions-v1', 'title': labels[0], 'language': language, 'labels': labels,
            'course_id': course_id, 'course_name': preview(courses[0]['fullname'], 160)[0],
            'as_of': datetime.fromtimestamp(started, zone).isoformat(), 'timezone': tz, 'rows': rows,
            'caption': labels[11], 'source': 'Moodle all-groups grading summaries; current participants who can submit',
            'coverage': {'complete': len(assignments) <= MAX_ASSIGNMENTS and all(r['status'] == 'ok' for r in rows),
                         'assignments_found': len(assignments), 'assignments_read': sum(r['status'] == 'ok' for r in rows),
                         'omitted_by_limit': max(0, len(assignments)-MAX_ASSIGNMENTS)},
            'limitations': ['Current snapshot, not submission history or an atomic Moodle snapshot.',
                           'Outstanding does not mean late: personal extensions and overrides are not inspected.',
                           'Team/offline assignments are explicitly excluded; no student names, grades or submissions are retained.']}


class ChartStore:
    """Small immutable aggregates retained for history, private and quota bounded."""
    def __init__(self, runtime):
        self.runtime = runtime
        self.root = ensure_private(Path(runtime.cache_root or private_root()) / 'charts' /
                                   str(runtime.store.organization_id) / str(runtime.store.owner_id))

    def save(self, snapshot, binding, *, command='moodle.chart.submissions'):
        identity = str(uuid.uuid4())
        payload = json.dumps({'snapshot': snapshot, 'binding': binding, 'command':command}, ensure_ascii=False).encode()
        if len(payload) > MAX_BYTES: raise ValueError('Chart exceeds the pilot size limit')
        fd = os.open(self.root / '.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if len(list(self.root.glob('*.json'))) >= MAX_CHARTS:
                raise ValueError('Pilot chart storage is full (100 saved charts); ask an administrator to archive snapshots')
            # Immutable write: inaccessible to anyone else until returned; fsync before publication.
            path = self.root / (identity + '.json')
            with os.fdopen(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600), 'wb') as out:
                out.write(payload); out.flush(); os.fsync(out.fileno())
        return identity

    def read(self, identity):
        try:
            identity = str(uuid.UUID(identity))
            with os.fdopen(os.open(self.root / (identity + '.json'), os.O_RDONLY | os.O_NOFOLLOW), 'rb') as source:
                raw = source.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES: raise ValueError()
            envelope = json.loads(raw)
        except (OSError, ValueError, TypeError):
            raise PermissionError('Chart is unavailable') from None
        self.runtime.validate_result_binding(envelope['binding'], envelope.get('command', 'moodle.chart.submissions'))
        return {'chart_id': identity, **envelope['snapshot']}

    def listing(self, offset=0):
        """Bound the scan, and never expose metadata before current ACL validation."""
        if not isinstance(offset, int) or offset < 0:
            raise ValueError('Invalid chart offset')
        paths = sorted(self.root.glob('*.json'), key=lambda p: (p.lstat().st_mtime_ns, p.name), reverse=True)
        items = []
        for path in paths[offset:offset + 20]:
            try:
                data = self.read(path.stem)
            except PermissionError:
                continue
            items.append({key: data[key] for key in
                ('chart_id', 'title', 'course_id', 'course_name', 'as_of', 'timezone', 'coverage')})
            if data.get('resource_scopes'):
                items[-1]['resource_scopes'] = data['resource_scopes']
            if data.get('grade_scopes'):
                items[-1]['grade_scopes'] = data['grade_scopes']
        return {'items': items, 'next_offset': offset + 20 if offset + 20 < len(paths) else None,
                'evidence_kind': 'saved_snapshot', 'refreshed': False}


def chart_task(runtime, client, owner_id, params, *, progress=None):
    binding = dict(runtime.result_binding(), course_id=params['course_id'])
    snapshot = submission_snapshot(client, owner_id, **params, progress=progress)
    client.checkpoint()
    identity = ChartStore(runtime).save(snapshot, binding)
    client.checkpoint()
    return {'chart_id': identity, 'title': snapshot['title'], 'course_id': snapshot['course_id'],
            'as_of': snapshot['as_of'], 'coverage': snapshot['coverage'], 'caption': snapshot['caption'],
            'facts': snapshot['rows'], 'limitations': snapshot['limitations'],
            'interpretation': {
                'individual_extensions': 'not_checked',
                'individual_lateness': 'unknown',
                'student_identities': 'not_collected',
                'reply': 'Use two or three sentences beside the Moodle Charts link, not a repeated table. '
                         'Say extensions were NOT CHECKED; never say there are none. '
                         'Offer only to explain these counts or, if requested, refresh this chart. '
                         'Do not offer contacting students, forum replies, grading or other chart recipes.'},
            'display': 'The saved chart is available in Moodle > Charts. The conversation links to it; do not claim it was opened.'}


def render_svg(snapshot):
    import vl_convert as vlc
    if snapshot.get('view_kind') == 'metric-bars-v1':
        rows = snapshot['rows']
        if len(rows) > 100: raise ValueError('Analytics mark limit exceeded')
        values = [{'label':r['name'], 'value':r['value']} for r in rows if r['status'] == 'ok' and r['value'] is not None]
        spec = {'width':480, 'height':max(70, 32 * len(values)), 'data':{'values':values},
                'mark':{'type':'bar','color':'#2463a1'}, 'encoding':{
                    'y':{'field':'label','type':'nominal','sort':None,'title':None,'axis':{'labelLimit':220}},
                    'x':{'field':'value','type':'quantitative','title':snapshot['metric_label'],'axis':{'tickMinStep':1}}}}
        with RENDER_LOCK:
            return vlc.vegalite_to_svg(spec, allowed_base_urls=[])
    labels = snapshot['labels']
    rows = snapshot['rows']
    if len(rows) > MAX_ASSIGNMENTS: raise ValueError('Chart mark limit exceeded')
    values = [{'assignment': f"{r['name']} (#{r['id']})", 'series': labels[i], 'count': r[key], 'order': i}
              for r in rows if r['status'] == 'ok' for i, key in ((1, 'submitted'), (2, 'outstanding'))]
    spec = {'width': 480, 'height': max(70, 42 * sum(r['status'] == 'ok' for r in rows)),
            'data': {'values': values}, 'mark': {'type': 'bar'},
            'encoding': {'y': {'field': 'assignment', 'type': 'nominal', 'sort': None, 'title': None,
                               'axis': {'labelLimit': 220}},
                         'x': {'field': 'count', 'type': 'quantitative', 'title': None, 'axis': {'tickMinStep': 1}},
                         'color': {'field': 'series', 'type': 'nominal', 'title': None,
                                   'scale': {'domain': labels[1:3], 'range': ['#2463a1', '#c9d3df']}},
                         'order': {'field': 'order'}},
            'config': {'font': 'sans-serif', 'legend': {'orient': 'top'}, 'view': {'stroke': None}}}
    # Code-owned specification, inline aggregate rows, bounded marks, no network.
    with RENDER_LOCK:
        return vlc.vegalite_to_svg(spec, allowed_base_urls=[])
