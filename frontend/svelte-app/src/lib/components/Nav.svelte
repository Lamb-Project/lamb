<script>
  import { user } from '$lib/stores/userStore';
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { base } from '$app/paths';
  import { locale, _ } from '$lib/i18n';
  import LanguageSelector from '$lib/components/LanguageSelector.svelte';
  import { VERSION_INFO } from '$lib/version.js';
  
  // Format version display
  let versionDisplay = `v${VERSION_INFO.version}`;
  
  // Default text for when i18n isn't loaded yet
  let localeLoaded = $state(false);
  
  // Navigation state
  let toolsMenuOpen = $state(false);

  // Logout function
  function logout() { // Restore logout function
    user.logout();
    // Redirect to the base path after logout
    window.location.href = base + '/';
  }

  // Close dropdown when clicking outside (optimized)
  function handleClickOutside(event) {
    // Only check if menu is actually open to avoid unnecessary work
    if (!toolsMenuOpen) return;
    
    const toolsMenu = event.target.closest('.tools-menu');
    if (!toolsMenu) {
      toolsMenuOpen = false;
    }
  }

  // Handle keyboard navigation
  function handleKeydown(event) {
    if (toolsMenuOpen && event.key === 'Escape') {
      toolsMenuOpen = false;
    }
  }
  
  // Use $effect to react to locale changes
  $effect(() => {
    // Directly read the locale store value
    const currentLocale = $locale;
    if (currentLocale) {
      localeLoaded = true;
    }
    // No cleanup function needed here as we're just reading the store
  });

  // Set up event listeners for dropdown
  onMount(() => {
    document.addEventListener('click', handleClickOutside);
    document.addEventListener('keydown', handleKeydown);

    // If the user is logged in (has token) but name is missing, fetch the profile
    // This handles page refreshes after LTI login where profile wasn't fully populated
    if ($user.isLoggedIn && !$user.name) {
      user.fetchAndPopulateProfile();
    }

    return () => {
      document.removeEventListener('click', handleClickOutside);
      document.removeEventListener('keydown', handleKeydown);
    };
  });
</script>

<nav class="bg-white shadow">
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
    <div class="flex justify-between h-16">
      <div class="flex">
        <!-- Logo -->
        <div class="flex-shrink-0 flex items-center">
          <div class="flex items-center space-x-2">
            <!-- Image path updated to be relative to static dir -->
            <img src="{base}/img/lamb_1.png" alt="LAMB Logo" class="h-14">
            <div class="text-lg font-bold">
              <a href="{base}/">{localeLoaded ? $_('app.logoText', { default: 'LAMB' }) : 'LAMB'}</a> 
              <span class="text-xs bg-gray-200 px-1 py-0.5 rounded" title="Version: {VERSION_INFO.version}, Commit: {VERSION_INFO.commit}, Branch: {VERSION_INFO.branch}">{versionDisplay}</span>
            </div>
          </div>
        </div>
        
        <!-- Navigation links -->
        <div class="hidden sm:ml-4 sm:flex sm:items-center sm:gap-1">
          
          <!-- Restore dynamic class based on $page.url.pathname and $user -->
          <!-- Restore: aria-disabled={!$user.isLoggedIn} -->
          <a
            href="{base}/assistants"
            class="inline-flex items-center px-2 pt-1 border-b-2 text-sm font-medium whitespace-nowrap {$page.url.pathname === base + '/assistants' ? 'border-[#2271b3] text-gray-900' : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'} {!$user.isLoggedIn ? 'opacity-50 pointer-events-none' : ''}"
            aria-disabled={!$user.isLoggedIn}
          >
            {localeLoaded ? $_('assistants.title') : 'Learning Assistants'}
          </a>
          
          {#if $user.isLoggedIn && $user.data?.role === 'admin'} <!-- System Admin link -->
          <a
            href="{base}/admin"
            class="inline-flex items-center px-2 pt-1 border-b-2 text-sm font-medium whitespace-nowrap {$page.url.pathname === base + '/admin' ? 'border-[#2271b3] text-gray-900' : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'}"
          >
            {localeLoaded ? $_('nav.admin', { default: 'Admin' }) : 'Admin'}
          </a>
          {/if}
          
          {#if $user.isLoggedIn && $user.data?.organization_role === 'admin' && $user.data?.role !== 'admin'} <!-- Org Admin link - only for org admins (not system admins) -->
          <a
            href="{base}/org-admin"
            class="inline-flex items-center px-2 pt-1 border-b-2 text-sm font-medium whitespace-nowrap {$page.url.pathname === base + '/org-admin' ? 'border-[#2271b3] text-gray-900' : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'}"
          >
            {localeLoaded ? $_('nav.orgAdmin', { default: 'Org Admin' }) : 'Org Admin'}
          </a>
          {/if}
          
          <!-- Sources dropdown menu -->
          <div class="relative tools-menu h-full flex items-center">
            <button
              type="button"
              onclick={() => toolsMenuOpen = !toolsMenuOpen}
              class="inline-flex items-center h-full px-2 py-4 border-b-2 text-sm font-medium cursor-pointer select-none whitespace-nowrap {($page.url.pathname.startsWith(base + '/knowledgebases') || $page.url.pathname.startsWith(base + '/evaluaitor')) ? 'border-[#2271b3] text-gray-900' : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'} {!$user.isLoggedIn ? 'opacity-50 pointer-events-none' : ''}"
              aria-disabled={!$user.isLoggedIn}
              aria-expanded={toolsMenuOpen}
              aria-haspopup="true"
            >
              <span class="pointer-events-none">{localeLoaded ? $_('nav.sources', { default: 'Sources of Knowledge' }) : 'Sources of Knowledge'}</span>
              <svg class="ml-1 h-4 w-4 transition-transform duration-200 pointer-events-none {toolsMenuOpen ? 'rotate-180' : ''}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>
              </svg>
            </button>

            {#if toolsMenuOpen}
              <div class="absolute z-50 left-0 top-full w-52 bg-white border border-gray-200 rounded-b-md shadow-lg">
                <div class="py-2">
                  <a
                    href="{base}/knowledgebases"
                    onclick={() => toolsMenuOpen = false}
                    class="block px-4 py-3 text-sm font-medium text-gray-700 hover:text-[#2271b3] hover:bg-gray-50 transition-colors duration-150 {$page.url.pathname.startsWith(base + '/knowledgebases') ? 'bg-blue-50 text-[#2271b3]' : ''}"
                  >
                    {localeLoaded ? $_('knowledgeBases.title') : 'Knowledge Bases'}
                  </a>
                  <a
                    href="{base}/evaluaitor"
                    onclick={() => toolsMenuOpen = false}
                    class="block px-4 py-3 text-sm font-medium text-gray-700 hover:text-[#2271b3] hover:bg-gray-50 transition-colors duration-150 {$page.url.pathname.startsWith(base + '/evaluaitor') ? 'bg-blue-50 text-[#2271b3]' : ''}"
                  >
                    {localeLoaded ? $_('nav.rubrics', { default: 'Rubrics' }) : 'Rubrics'}
                  </a>
                </div>
              </div>
            {/if}
          </div>

        </div>
      </div>
      
      <!-- User info and Language selector section -->
      <div class="flex items-center gap-3">
        {#if $user.isLoggedIn}
          <!-- Username -->
          <span class="text-sm font-medium text-gray-600 hidden sm:block">{$user.name || $user.email || ''}</span>
        {/if}
        
        <!-- Logout and Language stacked vertically -->
        <div class="flex flex-col items-end gap-0.5">
          {#if $user.isLoggedIn}
            <button
              onclick={logout}
              class="inline-flex items-center justify-center px-2 py-1 text-xs font-medium rounded text-white bg-red-600 hover:bg-red-700"
            >
              {localeLoaded ? $_('auth.logout') : 'Logout'}
            </button>
          {/if}
          <!-- Language selector (smaller) -->
          <LanguageSelector size="small" />
        </div>
      </div>
      
    </div>
  </div>
</nav> 