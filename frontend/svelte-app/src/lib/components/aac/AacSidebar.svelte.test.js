import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import { get } from 'svelte/store';
vi.mock('$lib/services/aacService', () => ({ createSession: vi.fn(), getSessions: vi.fn(), getSession: vi.fn().mockResolvedValue({ conversation: [] }), sendMessageStream: vi.fn(), attachFile: vi.fn(), sendMessage: vi.fn() }));
import { createSession, getSessions, sendMessageStream } from '$lib/services/aacService';
import { sidebarOpen, sidebarBusy, activeTabId, resetSidebar, showSession } from '$lib/stores/aacStore.svelte';
import Sidebar from './AacSidebar.svelte';

describe('persistent AAC sidebar', () => {
    beforeEach(() => { resetSidebar(); vi.clearAllMocks(); });
    it('hides without removing the terminal or losing the session', async () => {
        showSession('existing');
        render(Sidebar);
        await fireEvent.click(screen.getByRole('button', { name: 'Hide AAC' }));
        expect(get(activeTabId)).toBe('existing');
        expect(document.querySelector('.terminal')).not.toBeNull();
        await fireEvent.click(screen.getByRole('button', { name: 'Open AAC' }));
        expect(get(sidebarOpen)).toBe(true);
    });
    it('starts a new session without archiving the old one', async () => {
        createSession.mockResolvedValue({ id: 'new-session', title: 'New helper' });
        showSession('old-session');
        render(Sidebar);
        await fireEvent.click(screen.getByRole('button', { name: 'New conversation' }));
        await waitFor(() => expect(get(activeTabId)).toBe('new-session'));
        expect(createSession).toHaveBeenCalledOnce();
    });
    it('opens and resumes history inside the sidebar', async () => {
        getSessions.mockResolvedValue([{ id: 'saved', title: 'My saved conversation' }]);
        sidebarOpen.set(true);render(Sidebar);
        await fireEvent.click(screen.getByRole('button', { name: 'History', exact: true }));
        await fireEvent.click(await screen.findByRole('button', { name: 'My saved conversation' }));
        expect(get(activeTabId)).toBe('saved');
    });
});
