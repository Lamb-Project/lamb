import '@testing-library/jest-dom/vitest';
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/svelte';
import { initI18n, locale, waitLocale } from '$lib/i18n.js';
import en from '$lib/locales/en.json';
import es from '$lib/locales/es.json';
import ca from '$lib/locales/ca.json';
import eu from '$lib/locales/eu.json';
import CreatorAccess from './CreatorAccess.svelte';

const TOKEN = 'launch-token';
const CREATOR_URL = 'https://lamb.example/assistants?token=creator-session';
const REFUSAL = 'Open the activity from your LMS again to enter LAMB Creator.';
const tutorial = {
	creator_user_id: 12,
	organization_id: 9,
	organization_name: 'LAMB Tutorial University',
	user_name: 'Robin Vale'
};
const riverside = {
	creator_user_id: 31,
	organization_id: 4,
	organization_name: 'Riverside College',
	user_name: 'Robin Vale'
};

/** @param {unknown} data */
const reply = (data, status = 200) =>
	/** @type {any} */ ({ ok: status < 400, status, json: async () => data });

/** The blank tab the browser hands back to the click. @type {any} */
let tab;

describe('entering LAMB Creator from an activity', () => {
	beforeAll(async () => {
		initI18n();
		await waitLocale();
	});

	beforeEach(async () => {
		await locale.set('en');
		tab = { opener: window, closed: false, close: vi.fn(), location: { replace: vi.fn() } };
		vi.spyOn(window, 'open').mockImplementation(() => tab);
		vi.stubGlobal('fetch', vi.fn());
	});

	it('renders nothing when no account is offered', () => {
		for (const accounts of [[], undefined, null]) {
			const { container, unmount } = render(CreatorAccess, { token: TOKEN, accounts });
			// No element and no text: not even an empty box.
			expect(container.querySelector('*')).toBeNull();
			expect(container.textContent).toBe('');
			unmount();
		}
	});

	it('shows one button for one account and opens LAMB Creator in a new tab', async () => {
		/** @type {(response: any) => void} */
		let answer = () => {};
		vi.mocked(fetch).mockReturnValueOnce(new Promise((resolve) => (answer = resolve)));
		render(CreatorAccess, { token: TOKEN, accounts: [tutorial] });

		const buttons = screen.getAllByRole('button');
		expect(buttons).toHaveLength(1);
		expect(buttons[0]).toHaveAccessibleName('Open LAMB Creator');
		expect(buttons[0]).toHaveAttribute('title', 'Opens in a new tab');

		await fireEvent.click(buttons[0]);
		// The blank tab opens with the click and cannot reach this page.
		expect(window.open).toHaveBeenCalledWith('about:blank', '_blank');
		expect(tab.opener).toBeNull();
		expect(fetch).toHaveBeenCalledWith('/lamb/v1/lti/creator-session', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ token: TOKEN, creator_user_id: 12 })
		});
		expect(buttons[0]).toBeDisabled();
		expect(tab.location.replace).not.toHaveBeenCalled();

		answer(reply({ url: CREATOR_URL }));
		await vi.waitFor(() => expect(tab.location.replace).toHaveBeenCalledWith(CREATOR_URL));
		expect(tab.close).not.toHaveBeenCalled();
		expect(buttons[0]).toBeEnabled();
		expect(screen.queryByRole('alert')).toBeNull();
		// The address carries a session token: it goes to the tab and nowhere on the page.
		expect(document.body.innerHTML).not.toContain('creator-session');
	});

	it('offers one choice per organization for two accounts', async () => {
		vi.mocked(fetch).mockResolvedValueOnce(reply({ url: CREATOR_URL }));
		render(CreatorAccess, { token: TOKEN, accounts: [tutorial, riverside] });

		const buttons = screen.getAllByRole('button');
		expect(buttons).toHaveLength(2);
		expect(buttons[0]).toHaveAccessibleName('Open LAMB Creator in LAMB Tutorial University');
		expect(buttons[0]).toHaveTextContent('LAMB Tutorial University');
		expect(buttons[1]).toHaveAccessibleName('Open LAMB Creator in Riverside College');
		expect(buttons[1]).toHaveTextContent('Riverside College');

		await fireEvent.click(buttons[1]);
		expect(JSON.parse(String(vi.mocked(fetch).mock.calls[0][1]?.body))).toEqual({
			token: TOKEN,
			creator_user_id: 31
		});
		await vi.waitFor(() => expect(tab.location.replace).toHaveBeenCalledWith(CREATOR_URL));
	});

	it('shows the reason the backend gives and closes the tab when the call is refused', async () => {
		vi.mocked(fetch).mockResolvedValueOnce(reply({ detail: REFUSAL }, 403));
		render(CreatorAccess, { token: TOKEN, accounts: [tutorial] });

		await fireEvent.click(screen.getByRole('button', { name: 'Open LAMB Creator' }));
		expect(await screen.findByRole('alert')).toHaveTextContent(REFUSAL);
		expect(tab.close).toHaveBeenCalledTimes(1);
		expect(tab.location.replace).not.toHaveBeenCalled();
		expect(screen.getByRole('button', { name: 'Open LAMB Creator' })).toBeEnabled();
	});

	it('falls back to its own message when the server gives no reason or no usable address', async () => {
		render(CreatorAccess, { token: TOKEN, accounts: [tutorial] });
		const button = screen.getByRole('button', { name: 'Open LAMB Creator' });

		for (const outcome of [
			() => vi.mocked(fetch).mockRejectedValueOnce(new TypeError('Failed to fetch')),
			() => vi.mocked(fetch).mockResolvedValueOnce(reply({ detail: [{ msg: 'required' }] }, 422)),
			() => vi.mocked(fetch).mockResolvedValueOnce(reply({})),
			() => vi.mocked(fetch).mockResolvedValueOnce(reply({ url: 'javascript:alert(1)' }))
		]) {
			outcome();
			await fireEvent.click(button);
			expect(await screen.findByRole('alert')).toHaveTextContent(en.creatorAccess.failed);
			expect(tab.close).toHaveBeenCalledTimes(1);
			expect(tab.location.replace).not.toHaveBeenCalled();
			tab.close.mockClear();
		}
	});

	it('asks nothing of the server when the browser blocks the new tab', async () => {
		vi.mocked(window.open).mockImplementation(() => null);
		render(CreatorAccess, { token: TOKEN, accounts: [tutorial] });

		await fireEvent.click(screen.getByRole('button', { name: 'Open LAMB Creator' }));
		expect(await screen.findByRole('alert')).toHaveTextContent(en.creatorAccess.blocked);
		expect(fetch).not.toHaveBeenCalled();
	});

	it('has its texts in the four languages of the app', async () => {
		const keys = Object.keys(en.creatorAccess).sort();
		const emDash = String.fromCharCode(0x2014);
		expect(JSON.stringify({ en, es, ca, eu })).not.toContain(emDash);
		for (const { code, messages, open } of [
			{ code: 'es', messages: es, open: 'Abrir LAMB Creator' },
			{ code: 'ca', messages: ca, open: 'Obre LAMB Creator' },
			{ code: 'eu', messages: eu, open: 'Ireki LAMB Creator' }
		]) {
			expect(Object.keys(messages.creatorAccess).sort()).toEqual(keys);
			expect(messages.creatorAccess.openIn).toContain('{organization}');
			await locale.set(code);
			const { unmount } = render(CreatorAccess, { token: TOKEN, accounts: [tutorial] });
			expect(screen.getByRole('button', { name: open })).toBeInTheDocument();
			unmount();
		}
	});
});
