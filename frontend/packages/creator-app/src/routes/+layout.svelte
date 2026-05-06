<script>
	import '../app.css';
	import { Nav, Footer, userStore as user, initI18n } from '@lamb/ui';
	import { browser } from '$app/environment';
	import { base } from '$app/paths';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { onDestroy, onMount } from 'svelte';
	import { startSessionPolling, stopSessionPolling } from '$lib/utils/sessionGuard';
	import GlobalAacTabBar from '$lib/components/aac/GlobalAacTabBar.svelte';
	import { replaceSessionWithToken } from '$lib/session/sessionManager';

	let { children } = $props();
	let sessionReady = $state(!browser || !new URL(window.location.href).searchParams.get('token'));
	let processingToken = $state(false);
	let processedToken = $state(/** @type {string | null} */ (null));
	let sessionError = $state(/** @type {string | null} */ (null));

	/** @param {URL} url */
	async function handleTokenLogin(url) {
		if (!browser) return;

		const token = url.searchParams.get('token');
		if (!token) {
			sessionError = null;
			if (!processingToken) sessionReady = true;
			return;
		}

		if (processingToken || processedToken === token) return;

		processingToken = true;
		sessionReady = false;
		sessionError = null;

		try {
			await replaceSessionWithToken(token);
			processedToken = token;
		} catch (error) {
			console.error('Error bootstrapping session from URL token:', error);
			sessionError = error instanceof Error ? error.message : 'Failed to start session';
		} finally {
			const cleanUrl = new URL(window.location.href);
			cleanUrl.searchParams.delete('token');
			window.history.replaceState({}, '', cleanUrl.toString());
			processingToken = false;
			sessionReady = true;
		}
	}

	onMount(() => {
		initI18n();

		if (browser) {
			const unsubscribe = page.subscribe(($page) => {
				void handleTokenLogin($page.url);
			});
			return unsubscribe;
		}
	});

	$effect(() => {
		if (browser && sessionReady && !sessionError && !$user.isLoggedIn) {
			const currentPath = $page.url.pathname.replace(base, '') || '/';
			if (currentPath !== '/') {
				goto(`${base}/`, { replaceState: true });
			}
		}
	});

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
	<GlobalAacTabBar />

	<main class="w-full mx-auto py-6 sm:px-6 lg:px-8 flex-grow">
		{#if sessionError}
			<div class="max-w-md mx-auto mt-12 bg-red-50 border border-red-200 rounded-lg p-6 text-center">
				<h2 class="text-lg font-semibold text-red-800">Unable to start session</h2>
				<p class="text-sm text-red-600 mt-2">{sessionError}</p>
				<a href="{base}/" class="mt-4 inline-block text-sm font-medium text-blue-600 hover:underline">
					Return to login
				</a>
			</div>
		{:else if sessionReady}
			{@render children()}
		{/if}
	</main>

	<Footer />
</div>
