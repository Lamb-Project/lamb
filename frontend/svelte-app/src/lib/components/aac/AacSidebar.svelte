<script>
    import { onMount, tick } from 'svelte';
    import { get } from 'svelte/store';
    import { user } from '$lib/stores/userStore';
    import { locale } from '$lib/i18n';
    import { sidebarOpen, sidebarWidth, sidebarMobile, frontendDestination, sidebarBusy, activeTabId, startupSessions, showSession, resetSidebar } from '$lib/stores/aacStore.svelte';
    import { createSession, getSessions } from '$lib/services/aacService';
    import { sidebarSize } from '$lib/utils/aacLayout';
    import AacTerminal from './AacTerminal.svelte';
    let history = $state(false);
    let historyLoading = $state(false);
    let sessions = $state([]);
    let error = $state('');
    let creating = $state(false);
    let filter = $state('');
    let owner = null;
    let panel; let backButton;
    let ratio = $state(.35); let viewport = $state(1500);
    let limits = $derived(sidebarSize(viewport, ratio));
    let dragging = $state(false);
    let opener;
    function resize() {
        viewport = window.innerWidth;
        const size = sidebarSize(viewport, ratio);
        sidebarWidth.set(size.width); sidebarMobile.set(size.mobile);
        const visual = window.visualViewport;
        panel?.style.setProperty('--aac-height', (visual?.height || window.innerHeight) + 'px');
        panel?.style.setProperty('--aac-top', (visual?.offsetTop || 0) + 'px');
    }
    function setWidth(width) {
        const size = sidebarSize(viewport, width / viewport);
        ratio = size.width / viewport;
        sidebarWidth.set(size.width);
        try { localStorage.setItem('lamb-agent-width-ratio', String(ratio)); } catch (_) {}
    }
    function startDrag(event) {
        if (event.button !== 0) return;
        event.preventDefault(); dragging = true;
        event.currentTarget.setPointerCapture(event.pointerId);
    }
    function moveDrag(event) { if (dragging) setWidth(viewport - event.clientX); }
    function endDrag() { dragging = false; }
    function resizeKeys(event) {
        const steps = {ArrowLeft: 24, ArrowRight: -24};
        if (event.key in steps) { event.preventDefault(); setWidth($sidebarWidth + steps[event.key]); }
        else if (event.key === 'Home' || event.key === 'End') { event.preventDefault(); setWidth(event.key === 'Home' ? limits.min : limits.max); }
    }
    function hide() {
        sidebarOpen.set(false);
        void tick().then(() => {
            const target = opener?.isConnected && opener !== document.body && !panel?.contains(opener) ? opener : document.querySelector('[aria-label="Open LAMB AGENT"]');
            target?.focus();
        });
    }
    function panelKeys(event) {
        if (panel?.querySelector('dialog[open]')) return;
        if (event.key === 'Escape') { event.preventDefault(); hide(); }
        if (!$sidebarMobile || event.key !== 'Tab') return;
        const nodes = [...panel.querySelectorAll('button:not(:disabled), input:not(:disabled), textarea:not(:disabled), a[href], [tabindex="0"]')].filter(el => el.getClientRects().length);
        const first = nodes[0], last = nodes.at(-1);
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    }
    $effect(() => {
        if (!$sidebarOpen || !$sidebarMobile) return;
        opener = document.activeElement;
        const overflow = document.body.style.overflow;
        document.body.style.overflow = 'hidden';
        void tick().then(() => { if ($sidebarOpen && $sidebarMobile) backButton?.focus(); });
        return () => { document.body.style.overflow = overflow; if (opener?.isConnected) opener.focus(); };
    });
    onMount(() => {
        try { const saved = Number(localStorage.getItem('lamb-agent-width-ratio')); if (saved >= .25 && saved <= .55) ratio = saved; } catch (_) {}
        resize(); window.addEventListener('resize', resize);
        window.visualViewport?.addEventListener('resize', resize);
        window.visualViewport?.addEventListener('scroll', resize);
        const unsubscribe = user.subscribe(value => {
            if (owner && owner !== value.token) resetSidebar();
            owner = value.token;
        });
        return () => { unsubscribe(); window.removeEventListener('resize', resize); window.visualViewport?.removeEventListener('resize', resize); window.visualViewport?.removeEventListener('scroll', resize); };
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
<button class="aac-launch" onclick={() => sidebarOpen.set(true)} aria-label="Open LAMB AGENT">LAMB AGENT</button>
{/if}
<!-- svelte-ignore a11y_no_noninteractive_element_interactions (Panel-level Escape and mobile focus containment) -->
<aside bind:this={panel} class="aac-sidebar" class:hidden={!$sidebarOpen} style:width={$sidebarWidth + 'px'} aria-label="LAMB AGENT" onkeydown={panelKeys}>
    {#if !$sidebarMobile}
    <!-- svelte-ignore a11y_no_noninteractive_tabindex a11y_no_noninteractive_element_interactions (An adjustable ARIA separator is keyboard operable) -->
    <div class="divider" class:dragging role="separator" aria-label="Resize LAMB AGENT" aria-orientation="vertical" aria-valuemin={Math.round(limits.min)} aria-valuemax={Math.round(limits.max)} aria-valuenow={Math.round($sidebarWidth)} tabindex="0" onpointerdown={startDrag} onpointermove={moveDrag} onpointerup={endDrag} onlostpointercapture={endDrag} onkeydown={resizeKeys}></div>
    {/if}
    <header>
        <strong>LAMB AGENT</strong>
        <button onclick={newConversation} disabled={$sidebarBusy || creating}>New conversation</button>
        <button onclick={showHistory} disabled={$sidebarBusy || creating}>History</button>
        <button bind:this={backButton} onclick={hide} aria-label={$sidebarMobile ? "Back to LAMB" : "Hide LAMB AGENT"}>{$sidebarMobile ? "Back to LAMB" : "✕"}</button>
    </header>
    {#if $sidebarMobile && $frontendDestination}
    <button class="destination" onclick={hide}>Open in LAMB: {$frontendDestination.resource} {$frontendDestination.id} {$frontendDestination.tab}</button>
    {/if}
    {#if error}<p role="alert" class="error">{error}</p>{/if}
    {#if history}
    <section class="history">
        <div class="history-heading"><h2>Conversation history</h2><button onclick={() => history = false}>Back</button></div>
        <input aria-label="Search conversations" placeholder="Search conversations" bind:value={filter} />
        {#if historyLoading}<p role="status">Loading conversations…</p>{/if}
        {#each sessions.filter(s => `${s.title || ''} ${s.summary || ''}`.toLowerCase().includes(filter.toLowerCase())) as s}
            <button class="history-item" onclick={() => resume(s)}><strong>{s.title || 'Conversation'}</strong>{#if s.summary}<span class="summary">{s.summary}</span>{/if}<small>{s.updated_at?.slice(0, 16).replace('T', ' ')}</small></button>
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
            <div class="welcome"><h2>Work with LAMB AGENT</h2><p>Create, inspect and test assistants alongside your workspace.</p><button onclick={newConversation} disabled={creating}>Start a conversation</button><button onclick={showHistory}>Open history</button></div>
        {/if}
    </div>
</aside>
<style>
.aac-launch { position: fixed; right: 24px; bottom: 24px; z-index: 45; background: #173f64; color: white; border-radius: 28px; padding: 12px 22px; box-shadow: 0 4px 20px #173f6430; font-weight: 600; }
.aac-sidebar { position: fixed; right: 0; top: var(--aac-top, 0px); height: var(--aac-height, 100dvh); width: 440px; max-width: 100vw; z-index: 45; display: flex; flex-direction: column; background: white; border-left: 1px solid #d6e0ea; box-shadow: -8px 0 32px #173f6410; }
header { flex-wrap: wrap; flex-shrink: 0; display: flex; align-items: center; gap: 12px; padding: 16px 12px; border-bottom: 1px solid #d6e0ea; color: #173f64; }
header strong { margin-right: auto; font-size: 13px; white-space: nowrap; }
.summary { font-size: 12px; line-height: 1.5; color: #475569; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
button { cursor: pointer; font-size: 13px; } button:disabled { opacity: .5; cursor: default; } button:focus-visible { outline: 2px solid #2271b3; outline-offset: 3px; }
.terminal { flex: 1; min-height: 0; overflow: hidden; } .hidden { display: none; }
.history { flex: 1; overflow: auto; padding: 18px; } .history-heading { display: flex; justify-content: space-between; margin-bottom: 16px; }
.history input { width: 100%; border: 1px solid #d6e0ea; border-radius: 8px; padding: 10px; }
.history-item { display: flex; flex-direction: column; text-align: left; gap: 6px; padding: 14px 8px; border-bottom: 1px solid #edf1f5; width: 100%; }
.history-item:hover { background: #f2f6fa; } small { color: #62758a; } .welcome { padding: 32px; display: grid; gap: 20px; } .welcome button { padding: 12px; border: 1px solid #d6e0ea; border-radius: 8px; } h2 { font-weight: 600; } .error { color: #a12727; padding: 12px; }
.divider { position: absolute; left: -6px; top: 0; bottom: 0; width: 12px; cursor: col-resize; touch-action: none; z-index: 2; }
.divider::after { content: ''; position: absolute; left: 5px; top: 0; bottom: 0; width: 2px; background: #94a3b8; }
.divider:hover::after, .divider.dragging::after, .divider:focus-visible::after { background: #2271b3; width: 4px; }
.divider:focus-visible { outline: 2px solid #2271b3; }
.destination { padding: 10px; background: #e8f2fc; color: #173f64; border-bottom: 1px solid #cad8e5; }
@media (max-width: 919px) { .aac-sidebar { width: 100%; padding-bottom: env(safe-area-inset-bottom); } header strong { flex: 1 0 100%; } .aac-launch { bottom: max(20px, env(safe-area-inset-bottom)); } }
</style>
