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
	import { Button, Tabs } from '$lib/components/ui';
	import { ChevronLeft } from 'lucide-svelte';

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

	let sectionTabs = $derived([
		{ value: 'libraries', label: $_('libraries.pageTitle', { default: 'Libraries' }) },
		{
			value: 'knowledge-stores',
			label: $_('knowledgeStores.pageTitle', { default: 'Knowledge Stores' })
		}
	]);

	/** @param {string} v */
	function handleTabChange(v) {
		switchSection(v);
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

<div class="mx-auto max-w-7xl px-4 pt-6 pb-0 sm:px-6 lg:px-8">
	<div class="border-border border-b pb-5">
		{#if view === 'detail' && detailId}
			<div class="flex items-center gap-2">
				<Button
					variant="ghost"
					size="sm"
					iconLeftComponent={ChevronLeft}
					ariaLabel={section === 'knowledge-stores'
						? $_('knowledgeStores.backButton', { default: 'Back to Knowledge Stores' })
						: $_('libraries.backButton', { default: 'Back to libraries' })}
					onclick={backToList}
				>
					{$_('common.back', { default: 'Back' })}
				</Button>
				<h1 class="type-page-title min-w-0 flex-1 truncate">
					{#if section === 'knowledge-stores'}
						{$_('knowledgeStores.detailTitle', { default: 'Knowledge Store Details' })}
					{:else}
						{$_('libraries.detailTitle', { default: 'Library Details' })}
					{/if}
				</h1>
			</div>
		{:else}
			<div>
				<h1 class="type-page-title">
					{$_('knowledge.title', { default: 'Sources of Knowledge' })}
				</h1>
				<p class="type-body-muted mt-1">
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

			<div class="mt-4">
				<Tabs tabs={sectionTabs} value={section} onchange={handleTabChange} />
			</div>
		{/if}
	</div>

	<main class="mt-6">
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
	</main>
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
