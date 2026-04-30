<script>
    import { openTabs, activeTabId, setActiveTab, closeTab } from '$lib/stores/aacStore.svelte';
    import { deleteSession } from '$lib/services/aacService';
    import { goto } from '$app/navigation';
    import { page } from '$app/stores';
    import { _ } from '$lib/i18n';

    // Subscribe directly to the writable stores via the `$` auto-subscription.
    // Previously this component polled getOpenTabs() every 500ms because cross-
    // module $state reactivity didn't propagate in built mode — fixed at the
    // store level by switching to writable() (#352, H6).

    const skillIcons = {
        'about-lamb': '🤖',
        'create-assistant': '➕',
        'improve-assistant': '✨',
        'explain-assistant': '🔍',
        'test-and-evaluate': '🧪',
        'test-lti-tools': '🔗',
    };

    function icon(skill) {
        return skillIcons[skill] || '💬';
    }

    async function switchToTab(id) {
        setActiveTab(id);
        if (!$page.url.pathname.startsWith('/agent') || $page.url.pathname.includes('/history')) {
            await goto(`/agent?session=${id}`);
        }
    }

    async function closeSessionTab(e, id) {
        e.stopPropagation();
        const wasActive = $activeTabId === id;
        try {
            await deleteSession(id);
        } catch (_) { /* might already be archived */ }
        closeTab(id);
        // No manual refresh needed — the store update propagates automatically.
        if (wasActive && $page.url.pathname.startsWith('/agent')) {
            const remaining = $openTabs;
            if (remaining.length > 0) {
                await goto(`/agent?session=${remaining[remaining.length - 1].id}`);
            } else {
                await goto('/agent/history');
            }
        }
    }
</script>

{#if $openTabs.length > 0}
    <div class="bg-white border-b border-gray-200 px-4 sm:px-6 lg:px-8">
        <div class="max-w-7xl mx-auto flex items-center gap-1 overflow-x-auto py-1">
            {#each $openTabs as tab}
                <button
                    onclick={() => switchToTab(tab.id)}
                    class="group flex items-center gap-1.5 px-3 py-1.5 rounded-t-md text-sm whitespace-nowrap
                           transition-colors border border-b-0
                           {$activeTabId === tab.id && !$page.url.pathname.includes('/history')
                             ? 'bg-blue-50 border-blue-300 text-blue-700 font-medium'
                             : 'border-transparent text-gray-500 hover:text-gray-700 hover:bg-gray-50'}"
                >
                    <span class="text-xs">{icon(tab.skill)}</span>
                    <span class="max-w-[150px] truncate">{tab.title || tab.id.slice(0, 8)}</span>
                    <span
                        role="button"
                        tabindex="0"
                        onclick={(e) => closeSessionTab(e, tab.id)}
                        onkeydown={(e) => { if (e.key === 'Enter') closeSessionTab(e, tab.id); }}
                        class="ml-1 text-gray-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity text-xs cursor-pointer"
                        title={$_('agent.tabs.close', { default: 'Close session' })}
                    >
                        ✕
                    </span>
                </button>
            {/each}
            <a
                href="/agent/history"
                class="flex items-center gap-1.5 px-3 py-1.5 rounded-t-md text-sm whitespace-nowrap
                       transition-colors border border-b-0
                       {$page.url.pathname.includes('/history')
                         ? 'bg-blue-50 border-blue-300 text-blue-700 font-medium'
                         : 'border-transparent text-gray-500 hover:text-gray-700 hover:bg-gray-50'}"
            >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
                </svg>
                <span>{$_('agent.history.title', { default: 'History' })}</span>
            </a>
        </div>
    </div>
{/if}
