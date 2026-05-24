<!--
  @component StepKSContent
  Step 4 of the 5-step wizard.
  Multi-select picker over the chosen library's "ready" items. ALL items
  are pre-selected by default. Skippable.

  For the NEW-library path: files/URLs queued in Step 2 don't exist in
  the library yet (uploads happen in Step 5 / Review). This step shows
  a checklist of those pending items so the user can uncheck the ones
  they do NOT want ingested. All are pre-selected. IDs take the form
  `pendingFile_<i>` / `pendingUrl_<i>` — Review maps these back to the
  real uploaded item IDs.

  Phase C consistency contract:
    * Native checkboxes replaced by the `<Checkbox>` primitive.
    * `max-h-72` bumped to `max-h-96`.
    * Items grouped into two labeled sections ("From this library" /
      "New uploads in this wizard") with per-section "Select all".
    * NEW pill rendered via `<Badge variant="info" size="sm">`.
    * `text-gray-400` → `text-text-muted`.

  Emits:
    - update: { selectedItemIds }
    - validity: { valid: boolean }
-->
<script>
	import { createEventDispatcher } from 'svelte';
	import { SvelteSet } from 'svelte/reactivity';
	import { getItems } from '$lib/services/libraryService';
	import { _ } from '$lib/i18n';
	import { Checkbox, Badge, Banner } from '$lib/components/ui';

	/** @type {{ wizardState: any }} */
	let { wizardState } = $props();

	const dispatch = createEventDispatcher();

	let items = $state(/** @type {any[]} */ ([]));
	// eslint-disable-next-line svelte/no-unnecessary-state-wrap
	let selectedIds = $state(new SvelteSet(wizardState.selectedItemIds || []));
	let didPreselect = $state(
		!!wizardState.selectionInitialized || (wizardState.selectedItemIds || []).length > 0
	);
	let loading = $state(false);
	let error = $state('');
	let isNewLibrary = $derived(wizardState.libraryPath === 'new');

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

	let loadSeq = 0;

	/** @param {string} libraryId */
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

	/** Toggle every selectable id in a given section. */
	/** @param {string[]} sectionIds */
	function toggleSection(sectionIds) {
		const allInSection = sectionIds.every((id) => selectedIds.has(id));
		const next = new SvelteSet(selectedIds);
		if (allInSection) {
			for (const id of sectionIds) next.delete(id);
		} else {
			for (const id of sectionIds) next.add(id);
		}
		selectedIds = next;
		didPreselect = true;
		dispatch('update', { selectionInitialized: true });
	}

	$effect(() => {
		dispatch('validity', { valid: true });
		dispatch('update', { selectedItemIds: [...selectedIds] });
	});

	let existingRows = $derived(
		isNewLibrary
			? []
			: items.map((/** @type {any} */ i) => ({
					id: i.id,
					label: i.title,
					detail: `${i.source_type} · ${i.id}`,
					isNew: false
				}))
	);
	let pendingRows = $derived(
		pendingItems.map((p) => ({
			id: p.id,
			label: p.label,
			detail: p.detail,
			isNew: true
		}))
	);
	let totalRows = $derived(existingRows.length + pendingRows.length);
	let existingAllChecked = $derived(
		existingRows.length > 0 &&
			existingRows.every((/** @type {{ id: string }} */ r) => selectedIds.has(r.id))
	);
	let pendingAllChecked = $derived(
		pendingRows.length > 0 &&
			pendingRows.every((/** @type {{ id: string }} */ r) => selectedIds.has(r.id))
	);
</script>

<div class="space-y-4">
	<h3 class="type-section-title">
		{$_('knowledge.wizard.step7.heading', { default: 'Pick items to ingest' })}
	</h3>
	<p class="type-body-muted">
		{$_('knowledge.wizard.step7.description', {
			default:
				'These items will be ingested into the Knowledge Store. All ready items are selected by default.'
		})}
	</p>

	{#if loading && !isNewLibrary}
		<p class="type-body-muted">{$_('common.loading', { default: 'Loading...' })}</p>
	{:else if error && !isNewLibrary}
		<Banner variant="danger" size="sm" description={error} />
	{:else if totalRows === 0}
		<p class="type-body-muted">
			{$_('knowledge.wizard.step7.noItems', {
				default: 'This library has no ready items. You can skip this step and add content later.'
			})}
		</p>
	{:else}
		<div class="type-body-muted text-xs">
			{selectedIds.size} / {totalRows}
			{$_('knowledgeStores.addContentModal.selected', { default: 'selected' })}
		</div>

		<!-- ── Section: From this library ───────────────────────────────── -->
		{#if existingRows.length > 0}
			<div class="border-border bg-surface overflow-hidden rounded-md border">
				<div
					class="border-border bg-surface-muted flex items-center justify-between border-b px-3 py-2"
				>
					<Checkbox
						checked={existingAllChecked}
						onchange={() =>
							toggleSection(existingRows.map((/** @type {{ id: string }} */ r) => r.id))}
						label={$_('knowledge.wizard.ksContent.fromLibrary', {
							default: 'From this library'
						})}
					/>
					<span class="type-caption">{existingRows.length}</span>
				</div>
				<div class="max-h-96 overflow-y-auto">
					{#each existingRows as row (row.id)}
						<label
							class="border-border hover:bg-surface-sunken flex cursor-pointer items-center gap-3 border-b px-3 py-2 last:border-b-0"
						>
							<Checkbox checked={selectedIds.has(row.id)} onchange={() => toggleItem(row.id)} />
							<div class="min-w-0 flex-1">
								<div class="text-text truncate text-sm font-medium">{row.label}</div>
								<div class="text-text-muted truncate text-xs">{row.detail}</div>
							</div>
						</label>
					{/each}
				</div>
			</div>
		{/if}

		<!-- ── Section: New uploads in this wizard ──────────────────────── -->
		{#if pendingRows.length > 0}
			<div class="border-border bg-surface overflow-hidden rounded-md border">
				<div
					class="border-border bg-surface-muted flex items-center justify-between border-b px-3 py-2"
				>
					<Checkbox
						checked={pendingAllChecked}
						onchange={() =>
							toggleSection(pendingRows.map((/** @type {{ id: string }} */ r) => r.id))}
						label={$_('knowledge.wizard.ksContent.newUploads', {
							default: 'New uploads in this wizard'
						})}
					/>
					<span class="type-caption">{pendingRows.length}</span>
				</div>
				<div class="max-h-96 overflow-y-auto">
					{#each pendingRows as row (row.id)}
						<label
							class="border-border hover:bg-surface-sunken flex cursor-pointer items-center gap-3 border-b px-3 py-2 last:border-b-0"
						>
							<Checkbox checked={selectedIds.has(row.id)} onchange={() => toggleItem(row.id)} />
							<div class="min-w-0 flex-1">
								<div class="flex items-center gap-2">
									<span class="text-text truncate text-sm font-medium">{row.label}</span>
									<Badge variant="info" size="sm">
										{$_('knowledge.wizard.step7.newBadge', { default: 'NEW' })}
									</Badge>
								</div>
								<div class="text-text-muted truncate text-xs">{row.detail}</div>
							</div>
						</label>
					{/each}
				</div>
			</div>
		{/if}
	{/if}
</div>
