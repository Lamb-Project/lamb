<!--
  @component LibraryDetail
  Shows library metadata, item list, file upload, and import actions.
  Receives libraryId as a prop from the page.
-->
<script>
    import { onMount } from 'svelte';
    import {
        getLibrary, getItems, uploadFile, deleteItem,
        getItemStatus, exportLibrary, toggleSharing,
    } from '$lib/services/libraryService';
    import { _ } from '$lib/i18n';
    import { user } from '$lib/stores/userStore';
    import ConfirmationModal from '$lib/components/modals/ConfirmationModal.svelte';
    import ImportModal from '$lib/components/modals/ImportModal.svelte';

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
    let pendingItemIds = $state(new Set());
    let pollInterval = $state(null);

    // Delete item modal
    let showDeleteItemModal = $state(false);
    let isDeletingItem = $state(false);
    let deleteItemTarget = $state({ id: '', title: '' });

    // Import modal ref
    let importModal;

    let isOwner = $derived(library?.is_owner ?? false);

    onMount(() => {
        return () => {
            if (pollInterval) clearInterval(pollInterval);
        };
    });

    $effect(() => {
        // Re-load data whenever libraryId changes (including the initial value)
        if (libraryId) {
            loadData();
        }
    });

    async function loadData() {
        if (pollInterval) { clearInterval(pollInterval); pollInterval = null; }
        loading = true;
        error = '';
        try {
            const [lib, itemsData] = await Promise.all([
                getLibrary(libraryId),
                getItems(libraryId, { limit: 100 }),
            ]);
            library = lib;
            items = itemsData.items || [];
            totalItems = itemsData.total || items.length;
            startPollingIfNeeded();
        } catch (/** @type {unknown} */ err) {
            console.error('Error loading library:', err);
            error = err instanceof Error ? err.message : 'Failed to load library';
        } finally {
            loading = false;
        }
    }

    function startPollingIfNeeded() {
        if (pollInterval) clearInterval(pollInterval);
        const pending = items.filter(i => i.status === 'processing' || i.status === 'pending');
        if (pending.length === 0) return;
        pendingItemIds = new Set(pending.map(i => i.id));
        pollInterval = setInterval(pollPendingItems, 3000);
    }

    async function pollPendingItems() {
        if (pendingItemIds.size === 0) {
            clearInterval(pollInterval);
            pollInterval = null;
            return;
        }
        for (const itemId of [...pendingItemIds]) {
            try {
                const status = await getItemStatus(libraryId, itemId);
                if (status.status === 'ready' || status.status === 'failed') {
                    pendingItemIds.delete(itemId);
                    pendingItemIds = new Set(pendingItemIds);
                    const idx = items.findIndex(i => i.id === itemId);
                    if (idx !== -1) {
                        items[idx] = { ...items[idx], status: status.status };
                        items = [...items];
                    }
                }
            } catch {
                // Ignore individual poll errors
            }
        }
        if (pendingItemIds.size === 0 && pollInterval) {
            clearInterval(pollInterval);
            pollInterval = null;
        }
    }

    function showSuccess(msg) {
        successMessage = msg;
        setTimeout(() => { successMessage = ''; }, 4000);
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
            const result = await uploadFile(libraryId, selectedFile, {
                title: fileTitle.trim() || selectedFile.name,
                pluginName: pluginForFile(selectedFile),
            });
            selectedFile = null;
            fileTitle = '';
            showSuccess($_('libraries.uploadSuccess', { default: 'File uploaded. Processing...' }));
            await loadData();
        } catch (/** @type {unknown} */ err) {
            error = err instanceof Error ? err.message : 'Upload failed';
        } finally {
            uploading = false;
        }
    }

    // Import callback
    async function handleImported() {
        showSuccess($_('libraries.importSuccess', { default: 'Import started.' }));
        await loadData();
    }

    // Delete item
    function requestDeleteItem(item) {
        deleteItemTarget = { id: item.id, title: item.title };
        showDeleteItemModal = true;
    }

    async function handleDeleteItemConfirm() {
        isDeletingItem = true;
        try {
            await deleteItem(libraryId, deleteItemTarget.id);
            showDeleteItemModal = false;
            showSuccess($_('libraries.itemDeleteSuccess', { default: 'Item deleted.' }));
            await loadData();
        } catch (/** @type {unknown} */ err) {
            error = err instanceof Error ? err.message : 'Delete failed';
        } finally {
            isDeletingItem = false;
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
            showSuccess(library.is_shared
                ? $_('libraries.shareSuccess', { default: 'Library shared.' })
                : $_('libraries.unshareSuccess', { default: 'Library is now private.' }));
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
            case 'ready': return 'bg-green-100 text-green-800';
            case 'processing': case 'pending': return 'bg-yellow-100 text-yellow-800';
            case 'failed': return 'bg-red-100 text-red-800';
            default: return 'bg-gray-100 text-gray-800';
        }
    }
</script>

{#if loading}
    <div class="p-6 text-center">
        <div class="animate-pulse text-gray-500">{$_('libraries.loading', { default: 'Loading...' })}</div>
    </div>
{:else if error && !library}
    <div class="p-6 text-center" role="alert">
        <p class="text-red-500">{error}</p>
    </div>
{:else if library}
    <div class="space-y-6">
        <!-- Success banner -->
        {#if successMessage}
            <div class="p-3 bg-green-50 border border-green-200 rounded-md text-sm text-green-700" role="status">{successMessage}</div>
        {/if}
        {#if error}
            <div class="p-3 bg-red-50 border border-red-200 rounded-md text-sm text-red-700" role="alert">{error}</div>
        {/if}

        <!-- Metadata card -->
        <div class="bg-white shadow rounded-lg p-6">
            <div class="flex items-start justify-between">
                <div>
                    <h2 class="text-xl font-semibold text-gray-900">{library.name}</h2>
                    {#if library.description}
                        <p class="mt-1 text-sm text-gray-500">{library.description}</p>
                    {/if}
                </div>
                <div class="flex gap-2">
                    {#if isOwner}
                        <button
                            type="button"
                            onclick={handleToggleSharing}
                            class="text-xs px-3 py-1.5 rounded border {library.is_shared ? 'border-green-300 text-green-700 bg-green-50 hover:bg-green-100' : 'border-gray-300 text-gray-600 bg-gray-50 hover:bg-gray-100'}"
                        >
                            {library.is_shared
                                ? $_('libraries.sharing.shared', { default: 'Shared' })
                                : $_('libraries.sharing.private', { default: 'Private' })}
                        </button>
                    {/if}
                    <button
                        type="button"
                        onclick={handleExport}
                        class="text-xs px-3 py-1.5 rounded border border-gray-300 text-gray-600 bg-gray-50 hover:bg-gray-100"
                    >
                        {$_('libraries.export', { default: 'Export' })}
                    </button>
                </div>
            </div>
            <dl class="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
                <div>
                    <dt class="text-gray-500">{$_('libraries.items.title', { default: 'Items' })}</dt>
                    <dd class="font-medium text-gray-900">{totalItems}</dd>
                </div>
                <div>
                    <dt class="text-gray-500">{$_('libraries.owner', { default: 'Owner' })}</dt>
                    <dd class="font-medium text-gray-900">{library.owner_name || library.owner_email || '-'}</dd>
                </div>
                <div>
                    <dt class="text-gray-500">{$_('libraries.createdAt', { default: 'Created' })}</dt>
                    <dd class="font-medium text-gray-900">{formatDate(library.created_at)}</dd>
                </div>
                <div>
                    <dt class="text-gray-500">ID</dt>
                    <dd class="font-mono text-xs text-gray-500 truncate" title={library.id}>{library.id}</dd>
                </div>
            </dl>
        </div>

        {#if isOwner || library.is_shared}
            <div class="bg-white shadow rounded-lg p-6">
                <h3 class="text-base font-semibold text-gray-900 mb-4">
                    {$_('libraries.addContent', { default: 'Add Content' })}
                </h3>
                <div class="flex flex-wrap items-end gap-4">
                    <div class="flex-1 min-w-[200px]">
                        <label for="upload-file" class="block text-sm font-medium text-gray-700 mb-1">
                            {$_('libraries.uploadFile', { default: 'Upload file' })}
                        </label>
                        <input
                            id="upload-file"
                            type="file"
                            onchange={handleFileSelect}
                            class="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-[#2271b3] file:text-white hover:file:bg-[#195a91]"
                            disabled={uploading}
                        />
                    </div>
                    <div class="w-48">
                        <label for="upload-title" class="block text-sm font-medium text-gray-700 mb-1">
                            {$_('libraries.titleOptional', { default: 'Title' })}
                        </label>
                        <input
                            id="upload-title"
                            type="text"
                            bind:value={fileTitle}
                            maxlength="200"
                            class="block w-full border border-gray-300 rounded-md shadow-sm px-3 py-2 text-sm focus:ring-[#2271b3] focus:border-[#2271b3]"
                            disabled={uploading}
                        />
                    </div>
                    <button
                        type="button"
                        onclick={handleUpload}
                        disabled={!selectedFile || uploading}
                        class="px-4 py-2 text-sm font-medium text-white rounded-md shadow-sm bg-[#2271b3] hover:bg-[#195a91] disabled:opacity-50"
                    >
                        {uploading
                            ? $_('libraries.uploading', { default: 'Uploading...' })
                            : $_('libraries.upload', { default: 'Upload' })}
                    </button>
                    <button
                        type="button"
                        onclick={() => importModal.open(libraryId)}
                        class="px-4 py-2 text-sm font-medium text-gray-700 border border-gray-300 rounded-md hover:bg-gray-50"
                    >
                        {$_('libraries.importContent', { default: 'Import URL / YouTube' })}
                    </button>
                </div>
            </div>
        {/if}

        <div class="bg-white shadow rounded-lg overflow-hidden">
            <div class="px-6 py-4 border-b border-gray-200">
                <h3 class="text-base font-semibold text-gray-900">
                    {$_('libraries.items.title', { default: 'Items' })}
                    <span class="ml-1 text-sm font-normal text-gray-500">({totalItems})</span>
                </h3>
            </div>

            {#if items.length === 0}
                <div class="p-6 text-center text-gray-500">
                    {$_('libraries.items.empty', { default: 'No items yet. Upload a file or import content to get started.' })}
                </div>
            {:else}
                <div class="overflow-x-auto">
                    <table class="min-w-full divide-y divide-gray-200">
                        <thead class="bg-gray-50">
                            <tr>
                                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{$_('libraries.items.titleCol', { default: 'Title' })}</th>
                                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{$_('libraries.items.source', { default: 'Source' })}</th>
                                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{$_('libraries.items.size', { default: 'Size' })}</th>
                                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{$_('libraries.items.status', { default: 'Status' })}</th>
                                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{$_('libraries.items.created', { default: 'Created' })}</th>
                                {#if isOwner}
                                    <th class="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">{$_('libraries.actions', { default: 'Actions' })}</th>
                                {/if}
                            </tr>
                        </thead>
                        <tbody class="bg-white divide-y divide-gray-200">
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
                                        <span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium {statusBadge(item.status)}">
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
    title={$_('libraries.deleteItemModal.title', { default: 'Delete Item' })}
    message={$_('libraries.deleteItemModal.message', { default: `Are you sure you want to delete "${deleteItemTarget.title}"?` })}
    confirmText={$_('libraries.deleteItemModal.confirm', { default: 'Delete' })}
    variant="danger"
    onconfirm={handleDeleteItemConfirm}
    oncancel={() => { showDeleteItemModal = false; }}
/>
