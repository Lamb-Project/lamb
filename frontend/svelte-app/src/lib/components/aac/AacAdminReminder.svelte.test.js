import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, cleanup, waitFor } from '@testing-library/svelte';
import '@testing-library/jest-dom/vitest';
vi.mock('$lib/services/apiClient', () => ({ apiJson: vi.fn() }));
import { apiJson } from '$lib/services/apiClient';
const request = vi.mocked(apiJson);
import { user } from '$lib/stores/userStore';
import { sidebarOpen } from '$lib/stores/aacStore.svelte';
import Reminder from './AacAdminReminder.svelte';

const pending = { reminders: [{ id: 'lms_origin_unset', organization_id: 4, settings_path: '/org-admin?view=settings&section=lti-creator' }] };

describe('LEGATUS organization reminder', () => {
    beforeEach(() => {
        cleanup(); vi.resetAllMocks();
        user.setToken('admin-fixture');
        sidebarOpen.set(true);
    });

    it('shows the setup link without starting a conversation and clears after settings save', async () => {
        request.mockResolvedValueOnce(pending);
        render(Reminder);
        expect(await screen.findByRole('link', { name: 'Open the LMS lock' })).toHaveAttribute('href', pending.reminders[0].settings_path);
        expect(screen.getByText(/Locking it to the installation you use is optional/)).toBeInTheDocument();
        request.mockResolvedValueOnce({ reminders: [] });
        await fireEvent(window, new CustomEvent('lamb-lti-access-changed'));
        await waitFor(() => expect(screen.queryByRole('link')).not.toBeInTheDocument());
        expect(request.mock.calls.every(([path]) => path === '/aac/admin-reminders')).toBe(true);
    });

    it('does not show a reminder for ordinary members or configured organizations', async () => {
        request.mockResolvedValue({ reminders: [] });
        render(Reminder);
        await waitFor(() => expect(apiJson).toHaveBeenCalledOnce());
        expect(screen.queryByLabelText('LAMB LEGATUS reminder')).not.toBeInTheDocument();
    });

    it('refreshes when the panel reopens or the window regains focus', async () => {
        request.mockResolvedValue(pending);
        sidebarOpen.set(false);
        render(Reminder);
        expect(apiJson).not.toHaveBeenCalled();
        sidebarOpen.set(true);
        await screen.findByRole('link');
        request.mockResolvedValue({ reminders: [] });
        await fireEvent.focus(window);
        await waitFor(() => expect(screen.queryByRole('link')).not.toBeInTheDocument());
    });

    it('ignores an old organization response after switching accounts', async () => {
        /** @type {(value: typeof pending) => void} */
        let resolveOld = () => {};
        request.mockImplementationOnce(() => new Promise(resolve => { resolveOld = resolve; }));
        render(Reminder);
        await waitFor(() => expect(resolveOld).toBeTypeOf('function'));
        request.mockResolvedValueOnce({ reminders: [] });
        user.setToken('other-account');
        await waitFor(() => expect(apiJson).toHaveBeenCalledTimes(2));
        resolveOld(pending);
        await new Promise(resolve => setTimeout(resolve, 0));
        expect(screen.queryByRole('link')).not.toBeInTheDocument();
    });
});
