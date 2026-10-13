// src/lib/services/workshopApi.js
/**
 * Workshop student API client (token lifetime + readable 401s).
 *
 * Two jobs the wizard used to do inline, badly:
 *
 * 1. **Token lifetime.** A workshop token lives 30 minutes; a lesson lasts
 *    45–60. The client renews it in the background — when less than half its
 *    lifetime is left, checked every 5 minutes and whenever the tab becomes
 *    visible again — and writes the fresh token back into the URL, so a reload
 *    or a bookmark keeps working. Renewal is only possible while the current
 *    token is still valid; an expired token is never renewed (that is the
 *    security boundary), and the student is told to re-enter from the course.
 * 2. **A readable 401.** ``detail: "token_expired"`` means "renew and retry
 *    once"; any other 401 is surfaced with the backend's own detail.
 *
 * Auth travels in the custom ``token`` header (the LTI launch contract), NOT
 * the Bearer header, so this client must not use the shared apiFetch helper.
 */

/** Backend detail string for an expired (but genuine) workshop token. */
export const TOKEN_EXPIRED = 'token_expired';

/** How often the background check runs while the workshop page is open. */
export const RENEW_CHECK_INTERVAL_MS = 5 * 60 * 1000;

/** Assumed token lifetime when a token carries no `iat` claim. */
export const ASSUMED_TOKEN_TTL_SECONDS = 1800;

/**
 * Decode a JWT payload (base64url middle segment). No signature check — the
 * server re-verifies on every call; this is only for expiry bookkeeping.
 *
 * @param {string} jwt
 * @returns {any} decoded payload, or {} when unreadable
 */
export function decodeTokenPayload(jwt) {
	try {
		const part = String(jwt || '').split('.')[1] || '';
		if (!part) return {};
		const b64 = part.replace(/-/g, '+').replace(/_/g, '/');
		const pad = b64 + '='.repeat((4 - (b64.length % 4)) % 4);
		const json = decodeURIComponent(
			atob(pad)
				.split('')
				.map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
				.join('')
		);
		return JSON.parse(json);
	} catch {
		return {};
	}
}

/**
 * Token expiry in epoch milliseconds, or null when the token is unreadable.
 * @param {string} jwt
 * @returns {number | null}
 */
export function tokenExpiryMs(jwt) {
	const exp = decodeTokenPayload(jwt).exp;
	return typeof exp === 'number' ? exp * 1000 : null;
}

/**
 * Whether a token is already expired (or unreadable).
 * @param {string} jwt
 * @param {number} [now]
 * @returns {boolean}
 */
export function isTokenExpired(jwt, now = Date.now()) {
	const exp = tokenExpiryMs(jwt);
	return exp === null || exp <= now;
}

/**
 * Whether a token should be renewed now: less than half of its lifetime left.
 *
 * Renewing at the halfway mark means one background call per lesson for a
 * 30-minute token, and the student never reaches the expiry edge.
 *
 * @param {string} jwt
 * @param {number} [now]
 * @returns {boolean}
 */
export function shouldRenewToken(jwt, now = Date.now()) {
	const payload = decodeTokenPayload(jwt);
	const exp = typeof payload.exp === 'number' ? payload.exp * 1000 : null;
	if (exp === null) return false; // unreadable: let the server decide
	if (exp <= now) return false; // expired tokens cannot be renewed
	const iat = typeof payload.iat === 'number' ? payload.iat * 1000 : null;
	const lifetime = iat !== null && exp > iat
		? exp - iat
		: ASSUMED_TOKEN_TTL_SECONDS * 1000;
	return exp - now < lifetime / 2;
}

/**
 * Rewrite the `token` query parameter in the address bar (no navigation).
 *
 * Keeps the URL the source of truth for a page reload: the wizard token is
 * consumed from the URL on mount and never stored in localStorage.
 *
 * @param {string} token
 * @param {string} [href]
 * @returns {string} the new href (unchanged when there is no browser)
 */
export function syncTokenInUrl(token, href = '') {
	if (typeof window === 'undefined') return href;
	const url = new URL(href || window.location.href);
	url.searchParams.set('token', token);
	window.history.replaceState({}, '', url.toString());
	return url.toString();
}

/**
 * Error raised for a failed workshop request.
 *
 * `code` is machine readable so the UI can localize:
 *   - `token_expired`: the session token expired and could not be renewed →
 *     ask the student to re-enter from the course page
 *   - `http`: any other failure, `message` carries the backend detail
 */
export class WorkshopApiError extends Error {
	/**
	 * @param {string} message
	 * @param {number} status
	 * @param {string} code
	 */
	constructor(message, status, code) {
		super(message);
		this.name = 'WorkshopApiError';
		this.status = status;
		this.code = code;
	}
}

/**
 * Read `detail` from a failed response body without consuming it twice.
 * @param {Response} res
 * @returns {Promise<string>}
 */
async function readDetail(res) {
	try {
		const body = await res.clone().json();
		if (typeof body?.detail === 'string') return body.detail;
	} catch {
		/* non-JSON error body */
	}
	return '';
}

/**
 * Create the workshop API client for one session.
 *
 * @param {Object} params
 * @param {string} params.sessionId
 * @param {string} params.token - current workshop token
 * @param {(token: string) => void} [params.onToken] - called after every renewal
 * @param {typeof fetch} [params.fetchImpl]
 * @param {() => number} [params.now]
 */
export function createWorkshopApi({
	sessionId,
	token,
	onToken,
	fetchImpl,
	now = Date.now
}) {
	const doFetch = fetchImpl || ((...args) => fetch(...args));
	let currentToken = token;
	let renewPromise = /** @type {Promise<string> | null} */ (null);
	let timer = null;
	let visibilityHandler = null;

	/** @param {string} next */
	function setToken(next) {
		currentToken = next;
		if (next && next !== token) syncTokenInUrl(next);
		if (onToken) onToken(next);
	}

	/**
	 * Renew the token. Concurrent callers share one in-flight request.
	 * @returns {Promise<string>}
	 */
	async function renewToken() {
		if (renewPromise) return renewPromise;
		renewPromise = (async () => {
			try {
				const res = await doFetch(
					`/lamb/v1/workshop/sessions/${encodeURIComponent(sessionId)}/refresh`,
					{ method: 'POST', headers: { token: currentToken } }
				);
				if (!res.ok) {
					const detail = await readDetail(res);
					throw new WorkshopApiError(
						detail || `Renewal failed (${res.status})`,
						res.status,
						res.status === 401 ? TOKEN_EXPIRED : 'http'
					);
				}
				const data = await res.json();
				setToken(data.token);
				return data.token;
			} finally {
				renewPromise = null;
			}
		})();
		return renewPromise;
	}

	/**
	 * Perform a request, renewing once on `token_expired` when possible.
	 * Never throws for HTTP failures — the caller inspects the response.
	 * @param {string} path
	 * @param {RequestInit} [init]
	 * @returns {Promise<Response>}
	 */
	async function fetchWithRenew(path, init = {}) {
		const url = `/lamb/v1/workshop${path}`;
		const send = (tok) =>
			doFetch(url, {
				...init,
				headers: { ...(init.headers || {}), token: tok }
			});

		let res = await send(currentToken);
		if (res.status !== 401) return res;

		const detail = await readDetail(res);
		// Only a genuinely expired token may be renewed, and only once.
		if (detail !== TOKEN_EXPIRED || isTokenExpired(currentToken, now())) {
			return res;
		}
		try {
			await renewToken();
		} catch {
			return res;
		}
		return send(currentToken);
	}

	/**
	 * @param {Response} res
	 * @returns {Promise<WorkshopApiError>}
	 */
	async function toError(res) {
		const detail = await readDetail(res);
		if (res.status === 401 && detail === TOKEN_EXPIRED) {
			return new WorkshopApiError(
				'The workshop session expired.', 401, TOKEN_EXPIRED);
		}
		return new WorkshopApiError(
			detail || `Request failed (${res.status})`, res.status, 'http');
	}

	/**
	 * JSON request against `/lamb/v1/workshop`.
	 * @param {string} path
	 * @param {{method?: string, body?: any, signal?: AbortSignal, headers?: Object}} [opts]
	 * @returns {Promise<any>}
	 */
	async function request(path, opts = {}) {
		const { method = 'GET', body, signal, headers = {} } = opts;
		/** @type {RequestInit} */
		const init = { method, signal, headers: { ...headers } };
		if (body !== undefined) {
			init.headers = { ...init.headers, 'Content-Type': 'application/json' };
			init.body = typeof body === 'string' ? body : JSON.stringify(body);
		}
		const res = await fetchWithRenew(path, init);
		if (!res.ok) throw await toError(res);
		return res.json();
	}

	/** Start the background renewal timer (browser only). */
	function startAutoRenew() {
		if (typeof window === 'undefined' || timer) return;
		const tick = () => {
			if (!shouldRenewToken(currentToken, now())) return;
			renewToken().catch(() => {
				/* the next 401 path shows the re-enter hint */
			});
		};
		timer = window.setInterval(tick, RENEW_CHECK_INTERVAL_MS);
		visibilityHandler = () => {
			if (document.visibilityState === 'visible') tick();
		};
		document.addEventListener('visibilitychange', visibilityHandler);
		tick();
	}

	/** Stop the background renewal timer. */
	function stopAutoRenew() {
		if (typeof window === 'undefined') return;
		if (timer) window.clearInterval(timer);
		if (visibilityHandler) {
			document.removeEventListener('visibilitychange', visibilityHandler);
		}
		timer = null;
		visibilityHandler = null;
	}

	return {
		getToken: () => currentToken,
		setToken,
		renewToken,
		request,
		fetchWithRenew,
		startAutoRenew,
		stopAutoRenew
	};
}