<script>
	import '../app.css';
	import Nav from '$lib/components/Nav.svelte';
	import Footer from '$lib/components/Footer.svelte';

	let { children } = $props();
</script>

<div class="min-h-screen bg-gray-50 text-gray-900 flex flex-col">
	<Nav />
	
	<main class="w-full mx-auto py-6 sm:px-6 lg:px-8 flex-grow">
		{@render children()}
	</main>

	<Footer />
</div>
