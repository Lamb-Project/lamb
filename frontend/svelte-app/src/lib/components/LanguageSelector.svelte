<script>
  // Remove onMount import
  // import { onMount } from 'svelte'; 
  import { locale } from 'svelte-i18n';
  import { setLocale } from '$lib/i18n';
  import { browser } from '$app/environment'; // Import browser check

  /** @type {{ size?: 'normal' | 'small' }} */
  let { size = 'normal' } = $props();

  let open = $state(false);
  let currentLang = $state('en');

  // Subscribe to locale changes directly using reactive $locale
  $effect(() => {
    if ($locale) { // Ensure value is not null/undefined initially
      currentLang = $locale;
    }
  });
  
  /** @param {MouseEvent} event */
  function handleClickOutside(event) {
    if (open && event.target instanceof Element && !event.target.closest('.lang-selector')) {
      open = false;
    }
  }
  
  /** @param {string} lang */
  function changeLanguage(lang) {
    setLocale(lang);
    open = false;
  }
  
  // Use $effect for adding/removing the global listener
  $effect(() => {
    if (!browser) return; // Only run in browser
    
    /** @param {MouseEvent} e */
    const handler = (e) => handleClickOutside(e);
    
    // Add listener
    window.addEventListener('click', handler, true);
    
    // Return a cleanup function to remove the listener
    return () => {
      window.removeEventListener('click', handler, true);
    };
  });
</script>

<div class="lang-selector relative">
  <button 
    onclick={() => open = !open}
    class="inline-flex items-center border border-gray-300 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 {size === 'small' ? 'px-1.5 py-0.5 text-xs' : 'px-3 py-1 text-sm'}"
    aria-haspopup="true"
    aria-expanded={open}
  >
    {currentLang?.toUpperCase() ?? ''} 
    <svg class="{size === 'small' ? 'ml-0.5 h-3 w-3' : 'ml-1 h-4 w-4'}" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
      <path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clip-rule="evenodd" />
    </svg>
  </button>
  
  {#if open}
    <div 
        class="origin-top-right absolute right-0 mt-2 w-24 rounded-md shadow-lg bg-white ring-1 ring-black ring-opacity-5 z-10 focus:outline-none"
        role="menu" 
        aria-orientation="vertical" 
        aria-labelledby="language-menu-button" 
        tabindex="-1"
    >
      <div class="py-1" role="none">
        <!-- Active: "bg-gray-100 text-gray-900", Not Active: "text-gray-700" -->
        <button 
          onclick={() => changeLanguage('en')}
          class={`block w-full text-left px-4 py-2 text-sm ${currentLang === 'en' ? 'bg-gray-100 text-gray-900' : 'text-gray-700 hover:bg-gray-100'}`}
          role="menuitem" tabindex="-1" id="language-menu-item-0"
        >
          EN
        </button>
        <button 
          onclick={() => changeLanguage('es')}
          class={`block w-full text-left px-4 py-2 text-sm ${currentLang === 'es' ? 'bg-gray-100 text-gray-900' : 'text-gray-700 hover:bg-gray-100'}`}
           role="menuitem" tabindex="-1" id="language-menu-item-1"
        >
          ES
        </button>
        <button 
          onclick={() => changeLanguage('ca')}
          class={`block w-full text-left px-4 py-2 text-sm ${currentLang === 'ca' ? 'bg-gray-100 text-gray-900' : 'text-gray-700 hover:bg-gray-100'}`}
           role="menuitem" tabindex="-1" id="language-menu-item-2"
        >
          CA
        </button>
        <button 
          onclick={() => changeLanguage('eu')}
          class={`block w-full text-left px-4 py-2 text-sm ${currentLang === 'eu' ? 'bg-gray-100 text-gray-900' : 'text-gray-700 hover:bg-gray-100'}`}
           role="menuitem" tabindex="-1" id="language-menu-item-3"
        >
          EU
        </button>
      </div>
    </div>
  {/if}
</div> 