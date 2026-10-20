/** Status line after an AAC turn: the agent has stopped and says what it waits for. */
/** @type {Record<string, string[]>} */
const text = {
	en: ['Done · waiting for your instructions', 'Waiting for your approval'],
	es: ['Hecho · esperando tus instrucciones', 'Esperando tu aprobación'],
	ca: ['Fet · esperant les teves instruccions', 'Esperant la teva aprovació'],
	eu: ['Eginda · zure argibideen zain', 'Zure onarpenaren zain']
};

/**
 * @param {string | null | undefined} language session response language
 * @param {boolean} awaitingApproval an approval card is pending
 */
export function turnEndText(language, awaitingApproval) {
	const labels = text[String(language || 'en').split('-')[0]] || text.en;
	return labels[awaitingApproval ? 1 : 0];
}
