<!--
  @component StepLibraryContent
  Optional step. Source-type tabs auto-derived from the registered import
  plugins (``GET /creator/libraries/plugins``). One tab per distinct
  ``source_type`` returned by the registry — e.g. ``file``, ``url``,
  ``youtube``, and any future ``rss``/``firecrawl``/etc. drop-in plugin
  with a fresh ``source_type``.

  Content is NOT uploaded here — it is collected in memory until Step 5
  ("Review & Create") runs the actual import.

  Tab rendering rules:
    - Tab label = i18n ``sourceType.{type}`` with fallback to the raw
      type string (so an unknown ``rss`` source-type shows up as "rss"
      until a translator adds a key).
    - When >1 plugin lives in the same source-type tab, a selector
      lists each plugin's ``human_label`` (with ``description`` as
      subtitle). When exactly 1, it is auto-picked. When 0, the tab
      is not shown.
    - ``source_type === 'file'`` renders a file picker; anything else
      renders the URL form. The URL form has a YouTube-specific
      ``language`` field surfaced for the ``youtube`` source type — for
      any other URL-style source the field is hidden (with a clean
      fall-through path for future plugins).

  Emits:
    - update: { pendingFiles, pendingUrlSources }
    - validity: { valid: boolean }   (always true — skippable)
-->
<script>
	import { createEventDispatcher, onMount } from 'svelte';
	import { _ } from '$lib/i18n';
	import { getPlugins } from '$lib/services/libraryService';
	import PluginParamFields from '$lib/components/plugins/PluginParamFields.svelte';

	/** @type {{ wizardState: any }} */
	let { wizardState } = $props();

	const dispatch = createEventDispatcher();

	// ── Files ────────────────────────────────────────────────────────────────
	let files = $state(/** @type {File[]} */ (wizardState.pendingFiles || []));
	// Parallel array — per-file plugin_params dict. Index-aligned with
	// ``files``. Each entry is the params dict the renderer fills based on
	// the matched plugin's schema. ``Step8_ReviewCreate`` forwards each
	// dict as ``params`` to ``uploadFile``.
	let fileParams = $state(
		/** @type {Record<string, unknown>[]} */ (wizardState.pendingFileParams || [])
	);

	// ── URL / YouTube sources ────────────────────────────────────────────────
	/**
	 * @typedef {{ type: string, url: string, title?: string, pluginName?: string, params?: Record<string, unknown> }} UrlSource
	 */
	let urlSources = $state(/** @type {UrlSource[]} */ (wizardState.pendingUrlSources || []));

	// ── Plugin catalogue ─────────────────────────────────────────────────────
	/**
	 * @typedef {Object} PluginMeta
	 * @property {string} name
	 * @property {string} [description]
	 * @property {string} [human_label]
	 * @property {string} [source_type]
	 * @property {string[]} [file_extensions]
	 * @property {Array<any>} [parameters]
	 * @property {string} [mode]
	 */
	let plugins = $state(/** @type {PluginMeta[]} */ ([]));
	let pluginsLoaded = $state(false);
	let pluginsError = $state('');

	onMount(async () => {
		try {
			plugins = await getPlugins();
		} catch (/** @type {unknown} */ err) {
			pluginsError = err instanceof Error ? err.message : 'Failed to load plugins';
			console.error('StepLibraryContent: failed to load plugins', err);
		} finally {
			pluginsLoaded = true;
		}
	});

	// Distinct source-types (preserves first-seen ordering — backend already
	// returns plugins in registration order which is stable). A tab is shown
	// for every distinct type that has at least one plugin.
	let sourceTypes = $derived.by(() => {
		// Plain-object keyed lookup keeps the derived value cheap and side-effect
		// free — using a Set here would trip svelte/prefer-svelte-reactivity even
		// though the instance never leaks past this block.
		const seen = /** @type {Record<string, true>} */ ({});
		const ordered = /** @type {string[]} */ ([]);
		for (const p of plugins) {
			const t = p?.source_type || 'file';
			if (!seen[t]) {
				seen[t] = true;
				ordered.push(t);
			}
		}
		return ordered;
	});

	// Currently-selected tab. Defaults to the first available source-type,
	// falling back to 'file' before the registry response lands so the
	// initial render isn't blank.
	let sourceType = $state(/** @type {string} */ ('file'));
	let userTouchedTab = $state(false);

	$effect(() => {
		if (userTouchedTab) return;
		if (sourceTypes.length === 0) return;
		if (sourceTypes.includes(sourceType)) return;
		sourceType = sourceTypes[0];
	});

	// Plugins available inside the active tab.
	let pluginsForActiveTab = $derived(
		plugins.filter((p) => (p?.source_type || 'file') === sourceType)
	);

	// Per-tab plugin selection. Keyed by source-type so switching tabs
	// preserves the user's pick. Auto-selects when there's exactly one
	// candidate.
	let selectedPluginByType = $state(/** @type {Record<string, string>} */ ({}));

	$effect(() => {
		for (const t of sourceTypes) {
			const candidates = plugins.filter((p) => (p?.source_type || 'file') === t);
			const current = selectedPluginByType[t];
			if (candidates.length === 0) {
				if (current !== undefined) {
					const next = { ...selectedPluginByType };
					delete next[t];
					selectedPluginByType = next;
				}
				continue;
			}
			if (!current || !candidates.find((p) => p.name === current)) {
				selectedPluginByType = { ...selectedPluginByType, [t]: candidates[0].name };
			}
		}
	});

	let activePluginName = $derived(selectedPluginByType[sourceType] || '');
	let activePlugin = $derived(plugins.find((p) => p.name === activePluginName));
	let activePluginParameters = $derived(activePlugin?.parameters ?? []);

	/** @param {string} type */
	function sourceTypeLabel(type) {
		// i18n key with fall-through to the raw type string — keeps brand-new
		// source-types (e.g. ``rss``) showing a sensible label without a
		// translator round-trip.
		return $_(`sourceType.${type}`, { default: type });
	}

	// Inputs for URL / YouTube
	let inputUrl = $state('');
	let inputUrlTitle = $state('');
	// Per-source params dict the renderer fills. Reset when the user adds
	// a source or switches plugin. The plugin schema is the only source of
	// keys here — no hardcoded plugin-specific fields.
	let inputParams = $state(/** @type {Record<string, unknown>} */ ({}));
	let inputParamErrors = $state(/** @type {Record<string, string>} */ ({}));
	let urlError = $state('');

	// Reset input params when the active plugin changes — different plugins
	// have different schemas, so a stale param dict would carry irrelevant
	// keys. The renderer re-initialises from the new schema's defaults on
	// next mount.
	$effect(() => {
		const _plugin = activePluginName;
		void _plugin;
		inputParams = {};
	});

	// ── Dispatch on changes ──────────────────────────────────────────────────
	$effect(() => {
		// Touch reactive props so this effect re-runs on edits.
		const _files = files;
		const _urls = urlSources;
		const _fileParams = fileParams;
		void _files;
		void _urls;
		void _fileParams;
		dispatch('validity', { valid: true });
		dispatch('update', {
			pendingFiles: files,
			pendingUrlSources: urlSources,
			pendingFileParams: fileParams
		});
	});

	// ── File handling ────────────────────────────────────────────────────────
	/** @param {Event} event */
	function handleFileChange(event) {
		const target = /** @type {HTMLInputElement} */ (event.target);
		if (!target.files) return;
		const incoming = Array.from(target.files);
		files = [...files, ...incoming];
		// One empty params dict per new file — the renderer fills in
		// defaults from the matched plugin's schema when expanded.
		fileParams = [...fileParams, ...incoming.map(() => ({}))];
		target.value = '';
	}

	/** @param {number} idx */
	function removeFile(idx) {
		files = files.filter((_, i) => i !== idx);
		fileParams = fileParams.filter((_, i) => i !== idx);
	}

	/**
	 * Best-effort plugin lookup for a given file. Used to populate the
	 * per-file param renderer with the right schema — the same matching
	 * step8 performs at upload time. When zero or many plugins match, we
	 * leave the params section closed and skip the renderer; the schema
	 * picker happens at submit.
	 * @param {File} file
	 */
	function pluginForFile(file) {
		const ext = file.name.split('.').pop()?.toLowerCase() || '';
		const matches = plugins.filter(
			(p) =>
				Array.isArray(p?.file_extensions) &&
				p.file_extensions.length > 0 &&
				p.file_extensions.includes(ext)
		);
		return matches.length === 1 ? matches[0] : null;
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

	// ── Add a non-file source ───────────────────────────────────────────────
	// Covers ``url``, ``youtube`` and any future non-file source-type a
	// drop-in plugin registers. All plugin-specific knobs (transcript
	// language for YouTube, crawl depth for URL, etc.) travel through the
	// generic ``params`` dict the renderer produces — no source-type
	// branches here.
	function addUrlSource() {
		urlError = '';
		const trimmed = inputUrl.trim();
		if (!trimmed || !isValidHttpUrl(trimmed)) {
			urlError =
				sourceType === 'youtube'
					? $_('knowledge.wizard.libraryContent.invalidYoutubeUrl', {
							default: 'A valid YouTube URL is required.'
						})
					: $_('knowledge.wizard.libraryContent.invalidUrl', {
							default: 'A valid HTTP(S) URL is required.'
						});
			return;
		}
		if (Object.keys(inputParamErrors).length > 0) {
			urlError = $_('plugins.params.fixErrors', {
				default: 'Fix the plugin parameter errors before adding the source.'
			});
			return;
		}
		/** @type {UrlSource} */
		const next = {
			type: sourceType,
			url: trimmed,
			pluginName: activePluginName || undefined,
			title: inputUrlTitle.trim() || undefined,
			params: { ...inputParams }
		};
		urlSources = [...urlSources, next];
		inputUrl = '';
		inputUrlTitle = '';
		inputParams = {};
	}

	/** @param {number} idx */
	function removeUrlSource(idx) {
		urlSources = urlSources.filter((_, i) => i !== idx);
	}

	/** @param {string} type */
	function sourceBadge(type) {
		if (type === 'youtube') return '▶';
		if (type === 'url') return '🔗';
		return '🔗';
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

	<!-- Plugin-load error (only shown once the registry call has settled) -->
	{#if pluginsLoaded && pluginsError}
		<div class="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700" role="alert">
			{pluginsError}
		</div>
	{/if}

	<!-- Source type selector (auto-derived from plugins) -->
	{#if sourceTypes.length === 0}
		{#if pluginsLoaded && !pluginsError}
			<p class="text-sm text-gray-500">
				{$_('knowledge.wizard.libraryContent.noPlugins', {
					default: 'No import plugins are currently enabled.'
				})}
			</p>
		{/if}
	{:else}
		<div class="flex flex-wrap gap-2">
			{#each sourceTypes as type (type)}
				<button
					type="button"
					class="rounded-md border px-3 py-1.5 text-sm {sourceType === type
						? 'border-[#2271b3] bg-[#2271b3] text-white'
						: 'border-gray-300 bg-white text-gray-700 hover:bg-gray-50'}"
					onclick={() => {
						sourceType = type;
						userTouchedTab = true;
						urlError = '';
					}}
				>
					{sourceTypeLabel(type)}
				</button>
			{/each}
		</div>

		<!-- Plugin selector inside the active tab. Hidden when only one
		     plugin handles this source-type (auto-picked). -->
		{#if pluginsForActiveTab.length > 1}
			<div class="rounded-md border border-gray-200 p-3">
				<label for="wizard-library-tab-plugin" class="block text-sm font-medium text-gray-700">
					{$_('knowledge.wizard.libraryContent.pluginLabel', { default: 'Import plugin' })}
				</label>
				<select
					id="wizard-library-tab-plugin"
					bind:value={selectedPluginByType[sourceType]}
					class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
				>
					{#each pluginsForActiveTab as plugin (plugin.name)}
						<option value={plugin.name}>{plugin.human_label || plugin.name}</option>
					{/each}
				</select>
				{#each pluginsForActiveTab as plugin (plugin.name)}
					{#if plugin.name === activePluginName && plugin.description}
						<p class="mt-2 text-xs text-gray-500">{plugin.description}</p>
					{/if}
				{/each}
			</div>
		{/if}
	{/if}

	<!-- File picker (only for the file source-type) -->
	{#if sourceType === 'file'}
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
	{:else if sourceTypes.includes(sourceType)}
		<!-- Generic URL-style form. Covers ``url``, ``youtube`` and any
		     future non-file source-type a drop-in plugin registers. -->
		<div class="space-y-3 rounded-md border border-gray-200 p-3">
			{#if urlError}
				<div class="rounded-md bg-red-50 p-2 text-sm text-red-700" role="alert">{urlError}</div>
			{/if}
			<div>
				<label for="wizard-source-url" class="block text-sm font-medium text-gray-700">
					{sourceType === 'youtube'
						? $_('knowledge.wizard.libraryContent.youtubeUrl', { default: 'YouTube URL' })
						: 'URL'}
					<span class="text-red-500">*</span>
				</label>
				<input
					type="url"
					id="wizard-source-url"
					bind:value={inputUrl}
					class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-[#2271b3] focus:ring-[#2271b3]"
					placeholder={sourceType === 'youtube'
						? 'https://www.youtube.com/watch?v=...'
						: 'https://example.com/document'}
				/>
			</div>
			<div>
				<label for="wizard-source-title" class="block text-sm font-medium text-gray-700">
					{$_('knowledge.wizard.libraryContent.titleOptional', { default: 'Title (optional)' })}
				</label>
				<input
					type="text"
					id="wizard-source-title"
					bind:value={inputUrlTitle}
					class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-[#2271b3] focus:ring-[#2271b3]"
				/>
			</div>
			{#if activePluginParameters.length > 0}
				<fieldset class="space-y-2 rounded-md border border-gray-200 bg-gray-50 p-3">
					<legend class="px-1 text-xs font-medium text-gray-700">
						{$_('knowledge.wizard.libraryContent.pluginParamsLabel', {
							values: { plugin: activePlugin?.human_label || activePluginName },
							default: 'Plugin parameters'
						})}
					</legend>
					<PluginParamFields
						parameters={activePluginParameters}
						bind:values={inputParams}
						bind:errors={inputParamErrors}
						idPrefix="wizard-source-param"
						mode={activePlugin?.mode === 'ADVANCED' ? 'advanced' : 'simplified'}
					/>
				</fieldset>
			{/if}
			<button
				type="button"
				onclick={addUrlSource}
				class="rounded-md border border-[#2271b3] px-3 py-1.5 text-sm font-medium text-[#2271b3] hover:bg-blue-50"
			>
				{sourceType === 'youtube'
					? $_('knowledge.wizard.libraryContent.addYouTube', { default: '+ Add YouTube' })
					: $_('knowledge.wizard.libraryContent.addUrl', { default: '+ Add URL' })}
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
					{@const matchedPlugin = pluginForFile(f)}
					<div class="px-3 py-2">
						<div class="flex items-center gap-3">
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
						{#if matchedPlugin && (matchedPlugin.parameters?.length ?? 0) > 0}
							<details class="ml-7 mt-1 text-xs">
								<summary class="cursor-pointer text-[#2271b3] hover:underline">
									{$_('knowledge.wizard.libraryContent.perFileParams', {
										default: 'Plugin parameters'
									})}
								</summary>
								<div class="mt-2 rounded-md border border-gray-200 bg-gray-50 p-2">
									<PluginParamFields
										parameters={matchedPlugin.parameters ?? []}
										bind:values={fileParams[idx]}
										idPrefix={`wizard-file-${idx}-param`}
										mode={matchedPlugin.mode === 'ADVANCED' ? 'advanced' : 'simplified'}
									/>
								</div>
							</details>
						{/if}
					</div>
				{/each}
				{#each urlSources as src, idx (idx + '-' + src.url)}
					<div class="flex items-center gap-3 px-3 py-2">
						<span class="text-base" aria-label={src.type}>{sourceBadge(src.type)}</span>
						<div class="min-w-0 flex-1">
							<div class="truncate text-sm font-medium text-gray-900">
								{src.title || src.url}
							</div>
							<div class="truncate text-xs text-gray-400">{src.url}</div>
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
