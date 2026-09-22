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

it('renders a generic analytics snapshot without submission-specific caveats', async () => {
    apiJson.mockResolvedValue({...snapshot(),view_kind:'metric-bars-v1',title:'Grading queue',metric_label:'Needs grading',
        window_label:'Since 2026-09-01, Europe/Madrid',population_label:'Visible active student enrolments',
        caption:'Needs grading is not feedback release.',rows:[{name:'Essay',status:'ok',value:2,reason:null}]});
    render(AacChart,{chartId:'analytics'});
    await screen.findByText('Needs grading is not feedback release.');
    expect(screen.getByRole('cell')).toHaveTextContent('2');
    expect(screen.getByRole('region')).toHaveAttribute('tabindex','0');
    expect(screen.getByText('Since 2026-09-01, Europe/Madrid')).toBeInTheDocument();
    expect(screen.getByText('Visible active student enrolments')).toBeInTheDocument();
    expect(screen.queryByText(chartText('en').extensions)).toBeNull();
});

it.each(['en','es','ca','eu'])('distinguishes retrieved coverage from unknown history in %s', async language => {
    apiJson.mockResolvedValue({...snapshot(language),view_kind:'metric-bars-v1',
        coverage:{complete:false,collection_complete:true,history_complete:false},
        rows:[{name:'0',value:1,status:'ok'}]});
    render(AacChart,{chartId:'observed'});
    await screen.findByText(chartText(language).historyUnknown);
    expect(screen.queryByText(chartText(language).partial)).toBeNull();
    cleanup();
    apiJson.mockResolvedValue({...snapshot(language),view_kind:'metric-bars-v1',
        coverage:{complete:false,collection_complete:false,history_complete:false},rows:[]});
    render(AacChart,{chartId:'partial-observed'});
    await screen.findByText(chartText(language).collectionIncomplete);
});

it('renders dated view trends with separate event and viewer columns', async () => {
    apiJson.mockResolvedValue({...snapshot(),view_kind:'view-trend-v1',title:'Recorded daily views',
        metric_label:'Recorded views',caption:'Recorded views only, not all activity.',
        view_columns:['Date','Views','Viewers','Course','Resource','Chapter'],
        view_keys:['date','recorded_views','unique_student_viewers','course_view','resource_view','chapter_view'],
        rows:[{name:'2026-09-21',date:'2026-09-21',status:'ok',value:7,recorded_views:7,
            unique_student_viewers:3,course_view:3,resource_view:4,chapter_view:0}]});
    render(AacChart,{chartId:'view-trends'});
    await screen.findByRole('table');
    expect(screen.getAllByRole('columnheader')).toHaveLength(6);
    expect(screen.getAllByRole('cell').map(cell=>cell.textContent)).toEqual(['7','3','3','4','0']);
    expect(screen.queryByText(chartText('en').extensions)).toBeNull();
});

it('renders the heatmap as a scrollable image and exact seven-by-24 table, not 168 bars', async () => {
    const days=['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'];
    apiJson.mockResolvedValue({...snapshot(),view_kind:'view-heatmap-v1',title:'Recorded view heatmap',
        metric_label:'Recorded views',heatmap_day_label:'Weekday',
        rows:days.flatMap((day,weekday)=>Array.from({length:24},(_,hour)=>({
            name:`${day} ${hour}`,weekday,hour,value:weekday===0&&hour===9?4:0,status:'ok'}))),
        heatmap_rows:days.map((day,weekday)=>({day,values:Array.from({length:24},(_,hour)=>weekday===0&&hour===9?4:0)}))});
    render(AacChart,{chartId:'heatmap'});
    await screen.findByRole('img');
    expect(screen.getAllByRole('columnheader')).toHaveLength(25);
    expect(screen.getAllByRole('rowheader')).toHaveLength(7);
    expect(screen.getAllByRole('cell')).toHaveLength(168);
    expect(screen.getAllByRole('cell')[9]).toHaveTextContent('4');
    expect(document.querySelector('.mobile-chart')).toBeNull();
    expect(document.querySelector('.heatmap-chart')).toHaveAttribute('tabindex','0');
});

it.each(['en','es','ca','eu'])('handles empty analytics without assignment claims in %s', async language => {
    apiJson.mockResolvedValue({...snapshot(language),view_kind:'metric-bars-v1',rows:[]});
    render(AacChart,{chartId:'empty-analytics'});
    await screen.findByText(chartText(language).analyticsEmpty);
    expect(screen.queryByRole('table')).toBeNull();
    expect(apiFetch).not.toHaveBeenCalled();
});

it('does not turn unavailable analytics into zero bars', async () => {
    apiJson.mockResolvedValue({...snapshot(),view_kind:'metric-bars-v1',
        rows:[{name:'Team',status:'unavailable',value:null,reason:'Unsupported'}]});
    render(AacChart,{chartId:'unavailable-analytics'});
    await screen.findByText(chartText('en').analyticsUnavailable);
    expect(screen.getByRole('cell')).toHaveTextContent('–');
    expect(apiFetch).not.toHaveBeenCalled();
});

it('separates resource viewers, event counts and student population', async () => {
    apiJson.mockResolvedValue({...snapshot(),view_kind:'metric-bars-v1',resource_columns:
        ['Resource','Unique students','Module views','Chapter views','Population'],
        rows:[{name:'Reading',status:'ok',value:2,unique_student_viewers:2,
            recorded_module_views:4,recorded_chapter_views:0,population_students:3}]});
    render(AacChart,{chartId:'resource'});
    await screen.findByRole('table');
    expect(screen.getAllByRole('cell').map(cell=>cell.textContent)).toEqual(['2','4','0','3']);
    expect(screen.getAllByRole('columnheader')).toHaveLength(5);
    expect(screen.getByRole('region')).toHaveAttribute('tabindex','0');
});

it('shows grade summaries with zero distinct from missing', async () => {
    apiJson.mockResolvedValue({...snapshot(),view_kind:'metric-bars-v1',
        summary_statistics:[{label:'Mean (%)',value:0},{label:'Median (%)',value:null}],
        rows:[{name:'[0, 10) %',status:'ok',value:1}]});
    render(AacChart,{chartId:'grades'});
    await screen.findByText('Mean (%)');
    const stats=document.querySelector('[data-analytics-statistics]');
    expect([...stats.querySelectorAll('dd')].map(e=>e.textContent)).toEqual(['0',chartText('en').analyticsUnavailable]);
});

it('keeps completion fail, unknown and untracked separate in the exact table', async () => {
    apiJson.mockResolvedValue({...snapshot(),view_kind:'metric-bars-v1',
        completion_columns:['Activity','Complete-fail','Unknown','Untracked'],
        completion_keys:['name','complete_fail','unknown','untracked'],
        rows:[{name:'Task',status:'ok',value:0,complete_fail:1,unknown:2,untracked:3}]});
    render(AacChart,{chartId:'completion'});
    await screen.findByRole('table');
    expect(screen.getAllByRole('cell').map(cell=>cell.textContent)).toEqual(['1','2','3']);
    expect(screen.getByRole('region')).toHaveAttribute('tabindex','0');
});
