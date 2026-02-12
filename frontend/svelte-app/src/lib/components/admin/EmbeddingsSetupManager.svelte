<script>
    import { _ } from '$lib/i18n';
    import axios from 'axios';
    import { getApiUrl } from '$lib/config';
    import { browser } from '$app/environment';

    // Props
    let {
        organizationId = null,
        onClose = () => {}
    } = $props();

    // State
    let setups = $state([]);
    let isLoading = $state(false);
    let error = $state('');
    let showForm = $state(false);
    let editingSetup = $state(null);
    let isSubmitting = $state(false);
    let deleteConfirmSetup = $state(null);

    // Form state
    let formData = $state({
        name: '',
        setup_key: '',
        vendor: 'openai',
        api_endpoint: '',
        api_key: '',
        model_name: '',
        embedding_dimensions: 1536,
        is_default: false,
        description: ''
    });

    // Vendor options with common models and dimensions
    const vendorOptions = [
        { value: 'openai', label: 'OpenAI', defaultModel: 'text-embedding-3-small', defaultDimensions: 1536 },
        { value: 'ollama', label: 'Ollama (Local)', defaultModel: 'nomic-embed-text', defaultDimensions: 768 },
        { value: 'huggingface', label: 'Hugging Face', defaultModel: 'sentence-transformers/all-MiniLM-L6-v2', defaultDimensions: 384 },
        { value: 'cohere', label: 'Cohere', defaultModel: 'embed-english-v3.0', defaultDimensions: 1024 },
        { value: 'custom', label: 'Custom', defaultModel: '', defaultDimensions: 1536 }
    ];

    function getToken() {
        if (!browser) return null;
        return localStorage.getItem('userToken');
    }

    async function loadSetups() {
        if (!organizationId) return;
        
        isLoading = true;
        error = '';
        
        try {
            const token = getToken();
            const url = getApiUrl(`/creator/admin/organizations/${organizationId}/embeddings-setups`);
            const response = await axios.get(url, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            
            setups = response.data || [];
        } catch (err) {
            console.error('Error loading embeddings setups:', err);
            error = err.response?.data?.detail || 'Failed to load embeddings setups';
        } finally {
            isLoading = false;
        }
    }

    function resetForm() {
        formData = {
            name: '',
            setup_key: '',
            vendor: 'openai',
            api_endpoint: '',
            api_key: '',
            model_name: '',
            embedding_dimensions: 1536,
            is_default: false,
            description: ''
        };
        editingSetup = null;
    }

    function openCreateForm() {
        resetForm();
        showForm = true;
    }

    function openEditForm(setup) {
        editingSetup = setup;
        formData = {
            name: setup.name || '',
            setup_key: setup.setup_key || '',
            vendor: setup.vendor || 'openai',
            api_endpoint: setup.api_endpoint || '',
            api_key: '', // Don't pre-fill API key for security
            model_name: setup.model_name || '',
            embedding_dimensions: setup.embedding_dimensions || 1536,
            is_default: setup.is_default || false,
            description: setup.description || ''
        };
        showForm = true;
    }

    function closeForm() {
        showForm = false;
        resetForm();
    }

    function handleVendorChange() {
        const vendor = vendorOptions.find(v => v.value === formData.vendor);
        if (vendor && !formData.model_name) {
            formData.model_name = vendor.defaultModel;
            formData.embedding_dimensions = vendor.defaultDimensions;
        }
    }

    function generateSetupKey() {
        if (!formData.name) return;
        formData.setup_key = formData.name
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, '_')
            .replace(/^_|_$/g, '');
    }

    async function handleSubmit(event) {
        event.preventDefault();
        isSubmitting = true;
        error = '';

        try {
            const token = getToken();
            const payload = {
                name: formData.name,
                setup_key: formData.setup_key,
                vendor: formData.vendor,
                api_endpoint: formData.api_endpoint || null,
                api_key: formData.api_key || null,
                model_name: formData.model_name,
                embedding_dimensions: parseInt(formData.embedding_dimensions),
                is_default: formData.is_default,
                description: formData.description || null
            };

            const baseUrl = getApiUrl(`/creator/admin/organizations/${organizationId}/embeddings-setups`);
            
            if (editingSetup) {
                // Update existing
                await axios.put(`${baseUrl}/${editingSetup.id}`, payload, {
                    headers: { 'Authorization': `Bearer ${token}` }
                });
            } else {
                // Create new
                await axios.post(baseUrl, payload, {
                    headers: { 'Authorization': `Bearer ${token}` }
                });
            }

            closeForm();
            await loadSetups();
        } catch (err) {
            console.error('Error saving embeddings setup:', err);
            error = err.response?.data?.detail || 'Failed to save embeddings setup';
        } finally {
            isSubmitting = false;
        }
    }

    async function handleDelete(setup) {
        deleteConfirmSetup = null;
        
        try {
            const token = getToken();
            const url = getApiUrl(`/creator/admin/organizations/${organizationId}/embeddings-setups/${setup.id}`);
            await axios.delete(url, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            await loadSetups();
        } catch (err) {
            console.error('Error deleting embeddings setup:', err);
            error = err.response?.data?.detail || 'Failed to delete embeddings setup. It may be in use by collections.';
        }
    }

    async function setAsDefault(setup) {
        try {
            const token = getToken();
            const url = getApiUrl(`/creator/admin/organizations/${organizationId}/embeddings-setups/${setup.id}`);
            await axios.put(url, { ...setup, is_default: true }, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            await loadSetups();
        } catch (err) {
            console.error('Error setting default:', err);
            error = err.response?.data?.detail || 'Failed to set as default';
        }
    }

    // Load on mount
    $effect(() => {
        if (organizationId) {
            loadSetups();
        }
    });
</script>

<div class="bg-white rounded-lg shadow-sm border border-gray-200">
    <!-- Header -->
    <div class="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
        <div>
            <h2 class="text-lg font-semibold text-gray-900">Embeddings Setups</h2>
            <p class="text-sm text-gray-500 mt-1">Manage embeddings configurations for knowledge bases</p>
        </div>
        <button
            onclick={openCreateForm}
            class="inline-flex items-center gap-2 px-4 py-2 bg-brand text-white text-sm font-medium rounded-lg hover:bg-brand-hover transition-colors"
        >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
            </svg>
            Add Setup
        </button>
    </div>

    <!-- Error message -->
    {#if error}
        <div class="mx-6 mt-4 p-3 bg-red-50 border border-red-200 text-red-700 text-sm rounded-md">
            {error}
            <button onclick={() => error = ''} class="ml-2 text-red-500 hover:text-red-700">×</button>
        </div>
    {/if}

    <!-- Content -->
    <div class="p-6">
        {#if isLoading}
            <div class="flex items-center justify-center py-8">
                <svg class="animate-spin h-8 w-8 text-gray-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
            </div>
        {:else if setups.length === 0}
            <div class="text-center py-12">
                <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"/>
                </svg>
                <h3 class="mt-4 text-sm font-medium text-gray-900">No embeddings setups</h3>
                <p class="mt-2 text-sm text-gray-500">Create your first embeddings configuration to get started.</p>
                <button
                    onclick={openCreateForm}
                    class="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-brand text-white text-sm font-medium rounded-lg hover:bg-brand-hover"
                >
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
                    </svg>
                    Create Setup
                </button>
            </div>
        {:else}
            <div class="space-y-3">
                {#each setups as setup}
                    <div class="border border-gray-200 rounded-lg p-4 hover:border-gray-300 transition-colors {setup.is_default ? 'bg-blue-50 border-blue-200' : ''}">
                        <div class="flex items-start justify-between">
                            <div class="flex-1">
                                <div class="flex items-center gap-2">
                                    <h4 class="font-medium text-gray-900">{setup.name}</h4>
                                    {#if setup.is_default}
                                        <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800">
                                            Default
                                        </span>
                                    {/if}
                                    {#if !setup.is_active}
                                        <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-600">
                                            Inactive
                                        </span>
                                    {/if}
                                </div>
                                <p class="text-sm text-gray-500 mt-1">
                                    <span class="font-mono text-xs bg-gray-100 px-1 rounded">{setup.setup_key}</span>
                                    · {setup.vendor} · {setup.model_name}
                                </p>
                                <p class="text-xs text-gray-400 mt-1">
                                    {setup.embedding_dimensions} dimensions
                                    {#if setup.collections_count !== undefined}
                                        · {setup.collections_count} collection{setup.collections_count === 1 ? '' : 's'}
                                    {/if}
                                </p>
                            </div>
                            <div class="flex items-center gap-2">
                                {#if !setup.is_default}
                                    <button
                                        onclick={() => setAsDefault(setup)}
                                        class="text-xs text-gray-500 hover:text-blue-600 px-2 py-1 rounded hover:bg-blue-50"
                                        title="Set as default"
                                    >
                                        Set Default
                                    </button>
                                {/if}
                                <button
                                    onclick={() => openEditForm(setup)}
                                    class="p-1.5 text-gray-400 hover:text-gray-600 rounded hover:bg-gray-100"
                                    title="Edit"
                                >
                                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
                                    </svg>
                                </button>
                                <button
                                    onclick={() => deleteConfirmSetup = setup}
                                    class="p-1.5 text-gray-400 hover:text-red-600 rounded hover:bg-red-50"
                                    title="Delete"
                                    disabled={setup.collections_count > 0}
                                >
                                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                                    </svg>
                                </button>
                            </div>
                        </div>
                    </div>
                {/each}
            </div>
        {/if}
    </div>
</div>

<!-- Create/Edit Form Modal -->
{#if showForm}
    <div class="fixed inset-0 z-50 overflow-y-auto">
        <div class="fixed inset-0 bg-black bg-opacity-50" onclick={closeForm}></div>
        <div class="flex min-h-screen items-center justify-center p-4">
            <div class="relative bg-white rounded-lg shadow-xl max-w-lg w-full p-6" onclick={e => e.stopPropagation()}>
                <h3 class="text-lg font-medium text-gray-900 mb-4">
                    {editingSetup ? 'Edit Embeddings Setup' : 'Create Embeddings Setup'}
                </h3>

                <form onsubmit={handleSubmit} class="space-y-4">
                    <!-- Name -->
                    <div>
                        <label for="setup-name" class="block text-sm font-medium text-gray-700">Name *</label>
                        <input
                            type="text"
                            id="setup-name"
                            bind:value={formData.name}
                            oninput={generateSetupKey}
                            class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 text-sm focus:ring-brand focus:border-brand"
                            placeholder="e.g., OpenAI Small"
                            required
                        />
                    </div>

                    <!-- Setup Key -->
                    <div>
                        <label for="setup-key" class="block text-sm font-medium text-gray-700">Setup Key *</label>
                        <input
                            type="text"
                            id="setup-key"
                            bind:value={formData.setup_key}
                            class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 text-sm font-mono focus:ring-brand focus:border-brand"
                            placeholder="e.g., openai_small"
                            pattern="[a-z0-9_]+"
                            required
                            disabled={editingSetup}
                        />
                        <p class="mt-1 text-xs text-gray-500">Lowercase letters, numbers, and underscores only</p>
                    </div>

                    <!-- Vendor -->
                    <div>
                        <label for="vendor" class="block text-sm font-medium text-gray-700">Provider *</label>
                        <select
                            id="vendor"
                            bind:value={formData.vendor}
                            onchange={handleVendorChange}
                            class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 text-sm focus:ring-brand focus:border-brand"
                        >
                            {#each vendorOptions as vendor}
                                <option value={vendor.value}>{vendor.label}</option>
                            {/each}
                        </select>
                    </div>

                    <!-- API Endpoint (for Ollama/Custom) -->
                    {#if formData.vendor === 'ollama' || formData.vendor === 'custom'}
                        <div>
                            <label for="api-endpoint" class="block text-sm font-medium text-gray-700">API Endpoint</label>
                            <input
                                type="url"
                                id="api-endpoint"
                                bind:value={formData.api_endpoint}
                                class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 text-sm focus:ring-brand focus:border-brand"
                                placeholder="http://localhost:11434/api/embeddings"
                            />
                        </div>
                    {/if}

                    <!-- API Key (for cloud providers) -->
                    {#if formData.vendor !== 'ollama'}
                        <div>
                            <label for="api-key" class="block text-sm font-medium text-gray-700">
                                API Key {editingSetup ? '(leave blank to keep existing)' : '*'}
                            </label>
                            <input
                                type="password"
                                id="api-key"
                                bind:value={formData.api_key}
                                class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 text-sm focus:ring-brand focus:border-brand"
                                placeholder="sk-..."
                                required={!editingSetup}
                            />
                        </div>
                    {/if}

                    <!-- Model Name -->
                    <div>
                        <label for="model-name" class="block text-sm font-medium text-gray-700">Model Name *</label>
                        <input
                            type="text"
                            id="model-name"
                            bind:value={formData.model_name}
                            class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 text-sm focus:ring-brand focus:border-brand"
                            placeholder="text-embedding-3-small"
                            required
                        />
                    </div>

                    <!-- Dimensions -->
                    <div>
                        <label for="dimensions" class="block text-sm font-medium text-gray-700">Embedding Dimensions *</label>
                        <input
                            type="number"
                            id="dimensions"
                            bind:value={formData.embedding_dimensions}
                            class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 text-sm focus:ring-brand focus:border-brand"
                            min="1"
                            max="8192"
                            required
                            disabled={editingSetup}
                        />
                        {#if editingSetup}
                            <p class="mt-1 text-xs text-amber-600">Dimensions cannot be changed after creation</p>
                        {/if}
                    </div>

                    <!-- Is Default -->
                    <div class="flex items-center gap-2">
                        <input
                            type="checkbox"
                            id="is-default"
                            bind:checked={formData.is_default}
                            class="h-4 w-4 text-brand focus:ring-brand border-gray-300 rounded"
                        />
                        <label for="is-default" class="text-sm text-gray-700">Set as default for this organization</label>
                    </div>

                    <!-- Form Actions -->
                    <div class="flex justify-end gap-3 pt-4">
                        <button
                            type="button"
                            onclick={closeForm}
                            class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
                            disabled={isSubmitting}
                        >
                            Cancel
                        </button>
                        <button
                            type="submit"
                            class="px-4 py-2 text-sm font-medium text-white bg-brand rounded-md hover:bg-brand-hover disabled:opacity-50"
                            disabled={isSubmitting}
                        >
                            {isSubmitting ? 'Saving...' : (editingSetup ? 'Update' : 'Create')}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    </div>
{/if}

<!-- Delete Confirmation Modal -->
{#if deleteConfirmSetup}
    <div class="fixed inset-0 z-50 overflow-y-auto">
        <div class="fixed inset-0 bg-black bg-opacity-50" onclick={() => deleteConfirmSetup = null}></div>
        <div class="flex min-h-screen items-center justify-center p-4">
            <div class="relative bg-white rounded-lg shadow-xl max-w-md w-full p-6" onclick={e => e.stopPropagation()}>
                <h3 class="text-lg font-medium text-gray-900 mb-2">Delete Embeddings Setup</h3>
                <p class="text-sm text-gray-500 mb-4">
                    Are you sure you want to delete <strong>{deleteConfirmSetup.name}</strong>? This action cannot be undone.
                </p>
                {#if deleteConfirmSetup.collections_count > 0}
                    <div class="p-3 bg-amber-50 border border-amber-200 text-amber-700 text-sm rounded-md mb-4">
                        This setup is used by {deleteConfirmSetup.collections_count} collection(s) and cannot be deleted.
                    </div>
                {/if}
                <div class="flex justify-end gap-3">
                    <button
                        onclick={() => deleteConfirmSetup = null}
                        class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
                    >
                        Cancel
                    </button>
                    <button
                        onclick={() => handleDelete(deleteConfirmSetup)}
                        class="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-md hover:bg-red-700 disabled:opacity-50"
                        disabled={deleteConfirmSetup.collections_count > 0}
                    >
                        Delete
                    </button>
                </div>
            </div>
        </div>
    </div>
{/if}
