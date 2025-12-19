<script>
	import { browser } from '$app/environment';
	import { base } from '$app/paths'; // Import base path helper
	import Login from '$lib/components/Login.svelte';
	import Signup from '$lib/components/Signup.svelte';
	import { user } from '$lib/stores/userStore';
	import { onMount } from 'svelte';
	import { marked } from 'marked';
	import { getApiUrl } from '$lib/config';
	import { locale } from '$lib/i18n';
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

	// Function to load news content
	async function loadNews() {
		if (!$user.isLoggedIn) {
			isLoadingNews = false;
			return;
		}

		try {
			isLoadingNews = true;
			// Get current language from the locale store
			const currentLang = $locale || 'en'; // Default to 'en' if no locale set (backend handles default language)
			console.log('Loading news for language:', currentLang);

			// Build the API URL for news endpoint
			const newsUrl = getApiUrl(`news/${currentLang}`);
			console.log('Fetching news from API:', newsUrl);

			// Include authorization header for the API call
			const response = await fetch(newsUrl, {
				headers: {
					'Authorization': `Bearer ${$user.token}`,
					'Content-Type': 'application/json'
				}
			});
			console.log('News API response status:', response.status);

			if (response.ok) {
				const data = await response.json();
				console.log('News API response:', data);

				if (data.success && data.content && data.content.trim()) {
					newsContent = String(marked.parse(data.content));
					console.log('News content rendered successfully');
				} else {
					console.warn('News API returned empty content');
					newsContent = '<p>No news content available.</p>';
				}
			} else if (response.status === 404) {
				console.warn('News not found for current language, trying fallback to English');
				// Try fallback to English if current language doesn't have news
				const fallbackUrl = getApiUrl('news/en');
				const fallbackResponse = await fetch(fallbackUrl, {
					headers: {
						'Authorization': `Bearer ${$user.token}`,
						'Content-Type': 'application/json'
					}
				});

				if (fallbackResponse.ok) {
					const fallbackData = await fallbackResponse.json();
					if (fallbackData.success && fallbackData.content && fallbackData.content.trim()) {
						newsContent = String(marked.parse(fallbackData.content));
						console.log('News fallback to English successful');
					} else {
						newsContent = '<p>No news content available.</p>';
					}
				} else {
					newsContent = '<p>No news content available for your language.</p>';
				}
			} else if (response.status === 503) {
				// Service unavailable - likely using cache due to origin timeout
				try {
					const cacheData = await response.json();
					if (cacheData.success && cacheData.content) {
						newsContent = String(marked.parse(cacheData.content));
						console.log('Using cached news due to origin timeout');
					} else {
						newsContent = '<p>News service temporarily unavailable.</p>';
					}
				} catch (e) {
					newsContent = '<p>News service temporarily unavailable.</p>';
				}
			} else {
				let errorMessage = 'Error loading news. Please try again later.';
				try {
					const errorData = await response.json();
					if (errorData.error) {
						errorMessage = `Error: ${errorData.error}`;
					}
				} catch (e) {
					// Ignore JSON parsing errors
				}
				newsContent = `<p>${errorMessage}</p>`;
				console.error('Failed to fetch news from API:', response.status, response.statusText);
			}
		} catch (error) {
			newsContent = '<p>Error loading news. Please try again later.</p>';
			console.error('Error fetching news from API:', error);
		} finally {
			isLoadingNews = false;
		}
	}

	// Load news when component mounts
	onMount(async () => {
		await loadNews();
	});

	// Reload news when language changes
	$effect(() => {
		// React to locale changes
		if ($locale && $user.isLoggedIn) {
			console.log('Language changed, reloading news...');
			loadNews();
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
	{#if $user.isLoggedIn} <!-- Reactive check of user store -->
		<!-- Content for logged in users -->
		<div class="bg-white shadow rounded-lg p-6">
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
					class="inline-block px-4 py-2 bg-[#2271b3] text-white rounded hover:bg-[#195a91] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#2271b3]"
				>
					View Learning Assistants
				</a>
			</div>
		</div>
	{:else}
		<!-- Auth container for non-logged in users -->
		<div class="max-w-md mx-auto bg-white shadow-md rounded-lg overflow-hidden">
			{#if authMode === 'login'}
				<Login on:show-signup={showSignup} />
			{:else}
				<Signup on:show-login={showLogin} />
			{/if}
		</div>
		
		<!-- Logo for non-logged in users -->
		<div class="text-center mt-8">
			<div class="mx-auto bg-[#e9ecef] p-4 rounded-lg" style="max-width: 400px;">
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
