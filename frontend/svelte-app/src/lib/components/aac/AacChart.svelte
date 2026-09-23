<script>
    import { locale } from 'svelte-i18n';
    import { apiFetch, apiJson } from '$lib/services/apiClient';
    import { chartText, chartReason } from '$lib/utils/aacChartText';
    import { workspaceText } from '$lib/utils/moodleChartWorkspaceText';
    import DeadlineCalendar from './DeadlineCalendar.svelte';
    let { chartId } = $props();
    let data = $state(null), imageUrl = $state(''), error = $state(false), imageError = $state(false);
    let attempt = $state(0);
    const text = $derived(chartText(data?.language || $locale));
    const supported = $derived(data?.rows.filter(row => row.status === 'ok') || []);
    const maxParticipants = $derived(Math.max(1, ...supported.map(row => row.participants)));
    const maxMetric = $derived(Math.max(1, ...supported.map(row => row.value || 0)));
    function dateLabel(value) { return new Intl.DateTimeFormat(data.language, {dateStyle:'medium', timeStyle:'short', timeZone:data.timezone}).format(new Date(value)); }
    const statusIndex = {open:6, deadline_passed:7, not_open:8, no_deadline:9};
    $effect(() => {
        const id = chartId;
        void attempt;
        const controller = new AbortController();
        let url = '', alive = true;
        data = null; imageUrl = ''; error = false; imageError = false;
        (async () => {
            try {
                const snapshot = await apiJson(`/moodle/charts/${encodeURIComponent(id)}`, {signal:controller.signal});
                if (!alive) return;
                data = snapshot;
                if (!snapshot.rows.some(row => row.status === 'ok')) return;
                try {
                    const response = await apiFetch(`/moodle/charts/${encodeURIComponent(id)}/image.svg`, {signal:controller.signal});
                    if (!response.ok) throw Error('Image unavailable');
                    const blob = await response.blob();
                    if (!alive) return;
                    url = URL.createObjectURL(blob); imageUrl = url;
                } catch (e) { if (alive && e.name !== 'AbortError') imageError = true; }
            } catch (e) { if (alive && e.name !== 'AbortError') error = true; }
        })();
        return () => { alive = false; controller.abort(); if(url) URL.revokeObjectURL(url); };
    });
</script>

<div class="chart-content" data-chart-id={chartId}>
{#if error}
    <p role="alert">{text.error}</p><button onclick={() => attempt++}>{text.retry}</button>
{:else if data}
    <h3>{data.course_name}</h3>
    <p class="snapshot">{dateLabel(data.as_of)} · {data.timezone}</p>
    {#if data.view_kind === 'deadline-calendar-v1'}
        <DeadlineCalendar {data} {imageUrl} />
        {#if imageError}<p role="status">{text.imageError}</p><button onclick={() => attempt++}>{text.retry}</button>{/if}
    {:else if ['metric-bars-v1','view-trend-v1','view-heatmap-v1'].includes(data.view_kind)}
        <h3>{data.title}</h3>
        {#if data.window_label}<p class="snapshot" data-analytics-window>{data.window_label}</p>{/if}
        {#if data.population_label}<p class="snapshot" data-analytics-population>{data.population_label}</p>{/if}
        {#if data.summary_statistics}
            <dl class="summary-statistics" data-analytics-statistics>
                {#each data.summary_statistics as statistic}
                    <div>
                    <dt>{statistic.label}</dt>
                    <dd>{statistic.value === null ? text.analyticsUnavailable : new Intl.NumberFormat(data.language, {maximumFractionDigits: 4}).format(statistic.value)}</dd>
                    </div>
                {/each}
            </dl>
        {/if}
        {#if data.coverage.history_complete === false && typeof data.coverage.collection_complete === 'boolean'}
            <p class="partial" data-chart-coverage>{data.coverage.collection_complete === true ? text.historyUnknown : text.collectionIncomplete}</p>
        {:else if !data.coverage.complete}<p class="partial" data-chart-coverage>{text.partial}</p>{/if}
        {#if !data.rows.length}<p role="status">{text.analyticsEmpty}</p>
        {:else if !supported.length}<p role="status">{text.analyticsUnavailable}</p>{/if}
        {#if imageUrl && data.view_kind === 'view-heatmap-v1'}
            <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
            <div class="heatmap-chart" role="region" tabindex="0" aria-label={data.title}><img src={imageUrl} alt={data.title} /></div>
        {:else if imageUrl}<div class="desktop-chart"><img src={imageUrl} alt={data.title} /></div>{/if}
        {#if data.view_kind !== 'view-heatmap-v1'}
        <ul class="mobile-chart" aria-label={data.title}>
            {#each supported as row}<li><strong>{row.name}</strong>
                <div class="bar" aria-hidden="true"><span class="submitted" style:width={`${100 * row.value / maxMetric}%`}></span></div>
                <p>{data.metric_label}: {row.value}</p>
            </li>{/each}
        </ul>
        {/if}
        {#if imageError}<p role="status">{text.imageError}</p><button onclick={() => attempt++}>{text.retry}</button>{/if}
        <p class="caption">{data.caption}</p>
        {#if data.rows.length}
        <p class="table-hint">{text.table}</p>
        <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
        <div class="table-scroll" tabindex="0" role="region" aria-label={text.table}>
            {#if data.heatmap_rows}
            <table class="heatmap-table"><caption>{data.title}</caption>
                <thead><tr><th scope="col">{data.heatmap_day_label}</th>{#each Array(24) as _,hour}<th scope="col">{hour}:00</th>{/each}</tr></thead>
                <tbody>{#each data.heatmap_rows as row}<tr><th scope="row">{row.day}</th>
                    {#each row.values as value}<td>{value}</td>{/each}
                </tr>{/each}</tbody>
            </table>
            {:else if data.view_columns}
            <table><caption>{data.title}</caption>
                <thead><tr>{#each data.view_columns as column}<th scope="col">{column}</th>{/each}</tr></thead>
                <tbody>{#each data.rows as row}<tr><th scope="row">{row.date}</th>
                    {#each data.view_keys.slice(1) as key}<td>{row[key] ?? '–'}</td>{/each}
                </tr>{/each}</tbody>
            </table>
            {:else if data.completion_columns}
            <table class="completion-table"><caption>{data.title}</caption>
                <thead><tr>{#each data.completion_columns as column}<th scope="col">{column}</th>{/each}</tr></thead>
                <tbody>{#each data.rows as row}<tr><th scope="row">{row.name}</th>
                    {#each data.completion_keys.slice(1) as key}<td>{row[key] ?? '–'}</td>{/each}
                </tr>{/each}</tbody>
            </table>
            {:else if data.resource_columns}
            <table><caption>{data.title}</caption>
                <thead><tr>{#each data.resource_columns as column}<th scope="col">{column}</th>{/each}</tr></thead>
                <tbody>{#each data.rows as row}<tr><th scope="row">{row.name}</th>
                    <td>{row.unique_student_viewers}</td><td>{row.recorded_module_views}</td>
                    <td>{row.recorded_chapter_views}</td><td>{row.population_students}</td>
                </tr>{/each}</tbody>
            </table>
            {:else}
            <table class="metric-table"><caption>{data.title}</caption>
                <thead><tr><th scope="col">{data.title}</th><th scope="col">{data.metric_label}</th></tr></thead>
                <tbody>{#each data.rows as row}<tr><th scope="row">{row.name}</th><td>{row.value ?? '–'}{#if row.reason}<br />{row.reason}{/if}</td></tr>{/each}</tbody>
            </table>
            {/if}
        </div>
        {/if}
    {:else}
    <p class:partial={!data.coverage.complete} data-chart-coverage>
        {data.coverage.assignments_read} / {data.coverage.assignments_found} {text.read}.
        {#if !data.coverage.complete}<strong>{text.partial}.</strong>{/if}
        {#if data.coverage.omitted_by_limit} {text.omitted}: {data.coverage.omitted_by_limit}.{/if}
    </p>
    {#if !data.rows.length}<p role="status">{text.empty}</p>
    {:else if !supported.length}<p role="status">{text.unavailable}</p>{/if}
    {#if imageUrl}<div class="desktop-chart"><img src={imageUrl} alt={data.title + '. ' + data.caption} /></div>{/if}
    {#if imageError}<p role="status">{text.imageError}</p><button onclick={() => attempt++}>{text.retry}</button>{/if}
    <ul class="mobile-chart" aria-label={data.title}>
        {#each supported as row}
            <li>
                <strong>{row.name}</strong>
                <div class="bar" aria-hidden="true">
                    <span class="submitted" style:width={`${100 * row.submitted / maxParticipants}%`}></span>
                    <span class="outstanding" style:width={`${100 * row.outstanding / maxParticipants}%`}></span>
                </div>
                <p>{text.submitted}: {row.submitted} · {text.outstanding}: {row.outstanding}</p>
                <p class="snapshot">{data.labels[statusIndex[row.deadline_status]]}{row.deadline ? ': ' + dateLabel(row.deadline) : ''}</p>
            </li>
        {/each}
    </ul>
    <p class="caption">{workspaceText(data.language).caption}<br /><span>{text.extensions}</span></p>
    {#if data.deadline_provenance_caption}<p class="caption" data-deadline-provenance>{data.deadline_provenance_caption}</p>{/if}
    {#if data.rows.length}
    <p class="table-hint">{text.table}</p>
    <!-- Keyboard focus lets users scroll the exact-values table with arrow keys. -->
    <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
    <div class="table-scroll" tabindex="0" role="region" aria-label={text.table}>
    <table>
        <caption>{data.title} · {data.course_name}</caption>
        <thead><tr><th scope="col">{data.labels[3]}</th><th scope="col">{data.labels[1]}</th><th scope="col">{data.labels[2]}</th><th scope="col">{data.labels[4]}</th><th scope="col">{data.labels[5]}</th></tr></thead>
        <tbody>{#each data.rows as row}
            <tr><th scope="row">{row.name}</th><td>{row.submitted ?? '–'}</td><td>{row.outstanding ?? '–'}</td>
                <td>{row.status !== 'ok' ? data.labels[10] : row.deadline ? dateLabel(row.deadline) : data.labels[9]}</td>
                <td>{row.status === 'ok' ? data.labels[statusIndex[row.deadline_status]] : data.labels[10] + ': ' + chartReason(row, data.language)}</td></tr>
        {/each}</tbody>
    </table>
    </div>
    {/if}
    {/if}
    {#if imageUrl}<a href={imageUrl} download={`lamb-chart-${chartId}.svg`}>{text.download}</a>{/if}
{:else}<p role="status">{text.loading}</p>{/if}
</div>
<style>
    .chart-content { padding:20px; color:#172b40; min-width:0; overflow-wrap:anywhere; }
    h3 { font-weight:600; font-size:1.15rem; }
    .snapshot { color:#53677b; font-size:.85rem; margin:6px 0; }
    .summary-statistics { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; margin:16px 0; }
    .summary-statistics dt { color:#53677b; font-size:.85rem; }
    .summary-statistics dd { margin:0; font-weight:600; }
    .partial { background:#fff4d5; padding:8px; border-radius:6px; }
    .desktop-chart { margin:18px 0; }
    .heatmap-chart { margin:18px 0; overflow:auto; max-width:100%; }
    .heatmap-chart img { min-width:720px; }
    .heatmap-table { min-width:1250px; }
    .heatmap-table th, .heatmap-table td { white-space:nowrap; word-break:normal; }
    .heatmap-table th:first-child { min-width:120px; }
    img { display:block; width:100%; height:auto; }
    .mobile-chart { display:none; list-style:none; padding:0; margin:16px 0; }
    .mobile-chart li { margin-bottom:18px; }
    .mobile-chart p { margin:4px 0; }
    .bar { display:flex; height:20px; margin:6px 0; }
    .submitted { background:#2463a1; }
    .outstanding { background:#c9d3df; }
    .caption { border-left:3px solid #2463a1; padding:8px 12px; margin-bottom:18px; }
    .table-hint { font-size:.85rem; margin-bottom:6px; }
    .table-scroll { overflow:auto; max-width:100%; }
    table { width:100%; min-width:600px; border-collapse:collapse; font-size:.9rem; }
    .metric-table { min-width:0; table-layout:fixed; }
    .metric-table th:first-child { width:65%; }
    .completion-table { min-width:1600px; }
    .completion-table th, .completion-table td { min-width:100px; overflow-wrap:normal; }
    .completion-table th:first-child { min-width:220px; max-width:300px; overflow-wrap:anywhere; }
    th, td { border-bottom:1px solid #d6e0ea; text-align:left; padding:10px 8px; }
    caption { text-align:left; font-weight:600; padding:8px; }
    a, button { display:inline-block; margin-top:16px; color:#2463a1; }
    button { border:1px solid #2463a1; padding:8px 16px; border-radius:6px; }
    :focus-visible { outline:3px solid #2463a1; outline-offset:3px; }
    @media(max-width:600px) {
        .summary-statistics { grid-template-columns:repeat(2,minmax(0,1fr)); }
        .chart-content { padding:12px; }
        .desktop-chart { display:none; }
        .mobile-chart { display:block; }
    }
</style>
