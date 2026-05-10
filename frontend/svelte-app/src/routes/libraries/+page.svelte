<!--
  @component Knowledge page (route: /libraries)
  Hosts both Libraries and Knowledge Stores under a single "Knowledge"
  page with sub-tabs. The unified Create-Knowledge wizard is the primary
  creation entry point.

  URL state machine:
    /libraries                                          → section=libraries, view=list  (default)
    /libraries?view=detail&id=X                         → section=libraries, view=detail (back-compat)
    /libraries?section=libraries                        → section=libraries, view=list
    /libraries?section=libraries&view=detail&id=X       → section=libraries, view=detail
    /libraries?section=knowledge-stores                 → section=knowledge-stores, view=list
    /libraries?section=knowledge-stores&view=detail&id=X → section=knowledge-stores, view=detail
-->
<script>
	import LibrariesList from '$lib/components/libraries/LibrariesList.svelte';
	import LibraryDetail from '$lib/components/libraries/LibraryDetail.svelte';
	import KnowledgeStoresList from '$lib/components/knowledgeStores/KnowledgeStoresList.svelte';
	import KnowledgeStoreDetail from '$lib/components/knowledgeStores/KnowledgeStoreDetail.svelte';
	import CreateKnowledgeWizard from '$lib/components/knowledge/CreateKnowledgeWizard.svelte';
	import { _ } from '$lib/i18n';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { base } from '$app/paths';
	import { onMount } from 'svelte';
	import { SvelteURLSearchParams } from 'svelte/reactivity';

	/** @type {'libraries'|'knowledge-stores'} */
	let section = $state('libraries');
	/** @type {'list'|'detail'} */
	let view = $state('list');
	let detailId = $state('');

	let wizardOpen = $state(false);
	/** @type {Record<string, any> | null} */
	let wizardInitialState = $state(null);

	// Bumped to force the list components to remount/refresh after a
	// wizard creates new entities. Each list mounts/loads on creation,
	// so re-keying triggers a fresh load.
	let librariesListKey = $state(0);
	let ksListKey = $state(0);

	onMount(() => {
		updateStateFromUrl();
	});

	function updateStateFromUrl() {
		const params = $page.url.searchParams;
		const s = params.get('section');
		const v = params.get('view');
		const id = params.get('id');

		section = s === 'knowledge-stores' ? 'knowledge-stores' : 'libraries';
		view = v === 'detail' && id ? 'detail' : 'list';
		detailId = view === 'detail' ? id || '' : '';
	}

	$effect(() => {
		if ($page.url) updateStateFromUrl();
	});

	/**
	 * @param {string} nextSection
	 * @param {string} [nextView]
	 * @param {string} [nextId]
	 */
	function buildUrl(nextSection, nextView, nextId) {
		const params = new SvelteURLSearchParams();
		// Always emit section so URLs are explicit going forward.
		params.set('section', nextSection);
		if (nextView === 'detail' && nextId) {
			params.set('view', 'detail');
			params.set('id', nextId);
		}
		const qs = params.toString();
		return `${base}/libraries${qs ? `?${qs}` : ''}`;
	}

	/** @param {string} nextSection */
	function switchSection(nextSection) {
		if (section === nextSection && view === 'list') return;
		// eslint-disable-next-line svelte/no-navigation-without-resolve
		goto(buildUrl(nextSection, 'list'), { replaceState: false, keepFocus: true });
	}

	/** @param {CustomEvent<{id: string}>} event */
	function handleLibraryView(event) {
		// eslint-disable-next-line svelte/no-navigation-without-resolve
		goto(buildUrl('libraries', 'detail', event.detail.id), {
			replaceState: false,
			keepFocus: true
		});
	}

	/** @param {CustomEvent<{id: string}>} event */
	function handleKsView(event) {
		// eslint-disable-next-line svelte/no-navigation-without-resolve
		goto(buildUrl('knowledge-stores', 'detail', event.detail.id), {
			replaceState: false,
			keepFocus: true
		});
	}

	function backToList() {
		// eslint-disable-next-line svelte/no-navigation-without-resolve
		goto(buildUrl(section, 'list'), { replaceState: false, keepFocus: true });
	}

	function openWizard() {
		wizardInitialState = null;
		wizardOpen = true;
	}

	/**
	 * @param {Record<string, any>} state
	 */
	function openWizardWithState(state) {
		wizardInitialState = state;
		wizardOpen = true;
	}

	function closeWizard() {
		wizardOpen = false;
		wizardInitialState = null;
	}

	/** @param {CustomEvent<Record<string, any>>} event */
	function handleCreateWithInitialState(event) {
		openWizardWithState(event.detail || {});
	}

	/** @param {CustomEvent<Record<string, any>>} event */
	function handleWizardDone(event) {
		const refs = event.detail || {};
		// Refresh both lists regardless of which side the wizard touched.
		librariesListKey += 1;
		ksListKey += 1;

		// Honour the user's choice from Step 9 ("Open Knowledge Store" vs
		// "Open Library"). The Done step embeds ``target: 'ks' | 'library'``
		// in the dispatched payload. Fall back to whichever side has an
		// id when no explicit target is set.
		const target = refs.target;
		if (target === 'library' && refs.libraryId) {
			// eslint-disable-next-line svelte/no-navigation-without-resolve
			goto(buildUrl('libraries', 'detail', refs.libraryId), {
				replaceState: false,
				keepFocus: true
			});
			return;
		}
		if (target === 'ks' && refs.ksId) {
			// eslint-disable-next-line svelte/no-navigation-without-resolve
			goto(buildUrl('knowledge-stores', 'detail', refs.ksId), {
				replaceState: false,
				keepFocus: true
			});
			return;
		}
		if (refs.ksId) {
			// eslint-disable-next-line svelte/no-navigation-without-resolve
			goto(buildUrl('knowledge-stores', 'detail', refs.ksId), {
				replaceState: false,
				keepFocus: true
			});
		} else if (refs.libraryId) {
			// eslint-disable-next-line svelte/no-navigation-without-resolve
			goto(buildUrl('libraries', 'detail', refs.libraryId), {
				replaceState: false,
				keepFocus: true
			});
		}
	}
</script>

<div class="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
	<div class="border-b border-gray-200 pb-5">
		{#if view === 'detail' && detailId}
			<div class="flex items-center">
				<button
					type="button"
					onclick={backToList}
					aria-label={section === 'knowledge-stores'
						? $_('knowledgeStores.backButton', { default: 'Back to Knowledge Stores' })
						: $_('libraries.backButton', { default: 'Back to libraries' })}
					class="mr-3 inline-flex items-center rounded-full border border-transparent bg-[#2271b3] p-1 text-white shadow-sm hover:bg-[#195a91] focus:ring-2 focus:ring-[#2271b3] focus:ring-offset-2 focus:outline-none"
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
				<h1
					class="text-2xl leading-tight font-bold text-gray-900 sm:truncate sm:text-3xl sm:leading-tight"
				>
					{#if section === 'knowledge-stores'}
						{$_('knowledgeStores.detailTitle', { default: 'Knowledge Store Details' })}
					{:else}
						{$_('libraries.detailTitle', { default: 'Library Details' })}
					{/if}
				</h1>
			</div>
		{:else}
			<div>
				<h1 class="text-2xl leading-tight font-bold text-gray-900 sm:text-3xl sm:leading-tight">
					{$_('knowledge.title', { default: 'Sources of Knowledge' })}
				</h1>
				<p class="mt-1 text-sm text-gray-500">
					{#if section === 'knowledge-stores'}
						{$_('knowledgeStores.pageDescription', {
							default: 'Manage Knowledge Stores — vector indexes built from library content.'
						})}
					{:else}
						{$_('libraries.pageDescription', {
							default: 'Manage your document libraries.'
						})}
					{/if}
				</p>
			</div>

			<div class="mt-4 flex gap-6 border-b border-transparent">
				<button
					type="button"
					onclick={() => switchSection('libraries')}
					class="-mb-px border-b-2 pb-2 text-sm font-medium {section === 'libraries'
						? 'border-[#2271b3] text-[#2271b3]'
						: 'border-transparent text-gray-500 hover:text-gray-700'}"
				>
					{$_('libraries.pageTitle', { default: 'Libraries' })}
				</button>
				<button
					type="button"
					onclick={() => switchSection('knowledge-stores')}
					class="-mb-px border-b-2 pb-2 text-sm font-medium {section === 'knowledge-stores'
						? 'border-[#2271b3] text-[#2271b3]'
						: 'border-transparent text-gray-500 hover:text-gray-700'}"
				>
					{$_('knowledgeStores.pageTitle', { default: 'Knowledge Stores' })}
				</button>
			</div>
		{/if}
	</div>

	<div class="mt-6">
		{#if section === 'libraries'}
			{#if view === 'detail' && detailId}
				<LibraryDetail libraryId={detailId} />
			{:else}
				{#key librariesListKey}
					<LibrariesList on:view={handleLibraryView} />
				{/key}
			{/if}
		{:else if section === 'knowledge-stores'}
			{#if view === 'detail' && detailId}
				<KnowledgeStoreDetail ksId={detailId} />
			{:else}
				{#key ksListKey}
					<KnowledgeStoresList
						on:view={handleKsView}
						on:createWithInitialState={handleCreateWithInitialState}
					/>
				{/key}
			{/if}
		{/if}
	</div>
</div>

<svelte:window
	onkeydown={(e) => {
		if (wizardOpen && e.key === 'Escape') closeWizard();
	}}
/>

{#if wizardOpen}
	<CreateKnowledgeWizard
		onclose={closeWizard}
		on:done={handleWizardDone}
		initialState={wizardInitialState}
	/>
{/if}
