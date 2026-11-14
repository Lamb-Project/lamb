/**
 * The LMS activity a teacher came from (#562).
 *
 * A teacher reaches LAMB Creator from an activity with `?token=<session>&activity=<return token>`.
 * The return token is kept per browser tab (sessionStorage, not localStorage: another tab that came
 * from another activity keeps its own) and takes the same window back to that activity.
 *
 * The token is opaque and signed. Its payload is read here only for the course name and the expiry;
 * the backend alone decides whether it is valid. Storage and decoding never throw: any failure means
 * "this tab has no activity".
 */
import { browser } from '$app/environment';
import { getLambApiUrl } from '$lib/config';

/** sessionStorage key of the return token. */
export const STORAGE_KEY = 'ltiActivityReturn';
/** Name of the address parameter that carries the return token. */
export const ACTIVITY_PARAM = 'activity';

/** @typedef {{ token: string, title: string, exp: number }} ActivityReturn */

/** @returns {Storage | null} */
function tabStorage() {
	try {
		return browser && typeof window !== 'undefined' ? window.sessionStorage || null : null;
	} catch {
		return null; // storage blocked by the browser
	}
}

/**
 * Course name and expiry (unix seconds) of a return token; null when it cannot be read.
 * @param {string | null | undefined} token
 * @returns {{ title: string, exp: number } | null}
 */
export function decodeActivity(token) {
	try {
		const parts = String(token || '').split('.');
		if (parts.length !== 3 || !parts[1]) return null;
		const base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
		const binary = atob(base64.padEnd(Math.ceil(base64.length / 4) * 4, '='));
		const json = new TextDecoder().decode(Uint8Array.from(binary, (char) => char.charCodeAt(0)));
		const payload = JSON.parse(json);
		if (!payload || typeof payload !== 'object' || typeof payload.exp !== 'number' || !Number.isFinite(payload.exp)) {
			return null;
		}
		const title = typeof payload.lti_context_title === 'string' ? payload.lti_context_title.trim() : '';
		return { title, exp: payload.exp };
	} catch {
		return null;
	}
}

/** Forget the activity of this tab. */
export function clearActivity() {
	try {
		tabStorage()?.removeItem(STORAGE_KEY);
	} catch {
		/* nothing was kept */
	}
}

/**
 * Keep a return token for this tab. A token that cannot be read or has expired is not kept.
 * @param {string | null | undefined} token
 * @param {number} [now] - milliseconds
 * @returns {boolean} whether it was kept
 */
export function storeActivity(token, now = Date.now()) {
	try {
		const info = decodeActivity(token);
		const storage = tabStorage();
		if (!token || !info || info.exp * 1000 <= now || !storage) return false;
		storage.setItem(STORAGE_KEY, token);
		return true;
	} catch {
		return false;
	}
}

/**
 * The activity of this tab, or null. A stored token that is broken or has expired is dropped.
 * @param {number} [now] - milliseconds
 * @returns {ActivityReturn | null}
 */
export function readActivity(now = Date.now()) {
	try {
		const token = tabStorage()?.getItem(STORAGE_KEY);
		if (!token) return null;
		const info = decodeActivity(token);
		if (!info || info.exp * 1000 <= now) {
			clearActivity();
			return null;
		}
		return { token, ...info };
	} catch {
		return null;
	}
}

/**
 * Keep the return token an address carries, if it carries one.
 * @param {URL | string} address
 * @returns {boolean} whether a token was kept
 */
export function captureActivity(address) {
	try {
		return storeActivity(new URL(String(address), 'http://localhost').searchParams.get(ACTIVITY_PARAM));
	} catch {
		return false;
	}
}

/**
 * The same address without the session token and the return token.
 * @param {string} href - an absolute address
 * @returns {string}
 */
export function stripSessionParams(href) {
	const clean = new URL(href);
	clean.searchParams.delete('token');
	clean.searchParams.delete(ACTIVITY_PARAM);
	return clean.toString();
}

/**
 * The same address carrying the return token of this tab, the way the activity sends a teacher in.
 * Signing in through an address replaces the session, and ending a session forgets the activity; an
 * organization switch is the same person in the same visit, so the token travels with it.
 * @param {string} address - absolute, or relative to this page
 * @returns {string}
 */
export function carryActivity(address) {
	const current = readActivity();
	if (!current) return address;
	try {
		const target = new URL(address, window.location.href);
		target.searchParams.set(ACTIVITY_PARAM, current.token);
		return target.toString();
	} catch {
		return address;
	}
}

/**
 * Backend address that takes the window back to the activity.
 * @param {string} token
 * @returns {string}
 */
export function activityReturnUrl(token) {
	return `${getLambApiUrl('/lamb/v1/lti/return')}?token=${encodeURIComponent(token)}`;
}
