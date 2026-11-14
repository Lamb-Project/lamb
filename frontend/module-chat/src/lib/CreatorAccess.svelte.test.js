import '@testing-library/jest-dom/vitest';
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/svelte';
import { initI18n, locale, waitLocale } from '$lib/i18n.js';
import en from '$lib/locales/en.json';
import es from '$lib/locales/es.json';
import ca from '$lib/locales/ca.json';
import eu from '$lib/locales/eu.json';
import CreatorAccess, { creatorAccountFor } from './CreatorAccess.svelte';

const TOKEN = 'launch-token';
const CREATOR_URL = 'https://lamb.example/assistants?token=creator-session&activity=return-ticket';
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

/** Where the control sends this window: stands in for `window.location.assign`. */
const navigate = vi.fn();

/** The page comes back out of the browser's cache, as after the Back button. */
function comeBack() {
	const shown = new Event('pageshow');
	Object.defineProperty(shown, 'persisted', { value: true });
	window.dispatchEvent(shown);
}

describe('entering LAMB Creator from an activity', () => {
	beforeAll(async () => {
		initI18n();
		await waitLocale();
	});

	beforeEach(async () => {
		await locale.set('en');
		// No tab is ever opened: every test would see it here.
		vi.spyOn(window, 'open').mockImplementation(() => null);
		vi.stubGlobal('fetch', vi.fn());
	});

	it('renders nothing when no account is offered', () => {
		for (const accounts of [[], undefined, null]) {
			const { container, unmount } = render(CreatorAccess, { token: TOKEN, accounts, navigate });
			// No element and no text: not even an empty box.
			expect(container.querySelector('*')).toBeNull();
			expect(container.textContent).toBe('');
			unmount();
		}
	});

	it('shows one button for one account and opens LAMB Creator in this same window', async () => {
		/** @type {(response: any) => void} */
		let answer = () => {};
		vi.mocked(fetch).mockReturnValueOnce(new Promise((resolve) => (answer = resolve)));
		render(CreatorAccess, { token: TOKEN, accounts: [tutorial], navigate });

		const buttons = screen.getAllByRole('button');
		expect(buttons).toHaveLength(1);
		expect(buttons[0]).toHaveAccessibleName('Open LAMB Creator');
		// Nothing announces a new tab any more.
		expect(buttons[0]).not.toHaveAttribute('title');

		await fireEvent.click(buttons[0]);
		expect(fetch).toHaveBeenCalledWith('/lamb/v1/lti/creator-session', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ token: TOKEN, creator_user_id: 12 })
		});
		expect(buttons[0]).toBeDisabled();
		expect(navigate).not.toHaveBeenCalled();

		// A second click while the request is in flight asks nothing more.
		await fireEvent.click(buttons[0]);
		expect(fetch).toHaveBeenCalledTimes(1);

		answer(reply({ url: CREATOR_URL }));
		await vi.waitFor(() => expect(navigate).toHaveBeenCalledWith(CREATOR_URL));
		expect(navigate).toHaveBeenCalledTimes(1);
		expect(window.open).not.toHaveBeenCalled();
		expect(screen.queryByRole('alert')).toBeNull();
		// The address carries a session token: it goes to the browser and nowhere on the page.
		expect(document.body.innerHTML).not.toContain('creator-session');
		expect(document.body.innerHTML).not.toContain('return-ticket');

		// The page is being left: the control stays disabled, until the page is shown again.
		expect(buttons[0]).toBeDisabled();
		comeBack();
		await vi.waitFor(() => expect(buttons[0]).toBeEnabled());
	});

	it('goes there with the address bar of this window when no other way is given', async () => {
		// jsdom follows an address that differs only in its fragment, which is enough to see
		// that the default is `window.location.assign` on this window.
		const landing = new URL('#creator-landing', window.location.href).href;
		vi.mocked(fetch).mockResolvedValueOnce(reply({ url: landing }));
		render(CreatorAccess, { token: TOKEN, accounts: [tutorial] });

		await fireEvent.click(screen.getByRole('button', { name: 'Open LAMB Creator' }));
		await vi.waitFor(() => expect(window.location.hash).toBe('#creator-landing'));
		expect(window.open).not.toHaveBeenCalled();
		window.location.hash = '';
	});

	it('offers one choice per organization for two accounts', async () => {
		vi.mocked(fetch).mockResolvedValueOnce(reply({ url: CREATOR_URL }));
		render(CreatorAccess, { token: TOKEN, accounts: [tutorial, riverside], navigate });

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
		await vi.waitFor(() => expect(navigate).toHaveBeenCalledWith(CREATOR_URL));
		expect(window.open).not.toHaveBeenCalled();
	});

	it('restricted to one organization, shows a single button for that organization', async () => {
		vi.mocked(fetch).mockResolvedValueOnce(reply({ url: CREATOR_URL }));
		// The setup page knows organizations by the keys of an object: strings.
		for (const organizationId of [4, '4']) {
			const { unmount } = render(CreatorAccess, {
				token: TOKEN,
				accounts: [tutorial, riverside],
				organizationId,
				navigate
			});
			const buttons = screen.getAllByRole('button');
			expect(buttons).toHaveLength(1);
			expect(buttons[0]).toHaveAccessibleName('Open LAMB Creator');
			expect(buttons[0]).not.toHaveTextContent('Riverside College');
			if (organizationId === '4') {
				await fireEvent.click(buttons[0]);
				expect(JSON.parse(String(vi.mocked(fetch).mock.calls[0][1]?.body))).toEqual({
					token: TOKEN,
					creator_user_id: 31
				});
				await vi.waitFor(() => expect(navigate).toHaveBeenCalledWith(CREATOR_URL));
			}
			unmount();
		}
	});

	it('restricted to an organization with no account in the list, renders nothing', () => {
		// 7: an organization where the instructor has a regular account. '': none chosen yet.
		for (const organizationId of [7, '7', '']) {
			const { container, unmount } = render(CreatorAccess, {
				token: TOKEN,
				accounts: [tutorial, riverside],
				organizationId,
				navigate
			});
			expect(container.querySelector('*')).toBeNull();
			unmount();
		}
		expect(creatorAccountFor([tutorial, riverside], '4')).toBe(riverside);
		expect(creatorAccountFor([tutorial, riverside], 7)).toBeUndefined();
		expect(creatorAccountFor([tutorial, riverside], null)).toBeUndefined();
		expect(creatorAccountFor(null, 9)).toBeUndefined();
	});

	it('is the main button of the page only when asked to be', () => {
		const quiet = render(CreatorAccess, { token: TOKEN, accounts: [tutorial], navigate });
		expect(screen.getByRole('button')).not.toHaveClass('bg-blue-600');
		quiet.unmount();
		render(CreatorAccess, { token: TOKEN, accounts: [tutorial], prominent: true, navigate });
		expect(screen.getByRole('button')).toHaveClass('bg-blue-600', 'text-white');
	});

	it('shows the reason the backend gives and stays on the page when the call is refused', async () => {
		vi.mocked(fetch).mockResolvedValueOnce(reply({ detail: REFUSAL }, 403));
		render(CreatorAccess, { token: TOKEN, accounts: [tutorial], navigate });

		await fireEvent.click(screen.getByRole('button', { name: 'Open LAMB Creator' }));
		expect(await screen.findByRole('alert')).toHaveTextContent(REFUSAL);
		expect(navigate).not.toHaveBeenCalled();
		expect(screen.getByRole('button', { name: 'Open LAMB Creator' })).toBeEnabled();
	});

	it('falls back to its own message when the server gives no reason or no usable address', async () => {
		render(CreatorAccess, { token: TOKEN, accounts: [tutorial], navigate });
		const button = screen.getByRole('button', { name: 'Open LAMB Creator' });

		for (const outcome of [
			() => vi.mocked(fetch).mockRejectedValueOnce(new TypeError('Failed to fetch')),
			() => vi.mocked(fetch).mockResolvedValueOnce(reply({ detail: [{ msg: 'required' }] }, 422)),
			() => vi.mocked(fetch).mockResolvedValueOnce(reply({})),
			() => vi.mocked(fetch).mockResolvedValueOnce(reply({ url: 'javascript:alert(1)' })),
			() => vi.mocked(fetch).mockResolvedValueOnce(reply({ url: 'data:text/html,<p>x</p>' }))
		]) {
			outcome();
			await fireEvent.click(button);
			expect(await screen.findByRole('alert')).toHaveTextContent(en.creatorAccess.failed);
			expect(navigate).not.toHaveBeenCalled();
			expect(button).toBeEnabled();
		}
		// A new attempt clears the message of the one before while it is in flight.
		vi.mocked(fetch).mockReturnValueOnce(new Promise(() => {}));
		await fireEvent.click(button);
		expect(screen.queryByRole('alert')).toBeNull();
	});

	it('has its texts in the four languages of the app', async () => {
		const keys = Object.keys(en.creatorAccess).sort();
		// Nothing is left of the new tab and of the pop-up a browser could block.
		expect(keys).toEqual(['failed', 'open', 'openIn']);
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
			const { unmount } = render(CreatorAccess, { token: TOKEN, accounts: [tutorial], navigate });
			expect(screen.getByRole('button', { name: open })).toBeInTheDocument();
			unmount();
		}
	});
});
