<!--
  @component AddContentToKSModal
  Three-step modal for adding library items to an existing Knowledge Store.

    Step 1 — Library: list ALL libraries the user can access (including
             empty ones, clearly badged) and pick one as the source.
    Step 2 — Items:   show ready items in the picked library, checkboxes +
             select-all, must pick at least one to advance.
    Step 3 — Review:  list of items about to be ingested + the Add button.

  Draft auto-save uses the shared wizardDraftStore so a closed modal can
  be resumed on the same KS (state: { step, libraryId, itemIds }).

  Phase C consistency contract:
    * Wraps the canonical `<Modal size="lg">`.
    * Step indicator is the same `<Stepper>` primitive as
      CreateKnowledgeWizard — guarantees visual identity.
    * Draft banner uses `<Banner variant="info">`.
    * Footer is Back (ghost, left) + Next/Add (primary, right). The
      redundant Cancel is gone — the modal close button is the only
      cancel affordance.
-->
<script>
	import { createEventDispatcher, tick } from 'svelte';
	import { SvelteSet } from 'svelte/reactivity';
	import { getLibraries, getItems } from '$lib/services/libraryService';
	import { addContent, listContent } from '$lib/services/knowledgeStoreService';
	import {
		saveDraft,
		clearDraft,
		getDraft,
		formatDraftAge
	} from '$lib/stores/wizardDraftStore.svelte.js';
	import { user } from '$lib/stores/userStore';
	import { _ } from '$lib/i18n';
	import { Modal, Stepper, Banner, Button, Badge, Checkbox } from '$lib/components/ui';
	import { FileText, Link as LinkIcon, Youtube } from 'lucide-svelte';

	const dispatch = createEventDispatcher();

	/** @type {{ isOpen: boolean, ksId: string }} */
	let { isOpen = $bindable(false), ksId } = $props();

	// Draft state is scoped per-KS so different Knowledge Stores keep
	// independent in-progress selections.
	let draftKind = $derived(`addContentToKS:${ksId}`);
	let userId = $derived($user?.data?.id || $user?.email || '_anon');

	// ── Wizard step ──────────────────────────────────────────────────
	/** @type {1|2|3} */
	let step = $state(/** @type {1|2|3} */ (1));

	// ── Step 1: libraries ────────────────────────────────────────────
	/** @type {any[]} */
	let libraries = $state([]);
	let selectedLibraryId = $state('');
	let loadingLibs = $state(false);

	// ── Step 2: items ────────────────────────────────────────────────
	/** @type {any[]} */
	let items = $state([]);
	// eslint-disable-next-line svelte/no-unnecessary-state-wrap
	let selectedItemIds = $state(new SvelteSet(/** @type {string[]} */ ([])));
	/** Set of library_item_ids already linked to this KS (any non-failed status). */
	let alreadyLinkedIds = $state(new Set(/** @type {string[]} */ ([])));
	let loadingItems = $state(false);
	let itemsLibraryId = $state(''); // tracks which lib we last loaded items for

	// ── Submit state ─────────────────────────────────────────────────
	let submitting = $state(false);
	let error = $state('');

	// ── Draft resume banner ──────────────────────────────────────────
	let draftBannerVisible = $state(false);
	let draftSavedAt = $state('');

	// Tracks whether the user has taken a deliberate action in the
	// current modal instance. Auto-save is gated on this so opening the
	// modal alone never overwrites the saved draft.
	let userInteracted = $state(false);

	let selectedLibrary = $derived(libraries.find((l) => l.id === selectedLibraryId) || null);

	let stepperSteps = $derived([
		{
			key: 'library',
			label: $_('knowledgeStores.addContentModal.stepLibrary', { default: 'Library' })
		},
		{
			key: 'items',
			label: $_('knowledgeStores.addContentModal.stepItems', { default: 'Items' })
		},
		{
			key: 'review',
			label: $_('knowledgeStores.addContentModal.stepReview', { default: 'Review' })
		}
	]);

	// Completed step keys for the Stepper — same shape the wizard uses.
	let completedSteps = $derived(
		new Set(
			/** @type {string[]} */ (
				[step > 1 ? 'library' : '', step > 2 ? 'items' : ''].filter((k) => k)
			)
		)
	);

	$effect(() => {
		if (!isOpen) return;
		resetState();
		(async () => {
			await loadLibraries();
			const d = getDraft(userId, draftKind);
			if (d?.state && (d.state.libraryId || (d.state.itemIds && d.state.itemIds.length))) {
				draftBannerVisible = true;
				draftSavedAt = d.savedAt || '';
			} else {
				draftBannerVisible = false;
				draftSavedAt = '';
			}
		})();
	});

	$effect(() => {
		if (!isOpen) return;
		const _step = step;
		const _lib = selectedLibraryId;
		const ids = [...selectedItemIds];
		void _step;
		void _lib;
		if (!userInteracted) return;
		saveDraft(userId, draftKind, {
			step: _step,
			libraryId: _lib,
			itemIds: ids
		});
	});

	function markInteracted() {
		if (!userInteracted) userInteracted = true;
	}

	async function loadLibraries() {
		loadingLibs = true;
		error = '';
		try {
			libraries = (await getLibraries()) || [];
		} catch (/** @type {unknown} */ err) {
			error = err instanceof Error ? err.message : 'Failed to load libraries';
		} finally {
			loadingLibs = false;
		}
	}

	async function loadItemsForCurrentLibrary() {
		if (!selectedLibraryId) {
			items = [];
			return;
		}
		if (itemsLibraryId === selectedLibraryId && items.length > 0) return;
		loadingItems = true;
		items = [];
		try {
			const [data, linked] = await Promise.all([
				getItems(selectedLibraryId, { limit: 200 }),
				listContent(ksId).catch(() => [])
			]);
			alreadyLinkedIds = new Set(
				linked
					.filter((/** @type {any} */ l) => l.status !== 'failed')
					.map((/** @type {any} */ l) => l.library_item_id)
			);
			const all = data?.items ?? [];
			items = [
				...all.filter(
					(/** @type {any} */ i) => i.status === 'ready' && !alreadyLinkedIds.has(i.id)
				),
				...all.filter((/** @type {any} */ i) => i.status === 'ready' && alreadyLinkedIds.has(i.id)),
				...all.filter((/** @type {any} */ i) => i.status !== 'ready')
			];
			itemsLibraryId = selectedLibraryId;
			const selectableIds = new Set(
				items
					.filter((/** @type {any} */ i) => i.status === 'ready' && !alreadyLinkedIds.has(i.id))
					.map((/** @type {any} */ i) => i.id)
			);
			const restoredFromDraft = [...selectedItemIds].filter((id) => selectableIds.has(id));
			selectedItemIds = new SvelteSet(
				restoredFromDraft.length > 0 ? restoredFromDraft : selectableIds
			);
		} catch (/** @type {unknown} */ err) {
			error = err instanceof Error ? err.message : 'Failed to load items';
		} finally {
			loadingItems = false;
		}
	}

	async function resumeDraft() {
		const d = getDraft(userId, draftKind);
		if (!d?.state) {
			draftBannerVisible = false;
			return;
		}
		const s = d.state;
		const libExists = libraries.some((l) => l.id === s.libraryId);
		selectedLibraryId = libExists ? s.libraryId : '';
		const restoredIds = Array.isArray(s.itemIds) ? s.itemIds : [];
		selectedItemIds = new SvelteSet(restoredIds);
		markInteracted();
		if (selectedLibraryId) {
			await loadItemsForCurrentLibrary();
		}
		const restoredStep = Number.isInteger(s.step) ? s.step : 1;
		step = /** @type {1|2|3} */ (
			libExists && restoredStep >= 1 && restoredStep <= 3 ? restoredStep : 1
		);
		draftBannerVisible = false;
	}

	function discardDraft() {
		clearDraft(userId, draftKind);
		draftBannerVisible = false;
	}

	/** @param {string} id */
	function selectLibrary(id) {
		selectedLibraryId = id;
		markInteracted();
		if (draftBannerVisible) draftBannerVisible = false;
	}

	/** @param {string} id */
	function toggleItem(id) {
		const next = new SvelteSet(selectedItemIds);
		if (next.has(id)) next.delete(id);
		else next.add(id);
		selectedItemIds = next;
		markInteracted();
	}

	function toggleAllItems() {
		const selectableIds = items
			.filter((i) => i.status === 'ready' && !alreadyLinkedIds.has(i.id))
			.map((i) => i.id);
		if (selectedItemIds.size === selectableIds.length) {
			selectedItemIds = new SvelteSet();
		} else {
			selectedItemIds = new SvelteSet(selectableIds);
		}
		markInteracted();
	}

	async function goNext() {
		error = '';
		if (step === 1) {
			if (!selectedLibraryId) {
				error = $_('knowledgeStores.addContentModal.libraryRequired', {
					default: 'Pick a library to continue.'
				});
				return;
			}
			step = 2;
			markInteracted();
			await loadItemsForCurrentLibrary();
			await tick();
			return;
		}
		if (step === 2) {
			if (selectedItemIds.size === 0) {
				error = $_('knowledgeStores.addContentModal.noItems', {
					default: 'Select at least one item.'
				});
				return;
			}
			step = 3;
			markInteracted();
		}
	}

	function goBack() {
		error = '';
		if (step === 3) step = 2;
		else if (step === 2) step = 1;
		markInteracted();
	}

	/** @param {string} key @param {number} idx */
	function jumpToStep(key, idx) {
		// Stepper jump — only used for already-completed steps. Idx is 0-based.
		const target = idx + 1;
		if (target < 1 || target > 3) return;
		step = /** @type {1|2|3} */ (target);
		markInteracted();
	}

	async function handleSubmit() {
		if (selectedItemIds.size === 0 || !selectedLibraryId) {
			error = $_('knowledgeStores.addContentModal.noItems', {
				default: 'Select at least one item.'
			});
			return;
		}
		submitting = true;
		error = '';
		try {
			const count = selectedItemIds.size;
			const addedItems = [...selectedItemIds].map((id) => {
				const item = items.find((i) => i.id === id);
				return { id, title: item?.title || id };
			});
			await addContent(ksId, {
				libraryId: selectedLibraryId,
				itemIds: [...selectedItemIds]
			});
			clearDraft(userId, draftKind);
			isOpen = false;
			dispatch('done', { count, ksId, items: addedItems });
			resetState();
		} catch (/** @type {unknown} */ err) {
			error = err instanceof Error ? err.message : 'Failed to add content';
		} finally {
			submitting = false;
		}
	}

	function resetState() {
		step = 1;
		selectedLibraryId = '';
		selectedItemIds = new SvelteSet();
		alreadyLinkedIds = new Set();
		items = [];
		itemsLibraryId = '';
		error = '';
		draftBannerVisible = false;
		draftSavedAt = '';
		userInteracted = false;
	}

	function close() {
		if (submitting) return;
		isOpen = false;
		dispatch('close');
	}

	/** @param {any} lib */
	function itemCount(lib) {
		return typeof lib.item_count === 'number' ? lib.item_count : 0;
	}

	/** @param {string} sourceType */
	function sourceTypeIcon(sourceType) {
		switch ((sourceType || '').toLowerCase()) {
			case 'youtube':
				return Youtube;
			case 'url':
				return LinkIcon;
			default:
				return FileText;
		}
	}
</script>

<Modal
	open={isOpen}
	onclose={close}
	size="lg"
	title={$_('knowledgeStores.addContentModal.title', {
		default: 'Add Library Content to Knowledge Store'
	})}
	closeAriaLabel={$_('common.close', { default: 'Close' })}
>
	<!-- eslint-disable-next-line svelte/no-useless-children-snippet -->
	{#snippet children()}
		<Stepper
			steps={stepperSteps}
			current={step}
			completed={completedSteps}
			onJump={jumpToStep}
			mobileCollapsed
			class="mb-5"
		/>

		<div class="space-y-4">
			{#if draftBannerVisible}
				<Banner
					variant="info"
					description={$_('knowledge.wizard.draft.banner', {
						default: 'You have an unfinished draft from {time}.',
						values: { time: formatDraftAge(draftSavedAt) }
					})}
				>
					{#snippet actions()}
						<div class="flex items-center gap-2">
							<Button variant="primary" size="sm" onclick={resumeDraft}>
								{$_('knowledge.wizard.draft.resume', { default: 'Resume' })}
							</Button>
							<Button variant="ghost" size="sm" onclick={discardDraft}>
								{$_('knowledge.wizard.draft.discard', { default: 'Discard' })}
							</Button>
						</div>
					{/snippet}
				</Banner>
			{/if}

			{#if error}
				<Banner variant="danger" description={error} />
			{/if}

			{#if step === 1}
				<p class="type-body-muted">
					{$_('knowledgeStores.addContentModal.libraryHint', {
						default: 'Pick the library that contains the items to ingest.'
					})}
				</p>
				{#if loadingLibs}
					<p class="type-body-muted">{$_('common.loading', { default: 'Loading...' })}</p>
				{:else if libraries.length === 0}
					<p class="type-body-muted">
						{$_('knowledgeStores.addContentModal.noLibraries', {
							default: 'No libraries available. Create a library and import some content first.'
						})}
					</p>
				{:else}
					<ul class="divide-border border-border overflow-hidden rounded-md border">
						{#each libraries as lib (lib.id)}
							{@const count = itemCount(lib)}
							{@const isEmpty = count === 0}
							{@const isSelected = selectedLibraryId === lib.id}
							<li>
								<label
									class="hover:bg-surface-sunken flex cursor-pointer items-center gap-3 px-3 py-2 {isSelected
										? 'bg-brand-subtle'
										: ''}"
								>
									<input
										type="radio"
										name="add-content-lib"
										value={lib.id}
										checked={isSelected}
										onchange={() => selectLibrary(lib.id)}
										class="border-border-strong text-brand focus:ring-brand shrink-0"
									/>
									<div class="min-w-0 flex-1">
										<div class="flex items-center gap-2">
											<span class="text-text truncate text-sm font-medium">{lib.name}</span>
											<Badge variant={isEmpty ? 'neutral' : 'brand'}>
												{count}
												{count === 1
													? $_('knowledgeStores.addContentModal.itemSingular', {
															default: 'item'
														})
													: $_('knowledgeStores.addContentModal.itemPlural', {
															default: 'items'
														})}
											</Badge>
											{#if isEmpty}
												<span class="type-caption italic">
													{$_('knowledgeStores.addContentModal.emptyTag', {
														default: '(empty — nothing to add)'
													})}
												</span>
											{/if}
										</div>
										{#if lib.description}
											<p class="type-caption truncate">{lib.description}</p>
										{/if}
									</div>
								</label>
							</li>
						{/each}
					</ul>
				{/if}
			{:else if step === 2}
				<div class="bg-surface-muted rounded-md px-3 py-2 text-xs">
					<span class="text-text-muted">
						{$_('knowledgeStores.addContentModal.fromLibrary', { default: 'From library:' })}
					</span>
					<span class="text-text ml-1 font-medium">{selectedLibrary?.name || '—'}</span>
				</div>

				{#if loadingItems}
					<p class="type-body-muted">{$_('common.loading', { default: 'Loading...' })}</p>
				{:else if items.length === 0}
					<Banner
						variant="warning"
						description={$_('knowledgeStores.addContentModal.libraryEmptyHint', {
							default:
								'This library has no items ready to ingest. Go back and choose a different library, or import content into this one first.'
						})}
					/>
				{:else if items.filter((i) => i.status === 'ready').length === 0}
					<Banner
						variant="warning"
						description={$_('knowledgeStores.addContentModal.libraryAllFailedHint', {
							default:
								'All items in this library have failed to import. Go back and choose a different library.'
						})}
					/>
				{:else}
					{@const selectableCount = items.filter(
						(i) => i.status === 'ready' && !alreadyLinkedIds.has(i.id)
					).length}
					{@const alreadyLinkedInThisLib = items.filter(
						(i) => i.status === 'ready' && alreadyLinkedIds.has(i.id)
					).length}
					<div class="flex items-center justify-between">
						<span class="text-text type-body font-medium">
							{$_('knowledgeStores.addContentModal.itemsLabel', { default: 'Items to ingest' })}
						</span>
						<Button variant="ghost" size="sm" onclick={toggleAllItems}>
							{selectedItemIds.size === selectableCount
								? $_('knowledgeStores.addContentModal.deselectAll', {
										default: 'Deselect all'
									})
								: $_('knowledgeStores.addContentModal.selectAll', { default: 'Select all' })}
						</Button>
					</div>
					{#if alreadyLinkedInThisLib > 0}
						<Banner
							variant="warning"
							size="sm"
							description={alreadyLinkedInThisLib === 1
								? $_('knowledgeStores.addContentModal.duplicateWarning1', {
										default: '1 item is already in this Knowledge Store and will be skipped.'
									})
								: $_('knowledgeStores.addContentModal.duplicateWarningN', {
										default: '{n} items are already in this Knowledge Store and will be skipped.',
										values: { n: alreadyLinkedInThisLib }
									})}
						/>
					{/if}
					<div class="border-border max-h-96 overflow-y-auto rounded-md border">
						{#each items as item (item.id)}
							{@const isFailed = item.status !== 'ready'}
							{@const isLinked = !isFailed && alreadyLinkedIds.has(item.id)}
							{@const isDisabled = isFailed || isLinked}
							<label
								class="border-border flex items-center gap-3 border-b px-3 py-2 last:border-b-0 {isDisabled
									? 'cursor-not-allowed opacity-50'
									: 'hover:bg-surface-sunken cursor-pointer'}"
							>
								<Checkbox
									disabled={isDisabled}
									checked={!isDisabled && selectedItemIds.has(item.id)}
									onchange={() => !isDisabled && toggleItem(item.id)}
								/>
								<div class="min-w-0 flex-1">
									<div
										class="truncate text-sm font-medium {isDisabled
											? 'text-text-muted'
											: 'text-text'}"
									>
										{item.title}
									</div>
									<div class="type-caption truncate">
										{item.source_type}{isFailed ? ` · failed` : isLinked ? ` · already added` : ''}
									</div>
								</div>
							</label>
						{/each}
					</div>
					<div class="type-caption">
						{selectedItemIds.size} / {selectableCount}
						{$_('knowledgeStores.addContentModal.selected', { default: 'selected' })}
					</div>
				{/if}
			{:else}
				<p class="type-body-muted">
					{$_('knowledgeStores.addContentModal.reviewHint', {
						default: 'Review what will be ingested, then click Add.'
					})}
				</p>
				<div class="border-border bg-surface-muted rounded-md border p-3">
					<p class="type-label">
						{$_('knowledgeStores.addContentModal.fromLibrary', { default: 'From library:' })}
					</p>
					<p class="text-text mt-1 text-sm font-medium">
						{selectedLibrary?.name || '—'}
					</p>
				</div>
				<div>
					<p class="type-label mb-1">
						{$_('knowledgeStores.addContentModal.reviewItems', {
							default: 'Items to ingest',
							values: { count: selectedItemIds.size }
						})}
						<span class="text-text-muted ml-1">({selectedItemIds.size})</span>
					</p>
					<ul class="border-border max-h-96 overflow-y-auto rounded-md border">
						{#each items.filter((i) => selectedItemIds.has(i.id)) as item (item.id)}
							{@const IconCmp = sourceTypeIcon(item.source_type)}
							<li
								class="border-border flex items-center gap-2 border-b px-3 py-2 text-sm last:border-b-0"
							>
								<IconCmp size={14} class="text-text-muted shrink-0" aria-hidden="true" />
								<div class="min-w-0 flex-1">
									<div class="text-text truncate font-medium">{item.title}</div>
									<div class="type-caption truncate">
										{item.source_type} · {item.id}
									</div>
								</div>
								<Badge variant="neutral">{item.source_type}</Badge>
							</li>
						{/each}
					</ul>
				</div>
			{/if}
		</div>
	{/snippet}

	{#snippet footer()}
		<!-- Modal footer is flex-row-reverse: declare primary first so it
		     visually lands on the right; Back (ghost) lands on the left. -->
		{#if step < 3}
			<Button
				variant="primary"
				onclick={goNext}
				disabled={submitting ||
					(step === 1 && !selectedLibraryId) ||
					(step === 2 && selectedItemIds.size === 0)}
			>
				{$_('common.next', { default: 'Next' })}
			</Button>
		{:else}
			<Button
				variant="primary"
				onclick={handleSubmit}
				loading={submitting}
				disabled={selectedItemIds.size === 0}
			>
				{submitting
					? $_('knowledgeStores.addContentModal.submitting', { default: 'Adding...' })
					: $_('knowledgeStores.addContentModal.submit', { default: 'Add' })}
			</Button>
		{/if}
		{#if step > 1}
			<Button variant="ghost" onclick={goBack} disabled={submitting}>
				{$_('common.back', { default: 'Back' })}
			</Button>
		{/if}
	{/snippet}
</Modal>
