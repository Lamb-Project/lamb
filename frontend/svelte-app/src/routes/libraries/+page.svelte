<!--
  @component Libraries page
  Top-level route for library management. Switches between list and detail
  views based on URL query params (?view=detail&id=...).
-->
<script>
    import LibrariesList from '$lib/components/libraries/LibrariesList.svelte';
    import LibraryDetail from '$lib/components/libraries/LibraryDetail.svelte';
    import { _ } from '$lib/i18n';
    import { page } from '$app/stores';
    import { goto } from '$app/navigation';
    import { base } from '$app/paths';
    import { onMount } from 'svelte';

    let view = $state('list');
    let libraryId = $state('');

    onMount(() => { updateStateFromUrl(); });

    function updateStateFromUrl() {
        const params = $page.url.searchParams;
        const v = params.get('view');
        const id = params.get('id');
        view = (v === 'detail' && id) ? 'detail' : 'list';
        libraryId = view === 'detail' ? id || '' : '';
    }

    $effect(() => {
        if ($page.url) updateStateFromUrl();
    });

    function handleView(event) {
        goto(`${base}/libraries?view=detail&id=${event.detail.id}`, {
            replaceState: false,
            keepFocus: true,
        });
    }

    function backToList() {
        goto(`${base}/libraries`, { replaceState: false, keepFocus: true });
    }
</script>

<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
    <div class="pb-5 border-b border-gray-200">
        {#if view === 'detail' && libraryId}
            <div class="flex items-center">
                <button
                    type="button"
                    onclick={backToList}
                    aria-label={$_('libraries.backButton', { default: 'Back to libraries' })}
                    class="mr-3 inline-flex items-center p-1 border border-transparent rounded-full shadow-sm text-white bg-[#2271b3] hover:bg-[#195a91] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#2271b3]"
                >
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                        <path fill-rule="evenodd" d="M9.707 16.707a1 1 0 01-1.414 0l-6-6a1 1 0 010-1.414l6-6a1 1 0 011.414 1.414L5.414 9H17a1 1 0 110 2H5.414l4.293 4.293a1 1 0 010 1.414z" clip-rule="evenodd" />
                    </svg>
                </button>
                <h1 class="text-2xl font-bold leading-7 text-gray-900 sm:text-3xl sm:truncate">
                    {$_('libraries.detailTitle', { default: 'Library Details' })}
                </h1>
            </div>
        {:else}
            <h1 class="text-2xl font-bold leading-7 text-gray-900 sm:text-3xl sm:truncate">
                {$_('libraries.pageTitle', { default: 'Libraries' })}
            </h1>
            <p class="mt-1 text-sm text-gray-500">
                {$_('libraries.pageDescription', { default: 'Manage your document libraries.' })}
            </p>
        {/if}
    </div>

    <div class="mt-6">
        {#if view === 'detail' && libraryId}
            <LibraryDetail {libraryId} />
        {:else}
            <LibrariesList on:view={handleView} />
        {/if}
    </div>
</div>
