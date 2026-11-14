import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, cleanup } from '@testing-library/svelte';
import { createRawSnippet } from 'svelte';
import { addMessages, init } from 'svelte-i18n';
import en from '$lib/locales/en.json';
vi.mock('$app/environment', () => ({ browser: true, dev: true, building: false, version: 'test' }));
vi.mock('$app/navigation', () => ({ afterNavigate: vi.fn(), goto: vi.fn() }));
vi.mock('$app/stores', async () => {
	const { writable } = await import('svelte/store');
	return { page: writable({ url: new URL('http://localhost/') }) };
});
// The parts of the page this test is not about.
vi.mock('$lib/components/Nav.svelte', () => ({ default: () => {} }));
vi.mock('$lib/components/Footer.svelte', () => ({ default: () => {} }));
vi.mock('$lib/components/aac/AacSidebar.svelte', () => ({ default: () => {} }));
vi.mock('$lib/components/TakeoverBar.svelte', () => ({ default: () => {} }));
vi.mock('$lib/components/TakeoverNotices.svelte', () => ({ default: () => {} }));
vi.mock('$lib/services/authService', () => ({ fetchUserProfile: vi.fn() }));
import { page } from '$app/stores';
import { fetchUserProfile } from '$lib/services/authService';
import { user } from '$lib/stores/userStore';
import { STORAGE_KEY } from '$lib/session/activityReturn';
import Layout from './+layout.svelte';

addMessages('en', en);
init({ fallbackLocale: 'en', initialLocale: 'en' });

const part = (/** @type {any} */ value) => btoa(JSON.stringify(value)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
/** A return token as the activity sends it. */
const returnToken = (title = 'Databases 101') =>
	`${part({ alg: 'HS256' })}.${part({ lti_context_title: title, exp: Math.floor(Date.now() / 1000) + 3600 })}.signature`;
const profile = { success: true, data: { name: 'Ada Teacher', email: 'ada@example.test', organization: { id: 9, name: 'LAMB Tutorial University' }, lti_organizations: [] } };

/** Open LAMB Creator at an address, the way the browser does. @param {string} address */
function arrive(address) {
	window.history.replaceState({}, '', address);
	page.set({ url: new URL(window.location.href) });
	return render(Layout, { children: createRawSnippet(() => ({ render: () => '<p>The page</p>' })) });
}
const here = () => window.location.pathname + window.location.search;
const backButton = () => screen.queryByRole('button', { name: 'Back to the activity' });

describe('arriving at LAMB Creator from an LMS activity', () => {
	beforeEach(() => {
		cleanup();
		vi.resetAllMocks();
		vi.spyOn(console, 'log').mockImplementation(() => {});
		vi.spyOn(console, 'error').mockImplementation(() => {});
		user.logout();
		sessionStorage.clear();
		localStorage.clear();
		fetchUserProfile.mockResolvedValue(profile);
	});
	afterEach(() => {
		vi.restoreAllMocks();
		window.history.replaceState({}, '', '/');
	});

	it('starts the session, keeps the way back for this tab and cleans the address', async () => {
		const token = returnToken();
		arrive(`/assistants?token=session-one&activity=${token}&tab=shared`);

		expect(await screen.findByRole('button', { name: 'Back to the activity' })).toBeInTheDocument();
		expect(screen.getByRole('status')).toHaveTextContent('You came from the activity in Databases 101');
		expect(screen.getByText('The page')).toBeInTheDocument();
		expect(fetchUserProfile).toHaveBeenCalledWith('session-one');
		expect(localStorage.getItem('userToken')).toBe('session-one');
		expect(sessionStorage.getItem(STORAGE_KEY)).toBe(token);
		expect(JSON.stringify(Object.entries(localStorage))).not.toContain(token);
		expect(here()).toBe('/assistants?tab=shared');
	});

	it('works the same on any Creator page', async () => {
		const token = returnToken('Compilers');
		arrive(`/knowledgebases?activity=${token}&token=session-one`);

		expect(await screen.findByRole('status')).toHaveTextContent('You came from the activity in Compilers');
		expect(here()).toBe('/knowledgebases');
	});

	it('still cleans an address that carries a session token alone', async () => {
		arrive('/assistants?token=session-one&tab=shared');

		expect(await screen.findByText('The page')).toBeInTheDocument();
		expect(localStorage.getItem('userToken')).toBe('session-one');
		expect(here()).toBe('/assistants?tab=shared');
		expect(backButton()).toBeNull();
	});

	it('forgets the previous activity when another session starts without one', async () => {
		sessionStorage.setItem(STORAGE_KEY, returnToken());
		arrive('/assistants?token=session-two');

		expect(await screen.findByText('The page')).toBeInTheDocument();
		expect(sessionStorage.getItem(STORAGE_KEY)).toBeNull();
		expect(backButton()).toBeNull();
	});

	it('replaces the previous activity with the one the address carries', async () => {
		sessionStorage.setItem(STORAGE_KEY, returnToken('Databases 101'));
		const token = returnToken('Compilers');
		arrive(`/assistants?token=session-two&activity=${token}`);

		expect(await screen.findByRole('status')).toHaveTextContent('You came from the activity in Compilers');
		expect(sessionStorage.getItem(STORAGE_KEY)).toBe(token);
	});

	it('keeps nothing when the session cannot start, and cleans the address all the same', async () => {
		fetchUserProfile.mockResolvedValue({ success: false, error: 'Token refused' });
		arrive(`/assistants?token=refused&activity=${returnToken()}`);

		expect(await screen.findByText('Unable to start session')).toBeInTheDocument();
		expect(screen.getByText('Token refused')).toBeInTheDocument();
		expect(sessionStorage.getItem(STORAGE_KEY)).toBeNull();
		expect(localStorage.getItem('userToken')).toBeNull();
		expect(backButton()).toBeNull();
		expect(here()).toBe('/assistants');
	});

	it('shows the bar again after a reload, on every page, while the session lasts', async () => {
		user.login({ token: 'session-one', name: 'Ada Teacher', email: 'ada@example.test' });
		const token = returnToken();
		sessionStorage.setItem(STORAGE_KEY, token);
		arrive('/evaluaitor?view=list');

		expect(await screen.findByRole('button', { name: 'Back to the activity' })).toBeInTheDocument();
		expect(fetchUserProfile).not.toHaveBeenCalled();
		expect(sessionStorage.getItem(STORAGE_KEY)).toBe(token);
		expect(here()).toBe('/evaluaitor?view=list');
	});

	it('shows no bar without a session', async () => {
		sessionStorage.setItem(STORAGE_KEY, returnToken());
		arrive('/');

		expect(await screen.findByText('The page')).toBeInTheDocument();
		expect(backButton()).toBeNull();
	});
});
