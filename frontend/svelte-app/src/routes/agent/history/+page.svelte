<script>
    import { onMount } from 'svelte';
    import { _ } from '$lib/i18n';
    import { getSessions, deleteSession } from '$lib/services/aacService';
    import { openTab } from '$lib/stores/aacStore.svelte';
    import { goto } from '$app/navigation';

    /** @type {Array<any>} */
    let sessions = $state([]);
    let loading = $state(true);
    let filter = $state('all');
    let skillFilter = $state('');
    let search = $state('');

    onMount(async () => {
        await loadSessions();
    });

    async function loadSessions() {
        loading = true;
        try {
            sessions = await getSessions();
        } catch (e) {
            sessions = [];
        }
        loading = false;
    }

    function filteredSessions() {
        let result = sessions;
        if (filter === 'today') {
            const today = new Date().toISOString().slice(0, 10);
            result = result.filter(s => (s.created_at || '').startsWith(today));
        } else if (filter === 'errors') {
            result = result.filter(s => (s.tool_errors || 0) > 0);
        } else if (filter === 'active') {
            result = result.filter(s => s.status === 'active');
        }
        if (skillFilter) {
            result = result.filter(s => s.skill_id === skillFilter);
        }
        if (search.trim()) {
            const q = search.toLowerCase();
            result = result.filter(s => (s.title || '').toLowerCase().includes(q));
        }
        return result;
    }

    function formatDate(iso) {
        if (!iso) return '-';
        const d = new Date(iso);
        const now = new Date();
        const today = now.toISOString().slice(0, 10);
        const dateStr = iso.slice(0, 10);
        const time = iso.slice(11, 16);
        if (dateStr === today) return `Today ${time}`;
        const yesterday = new Date(now - 86400000).toISOString().slice(0, 10);
        if (dateStr === yesterday) return `Yesterday ${time}`;
        return `${dateStr} ${time}`;
    }

    function skillIcon(skillId) {
        const icons = {
            'about-lamb': '🤖',
            'create-assistant': '➕',
            'improve-assistant': '✨',
            'explain-assistant': '🔍',
            'test-and-evaluate': '🧪',
            'test-lti-tools': '🔗',
        };
        return icons[skillId] || '💬';
    }

    async function resumeSession(s) {
        openTab(s.id, s.title || 'Session', s.assistant_id, s.skill_id);
        await goto(`/agent?session=${s.id}`);
    }

    async function removeSession(s) {
        const ok = confirm(`Delete session "${s.title || s.id.slice(0,8)}"?`);
        if (!ok) return;
        try {
            await deleteSession(s.id);
            await loadSessions();
        } catch (_) { /* ignore */ }
    }

    // Compute unique skills for filter dropdown
    function uniqueSkills() {
        const skills = new Set();
        for (const s of sessions) {
            if (s.skill_id) skills.add(s.skill_id);
        }
        return [...skills].sort();
    }
</script>

<div class="max-w-6xl mx-auto px-4 py-6">
    <div class="flex items-center justify-between mb-6">
        <h1 class="text-3xl font-bold text-brand">
            {$_('agent.history.title', { default: 'Agent Sessions' })}
        </h1>
        <a href="/agent" class="text-sm text-blue-600 hover:text-blue-800">
            &larr; {$_('agent.history.backToAgent', { default: 'Back to Agent' })}
        </a>
    </div>

    <!-- Filters -->
    <div class="flex flex-wrap gap-3 mb-4">
        <div class="flex rounded-md border border-gray-300 text-sm overflow-hidden">
            {#each [['all', 'All'], ['today', 'Today'], ['active', 'Active'], ['errors', 'Errors']] as [val, label]}
                <button
                    onclick={() => filter = val}
                    class="px-3 py-1.5 {filter === val ? 'bg-brand text-white' : 'bg-white text-gray-700 hover:bg-gray-50'}"
                >{label}</button>
            {/each}
        </div>
        <select
            bind:value={skillFilter}
            class="text-sm border border-gray-300 rounded-md px-2 py-1.5"
        >
            <option value="">All skills</option>
            {#each uniqueSkills() as sk}
                <option value={sk}>{sk}</option>
            {/each}
        </select>
        <input
            type="text"
            bind:value={search}
            placeholder="Search titles..."
            class="text-sm border border-gray-300 rounded-md px-3 py-1.5 w-48"
        >
    </div>

    <!-- Sessions table -->
    {#if loading}
        <div class="text-center py-12 text-gray-400">Loading sessions...</div>
    {:else}
        {@const filtered = filteredSessions()}
        <div class="text-sm text-gray-500 mb-2">{filtered.length} sessions</div>
        <div class="bg-white shadow rounded-lg border border-gray-200 overflow-hidden">
            <table class="w-full text-sm">
                <thead>
                    <tr class="border-b text-left text-xs text-gray-500 uppercase tracking-wider bg-gray-50">
                        <th class="px-4 py-3"></th>
                        <th class="px-4 py-3">Title</th>
                        <th class="px-4 py-3">Skill</th>
                        <th class="px-4 py-3 text-center">Turns</th>
                        <th class="px-4 py-3 text-center">Tools</th>
                        <th class="px-4 py-3 text-center">Errors</th>
                        <th class="px-4 py-3">Updated</th>
                        <th class="px-4 py-3">Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {#each filtered as s}
                        <tr class="border-b border-gray-100 hover:bg-gray-50">
                            <td class="px-4 py-3 text-lg">{skillIcon(s.skill_id)}</td>
                            <td class="px-4 py-3 font-medium text-gray-900">
                                <a href="/agent/history/{s.id}" class="hover:text-brand hover:underline">
                                    {s.title || s.id.slice(0, 8)}
                                </a>
                            </td>
                            <td class="px-4 py-3 text-gray-600">{s.skill_id || '-'}</td>
                            <td class="px-4 py-3 text-center text-gray-600">{s.turn_count || 0}</td>
                            <td class="px-4 py-3 text-center text-gray-600">{s.tool_calls || 0}</td>
                            <td class="px-4 py-3 text-center {(s.tool_errors || 0) > 0 ? 'text-red-600 font-semibold' : 'text-gray-400'}">{s.tool_errors || 0}</td>
                            <td class="px-4 py-3 text-gray-500 text-xs">{formatDate(s.updated_at)}</td>
                            <td class="px-4 py-3">
                                <div class="flex gap-2">
                                    {#if s.status === 'active'}
                                        <button onclick={() => resumeSession(s)} class="text-xs text-blue-600 hover:text-blue-800 font-medium">Resume</button>
                                    {/if}
                                    <a href="/agent/history/{s.id}" class="text-xs text-gray-600 hover:text-gray-800">Review</a>
                                    <button onclick={() => removeSession(s)} class="text-xs text-red-500 hover:text-red-700">Delete</button>
                                </div>
                            </td>
                        </tr>
                    {/each}
                    {#if filtered.length === 0}
                        <tr><td colspan="8" class="px-4 py-8 text-center text-gray-400 italic">No sessions match your filters.</td></tr>
                    {/if}
                </tbody>
            </table>
        </div>
    {/if}
</div>
