import { beforeEach, expect, it, vi } from 'vitest';
import { render, screen, fireEvent, cleanup, waitFor } from '@testing-library/svelte';
import { locale } from '$lib/i18n';
vi.mock('$lib/i18n', async () => ({locale:(await import('svelte-i18n')).locale}));
vi.mock('$lib/services/apiClient', () => ({apiJson:vi.fn(), apiFetch:vi.fn()}));
vi.mock('$lib/services/aacService', () => ({createSession:vi.fn()}));
vi.mock('$lib/stores/aacStore.svelte', async () => {const {writable}=await import('svelte/store');return {showSession:vi.fn(),sidebarBusy:writable(false)};});
import { apiJson } from '$lib/services/apiClient';
import { createSession } from '$lib/services/aacService';
import { showSession, sidebarBusy } from '$lib/stores/aacStore.svelte';
import { workspaceText } from '$lib/utils/moodleChartWorkspaceText';
import MoodleCharts from './MoodleCharts.svelte';
const item = {chart_id:'saved',title:'Submissions',course_id:7,course_name:'Synthetic course',as_of:'2026-09-22T12:00:00Z',timezone:'UTC'};
beforeEach(() => {cleanup();vi.resetAllMocks();locale.set('en');sidebarBusy.set(false);apiJson.mockResolvedValue({items:[item],next_offset:null});createSession.mockResolvedValue({id:'new',title:'Saved chart'});});
it.each(['en','es','ca','eu'])('lists saved evidence with a dated link in %s', async language => {
    locale.set(language);render(MoodleCharts);
    await screen.findByText('Synthetic course');
    expect(screen.getByRole('link')).toHaveAttribute('href','/moodle?tab=charts&chart=saved');
    expect(screen.getByText(workspaceText(language).list)).toBeInTheDocument();
    expect(document.querySelector('time')).toHaveAttribute('datetime',item.as_of);
    expect(apiJson).toHaveBeenCalledWith('/moodle/charts?offset=0');
});
it('opens a new chart-bound conversation without sending a question or refreshing Moodle', async () => {
    apiJson.mockImplementation(async path => path.includes('?offset=')?{items:[item],next_offset:null}:Promise.reject(Error('chart unavailable')));
    render(MoodleCharts,{chartId:'saved'});
    await fireEvent.click(screen.getByRole('button',{name:workspaceText('en').ask}));
    await waitFor(()=>expect(showSession).toHaveBeenCalledWith('new','Saved chart'));
    expect(createSession).toHaveBeenCalledWith({skill:'moodle-triage',chartId:'saved'});
    expect(screen.queryByRole('dialog')).toBeNull();
});
it('does not replace a busy conversation', async () => {
    sidebarBusy.set(true);apiJson.mockRejectedValue(Error('no data'));
    render(MoodleCharts,{chartId:'saved'});
    expect(screen.getByRole('button',{name:workspaceText('en').ask})).toBeDisabled();
    expect(createSession).not.toHaveBeenCalled();
});
it('supports an empty library and paginated authorized metadata', async () => {
    apiJson.mockResolvedValueOnce({items:[],next_offset:20}).mockResolvedValueOnce({items:[item],next_offset:null});
    render(MoodleCharts);
    await screen.findByText(workspaceText('en').empty);
    await fireEvent.click(screen.getByRole('button',{name:workspaceText('en').more}));
    await screen.findByText('Synthetic course');
    expect(apiJson).toHaveBeenLastCalledWith('/moodle/charts?offset=20');
});
it('does not present failed listing as an empty library', async () => {
    apiJson.mockRejectedValue(Error('private server detail'));render(MoodleCharts);
    await screen.findByRole('alert');
    expect(screen.queryByText(workspaceText('en').empty)).toBeNull();
    expect(screen.queryByText('private server detail')).toBeNull();
});
