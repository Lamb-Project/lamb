import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, cleanup, waitFor } from '@testing-library/svelte';
import '@testing-library/jest-dom/vitest';
vi.mock('$lib/services/apiClient', () => ({ apiFetch: vi.fn() }));
import { apiFetch } from '$lib/services/apiClient';
import LtiAccessSettings from './LtiAccessSettings.svelte';

const reply = (data, status = 200) => ({ ok: status < 400, json: async () => data });
const policy = { whitelist_enabled: false, allowed_origins: [] };

describe('LMS admission settings', () => {
    beforeEach(() => { cleanup(); vi.resetAllMocks(); });

    it('saves the organization Moodle and displays server refusal', async () => {
        apiFetch.mockResolvedValueOnce(reply({ moodle_url: '', ...policy }));
        render(LtiAccessSettings, { org: 'faculty' });
        const field = await screen.findByLabelText('Moodle URL');
        expect(apiFetch).toHaveBeenCalledWith('/admin/org-admin/settings/lti-access?org=faculty', { method: 'GET' });
        await fireEvent.input(field, { target: { value: 'https://moodle.example' } });
        apiFetch.mockResolvedValueOnce(reply({ moodle_url: 'https://moodle.example', ...policy }));
        await fireEvent.click(screen.getByRole('button', { name: 'Save LMS access' }));
        await screen.findByText('LMS access settings saved.');
        expect(JSON.parse(apiFetch.mock.lastCall[1].body)).toEqual({ moodle_url: 'https://moodle.example' });
        apiFetch.mockResolvedValueOnce(reply({ detail: 'This LMS is not allowed by the LAMB administrator.' }, 400));
        await fireEvent.click(screen.getByRole('button', { name: 'Save LMS access' }));
        expect(await screen.findByRole('alert')).toHaveTextContent('not allowed');
        expect(screen.queryByText('LMS access settings saved.')).not.toBeInTheDocument();
    });

    it('saves an enabled empty whitelist explicitly and can disable it', async () => {
        apiFetch.mockResolvedValueOnce(reply(policy));
        render(LtiAccessSettings, { global: true });
        const checkbox = await screen.findByLabelText('Restrict LTI to the whitelist');
        await fireEvent.click(checkbox);
        apiFetch.mockResolvedValueOnce(reply({ ...policy, whitelist_enabled: true }));
        await fireEvent.click(screen.getByRole('button', { name: 'Save LMS access' }));
        await screen.findByText('LMS access settings saved.');
        expect(apiFetch.mock.lastCall[0]).toBe('/admin/lti-access');
        expect(JSON.parse(apiFetch.mock.lastCall[1].body)).toEqual({ whitelist_enabled: true, allowed_origins: [] });
        await fireEvent.click(checkbox);
        apiFetch.mockResolvedValueOnce(reply(policy));
        await fireEvent.click(screen.getByRole('button', { name: 'Save LMS access' }));
        await waitFor(() => expect(JSON.parse(apiFetch.mock.lastCall[1].body)).toEqual(policy));
    });

    it('does not offer an organization binding for the system organization', async () => {
        apiFetch.mockResolvedValueOnce(reply({ ...policy, is_system: true }));
        render(LtiAccessSettings, { org: 'lamb' });
        await screen.findByText(/Configure Moodle on each regular organization/);
        expect(screen.queryByRole('button', { name: 'Save LMS access' })).not.toBeInTheDocument();
    });
});
