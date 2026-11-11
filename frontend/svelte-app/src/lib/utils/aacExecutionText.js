/** @type {Record<string,string[]>} */
const messages = {
    en: ['Task execution', 'Mode', 'Auto', 'Guided', 'Assistant calls', 'Tools', 'New task', 'Changes', 'Show me', 'Previous values', 'Saved values', 'Review restoration', 'Pending', 'Running', 'Completed', 'Failed', 'Skipped', 'Outcome uncertain', 'LEGATUS evaluation', 'Human evaluation', 'Test results'],
    es: ['Ejecución de la tarea', 'Modo', 'Auto', 'Guiado', 'Llamadas a asistentes', 'Herramientas', 'Nueva tarea', 'Cambios', 'Ver resultado', 'Valores anteriores', 'Valores guardados', 'Revisar restauración', 'Pendiente', 'En curso', 'Completado', 'Fallido', 'Omitido', 'Resultado incierto', 'Evaluación de LEGATUS', 'Evaluación humana', 'Resultados de pruebas'],
    ca: ['Execució de la tasca', 'Mode', 'Auto', 'Guiat', 'Crides a assistents', 'Eines', 'Tasca nova', 'Canvis', 'Mostra el resultat', 'Valors anteriors', 'Valors desats', 'Revisar la restauració', 'Pendent', 'En curs', 'Completat', 'Fallat', 'Omès', 'Resultat incert', 'Avaluació de LEGATUS', 'Avaluació humana', 'Resultats de les proves'],
    eu: ['Zereginaren exekuzioa', 'Modua', 'Auto', 'Gidatua', 'Laguntzaileen deiak', 'Tresnak', 'Zeregin berria', 'Aldaketak', 'Erakutsi emaitza', 'Aurreko balioak', 'Gordetako balioak', 'Berrikusi leheneratzea', 'Zain', 'Exekutatzen', 'Osatuta', 'Huts egin du', 'Saltatuta', 'Emaitza ezezaguna', 'LEGATUSen ebaluazioa', 'Giza ebaluazioa', 'Proben emaitzak']
};
const keys = ['execution','mode','auto','guided','calls','tools','newTask','changes','showMe','previous','current','restore','pending','running','completed','failed','skipped','uncertain','legatus','human','testResults'];
/** @param {string|null|undefined} language */
export function executionText(language) { return Object.fromEntries(keys.map((key, i) => [key, (messages[language || 'en'] || messages.en)[i]])); }
