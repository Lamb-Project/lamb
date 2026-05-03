<!--
  @component Knowledge Stores redirect
  Secondary direct-URL entry point. Redirects power-users typing the
  /knowledge-stores route by hand to the unified Knowledge page with
  the Knowledge Stores sub-tab pre-selected.
-->
<script>
    import { onMount } from 'svelte';
    import { goto } from '$app/navigation';
    import { base } from '$app/paths';

    onMount(() => {
        goto(`${base}/libraries?section=knowledge-stores`, { replaceState: true });
    });
</script>

<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
    <p class="text-sm text-gray-500">Redirecting...</p>
</div>
