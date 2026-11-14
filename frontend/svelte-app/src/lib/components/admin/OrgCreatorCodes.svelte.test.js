import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent, cleanup, within } from '@testing-library/svelte';
import { addMessages, init, locale } from 'svelte-i18n';
import en from '$lib/locales/en.json';
import es from '$lib/locales/es.json';
import ca from '$lib/locales/ca.json';
import eu from '$lib/locales/eu.json';
vi.mock('$lib/services/apiClient', () => ({ apiFetch: vi.fn() }));
import { apiFetch } from '$lib/services/apiClient';
import OrgCreatorCodes from './OrgCreatorCodes.svelte';

for (const [code, messages] of Object.entries({ en, es, ca, eu })) addMessages(code, messages);
init({ fallbackLocale: 'en', initialLocale: 'en' });

const PATH = '/admin/org-admin/settings/creator-codes';
const DEFAULT_TEXT = 'Your institution lets teachers create their own LAMB Creator account with a creator code.';
const reply = (data, status = 200) => ({ ok: status < 400, status, json: async () => data });
const code = (overrides = {}) => ({
    id: 1, label: 'Autumn term', hint: '7KQ2', enabled: true, expires_at: null, max_uses: null,
    use_count: 3, created_at: 1760000000, status: 'active', ...overrides
});
const listing = (overrides = {}) => ({
    codes: [code()], codes_available: true, page_text: '', effective_page_text: DEFAULT_TEXT,
    default_page_text: DEFAULT_TEXT, page_text_limit: 4000, ...overrides
});
const sent = (method, body) => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

describe('organization creator codes', () => {
    beforeEach(() => {
        cleanup();
        vi.resetAllMocks();
        locale.set('en');
    });

    it('lists each code with its last characters, status, uses and expiry', async () => {
        const expired = Math.floor(new Date(2025, 0, 31, 23, 59, 59).getTime() / 1000);
        apiFetch.mockResolvedValueOnce(reply(listing({ codes: [
            code(),
            code({ id: 2, label: 'Faculty of Science', hint: 'M4XP', max_uses: 30, use_count: 30, status: 'used_up' }),
            code({ id: 3, label: '', hint: 'B2CD', enabled: false, use_count: 0, status: 'disabled' }),
            code({ id: 4, label: 'Last year', hint: 'Z9YW', expires_at: expired, max_uses: 10, use_count: 4, status: 'expired' })
        ] })));
        render(OrgCreatorCodes, { org: 'fixture-org' });

        const rows = within(await screen.findByRole('table')).getAllByRole('row').slice(1);
        expect(apiFetch).toHaveBeenCalledWith(`${PATH}?org=fixture-org`, { method: 'GET' });
        expect(rows).toHaveLength(4);

        expect(within(rows[0]).getByText('Autumn term')).toBeInTheDocument();
        expect(within(rows[0]).getByText('…7KQ2')).toBeInTheDocument();
        expect(within(rows[0]).getByText('Active')).toBeInTheDocument();
        expect(within(rows[0]).getByText('3')).toBeInTheDocument();
        expect(within(rows[0]).getByText('No expiry')).toBeInTheDocument();
        expect(within(rows[0]).getByRole('button', { name: 'Disable' })).toBeInTheDocument();

        expect(within(rows[1]).getByText('Used up')).toBeInTheDocument();
        expect(within(rows[1]).getByText('30 / 30')).toBeInTheDocument();

        expect(within(rows[2]).getByText('No label')).toBeInTheDocument();
        expect(within(rows[2]).getByText('Disabled')).toBeInTheDocument();
        expect(within(rows[2]).getByText('0')).toBeInTheDocument();
        expect(within(rows[2]).getByRole('button', { name: 'Enable' })).toBeInTheDocument();

        expect(within(rows[3]).getByText('Expired')).toBeInTheDocument();
        expect(within(rows[3]).getByText('4 / 10')).toBeInTheDocument();
        expect(within(rows[3]).getByText('Jan 31, 2025')).toBeInTheDocument();
    });

    it('shows a new code once, with a copy button, and forgets it when dismissed', async () => {
        const writeText = vi.fn().mockResolvedValue(undefined);
        Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
        apiFetch.mockResolvedValueOnce(reply(listing({ codes: [] })));
        render(OrgCreatorCodes);

        await fireEvent.input(await screen.findByLabelText('Label (optional)'), { target: { value: ' Spring term ' } });
        await fireEvent.input(screen.getByLabelText('Expiry date (optional)'), { target: { value: '2099-12-31' } });
        await fireEvent.input(screen.getByLabelText('Use limit (optional)'), { target: { value: '25' } });
        expect(screen.getByText('This organization has no creator codes yet.')).toBeInTheDocument();

        const endOfDay = Math.floor(new Date(2099, 11, 31, 23, 59, 59).getTime() / 1000);
        apiFetch.mockResolvedValueOnce(reply({
            ...code({ id: 9, label: 'Spring term', hint: 'JKLM', expires_at: endOfDay, max_uses: 25, use_count: 0 }),
            code: 'ABCD-EFGH-JKLM'
        }));
        await fireEvent.click(screen.getByRole('button', { name: 'Create code' }));

        expect(await screen.findByText('ABCD-EFGH-JKLM')).toBeInTheDocument();
        expect(apiFetch).toHaveBeenLastCalledWith(PATH, sent('POST', { label: 'Spring term', expires_at: endOfDay, max_uses: 25 }));
        expect(screen.getByText(/It will not be shown again/)).toBeInTheDocument();
        // The list knows the code only by its last four characters.
        const row = within(screen.getByRole('table')).getAllByRole('row')[1];
        expect(within(row).getByText('…JKLM')).toBeInTheDocument();
        expect(within(row).getByText('0 / 25')).toBeInTheDocument();
        // While the value is on screen the form is away, so a second code cannot push it out unseen.
        expect(screen.queryByRole('button', { name: 'Create code' })).toBeNull();

        await fireEvent.click(screen.getByRole('button', { name: 'Copy' }));
        expect(writeText).toHaveBeenCalledWith('ABCD-EFGH-JKLM');
        expect(await screen.findByRole('button', { name: 'Copied' })).toBeInTheDocument();

        await fireEvent.click(screen.getByRole('button', { name: 'I have saved it' }));
        expect(screen.queryByText('ABCD-EFGH-JKLM')).toBeNull();
        expect(screen.queryByText(/It will not be shown again/)).toBeNull();
        expect(within(screen.getByRole('table')).getByText('…JKLM')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Create code' })).toBeInTheDocument();
        expect(screen.getByLabelText('Label (optional)')).toHaveValue('');
        expect(apiFetch).toHaveBeenCalledTimes(2);
    });

    it('hides the codes for the system organization and says its text is the deployment default', async () => {
        apiFetch.mockResolvedValueOnce(reply(listing({ codes: [], codes_available: false })));
        render(OrgCreatorCodes, { org: 'lamb' });

        expect(await screen.findByText(/default for the whole deployment/)).toBeInTheDocument();
        expect(screen.queryByRole('table')).toBeNull();
        expect(screen.queryByText('This organization has no creator codes yet.')).toBeNull();
        expect(screen.queryByLabelText('Label (optional)')).toBeNull();
        expect(screen.queryByRole('button', { name: 'Create code' })).toBeNull();
        expect(screen.getByLabelText('Text of this organization')).toHaveValue('');
        expect(screen.getByText(DEFAULT_TEXT)).toBeInTheDocument();
    });

    it('disables and enables a code, and shows what the API refuses', async () => {
        apiFetch.mockResolvedValueOnce(reply(listing()));
        render(OrgCreatorCodes, { org: 'fixture-org' });

        apiFetch.mockResolvedValueOnce(reply(code({ enabled: false, status: 'disabled' })));
        await fireEvent.click(await screen.findByRole('button', { name: 'Disable' }));
        expect(await screen.findByRole('button', { name: 'Enable' })).toBeInTheDocument();
        expect(apiFetch).toHaveBeenLastCalledWith(`${PATH}/1?org=fixture-org`, sent('PUT', { enabled: false }));
        expect(within(screen.getByRole('table')).getByText('Disabled')).toBeInTheDocument();
        expect(screen.getByRole('status')).toHaveTextContent('Code …7KQ2 disabled.');

        apiFetch.mockResolvedValueOnce(reply({ detail: 'Creator code not found in this organization' }, 404));
        await fireEvent.click(screen.getByRole('button', { name: 'Enable' }));
        expect(await screen.findByRole('alert')).toHaveTextContent('Creator code not found in this organization');
        expect(apiFetch).toHaveBeenLastCalledWith(`${PATH}/1?org=fixture-org`, sent('PUT', { enabled: true }));
        expect(within(screen.getByRole('table')).getByText('Disabled')).toBeInTheDocument();
    });

    it('shows the default text, counts characters, saves the text and restores the default', async () => {
        apiFetch.mockResolvedValueOnce(reply(listing({ page_text_limit: 20 })));
        render(OrgCreatorCodes);

        const textarea = await screen.findByLabelText('Text of this organization');
        expect(textarea).toHaveValue('');
        expect(screen.getByText(DEFAULT_TEXT)).toBeInTheDocument();
        expect(screen.getByText('0 / 20 characters')).toBeInTheDocument();
        const save = screen.getByRole('button', { name: 'Save text' });
        expect(save).toBeDisabled();
        expect(screen.queryByRole('button', { name: 'Restore the default text' })).toBeNull();

        await fireEvent.input(textarea, { target: { value: 'x'.repeat(21) } });
        expect(screen.getByText('21 / 20 characters')).toBeInTheDocument();
        expect(save).toBeDisabled();

        await fireEvent.input(textarea, { target: { value: 'Ask the library.' } });
        expect(screen.getByText('16 / 20 characters')).toBeInTheDocument();
        apiFetch.mockResolvedValueOnce(reply({ page_text: 'Ask the library.', effective_page_text: 'Ask the library.' }));
        await fireEvent.click(save);
        expect(await screen.findByText('Text saved.')).toBeInTheDocument();
        expect(apiFetch).toHaveBeenLastCalledWith(`${PATH}/page-text`, sent('PUT', { page_text: 'Ask the library.' }));
        expect(screen.queryByText(DEFAULT_TEXT)).toBeNull();
        expect(textarea).toHaveValue('Ask the library.');

        await fireEvent.click(screen.getByRole('button', { name: 'Restore the default text' }));
        const dialog = screen.getByRole('dialog');
        expect(dialog).toHaveTextContent('Instructors will read the default text again.');
        apiFetch.mockResolvedValueOnce(reply({ page_text: '', effective_page_text: DEFAULT_TEXT }));
        await fireEvent.click(within(dialog).getByRole('button', { name: 'Restore the default text' }));
        expect(await screen.findByText('Default text restored.')).toBeInTheDocument();
        expect(apiFetch).toHaveBeenLastCalledWith(`${PATH}/page-text`, sent('PUT', { page_text: '' }));
        expect(screen.queryByRole('dialog')).toBeNull();
        expect(textarea).toHaveValue('');
        expect(screen.getByText(DEFAULT_TEXT)).toBeInTheDocument();
    });

    it('reports a failed load with a general message when the API gives no detail', async () => {
        apiFetch.mockRejectedValueOnce(new TypeError('Failed to fetch'));
        render(OrgCreatorCodes);
        expect(await screen.findByRole('alert')).toHaveTextContent('The request failed. Try again.');
        expect(screen.queryByRole('table')).toBeNull();
        expect(screen.queryByLabelText('Text of this organization')).toBeNull();
    });

    it('has every string in the four languages, without em-dashes', async () => {
        const keys = (node, prefix = '') => Object.entries(node).flatMap(([key, value]) =>
            typeof value === 'string' ? [prefix + key] : keys(value, `${prefix}${key}.`));
        for (const messages of [es, ca, eu]) {
            expect(keys(messages.creatorCodes)).toEqual(keys(en.creatorCodes));
            expect(JSON.stringify(messages.creatorCodes)).not.toContain('\u2014');
        }
        expect(JSON.stringify(en.creatorCodes)).not.toContain('\u2014');

        for (const [language, title, enable] of [['es', 'Códigos de creador', 'Activar'], ['ca', 'Codis de creador', 'Activa'], ['eu', 'Sortzaile-kodeak', 'Gaitu']]) {
            locale.set(language);
            apiFetch.mockResolvedValueOnce(reply(listing({ codes: [code({ enabled: false, status: 'disabled' })] })));
            render(OrgCreatorCodes);
            expect(await screen.findByRole('button', { name: enable })).toBeInTheDocument();
            expect(screen.getByRole('heading', { name: title })).toBeInTheDocument();
            cleanup();
        }
    });
});
