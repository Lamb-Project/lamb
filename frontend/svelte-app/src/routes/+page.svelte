<script>
	import { browser } from '$app/environment';
	import { base } from '$app/paths'; // Import base path helper
	import { dev } from '$app/environment';
	import Login from '$lib/components/Login.svelte';
	import Signup from '$lib/components/Signup.svelte';
	import { user } from '$lib/stores/userStore';
	import { onMount } from 'svelte';
	import { marked } from 'marked';
	// import { _ } from 'svelte-i18n'; // Restore later
	// onMount(() => { // Needed for i18n

	let config = $state(null);
	// let localeLoaded = $state(false); // Restore later
	let authMode = $state('login'); // 'login' or 'signup'
	let newsContent = $state('');
	let isLoadingNews = $state(true);

	$effect(() => {
		if (browser && window.LAMB_CONFIG) {
			config = window.LAMB_CONFIG;
		}
	});

	onMount(async () => {
		if ($user.isLoggedIn) {
			try {
				// Build the fetch URL - the news file is in backend/static/md/lamb-news.md
				// In dev mode, it's served at /md/, in prod at /static/md/
				const newsUrl = dev ? `${base}/md/lamb-news.md` : `${base}/static/md/lamb-news.md`;
				console.log('Fetching news from:', newsUrl);

				const response = await fetch(newsUrl);
				console.log('News fetch response status:', response.status);

				if (response.ok) {
					const markdown = await response.text();
					console.log('News markdown length:', markdown.length);

					if (markdown && markdown.trim()) {
						newsContent = String(marked.parse(markdown));
					} else {
						console.warn('News markdown is empty');
						newsContent = '<p>No news content available.</p>';
					}
				} else {
					newsContent = '<p>Error loading news. Please try again later.</p>';
					console.error('Failed to fetch lamb-news.md:', response.status, response.statusText);
				}
			} catch (error) {
				newsContent = '<p>Error loading news. Please try again later.</p>';
				console.error('Error fetching lamb-news.md:', error);
			} finally {
				isLoadingNews = false;
			}
		} else {
			isLoadingNews = false; // Not logged in, no need to load news
		}
	});

	// Functions to switch auth modes
	function showLogin() {
		authMode = 'login';
	}
	function showSignup() {
		authMode = 'signup';
	}

	/* Removed handleAssistantsClick
	function handleAssistantsClick() {
		if ($user.isLoggedIn) { // Check store value reactively
			showAssistants = true;
		}
	}
	*/

	// Restore onMount for i18n later
	// onMount(() => {
	// 	const unsubscribe = locale.subscribe(value => {
	// 		if (value) {
	// 			localeLoaded = true;
	// 		}
	// 	});
	//
	// 	return unsubscribe;
	// });
</script>

<div class="container mx-auto px-4 py-8">
	{#if $user.isLoggedIn}
		<!-- Reactive check of user store -->
		<!-- Content for logged in users -->
		<div class="rounded-lg bg-white p-6 shadow">
			{#if isLoadingNews}
				<p class="text-center">Loading news...</p>
			{:else if newsContent}
				<div class="prose max-w-none">
					{@html newsContent}
				</div>
			{:else}
				<p class="text-center">No news to display.</p>
			{/if}

			<div class="mt-8 text-center">
				<a
					href="{base}/assistants"
					class="inline-block rounded bg-[#2271b3] px-4 py-2 text-white hover:bg-[#195a91] focus:ring-2 focus:ring-[#2271b3] focus:ring-offset-2 focus:outline-none"
				>
					View Learning Assistants
				</a>
			</div>
		</div>
	{:else}
		<!-- Auth container for non-logged in users -->
		<div class="mx-auto max-w-md overflow-hidden rounded-lg bg-white shadow-md">
			{#if authMode === 'login'}
				<Login on:show-signup={showSignup} />
			{:else}
				<Signup on:show-login={showLogin} />
			{/if}
		</div>

		<!-- Logo for non-logged in users -->
		<div class="mt-8 text-center">
			<div class="mx-auto rounded-lg bg-[#e9ecef] p-4" style="max-width: 400px;">
				<h2 class="text-3xl font-bold text-[#2271b3]">LAMB</h2>
				<p class="text-[#195a91]">Learning Assistants Manager and Builder</p>
			</div>
		</div>
	{/if}
</div>

<!-- Debug Config commented out 
<h2>LAMB Configuration (Debug)</h2>
{#if config}
	<pre>{JSON.stringify(config, null, 2)}</pre>
{:else}
	<p>Loading configuration...</p>
{/if} 
-->
