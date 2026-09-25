"""Fixed initial read. No LLM, command discovery, student records or Moodle writes."""
import html
import re
from .runtime import MoodleRuntime

TEXT = {
    'en': ('Moodle course summary', 'Initial read-only sync completed. Enrolled courses: {count}.',
           'This summary contains course IDs, names and your available course roles. No class roster, posts or grades were read. Which course would you like to work with?'),
    'es': ('Resumen de cursos de Moodle', 'Sincronización inicial de solo lectura completada. Cursos matriculados: {count}.',
           'Este resumen contiene identificadores, nombres y tus roles disponibles en los cursos. No se han leído listas de estudiantes, mensajes ni notas. ¿Con qué curso quieres trabajar?'),
    'ca': ('Resum de cursos de Moodle', 'Sincronització inicial de només lectura completada. Cursos matriculats: {count}.',
           "Aquest resum conté identificadors, noms i els teus rols disponibles als cursos. No s’han llegit llistes d’estudiants, missatges ni notes. Amb quin curs vols treballar?"),
    'eu': ('Moodle ikastaroen laburpena', 'Hasierako irakurketa sinkronizazioa amaitu da. Matrikulatutako ikastaroak: {count}.',
           'Laburpen honek ikastaroen identifikatzaileak, izenak eta zure rol erabilgarriak ditu. Ez da ikasleen zerrendarik, mezurik edo kalifikaziorik irakurri. Zein ikastarorekin lan egin nahi duzu?'),
}


def course_summary(store, language='en'):
    courses = MoodleRuntime(store).execute('course.list', {})
    title, intro, ending = TEXT.get(language, TEXT['en'])
    def safe_name(value):
        # Render external course names as escaped data, never HTML/Markdown links.
        text = html.unescape(re.sub(r'<[^>]*>', '', str(value)))
        return re.sub(r'([\\`*_{}\[\]()<>#!|])', r'\\\1', ' '.join(text.split())[:250])
    lines = [intro.format(count=len(courses))]
    for course in courses[:100]:
        roles = course.get('my_roles')
        role_text = ', '.join(safe_name(role.get('name') or role['shortname']) for role in roles) if roles else ''
        label, unknown, empty = {
            'en': ('Your roles', 'unavailable', 'none returned'),
            'es': ('Tus roles', 'no disponibles', 'ninguno devuelto'),
            'ca': ('Els teus rols', 'no disponibles', 'cap retornat'),
            'eu': ('Zure rolak', 'ez daude erabilgarri', 'ez da rolik itzuli'),
        }.get(language, ('Your roles', 'unavailable', 'none returned'))
        role_text = role_text or (empty if roles == [] else unknown)
        lines.append(f"- {int(course['id'])}: {safe_name(course.get('fullname', ''))} ({safe_name(course.get('shortname', ''))}) · {label}: {role_text}")
    if len(courses) > 100:
        lines.append('… (100 / ' + str(len(courses)) + ')')
    lines.extend(['', ending])
    return title, '\n'.join(lines)
