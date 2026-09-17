<script>
    import { onMount } from 'svelte';
    import { page } from '$app/stores';
    import { goto } from '$app/navigation';
    import { base } from '$app/paths';
    import { sidebarOpen, sidebarBusy, showSession } from '$lib/stores/aacStore.svelte';
    import { createSession } from '$lib/services/aacService';
    import { locale } from '$lib/i18n';
    onMount(async () => {
        const id = $page.url.searchParams.get('session');
        if ($page.url.searchParams.get('new') === 'true' && !$sidebarBusy) {
            const language = { en: 'English', es: 'Spanish', ca: 'Catalan', eu: 'Basque' }[$locale] || 'English';
            const s = await createSession({ context: { language } });
            showSession(s.id, s.title, null, null, false);
        } else if (id) showSession(id);
        else sidebarOpen.set(true);
        goto(`${base}/assistants`, { replaceState: true });
    });
</script>
<p>Opening AAC alongside your workspace…</p>
