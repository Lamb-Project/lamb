<!--
  @component StepLibraryContent
  Optional step. File picker + URL + YouTube import queue.
  Content is NOT uploaded here — collected in memory until Step 5 ("Create").

  Source types:
    - Files: drag-drop / browse (existing behaviour)
    - URL:  text input for http(s) URL + optional title
    - YouTube: YouTube URL + optional language + optional title

  All queued sources are shown in a unified list with a type badge.

  Emits:
    - update: { pendingFiles, pendingUrlSources }
    - validity: { valid: boolean }   (always true — skippable)
-->
<script>
	import { createEventDispatcher } from 'svelte';
	import { _ } from '$lib/i18n';

	/** @type {{ wizardState: any }} */
	let { wizardState } = $props();

	const dispatch = createEventDispatcher();

	// ── Files ────────────────────────────────────────────────────────────────
	let files = $state(/** @type {File[]} */ (wizardState.pendingFiles || []));

	// ── URL / YouTube sources ────────────────────────────────────────────────
	/**
	 * @typedef {{ type: 'url'|'youtube', url: string, title?: string, language?: string }} UrlSource
	 */
	let urlSources = $state(/** @type {UrlSource[]} */ (wizardState.pendingUrlSources || []));

	// ── Source type selector ─────────────────────────────────────────────────
	let sourceType = $state(/** @type {'files'|'url'|'youtube'} */ ('files'));

	// Inputs for URL / YouTube
	let inputUrl = $state('');
	let inputUrlTitle = $state('');
	let inputYtUrl = $state('');
	let inputYtTitle = $state('');
	let inputYtLang = $state('en');
	let urlError = $state('');

	// ── Dispatch on changes ──────────────────────────────────────────────────
	$effect(() => {
		dispatch('validity', { valid: true });
		dispatch('update', { pendingFiles: files, pendingUrlSources: urlSources });
	});

	// ── File handling ────────────────────────────────────────────────────────
	/** @param {Event} event */
	function handleFileChange(event) {
		const target = /** @type {HTMLInputElement} */ (event.target);
		if (!target.files) return;
		const incoming = Array.from(target.files);
		files = [...files, ...incoming];
		target.value = '';
	}

	/** @param {number} idx */
	function removeFile(idx) {
		files = files.filter((_, i) => i !== idx);
	}

	/** @param {number} bytes */
	function formatSize(bytes) {
		if (bytes < 1024) return `${bytes} B`;
		if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
		return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
	}

	// ── URL validation ───────────────────────────────────────────────────────
	/** @param {string} value */
	function isValidHttpUrl(value) {
		try {
			const parsed = new URL(value);
			return parsed.protocol === 'http:' || parsed.protocol === 'https:';
		} catch {
			return false;
		}
	}

	// ── Add URL source ───────────────────────────────────────────────────────
	function addUrlSource() {
		urlError = '';
		const trimmed = inputUrl.trim();
		if (!trimmed || !isValidHttpUrl(trimmed)) {
			urlError = $_('knowledge.wizard.libraryContent.invalidUrl', {
				default: 'A valid HTTP(S) URL is required.'
			});
			return;
		}
		urlSources = [
			...urlSources,
			{ type: 'url', url: trimmed, title: inputUrlTitle.trim() || undefined }
		];
		inputUrl = '';
		inputUrlTitle = '';
	}

	// ── Add YouTube source ───────────────────────────────────────────────────
	function addYtSource() {
		urlError = '';
		const trimmed = inputYtUrl.trim();
		if (!trimmed || !isValidHttpUrl(trimmed)) {
			urlError = $_('knowledge.wizard.libraryContent.invalidYoutubeUrl', {
				default: 'A valid YouTube URL is required.'
			});
			return;
		}
		urlSources = [
			...urlSources,
			{
				type: 'youtube',
				url: trimmed,
				title: inputYtTitle.trim() || undefined,
				language: inputYtLang.trim() || 'en'
			}
		];
		inputYtUrl = '';
		inputYtTitle = '';
		inputYtLang = 'en';
	}

	/** @param {number} idx */
	function removeUrlSource(idx) {
		urlSources = urlSources.filter((_, i) => i !== idx);
	}

	/** @param {'url'|'youtube'} type */
	function sourceBadge(type) {
		return type === 'url' ? '🔗' : '▶';
	}

	let totalSources = $derived(files.length + urlSources.length);
</script>

<div class="space-y-4">
	<h3 class="text-base font-semibold text-gray-900">
		{$_('knowledge.wizard.libraryContent.heading', { default: 'Initial content' })}
	</h3>

	<!-- Optional-step info card -->
	<div
		class="rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-900"
		role="note"
	>
		<span class="mr-1.5 inline-block align-text-bottom" aria-hidden="true">
			<svg
				xmlns="http://www.w3.org/2000/svg"
				class="inline h-4 w-4"
				viewBox="0 0 20 20"
				fill="currentColor"
			>
				<path
					fill-rule="evenodd"
					d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
					clip-rule="evenodd"
				/>
			</svg>
		</span>
		{$_('knowledge.wizard.libraryContent.optionalHint', {
			default:
				'Adding content here is optional — you can also add files, URLs, or YouTube transcripts later from the Library detail page. Note: a Knowledge Store can only ingest items that exist in its Library, so anything you skip now must be added to the Library before it can land in the Knowledge Store.'
		})}
	</div>

	<!-- Source type selector -->
	<div class="flex gap-2">
		{#each [{ value: 'files', label: $_( 'knowledge.wizard.libraryContent.sourceTypeFiles', { default: 'Files' } ) }, { value: 'url', label: $_( 'knowledge.wizard.libraryContent.sourceTypeUrl', { default: 'URL' } ) }, { value: 'youtube', label: $_( 'knowledge.wizard.libraryContent.sourceTypeYouTube', { default: 'YouTube' } ) }] as tab (tab.value)}
			<button
				type="button"
				class="rounded-md border px-3 py-1.5 text-sm {sourceType === tab.value
					? 'border-[#2271b3] bg-[#2271b3] text-white'
					: 'border-gray-300 bg-white text-gray-700 hover:bg-gray-50'}"
				onclick={() => {
					sourceType = /** @type {'files'|'url'|'youtube'} */ (tab.value);
					urlError = '';
				}}
			>
				{tab.label}
			</button>
		{/each}
	</div>

	<!-- File picker -->
	{#if sourceType === 'files'}
		<div>
			<label for="wizard-library-files" class="block text-sm font-medium text-gray-700">
				{$_('knowledge.wizard.libraryContent.pickLabel', { default: 'Pick files' })}
			</label>
			<input
				type="file"
				id="wizard-library-files"
				multiple
				onchange={handleFileChange}
				class="mt-1 block w-full text-sm text-gray-700 file:mr-3 file:rounded-md file:border-0 file:bg-[#2271b3] file:px-4 file:py-2 file:text-sm file:font-medium file:text-white hover:file:bg-[#195a91]"
			/>
		</div>
	{/if}

	<!-- URL input -->
	{#if sourceType === 'url'}
		<div class="space-y-3 rounded-md border border-gray-200 p-3">
			{#if urlError}
				<div class="rounded-md bg-red-50 p-2 text-sm text-red-700" role="alert">{urlError}</div>
			{/if}
			<div>
				<label for="wizard-url-input" class="block text-sm font-medium text-gray-700">
					URL <span class="text-red-500">*</span>
				</label>
				<input
					type="url"
					id="wizard-url-input"
					bind:value={inputUrl}
					class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-[#2271b3] focus:ring-[#2271b3]"
					placeholder="https://example.com/document"
				/>
			</div>
			<div>
				<label for="wizard-url-title" class="block text-sm font-medium text-gray-700">
					{$_('knowledge.wizard.libraryContent.titleOptional', { default: 'Title (optional)' })}
				</label>
				<input
					type="text"
					id="wizard-url-title"
					bind:value={inputUrlTitle}
					class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-[#2271b3] focus:ring-[#2271b3]"
				/>
			</div>
			<button
				type="button"
				onclick={addUrlSource}
				class="rounded-md border border-[#2271b3] px-3 py-1.5 text-sm font-medium text-[#2271b3] hover:bg-blue-50"
			>
				{$_('knowledge.wizard.libraryContent.addUrl', { default: '+ Add URL' })}
			</button>
		</div>
	{/if}

	<!-- YouTube input -->
	{#if sourceType === 'youtube'}
		<div class="space-y-3 rounded-md border border-gray-200 p-3">
			{#if urlError}
				<div class="rounded-md bg-red-50 p-2 text-sm text-red-700" role="alert">{urlError}</div>
			{/if}
			<div>
				<label for="wizard-yt-url" class="block text-sm font-medium text-gray-700">
					{$_('knowledge.wizard.libraryContent.youtubeUrl', { default: 'YouTube URL' })}
					<span class="text-red-500">*</span>
				</label>
				<input
					type="url"
					id="wizard-yt-url"
					bind:value={inputYtUrl}
					class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-[#2271b3] focus:ring-[#2271b3]"
					placeholder="https://www.youtube.com/watch?v=..."
				/>
			</div>
			<div>
				<label for="wizard-yt-lang" class="block text-sm font-medium text-gray-700">
					{$_('knowledge.wizard.libraryContent.ytLanguage', { default: 'Transcript language' })}
				</label>
				<input
					type="text"
					id="wizard-yt-lang"
					bind:value={inputYtLang}
					class="mt-1 block w-32 rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-[#2271b3] focus:ring-[#2271b3]"
					placeholder="en"
				/>
			</div>
			<div>
				<label for="wizard-yt-title" class="block text-sm font-medium text-gray-700">
					{$_('knowledge.wizard.libraryContent.titleOptional', { default: 'Title (optional)' })}
				</label>
				<input
					type="text"
					id="wizard-yt-title"
					bind:value={inputYtTitle}
					class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-[#2271b3] focus:ring-[#2271b3]"
				/>
			</div>
			<button
				type="button"
				onclick={addYtSource}
				class="rounded-md border border-[#2271b3] px-3 py-1.5 text-sm font-medium text-[#2271b3] hover:bg-blue-50"
			>
				{$_('knowledge.wizard.libraryContent.addYouTube', { default: '+ Add YouTube' })}
			</button>
		</div>
	{/if}

	<!-- Queued sources list -->
	{#if totalSources > 0}
		<div>
			<p class="mb-1 text-xs font-medium tracking-wide text-gray-500 uppercase">
				{$_('knowledge.wizard.libraryContent.queuedSources', { default: 'Queued sources' })}
				({totalSources})
			</p>
			<div class="divide-y rounded-md border border-gray-200">
				{#each files as f, idx (idx + '-' + f.name)}
					<div class="flex items-center gap-3 px-3 py-2">
						<span class="text-base" aria-label="File">📄</span>
						<div class="min-w-0 flex-1">
							<div class="truncate text-sm font-medium text-gray-900">{f.name}</div>
							<div class="text-xs text-gray-400">{formatSize(f.size)}</div>
						</div>
						<button
							type="button"
							onclick={() => removeFile(idx)}
							class="text-xs text-red-600 hover:underline"
							aria-label="Remove {f.name}"
						>
							&times;
						</button>
					</div>
				{/each}
				{#each urlSources as src, idx (idx + '-' + src.url)}
					<div class="flex items-center gap-3 px-3 py-2">
						<span class="text-base" aria-label={src.type}>{sourceBadge(src.type)}</span>
						<div class="min-w-0 flex-1">
							<div class="truncate text-sm font-medium text-gray-900">
								{src.title || src.url}
							</div>
							<div class="truncate text-xs text-gray-400">
								{src.url}{#if src.type === 'youtube' && src.language}
									· {src.language}{/if}
							</div>
						</div>
						<button
							type="button"
							onclick={() => removeUrlSource(idx)}
							class="text-xs text-red-600 hover:underline"
							aria-label="Remove {src.url}"
						>
							&times;
						</button>
					</div>
				{/each}
			</div>
			<p class="mt-1 text-xs text-gray-500">
				{$_('knowledge.wizard.libraryContent.uploadNote', {
					default: 'Content will be imported when you click "Create" in the Review step.'
				})}
			</p>
		</div>
	{:else}
		<p class="text-sm text-gray-500">
			{$_('knowledge.wizard.libraryContent.emptyHint', {
				default: 'No content queued. You can skip this step.'
			})}
		</p>
	{/if}
</div>
