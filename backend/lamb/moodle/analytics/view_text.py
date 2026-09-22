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


def present_views(language,timezone,data):
    title,columns=TEXT[language]
    fields=present_resource(language,timezone,data)
    fields.pop('resource_columns')
    fields['caption']=LIMITS[language]+fields['caption']
    fields.update(title=title,metric_label=columns[1],view_kind='view-trend-v1',view_columns=columns,
        view_keys=['date','recorded_views','unique_student_viewers','course_view','resource_view','chapter_view'])
    return fields
