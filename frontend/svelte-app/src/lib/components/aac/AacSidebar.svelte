<script>
    import { onMount } from 'svelte';
    import { get } from 'svelte/store';
    import { user } from '$lib/stores/userStore';
    import { locale } from '$lib/i18n';
    import { sidebarOpen, sidebarBusy, activeTabId, startupSessions, showSession, resetSidebar } from '$lib/stores/aacStore.svelte';
    import { createSession, getSessions } from '$lib/services/aacService';
    import AacTerminal from './AacTerminal.svelte';
    let history = $state(false);
    let historyLoading = $state(false);
    let sessions = $state([]);
    let error = $state('');
    let creating = $state(false);
    let filter = $state('');
    let owner = null;
    onMount(() => {
        const unsubscribe = user.subscribe(value => {
            if (owner && owner !== value.token) resetSidebar();
            owner = value.token;
        });
        return unsubscribe;
    });
    async function newConversation() {
        if ($sidebarBusy || creating) return;
        creating = true; error = '';
        try {
            const language = { en: 'English', es: 'Spanish', ca: 'Catalan', eu: 'Basque' }[$locale] || 'English';
            const s = await createSession({ skill: 'about-lamb', context: { language } });
            showSession(s.id, s.title || 'LAMB Helper', null, 'about-lamb', true);
            history = false;
        } catch (e) { error = e.message; }
        finally { creating = false; }
    }
    async function showHistory() {
        history = true; error = ''; historyLoading = true;
        try { sessions = await getSessions(); }
        catch (e) { error = e.message; }
        finally { historyLoading = false; }
    }
    function resume(s) {
        if (showSession(s.id, s.title, s.assistant_id, s.skill_id)) history = false;
    }
</script>

{#if !$sidebarOpen}
<button class="aac-launch" onclick={() => sidebarOpen.set(true)} aria-label="Open AAC">✦ AAC</button>
{/if}
<aside class="aac-sidebar" class:hidden={!$sidebarOpen} aria-label="AAC assistant">
    <header>
        <strong>✦ AAC</strong>
        <button onclick={newConversation} disabled={$sidebarBusy || creating}>New conversation</button>
        <button onclick={showHistory} disabled={$sidebarBusy || creating}>History</button>
        <button onclick={() => sidebarOpen.set(false)} aria-label="Hide AAC">✕</button>
    </header>
    {#if error}<p role="alert" class="error">{error}</p>{/if}
    {#if history}
    <section class="history">
        <div class="history-heading"><h2>Conversation history</h2><button onclick={() => history = false}>Back</button></div>
        <input aria-label="Search conversations" placeholder="Search conversations" bind:value={filter} />
        {#if historyLoading}<p role="status">Loading conversations…</p>{/if}
        {#each sessions.filter(s => (s.title || '').toLowerCase().includes(filter.toLowerCase())) as s}
            <button class="history-item" onclick={() => resume(s)}><strong>{s.title || 'Conversation'}</strong><small>{s.updated_at?.slice(0, 16).replace('T', ' ')}</small></button>
        {/each}
        {#if !historyLoading && !sessions.length}<p>No saved conversations yet.</p>{/if}
    </section>
    {/if}
    <div class="terminal" class:hidden={history}>
        {#if $activeTabId}
            {#key $activeTabId}
                <AacTerminal sessionId={$activeTabId} resumed={!$startupSessions.has($activeTabId)} skillStartup={$startupSessions.has($activeTabId)} />
            {/key}
        {:else}
            <div class="welcome"><h2>Work with AAC</h2><p>Create, inspect and test assistants alongside your workspace.</p><button onclick={newConversation} disabled={creating}>Start a conversation</button><button onclick={showHistory}>Open history</button></div>
        {/if}
    </div>
</aside>
<style>
.aac-launch { position: fixed; right: 24px; bottom: 24px; z-index: 45; background: #173f64; color: white; border-radius: 28px; padding: 12px 22px; box-shadow: 0 4px 20px #173f6430; font-weight: 600; }
.aac-sidebar { position: fixed; right: 0; top: 0; bottom: 0; width: 440px; max-width: 100vw; z-index: 45; display: flex; flex-direction: column; background: white; border-left: 1px solid #d6e0ea; box-shadow: -8px 0 32px #173f6410; }
header { display: flex; align-items: center; gap: 12px; padding: 16px 12px; border-bottom: 1px solid #d6e0ea; color: #173f64; }
header strong { margin-right: auto; }
button { cursor: pointer; font-size: 13px; } button:disabled { opacity: .5; cursor: default; } button:focus-visible { outline: 2px solid #2271b3; outline-offset: 3px; }
.terminal { flex: 1; min-height: 0; overflow: hidden; } .hidden { display: none; }
.history { flex: 1; overflow: auto; padding: 18px; } .history-heading { display: flex; justify-content: space-between; margin-bottom: 16px; }
.history input { width: 100%; border: 1px solid #d6e0ea; border-radius: 8px; padding: 10px; }
.history-item { display: flex; flex-direction: column; text-align: left; gap: 6px; padding: 14px 8px; border-bottom: 1px solid #edf1f5; width: 100%; }
.history-item:hover { background: #f2f6fa; } small { color: #62758a; } .welcome { padding: 32px; display: grid; gap: 20px; } .welcome button { padding: 12px; border: 1px solid #d6e0ea; border-radius: 8px; } h2 { font-weight: 600; } .error { color: #a12727; padding: 12px; }
@media (max-width: 600px) { .aac-sidebar { width: 100%; } }
</style>
