"""Aggregate-only quiz snapshot; raw attempt records never become chart data."""
from datetime import datetime
from zoneinfo import ZoneInfo
from .quiz_attempts import summarize_attempts

TEXT = {
    'en': ('Quiz raw score distribution', 'Scored attempts', 'Course',
        ['First finished', 'Latest finished', 'Best observed scored finished', 'All finished'],
        ['Mean (%)', 'Q1 (%)', 'Median (%)', 'Q3 (%)', 'Selected attempts', 'Selected without marks', 'Current students'],
        'Policy: {policy}. Current active student-role enrolments only; custom roles are not included. Missing marks are not zero. Raw marks are not final grades or evidence of learning. Elapsed time is not study time. Retry comparisons use actual attempts 1 and 2, without checking question comparability. Best observed scores can change when missing marks arrive. Bins include the lower bound and exclude the upper, except 100 is included. Collection is not atomic.'),
    'es': ('Distribución de puntuaciones brutas del cuestionario', 'Intentos con puntuación', 'Curso',
        ['Primer intento finalizado', 'Último intento finalizado', 'Mejor intento finalizado con puntuación observada', 'Todos los intentos finalizados'],
        ['Media (%)', 'Q1 (%)', 'Mediana (%)', 'Q3 (%)', 'Intentos seleccionados', 'Seleccionados sin puntuación', 'Estudiantes actuales'],
        'Criterio: {policy}. Solo matrículas activas con rol student; no se incluyen roles personalizados. Las puntuaciones ausentes no son ceros. Las puntuaciones brutas no son notas finales ni pruebas de aprendizaje. El tiempo transcurrido no es tiempo de estudio. La comparación usa los intentos reales 1 y 2, sin comprobar la equivalencia de las preguntas. La mejor puntuación observada puede cambiar al llegar notas ausentes. Los intervalos incluyen el límite inferior y excluyen el superior, salvo el 100. La consulta no es atómica.'),
    'ca': ('Distribució de puntuacions brutes del qüestionari', 'Intents amb puntuació', 'Curs',
        ['Primer intent finalitzat', 'Últim intent finalitzat', 'Millor intent finalitzat amb puntuació observada', 'Tots els intents finalitzats'],
        ['Mitjana (%)', 'Q1 (%)', 'Mediana (%)', 'Q3 (%)', 'Intents seleccionats', 'Seleccionats sense puntuació', 'Estudiants actuals'],
        'Criteri: {policy}. Només matrícules actives amb rol student; no s’hi inclouen rols personalitzats. Les puntuacions absents no són zeros. Les puntuacions brutes no són notes finals ni proves d’aprenentatge. El temps transcorregut no és temps d’estudi. La comparació fa servir els intents reals 1 i 2, sense comprovar l’equivalència de les preguntes. La millor puntuació observada pot canviar quan arribin notes absents. Els intervals inclouen el límit inferior i exclouen el superior, excepte el 100. La consulta no és atòmica.'),
    'eu': ('Galdetegiaren puntuazio gordinen banaketa', 'Puntuazioa duten saiakerak', 'Ikastaroa',
        ['Amaitutako lehen saiakera', 'Amaitutako azken saiakera', 'Behatutako puntuaziorik onena duen amaitutako saiakera', 'Amaitutako saiakera guztiak'],
        ['Batezbestekoa (%)', 'Q1 (%)', 'Mediana (%)', 'Q3 (%)', 'Hautatutako saiakerak', 'Puntuaziorik gabe hautatutakoak', 'Uneko ikasleak'],
        'Irizpidea: {policy}. Student rola duten matrikula aktiboak soilik; rol pertsonalizatuak ez dira sartzen. Falta diren puntuazioak ez dira zeroak. Puntuazio gordinak ez dira azken notak edo ikaskuntzaren frogak. Igarotako denbora ez da ikasteko denbora. Konparazioak benetako 1. eta 2. saiakerak erabiltzen ditu, galderen baliokidetasuna egiaztatu gabe. Behatutako puntuaziorik onena alda daiteke falta diren notak iristean. Tarteek beheko muga barne hartzen dute eta goikoa kanpo uzten dute, 100 izan ezik. Bilketa ez da atomikoa.'),
}
POLICY_ORDER = ['first_finished', 'latest_finished', 'best_scored_finished', 'all_finished']


def snapshot(state, run_id):
    if state.get('done') is not True or state['cursor'].get('done') is not True:
        raise ValueError('Quiz collection is not finished')
    language = state.get('language', 'en')
    tz = state.get('tz', 'UTC')
    title, metric, course_label, policies, labels, caption = TEXT[language]
    started = datetime.fromisoformat(state['started_at'])
    completed = datetime.fromisoformat(state['completed_at'])
    if started.utcoffset() is None or completed.utcoffset() is None or completed < started:
        raise ValueError('Invalid quiz collection interval')
    scope = state['scope']
    metrics = summarize_attempts(state['cursor']['records'], state['context']['students'],
        quiz_id=scope['quiz_id'], maximum=state['cursor']['metadata']['raw_maximum'], policy=state['policy'])
    rows = [{'id': index, 'name': f"[{row['lower']}, {row['upper']}{']' if row['upper_inclusive'] else ')'} %",
             'value': row['attempts'], 'status': 'ok', 'reason': None, **row}
            for index, row in enumerate(metrics['score_bins'])]
    values = [metrics['score_percent'][key] for key in ('mean', 'q1', 'median', 'q3')]
    values += [metrics['selected_attempts'], metrics['ungraded_selected_attempts'], metrics['population_students']]
    local = completed.astimezone(ZoneInfo(tz)).isoformat()
    return {'schema_version': 1, 'recipe': {'id': 'quiz-overview', 'version': 1},
        'course_id': scope['course_id'], 'quiz_id': scope['quiz_id'], 'group_id': scope['group_id'],
        'course_name': f"{course_label} {scope['course_id']}",
        'title': f"{title} (#{scope['quiz_id']})", 'language': language, 'timezone': tz,
        'view_kind': 'metric-bars-v1', 'metric_label': metric,
        'population_label': policies[POLICY_ORDER.index(state['policy'])],
        'caption': caption.format(policy=policies[POLICY_ORDER.index(state['policy'])]),
        'rows': rows, 'metrics': metrics,
        'quiz_metadata': {key: state['cursor']['metadata'][key] for key in
                          ('raw_maximum', 'grade_maximum', 'grading_method')},
        'summary_statistics': [
            {'label': label, 'value': value} for label, value in zip(labels, values)],
        'coverage': {'complete': metrics['ungraded_finished_attempts'] == 0,
                     'collection_complete': True, 'population_exhausted': True,
                     'student_rows': metrics['population_students'], 'atomic_snapshot': False},
        'as_of': state['completed_at'], 'as_of_local': local,
        'snapshot_date_label': f'{local} ({tz})', 'collection_started_at': state['started_at'],
        'collection_completed_at': state['completed_at'], 'collection_run_id': run_id,
        'quiz_scopes': [dict(scope)], 'source': 'local_lambanalytics_quiz_attempts',
        'limitations': metrics['limitations'] + ['Current student-role enrolments only; custom roles are not included.',
            'Collection spans an interval. Upper attempt ID excludes later attempts but does not freeze edits or regrading.']}
