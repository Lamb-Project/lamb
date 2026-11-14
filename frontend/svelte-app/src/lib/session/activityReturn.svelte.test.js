import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
vi.mock('$app/environment', () => ({ browser: true, dev: true, building: false, version: 'test' }));
import {
	ACTIVITY_PARAM,
	STORAGE_KEY,
	activityReturnUrl,
	captureActivity,
	carryActivity,
	clearActivity,
	decodeActivity,
	readActivity,
	storeActivity,
	stripSessionParams
} from './activityReturn.js';
import { user } from '$lib/stores/userStore';

const NOW = 1_800_000_000_000; // milliseconds
const LATER = NOW / 1000 + 3600; // unix seconds, one hour ahead
const EARLIER = NOW / 1000 - 60;

/** @param {any} value */
const part = (value) =>
	btoa(String.fromCharCode(...new TextEncoder().encode(JSON.stringify(value))))
		.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
/** A token shaped like the backend's: header.payload.signature, base64url. */
const tokenWith = (/** @type {any} */ payload) => `${part({ alg: 'HS256', typ: 'JWT' })}.${part(payload)}.c2lnbmF0dXJl`;
const valid = (title = 'Databases 101') => tokenWith({ lti_type: 'return', lti_context_title: title, exp: LATER });

describe('the activity a teacher came from', () => {
	beforeEach(() => {
		vi.useFakeTimers();
		vi.setSystemTime(NOW);
		sessionStorage.clear();
		localStorage.clear();
		delete window.LAMB_CONFIG;
	});
	afterEach(() => {
		vi.restoreAllMocks();
		vi.useRealTimers();
	});

	it('reads the course name and the expiry from the token payload', () => {
		expect(decodeActivity(valid())).toEqual({ title: 'Databases 101', exp: LATER });
		expect(decodeActivity(valid('Àlgebra i càlcul · 1r'))).toEqual({ title: 'Àlgebra i càlcul · 1r', exp: LATER });
		expect(decodeActivity(tokenWith({ exp: LATER }))).toEqual({ title: '', exp: LATER });
		expect(decodeActivity(tokenWith({ lti_context_title: 7, exp: LATER }))).toEqual({ title: '', exp: LATER });
	});

	it('treats a broken token as no activity', () => {
		for (const broken of [null, undefined, '', 'not-a-token', 'a.b', 'a.%%%.c', `x.${btoa('not json')}.y`,
			tokenWith({ lti_context_title: 'No expiry' }), tokenWith({ exp: 'soon' }), tokenWith('text'), `${valid()}.extra`]) {
			expect(decodeActivity(broken)).toBeNull();
			expect(storeActivity(broken)).toBe(false);
		}
		expect(sessionStorage.length).toBe(0);

		sessionStorage.setItem(STORAGE_KEY, 'not-a-token');
		expect(readActivity()).toBeNull();
		expect(sessionStorage.getItem(STORAGE_KEY)).toBeNull();
	});

	it('keeps the token an address carries, for this tab only', () => {
		const token = valid();
		const address = new URL(`http://localhost/assistants?token=session-token&${ACTIVITY_PARAM}=${encodeURIComponent(token)}`);

		expect(captureActivity(address)).toBe(true);
		expect(sessionStorage.getItem(STORAGE_KEY)).toBe(token);
		expect(localStorage.length).toBe(0);
		expect(readActivity()).toEqual({ token, title: 'Databases 101', exp: LATER });

		// The same from the text of an address, on any page.
		sessionStorage.clear();
		expect(captureActivity(`/knowledgebases?view=detail&activity=${token}&token=session-token`)).toBe(true);
		expect(readActivity()?.token).toBe(token);
	});

	it('keeps nothing from an address without a usable token', () => {
		expect(captureActivity(new URL('http://localhost/assistants?token=session-token'))).toBe(false);
		expect(captureActivity(new URL('http://localhost/assistants?token=session-token&activity='))).toBe(false);
		expect(captureActivity(new URL('http://localhost/assistants?token=session-token&activity=broken'))).toBe(false);
		const expired = tokenWith({ lti_context_title: 'Databases 101', exp: EARLIER });
		expect(captureActivity(new URL(`http://localhost/assistants?token=session-token&activity=${expired}`))).toBe(false);
		expect(sessionStorage.length).toBe(0);
	});

	it('takes the session token and the return token out of the address, and nothing else', () => {
		expect(stripSessionParams(`http://localhost/assistants?token=session-token&activity=${valid()}`))
			.toBe('http://localhost/assistants');
		expect(stripSessionParams(`http://localhost/evaluaitor?view=list&token=session-token&activity=${valid()}&page=2#top`))
			.toBe('http://localhost/evaluaitor?view=list&page=2#top');
		// The clean-up that existed before: an address with a session token alone.
		expect(stripSessionParams('http://localhost/assistants?token=session-token&tab=shared'))
			.toBe('http://localhost/assistants?tab=shared');
		expect(stripSessionParams('http://localhost/assistants?tab=shared')).toBe('http://localhost/assistants?tab=shared');
	});

	it('drops the token once it has expired', () => {
		const token = valid();
		expect(storeActivity(token)).toBe(true);
		expect(readActivity()?.title).toBe('Databases 101');

		vi.setSystemTime(LATER * 1000 - 1);
		expect(readActivity()?.token).toBe(token);

		vi.setSystemTime(LATER * 1000);
		expect(readActivity()).toBeNull();
		expect(sessionStorage.getItem(STORAGE_KEY)).toBeNull();
	});

	it('a newer activity replaces the one this tab had', () => {
		storeActivity(valid('Databases 101'));
		captureActivity(new URL(`http://localhost/assistants?token=other-session&activity=${valid('Compilers')}`));
		expect(readActivity()?.title).toBe('Compilers');
	});

	it('means no activity when the storage of the browser throws', () => {
		const token = valid();
		const denied = () => { throw new DOMException('The operation is insecure.', 'SecurityError'); };

		vi.spyOn(Storage.prototype, 'setItem').mockImplementation(denied);
		expect(storeActivity(token)).toBe(false);
		expect(captureActivity(new URL(`http://localhost/assistants?token=session-token&activity=${token}`))).toBe(false);
		vi.restoreAllMocks();

		sessionStorage.setItem(STORAGE_KEY, token);
		vi.spyOn(Storage.prototype, 'getItem').mockImplementation(denied);
		vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(denied);
		expect(readActivity()).toBeNull();
		expect(() => clearActivity()).not.toThrow();
		expect(carryActivity('/assistants?token=new-session')).toBe('/assistants?token=new-session');
	});

	it('builds the way back on the backend, with the token encoded', () => {
		const token = `${valid()}+/=`;
		expect(activityReturnUrl(token)).toBe(`/lamb/v1/lti/return?token=${encodeURIComponent(token)}`);
		expect(activityReturnUrl(token)).toContain('%2B%2F%3D');

		// The same base the app uses for backend calls, with its path prefix.
		window.LAMB_CONFIG = { api: { baseUrl: 'https://lamb.example.test/heavy/creator' } };
		expect(activityReturnUrl('a.b.c')).toBe('https://lamb.example.test/heavy/lamb/v1/lti/return?token=a.b.c');
	});

	it('carries the token along when the same teacher signs in again through an address', () => {
		expect(carryActivity('/assistants?token=new-session')).toBe('/assistants?token=new-session');

		const token = valid();
		storeActivity(token);
		const carried = new URL(carryActivity('/assistants?token=new-session'));
		expect(carried.origin + carried.pathname).toBe(`${window.location.origin}/assistants`);
		expect(carried.searchParams.get('token')).toBe('new-session');
		expect(carried.searchParams.get(ACTIVITY_PARAM)).toBe(token);
	});

	it('is forgotten when the session ends', () => {
		storeActivity(valid());
		localStorage.setItem('userToken', 'session-token');
		vi.spyOn(console, 'log').mockImplementation(() => {});

		user.logout();

		expect(sessionStorage.getItem(STORAGE_KEY)).toBeNull();
		expect(readActivity()).toBeNull();
		expect(localStorage.getItem('userToken')).toBeNull();
	});
});
