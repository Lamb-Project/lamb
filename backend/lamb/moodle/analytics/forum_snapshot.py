"""Authorized forum tables. Learner IDs require saved forum scope on every read.

No message text, names, private posts or inferred resolution are projected.
"""
from datetime import datetime
from zoneinfo import ZoneInfo
from .forum_participation import summarize_forums

RECIPES = {'forum-participation', 'forum-discussions'}
TEXT = {
    'en': ('Forum participation', 'Forum discussions', 'Student', 'Discussion',
           'Observed public posts', 'Observed public replies',
           'Counts are not contribution quality or learning. No observed public replies does not mean unanswered or unresolved. Current student population; not historical enrolment. Private/deleted posts excluded. Collection is not atomic.'),
    'es': ('Participación en el foro', 'Discusiones del foro', 'Estudiante', 'Discusión',
           'Publicaciones públicas observadas', 'Respuestas públicas observadas',
           'Los recuentos no miden la calidad ni el aprendizaje. No observar respuestas públicas no significa que la pregunta esté sin responder o resolver. Población estudiantil actual, no matrícula histórica. Se excluyen publicaciones privadas y eliminadas. La consulta no es atómica.'),
    'ca': ('Participació al fòrum', 'Discussions del fòrum', 'Estudiant', 'Discussió',
           'Publicacions públiques observades', 'Respostes públiques observades',
           'Els recomptes no mesuren la qualitat ni l’aprenentatge. No observar respostes públiques no vol dir que la pregunta estigui sense resposta o resoldre. Població estudiantil actual, no matrícula històrica. S’exclouen publicacions privades i eliminades. La consulta no és atòmica.'),
    'eu': ('Foroko parte-hartzea', 'Foroko eztabaidak', 'Ikaslea', 'Eztabaida',
           'Behatutako mezu publikoak', 'Behatutako erantzun publikoak',
           'Zenbaketek ez dute kalitatea edo ikaskuntza neurtzen. Erantzun publikorik ez ikusteak ez du esan nahi galdera erantzun edo konpondu gabe dagoenik. Uneko ikasleak, ez matrikula historikoa. Mezu pribatuak eta ezabatuak kanpo geratzen dira. Bilketa ez da atomikoa.'),
}


def snapshot(state, run_id, *, recipe):
    if recipe not in RECIPES:
        raise ValueError('Invalid forum recipe')
    if state.get('done') is not True or state.get('cursor') is not None:
        raise ValueError('Forum collection is not finished')
    context, scope = state['context'], state['scope']
    ids = [row['discussion_id'] for row in context['discussions']]
    if (len(ids)!=len(set(ids)) or sorted(ids)!=sorted(t['id'] for t in state['threads'])
            or any(t['forum_id']!=scope['forum_id'] for t in state['threads'])):
        raise ValueError('Forum collection differs from inventory')
    started = datetime.fromisoformat(state['started_at'])
    completed = datetime.fromisoformat(state['completed_at'])
    if (started.utcoffset() is None or completed.utcoffset() is None or completed<started
            or type(state['as_of']) is not int or int(completed.timestamp())!=state['as_of']):
        raise ValueError('Invalid forum observation interval')
    metrics = summarize_forums(state['threads'],context['students'],since=state['since'],
        until=state['until'],as_of=state['as_of'],timezone=state['tz'],inventory_complete=True)
    language = state['language']
    participation, discussions, student, discussion, posts, replies, caption = TEXT[language]
    learner_rows = metrics.pop('student_rows')
    discussion_rows = metrics.pop('discussion_rows')
    if recipe=='forum-participation':
        title, metric = participation, posts
        rows = [dict(row,id=row['student_id'],name=f"{student} #{row['student_id']}",
                     value=row['posts'],status='ok',reason=None) for row in learner_rows]
        basis = 'Current student-role population; post creation in [since, until).'
    else:
        title, metric = discussions, replies
        rows = [dict(row,id=row['discussion_id'],name=f"{discussion} #{row['discussion_id']}",
                     value=row['observed_public_replies_as_of'],
                     status='ok' if row['public_thread_complete'] else 'partial',reason=None)
                for row in discussion_rows]
        basis = 'All visible authors and self-replies; retrieved public posts through as_of, not only the window.'
    local = completed.astimezone(ZoneInfo(state['tz'])).isoformat()
    coverage = dict(metrics.pop('coverage'),population_exhausted=True,
                    student_rows=len(context['students']),atomic_snapshot=False)
    coverage['complete'] = coverage['collection_complete']
    limitations = metrics.pop('limitations')
    return {'schema_version':1,'recipe':{'id':recipe,'version':1},
        'course_id':scope['course_id'],'forum_id':scope['forum_id'],'group_id':scope['group_id'],
        'course_name':f"#{scope['course_id']}",'title':f"{title} (#{scope['forum_id']})",
        'language':language,'timezone':state['tz'],'view_kind':'forum-table-v1',
        'metric_label':metric,'population_label':basis,'caption':caption,'rows':rows,
        'metrics':metrics,'coverage':coverage,'limitations':limitations,
        'as_of':state['completed_at'],'as_of_local':local,'snapshot_date_label':f'{local} ({state["tz"]})',
        'collection_started_at':state['started_at'],'collection_completed_at':state['completed_at'],
        'collection_run_id':run_id,'source':'local_lambanalytics_forum_posts',
        'forum_scopes':[dict(scope,discussion_ids=sorted(ids))]}
