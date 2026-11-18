import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, cleanup, waitFor } from '@testing-library/svelte';
import '@testing-library/jest-dom/vitest';
import { addMessages, init, locale } from 'svelte-i18n';
import en from '$lib/locales/en.json';
import es from '$lib/locales/es.json';
import ca from '$lib/locales/ca.json';
import eu from '$lib/locales/eu.json';
vi.mock('$lib/services/apiClient', () => ({ apiFetch: vi.fn() }));
import { apiFetch } from '$lib/services/apiClient';
import LtiAccessSettings from './LtiAccessSettings.svelte';

for (const [code, messages] of Object.entries({ en, es, ca, eu })) addMessages(code, messages);
init({ fallbackLocale: 'en', initialLocale: 'en' });

const reply = (data, status = 200) => ({ ok: status < 400, json: async () => data });
const open = { locked_instances: [], my_instance: '', seen_instances: [], can_type: false, whitelist_enabled: false, allowed_instances: [] };
const body = () => JSON.parse(apiFetch.mock.lastCall[1].body);

describe('optional LMS admission settings', () => {
    beforeEach(() => { cleanup(); vi.resetAllMocks(); locale.set('en'); });

    it('locks the organization to the LMS the administrator came from, with nothing to type', async () => {
        apiFetch.mockResolvedValueOnce(reply({ ...open, my_instance: 'atenea.upc.edu' }));
        render(LtiAccessSettings, { org: 'faculty' });
        expect(await screen.findByText(/Not locked/)).toBeInTheDocument();
        expect(apiFetch).toHaveBeenCalledWith('/admin/org-admin/settings/lti-access?org=faculty', { method: 'GET' });
        expect(screen.getByText('You opened LAMB from atenea.upc.edu.')).toBeInTheDocument();
        expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
        apiFetch.mockResolvedValueOnce(reply({ ...open, my_instance: 'atenea.upc.edu', locked_instances: ['atenea.upc.edu'] }));
        await fireEvent.click(screen.getByRole('button', { name: 'Lock to atenea.upc.edu' }));
        await screen.findByText('LMS access settings saved.');
        expect(body()).toEqual({ locked_instances: ['atenea.upc.edu'] });
        expect(screen.getByText(/^Locked/)).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: 'Lock to atenea.upc.edu' })).not.toBeInTheDocument();
        // The server refuses a change that would lock the administrator out, and the list stays.
        apiFetch.mockResolvedValueOnce(reply({ detail: 'Keep the LMS you are connected from in the list, or you would lock yourself out.' }, 400));
        await fireEvent.click(screen.getByRole('button', { name: 'Remove atenea.upc.edu' }));
        expect(await screen.findByRole('alert')).toHaveTextContent('lock yourself out');
        expect(screen.getByText('atenea.upc.edu')).toBeInTheDocument();
        expect(screen.queryByText('LMS access settings saved.')).not.toBeInTheDocument();
    });

    it('offers installations already seen, and tells an administrator with no LMS session how to get one', async () => {
        apiFetch.mockResolvedValueOnce(reply(open));
        render(LtiAccessSettings, {});
        expect(await screen.findByText(/open LAMB Creator from your LMS/)).toBeInTheDocument();
        expect(screen.queryByRole('button')).not.toBeInTheDocument();
        cleanup();
        apiFetch.mockResolvedValueOnce(reply({ ...open, seen_instances: ['moodle.school.example'], whitelist_enabled: true, allowed_instances: ['moodle.school.example'] }));
        render(LtiAccessSettings, {});
        expect(await screen.findByText(/already used with this organization/)).toBeInTheDocument();
        expect(screen.getByText('The system administrator only allows: moodle.school.example.')).toBeInTheDocument();
        apiFetch.mockResolvedValueOnce(reply({ ...open, seen_instances: ['moodle.school.example'], locked_instances: ['moodle.school.example'] }));
        await fireEvent.click(screen.getByRole('button', { name: 'Add moodle.school.example' }));
        await waitFor(() => expect(body()).toEqual({ locked_instances: ['moodle.school.example'] }));
    });

    it('lets the system administrator type an identifier and edit the whitelist before saving it', async () => {
        apiFetch.mockResolvedValueOnce(reply({ whitelist_enabled: false, allowed_instances: [], seen_instances: ['atenea.upc.edu'] }));
        render(LtiAccessSettings, { global: true });
        const checkbox = await screen.findByLabelText('Accept only the installations in this list');
        await fireEvent.click(checkbox);
        expect(screen.getByText(/every LTI 1.1 launch is refused/)).toBeInTheDocument();
        await fireEvent.click(screen.getByRole('button', { name: 'Add atenea.upc.edu' }));
        await fireEvent.input(screen.getByLabelText('Identifier, exactly as the LMS sends it'), { target: { value: ' campus virtual ' } });
        await fireEvent.click(screen.getByRole('button', { name: 'Add to the list' }));
        expect(apiFetch).toHaveBeenCalledTimes(1);  // nothing is sent until Save
        const saved = { whitelist_enabled: true, allowed_instances: ['atenea.upc.edu', 'campus virtual'] };
        apiFetch.mockResolvedValueOnce(reply({ ...saved, seen_instances: ['atenea.upc.edu'] }));
        await fireEvent.click(screen.getByRole('button', { name: 'Save' }));
        await screen.findByText('LMS access settings saved.');
        expect(apiFetch.mock.lastCall[0]).toBe('/admin/lti-access');
        expect(body()).toEqual(saved);
    });

    it('is translated', async () => {
        locale.set('ca');
        apiFetch.mockResolvedValueOnce(reply({ ...open, my_instance: 'atenea.upc.edu' }));
        render(LtiAccessSettings, {});
        expect(await screen.findByRole('button', { name: 'Bloqueja a atenea.upc.edu' })).toBeInTheDocument();
        expect(screen.getByRole('heading', { name: 'Bloqueja al teu LMS' })).toBeInTheDocument();
    });
});
