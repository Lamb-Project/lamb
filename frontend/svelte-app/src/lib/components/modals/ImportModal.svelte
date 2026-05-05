<!--
  @component ImportModal
  Modal for importing content into a library from URL, YouTube, or ZIP file.
  Emits 'imported' event on success.
-->
<script>
	import axios from 'axios';
	import { createEventDispatcher, tick } from 'svelte';
	import { importUrl, importYouTube, importLibrary } from '$lib/services/libraryService';
	import { _ } from '$lib/i18n';

	const MAX_ZIP_SIZE = 500 * 1024 * 1024;

	const dispatch = createEventDispatcher();

	/** @type {string} */
	let libraryId = '';
	let isOpen = $state(false);
	let isSubmitting = $state(false);
	let error = $state('');

	let importType = $state('url');
	let url = $state('');
	let videoUrl = $state('');
	let language = $state('en');
	let title = $state('');
	/** @type {File|null} */
	let zipFile = $state(null);

	/**
	 * Open the modal for a specific library.
	 * @param {string} id - Library ID.
	 */
	export async function open(id) {
		libraryId = id;
		isOpen = true;
		resetForm();
		await tick();
		focusFirstInput();
	}

	function focusFirstInput() {
		if (importType === 'url') {
			document.getElementById('import-url')?.focus();
		} else if (importType === 'youtube') {
			document.getElementById('import-yt-url')?.focus();
		} else if (importType === 'zip') {
			document.getElementById('import-zip')?.focus();
		}
	}

	function close() {
		if (isSubmitting) return;
		isOpen = false;
		resetForm();
	}

	function resetForm() {
		importType = 'url';
		url = '';
		videoUrl = '';
		language = 'en';
		title = '';
		zipFile = null;
		error = '';
		isSubmitting = false;
	}

	function isValidHttpUrl(value) {
		try {
			const parsed = new URL(value);
			return parsed.protocol === 'http:' || parsed.protocol === 'https:';
		} catch {
			return false;
		}
	}

	async function handleSubmit(event) {
		event.preventDefault();
		isSubmitting = true;
		error = '';

		try {
			if (importType === 'url') {
				if (!url.trim() || !isValidHttpUrl(url.trim())) {
					error = $_('libraries.importModal.invalidUrl', {
						default: 'A valid HTTP(S) URL is required.'
					});
					isSubmitting = false;
					return;
				}
				const result = await importUrl(libraryId, {
					url: url.trim(),
					title: title.trim() || undefined
				});
				isOpen = false;
				dispatch('imported', { type: 'url', itemId: result.item_id });
			} else if (importType === 'youtube') {
				if (!videoUrl.trim() || !isValidHttpUrl(videoUrl.trim())) {
					error = $_('libraries.importModal.invalidYoutubeUrl', {
						default: 'A valid YouTube URL is required.'
					});
					isSubmitting = false;
					return;
				}
				const result = await importYouTube(libraryId, {
					videoUrl: videoUrl.trim(),
					language,
					title: title.trim() || undefined
				});
				isOpen = false;
				dispatch('imported', { type: 'youtube', itemId: result.item_id });
			} else if (importType === 'zip') {
				if (!zipFile) {
					error = $_('libraries.importModal.zipRequired', { default: 'A ZIP file is required.' });
					isSubmitting = false;
					return;
				}
				if (zipFile.size > MAX_ZIP_SIZE) {
					error = $_('libraries.importModal.zipTooLarge', {
						default: 'ZIP file exceeds 500 MB limit.'
					});
					isSubmitting = false;
					return;
				}
				const result = await importLibrary(zipFile);
				isOpen = false;
				dispatch('imported', {
					type: 'zip',
					libraryId: result.library_id,
					libraryName: result.library_name
				});
			}
			resetForm();
		} catch (/** @type {unknown} */ err) {
			error =
				axios.isAxiosError(err) && err.response?.data?.detail
					? err.response.data.detail
					: $_('libraries.importModal.importFailed', {
							default: 'Import failed. Please try again.'
						});
			isSubmitting = false;
		}
	}

	function handleZipSelect(event) {
		const files = event.target?.files;
		zipFile = files?.[0] || null;
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
		aria-labelledby="import-modal-title"
		tabindex="-1"
		onclick={handleBackdropClick}
		onkeydown={handleKeydown}
	>
		<!-- Inner panel: presentational only — see CreateLibraryModal for context. -->
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<!-- svelte-ignore a11y_click_events_have_key_events -->
		<div
			class="mx-4 w-full max-w-lg rounded-lg bg-white shadow-xl"
			role="presentation"
			onclick={stopPropagation}
		>
			<div class="border-b border-gray-200 px-6 py-4">
				<h2 id="import-modal-title" class="text-lg font-semibold text-gray-900">
					{$_('libraries.importModal.title', { default: 'Import Content' })}
				</h2>
			</div>

			<form onsubmit={handleSubmit} class="space-y-4 px-6 py-4">
				{#if error}
					<div class="rounded-md bg-red-50 p-3 text-sm text-red-700" role="alert">{error}</div>
				{/if}

				<fieldset>
					<legend class="mb-2 block text-sm font-medium text-gray-700">
						{$_('libraries.importModal.typeLabel', { default: 'Import type' })}
					</legend>
					<div class="flex gap-2">
						{#each [{ value: 'url', label: $_( 'libraries.importModal.typeUrl', { default: 'URL' } ) }, { value: 'youtube', label: $_( 'libraries.importModal.typeYouTube', { default: 'YouTube' } ) }, { value: 'zip', label: $_( 'libraries.importModal.typeZip', { default: 'ZIP Archive' } ) }] as tab}
							<button
								type="button"
								class="rounded-md border px-3 py-1.5 text-sm {importType === tab.value
									? 'border-[#2271b3] bg-[#2271b3] text-white'
									: 'border-gray-300 bg-white text-gray-700 hover:bg-gray-50'}"
								onclick={() => {
									importType = tab.value;
									error = '';
								}}
							>
								{tab.label}
							</button>
						{/each}
					</div>
				</fieldset>

				{#if importType === 'url'}
					<div>
						<label for="import-url" class="block text-sm font-medium text-gray-700">
							URL <span class="text-red-500">*</span>
						</label>
						<input
							type="url"
							id="import-url"
							bind:value={url}
							class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-[#2271b3] focus:ring-[#2271b3]"
							placeholder="https://example.com/document"
							disabled={isSubmitting}
							required
						/>
					</div>
					<div>
						<label for="import-url-title" class="block text-sm font-medium text-gray-700">
							{$_('libraries.importModal.titleLabel', { default: 'Title (optional)' })}
						</label>
						<input
							type="text"
							id="import-url-title"
							bind:value={title}
							class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-[#2271b3] focus:ring-[#2271b3]"
							disabled={isSubmitting}
						/>
					</div>
				{:else if importType === 'youtube'}
					<div>
						<label for="import-yt-url" class="block text-sm font-medium text-gray-700">
							{$_('libraries.importModal.youtubeUrl', { default: 'YouTube URL' })}
							<span class="text-red-500">*</span>
						</label>
						<input
							type="url"
							id="import-yt-url"
							bind:value={videoUrl}
							class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-[#2271b3] focus:ring-[#2271b3]"
							placeholder="https://www.youtube.com/watch?v=..."
							disabled={isSubmitting}
							required
						/>
					</div>
					<div>
						<label for="import-yt-lang" class="block text-sm font-medium text-gray-700">
							{$_('libraries.importModal.language', { default: 'Transcript language' })}
						</label>
						<input
							type="text"
							id="import-yt-lang"
							bind:value={language}
							class="mt-1 block w-32 rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-[#2271b3] focus:ring-[#2271b3]"
							placeholder="en"
							disabled={isSubmitting}
						/>
					</div>
					<div>
						<label for="import-yt-title" class="block text-sm font-medium text-gray-700">
							{$_('libraries.importModal.titleLabel', { default: 'Title (optional)' })}
						</label>
						<input
							type="text"
							id="import-yt-title"
							bind:value={title}
							class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-[#2271b3] focus:ring-[#2271b3]"
							disabled={isSubmitting}
						/>
					</div>
				{:else if importType === 'zip'}
					<div>
						<label for="import-zip" class="block text-sm font-medium text-gray-700">
							{$_('libraries.importModal.zipFile', { default: 'ZIP file' })}
							<span class="text-red-500">*</span>
						</label>
						<input
							type="file"
							id="import-zip"
							accept=".zip"
							onchange={handleZipSelect}
							class="mt-1 block w-full text-sm text-gray-500 file:mr-4 file:rounded-md file:border-0 file:bg-[#2271b3] file:px-4 file:py-2 file:text-sm file:font-semibold file:text-white hover:file:bg-[#195a91]"
							disabled={isSubmitting}
						/>
						<p class="mt-1 text-xs text-gray-500">
							{$_('libraries.importModal.zipHint', {
								default: 'Import a previously exported library.'
							})}
						</p>
					</div>
				{/if}

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
							{$_('libraries.importModal.importing', { default: 'Importing...' })}
						{:else}
							{$_('libraries.importModal.importButton', { default: 'Import' })}
						{/if}
					</button>
				</div>
			</form>
		</div>
	</div>
{/if}
