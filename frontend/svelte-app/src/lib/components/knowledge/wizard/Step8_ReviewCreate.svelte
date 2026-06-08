<!--
  @component Step8_ReviewCreate
  Final review + create. This step is where ALL DB-writing actions
  happen (libraries created, files uploaded, KS created, content
  ingested). Up to this point the wizard has only collected state in
  memory — keeping it fully reversible.

  Flow when "Create" is clicked:
    1. If libraryPath === 'new': createLibrary({ name, description }).
       Optionally toggle sharing.
    2. For each File in pendingFiles: uploadFile(libraryId, file).
       Poll each item via getItemStatus until 'ready' or 'failed'.
    3. If ksPath === 'new': createKnowledgeStore({ ...ksConfig, name, description }).
       Optionally toggle sharing.
    4. Build the final list of item IDs to ingest.
    5. addContent(ksId, { libraryId, itemIds }) — fire and forget.
    6. Emit 'created' with { libraryId, libraryName, ksId, ksName }.

  Phase C consistency contract:
    * Card titles use `type-label` (instead of `text-gray-400 uppercase`).
    * Each summary section wraps in `<Card>` with a `<IconButton
      icon={Pencil}>` jump-back affordance in the header.
    * Progress icons use canonical Loader2 / CheckCircle2 / AlertCircle.

  Emits:
    - update: ()
    - validity: { valid: boolean }     (always true, disabled while submitting)
    - created: { libraryId, libraryName, ksId, ksName }
-->
<script>
	import { createEventDispatcher, onMount, tick } from 'svelte';
	import axios from 'axios';
	import {
		createLibrary,
		getLibraries,
		toggleSharing as toggleLibrarySharing,
		uploadFile,
		importUrl,
		importYouTube,
		getItemStatus,
		getPlugins
	} from '$lib/services/libraryService';
	import { matchPluginsForFile } from '$lib/services/pluginMatcher';
	import {
		createKnowledgeStore,
		getKnowledgeStores,
		toggleSharing as toggleKSSharing,
		addContent
	} from '$lib/services/knowledgeStoreService';
	import PluginPickerModal from '$lib/components/libraries/PluginPickerModal.svelte';
	import { _ } from '$lib/i18n';
	import { Card, Banner, IconButton } from '$lib/components/ui';
	import { Pencil, Loader2, CheckCircle2, AlertCircle } from 'lucide-svelte';

	/** @type {any[]} */
	let plugins = $state([]);

	onMount(async () => {
		try {
			plugins = await getPlugins();
		} catch (err) {
			console.warn('Step8_ReviewCreate: failed to load plugins', err);
		}
	});

	/**
	 * Pick the first plugin registered for a source type.
	 * @param {string} sourceType
	 * @returns {string|null}
	 */
	function pluginForSourceType(sourceType) {
		const match = plugins.find(
			(p) =>
				Array.isArray(p?.supported_source_types) && p.supported_source_types.includes(sourceType)
		);
		return match?.name ?? null;
	}

	// Picker modal state for the multi-match tie-break.
	let showPluginPicker = $state(false);
	/** @type {any[]} */
	let pluginMatches = $state([]);
	/** @type {File|null} */
	let pickerFile = $state(null);
	/** @type {((pluginName: string|null) => void) | null} */
	let pickerResolver = null;

	/**
	 * @param {File} file
	 * @returns {Promise<string|null>}
	 */
	async function resolvePluginForFile(file) {
		const matches = matchPluginsForFile(file, plugins);
		if (matches.length === 0) return null;
		if (matches.length === 1) return matches[0].name;
		pluginMatches = matches;
		pickerFile = file;
		showPluginPicker = true;
		await tick();
		return new Promise((resolve) => {
			pickerResolver = resolve;
		});
	}

	/** @param {{ name: string }} plugin */
	function handlePluginPicked(plugin) {
		showPluginPicker = false;
		const resolver = pickerResolver;
		pickerResolver = null;
		if (resolver) resolver(plugin.name);
	}

	function handlePluginPickerCancel() {
		showPluginPicker = false;
		const resolver = pickerResolver;
		pickerResolver = null;
		if (resolver) resolver(null);
	}

	/**
	 * @param {unknown} err
	 * @param {string} fallback
	 * @returns {string}
	 */
	function readableError(err, fallback) {
		if (axios.isAxiosError(err) && err.response) {
			const data = err.response.data;
			const detail =
				typeof data?.detail === 'string'
					? data.detail
					: typeof data?.message === 'string'
						? data.message
						: '';
			if (detail) return detail;
			return `Request failed (${err.response.status})`;
		}
		if (err instanceof Error && err.message) return err.message;
		return fallback;
	}

	/** @type {{ wizardState: any, submitting?: boolean, onJumpToStep?: (stepIndex: number) => void }} */
	let { wizardState, submitting = $bindable(false), onJumpToStep } = $props();

	const dispatch = createEventDispatcher();

	export function submit() {
		return handleCreate();
	}

	let error = $state('');

	/**
	 * @typedef {{ label: string; status: 'pending' | 'running' | 'done' | 'failed' }} ProgressStep
	 */
	/** @type {ProgressStep[]} */
	let progressSteps = $state([]);

	$effect(() => {
		dispatch('validity', { valid: !submitting });
	});

	/**
	 * Poll an item's status with simple backoff until it's ready or failed.
	 * @param {string} libraryId
	 * @param {string} itemId
	 * @param {number} [maxWaitMs]
	 * @returns {Promise<string>}
	 */
	async function pollItem(libraryId, itemId, maxWaitMs = 120_000) {
		const deadline = Date.now() + maxWaitMs;
		let delay = 1000;
		while (Date.now() < deadline) {
			try {
				const s = await getItemStatus(libraryId, itemId);
				if (s.status === 'ready' || s.status === 'failed') {
					return s.status;
				}
			} catch (err) {
				console.error('Status poll error', err);
			}
			await new Promise((r) => setTimeout(r, delay));
			delay = Math.min(delay * 2, 8000);
		}
		return 'timeout';
	}

	/** @param {string} label */
	function pushStep(label) {
		progressSteps = [...progressSteps, { label, status: 'running' }];
	}

	/** @param {'done'|'failed'} status */
	function finishStep(status) {
		progressSteps = progressSteps.map((s, i) =>
			i === progressSteps.length - 1 ? { ...s, status } : s
		);
	}

	async function handleCreate() {
		submitting = true;
		error = '';
		progressSteps = [];

		let libraryId = wizardState.existingLibraryId;
		let libraryName = wizardState.libraryName;
		let ksId = wizardState.existingKsId;
		let ksName = wizardState.ksName;

		// Pre-flight name-conflict check.
		try {
			/** @type {string[]} */
			const conflicts = [];
			const proposedLibName = (wizardState.libraryName || '').trim().toLowerCase();
			const proposedKsName = (wizardState.ksName || '').trim().toLowerCase();
			/** @type {Promise<void>[]} */
			const checks = [];
			if (wizardState.libraryPath === 'new' && proposedLibName) {
				checks.push(
					getLibraries()
						.then((libs) => {
							const taken = (libs || []).some(
								(l) => (l?.name || '').trim().toLowerCase() === proposedLibName
							);
							if (taken) {
								conflicts.push(
									$_('knowledge.wizard.step8.libraryNameTaken', {
										default: 'A library named "{name}" already exists.',
										values: { name: wizardState.libraryName.trim() }
									})
								);
							}
						})
						.catch(() => {})
				);
			}
			if (wizardState.ksPath === 'new' && proposedKsName) {
				checks.push(
					getKnowledgeStores()
						.then((stores) => {
							const taken = (stores || []).some(
								(s) => (s?.name || '').trim().toLowerCase() === proposedKsName
							);
							if (taken) {
								conflicts.push(
									$_('knowledge.wizard.step8.ksNameTaken', {
										default: 'A Knowledge Store named "{name}" already exists.',
										values: { name: wizardState.ksName.trim() }
									})
								);
							}
						})
						.catch(() => {})
				);
			}
			await Promise.all(checks);
			if (conflicts.length > 0) {
				error = conflicts.join(' ');
				submitting = false;
				return;
			}
		} catch {
			// Pre-flight is best-effort; fall through to the real create path.
		}

		try {
			// 1. Create library if new.
			if (wizardState.libraryPath === 'new') {
				pushStep(
					$_('knowledge.wizard.step8.progressLibrary', {
						default: 'Creating library...'
					})
				);
				const lib = await createLibrary({
					name: wizardState.libraryName,
					description: wizardState.libraryDescription || ''
				});
				libraryId = lib.id;
				libraryName = lib.name;
				finishStep('done');

				if (wizardState.libraryIsShared) {
					try {
						await toggleLibrarySharing(libraryId, true);
					} catch (e) {
						console.error('toggleLibrarySharing failed', e);
					}
				}
			}

			// 2. Upload pending files.
			/** @type {string[]} */
			const newlyReadyIds = [];
			const pending = wizardState.pendingFiles ?? [];
			if (pending.length > 0 && libraryId) {
				for (let i = 0; i < pending.length; i += 1) {
					const f = pending[i];
					pushStep(
						$_('knowledge.wizard.step8.progressUpload', {
							default: 'Uploading {name} ({n}/{total})...',
							values: { name: f.name, n: i + 1, total: pending.length }
						})
					);
					try {
						const pluginName = await resolvePluginForFile(f);
						if (!pluginName) {
							const ext = f.name.split('.').pop()?.toLowerCase() || '';
							console.warn(`No plugin can handle .${ext} for ${f.name}`);
							finishStep('failed');
							continue;
						}
						const fileParams = (wizardState.pendingFileParams ?? [])[i] ?? {};
						const result = await uploadFile(libraryId, f, {
							pluginName,
							params: fileParams
						});
						const itemId = result.item_id;
						finishStep('done');
						pushStep(
							$_('knowledge.wizard.step8.progressIngestStatus', {
								default: 'Waiting for {name} to finish importing...',
								values: { name: f.name }
							})
						);
						const finalStatus = await pollItem(libraryId, itemId);
						finishStep(finalStatus === 'ready' ? 'done' : 'failed');
						if (finalStatus === 'ready') {
							newlyReadyIds.push(itemId);
						}
					} catch (e) {
						console.error(`Upload failed for ${f.name}`, e);
						finishStep('failed');
					}
				}
			}

			// 2b. Import pending URL / YouTube sources.
			const pendingUrlSources = wizardState.pendingUrlSources ?? [];
			if (pendingUrlSources.length > 0 && libraryId) {
				for (let i = 0; i < pendingUrlSources.length; i += 1) {
					const src = pendingUrlSources[i];
					pushStep(
						$_('knowledge.wizard.step8.progressImportUrl', {
							default: 'Importing {url} ({n}/{total})...',
							values: { url: src.title || src.url, n: i + 1, total: pendingUrlSources.length }
						})
					);
					try {
						let result;
						const srcParams = src.params || {};
						if (src.type === 'youtube') {
							const ytPlugin = pluginForSourceType('youtube');
							if (!ytPlugin) {
								console.warn('No YouTube plugin enabled');
								finishStep('failed');
								continue;
							}
							result = await importYouTube(libraryId, {
								videoUrl: src.url,
								pluginName: ytPlugin,
								title: src.title || undefined,
								params: srcParams
							});
						} else {
							const urlPlugin = pluginForSourceType('url');
							if (!urlPlugin) {
								console.warn('No URL plugin enabled');
								finishStep('failed');
								continue;
							}
							result = await importUrl(libraryId, {
								url: src.url,
								pluginName: urlPlugin,
								title: src.title || undefined,
								params: srcParams
							});
						}
						const itemId = result.item_id;
						finishStep('done');
						pushStep(
							$_('knowledge.wizard.step8.progressIngestStatus', {
								default: 'Waiting for {name} to finish importing...',
								values: { name: src.title || src.url }
							})
						);
						const finalStatus = await pollItem(libraryId, itemId);
						finishStep(finalStatus === 'ready' ? 'done' : 'failed');
						if (finalStatus === 'ready') {
							newlyReadyIds.push(itemId);
						}
					} catch (e) {
						console.error(`URL import failed for ${src.url}`, e);
						finishStep('failed');
					}
				}
			}

			// 3. Create KS if new.
			if (wizardState.ksPath === 'new') {
				pushStep(
					$_('knowledge.wizard.step8.progressKS', {
						default: 'Creating Knowledge Store...'
					})
				);
				const ks = await createKnowledgeStore({
					name: wizardState.ksName,
					description: wizardState.ksDescription || '',
					chunking_strategy: wizardState.ksConfig.chunking_strategy,
					chunking_params: wizardState.ksConfig.chunking_params || {},
					embedding_vendor: wizardState.ksConfig.embedding_vendor,
					embedding_model: wizardState.ksConfig.embedding_model,
					embedding_endpoint: wizardState.ksConfig.embedding_endpoint || undefined,
					embedding_params: wizardState.ksConfig.embedding_params || {},
					vector_db_backend: wizardState.ksConfig.vector_db_backend,
					vector_db_params: wizardState.ksConfig.vector_db_params || {}
				});
				ksId = ks.id;
				ksName = ks.name;
				finishStep('done');

				if (wizardState.ksIsShared) {
					try {
						await toggleKSSharing(ksId, true);
					} catch (e) {
						console.error('toggleKSSharing failed', e);
					}
				}
			}

			// 4. Compute final list of item IDs to ingest.
			/** @type {string[]} */
			let itemsToIngest = [];
			{
				const selectedIds = wizardState.selectedItemIds || [];
				const pendingFiles = wizardState.pendingFiles ?? [];
				for (const selId of selectedIds) {
					const fileMatch = selId.match(/^pendingFile_(\d+)$/);
					const urlMatch = selId.match(/^pendingUrl_(\d+)$/);
					if (fileMatch) {
						const idx = parseInt(fileMatch[1], 10);
						if (idx < pendingFiles.length && idx < newlyReadyIds.length) {
							itemsToIngest.push(newlyReadyIds[idx]);
						}
					} else if (urlMatch) {
						const idx = parseInt(urlMatch[1], 10);
						const urlOffset = pendingFiles.length;
						if (urlOffset + idx < newlyReadyIds.length) {
							itemsToIngest.push(newlyReadyIds[urlOffset + idx]);
						}
					} else {
						itemsToIngest.push(selId);
					}
				}
			}

			// 5. Ingest content into KS.
			if (libraryId && ksId && itemsToIngest.length > 0) {
				pushStep(
					$_('knowledge.wizard.step8.progressIngest', {
						default: 'Queuing {n} item(s) for ingestion...',
						values: { n: itemsToIngest.length }
					})
				);
				try {
					await addContent(ksId, { libraryId, itemIds: itemsToIngest });
					finishStep('done');
				} catch (e) {
					console.error('addContent failed', e);
					finishStep('failed');
				}
			}

			// 6. Done.
			dispatch('created', { libraryId, libraryName, ksId, ksName });
		} catch (/** @type {unknown} */ err) {
			error = readableError(err, 'Failed to create');
			const isNoResponseAxios =
				!!err &&
				typeof err === 'object' &&
				/** @type {any} */ (err).isAxiosError === true &&
				!(/** @type {any} */ (err).response);
			if (isNoResponseAxios && wizardState.ksPath === 'new' && wizardState.ksName) {
				try {
					const stores = await getKnowledgeStores();
					const proposed = wizardState.ksName.trim().toLowerCase();
					const dup = (stores || []).some((s) => (s?.name || '').trim().toLowerCase() === proposed);
					if (dup) {
						error = $_('knowledge.wizard.step8.ksNameTaken', {
							default: 'A Knowledge Store named "{name}" already exists.',
							values: { name: wizardState.ksName.trim() }
						});
					}
				} catch (e) {
					console.warn('Duplicate-name fallback check failed', e);
				}
			}
			if (
				progressSteps.length > 0 &&
				progressSteps[progressSteps.length - 1].status === 'running'
			) {
				finishStep('failed');
			}
		} finally {
			submitting = false;
		}
	}

	/** Total items that will exist in the library after upload (for display). */
	let summaryTotalCount = $derived.by(() => {
		if (wizardState.libraryPath === 'new') {
			return (wizardState.pendingFiles ?? []).length + (wizardState.pendingUrlSources ?? []).length;
		}
		return (wizardState.selectedItemIds ?? []).length;
	});

	/** Number of items the user has chosen to ingest (may be a subset). */
	let summarySelectedCount = $derived.by(() => {
		if (wizardState.libraryPath === 'new') {
			const selectedIds = wizardState.selectedItemIds ?? [];
			return selectedIds.length;
		}
		return (wizardState.selectedItemIds ?? []).length;
	});

	// Wizard step indices kept in sync with CreateKnowledgeWizard.
	const STEP_LIBRARY_SETUP = 1;
	const STEP_LIBRARY_CONTENT = 2;
	const STEP_KS_SETUP = 3;
	const STEP_KS_CONTENT = 4;

	/** @param {number} stepIndex */
	function jumpTo(stepIndex) {
		if (typeof onJumpToStep === 'function') onJumpToStep(stepIndex);
	}
</script>

<div class="space-y-5">
	<div>
		<h3 class="type-section-title">
			{$_('knowledge.wizard.step8.heading', { default: 'Review & create' })}
		</h3>
		<p class="type-body-muted mt-1">
			{$_('knowledge.wizard.step8.description', {
				default:
					'Double-check the summary below. Nothing has been created yet — clicking "Create" will create the resources and queue the ingestion.'
			})}
		</p>
	</div>

	{#if error}
		<Banner variant="danger" description={error}>
			{#snippet actions()}
				<button
					type="button"
					onclick={handleCreate}
					class="text-danger text-sm font-medium underline hover:no-underline"
				>
					{$_('knowledge.wizard.step8.retry', { default: 'Retry' })}
				</button>
			{/snippet}
		</Banner>
	{/if}

	<!-- Library summary -->
	<Card title={$_('knowledge.wizard.step8.libraryHeading', { default: 'Library' })}>
		{#snippet actions()}
			<IconButton
				icon={Pencil}
				ariaLabel={$_('knowledge.wizard.editStep', { default: 'Edit this step' })}
				tooltip={$_('knowledge.wizard.editStep', { default: 'Edit this step' })}
				variant="ghost"
				size="sm"
				onclick={() => jumpTo(STEP_LIBRARY_SETUP)}
			/>
		{/snippet}

		<dl class="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-2 text-sm">
			<dt class="type-label">
				{$_('knowledge.wizard.libraryStep.selectLabel', { default: 'Library' })}
			</dt>
			<dd class="text-text">{wizardState.libraryName || '-'}</dd>

			<dt class="type-label">
				{$_('knowledge.wizard.ksStep.legend', { default: 'Path' })}
			</dt>
			<dd class="text-text">
				{wizardState.libraryPath === 'existing'
					? $_('knowledge.wizard.useExisting', { default: 'Use existing' })
					: $_('knowledge.wizard.createNew', { default: 'Create new' })}
			</dd>

			{#if wizardState.libraryDescription}
				<dt class="type-label">
					{$_('knowledge.wizard.libraryStep.descriptionLabel', { default: 'Description' })}
				</dt>
				<dd class="text-text">{wizardState.libraryDescription}</dd>
			{/if}

			{#if wizardState.libraryPath === 'new'}
				<dt class="type-label">
					{$_('knowledge.wizard.libraryStep.pluginLabel', { default: 'Import plugin' })}
				</dt>
				<dd class="text-text">
					{wizardState.libraryImportConfig?.pluginName ||
						$_('knowledge.wizard.step8.pluginAuto', { default: 'Auto-selected' })}
				</dd>

				<dt class="type-label">
					{$_('knowledge.wizard.libraryContent.queuedLabel', { default: 'Queued sources' })}
				</dt>
				<dd class="text-text">
					{$_('knowledge.wizard.step8.libraryFileCount', {
						default: '{n} file(s) to upload',
						values: { n: (wizardState.pendingFiles ?? []).length }
					})}
					{#if (wizardState.pendingUrlSources ?? []).length > 0}
						+
						{$_('knowledge.wizard.step8.libraryUrlCount', {
							default: '{n} URL/YouTube source(s) to import',
							values: { n: (wizardState.pendingUrlSources ?? []).length }
						})}
					{/if}
				</dd>
			{/if}
		</dl>
	</Card>

	<!-- Knowledge Store summary -->
	<Card title={$_('knowledge.wizard.step8.ksHeading', { default: 'Knowledge Store' })}>
		{#snippet actions()}
			<IconButton
				icon={Pencil}
				ariaLabel={$_('knowledge.wizard.editStep', { default: 'Edit this step' })}
				tooltip={$_('knowledge.wizard.editStep', { default: 'Edit this step' })}
				variant="ghost"
				size="sm"
				onclick={() => jumpTo(STEP_KS_SETUP)}
			/>
		{/snippet}

		<dl class="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-2 text-sm">
			<dt class="type-label">
				{$_('knowledge.wizard.ksStep.selectLabel', { default: 'Knowledge Store' })}
			</dt>
			<dd class="text-text">{wizardState.ksName || '-'}</dd>

			<dt class="type-label">
				{$_('knowledge.wizard.ksStep.legend', { default: 'Path' })}
			</dt>
			<dd class="text-text">
				{wizardState.ksPath === 'existing'
					? $_('knowledge.wizard.useExisting', { default: 'Use existing' })
					: $_('knowledge.wizard.createNew', { default: 'Create new' })}
			</dd>

			<dt class="type-label">
				{$_('knowledge.wizard.step8.itemsToIngest', { default: 'Items to ingest' })}
			</dt>
			<dd class="text-text">{summarySelectedCount} of {summaryTotalCount}</dd>

			{#if wizardState.ksPath === 'new'}
				<dt class="type-label">
					{$_('knowledge.wizard.step6.chunkingLabel', { default: 'Chunking strategy' })}
				</dt>
				<dd class="text-text">{wizardState.ksConfig?.chunking_strategy || '-'}</dd>

				<dt class="type-label">
					{$_('knowledge.wizard.step6.vendorLabel', { default: 'Embedding vendor' })}
				</dt>
				<dd class="text-text">{wizardState.ksConfig?.embedding_vendor || '-'}</dd>

				<dt class="type-label">
					{$_('knowledge.wizard.step6.modelLabel', { default: 'Embedding model' })}
				</dt>
				<dd class="text-text">{wizardState.ksConfig?.embedding_model || '-'}</dd>

				<dt class="type-label">
					{$_('knowledge.wizard.step6.vectorDbLabel', { default: 'Vector DB' })}
				</dt>
				<dd class="text-text">{wizardState.ksConfig?.vector_db_backend || '-'}</dd>
			{/if}
		</dl>
	</Card>

	<!-- Content / ingestion section: only show when the user queued items
	     so we don't surface a stub card when there's nothing to summarise. -->
	{#if (wizardState.pendingFiles ?? []).length > 0 || (wizardState.pendingUrlSources ?? []).length > 0 || (wizardState.selectedItemIds ?? []).length > 0}
		<Card title={$_('knowledge.wizard.libraryContent.title', { default: 'Library Content' })}>
			{#snippet actions()}
				<IconButton
					icon={Pencil}
					ariaLabel={$_('knowledge.wizard.editStep', { default: 'Edit this step' })}
					tooltip={$_('knowledge.wizard.editStep', { default: 'Edit this step' })}
					variant="ghost"
					size="sm"
					onclick={() =>
						jumpTo(
							(wizardState.pendingFiles ?? []).length > 0 ||
								(wizardState.pendingUrlSources ?? []).length > 0
								? STEP_LIBRARY_CONTENT
								: STEP_KS_CONTENT
						)}
				/>
			{/snippet}
			<dl class="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-2 text-sm">
				<dt class="type-label">
					{$_('knowledge.wizard.libraryContent.queuedSources', { default: 'Queued sources' })}
				</dt>
				<dd class="text-text">
					{(wizardState.pendingFiles ?? []).length + (wizardState.pendingUrlSources ?? []).length}
				</dd>
				<dt class="type-label">
					{$_('knowledge.wizard.step8.itemsToIngest', { default: 'Items to ingest' })}
				</dt>
				<dd class="text-text">{summarySelectedCount}</dd>
			</dl>
		</Card>
	{/if}

	<!-- Progress steps during creation -->
	{#if submitting && progressSteps.length > 0}
		<div
			class="border-info-border bg-info-subtle text-info-text rounded-lg border px-4 py-3"
			aria-live="polite"
			aria-label="Creation progress"
		>
			<ul class="space-y-2">
				{#each progressSteps as step (step.label + step.status)}
					<li class="flex items-center gap-2 pl-1 text-sm">
						{#if step.status === 'running'}
							<Loader2 size={14} class="text-info shrink-0 animate-spin" aria-hidden="true" />
						{:else if step.status === 'done'}
							<CheckCircle2 size={14} class="text-success shrink-0" aria-hidden="true" />
						{:else}
							<AlertCircle size={14} class="text-danger shrink-0" aria-hidden="true" />
						{/if}
						<span class={step.status === 'failed' ? 'text-danger-text line-through' : ''}>
							{step.label}
						</span>
					</li>
				{/each}
			</ul>
		</div>
	{/if}
</div>

<PluginPickerModal
	bind:isOpen={showPluginPicker}
	matches={pluginMatches}
	file={pickerFile?.name ?? ''}
	onselect={handlePluginPicked}
	oncancel={handlePluginPickerCancel}
/>
