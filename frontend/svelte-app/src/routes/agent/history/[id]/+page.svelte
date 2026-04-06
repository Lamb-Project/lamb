<script>
    import { onMount } from 'svelte';
    import { page } from '$app/stores';
    import { _ } from '$lib/i18n';
    import { getSession } from '$lib/services/aacService';
    import { openTab } from '$lib/stores/aacStore.svelte';
    import { goto } from '$app/navigation';
    import { marked } from 'marked';

    let session = $state(/** @type {any} */ (null));
    let loading = $state(true);
    let error = $state('');
    let showAudit = $state(false);

    function renderMarkdown(text) {
        if (!text) return '';
        return marked.parse(text, { breaks: true });
    }

    onMount(async () => {
        const id = $page.params.id;
        try {
            session = await getSession(id);
        } catch (e) {
            error = e.message || 'Session not found';
        }
        loading = false;
    });

    function getVisibleMessages() {
        if (!session) return [];
        return (session.conversation || []).filter(
            m => (m.role === 'user' && !(m.content || '').startsWith('[System:'))
              || (m.role === 'assistant' && m.content && !m.tool_calls)
        );
    }

    function formatDate(iso) {
        if (!iso) return '-';
        return `${iso.slice(0, 10)} ${iso.slice(11, 16)}`;
    }

    async function resumeSession() {
        if (!session) return;
        openTab(session.id, session.title || 'Session', session.assistant_id, session.skill_info?.skill_id);
        await goto(`/agent?session=${session.id}`);
    }
</script>

<div class="max-w-4xl mx-auto px-4 py-6">
    <div class="flex items-center justify-between mb-6">
        <a href="/agent/history" class="text-sm text-blue-600 hover:text-blue-800">
            &larr; {$_('agent.history.backToHistory', { default: 'Back to sessions' })}
        </a>
    </div>

    {#if loading}
        <div class="text-center py-12 text-gray-400">Loading...</div>
    {:else if error}
        <div class="bg-red-50 border border-red-200 text-red-700 px-6 py-4 rounded-xl">
            <p class="font-medium">{error}</p>
        </div>
    {:else if session}
        <!-- Header -->
        <div class="bg-white shadow rounded-lg border border-gray-200 p-6 mb-6">
            <div class="flex items-start justify-between">
                <div>
                    <h1 class="text-2xl font-bold text-gray-900 mb-1">{session.title || session.id.slice(0, 12)}</h1>
                    <div class="flex flex-wrap gap-4 text-sm text-gray-500">
                        <span>Status: <strong class="{session.status === 'active' ? 'text-green-600' : 'text-gray-400'}">{session.status}</strong></span>
                        <span>Created: {formatDate(session.created_at)}</span>
                        <span>Updated: {formatDate(session.updated_at)}</span>
                        {#if session.assistant_id}
                            <span>Assistant: #{session.assistant_id}</span>
                        {/if}
                    </div>
                </div>
                {#if session.status === 'active'}
                    <button
                        onclick={resumeSession}
                        class="px-4 py-2 bg-brand text-white rounded-lg hover:bg-brand/90 text-sm font-medium"
                    >Resume</button>
                {/if}
            </div>
        </div>

        <!-- Stats -->
        {#if session.tool_audit?.length}
            <div class="bg-white shadow rounded-lg border border-gray-200 mb-6">
                <button
                    onclick={() => showAudit = !showAudit}
                    class="w-full px-6 py-3 flex items-center justify-between text-sm font-medium text-gray-700 hover:bg-gray-50"
                >
                    <span>Tool Audit ({session.tool_audit.length} calls, {session.tool_audit.filter(e => !e.success).length} errors)</span>
                    <span>{showAudit ? '▴' : '▾'}</span>
                </button>
                {#if showAudit}
                    <div class="px-6 pb-4 border-t border-gray-100">
                        <table class="w-full text-xs mt-2">
                            <thead>
                                <tr class="text-left text-gray-500">
                                    <th class="pr-3 py-1">Time</th>
                                    <th class="pr-3 py-1">Status</th>
                                    <th class="pr-3 py-1">Duration</th>
                                    <th class="py-1">Command</th>
                                </tr>
                            </thead>
                            <tbody>
                                {#each session.tool_audit as e}
                                    <tr class="border-t border-gray-50">
                                        <td class="pr-3 py-1 text-gray-400 font-mono">{(e.ts || '').slice(11, 19)}</td>
                                        <td class="pr-3 py-1 {e.success ? 'text-green-600' : 'text-red-600'}">{e.success ? 'ok' : 'FAIL'}</td>
                                        <td class="pr-3 py-1 text-gray-500">{Math.round(e.elapsed_ms || 0)}ms</td>
                                        <td class="py-1 font-mono text-gray-700">{e.command || '?'}</td>
                                    </tr>
                                {/each}
                            </tbody>
                        </table>
                    </div>
                {/if}
            </div>
        {/if}

        <!-- Conversation transcript -->
        <div class="bg-white shadow rounded-lg border border-gray-200 overflow-hidden">
            <div class="px-6 py-3 border-b border-gray-200 bg-gray-50">
                <h2 class="text-sm font-semibold text-gray-700">Conversation</h2>
            </div>
            <div class="px-6 py-4 space-y-4">
                {#each getVisibleMessages() as msg}
                    {#if msg.role === 'user'}
                        <div class="my-3">
                            <hr class="border-t-2 border-blue-300">
                            <div class="flex gap-2 py-2.5 px-2 rounded bg-blue-50">
                                <span class="shrink-0 font-bold text-blue-600">$</span>
                                <span class="font-semibold text-gray-800">{msg.content}</span>
                            </div>
                            <hr class="border-t-2 border-blue-300">
                        </div>
                    {:else if msg.role === 'assistant'}
                        <div class="pl-2 leading-relaxed text-sm text-gray-700 prose prose-sm max-w-none">
                            {@html renderMarkdown(msg.content)}
                        </div>
                    {/if}
                {/each}
                {#if getVisibleMessages().length === 0}
                    <p class="text-gray-400 italic py-4 text-center">No messages in this session.</p>
                {/if}
            </div>
        </div>
    {/if}
</div>
