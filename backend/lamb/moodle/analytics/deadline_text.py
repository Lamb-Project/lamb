"""Calendar labels; source dates remain exact, immutable evidence."""
from datetime import datetime
from zoneinfo import ZoneInfo

TEXT = {
    'en': {
        'title':'Stored course schedule','metric':'Deadlines','week':'Week starting',
        'activity':'Activity','opens':'Opens','due':'Due','closes':'Closes',
        'unset':'Not set','inside':'In requested window','outside':'Outside requested window',
        'partial':'Partial week','timeline':'Calendar events','weekly':'Weekly deadline density',
        'window':'From {since} (inclusive) to {until} (exclusive).',
        'caption':'Stored assignment and quiz defaults, not individual or group deadlines. Overrides and learner eligibility were not checked. Weekly counts include assignment due dates and quiz closing dates only, not opening or cutoff events. Counts are not study hours or evidence of lateness. Boundary weeks may be partial.',
    },
    'es': {
        'title':'Calendario base del curso','metric':'Fechas límite','week':'Semana del',
        'activity':'Actividad','opens':'Apertura','due':'Fecha límite','closes':'Cierre',
        'unset':'Sin definir','inside':'Dentro del intervalo solicitado','outside':'Fuera del intervalo solicitado',
        'partial':'Semana parcial','timeline':'Eventos del calendario','weekly':'Fechas límite por semana',
        'window':'Desde {since} (incluido) hasta {until} (excluido).',
        'caption':'Fechas base de tareas y cuestionarios, no plazos individuales o de grupo. No se han comprobado las excepciones ni la elegibilidad del alumnado. El recuento semanal incluye solo fechas de entrega de tareas y cierres de cuestionarios, no aperturas ni fechas de corte. Los recuentos no son horas de estudio ni pruebas de retraso. Las semanas de los extremos pueden ser parciales.',
    },
    'ca': {
        'title':'Calendari base del curs','metric':'Dates límit','week':'Setmana del',
        'activity':'Activitat','opens':'Obertura','due':'Data límit','closes':'Tancament',
        'unset':'Sense definir','inside':'Dins de l’interval sol·licitat','outside':'Fora de l’interval sol·licitat',
        'partial':'Setmana parcial','timeline':'Esdeveniments del calendari','weekly':'Dates límit per setmana',
        'window':'Des de {since} (inclòs) fins a {until} (exclòs).',
        'caption':'Dates base de tasques i qüestionaris, no terminis individuals o de grup. No s’han comprovat les excepcions ni l’elegibilitat de l’alumnat. El recompte setmanal inclou només dates de lliurament de tasques i tancaments de qüestionaris, no obertures ni dates de tall. Els recomptes no són hores d’estudi ni proves de retard. Les setmanes dels extrems poden ser parcials.',
    },
    'eu': {
        'title':'Ikastaroaren oinarrizko egutegia','metric':'Epemugak','week':'Astearen hasiera',
        'activity':'Jarduera','opens':'Irekiera','due':'Epemuga','closes':'Itxiera',
        'unset':'Zehaztu gabe','inside':'Eskatutako tartean','outside':'Eskatutako tartetik kanpo',
        'partial':'Aste partziala','timeline':'Egutegiko gertaerak','weekly':'Asteko epemugak',
        'window':'{since} datatik (barne) {until} datara (kanpo).',
        'caption':'Zereginen eta galdetegien oinarrizko datak, ez banakako edo taldeko epemugak. Ez dira salbuespenak edo ikasleen hautagarritasuna egiaztatu. Asteko kopuruak zereginen epemugak eta galdetegien itxierak soilik jasotzen ditu, ez irekierak edo azken onarpen-datak. Kopuruak ez dira ikasketa-orduak edo atzerapenaren frogak. Muturretako asteak partzialak izan daitezke.',
    },
}


def present_deadlines(language,timezone,data,rows):
    text=TEXT[language]
    zone=ZoneInfo(timezone)
    local=lambda value: datetime.fromtimestamp(value,zone).isoformat()
    for row in rows:
        for key in ('opens','due','closes'):
            row[key+'_label']=local(row[key]) if row[key] else text['unset']
        row['window_status_label']=text['unset' if not row['due'] else 'inside' if row['in_window'] else 'outside']
    return {'view_kind':'deadline-calendar-v1','title':text['title'],'metric_label':text['metric'],
        'calendar_labels':text,'caption':text['caption'],
        'window_label':text['window'].format(since=local(data['window']['since']),until=local(data['window']['until']))}
