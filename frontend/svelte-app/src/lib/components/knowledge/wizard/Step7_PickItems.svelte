<!--
  @component Step7_PickItems
  Multi-select picker over the chosen library's "ready" items. ALL items
  are pre-selected by default. Skippable.

  Note: when a NEW library is being created, files have been collected in
  Step 3 but not yet uploaded — those uploads happen in Step 8. So in the
  new-library path, this list will only show pre-existing items in the
  library if any exist (typically empty for a fresh library). The freshly
  uploaded items will be picked up automatically in Step 8.

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
		if (selectedIds.size === items.length) {
			selectedIds = new SvelteSet();
		} else {
			selectedIds = new SvelteSet(items.map((i) => i.id));
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
		<div class="rounded-md border border-blue-200 bg-blue-50 p-3 text-sm text-blue-800">
			{$_('knowledge.wizard.step7.newLibraryNote', {
				default:
					'You are creating a new Library. Any files you added in the previous step will be uploaded and automatically queued for ingestion when you click "Create".'
			})}
		</div>
		{#if (wizardState.pendingFiles ?? []).length > 0}
			<div class="text-sm text-gray-700">
				{$_('knowledge.wizard.step7.pendingCount', {
					default: '{n} file(s) ready to upload',
					values: { n: wizardState.pendingFiles.length }
				})}
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
