<script>
	import { user } from '$lib/stores/userStore'; // Restore user store import
	// import LanguageSelector from './LanguageSelector.svelte'; // Migrated in Internationalization module
	// import { _, locale } from 'svelte-i18n'; // Migrated in Internationalization module
	import { /* onMount, */ createEventDispatcher } from 'svelte'; // onMount needed for i18n
	// import { browser } from '$app/environment';
	import { page } from '$app/stores';
	import { base } from '$app/paths'; // Import base path helper
	import { locale, _ } from '$lib/i18n'; // Import i18n tools
	import LanguageSelector from '$lib/components/LanguageSelector.svelte'; // Import selector
	// import { onMount } from 'svelte';

	// Event dispatcher for component events
	const dispatch = createEventDispatcher();

	// Default text for when i18n isn't loaded yet
	let localeLoaded = $state(false);

	// Navigation state

	// Logout function
	function logout() {
		// Restore logout function
		user.logout();
		// Redirect to the base path after logout
		window.location.href = base + '/';
	}

	// Get help from input
	// function getHelpFromInput() { // Part of Help System module
	//   const helpInput = document.getElementById('helpInput');
	//   // Check if it's an input element before accessing value
	//   if (helpInput instanceof HTMLInputElement && helpInput.value.trim()) {
	//     dispatch('help', { question: helpInput.value.trim() });
	//     helpInput.value = '';
	//   }
	// }

	// Use $effect to react to locale changes
	$effect(() => {
		// Directly read the locale store value
		const currentLocale = $locale;
		if (currentLocale) {
			localeLoaded = true;
			console.log('Locale loaded via $effect:', currentLocale); // Optional: for debugging
		}
		// No cleanup function needed here as we're just reading the store
	});
</script>

<nav class="bg-white shadow">
	<div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
		<div class="flex h-16 justify-between">
			<div class="flex">
				<!-- Logo -->
				<div class="flex flex-shrink-0 items-center">
					<div class="flex items-center space-x-2">
						<!-- Image path updated to be relative to static dir -->
						<img src="{base}/img/lamb_1.png" alt="LAMB Logo" class="h-14" />
						<div>
							<div class="text-lg font-bold">
								<a href="{base}/"
									>{localeLoaded ? $_('app.logoText', { default: 'LAMB' }) : 'LAMB'}</a
								>
								<span class="rounded bg-gray-200 px-1 py-0.5 text-xs">v0.1</span>
							</div>
							<span class="text-xs text-gray-600"
								>{localeLoaded
									? $_('app.tagline', { default: 'Learning Assistants Manager and Builder' })
									: 'Learning Assistants Manager and Builder'}</span
							>
						</div>
					</div>
				</div>

				<!-- Navigation links -->
				<div class="hidden sm:ml-6 sm:flex sm:space-x-8">
					<!-- Restore dynamic class based on $page.url.pathname and $user -->
					<!-- Restore: aria-disabled={!$user.isLoggedIn} -->
					<a
						href="{base}/assistants"
						class="inline-flex items-center border-b-2 px-1 pt-1 text-sm font-medium {$page.url
							.pathname ===
						base + '/assistants'
							? 'border-[#2271b3] text-gray-900'
							: 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'} {!$user.isLoggedIn
							? 'pointer-events-none opacity-50'
							: ''}"
						aria-disabled={!$user.isLoggedIn}
					>
						{localeLoaded ? $_('assistants.title') : 'Learning Assistants'}
					</a>

					{#if $user.isLoggedIn && $user.data?.role === 'admin'}
						<!-- Restore check for admin role -->
						<!-- Restore dynamic class based on $page.url.pathname -->
						<a
							href="{base}/admin"
							class="inline-flex items-center border-b-2 px-1 pt-1 text-sm font-medium {$page.url
								.pathname ===
							base + '/admin'
								? 'border-[#2271b3] text-gray-900'
								: 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'}"
						>
							{localeLoaded ? $_('nav.admin', { default: 'System Admin' }) : 'System Admin'}
						</a>
					{/if}

					{#if $user.isLoggedIn}
						<!-- Organization admin link - we'll check access dynamically -->
						<a
							href="{base}/org-admin"
							class="inline-flex items-center border-b-2 px-1 pt-1 text-sm font-medium {$page.url
								.pathname ===
							base + '/org-admin'
								? 'border-[#2271b3] text-gray-900'
								: 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'}"
						>
							{localeLoaded ? $_('nav.orgAdmin', { default: 'Org Admin' }) : 'Org Admin'}
						</a>
					{/if}

					<!-- Restore dynamic class based on $page.url.pathname and $user -->
					<!-- Restore: aria-disabled={!$user.isLoggedIn} -->
					<a
						href="{base}/knowledgebases"
						class="inline-flex items-center border-b-2 px-1 pt-1 text-sm font-medium {$page.url.pathname.startsWith(
							base + '/knowledgebases'
						)
							? 'border-[#2271b3] text-gray-900'
							: 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'} {!$user.isLoggedIn
							? 'pointer-events-none opacity-50'
							: ''}"
						aria-disabled={!$user.isLoggedIn}
					>
						{localeLoaded ? $_('knowledgeBases.title') : 'Knowledge Bases'}
					</a>
				</div>
			</div>

			<!-- User info and Language selector section -->
			<div class="flex items-center">
				{#if $user.isLoggedIn}
					<div class="flex items-center space-x-4">
						<span class="text-sm font-medium text-gray-700">{$user.name}</span>
						{#if $user.owiUrl}
							<a
								href={$user.owiUrl}
								target="_blank"
								class="inline-flex items-center rounded-md border border-gray-300 bg-white px-3 py-1 text-sm font-medium text-gray-700 hover:bg-gray-50"
							>
								{localeLoaded ? $_('nav.openWebUI', { default: 'OpenWebUI' }) : 'OpenWebUI'}
							</a>
						{/if}
						<button
							onclick={logout}
							class="inline-flex items-center rounded-md border border-transparent bg-red-600 px-3 py-1 text-sm font-medium text-white hover:bg-red-700"
						>
							{localeLoaded ? $_('auth.logout') : 'Logout'}
						</button>
					</div>
				{/if}

				<!-- Explicitly add the Language selector div -->
				<div class="ml-4">
					<LanguageSelector />
				</div>
			</div>
		</div>
	</div>
</nav>

<!-- Help container (temporarily disabled) -->
<!-- 
<div class="bg-gray-100 py-2">
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
    <div class="flex items-center">
      <input 
        type="text" 
        id="helpInput" 
        placeholder="Ask LAMB anything..." 
        class="flex-grow px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-[#2271b3] focus:border-[#2271b3]"
      >
      <button 
        id="helpButton" 
        class="ml-3 inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-[#2271b3] hover:bg-[#195a91]"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mr-2" viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M11.3 1.046A1 1 0 0112 2v5h4a1 1 0 01.82 1.573l-7 10A1 1 0 018 18v-5H4a1 1 0 01-.82-1.573l7-10a1 1 0 011.12-.38z" clip-rule="evenodd" />
        </svg>
        LAMB Help
      </button>
    </div>
  </div>
</div>
-->
