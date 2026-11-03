<script>
    import { page } from '$app/stores';
    import { locale } from 'svelte-i18n';
    import { apiJson } from '$lib/services/apiClient';
    import { renderMarkdownWithMath } from '$lib/utils/renderMarkdown';
    import { openReportTests } from '$lib/services/frontendManage';
    import { executionText } from '$lib/utils/aacExecutionText';
    /** @type {any} */
    let report = $state(null);
    let error = $state('');
    const labels = $derived(executionText($locale));
    $effect(() => {
        const session = $page.params.session, id = $page.params.report;
        let cancelled = false;
        apiJson(`/aac/sessions/${session}/reports/${id}`).then(value => { if (!cancelled) report = value; })
            .catch(e => { if (!cancelled) error = e.message; });
        return () => { cancelled = true; };
    });
    async function tests() {
        const result = await openReportTests(report);
        if (result.status !== 'opened') error = result.reason || 'Unable to open test results';
    }
</script>

<main class="mx-auto max-w-5xl p-6" data-aac-resource="legatus-report" data-aac-id={$page.params.report} data-aac-tab="view">
    {#if error}<p role="alert">{error}</p>{/if}
    {#if report}
        <h1 class="text-2xl font-semibold mb-3">{report.title}</h1>
        <p class="text-sm mb-4">{labels.calls}: {report.calls} · {labels.tools}: {report.tools}</p>
        <button class="border rounded px-3 py-2 mb-5" onclick={tests}>{labels.testResults}</button>
        <article class="prose max-w-none dark:prose-invert">{@html renderMarkdownWithMath(report.content)}</article>
    {/if}
</main>
