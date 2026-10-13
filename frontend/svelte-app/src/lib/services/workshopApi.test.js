// src/lib/services/workshopApi.test.js
import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
import {
	createWorkshopApi,
	decodeTokenPayload,
	isTokenExpired,
	shouldRenewToken,
	syncTokenInUrl,
	tokenExpiryMs,
	TOKEN_EXPIRED,
	WorkshopApiError
} from './workshopApi.js';

/**
 * Build an unsigned JWT with the given payload (signature is irrelevant here —
 * the client only reads exp/iat for bookkeeping).
 * @param {any} payload
 */
function makeJwt(payload) {
	const b64 = (obj) =>
		btoa(JSON.stringify(obj)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
	return `${b64({ alg: 'HS256', typ: 'JWT' })}.${b64(payload)}.sig`;
}

const NOW = 1_800_000_000_000; // fixed epoch ms
const seconds = (ms) => Math.floor(ms / 1000);

/** A token with `minutesLeft` of a 30-minute lifetime remaining. */
function tokenWith(minutesLeft, lifetimeMinutes = 30) {
	return makeJwt({
		scope: 'workshop_student',
		session_id: 'ws-1',
		iat: seconds(NOW) - (lifetimeMinutes - minutesLeft) * 60,
		exp: seconds(NOW) + minutesLeft * 60
	});
}

describe('workshopApi — token introspection', () => {
	test('decodeTokenPayload returns the claims', () => {
		const jwt = tokenWith(30);
		expect(decodeTokenPayload(jwt).session_id).toBe('ws-1');
	});

	test('unreadable tokens decode to an empty payload', () => {
		expect(decodeTokenPayload('nonsense')).toEqual({});
		expect(decodeTokenPayload('')).toEqual({});
		expect(tokenExpiryMs('nonsense')).toBeNull();
	});

	test('isTokenExpired is true for expired and unreadable tokens', () => {
		expect(isTokenExpired(tokenWith(-1), NOW)).toBe(true);
		expect(isTokenExpired(tokenWith(5), NOW)).toBe(false);
		expect(isTokenExpired('nonsense', NOW)).toBe(true);
	});

	test('shouldRenewToken renews once half the lifetime is gone', () => {
		expect(shouldRenewToken(tokenWith(29), NOW)).toBe(false);
		expect(shouldRenewToken(tokenWith(20), NOW)).toBe(false);
		expect(shouldRenewToken(tokenWith(14), NOW)).toBe(true);
		expect(shouldRenewToken(tokenWith(1), NOW)).toBe(true);
	});

	test('shouldRenewToken never renews an expired or unknown token', () => {
		expect(shouldRenewToken(tokenWith(-5), NOW)).toBe(false);
		expect(shouldRenewToken('nonsense', NOW)).toBe(false);
	});

	test('tokens without iat assume the 30-minute default lifetime', () => {
		const exp = seconds(NOW) + 10 * 60; // 10 minutes left
		const jwt = makeJwt({ exp });
		expect(shouldRenewToken(jwt, NOW)).toBe(true);
	});
});

describe('syncTokenInUrl', () => {
	afterEach(() => {
		vi.unstubAllGlobals();
	});

	test('replaces the token query parameter without navigating', () => {
		const replaceState = vi.fn();
		vi.stubGlobal('window', {
			location: { href: 'https://lms.example/m/workshop/1?token=old&lang=es' },
			history: { replaceState }
		});

		const href = syncTokenInUrl('new-token');

		expect(href).toContain('token=new-token');
		expect(href).toContain('lang=es'); // other params preserved
		expect(replaceState).toHaveBeenCalledTimes(1);
	});
});

describe('createWorkshopApi — request + renewal', () => {
	let fetchMock;

	beforeEach(() => {
		fetchMock = vi.fn();
	});

	afterEach(() => {
		vi.unstubAllGlobals();
	});

	function jsonResponse(status, body) {
		return {
			ok: status >= 200 && status < 300,
			status,
			json: async () => body,
			clone() {
				return this;
			}
		};
	}

	test('successful GET returns parsed JSON and sends the token header', async () => {
		fetchMock.mockResolvedValue(jsonResponse(200, { session_id: 'ws-1' }));
		const api = createWorkshopApi({
			sessionId: 'ws-1', token: 'tok-1', fetchImpl: fetchMock, now: () => NOW
		});

		const data = await api.request('/sessions/ws-1');

		expect(data.session_id).toBe('ws-1');
		expect(fetchMock.mock.calls[0][0]).toBe('/lamb/v1/workshop/sessions/ws-1');
		expect(fetchMock.mock.calls[0][1].headers.token).toBe('tok-1');
	});

	test('401 token_expired → renews and retries once', async () => {
		const fresh = tokenWith(30);
		fetchMock
			.mockResolvedValueOnce(jsonResponse(401, { detail: TOKEN_EXPIRED }))
			.mockResolvedValueOnce(jsonResponse(200, { token: fresh, expires_in: 1800 }))
			.mockResolvedValueOnce(jsonResponse(200, { ok: true }));

		const onToken = vi.fn();
		const api = createWorkshopApi({
			sessionId: 'ws-1', token: tokenWith(10), fetchImpl: fetchMock,
			onToken, now: () => NOW
		});

		const data = await api.request('/sessions/ws-1');

		expect(data).toEqual({ ok: true });
		expect(fetchMock).toHaveBeenCalledTimes(3);
		expect(fetchMock.mock.calls[1][0]).toBe(
			'/lamb/v1/workshop/sessions/ws-1/refresh');
		// The retry carries the renewed token.
		expect(fetchMock.mock.calls[2][1].headers.token).toBe(fresh);
		expect(onToken).toHaveBeenCalledWith(fresh);
		expect(api.getToken()).toBe(fresh);
	});

	test('401 token_expired on an expired token is NOT renewed', async () => {
		fetchMock.mockResolvedValue(jsonResponse(401, { detail: TOKEN_EXPIRED }));
		const api = createWorkshopApi({
			sessionId: 'ws-1', token: tokenWith(-5), fetchImpl: fetchMock,
			now: () => NOW
		});

		await expect(api.request('/sessions/ws-1')).rejects.toMatchObject({
			code: TOKEN_EXPIRED,
			status: 401
		});
		expect(fetchMock).toHaveBeenCalledTimes(1);
	});

	test('a failed renewal surfaces the original 401', async () => {
		fetchMock
			.mockResolvedValueOnce(jsonResponse(401, { detail: TOKEN_EXPIRED }))
			.mockResolvedValueOnce(jsonResponse(401, { detail: TOKEN_EXPIRED }));

		const api = createWorkshopApi({
			sessionId: 'ws-1', token: tokenWith(10), fetchImpl: fetchMock,
			now: () => NOW
		});

		await expect(api.request('/sessions/ws-1')).rejects.toBeInstanceOf(
			WorkshopApiError);
		expect(fetchMock).toHaveBeenCalledTimes(2);
	});

	test('other 401 details are surfaced verbatim', async () => {
		fetchMock.mockResolvedValue(
			jsonResponse(401, { detail: 'Invalid workshop token' }));
		const api = createWorkshopApi({
			sessionId: 'ws-1', token: tokenWith(10), fetchImpl: fetchMock,
			now: () => NOW
		});

		await expect(api.request('/sessions/ws-1')).rejects.toMatchObject({
			message: 'Invalid workshop token',
			status: 401,
			code: 'http'
		});
		expect(fetchMock).toHaveBeenCalledTimes(1);
	});

	test('non-401 failures carry the backend detail', async () => {
		fetchMock.mockResolvedValue(
			jsonResponse(403, { detail: 'kb_id does not belong to this session' }));
		const api = createWorkshopApi({
			sessionId: 'ws-1', token: tokenWith(30), fetchImpl: fetchMock,
			now: () => NOW
		});

		await expect(api.request('/sessions/ws-1')).rejects.toMatchObject({
			message: 'kb_id does not belong to this session',
			status: 403
		});
	});

	test('POST bodies are JSON encoded', async () => {
		fetchMock.mockResolvedValue(jsonResponse(200, { success: true }));
		const api = createWorkshopApi({
			sessionId: 'ws-1', token: 'tok', fetchImpl: fetchMock, now: () => NOW
		});

		await api.request('/sessions/ws-1/submit', {
			method: 'POST', body: { reflection: 'hi' }
		});

		const init = fetchMock.mock.calls[0][1];
		expect(init.method).toBe('POST');
		expect(init.headers['Content-Type']).toBe('application/json');
		expect(JSON.parse(init.body)).toEqual({ reflection: 'hi' });
	});

	test('concurrent renewals share one in-flight request', async () => {
		const fresh = tokenWith(30);
		let resolveRefresh;
		fetchMock.mockImplementation((url) => {
			if (String(url).endsWith('/refresh')) {
				return new Promise((resolve) => {
					resolveRefresh = () =>
						resolve(jsonResponse(200, { token: fresh, expires_in: 1800 }));
				});
			}
			return Promise.resolve(jsonResponse(200, { ok: true }));
		});

		const api = createWorkshopApi({
			sessionId: 'ws-1', token: tokenWith(10), fetchImpl: fetchMock,
			now: () => NOW
		});

		const first = api.renewToken();
		const second = api.renewToken();
		resolveRefresh();
		expect(await first).toBe(fresh);
		expect(await second).toBe(fresh);

		const refreshCalls = fetchMock.mock.calls.filter((c) =>
			String(c[0]).endsWith('/refresh'));
		expect(refreshCalls).toHaveLength(1);
	});
});

describe('createWorkshopApi — background renewal', () => {
	afterEach(() => {
		vi.unstubAllGlobals();
		vi.useRealTimers();
	});

	test('startAutoRenew schedules a check and stops cleanly', () => {
		const setInterval = vi.fn(() => 42);
		const clearInterval = vi.fn();
		const addEventListener = vi.fn();
		const removeEventListener = vi.fn();
		vi.stubGlobal('window', { setInterval, clearInterval });
		vi.stubGlobal('document', {
			visibilityState: 'visible',
			addEventListener,
			removeEventListener
		});

		const fetchMock = vi.fn().mockResolvedValue({
			ok: true, status: 200, json: async () => ({ token: 'new' }),
			clone() { return this; }
		});
		const api = createWorkshopApi({
			sessionId: 'ws-1', token: tokenWith(30), fetchImpl: fetchMock,
			now: () => NOW
		});

		api.startAutoRenew();

		expect(setInterval).toHaveBeenCalledTimes(1);
		// A fresh token needs no immediate renewal.
		expect(fetchMock).not.toHaveBeenCalled();
		expect(addEventListener).toHaveBeenCalledWith(
			'visibilitychange', expect.any(Function));

		api.stopAutoRenew();
		expect(clearInterval).toHaveBeenCalledWith(42);
		expect(removeEventListener).toHaveBeenCalled();
	});
});