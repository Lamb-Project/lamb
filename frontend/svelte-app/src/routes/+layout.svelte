<script>
	import '../app.css';
	import Nav from '$lib/components/Nav.svelte';
	import Footer from '$lib/components/Footer.svelte';
	import { browser } from '$app/environment';
	import { base } from '$app/paths';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { user } from '$lib/stores/userStore';
	import { onDestroy } from 'svelte';
	import { startSessionPolling, stopSessionPolling } from '$lib/utils/sessionGuard';

	let { children } = $props();

	// Layout-level auth guard: redirect unauthenticated users to root (login page)
	// The root path '/' is the only public route — it shows Login/Signup when not logged in.
	$effect(() => {
		if (browser && !$user.isLoggedIn) {
			const currentPath = $page.url.pathname.replace(base, '') || '/';
			if (currentPath !== '/') {
				goto(`${base}/`, { replaceState: true });
			}
		}
	});

	// Session guard: periodically check if the account has been disabled mid-session.
	// When logged in, polls the backend every 60 seconds; forces logout on 403 "Account disabled".
	$effect(() => {
		if (browser && $user.isLoggedIn) {
			startSessionPolling(60000);
		} else {
			stopSessionPolling();
		}
	});

	onDestroy(() => {
		stopSessionPolling();
	});
</script>

<div class="min-h-screen bg-gray-50 text-gray-900 flex flex-col">
	<Nav />
	
	<main class="w-full mx-auto py-6 sm:px-6 lg:px-8 flex-grow">
		{@render children()}
	</main>

	<Footer />
</div>
