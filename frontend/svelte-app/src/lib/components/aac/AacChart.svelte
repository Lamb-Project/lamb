<script>
    import { apiFetch, apiJson } from '$lib/services/apiClient';
    let { chartId } = $props();
    let data = $state(null), imageUrl = $state(''), error = $state('');
    function dateLabel(value) { return new Intl.DateTimeFormat(data.language, {dateStyle:'medium', timeStyle:'short', timeZone:data.timezone}).format(new Date(value)); }
    const statusIndex = {open:6, deadline_passed:7, not_open:8, no_deadline:9};
    $effect(() => {
        const id = chartId;
        const controller = new AbortController();
        let url = '', alive = true;
        data = null; imageUrl = ''; error = '';
        (async () => {
            try {
                const snapshot = await apiJson(`/moodle/charts/${encodeURIComponent(id)}`, {signal:controller.signal});
                const response = await apiFetch(`/moodle/charts/${encodeURIComponent(id)}/image.svg`, {signal:controller.signal});
                if (!response.ok) throw Error('Chart could not be loaded. Check the Moodle connection and retry.');
                const blob = await response.blob();
                if (!alive) return;
                url = URL.createObjectURL(blob); imageUrl = url; data = snapshot;
            } catch (e) { if (alive && e.name !== 'AbortError') error = e.message; }
        })();
        return () => { alive = false; controller.abort(); if(url) URL.revokeObjectURL(url); };
    });
</script>

<div class="chart-content" data-chart-id={chartId}>
{#if error}<p role="alert">{error}</p>
{:else if data}
    <h3>{data.course_name}</h3>
    <p class="snapshot">{dateLabel(data.as_of)} · {data.timezone}</p>
    <p class:partial={!data.coverage.complete} data-chart-coverage>
        {data.coverage.assignments_read} / {data.coverage.assignments_found}
        {data.language === 'es' ? 'tareas consultadas' : data.language === 'ca' ? 'tasques consultades' : 'assignments read'}.
        {#if !data.coverage.complete}<strong>{data.language === 'es' ? 'Datos incompletos' : data.language === 'ca' ? 'Dades incompletes' : 'Incomplete data'}.</strong>{/if}
    </p>
    <div class="image-scroll"><img src={imageUrl} alt={data.title + '. ' + data.caption} /></div>
    <p class="caption">{data.caption}</p>
    <div class="table-scroll" tabindex="0" role="region" aria-label={data.title}>
    <table>
        <caption>{data.title} · {data.course_name}</caption>
        <thead><tr><th>{data.labels[3]}</th><th>{data.labels[1]}</th><th>{data.labels[2]}</th><th>{data.labels[4]}</th><th>{data.labels[5]}</th></tr></thead>
        <tbody>{#each data.rows as row}
            <tr><th scope="row">{row.name}</th><td>{row.submitted ?? '—'}</td><td>{row.outstanding ?? '—'}</td>
                <td>{row.status !== 'ok' ? data.labels[10] : row.deadline ? dateLabel(row.deadline) : data.labels[9]}</td>
                <td>{row.status === 'ok' ? data.labels[statusIndex[row.deadline_status]] : data.labels[10] + ': ' + row.reason}</td></tr>
        {/each}</tbody>
    </table>
    </div>
    <a href={imageUrl} download={`lamb-submissions-${chartId}.svg`}>SVG ↓</a>
{:else}<p role="status">Loading chart…</p>{/if}
</div>
<style>
    .chart-content { padding:20px; color:#172b40; }
    h3 { font-weight:600; font-size:1.15rem; }
    .snapshot { color:#53677b; font-size:.85rem; margin:6px 0; }
    .partial { background:#fff4d5; padding:8px; border-radius:6px; }
    .image-scroll { overflow:auto; margin:18px 0; }
    img { display:block; width:100%; min-width:600px; height:auto; }
    .caption { border-left:3px solid #2463a1; padding:8px 12px; margin-bottom:18px; }
    .table-scroll { overflow:auto; max-width:100%; }
    table { width:100%; min-width:600px; border-collapse:collapse; font-size:.9rem; }
    th, td { border-bottom:1px solid #d6e0ea; text-align:left; padding:10px 8px; }
    caption { text-align:left; font-weight:600; padding:8px; }
    a { display:inline-block; margin-top:16px; color:#2463a1; }
</style>
