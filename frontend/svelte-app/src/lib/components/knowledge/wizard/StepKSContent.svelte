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
	// Wrap in $state so reassignment (e.g. `selectedIds = new SvelteSet()` for
	// Select all / Deselect all) triggers reactive re-renders. Without $state,
	// only in-place mutations would be tracked and the toggle button would
	// appear inert.
	// eslint-disable-next-line svelte/no-unnecessary-state-wrap
	let selectedIds = $state(new SvelteSet(wizardState.selectedItemIds || []));
	// Tracks whether the one-time "select everything by default" pass has run.
	// Persisted in wizardState so navigating Back/Next doesn't re-run the
	// pre-select pass and clobber an explicit Deselect all from the user.
	let didPreselect = $state(
		!!wizardState.selectionInitialized || (wizardState.selectedItemIds || []).length > 0
	);
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

	// Pre-select all pending items the first time this step renders with
	// queued content (works for both new and existing-library flows).
	// Guarded by didPreselect so an explicit Deselect-all from the user
	// is preserved instead of getting auto-reverted on remount.
	$effect(() => {
		if (pendingItems.length > 0 && !didPreselect) {
			const next = new SvelteSet([...selectedIds, ...pendingItems.map((p) => p.id)]);
			selectedIds = next;
			didPreselect = true;
			dispatch('update', { selectionInitialized: true });
		}
	});

	$effect(() => {
		if (wizardState.libraryPath === 'existing' && wizardState.existingLibraryId) {
			loadItems(wizardState.existingLibraryId);
		}
	});

	// Race guard for rapid library switches (#370).
	let loadSeq = 0;

	/**
	 * Load "ready" items for a library, dropping stale responses if a newer
	 * load was issued before this one resolved. Pre-selects everything on
	 * first visit; preserves the user's explicit selection otherwise.
	 * @param {string} libraryId
	 */
	async function loadItems(libraryId) {
		const mySeq = ++loadSeq;
		loading = true;
		error = '';
		try {
			const data = await getItems(libraryId, { limit: 200, status: 'ready' });
			if (mySeq !== loadSeq) return;
			items = data?.items ?? [];
			if (selectedIds.size === 0 && !wizardState.selectionInitialized) {
				selectedIds = new SvelteSet(items.map((i) => i.id));
				dispatch('update', { selectionInitialized: true });
			}
		} catch (/** @type {unknown} */ err) {
			if (mySeq !== loadSeq) return;
			error = err instanceof Error ? err.message : 'Failed to load items';
		} finally {
			if (mySeq === loadSeq) loading = false;
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
		didPreselect = true;
		dispatch('update', { selectionInitialized: true });
	}

	function toggleAll() {
		const allIds = [
			...(isNewLibrary ? [] : items.map((i) => i.id)),
			...pendingItems.map((p) => p.id)
		];
		if (selectedIds.size === allIds.length) {
			selectedIds = new SvelteSet();
		} else {
			selectedIds = new SvelteSet(allIds);
		}
		didPreselect = true;
		dispatch('update', { selectionInitialized: true });
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

	{#if loading && !isNewLibrary}
		<div class="text-sm text-gray-500">{$_('common.loading', { default: 'Loading...' })}</div>
	{:else if error && !isNewLibrary}
		<div class="rounded border border-red-100 bg-red-50 p-3 text-sm text-red-700" role="alert">
			{error}
		</div>
	{:else}
		{@const existingRows = isNewLibrary
			? []
			: items.map((i) => ({
					id: i.id,
					label: i.title,
					detail: `${i.source_type} · ${i.id}`,
					isNew: false
				}))}
		{@const pendingRows = pendingItems.map((p) => ({
			id: p.id,
			label: p.label,
			detail: p.detail,
			isNew: true
		}))}
		{@const allRows = [...existingRows, ...pendingRows]}

		{#if allRows.length === 0}
			<div class="text-sm text-gray-500">
				{$_('knowledge.wizard.step7.noItems', {
					default: 'This library has no ready items. You can skip this step and add content later.'
				})}
			</div>
		{:else}
			<div class="flex items-center justify-between">
				<span class="text-sm text-gray-700">
					{selectedIds.size} / {allRows.length}
					{$_('knowledgeStores.addContentModal.selected', { default: 'selected' })}
				</span>
				<button type="button" onclick={toggleAll} class="text-xs text-[#2271b3] hover:underline">
					{selectedIds.size === allRows.length
						? $_('knowledgeStores.addContentModal.deselectAll', { default: 'Deselect all' })
						: $_('knowledgeStores.addContentModal.selectAll', { default: 'Select all' })}
				</button>
			</div>

			<div class="max-h-72 overflow-y-auto rounded border border-gray-200">
				{#each allRows as row (row.id)}
					<label
						class="flex cursor-pointer items-center gap-3 border-b border-gray-100 px-3 py-2 hover:bg-gray-50"
					>
						<input
							type="checkbox"
							checked={selectedIds.has(row.id)}
							onchange={() => toggleItem(row.id)}
						/>
						<div class="min-w-0 flex-1">
							<div class="flex items-center gap-2">
								<span class="truncate text-sm font-medium text-gray-900">{row.label}</span>
								{#if row.isNew}
									<span
										class="shrink-0 rounded-full bg-blue-100 px-2 py-0.5 text-[10px] font-medium tracking-wide text-blue-800 uppercase"
									>
										{$_('knowledge.wizard.step7.newBadge', { default: 'New' })}
									</span>
								{/if}
							</div>
							<div class="truncate text-xs text-gray-400">{row.detail}</div>
						</div>
					</label>
				{/each}
			</div>
		{/if}
	{/if}
</div>
