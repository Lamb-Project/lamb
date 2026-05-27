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
		// eslint-disable-next-line svelte/no-navigation-without-resolve
		goto(`${base}/libraries?section=knowledge-stores`, { replaceState: true });
	});
</script>

<div class="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
	<p class="type-body-muted">Redirecting...</p>
</div>
