<!--
  @component StepLibraryContent
  Optional step. Source-type tabs auto-derived from the registered import
  plugins (``GET /creator/libraries/plugins``). One tab per distinct
  ``source_type`` returned by the registry — e.g. ``file``, ``url``,
  ``youtube``, and any future ``rss``/``firecrawl``/etc. drop-in plugin
  with a fresh ``source_type``.

  Content is NOT uploaded here — it is collected in memory until Step 5
  ("Review & Create") runs the actual import.

  Phase C consistency contract:
    * Emoji source badges replaced with lucide FileText / Youtube /
      Link icons.
    * File input replaced with the canonical `<Dropzone>` primitive.
    * URL / YouTube inputs are `<FormField type="url" validateOnBlur
      leadingIcon={Link|Youtube}>`.
    * Per-item remove uses `<IconButton icon={X} variant="danger-ghost">`.
    * Plugin defaults are shown inline below the "Defaults come from the
      plugin…" copy.

  Emits:
    - update: { pendingFiles, pendingUrlSources }
    - validity: { valid: boolean }   (always true — skippable)
-->
<script>
	import { createEventDispatcher, onMount } from 'svelte';
	import { _ } from '$lib/i18n';
	import { getPlugins } from '$lib/services/libraryService';
	import PluginParamFields from '$lib/components/plugins/PluginParamFields.svelte';
	import { Banner, FormField, IconButton, Dropzone, Button, Badge } from '$lib/components/ui';
	import { FileText, Youtube, Link as LinkIcon, X } from '$lib/components/ui/icons.js';

	/** @type {{ wizardState: any }} */
	let { wizardState } = $props();

	const dispatch = createEventDispatcher();

	// ── Files ────────────────────────────────────────────────────────────────
	let files = $state(/** @type {File[]} */ (wizardState.pendingFiles || []));
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

	let sourceTypes = $derived.by(() => {
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

	let sourceType = $state(/** @type {string} */ ('file'));
	let userTouchedTab = $state(false);

	$effect(() => {
		if (userTouchedTab) return;
		if (sourceTypes.length === 0) return;
		if (sourceTypes.includes(sourceType)) return;
		sourceType = sourceTypes[0];
	});

	let pluginsForActiveTab = $derived(
		plugins.filter((p) => (p?.source_type || 'file') === sourceType)
	);

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
		return $_(`sourceType.${type}`, { default: type });
	}

	let inputUrl = $state('');
	let inputUrlTitle = $state('');
	let inputParams = $state(/** @type {Record<string, unknown>} */ ({}));
	let inputParamErrors = $state(/** @type {Record<string, string>} */ ({}));
	let urlError = $state('');

	$effect(() => {
		const _plugin = activePluginName;
		void _plugin;
		inputParams = {};
	});

	$effect(() => {
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

	/** @param {File[]} merged */
	function onDropzoneFiles(merged) {
		// Dropzone already swaps in the merged list; sync the parallel
		// fileParams array so future indices line up.
		const diff = merged.length - fileParams.length;
		if (diff > 0) {
			fileParams = [...fileParams, ...Array.from({ length: diff }, () => ({}))];
		} else if (diff < 0) {
			fileParams = fileParams.slice(0, merged.length);
		}
	}

	/** @param {File} _f @param {number} idx */
	function onDropzoneRemove(_f, idx) {
		fileParams = fileParams.filter((/** @type {any} */ _, /** @type {number} */ i) => i !== idx);
	}

	/**
	 * Best-effort plugin lookup for a given file. Used to populate the
	 * per-file param renderer with the right schema.
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

	/** @param {string} value */
	function isValidHttpUrl(value) {
		try {
			const parsed = new URL(value);
			return parsed.protocol === 'http:' || parsed.protocol === 'https:';
		} catch {
			return false;
		}
	}

	/** @param {string} v */
	function validateUrl(v) {
		if (!v || !v.trim()) return undefined;
		if (!isValidHttpUrl(v.trim())) {
			return sourceType === 'youtube'
				? $_('knowledge.wizard.libraryContent.invalidYoutubeUrl', {
						default: 'A valid YouTube URL is required.'
					})
				: $_('knowledge.wizard.libraryContent.invalidUrl', {
						default: 'A valid HTTP(S) URL is required.'
					});
		}
		return undefined;
	}

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
	function sourceIcon(type) {
		switch (type) {
			case 'youtube':
				return Youtube;
			case 'url':
				return LinkIcon;
			default:
				return FileText;
		}
	}

	let totalSources = $derived(files.length + urlSources.length);

	// Plugin defaults visible inline below the "Defaults come from the
	// plugin…" copy. Reads each schema entry's `default`.
	let pluginDefaults = $derived.by(() => {
		if (!activePluginParameters || activePluginParameters.length === 0) return [];
		return activePluginParameters
			.filter((/** @type {any} */ p) => p && typeof p.name === 'string' && 'default' in p)
			.map((/** @type {any} */ p) => ({ name: p.name, value: p.default }));
	});
</script>

<div class="space-y-4">
	<h3 class="type-section-title">
		{$_('knowledge.wizard.libraryContent.heading', { default: 'Initial content' })}
	</h3>

	<Banner
		variant="info"
		description={$_('knowledge.wizard.libraryContent.optionalHint', {
			default:
				'Adding content here is optional — you can also add files, URLs, or YouTube transcripts later from the Library detail page. Note: a Knowledge Store can only ingest items that exist in its Library, so anything you skip now must be added to the Library before it can land in the Knowledge Store.'
		})}
	/>

	{#if pluginsLoaded && pluginsError}
		<Banner variant="danger" size="sm" description={pluginsError} />
	{/if}

	<!-- Source type selector (auto-derived from plugins) -->
	{#if sourceTypes.length === 0}
		{#if pluginsLoaded && !pluginsError}
			<p class="type-body-muted">
				{$_('knowledge.wizard.libraryContent.noPlugins', {
					default: 'No import plugins are currently enabled.'
				})}
			</p>
		{/if}
	{:else}
		<div class="flex flex-wrap gap-2">
			{#each sourceTypes as type (type)}
				<Button
					variant={sourceType === type ? 'primary' : 'secondary'}
					size="sm"
					onclick={() => {
						sourceType = type;
						userTouchedTab = true;
						urlError = '';
					}}
				>
					{sourceTypeLabel(type)}
				</Button>
			{/each}
		</div>

		<!-- Plugin selector inside the active tab. -->
		{#if pluginsForActiveTab.length > 1}
			<div class="border-border bg-surface rounded-md border p-3">
				<FormField
					id="wizard-library-tab-plugin"
					label={$_('knowledge.wizard.libraryContent.pluginLabel', { default: 'Import plugin' })}
					type="select"
					bind:value={selectedPluginByType[sourceType]}
					options={pluginsForActiveTab.map((/** @type {any} */ plugin) => ({
						value: plugin.name,
						label: plugin.human_label || plugin.name
					}))}
				/>
				{#each pluginsForActiveTab as plugin (plugin.name)}
					{#if plugin.name === activePluginName && plugin.description}
						<p class="type-caption mt-2">{plugin.description}</p>
					{/if}
				{/each}
			</div>
		{/if}
	{/if}

	<!-- File picker (only for the file source-type) → Dropzone primitive. -->
	{#if sourceType === 'file'}
		<Dropzone
			bind:files
			title={$_('knowledge.wizard.libraryContent.dropTitle', {
				default: 'Drop files here or click to upload'
			})}
			hint={$_('knowledge.wizard.libraryContent.dropHint', {
				default: 'You can add multiple files; they will be imported when you click Create.'
			})}
			onfiles={onDropzoneFiles}
			onremove={onDropzoneRemove}
		/>
	{:else if sourceTypes.includes(sourceType)}
		<!-- Generic URL-style form. -->
		<div class="border-border bg-surface space-y-3 rounded-md border p-3">
			{#if urlError}
				<Banner variant="danger" size="sm" description={urlError} />
			{/if}
			<FormField
				id="wizard-source-url"
				label={sourceType === 'youtube'
					? $_('knowledge.wizard.libraryContent.youtubeUrl', { default: 'YouTube URL' })
					: 'URL'}
				type="url"
				bind:value={inputUrl}
				required
				validateOnBlur={validateUrl}
				leadingIcon={sourceType === 'youtube' ? Youtube : LinkIcon}
				placeholder={sourceType === 'youtube'
					? 'https://www.youtube.com/watch?v=...'
					: 'https://example.com/document'}
			/>
			<FormField
				id="wizard-source-title"
				label={$_('knowledge.wizard.libraryContent.titleOptional', {
					default: 'Title (optional)'
				})}
				type="text"
				bind:value={inputUrlTitle}
			/>
			{#if activePluginParameters.length > 0}
				<fieldset class="border-border bg-surface-muted space-y-2 rounded-md border p-3">
					<legend class="type-label px-1">
						{$_('knowledge.wizard.libraryContent.pluginParamsLabel', {
							values: { plugin: activePlugin?.human_label || activePluginName },
							default: 'Plugin parameters'
						})}
					</legend>
					<p class="type-caption">
						{$_('knowledge.wizard.libraryContent.pluginParamsHint', {
							default:
								'Defaults come from the plugin and work for most documents — override only if needed.'
						})}
					</p>
					{#if pluginDefaults.length > 0}
						<dl class="text-text-muted grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1 text-xs">
							{#each pluginDefaults as d (d.name)}
								<dt class="font-medium">{d.name}</dt>
								<dd class="font-mono">{String(d.value)}</dd>
							{/each}
						</dl>
					{/if}
					<PluginParamFields
						parameters={activePluginParameters}
						bind:values={inputParams}
						bind:errors={inputParamErrors}
						idPrefix="wizard-source-param"
						mode={activePlugin?.mode === 'ADVANCED' ? 'advanced' : 'simplified'}
					/>
				</fieldset>
			{/if}
			<Button variant="secondary" onclick={addUrlSource}>
				{sourceType === 'youtube'
					? $_('knowledge.wizard.libraryContent.addYouTube', { default: 'Add YouTube' })
					: $_('knowledge.wizard.libraryContent.addUrl', { default: 'Add URL' })}
			</Button>
		</div>
	{/if}

	<!-- Queued sources list (URL/YouTube items; Dropzone already lists files itself). -->
	{#if urlSources.length > 0}
		<div>
			<p class="type-label mb-1">
				{$_('knowledge.wizard.libraryContent.queuedSources', { default: 'Queued sources' })}
				({urlSources.length})
			</p>
			<ul class="divide-border border-border bg-surface divide-y rounded-md border">
				{#each urlSources as src, idx (idx + '-' + src.url)}
					{@const IconCmp = sourceIcon(src.type)}
					<li class="flex items-center gap-3 px-3 py-2">
						<IconCmp size={14} class="text-text-muted shrink-0" aria-hidden="true" />
						<div class="min-w-0 flex-1">
							<div class="text-text truncate text-sm font-medium">
								{src.title || src.url}
							</div>
							<div class="type-caption truncate">{src.url}</div>
						</div>
						<Badge variant="neutral">{src.type}</Badge>
						<IconButton
							icon={X}
							ariaLabel={`Remove ${src.url}`}
							tooltip={$_('common.remove', { default: 'Remove' })}
							variant="danger-ghost"
							size="sm"
							onclick={() => removeUrlSource(idx)}
						/>
					</li>
				{/each}
			</ul>
		</div>
	{/if}

	{#if totalSources > 0}
		<p class="type-caption">
			{$_('knowledge.wizard.libraryContent.uploadNote', {
				default: 'Content will be imported when you click "Create" in the Review step.'
			})}
		</p>
	{:else if sourceType !== 'file'}
		<p class="type-body-muted">
			{$_('knowledge.wizard.libraryContent.emptyHint', {
				default: 'No content queued. You can skip this step.'
			})}
		</p>
	{/if}

	<!-- Per-file plugin params section. Dropzone owns the file list UI, but
	     we still expose the per-file Advanced parameters underneath it when
	     a file matches a plugin with a parameters schema. -->
	{#if files.length > 0}
		<details class="border-border bg-surface rounded-md border">
			<summary
				class="text-brand hover:bg-surface-sunken cursor-pointer rounded-md px-3 py-2 text-sm font-medium select-none"
			>
				{$_('knowledge.wizard.libraryContent.perFileParams', {
					default: 'Per-file plugin parameters'
				})}
			</summary>
			<div class="space-y-3 px-3 pb-3">
				{#each files as f, idx (`${f.name}-${idx}`)}
					{@const matched = pluginForFile(f)}
					{#if matched && (matched.parameters?.length ?? 0) > 0}
						<div class="border-border bg-surface-muted rounded-md border p-2">
							<p class="type-label mb-1">{f.name}</p>
							<PluginParamFields
								parameters={matched.parameters ?? []}
								bind:values={fileParams[idx]}
								idPrefix={`wizard-file-${idx}-param`}
								mode={matched.mode === 'ADVANCED' ? 'advanced' : 'simplified'}
							/>
						</div>
					{/if}
				{/each}
			</div>
		</details>
	{/if}
</div>
