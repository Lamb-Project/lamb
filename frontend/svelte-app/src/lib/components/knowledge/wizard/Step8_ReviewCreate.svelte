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
    4. Build the final list of item IDs to ingest:
         - existing-library: use the user's selectedItemIds.
         - new-library: use the IDs of items that became 'ready' in step 2.
    5. addContent(ksId, { libraryId, itemIds }) — fire and forget; the
       KB Server runs the ingestion job asynchronously.
    6. Emit 'created' with { libraryId, libraryName, ksId, ksName }.

  Emits:
    - update: ()
    - validity: { valid: boolean }     (always true, but disabled while submitting)
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

	// Plugin catalogue fetched once on mount. The wizard uses it to:
	//   * route file uploads (multi-match files → picker modal)
	//   * resolve which plugin handles ``url`` / ``youtube`` source types,
	//     so libraryService gets an explicit plugin name (no hardcoded
	//     defaults on either side any more).
	// Typed loosely to match the matcher's PluginMeta-style consumption.
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
	 * Pick the first plugin registered for a source type. Used to route
	 * URL and YouTube imports without hardcoding plugin names.
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
	 * Resolve a plugin name for a file. If exactly one plugin matches the
	 * extension, return it directly. If more than one matches, open the
	 * picker modal and return a Promise that resolves once the user picks.
	 * If no plugin matches, return ``null``.
	 *
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
	 * Extract a user-readable message from a thrown error. Axios surfaces
	 * the status-code generic message ("Request failed with status code 409")
	 * on `err.message`, which is useless to users — the actionable text is in
	 * `err.response.data.detail` (FastAPI's HTTPException payload). Fall
	 * through to `data.message`, then to a tagged status code, then the
	 * caller's fallback.
	 *
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

	/** @type {{ wizardState: any, submitting?: boolean }} */
	let { wizardState, submitting = $bindable(false) } = $props();

	const dispatch = createEventDispatcher();

	// Exposed to the wizard shell so the footer can host the Create button.
	// Wizard binds this component via bind:this and calls submit() from its
	// footer Create button so the button visually aligns with Back/Skip.
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
	 * @returns {Promise<string>}  Final status.
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

		// Pre-flight name-conflict check: aggregate every duplicate-name
		// problem before doing any actual creation, so the user sees ALL
		// conflicts at once instead of being shown library errors first
		// and KS errors only after fixing the library name.
		try {
			const conflicts = [];
			const proposedLibName = (wizardState.libraryName || '').trim().toLowerCase();
			const proposedKsName = (wizardState.ksName || '').trim().toLowerCase();
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
						.catch(() => {
							// If the lookup fails, fall through; the create call
							// itself will still surface a 409 if there's a real conflict.
						})
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

			// 2. Upload pending files queued in Step 2. Runs for BOTH new
			// and existing libraries — when adding content to an existing
			// library/KS, the user may queue new files in Step 2 and we
			// need to upload them here before the Pick-Items mapping can
			// link them.
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
						// Per-file params dict captured in Step 2. Empty when the
						// user didn't open the per-file Advanced panel — the
						// backend then applies each schema parameter's default.
						const fileParams =
							(wizardState.pendingFileParams ?? [])[i] ?? {};
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

			// 2b. Import pending URL / YouTube sources. Same rationale as
			// the file-upload block above — runs regardless of library path.
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
						// Plugin params captured in Step 2 (per-source). All
						// plugin-specific knobs (YouTube language, URL crawl
						// depth, future plugin fields) travel through this
						// dict — the renderer is the only thing that writes it.
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

			// 4. Compute final list of item IDs to ingest. An empty selection
			// is now meaningful — it's the explicit "Skip" outcome from
			// Step 4 and means "create the KS but ingest nothing right now".
			// We do NOT silently fall back to "everything" on empty.
			//
			// Selected IDs may be a mix of:
			//   - Real DB item IDs (existing library items the user picked)
			//   - Transient ``pendingFile_<i>`` / ``pendingUrl_<i>`` ids from
			//     items the user queued in Step 2 (need to be mapped back to
			//     the freshly-uploaded item ids in ``newlyReadyIds``).
			// This unified mapping works for both new and existing library
			// flows now that Step 2 is shown for both.
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
						// Real item ID (existing-library pick or resumed draft).
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
					// Don't fail the whole wizard — KS and library exist.
				}
			}

			// 6. Done.
			dispatch('created', { libraryId, libraryName, ksId, ksName });
		} catch (/** @type {unknown} */ err) {
			error = readableError(err, 'Failed to create');
			// Replace a bare "Network Error" with the duplicate-name message
			// when that's the real cause (the pre-flight check may have
			// silently failed too).
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
		// For existing library, total = same as selected (we don't know the full count here).
		return (wizardState.selectedItemIds ?? []).length;
	});

	/** Number of items the user has chosen to ingest (may be a subset). */
	let summarySelectedCount = $derived.by(() => {
		if (wizardState.libraryPath === 'new') {
			const selectedIds = wizardState.selectedItemIds ?? [];
			// An empty selection is the explicit Skip outcome — count is 0,
			// not "default to total". The wizard never advances past Step 4
			// without either a populated selection (Next) or a deliberate
			// clear (Skip), so empty here always means "ingest nothing".
			return selectedIds.length;
		}
		return (wizardState.selectedItemIds ?? []).length;
	});
</script>

<div class="space-y-5">
	<div>
		<h3 class="text-base font-semibold text-gray-900">
			{$_('knowledge.wizard.step8.heading', { default: 'Review & create' })}
		</h3>
		<p class="mt-1 text-sm text-gray-500">
			{$_('knowledge.wizard.step8.description', {
				default:
					'Double-check the summary below. Nothing has been created yet — clicking "Create" will create the resources and queue the ingestion.'
			})}
		</p>
	</div>

	{#if error}
		<div
			class="flex items-start gap-3 rounded-md border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800"
			role="alert"
		>
			<svg
				class="mt-0.5 h-4 w-4 shrink-0 text-red-500"
				viewBox="0 0 20 20"
				fill="currentColor"
				aria-hidden="true"
			>
				<path
					fill-rule="evenodd"
					d="M10 18a8 8 0 100-16 8 8 0 000 16zm-.75-4.75a.75.75 0 001.5 0v-4.5a.75.75 0 00-1.5 0v4.5zm.75-7a.75.75 0 100 1.5.75.75 0 000-1.5z"
					clip-rule="evenodd"
				/>
			</svg>
			<div class="min-w-0 flex-1">
				<p class="font-medium">{error}</p>
				<button
					type="button"
					onclick={handleCreate}
					class="mt-1 font-medium underline hover:no-underline"
				>
					{$_('knowledge.wizard.step8.retry', { default: 'Retry' })}
				</button>
			</div>
		</div>
	{/if}

	<!-- Summary cards -->
	<div class="space-y-3">
		<!-- Library card -->
		<div class="rounded-lg border border-gray-200 bg-white p-4">
			<p class="mb-3 text-xs font-semibold tracking-wide text-gray-400 uppercase">
				{$_('knowledge.wizard.step8.libraryHeading', { default: 'Library' })}
			</p>
			<dl class="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-2 text-sm">
				<dt class="font-medium text-gray-500">
					{$_('knowledge.wizard.libraryStep.selectLabel', { default: 'Library' })}
				</dt>
				<dd class="text-gray-900">{wizardState.libraryName || '-'}</dd>

				<dt class="font-medium text-gray-500">
					{$_('knowledge.wizard.ksStep.legend', { default: 'Path' })}
				</dt>
				<dd class="text-gray-900">
					{wizardState.libraryPath === 'existing'
						? $_('knowledge.wizard.useExisting', { default: 'Use existing' })
						: $_('knowledge.wizard.createNew', { default: 'Create new' })}
				</dd>

				{#if wizardState.libraryDescription}
					<dt class="font-medium text-gray-500">
						{$_('knowledge.wizard.libraryStep.descriptionLabel', { default: 'Description' })}
					</dt>
					<dd class="text-gray-900">{wizardState.libraryDescription}</dd>
				{/if}

				{#if wizardState.libraryPath === 'new'}
					<dt class="font-medium text-gray-500">
						{$_('knowledge.wizard.libraryStep.pluginLabel', { default: 'Import plugin' })}
					</dt>
					<dd class="text-gray-900">
						{wizardState.libraryImportConfig?.pluginName ||
							$_('knowledge.wizard.step8.pluginAuto', { default: 'Auto-selected' })}
					</dd>

					<dt class="font-medium text-gray-500">
						{$_('knowledge.wizard.libraryContent.queuedLabel', { default: 'Queued sources' })}
					</dt>
					<dd class="text-gray-900">
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
		</div>

		<!-- Knowledge Store card -->
		<div class="rounded-lg border border-gray-200 bg-white p-4">
			<p class="mb-3 text-xs font-semibold tracking-wide text-gray-400 uppercase">
				{$_('knowledge.wizard.step8.ksHeading', { default: 'Knowledge Store' })}
			</p>
			<dl class="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-2 text-sm">
				<dt class="font-medium text-gray-500">
					{$_('knowledge.wizard.ksStep.selectLabel', { default: 'Knowledge Store' })}
				</dt>
				<dd class="text-gray-900">{wizardState.ksName || '-'}</dd>

				<dt class="font-medium text-gray-500">
					{$_('knowledge.wizard.ksStep.legend', { default: 'Path' })}
				</dt>
				<dd class="text-gray-900">
					{wizardState.ksPath === 'existing'
						? $_('knowledge.wizard.useExisting', { default: 'Use existing' })
						: $_('knowledge.wizard.createNew', { default: 'Create new' })}
				</dd>

				<dt class="font-medium text-gray-500">
					{$_('knowledge.wizard.step8.itemsToIngest', { default: 'Items to ingest' })}
				</dt>
				<dd class="text-gray-900">{summarySelectedCount} of {summaryTotalCount}</dd>

				{#if wizardState.ksPath === 'new'}
					<dt class="font-medium text-gray-500">
						{$_('knowledge.wizard.step6.chunkingLabel', { default: 'Chunking strategy' })}
					</dt>
					<dd class="text-gray-900">{wizardState.ksConfig?.chunking_strategy || '-'}</dd>

					<dt class="font-medium text-gray-500">
						{$_('knowledge.wizard.step6.vendorLabel', { default: 'Embedding vendor' })}
					</dt>
					<dd class="text-gray-900">{wizardState.ksConfig?.embedding_vendor || '-'}</dd>

					<dt class="font-medium text-gray-500">
						{$_('knowledge.wizard.step6.modelLabel', { default: 'Embedding model' })}
					</dt>
					<dd class="text-gray-900">{wizardState.ksConfig?.embedding_model || '-'}</dd>

					<dt class="font-medium text-gray-500">
						{$_('knowledge.wizard.step6.vectorDbLabel', { default: 'Vector DB' })}
					</dt>
					<dd class="text-gray-900">{wizardState.ksConfig?.vector_db_backend || '-'}</dd>
				{/if}
			</dl>
		</div>

		<!-- Ingestion section removed — the Knowledge Store card already
             shows "Items to ingest: N of total" so a separate card here was
             redundant. -->
	</div>

	<!-- Progress steps during creation -->
	{#if submitting && progressSteps.length > 0}
		<div
			class="rounded-lg border border-blue-100 bg-blue-50 px-4 py-3"
			aria-live="polite"
			aria-label="Creation progress"
		>
			<ul class="space-y-2">
				{#each progressSteps as step (step.label + step.status)}
					<li class="flex items-center gap-2 pl-1 text-sm text-blue-900">
						{#if step.status === 'running'}
							<!-- Spinner -->
							<svg
								class="h-4 w-4 shrink-0 animate-spin text-blue-500"
								viewBox="0 0 24 24"
								fill="none"
								aria-hidden="true"
							>
								<circle
									class="opacity-25"
									cx="12"
									cy="12"
									r="10"
									stroke="currentColor"
									stroke-width="4"
								/>
								<path
									class="opacity-75"
									fill="currentColor"
									d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
								/>
							</svg>
						{:else if step.status === 'done'}
							<!-- Checkmark -->
							<svg
								class="h-4 w-4 shrink-0 text-green-500"
								viewBox="0 0 20 20"
								fill="currentColor"
								aria-hidden="true"
							>
								<path
									fill-rule="evenodd"
									d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z"
									clip-rule="evenodd"
								/>
							</svg>
						{:else}
							<!-- X / failed -->
							<svg
								class="h-4 w-4 shrink-0 text-red-400"
								viewBox="0 0 20 20"
								fill="currentColor"
								aria-hidden="true"
							>
								<path
									d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z"
								/>
							</svg>
						{/if}
						<span class={step.status === 'failed' ? 'text-red-700 line-through' : ''}
							>{step.label}</span
						>
					</li>
				{/each}
			</ul>
		</div>
	{/if}

	<!-- Create button lives in the wizard shell footer (alongside Back) so
	     it doesn't push the dialog content into a scroll. The wizard calls
	     this component's exported submit() when the user clicks it. -->
</div>

<PluginPickerModal
	bind:isOpen={showPluginPicker}
	matches={pluginMatches}
	file={pickerFile}
	onselect={handlePluginPicked}
	oncancel={handlePluginPickerCancel}
/>
