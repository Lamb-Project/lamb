<script>
    import DOMPurify from 'dompurify';
    import { locale } from 'svelte-i18n';
    import { apiJson } from '$lib/services/apiClient';
    import { getChatDetail } from '$lib/services/analyticsService';
    import { renderMarkdownWithMath } from '$lib/utils/renderMarkdown.js';
    import { analysisText } from '$lib/utils/activityAnalysisText';
    import AacSkillButton from '$lib/components/aac/AacSkillButton.svelte';

    /** @type {{assistantId: number, reportId?: string}} */
    let { assistantId, reportId = '' } = $props();
    const labels = $derived(analysisText($locale));
    /** @type {any[]} */ let reports = $state([]);
    /** @type {any} */ let selected = $state(null);
    /** @type {any} */ let evidence = $state(null);
    let loading = $state(false);
    let error = $state('');
    let request = 0;
    let evidenceRequest = 0;
    const endpoint = $derived(`/analytics/assistant/${assistantId}/analysis-reports`);
    /** @param {number} value */
    function date(value) { return new Date(value * 1000).toLocaleString($locale || 'en'); }
    /** @param {any} value */
    function range(value) { return value?.start || value?.end ? `${value.start || '…'} → ${value.end || '…'}` : labels.allDates; }
    async function refresh() {
        const ticket = ++request;
        loading = true; error = ''; selected = null; evidence = null; ++evidenceRequest;
        try {
            const items = await apiJson(endpoint);
            if (ticket !== request) return;
            reports = items;
            const id = reportId || items[0]?.id;
            if (id) await select(id);
        } catch (e) { if (ticket === request) error = e instanceof Error ? e.message : String(e); }
        finally { if (ticket === request) loading = false; }
    }
    /** @param {string} id */
    async function select(id) {
        const ticket = ++request;
        error = ''; selected = null; evidence = null; ++evidenceRequest; loading = true;
        try {
            const item = await apiJson(`${endpoint}/${encodeURIComponent(id)}`);
            if (ticket === request) selected = item;
        } catch (e) { if (ticket === request) error = e instanceof Error ? e.message : String(e); }
        finally { if (ticket === request) loading = false; }
    }
    /** @param {string} id */
    async function openEvidence(id) {
        const ticket = ++evidenceRequest;
        evidence = null; error = '';
        try {
            const item = await getChatDetail(assistantId, id);
            if (ticket === evidenceRequest) evidence = item;
        } catch (e) { if (ticket === evidenceRequest) error = e instanceof Error ? e.message : String(e); }
    }
    /** @param {string} text */
    function render(text) { return DOMPurify.sanitize(renderMarkdownWithMath(text), {FORBID_TAGS: ['img', 'iframe', 'video', 'audio', 'source']}); }
    $effect(() => { assistantId; reportId; refresh(); });
</script>

<section class="analysis">
    <header><h2>{labels.title}</h2><div class="actions">
        <AacSkillButton skill="inspect-activity" {assistantId} label={labels.newAnalysis} context={{analysis_scope: 'propose'}} />
        <AacSkillButton skill="inspect-activity" {assistantId} label={labels.fullAudit} context={{analysis_scope: 'full'}} />
        <button onclick={refresh} disabled={loading}>{labels.refresh}</button>
    </div></header>
    <p class="nudge">{labels.nudge}</p>
    {#if error}<p role="alert">{error}</p>{/if}
    {#if loading}<p role="status">{labels.loading}</p>{/if}
    <div class="layout">
        <nav aria-label={labels.title}>
            {#each reports as report}
                <button class:active={selected?.id === report.id} onclick={() => select(report.id)}>
                    <strong>{report.title}</strong><time>{date(report.created_at)}</time><small>{range(report.period)}</small>
                </button>
            {:else}<p>{labels.empty}</p>{/each}
        </nav>
        {#if selected}
            <article>
                <h3>{selected.title}</h3><time>{date(selected.created_at)}</time>
                <p><strong>{labels.period}:</strong> {range(selected.period)}</p>
                <p>{selected.dimensions.map(/** @param {string} d */ d => labels[d] || d).join(' · ')}</p>
                <details><summary>{labels.scenario}: {selected.scenario?.title || labels.general}</summary>
                    {#if selected.scenario}<p class="scenario">{selected.scenario.content}</p><small>Revision {selected.scenario.revision}</small>{/if}
                </details>
                <div class="coverage"><h4>{labels.coverage}</h4>
                    <p>{labels.total}: {selected.coverage.total_conversations} · {labels.provided}: {selected.coverage.provided_conversations} · {labels.reviewed}: {selected.reviewed_chat_ids.length}</p>
                    <p>{selected.coverage.exhaustive ? labels.exhaustive : labels.sample}</p>
                    <p>{Object.entries(selected.coverage.source_status || {}).map(([source, status]) => `${labels[source] || source}: ${labels[String(status)] || status}`).join(' · ')}</p>
                    <p>{Object.entries(selected.coverage.provided_by_source).map(([source, count]) => `${labels[source] || source}: ${count}`).join(' · ')}</p>
                    <table><thead><tr><th></th><th>{labels.median}</th></tr></thead><tbody>
                        {#each [['messages_per_conversation', labels.messages], ['user_prompt_characters', labels.userLength], ['assistant_response_characters', labels.responseLength]] as [key, label]}
                            <tr><td>{label}</td><td>{selected.metrics[key].median ?? '…'}</td></tr>
                        {/each}
                    </tbody></table>
                </div>
                <div class="prose max-w-none">{@html render(selected.content)}</div>
                <details><summary>{labels.limitations}</summary><ul>{#each selected.limitations as limitation}<li>{limitation}</li>{/each}</ul></details>
                <h4>{labels.evidence}</h4><div class="actions">{#each selected.evidence as ref}<button onclick={() => openEvidence(ref.chat_id)}>{ref.label}</button>{/each}</div>
                {#if evidence}<section class="evidence"><button onclick={() => { evidence = null; ++evidenceRequest; }}>{labels.close}</button>
                    {#each evidence.messages as message}<div><strong>{message.role}</strong><div class="prose max-w-none">{@html render(message.content)}</div></div>{/each}
                </section>{/if}
            </article>
        {/if}
    </div>
</section>

<style>
    .analysis { padding: 1.25rem; color: #1e293b; }
    header, .actions { display: flex; flex-wrap: wrap; align-items: center; gap: .6rem; }
    header { justify-content: space-between; } h2 { font-size: 1.25rem; font-weight: 650; } h3 { font-size: 1.2rem; font-weight: 650; } h4 { font-weight: 650; margin: .8rem 0; }
    .nudge, .coverage { padding: .8rem; background: #f1f5f9; border-radius: .5rem; margin: 1rem 0; }
    .layout { display: grid; grid-template-columns: minmax(12rem, 17rem) minmax(0, 1fr); gap: 1.25rem; }
    nav { border-right: 1px solid #cbd5e1; padding-right: .8rem; max-height: 65vh; overflow: auto; }
    nav button { display: flex; flex-direction: column; text-align: left; width: 100%; margin-bottom: .5rem; overflow-wrap: anywhere; }
    button { border: 1px solid #cbd5e1; padding: .5rem .65rem; border-radius: .4rem; background: white; }
    button:hover, button.active { background: #eff6ff; border-color: #2563eb; } time, small { font-size: .8rem; color: #475569; }
    article { min-width: 0; overflow-wrap: anywhere; } summary { cursor: pointer; } details, article p { margin: .65rem 0; } .scenario { white-space: pre-wrap; }
    table { width: 100%; text-align: left; } td, th { padding: .25rem; } [role='alert'] { color: #b91c1c; }
    .evidence { margin-top: .8rem; padding: 1rem; border: 1px solid #94a3b8; border-radius: .5rem; } .evidence > div { margin: .8rem 0; }
    @media (max-width: 700px) { .layout { grid-template-columns: 1fr; } nav { border-right: 0; border-bottom: 1px solid #cbd5e1; max-height: 14rem; } }
</style>
