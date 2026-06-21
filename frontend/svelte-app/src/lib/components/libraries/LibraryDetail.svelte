<!--
  @component LibraryDetail
  Shows library metadata, item list, file upload, and import actions.
  Receives libraryId as a prop from the page.

  Perceived performance:
    - Header card paints instantly from the row cache when the user
      navigated here from the libraries list.
    - The Knowledge Stores panel is collapsed by default and only fetches
      when first expanded.
-->
<script>
	import { onMount, onDestroy } from 'svelte';
	import { slide } from 'svelte/transition';
	import { cubicInOut } from 'svelte/easing';
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
		updateLibrary,
		getItemContent,
		getItemOriginal,
		getItemKbLinks,
		getLibraryKnowledgeStores,
		getPlugins
	} from '$lib/services/libraryService';
	import { matchPluginsForFile } from '$lib/services/pluginMatcher';
	import { _ } from '$lib/i18n';
	import {
		getKnowledgeStores,
		removeContent as removeKsContent
	} from '$lib/services/knowledgeStoreService';
	import { user } from '$lib/stores/userStore';
	import { toast } from '$lib/stores/toast.js';
	import { findLibraryInCache, patchLibraryInCache } from '$lib/stores/librariesCache.js';
	import { statusBadgeProps } from '$lib/utils/statusBadge.js';
	import ConfirmationModal from '$lib/components/modals/ConfirmationModal.svelte';
	import ImportModal from '$lib/components/modals/ImportModal.svelte';
	import ItemContentModal from '$lib/components/libraries/ItemContentModal.svelte';
	import PluginPickerModal from '$lib/components/libraries/PluginPickerModal.svelte';
	import FileTreeModal from '$lib/components/libraries/fileTree/FileTreeModal.svelte';
	import {
		Button,
		IconButton,
		Card,
		Badge,
		Banner,
		EmptyState,
		Collapsible,
		FormField,
		SkeletonCard,
		OverflowMenu
	} from '$lib/components/ui';
	import {
		Users,
		Lock,
		Download,
		Trash2,
		Pencil,
		Plus,
		Eye,
		FileText,
		FolderTree,
		ExternalLink,
		RefreshCw,
		Loader2
	} from '$lib/components/ui/icons.js';

	let treeModalOpen = $state(false);

	// Description inline edit state. The library's ``name`` is intentionally
	// read-only here; only the description is editable.
	let editingDescription = $state(false);
	let descriptionDraft = $state('');
	let savingDescription = $state(false);
	let descriptionError = $state('');

	function beginEditDescription() {
		descriptionDraft = library?.description || '';
		descriptionError = '';
		editingDescription = true;
	}

	function cancelEditDescription() {
		editingDescription = false;
		descriptionDraft = '';
		descriptionError = '';
	}

	async function saveDescription() {
		if (!library) return;
		const trimmed = descriptionDraft.trim();
		// No-op if unchanged
		if (trimmed === (library.description || '').trim()) {
			cancelEditDescription();
			return;
		}
		// Optimistic write: flip immediately, rollback on failure.
		const previous = library.description;
		library = { ...library, description: trimmed };
		editingDescription = false;
		savingDescription = true;
		descriptionError = '';
		try {
			await updateLibrary(libraryId, { description: trimmed });
			patchLibraryInCache(orgId, libraryId, { description: trimmed });
			toast.success($_('libraries.descriptionSavedSuccess', { default: 'Description updated.' }));
		} catch (/** @type {unknown} */ err) {
			// Rollback
			library = { ...library, description: previous };
			editingDescription = true;
			descriptionDraft = trimmed;
			descriptionError = readableError(err, 'Could not save description.');
		} finally {
			savingDescription = false;
		}
	}

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

	let orgId = $derived(/** @type {any} */ ($user)?.organization_id || '');

	// Library data — seed from the librariesCache row (if we navigated from
	// the list) so the header card paints instantly without a fetch.
	let library = $state(/** @type {any} */ (null));
	let items = $state([]);
	let totalItems = $state(0);
	// Loading flag is only true when we have NO library data yet (no cache
	// hit and the fetch hasn't returned). With a cache hit we skip the full
	// page skeleton entirely.
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

	// Upload state
	/** @type {File|null} */
	let selectedFile = $state(null);
	let fileTitle = $state('');
	let uploading = $state(false);

	// Plugin catalogue fetched once on mount. Used by the upload flow to
	// route a file to the right plugin (or prompt with the picker modal
	// when more than one plugin matches the extension). Typed loosely
	// because the backend response includes more fields than the strict
	// ImportPlugin alias documents, and the picker only consumes a subset.
	/** @type {any[]} */
	let plugins = $state([]);

	// Plugin picker modal state for the multi-match tie-break case.
	let showPluginPicker = $state(false);
	/** @type {any[]} */
	let pluginMatches = $state([]);

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

	// Knowledge Stores that reference items from this library. Loaded
	// LAZILY when the user expands the panel (perceived-performance rule).
	/** @type {import('$lib/services/libraryService').LibraryKnowledgeStore[]} */
	let libraryKnowledgeStores = $state([]);
	let ksPanelLoading = $state(false);
	let ksPanelExpanded = $state(false);
	let ksPanelFetched = $state(false);

	// View item content modal
	let showItemContentModal = $state(false);
	let isLoadingItemContent = $state(false);
	let itemContentTarget = $state({
		id: '',
		title: '',
		sourceType: '',
		sourceUrl: '',
		originalFilename: ''
	});
	let itemContent = $state('');
	/** @type {string|null} */
	let itemContentError = $state(null);

	// Import modal ref
	let importModal;

	let isOwner = $derived(library?.is_owner ?? false);

	// --- Resilience plumbing (#352, M4-M7) ---
	let isMounted = true;
	let currentLoadId = 0;

	onMount(() => {
		// Seed the header card from cache so it paints before the fetch resolves.
		const cached = findLibraryInCache(orgId, libraryId);
		if (cached) {
			library = cached;
			loading = false;
		}
		// Fetch plugin catalogue in parallel with the rest of the page —
		// the upload UI doesn't block on it, but it must arrive before the
		// user clicks Upload. If the fetch fails, the upload handler shows
		// a clear error rather than silently routing to a hardcoded plugin.
		(async () => {
			try {
				plugins = await getPlugins();
			} catch (err) {
				console.warn('LibraryDetail: failed to load plugins', err);
			}
		})();
		return () => {
			if (pollInterval) clearInterval(pollInterval);
		};
	});

	onDestroy(() => {
		isMounted = false;
		if (pollInterval) clearInterval(pollInterval);
	});

	// Guard against spurious effect re-runs.
	let lastLoadedLibraryId = '';
	$effect(() => {
		const id = libraryId;
		if (id && id !== lastLoadedLibraryId) {
			lastLoadedLibraryId = id;
			loadData();
		}
	});

	// Fetches /items with auto-retry on a suspect empty response.
	async function fetchItemsWithRetry(maxRetries = 3) {
		const backoffMs = [250, 500, 1000];
		/** @type {{ items: any[], total: number } | null} */
		let lastData = null;
		for (let attempt = 0; attempt <= maxRetries; attempt++) {
			const data = await getItems(libraryId, { limit: 100 });
			lastData = data;
			const count = Array.isArray(data?.items) ? data.items.length : 0;
			if (count > 0 || attempt === maxRetries) return data;
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
			itemsInconsistent =
				items.length === 0 && typeof library?.item_count === 'number' && library.item_count > 0;
			startPollingIfNeeded();
		} catch (/** @type {unknown} */ err) {
			console.error('refreshItems failed', err);
			if (isMounted) {
				itemsError = readableError(
					err,
					$_('libraries.items.loadError', {
						default: 'Could not load items. The Library Manager may be temporarily unavailable.'
					})
				);
			}
		} finally {
			if (isMounted) itemsLoading = false;
		}
	}

	async function loadData(opts = {}) {
		const silent = !!opts.silent;
		const myLoadId = ++currentLoadId;

		if (pollInterval) {
			clearInterval(pollInterval);
			pollInterval = null;
		}
		// Only flash the full-page skeleton when we have nothing to show.
		if (!silent && !library) loading = true;
		error = '';

		/** @type {(value?: unknown) => void} */
		let resolveLibraryReady = () => {};
		const libraryReady = new Promise((res) => {
			resolveLibraryReady = res;
		});
		(async () => {
			try {
				const lib = await getLibrary(libraryId);
				if (!isMounted || myLoadId !== currentLoadId) return;
				library = lib;
				patchLibraryInCache(orgId, libraryId, lib);
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

		(async () => {
			itemsLoading = true;
			itemsError = '';
			itemsInconsistent = false;
			try {
				/** @type {{ items: any[], total: number } | null} */
				let data = await getItems(libraryId, { limit: 20 });
				if (!isMounted || myLoadId !== currentLoadId) return;

				const looksEmpty = !Array.isArray(data?.items) || data.items.length === 0;
				if (looksEmpty) {
					await Promise.race([libraryReady, new Promise((res) => setTimeout(res, 500))]);
					if (!isMounted || myLoadId !== currentLoadId) return;
					data = await fetchItemsWithRetry(3);
					if (!isMounted || myLoadId !== currentLoadId) return;
				}

				items = data?.items || [];
				totalItems = data?.total || items.length;
				itemsInconsistent =
					items.length === 0 && typeof library?.item_count === 'number' && library.item_count > 0;
				startPollingIfNeeded();

				// Background-fetch the rest if `total > 20`.
				if (data && typeof data.total === 'number' && data.total > items.length) {
					(async () => {
						try {
							const more = await getItems(libraryId, { limit: 100, offset: items.length });
							if (!isMounted || myLoadId !== currentLoadId) return;
							if (Array.isArray(more?.items) && more.items.length > 0) {
								items = [...items, ...more.items];
							}
						} catch (e) {
							console.warn('Background-fetch of remaining items failed', e);
						}
					})();
				}
			} catch (/** @type {unknown} */ err) {
				if (!isMounted || myLoadId !== currentLoadId) return;
				if (err instanceof Error && err.message.startsWith('Session expired')) return;
				console.error('Error loading items:', err);
				itemsError = readableError(
					err,
					$_('libraries.items.loadError', {
						default: 'Could not load items. The Library Manager may be temporarily unavailable.'
					})
				);
			} finally {
				if (isMounted && myLoadId === currentLoadId) itemsLoading = false;
			}
		})();

		// NOTE: ksPanel data fetch is DEFERRED — it triggers on first expand.
	}

	// Lazy-fetch the KS panel data on first expand.
	async function ensureKsPanelLoaded() {
		if (ksPanelFetched) return;
		ksPanelLoading = true;
		try {
			const stores = await getLibraryKnowledgeStores(libraryId);
			if (isMounted) libraryKnowledgeStores = stores;
			ksPanelFetched = true;
		} catch (/** @type {unknown} */ err) {
			if (isMounted) console.warn('Error loading library KS panel:', err);
		} finally {
			if (isMounted) ksPanelLoading = false;
		}
	}

	/** @param {boolean} open */
	function handleKsPanelToggle(open) {
		ksPanelExpanded = open;
		if (open) ensureKsPanelLoaded();
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
						items[idx] = {
							...items[idx],
							status: status.status,
							error_message: status.error_message ?? items[idx].error_message ?? ''
						};
						items = [...items];
					}
				}
			} catch (e) {
				if (e instanceof Error && e.message.startsWith('Session expired')) {
					clearInterval(pollInterval);
					pollInterval = null;
					return;
				}
				sawError = true;
			}
		}
		if (sawError) {
			pollFailures += 1;
			if (pollFailures >= 5) {
				clearInterval(pollInterval);
				pollInterval = null;
				error = $_('libraries.detail.connectionLost');
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

	function handleFileSelect(event) {
		const files = event.target?.files;
		selectedFile = files?.[0] || null;
		if (selectedFile && !fileTitle) {
			fileTitle = selectedFile.name;
		}
	}

	/** @param {string} pluginName */
	async function uploadWithPlugin(pluginName) {
		if (!selectedFile) return;
		const MAX_FILE_SIZE = 500 * 1024 * 1024;
		if (selectedFile.size > MAX_FILE_SIZE) {
			toast.error($_('libraries.fileTooLarge', { default: 'File exceeds 500 MB limit.' }));
			return;
		}
		uploading = true;
		try {
			await uploadFile(libraryId, selectedFile, {
				title: fileTitle.trim() || selectedFile.name,
				pluginName
			});
			selectedFile = null;
			fileTitle = '';
			toast.success($_('libraries.uploadSuccess', { default: 'File uploaded. Processing...' }));
			await refreshItems();
		} catch (/** @type {unknown} */ err) {
			toast.error(readableError(err, 'Upload failed'));
			console.error('uploadFile failed', err);
		} finally {
			uploading = false;
		}
	}

	async function handleUpload() {
		if (!selectedFile) return;
		const matches = matchPluginsForFile(selectedFile, plugins);
		if (matches.length === 0) {
			const ext = selectedFile.name.split('.').pop()?.toLowerCase() || '';
			toast.error(
				$_('libraries.noPluginForExtension', {
					default: 'No plugin can handle .{ext} files.',
					values: { ext: ext || '?' }
				})
			);
			return;
		}
		if (matches.length === 1) {
			await uploadWithPlugin(matches[0].name);
			return;
		}
		pluginMatches = matches;
		showPluginPicker = true;
	}

	/** @param {{ name: string }} plugin */
	async function handlePluginPicked(plugin) {
		showPluginPicker = false;
		await uploadWithPlugin(plugin.name);
	}

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
			if (item.error_message) {
				isLoadingItemContent = false;
				itemContentError = item.error_message;
				return;
			}
			isLoadingItemContent = true;
			try {
				const status = await getItemStatus(libraryId, item.id);
				if (status?.error_message) {
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
				itemContentError =
					err instanceof Error
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
			itemContentError =
				err instanceof Error
					? err.message
					: $_('libraries.itemContentModal.loadError', { default: 'Failed to load content.' });
		} finally {
			isLoadingItemContent = false;
		}
	}

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
			toast.error(
				readableError(
					err,
					$_('libraries.viewOriginalError', { default: 'Failed to load original file.' })
				)
			);
		} finally {
			if (placeholder && !opened) placeholder.close();
		}
	}

	async function handleImported() {
		toast.success($_('libraries.importSuccess', { default: 'Import started.' }));
		await refreshItems();
	}

	/** @param {{ id: string, title: string }} item */
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
			toast.success($_('libraries.itemDeleteSuccess', { default: 'Item deleted.' }));
			await refreshItems();
		} catch (/** @type {unknown} */ err) {
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

	async function handleRemoveBlocker(/** @type {string} */ ksId) {
		deleteItemBlockers = deleteItemBlockers.map((b) =>
			b.id === ksId ? { ...b, removing: true } : b
		);
		try {
			await removeKsContent(ksId, deleteItemTarget.id);
			deleteItemBlockers = deleteItemBlockers.filter((b) => b.id !== ksId);
			if (deleteItemBlockers.length === 0) {
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

	async function handleExport() {
		try {
			await exportLibrary(libraryId, `${library?.name || 'library'}.zip`);
		} catch (/** @type {unknown} */ err) {
			toast.error(err instanceof Error ? err.message : 'Export failed');
		}
	}

	async function handleToggleSharing() {
		if (!library) return;
		// Optimistic flip + rollback on failure.
		const newState = !library.is_shared;
		const previous = library.is_shared;
		library.is_shared = newState;
		library = { ...library };
		patchLibraryInCache(orgId, libraryId, { is_shared: newState });
		try {
			await toggleSharing(libraryId, newState);
			toast.success(
				newState
					? $_('libraries.shareSuccess', { default: 'Library shared.' })
					: $_('libraries.unshareSuccess', { default: 'Library is now private.' })
			);
		} catch (/** @type {unknown} */ err) {
			library.is_shared = previous;
			library = { ...library };
			patchLibraryInCache(orgId, libraryId, { is_shared: previous });
			toast.error(err instanceof Error ? err.message : 'Failed to toggle sharing');
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

	/** Build the per-row OverflowMenu items for the items table. */
	function buildItemMenuItems(item) {
		/** @type {Array<{label?: string, onClick?: () => void, icon?: any, danger?: boolean, divider?: boolean, disabled?: boolean}>} */
		const items = [];
		if (isOwner) {
			items.push({
				label: $_('libraries.delete', { default: 'Delete' }),
				icon: Trash2,
				danger: true,
				onClick: () => requestDeleteItem(item)
			});
		}
		return items;
	}
</script>

{#if loading}
	<div class="space-y-6">
		<SkeletonCard lines={3} />
		<SkeletonCard lines={5} />
	</div>
{:else if error && !library}
	<Banner variant="danger" description={error}>
		{#snippet actions()}
			<Button
				variant="secondary"
				size="sm"
				iconLeftComponent={RefreshCw}
				onclick={() => loadData()}
			>
				{$_('common.retry', { default: 'Retry' })}
			</Button>
		{/snippet}
	</Banner>
{:else if library}
	<div class="space-y-6">
		<!-- Page-level error (non-fatal: library shown but a refresh failed) -->
		{#if error}
			<Banner variant="danger" description={error} />
		{/if}

		<!-- Metadata card -->
		<Card divided={false}>
			<div class="flex items-start justify-between gap-4">
				<h2 class="text-text type-section-title min-w-0 flex-1 break-words">
					{library.name}
				</h2>
				<div class="flex shrink-0 flex-wrap items-center gap-2">
					{#if isOwner}
						<Button
							variant="ghost"
							size="sm"
							iconLeftComponent={library.is_shared ? Users : Lock}
							onclick={handleToggleSharing}
							class={library.is_shared ? 'text-success' : 'text-text-muted'}
						>
							{library.is_shared
								? $_('libraries.sharing.shared', { default: 'Shared' })
								: $_('libraries.sharing.private', { default: 'Private' })}
						</Button>
					{/if}
					<Button variant="secondary" size="sm" iconLeftComponent={Download} onclick={handleExport}>
						{$_('libraries.export', { default: 'Export' })}
					</Button>
				</div>
			</div>

			<!-- Description: inline editable by the owner. -->
			{#if editingDescription}
				<div
					class="mt-3 space-y-2"
					transition:slide={{ duration: 280, easing: cubicInOut, axis: 'y' }}
				>
					<FormField
						type="textarea"
						rows={3}
						bind:value={descriptionDraft}
						placeholder={$_('libraries.descriptionPlaceholder', {
							default: 'Optional description'
						})}
						disabled={savingDescription}
						error={descriptionError}
						maxlength={500}
						helper={`${(descriptionDraft || '').length}/500`}
					/>
					<div class="flex items-center justify-end gap-2">
						<Button
							variant="ghost"
							size="sm"
							onclick={cancelEditDescription}
							disabled={savingDescription}
						>
							{$_('common.cancel', { default: 'Cancel' })}
						</Button>
						<Button
							variant="primary"
							size="sm"
							onclick={saveDescription}
							loading={savingDescription}
						>
							{$_('common.save', { default: 'Save' })}
						</Button>
					</div>
				</div>
			{:else if library.description}
				<div
					class="mt-2 flex items-start gap-2"
					transition:slide={{ duration: 280, easing: cubicInOut, axis: 'y' }}
				>
					<p class="text-text-muted min-w-0 flex-1 text-sm break-words whitespace-pre-wrap">
						{library.description}
					</p>
					{#if isOwner}
						<IconButton
							icon={Pencil}
							ariaLabel={$_('libraries.editDescription', { default: 'Edit description' })}
							tooltip={$_('libraries.editDescription', { default: 'Edit description' })}
							variant="ghost"
							size="sm"
							onclick={beginEditDescription}
						/>
					{/if}
				</div>
			{:else if isOwner}
				<div transition:slide={{ duration: 280, easing: cubicInOut, axis: 'y' }}>
					<Button
						variant="ghost"
						size="sm"
						iconLeftComponent={Plus}
						class="mt-2"
						onclick={beginEditDescription}
					>
						{$_('libraries.addDescription', { default: 'Add description' })}
					</Button>
				</div>
			{/if}

			<dl class="mt-4 grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
				<div>
					<dt class="type-label">{$_('libraries.items.title', { default: 'Items' })}</dt>
					<dd class="text-text font-medium">{totalItems}</dd>
				</div>
				<div>
					<dt class="type-label">{$_('libraries.owner', { default: 'Owner' })}</dt>
					<dd class="text-text font-medium">
						{library.owner_name || library.owner_email || '-'}
					</dd>
				</div>
				<div>
					<dt class="type-label">{$_('libraries.createdAt', { default: 'Created' })}</dt>
					<dd class="text-text font-medium">{formatDate(library.created_at)}</dd>
				</div>
				<div>
					<dt class="type-label">ID</dt>
					<dd class="text-text-muted truncate font-mono text-xs" title={library.id}>
						{library.id}
					</dd>
				</div>
			</dl>
		</Card>

		{#if isOwner || library.is_shared}
			<Card title={$_('libraries.addContent.title', { default: 'Add content' })} divided>
				<div class="flex flex-wrap items-end gap-4">
					<div class="min-w-[200px] flex-1">
						<label for="upload-file" class="text-text mb-1 block text-sm font-medium">
							{$_('libraries.uploadFile', { default: 'Upload file' })}
						</label>
						<input
							id="upload-file"
							type="file"
							onchange={handleFileSelect}
							class="text-text-muted file:bg-brand hover:file:bg-brand-hover file:text-brand-fg block w-full text-sm file:mr-4 file:rounded-md file:border-0 file:px-4 file:py-2 file:text-sm file:font-semibold"
							disabled={uploading}
						/>
					</div>
					<div class="w-48">
						<FormField
							type="text"
							id="upload-title"
							label={$_('libraries.titleOptional', { default: 'Title' })}
							bind:value={fileTitle}
							maxlength={200}
							disabled={uploading}
						/>
					</div>
					<Button
						variant="primary"
						loading={uploading}
						disabled={!selectedFile || uploading}
						onclick={handleUpload}
					>
						{$_('libraries.upload', { default: 'Upload' })}
					</Button>
					<Button variant="secondary" onclick={() => importModal.open(libraryId)}>
						{$_('libraries.importContent', { default: 'Import URL / YouTube' })}
					</Button>
				</div>
			</Card>
		{/if}

		<!-- KS panel: collapsed by default; data fetched lazily on first expand. -->
		<div class="border-border bg-surface shadow-card overflow-hidden rounded-lg border">
			<Collapsible
				label={$_('libraries.knowledgeStores.title', {
					default: 'Knowledge Stores using this library'
				})}
				bordered={false}
				open={ksPanelExpanded}
				onopenchange={handleKsPanelToggle}
			>
				{#if ksPanelLoading}
					<div class="text-text-muted px-6 py-3 text-sm">
						<Loader2 class="mr-2 inline-block h-3 w-3 animate-spin" aria-hidden="true" />
						{$_('common.processing', { default: 'Loading...' })}
					</div>
				{:else if libraryKnowledgeStores.length === 0}
					<p class="text-text-muted px-6 py-3 text-sm">
						{$_('libraries.knowledgeStores.empty', {
							default: 'No Knowledge Stores reference this library yet.'
						})}
					</p>
				{:else}
					<ul class="divide-border divide-y">
						{#each libraryKnowledgeStores as ks (ks.id)}
							<li class="hover:bg-surface-sunken flex items-center gap-3 px-6 py-2.5">
								<div class="min-w-0 flex-1">
									<span class="text-text truncate text-sm font-medium" title={ks.name}>
										{ks.name}
									</span>
									<span class="text-text-subtle ml-2 text-xs">
										{ks.embedding_vendor} · {ks.embedding_model}
									</span>
								</div>
								<Badge
									variant={ks.is_shared ? 'success' : 'neutral'}
									icon={ks.is_shared ? Users : Lock}
								>
									{ks.is_shared
										? $_('libraries.knowledgeStores.shared', { default: 'Shared' })
										: $_('libraries.knowledgeStores.private', { default: 'Private' })}
								</Badge>
								<IconButton
									icon={ExternalLink}
									ariaLabel={$_('libraries.knowledgeStores.view', {
										default: 'Open Knowledge Store'
									})}
									tooltip={$_('libraries.knowledgeStores.view', {
										default: 'Open Knowledge Store'
									})}
									variant="ghost"
									size="sm"
									href={`${base}/libraries?section=knowledge-stores&view=detail&id=${ks.id}&library=${encodeURIComponent(libraryId)}`}
								/>
							</li>
						{/each}
					</ul>
				{/if}
			</Collapsible>
		</div>

		<!-- Items table -->
		<div class="border-border bg-surface shadow-card overflow-hidden rounded-lg border">
			<div class="border-border flex items-center justify-between gap-4 border-b px-6 py-4">
				<h3 class="type-section-title">
					{$_('libraries.items.title', { default: 'Items' })}
					<span class="text-text-muted ml-1 text-sm font-normal">({totalItems})</span>
					{#if itemsLoading && items.length > 0}
						<span class="text-text-subtle ml-2 inline-flex items-center text-xs font-normal">
							<Loader2 class="mr-1 h-3 w-3 animate-spin" aria-hidden="true" />
							{$_('libraries.items.refreshing', { default: 'Refreshing…' })}
						</span>
					{/if}
				</h3>
				<Button
					variant="secondary"
					size="sm"
					iconLeftComponent={FolderTree}
					onclick={() => (treeModalOpen = true)}
				>
					{$_('libraries.fileTree.detailButton', { default: 'View file tree' })}
				</Button>
			</div>

			{#if itemsLoading && items.length === 0}
				<div class="p-6">
					<SkeletonCard lines={4} class="border-0 shadow-none" />
				</div>
			{:else if itemsError}
				<div class="p-6">
					<Banner
						variant="danger"
						title={$_('libraries.items.loadErrorTitle', { default: 'Could not load items' })}
						description={itemsError}
					>
						{#snippet actions()}
							<Button
								variant="secondary"
								size="sm"
								iconLeftComponent={RefreshCw}
								onclick={refreshItems}
							>
								{$_('common.retry', { default: 'Retry' })}
							</Button>
						{/snippet}
					</Banner>
				</div>
			{:else if itemsInconsistent}
				<div class="p-6">
					<Banner
						variant="warning"
						title={$_('libraries.items.inconsistentTitle', {
							default: 'Having trouble loading items'
						})}
					>
						<p>
							{$_('libraries.items.inconsistentBody', {
								default:
									'Your items are safe — the library record shows they should be here, but we could not load the list this time. Please retry; if this keeps happening, refresh the page or try again in a moment.'
							})}
							{#if typeof library?.item_count === 'number' && library.item_count > 0}
								<span class="mt-1 block text-xs">
									{$_('libraries.items.inconsistentExpected', {
										default: 'Library record reports'
									})}: {library.item_count}
									{library.item_count === 1
										? $_('libraries.items.itemSingular', { default: 'item' })
										: $_('libraries.items.itemPlural', { default: 'items' })}.
								</span>
							{/if}
						</p>
						{#snippet actions()}
							<Button
								variant="secondary"
								size="sm"
								iconLeftComponent={RefreshCw}
								onclick={refreshItems}
							>
								{$_('common.retry', { default: 'Retry' })}
							</Button>
						{/snippet}
					</Banner>
				</div>
			{:else if items.length === 0}
				<EmptyState
					icon={FileText}
					title={$_('libraries.items.emptyTitle', { default: 'No items yet' })}
					description={$_('libraries.items.empty', {
						default: 'Upload a file or import content to get started.'
					})}
				/>
			{:else}
				<div class="overflow-x-auto">
					<table class="divide-border min-w-full divide-y">
						<thead class="bg-surface-muted">
							<tr>
								<th class="type-label px-4 py-3 text-left"
									>{$_('libraries.items.titleCol', { default: 'Title' })}</th
								>
								<th class="type-label px-4 py-3 text-left"
									>{$_('libraries.items.source', { default: 'Source' })}</th
								>
								<th class="type-label w-24 px-4 py-3 text-left"
									>{$_('libraries.items.size', { default: 'Size' })}</th
								>
								<th class="type-label px-4 py-3 text-left"
									>{$_('libraries.items.status', { default: 'Status' })}</th
								>
								<th class="type-label w-28 px-4 py-3 text-left"
									>{$_('libraries.items.created', { default: 'Created' })}</th
								>
								<th class="type-label px-4 py-3 text-right"
									>{$_('libraries.actions', { default: 'Actions' })}</th
								>
							</tr>
						</thead>
						<tbody class="divide-border bg-surface divide-y">
							{#each items as item (item.id)}
								{@const sb = statusBadgeProps(item.status)}
								<tr class="hover:bg-surface-sunken">
									<td class="px-4 py-3">
										<div class="text-text text-sm font-medium">{item.title}</div>
										{#if item.original_filename}
											<div class="text-text-subtle text-xs">{item.original_filename}</div>
										{/if}
									</td>
									<td class="text-text-muted px-4 py-3 text-sm">{item.source_type}</td>
									<td class="text-text-muted px-4 py-3 text-sm whitespace-nowrap">
										{formatSize(item.file_size)}
									</td>
									<td class="px-4 py-3">
										<Badge variant={sb.variant} icon={sb.icon} spin={sb.spin}>
											{sb.label}
										</Badge>
									</td>
									<td class="text-text-muted px-4 py-3 text-sm whitespace-nowrap">
										{formatDate(item.created_at)}
									</td>
									<td class="px-4 py-3 text-right whitespace-nowrap">
										<div class="inline-flex items-center gap-1">
											{#if item.status === 'completed' || item.status === 'ready' || item.status === 'failed'}
												<IconButton
													icon={Eye}
													ariaLabel={item.status === 'failed'
														? $_('libraries.viewError', { default: 'View error details' })
														: $_('libraries.viewItem', { default: 'View item' })}
													tooltip={item.status === 'failed'
														? $_('libraries.viewError', { default: 'View error details' })
														: $_('libraries.viewItem', { default: 'View item' })}
													variant="ghost"
													size="sm"
													onclick={() => requestViewItem(item)}
												/>
											{/if}
											{#if isOwner}
												<OverflowMenu
													items={buildItemMenuItems(item)}
													ariaLabel={$_('list.moreActions', { default: 'More actions' })}
													tooltip={$_('list.moreActions', { default: 'More actions' })}
													size="sm"
												/>
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

<PluginPickerModal
	bind:isOpen={showPluginPicker}
	matches={pluginMatches}
	file={selectedFile}
	onselect={handlePluginPicked}
	oncancel={() => {
		showPluginPicker = false;
	}}
/>

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
				default: `Delete "${deleteItemTarget.title}"? This action cannot be undone.`,
				values: { title: deleteItemTarget.title }
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
	{libraryId}
	itemId={itemContentTarget.id}
	onviewOriginal={() => {
		if (itemContentTarget.id) {
			requestViewItemOriginal({ id: itemContentTarget.id, title: itemContentTarget.title });
		}
	}}
	onclose={() => {
		showItemContentModal = false;
	}}
/>

<FileTreeModal
	bind:isOpen={treeModalOpen}
	{libraryId}
	libraryName={library?.name || ''}
	isReadOnly={!isOwner}
	onclose={async () => {
		treeModalOpen = false;
		await refreshItems();
	}}
/>
