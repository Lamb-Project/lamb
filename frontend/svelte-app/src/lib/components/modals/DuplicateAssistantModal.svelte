<script>
  import { _, locale } from '$lib/i18n'; // For translated text

  // --- Props (using $props rune) ---
  let { 
      isOpen = $bindable(false), // Bindable: Controls modal visibility
      originalName = '',        // Name of the assistant being duplicated
      defaultNewName = '',      // Pre-filled name for the duplicate
      isSubmitting = $bindable(false), // Bindable: Shows loading state
      error = '',               // Displays submission errors
      onSubmit,                 // Callback for form submission
      onClose                   // Callback for modal close
  } = $props();

  // --- Internal State ---
  let newName = $state(''); // The name entered by the user
  let localeLoaded = $state(false);

  // --- Lifecycle ---
  $effect(() => {
    // Update internal newName when defaultNewName prop changes (e.g., on modal open)
    if (defaultNewName) {
      newName = defaultNewName;
    }
  });

  let localeUnsubscribe = () => {};
  $effect(() => {
      localeUnsubscribe = locale.subscribe(value => {
          localeLoaded = !!value;
      });
      return () => {
          localeUnsubscribe();
      };
  });

  // --- Functions ---
  function handleSubmit() {
    if (!newName.trim() || isSubmitting) return;
    onSubmit?.({ newName: newName.trim() });
  }

  function handleClose() {
    onClose?.();
  }

  /** @param {Event} event */
  function sanitizeName(event) {
    const inputElement = /** @type {HTMLInputElement} */ (event.target);
    // Allow letters, numbers, underscore, hyphen
    const sanitized = inputElement.value.replace(/[^a-zA-Z0-9_-]/g, '');
    if (inputElement.value !== sanitized) {
      inputElement.value = sanitized;
    }
    newName = sanitized; // Update the state variable as well
  }

  /** @param {KeyboardEvent} event */
  function handleKeydown(event) {
    if (event.key === 'Escape') {
      handleClose();
    }
    if (event.key === 'Enter') {
        handleSubmit();
    }
  }
</script>

<!-- Use keydown listener for Escape key -->
<svelte:window onkeydown={handleKeydown}/>

{#if isOpen}
  <!-- Modal Overlay -->
  <div class="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity z-40" onclick={handleClose} aria-hidden="true"></div>

  <!-- Modal Panel -->
  <div class="fixed inset-0 z-50 flex items-center justify-center p-4">
    <div class="relative bg-white rounded-lg shadow-xl overflow-hidden max-w-lg w-full border border-gray-300" role="dialog" aria-modal="true" aria-labelledby="modal-title">
      
      <!-- Modal Header -->
      <div class="bg-gray-50 px-4 py-3 sm:px-6 border-b border-gray-200">
        <h3 class="text-lg leading-6 font-medium text-gray-900" id="modal-title">
            {localeLoaded ? $_('assistants.duplicateModal.title', { default: 'Duplicate Assistant' }) : 'Duplicate Assistant'}
        </h3>
      </div>

      <!-- Modal Body -->
      <div class="px-4 py-5 sm:p-6">
        <p class="text-sm text-gray-600 mb-4">
            {localeLoaded ? $_('assistants.duplicateModal.description', { values: { name: originalName }, default: `Creating a copy of assistant: ${originalName}` }) : `Creating a copy of assistant: ${originalName}`}
        </p>

        <!-- New Name Input -->
        <div>
          <label for="new-assistant-name" class="block text-sm font-medium text-gray-700">
            {localeLoaded ? $_('assistants.duplicateModal.newNameLabel', { default: 'New Assistant Name' }) : 'New Assistant Name'}
          </label>
          <div class="mt-1">
            <input 
              type="text" 
              id="new-assistant-name" 
              bind:value={newName} 
              disabled={isSubmitting}
              oninput={sanitizeName}
              class="shadow-sm focus:ring-brand focus:border-brand block w-full sm:text-sm border-gray-300 rounded-md disabled:bg-gray-100" 
              placeholder={localeLoaded ? $_('assistants.duplicateModal.newNamePlaceholder', { default: 'Enter name for the copy...' }) : 'Enter name for the copy...'}
            />
          </div>
        </div>

        <!-- Error Message -->
        {#if error}
          <div class="mt-4 bg-red-100 border border-red-400 text-red-700 px-4 py-2 rounded text-sm" role="alert">
            {error}
          </div>
        {/if}
      </div>

      <!-- Modal Footer -->
      <div class="bg-gray-50 px-4 py-3 sm:px-6 sm:flex sm:flex-row-reverse border-t border-gray-200">
        <button 
          type="button" 
          class="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-brand text-base font-medium text-white hover:bg-brand-hover focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand sm:ml-3 sm:w-auto sm:text-sm disabled:opacity-50"
          onclick={handleSubmit}
          disabled={isSubmitting || !newName.trim()}
        >
          {#if isSubmitting}
            <svg class="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            {localeLoaded ? $_('assistants.duplicateModal.submitting', { default: 'Creating...' }) : 'Creating...'}
          {:else}
            {localeLoaded ? $_('assistants.duplicateModal.submitButton', { default: 'Create Duplicate' }) : 'Create Duplicate'}
          {/if}
        </button>
        <button 
          type="button" 
          class="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand sm:mt-0 sm:ml-3 sm:w-auto sm:text-sm disabled:opacity-50" 
          onclick={handleClose}
          disabled={isSubmitting}
        >
          {localeLoaded ? $_('common.cancel', { default: 'Cancel' }) : 'Cancel'}
        </button>
      </div>
    </div>
  </div>
{/if} 