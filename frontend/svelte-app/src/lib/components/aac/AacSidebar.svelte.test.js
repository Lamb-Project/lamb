import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import { get } from 'svelte/store';
vi.mock('$lib/services/aacService', () => ({ createSession: vi.fn(), getSessions: vi.fn(), getSession: vi.fn().mockResolvedValue({ conversation: [] }), sendMessageStream: vi.fn(), attachFile: vi.fn(), sendMessage: vi.fn() }));
import { createSession, getSessions, getSession, sendMessageStream } from '$lib/services/aacService';
import { sidebarOpen, sidebarBusy, activeTabId, resetSidebar, showSession } from '$lib/stores/aacStore.svelte';
import Sidebar from './AacSidebar.svelte';

describe('persistent AAC sidebar', () => {
    beforeEach(() => { resetSidebar(); vi.clearAllMocks(); });
    it('hides without removing the terminal or losing the session', async () => {
        showSession('existing');
        render(Sidebar);
        await fireEvent.click(screen.getByRole('button', { name: 'Hide LAMB AGENT' }));
        expect(get(activeTabId)).toBe('existing');
        expect(document.querySelector('.terminal')).not.toBeNull();
        await fireEvent.click(screen.getByRole('button', { name: 'Open LAMB AGENT' }));
        expect(get(sidebarOpen)).toBe(true);
    });
    it('waits for resumed history before sending so it cannot overwrite streamed output', async () => {
        let resolveHistory;
        getSession.mockImplementationOnce(() => new Promise(resolve => { resolveHistory=resolve; }));
        showSession('history-race');render(Sidebar);
        const input=screen.getByRole('textbox',{name:'Message LAMB AGENT'});
        expect(input.disabled).toBe(true);
        await fireEvent.input(input,{target:{value:'New question'}});
        await fireEvent.keyDown(input,{key:'Enter'});
        expect(sendMessageStream).not.toHaveBeenCalled();
        resolveHistory({conversation:[{role:'assistant',content:'Saved answer'}]});
        await waitFor(()=>expect(input.disabled).toBe(false));
        sendMessageStream.mockImplementationOnce(async (id,text,chunk) => { chunk('Fresh answer'); });
        await fireEvent.keyDown(input,{key:'Enter'});
        await waitFor(()=>expect(screen.getByText('Fresh answer')).not.toBeNull());
        expect(screen.getByText('Saved answer')).not.toBeNull();
        expect(sendMessageStream).toHaveBeenCalledOnce();
    });
    it('starts a new session without archiving the old one', async () => {
        createSession.mockResolvedValue({ id: 'new-session', title: 'New helper' });
        showSession('old-session');
        render(Sidebar);
        await waitFor(() => expect(screen.getByRole('button', { name: 'New conversation' }).disabled).toBe(false));
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
    it('keeps multiline drafts on Shift+Enter and sends on Enter', async () => {
        showSession('draft-session');render(Sidebar);
        const input = screen.getByRole('textbox', {name: 'Message LAMB AGENT'});
        expect(input.tagName).toBe('TEXTAREA');
        await fireEvent.input(input, {target: {value: 'First line\nSecond line'}});
        await fireEvent.keyDown(input, {key: 'Enter', shiftKey: true});
        expect(sendMessageStream).not.toHaveBeenCalled();
        expect(input.value).toBe('First line\nSecond line');
        await fireEvent.keyDown(input, {key: 'Enter'});
        await waitFor(() => expect(sendMessageStream).toHaveBeenCalledOnce());
        expect(sendMessageStream.mock.calls[0][1]).toBe('First line\nSecond line');
        expect(screen.queryByTitle('Attach source file')).toBeNull();
    });

    it('stops the active request and retains partial output', async () => {
        sendMessageStream.mockImplementationOnce((id,text,chunk,done,error,status,signal) => {
            chunk('Partial answer');
            return new Promise(resolve => signal.addEventListener('abort', resolve, {once:true}));
        });
        showSession('stop-session');render(Sidebar);
        const input=screen.getByRole('textbox',{name:'Message LAMB AGENT'});
        await fireEvent.input(input,{target:{value:'Explain this'}});
        await fireEvent.keyDown(input,{key:'Enter'});
        await fireEvent.click(await screen.findByRole('button',{name:'Stop response'}));
        await waitFor(()=>expect(screen.getByRole('button',{name:'Send'})).not.toBeNull());
        expect(screen.getByText('Partial answer')).not.toBeNull();
        expect(screen.getByRole('status').textContent).toContain('Stopped receiving the response');
    });
    it('shows real tool activity, retains its result during thinking and clears it for the next turn', async () => {
        let progress, finish;
        sendMessageStream.mockImplementationOnce((id,text,chunk,done,error,status) => {
            progress=status;
            return new Promise(resolve => { finish=resolve; });
        });
        showSession('progress-session');render(Sidebar);
        const input=screen.getByRole('textbox',{name:'Message LAMB AGENT'});
        await fireEvent.input(input,{target:{value:'Check my assistant'}});
        await fireEvent.keyDown(input,{key:'Enter'});
        await waitFor(()=>expect(progress).toBeTypeOf('function'));
        expect(screen.getByRole('status').textContent).toContain('Preparing a response');
        progress({status:'tool',command:'Reading assistant config'});
        await waitFor(()=>expect(screen.getByRole('status').textContent).toBe('Reading assistant config'));
        await waitFor(()=>expect(Number.parseInt(screen.getByText(/^\d+s$/).textContent)).toBeGreaterThan(0),{timeout:3500});
        progress({status:'tool_done',command:'Reading assistant config',success:false});
        progress({status:'thinking'});
        await waitFor(()=>expect(screen.getByText('Tool reported a problem: Reading assistant config')).not.toBeNull());
        expect(screen.getByRole('status').textContent).toContain('Reviewing the tool result');
        progress({status:'tool_done',command:'Updating assistant',success:true,awaiting_user_confirmation:true});
        await waitFor(()=>expect(screen.getByText('Awaiting your approval; not executed: Updating assistant')).not.toBeNull());
        expect(screen.queryByText('Tool completed: Updating assistant')).toBeNull();
        finish();
        await waitFor(()=>expect(screen.getByRole('button',{name:'Send'})).not.toBeNull());
        expect(screen.queryByText('Tool reported a problem: Reading assistant config')).toBeNull();
        sendMessageStream.mockImplementationOnce((id,text,chunk,done,error,status,signal)=>new Promise(resolve=>signal.addEventListener('abort',resolve,{once:true})));
        await fireEvent.input(input,{target:{value:'Next request'}});
        await fireEvent.keyDown(input,{key:'Enter'});
        await waitFor(()=>expect(screen.getByRole('status').textContent).toContain('Preparing a response'));
        expect(screen.queryByText('Tool reported a problem: Reading assistant config')).toBeNull();
        await fireEvent.click(screen.getByRole('button',{name:'Stop response'}));
    });
    it('does not send while composing text with an IME', async () => {
        showSession('ime-session');render(Sidebar);
        const input=screen.getByRole('textbox',{name:'Message LAMB AGENT'});
        await fireEvent.input(input,{target:{value:'test'}});
        await fireEvent.keyDown(input,{key:'Enter',isComposing:true});
        expect(sendMessageStream).not.toHaveBeenCalled();
    });

});
