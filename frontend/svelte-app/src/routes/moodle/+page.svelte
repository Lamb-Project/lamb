<script>
    import { page } from '$app/stores';
    import { base } from '$app/paths';
    import MoodleEvidence from '$lib/components/MoodleEvidence.svelte';
    import MoodleCharts from '$lib/components/MoodleCharts.svelte';
    import { workspaceText } from '$lib/utils/moodleChartWorkspaceText';
    import MoodleConnection from '$lib/components/MoodleConnection.svelte';
    import { locale } from '$lib/i18n';
    const workspaceLabels = $derived(workspaceText($locale));
    const chartsTab = $derived($page.url.searchParams.get('tab') === 'charts' || !!$page.url.searchParams.get('chart'));
</script>
<svelte:head><title>Moodle | LAMB</title></svelte:head>
<section class="moodle-settings" class:charts-workspace={chartsTab}>
    <nav class="subtabs" aria-label="Moodle">
        <a href={`${base}/moodle`} aria-current={!chartsTab ? 'page' : undefined}>{workspaceLabels.connection}</a>
        <a href={`${base}/moodle?tab=charts`} aria-current={chartsTab ? 'page' : undefined}>{workspaceLabels.charts}</a>
    </nav>
    {#if $page.url.searchParams.get('result')}
        <a href={`${base}/moodle`}>Moodle connection</a>
        <MoodleEvidence resultId={$page.url.searchParams.get('result')} />
    {:else if chartsTab}
        <MoodleCharts chartId={$page.url.searchParams.get('chart')} />
    {:else}
    <MoodleConnection />
    {/if}
</section>
<style>
    .moodle-settings.charts-workspace {max-width:1500px}
    .subtabs {display:flex;gap:8px;border-bottom:1px solid #d6e0ea;margin-bottom:24px}
    .subtabs a {padding:12px 18px;color:#173f64}.subtabs a[aria-current] {border-bottom:3px solid #2463a1;font-weight:600}
    .moodle-settings{max-width:850px;margin:2rem auto;padding:0 1rem;color:#1f2937}
</style>
