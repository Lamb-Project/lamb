/** Chart chrome is localized independently of immutable saved evidence. */
const messages = {
    en: {
        chart: 'Assignment submissions', back: 'Back to conversation', loading: 'Loading chart…',
        error: 'The chart is unavailable. Check your Moodle connection and course access, then retry.',
        imageError: 'The image could not be loaded. The saved figures remain available below.', retry: 'Retry',
        read: 'assignments read', partial: 'Incomplete data', omitted: 'Assignments omitted by the limit',
        empty: 'No assignments were found in this course.', unavailable: 'No supported assignment counts are available.',
        extensions: 'Individual extensions and overrides were not checked. Outstanding does not necessarily mean late.',
        download: 'Download SVG', table: 'Exact values (scroll horizontally if needed)',
        submitted: 'Submitted', outstanding: 'Outstanding',
        reasons: {team: 'Team assignments are outside this pilot.', offline: 'Online submissions are disabled.',
            summary: 'The all-groups grading summary is unavailable.', counts: 'Moodle returned inconsistent counts.',
            unavailable: 'The grading summary could not be read.'}
    },
    es: {
        chart: 'Entregas de tareas', back: 'Volver a la conversación', loading: 'Cargando gráfico…',
        error: 'El gráfico no está disponible. Comprueba la conexión con Moodle y el acceso al curso, y vuelve a intentarlo.',
        imageError: 'No se ha podido cargar la imagen. Los datos guardados siguen disponibles debajo.', retry: 'Reintentar',
        read: 'tareas consultadas', partial: 'Datos incompletos', omitted: 'Tareas omitidas por el límite',
        empty: 'No se han encontrado tareas en este curso.', unavailable: 'No hay recuentos de tareas compatibles disponibles.',
        extensions: 'No se han comprobado las prórrogas ni las excepciones individuales. Una entrega pendiente no es necesariamente una entrega atrasada.',
        download: 'Descargar SVG', table: 'Valores exactos (desplázate horizontalmente si es necesario)',
        submitted: 'Entregadas', outstanding: 'Pendientes',
        reasons: {team: 'Las tareas en equipo quedan fuera de este piloto.', offline: 'Las entregas en línea están desactivadas.',
            summary: 'El resumen de calificación de todos los grupos no está disponible.', counts: 'Moodle ha devuelto recuentos incoherentes.',
            unavailable: 'No se ha podido consultar el resumen de calificación.'}
    },
    ca: {
        chart: 'Lliuraments de tasques', back: 'Tornar a la conversa', loading: 'S’està carregant el gràfic…',
        error: 'El gràfic no està disponible. Comprova la connexió amb Moodle i l’accés al curs, i torna-ho a provar.',
        imageError: 'No s’ha pogut carregar la imatge. Les dades desades continuen disponibles a sota.', retry: 'Torna-ho a provar',
        read: 'tasques consultades', partial: 'Dades incompletes', omitted: 'Tasques omeses pel límit',
        empty: 'No s’han trobat tasques en aquest curs.', unavailable: 'No hi ha recomptes de tasques compatibles disponibles.',
        extensions: 'No s’han comprovat les pròrrogues ni les excepcions individuals. Un lliurament pendent no és necessàriament un lliurament fora de termini.',
        download: 'Descarrega l’SVG', table: 'Valors exactes (desplaça’t horitzontalment si cal)',
        submitted: 'Lliurades', outstanding: 'Pendents',
        reasons: {team: 'Les tasques en equip queden fora d’aquest pilot.', offline: 'Els lliuraments en línia estan desactivats.',
            summary: 'El resum de qualificació de tots els grups no està disponible.', counts: 'Moodle ha retornat recomptes incoherents.',
            unavailable: 'No s’ha pogut consultar el resum de qualificació.'}
    },
    eu: {
        chart: 'Zereginen entregak', back: 'Itzuli elkarrizketara', loading: 'Grafikoa kargatzen…',
        error: 'Grafikoa ez dago erabilgarri. Egiaztatu Moodleko konexioa eta ikastarorako sarbidea, eta saiatu berriro.',
        imageError: 'Ezin izan da irudia kargatu. Gordetako datuak behean daude.', retry: 'Saiatu berriro',
        read: 'kontsultatutako zereginak', partial: 'Datu osatugabeak', omitted: 'Mugagatik kanpo utzitako zereginak',
        empty: 'Ez da zereginik aurkitu ikastaro honetan.', unavailable: 'Ez dago zeregin bateragarrien kopururik erabilgarri.',
        extensions: 'Ez dira banakako luzapenak edo salbuespenak egiaztatu. Zain dagoen entrega bat ez da nahitaez berandu egindako entrega.',
        download: 'Deskargatu SVG', table: 'Balio zehatzak (mugitu horizontalki behar izanez gero)',
        submitted: 'Entregatuta', outstanding: 'Zain',
        reasons: {team: 'Taldeko zereginak proba honetatik kanpo daude.', offline: 'Lineako entregak desgaituta daude.',
            summary: 'Talde guztien kalifikazio-laburpena ez dago erabilgarri.', counts: 'Moodlek kopuru bateraezinak itzuli ditu.',
            unavailable: 'Ezin izan da kalifikazio-laburpena irakurri.'}
    }
};
export function chartText(language) {
    return messages[String(language || 'en').split('-')[0]] || messages.en;
}
const legacyReasons = {
    'Team submissions are outside this pilot': 'team',
    'Online submissions are disabled': 'offline',
    'All-groups grading summary unavailable': 'summary',
    'Inconsistent Moodle counts; retry the chart': 'counts'
};
export function chartReason(row, language) {
    const reasons = chartText(language).reasons;
    return reasons[row.reason_code || legacyReasons[row.reason]] || reasons.unavailable;
}
