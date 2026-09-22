"""Localized observed-view presentation, not general activity claims."""
from .resource_text import present_resource

TEXT={
    'en':('Recorded daily views',['Date','Recorded views','Distinct student viewers','Course views','Resource views','Chapter views']),
    'es':('Visitas diarias registradas',['Fecha','Visitas registradas','Estudiantes visitantes únicos','Visitas al curso','Visitas a recursos','Visitas a capítulos']),
    'ca':('Visites diàries registrades',['Data','Visites registrades','Estudiants visitants únics','Visites al curs','Visites a recursos','Visites a capítols']),
    'eu':('Eguneko bisita erregistratuak',['Data','Bisita erregistratuak','Ikasle bisitari bakarrak','Ikastaroko bisitak','Baliabideetako bisitak','Kapituluetako bisitak']),
}
LIMITS={
    'en':'Only course, resource and chapter views are included, not all activity. Daily distinct viewers overlap; do not sum them. Boundary days may be partial. ',
    'es':'Solo se incluyen visitas al curso, recursos y capítulos, no toda la actividad. Los visitantes únicos diarios pueden repetirse entre días; no se deben sumar. Los días de los extremos pueden ser parciales. ',
    'ca':'Només s’inclouen visites al curs, recursos i capítols, no tota l’activitat. Els visitants únics diaris es poden repetir entre dies; no s’han de sumar. Els dies dels extrems poden ser parcials. ',
    'eu':'Ikastaroko, baliabideetako eta kapituluetako bisitak soilik sartzen dira, ez jarduera guztia. Eguneko bisitari bakarrak egun desberdinetan errepika daitezke; ez batu. Hasierako eta amaierako egunak partzialak izan daitezke. ',
}
HEATMAP={
    'en':('Recorded views by weekday and hour','Weekday','Hour',
        ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'],
        'Raw counts, not rates: weekdays can have different exposure. Repeated clock-change hours share a cell. No deadline-relative activity was collected. '),
    'es':('Visitas registradas por día y hora','Día de la semana','Hora',
        ['Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo'],
        'Recuentos, no tasas: los días pueden tener distinta exposición. Las horas repetidas por el cambio horario comparten celda. No se ha recogido actividad relativa a fechas límite. '),
    'ca':('Visites registrades per dia i hora','Dia de la setmana','Hora',
        ['Dilluns','Dimarts','Dimecres','Dijous','Divendres','Dissabte','Diumenge'],
        'Recomptes, no taxes: els dies poden tenir una exposició diferent. Les hores repetides pel canvi horari comparteixen cel·la. No s’ha recollit activitat relativa a dates límit. '),
    'eu':('Bisita erregistratuak asteko egunaren eta orduaren arabera','Asteko eguna','Ordua',
        ['Astelehena','Asteartea','Asteazkena','Osteguna','Ostirala','Larunbata','Igandea'],
        'Kopuruak dira, ez tasak: egunek esposizio desberdina izan dezakete. Ordu-aldaketako ordu errepikatuek gelaxka partekatzen dute. Ez da epeekiko jarduerarik jaso. '),
}


def present_views(language,timezone,data):
    title,columns=TEXT[language]
    fields=present_resource(language,timezone,data)
    fields.pop('resource_columns')
    fields['caption']=LIMITS[language]+fields['caption']
    fields.update(title=title,metric_label=columns[1],view_kind='view-trend-v1',view_columns=columns,
        view_keys=['date','recorded_views','unique_student_viewers','course_view','resource_view','chapter_view'])
    return fields


def present_heatmap(language,timezone,data,rows):
    fields=present_views(language,timezone,data)
    title,day_label,hour_label,days,caption=HEATMAP[language]
    for row in rows:row['name']=f"{days[row['weekday']]} {row['hour']:02d}:00"
    fields.pop('view_columns');fields.pop('view_keys')
    fields.update(title=title,view_kind='view-heatmap-v1',heatmap_days=days,
        heatmap_day_label=day_label,heatmap_hour_label=hour_label,
        heatmap_rows=[{'day':days[day],'values':[row['value'] for row in sorted(rows,key=lambda row:row['hour']) if row['weekday']==day]} for day in range(7)],
        caption=caption+fields['caption'])
    return fields
