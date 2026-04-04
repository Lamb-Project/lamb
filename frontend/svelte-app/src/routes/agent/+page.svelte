<script>
    import { onMount } from 'svelte';
    import { page } from '$app/stores';
    import { _, locale } from '$lib/i18n';
    import { user } from '$lib/stores/userStore';
    import { createSession, getSessions } from '$lib/services/aacService';
    import { openTab, setActiveTab, getActiveTabId } from '$lib/stores/aacStore.svelte';
    import AacTerminal from '$lib/components/aac/AacTerminal.svelte';

    let sessionId = $state(/** @type {string|null} */ (null));
    let loading = $state(true);
    let error = $state('');

    const localeToLanguage = { en: 'English', es: 'Spanish', ca: 'Catalan', eu: 'Basque' };

    onMount(async () => {
        // Check URL for a session ID
        const urlSession = $page.url.searchParams.get('session');
        if (urlSession) {
            sessionId = urlSession;
            setActiveTab(sessionId);
            loading = false;
            return;
        }

        // Check for an existing active about-lamb session from today
        try {
            const sessions = await getSessions();
            const today = new Date().toISOString().slice(0, 10);
            const active = sessions.find(
                (s) => s.status === 'active' && s.title === 'LAMB Helper' && s.created_at?.startsWith(today)
            );
            if (active) {
                sessionId = active.id;
                openTab(sessionId, active.title || 'LAMB Helper', null, 'about-lamb');
                loading = false;
                return;
            }
        } catch (_) { /* no existing session */ }

        // Create a new session
        try {
            const session = await createSession({
                assistantId: null,
                skill: 'about-lamb',
                context: { language: localeToLanguage[$locale] || 'English' },
            });
            sessionId = session.id;
            openTab(sessionId, session.title || 'LAMB Helper', null, 'about-lamb');
        } catch (e) {
            error = e.message || 'Failed to start agent session';
        }
        loading = false;
    });
</script>

<div class="max-w-5xl mx-auto px-4 py-6">
    <h1 class="text-3xl font-bold text-brand mb-6">
        🤖 {$_('home.dashboard.agent.title', { default: 'LAMB Agent' })}
    </h1>

    {#if loading}
        <div class="bg-white shadow rounded-lg border border-gray-200 p-12 text-center">
            <div class="animate-spin text-3xl mb-3">⏳</div>
            <p class="text-gray-500">{$_('home.dashboard.agent.starting', { default: 'Starting...' })}</p>
        </div>
    {:else if error}
        <div class="bg-red-50 border border-red-200 text-red-700 px-6 py-4 rounded-xl">
            <p class="font-medium">{error}</p>
        </div>
    {:else if sessionId}
        <div class="bg-white shadow rounded-lg border border-gray-200 overflow-hidden">
            {#key sessionId}
            <div class="h-[700px]">
                <AacTerminal
                    {sessionId}
                    firstMessage=""
                    resumed={true}
                    skillStartup={true}
                />
            </div>
            {/key}
        </div>
    {/if}
</div>
