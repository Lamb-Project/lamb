import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent, cleanup, within, waitFor } from '@testing-library/svelte';
import { addMessages, init, locale } from 'svelte-i18n';
import en from '$lib/locales/en.json';
import es from '$lib/locales/es.json';
import ca from '$lib/locales/ca.json';
import eu from '$lib/locales/eu.json';
vi.mock('$app/environment', () => ({ browser: true, dev: true, building: false, version: 'test' }));
vi.mock('$app/stores', async () => {
	const { writable } = await import('svelte/store');
	return { page: writable({ url: new URL('http://localhost/assistants') }) };
});
vi.mock('$lib/services/moodleService', () => ({ moodleStatus: vi.fn() }));
vi.mock('$lib/services/apiKeysService', () => ({ apiKeysEnabled: vi.fn() }));
vi.mock('$lib/services/apiClient', () => ({ apiFetch: vi.fn(), apiJson: vi.fn(), apiAxios: {} }));
vi.mock('$lib/session/sessionManager', () => ({ clearCurrentSession: vi.fn(), ensureProfileLoaded: vi.fn() }));
vi.mock('$lib/stores/userStore', async () => {
	const { writable } = await import('svelte/store');
	const store = writable({ isLoggedIn: false, token: null, name: null, email: null, owiUrl: null, data: null });
	return { user: { subscribe: store.subscribe, set: store.set, fetchAndPopulateProfile: vi.fn() } };
});
import { moodleStatus } from '$lib/services/moodleService';
import { apiKeysEnabled } from '$lib/services/apiKeysService';
import { apiFetch } from '$lib/services/apiClient';
import { user } from '$lib/stores/userStore';
import { STORAGE_KEY } from '$lib/session/activityReturn';
import Nav from './Nav.svelte';

for (const [code, messages] of Object.entries({ en, es, ca, eu })) addMessages(code, messages);
init({ fallbackLocale: 'en', initialLocale: 'en' });

const HERE = { id: 9, name: 'LAMB Tutorial University' };
const accounts = [
	{ creator_user_id: 12, organization_id: 9, organization_name: 'LAMB Tutorial University', user_name: 'Ada Teacher', current: true },
	{ creator_user_id: 13, organization_id: 4, organization_name: 'Faculty of Science', user_name: 'Ada Teacher', current: false }
];
const reply = (/** @type {any} */ data, status = 200) => ({ ok: status < 400, status, json: async () => data });
const SWITCH = ['/lti/switch-organization', {
	method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ creator_user_id: 13 })
}];

/** @param {Record<string, any>} [data] - what the profile adds to the session; null for a profile without the new fields */
function signIn(data = { organization: HERE, lti_organizations: [] }) {
	user.set({
		isLoggedIn: true, token: 'session-token', name: 'Ada Teacher', email: 'ada@example.test', owiUrl: null,
		data: { name: 'Ada Teacher', email: 'ada@example.test', role: 'user', ...data }
	});
}
const switcher = () => screen.findByRole('button', { name: /Change organization/ });
/** A return token for this tab, as the activity leaves it. */
function activityToken() {
	const part = (/** @type {any} */ value) => btoa(JSON.stringify(value)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
	return `${part({ alg: 'HS256' })}.${part({ lti_context_title: 'Databases 101', exp: Math.floor(Date.now() / 1000) + 3600 })}.signature`;
}

describe('the organization in the top bar', () => {
	const assign = vi.fn();

	beforeEach(() => {
		cleanup();
		vi.resetAllMocks();
		sessionStorage.clear();
		locale.set('en');
		moodleStatus.mockResolvedValue({ settings: { enabled: false } });
		apiKeysEnabled.mockResolvedValue(false);
		user.fetchAndPopulateProfile.mockResolvedValue({ success: true });
		user.set({ isLoggedIn: false, token: null, name: null, email: null, owiUrl: null, data: null });
		vi.stubGlobal('location', { href: 'http://localhost/assistants', origin: 'http://localhost', assign });
	});
	afterEach(() => {
		vi.unstubAllGlobals();
		vi.restoreAllMocks();
	});

	it('shows the organization of the session next to the user name, without a menu', async () => {
		signIn();
		render(Nav);

		const name = await screen.findByText('LAMB Tutorial University');
		expect(name).toHaveAttribute('title', 'Organization: LAMB Tutorial University');
		expect(name).toHaveClass('truncate');
		expect(screen.getByText('Ada Teacher')).toBeInTheDocument();
		expect(screen.queryByRole('button', { name: /Change organization/ })).toBeNull();
		expect(user.fetchAndPopulateProfile).not.toHaveBeenCalled();
		expect(apiFetch).not.toHaveBeenCalled();
	});

	it('shows no organization to somebody who is not signed in', async () => {
		render(Nav);
		await screen.findByText('Learning Assistants');
		expect(screen.queryByText('LAMB Tutorial University')).toBeNull();
		expect(document.querySelector('[data-organization-name], [data-organization-switcher]')).toBeNull();
		expect(user.fetchAndPopulateProfile).not.toHaveBeenCalled();
	});

	it('offers no menu with a single organization to switch to', async () => {
		signIn({ organization: HERE, lti_organizations: [accounts[0]] });
		render(Nav);

		expect(await screen.findByText('LAMB Tutorial University')).toHaveAttribute('data-organization-name');
		expect(screen.queryByRole('button', { name: /Change organization/ })).toBeNull();
	});

	it('lists the organizations with two or more, the current one marked', async () => {
		signIn({ organization: HERE, lti_organizations: accounts });
		render(Nav);

		const button = await switcher();
		expect(button).toHaveTextContent('LAMB Tutorial University');
		expect(button).toHaveAttribute('title', 'Organization: LAMB Tutorial University');
		expect(button).toHaveAttribute('aria-expanded', 'false');
		expect(screen.queryByRole('button', { name: /Faculty of Science/ })).toBeNull();

		await fireEvent.click(button);
		expect(button).toHaveAttribute('aria-expanded', 'true');
		const menu = /** @type {HTMLElement} */ (document.querySelector('[data-organization-menu]'));
		const [current, other] = within(menu).getAllByRole('button');
		expect(within(menu).getAllByRole('button')).toHaveLength(2);
		expect(current).toHaveTextContent('LAMB Tutorial University');
		expect(current).toHaveTextContent('current');
		expect(current).toHaveAttribute('aria-current', 'true');
		expect(current).toBeDisabled();
		expect(other).toHaveTextContent('Faculty of Science');
		expect(other).not.toHaveAttribute('aria-current');
		expect(other).toBeEnabled();

		// Escape and a click elsewhere close it.
		await fireEvent.keyDown(document, { key: 'Escape' });
		expect(document.querySelector('[data-organization-menu]')).toBeNull();
		await fireEvent.click(button);
		expect(document.querySelector('[data-organization-menu]')).not.toBeNull();
		await fireEvent.click(document.body);
		expect(document.querySelector('[data-organization-menu]')).toBeNull();
		expect(apiFetch).not.toHaveBeenCalled();
	});

	it('moves to the chosen organization in the same window, without logging the address', async () => {
		const logs = ['log', 'info', 'warn', 'error', 'debug'].map((level) => vi.spyOn(console, /** @type {any} */ (level)).mockImplementation(() => {}));
		signIn({ organization: HERE, lti_organizations: accounts });
		render(Nav);
		await fireEvent.click(await switcher());

		apiFetch.mockResolvedValueOnce(reply({ url: '/assistants?token=new-session-token' }));
		await fireEvent.click(screen.getByRole('button', { name: /Faculty of Science/ }));

		await waitFor(() => expect(assign).toHaveBeenCalledTimes(1));
		expect(apiFetch).toHaveBeenCalledTimes(1);
		expect(apiFetch).toHaveBeenCalledWith(...SWITCH);
		// A tab that did not come from an activity follows the address exactly as the API gave it.
		expect(assign).toHaveBeenCalledWith('/assistants?token=new-session-token');
		expect(screen.queryByRole('alert')).toBeNull();
		expect(document.body.textContent).not.toContain('new-session-token');
		for (const spy of logs) expect(JSON.stringify(spy.mock.calls)).not.toContain('new-session-token');
		// No second switch while the window is leaving.
		expect(screen.getByRole('button', { name: /Faculty of Science/ })).toBeDisabled();
		expect(screen.getByRole('status')).toHaveTextContent('Changing organization...');
	});

	it('keeps the way back to the activity across the switch', async () => {
		const token = activityToken();
		sessionStorage.setItem(STORAGE_KEY, token);
		signIn({ organization: HERE, lti_organizations: accounts });
		render(Nav);
		await fireEvent.click(await switcher());

		apiFetch.mockResolvedValueOnce(reply({ url: '/assistants?token=new-session-token' }));
		await fireEvent.click(screen.getByRole('button', { name: /Faculty of Science/ }));

		await waitFor(() => expect(assign).toHaveBeenCalledTimes(1));
		const target = new URL(assign.mock.calls[0][0]);
		expect(target.origin + target.pathname).toBe('http://localhost/assistants');
		expect(target.searchParams.get('token')).toBe('new-session-token');
		expect(target.searchParams.get('activity')).toBe(token);
	});

	it('shows what the API says when the switch is refused, and stays where it is', async () => {
		signIn({ organization: HERE, lti_organizations: accounts });
		render(Nav);
		await fireEvent.click(await switcher());

		apiFetch.mockResolvedValueOnce(reply({ detail: 'Open LAMB from your LMS again to change organization.' }, 403));
		await fireEvent.click(screen.getByRole('button', { name: /Faculty of Science/ }));

		expect(await screen.findByRole('alert')).toHaveTextContent('Open LAMB from your LMS again to change organization.');
		expect(apiFetch).toHaveBeenCalledWith(...SWITCH);
		expect(assign).not.toHaveBeenCalled();
		expect(screen.queryByRole('status')).toBeNull();
		// The teacher may try again.
		expect(screen.getByRole('button', { name: /Faculty of Science/ })).toBeEnabled();
	});

	it('gives a general message when the API says nothing, in the language of the interface', async () => {
		signIn({ organization: HERE, lti_organizations: accounts });
		render(Nav);
		await fireEvent.click(await switcher());

		apiFetch.mockRejectedValueOnce(new TypeError('Failed to fetch'));
		await fireEvent.click(screen.getByRole('button', { name: /Faculty of Science/ }));
		expect(await screen.findByRole('alert')).toHaveTextContent('The organization could not be changed. Open LAMB from your LMS again.');

		// An answer without an address is a refusal too.
		apiFetch.mockResolvedValueOnce(reply({}));
		await fireEvent.click(screen.getByRole('button', { name: /Faculty of Science/ }));
		await waitFor(() => expect(apiFetch).toHaveBeenCalledTimes(2));
		expect(await screen.findByRole('alert')).toHaveTextContent('The organization could not be changed.');
		expect(assign).not.toHaveBeenCalled();
		cleanup();

		for (const [language, change, failed] of [
			['es', 'Cambiar de organización', 'No se ha podido cambiar de organización. Vuelve a abrir LAMB desde tu LMS.'],
			['ca', 'Canvia d’organització', 'No s’ha pogut canviar d’organització. Torna a obrir LAMB des del teu LMS.'],
			['eu', 'Aldatu erakundea', 'Ezin izan da erakundea aldatu. Ireki LAMB berriro zure LMStik.']
		]) {
			locale.set(language);
			render(Nav);
			await fireEvent.click(await screen.findByRole('button', { name: new RegExp(change) }));
			apiFetch.mockRejectedValueOnce(new TypeError('Failed to fetch'));
			await fireEvent.click(screen.getByRole('button', { name: /Faculty of Science/ }));
			expect(await screen.findByRole('alert')).toHaveTextContent(failed);
			cleanup();
		}
	});

	it('reads the profile once more when the stored one has no organization', async () => {
		// A password sign-in, or a session stored before the profile carried the organization.
		signIn({});
		render(Nav);
		await waitFor(() => expect(user.fetchAndPopulateProfile).toHaveBeenCalledTimes(1));
		expect(document.querySelector('[data-organization-name], [data-organization-switcher]')).toBeNull();

		// The profile arrives: the name appears and nothing is asked again.
		signIn();
		expect(await screen.findByText('LAMB Tutorial University')).toBeInTheDocument();
		signIn({});
		await waitFor(() => expect(screen.queryByText('LAMB Tutorial University')).toBeNull());
		expect(user.fetchAndPopulateProfile).toHaveBeenCalledTimes(1);
	});
});
