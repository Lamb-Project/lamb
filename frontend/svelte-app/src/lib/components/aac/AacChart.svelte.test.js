import { beforeEach, expect, it, vi } from 'vitest';
import { render, screen, fireEvent, cleanup, waitFor } from '@testing-library/svelte';
import { locale } from 'svelte-i18n';
vi.mock('$lib/services/apiClient', () => ({apiJson: vi.fn(), apiFetch: vi.fn()}));
import { apiJson, apiFetch } from '$lib/services/apiClient';
import { chartText, chartReason } from '$lib/utils/aacChartText';
import AacChart from './AacChart.svelte';
const snapshot = (language = 'en') => ({
    course_name: 'Synthetic course', language, timezone: 'Europe/Madrid', as_of: '2026-09-21T15:00:00+02:00',
    title: 'Submissions', caption: 'Course deadlines only.',
    labels: ['Submissions','Submitted','Outstanding','Assignment','Course deadline','Deadline status','Open','Passed','Not open','No deadline','Unavailable'],
    coverage: {complete: false, assignments_read: 1, assignments_found: 2, omitted_by_limit: 0},
    rows: [{name:'Essay',status:'ok',submitted:3,outstanding:3,participants:6,deadline:null,deadline_status:'no_deadline'},
        {name:'Team',status:'unavailable',submitted:null,outstanding:null,reason:'Team submissions are outside this pilot'}]
});
beforeEach(() => {
    cleanup(); vi.resetAllMocks(); locale.set('en');
    URL.createObjectURL = vi.fn(() => 'blob:chart'); URL.revokeObjectURL = vi.fn();
    apiJson.mockResolvedValue(snapshot());
    apiFetch.mockResolvedValue({ok:true,blob:async()=>new Blob(['<svg/>'])});
});
it.each(['en','es','ca','eu'])('localizes exclusions and caveats for %s including old snapshots', async language => {
    apiJson.mockResolvedValue(snapshot(language)); render(AacChart,{chartId:'saved'});
    expect(await screen.findByText(chartText(language).extensions)).toBeInTheDocument();
    expect(screen.getByText('Unavailable: ' + chartText(language).reasons.team)).toBeInTheDocument();
    expect(screen.getByRole('region')).toHaveAttribute('tabindex','0');
    expect(screen.getAllByRole('columnheader')).toHaveLength(5);
    expect(chartReason({reason_code:'offline'},language)).toBe(chartText(language).reasons.offline);
});
it('shows localized failure and retries the same saved ID without a new Moodle task', async () => {
    locale.set('es'); apiJson.mockRejectedValueOnce(new Error('Raw internal detail'));
    render(AacChart,{chartId:'saved'});
    expect(await screen.findByRole('alert')).toHaveTextContent(chartText('es').error);
    expect(screen.queryByText('Raw internal detail')).toBeNull();
    await fireEvent.click(screen.getByRole('button',{name:'Reintentar'}));
    await screen.findByText('Synthetic course');
    expect(apiJson.mock.calls.map(c=>c[0])).toEqual(['/moodle/charts/saved','/moodle/charts/saved']);
});
it('retains the table if rendering fails', async () => {
    apiFetch.mockResolvedValue({ok:false}); render(AacChart,{chartId:'saved'});
    await screen.findByText(chartText('en').imageError);
    expect(screen.getByRole('table')).toBeInTheDocument();
    expect(screen.queryByRole('img')).toBeNull();
});
it('shows empty state without requesting a meaningless image', async () => {
    apiJson.mockResolvedValue({...snapshot(),rows:[],coverage:{complete:true,assignments_read:0,assignments_found:0}});
    render(AacChart,{chartId:'empty'});
    await screen.findByText(chartText('en').empty);
    expect(apiFetch).not.toHaveBeenCalled();
});
it('shows unavailable and capped coverage without zero bars', async () => {
    const data=snapshot();data.rows=data.rows.slice(1);data.coverage.assignments_read=0;data.coverage.omitted_by_limit=3;
    apiJson.mockResolvedValue(data); render(AacChart,{chartId:'partial'});
    await screen.findByText(chartText('en').unavailable);
    expect(screen.getByText(/Assignments omitted by the limit: 3/)).toBeInTheDocument();
    expect(apiFetch).not.toHaveBeenCalled();
});
it('releases the protected blob when the canvas closes', async () => {
    const {unmount}=render(AacChart,{chartId:'saved'});
    await screen.findByRole('img'); unmount();
    await waitFor(()=>expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:chart'));
});
