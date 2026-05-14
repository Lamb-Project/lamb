<!--
  @component AddContentToKSModal
  Three-step modal for adding library items to an existing Knowledge Store.

    Step 1 — Library: list ALL libraries the user can access (including empty
             ones, clearly badged) and pick one as the source.
    Step 2 — Items:   show ready items in the picked library, checkboxes +
             select-all, must pick at least one to advance.
    Step 3 — Review:  list of items about to be ingested + the Add button.

  Draft auto-save uses the shared wizardDraftStore so a closed modal can be
  resumed on the same KS (state: { step, libraryId, itemIds }).
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
	// current modal instance. Auto-save is gated on this so opening
	// the modal alone never overwrites the saved draft — the user has
	// to either explicitly Resume or interact with the form.
	let userInteracted = $state(false);

	let selectedLibrary = $derived(libraries.find((l) => l.id === selectedLibraryId) || null);

	// Open: start from a clean slate every time, then offer to Resume
	// from sessionStorage if a draft exists. The user must opt-in.
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

	// Auto-save on every meaningful change — but only after the user has
	// actually interacted (Resume click or any form input). Reads are
	// explicit so Svelte 5 tracks them; writes go through the debounced
	// saveDraft so quick clicks don't thrash sessionStorage.
	$effect(() => {
		if (!isOpen) return;
		// Always read the tracked deps so the effect re-runs on changes
		// even before userInteracted flips.
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
				...all.filter((/** @type {any} */ i) => i.status === 'ready' && !alreadyLinkedIds.has(i.id)),
				...all.filter((/** @type {any} */ i) => i.status === 'ready' && alreadyLinkedIds.has(i.id)),
				...all.filter((/** @type {any} */ i) => i.status !== 'ready')
			];
			itemsLibraryId = selectedLibraryId;
			const selectableIds = new Set(
				items.filter((/** @type {any} */ i) => i.status === 'ready' && !alreadyLinkedIds.has(i.id)).map((/** @type {any} */ i) => i.id)
			);
			const restoredFromDraft = [...selectedItemIds].filter((id) => selectableIds.has(id));
			selectedItemIds = new SvelteSet(restoredFromDraft.length > 0 ? restoredFromDraft : selectableIds);
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
		// Resume is a deliberate action — auto-save resumes from here.
		markInteracted();
		// If the user was past step 1, pre-load items so step 2/3 render
		// the correct list before we land on them.
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
		// User said "no thanks" — leave the form blank and let any
		// subsequent action be the first auto-save of a new draft.
	}

	function selectLibrary(/** @type {string} */ id) {
		selectedLibraryId = id;
		markInteracted();
		// If the user clicks a library while the resume banner is up, it
		// means they're starting fresh — hide the banner. The previous
		// draft is still in sessionStorage and will be overwritten on the
		// next auto-save tick.
		if (draftBannerVisible) draftBannerVisible = false;
	}

	function toggleItem(/** @type {string} */ id) {
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
		// New modal instance starts in "uninteracted" state so auto-save
		// won't fire from the reset itself and stomp the saved draft.
		userInteracted = false;
	}

	function close() {
		if (submitting) return;
		// Draft is preserved (auto-saved by the effect). Just hide the modal.
		isOpen = false;
		dispatch('close');
	}

	function handleKeydown(/** @type {KeyboardEvent} */ e) {
		if (isOpen && e.key === 'Escape') close();
	}

	// ── Display helpers ──────────────────────────────────────────────
	function itemCount(/** @type {any} */ lib) {
		return typeof lib.item_count === 'number' ? lib.item_count : 0;
	}
</script>

<svelte:window onkeydown={handleKeydown} />

{#if isOpen}
	<div
		class="fixed inset-0 z-50 flex items-center justify-center bg-black/30"
		role="dialog"
		aria-modal="true"
		aria-labelledby="add-content-title"
		onclick={close}
	>
		<!-- svelte-ignore a11y_click_events_have_key_events -->
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div
			class="mx-4 flex max-h-[90vh] w-full max-w-2xl flex-col rounded-lg bg-white shadow-2xl ring-1 ring-black/10"
			onclick={(e) => e.stopPropagation()}
		>
			<!-- Header + stepper -->
			<div class="border-b border-gray-200 px-6 py-4">
				<h2 id="add-content-title" class="text-lg font-semibold text-gray-900">
					{$_('knowledgeStores.addContentModal.title', {
						default: 'Add Library Content to Knowledge Store'
					})}
				</h2>
				<div class="mt-3 flex items-center gap-2 text-xs">
					{#each [1, 2, 3] as n (n)}
						<div
							class="flex h-6 w-6 items-center justify-center rounded-full border text-[11px] font-semibold {step ===
							n
								? 'border-[#2271b3] bg-[#2271b3] text-white'
								: step > n
									? 'border-[#2271b3] bg-blue-50 text-[#2271b3]'
									: 'border-gray-300 bg-white text-gray-400'}"
						>
							{n}
						</div>
						<span
							class="{step === n
								? 'font-medium text-gray-900'
								: 'text-gray-500'} hidden sm:inline"
						>
							{n === 1
								? $_('knowledgeStores.addContentModal.stepLibrary', { default: 'Library' })
								: n === 2
									? $_('knowledgeStores.addContentModal.stepItems', { default: 'Items' })
									: $_('knowledgeStores.addContentModal.stepReview', { default: 'Review' })}
						</span>
						{#if n < 3}
							<span class="h-px flex-1 bg-gray-200"></span>
						{/if}
					{/each}
				</div>
			</div>

			<!-- Body -->
			<div class="flex-1 space-y-4 overflow-y-auto px-6 py-4">
				{#if draftBannerVisible}
					<div
						class="flex items-center justify-between gap-2 rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-800"
						role="status"
					>
						<span>
							{$_('knowledge.wizard.draft.banner', {
								default: 'You have an unfinished draft from {time}.',
								values: { time: formatDraftAge(draftSavedAt) }
							})}
						</span>
						<div class="flex items-center gap-2">
							<button
								type="button"
								onclick={resumeDraft}
								class="font-medium underline hover:no-underline"
							>
								{$_('knowledge.wizard.draft.resume', { default: 'Resume' })}
							</button>
							<button type="button" onclick={discardDraft} class="text-blue-600 hover:text-blue-800">
								{$_('knowledge.wizard.draft.discard', { default: 'Discard' })}
							</button>
						</div>
					</div>
				{/if}

				{#if error}
					<div
						class="rounded border border-red-100 bg-red-50 p-3 text-sm text-red-700"
						role="alert"
					>
						{error}
					</div>
				{/if}

				{#if step === 1}
					<!-- ── Step 1: pick a library ─────────────────────────────── -->
					<p class="text-sm text-gray-600">
						{$_('knowledgeStores.addContentModal.libraryHint', {
							default: 'Pick the library that contains the items to ingest.'
						})}
					</p>
					{#if loadingLibs}
						<div class="text-sm text-gray-500">
							{$_('common.loading', { default: 'Loading...' })}
						</div>
					{:else if libraries.length === 0}
						<div class="text-sm text-gray-500">
							{$_('knowledgeStores.addContentModal.noLibraries', {
								default: 'No libraries available. Create a library and import some content first.'
							})}
						</div>
					{:else}
						<ul
							class="divide-y divide-gray-200 overflow-hidden rounded-md border border-gray-200"
						>
							{#each libraries as lib (lib.id)}
								{@const count = itemCount(lib)}
								{@const isEmpty = count === 0}
								{@const isSelected = selectedLibraryId === lib.id}
								<li>
									<label
										class="flex cursor-pointer items-center gap-3 px-3 py-2 hover:bg-gray-50 {isSelected
											? 'bg-blue-50'
											: ''}"
									>
										<input
											type="radio"
											name="add-content-lib"
											value={lib.id}
											checked={isSelected}
											onchange={() => selectLibrary(lib.id)}
											class="shrink-0"
										/>
										<div class="min-w-0 flex-1">
											<div class="flex items-center gap-2">
												<span class="truncate text-sm font-medium text-gray-900">{lib.name}</span>
												<span
													class="inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium {isEmpty
														? 'bg-gray-100 text-gray-500'
														: 'bg-blue-100 text-[#2271b3]'}"
												>
													{count}
													{count === 1
														? $_('knowledgeStores.addContentModal.itemSingular', { default: 'item' })
														: $_('knowledgeStores.addContentModal.itemPlural', { default: 'items' })}
												</span>
												{#if isEmpty}
													<span class="text-[11px] text-gray-400 italic">
														{$_('knowledgeStores.addContentModal.emptyTag', {
															default: '(empty — nothing to add)'
														})}
													</span>
												{/if}
											</div>
											{#if lib.description}
												<p class="truncate text-xs text-gray-500">{lib.description}</p>
											{/if}
										</div>
									</label>
								</li>
							{/each}
						</ul>
					{/if}
				{:else if step === 2}
					<!-- ── Step 2: pick items from the chosen library ─────────── -->
					<div class="rounded-md bg-gray-50 px-3 py-2 text-xs text-gray-600">
						{$_('knowledgeStores.addContentModal.fromLibrary', { default: 'From library:' })}
						<span class="ml-1 font-medium text-gray-900">{selectedLibrary?.name || '—'}</span>
					</div>

					{#if loadingItems}
						<div class="text-sm text-gray-500">
							{$_('common.loading', { default: 'Loading...' })}
						</div>
					{:else if items.length === 0}
						<div
							class="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800"
							role="note"
						>
							{$_('knowledgeStores.addContentModal.libraryEmptyHint', {
								default:
									'This library has no items ready to ingest. Go back and choose a different library, or import content into this one first.'
							})}
						</div>
					{:else if items.filter((i) => i.status === 'ready').length === 0}
						<div
							class="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800"
							role="note"
						>
							{$_('knowledgeStores.addContentModal.libraryAllFailedHint', {
								default:
									'All items in this library have failed to import. Go back and choose a different library.'
							})}
						</div>
					{:else}
						{@const selectableCount = items.filter((i) => i.status === 'ready' && !alreadyLinkedIds.has(i.id)).length}
						{@const alreadyLinkedInThisLib = items.filter((i) => i.status === 'ready' && alreadyLinkedIds.has(i.id)).length}
						<div class="flex items-center justify-between">
							<span class="text-sm font-medium text-gray-700">
								{$_('knowledgeStores.addContentModal.itemsLabel', {
									default: 'Items to ingest'
								})}
							</span>
							<button
								type="button"
								onclick={toggleAllItems}
								class="text-xs text-[#2271b3] hover:underline"
							>
								{selectedItemIds.size === selectableCount
									? $_('knowledgeStores.addContentModal.deselectAll', {
											default: 'Deselect all'
										})
									: $_('knowledgeStores.addContentModal.selectAll', { default: 'Select all' })}
							</button>
						</div>
						{#if alreadyLinkedInThisLib > 0}
							<div
								class="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800"
								role="note"
							>
								{alreadyLinkedInThisLib === 1
									? $_('knowledgeStores.addContentModal.duplicateWarning1', { default: '1 item is already in this Knowledge Store and will be skipped.' })
									: $_('knowledgeStores.addContentModal.duplicateWarningN', { default: '{n} items are already in this Knowledge Store and will be skipped.', values: { n: alreadyLinkedInThisLib } })}
							</div>
						{/if}
						<div class="max-h-72 overflow-y-auto rounded border border-gray-200">
							{#each items as item (item.id)}
								{@const isFailed = item.status !== 'ready'}
								{@const isLinked = !isFailed && alreadyLinkedIds.has(item.id)}
								{@const isDisabled = isFailed || isLinked}
								<label
									class="flex items-center gap-3 border-b border-gray-100 px-3 py-2 {isDisabled ? 'cursor-not-allowed opacity-45' : 'cursor-pointer hover:bg-gray-50'}"
								>
									<input
										type="checkbox"
										disabled={isDisabled}
										checked={!isDisabled && selectedItemIds.has(item.id)}
										onchange={() => !isDisabled && toggleItem(item.id)}
									/>
									<div class="min-w-0 flex-1">
										<div class="truncate text-sm font-medium {isDisabled ? 'text-gray-400' : 'text-gray-900'}">
											{item.title}
										</div>
										<div class="truncate text-xs text-gray-400">
											{item.source_type}{isFailed ? ` · failed` : isLinked ? ` · already added` : ''}
										</div>
									</div>
								</label>
							{/each}
						</div>
						<div class="text-xs text-gray-400">
							{selectedItemIds.size} / {selectableCount}
							{$_('knowledgeStores.addContentModal.selected', { default: 'selected' })}
						</div>
					{/if}
				{:else}
					<!-- ── Step 3: review + add ────────────────────────────── -->
					<p class="text-sm text-gray-600">
						{$_('knowledgeStores.addContentModal.reviewHint', {
							default: 'Review what will be ingested, then click Add.'
						})}
					</p>
					<div class="rounded-md border border-gray-200 bg-gray-50 p-3">
						<div class="text-xs uppercase tracking-wide text-gray-500">
							{$_('knowledgeStores.addContentModal.fromLibrary', { default: 'From library:' })}
						</div>
						<div class="mt-1 text-sm font-medium text-gray-900">
							{selectedLibrary?.name || '—'}
						</div>
					</div>
					<div>
						<div class="mb-1 text-xs uppercase tracking-wide text-gray-500">
							{$_('knowledgeStores.addContentModal.reviewItems', {
								default: 'Items to ingest',
								values: { count: selectedItemIds.size }
							})}
							<span class="ml-1 text-gray-400">({selectedItemIds.size})</span>
						</div>
						<ul class="max-h-72 overflow-y-auto rounded border border-gray-200 bg-white">
							{#each items.filter((i) => selectedItemIds.has(i.id)) as item (item.id)}
								<li class="border-b border-gray-100 px-3 py-2 text-sm last:border-b-0">
									<div class="truncate font-medium text-gray-900">{item.title}</div>
									<div class="truncate text-xs text-gray-400">
										{item.source_type} · {item.id}
									</div>
								</li>
							{/each}
						</ul>
					</div>
				{/if}
			</div>

			<!-- Footer -->
			<div class="flex justify-between gap-2 border-t border-gray-200 px-6 py-4">
				<button
					type="button"
					onclick={close}
					disabled={submitting}
					class="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
				>
					{$_('common.cancel', { default: 'Cancel' })}
				</button>
				<div class="flex gap-2">
					{#if step > 1}
						<button
							type="button"
							onclick={goBack}
							disabled={submitting}
							class="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
						>
							{$_('common.back', { default: 'Back' })}
						</button>
					{/if}
					{#if step < 3}
						<button
							type="button"
							onclick={goNext}
							disabled={submitting ||
								(step === 1 && !selectedLibraryId) ||
								(step === 2 && selectedItemIds.size === 0)}
							class="rounded-md bg-[#2271b3] px-4 py-2 text-sm font-medium text-white hover:bg-[#195a91] disabled:opacity-50"
						>
							{$_('common.next', { default: 'Next' })}
						</button>
					{:else}
						<button
							type="button"
							onclick={handleSubmit}
							disabled={submitting || selectedItemIds.size === 0}
							class="rounded-md bg-[#2271b3] px-4 py-2 text-sm font-medium text-white hover:bg-[#195a91] disabled:opacity-50"
						>
							{submitting
								? $_('knowledgeStores.addContentModal.submitting', {
										default: 'Adding...'
									})
								: $_('knowledgeStores.addContentModal.submit', {
										default: 'Add'
									})}
						</button>
					{/if}
				</div>
			</div>
		</div>
	</div>
{/if}
