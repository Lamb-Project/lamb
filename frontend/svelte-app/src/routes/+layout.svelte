<script>
	import '../app.css';
	import { browser } from '$app/environment';
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { base } from '$app/paths';
	import Nav from '$lib/components/Nav.svelte';
	import Footer from '$lib/components/Footer.svelte';
	import AacSidebar from '$lib/components/aac/AacSidebar.svelte';
	import { sidebarOpen, sidebarWidth, sidebarMobile } from '$lib/stores/aacStore.svelte';
	import { afterNavigate } from '$app/navigation';
	import { markWorkspaceDirty, clearWorkspaceDirty } from '$lib/services/frontendManage';
	afterNavigate(clearWorkspaceDirty);
	import { replaceSessionWithToken } from '$lib/session/sessionManager';
	import { get } from 'svelte/store';
	import { user } from '$lib/stores/userStore';

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

		// Cross-tab session reconciliation (#302). localStorage is shared across
		// tabs of the same browser, but each tab keeps its own in-memory user
		// store. If another tab logs in as a different user (or via an LTI
		// activity launch) or logs out, this tab's in-memory session goes stale
		// while the shared token changes underneath it — letting the previous
		// user linger here and act with the new token. The `storage` event fires
		// only in OTHER tabs, so when the auth token changes elsewhere we reload
		// to re-bootstrap cleanly from the current localStorage. (e.key is null
		// on a full localStorage.clear().)
		const onStorage = (/** @type {StorageEvent} */ e) => {
			if (e.key && e.key !== 'userToken') return;
			const current = get(user).token || null;
			const next = localStorage.getItem('userToken') || null;
			if (next !== current) {
				window.location.reload();
			}
		};
		window.addEventListener('storage', onStorage);

		return () => {
			unsubscribe();
			window.removeEventListener('storage', onStorage);
		};
	});
</script>

<div class="min-h-screen bg-gray-50 text-gray-900 flex flex-col">
	<div class="lamb-workspace" class:agent-open={$sidebarOpen && !!$user.token} style:--aac-width={$sidebarWidth + "px"} inert={$sidebarOpen && $sidebarMobile && !!$user.token}>
	<Nav />


	<main oninputcapture={markWorkspaceDirty} class="w-full mx-auto py-6 sm:px-6 lg:px-8 flex-grow" class:aac-workspace={$sidebarOpen && !!$user.token}>
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
	{#if sessionReady && $user.token}<AacSidebar />{/if}
</div>

<style>
.lamb-workspace { min-height: 100vh; display: flex; flex-direction: column; min-width: 0; width: 100%; }
.lamb-workspace main { min-width: 0; overflow-x: auto; }
@media (min-width: 920px) { .lamb-workspace.agent-open { width: calc(100% - var(--aac-width)); } }
</style>
