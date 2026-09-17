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
            sidebarOpen.set(true);
            window.dispatchEvent(new CustomEvent('aac-new-conversation'));
        } else if (id) showSession(id);
        else sidebarOpen.set(true);
        goto(`${base}/assistants`, { replaceState: true });
    });
</script>
<p>Opening AAC alongside your workspace…</p>
