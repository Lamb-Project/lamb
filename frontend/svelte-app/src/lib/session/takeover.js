import { browser } from '$app/environment';
import { base } from '$app/paths';
import { get } from 'svelte/store';
import { user } from '$lib/stores/userStore';
import { clearCurrentSession, replaceSessionWithLoginData, replaceSessionWithToken } from '$lib/session/sessionManager';
import { startTakeover, endTakeover } from '$lib/services/takeoverService';

/** The administrator's own session, kept while they act as a creator (#523). */
const RETURN_KEY = 'takeoverReturn';

export function takeoverReturn() {
	if (!browser) return null;
	try {
		const saved = JSON.parse(localStorage.getItem(RETURN_KEY) || 'null');
		return saved && saved.token && saved.userData ? saved : null;
	} catch {
		return null;
	}
}

/**
 * Act as a creator: keep this session, switch to the creator's.
 * @param {number | string} userId
 */
export async function beginTakeover(userId) {
	const started = await startTakeover(userId);
	const own = get(user);
	const userData = JSON.parse(localStorage.getItem('userData') || 'null') || { name: own.name, email: own.email };
	localStorage.setItem(RETURN_KEY, JSON.stringify({
		token: own.token, userData, returnPath: window.location.pathname + window.location.search
	}));
	try {
		await replaceSessionWithToken(started.token);
	} catch (error) {
		await returnFromTakeover(false);
		throw error;
	}
	window.location.assign(`${base}/assistants`);
}

let returning = false;

/** End the takeover (unless it already ended) and restore the administrator's session. */
export async function returnFromTakeover(end = true) {
	// The bar and the layout can both notice an ended takeover; restore once.
	if (returning) return;
	returning = true;
	const saved = takeoverReturn();
	if (end) {
		try { await endTakeover(); } catch { /* already ended or expired */ }
	}
	localStorage.removeItem(RETURN_KEY);
	if (!saved) {
		clearCurrentSession();
		window.location.assign(`${base}/`);
		return;
	}
	replaceSessionWithLoginData({ ...saved.userData, token: saved.token });
	window.location.assign(saved.returnPath || `${base}/`);
}
