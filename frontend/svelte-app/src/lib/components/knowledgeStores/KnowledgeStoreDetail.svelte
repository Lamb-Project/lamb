<!--
  @component KnowledgeStoreDetail
  Detail panel for a Knowledge Store: locked-config display, linked
  content list with status badges, "add more content" trigger, query
  test box, share toggle, delete.

  Reactively reloads when the libraryId prop changes (Marc's #336 finding).
-->
<script>
	import { goto } from '$app/navigation';
	import { base } from '$app/paths';
	import { page } from '$app/stores';
	import {
		getKnowledgeStore,
		updateKnowledgeStore,
		toggleSharing,
		removeContent,
		queryKnowledgeStore,
		getContentLinkStatus
	} from '$lib/services/knowledgeStoreService';
	import { _ } from '$lib/i18n';
	import ConfirmationModal from '$lib/components/modals/ConfirmationModal.svelte';
	import AddContentToKSModal from '$lib/components/knowledgeStores/AddContentToKSModal.svelte';

	/** @type {{ ksId: string }} */
	let { ksId } = $props();

	let ks = $state(null);
	let content = $state([]);
	let loading = $state(true);
	let error = $state('');
	let successMessage = $state('');

	// Edit state
	let editingMeta = $state(false);
	let editName = $state('');
	let editDescription = $state('');
	let savingMeta = $state(false);

	// Query test
	let queryText = $state('');
	let queryTopK = $state(5);
	let querying = $state(false);
	let queryResults = $state([]);
	let queryError = $state('');

	// Modals
	let showAddContent = $state(false);
	let showRemoveModal = $state(false);
	let removeTarget = $state({ libraryItemId: '', title: '' });
	let isRemoving = $state(false);

	// Polling
	let pollTimer = null;

	// Library filter: restricts the linked-content table to items from one
	// library. ``''`` means "all libraries". The initial value is seeded from
	// the URL (``?library=<id|name>``) so links from LibraryDetail land on
	// the pre-filtered view.
	let libraryFilter = $state('');

	// Distinct library options derived from the current content list. Each
	// entry carries the library_id when available (preferred for matching)
	// plus the display name. We dedupe by id-or-name and keep names sorted.
	let libraryOptions = $derived.by(() => {
		const seen = new Map();
		for (const link of content || []) {
			const id = link.library_id || '';
			const name = link.library_name || '';
			if (!id && !name) continue;
			const key = id || `name:${name}`;
			if (!seen.has(key)) {
				seen.set(key, { id, name: name || id });
			}
		}
		return Array.from(seen.values()).sort((a, b) =>
			a.name.localeCompare(b.name)
		);
	});

	// Filtered content: kept as a derived view so polling-driven updates to
	// individual rows propagate without re-applying the filter manually.
	let filteredContent = $derived.by(() => {
		if (!libraryFilter) return content;
		return (content || []).filter((link) => {
			if (link.library_id && link.library_id === libraryFilter) return true;
			if ((link.library_name || '') === libraryFilter) return true;
			return false;
		});
	});

	$effect(() => {
		if (ksId) {
			// Seed the filter from the URL once per ksId so a deep link like
			// /knowledge-stores/<ks>?library=<id> opens pre-filtered.
			try {
				const fromQuery = $page.url.searchParams.get('library');
				if (fromQuery) libraryFilter = fromQuery;
			} catch {
				// $page may not be ready on first render — ignore.
			}
			loadAll();
		}
		return () => {
			if (pollTimer) clearTimeout(pollTimer);
		};
	});

	async function loadAll() {
		loading = true;
		error = '';
		try {
			ks = await getKnowledgeStore(ksId);
			content = ks?.content ?? [];
			editName = ks?.name ?? '';
			editDescription = ks?.description ?? '';
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
			(c) => c.status === 'pending' || c.status === 'processing'
		);
		if (inFlight.length === 0) return;
		pollTimer = setTimeout(async () => {
			for (const link of inFlight) {
				try {
					const updated = await getContentLinkStatus(ksId, link.library_item_id);
					const idx = content.findIndex((c) => c.id === link.id);
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

	function showSuccess(msg) {
		successMessage = msg;
		setTimeout(() => {
			successMessage = '';
		}, 4000);
	}

	async function saveMeta() {
		savingMeta = true;
		try {
			await updateKnowledgeStore(ksId, {
				name: editName,
				description: editDescription
			});
			editingMeta = false;
			showSuccess(
				$_('knowledgeStores.updateSuccess', {
					default: 'Knowledge Store updated.'
				})
			);
			await loadAll();
		} catch (/** @type {unknown} */ err) {
			error = err instanceof Error ? err.message : 'Update failed';
		} finally {
			savingMeta = false;
		}
	}

	async function handleToggleSharing() {
		if (!ks) return;
		try {
			const newState = !ks.is_shared;
			await toggleSharing(ksId, newState);
			ks = { ...ks, is_shared: newState };
			showSuccess(
				newState
					? $_('knowledgeStores.shareSuccess', {
							default: 'Knowledge Store shared with organization.'
						})
					: $_('knowledgeStores.unshareSuccess', {
							default: 'Knowledge Store is now private.'
						})
			);
		} catch (/** @type {unknown} */ err) {
			error = err instanceof Error ? err.message : 'Failed to toggle sharing';
		}
	}

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
			showSuccess(
				$_('knowledgeStores.removeContentSuccess', {
					default: 'Content removed from Knowledge Store.'
				})
			);
			await loadAll();
		} catch (/** @type {unknown} */ err) {
			error = err instanceof Error ? err.message : 'Remove failed';
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

	function statusBadgeClass(status) {
		switch (status) {
			case 'ready':
				return 'bg-green-100 text-green-800';
			case 'failed':
				return 'bg-red-100 text-red-800';
			case 'processing':
				return 'bg-blue-100 text-blue-800';
			default:
				return 'bg-gray-100 text-gray-700';
		}
	}

	function formatDate(ts) {
		if (!ts) return '';
		const d = typeof ts === 'number' ? new Date(ts * 1000) : new Date(ts);
		return d.toLocaleString();
	}

	/** @param {CustomEvent<Record<string, any>>} event */
	async function handleAddContentDone(event) {
		const refs = event?.detail || {};
		showAddContent = false;
		showSuccess(
			$_('knowledgeStores.addContentSuccess', {
				default: 'Content queued for ingestion.'
			})
		);
		// Honour the user's choice from Step 9. "Open Library" navigates
		// to the library detail page; "Open Knowledge Store" or
		// "Create another" stay on this KS and just refresh.
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

{#if loading}
	<div class="rounded-lg bg-white p-6 shadow">
		<div class="animate-pulse text-gray-500">
			{$_('knowledgeStores.loading', { default: 'Loading Knowledge Store...' })}
		</div>
	</div>
{:else if error}
	<div class="rounded-lg bg-white p-6 shadow" role="alert">
		<p class="text-red-500">{error}</p>
	</div>
{:else if ks}
	{#if successMessage}
		<div
			class="mb-4 rounded border border-green-100 bg-green-50 px-4 py-3 text-sm text-green-700"
			role="status"
		>
			{successMessage}
		</div>
	{/if}

	<!-- Header card: name + locked config -->
	<div class="mb-4 overflow-hidden rounded-lg bg-white shadow">
		<div class="flex items-start justify-between gap-4 border-b border-gray-200 px-6 py-5">
			<div class="min-w-0 flex-1">
				{#if editingMeta}
					<div class="space-y-3">
						<input
							type="text"
							bind:value={editName}
							class="w-full rounded-md border border-gray-300 px-3 py-2 text-lg font-semibold"
							placeholder={$_('knowledgeStores.namePlaceholder', { default: 'Name' })}
						/>
						<textarea
							bind:value={editDescription}
							rows="2"
							class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
							placeholder={$_('knowledgeStores.descriptionPlaceholder', {
								default: 'Description'
							})}
						></textarea>
						<div class="flex gap-2">
							<button
								type="button"
								onclick={saveMeta}
								disabled={savingMeta || !editName.trim()}
								class="rounded-md bg-[#2271b3] px-3 py-2 text-sm font-medium text-white hover:bg-[#195a91] disabled:opacity-50"
							>
								{savingMeta
									? $_('common.saving', { default: 'Saving...' })
									: $_('common.save', { default: 'Save' })}
							</button>
							<button
								type="button"
								onclick={() => {
									editingMeta = false;
									editName = ks.name;
									editDescription = ks.description || '';
								}}
								class="rounded-md border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
							>
								{$_('common.cancel', { default: 'Cancel' })}
							</button>
						</div>
					</div>
				{:else}
					<h2 class="text-xl font-semibold text-gray-900">{ks.name}</h2>
					{#if ks.description}
						<p class="mt-1 line-clamp-3 text-sm break-words text-gray-600" title={ks.description}>
							{ks.description}
						</p>
					{/if}
					<p class="mt-1 text-xs text-gray-400">{ks.id}</p>
				{/if}
			</div>
			<div class="flex flex-col items-end gap-2">
				{#if ks.is_owner && !editingMeta}
					<button
						type="button"
						onclick={() => (editingMeta = true)}
						class="text-sm text-[#2271b3] hover:underline"
					>
						{$_('knowledgeStores.edit', { default: 'Edit' })}
					</button>
					<button
						type="button"
						onclick={handleToggleSharing}
						class="rounded border px-2 py-1 text-xs {ks.is_shared
							? 'border-green-300 bg-green-50 text-green-700 hover:bg-green-100'
							: 'border-gray-300 bg-gray-50 text-gray-600 hover:bg-gray-100'}"
					>
						{ks.is_shared
							? $_('knowledgeStores.sharing.shared', { default: 'Shared' })
							: $_('knowledgeStores.sharing.private', { default: 'Private' })}
					</button>
				{/if}
			</div>
		</div>

		<!-- Locked configuration -->
		<div class="grid grid-cols-2 gap-4 bg-gray-50 px-6 py-4 text-xs sm:grid-cols-4">
			<div>
				<div class="font-semibold text-gray-500 uppercase">
					{$_('knowledgeStores.chunking', { default: 'Chunking' })}
				</div>
				<div class="mt-0.5 text-gray-800">{ks.chunking_strategy}</div>
			</div>
			<div>
				<div class="font-semibold text-gray-500 uppercase">
					{$_('knowledgeStores.embeddingVendor', { default: 'Embedding' })}
				</div>
				<div class="mt-0.5 text-gray-800">{ks.embedding_vendor}</div>
			</div>
			<div>
				<div class="font-semibold text-gray-500 uppercase">
					{$_('knowledgeStores.embeddingModel', { default: 'Model' })}
				</div>
				<div class="mt-0.5 break-all text-gray-800">{ks.embedding_model}</div>
			</div>
			<div>
				<div class="font-semibold text-gray-500 uppercase">
					{$_('knowledgeStores.vectorDb', { default: 'Vector DB' })}
				</div>
				<div class="mt-0.5 text-gray-800">{ks.vector_db_backend}</div>
			</div>
		</div>
		<div class="border-t border-yellow-100 bg-yellow-50 px-6 py-2 text-xs text-yellow-800">
			{$_('knowledgeStores.lockedNotice', {
				default:
					'Chunking strategy, embedding vendor / model, and vector DB are locked at creation and cannot be changed.'
			})}
		</div>
	</div>

	<!-- Linked content -->
	<div class="mb-4 overflow-hidden rounded-lg bg-white shadow">
		<div class="flex flex-wrap items-center justify-between gap-3 border-b border-gray-200 px-6 py-4">
			<h3 class="text-base font-semibold text-gray-900">
				{$_('knowledgeStores.linkedContent', { default: 'Linked Library Content' })}
				<span class="ml-2 text-sm text-gray-400">
					{#if libraryFilter}
						({filteredContent.length} / {content.length})
					{:else}
						({content.length})
					{/if}
				</span>
			</h3>
			<div class="flex items-center gap-3">
				{#if libraryOptions.length > 1 || libraryFilter}
					<label class="flex items-center gap-2 text-xs text-gray-600">
						<span>{$_('knowledgeStores.filterLibrary', { default: 'Library' })}:</span>
						<select
							bind:value={libraryFilter}
							class="rounded-md border border-gray-300 px-2 py-1 text-xs"
						>
							<option value="">
								{$_('knowledgeStores.filterLibraryAll', { default: 'All libraries' })}
							</option>
							{#each libraryOptions as opt (opt.id || opt.name)}
								<option value={opt.id || opt.name}>{opt.name}</option>
							{/each}
						</select>
						{#if libraryFilter}
							<button
								type="button"
								onclick={() => (libraryFilter = '')}
								class="text-xs text-gray-500 hover:text-gray-800"
								title={$_('knowledgeStores.filterLibraryClear', { default: 'Clear filter' })}
							>
								×
							</button>
						{/if}
					</label>
				{/if}
				{#if ks.is_owner}
					<button
						type="button"
						onclick={() => (showAddContent = true)}
						class="rounded-md bg-[#2271b3] px-3 py-2 text-sm font-medium text-white hover:bg-[#195a91]"
					>
						+ {$_('knowledgeStores.addContent', { default: 'Add Content' })}
					</button>
				{/if}
			</div>
		</div>

		{#if content.length === 0}
			<div class="p-6 text-center text-gray-500">
				{$_('knowledgeStores.noContent', {
					default: 'No library content linked yet. Add content to start indexing.'
				})}
			</div>
		{:else if filteredContent.length === 0}
			<div class="p-6 text-center text-sm text-gray-500">
				{$_('knowledgeStores.noContentForLibrary', {
					default: 'No items from the selected library are linked to this Knowledge Store.'
				})}
			</div>
		{:else}
			<div class="overflow-x-auto">
				<table class="min-w-full divide-y divide-gray-200">
					<thead class="bg-gray-50">
						<tr>
							<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
								{$_('knowledgeStores.contentTitle', { default: 'Title' })}
							</th>
							<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
								{$_('knowledgeStores.library', { default: 'Library' })}
							</th>
							<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
								{$_('knowledgeStores.status', { default: 'Status' })}
							</th>
							<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
								{$_('knowledgeStores.chunks', { default: 'Chunks' })}
							</th>
							<th class="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">
								{$_('knowledgeStores.actions', { default: 'Actions' })}
							</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-gray-200 bg-white">
						{#each filteredContent as link (link.id)}
							<tr class="hover:bg-gray-50">
								<td class="px-4 py-3 text-sm">
									<!-- item_title is COALESCEd server-side: live title when the
									     library_items row exists, otherwise the original filename
									     / video_url / url from the library.upload audit row.
									     item_deleted=true means the live row is gone. -->
									<div
										class="font-medium {link.item_deleted ? 'text-gray-500 italic' : 'text-gray-900'}"
									>
										{link.item_title || link.library_item_id}
										{#if link.item_deleted}
											<span class="ml-1 text-xs not-italic text-gray-400">
												{$_('knowledgeStores.deletedSuffix', { default: '(deleted)' })}
											</span>
										{/if}
									</div>
									<div class="text-xs text-gray-400">{link.library_item_id}</div>
								</td>
								<td class="px-4 py-3 text-sm">
									<!-- library_name follows the same COALESCE pattern; falls
									     back to the historical name from the library.create
									     audit row when the live library was deleted. -->
									<div
										class="{link.library_deleted ? 'text-gray-500 italic' : 'text-gray-700'}"
									>
										{link.library_name || '—'}
										{#if link.library_deleted}
											<span class="ml-1 text-xs not-italic text-gray-400">
												{$_('knowledgeStores.deletedSuffix', { default: '(deleted)' })}
											</span>
										{/if}
									</div>
								</td>
								<td class="px-4 py-3">
									<span
										class="inline-flex items-center rounded px-2 py-0.5 text-xs font-medium {statusBadgeClass(
											link.status
										)}"
									>
										{link.status}
									</span>
									{#if link.error_message}
										<p class="mt-1 text-xs text-red-500">
											{link.error_message}
										</p>
									{/if}
								</td>
								<td class="px-4 py-3 text-sm text-gray-700">
									{link.chunks_created ?? 0}
								</td>
								<td class="px-4 py-3 text-right">
									{#if ks.is_owner}
										<button
											type="button"
											onclick={() => requestRemoveContent(link)}
											class="text-sm text-red-600 hover:text-red-900"
										>
											{$_('knowledgeStores.remove', { default: 'Remove' })}
										</button>
									{/if}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	</div>

	<!-- Test query -->
	<div class="mb-4 overflow-hidden rounded-lg bg-white shadow">
		<div class="border-b border-gray-200 px-6 py-4">
			<h3 class="text-base font-semibold text-gray-900">
				{$_('knowledgeStores.testQuery', { default: 'Test Query' })}
			</h3>
			<p class="mt-1 text-xs text-gray-500">
				{$_('knowledgeStores.testQueryHelp', {
					default:
						'Run a similarity search against this Knowledge Store to verify it returns useful chunks.'
				})}
			</p>
		</div>
		<div class="space-y-3 px-6 py-4">
			<div class="flex gap-2">
				<input
					type="text"
					bind:value={queryText}
					placeholder={$_('knowledgeStores.queryPlaceholder', {
						default: 'Ask a question...'
					})}
					class="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm"
					onkeydown={(e) => {
						if (e.key === 'Enter' && !querying) runQuery();
					}}
				/>
				<label class="flex items-center gap-1 text-sm text-gray-600">
					<span>{$_('knowledgeStores.results', { default: 'Results' })}</span>
					<input
						type="number"
						bind:value={queryTopK}
						min="1"
						max="20"
						class="w-16 rounded-md border border-gray-300 px-2 py-2 text-sm"
					/>
				</label>
				<button
					type="button"
					onclick={runQuery}
					disabled={querying || !queryText.trim()}
					class="rounded-md bg-[#2271b3] px-4 py-2 text-sm font-medium text-white hover:bg-[#195a91] disabled:opacity-50"
				>
					{querying
						? $_('knowledgeStores.querying', { default: 'Querying...' })
						: $_('knowledgeStores.runQuery', { default: 'Query' })}
				</button>
			</div>

			{#if queryError}
				<div class="text-sm text-red-500" role="alert">{queryError}</div>
			{/if}

			{#if queryResults.length > 0}
				<div class="space-y-2">
					{#each queryResults as r, i (i)}
						<div class="rounded border border-gray-200 p-3 text-sm">
							<div class="mb-1 flex items-center justify-between">
								<div class="font-medium text-gray-900">
									{r.metadata?.source_title || r.metadata?.title || 'Source'}
								</div>
								<div class="text-xs text-gray-500">
									{$_('knowledgeStores.score', { default: 'score' })}: {(r.score ?? 0).toFixed(4)}
								</div>
							</div>
							<p class="text-sm whitespace-pre-wrap text-gray-700">{r.text}</p>
							{#if r.metadata?.permalink_markdown || r.metadata?.permalink_original || r.metadata?.permalink_page}
								<div class="mt-2 flex gap-3 text-xs">
									{#if r.metadata.permalink_original}
										<button
											type="button"
											class="text-[#2271b3] hover:underline"
											onclick={() => openPermalink(r.metadata.permalink_original)}
										>
											{$_('knowledgeStores.permalinks.original', {
												default: 'Source'
											})}
										</button>
									{/if}
									{#if r.metadata.permalink_markdown}
										<button
											type="button"
											class="text-[#2271b3] hover:underline"
											onclick={() => openPermalink(r.metadata.permalink_markdown)}
										>
											{$_('knowledgeStores.permalinks.markdown', {
												default: 'Markdown'
											})}
										</button>
									{/if}
									{#if r.metadata.permalink_page}
										<button
											type="button"
											class="text-[#2271b3] hover:underline"
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
	</div>

	<!-- Footer metadata -->
	<div class="text-right text-xs text-gray-400">
		{$_('knowledgeStores.created', { default: 'Created' })}: {formatDate(ks.created_at)}
		·
		{$_('knowledgeStores.updated', { default: 'Updated' })}: {formatDate(ks.updated_at)}
		{#if ks.owner_email}
			·
			{$_('knowledgeStores.owner', { default: 'Owner' })}: {ks.owner_email}
		{/if}
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
		default: `Remove "${removeTarget.title}" from this Knowledge Store? Vectors will be deleted but the library item remains intact.`
	})}
	confirmText={$_('knowledgeStores.removeModal.confirm', { default: 'Remove' })}
	variant="danger"
	onconfirm={handleRemoveConfirm}
	oncancel={() => {
		showRemoveModal = false;
	}}
/>
