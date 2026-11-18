<script>
  import { scenarioText } from '$lib/utils/learningScenarioText';
  import { activitiesText } from '$lib/utils/activities';
  import { moodleStatus } from '$lib/services/moodleService';
  import { apiKeysEnabled } from '$lib/services/apiKeysService';
  import { apiKeysText } from '$lib/utils/apiKeysText';
  let moodleEnabled = $state(false);
  let keysEnabled = $state(false);
  async function refreshMoodle() {
    try {moodleEnabled = (await moodleStatus()).settings.enabled === true;}
    catch (_) {moodleEnabled=false;}
  }
  $effect(() => {
    const identity = $user.isLoggedIn && ($user.email || $user.data?.id);
    moodleEnabled=false; keysEnabled=false;
    if (identity) {
      let active=true;
      moodleStatus().then(s => {if(active) moodleEnabled=s.settings.enabled === true;}).catch(() => {});
      apiKeysEnabled().then(ok => {if(active) keysEnabled=ok;});
      return () => {active=false;};
    }
  });
  import { sidebarOpen } from '$lib/stores/aacStore.svelte';
  import { user } from '$lib/stores/userStore';
  import { clearCurrentSession, ensureProfileLoaded } from '$lib/session/sessionManager';
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { base } from '$app/paths';
  import { locale, _ } from '$lib/i18n';
  import LanguageSelector from '$lib/components/LanguageSelector.svelte';
  import { VERSION_INFO } from '$lib/version.js';
  import { getConfig } from '$lib/config.js';
  import { switchLtiOrganization } from '$lib/services/authService';
  import { carryActivity } from '$lib/session/activityReturn';

  // The organization of this session, shown next to the user name. A teacher who came from the LMS
  // and has Creator accounts in several organizations gets a menu to move between them (#562).
  let ltiOrganizations = $derived(
    $user.isLoggedIn && Array.isArray($user.data?.lti_organizations) ? $user.data.lti_organizations : []
  );
  let organizationName = $derived(
    !$user.isLoggedIn ? '' : $user.data?.organization?.name
      || ltiOrganizations.find((/** @type {any} */ account) => account.current)?.organization_name
      || ''
  );
  let canSwitchOrganization = $derived(ltiOrganizations.length >= 2);
  let orgMenuOpen = $state(false);
  let switchingTo = $state(/** @type {number | null} */ (null));
  let switchError = $state('');

  // The organization comes with the profile. A password sign-in, and a session stored before this
  // version, carry a profile without it: read the profile once more, once per session.
  let profileAskedFor = '';
  $effect(() => {
    const token = $user.isLoggedIn && $user.name && !$user.data?.organization ? $user.token : null;
    if (!token || profileAskedFor === token) return;
    profileAskedFor = token;
    user.fetchAndPopulateProfile().catch(() => {});
  });

  /** @param {{ creator_user_id: number, current?: boolean }} account */
  async function switchOrganization(account) {
    if (account.current || switchingTo !== null) return;
    switchingTo = account.creator_user_id;
    switchError = '';
    try {
      // The address carries the new session: follow it in this window, never log or show it.
      const url = await switchLtiOrganization(account.creator_user_id);
      window.location.assign(carryActivity(url));
    } catch (error) {
      // What the API said, or a general message when it said nothing (network, expired session).
      const fallback = 'The organization could not be changed. Open LAMB from your LMS again.';
      switchError = /** @type {any} */ (error)?.detail || (localeLoaded ? $_('ltiSession.switchFailed', { default: fallback }) : fallback);
      switchingTo = null;
    }
  }
  
  // Format version display
  let versionDisplay = `v${VERSION_INFO.version}`;
  
  // Feature flags
  let librariesEnabled = $derived(getConfig().features.enableLibraries ?? false);
  
  // Default text for when i18n isn't loaded yet
  let localeLoaded = $state(false);
  
  // Navigation state
  let toolsMenuOpen = $state(false);

  // Logout function
  function logout() { // Restore logout function
    clearCurrentSession();
    // Redirect to the base path after logout
    window.location.href = base + '/';
  }

  // Close dropdown when clicking outside (optimized)
  /** @param {MouseEvent} event */
  function handleClickOutside(event) {
    if (orgMenuOpen && !(event.target instanceof Element && event.target.closest('.org-menu'))) {
      orgMenuOpen = false;
    }
    // Only check if menu is actually open to avoid unnecessary work
    if (!toolsMenuOpen) return;
    
    const target = /** @type {HTMLElement | null} */ (event.target instanceof HTMLElement ? event.target : null);
    const toolsMenu = target?.closest('.tools-menu');
    if (!toolsMenu) {
      toolsMenuOpen = false;
    }
  }

  // Handle keyboard navigation
  /** @param {KeyboardEvent} event */
  function handleKeydown(event) {
    if (toolsMenuOpen && event.key === 'Escape') {
      toolsMenuOpen = false;
    }
    if (orgMenuOpen && event.key === 'Escape') {
      orgMenuOpen = false;
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
    window.addEventListener('moodle-settings-changed', refreshMoodle);
    document.addEventListener('click', handleClickOutside);
    document.addEventListener('keydown', handleKeydown);

    ensureProfileLoaded();

    return () => {
      window.removeEventListener('moodle-settings-changed', refreshMoodle);
      document.removeEventListener('click', handleClickOutside);
      document.removeEventListener('keydown', handleKeydown);
    };
  });
</script>

<nav class="bg-white shadow">
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
    <div class="flex flex-wrap justify-between min-h-16 gap-y-2 py-1">
      <div class="flex flex-wrap">
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
        <div class="hidden sm:ml-4 sm:flex sm:flex-wrap sm:items-center sm:gap-1">
          
          <!-- Restore dynamic class based on $page.url.pathname and $user -->
          <!-- Restore: aria-disabled={!$user.isLoggedIn} -->
          <a
            href="{base}/assistants"
            class="inline-flex items-center px-2 pt-1 border-b-2 text-sm font-medium whitespace-nowrap {$page.url.pathname === base + '/assistants' ? 'border-[#2271b3] text-gray-900' : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'} {!$user.isLoggedIn ? 'opacity-50 pointer-events-none' : ''}"
            aria-disabled={!$user.isLoggedIn}
          >
            {localeLoaded ? $_('assistants.title') : 'Learning Assistants'}
          </a>


          {#if $user.isLoggedIn}
          <a href="{base}/activities" aria-current={$page.url.pathname === base + '/activities' ? 'page' : undefined}
             class="inline-flex items-center px-2 pt-1 border-b-2 text-sm font-medium whitespace-nowrap {$page.url.pathname === base + '/activities' ? 'border-[#2271b3] text-gray-900' : 'border-transparent text-gray-500 hover:text-gray-700'}">{activitiesText($locale).title}</a>
          <a href="{base}/learning-scenarios" aria-current={$page.url.pathname === base + '/learning-scenarios' ? 'page' : undefined}
             class="inline-flex items-center px-2 pt-1 border-b-2 text-sm font-medium whitespace-nowrap {$page.url.pathname === base + '/learning-scenarios' ? 'border-[#2271b3] text-gray-900' : 'border-transparent text-gray-500 hover:text-gray-700'}">{scenarioText($locale).plural}</a>
          {#if moodleEnabled}<a href="{base}/moodle" class="px-2 py-2 text-sm font-medium text-[#173f64]" aria-current={$page.url.pathname === base + '/moodle' ? 'page' : undefined}>Moodle</a>{/if}
          {#if keysEnabled}<a href="{base}/api-keys" data-nav-api-keys class="px-2 py-2 text-sm font-medium text-[#173f64]" aria-current={$page.url.pathname === base + '/api-keys' ? 'page' : undefined}>{apiKeysText($locale).nav}</a>{/if}
          {/if}

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
              class="inline-flex items-center h-full px-2 py-4 border-b-2 text-sm font-medium cursor-pointer select-none whitespace-nowrap {($page.url.pathname.startsWith(base + '/knowledgebases') || (librariesEnabled && $page.url.pathname.startsWith(base + '/libraries')) || $page.url.pathname.startsWith(base + '/evaluaitor')) ? 'border-[#2271b3] text-gray-900' : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'} {!$user.isLoggedIn ? 'opacity-50 pointer-events-none' : ''}"
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
                  {#if librariesEnabled}
                    <a
                      href="{base}/libraries"
                      onclick={() => toolsMenuOpen = false}
                      class="block px-4 py-3 text-sm font-medium text-gray-700 hover:text-[#2271b3] hover:bg-gray-50 transition-colors duration-150 {$page.url.pathname.startsWith(base + '/libraries') ? 'bg-blue-50 text-[#2271b3]' : ''}"
                    >
                      {localeLoaded ? $_('libraries.title', { default: 'Libraries' }) : 'Libraries'}
                    </a>
                  {/if}
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
      
      {#if $user.isLoggedIn}
      <a href="{base}/activities" class="sm:hidden order-last w-full py-2 text-sm font-medium text-[#173f64]">{activitiesText($locale).title}</a>
      <a href="{base}/learning-scenarios" class="sm:hidden order-last w-full py-2 text-sm font-medium text-[#173f64]" aria-current={$page.url.pathname === base + '/learning-scenarios' ? 'page' : undefined}>{scenarioText($locale).plural}</a>
      {#if moodleEnabled}<a href="{base}/moodle" class="sm:hidden order-last w-full py-2 text-sm font-medium text-[#173f64]">Moodle</a>{/if}
      {#if keysEnabled}<a href="{base}/api-keys" class="sm:hidden order-last w-full py-2 text-sm font-medium text-[#173f64]">{apiKeysText($locale).nav}</a>{/if}
      {/if}
      <!-- User info and Language selector section -->
      <div class="flex items-center gap-3 min-w-0">
        {#if $user.isLoggedIn}
          <button class="rounded bg-[#173f64] text-white px-3 py-2 text-xs font-semibold whitespace-nowrap" onclick={() => sidebarOpen.set(true)} aria-label="Open LAMB LEGATUS">LAMB LEGATUS</button>
          <!-- Username, and under it the organization of this session (#562) -->
          <div class="{organizationName ? 'flex' : 'hidden sm:flex'} flex-col items-end min-w-0">
            <span class="text-sm font-medium text-gray-600 hidden sm:block">{$user.name || $user.email || ''}</span>
            {#if organizationName}
              {@const organizationTitle = localeLoaded ? $_('ltiSession.organization', { values: { name: organizationName }, default: 'Organization: {name}' }) : `Organization: ${organizationName}`}
              {#if canSwitchOrganization}
                {@const changeLabel = localeLoaded ? $_('ltiSession.switchOrganization', { default: 'Change organization' }) : 'Change organization'}
                <!-- Narrow screens: the menu spans the page width; from sm up it hangs from the button -->
                <div class="org-menu max-w-[min(100%,9rem)] sm:relative sm:max-w-[min(100%,14rem)]">
                  <button
                    type="button"
                    data-organization-switcher
                    onclick={() => { orgMenuOpen = !orgMenuOpen; switchError = ''; }}
                    class="inline-flex max-w-full items-center gap-1 rounded border border-gray-300 bg-white px-1.5 py-0.5 text-xs font-medium text-[#173f64] hover:bg-gray-50"
                    title={organizationTitle}
                    aria-haspopup="true"
                    aria-expanded={orgMenuOpen}
                  >
                    <span class="truncate">{organizationName}</span>
                    <span class="sr-only">{changeLabel}</span>
                    <svg class="h-3 w-3 flex-shrink-0 transition-transform duration-200 {orgMenuOpen ? 'rotate-180' : ''}" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>
                    </svg>
                  </button>
                  {#if orgMenuOpen}
                    <div data-organization-menu class="absolute left-4 right-4 z-50 mt-1 rounded-md border border-gray-200 bg-white py-1 shadow-lg sm:left-auto sm:right-0 sm:w-64">
                      <p class="px-3 py-1 text-xs font-semibold text-gray-500">{changeLabel}</p>
                      <ul>
                        {#each ltiOrganizations as account (account.creator_user_id)}
                          <li>
                            <button
                              type="button"
                              onclick={() => switchOrganization(account)}
                              disabled={account.current || switchingTo !== null}
                              aria-current={account.current ? 'true' : undefined}
                              class="flex w-full items-center gap-2 px-3 py-2 text-left text-sm {account.current ? 'font-semibold text-[#173f64]' : switchingTo !== null ? 'text-gray-400' : 'text-gray-700 hover:bg-gray-50 hover:text-[#2271b3]'}"
                            >
                              <span class="w-4 flex-shrink-0 text-center" aria-hidden="true">{account.current ? '✓' : ''}</span>
                              <span class="min-w-0 flex-1 break-words">{account.organization_name || `#${account.organization_id}`}</span>
                              {#if account.current}
                                <span class="flex-shrink-0 text-xs font-normal text-gray-500">{localeLoaded ? $_('ltiSession.current', { default: 'current' }) : 'current'}</span>
                              {/if}
                            </button>
                          </li>
                        {/each}
                      </ul>
                      {#if switchingTo !== null}
                        <p role="status" class="border-t border-gray-100 px-3 py-2 text-xs text-gray-500">{localeLoaded ? $_('ltiSession.switching', { default: 'Changing organization...' }) : 'Changing organization...'}</p>
                      {/if}
                      {#if switchError}
                        <p role="alert" class="border-t border-gray-100 px-3 py-2 text-xs text-red-700">{switchError}</p>
                      {/if}
                    </div>
                  {/if}
                </div>
              {:else}
                <span data-organization-name class="block max-w-[min(100%,9rem)] sm:max-w-[min(100%,14rem)] truncate text-xs text-gray-500" title={organizationTitle}>{organizationName}</span>
              {/if}
            {/if}
          </div>
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
