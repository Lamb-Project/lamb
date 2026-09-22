"""Deterministic localized presentation, separate from machine evidence fields."""
from datetime import datetime
from zoneinfo import ZoneInfo


TEXT = {
    'en': {
        'course': 'Course', 'grading-queue': 'Assignments needing grading',
        'course-access': 'Last recorded course access', 'grading_metric': 'Needs grading', 'access_metric': 'Students',
        'recent': 'Access recorded on or after {date}', 'older': 'Last access before {date}',
        'no_course_access_recorded': 'No course access recorded', 'unknown': 'Access data unavailable',
        'window': 'Recency boundary: {date} 00:00 ({tz}). Observed through the snapshot date.',
        'access_population': 'Population: visible active enrolments with the student role; custom roles are not included.',
        'grading_population': 'Population: supported individual online assignments only.',
        'access_caption': 'Last course access is not last site access or a history of resource openings. No recorded access does not prove non-use. Access does not establish reading, comprehension or study time.',
        'grading_caption': 'Counts follow Moodle’s latest-submitted-attempt needs-grading rules. Needs grading is not feedback awaiting release. Workflow release and first-feedback timing were not collected. Team and offline assignments are excluded, not counted as zero. Collection is bounded and is not an atomic course snapshot.',
        'team': 'Team submission counts are not supported.', 'offline': 'Online submissions are disabled.',
        'invalid': 'Moodle counts are missing or inconsistent.', 'unavailable': 'Grading summary unavailable.',
    },
    'es': {
        'course': 'Curso', 'grading-queue': 'Tareas pendientes de calificación',
        'course-access': 'Último acceso registrado al curso', 'grading_metric': 'Pendientes de calificación', 'access_metric': 'Estudiantes',
        'recent': 'Acceso registrado desde {date}', 'older': 'Último acceso anterior a {date}',
        'no_course_access_recorded': 'Sin acceso al curso registrado', 'unknown': 'Datos de acceso no disponibles',
        'window': 'Fecha de referencia: {date} a las 00:00 ({tz}). Observación hasta la fecha de la instantánea.',
        'access_population': 'Población: matrículas activas visibles con el rol student; no se incluyen roles personalizados.',
        'grading_population': 'Población: solo tareas individuales en línea compatibles.',
        'access_caption': 'El último acceso al curso no es el último acceso al sitio ni un historial de apertura de recursos. La ausencia de accesos registrados no demuestra falta de uso. Un acceso no demuestra lectura, comprensión ni tiempo de estudio.',
        'grading_caption': 'Los recuentos siguen las reglas de Moodle para el último intento entregado pendiente de calificación. No equivalen a comentarios pendientes de publicación. No se han consultado la publicación del flujo de calificación ni el tiempo hasta el primer comentario. Las tareas en equipo y sin entrega en línea se excluyen, no se cuentan como cero. La consulta tiene límites y no es una instantánea atómica del curso.',
        'team': 'No se admiten recuentos de entregas en equipo.', 'offline': 'Las entregas en línea están desactivadas.',
        'invalid': 'Los recuentos de Moodle faltan o son incoherentes.', 'unavailable': 'Resumen de calificación no disponible.',
    },
    'ca': {
        'course': 'Curs', 'grading-queue': 'Tasques pendents de qualificació',
        'course-access': 'Últim accés registrat al curs', 'grading_metric': 'Pendents de qualificació', 'access_metric': 'Estudiants',
        'recent': 'Accés registrat des de {date}', 'older': 'Últim accés anterior a {date}',
        'no_course_access_recorded': 'Sense accés al curs registrat', 'unknown': 'Dades d’accés no disponibles',
        'window': 'Data de referència: {date} a les 00:00 ({tz}). Observació fins a la data de la instantània.',
        'access_population': 'Població: matrícules actives visibles amb el rol student; no s’hi inclouen rols personalitzats.',
        'grading_population': 'Població: només tasques individuals en línia compatibles.',
        'access_caption': 'L’últim accés al curs no és l’últim accés al lloc ni un historial d’obertura de recursos. L’absència d’accessos registrats no demostra manca d’ús. Un accés no demostra lectura, comprensió ni temps d’estudi.',
        'grading_caption': 'Els recomptes segueixen les regles de Moodle per a l’últim intent lliurat pendent de qualificació. No equivalen a comentaris pendents de publicació. No s’han consultat la publicació del flux de qualificació ni el temps fins al primer comentari. Les tasques en equip i sense lliurament en línia s’exclouen, no es compten com a zero. La consulta té límits i no és una instantània atòmica del curs.',
        'team': 'No s’admeten recomptes de lliuraments en equip.', 'offline': 'Els lliuraments en línia estan desactivats.',
        'invalid': 'Els recomptes de Moodle falten o són incoherents.', 'unavailable': 'Resum de qualificació no disponible.',
    },
    'eu': {
        'course': 'Ikastaroa', 'grading-queue': 'Kalifikatzeko dauden zereginak',
        'course-access': 'Ikastarorako azken sarbide erregistratua', 'grading_metric': 'Kalifikatzeko', 'access_metric': 'Ikasleak',
        'recent': '{date} datatik aurrera erregistratutako sarbidea', 'older': '{date} baino lehenagoko azken sarbidea',
        'no_course_access_recorded': 'Ez dago ikastarorako sarbiderik erregistratuta', 'unknown': 'Sarbide-datuak ez daude erabilgarri',
        'window': 'Erreferentzia-data: {date}, 00:00 ({tz}). Behaketa gordetako emaitzaren datara arte.',
        'access_population': 'Populazioa: student rola duten matrikula aktibo ikusgaiak; rol pertsonalizatuak ez dira sartzen.',
        'grading_population': 'Populazioa: banakako lineako zeregin bateragarriak soilik.',
        'access_caption': 'Ikastarorako azken sarbidea ez da gunerako azken sarbidea, ezta baliabideak irekitzeko historia ere. Erregistratutako sarbiderik ez izateak ez du erabilerarik eza frogatzen. Sarbideak ez du irakurketa, ulermena edo ikasteko denbora frogatzen.',
        'grading_caption': 'Kopuruek Moodleren azken saiakera entregatua kalifikatzeko arauak jarraitzen dituzte. Ez dira argitaratzeko dauden iruzkinen kopuruak. Ez dira kalifikazio-fluxuaren argitalpena edo lehen iruzkinaren denbora kontsultatu. Taldeko eta lineako entregarik gabeko zereginak kanpoan geratzen dira, ez dira zero gisa zenbatzen. Kontsulta mugatua da eta ez da ikastaroaren une bakarreko argazkia.',
        'team': 'Taldeko entregen kopuruak ez dira onartzen.', 'offline': 'Lineako entregak desgaituta daude.',
        'invalid': 'Moodleko kopuruak falta dira edo ez datoz bat.', 'unavailable': 'Kalifikazio-laburpena ez dago erabilgarri.',
    },
}

REASONS = {
    'team_submission_count_not_supported': 'team',
    'online_submissions_disabled': 'offline',
    'grading_counts_missing_or_invalid': 'invalid',
    'grading_counts_inconsistent': 'invalid',
}


def present(recipe, language, timezone, data, rows):
    if recipe == 'resource-reach':
        from .resource_text import present_resource
        return present_resource(language, timezone, data)
    text = TEXT[language]
    access = recipe == 'course-access'
    fields = {
        'title': text[recipe],
        'metric_label': text['access_metric' if access else 'grading_metric'],
        'population_label': text['access_population' if access else 'grading_population'],
        'caption': text['access_caption' if access else 'grading_caption'],
    }
    if access:
        boundary = datetime.fromtimestamp(data['window']['since'], ZoneInfo(timezone)).date().isoformat()
        fields['window_label'] = text['window'].format(date=boundary, tz=timezone)
        for row in rows:
            row['name'] = text[row['id']].format(date=boundary)
    else:
        for row in rows:
            if row['reason']:
                row['reason_code'] = row['reason']
                row['reason'] = text[REASONS.get(row['reason'], 'unavailable')]
    return fields
