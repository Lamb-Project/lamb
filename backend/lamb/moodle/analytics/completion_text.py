"""Completion states and limits, without inferred eligibility or learning."""
KEYS = ('name','tracking_label','incomplete','complete','complete_pass','complete_fail',
        'unknown','untracked','overridden','override_unknown','overall_complete','overall_unknown','population_students')
TEXT = {
    'en': ('Observed activity completion', 'Recorded incomplete',
        ['Activity','Tracking','Incomplete','Complete','Complete-pass','Complete-fail','Unknown','Untracked','Overridden','Override unknown','Overall complete','Overall unknown','Population'],
        ['Manual','Automatic'],
        'Current active student-role population: {n}. Tracking-disabled activities excluded: {disabled}.',
        'Bars show recorded incomplete states, not all learners without completion. Unknown and untracked states remain separate. Completion is not proof of learning. Required activities, learner eligibility and schedules were not collected: no overdue or mandatory-path claim is supported. Overall completion follows Moodle configuration, not a merge of pass/fail states.'),
    'es': ('Finalización observada de actividades', 'Incompletas registradas',
        ['Actividad','Seguimiento','Incompleta','Completa','Completa-aprobada','Completa-no aprobada','Desconocida','Sin seguimiento','Modificada manualmente','Modificación desconocida','Finalización global','Global desconocida','Población'],
        ['Manual','Automático'],
        'Población activa actual con rol student: {n}. Actividades sin seguimiento excluidas: {disabled}.',
        'Las barras muestran estados incompletos registrados, no todos los estudiantes sin finalización. Los estados desconocidos y sin seguimiento se mantienen separados. Finalización no demuestra aprendizaje. No se han consultado actividades obligatorias, elegibilidad individual ni calendarios: no se puede afirmar retraso ni una secuencia obligatoria. La finalización global sigue la configuración de Moodle, no una suma de aprobados y no aprobados.'),
    'ca': ('Compleció observada de les activitats', 'Incompletes registrades',
        ['Activitat','Seguiment','Incompleta','Completa','Completa-aprovada','Completa-no aprovada','Desconeguda','Sense seguiment','Modificada manualment','Modificació desconeguda','Compleció global','Global desconeguda','Població'],
        ['Manual','Automàtic'],
        'Població activa actual amb rol student: {n}. Activitats sense seguiment excloses: {disabled}.',
        'Les barres mostren estats incomplets registrats, no tots els estudiants sense compleció. Els estats desconeguts i sense seguiment es mantenen separats. La compleció no demostra aprenentatge. No s’han consultat activitats obligatòries, elegibilitat individual ni calendaris: no es pot afirmar retard ni una seqüència obligatòria. La compleció global segueix la configuració de Moodle, no una suma d’aprovats i no aprovats.'),
    'eu': ('Jardueren osatze behatua', 'Osatu gabeko egoera erregistratuak',
        ['Jarduera','Jarraipena','Osatu gabe','Osatua','Osatua-gainditua','Osatua-ez gainditua','Ezezaguna','Jarraipenik gabe','Eskuz aldatua','Aldaketa ezezaguna','Orokorrean osatua','Orokorra ezezaguna','Populazioa'],
        ['Eskuzkoa','Automatikoa'],
        'Student rola duen uneko populazio aktiboa: {n}. Jarraipenik gabeko jarduera baztertuak: {disabled}.',
        'Barrek osatu gabeko egoera erregistratuak erakusten dituzte. Egoera ezezagunak eta jarraipenik gabekoak bereizten dira. Osatzeak ez du ikaskuntza frogatzen. Ez dira derrigorrezko jarduerak, banakako baldintzak edo egutegiak kontsultatu; ezin da atzerapenik edo derrigorrezko sekuentziarik ondorioztatu. Osatze orokorrak Moodleren konfigurazioa jarraitzen du, ez gainditutako eta gainditu gabeko egoeren batura.'),
}


def present_completion(language,data,rows):
    title,metric,columns,tracking,population,caption=TEXT[language]
    for row in rows: row['tracking_label']=tracking[row['tracking']-1]
    return {'title':title,'metric_label':metric,'completion_columns':columns,'completion_keys':list(KEYS),
        'population_label':population.format(n=data['coverage']['student_rows'],disabled=data['coverage']['tracking_disabled_modules']),
        'caption':caption}
