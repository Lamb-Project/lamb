<!--
  @component StepKSContent
  Step 4 of the 5-step wizard (renamed from Step7_PickItems).
  Multi-select picker over the chosen library's "ready" items. ALL items
  are pre-selected by default. Skippable.

  For the NEW-library path: files/URLs queued in Step 2 don't exist in
  the library yet (uploads happen in Step 5 / Review). This step shows a
  checklist of those pending items so the user can uncheck the ones they
  do NOT want ingested. All are pre-selected. IDs take the form
  `pendingFile_<i>` / `pendingUrl_<i>` — Review maps these back to the
  real uploaded item IDs.

  Emits:
    - update: { selectedItemIds }
    - validity: { valid: boolean }
-->
<script>
	import { createEventDispatcher } from 'svelte';
	import { SvelteSet } from 'svelte/reactivity';
	import { getItems } from '$lib/services/libraryService';
	import { _ } from '$lib/i18n';

	/** @type {{ wizardState: any }} */
	let { wizardState } = $props();

	const dispatch = createEventDispatcher();

	let items = $state(/** @type {any[]} */ ([]));
	let selectedIds = new SvelteSet(wizardState.selectedItemIds || []);
	let loading = $state(false);
	let error = $state('');
	let isNewLibrary = $derived(wizardState.libraryPath === 'new');

	// Build a flat list of pending items with transient IDs for the new-library path.
	let pendingItems = $derived.by(() => {
		/** @type {Array<{ id: string, label: string, detail: string }>} */
		const result = [];
		const files = wizardState.pendingFiles ?? [];
		const urls = wizardState.pendingUrlSources ?? [];
		for (let i = 0; i < files.length; i++) {
			result.push({ id: `pendingFile_${i}`, label: files[i].name, detail: 'file' });
		}
		for (let i = 0; i < urls.length; i++) {
			const src = urls[i];
			result.push({
				id: `pendingUrl_${i}`,
				label: src.title || src.url,
				detail: src.type === 'youtube' ? 'youtube' : 'url'
			});
		}
		return result;
	});

	// Pre-select all pending items when the component first enters the new-library path.
	$effect(() => {
		if (isNewLibrary && pendingItems.length > 0 && selectedIds.size === 0) {
			selectedIds = new SvelteSet(pendingItems.map((p) => p.id));
		}
	});

	$effect(() => {
		if (wizardState.libraryPath === 'existing' && wizardState.existingLibraryId) {
			loadItems(wizardState.existingLibraryId);
		}
	});

	/** @param {string} libraryId */
	async function loadItems(libraryId) {
		loading = true;
		error = '';
		try {
			const data = await getItems(libraryId, { limit: 200, status: 'ready' });
			items = data?.items ?? [];
			// Pre-select all by default if no prior selection.
			if (selectedIds.size === 0) {
				selectedIds = new SvelteSet(items.map((i) => i.id));
			}
		} catch (/** @type {unknown} */ err) {
			error = err instanceof Error ? err.message : 'Failed to load items';
		} finally {
			loading = false;
		}
	}

	/** @param {string} id */
	function toggleItem(id) {
		if (selectedIds.has(id)) {
			selectedIds.delete(id);
		} else {
			selectedIds.add(id);
		}
		selectedIds = new SvelteSet(selectedIds);
	}

	function toggleAll() {
		const allIds = isNewLibrary ? pendingItems.map((p) => p.id) : items.map((i) => i.id);
		if (selectedIds.size === allIds.length) {
			selectedIds = new SvelteSet();
		} else {
			selectedIds = new SvelteSet(allIds);
		}
	}

	$effect(() => {
		// Always valid (skippable).
		dispatch('validity', { valid: true });
		dispatch('update', { selectedItemIds: [...selectedIds] });
	});
</script>

<div class="space-y-4">
	<h3 class="text-base font-semibold text-gray-900">
		{$_('knowledge.wizard.step7.heading', { default: 'Pick items to ingest' })}
	</h3>
	<p class="text-sm text-gray-600">
		{$_('knowledge.wizard.step7.description', {
			default:
				'These items will be ingested into the Knowledge Store. All ready items are selected by default.'
		})}
	</p>

	{#if isNewLibrary}
		{#if pendingItems.length === 0}
			<div class="text-sm text-gray-500">
				{$_('knowledge.wizard.step7.noItems', {
					default: 'This library has no ready items. You can skip this step and add content later.'
				})}
			</div>
		{:else}
			<p class="text-sm text-gray-600">
				{$_('knowledge.wizard.step7.newLibraryPendingNote', {
					default:
						"{files} file(s), {urls} URL/YouTube source(s) will be uploaded to the new Library. By default all are selected for ingestion into the Knowledge Store. Optionally uncheck the ones you don't want in this Knowledge Store.",
					values: {
						files: (wizardState.pendingFiles ?? []).length,
						urls: (wizardState.pendingUrlSources ?? []).length
					}
				})}
			</p>

			<div class="flex items-center justify-between">
				<span class="text-sm text-gray-700">
					{selectedIds.size} / {pendingItems.length}
					{$_('knowledgeStores.addContentModal.selected', { default: 'selected' })}
				</span>
				<button type="button" onclick={toggleAll} class="text-xs text-[#2271b3] hover:underline">
					{selectedIds.size === pendingItems.length
						? $_('knowledgeStores.addContentModal.deselectAll', { default: 'Deselect all' })
						: $_('knowledgeStores.addContentModal.selectAll', { default: 'Select all' })}
				</button>
			</div>

			<div class="max-h-72 overflow-y-auto rounded border border-gray-200">
				{#each pendingItems as pItem (pItem.id)}
					<label
						class="flex cursor-pointer items-center gap-3 border-b border-gray-100 px-3 py-2 hover:bg-gray-50"
					>
						<input
							type="checkbox"
							checked={selectedIds.has(pItem.id)}
							onchange={() => toggleItem(pItem.id)}
						/>
						<div class="min-w-0 flex-1">
							<div class="truncate text-sm font-medium text-gray-900">{pItem.label}</div>
							<div class="truncate text-xs text-gray-400">{pItem.detail}</div>
						</div>
					</label>
				{/each}
			</div>
		{/if}
	{:else if loading}
		<div class="text-sm text-gray-500">{$_('common.loading', { default: 'Loading...' })}</div>
	{:else if error}
		<div class="rounded border border-red-100 bg-red-50 p-3 text-sm text-red-700" role="alert">
			{error}
		</div>
	{:else if items.length === 0}
		<div class="text-sm text-gray-500">
			{$_('knowledge.wizard.step7.noItems', {
				default: 'This library has no ready items. You can skip this step and add content later.'
			})}
		</div>
	{:else}
		<div class="flex items-center justify-between">
			<span class="text-sm text-gray-700">
				{selectedIds.size} / {items.length}
				{$_('knowledgeStores.addContentModal.selected', { default: 'selected' })}
			</span>
			<button type="button" onclick={toggleAll} class="text-xs text-[#2271b3] hover:underline">
				{selectedIds.size === items.length
					? $_('knowledgeStores.addContentModal.deselectAll', { default: 'Deselect all' })
					: $_('knowledgeStores.addContentModal.selectAll', { default: 'Select all' })}
			</button>
		</div>

		<div class="max-h-72 overflow-y-auto rounded border border-gray-200">
			{#each items as item (item.id)}
				<label
					class="flex cursor-pointer items-center gap-3 border-b border-gray-100 px-3 py-2 hover:bg-gray-50"
				>
					<input
						type="checkbox"
						checked={selectedIds.has(item.id)}
						onchange={() => toggleItem(item.id)}
					/>
					<div class="min-w-0 flex-1">
						<div class="truncate text-sm font-medium text-gray-900">{item.title}</div>
						<div class="truncate text-xs text-gray-400">{item.source_type} · {item.id}</div>
					</div>
				</label>
			{/each}
		</div>
	{/if}
</div>
