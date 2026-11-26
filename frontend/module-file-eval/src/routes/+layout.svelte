<script>
	import '../app.css';
	import { initI18n, _ } from '$lib/i18n.js';
	import { onMount } from 'svelte';

	onMount(() => {
		initI18n();
	});

	let { children } = $props();
</script>

<svelte:head>
	<title>{$_('fileEval.activityName')} | LAMB</title>
</svelte:head>

<div class="min-h-screen bg-gray-50 font-sans text-gray-900">
	{@render children()}
</div>
