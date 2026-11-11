<script>
    import { analysisText } from '$lib/utils/activityAnalysisText';
    import { apiJson } from '$lib/services/apiClient';
    import { openSavedResult, openTaskResult } from '$lib/services/frontendManage';
    import { executionText } from '$lib/utils/aacExecutionText';
    /** @type {{sessionId:string, execution?:any, language?:string, busy?:boolean, refresh?:()=>Promise<void>, restore?:(id:string)=>void}} */
    let { sessionId, execution = null, language = 'en', busy = false, refresh = async () => {}, restore = () => {} } = $props();
    let error = $state('');
    /** @type {any[]|null} */
    let changes = $state(null);
    /** @type {any} */
    let selected = $state(null);
    let saving = $state(false);
    const labels = $derived(executionText(language));
    const report = $derived(execution?.reports?.findLast(/** @param {any} r */ r => r.task_id === execution.task_id || !r.task_id));
    const resultTitle = $derived(report?.title || execution?.result?.title || '');
    /** @param {{mode?:string,new_task?:boolean}} body */
    async function setting(body) {
        saving = true; error = '';
        try { await apiJson(`/aac/sessions/${sessionId}/execution`, {method: 'PUT', body: JSON.stringify(body)}); await refresh(); }
        catch (e) { error = e instanceof Error ? e.message : String(e); }
        finally { saving = false; }
    }
    async function show() {
        error = '';
        const result = report ? await openSavedResult(sessionId, report.id) : await openTaskResult(execution.result.destination);
        if (result.status !== 'opened') error = result.reason || 'Unable to open the result';
    }
    async function history() {
        error = '';
        if (changes) { changes = null; selected = null; return; }
        try { changes = await apiJson(`/aac/sessions/${sessionId}/changes`); }
        catch (e) { error = e instanceof Error ? e.message : String(e); }
    }
</script>

{#if execution}
<section class="execution" aria-label={labels.execution}>
    <div class="controls">
        <label>{labels.mode}
            <select value={execution.mode} disabled={busy || saving} onchange={(e) => setting({mode: e.currentTarget.value})}>
                <option value="auto">{labels.auto}</option><option value="guided">{labels.guided}</option>
            </select>
        </label>
        <span>{labels.calls}: {execution.calls}/{execution.call_limit} · {labels.tools}: {execution.tools}</span>
        <button disabled={busy || saving} onclick={() => setting({new_task: true})}>{labels.newTask}</button>
        {#if execution.changes}<button disabled={busy} onclick={history}>{labels.changes}</button>{/if}
    </div>
    {#if execution.plan && execution.status !== 'completed'}
        <div class="plan-title">{execution.plan.title}</div>
        <ol>{#each execution.steps || [] as step}<li>{step.title} <span>{labels[step.status] || step.status}</span></li>{/each}</ol>
    {/if}
    {#if (report || execution.result) && execution.status === 'completed'}
        <div class="result"><strong>{resultTitle}</strong> <button class="primary" onclick={show}>{report?.destination?.tab === 'analysis' ? analysisText(language).showReport : labels.showMe}</button></div>
    {/if}
    {#if changes}
        <div class="changes">
            {#each changes as change}
                <button onclick={() => selected = selected?.id === change.id ? null : change}>{change.action} · {labels[change.status] || change.status}</button>
            {/each}
            {#if selected}
                <p>{labels.previous}</p><pre>{JSON.stringify(selected.before?.fields || selected.before, null, 2)}</pre>
                <p>{labels.current}</p><pre>{JSON.stringify(selected.after?.fields || selected.after, null, 2)}</pre>
                {#if selected.restorable}<button disabled={busy} onclick={() => restore(selected.id)}>{labels.restore}</button>{/if}
            {/if}
        </div>
    {/if}
    {#if error}<p role="alert">{error}</p>{/if}
</section>
{/if}

<style>
    .execution { padding: .55rem .75rem; border-bottom: 1px solid #94a3b8; font-size: .78rem; color: inherit; }
    .controls, .result { display: flex; gap: .5rem; align-items: center; flex-wrap: wrap; }
    button, select { border: 1px solid #94a3b8; border-radius: .35rem; padding: .25rem .45rem; background: transparent; color: inherit; }
    button:disabled, select:disabled { opacity: .5; }
    .primary { background: #1d4ed8; color: white; }
    ol { margin: .4rem 0 .4rem 1.2rem; list-style: decimal; max-height: 8rem; overflow: auto; }
    li span { opacity: .7; margin-left: .4rem; }
    .plan-title { margin-top: .5rem; font-weight: 600; }
    .changes { margin-top: .5rem; max-height: 18rem; overflow: auto; }
    pre { white-space: pre-wrap; overflow-wrap: anywhere; font-size: .72rem; margin: .25rem 0 .6rem; }
    [role=alert] { color: #dc2626; margin-top: .4rem; }
</style>
