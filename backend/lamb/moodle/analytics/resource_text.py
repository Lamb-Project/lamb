"""Fixed resource-reach captions. No generated interpretation of logged events."""
from datetime import datetime
from zoneinfo import ZoneInfo

TEXT = {
    'en': ('Recorded resource reach', ['Resource','Students with recorded views','Module views','Chapter views','Student population'],
        '{count} current active student-role enrolments. Group: {group} (0 = all authorized groups).',
        'Window: {start} inclusive to {end} exclusive ({tz}).',
        'Recorded views are not proof of reading or learning. Unique viewers include chapter views; module and chapter events are counted separately. Historical completeness is unknown: zero means no matching recorded event in the retrieved evidence, not no use. Enrolments, groups and module visibility are current, not historical.'),
    'es': ('Alcance registrado de los recursos', ['Recurso','Estudiantes con visitas registradas','Visitas al módulo','Visitas a capítulos','Población estudiantil'],
        '{count} matrículas activas actuales con rol student. Grupo: {group} (0 = todos los grupos autorizados).',
        'Periodo: desde {start} inclusive hasta {end} exclusive ({tz}).',
        'Las visitas registradas no demuestran lectura ni aprendizaje. Los visitantes únicos incluyen visitas a capítulos; los eventos de módulos y capítulos se cuentan por separado. La integridad histórica es desconocida: cero significa que no hay eventos coincidentes en los datos recuperados, no ausencia de uso. Las matrículas, los grupos y la visibilidad son actuales, no históricos.'),
    'ca': ('Abast registrat dels recursos', ['Recurs','Estudiants amb visites registrades','Visites al mòdul','Visites a capítols','Població estudiantil'],
        '{count} matrícules actives actuals amb rol student. Grup: {group} (0 = tots els grups autoritzats).',
        'Període: des de {start} inclòs fins a {end} exclòs ({tz}).',
        'Les visites registrades no demostren lectura ni aprenentatge. Els visitants únics inclouen visites a capítols; els esdeveniments de mòduls i capítols es compten per separat. La integritat històrica és desconeguda: zero significa que no hi ha esdeveniments coincidents en les dades recuperades, no absència d’ús. Les matrícules, els grups i la visibilitat són actuals, no històrics.'),
    'eu': ('Baliabideen irismen erregistratua', ['Baliabidea','Bisita erregistratuak dituzten ikasleak','Modulu-bisitak','Kapitulu-bisitak','Ikasle-populazioa'],
        'Uneko {count} matrikula aktibo student rolarekin. Taldea: {group} (0 = baimendutako talde guztiak).',
        'Tartea: {start} barne, {end} kanpo ({tz}).',
        'Erregistratutako bisitek ez dute irakurketa edo ikaskuntza frogatzen. Bisitari bakarrek kapitulu-bisitak barne hartzen dituzte; moduluen eta kapituluen gertaerak bereiz zenbatzen dira. Historia osoa den ez dakigu: zeroak berreskuratutako datuetan bat datorren gertaerarik ez dagoela esan nahi du, ez erabilerarik ez dagoela. Matrikulak, taldeak eta ikusgaitasuna unekoak dira, ez historikoak.'),
}


def present_resource(language, timezone, data):
    title, columns, population, window, caption = TEXT[language]
    stamp = lambda value: datetime.fromtimestamp(value,ZoneInfo(timezone)).isoformat()
    return {'title':title,'metric_label':columns[1],'resource_columns':columns,
            'population_label':population.format(count=data['coverage']['student_rows'],group=data['group_id']),
            'window_label':window.format(start=stamp(data['window']['since']),end=stamp(data['window']['until']),tz=timezone),
            'caption':caption}
