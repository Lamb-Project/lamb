"""Aggregate-only assessment comparison evidence, independent of live refresh."""
from datetime import datetime
from zoneinfo import ZoneInfo
from .assessment_comparison import compare_assessments

TEXT = {
    'en': ('Assessment comparison', 'Course', 'Assessment',
        'Stored final grades, not raw marks or evidence of learning. Missing grades are not missing submissions. Stale and unsupported items have no score comparison. Populations may differ between assessments.'),
    'es': ('Comparación de evaluaciones', 'Curso', 'Evaluación',
        'Notas finales almacenadas, no puntuaciones brutas ni pruebas de aprendizaje. Las notas ausentes no son entregas ausentes. Los elementos desactualizados o no compatibles no tienen comparación de puntuaciones. Las poblaciones pueden diferir entre evaluaciones.'),
    'ca': ('Comparació d’avaluacions', 'Curs', 'Avaluació',
        'Notes finals emmagatzemades, no puntuacions brutes ni proves d’aprenentatge. Les notes absents no són lliuraments absents. Els elements desactualitzats o no compatibles no tenen comparació de puntuacions. Les poblacions poden diferir entre avaluacions.'),
    'eu': ('Ebaluazioen konparazioa', 'Ikastaroa', 'Ebaluazioa',
        'Gordetako azken notak, ez puntuazio gordinak edo ikaskuntzaren frogak. Falta diren notak ez dira falta diren entregak. Zaharkitutako edo onartu gabeko elementuek ez dute puntuazio-konparaziorik. Ikasle multzoak desberdinak izan daitezke ebaluazioen artean.'),
}


def snapshot(state, run_id):
    if state.get('done') is not True:
        raise ValueError('Assessment collection is not finished')
    language, tz = state.get('language','en'), state.get('tz','UTC')
    title, course_label, item_label, caption = TEXT[language]
    started, completed = (datetime.fromisoformat(state[key]) for key in ('started_at','completed_at'))
    if started.utcoffset() is None or completed.utcoffset() is None or completed < started:
        raise ValueError('Invalid assessment collection interval')
    comparison = compare_assessments([(i['cursor'],i['context']['students']) for i in state['items']])
    scopes, rows = [], []
    for item, summary in zip(state['items'],comparison['rows']):
        scope = item['scope']
        if scope != {'course_id':summary['course_id'],'grade_item_id':summary['grade_item_id'],'group_id':summary['group_id']}:
            raise ValueError('Assessment snapshot scope mismatch')
        scopes.append(dict(scope))
        context = item['context']
        stored_name=item['cursor']['item'].get('name','').strip()
        label=f"{stored_name} (#{summary['grade_item_id']})" if stored_name else f"{item_label} #{summary['grade_item_id']}"
        rows.append(dict(summary,id=summary['grade_item_id'],name=label,
            status='ok' if summary['comparison_status']=='available' else 'unavailable',
            population_basis=context['population_basis'],candidate_basis=context['candidate_basis'],
            candidate_students_n=len(context['candidates']),targeting_excluded_n=len(context['excluded_students'])))
    local = completed.astimezone(ZoneInfo(tz)).isoformat()
    available = sum(row['comparison_status']=='available' for row in rows)
    return {'schema_version':1,'recipe':{'id':'assessment-comparison','version':1},
        'view_kind':'assessment-comparison-v1','course_id':scopes[0]['course_id'],'group_id':scopes[0]['group_id'],
        'course_name':f"{course_label} {scopes[0]['course_id']}",'title':title,
        'language':language,'timezone':tz,'caption':caption,'rows':rows,
        'metrics':{'selected_assessments':len(rows),'comparable_assessments':available,
                   'unavailable_assessments':len(rows)-available},
        'comparison_basis':comparison['comparison_basis'],'difficulty_ranking':None,
        'submission_rate_collected':False,'grade_basis':'stored_finalgrade',
        'coverage':{'complete':available==len(rows),'collection_complete':True,
                    'population_exhausted':True,'atomic_snapshot':False},
        'as_of':state['completed_at'],'as_of_local':local,'snapshot_date_label':f'{local} ({tz})',
        'collection_started_at':state['started_at'],'collection_completed_at':state['completed_at'],
        'collection_run_id':run_id,'gradebook_scopes':scopes,
        'source':'local_lambanalytics_gradebook_grades + local_lambanalytics_gradebook_population',
        'limitations':[
            'Current active student-role enrolments only; custom roles and historical eligibility are not established.',
            'Module and section user-list targeting omits temporal conditions; this is not current access or required work.',
            'Missing-grade rates use nonexcluded target populations, not submission denominators.',
            'Pass rates use valid nonexcluded final grades, not the whole enrolled cohort.',
            'No confidence interval, paired-effect estimate, difficulty ranking or learning inference is provided.',
            'Collection spans an interval and is not an atomic snapshot. Saved reads do not refresh Moodle evidence.']}
