<script>
	import { browser } from '$app/environment';
	import { base } from '$app/paths';
	import Login from '$lib/components/Login.svelte';
	import Signup from '$lib/components/Signup.svelte';
	import UserDashboard from '$lib/components/UserDashboard.svelte';
	import { user } from '$lib/stores/userStore';
	import { onMount } from 'svelte';
	import { marked } from 'marked';
	import { getApiUrl } from '$lib/config';
	import { _, locale } from '$lib/i18n';
	import { getMyProfile } from '$lib/services/adminService';

	let config = $state(null);
	let authMode = $state('login'); // 'login' or 'signup'

	// Tab state
	/** @type {'dashboard' | 'help'} */
	let currentTab = $state('dashboard');

	// Dashboard state
	/** @type {any} */
	let profileData = $state(null);
	let isLoadingProfile = $state(false);
	/** @type {string | null} */
	let profileError = $state(null);

	// News / Help state
	let newsContent = $state('');
	let isLoadingNews = $state(true);

	$effect(() => {
		if (browser && window.LAMB_CONFIG) {
			config = window.LAMB_CONFIG;
		}
	});

	// Function to load user profile for dashboard
	async function loadProfile() {
		if (!$user.isLoggedIn || !$user.token) {
			return;
		}

		try {
			isLoadingProfile = true;
			profileError = null;
			profileData = await getMyProfile($user.token);
		} catch (error) {
			console.error('Error loading profile:', error);
			profileError = error instanceof Error ? error.message : 'Failed to load profile';
			profileData = null;
		} finally {
			isLoadingProfile = false;
		}
	}

	// Function to load news content
	async function loadNews() {
		if (!$user.isLoggedIn) {
			isLoadingNews = false;
			return;
		}

		try {
			isLoadingNews = true;
			const currentLang = $locale || 'en';
			const newsUrl = getApiUrl(`news/${currentLang}`);

			const response = await fetch(newsUrl, {
				headers: {
					'Authorization': `Bearer ${$user.token}`,
					'Content-Type': 'application/json'
				}
			});

			if (response.ok) {
				const data = await response.json();
				if (data.success && data.content && data.content.trim()) {
					newsContent = String(marked.parse(data.content));
				} else {
					newsContent = '';
				}
			} else if (response.status === 404) {
				// Fallback to English
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
					} else {
						newsContent = '';
					}
				} else {
					newsContent = '';
				}
			} else if (response.status === 503) {
				try {
					const cacheData = await response.json();
					if (cacheData.success && cacheData.content) {
						newsContent = String(marked.parse(cacheData.content));
					} else {
						newsContent = '';
					}
				} catch (e) {
					newsContent = '';
				}
			} else {
				newsContent = '';
			}
		} catch (error) {
			newsContent = '';
			console.error('Error fetching news:', error);
		} finally {
			isLoadingNews = false;
		}
	}

	// Load data when component mounts
	onMount(async () => {
		if ($user.isLoggedIn) {
			loadProfile();
			loadNews();
		}
	});

	// Reload news when language changes
	$effect(() => {
		if ($locale && $user.isLoggedIn) {
			loadNews();
		}
	});

	// Tab switch functions
	function showDashboard() {
		currentTab = 'dashboard';
	}

	function showHelp() {
		currentTab = 'help';
		// Lazy load news if not loaded yet
		if (!newsContent && !isLoadingNews) {
			loadNews();
		}
	}

	// Auth mode functions
	function showLogin() {
		authMode = 'login';
	}
	function showSignup() {
		authMode = 'signup';
	}
</script>

<div class="container mx-auto px-4 py-8">
	{#if $user.isLoggedIn}
		<!-- Tabs matching admin dashboard style -->
		<div class="border-b border-gray-200 mb-6">
			<ul class="flex flex-wrap -mb-px">
				<li class="mr-2">
					<button
						class={`inline-block py-2 px-4 text-sm font-medium ${currentTab === 'dashboard' ? 'text-white bg-[#2271b3] border-[#2271b3]' : 'text-gray-500 hover:text-[#2271b3] border-transparent'} rounded-t-lg border-b-2`}
						onclick={showDashboard}
						aria-label={$_('home.tabs.dashboard', { default: 'Dashboard' })}
					>
						<span class="inline-flex items-center gap-2">
							<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
							</svg>
							{$_('home.tabs.dashboard', { default: 'Dashboard' })}
						</span>
					</button>
				</li>
				<li class="mr-2">
					<button
						class={`inline-block py-2 px-4 text-sm font-medium ${currentTab === 'help' ? 'text-white bg-[#2271b3] border-[#2271b3]' : 'text-gray-500 hover:text-[#2271b3] border-transparent'} rounded-t-lg border-b-2`}
						onclick={showHelp}
						aria-label={$_('home.tabs.help', { default: 'Help & News' })}
					>
						<span class="inline-flex items-center gap-2">
							<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
							</svg>
							{$_('home.tabs.help', { default: 'Help & News' })}
						</span>
					</button>
				</li>
			</ul>
		</div>

		<!-- Tab content -->
		{#if currentTab === 'dashboard'}
			<UserDashboard
				profile={profileData}
				isLoading={isLoadingProfile}
				error={profileError}
				onRetry={loadProfile}
			/>
		{:else if currentTab === 'help'}
			<!-- Help & News tab (former home page content) -->
			<div>
				<h1 class="text-2xl font-semibold text-gray-800 mb-2">
					{$_('home.help.title', { default: 'Help & News' })}
				</h1>
				<p class="text-gray-500 mb-6 text-sm">
					{$_('home.help.subtitle', { default: 'Latest updates and information' })}
				</p>

				<div class="bg-white shadow rounded-lg p-6">
					{#if isLoadingNews}
						<div class="flex items-center justify-center py-8">
							<svg class="animate-spin h-6 w-6 text-[#2271b3] mr-3" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
								<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
								<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
							</svg>
							<span class="text-gray-500">{$_('home.help.loadingNews', { default: 'Loading news...' })}</span>
						</div>
					{:else if newsContent}
						<div class="prose max-w-none">
							{@html newsContent}
						</div>
					{:else}
						<p class="text-center text-gray-500 py-4">
							{$_('home.help.noNews', { default: 'No news to display.' })}
						</p>
					{/if}

					<div class="mt-8 text-center">
						<a
							href="{base}/assistants"
							class="inline-block px-4 py-2 bg-[#2271b3] text-white rounded hover:bg-[#195a91] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#2271b3]"
						>
							{$_('home.help.viewAssistants', { default: 'View Learning Assistants' })}
						</a>
					</div>
				</div>
			</div>
		{/if}
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
