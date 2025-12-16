<script>
	import '../app.css';
	import Nav from '$lib/components/Nav.svelte';
	import Footer from '$lib/components/Footer.svelte';
	import SessionExpiredModal from '$lib/components/modals/SessionExpiredModal.svelte';
	import { sessionExpired } from '$lib/stores/sessionStore';
	import { setupAxiosInterceptor } from '$lib/utils/axiosInterceptor';
	import { browser } from '$app/environment';
	import { onMount } from 'svelte';

	let { children } = $props();
	let showSessionModal = $state(false);

	// Setup axios interceptor on mount
	onMount(() => {
		if (browser) {
			setupAxiosInterceptor();
		}
	});

	// Subscribe to session expired store
	$effect(() => {
		const unsubscribe = sessionExpired.subscribe(value => {
			showSessionModal = value;
		});
		return unsubscribe;
	});
</script>

<div class="min-h-screen bg-gray-50 text-gray-900 flex flex-col">
	<Nav /> <!-- TODO: Restore on:help handler when Help System is migrated -->
	
	<main class="w-full mx-auto py-6 sm:px-6 lg:px-8 flex-grow">
		{@render children()}
	</main>

	<Footer />

	<!-- Session Expired Modal -->
	<SessionExpiredModal bind:isOpen={showSessionModal} />

	<!-- TODO: Add HelpModal when Help System is migrated -->
</div>
