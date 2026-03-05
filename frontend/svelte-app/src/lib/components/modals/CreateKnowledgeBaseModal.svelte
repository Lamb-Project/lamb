<script>
    import { createEventDispatcher, onMount } from 'svelte';
    import { _ } from '$lib/i18n';
    import { createKnowledgeBase, getAvailableEmbeddingsSetups } from '$lib/services/knowledgeBaseService';
    import { sanitizeName } from '$lib/utils/nameSanitizer';

    const dispatch = createEventDispatcher();
    
    // State management
    let isOpen = $state(false);
    let isSubmitting = $state(false);
    let error = $state('');
    
    // Form data
    let name = $state('');
    let description = $state('');
    let selectedSetupKey = $state('');
    
    // Embeddings setups
    let embeddingsSetups = $state([]);
    let isLoadingSetups = $state(false);
    let setupsError = $state('');
    
    // Derived: Sanitized name preview
    let sanitizedNameInfo = $derived(sanitizeName(name));
    let showSanitizationPreview = $derived(sanitizedNameInfo.wasModified && name.trim() !== '');
    
    // Error states
    let nameError = $state('');
    
    // Functions
    export function open() {
        isOpen = true;
        resetForm();
        loadEmbeddingsSetups();
    }
    
    async function loadEmbeddingsSetups() {
        isLoadingSetups = true;
        setupsError = '';
        try {
            embeddingsSetups = await getAvailableEmbeddingsSetups();
            // Auto-select default setup if available
            const defaultSetup = embeddingsSetups.find(s => s.is_default);
            if (defaultSetup) {
                selectedSetupKey = defaultSetup.setup_key;
            } else if (embeddingsSetups.length > 0) {
                selectedSetupKey = embeddingsSetups[0].setup_key;
            }
        } catch (err) {
            console.error('Error loading embeddings setups:', err);
            setupsError = err instanceof Error ? err.message : 'Failed to load embeddings options';
        } finally {
            isLoadingSetups = false;
        }
    }
    
    function close() {
        if (!isSubmitting) {
            isOpen = false;
            resetForm();
            dispatch('close');
        }
    }
    
    function resetForm() {
        name = '';
        description = '';
        selectedSetupKey = '';
        error = '';
        nameError = '';
        setupsError = '';
        isSubmitting = false;
    }
    
    function validateForm() {
        let isValid = true;
        
        // Reset errors
        nameError = '';
        error = '';
        
        // Validate name (required)
        if (!name.trim()) {
            nameError = $_('knowledgeBases.createModal.nameRequired', { default: 'Name is required' });
            isValid = false;
        } else if (name.length > 50) {
            nameError = $_('knowledgeBases.createModal.nameTooLong', { default: 'Name must be less than 50 characters' });
            isValid = false;
        }
        
        return isValid;
    }
    
    /**
     * Handle form submission
     * @param {SubmitEvent} event - The form submit event
     */
    async function handleSubmit(event) {
        // Prevent default form submission
        event.preventDefault();
        
        if (!validateForm()) {
            return;
        }
        
        isSubmitting = true;
        error = '';
        
        try {
            const payload = {
                name: name.trim(),
                description: description.trim() || undefined,
                access_control: 'private'
            };
            
            // Add embeddings_setup_key if selected
            if (selectedSetupKey) {
                payload.embeddings_setup_key = selectedSetupKey;
            }
            
            const result = await createKnowledgeBase(payload);
            
            console.log('Knowledge base created:', result);
            
            // Close modal and notify parent
            isOpen = false;
            dispatch('created', {
                id: result.kb_id,
                name: result.name,
                message: result.message
            });
            
            // Reset form
            resetForm();
        } catch (err) {
            console.error('Error creating knowledge base:', err);
            error = err instanceof Error ? err.message : 'Failed to create knowledge base';
            isSubmitting = false;
        }
    }
    
    /**
     * Handle keyboard events
     * @param {KeyboardEvent} event - The keyboard event
     */
    function handleKeydown(event) {
        // Close on escape key
        if (event.key === 'Escape') {
            close();
        }
    }
    
    // Handle click on backdrop
    function handleBackdropClick() {
        close();
    }
    
    /**
     * Prevent click event propagation
     * @param {MouseEvent} event - The mouse event
     */
    function handleModalClick(event) {
        event.stopPropagation();
    }
</script>

<!-- Modal backdrop -->
{#if isOpen}
<div class="fixed inset-0 z-40 overflow-y-auto">
    <!-- Overlay -->
    <div class="fixed inset-0 bg-black bg-opacity-50 transition-opacity" 
         onclick={handleBackdropClick} 
         aria-hidden="true">
    </div>
    
    <!-- Modal dialog -->
    <div class="flex min-h-screen items-center justify-center p-4">
        <div class="relative bg-white rounded-lg shadow-xl max-w-lg w-full mx-auto p-6"
             onclick={handleModalClick}
             onkeydown={handleKeydown}
             tabindex="-1"
             role="dialog"
             aria-modal="true"
             aria-labelledby="modal-title">
            
            <!-- Header -->
            <div class="mb-4">
                <h3 id="modal-title" class="text-lg font-medium text-gray-900">
                    {$_('knowledgeBases.createPageTitle', { default: 'Create Knowledge Base' })}
                </h3>
                <p class="text-sm text-gray-500 mt-1">
                    {$_('knowledgeBases.createModal.description', { default: 'Create a new knowledge base to store and retrieve documents.' })}
                </p>
            </div>
            
            <!-- Error message -->
            {#if error}
                <div class="mb-4 p-2 bg-red-50 text-red-500 text-sm rounded">
                    {error}
                </div>
            {/if}
            
            <!-- Form -->
            <form onsubmit={handleSubmit} class="space-y-4">
                <!-- Name field -->
                <div>
                    <label for="kb-name" class="block text-sm font-medium text-gray-700">
                        {$_('knowledgeBases.name', { default: 'Name' })} *
                    </label>
                    <input
                        type="text"
                        id="kb-name"
                        bind:value={name}
                        class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-[#2271b3] focus:border-[#2271b3] sm:text-sm {nameError ? 'border-red-300 focus:ring-red-500 focus:border-red-500' : ''}"
                        placeholder={$_('knowledgeBases.namePlaceholder', { default: 'Enter knowledge base name' })}
                    />
                    {#if showSanitizationPreview}
                        <div class="mt-2 p-2 bg-blue-50 border border-blue-200 rounded-md">
                            <p class="text-sm text-blue-800">
                                <span class="font-semibold">{$_('knowledgeBases.createModal.willBeSaved', { default: 'Will be saved as:' })}</span>
                                <code class="ml-2 px-2 py-1 bg-blue-100 rounded text-blue-900 font-mono">{sanitizedNameInfo.sanitized}</code>
                            </p>
                        </div>
                    {:else if !name.trim()}
                        <p class="mt-1 text-xs text-gray-500">
                            {$_('knowledgeBases.createModal.nameHint', { default: 'Special characters and spaces will be converted to underscores' })}
                        </p>
                    {/if}
                    {#if nameError}
                        <p class="mt-1 text-sm text-red-600">{nameError}</p>
                    {/if}
                </div>
                
                <!-- Description field -->
                <div>
                    <label for="kb-description" class="block text-sm font-medium text-gray-700">
                        {$_('knowledgeBases.description', { default: 'Description' })}
                    </label>
                    <textarea
                        id="kb-description"
                        bind:value={description}
                        rows="3"
                        class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-[#2271b3] focus:border-[#2271b3] sm:text-sm"
                        placeholder={$_('knowledgeBases.descriptionPlaceholder', { default: 'Enter a description for this knowledge base' })}
                    ></textarea>
                </div>
                
                <!-- Embeddings Model Selector -->
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">
                        {$_('knowledgeBases.embeddingsModel', { default: 'Embeddings Model' })}
                    </label>
                    
                    {#if isLoadingSetups}
                        <div class="p-4 bg-gray-50 rounded-md flex items-center justify-center">
                            <svg class="animate-spin h-5 w-5 text-gray-400 mr-2" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                            <span class="text-sm text-gray-500">Loading embeddings options...</span>
                        </div>
                    {:else if setupsError}
                        <div class="p-3 bg-red-50 text-red-600 text-sm rounded-md">
                            {setupsError}
                        </div>
                    {:else if embeddingsSetups.length === 0}
                        <div class="p-3 bg-yellow-50 text-yellow-700 text-sm rounded-md">
                            No embeddings configurations available. Using system defaults.
                        </div>
                    {:else}
                        <div class="space-y-2 border border-gray-200 rounded-md p-3 bg-gray-50">
                            {#each embeddingsSetups as setup}
                                <label class="flex items-start p-2 rounded-md cursor-pointer hover:bg-gray-100 transition-colors {selectedSetupKey === setup.setup_key ? 'bg-blue-50 border border-blue-200' : ''}">
                                    <input
                                        type="radio"
                                        name="embeddings_setup"
                                        value={setup.setup_key}
                                        bind:group={selectedSetupKey}
                                        class="mt-1 h-4 w-4 text-blue-600 border-gray-300 focus:ring-blue-500"
                                    />
                                    <div class="ml-3 flex-1">
                                        <div class="flex items-center">
                                            <span class="text-sm font-medium text-gray-900">{setup.name}</span>
                                            {#if setup.is_default}
                                                <span class="ml-2 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
                                                    Default
                                                </span>
                                            {/if}
                                        </div>
                                        <p class="text-xs text-gray-500 mt-0.5">
                                            {setup.model_name} · {setup.embedding_dimensions} dimensions
                                        </p>
                                        {#if setup.description}
                                            <p class="text-xs text-gray-400 mt-0.5">{setup.description}</p>
                                        {/if}
                                    </div>
                                </label>
                            {/each}
                        </div>
                        <p class="mt-2 text-xs text-gray-500 flex items-center">
                            <svg class="h-4 w-4 text-gray-400 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                            </svg>
                            The embeddings model cannot be changed after creation.
                        </p>
                    {/if}
                </div>
                
                <!-- Sanitization Preview (above form actions) -->
                {#if showSanitizationPreview}
                    <div class="mt-4 p-3 bg-blue-50 border border-blue-200 rounded-md">
                        <div class="flex items-center">
                            <svg class="w-5 h-5 text-blue-600 mr-2 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                            </svg>
                            <div class="flex-1">
                                <p class="text-sm font-semibold text-blue-800">
                                    {$_('knowledgeBases.createModal.willBeSaved', { default: 'Will be saved as:' })}
                                </p>
                                <code class="inline-block mt-1 px-3 py-1 bg-blue-100 rounded text-blue-900 font-mono text-sm">{sanitizedNameInfo.sanitized}</code>
                            </div>
                        </div>
                    </div>
                {/if}
                
                <!-- Form actions -->
                <div class="mt-5 sm:mt-6 sm:grid sm:grid-cols-2 sm:gap-3 sm:grid-flow-row-dense">
                    <button
                        type="submit"
                        class="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-brand text-base font-medium text-white hover:bg-brand-hover focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand sm:col-start-2 sm:text-sm"
                        disabled={isSubmitting}
                    >
                        {#if isSubmitting}
                            {$_('knowledgeBases.creating', { default: 'Creating...' })}
                        {:else}
                            {$_('knowledgeBases.create', { default: 'Create Knowledge Base' })}
                        {/if}
                    </button>
                    <button
                        type="button"
                        onclick={close}
                        class="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-500 sm:mt-0 sm:col-start-1 sm:text-sm"
                        disabled={isSubmitting}
                    >
                        {$_('knowledgeBases.cancel', { default: 'Cancel' })}
                    </button>
                </div>
            </form>
        </div>
    </div>
</div>
{/if} 