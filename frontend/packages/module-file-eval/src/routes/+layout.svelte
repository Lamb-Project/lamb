<script>
	import '../app.css';
	import { initI18n } from '@lamb/ui';
	import { onMount } from 'svelte';

	onMount(() => {
		initI18n();
	});

	let { children } = $props();
</script>

<div class="min-h-screen bg-gray-50 font-sans text-gray-900">
	{@render children()}
</div>
