import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/svelte';
import { addMessages, init, locale } from 'svelte-i18n';
import en from '$lib/locales/en.json';
import es from '$lib/locales/es.json';
import ca from '$lib/locales/ca.json';
import eu from '$lib/locales/eu.json';
vi.mock('$app/environment', () => ({ browser: true, dev: true, building: false, version: 'test' }));
import { STORAGE_KEY } from '$lib/session/activityReturn';
import ActivityReturnBar from './ActivityReturnBar.svelte';

for (const [code, messages] of Object.entries({ en, es, ca, eu })) addMessages(code, messages);
init({ fallbackLocale: 'en', initialLocale: 'en' });

/** @param {any} value */
const part = (value) =>
	btoa(String.fromCharCode(...new TextEncoder().encode(JSON.stringify(value))))
		.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
/** A return token as the backend issues it; the signature has characters an address must encode. */
const tokenWith = (/** @type {any} */ payload) => `${part({ alg: 'HS256', typ: 'JWT' })}.${part(payload)}.sig+/=`;
const inSeconds = (/** @type {number} */ seconds) => Math.floor(Date.now() / 1000) + seconds;

describe('the bar that leads back to the activity', () => {
	const assign = vi.fn();

	beforeEach(() => {
		cleanup();
		vi.resetAllMocks();
		sessionStorage.clear();
		delete window.LAMB_CONFIG;
		locale.set('en');
		vi.stubGlobal('location', { href: 'http://localhost/assistants', origin: 'http://localhost', assign });
	});
	afterEach(() => {
		vi.unstubAllGlobals();
		vi.useRealTimers();
	});

	it('names the course and offers the way back', () => {
		sessionStorage.setItem(STORAGE_KEY, tokenWith({ lti_context_title: 'Databases 101', exp: inSeconds(3600) }));
		render(ActivityReturnBar);

		expect(screen.getByRole('status')).toHaveTextContent('You came from the activity in Databases 101');
		expect(screen.getByRole('button', { name: 'Back to the activity' })).toBeEnabled();
	});

	it('still offers the way back when the course has no name', () => {
		sessionStorage.setItem(STORAGE_KEY, tokenWith({ lti_context_title: '', exp: inSeconds(3600) }));
		render(ActivityReturnBar);

		expect(screen.getByRole('status')).toHaveTextContent('You came from an activity in your LMS');
		expect(screen.getByRole('button', { name: 'Back to the activity' })).toBeInTheDocument();
	});

	it('is absent for a tab that did not come from an activity', () => {
		render(ActivityReturnBar);
		expect(screen.queryByRole('status')).toBeNull();
		expect(screen.queryByRole('button')).toBeNull();
	});

	it('is absent when the token has expired or cannot be read, and the stored value goes', () => {
		for (const stored of [tokenWith({ lti_context_title: 'Databases 101', exp: inSeconds(-1) }), 'not-a-token']) {
			sessionStorage.setItem(STORAGE_KEY, stored);
			render(ActivityReturnBar);
			expect(screen.queryByRole('status')).toBeNull();
			expect(screen.queryByRole('button')).toBeNull();
			expect(sessionStorage.getItem(STORAGE_KEY)).toBeNull();
			cleanup();
		}
	});

	it('goes back in the same window, to the backend address with the token encoded', async () => {
		const token = tokenWith({ lti_context_title: 'Databases 101', exp: inSeconds(3600) });
		sessionStorage.setItem(STORAGE_KEY, token);
		render(ActivityReturnBar);

		await fireEvent.click(screen.getByRole('button', { name: 'Back to the activity' }));

		expect(assign).toHaveBeenCalledTimes(1);
		expect(assign).toHaveBeenCalledWith(`/lamb/v1/lti/return?token=${encodeURIComponent(token)}`);
		expect(assign.mock.calls[0][0]).toMatch(/\.sig%2B%2F%3D$/);
		expect(screen.getByRole('button', { name: 'Back to the activity' })).toBeDisabled();
	});

	it('uses the base of the backend when the deployment sets one', async () => {
		window.LAMB_CONFIG = { api: { baseUrl: 'https://lamb.example.test/heavy/creator' } };
		const token = tokenWith({ lti_context_title: 'Databases 101', exp: inSeconds(3600) });
		sessionStorage.setItem(STORAGE_KEY, token);
		render(ActivityReturnBar);

		await fireEvent.click(screen.getByRole('button', { name: 'Back to the activity' }));
		expect(assign).toHaveBeenCalledWith(`https://lamb.example.test/heavy/lamb/v1/lti/return?token=${encodeURIComponent(token)}`);
	});

	it('goes away when the token expires while the page is open, and does not navigate after that', async () => {
		vi.useFakeTimers();
		sessionStorage.setItem(STORAGE_KEY, tokenWith({ lti_context_title: 'Databases 101', exp: inSeconds(60) }));
		render(ActivityReturnBar);
		expect(screen.getByRole('button', { name: 'Back to the activity' })).toBeInTheDocument();

		await vi.advanceTimersByTimeAsync(59_000);
		expect(screen.getByRole('button', { name: 'Back to the activity' })).toBeInTheDocument();

		await vi.advanceTimersByTimeAsync(3_000);
		expect(screen.queryByRole('button')).toBeNull();
		expect(sessionStorage.getItem(STORAGE_KEY)).toBeNull();
		expect(assign).not.toHaveBeenCalled();
	});

	it('does not navigate with a token that expired since the bar was drawn', async () => {
		vi.useFakeTimers();
		sessionStorage.setItem(STORAGE_KEY, tokenWith({ lti_context_title: 'Databases 101', exp: inSeconds(60) }));
		render(ActivityReturnBar);
		const button = screen.getByRole('button', { name: 'Back to the activity' });

		vi.setSystemTime(Date.now() + 60_500); // past the expiry, before the bar's own timer
		await fireEvent.click(button);

		expect(assign).not.toHaveBeenCalled();
		expect(screen.queryByRole('button')).toBeNull();
	});

	it('has every string in the four languages, without em-dashes', async () => {
		const keys = (/** @type {Record<string, any>} */ node) => Object.keys(node).sort();
		for (const messages of [en, es, ca, eu]) {
			expect(keys(messages.ltiSession)).toEqual(keys(en.ltiSession));
			expect(Object.values(messages.ltiSession).every((text) => typeof text === 'string' && text.trim())).toBe(true);
			expect(JSON.stringify(messages.ltiSession)).not.toContain('—');
		}
		// Catalan elisions use the typographic apostrophe, like the other recent keys.
		expect(JSON.stringify(ca.ltiSession)).not.toContain("'");

		const token = tokenWith({ lti_context_title: 'Bases de dades', exp: inSeconds(3600) });
		for (const [language, text, button] of [
			['es', 'Has llegado desde la actividad del curso Bases de dades', 'Volver a la actividad'],
			['ca', 'Has arribat des de l’activitat del curs Bases de dades', 'Torna a l’activitat'],
			['eu', 'Bases de dades ikastaroko jardueratik etorri zara', 'Itzuli jarduerara']
		]) {
			await locale.set(language); // the language file loads first
			sessionStorage.setItem(STORAGE_KEY, token);
			render(ActivityReturnBar);
			expect(screen.getByRole('status')).toHaveTextContent(text);
			expect(screen.getByRole('button', { name: button })).toBeInTheDocument();
			cleanup();
		}
	});
});
