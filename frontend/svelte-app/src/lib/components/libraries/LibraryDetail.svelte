<!--
  @component LibraryDetail
  Shows library metadata, item list, file upload, and import actions.
  Receives libraryId as a prop from the page.
-->
<script>
	import { onMount, onDestroy } from 'svelte';
	import { SvelteSet } from 'svelte/reactivity';
	import { base } from '$app/paths';
	import axios from 'axios';
	import {
		getLibrary,
		getItems,
		uploadFile,
		deleteItem,
		getItemStatus,
		exportLibrary,
		toggleSharing,
		getItemContent,
		getItemOriginal,
		getItemKbLinks,
		getLibraryKnowledgeStores
	} from '$lib/services/libraryService';
	import { _ } from '$lib/i18n';
	import {
		getKnowledgeStores,
		removeContent as removeKsContent
	} from '$lib/services/knowledgeStoreService';
	import ConfirmationModal from '$lib/components/modals/ConfirmationModal.svelte';
	import ImportModal from '$lib/components/modals/ImportModal.svelte';
	import ItemContentModal from '$lib/components/libraries/ItemContentModal.svelte';

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
	// Items load independently from the library metadata so the page chrome
	// (title, description, actions, modals) renders as soon as the library
	// shell is ready, instead of blocking on the items round-trip. When the
	// items endpoint is slow (large library, slow LM) we now show an inline
	// "Loading items..." indicator within the items section instead of a
	// blank full-page skeleton.
	let itemsLoading = $state(true);
	// Distinguishes "fetch failed" from "library is genuinely empty" so the
	// items section can render an error+retry panel instead of the misleading
	// "No items yet" state when the Library Manager round-trip fails (timeout,
	// 502/503 on cold start, transient network blip, etc.).
	let itemsError = $state('');
	// Set when /items returned empty but the library row says ``item_count > 0``
	// after all retries — i.e. we have positive evidence that the response is
	// wrong and the library is NOT actually empty. The UI uses this to render
	// a calm "having trouble loading" panel instead of the alarming
	// "No items yet" empty state, so users don't think their data is gone.
	let itemsInconsistent = $state(false);
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

	// Knowledge Stores that reference items from this library. Loaded in
	// parallel with items; the panel is hidden when the list is empty so
	// it doesn't take up vertical space on libraries that aren't yet wired
	// into any KS.
	/** @type {import('$lib/services/libraryService').LibraryKnowledgeStore[]} */
	let libraryKnowledgeStores = $state([]);
	let ksPanelLoading = $state(false);

	// View item content modal
	let showItemContentModal = $state(false);
	let isLoadingItemContent = $state(false);
	let itemContentTarget = $state({ id: '', title: '', sourceType: '', sourceUrl: '', originalFilename: '' });
	let itemContent = $state('');
	/** @type {string|null} */
	let itemContentError = $state(null);

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

	// Guard against spurious effect re-runs: the parent's $page-driven
	// effect re-evaluates props on every store emit, which made $effect
	// re-fire many times per second. Each re-fire cleared the polling
	// interval at the top of loadData(), so status polling never got to
	// tick — the user had to manually reload to see pending → ready.
	// Only call loadData() when libraryId actually changed.
	let lastLoadedLibraryId = '';
	$effect(() => {
		const id = libraryId;
		if (id && id !== lastLoadedLibraryId) {
			lastLoadedLibraryId = id;
			loadData();
		}
	});

	/**
	 * Refresh just the items list. Fires through the same items-loading
	 * indicator as the initial load so the user sees that something is
	 * happening even after upload / import / delete actions.
	 */
	// Fetches /items with auto-retry on a suspect empty response.
	//
	// The Library Manager occasionally returns ``{items: [], total: 0}`` on
	// the first request after a reload — likely a cold-start race in the
	// LM's SQLite session. The race can also surface in the parallel
	// ``item_count`` call from getLibrary, so we don't trust that value
	// blindly. Strategy:
	//
	//   - If the FIRST response is empty, always do one verification retry
	//     after a short delay. A truly-empty library pays ~250 ms of
	//     latency; a raced one self-heals.
	//   - On subsequent retries, only continue while ``library.item_count``
	//     suggests there *should* be items (or is unknown). Once two
	//     independent calls have both reported zero items, we trust it.
	//   - Capped at ``maxRetries`` so neither path spins forever.
	//
	// @param {number} [maxRetries] Upper bound on retry attempts.
	// @returns {Promise<{ items: any[], total: number } | null>}
	async function fetchItemsWithRetry(maxRetries = 3) {
		const backoffMs = [250, 500, 1000];
		/** @type {{ items: any[], total: number } | null} */
		let lastData = null;
		for (let attempt = 0; attempt <= maxRetries; attempt++) {
			const data = await getItems(libraryId, { limit: 100 });
			lastData = data;
			const count = Array.isArray(data?.items) ? data.items.length : 0;
			if (count > 0 || attempt === maxRetries) return data;
			// On the FIRST empty result, always retry once — even if the
			// library row says zero — because the racy source returns zero
			// for both calls. On subsequent attempts, give up if the library
			// row also says zero (two independent confirmations of empty).
			if (attempt >= 1 && library?.item_count === 0) return data;
			console.warn(
				`[LibraryDetail] /items returned empty (attempt ${attempt + 1}/${maxRetries + 1}); retrying.`
			);
			const delay = backoffMs[Math.min(attempt, backoffMs.length - 1)];
			await new Promise((r) => setTimeout(r, delay));
			if (!isMounted) return lastData;
		}
		return lastData;
	}

	async function refreshItems() {
		itemsLoading = true;
		itemsError = '';
		itemsInconsistent = false;
		try {
			const itemsData = await fetchItemsWithRetry();
			if (!isMounted) return;
			items = itemsData?.items || [];
			totalItems = itemsData?.total || items.length;
			// If the response is empty but the library row tells us there
			// should be items, surface a soft "trouble loading" panel instead
			// of "No items yet" so the user isn't shown a misleading empty.
			itemsInconsistent =
				items.length === 0
				&& typeof library?.item_count === 'number'
				&& library.item_count > 0;
			startPollingIfNeeded();
		} catch (/** @type {unknown} */ err) {
			console.error('refreshItems failed', err);
			if (isMounted) {
				itemsError = readableError(err, $_('libraries.items.loadError', {
					default: 'Could not load items. The Library Manager may be temporarily unavailable.'
				}));
			}
		} finally {
			if (isMounted) itemsLoading = false;
		}
	}

	/**
	 * Kick off library-metadata and items fetches **independently** so the
	 * page chrome renders as soon as the (fast) library row arrives, even
	 * if the items endpoint is slow (large library, slow LM, network
	 * jitter). The two halves track their own loading flags:
	 *   - ``loading`` covers the library row only
	 *   - ``itemsLoading`` covers the items list
	 * @param {{ silent?: boolean }} [opts] When ``silent`` is true, the
	 *   ``loading`` flag is not toggled — used for in-place refreshes
	 *   (e.g. after a file upload, polling tick, or item delete) so the
	 *   page doesn't flash back to the loading skeleton. Errors are still
	 *   surfaced.
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
		// Only flash the full-page skeleton when we have nothing to show.
		// Once `library` is populated, subsequent fetches refresh in place
		// (the items section shows its own inline "Refreshing…" indicator
		// instead). This prevents the flicker that happens when the effect
		// re-runs for any reason after the first successful load.
		if (!silent && !library) loading = true;
		error = '';

		// Library row — fast, blocks the page chrome only. Resolves the
		// `libraryReady` promise so the items branch can consult
		// `library.item_count` when deciding whether to retry on an empty
		// response.
		/** @type {(value?: unknown) => void} */
		let resolveLibraryReady = () => {};
		const libraryReady = new Promise((res) => { resolveLibraryReady = res; });
		(async () => {
			try {
				const lib = await getLibrary(libraryId);
				if (!isMounted || myLoadId !== currentLoadId) return;
				library = lib;
			} catch (/** @type {unknown} */ err) {
				if (!isMounted || myLoadId !== currentLoadId) return;
				if (err instanceof Error && err.message.startsWith('Session expired')) return;
				console.error('Error loading library:', err);
				error = err instanceof Error ? err.message : 'Failed to load library';
			} finally {
				resolveLibraryReady();
				if (isMounted && myLoadId === currentLoadId && !silent) loading = false;
			}
		})();

		// Items — fired in parallel. On a suspect empty response (LM cold-read
		// race) we wait for the library row's `item_count` and retry until
		// the two agree or we hit the retry cap; see fetchItemsWithRetry.
		(async () => {
			itemsLoading = true;
			itemsError = '';
			itemsInconsistent = false;
			try {
				// First attempt; if it comes back empty the retry helper will
				// re-fire after a brief delay (always at least once, then
				// gated by library.item_count once we can read it).
				/** @type {{ items: any[], total: number } | null} */
				let data = await getItems(libraryId, { limit: 100 });
				if (!isMounted || myLoadId !== currentLoadId) return;

				const looksEmpty = !Array.isArray(data?.items) || data.items.length === 0;
				if (looksEmpty) {
					// Wait briefly for the library fetch to land so the retry
					// helper can consult library.item_count for the second
					// and later attempts. Don't block forever — if the
					// library fetch is slow, the helper will still do the
					// unconditional first retry without it.
					await Promise.race([
						libraryReady,
						new Promise((res) => setTimeout(res, 500))
					]);
					if (!isMounted || myLoadId !== currentLoadId) return;
					data = await fetchItemsWithRetry(3);
					if (!isMounted || myLoadId !== currentLoadId) return;
				}

				items = data?.items || [];
				totalItems = data?.total || items.length;
				// Final consistency check: if the row says there should be
				// items but we got none, mark inconsistent so the UI shows
				// the soft "trouble loading" panel instead of "No items yet".
				itemsInconsistent =
					items.length === 0
					&& typeof library?.item_count === 'number'
					&& library.item_count > 0;
				startPollingIfNeeded();
			} catch (/** @type {unknown} */ err) {
				if (!isMounted || myLoadId !== currentLoadId) return;
				if (err instanceof Error && err.message.startsWith('Session expired')) return;
				// Don't surface items errors as full-page errors — keep the
				// chrome and show the items section's own error state with a
				// retry button. Without this the user sees the misleading
				// "No items yet" empty state on a transient fetch failure.
				console.error('Error loading items:', err);
				itemsError = readableError(err, $_('libraries.items.loadError', {
					default: 'Could not load items. The Library Manager may be temporarily unavailable.'
				}));
			} finally {
				if (isMounted && myLoadId === currentLoadId) itemsLoading = false;
			}
		})();

		// Knowledge Stores referencing this library — auxiliary panel.
		// Errors stay silent (this is a discoverability surface, not a
		// blocker for the page).
		(async () => {
			ksPanelLoading = true;
			try {
				const stores = await getLibraryKnowledgeStores(libraryId);
				if (!isMounted || myLoadId !== currentLoadId) return;
				libraryKnowledgeStores = stores;
			} catch (/** @type {unknown} */ err) {
				if (!isMounted || myLoadId !== currentLoadId) return;
				console.warn('Error loading library KS panel:', err);
			} finally {
				if (isMounted && myLoadId === currentLoadId) ksPanelLoading = false;
			}
		})();
	}

	// Refresh the KS-references panel — called after ingestion/removal so
	// the panel reflects the latest state without a full page reload.
	async function refreshLibraryKnowledgeStores() {
		try {
			const stores = await getLibraryKnowledgeStores(libraryId);
			if (isMounted) libraryKnowledgeStores = stores;
		} catch (/** @type {unknown} */ err) {
			console.warn('Error refreshing library KS panel:', err);
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
						// Carry forward whatever the status endpoint reports — in
						// particular `error_message`, which is needed by the
						// "View error" modal. Previously only `status` was copied
						// and the message was silently dropped, so failed rows
						// showed the generic "No error message recorded" fallback
						// even though the server had the full reason.
						items[idx] = {
							...items[idx],
							status: status.status,
							error_message: status.error_message ?? items[idx].error_message ?? ''
						};
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

	// View item content. For failed items the on-disk content is either
	// missing or a stale placeholder; surface the import ``error_message``
	// directly instead of attempting (and failing) to fetch the file.
	async function requestViewItem(item) {
		itemContentTarget = {
			id: item.id,
			title: item.title,
			sourceType: item.source_type || '',
			sourceUrl: item.source_url || '',
			originalFilename: item.original_filename || ''
		};
		itemContent = '';
		itemContentError = null;
		showItemContentModal = true;

		if (item.status === 'failed') {
			// If the in-memory row already has the message, show it. Otherwise
			// the row may be stale (e.g. the polling loop transitioned the
			// item to "failed" before we started carrying error_message, or
			// the page was opened directly without ever polling). Fetch the
			// current status from the API as a backstop so the user always
			// gets the actual reason instead of the "no message recorded"
			// fallback.
			if (item.error_message) {
				isLoadingItemContent = false;
				itemContentError = item.error_message;
				return;
			}
			isLoadingItemContent = true;
			try {
				const status = await getItemStatus(libraryId, item.id);
				if (status?.error_message) {
					// Cache it on the in-memory row so subsequent clicks
					// don't refetch.
					const idx = items.findIndex((i) => i.id === item.id);
					if (idx !== -1) {
						items[idx] = { ...items[idx], error_message: status.error_message };
						items = [...items];
					}
					itemContentError = status.error_message;
				} else {
					itemContentError = $_('libraries.itemContentModal.failedNoMessage', {
						default:
							'Import failed for this item. No error message was recorded — check the Library Manager logs.'
					});
				}
			} catch (/** @type {unknown} */ err) {
				itemContentError = err instanceof Error
					? err.message
					: $_('libraries.itemContentModal.failedNoMessage', {
							default:
								'Import failed for this item. No error message was recorded — check the Library Manager logs.'
						});
			} finally {
				isLoadingItemContent = false;
			}
			return;
		}

		isLoadingItemContent = true;
		try {
			itemContent = await getItemContent(libraryId, item.id);
		} catch (/** @type {unknown} */ err) {
			itemContentError = err instanceof Error
				? err.message
				: $_('libraries.itemContentModal.loadError', { default: 'Failed to load content.' });
		} finally {
			isLoadingItemContent = false;
		}
	}

	// View item original (source file). Two branches mirror the backend:
	//  - binary original → render an HTML wrapper containing an embed in a
	//    new tab so PDFs/images preview inline (direct blob-URL navigation
	//    from `about:blank` is unreliable: Safari blocks it because the
	//    placeholder has no origin, Chrome variants sometimes treat it as
	//    a download; the embed wrapper sidesteps both).
	//  - URL / YouTube import → backend returns the source URL via 404;
	//    open it directly in a new tab without proxying.
	// We must `window.open(...)` before the awaited fetch resolves, otherwise
	// Safari treats the click as expired and blocks the popup. The trick:
	// open a blank tab synchronously, then *write* into it once the blob
	// is ready. If anything fails, close the placeholder tab.
	async function requestViewItemOriginal(item) {
		const placeholder = window.open('', '_blank');
		let opened = false;
		try {
			const result = await getItemOriginal(libraryId, item.id);
			if (result.type === 'url') {
				if (placeholder) {
					placeholder.location.href = result.url;
					opened = true;
				} else {
					window.open(result.url, '_blank');
					opened = true;
				}
				return;
			}
			// Binary: navigate directly to the blob URL so the browser's native
			// viewer handles it (PDF viewer, image viewer, etc.). The objectUrl
			// stays alive until the tab is closed — revoking it early breaks the view.
			const objectUrl = URL.createObjectURL(result.blob);
			if (placeholder) {
				placeholder.location.href = objectUrl;
				opened = true;
			} else {
				const fallback = window.open(objectUrl, '_blank');
				opened = !!fallback;
				if (!fallback) {
					const a = document.createElement('a');
					a.href = objectUrl;
					a.download = result.filename;
					document.body.appendChild(a);
					a.click();
					document.body.removeChild(a);
				}
			}
		} catch (/** @type {unknown} */ err) {
			if (placeholder && !opened) placeholder.close();
			error = readableError(err, $_('libraries.viewOriginalError', {
				default: 'Failed to load original file.'
			}));
		} finally {
			if (placeholder && !opened) placeholder.close();
		}
	}

	// Import callback
	async function handleImported() {
		showSuccess($_('libraries.importSuccess', { default: 'Import started.' }));
		await refreshItems();
	}

	/**
	 * Open the delete modal in either "blocked" (KS references found) or
	 * "confirm" mode based on a pre-flight kb-links lookup. Falls through to
	 * confirm mode if the pre-check itself fails — the delete handler still
	 * enforces FR-10 with the 409 fallback below.
	 * @param {{ id: string, title: string }} item
	 */
	async function requestDeleteItem(item) {
		deleteItemTarget = { id: item.id, title: item.title };
		deleteItemError = '';
		deleteItemBlockers = [];
		try {
			const links = await getItemKbLinks(libraryId, item.id);
			const referenced = Array.isArray(links?.knowledge_stores) ? links.knowledge_stores : [];
			if (referenced.length > 0) {
				deleteItemError = $_('libraries.deleteItemModal.blockedMessage', {
					default:
						'This item is referenced by one or more Knowledge Stores. Remove it from each before deleting.'
				});
				deleteItemBlockers = referenced.map((k) => ({
					id: String(k?.id || ''),
					name: k?.name || k?.id || 'Knowledge Store',
					contentCount: /** @type {number|null} */ (null),
					removing: false
				}));
				await enrichBlockersWithCounts();
			}
		} catch (/** @type {unknown} */ err) {
			console.warn('kb-links pre-check failed; falling back to delete-time check', err);
		}
		showDeleteItemModal = true;
	}

	/** Add `content_count` to each blocker row from the KS list, best-effort. */
	async function enrichBlockersWithCounts() {
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
			// FR-10 fallback: if the pre-check missed (e.g. raced with a new
			// link), the 409 from DELETE carries the same blockers shape.
			console.error('deleteItem failed', err);
			const isAxios = !!(err && typeof err === 'object' && /** @type {any} */ (err).isAxiosError);
			const status = isAxios ? /** @type {any} */ (err).response?.status : null;
			const detail = isAxios ? /** @type {any} */ (err).response?.data?.detail : null;
			if (status === 409 && detail && typeof detail === 'object') {
				deleteItemError = typeof detail.message === 'string' ? detail.message : 'Delete failed';
				const referenced = Array.isArray(detail.knowledge_stores) ? detail.knowledge_stores : [];
				deleteItemBlockers = referenced.map((k) => ({
					id: String(k?.id || ''),
					name: k?.name || k?.id || 'Knowledge Store',
					contentCount: /** @type {number|null} */ (null),
					removing: false
				}));
				await enrichBlockersWithCounts();
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

		{#if libraryKnowledgeStores.length > 0 || ksPanelLoading}
			<div class="overflow-hidden rounded-lg bg-white shadow">
				<div class="flex items-center justify-between border-b border-gray-200 px-6 py-4">
					<h3 class="text-base font-semibold text-gray-900">
						{$_('libraries.knowledgeStores.title', {
							default: 'Knowledge Stores using this library'
						})}
						<span class="ml-1 text-sm font-normal text-gray-500">
							({libraryKnowledgeStores.length})
						</span>
					</h3>
					{#if ksPanelLoading}
						<span class="inline-flex items-center text-xs text-gray-400">
							<svg class="mr-1 h-3 w-3 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
								<circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" class="opacity-25" />
								<path
									d="M4 12a8 8 0 018-8"
									stroke="currentColor"
									stroke-width="4"
									class="opacity-75"
									fill="none"
								/>
							</svg>
							{$_('common.loading', { default: 'Loading…' })}
						</span>
					{/if}
				</div>
				{#if libraryKnowledgeStores.length > 0}
					<ul class="divide-y divide-gray-100">
						{#each libraryKnowledgeStores as ks (ks.id)}
							<li class="flex items-center gap-3 px-6 py-2.5 hover:bg-gray-50">
								<div class="min-w-0 flex-1">
									<span class="truncate text-sm font-medium text-gray-900" title={ks.name}>{ks.name}</span>
									<span class="ml-2 text-xs text-gray-400">{ks.embedding_vendor} · {ks.embedding_model}</span>
								</div>
								{#if ks.is_shared}
									<span class="shrink-0 inline-flex items-center rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700">
										{$_('libraries.knowledgeStores.shared', { default: 'Shared' })}
									</span>
								{/if}
								<a
									href={`${base}/libraries?section=knowledge-stores&view=detail&id=${ks.id}&library=${encodeURIComponent(libraryId)}`}
									title={$_('libraries.knowledgeStores.view', { default: 'Open Knowledge Store' })}
									class="shrink-0 rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
								>
									<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
									</svg>
								</a>
							</li>
						{/each}
					</ul>
				{/if}
			</div>
		{/if}

		<div class="overflow-hidden rounded-lg bg-white shadow">
			<div class="border-b border-gray-200 px-6 py-4">
				<h3 class="text-base font-semibold text-gray-900">
					{$_('libraries.items.title', { default: 'Items' })}
					<span class="ml-1 text-sm font-normal text-gray-500">({totalItems})</span>
					{#if itemsLoading && items.length > 0}
						<span class="ml-2 inline-flex items-center text-xs font-normal text-gray-400">
							<svg class="mr-1 h-3 w-3 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
								<circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" class="opacity-25" />
								<path
									d="M4 12a8 8 0 018-8"
									stroke="currentColor"
									stroke-width="4"
									class="opacity-75"
									fill="none"
								/>
							</svg>
							{$_('libraries.items.refreshing', { default: 'Refreshing…' })}
						</span>
					{/if}
				</h3>
			</div>

			{#if itemsLoading && items.length === 0}
				<div class="p-6 text-center text-gray-400">
					<div class="inline-flex items-center gap-2">
						<svg class="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
							<circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" class="opacity-25" />
							<path
								d="M4 12a8 8 0 018-8"
								stroke="currentColor"
								stroke-width="4"
								class="opacity-75"
								fill="none"
							/>
						</svg>
						<span>{$_('libraries.items.loading', { default: 'Loading items…' })}</span>
					</div>
				</div>
			{:else if itemsError}
				<div class="p-6">
					<div class="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-800" role="alert">
						<div class="font-medium">
							{$_('libraries.items.loadErrorTitle', {
								default: 'Could not load items'
							})}
						</div>
						<p class="mt-1">{itemsError}</p>
						<button
							type="button"
							onclick={refreshItems}
							class="mt-3 inline-flex items-center rounded-md border border-red-300 bg-white px-3 py-1.5 text-xs font-medium text-red-700 shadow-sm hover:bg-red-50"
						>
							{$_('libraries.items.retry', { default: 'Retry' })}
						</button>
					</div>
				</div>
			{:else if itemsInconsistent}
				<!-- Defensive state: library metadata says items exist, but the
				     items endpoint returned an empty list after retries. Never
				     show "No items yet" here — it makes users panic that their
				     data is gone. Show a calm "having trouble loading" panel
				     with a retry button and a hint about what the system
				     thinks should be there. -->
				<div class="p-6">
					<div class="rounded-md border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900" role="status">
						<div class="font-medium">
							{$_('libraries.items.inconsistentTitle', {
								default: 'Having trouble loading items'
							})}
						</div>
						<p class="mt-1">
							{$_('libraries.items.inconsistentBody', {
								default:
									'Your items are safe — the library record shows they should be here, but we could not load the list this time. Please retry; if this keeps happening, refresh the page or try again in a moment.'
							})}
							{#if typeof library?.item_count === 'number' && library.item_count > 0}
								<span class="block text-xs text-amber-700 mt-1">
									{$_('libraries.items.inconsistentExpected', {
										default: 'Library record reports'
									})}: {library.item_count} {library.item_count === 1
										? $_('libraries.items.itemSingular', { default: 'item' })
										: $_('libraries.items.itemPlural', { default: 'items' })}.
								</span>
							{/if}
						</p>
						<button
							type="button"
							onclick={refreshItems}
							class="mt-3 inline-flex items-center rounded-md border border-amber-300 bg-white px-3 py-1.5 text-xs font-medium text-amber-800 shadow-sm hover:bg-amber-50"
						>
							{$_('libraries.items.retry', { default: 'Retry' })}
						</button>
					</div>
				</div>
			{:else if items.length === 0}
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
								<th class="w-24 px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase"
									>{$_('libraries.items.size', { default: 'Size' })}</th
								>
								<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase"
									>{$_('libraries.items.status', { default: 'Status' })}</th
								>
								<th class="w-28 px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase"
									>{$_('libraries.items.created', { default: 'Created' })}</th
								>
								<th class="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase"
									>{$_('libraries.actions', { default: 'Actions' })}</th
								>
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
									<td class="whitespace-nowrap px-4 py-3 text-sm text-gray-500">{formatSize(item.file_size)}</td>
									<td class="px-4 py-3">
										<span
											class="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium {statusBadge(
												item.status
											)}"
										>
											{item.status}
										</span>
									</td>
									<td class="whitespace-nowrap px-4 py-3 text-sm text-gray-500">{formatDate(item.created_at)}</td>
									<td class="px-4 py-3 text-right whitespace-nowrap">
										<div class="inline-flex items-center gap-1">
											{#if item.status === 'completed' || item.status === 'ready' || item.status === 'failed'}
												<button
													type="button"
													onclick={() => requestViewItem(item)}
													class="rounded p-1.5 text-gray-400 transition-colors hover:bg-blue-50 hover:text-blue-600"
													title={item.status === 'failed'
														? $_('libraries.viewError', { default: 'View error details' })
														: $_('libraries.viewItem', { default: 'View item' })}
												>
													<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
														<path d="M10 12a2 2 0 100-4 2 2 0 000 4z" />
														<path fill-rule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clip-rule="evenodd" />
													</svg>
												</button>
											{/if}
											{#if isOwner}
												<button
													type="button"
													onclick={() => requestDeleteItem(item)}
													class="rounded p-1.5 text-gray-400 transition-colors hover:bg-red-50 hover:text-red-600"
													title={$_('libraries.delete', { default: 'Delete' })}
												>
													<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
														<path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clip-rule="evenodd" />
													</svg>
												</button>
											{/if}
										</div>
									</td>
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
	title={deleteItemBlockers.length > 0
		? $_('libraries.deleteItemModal.blockedTitle', { default: 'Cannot delete — in use' })
		: $_('libraries.deleteItemModal.title', { default: 'Delete Item' })}
	message={deleteItemBlockers.length > 0
		? ''
		: $_('libraries.deleteItemModal.message', {
				default: `Are you sure you want to delete "${deleteItemTarget.title}"?`
			})}
	confirmText={$_('libraries.deleteItemModal.confirm', { default: 'Delete' })}
	hideConfirm={deleteItemBlockers.length > 0}
	variant="danger"
	onconfirm={handleDeleteItemConfirm}
	oncancel={() => {
		showDeleteItemModal = false;
		deleteItemError = '';
		deleteItemBlockers = [];
	}}
/>

<ItemContentModal
	bind:isOpen={showItemContentModal}
	bind:isLoading={isLoadingItemContent}
	title={itemContentTarget.title}
	content={itemContent}
	error={itemContentError}
	sourceType={itemContentTarget.sourceType}
	sourceUrl={itemContentTarget.sourceUrl}
	originalFilename={itemContentTarget.originalFilename}
	onviewOriginal={() => {
		if (itemContentTarget.id) {
			requestViewItemOriginal({ id: itemContentTarget.id, title: itemContentTarget.title });
		}
	}}
	onclose={() => {
		showItemContentModal = false;
	}}
/>
