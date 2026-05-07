<!--
  @component CreateLibraryModal
  Modal form for creating a new library. Emits 'created' event on success.
  Follows the same pattern as CreateKnowledgeBaseModal.svelte.
-->
<script>
	import { createEventDispatcher, tick } from 'svelte';
	import { createLibrary } from '$lib/services/libraryService';
	import { _ } from '$lib/i18n';
	import { user } from '$lib/stores/userStore';
	import {
		saveDraft,
		clearDraft,
		getDraft,
		formatDraftAge
	} from '$lib/stores/wizardDraftStore.svelte.js';

	const dispatch = createEventDispatcher();

	let isOpen = $state(false);
	let isSubmitting = $state(false);
	let error = $state('');
	let nameError = $state('');
	let name = $state('');
	let description = $state('');

	const DRAFT_KIND = 'createLibrary';
	let userId = $derived($user?.data?.id || $user?.email || '_anon');
	let draftBannerVisible = $state(false);
	let draftSavedAt = $state('');

	// Auto-save on field change (debounced inside saveDraft).
	$effect(() => {
		if (!isOpen) return;
		saveDraft(userId, DRAFT_KIND, { name, description });
	});

	/** Suggest a default library name like "My Library 2026-05-07". */
	function suggestDefaultName() {
		const today = new Date().toISOString().slice(0, 10);
		return `My Library ${today}`;
	}

	/** Open the modal and check for an existing draft. */
	export async function open() {
		isOpen = true;
		resetForm();
		// Pre-fill with a sensible default — user can overwrite.
		name = suggestDefaultName();
		// Check for draft before resetting to draft state.
		const draft = getDraft(userId, DRAFT_KIND);
		if (draft?.state) {
			draftBannerVisible = true;
			draftSavedAt = draft.savedAt || '';
		}
		await tick();
		// Select the suggested name so typing replaces it cleanly.
		const input = /** @type {HTMLInputElement|null} */ (
			document.getElementById('lib-name')
		);
		input?.focus();
		input?.select();
	}

	function resumeDraft() {
		const draft = getDraft(userId, DRAFT_KIND);
		if (!draft?.state) return;
		name = draft.state.name || '';
		description = draft.state.description || '';
		draftBannerVisible = false;
	}

	function discardDraft() {
		clearDraft(userId, DRAFT_KIND);
		draftBannerVisible = false;
	}

	function close() {
		if (isSubmitting) return;
		// Save silently on close (already done by the reactive effect).
		isOpen = false;
		draftBannerVisible = false;
		dispatch('close');
	}

	function resetForm() {
		name = '';
		description = '';
		error = '';
		nameError = '';
		isSubmitting = false;
		draftBannerVisible = false;
		draftSavedAt = '';
	}

	function validate() {
		nameError = '';
		if (!name.trim()) {
			nameError = $_('libraries.createModal.nameRequired', { default: 'Name is required' });
			return false;
		}
		if (name.trim().length > 100) {
			nameError = $_('libraries.createModal.nameTooLong', {
				default: 'Name must be less than 100 characters'
			});
			return false;
		}
		return true;
	}

	/** @param {SubmitEvent} event */
	async function handleSubmit(event) {
		event.preventDefault();
		if (!validate()) return;

		isSubmitting = true;
		error = '';

		try {
			const result = await createLibrary({
				name: name.trim(),
				description: description.trim() || ''
			});
			clearDraft(userId, DRAFT_KIND);
			isOpen = false;
			dispatch('created', { id: result.id, name: result.name });
			resetForm();
		} catch (/** @type {unknown} */ err) {
			error = err instanceof Error ? err.message : 'Failed to create library';
			isSubmitting = false;
		}
	}

	/** @param {KeyboardEvent} event */
	function handleKeydown(event) {
		if (event.key === 'Escape') close();
	}

	function handleBackdropClick() {
		close();
	}

	/** @param {MouseEvent} event */
	function stopPropagation(event) {
		event.stopPropagation();
	}
</script>

{#if isOpen}
	<div
		class="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
		role="dialog"
		aria-modal="true"
		aria-labelledby="create-library-title"
		tabindex="-1"
		onclick={handleBackdropClick}
		onkeydown={handleKeydown}
	>
		<!-- Inner panel: presentational only — clicks are stopped to keep the
             backdrop from closing the modal, but it has no semantic interaction
             of its own (the backdrop and form inputs handle keyboard / aria). -->
		<div
			class="mx-4 w-full max-w-md rounded-lg bg-white shadow-xl"
			role="presentation"
			onclick={stopPropagation}
		>
			<div class="border-b border-gray-200 px-6 py-4">
				<h2 id="create-library-title" class="text-lg font-semibold text-gray-900">
					{$_('libraries.createModal.title', { default: 'Create Library' })}
				</h2>
				<p class="mt-1 text-sm text-gray-500">
					{$_('libraries.createModal.description', {
						default: 'Create a new document library to store imported content.'
					})}
				</p>
			</div>

			<form onsubmit={handleSubmit} class="space-y-4 px-6 py-4">
				{#if draftBannerVisible}
					<div
						class="flex items-center justify-between gap-2 rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-800"
						role="status"
					>
						<span>
							{$_('knowledge.wizard.draft.banner', {
								default: 'You have an unfinished draft from {time}.',
								values: { time: formatDraftAge(draftSavedAt) }
							})}
						</span>
						<div class="flex items-center gap-2">
							<button
								type="button"
								onclick={resumeDraft}
								class="font-medium underline hover:no-underline"
							>
								{$_('knowledge.wizard.draft.resume', { default: 'Resume' })}
							</button>
							<button
								type="button"
								onclick={discardDraft}
								class="text-blue-600 hover:text-blue-800"
							>
								{$_('knowledge.wizard.draft.discard', { default: 'Discard' })}
							</button>
						</div>
					</div>
				{/if}

				{#if error}
					<div class="rounded-md bg-red-50 p-3 text-sm text-red-700" role="alert">{error}</div>
				{/if}

				<div>
					<label for="lib-name" class="block text-sm font-medium text-gray-700">
						{$_('libraries.name', { default: 'Name' })} <span class="text-red-500">*</span>
					</label>
					<input
						type="text"
						id="lib-name"
						bind:value={name}
						class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-[#2271b3] focus:ring-[#2271b3] {nameError
							? 'border-red-500'
							: ''}"
						placeholder={$_('libraries.namePlaceholder', { default: 'Enter library name' })}
						disabled={isSubmitting}
					/>
					{#if nameError}
						<p class="mt-1 text-sm text-red-600" role="alert">{nameError}</p>
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
						class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-[#2271b3] focus:ring-[#2271b3]"
						placeholder={$_('libraries.descriptionPlaceholder', {
							default: 'Optional description'
						})}
						disabled={isSubmitting}
					></textarea>
				</div>

				<div class="flex justify-end gap-3 pt-2">
					<button
						type="button"
						onclick={close}
						class="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
						disabled={isSubmitting}
					>
						{$_('common.cancel', { default: 'Cancel' })}
					</button>
					<button
						type="submit"
						class="rounded-md bg-[#2271b3] px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-[#195a91] disabled:opacity-50"
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
