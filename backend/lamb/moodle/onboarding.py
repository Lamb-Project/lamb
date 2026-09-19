"""Fixed initial read. No LLM, command discovery, student records or Moodle writes."""
import html
import re
from .runtime import MoodleRuntime

TEXT = {
    'en': ('Moodle course summary', 'Initial read-only sync completed. Enrolled courses: {count}.',
           'This summary contains course IDs and names only. No student records, posts or grades were read. Which course would you like to work with?'),
    'es': ('Resumen de cursos de Moodle', 'Sincronización inicial de solo lectura completada. Cursos matriculados: {count}.',
           'Este resumen contiene solo identificadores y nombres de cursos. No se han leído datos de estudiantes, mensajes ni notas. ¿Con qué curso quieres trabajar?'),
    'ca': ('Resum de cursos de Moodle', 'Sincronització inicial de només lectura completada. Cursos matriculats: {count}.',
           "Aquest resum conté només identificadors i noms de cursos. No s’han llegit dades d’estudiants, missatges ni notes. Amb quin curs vols treballar?"),
    'eu': ('Moodle ikastaroen laburpena', 'Hasierako irakurketa sinkronizazioa amaitu da. Matrikulatutako ikastaroak: {count}.',
           'Laburpen honek ikastaroen identifikatzaileak eta izenak bakarrik ditu. Ez da ikasleen daturik, mezurik edo kalifikaziorik irakurri. Zein ikastarorekin lan egin nahi duzu?'),
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
        lines.append(f"- {int(course['id'])}: {safe_name(course.get('fullname', ''))} ({safe_name(course.get('shortname', ''))})")
    if len(courses) > 100:
        lines.append('… (100 / ' + str(len(courses)) + ')')
    lines.extend(['', ending])
    return title, '\n'.join(lines)
