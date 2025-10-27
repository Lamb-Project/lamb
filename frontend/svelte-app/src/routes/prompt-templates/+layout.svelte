<script>
	import '../../app.css';
	import Nav from '$lib/components/Nav.svelte';
	import Footer from '$lib/components/Footer.svelte';

	let { children } = $props();
</script>

<div class="min-h-screen bg-gray-50 flex flex-col">
	<Nav />
	
	<!-- WIDER MAIN CONTAINER FOR PROMPT TEMPLATES -->
	<main class="w-full mx-auto py-6 px-6 flex-grow">
		{@render children()}
	</main>

	<Footer />
</div>

