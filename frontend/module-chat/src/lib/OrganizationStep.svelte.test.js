import '@testing-library/jest-dom/vitest';
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/svelte';
import { initI18n, locale, waitLocale } from '$lib/i18n.js';
import en from '$lib/locales/en.json';
import es from '$lib/locales/es.json';
import ca from '$lib/locales/ca.json';
import eu from '$lib/locales/eu.json';
import OrganizationStep, { initialOrganization } from './OrganizationStep.svelte';

const TOKEN = 'launch-token';
const CREATOR_URL = 'https://lamb.example/assistants?token=creator-session&activity=return-ticket';
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
const assistant = { id: 1, name: 'Course tutor', owner_name: 'Robin Vale', access_type: 'owned' };

// Answers of /lamb/v1/lti/setup/info, as far as this step reads them. The organizations come as
// the keys of an object, which JSON makes strings.
/** One organization, entered through the LMS, nothing published yet. */
const one = {
	needs_org_selection: false,
	can_add_organization: true,
	org_names: { 9: 'LAMB Tutorial University' },
	orgs_with_assistants: { 9: [] },
	creator_access: [tutorial]
};
/** Two organizations, both entered through the LMS. */
const two = {
	needs_org_selection: true,
	can_add_organization: true,
	org_names: { 4: 'Riverside College', 9: 'LAMB Tutorial University' },
	orgs_with_assistants: { 4: [assistant], 9: [assistant, { ...assistant, id: 2 }] },
	creator_access: [tutorial, riverside]
};
/** Two organizations; in Riverside College the instructor has a regular account, with a password. */
const mixed = { ...two, creator_access: [tutorial] };

/** @param {unknown} data */
const reply = (data, status = 200) =>
	/** @type {any} */ ({ ok: status < 400, status, json: async () => data });

/** Where "Open LAMB Creator" sends this window: stands in for `window.location.assign`. */
const navigate = vi.fn();

/**
 * The step as the setup page shows it: the page computes the first choice from the answer and
 * from `org` in its own address.
 * @param {any} info
 * @param {Record<string, unknown>} [more]
 * @param {string | null} [org]
 */
const show = (info, more = {}, org = null) =>
	render(OrganizationStep, {
		token: TOKEN,
		info,
		selected: initialOrganization(info, org),
		navigate,
		...more
	});

describe('choosing the organization of an activity', () => {
	beforeAll(async () => {
		initI18n();
		await waitLocale();
	});

	beforeEach(async () => {
		await locale.set('en');
		vi.spyOn(window, 'open').mockImplementation(() => null);
		vi.stubGlobal('fetch', vi.fn());
	});

	it('starts with the only organization, or the one named in the address, or none', () => {
		expect(initialOrganization(one, null)).toBe('9');
		expect(initialOrganization(one)).toBe('9');
		expect(initialOrganization(two, null)).toBe('');
		expect(initialOrganization(two, '')).toBe('');
		expect(initialOrganization(two, '4')).toBe('4');
		expect(initialOrganization(two, '9')).toBe('9');
		// An organization that is not the instructor's is not a choice, whatever the address says.
		expect(initialOrganization(two, '77')).toBe('');
		expect(initialOrganization(one, '77')).toBe('9');
		expect(initialOrganization({ orgs_with_assistants: {} }, '9')).toBe('');
		expect(initialOrganization(null, '9')).toBe('');
	});

	it('shows a single organization as already chosen, with nothing to click', () => {
		show(one);

		expect(screen.getByRole('heading', { name: 'Your Organization' })).toBeInTheDocument();
		expect(screen.queryByRole('radio')).toBeNull();
		const chosen = screen.getByText('LAMB Tutorial University').closest('[aria-current="true"]');
		expect(chosen).toHaveTextContent('LAMB Tutorial University');
		expect(chosen).toHaveTextContent('(0 published assistants)');
		// With one organization there is no choice to warn about.
		expect(screen.queryByText(en.setupHub.chooseIntro)).toBeNull();
		expect(screen.queryByText(en.setupHub.cannotChange)).toBeNull();

		// The way into LAMB Creator for it: one sentence and exactly one button.
		expect(screen.getByText(en.setupHub.creator)).toBeInTheDocument();
		expect(screen.getAllByRole('button')).toHaveLength(1);
		expect(screen.getByRole('button')).toHaveAccessibleName('Open LAMB Creator');
		expect(screen.queryByText(en.setupHub.signIn)).toBeNull();
	});

	it('offers a choice between several organizations, and LAMB Creator for the chosen one', async () => {
		vi.mocked(fetch).mockResolvedValueOnce(reply({ url: CREATOR_URL }));
		show(two);

		expect(screen.getByRole('heading', { name: 'Choose Organization' })).toBeInTheDocument();
		expect(screen.getByText(en.setupHub.chooseIntro, { exact: false })).toBeInTheDocument();
		// The organization of an activity cannot be changed once it is saved.
		expect(screen.getByText('This cannot be changed later.')).toBeInTheDocument();

		const radios = /** @type {HTMLInputElement[]} */ (screen.getAllByRole('radio'));
		expect(radios).toHaveLength(2);
		expect(radios.map((radio) => radio.value)).toEqual(['4', '9']);
		expect(radios.every((radio) => !radio.checked && radio.name === 'organization_id')).toBe(true);
		expect(screen.getByRole('radio', { name: /Riverside College/ })).toHaveAccessibleName(
			'Riverside College (1 published assistant)'
		);
		expect(screen.getByRole('radio', { name: /LAMB Tutorial University/ })).toHaveAccessibleName(
			'LAMB Tutorial University (2 published assistants)'
		);
		// Nothing leads to LAMB Creator before an organization is chosen.
		expect(screen.queryByRole('button')).toBeNull();
		expect(screen.queryByText(en.setupHub.creator)).toBeNull();
		expect(screen.queryByText(en.setupHub.signIn)).toBeNull();

		await fireEvent.click(screen.getByRole('radio', { name: /Riverside College/ }));
		expect(screen.getByRole('radio', { name: /Riverside College/ })).toBeChecked();
		expect(screen.getByRole('radio', { name: /LAMB Tutorial University/ })).not.toBeChecked();
		// Still a choice: the heading and the warning stay.
		expect(screen.getByRole('heading', { name: 'Choose Organization' })).toBeInTheDocument();
		expect(screen.getByText(en.setupHub.creator)).toBeInTheDocument();

		// One button, for the chosen organization and no other.
		const buttons = screen.getAllByRole('button');
		expect(buttons).toHaveLength(1);
		expect(buttons[0]).toHaveAccessibleName('Open LAMB Creator');
		await fireEvent.click(buttons[0]);
		expect(fetch).toHaveBeenCalledWith('/lamb/v1/lti/creator-session', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ token: TOKEN, creator_user_id: 31 })
		});
		await vi.waitFor(() => expect(navigate).toHaveBeenCalledWith(CREATOR_URL));
		expect(window.open).not.toHaveBeenCalled();
	});

	it('hands the choice to the page that holds it', async () => {
		let chosen = '';
		render(OrganizationStep, {
			props: {
				token: TOKEN,
				info: two,
				navigate,
				// What `bind:selected` on the setup page amounts to.
				get selected() {
					return chosen;
				},
				set selected(value) {
					chosen = value;
				}
			}
		});

		await fireEvent.click(screen.getByRole('radio', { name: /LAMB Tutorial University/ }));
		expect(chosen).toBe('9');
		await fireEvent.click(screen.getByRole('radio', { name: /Riverside College/ }));
		expect(chosen).toBe('4');
	});

	it('starts with the organization named in the address, just added with a creator code', () => {
		show(two, {}, '4');

		expect(screen.getByRole('radio', { name: /Riverside College/ })).toBeChecked();
		expect(screen.getByRole('radio', { name: /LAMB Tutorial University/ })).not.toBeChecked();
		expect(screen.getAllByRole('button')).toHaveLength(1);
	});

	it('offers to add an organization with a creator code only when the backend allows it', () => {
		const allowed = show(two);
		const link = screen.getByRole('link', { name: 'Add an organization with a creator code' });
		expect(link).toHaveAttribute('href', `/lamb/v1/lti/onboarding?token=${TOKEN}`);
		// Same window.
		expect(link).not.toHaveAttribute('target');
		allowed.unmount();

		for (const info of [
			{ ...two, can_add_organization: false },
			{ ...one, can_add_organization: false },
			{ ...one, can_add_organization: undefined }
		]) {
			const { unmount } = show(info);
			expect(screen.queryByRole('link')).toBeNull();
			expect(screen.queryByText(en.setupHub.addOrganization)).toBeNull();
			unmount();
		}
	});

	it('sends to the login page for an organization that cannot be entered from here', async () => {
		show(mixed, {}, '4');

		expect(screen.queryByRole('button')).toBeNull();
		expect(screen.queryByText(en.setupHub.creator)).toBeNull();
		const link = screen.getByRole('link', { name: 'LAMB Creator' });
		expect(link).toHaveAttribute('href', '/');
		expect(link).not.toHaveAttribute('target');
		expect(link.closest('p')).toHaveTextContent(
			'Sign in to LAMB Creator with your LAMB account to build assistants for this organization.'
		);

		// The other organization of the same instructor is entered from here.
		await fireEvent.click(screen.getByRole('radio', { name: /LAMB Tutorial University/ }));
		expect(screen.queryByRole('link', { name: 'LAMB Creator' })).toBeNull();
		expect(screen.getByRole('button')).toHaveAccessibleName('Open LAMB Creator');
		expect(screen.getByText(en.setupHub.creator)).toBeInTheDocument();
	});

	it('makes LAMB Creator the main button when the form cannot go on without it', () => {
		const second = show({ ...one, orgs_with_assistants: { 9: [assistant] } });
		expect(screen.getByRole('button')).not.toHaveClass('bg-blue-600');
		second.unmount();

		show(one, { creatorFirst: true });
		expect(screen.getByRole('button')).toHaveClass('bg-blue-600');
	});

	it('names an organization the backend sent no name for', () => {
		show({ ...one, org_names: {} });
		expect(screen.getByText('Organization 9')).toBeInTheDocument();
	});

	it('has its texts in the four languages of the app', async () => {
		const keys = Object.keys(en.setupHub).sort();
		const emDash = String.fromCharCode(0x2014);
		for (const { code, messages, title, choose, count } of [
			{
				code: 'es',
				messages: es,
				title: 'Tu organización',
				choose: 'Elige una organización',
				count: '(1 asistente publicado)'
			},
			{
				code: 'ca',
				messages: ca,
				title: 'La teva organització',
				choose: 'Tria una organització',
				count: '(1 assistent publicat)'
			},
			{
				code: 'eu',
				messages: eu,
				title: 'Zure erakundea',
				choose: 'Aukeratu erakundea',
				count: '(Argitaratutako laguntzaileak: 1)'
			}
		]) {
			expect(Object.keys(messages.setupHub).sort()).toEqual(keys);
			const texts = JSON.stringify(messages.setupHub);
			expect(texts).not.toContain(emDash);
			// A typewriter apostrophe would also be read as a quote by the message format.
			expect(texts).not.toContain("'");
			expect(messages.setupHub.assistantCount).toContain('count');
			expect(messages.setupHub.organizationFallback).toContain('{id}');
			// The product name carries the link to the login page.
			expect(messages.setupHub.signIn).toContain('LAMB Creator');

			await locale.set(code);
			const single = show(one);
			expect(screen.getByRole('heading', { name: title })).toBeInTheDocument();
			expect(screen.getByText(messages.setupHub.creator)).toBeInTheDocument();
			expect(
				screen.getByRole('link', { name: messages.setupHub.addOrganization })
			).toBeInTheDocument();
			single.unmount();

			const several = show(mixed, {}, '4');
			expect(screen.getByRole('heading', { name: choose })).toBeInTheDocument();
			expect(screen.getByRole('radio', { name: /Riverside College/ })).toHaveAccessibleName(
				`Riverside College ${count}`
			);
			expect(screen.getByRole('link', { name: 'LAMB Creator' }).closest('p')).toHaveTextContent(
				messages.setupHub.signIn
			);
			several.unmount();
		}
	});
});
