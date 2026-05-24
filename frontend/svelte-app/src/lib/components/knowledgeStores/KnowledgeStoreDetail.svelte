<!--
  @component KnowledgeStoreDetail
  Detail panel for a Knowledge Store: locked-config display, linked
  content list with status badges, "add more content" trigger, query
  test box, share toggle, delete.

  Reactively reloads when the ksId prop changes (Marc's #336 finding).

  Phase C consistency contract:
    * Sections wrapped in `<Card>` primitives, header `<Banner>` for errors.
    * `<SkeletonCard>` cascade replaces the bespoke loading text.
    * CRITICAL BUG FIX — locked-warning Banner is rendered ABOVE the
      locked-config grid (was previously BELOW, where it landed after the
      user had already read past the editable controls).
    * Inline-edit pattern for both name AND description (matches
      LibraryDetail exactly).
    * Action group: share toggle Button + Edit IconButton + Delete
      danger-ghost IconButton.
    * Test query Card with FormField inputs and a primary Button.
    * Status badges via `statusBadgeProps`.
    * `toast` for success / error.
-->
<script>
	import { goto } from '$app/navigation';
	import { base } from '$app/paths';
	import { page } from '$app/stores';
	import { untrack } from 'svelte';
	import { slide } from 'svelte/transition';
	import { cubicInOut } from 'svelte/easing';
	import {
		getKnowledgeStore,
		updateKnowledgeStore,
		toggleSharing,
		removeContent,
		deleteKnowledgeStore,
		queryKnowledgeStore,
		getContentLinkStatus,
		getOptions
	} from '$lib/services/knowledgeStoreService';
	import { _ } from '$lib/i18n';
	import { user } from '$lib/stores/userStore';
	import { toast } from '$lib/stores/toast.js';
	import { findKsInCache, patchKsInCache, removeKsFromCache } from '$lib/stores/ksCache.js';
	import { statusBadgeProps } from '$lib/utils/statusBadge.js';
	import ConfirmationModal from '$lib/components/modals/ConfirmationModal.svelte';
	import AddContentToKSModal from '$lib/components/knowledgeStores/AddContentToKSModal.svelte';
	import PluginParamFields from '$lib/components/plugins/PluginParamFields.svelte';
	import {
		Button,
		IconButton,
		Badge,
		Banner,
		Card,
		FormField,
		SkeletonCard
	} from '$lib/components/ui';
	import {
		Pencil,
		Trash2,
		Users,
		Lock,
		Plus,
		Search,
		RefreshCw,
		X,
		ExternalLink
	} from 'lucide-svelte';

	/** @type {{ ksId: string, onclose?: () => void }} */
	let { ksId, onclose } = $props();

	/** @type {any} */
	let ks = $state(null);
	/** @type {any[]} */
	let content = $state([]);
	let loading = $state(true);
	let error = $state('');

	// Inline-edit state for name + description (canonical pattern).
	let editingName = $state(false);
	let editingDescription = $state(false);
	let nameDraft = $state('');
	let descriptionDraft = $state('');
	let savingName = $state(false);
	let savingDescription = $state(false);
	let nameError = $state('');

	// Chunking-params editor. Strategy is immutable but parameters can be
	// edited; updates apply only to content ingested AFTER the edit.
	let editingParams = $state(false);
	let editParams = $state(/** @type {Record<string, unknown>} */ ({}));
	let editParamErrors = $state(/** @type {Record<string, string>} */ ({}));
	let savingParams = $state(false);
	let paramsError = $state('');
	let chunkingSchema = $state(/** @type {Array<any>} */ ([]));
	let schemaLoaded = $state(false);

	let orgId = $derived(/** @type {any} */ ($user)?.organization_id || '');

	async function openParamsEditor() {
		paramsError = '';
		editParams = { ...(ks?.chunking_params || {}) };
		editingParams = true;
		if (!schemaLoaded) {
			try {
				const opts = await getOptions();
				const strategy = (opts?.chunking_strategies || []).find(
					(/** @type {any} */ s) => s.name === ks?.chunking_strategy
				);
				chunkingSchema = strategy?.parameters || [];
				schemaLoaded = true;
			} catch (err) {
				console.warn('Failed to load chunking schema for editor', err);
				paramsError = $_('knowledgeStores.params.schemaFailed', {
					default: 'Could not load chunking parameter schema. Try again later.'
				});
			}
		}
	}

	function cancelParamsEdit() {
		editingParams = false;
		editParams = {};
		editParamErrors = {};
		paramsError = '';
	}

	async function saveParams() {
		if (Object.keys(editParamErrors).length > 0) {
			paramsError = $_('plugins.params.fixErrors', {
				default: 'Fix the plugin parameter errors first.'
			});
			return;
		}
		savingParams = true;
		paramsError = '';
		try {
			await updateKnowledgeStore(ksId, {
				chunking_params: { ...editParams }
			});
			editingParams = false;
			// Reload via the GET endpoint so ``is_owner`` and ``content``
			// (added by the GET-only proxy enrichment) stay populated.
			await loadAll();
			toast.success(
				$_('knowledgeStores.params.saved', {
					default: 'Chunking parameters updated. Applies to new ingestions only.'
				})
			);
		} catch (/** @type {any} */ err) {
			console.error('updateKnowledgeStore chunking_params failed', err);
			paramsError =
				err?.response?.data?.detail ||
				err?.message ||
				$_('knowledgeStores.params.saveFailed', {
					default: 'Failed to update chunking parameters.'
				});
		} finally {
			savingParams = false;
		}
	}

	// Query test
	let queryText = $state('');
	let queryTopK = $state(5);
	let querying = $state(false);
	/** @type {any[]} */
	let queryResults = $state([]);
	let queryError = $state('');

	// Modals
	let showAddContent = $state(false);
	let showRemoveModal = $state(false);
	let removeTarget = $state({ libraryItemId: '', title: '' });
	let isRemoving = $state(false);

	// Delete KS modal (action group)
	let showDeleteModal = $state(false);
	let isDeleting = $state(false);
	let deleteError = $state('');

	// Polling
	/** @type {ReturnType<typeof setTimeout>|null} */
	let pollTimer = null;

	// Library filter
	let libraryFilter = $state('');

	let libraryOptions = $derived.by(() => {
		// Plain object lookup keeps the derived value cheap and side-effect
		// free — using a Map here would trip svelte/prefer-svelte-reactivity
		// even though the instance never leaks past this block.
		/** @type {Record<string, { id: string, name: string }>} */
		const seen = {};
		for (const link of content || []) {
			const id = link.library_id || '';
			const name = link.library_name || '';
			if (!id && !name) continue;
			const key = id || `name:${name}`;
			if (!(key in seen)) {
				seen[key] = { id, name: name || id };
			}
		}
		return Object.values(seen).sort((a, b) => a.name.localeCompare(b.name));
	});

	let filteredContent = $derived.by(() => {
		if (!libraryFilter) return content;
		return (content || []).filter((/** @type {any} */ link) => {
			if (link.library_id && link.library_id === libraryFilter) return true;
			if ((link.library_name || '') === libraryFilter) return true;
			return false;
		});
	});

	$effect(() => {
		// Only re-run when ksId or orgId changes. Reads of ``ks`` happen
		// inside ``untrack`` so the optimistic share toggle (which
		// reassigns ``ks``) does NOT retrigger a background ``loadAll``
		// — otherwise that GET races the in-flight PUT and overwrites
		// the optimistic state, producing a visible flicker.
		const id = ksId;
		const org = orgId;
		if (id) {
			untrack(() => {
				const cached = findKsInCache(org, id);
				if (cached && !ks) {
					ks = { ...cached };
					loading = false;
				}
				try {
					const fromQuery = $page.url.searchParams.get('library');
					if (fromQuery) libraryFilter = fromQuery;
				} catch {
					// $page may not be ready on first render — ignore.
				}
				loadAll();
			});
		}
		return () => {
			if (pollTimer) clearTimeout(pollTimer);
		};
	});

	async function loadAll() {
		// Skeleton min-show guard: only show the skeleton if there is no
		// cached header to paint and the fetch hasn't already resolved.
		if (!ks) loading = true;
		error = '';
		try {
			const fresh = await getKnowledgeStore(ksId);
			ks = fresh;
			content = fresh?.content ?? [];
			nameDraft = fresh?.name ?? '';
			descriptionDraft = fresh?.description ?? '';
			schedulePollIfNeeded();
		} catch (/** @type {unknown} */ err) {
			console.error('Error loading Knowledge Store:', err);
			error = err instanceof Error ? err.message : 'Failed to load Knowledge Store';
		} finally {
			loading = false;
		}
	}

	function schedulePollIfNeeded() {
		if (pollTimer) {
			clearTimeout(pollTimer);
			pollTimer = null;
		}
		const inFlight = (content || []).filter(
			(/** @type {any} */ c) => c.status === 'pending' || c.status === 'processing'
		);
		if (inFlight.length === 0) return;
		pollTimer = setTimeout(async () => {
			for (const link of inFlight) {
				try {
					const updated = await getContentLinkStatus(ksId, link.library_item_id);
					const idx = content.findIndex((/** @type {any} */ c) => c.id === link.id);
					if (idx !== -1) {
						content[idx] = { ...content[idx], ...updated };
					}
				} catch (err) {
					console.warn('Poll failed', err);
				}
			}
			schedulePollIfNeeded();
		}, 4000);
	}

	function beginEditName() {
		nameDraft = ks?.name ?? '';
		nameError = '';
		editingName = true;
	}

	function cancelEditName() {
		editingName = false;
		nameDraft = ks?.name ?? '';
		nameError = '';
	}

	async function saveName() {
		const trimmed = nameDraft.trim();
		if (!trimmed) {
			nameError = $_('knowledgeStores.nameRequired', { default: 'Name is required.' });
			return;
		}
		savingName = true;
		nameError = '';
		// Optimistic update.
		const prev = ks?.name;
		ks = { ...ks, name: trimmed };
		patchKsInCache(orgId, ksId, { name: trimmed });
		try {
			await updateKnowledgeStore(ksId, { name: trimmed });
			editingName = false;
			toast.success($_('knowledgeStores.updateSuccess', { default: 'Knowledge Store updated.' }));
		} catch (/** @type {unknown} */ err) {
			// Rollback.
			ks = { ...ks, name: prev };
			patchKsInCache(orgId, ksId, { name: prev });
			nameError = err instanceof Error ? err.message : 'Update failed';
			toast.error(nameError);
		} finally {
			savingName = false;
		}
	}

	function beginEditDescription() {
		descriptionDraft = ks?.description ?? '';
		editingDescription = true;
	}

	function cancelEditDescription() {
		editingDescription = false;
		descriptionDraft = ks?.description ?? '';
	}

	async function saveDescription() {
		savingDescription = true;
		const prev = ks?.description;
		ks = { ...ks, description: descriptionDraft };
		patchKsInCache(orgId, ksId, { description: descriptionDraft });
		try {
			await updateKnowledgeStore(ksId, { description: descriptionDraft });
			editingDescription = false;
			toast.success($_('knowledgeStores.updateSuccess', { default: 'Knowledge Store updated.' }));
		} catch (/** @type {unknown} */ err) {
			ks = { ...ks, description: prev };
			patchKsInCache(orgId, ksId, { description: prev });
			toast.error(err instanceof Error ? err.message : 'Update failed');
		} finally {
			savingDescription = false;
		}
	}

	async function handleToggleSharing() {
		if (!ks) return;
		const newState = !ks.is_shared;
		// Optimistic update.
		ks = { ...ks, is_shared: newState };
		patchKsInCache(orgId, ksId, { is_shared: newState });
		try {
			await toggleSharing(ksId, newState);
			toast.success(
				newState
					? $_('knowledgeStores.shareSuccess', {
							default: 'Knowledge Store shared with organization.'
						})
					: $_('knowledgeStores.unshareSuccess', {
							default: 'Knowledge Store is now private.'
						})
			);
		} catch (/** @type {unknown} */ err) {
			ks = { ...ks, is_shared: !newState };
			patchKsInCache(orgId, ksId, { is_shared: !newState });
			toast.error(err instanceof Error ? err.message : 'Failed to toggle sharing');
		}
	}

	function requestDeleteKs() {
		deleteError = '';
		showDeleteModal = true;
	}

	async function handleDeleteKs() {
		if (!ks) return;
		isDeleting = true;
		deleteError = '';
		try {
			await deleteKnowledgeStore(ksId);
			showDeleteModal = false;
			removeKsFromCache(orgId, ksId);
			toast.success(
				$_('knowledgeStores.deleteSuccess', {
					default: `Knowledge Store "${ks.name}" deleted.`
				})
			);
			if (typeof onclose === 'function') {
				onclose();
			} else {
				// eslint-disable-next-line svelte/no-navigation-without-resolve
				goto(`${base}/libraries?section=knowledge-stores`, { replaceState: true });
			}
		} catch (/** @type {unknown} */ err) {
			deleteError = err instanceof Error ? err.message : 'Delete failed';
		} finally {
			isDeleting = false;
		}
	}

	/** @param {any} link */
	function requestRemoveContent(link) {
		removeTarget = {
			libraryItemId: link.library_item_id,
			title: link.item_title || link.library_item_id
		};
		showRemoveModal = true;
	}

	async function handleRemoveConfirm() {
		isRemoving = true;
		try {
			await removeContent(ksId, removeTarget.libraryItemId);
			showRemoveModal = false;
			toast.success(
				$_('knowledgeStores.removeContentSuccess', {
					default: 'Content removed from Knowledge Store.'
				})
			);
			await loadAll();
		} catch (/** @type {unknown} */ err) {
			toast.error(err instanceof Error ? err.message : 'Remove failed');
		} finally {
			isRemoving = false;
		}
	}

	/**
	 * Open a permalink in a new tab. Internal /docs/ paths are fetched with
	 * auth headers and opened via a blob URL; external URLs open directly.
	 * @param {string} url
	 */
	async function openPermalink(url) {
		if (!url) return;
		if (url.startsWith('http://') || url.startsWith('https://')) {
			window.open(url, '_blank', 'noopener,noreferrer');
			return;
		}
		try {
			const token = localStorage.getItem('userToken');
			const res = await fetch(url, {
				headers: token ? { Authorization: `Bearer ${token}` } : {}
			});
			if (!res.ok) {
				queryError = `Could not load content (${res.status})`;
				return;
			}
			const blob = await res.blob();
			const blobUrl = URL.createObjectURL(blob);
			const win = window.open(blobUrl, '_blank');
			if (win) setTimeout(() => URL.revokeObjectURL(blobUrl), 60000);
		} catch (err) {
			queryError = err instanceof Error ? err.message : 'Failed to open content';
		}
	}

	async function runQuery() {
		if (!queryText.trim()) return;
		querying = true;
		queryError = '';
		queryResults = [];
		try {
			const data = await queryKnowledgeStore(ksId, {
				queryText,
				topK: queryTopK
			});
			queryResults = data?.results ?? [];
		} catch (/** @type {unknown} */ err) {
			queryError = err instanceof Error ? err.message : 'Query failed';
		} finally {
			querying = false;
		}
	}

	/** @param {number|string|null|undefined} ts */
	function formatDate(ts) {
		if (!ts) return '';
		const d = typeof ts === 'number' ? new Date(ts * 1000) : new Date(ts);
		return d.toLocaleString();
	}

	/** @param {CustomEvent<Record<string, any>>} event */
	async function handleAddContentDone(event) {
		const refs = event?.detail || {};
		showAddContent = false;
		toast.success(
			$_('knowledgeStores.addContentSuccess', { default: 'Content queued for ingestion.' })
		);
		if (refs.target === 'library' && refs.libraryId) {
			// eslint-disable-next-line svelte/no-navigation-without-resolve
			goto(`${base}/libraries?section=libraries&view=detail&id=${refs.libraryId}`, {
				replaceState: false,
				keepFocus: true
			});
			return;
		}
		await loadAll();
	}
</script>

{#if loading && !ks}
	<div class="space-y-6">
		<SkeletonCard lines={3} />
		<SkeletonCard lines={5} />
		<SkeletonCard lines={3} />
	</div>
{:else if error && !ks}
	<Banner variant="danger" description={error}>
		{#snippet actions()}
			<Button variant="secondary" size="sm" iconLeftComponent={RefreshCw} onclick={() => loadAll()}>
				{$_('common.retry', { default: 'Retry' })}
			</Button>
		{/snippet}
	</Banner>
{:else if ks}
	<div class="space-y-6">
		{#if error}
			<Banner variant="danger" description={error}>
				{#snippet actions()}
					<Button
						variant="secondary"
						size="sm"
						iconLeftComponent={RefreshCw}
						onclick={() => loadAll()}
					>
						{$_('common.retry', { default: 'Retry' })}
					</Button>
				{/snippet}
			</Banner>
		{/if}

		<!-- Header card: name + locked-config notice + locked-config grid + chunking params. -->
		<Card divided={false}>
			<div class="flex items-start justify-between gap-4">
				<div class="min-w-0 flex-1">
					{#if editingName}
						<div
							class="space-y-2"
							transition:slide={{ duration: 280, easing: cubicInOut, axis: 'y' }}
						>
							<FormField
								type="text"
								bind:value={nameDraft}
								disabled={savingName}
								error={nameError}
								required
								maxlength={200}
								helper={`${(nameDraft || '').length}/200`}
							/>
							<div class="flex items-center justify-end gap-2">
								<Button variant="ghost" size="sm" onclick={cancelEditName} disabled={savingName}>
									{$_('common.cancel', { default: 'Cancel' })}
								</Button>
								<Button
									variant="primary"
									size="sm"
									onclick={saveName}
									loading={savingName}
									disabled={!nameDraft.trim()}
								>
									{$_('common.save', { default: 'Save' })}
								</Button>
							</div>
						</div>
					{:else}
						<div transition:slide={{ duration: 280, easing: cubicInOut, axis: 'y' }}>
							<div class="flex items-center gap-2">
								<h2 class="text-text type-section-title min-w-0 flex-1 break-words">
									{ks.name}
								</h2>
								{#if ks.is_owner}
									<IconButton
										icon={Pencil}
										ariaLabel={$_('knowledgeStores.editName', { default: 'Edit name' })}
										tooltip={$_('knowledgeStores.editName', { default: 'Edit name' })}
										variant="ghost"
										size="sm"
										onclick={beginEditName}
									/>
								{/if}
							</div>
							<p class="type-caption mt-1 truncate">{ks.id}</p>
						</div>
					{/if}
				</div>
				<div class="flex shrink-0 flex-wrap items-center gap-2">
					{#if ks.is_owner}
						<Button
							variant="ghost"
							size="sm"
							iconLeftComponent={ks.is_shared ? Users : Lock}
							onclick={handleToggleSharing}
							class={ks.is_shared ? 'text-success' : 'text-text-muted'}
						>
							{ks.is_shared
								? $_('knowledgeStores.sharing.shared', { default: 'Shared' })
								: $_('knowledgeStores.sharing.private', { default: 'Private' })}
						</Button>
						<IconButton
							icon={Trash2}
							ariaLabel={$_('knowledgeStores.delete', { default: 'Delete' })}
							tooltip={$_('knowledgeStores.delete', { default: 'Delete' })}
							variant="danger-ghost"
							size="sm"
							onclick={requestDeleteKs}
						/>
					{/if}
				</div>
			</div>

			<!-- Description (inline-editable, same pattern as LibraryDetail). -->
			{#if editingDescription}
				<div
					class="mt-3 space-y-2"
					transition:slide={{ duration: 280, easing: cubicInOut, axis: 'y' }}
				>
					<FormField
						type="textarea"
						rows={3}
						bind:value={descriptionDraft}
						placeholder={$_('knowledgeStores.descriptionPlaceholder', {
							default: 'Description'
						})}
						disabled={savingDescription}
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
			{:else if ks.description}
				<div
					class="mt-2 flex items-start gap-2"
					transition:slide={{ duration: 280, easing: cubicInOut, axis: 'y' }}
				>
					<p class="text-text-muted min-w-0 flex-1 text-sm break-words whitespace-pre-wrap">
						{ks.description}
					</p>
					{#if ks.is_owner}
						<IconButton
							icon={Pencil}
							ariaLabel={$_('knowledgeStores.editDescription', { default: 'Edit description' })}
							tooltip={$_('knowledgeStores.editDescription', { default: 'Edit description' })}
							variant="ghost"
							size="sm"
							onclick={beginEditDescription}
						/>
					{/if}
				</div>
			{:else if ks.is_owner}
				<div transition:slide={{ duration: 280, easing: cubicInOut, axis: 'y' }}>
					<Button
						variant="ghost"
						size="sm"
						iconLeftComponent={Plus}
						class="mt-2"
						onclick={beginEditDescription}
					>
						{$_('knowledgeStores.addDescription', { default: 'Add description' })}
					</Button>
				</div>
			{/if}

			<!-- CRITICAL: locked-config warning now lives ABOVE the grid. -->
			<div class="mt-5">
				<Banner
					variant="warning"
					size="sm"
					description={$_('knowledgeStores.lockedNotice', {
						default:
							'Chunking strategy, embedding vendor / model, and vector DB are locked at creation and cannot be changed.'
					})}
				/>
			</div>

			<!-- Locked-config grid (each cell carries a Lock icon). -->
			<dl
				class="border-border bg-surface-muted mt-3 grid grid-cols-2 gap-4 rounded-md border px-4 py-3 text-xs sm:grid-cols-4"
			>
				<div>
					<dt class="type-label flex items-center gap-1">
						<Lock size={10} aria-hidden="true" />
						{$_('knowledgeStores.chunking', { default: 'Chunking' })}
					</dt>
					<dd class="text-text mt-0.5">{ks.chunking_strategy}</dd>
				</div>
				<div>
					<dt class="type-label flex items-center gap-1">
						<Lock size={10} aria-hidden="true" />
						{$_('knowledgeStores.embeddingVendor', { default: 'Embedding' })}
					</dt>
					<dd class="text-text mt-0.5">{ks.embedding_vendor}</dd>
				</div>
				<div>
					<dt class="type-label flex items-center gap-1">
						<Lock size={10} aria-hidden="true" />
						{$_('knowledgeStores.embeddingModel', { default: 'Model' })}
					</dt>
					<dd class="text-text mt-0.5 break-all">{ks.embedding_model}</dd>
				</div>
				<div>
					<dt class="type-label flex items-center gap-1">
						<Lock size={10} aria-hidden="true" />
						{$_('knowledgeStores.vectorDb', { default: 'Vector DB' })}
					</dt>
					<dd class="text-text mt-0.5">{ks.vector_db_backend}</dd>
				</div>
			</dl>
		</Card>

		<!-- Chunking parameters card -->
		{#if (ks.chunking_params && Object.keys(ks.chunking_params).length > 0) || ks.is_owner}
			<Card title={$_('knowledgeStores.chunkingParams', { default: 'Chunking parameters' })}>
				{#snippet actions()}
					{#if ks.is_owner && !editingParams}
						<IconButton
							icon={Pencil}
							ariaLabel={$_('knowledgeStores.params.editButton', { default: 'Edit' })}
							tooltip={$_('knowledgeStores.params.editButton', { default: 'Edit' })}
							variant="ghost"
							size="sm"
							onclick={openParamsEditor}
						/>
					{/if}
				{/snippet}

				{#if !editingParams}
					{#if ks.chunking_params && Object.keys(ks.chunking_params).length > 0}
						<dl class="flex flex-wrap gap-x-6 gap-y-2 text-sm">
							{#each Object.entries(ks.chunking_params) as [paramName, paramValue] (paramName)}
								<div class="flex items-baseline gap-1.5">
									<dt class="type-label">{paramName}</dt>
									<dd class="text-text font-mono text-xs">{paramValue}</dd>
								</div>
							{/each}
						</dl>
					{:else}
						<p class="type-body-muted">
							{$_('knowledgeStores.params.usingDefaults', {
								default: 'Using the strategy defaults.'
							})}
						</p>
					{/if}
				{:else}
					<div class="space-y-3">
						<Banner
							variant="info"
							size="sm"
							description={$_('knowledgeStores.params.editNotice', {
								default:
									'Changes apply only to content ingested after saving — existing chunks keep the parameters they were created with.'
							})}
						/>

						{#if chunkingSchema.length > 0}
							<PluginParamFields
								parameters={chunkingSchema}
								bind:values={editParams}
								bind:errors={editParamErrors}
								idPrefix="ks-detail-chunking-edit"
							/>
						{:else if schemaLoaded}
							<p class="type-body-muted">
								{$_('knowledgeStores.params.noParams', {
									default: 'This strategy has no editable parameters.'
								})}
							</p>
						{:else}
							<p class="type-body-muted">{$_('common.loading', { default: 'Loading...' })}</p>
						{/if}

						{#if paramsError}
							<Banner variant="danger" size="sm" description={paramsError} />
						{/if}

						<div class="flex justify-end gap-2">
							<Button variant="ghost" size="sm" onclick={cancelParamsEdit} disabled={savingParams}>
								{$_('common.cancel', { default: 'Cancel' })}
							</Button>
							<Button
								variant="primary"
								size="sm"
								onclick={saveParams}
								loading={savingParams}
								disabled={Object.keys(editParamErrors).length > 0}
							>
								{$_('common.save', { default: 'Save' })}
							</Button>
						</div>
					</div>
				{/if}
			</Card>
		{/if}

		<!-- Linked content card -->
		<Card>
			{#snippet header()}
				<div class="min-w-0 flex-1">
					<h3 class="type-card-title">
						{$_('knowledgeStores.linkedContent', { default: 'Linked Library Content' })}
						<span class="text-text-muted ml-2 text-sm font-normal">
							{#if libraryFilter}
								({filteredContent.length} / {content.length})
							{:else}
								({content.length})
							{/if}
						</span>
					</h3>
				</div>
			{/snippet}

			{#snippet actions()}
				<div class="flex items-center gap-3">
					{#if libraryOptions.length > 1 || libraryFilter}
						<label class="text-text-muted flex items-center gap-2 text-xs">
							<span>{$_('knowledgeStores.filterLibrary', { default: 'Library' })}:</span>
							<select
								bind:value={libraryFilter}
								class="border-border-strong bg-surface text-text rounded-md border px-2 py-1 text-xs"
							>
								<option value="">
									{$_('knowledgeStores.filterLibraryAll', { default: 'All libraries' })}
								</option>
								{#each libraryOptions as opt (opt.id || opt.name)}
									<option value={opt.id || opt.name}>{opt.name}</option>
								{/each}
							</select>
							{#if libraryFilter}
								<IconButton
									icon={X}
									ariaLabel={$_('knowledgeStores.filterLibraryClear', {
										default: 'Clear filter'
									})}
									tooltip={$_('knowledgeStores.filterLibraryClear', {
										default: 'Clear filter'
									})}
									variant="ghost"
									size="sm"
									onclick={() => (libraryFilter = '')}
								/>
							{/if}
						</label>
					{/if}
					{#if ks.is_owner}
						<Button
							variant="primary"
							iconLeftComponent={Plus}
							onclick={() => (showAddContent = true)}
						>
							{$_('knowledgeStores.addContent', { default: 'Add Content' })}
						</Button>
					{/if}
				</div>
			{/snippet}

			{#if content.length === 0}
				<p class="text-text-muted py-4 text-center text-sm">
					{$_('knowledgeStores.noContent', {
						default: 'No library content linked yet. Add content to start indexing.'
					})}
				</p>
			{:else if filteredContent.length === 0}
				<p class="text-text-muted py-4 text-center text-sm">
					{$_('knowledgeStores.noContentForLibrary', {
						default: 'No items from the selected library are linked to this Knowledge Store.'
					})}
				</p>
			{:else}
				<div class="overflow-x-auto">
					<table class="divide-border min-w-full divide-y">
						<thead class="bg-surface-muted">
							<tr>
								<th class="type-label px-4 py-3 text-left">
									{$_('knowledgeStores.contentTitle', { default: 'Title' })}
								</th>
								<th class="type-label px-4 py-3 text-left">
									{$_('knowledgeStores.library', { default: 'Library' })}
								</th>
								<th class="type-label px-4 py-3 text-left">
									{$_('knowledgeStores.status', { default: 'Status' })}
								</th>
								<th class="type-label px-4 py-3 text-left">
									{$_('knowledgeStores.chunks', { default: 'Chunks' })}
								</th>
								<th class="type-label px-4 py-3 text-right">
									{$_('knowledgeStores.actions', { default: 'Actions' })}
								</th>
							</tr>
						</thead>
						<tbody class="divide-border bg-surface divide-y">
							{#each filteredContent as link (link.id)}
								{@const badge = statusBadgeProps(link.status)}
								<tr class="hover:bg-surface-sunken">
									<td class="px-4 py-3 text-sm">
										<div
											class="font-medium {link.item_deleted
												? 'text-text-muted italic'
												: 'text-text'}"
										>
											{link.item_title || link.library_item_id}
											{#if link.item_deleted}
												<span class="text-text-subtle ml-1 text-xs not-italic">
													{$_('knowledgeStores.deletedSuffix', { default: '(deleted)' })}
												</span>
											{/if}
										</div>
										<div class="type-caption">{link.library_item_id}</div>
									</td>
									<td class="px-4 py-3 text-sm">
										<div class={link.library_deleted ? 'text-text-muted italic' : 'text-text'}>
											{link.library_name || '—'}
											{#if link.library_deleted}
												<span class="text-text-subtle ml-1 text-xs not-italic">
													{$_('knowledgeStores.deletedSuffix', { default: '(deleted)' })}
												</span>
											{/if}
										</div>
									</td>
									<td class="px-4 py-3">
										<Badge variant={badge.variant} icon={badge.icon} spin={badge.spin}>
											{badge.label}
										</Badge>
										{#if link.error_message}
											<p class="text-danger mt-1 text-xs">{link.error_message}</p>
										{/if}
									</td>
									<td class="text-text-muted px-4 py-3 text-sm">
										{link.chunks_created ?? 0}
									</td>
									<td class="px-4 py-3">
										<div class="flex items-center justify-end gap-1">
											{#if link.library_id && link.library_item_id}
												<IconButton
													icon={ExternalLink}
													ariaLabel={$_('knowledgeStores.viewItem', { default: 'View item' })}
													tooltip={$_('knowledgeStores.viewItem', { default: 'View item' })}
													variant="ghost"
													size="sm"
													href={`${base}/libraries?section=libraries&view=detail&id=${encodeURIComponent(
														link.library_id
													)}#item-${encodeURIComponent(link.library_item_id)}`}
												/>
											{/if}
											{#if ks.is_owner}
												<Button
													variant="secondary"
													size="sm"
													iconLeftComponent={X}
													class="text-danger hover:bg-danger-subtle hover:text-danger-hover"
													onclick={() => requestRemoveContent(link)}
												>
													{$_('knowledgeStores.remove', { default: 'Remove' })}
												</Button>
											{/if}
										</div>
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}
		</Card>

		<!-- Test query card -->
		<Card
			title={$_('knowledgeStores.testQuery', { default: 'Test Query' })}
			description={$_('knowledgeStores.testQueryHelp', {
				default:
					'Run a similarity search against this Knowledge Store to verify it returns useful chunks.'
			})}
		>
			<div class="space-y-3">
				<div class="flex flex-wrap items-end gap-2">
					<div class="min-w-[240px] flex-1">
						<FormField
							type="search"
							bind:value={queryText}
							placeholder={$_('knowledgeStores.queryPlaceholder', {
								default: 'Ask a question...'
							})}
							leadingIcon={Search}
							onkeydown={(/** @type {KeyboardEvent} */ e) => {
								if (e.key === 'Enter' && !querying) runQuery();
							}}
						/>
					</div>
					<div class="w-24">
						<FormField
							type="number"
							label={$_('knowledgeStores.results', { default: 'Results' })}
							bind:value={queryTopK}
							min={1}
							max={20}
						/>
					</div>
					<Button
						variant="primary"
						iconLeftComponent={Search}
						loading={querying}
						disabled={!queryText.trim()}
						onclick={runQuery}
					>
						{$_('knowledgeStores.runQuery', { default: 'Query' })}
					</Button>
				</div>

				{#if queryError}
					<Banner variant="danger" size="sm" description={queryError} />
				{/if}

				{#if queryResults.length > 0}
					<div class="space-y-2">
						{#each queryResults as r, i (i)}
							<div class="border-border bg-surface rounded-md border p-3 text-sm">
								<div class="mb-1 flex items-center justify-between">
									<div class="text-text font-medium">
										{r.metadata?.source_title || r.metadata?.title || 'Source'}
									</div>
									<div class="type-caption">
										{$_('knowledgeStores.score', { default: 'score' })}:
										{(r.score ?? 0).toFixed(4)}
									</div>
								</div>
								<p class="text-text-muted text-sm whitespace-pre-wrap">{r.text}</p>
								{#if r.metadata?.permalink_markdown || r.metadata?.permalink_original || r.metadata?.permalink_page}
									<div class="mt-2 flex gap-3 text-xs">
										{#if r.metadata.permalink_original}
											<button
												type="button"
												class="text-brand hover:underline"
												onclick={() => openPermalink(r.metadata.permalink_original)}
											>
												{$_('knowledgeStores.permalinks.original', { default: 'Source' })}
											</button>
										{/if}
										{#if r.metadata.permalink_markdown}
											<button
												type="button"
												class="text-brand hover:underline"
												onclick={() => openPermalink(r.metadata.permalink_markdown)}
											>
												{$_('knowledgeStores.permalinks.markdown', { default: 'Markdown' })}
											</button>
										{/if}
										{#if r.metadata.permalink_page}
											<button
												type="button"
												class="text-brand hover:underline"
												onclick={() => openPermalink(r.metadata.permalink_page)}
											>
												{$_('knowledgeStores.permalinks.page', { default: 'Page' })}
											</button>
										{/if}
									</div>
								{/if}
							</div>
						{/each}
					</div>
				{/if}
			</div>
		</Card>

		<!-- Footer metadata -->
		<p class="type-caption text-right">
			{$_('knowledgeStores.created', { default: 'Created' })}: {formatDate(ks.created_at)}
			·
			{$_('knowledgeStores.updated', { default: 'Updated' })}: {formatDate(ks.updated_at)}
			{#if ks.owner_email}
				·
				{$_('knowledgeStores.owner', { default: 'Owner' })}: {ks.owner_email}
			{/if}
		</p>
	</div>
{/if}

<AddContentToKSModal
	bind:isOpen={showAddContent}
	{ksId}
	on:done={handleAddContentDone}
	on:close={() => (showAddContent = false)}
/>

<ConfirmationModal
	bind:isOpen={showRemoveModal}
	bind:isLoading={isRemoving}
	title={$_('knowledgeStores.removeModal.title', {
		default: 'Remove from Knowledge Store'
	})}
	message={$_('knowledgeStores.removeModal.message', {
		default: `Remove "${removeTarget.title}" from this Knowledge Store? Vectors will be deleted but the library item remains intact.`,
		values: { title: removeTarget.title }
	})}
	confirmText={$_('knowledgeStores.removeModal.confirm', { default: 'Remove' })}
	variant="danger"
	onconfirm={handleRemoveConfirm}
	oncancel={() => {
		showRemoveModal = false;
	}}
/>

<ConfirmationModal
	bind:isOpen={showDeleteModal}
	bind:isLoading={isDeleting}
	title={$_('knowledgeStores.deleteModal.title', { default: 'Delete Knowledge Store' })}
	message={$_('knowledgeStores.deleteModal.message', {
		default: `Delete Knowledge Store "${ks?.name ?? ''}"? This action cannot be undone. All vectors will be permanently removed. The library items linked to it will not be affected.`,
		values: { name: ks?.name ?? '' }
	})}
	confirmText={$_('knowledgeStores.deleteModal.confirm', { default: 'Delete' })}
	variant="danger"
	error={deleteError}
	onconfirm={handleDeleteKs}
	oncancel={() => {
		showDeleteModal = false;
		deleteError = '';
	}}
/>
