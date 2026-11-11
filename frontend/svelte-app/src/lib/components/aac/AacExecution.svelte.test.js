import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
vi.mock('$lib/services/apiClient', () => ({apiJson: vi.fn()}));
vi.mock('$lib/services/frontendManage', () => ({openSavedResult: vi.fn().mockResolvedValue({status: 'opened'})}));
import { apiJson } from '$lib/services/apiClient';
import { openSavedResult } from '$lib/services/frontendManage';
import Execution from './AacExecution.svelte';

const state = () => ({mode: 'auto', task_id: 'task', calls: 5, call_limit: 10, tools: 15, status: 'completed', changes: 1,
    reports: [{id: 'report', title: 'Saved test report'}], steps: []});
describe('LEGATUS execution controls', () => {
    beforeEach(() => vi.clearAllMocks());
    it('opens the saved result only on click, with no model message', async () => {
        render(Execution, {sessionId: 'session', execution: state()});
        expect(openSavedResult).not.toHaveBeenCalled();
        await fireEvent.click(screen.getByRole('button', {name: 'Show me'}));
        expect(openSavedResult).toHaveBeenCalledWith('session', 'report');
        expect(apiJson).not.toHaveBeenCalled();
    });
    it('shows progress without a continuation or next-step menu', () => {
        render(Execution, {sessionId: 'session', busy: true, execution: {...state(), status: 'active',
            plan: {title: 'Run tests'}, steps: [{id: 'run', title: 'Run the normal case', status: 'running'}]}});
        expect(screen.getByText('Run the normal case')).toBeTruthy();
        expect(screen.queryByRole('button', {name: 'Show me'})).toBeNull();
        expect(screen.queryByRole('button', {name: /continue|next/i})).toBeNull();
        expect(screen.getByRole('combobox').disabled).toBe(true);
    });
    it('mode changes are explicit and refresh saved state', async () => {
        apiJson.mockResolvedValueOnce({mode: 'guided'});
        const refresh = vi.fn();
        render(Execution, {sessionId: 'session', execution: state(), refresh});
        await fireEvent.change(screen.getByRole('combobox'), {target: {value: 'guided'}});
        await waitFor(() => expect(refresh).toHaveBeenCalledOnce());
        expect(JSON.parse(apiJson.mock.calls[0][1].body)).toEqual({mode: 'guided'});
    });
    it('shows old values and requests review rather than performing a restore', async () => {
        apiJson.mockResolvedValueOnce([{id: 'change', action: 'assistant.update', status: 'completed',
            before: {fields: {system_prompt: 'Previous prompt'}}, after: {fields: {system_prompt: 'New prompt'}}, restorable: true}]);
        const restore = vi.fn();
        render(Execution, {sessionId: 'session', execution: state(), restore});
        await fireEvent.click(screen.getByRole('button', {name: 'Changes'}));
        await fireEvent.click(await screen.findByRole('button', {name: /assistant.update/}));
        expect(screen.getByText(/Previous prompt/)).toBeTruthy();
        await fireEvent.click(screen.getByRole('button', {name: 'Review restoration'}));
        expect(restore).toHaveBeenCalledWith('change');
        expect(apiJson).toHaveBeenCalledTimes(1);
    });
});
