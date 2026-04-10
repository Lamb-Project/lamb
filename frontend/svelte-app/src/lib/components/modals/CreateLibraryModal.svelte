<!--
  @component CreateLibraryModal
  Modal form for creating a new library. Emits 'created' event on success.
  Follows the same pattern as CreateKnowledgeBaseModal.svelte.
-->
<script>
    import { createEventDispatcher } from 'svelte';
    import { createLibrary } from '$lib/services/libraryService';
    import { _ } from '$lib/i18n';

    const dispatch = createEventDispatcher();

    let isOpen = $state(false);
    let isSubmitting = $state(false);
    let error = $state('');
    let nameError = $state('');
    let name = $state('');
    let description = $state('');

    /** Open the modal and reset the form. */
    export function open() {
        isOpen = true;
        resetForm();
    }

    function close() {
        if (isSubmitting) return;
        isOpen = false;
        resetForm();
        dispatch('close');
    }

    function resetForm() {
        name = '';
        description = '';
        error = '';
        nameError = '';
        isSubmitting = false;
    }

    function validate() {
        nameError = '';
        if (!name.trim()) {
            nameError = $_('libraries.createModal.nameRequired', { default: 'Name is required' });
            return false;
        }
        if (name.trim().length > 100) {
            nameError = $_('libraries.createModal.nameTooLong', { default: 'Name must be less than 100 characters' });
            return false;
        }
        return true;
    }

    async function handleSubmit(event) {
        event.preventDefault();
        if (!validate()) return;

        isSubmitting = true;
        error = '';

        try {
            const result = await createLibrary({
                name: name.trim(),
                description: description.trim() || '',
            });
            isOpen = false;
            dispatch('created', { id: result.id, name: result.name });
            resetForm();
        } catch (/** @type {unknown} */ err) {
            error = err instanceof Error ? err.message : 'Failed to create library';
            isSubmitting = false;
        }
    }

    function handleKeydown(event) {
        if (event.key === 'Escape') close();
    }

    function handleBackdropClick() {
        close();
    }

    function stopPropagation(event) {
        event.stopPropagation();
    }
</script>

{#if isOpen}
    <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
    <div
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
        role="dialog"
        aria-modal="true"
        aria-labelledby="create-library-title"
        onclick={handleBackdropClick}
        onkeydown={handleKeydown}
    >
        <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
        <!-- svelte-ignore a11y_click_events_have_key_events -->
        <div
            class="bg-white rounded-lg shadow-xl w-full max-w-md mx-4"
            onclick={stopPropagation}
        >
            <div class="px-6 py-4 border-b border-gray-200">
                <h2 id="create-library-title" class="text-lg font-semibold text-gray-900">
                    {$_('libraries.createModal.title', { default: 'Create Library' })}
                </h2>
                <p class="mt-1 text-sm text-gray-500">
                    {$_('libraries.createModal.description', { default: 'Create a new document library to store imported content.' })}
                </p>
            </div>

            <form onsubmit={handleSubmit} class="px-6 py-4 space-y-4">
                {#if error}
                    <div class="p-3 text-sm text-red-700 bg-red-50 rounded-md">{error}</div>
                {/if}

                <div>
                    <label for="lib-name" class="block text-sm font-medium text-gray-700">
                        {$_('libraries.name', { default: 'Name' })} <span class="text-red-500">*</span>
                    </label>
                    <input
                        type="text"
                        id="lib-name"
                        bind:value={name}
                        class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm px-3 py-2 text-sm focus:ring-[#2271b3] focus:border-[#2271b3] {nameError ? 'border-red-500' : ''}"
                        placeholder={$_('libraries.namePlaceholder', { default: 'Enter library name' })}
                        disabled={isSubmitting}
                    />
                    {#if nameError}
                        <p class="mt-1 text-sm text-red-600">{nameError}</p>
                    {/if}
                </div>

                <div>
                    <label for="lib-description" class="block text-sm font-medium text-gray-700">
                        {$_('libraries.description', { default: 'Description' })}
                    </label>
                    <textarea
                        id="lib-description"
                        bind:value={description}
                        rows="3"
                        class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm px-3 py-2 text-sm focus:ring-[#2271b3] focus:border-[#2271b3]"
                        placeholder={$_('libraries.descriptionPlaceholder', { default: 'Optional description' })}
                        disabled={isSubmitting}
                    ></textarea>
                </div>

                <div class="flex justify-end gap-3 pt-2">
                    <button
                        type="button"
                        onclick={close}
                        class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
                        disabled={isSubmitting}
                    >
                        {$_('common.cancel', { default: 'Cancel' })}
                    </button>
                    <button
                        type="submit"
                        class="px-4 py-2 text-sm font-medium text-white rounded-md shadow-sm bg-[#2271b3] hover:bg-[#195a91] disabled:opacity-50"
                        disabled={isSubmitting}
                    >
                        {#if isSubmitting}
                            {$_('libraries.creating', { default: 'Creating...' })}
                        {:else}
                            {$_('libraries.createButton', { default: 'Create Library' })}
                        {/if}
                    </button>
                </div>
            </form>
        </div>
    </div>
{/if}
