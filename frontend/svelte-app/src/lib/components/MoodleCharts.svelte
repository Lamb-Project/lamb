<script>
    import { onMount } from 'svelte';
    import { base } from '$app/paths';
    import { locale } from '$lib/i18n';
    import { apiJson } from '$lib/services/apiClient';
    import { createSession } from '$lib/services/aacService';
    import { showSession, sidebarBusy } from '$lib/stores/aacStore.svelte';
    import { workspaceText } from '$lib/utils/moodleChartWorkspaceText';
    import { chartText } from '$lib/utils/aacChartText';
    import AacChart from './aac/AacChart.svelte';
    let { chartId = null } = $props();
    let charts = $state([]), next = $state(null), loading = $state(true), error = $state(''), opening = $state(false);
    const text = $derived(workspaceText($locale));
    const groups = $derived([...new Set(charts.map(c => c.course_id))].map(id => ({
        id, name:charts.find(c => c.course_id === id).course_name, items:charts.filter(c => c.course_id === id)
    })));
    let requestId = 0;
    async function load(append = false) {
        const id = ++requestId;
        loading = true; error = '';
        if (!append) { charts = []; next = null; }
        try {
            const result = await apiJson(`/moodle/charts?offset=${append ? next : 0}`);
            if (id !== requestId) return;
            charts = [...(append ? charts : []), ...result.items].filter((c,i,a) => a.findIndex(x => x.chart_id === c.chart_id) === i);
            next = result.next_offset;
        } catch (_) { if (id === requestId) error = chartText($locale).error; }
        finally { if (id === requestId) loading = false; }
    }
    onMount(() => {
        load();
        const changed = () => load();
        window.addEventListener('moodle-charts-changed', changed);
        return () => { requestId++; window.removeEventListener('moodle-charts-changed', changed); };
    });
    function date(item) { return new Intl.DateTimeFormat($locale || 'en', {dateStyle:'medium',timeStyle:'short',timeZone:item.timezone}).format(new Date(item.as_of)); }
    async function ask() {
        if ($sidebarBusy || opening) return;
        opening = true; error = '';
        try {
            const session = await createSession({skill:'moodle-triage', chartId});
            showSession(session.id, session.title);
        } catch (_) { error = chartText($locale).error; }
        finally { opening = false; }
    }
</script>

<div class="workspace" class:has-selection={!!chartId} data-chart-workspace>
    {#if error}<p class="workspace-error" role="alert">{error}</p>{/if}
    <aside class="chart-sidebar" aria-label={text.list}>
        <h2>{text.list}</h2>
        <button disabled={loading} onclick={() => load()}>{text.reload}</button>
        {#each groups as group}
            <section><h3>{group.name}</h3><ul>
                {#each group.items as chart}
                    <li><a href={`${base}/moodle?tab=charts&chart=${encodeURIComponent(chart.chart_id)}`}
                        aria-current={chartId === chart.chart_id ? 'page' : undefined} data-saved-chart={chart.chart_id}>
                        <span>{chart.title}</span><time datetime={chart.as_of}>{date(chart)} · {chart.timezone}</time>
                    </a></li>
                {/each}
            </ul></section>
        {/each}
        {#if loading}<p role="status">{chartText($locale).loading}</p>{/if}
        {#if !loading && !error && !charts.length}<p>{text.empty}</p>{/if}
        {#if next !== null}<button disabled={loading} onclick={() => load(true)}>{text.more}</button>{/if}
    </aside>
    <section class="chart-detail" aria-label={text.charts}>
        {#if chartId}
            <div class="toolbar">
                <a class="back" href={`${base}/moodle?tab=charts`}>← {text.back}</a>
                <button data-ask-chart disabled={opening || $sidebarBusy} onclick={ask}>{text.ask}</button>
            </div>
            {#if $sidebarBusy}<p role="status">{text.busy}</p>{/if}
            <p class="snapshot-notice">{text.snapshot}</p>
            {#key chartId}<AacChart {chartId} />{/key}
        {:else}<h2>{text.select}</h2>{/if}
    </section>
</div>

<style>
    .workspace { display:grid; grid-template-columns:260px minmax(0,1fr); gap:20px; align-items:start; }
    .workspace-error {grid-column:1/-1;color:#991b1b}
    .chart-sidebar { border-right:1px solid #d6e0ea; padding-right:16px; max-height:75dvh; overflow:auto; }
    h2 {font-size:1.15rem;font-weight:600;margin-bottom:12px} h3 {font-weight:600;margin:20px 0 8px;overflow-wrap:anywhere}
    ul {list-style:none;padding:0} li {margin:6px 0}
    li a {display:block;padding:12px;border:1px solid #d6e0ea;border-radius:6px;overflow-wrap:anywhere}
    li a[aria-current] {background:#e9f2fb;border-color:#2463a1}
    time {display:block;font-size:.8rem;color:#53677b;margin-top:6px}
    .chart-detail {min-width:0} .toolbar {display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}
    button {border:1px solid #2463a1;color:#173f64;border-radius:6px;padding:10px;min-height:44px}
    button:disabled {opacity:.55} .back {display:none} .snapshot-notice {margin:12px 0;color:#53677b;font-size:.9rem}
    :focus-visible {outline:3px solid #2463a1;outline-offset:3px}
    @media(max-width:700px) {
        .workspace {grid-template-columns:minmax(0,1fr)}
        .has-selection .chart-sidebar {display:none}
        .workspace:not(.has-selection) .chart-detail {display:none}
        .chart-sidebar {border:0;max-height:none;padding:0}.back {display:block}
    }
</style>
