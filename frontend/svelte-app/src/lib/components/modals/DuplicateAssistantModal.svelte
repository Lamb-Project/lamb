<script>
	import { _, locale } from '$lib/i18n'; // For translated text

	// --- Props (using $props rune) ---
	let {
		isOpen = $bindable(false), // Bindable: Controls modal visibility
		originalName = '', // Name of the assistant being duplicated
		defaultNewName = '', // Pre-filled name for the duplicate
		isSubmitting = $bindable(false), // Bindable: Shows loading state
		error = '', // Displays submission errors
		onSubmit, // Callback for form submission
		onClose // Callback for modal close
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
		localeUnsubscribe = locale.subscribe((value) => {
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
<svelte:window onkeydown={handleKeydown} />

{#if isOpen}
	<!-- Modal Overlay -->
	<div
		class="bg-opacity-75 fixed inset-0 z-40 bg-gray-500 transition-opacity"
		onclick={handleClose}
		aria-hidden="true"
	></div>

	<!-- Modal Panel -->
	<div class="fixed inset-0 z-50 flex items-center justify-center p-4">
		<div
			class="relative w-full max-w-lg overflow-hidden rounded-lg border border-gray-300 bg-white shadow-xl"
			role="dialog"
			aria-modal="true"
			aria-labelledby="modal-title"
		>
			<!-- Modal Header -->
			<div class="border-b border-gray-200 bg-gray-50 px-4 py-3 sm:px-6">
				<h3 class="text-lg leading-6 font-medium text-gray-900" id="modal-title">
					{localeLoaded
						? $_('assistants.duplicateModal.title', { default: 'Duplicate Assistant' })
						: 'Duplicate Assistant'}
				</h3>
			</div>

			<!-- Modal Body -->
			<div class="px-4 py-5 sm:p-6">
				<p class="mb-4 text-sm text-gray-600">
					{localeLoaded
						? $_('assistants.duplicateModal.description', {
								values: { name: originalName },
								default: `Creating a copy of assistant: ${originalName}`
							})
						: `Creating a copy of assistant: ${originalName}`}
				</p>

				<!-- New Name Input -->
				<div>
					<label for="new-assistant-name" class="block text-sm font-medium text-gray-700">
						{localeLoaded
							? $_('assistants.duplicateModal.newNameLabel', { default: 'New Assistant Name' })
							: 'New Assistant Name'}
					</label>
					<div class="mt-1">
						<input
							type="text"
							id="new-assistant-name"
							bind:value={newName}
							disabled={isSubmitting}
							oninput={sanitizeName}
							class="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 disabled:bg-gray-100 sm:text-sm"
							placeholder={localeLoaded
								? $_('assistants.duplicateModal.newNamePlaceholder', {
										default: 'Enter name for the copy...'
									})
								: 'Enter name for the copy...'}
						/>
					</div>
				</div>

				<!-- Error Message -->
				{#if error}
					<div
						class="mt-4 rounded border border-red-400 bg-red-100 px-4 py-2 text-sm text-red-700"
						role="alert"
					>
						{error}
					</div>
				{/if}
			</div>

			<!-- Modal Footer -->
			<div
				class="border-t border-gray-200 bg-gray-50 px-4 py-3 sm:flex sm:flex-row-reverse sm:px-6"
			>
				<button
					type="button"
					class="bg-brand hover:bg-brand-hover inline-flex w-full justify-center rounded-md border border-transparent px-4 py-2 text-base font-medium text-white shadow-sm focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 focus:outline-none disabled:opacity-50 sm:ml-3 sm:w-auto sm:text-sm"
					style="background-color: #2271b3;"
					onclick={handleSubmit}
					disabled={isSubmitting || !newName.trim()}
				>
					{#if isSubmitting}
						<svg
							class="mr-3 -ml-1 h-5 w-5 animate-spin text-white"
							xmlns="http://www.w3.org/2000/svg"
							fill="none"
							viewBox="0 0 24 24"
						>
							<circle
								class="opacity-25"
								cx="12"
								cy="12"
								r="10"
								stroke="currentColor"
								stroke-width="4"
							></circle>
							<path
								class="opacity-75"
								fill="currentColor"
								d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
							></path>
						</svg>
						{localeLoaded
							? $_('assistants.duplicateModal.submitting', { default: 'Creating...' })
							: 'Creating...'}
					{:else}
						{localeLoaded
							? $_('assistants.duplicateModal.submitButton', { default: 'Create Duplicate' })
							: 'Create Duplicate'}
					{/if}
				</button>
				<button
					type="button"
					class="mt-3 inline-flex w-full justify-center rounded-md border border-gray-300 bg-white px-4 py-2 text-base font-medium text-gray-700 shadow-sm hover:bg-gray-50 focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 focus:outline-none disabled:opacity-50 sm:mt-0 sm:ml-3 sm:w-auto sm:text-sm"
					onclick={handleClose}
					disabled={isSubmitting}
				>
					{localeLoaded ? $_('common.cancel', { default: 'Cancel' }) : 'Cancel'}
				</button>
			</div>
		</div>
	</div>
{/if}
