"""Fixed raw-grade labels; never imply final marks or released feedback."""
TEXT = {
    'en': ('Raw assignment grade distribution', 'Students',
        'Valid: {valid_n}; missing: {missing_n}; active student-role population: {population_n}.',
        'Raw marks for the latest attempt, normalized to percentages. Not final gradebook marks. Release, hidden/excluded state and overrides were not checked. Missing marks are not zeros. Bins include the lower bound and exclude the upper, except 100 is included. Quartiles use linear interpolation.',
        ['Mean (%)','Q1 (%)','Median (%)','Q3 (%)']),
    'es': ('Distribución de notas brutas de la tarea', 'Estudiantes',
        'Válidas: {valid_n}; ausentes: {missing_n}; población activa con rol student: {population_n}.',
        'Notas brutas del último intento, normalizadas a porcentajes. No son notas finales del libro de calificaciones. No se han comprobado publicación, ocultación, exclusión ni anulaciones. Las notas ausentes no son ceros. Los intervalos incluyen el límite inferior y excluyen el superior, salvo el 100. Los cuartiles usan interpolación lineal.',
        ['Media (%)','Q1 (%)','Mediana (%)','Q3 (%)']),
    'ca': ('Distribució de notes brutes de la tasca', 'Estudiants',
        'Vàlides: {valid_n}; absents: {missing_n}; població activa amb rol student: {population_n}.',
        'Notes brutes de l’últim intent, normalitzades a percentatges. No són notes finals del llibre de qualificacions. No s’han comprovat publicació, ocultació, exclusió ni anul·lacions. Les notes absents no són zeros. Els intervals inclouen el límit inferior i exclouen el superior, excepte el 100. Els quartils fan servir interpolació lineal.',
        ['Mitjana (%)','Q1 (%)','Mediana (%)','Q3 (%)']),
    'eu': ('Zereginaren kalifikazio gordinen banaketa', 'Ikasleak',
        'Baliozkoak: {valid_n}; falta direnak: {missing_n}; student rola duen populazio aktiboa: {population_n}.',
        'Azken saiakeraren kalifikazio gordinak, ehunekotan normalizatuta. Ez dira kalifikazio-liburuko azken notak. Argitalpena, ezkutatzea, baztertzea eta ordezkapenak ez dira egiaztatu. Falta diren notak ez dira zeroak. Tarteek beheko muga barne hartzen dute eta goikoa kanpo uzten dute, 100 izan ezik. Kuartilek interpolazio lineala erabiltzen dute.',
        ['Batezbestekoa (%)','Q1 (%)','Mediana (%)','Q3 (%)']),
}


def present_grades(language,data):
    title, metric, population, caption, labels = TEXT[language]
    return {'title':f"{title}: {data.get('assignment_name','')} (#{data['assignment_id']})",'metric_label':metric,
        'population_label':population.format(**data['metrics']),'caption':caption,
        'summary_statistics':[{'label':label,'value':data['metrics'][key]}
                              for label,key in zip(labels,['mean','q1','median','q3'])]}
