/** @type {Record<string, Record<string, string>>} */
const labels = {
  en: { title: 'Activities', intro: 'Activities in your organization, grouped by LMS and course.', unknownLms: 'LMS not yet recorded', unknownCourse: 'Course not yet recorded', empty: 'No activities in this organization yet.', owner: 'Owner', instructor: 'Instructor', catalogue: 'Catalogue only', open: 'Open activity', access: 'Open this activity as an instructor from your LMS to establish access.', loading: 'Loading activities…', error: 'Could not load activities.', archived: 'Archived', chat: 'Chat', file_evaluation: 'Supervised Assessment', llm_access: 'LLM access' },
  es: { title: 'Actividades', intro: 'Actividades de tu organización, agrupadas por LMS y curso.', unknownLms: 'LMS aún no registrado', unknownCourse: 'Curso aún no registrado', empty: 'Todavía no hay actividades en esta organización.', owner: 'Propietario', instructor: 'Docente', catalogue: 'Solo catálogo', open: 'Abrir actividad', access: 'Abre esta actividad como docente desde tu LMS para establecer el acceso.', loading: 'Cargando actividades…', error: 'No se pudieron cargar las actividades.', archived: 'Archivada', chat: 'Chat', file_evaluation: 'Evaluación supervisada', llm_access: 'Acceso a LLM' },
  ca: { title: 'Activitats', intro: 'Activitats de la teva organització, agrupades per LMS i curs.', unknownLms: 'LMS encara no registrat', unknownCourse: 'Curs encara no registrat', empty: 'Encara no hi ha activitats en aquesta organització.', owner: 'Propietari', instructor: 'Docent', catalogue: 'Només catàleg', open: 'Obre l’activitat', access: 'Obre aquesta activitat com a docent des del teu LMS per establir-hi l’accés.', loading: 'Carregant activitats…', error: 'No s’han pogut carregar les activitats.', archived: 'Arxivada', chat: 'Xat', file_evaluation: 'Avaluació supervisada', llm_access: 'Accés a LLM' },
  eu: { title: 'Jarduerak', intro: 'Zure erakundeko jarduerak, LMSaren eta ikastaroaren arabera multzokatuta.', unknownLms: 'LMSa oraindik erregistratu gabe', unknownCourse: 'Ikastaroa oraindik erregistratu gabe', empty: 'Oraindik ez dago jarduerarik erakunde honetan.', owner: 'Jabea', instructor: 'Irakaslea', catalogue: 'Katalogoa soilik', open: 'Ireki jarduera', access: 'Ireki jarduera hau irakasle gisa zure LMSetik sarbidea ezartzeko.', loading: 'Jarduerak kargatzen…', error: 'Ezin izan dira jarduerak kargatu.', archived: 'Artxibatuta', chat: 'Txata', file_evaluation: 'Ebaluazio gainbegiratua', llm_access: 'LLM sarbidea' }
};

/** @param {string | null | undefined} locale */
export const activitiesText = locale => labels[locale || "en"] || labels.en;

/** @param {any[]} activities */
export function groupActivities(activities) {
  const groups = new Map();
  for (const activity of activities) {
    // Unknown LMS/course records are kept separate until verified, never guessed from names.
    const key = JSON.stringify([activity.lms_scope || `unknown-${activity.id}`, activity.context_id || `unknown-${activity.id}`]);
    if (!groups.has(key)) groups.set(key, { key, lms: activity.lms_origin, course: activity.context_title || activity.context_id, activities: [] });
    groups.get(key).activities.push(activity);
  }
  return [...groups.values()].sort((a, b) => `${a.lms} ${a.course}`.localeCompare(`${b.lms} ${b.course}`));
}
