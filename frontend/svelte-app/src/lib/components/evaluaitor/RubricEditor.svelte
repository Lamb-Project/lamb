<script>
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { rubricStore } from '$lib/stores/rubricStore.svelte.js';
	import {
		fetchRubric,
		createRubric,
		updateRubric,
		aiGenerateRubric,
		aiModifyRubric
	} from '$lib/services/rubricService';
	import RubricTable from './RubricTable.svelte';
	import RubricMetadataForm from './RubricMetadataForm.svelte';
	import RubricAIChat from './RubricAIChat.svelte';
	import ConfirmationModal from '$lib/components/modals/ConfirmationModal.svelte';

	// Props
	let { rubricId } = $props();

	// Local state
	let loading = $state(true);
	let saving = $state(false);
	let error = $state(null);
	let showAIChat = $state(false);
	let aiGenerating = $state(false);
	let successMessage = $state(null);
	let showSaveAsModal = $state(false);
	let saveAsTitle = $state('');

	// Check if this is a new rubric (generated from template)
	let isNewRubric = $state(false);

	// Check if we're in edit mode - default to false (view mode)
	let isEditMode = $state(false);

	// Discard changes confirmation modal
	let showDiscardModal = $state(false);

	// Check URL params for edit mode
	$effect(() => {
		const urlParams = new URLSearchParams($page.url.search);
		if (urlParams.has('edit')) {
			isEditMode = urlParams.get('edit') === 'true';
		}
	});

	// Enter edit mode
	function enterEditMode() {
		isEditMode = true;
	}

	// Open discard changes modal
	function cancelEdit() {
		showDiscardModal = true;
	}

	// Confirm discard changes
	function confirmDiscard() {
		loadRubric(); // Reload from backend to discard changes
		isEditMode = false;
		showDiscardModal = false;
	}

	// Cancel discard
	function cancelDiscard() {
		showDiscardModal = false;
	}

	// Load rubric data
	async function loadRubric() {
		if (!rubricId) {
			error = 'No rubric ID provided';
			loading = false;
			return;
		}

		try {
			loading = true;
			const rubricData = await fetchRubric(rubricId);
			rubricStore.loadRubric(rubricData.rubric_data);
		} catch (err) {
			error = err.message || 'Failed to load rubric';
			console.error('Error loading rubric:', err);
		} finally {
			loading = false;
		}
	}

	// Save rubric
	async function saveRubric() {
		const rubricData = rubricStore.getRubricData();
		if (!rubricData) {
			error = 'No rubric data to save';
			return;
		}

		// Validate rubric
		const validation = rubricStore.validate();
		if (!validation.isValid) {
			error = `Validation errors: ${validation.errors.join(', ')}`;
			return;
		}

		try {
			saving = true;
			error = null;
			successMessage = null;

			// Prepare full rubric data for API
			const fullRubricData = {
				...rubricData,
				rubricId: rubricId,
				metadata: {
					...rubricData.metadata,
					modifiedAt: new Date().toISOString()
				}
			};

			await updateRubric(rubricId, fullRubricData);

			// Show success message
			successMessage = 'Rubric updated';

			// Exit edit mode
			isEditMode = false;

			// Reload rubric to ensure we have the latest data
			await loadRubric();

			// Clear success message after 3 seconds
			setTimeout(() => {
				successMessage = null;
			}, 3000);
		} catch (err) {
			error = err.message || 'Failed to save rubric';
			console.error('Error saving rubric:', err);
		} finally {
			saving = false;
		}
	}

	// Save as new version
	async function saveAsNewVersion() {
		const rubricData = rubricStore.getRubricData();
		if (!rubricData) {
			error = 'No rubric data to save';
			return;
		}

		// Validate rubric
		const validation = rubricStore.validate();
		if (!validation.isValid) {
			error = `Validation errors: ${validation.errors.join(', ')}`;
			return;
		}

		// Show modal to ask for new title
		saveAsTitle = `${rubricData.title} (Copy)`;
		showSaveAsModal = true;
	}

	// Confirm save as with the new title
	async function confirmSaveAs() {
		if (!saveAsTitle.trim()) {
			error = 'Please enter a title for the new rubric';
			return;
		}

		const rubricData = rubricStore.getRubricData();

		try {
			saving = true;
			error = null;
			successMessage = null;

			// Create new rubric with the specified title
			const versionedData = {
				...rubricData,
				title: saveAsTitle,
				metadata: {
					...rubricData.metadata,
					createdAt: new Date().toISOString(),
					modifiedAt: new Date().toISOString()
				}
			};

			const response = await createRubric(versionedData);

			console.log('Create rubric response:', response);

			// Extract rubric ID from response
			// Backend returns: { success: true, rubric: { rubric_id: "...", ... } }
			const newRubricId = response.rubric?.rubric_id || response.rubricId || response.id;

			console.log('New rubric ID:', newRubricId);
			console.log('Current rubric ID (should be different):', rubricId);

			if (!newRubricId) {
				console.error('Failed to extract rubric ID from response:', response);
				throw new Error('Failed to get new rubric ID from response');
			}

			// Close modal
			showSaveAsModal = false;
			saveAsTitle = '';

			// Show success message
			successMessage = 'Rubric saved as new version';

			// Wait a moment for success message to be visible, then navigate to new rubric in VIEW mode
			// Use window.location.href to force a full page reload and ensure we're in view mode
			setTimeout(() => {
				console.log('Navigating to new rubric:', `/evaluaitor/${newRubricId}`);
				window.location.href = `/evaluaitor/${newRubricId}`;
			}, 1500);
		} catch (err) {
			error = err.message || 'Failed to create new version';
			console.error('Error creating new version:', err);
		} finally {
			saving = false;
		}
	}

	// Cancel save as
	function cancelSaveAs() {
		showSaveAsModal = false;
		saveAsTitle = '';
		error = null;
	}

	// Handle AI generation
	async function handleAIGenerate(prompt) {
		try {
			aiGenerating = true;
			error = null;

			const response = await aiGenerateRubric(prompt);

			// Load the generated rubric into the store
			rubricStore.loadRubric(response.rubric_data);

			// Mark as new rubric (not saved yet)
			isNewRubric = true;

			showAIChat = false;

			console.log('AI generation completed:', response.explanation);
		} catch (err) {
			error = err.message || 'Failed to generate rubric with AI';
			console.error('Error generating rubric:', err);
		} finally {
			aiGenerating = false;
		}
	}

	// Handle AI modification
	async function handleAIModify(prompt) {
		const currentRubricData = rubricStore.getRubricData();
		if (!currentRubricData) {
			error = 'No rubric to modify';
			return;
		}

		try {
			aiGenerating = true;
			error = null;

			const response = await aiModifyRubric(rubricId, prompt);

			// Show changes preview (you could add a modal here)
			const changes = rubricStore.getChanges(response.rubric_data);

			// For now, just apply the changes directly
			rubricStore.replaceRubric(response.rubric_data);

			console.log('AI modification completed:', response.explanation);
			console.log('Changes:', changes);
		} catch (err) {
			error = err.message || 'Failed to modify rubric with AI';
			console.error('Error modifying rubric:', err);
		} finally {
			aiGenerating = false;
		}
	}

	// Handle undo/redo
	function handleUndo() {
		rubricStore.undo();
	}

	function handleRedo() {
		rubricStore.redo();
	}

	// Handle back navigation
	function handleBack() {
		goto('/evaluaitor');
	}

	// Initialize
	onMount(() => {
		loadRubric();
	});

	// Reactive effects
	$effect(() => {
		// Update document title when rubric title changes
		if (rubricStore.rubric?.title) {
			document.title = `${rubricStore.rubric.title} - Evaluaitor`;
		}
	});
</script>

<div class="min-h-screen bg-gray-50">
	<!-- Success Toast -->
	{#if successMessage}
		<div class="animate-fade-in fixed top-4 right-4 z-50">
			<div class="rounded-md border border-green-200 bg-green-50 p-4 shadow-lg">
				<div class="flex items-center">
					<div class="flex-shrink-0">
						<svg
							class="h-5 w-5 text-green-400"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
						>
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="2"
								d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
							/>
						</svg>
					</div>
					<div class="ml-3">
						<p class="text-sm font-medium text-green-800">{successMessage}</p>
					</div>
					<div class="ml-auto pl-3">
						<button
							onclick={() => (successMessage = null)}
							class="inline-flex text-green-400 hover:text-green-600"
							aria-label="Dismiss success message"
						>
							<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									stroke-width="2"
									d="M6 18L18 6M6 6l12 12"
								/>
							</svg>
						</button>
					</div>
				</div>
			</div>
		</div>
	{/if}

	<!-- Save As Modal -->
	{#if showSaveAsModal}
		<div class="fixed inset-0 z-50 overflow-y-auto">
			<div
				class="flex min-h-screen items-center justify-center px-4 pt-4 pb-20 text-center sm:block sm:p-0"
			>
				<!-- Background overlay -->
				<div
					class="bg-opacity-75 fixed inset-0 bg-gray-500 transition-opacity"
					onclick={cancelSaveAs}
					onkeydown={(e) => {
						if (e.key === 'Enter' || e.key === ' ') {
							cancelSaveAs();
						}
					}}
					role="button"
					aria-label="Close modal"
					tabindex="-1"
				></div>

				<!-- Modal panel -->
				<div
					class="relative z-50 inline-block transform overflow-hidden rounded-lg bg-white px-4 pt-5 pb-4 text-left align-bottom shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-lg sm:p-6 sm:align-middle"
				>
					<div>
						<div class="mt-3 text-center sm:mt-0 sm:text-left">
							<h3 class="text-lg leading-6 font-medium text-gray-900">Save as New Rubric</h3>
							<div class="mt-4">
								<label for="rubric-title" class="block text-sm font-medium text-gray-700">
									Rubric Title
								</label>
								<input
									id="rubric-title"
									type="text"
									bind:value={saveAsTitle}
									class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:ring-blue-500 focus:outline-none sm:text-sm"
									placeholder="Enter new rubric title"
									onkeydown={(e) => {
										if (e.key === 'Enter') {
											confirmSaveAs();
										} else if (e.key === 'Escape') {
											cancelSaveAs();
										}
									}}
								/>
								<p class="mt-2 text-sm text-gray-500">
									A new rubric will be created with this title.
								</p>
							</div>
						</div>
					</div>
					<div class="mt-5 sm:mt-4 sm:flex sm:flex-row-reverse">
						<button
							type="button"
							onclick={confirmSaveAs}
							disabled={saving || !saveAsTitle.trim()}
							class="inline-flex w-full justify-center rounded-md border border-transparent bg-blue-600 px-4 py-2 text-base font-medium text-white shadow-sm hover:bg-blue-700 focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50 sm:ml-3 sm:w-auto sm:text-sm"
						>
							{#if saving}
								<svg
									class="mr-2 -ml-1 h-4 w-4 animate-spin text-white"
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
								Creating...
							{:else}
								Create Rubric
							{/if}
						</button>
						<button
							type="button"
							onclick={cancelSaveAs}
							disabled={saving}
							class="mt-3 inline-flex w-full justify-center rounded-md border border-gray-300 bg-white px-4 py-2 text-base font-medium text-gray-700 shadow-sm hover:bg-gray-50 focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50 sm:mt-0 sm:w-auto sm:text-sm"
						>
							Cancel
						</button>
					</div>
				</div>
			</div>
		</div>
	{/if}

	<!-- Header -->
	<div class="bg-white shadow">
		<div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
			<div class="py-6">
				<!-- Back button and status indicator -->
				<div class="mb-4 flex items-center justify-between">
					<button
						onclick={handleBack}
						class="rounded-md p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-500"
						aria-label="Go back"
					>
						<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="2"
								d="M15 19l-7-7 7-7"
							/>
						</svg>
					</button>

					<!-- Status Badge and Action Buttons -->
					<div class="flex items-center space-x-3">
						{#if isEditMode || isNewRubric}
							<!-- Edit Mode Indicator -->
							<span
								class="inline-flex items-center rounded-md border border-blue-200 bg-blue-100 px-3 py-1 text-sm font-medium text-blue-800"
							>
								<svg
									class="mr-2 -ml-0.5 h-4 w-4"
									fill="none"
									stroke="currentColor"
									viewBox="0 0 24 24"
								>
									<path
										stroke-linecap="round"
										stroke-linejoin="round"
										stroke-width="2"
										d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
									/>
								</svg>
								Editing Rubric
							</span>

							<!-- Undo/Redo buttons -->
							<button
								onclick={handleUndo}
								disabled={!rubricStore.canUndo}
								class="rounded-md p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-500 disabled:cursor-not-allowed disabled:opacity-50"
								title="Undo"
							>
								<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path
										stroke-linecap="round"
										stroke-linejoin="round"
										stroke-width="2"
										d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6"
									/>
								</svg>
							</button>
							<button
								onclick={handleRedo}
								disabled={!rubricStore.canRedo}
								class="rounded-md p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-500 disabled:cursor-not-allowed disabled:opacity-50"
								title="Redo"
							>
								<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path
										stroke-linecap="round"
										stroke-linejoin="round"
										stroke-width="2"
										d="M21 10H11a8 8 0 00-8 8v2M21 10l-6 6m6-6l-6-6"
									/>
								</svg>
							</button>

							{#if !isNewRubric}
								<!-- Cancel Edit Button -->
								<button
									onclick={cancelEdit}
									disabled={saving || loading}
									class="inline-flex items-center rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
								>
									<svg
										class="mr-2 -ml-1 h-5 w-5"
										fill="none"
										stroke="currentColor"
										viewBox="0 0 24 24"
									>
										<path
											stroke-linecap="round"
											stroke-linejoin="round"
											stroke-width="2"
											d="M6 18L18 6M6 6l12 12"
										/>
									</svg>
									Cancel
								</button>
							{/if}

							<!-- Update/Save Button -->
							<button
								onclick={saveRubric}
								disabled={saving || loading}
								class="inline-flex items-center rounded-md border border-transparent bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
							>
								{#if saving}
									<svg
										class="mr-2 -ml-1 h-4 w-4 animate-spin text-white"
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
									{isNewRubric ? 'Saving...' : 'Updating...'}
								{:else}
									<svg
										class="mr-2 -ml-1 h-5 w-5"
										fill="none"
										stroke="currentColor"
										viewBox="0 0 24 24"
									>
										<path
											stroke-linecap="round"
											stroke-linejoin="round"
											stroke-width="2"
											d="M5 13l4 4L19 7"
										/>
									</svg>
									{isNewRubric ? 'Save' : 'Update Rubric'}
								{/if}
							</button>

							<!-- Save as New Version -->
							{#if !isNewRubric}
								<button
									onclick={saveAsNewVersion}
									disabled={saving || loading}
									class="inline-flex items-center rounded-md border border-gray-300 bg-white px-4 py-2 text-sm leading-4 font-medium text-gray-700 shadow-sm hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
								>
									Save as New Version
								</button>
							{/if}
						{:else}
							<!-- VIEW MODE: Show view label and edit button -->

							<!-- View Only Label/Badge -->
							<span
								class="inline-flex items-center rounded-md border border-gray-300 bg-gray-100 px-3 py-1 text-sm font-medium text-gray-700"
							>
								<svg
									class="mr-2 -ml-0.5 h-4 w-4"
									fill="none"
									stroke="currentColor"
									viewBox="0 0 24 24"
								>
									<path
										stroke-linecap="round"
										stroke-linejoin="round"
										stroke-width="2"
										d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
									/>
									<path
										stroke-linecap="round"
										stroke-linejoin="round"
										stroke-width="2"
										d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
									/>
								</svg>
								View Only
							</span>

							<!-- Edit Button -->
							<button
								onclick={enterEditMode}
								class="inline-flex items-center rounded-md border border-transparent bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-blue-700"
							>
								<svg
									class="mr-2 -ml-1 h-5 w-5"
									fill="none"
									stroke="currentColor"
									viewBox="0 0 24 24"
								>
									<path
										stroke-linecap="round"
										stroke-linejoin="round"
										stroke-width="2"
										d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
									/>
								</svg>
								Edit
							</button>
						{/if}
					</div>
				</div>

				<!-- Rubric Title (Bigger) -->
				<h1 class="mb-3 text-3xl font-bold text-gray-900">
					{rubricStore.rubric?.title || 'Loading...'}
				</h1>

				<!-- Description (Wide box below title) -->
				{#if rubricStore.rubric?.description}
					<div class="rounded-md border border-gray-200 bg-gray-50 p-4">
						<p class="text-sm leading-relaxed text-gray-700">
							{rubricStore.rubric.description}
						</p>
					</div>
				{/if}
			</div>
		</div>
	</div>

	<!-- Main Content -->
	<div class="mx-auto max-w-none px-6 py-6 lg:px-12">
		{#if loading}
			<div class="py-12 text-center">
				<div class="mx-auto h-12 w-12 animate-spin rounded-full border-b-2 border-blue-600"></div>
				<p class="mt-4 text-lg text-gray-600">Loading rubric...</p>
			</div>
		{:else if error}
			<div class="mb-6 rounded-md border border-red-200 bg-red-50 p-4">
				<div class="flex">
					<div class="flex-shrink-0">
						<svg class="h-5 w-5 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="2"
								d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z"
							/>
						</svg>
					</div>
					<div class="ml-3">
						<h3 class="text-sm font-medium text-red-800">Error</h3>
						<div class="mt-2 text-sm text-red-700">{error}</div>
						<div class="mt-4">
							<button
								onclick={() => goto('/evaluaitor')}
								class="rounded-md bg-red-100 px-3 py-2 text-sm font-medium text-red-800 hover:bg-red-200"
							>
								Back to Rubrics
							</button>
						</div>
					</div>
				</div>
			</div>
		{:else}
			<div class="grid grid-cols-1 {showAIChat ? 'xl:grid-cols-4' : ''} gap-8">
				<!-- Main Editor Area -->
				<div class="{showAIChat ? 'xl:col-span-3' : ''} space-y-8">
					<!-- Rubric Metadata -->
					<RubricMetadataForm {isEditMode} />

					<!-- Rubric Table -->
					<RubricTable {isEditMode} />
				</div>

				<!-- AI Chat Panel -->
				{#if showAIChat}
					<div class="xl:col-span-1">
						<RubricAIChat
							{rubricId}
							{aiGenerating}
							onGenerate={handleAIGenerate}
							onModify={handleAIModify}
						/>
					</div>
				{/if}
			</div>
		{/if}
	</div>
</div>

<!-- Discard Changes Confirmation Modal -->
<ConfirmationModal
	bind:isOpen={showDiscardModal}
	title="Discard Changes"
	message="Are you sure you want to discard all changes and exit edit mode? Any unsaved changes will be lost."
	confirmText="Discard"
	variant="warning"
	onconfirm={confirmDiscard}
	oncancel={cancelDiscard}
/>

<style>
	/* Toast animation */
	@keyframes fade-in {
		from {
			opacity: 0;
			transform: translateY(-1rem);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}

	.animate-fade-in {
		animation: fade-in 0.3s ease-out;
	}
</style>
