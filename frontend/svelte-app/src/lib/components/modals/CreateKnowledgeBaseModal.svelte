<script>
    import { createEventDispatcher } from 'svelte';
    import { _ } from '$lib/i18n';
    import { createKnowledgeBase } from '$lib/services/knowledgeBaseService';

    const dispatch = createEventDispatcher();
    
    // State management
    let isOpen = $state(false);
    let isSubmitting = $state(false);
    let error = $state('');
    
    // Form data
    let name = $state('');
    let description = $state('');
    let accessControl = $state('private'); // Default to private
    
    // Error states
    let nameError = $state('');
    
    // Functions
    export function open() {
        isOpen = true;
        resetForm();
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
        accessControl = 'private';
        error = '';
        nameError = '';
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
            const result = await createKnowledgeBase({
                name: name.trim(),
                description: description.trim() || undefined, // Don't send empty string
                access_control: accessControl
            });
            
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
                
                <!-- Access Control -->
                <div>
                    <fieldset>
                        <legend class="block text-sm font-medium text-gray-700">
                            {$_('knowledgeBases.accessControl', { default: 'Access Control' })}
                        </legend>
                        <div class="mt-2 space-y-2">
                            <div class="flex items-center">
                                <input
                                    id="private"
                                    name="accessControl"
                                    type="radio"
                                    bind:group={accessControl}
                                    value="private"
                                    class="h-4 w-4 text-brand focus:ring-brand border-gray-300"
                                />
                                <label for="private" class="ml-2 block text-sm text-gray-700">
                                    {$_('knowledgeBases.private', { default: 'Private' })}
                                </label>
                            </div>
                            <div class="flex items-center">
                                <input
                                    id="public"
                                    name="accessControl"
                                    type="radio"
                                    bind:group={accessControl}
                                    value="public"
                                    class="h-4 w-4 text-brand focus:ring-brand border-gray-300"
                                />
                                <label for="public" class="ml-2 block text-sm text-gray-700">
                                    {$_('knowledgeBases.public', { default: 'Public' })}
                                </label>
                            </div>
                        </div>
                        <p class="mt-1 text-xs text-gray-500">
                            {$_('knowledgeBases.accessControlHelp', { default: 'Private knowledge bases are only accessible by you, while public ones can be accessed by other users.' })}
                        </p>
                    </fieldset>
                </div>
                
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