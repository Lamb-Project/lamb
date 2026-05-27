<script>
	import '../app.css';
	import { browser } from '$app/environment';
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { base } from '$app/paths';
	import Nav from '$lib/components/Nav.svelte';
	import Footer from '$lib/components/Footer.svelte';
	import GlobalAacTabBar from '$lib/components/aac/GlobalAacTabBar.svelte';
	import Toast from '$lib/components/ui/Toast.svelte';
	import { replaceSessionWithToken } from '$lib/session/sessionManager';

	let { children } = $props();
	let sessionReady = $state(!$page.url.searchParams.get('token'));
	let processingToken = $state(false);
	let processedToken = $state(/** @type {string | null} */ (null));
	let sessionError = $state(/** @type {string | null} */ (null));

	/** @param {URL} url */
	async function handleTokenLogin(url) {
		if (!browser) return;

		const token = url.searchParams.get('token');
		if (!token) {
			sessionError = null;
			if (!processingToken) {
				sessionReady = true;
			}
			return;
		}

		if (processingToken || processedToken === token) {
			return;
		}

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
		if (!browser) return;

		const unsubscribe = page.subscribe(($page) => {
			void handleTokenLogin($page.url);
		});

		return unsubscribe;
	});
</script>

<Toast />

<div class="flex min-h-screen flex-col bg-gray-50 text-gray-900">
	<Nav />
	<GlobalAacTabBar />

	<main class="mx-auto w-full flex-grow py-6 sm:px-6 lg:px-8">
		{#if sessionError}
			<div
				class="mx-auto mt-12 max-w-md rounded-lg border border-red-200 bg-red-50 p-6 text-center"
			>
				<h2 class="text-lg font-semibold text-red-800">Unable to start session</h2>
				<p class="mt-2 text-sm text-red-600">{sessionError}</p>
				<a
					href="{base}/"
					class="mt-4 inline-block text-sm font-medium text-blue-600 hover:underline"
				>
					Return to login
				</a>
			</div>
		{:else if sessionReady}
			{@render children()}
		{/if}
	</main>

	<Footer />
</div>
