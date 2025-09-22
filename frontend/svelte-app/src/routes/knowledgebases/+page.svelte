<script>
	import KnowledgeBasesList from '$lib/components/KnowledgeBasesList.svelte';
	import KnowledgeBaseDetail from '$lib/components/KnowledgeBaseDetail.svelte';
	import { _ } from '$lib/i18n';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { base } from '$app/paths';
	import { onMount } from 'svelte';

	// Page state using Svelte 5 runes
	let view = $state('list');
	let kbId = $state('');

	// Debug logging
	onMount(() => {
		console.log('KnowledgeBases page mounted');
		// Initialize state from URL on mount
		updateStateFromUrl();
	});

	// Function to update state based on URL params
	function updateStateFromUrl() {
		const params = $page.url.searchParams;
		const currentView = params.get('view');
		const currentId = params.get('id');

		view = currentView === 'detail' && currentId ? 'detail' : 'list';
		kbId = view === 'detail' ? currentId || '' : '';

		console.log('State updated from URL - view:', view, 'kbId:', kbId);
	}

	// Update state whenever URL changes
	$effect(() => {
		// Rerun state update logic when page store changes
		if ($page.url) {
			updateStateFromUrl();
		}
	});

	/**
	 * Handle view event from KnowledgeBasesList
	 * @param {CustomEvent<{id: string}>} event - The view event with KB ID
	 */
	function handleView(event) {
		const id = event.detail.id;
		console.log('View event received for KB:', id);

		// Use goto to navigate, let the $effect handle state update
		goto(`${base}/knowledgebases?view=detail&id=${id}`, {
			replaceState: false, // Add to browser history
			keepFocus: true
		});
	}

	/**
	 * Return to the list view
	 */
	function backToList() {
		console.log('Back to list called');

		// Use goto to navigate, let the $effect handle state update
		goto(`${base}/knowledgebases`, {
			replaceState: false, // Add to browser history
			keepFocus: true
		});
	}
</script>

<div class="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
	<div class="border-b border-gray-200 pb-5">
		{#if view === 'detail' && kbId}
			<div class="flex items-center">
				<button
					type="button"
					onclick={backToList}
					aria-label={$_('knowledgeBases.backButton', { default: 'Back to knowledge bases list' })}
					class="mr-3 inline-flex items-center rounded-full border border-transparent bg-[#2271b3] p-1 text-white shadow-sm hover:bg-[#195a91] focus:ring-2 focus:ring-[#2271b3] focus:ring-offset-2 focus:outline-none"
					style="background-color: #2271b3;"
				>
					<svg
						xmlns="http://www.w3.org/2000/svg"
						class="h-5 w-5"
						viewBox="0 0 20 20"
						fill="currentColor"
					>
						<path
							fill-rule="evenodd"
							d="M9.707 16.707a1 1 0 01-1.414 0l-6-6a1 1 0 010-1.414l6-6a1 1 0 011.414 1.414L5.414 9H17a1 1 0 110 2H5.414l4.293 4.293a1 1 0 010 1.414z"
							clip-rule="evenodd"
						/>
					</svg>
				</button>
				<h1 class="text-2xl leading-7 font-bold text-gray-900 sm:truncate sm:text-3xl">
					{$_('knowledgeBases.detailTitle', { default: 'Knowledge Base Details' })}
				</h1>
			</div>
			<p class="mt-1 text-sm text-gray-500">
				{$_('knowledgeBases.detailDescription', {
					default: 'View details and manage files for this knowledge base.'
				})}
			</p>
		{:else}
			<h1 class="text-2xl leading-7 font-bold text-gray-900 sm:truncate sm:text-3xl">
				{$_('knowledgeBases.pageTitle', { default: 'Knowledge Bases' })}
			</h1>
			<p class="mt-1 text-sm text-gray-500">
				{$_('knowledgeBases.pageDescription', {
					default: 'Manage your knowledge bases for use with learning assistants.'
				})}
			</p>
		{/if}
	</div>

	<div class="mt-6">
		{#if view === 'detail' && kbId}
			<!-- Debug info -->
			<!-- <div class="mb-4 p-2 bg-gray-100 text-xs">Debug: view={view}, kbId={kbId}</div> -->
			<KnowledgeBaseDetail {kbId} />
		{:else}
			<KnowledgeBasesList on:view={handleView} />
		{/if}
	</div>
</div>
