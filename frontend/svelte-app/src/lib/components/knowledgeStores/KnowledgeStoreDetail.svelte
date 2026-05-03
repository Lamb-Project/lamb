<!--
  @component KnowledgeStoreDetail
  Detail panel for a Knowledge Store: locked-config display, linked
  content list with status badges, "add more content" trigger, query
  test box, share toggle, delete.

  Reactively reloads when the libraryId prop changes (Marc's #336 finding).
-->
<script>
    import {
        getKnowledgeStore,
        updateKnowledgeStore,
        toggleSharing,
        removeContent,
        queryKnowledgeStore,
        getContentLinkStatus,
    } from '$lib/services/knowledgeStoreService';
    import { _ } from '$lib/i18n';
    import ConfirmationModal from '$lib/components/modals/ConfirmationModal.svelte';
    import AddContentToKSModal from './AddContentToKSModal.svelte';

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

    $effect(() => {
        if (ksId) {
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
            (c) => c.status === 'pending' || c.status === 'processing',
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
                description: editDescription,
            });
            editingMeta = false;
            showSuccess(
                $_('knowledgeStores.updateSuccess', {
                    default: 'Knowledge Store updated.',
                }),
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
                          default: 'Knowledge Store shared with organization.',
                      })
                    : $_('knowledgeStores.unshareSuccess', {
                          default: 'Knowledge Store is now private.',
                      }),
            );
        } catch (/** @type {unknown} */ err) {
            error = err instanceof Error ? err.message : 'Failed to toggle sharing';
        }
    }

    function requestRemoveContent(link) {
        removeTarget = {
            libraryItemId: link.library_item_id,
            title: link.item_title || link.library_item_id,
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
                    default: 'Content removed from Knowledge Store.',
                }),
            );
            await loadAll();
        } catch (/** @type {unknown} */ err) {
            error = err instanceof Error ? err.message : 'Remove failed';
        } finally {
            isRemoving = false;
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
                topK: queryTopK,
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

    async function handleAddContentDone() {
        showAddContent = false;
        showSuccess(
            $_('knowledgeStores.addContentSuccess', {
                default: 'Content queued for ingestion.',
            }),
        );
        await loadAll();
    }
</script>

{#if loading}
    <div class="bg-white shadow rounded-lg p-6">
        <div class="animate-pulse text-gray-500">
            {$_('knowledgeStores.loading', { default: 'Loading Knowledge Store...' })}
        </div>
    </div>
{:else if error}
    <div class="bg-white shadow rounded-lg p-6" role="alert">
        <p class="text-red-500">{error}</p>
    </div>
{:else if ks}
    {#if successMessage}
        <div
            class="mb-4 px-4 py-3 bg-green-50 border border-green-100 rounded text-sm text-green-700"
            role="status"
        >
            {successMessage}
        </div>
    {/if}

    <!-- Header card: name + locked config -->
    <div class="bg-white shadow rounded-lg overflow-hidden mb-4">
        <div class="px-6 py-5 border-b border-gray-200 flex items-start justify-between gap-4">
            <div class="flex-1 min-w-0">
                {#if editingMeta}
                    <div class="space-y-3">
                        <input
                            type="text"
                            bind:value={editName}
                            class="w-full px-3 py-2 border border-gray-300 rounded-md text-lg font-semibold"
                            placeholder={$_('knowledgeStores.namePlaceholder', { default: 'Name' })}
                        />
                        <textarea
                            bind:value={editDescription}
                            rows="2"
                            class="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                            placeholder={$_('knowledgeStores.descriptionPlaceholder', {
                                default: 'Description',
                            })}
                        ></textarea>
                        <div class="flex gap-2">
                            <button
                                type="button"
                                onclick={saveMeta}
                                disabled={savingMeta || !editName.trim()}
                                class="px-3 py-2 text-sm font-medium text-white rounded-md bg-[#2271b3] hover:bg-[#195a91] disabled:opacity-50"
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
                                class="px-3 py-2 text-sm font-medium text-gray-700 rounded-md border border-gray-300 hover:bg-gray-50"
                            >
                                {$_('common.cancel', { default: 'Cancel' })}
                            </button>
                        </div>
                    </div>
                {:else}
                    <h2 class="text-xl font-semibold text-gray-900">{ks.name}</h2>
                    {#if ks.description}
                        <p class="text-sm text-gray-600 mt-1">{ks.description}</p>
                    {/if}
                    <p class="text-xs text-gray-400 mt-1">{ks.id}</p>
                {/if}
            </div>
            <div class="flex flex-col gap-2 items-end">
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
                        class="text-xs px-2 py-1 rounded border {ks.is_shared
                            ? 'border-green-300 text-green-700 bg-green-50 hover:bg-green-100'
                            : 'border-gray-300 text-gray-600 bg-gray-50 hover:bg-gray-100'}"
                    >
                        {ks.is_shared
                            ? $_('knowledgeStores.sharing.shared', { default: 'Shared' })
                            : $_('knowledgeStores.sharing.private', { default: 'Private' })}
                    </button>
                {/if}
            </div>
        </div>

        <!-- Locked configuration -->
        <div class="px-6 py-4 bg-gray-50 grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
            <div>
                <div class="font-semibold uppercase text-gray-500">
                    {$_('knowledgeStores.chunking', { default: 'Chunking' })}
                </div>
                <div class="text-gray-800 mt-0.5">{ks.chunking_strategy}</div>
            </div>
            <div>
                <div class="font-semibold uppercase text-gray-500">
                    {$_('knowledgeStores.embeddingVendor', { default: 'Embedding' })}
                </div>
                <div class="text-gray-800 mt-0.5">{ks.embedding_vendor}</div>
            </div>
            <div>
                <div class="font-semibold uppercase text-gray-500">
                    {$_('knowledgeStores.embeddingModel', { default: 'Model' })}
                </div>
                <div class="text-gray-800 mt-0.5 break-all">{ks.embedding_model}</div>
            </div>
            <div>
                <div class="font-semibold uppercase text-gray-500">
                    {$_('knowledgeStores.vectorDb', { default: 'Vector DB' })}
                </div>
                <div class="text-gray-800 mt-0.5">{ks.vector_db_backend}</div>
            </div>
        </div>
        <div class="px-6 py-2 bg-yellow-50 border-t border-yellow-100 text-xs text-yellow-800">
            {$_('knowledgeStores.lockedNotice', {
                default:
                    'Chunking strategy, embedding vendor / model, and vector DB are locked at creation and cannot be changed.',
            })}
        </div>
    </div>

    <!-- Linked content -->
    <div class="bg-white shadow rounded-lg overflow-hidden mb-4">
        <div class="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
            <h3 class="text-base font-semibold text-gray-900">
                {$_('knowledgeStores.linkedContent', { default: 'Linked Library Content' })}
                <span class="ml-2 text-sm text-gray-400">({content.length})</span>
            </h3>
            {#if ks.is_owner}
                <button
                    type="button"
                    onclick={() => (showAddContent = true)}
                    class="px-3 py-2 text-sm font-medium text-white rounded-md bg-[#2271b3] hover:bg-[#195a91]"
                >
                    + {$_('knowledgeStores.addContent', { default: 'Add Content' })}
                </button>
            {/if}
        </div>

        {#if content.length === 0}
            <div class="p-6 text-center text-gray-500">
                {$_('knowledgeStores.noContent', {
                    default: 'No library content linked yet. Add content to start indexing.',
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
                    <tbody class="bg-white divide-y divide-gray-200">
                        {#each content as link (link.id)}
                            <tr class="hover:bg-gray-50">
                                <td class="px-4 py-3 text-sm">
                                    <div class="font-medium text-gray-900">
                                        {link.item_title || link.library_item_id}
                                    </div>
                                    <div class="text-xs text-gray-400">{link.library_item_id}</div>
                                </td>
                                <td class="px-4 py-3 text-sm text-gray-700">
                                    {link.library_name || '—'}
                                </td>
                                <td class="px-4 py-3">
                                    <span
                                        class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium {statusBadgeClass(
                                            link.status,
                                        )}"
                                    >
                                        {link.status}
                                    </span>
                                    {#if link.error_message}
                                        <p class="text-xs text-red-500 mt-1">
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
    <div class="bg-white shadow rounded-lg overflow-hidden mb-4">
        <div class="px-6 py-4 border-b border-gray-200">
            <h3 class="text-base font-semibold text-gray-900">
                {$_('knowledgeStores.testQuery', { default: 'Test Query' })}
            </h3>
            <p class="text-xs text-gray-500 mt-1">
                {$_('knowledgeStores.testQueryHelp', {
                    default:
                        'Run a similarity search against this Knowledge Store to verify it returns useful chunks.',
                })}
            </p>
        </div>
        <div class="px-6 py-4 space-y-3">
            <div class="flex gap-2">
                <input
                    type="text"
                    bind:value={queryText}
                    placeholder={$_('knowledgeStores.queryPlaceholder', {
                        default: 'Ask a question...',
                    })}
                    class="flex-1 px-3 py-2 border border-gray-300 rounded-md text-sm"
                    onkeydown={(e) => {
                        if (e.key === 'Enter' && !querying) runQuery();
                    }}
                />
                <input
                    type="number"
                    bind:value={queryTopK}
                    min="1"
                    max="20"
                    class="w-20 px-3 py-2 border border-gray-300 rounded-md text-sm"
                    title={$_('knowledgeStores.topK', { default: 'Top K' })}
                />
                <button
                    type="button"
                    onclick={runQuery}
                    disabled={querying || !queryText.trim()}
                    class="px-4 py-2 text-sm font-medium text-white rounded-md bg-[#2271b3] hover:bg-[#195a91] disabled:opacity-50"
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
                        <div class="p-3 border border-gray-200 rounded text-sm">
                            <div class="flex items-center justify-between mb-1">
                                <div class="font-medium text-gray-900">
                                    {r.metadata?.source_title || r.metadata?.title || 'Source'}
                                </div>
                                <div class="text-xs text-gray-500">
                                    {$_('knowledgeStores.score', { default: 'score' })}: {(
                                        r.score ?? 0
                                    ).toFixed(4)}
                                </div>
                            </div>
                            <p class="text-gray-700 text-sm whitespace-pre-wrap">{r.text}</p>
                            {#if r.metadata?.permalink_markdown || r.metadata?.permalink_original || r.metadata?.permalink_page}
                                <div class="mt-2 flex gap-3 text-xs">
                                    {#if r.metadata.permalink_original}
                                        <!-- eslint-disable svelte/no-navigation-without-resolve -->
                                        <a
                                            href={r.metadata.permalink_original}
                                            class="text-[#2271b3] hover:underline"
                                            target="_blank"
                                            rel="noopener noreferrer"
                                        >
                                            {$_('knowledgeStores.permalinks.original', {
                                                default: 'Source',
                                            })}
                                        </a>
                                    {/if}
                                    {#if r.metadata.permalink_markdown}
                                        <a
                                            href={r.metadata.permalink_markdown}
                                            class="text-[#2271b3] hover:underline"
                                            target="_blank"
                                            rel="noopener noreferrer"
                                        >
                                            {$_('knowledgeStores.permalinks.markdown', {
                                                default: 'Markdown',
                                            })}
                                        </a>
                                    {/if}
                                    {#if r.metadata.permalink_page}
                                        <a
                                            href={r.metadata.permalink_page}
                                            class="text-[#2271b3] hover:underline"
                                            target="_blank"
                                            rel="noopener noreferrer"
                                        >
                                            {$_('knowledgeStores.permalinks.page', { default: 'Page' })}
                                        </a>
                                    {/if}
                                </div>
                            {/if}
                        </div>
                    {/each}
                </div>
            {/if}
        </div>
    </div>
    <!-- eslint-enable svelte/no-navigation-without-resolve -->

    <!-- Footer metadata -->
    <div class="text-xs text-gray-400 text-right">
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
/>

<ConfirmationModal
    bind:isOpen={showRemoveModal}
    bind:isLoading={isRemoving}
    title={$_('knowledgeStores.removeModal.title', {
        default: 'Remove from Knowledge Store',
    })}
    message={$_('knowledgeStores.removeModal.message', {
        default: `Remove "${removeTarget.title}" from this Knowledge Store? Vectors will be deleted but the library item remains intact.`,
    })}
    confirmText={$_('knowledgeStores.removeModal.confirm', { default: 'Remove' })}
    variant="danger"
    onconfirm={handleRemoveConfirm}
    oncancel={() => {
        showRemoveModal = false;
    }}
/>
