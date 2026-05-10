<!--
  @component LibraryDetail
  Shows library metadata, item list, file upload, and import actions.
  Receives libraryId as a prop from the page.
-->
<script>
	import { onMount, onDestroy } from 'svelte';
	import { SvelteSet } from 'svelte/reactivity';
	import axios from 'axios';
	import {
		getLibrary,
		getItems,
		uploadFile,
		deleteItem,
		getItemStatus,
		exportLibrary,
		toggleSharing
	} from '$lib/services/libraryService';
	import { _ } from '$lib/i18n';
	import {
		getKnowledgeStores,
		removeContent as removeKsContent
	} from '$lib/services/knowledgeStoreService';
	import ConfirmationModal from '$lib/components/modals/ConfirmationModal.svelte';
	import ImportModal from '$lib/components/modals/ImportModal.svelte';

	/** @param {unknown} err @param {string} fallback @returns {string} */
	function readableError(err, fallback) {
		if (axios.isAxiosError(err) && err.response) {
			const data = err.response.data;
			// FastAPI's HTTPException body: ``detail`` may be a string or
			// a dict (e.g. the FR-10 delete-blocked response carries
			// ``{ message, knowledge_stores: [...] }``). Surface whichever
			// form is most useful, with a list of KS names appended when
			// available.
			const rawDetail = data?.detail;
			if (typeof rawDetail === 'string' && rawDetail) return rawDetail;
			if (rawDetail && typeof rawDetail === 'object') {
				if (typeof rawDetail.message === 'string' && rawDetail.message) {
					return rawDetail.message;
				}
			}
			if (typeof data?.message === 'string' && data.message) return data.message;
			return `Request failed (${err.response.status})`;
		}
		if (err instanceof Error && err.message) return err.message;
		return fallback;
	}

	let { libraryId = '' } = $props();

	// Library data
	let library = $state(null);
	let items = $state([]);
	let totalItems = $state(0);
	let loading = $state(true);
	let error = $state('');
	let successMessage = $state('');

	// Upload state
	/** @type {File|null} */
	let selectedFile = $state(null);
	let fileTitle = $state('');
	let uploading = $state(false);

	// Polling
	// $state wrap is required because we reassign (`pendingItemIds = new
	// SvelteSet(...)`) on each poll cycle. SvelteSet is reactive for
	// in-place mutations on its own, but reassignment to a fresh instance
	// still needs $state to trigger reactive re-renders.
	// eslint-disable-next-line svelte/no-unnecessary-state-wrap
	let pendingItemIds = $state(new SvelteSet());
	let pollInterval = $state(null);
	let pollFailures = 0;

	// Delete item modal
	let showDeleteItemModal = $state(false);
	let isDeletingItem = $state(false);
	let deleteItemError = $state('');
	/** @type {{ id: string, name: string, contentCount: number|null, removing: boolean }[]} */
	let deleteItemBlockers = $state([]);
	let deleteItemTarget = $state({ id: '', title: '' });

	// Import modal ref
	let importModal;

	let isOwner = $derived(library?.is_owner ?? false);

	// --- Resilience plumbing (#352, M4-M7) ---
	// - isMounted prevents setState writes after the user navigates away
	// - currentLoadId tags every loadData() invocation so a stale fetch that
	//   resolves AFTER a newer one cannot overwrite current state
	// - successTimer is tracked so we can clear it on unmount
	let isMounted = true;
	let currentLoadId = 0;
	/** @type {ReturnType<typeof setTimeout>|null} */
	let successTimer = null;

	onMount(() => {
		return () => {
			// Legacy return-from-onMount cleanup; full cleanup is in onDestroy.
			if (pollInterval) clearInterval(pollInterval);
		};
	});

	onDestroy(() => {
		isMounted = false;
		if (pollInterval) clearInterval(pollInterval);
		if (successTimer) clearTimeout(successTimer);
	});

	$effect(() => {
		// Re-load data whenever libraryId changes (including the initial value)
		if (libraryId) {
			loadData();
		}
	});

	/**
	 * Refresh just the items list (no library metadata reload, no
	 * ``loading`` flag toggle). Used after upload / import / delete so the
	 * page doesn't flicker through any skeleton or even momentarily re-key
	 * the metadata card.
	 */
	async function refreshItems() {
		try {
			const itemsData = await getItems(libraryId, { limit: 100 });
			if (!isMounted) return;
			items = itemsData.items || [];
			totalItems = itemsData.total || items.length;
			startPollingIfNeeded();
		} catch (/** @type {unknown} */ err) {
			console.error('refreshItems failed', err);
		}
	}

	/**
	 * Load library + items.
	 * @param {{ silent?: boolean }} [opts] When ``silent`` is true, the
	 *   ``loading`` flag is not toggled — used for in-place refreshes (e.g.
	 *   after a file upload, polling tick, or item delete) so the page
	 *   doesn't flash back to the blank "Loading library…" skeleton.
	 *   Errors are still surfaced.
	 */
	async function loadData(opts = {}) {
		const silent = !!opts.silent;
		// Tag this run; if a newer call starts before we finish, our writes
		// are dropped on resolution to prevent stale data from clobbering
		// the current view (#352, M4).
		const myLoadId = ++currentLoadId;

		if (pollInterval) {
			clearInterval(pollInterval);
			pollInterval = null;
		}
		if (!silent) loading = true;
		error = '';
		try {
			const [lib, itemsData] = await Promise.all([
				getLibrary(libraryId),
				getItems(libraryId, { limit: 100 })
			]);
			if (!isMounted || myLoadId !== currentLoadId) return;
			library = lib;
			items = itemsData.items || [];
			totalItems = itemsData.total || items.length;
			startPollingIfNeeded();
		} catch (/** @type {unknown} */ err) {
			if (!isMounted || myLoadId !== currentLoadId) return;
			// Session-expired errors are already redirecting elsewhere.
			if (err instanceof Error && err.message.startsWith('Session expired')) return;
			console.error('Error loading library:', err);
			error = err instanceof Error ? err.message : 'Failed to load library';
		} finally {
			if (isMounted && myLoadId === currentLoadId && !silent) loading = false;
		}
	}

	function startPollingIfNeeded() {
		if (pollInterval) clearInterval(pollInterval);
		pollFailures = 0;
		const pending = items.filter((i) => i.status === 'processing' || i.status === 'pending');
		if (pending.length === 0) return;
		pendingItemIds = new SvelteSet(pending.map((i) => i.id));
		pollInterval = setInterval(pollPendingItems, 3000);
	}

	async function pollPendingItems() {
		if (!isMounted) return;
		if (pendingItemIds.size === 0) {
			clearInterval(pollInterval);
			pollInterval = null;
			return;
		}
		let sawError = false;
		for (const itemId of [...pendingItemIds]) {
			try {
				const status = await getItemStatus(libraryId, itemId);
				if (!isMounted) return;
				if (status.status === 'ready' || status.status === 'failed') {
					pendingItemIds.delete(itemId);
					pendingItemIds = new SvelteSet(pendingItemIds);
					const idx = items.findIndex((i) => i.id === itemId);
					if (idx !== -1) {
						items[idx] = { ...items[idx], status: status.status };
						items = [...items];
					}
				}
			} catch (e) {
				// Session-expired aborts the whole poll loop — stop polling so
				// we don't keep hammering after the redirect kicks in.
				if (e instanceof Error && e.message.startsWith('Session expired')) {
					clearInterval(pollInterval);
					pollInterval = null;
					return;
				}
				sawError = true;
			}
		}
		if (sawError) {
			// After 5 consecutive cycles where every probe errored, stop and
			// surface a banner. Previously errors were silently swallowed and
			// items appeared "processing" forever (#352, M5).
			pollFailures += 1;
			if (pollFailures >= 5) {
				clearInterval(pollInterval);
				pollInterval = null;
				error = 'Lost connection while checking item status. Reload to retry.';
				return;
			}
		} else {
			pollFailures = 0;
		}
		if (pendingItemIds.size === 0 && pollInterval) {
			clearInterval(pollInterval);
			pollInterval = null;
		}
	}

	function showSuccess(msg) {
		successMessage = msg;
		// Clear any previous pending timer so rapid successes don't accumulate
		// and so unmount doesn't fire setState on a destroyed component (#352, M6).
		if (successTimer) clearTimeout(successTimer);
		successTimer = setTimeout(() => {
			if (isMounted) successMessage = '';
			successTimer = null;
		}, 4000);
	}

	const SIMPLE_IMPORT_EXTENSIONS = new Set(['txt', 'md', 'html', 'htm']);

	function pluginForFile(file) {
		const ext = file.name.split('.').pop()?.toLowerCase() || '';
		return SIMPLE_IMPORT_EXTENSIONS.has(ext) ? 'simple_import' : 'markitdown_import';
	}

	function handleFileSelect(event) {
		const files = event.target?.files;
		selectedFile = files?.[0] || null;
		if (selectedFile && !fileTitle) {
			fileTitle = selectedFile.name;
		}
	}

	async function handleUpload() {
		if (!selectedFile) return;
		const MAX_FILE_SIZE = 500 * 1024 * 1024;
		if (selectedFile.size > MAX_FILE_SIZE) {
			error = $_('libraries.fileTooLarge', { default: 'File exceeds 500 MB limit.' });
			return;
		}
		uploading = true;
		error = '';
		try {
			await uploadFile(libraryId, selectedFile, {
				title: fileTitle.trim() || selectedFile.name,
				pluginName: pluginForFile(selectedFile)
			});
			selectedFile = null;
			fileTitle = '';
			showSuccess($_('libraries.uploadSuccess', { default: 'File uploaded. Processing...' }));
			await refreshItems();
		} catch (/** @type {unknown} */ err) {
			error = readableError(err, 'Upload failed');
			console.error('uploadFile failed', err);
		} finally {
			uploading = false;
		}
	}

	// Import callback
	async function handleImported() {
		showSuccess($_('libraries.importSuccess', { default: 'Import started.' }));
		await refreshItems();
	}

	// Delete item
	function requestDeleteItem(item) {
		deleteItemTarget = { id: item.id, title: item.title };
		deleteItemError = '';
		deleteItemBlockers = [];
		showDeleteItemModal = true;
	}

	async function handleDeleteItemConfirm() {
		isDeletingItem = true;
		deleteItemError = '';
		try {
			await deleteItem(libraryId, deleteItemTarget.id);
			showDeleteItemModal = false;
			deleteItemBlockers = [];
			showSuccess($_('libraries.itemDeleteSuccess', { default: 'Item deleted.' }));
			await refreshItems();
		} catch (/** @type {unknown} */ err) {
			// FR-10: a 409 with a structured ``detail`` lists the Knowledge
			// Stores still referencing this item. Show them in their own
			// section with a Remove button per row so the user can clear
			// the references inline and retry the delete without leaving
			// the dialog. Falls back to a plain error string for any other
			// failure shape.
			console.error('deleteItem failed', err);
			const isAxios = !!(err && typeof err === 'object' && /** @type {any} */ (err).isAxiosError);
			const status = isAxios ? /** @type {any} */ (err).response?.status : null;
			const detail = isAxios ? /** @type {any} */ (err).response?.data?.detail : null;
			if (status === 409 && detail && typeof detail === 'object') {
				deleteItemError = typeof detail.message === 'string' ? detail.message : 'Delete failed';
				const referenced = Array.isArray(detail.knowledge_stores) ? detail.knowledge_stores : [];
				const initial = referenced.map((k) => ({
					id: String(k?.id || ''),
					name: k?.name || k?.id || 'Knowledge Store',
					contentCount: /** @type {number|null} */ (null),
					removing: false
				}));
				deleteItemBlockers = initial;
				// Enrich with content counts asynchronously so the rows can
				// render immediately and the count fades in once available.
				try {
					const allKs = await getKnowledgeStores();
					const byId = new Map(allKs.map((k) => [k.id, k]));
					deleteItemBlockers = deleteItemBlockers.map((b) => {
						const full = byId.get(b.id);
						return {
							...b,
							contentCount: typeof full?.content_count === 'number' ? full.content_count : null
						};
					});
				} catch (e) {
					console.warn('Could not enrich blockers with content counts', e);
				}
			} else {
				deleteItemError = readableError(err, 'Delete failed');
			}
		} finally {
			isDeletingItem = false;
		}
	}

	/** Remove the current item's link from a single Knowledge Store. */
	async function handleRemoveBlocker(/** @type {string} */ ksId) {
		// Mark just the targeted row as removing.
		deleteItemBlockers = deleteItemBlockers.map((b) =>
			b.id === ksId ? { ...b, removing: true } : b
		);
		try {
			await removeKsContent(ksId, deleteItemTarget.id);
			deleteItemBlockers = deleteItemBlockers.filter((b) => b.id !== ksId);
			if (deleteItemBlockers.length === 0) {
				// All references cleared — clear the error so the Confirm
				// button reads as actionable again.
				deleteItemError = '';
			}
		} catch (/** @type {unknown} */ e) {
			console.error('removeKsContent failed', e);
			deleteItemBlockers = deleteItemBlockers.map((b) =>
				b.id === ksId ? { ...b, removing: false } : b
			);
			deleteItemError = readableError(e, 'Could not remove this link.');
		}
	}

	// Export
	async function handleExport() {
		try {
			await exportLibrary(libraryId, `${library?.name || 'library'}.zip`);
		} catch (/** @type {unknown} */ err) {
			error = err instanceof Error ? err.message : 'Export failed';
		}
	}

	// Sharing
	async function handleToggleSharing() {
		if (!library) return;
		try {
			await toggleSharing(libraryId, !library.is_shared);
			library.is_shared = !library.is_shared;
			library = { ...library };
			showSuccess(
				library.is_shared
					? $_('libraries.shareSuccess', { default: 'Library shared.' })
					: $_('libraries.unshareSuccess', { default: 'Library is now private.' })
			);
		} catch (/** @type {unknown} */ err) {
			error = err instanceof Error ? err.message : 'Failed to toggle sharing';
		}
	}

	function formatDate(ts) {
		if (!ts) return '';
		const d = typeof ts === 'number' ? new Date(ts * 1000) : new Date(ts);
		return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
	}

	function formatSize(bytes) {
		if (!bytes) return '';
		if (bytes < 1024) return `${bytes} B`;
		if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
		return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
	}

	function statusBadge(status) {
		switch (status) {
			case 'ready':
				return 'bg-green-100 text-green-800';
			case 'processing':
			case 'pending':
				return 'bg-yellow-100 text-yellow-800';
			case 'failed':
				return 'bg-red-100 text-red-800';
			default:
				return 'bg-gray-100 text-gray-800';
		}
	}
</script>

{#if loading}
	<div class="p-6 text-center">
		<div class="animate-pulse text-gray-500">
			{$_('libraries.loading', { default: 'Loading...' })}
		</div>
	</div>
{:else if error && !library}
	<div class="p-6 text-center" role="alert">
		<p class="text-red-500">{error}</p>
	</div>
{:else if library}
	<div class="space-y-6">
		<!-- Success banner -->
		{#if successMessage}
			<div
				class="rounded-md border border-green-200 bg-green-50 p-3 text-sm text-green-700"
				role="status"
			>
				{successMessage}
			</div>
		{/if}
		{#if error}
			<div class="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700" role="alert">
				{error}
			</div>
		{/if}

		<!-- Metadata card -->
		<div class="rounded-lg bg-white p-6 shadow">
			<div class="flex items-start justify-between">
				<div>
					<h2 class="text-xl leading-8 font-semibold break-words text-gray-900">
						{library.name}
					</h2>
					{#if library.description}
						<p
							class="mt-1 line-clamp-3 text-sm break-words text-gray-500"
							title={library.description}
						>
							{library.description}
						</p>
					{/if}
				</div>
				<div class="flex gap-2">
					{#if isOwner}
						<button
							type="button"
							onclick={handleToggleSharing}
							class="rounded border px-3 py-1.5 text-xs {library.is_shared
								? 'border-green-300 bg-green-50 text-green-700 hover:bg-green-100'
								: 'border-gray-300 bg-gray-50 text-gray-600 hover:bg-gray-100'}"
						>
							{library.is_shared
								? $_('libraries.sharing.shared', { default: 'Shared' })
								: $_('libraries.sharing.private', { default: 'Private' })}
						</button>
					{/if}
					<button
						type="button"
						onclick={handleExport}
						class="rounded border border-gray-300 bg-gray-50 px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-100"
					>
						{$_('libraries.export', { default: 'Export' })}
					</button>
				</div>
			</div>
			<dl class="mt-4 grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
				<div>
					<dt class="text-gray-500">{$_('libraries.items.title', { default: 'Items' })}</dt>
					<dd class="font-medium text-gray-900">{totalItems}</dd>
				</div>
				<div>
					<dt class="text-gray-500">{$_('libraries.owner', { default: 'Owner' })}</dt>
					<dd class="font-medium text-gray-900">
						{library.owner_name || library.owner_email || '-'}
					</dd>
				</div>
				<div>
					<dt class="text-gray-500">{$_('libraries.createdAt', { default: 'Created' })}</dt>
					<dd class="font-medium text-gray-900">{formatDate(library.created_at)}</dd>
				</div>
				<div>
					<dt class="text-gray-500">ID</dt>
					<dd class="truncate font-mono text-xs text-gray-500" title={library.id}>{library.id}</dd>
				</div>
			</dl>
		</div>

		{#if isOwner || library.is_shared}
			<div class="rounded-lg bg-white p-6 shadow">
				<h3 class="mb-4 text-base font-semibold text-gray-900">
					{$_('libraries.addContent', { default: 'Add Content' })}
				</h3>
				<div class="flex flex-wrap items-end gap-4">
					<div class="min-w-[200px] flex-1">
						<label for="upload-file" class="mb-1 block text-sm font-medium text-gray-700">
							{$_('libraries.uploadFile', { default: 'Upload file' })}
						</label>
						<input
							id="upload-file"
							type="file"
							onchange={handleFileSelect}
							class="block w-full text-sm text-gray-500 file:mr-4 file:rounded-md file:border-0 file:bg-[#2271b3] file:px-4 file:py-2 file:text-sm file:font-semibold file:text-white hover:file:bg-[#195a91]"
							disabled={uploading}
						/>
					</div>
					<div class="w-48">
						<label for="upload-title" class="mb-1 block text-sm font-medium text-gray-700">
							{$_('libraries.titleOptional', { default: 'Title' })}
						</label>
						<input
							id="upload-title"
							type="text"
							bind:value={fileTitle}
							maxlength="200"
							class="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-[#2271b3] focus:ring-[#2271b3]"
							disabled={uploading}
						/>
					</div>
					<button
						type="button"
						onclick={handleUpload}
						disabled={!selectedFile || uploading}
						class="rounded-md bg-[#2271b3] px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-[#195a91] disabled:opacity-50"
					>
						{uploading
							? $_('libraries.uploading', { default: 'Uploading...' })
							: $_('libraries.upload', { default: 'Upload' })}
					</button>
					<button
						type="button"
						onclick={() => importModal.open(libraryId)}
						class="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
					>
						{$_('libraries.importContent', { default: 'Import URL / YouTube' })}
					</button>
				</div>
			</div>
		{/if}

		<div class="overflow-hidden rounded-lg bg-white shadow">
			<div class="border-b border-gray-200 px-6 py-4">
				<h3 class="text-base font-semibold text-gray-900">
					{$_('libraries.items.title', { default: 'Items' })}
					<span class="ml-1 text-sm font-normal text-gray-500">({totalItems})</span>
				</h3>
			</div>

			{#if items.length === 0}
				<div class="p-6 text-center text-gray-500">
					{$_('libraries.items.empty', {
						default: 'No items yet. Upload a file or import content to get started.'
					})}
				</div>
			{:else}
				<div class="overflow-x-auto">
					<table class="min-w-full divide-y divide-gray-200">
						<thead class="bg-gray-50">
							<tr>
								<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase"
									>{$_('libraries.items.titleCol', { default: 'Title' })}</th
								>
								<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase"
									>{$_('libraries.items.source', { default: 'Source' })}</th
								>
								<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase"
									>{$_('libraries.items.size', { default: 'Size' })}</th
								>
								<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase"
									>{$_('libraries.items.status', { default: 'Status' })}</th
								>
								<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase"
									>{$_('libraries.items.created', { default: 'Created' })}</th
								>
								{#if isOwner}
									<th class="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase"
										>{$_('libraries.actions', { default: 'Actions' })}</th
									>
								{/if}
							</tr>
						</thead>
						<tbody class="divide-y divide-gray-200 bg-white">
							{#each items as item (item.id)}
								<tr class="hover:bg-gray-50">
									<td class="px-4 py-3">
										<div class="text-sm font-medium text-gray-900">{item.title}</div>
										{#if item.original_filename}
											<div class="text-xs text-gray-400">{item.original_filename}</div>
										{/if}
									</td>
									<td class="px-4 py-3 text-sm text-gray-500">{item.source_type}</td>
									<td class="px-4 py-3 text-sm text-gray-500">{formatSize(item.file_size)}</td>
									<td class="px-4 py-3">
										<span
											class="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium {statusBadge(
												item.status
											)}"
										>
											{item.status}
										</span>
									</td>
									<td class="px-4 py-3 text-sm text-gray-500">{formatDate(item.created_at)}</td>
									{#if isOwner}
										<td class="px-4 py-3 text-right">
											<button
												type="button"
												onclick={() => requestDeleteItem(item)}
												class="text-sm text-red-600 hover:text-red-900"
											>
												{$_('libraries.delete', { default: 'Delete' })}
											</button>
										</td>
									{/if}
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}
		</div>
	</div>
{/if}

<ImportModal bind:this={importModal} on:imported={handleImported} />

<ConfirmationModal
	bind:isOpen={showDeleteItemModal}
	bind:isLoading={isDeletingItem}
	bind:error={deleteItemError}
	bind:blockers={deleteItemBlockers}
	blockersTitle={$_('libraries.deleteItemModal.blockersTitle', {
		default: 'Referenced by Knowledge Stores'
	})}
	blockerRemoveLabel={$_('libraries.deleteItemModal.blockerRemove', {
		default: 'Remove from KS'
	})}
	onRemoveBlocker={handleRemoveBlocker}
	title={$_('libraries.deleteItemModal.title', { default: 'Delete Item' })}
	message={$_('libraries.deleteItemModal.message', {
		default: `Are you sure you want to delete "${deleteItemTarget.title}"?`
	})}
	confirmText={$_('libraries.deleteItemModal.confirm', { default: 'Delete' })}
	variant="danger"
	onconfirm={handleDeleteItemConfirm}
	oncancel={() => {
		showDeleteItemModal = false;
		deleteItemError = '';
		deleteItemBlockers = [];
	}}
/>
