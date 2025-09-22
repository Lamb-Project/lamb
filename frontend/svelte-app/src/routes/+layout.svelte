<script>
	import '../app.css';
	import Nav from '$lib/components/Nav.svelte';

	let { children } = $props();
</script>

<div class="min-h-screen bg-gray-50">
	<Nav />
	<!-- TODO: Restore on:help handler when Help System is migrated -->

	<main class="mx-auto max-w-7xl py-6 sm:px-6 lg:px-8">
		{@render children()}
	</main>

	<!-- TODO: Add HelpModal when Help System is migrated -->
</div>
