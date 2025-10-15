<script>
	import '../app.css';
	import Nav from '$lib/components/Nav.svelte';
	import Footer from '$lib/components/Footer.svelte';

	let { children } = $props();
</script>

<div class="min-h-screen bg-gray-50 flex flex-col">
	<Nav /> <!-- TODO: Restore on:help handler when Help System is migrated -->
	
	<main class="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8 flex-grow">
		{@render children()}
	</main>

	<Footer />

	<!-- TODO: Add HelpModal when Help System is migrated -->
</div>
