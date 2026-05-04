<!--
  @component AddContentToKSModal
  Modal that picks library + items to ingest into an existing Knowledge
  Store. Used from KnowledgeStoreDetail's "Add Content" button.

  The unified create wizard (CreateKnowledgeWizard) handles "create new
  KS + ingest in one flow"; this modal is the path for adding more
  content to an already-existing KS.
-->
<script>
	import { createEventDispatcher, tick } from 'svelte';
	import { SvelteSet } from 'svelte/reactivity';
	import { getLibraries, getItems } from '$lib/services/libraryService';
	import { addContent } from '$lib/services/knowledgeStoreService';
	import { _ } from '$lib/i18n';

	const dispatch = createEventDispatcher();

	/** @type {{ isOpen: boolean, ksId: string }} */
	let { isOpen = $bindable(false), ksId } = $props();

	let libraries = $state([]);
	let selectedLibraryId = $state('');
	let items = $state([]);
	let selectedItemIds = new SvelteSet();
	let loading = $state(false);
	let loadingItems = $state(false);
	let submitting = $state(false);
	let error = $state('');

	$effect(() => {
		if (isOpen) {
			loadLibraries();
		}
	});

	async function loadLibraries() {
		loading = true;
		error = '';
		try {
			libraries = await getLibraries();
			if (libraries.length > 0 && !selectedLibraryId) {
				selectedLibraryId = libraries[0].id;
				await loadItems();
			}
			await tick();
			document.getElementById('add-content-library')?.focus();
		} catch (/** @type {unknown} */ err) {
			error = err instanceof Error ? err.message : 'Failed to load libraries';
		} finally {
			loading = false;
		}
	}

	async function loadItems() {
		if (!selectedLibraryId) return;
		loadingItems = true;
		items = [];
		selectedItemIds = new SvelteSet();
		try {
			const data = await getItems(selectedLibraryId, { limit: 100, status: 'ready' });
			items = data?.items ?? [];
			// Default: pre-select all ready items.
			selectedItemIds = new SvelteSet(items.map((i) => i.id));
		} catch (/** @type {unknown} */ err) {
			error = err instanceof Error ? err.message : 'Failed to load items';
		} finally {
			loadingItems = false;
		}
	}

	function toggleItem(id) {
		if (selectedItemIds.has(id)) {
			selectedItemIds.delete(id);
		} else {
			selectedItemIds.add(id);
		}
		selectedItemIds = new SvelteSet(selectedItemIds);
	}

	function toggleAll() {
		if (selectedItemIds.size === items.length) {
			selectedItemIds = new SvelteSet();
		} else {
			selectedItemIds = new SvelteSet(items.map((i) => i.id));
		}
	}

	async function handleLibraryChange() {
		await loadItems();
	}

	async function handleSubmit() {
		if (!selectedLibraryId || selectedItemIds.size === 0) {
			error = $_('knowledgeStores.addContentModal.noItems', {
				default: 'Select at least one item.'
			});
			return;
		}
		submitting = true;
		error = '';
		try {
			await addContent(ksId, {
				libraryId: selectedLibraryId,
				itemIds: [...selectedItemIds]
			});
			isOpen = false;
			dispatch('done', { count: selectedItemIds.size });
			selectedItemIds = new SvelteSet();
		} catch (/** @type {unknown} */ err) {
			error = err instanceof Error ? err.message : 'Failed to add content';
		} finally {
			submitting = false;
		}
	}

	function close() {
		if (submitting) return;
		isOpen = false;
		dispatch('close');
	}

	function handleKeydown(e) {
		if (isOpen && e.key === 'Escape') close();
	}
</script>

<svelte:window onkeydown={handleKeydown} />

{#if isOpen}
	<div
		class="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
		role="dialog"
		aria-modal="true"
		aria-labelledby="add-content-title"
		onclick={close}
	>
		<!-- svelte-ignore a11y_click_events_have_key_events -->
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div
			class="mx-4 flex max-h-[90vh] w-full max-w-2xl flex-col rounded-lg bg-white shadow-xl"
			onclick={(e) => e.stopPropagation()}
		>
			<div class="border-b border-gray-200 px-6 py-4">
				<h2 id="add-content-title" class="text-lg font-semibold text-gray-900">
					{$_('knowledgeStores.addContentModal.title', {
						default: 'Add Library Content to Knowledge Store'
					})}
				</h2>
				<p class="mt-1 text-sm text-gray-500">
					{$_('knowledgeStores.addContentModal.description', {
						default:
							'Pick a library and the items to ingest. Only items with status "ready" can be ingested.'
					})}
				</p>
			</div>

			<div class="flex-1 space-y-4 overflow-y-auto px-6 py-4">
				{#if error}
					<div
						class="rounded border border-red-100 bg-red-50 p-3 text-sm text-red-700"
						role="alert"
					>
						{error}
					</div>
				{/if}

				{#if loading}
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
					<div>
						<label for="add-content-library" class="block text-sm font-medium text-gray-700">
							{$_('knowledgeStores.addContentModal.libraryLabel', {
								default: 'Library'
							})}
						</label>
						<select
							id="add-content-library"
							bind:value={selectedLibraryId}
							onchange={handleLibraryChange}
							class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
						>
							{#each libraries as lib (lib.id)}
								<option value={lib.id}>{lib.name}</option>
							{/each}
						</select>
					</div>

					<div>
						<div class="flex items-center justify-between">
							<span class="block text-sm font-medium text-gray-700">
								{$_('knowledgeStores.addContentModal.itemsLabel', {
									default: 'Items to ingest'
								})}
							</span>
							{#if items.length > 0}
								<button
									type="button"
									onclick={toggleAll}
									class="text-xs text-[#2271b3] hover:underline"
								>
									{selectedItemIds.size === items.length
										? $_('knowledgeStores.addContentModal.deselectAll', {
												default: 'Deselect all'
											})
										: $_('knowledgeStores.addContentModal.selectAll', {
												default: 'Select all'
											})}
								</button>
							{/if}
						</div>
						{#if loadingItems}
							<div class="mt-2 text-sm text-gray-500">
								{$_('common.loading', { default: 'Loading...' })}
							</div>
						{:else if items.length === 0}
							<div class="mt-2 text-sm text-gray-500">
								{$_('knowledgeStores.addContentModal.noItems2', {
									default: 'This library has no ready items to ingest.'
								})}
							</div>
						{:else}
							<div class="mt-2 max-h-72 overflow-y-auto rounded border border-gray-200">
								{#each items as item (item.id)}
									<label
										class="flex cursor-pointer items-center gap-3 border-b border-gray-100 px-3 py-2 hover:bg-gray-50"
									>
										<input
											type="checkbox"
											checked={selectedItemIds.has(item.id)}
											onchange={() => toggleItem(item.id)}
										/>
										<div class="min-w-0 flex-1">
											<div class="truncate text-sm font-medium text-gray-900">
												{item.title}
											</div>
											<div class="truncate text-xs text-gray-400">
												{item.source_type} · {item.id}
											</div>
										</div>
									</label>
								{/each}
							</div>
							<div class="mt-1 text-xs text-gray-400">
								{selectedItemIds.size} / {items.length}
								{$_('knowledgeStores.addContentModal.selected', {
									default: 'selected'
								})}
							</div>
						{/if}
					</div>
				{/if}
			</div>

			<div class="flex justify-end gap-2 border-t border-gray-200 px-6 py-4">
				<button
					type="button"
					onclick={close}
					disabled={submitting}
					class="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
				>
					{$_('common.cancel', { default: 'Cancel' })}
				</button>
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
								default: 'Add to Knowledge Store'
							})}
				</button>
			</div>
		</div>
	</div>
{/if}
