<script>
	import {
		publishModalOpen,
		selectedAssistant,
		publishingStatus,
		resetPublishingStatus
	} from '$lib/stores/assistantPublish';
	import { publishAssistant } from '$lib/services/assistantService'; // Import service function
	import { _, locale } from '$lib/i18n'; // Import i18n
	import { createEventDispatcher, onMount } from 'svelte'; // For dispatching event and onMount

	let localeLoaded = $state(false);
	let form = $state(); // Use $state for form ref
	let groupName = $state('');
	let oauthConsumerName = $state('');

	const dispatch = createEventDispatcher();

	// Check locale loaded state
	onMount(() => {
		const unsubscribe = locale.subscribe((value) => {
			if (value) localeLoaded = true;
		});
		return unsubscribe;
	});

	// Derive from selectedAssistant store
	$effect(() => {
		if ($selectedAssistant) {
			groupName = `assistant_${$selectedAssistant.id}`;
			oauthConsumerName = `${$selectedAssistant.id}_consumer`;
		} else {
			groupName = '';
			oauthConsumerName = '';
		}
	});

	function handleClose() {
		$publishModalOpen = false;
		resetPublishingStatus(); // Reset status on close
	}

	/** @param {SubmitEvent} event */
	async function handleSubmit(event) {
		event.preventDefault();
		if (!$selectedAssistant) return; // Check the object

		publishingStatus.set({ loading: true, error: null, success: false });

		try {
			// Pass ID and Name to the service function
			await publishAssistant(
				$selectedAssistant.id,
				$selectedAssistant.name,
				groupName,
				oauthConsumerName
			);

			publishingStatus.set({ loading: false, error: null, success: true });

			// Dispatch event with ID
			dispatch('assistantPublished', { assistantId: $selectedAssistant.id });

			setTimeout(() => {
				handleClose();
			}, 1500);
		} catch (error) {
			console.error('Error publishing assistant:', error);
			const message = error instanceof Error ? error.message : 'Unknown publishing error';
			publishingStatus.set({ loading: false, error: message, success: false });
		}
	}

	/** @param {KeyboardEvent} event */
	function handleKeydown(event) {
		if (event.key === 'Escape') {
			handleClose();
		}
	}
</script>

<svelte:window onkeydown={handleKeydown} />

{#if $publishModalOpen}
	<!-- Add role=dialog, aria-modal=true -->
	<div
		class="bg-opacity-50 fixed inset-0 z-50 flex items-center justify-center bg-black"
		role="dialog"
		aria-modal="true"
		aria-labelledby="publish-modal-title"
	>
		<!-- The aria-labelledby attribute points to the h2 below -->
		<div class="w-full max-w-md rounded-lg bg-white shadow-xl">
			<div class="flex items-center justify-between border-b p-4">
				<h2 class="text-lg font-semibold" id="publish-modal-title">
					{localeLoaded ? $_('assistants.publishModal.title') : 'Publish Assistant'}
				</h2>
				<button
					class="text-gray-500 hover:text-gray-700"
					onclick={handleClose}
					aria-label={localeLoaded ? $_('common.close') : 'Close modal'}>&times;</button
				>
			</div>

			<form bind:this={form} onsubmit={handleSubmit} class="p-4">
				<div class="mb-4">
					<label for="groupName" class="mb-1 block text-sm font-medium text-gray-700">
						{localeLoaded ? $_('assistants.publishModal.groupName') : 'Group Name'}
					</label>
					<input
						type="text"
						id="groupName"
						bind:value={groupName}
						required
						readonly
						class="w-full cursor-not-allowed rounded-md border border-gray-300 bg-gray-100 px-3 py-2"
						placeholder={localeLoaded
							? $_('assistants.publishModal.groupNamePlaceholder')
							: 'e.g., assistant_123'}
					/>
				</div>

				<div class="mb-4">
					<label for="oauthConsumerName" class="mb-1 block text-sm font-medium text-gray-700">
						{localeLoaded ? $_('assistants.publishModal.oauthConsumer') : 'OAuth Consumer Name'}
					</label>
					<input
						type="text"
						id="oauthConsumerName"
						bind:value={oauthConsumerName}
						required
						readonly
						class="w-full cursor-not-allowed rounded-md border border-gray-300 bg-gray-100 px-3 py-2"
						placeholder={localeLoaded
							? $_('assistants.publishModal.oauthConsumerPlaceholder')
							: 'e.g., 123_consumer'}
					/>
				</div>

				{#if $publishingStatus.error}
					<div class="mt-4 rounded-md bg-red-100 p-2 text-sm text-red-700">
						{localeLoaded ? $_('common.error') : 'Error'}: {$publishingStatus.error}
					</div>
				{/if}

				{#if $publishingStatus.success}
					<div class="mt-4 rounded-md bg-green-100 p-2 text-sm text-green-700">
						{localeLoaded
							? $_('assistants.publishModal.success')
							: 'Assistant published successfully!'}
					</div>
				{/if}

				<div class="mt-6 flex justify-end gap-2">
					<button
						type="button"
						onclick={handleClose}
						class="focus:ring-brand mt-3 inline-flex w-full justify-center rounded-md border border-gray-300 bg-white px-4 py-2 text-base font-medium text-gray-700 shadow-sm hover:bg-gray-50 focus:ring-2 focus:ring-offset-2 focus:outline-none sm:mt-0 sm:ml-3 sm:w-auto sm:text-sm"
					>
						{$_('common.cancel', { default: 'Cancel' })}
					</button>
					<button
						type="submit"
						disabled={$publishingStatus.loading || $publishingStatus.success}
						class="bg-brand hover:bg-brand-hover focus:ring-brand inline-flex w-full justify-center rounded-md border border-transparent px-4 py-2 text-base font-medium text-white shadow-sm focus:ring-2 focus:ring-offset-2 focus:outline-none disabled:opacity-50 sm:ml-3 sm:w-auto sm:text-sm"
						style="background-color: #2271b3;"
					>
						{#if $publishingStatus.loading}
							{localeLoaded ? $_('assistants.publishModal.publishing') : 'Publishing...'}
						{:else}
							{localeLoaded ? $_('assistants.publish') : 'Publish'}
						{/if}
					</button>
				</div>
			</form>
		</div>
	</div>
{/if}

<!-- Removing old style block, assuming Tailwind is used -->
