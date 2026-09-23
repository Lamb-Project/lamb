<script>
    import { chartText } from '$lib/utils/aacChartText';
    let { data, imageUrl = '' } = $props();
    const labels = $derived(data.calendar_labels);
    const text = $derived(chartText(data.language));
</script>

<section data-deadline-calendar aria-label={data.title}>
    <h3>{data.title}</h3>
    <p>{data.window_label}</p>
    {#if !data.coverage.complete}<p data-chart-coverage>{text.partial}</p>{/if}
    <p>{data.caption}</p>
    {#if imageUrl}
        <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
        <div class="scroll calendar-image" role="region" tabindex="0" aria-label={labels.timeline}>
            <img src={imageUrl} alt={data.title} />
        </div>
    {/if}
    <h4>{labels.timeline}</h4>
    {#if !data.events.length}<p role="status">{text.analyticsEmpty}</p>{/if}
    <ol class="events">
        {#each data.events as event}
            <li><time datetime={event.local}>{event.local}</time>
                <strong>{event.name} (#{event.cmid})</strong>
                <span>{labels[event.kind]}{event.also_closes ? ' / ' + labels.closes : ''}</span>
            </li>
        {/each}
    </ol>
    <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
    <div class="scroll" role="region" tabindex="0" aria-label={labels.weekly}>
        <table><caption>{labels.weekly}</caption>
            <thead><tr><th scope="col">{labels.week}</th><th scope="col">{labels.metric}</th><th scope="col">{labels.partial}</th></tr></thead>
            <tbody>{#each data.weekly as week}<tr><th scope="row">{week.week_start}</th><td>{week.deadlines}</td><td>{week.partial_week ? labels.partial : '–'}</td></tr>{/each}</tbody>
        </table>
    </div>
    <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
    <div class="scroll" role="region" tabindex="0" aria-label={labels.activity}>
        <table class="schedule-table"><caption>{labels.title}</caption>
            <thead><tr><th scope="col">{labels.activity}</th><th scope="col">{labels.opens}</th><th scope="col">{labels.due}</th><th scope="col">{labels.closes}</th><th scope="col">{labels.inside}</th></tr></thead>
            <tbody>{#each data.rows as row}<tr><th scope="row">{row.name}</th><td>{row.opens_label}</td><td>{row.due_label}</td><td>{row.closes_label}</td><td>{row.window_status_label}</td></tr>{/each}</tbody>
        </table>
    </div>
</section>

<style>
    h3,h4 { font-weight:600; margin:12px 0; }
    p { margin:8px 0; }
    .scroll { overflow-x:auto; max-width:100%; margin:16px 0; }
    .scroll:focus { outline:2px solid #2463a1; }
    img { min-width:720px; width:100%; height:auto; }
    table { border-collapse:collapse; width:100%; }
    th,td { text-align:left; padding:8px; border-bottom:1px solid #ccd5df; }
    td { white-space:nowrap; }
    .schedule-table { min-width:1100px; }
    .schedule-table th:first-child { min-width:240px; overflow-wrap:normal; }
    .schedule-table td { min-width:180px; }
    caption { text-align:left; font-weight:600; }
    .events { padding-left:20px; }
    li { margin:10px 0; }
    li time,li strong,li span { display:block; overflow-wrap:anywhere; }
</style>
