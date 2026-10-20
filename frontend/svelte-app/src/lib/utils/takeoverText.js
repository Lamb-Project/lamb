/** Texts for administrators acting as a creator (#523). */
/** @type {Record<string, Record<string, string>>} */
const text = {
	en: {actAs:'Act as', actAsTitle:'Act as this creator to give support', confirm:'Act as {name} for up to 60 minutes? You will see and change LAMB exactly as this creator. Moodle stays read-only. The creator will be told, and your actions are logged.', acting:'You are acting as {name} ({email})', until:'until {time}', back:'Return to my account', failed:'Could not act as this user: {reason}', noticeTitle:'An administrator acted on your account', noticeActive:'{actor} ({email}) is acting on your account now, since {start}.', noticeEnded:'{actor} ({email}) acted on your account from {start} to {end}.', noticeWhy:'Administrators do this to help with support. Contact them if you did not expect it.', dismiss:'OK'},
	es: {actAs:'Actuar como', actAsTitle:'Actuar como este creador para darle soporte', confirm:'¿Actuar como {name} durante un máximo de 60 minutos? Verás y cambiarás LAMB exactamente como este creador. Moodle queda en solo lectura. Se avisará al creador y tus acciones quedan registradas.', acting:'Estás actuando como {name} ({email})', until:'hasta las {time}', back:'Volver a mi cuenta', failed:'No se ha podido actuar como este usuario: {reason}', noticeTitle:'Un administrador ha actuado en tu cuenta', noticeActive:'{actor} ({email}) está actuando en tu cuenta ahora, desde {start}.', noticeEnded:'{actor} ({email}) actuó en tu cuenta de {start} a {end}.', noticeWhy:'La administración lo hace para ayudar en tareas de soporte. Ponte en contacto si no lo esperabas.', dismiss:'De acuerdo'},
	ca: {actAs:'Actua com a', actAsTitle:'Actua com aquest creador per donar-li suport', confirm:'Vols actuar com a {name} durant un màxim de 60 minuts? Veuràs i canviaràs LAMB exactament com aquest creador. Moodle queda en només lectura. S’avisarà el creador i les teves accions queden registrades.', acting:'Estàs actuant com a {name} ({email})', until:'fins a les {time}', back:'Torna al meu compte', failed:'No s’ha pogut actuar com aquest usuari: {reason}', noticeTitle:'Un administrador ha actuat al teu compte', noticeActive:'{actor} ({email}) està actuant al teu compte ara, des de {start}.', noticeEnded:'{actor} ({email}) va actuar al teu compte de {start} a {end}.', noticeWhy:'L’administració ho fa per ajudar en tasques de suport. Posa-t’hi en contacte si no t’ho esperaves.', dismiss:'D’acord'},
	eu: {actAs:'Jardun honela', actAsTitle:'Jardun sortzaile honen gisa laguntza emateko', confirm:'{name} gisa jardun gehienez 60 minutuz? LAMB sortzaile honek bezala ikusi eta aldatuko duzu. Moodle irakurtzeko soilik geratzen da. Sortzaileari jakinaraziko zaio, eta zure ekintzak erregistratzen dira.', acting:'{name} ({email}) gisa ari zara', until:'{time} arte', back:'Itzuli nire kontura', failed:'Ezin izan da erabiltzaile honen gisa jardun: {reason}', noticeTitle:'Administratzaile batek zure kontuan jardun du', noticeActive:'{actor} ({email}) zure kontuan ari da orain, {start}(e)tik.', noticeEnded:'{actor} ({email}) zure kontuan aritu zen {start}(e)tik {end} arte.', noticeWhy:'Administrazioak laguntza emateko egiten du. Jarri harremanetan espero ez bazenuen.', dismiss:'Ados'}
};

/** @param {string | null | undefined} language */
export function takeoverText(language) { return text[String(language || 'en').split('-')[0]] || text.en; }

/** @param {string} template @param {Record<string, any>} values */
export function fill(template, values) {
	return template.replace(/\{(\w+)\}/g, (_, k) => (values[k] ?? '').toString());
}

/** @param {number | null | undefined} seconds @param {string | null | undefined} language */
export function when(seconds, language, timeOnly = false) {
	if (!seconds) return '';
	const options = /** @type {Intl.DateTimeFormatOptions} */ (timeOnly ? { timeStyle: 'short' } : { dateStyle: 'medium', timeStyle: 'short' });
	return new Intl.DateTimeFormat(language || 'en', options).format(new Date(seconds * 1000));
}
