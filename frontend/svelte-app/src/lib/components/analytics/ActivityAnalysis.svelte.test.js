import {vi, it, expect, beforeEach} from 'vitest';
import {render, screen, fireEvent, waitFor, cleanup} from '@testing-library/svelte';
import {init, locale} from 'svelte-i18n';
vi.mock('$lib/services/apiClient', () => ({apiJson: vi.fn()}));
vi.mock('$lib/services/analyticsService', () => ({getChatDetail: vi.fn()}));
vi.mock('$lib/services/aacService', () => ({createSession: vi.fn()}));
vi.mock('$lib/utils/renderMarkdown.js', () => ({renderMarkdownWithMath: /** @param {string} s */ s => s}));
import {apiJson} from '$lib/services/apiClient';
import {getChatDetail} from '$lib/services/analyticsService';
import {createSession} from '$lib/services/aacService';
import {resetSidebar} from '$lib/stores/aacStore.svelte';
import View from './ActivityAnalysis.svelte';
const report = {id:'report', title:'Conceptual findings', created_at:1, period:{start:null,end:null}, dimensions:['learning'], scenario:{title:'Physics',content:'Original context',revision:1}, coverage:{total_conversations:8,provided_conversations:2,exhaustive:false,provided_by_source:{owi:2}}, reviewed_chat_ids:['a'], metrics:{messages_per_conversation:{median:4},user_prompt_characters:{median:18},assistant_response_characters:{median:40}}, content:'Observed misconception', limitations:['Newest-first sample'], evidence:[{chat_id:'a',label:'Conversation 1'}]};
beforeEach(()=>{cleanup();vi.resetAllMocks();resetSidebar();init({fallbackLocale:'en',initialLocale:'en'});locale.set('en');vi.mocked(apiJson).mockImplementation(async p=>p.endsWith('/analysis-reports')?[report]:report);});
it('loads saved report, original scenario, explicit sampling and live evidence', async()=>{
    render(View,{assistantId:7});
    await screen.findByText('Observed misconception');
    expect(screen.getByText('Sampled or incomplete evidence')).toBeTruthy();
    expect(screen.getByText('Original context')).toBeTruthy();
    vi.mocked(getChatDetail).mockResolvedValue(/** @type {any} */ ({messages:[{role:'user',content:'Original student question'}]}));
    await fireEvent.click(screen.getByRole('button',{name:'Conversation 1'}));
    await screen.findByText('Original student question');
    expect(getChatDetail).toHaveBeenCalledWith(7,'a');
});
it('opens the requested report, and does not mask revoked access with an old report', async()=>{
    vi.mocked(apiJson).mockImplementation(async p=>{if(p.endsWith('/analysis-reports'))return [report];throw new Error('403 Access revoked');});
    render(View,{assistantId:7,reportId:'requested'});
    await screen.findByRole('alert');
    expect(apiJson).toHaveBeenCalledWith('/analytics/assistant/7/analysis-reports/requested');
    expect(screen.queryByText('Observed misconception')).toBeNull();
});
it('starts the full-audit recipe with the chosen scope and assistant', async()=>{
    vi.mocked(createSession).mockResolvedValue(/** @type {any} */ ({id:'new-session',title:'Audit'}));
    render(View,{assistantId:7});
    await fireEvent.click(screen.getByRole('button',{name:/Full audit/}));
    await waitFor(()=>expect(createSession).toHaveBeenCalledWith(expect.objectContaining({assistantId:7,skill:'inspect-activity',context:expect.objectContaining({analysis_scope:'full'})})));
});
