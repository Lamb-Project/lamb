<script>
	import { _, locale } from '$lib/i18n';
	import { createEventDispatcher } from 'svelte';

	const dispatch = createEventDispatcher();

	// --- Props ---
	let { isOpen = $bindable(false), assistantName = '', isDeleting = $bindable(false) } = $props();

	// --- Internal State ---
	let localeLoaded = $state(false);

	// --- Lifecycle ---
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
	function handleConfirm() {
		console.log('[DeleteConfirmationModal] handleConfirm called');
		if (isDeleting) return;
		console.log('[DeleteConfirmationModal] About to dispatch confirm event');
		dispatch('confirm');
	}
	function handleClose() {
		if (isDeleting) return; // Prevent closing while delete is in progress
		dispatch('close');
	}

	/** @param {KeyboardEvent} event */
	function handleKeydown(event) {
		if (event.key === 'Escape') {
			handleClose();
		}
		// Optional: Confirm on Enter? Maybe risky for delete.
	}
</script>

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
			aria-labelledby="modal-title-delete"
		>
			<!-- Modal Header -->
			<div class="flex items-center border-b border-red-200 bg-red-50 px-4 py-3 sm:px-6">
				<svg
					class="mr-2 h-6 w-6 text-red-600"
					xmlns="http://www.w3.org/2000/svg"
					fill="none"
					viewBox="0 0 24 24"
					stroke-width="1.5"
					stroke="currentColor"
					aria-hidden="true"
				>
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
					/>
				</svg>
				<h3 class="text-lg leading-6 font-medium text-red-900" id="modal-title-delete">
					{localeLoaded
						? $_('assistants.deleteModal.title', { default: 'Delete Assistant' })
						: 'Delete Assistant'}
				</h3>
			</div>

			<!-- Modal Body -->
			<div class="px-4 py-5 sm:p-6">
				<p class="text-sm text-gray-700">
					{localeLoaded
						? $_('assistants.deleteModal.confirmation', {
								values: { name: assistantName },
								default: `Are you sure you want to delete the assistant "${assistantName}"? This action cannot be undone.`
							})
						: `Are you sure you want to delete the assistant "${assistantName}"? This action cannot be undone.`}
				</p>
				{#if isDeleting}
					<p class="mt-2 text-sm text-red-600">
						{localeLoaded
							? $_('assistants.deleteModal.deleting', { default: 'Deleting...' })
							: 'Deleting...'}
					</p>
				{/if}
			</div>

			<!-- Modal Footer -->
			<div
				class="border-t border-gray-200 bg-gray-50 px-4 py-3 sm:flex sm:flex-row-reverse sm:px-6"
			>
				<button
					type="button"
					class="inline-flex w-full justify-center rounded-md border border-transparent bg-red-600 px-4 py-2 text-base font-medium text-white shadow-sm hover:bg-red-700 focus:ring-2 focus:ring-red-500 focus:ring-offset-2 focus:outline-none disabled:opacity-50 sm:ml-3 sm:w-auto sm:text-sm"
					onclick={handleConfirm}
					disabled={isDeleting}
				>
					{#if isDeleting}
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
					{/if}
					{localeLoaded
						? $_('assistants.deleteModal.confirmButton', { default: 'Delete' })
						: 'Delete'}
				</button>
				<button
					type="button"
					class="mt-3 inline-flex w-full justify-center rounded-md border border-gray-300 bg-white px-4 py-2 text-base font-medium text-gray-700 shadow-sm hover:bg-gray-50 focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 focus:outline-none disabled:opacity-50 sm:mt-0 sm:ml-3 sm:w-auto sm:text-sm"
					onclick={handleClose}
					disabled={isDeleting}
				>
					{localeLoaded ? $_('common.cancel', { default: 'Cancel' }) : 'Cancel'}
				</button>
			</div>
		</div>
	</div>
{/if}
