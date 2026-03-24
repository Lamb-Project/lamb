/**
 * API helper for the file-eval module.
 * Reads the JWT from the URL query param `token` and sends it as a Bearer header.
 */

function getToken() {
	if (typeof window === 'undefined') return '';
	const params = new URLSearchParams(window.location.search);
	return params.get('token') || '';
}

/**
 * Decode JWT payload (no signature verify; token is from our backend).
 * @param {string} token
 * @returns {Record<string, unknown>|null}
 */
function parseJwtPayload(token) {
	if (!token) return null;
	const parts = token.split('.');
	if (parts.length !== 3) return null;
	try {
		const b64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
		const pad = b64.length % 4;
		const padded = pad ? b64 + '='.repeat(4 - pad) : b64;
		const json = atob(padded);
		return JSON.parse(json);
	} catch {
		return null;
	}
}

/**
 * LTI activity row id (integer). API paths use this, not resource_link_id (UUID).
 */
function getActivityId() {
	if (typeof window === 'undefined') return '';
	const params = new URLSearchParams(window.location.search);
	const raw = (params.get('activity_id') || '').trim();
	if (/^\d+$/.test(raw)) return raw;
	const payload = parseJwtPayload(getToken());
	const lid = payload?.lti_activity_id;
	if (lid != null && /^\d+$/.test(String(lid))) return String(lid);
	return '';
}

function baseUrl() {
	const cfg = /** @type {any} */ (window).LAMB_CONFIG || {};
	return cfg.API_BASE_URL || '';
}

const MODULE_PREFIX = '/lamb/v1/modules/file_evaluation';

/**
 * @param {string} path
 * @param {RequestInit} [opts]
 */
export async function apiFetch(path, opts = {}) {
	const token = getToken();
	const url = `${baseUrl()}${MODULE_PREFIX}${path}${path.includes('?') ? '&' : '?'}token=${token}`;
	const headers = {
		...(opts.headers || {}),
		Authorization: `Bearer ${token}`
	};
	const res = await fetch(url, { ...opts, headers });
	if (!res.ok) {
		const text = await res.text();
		throw new Error(text || `HTTP ${res.status}`);
	}
	return res.json();
}

/**
 * @param {string} path
 * @param {FormData} formData
 */
export async function apiUpload(path, formData) {
	const token = getToken();
	formData.append('token', token);
	const url = `${baseUrl()}${MODULE_PREFIX}${path}`;
	const res = await fetch(url, {
		method: 'POST',
		headers: { Authorization: `Bearer ${token}` },
		body: formData
	});
	if (!res.ok) {
		const text = await res.text();
		throw new Error(text || `HTTP ${res.status}`);
	}
	return res.json();
}

export { getToken, getActivityId };
