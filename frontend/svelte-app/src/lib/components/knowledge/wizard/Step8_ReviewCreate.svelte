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
	import { createEventDispatcher } from 'svelte';
	import {
		createLibrary,
		toggleSharing as toggleLibrarySharing,
		uploadFile,
		importUrl,
		importYouTube,
		getItemStatus
	} from '$lib/services/libraryService';
	import {
		createKnowledgeStore,
		toggleSharing as toggleKSSharing,
		addContent
	} from '$lib/services/knowledgeStoreService';
	import { _ } from '$lib/i18n';

	/** @type {{ wizardState: any }} */
	let { wizardState } = $props();

	const dispatch = createEventDispatcher();

	let submitting = $state(false);
	let error = $state('');
	let progressMessage = $state('');

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

	async function handleCreate() {
		submitting = true;
		error = '';

		let libraryId = wizardState.existingLibraryId;
		let libraryName = wizardState.libraryName;
		let ksId = wizardState.existingKsId;
		let ksName = wizardState.ksName;

		try {
			// 1. Create library if new.
			if (wizardState.libraryPath === 'new') {
				progressMessage = $_('knowledge.wizard.step8.progressLibrary', {
					default: 'Creating library...'
				});
				const lib = await createLibrary({
					name: wizardState.libraryName,
					description: wizardState.libraryDescription || ''
				});
				libraryId = lib.id;
				libraryName = lib.name;

				if (wizardState.libraryIsShared) {
					try {
						await toggleLibrarySharing(libraryId, true);
					} catch (e) {
						console.error('toggleLibrarySharing failed', e);
					}
				}
			}

			// 2. Upload pending files (only when new-library path; pendingFiles only collected then).
			/** @type {string[]} */
			const newlyReadyIds = [];
			const pending = wizardState.pendingFiles ?? [];
			if (wizardState.libraryPath === 'new' && pending.length > 0 && libraryId) {
				for (let i = 0; i < pending.length; i += 1) {
					const f = pending[i];
					progressMessage = $_('knowledge.wizard.step8.progressUpload', {
						default: 'Uploading {name} ({n}/{total})...',
						values: { name: f.name, n: i + 1, total: pending.length }
					});
					try {
						const result = await uploadFile(libraryId, f, {
							pluginName: wizardState.libraryImportConfig?.pluginName
						});
						const itemId = result.item_id;
						progressMessage = $_('knowledge.wizard.step8.progressIngestStatus', {
							default: 'Waiting for {name} to finish importing...',
							values: { name: f.name }
						});
						const finalStatus = await pollItem(libraryId, itemId);
						if (finalStatus === 'ready') {
							newlyReadyIds.push(itemId);
						}
					} catch (e) {
						console.error(`Upload failed for ${f.name}`, e);
					}
				}
			}

			// 2b. Import pending URL / YouTube sources.
			const pendingUrlSources = wizardState.pendingUrlSources ?? [];
			if (wizardState.libraryPath === 'new' && pendingUrlSources.length > 0 && libraryId) {
				for (let i = 0; i < pendingUrlSources.length; i += 1) {
					const src = pendingUrlSources[i];
					progressMessage = $_('knowledge.wizard.step8.progressImportUrl', {
						default: 'Importing {url} ({n}/{total})...',
						values: { url: src.title || src.url, n: i + 1, total: pendingUrlSources.length }
					});
					try {
						let result;
						if (src.type === 'youtube') {
							result = await importYouTube(libraryId, {
								videoUrl: src.url,
								language: src.language || 'en',
								title: src.title || undefined
							});
						} else {
							result = await importUrl(libraryId, {
								url: src.url,
								title: src.title || undefined
							});
						}
						const itemId = result.item_id;
						progressMessage = $_('knowledge.wizard.step8.progressIngestStatus', {
							default: 'Waiting for {name} to finish importing...',
							values: { name: src.title || src.url }
						});
						const finalStatus = await pollItem(libraryId, itemId);
						if (finalStatus === 'ready') {
							newlyReadyIds.push(itemId);
						}
					} catch (e) {
						console.error(`URL import failed for ${src.url}`, e);
					}
				}
			}

			// 3. Create KS if new.
			if (wizardState.ksPath === 'new') {
				progressMessage = $_('knowledge.wizard.step8.progressKS', {
					default: 'Creating Knowledge Store...'
				});
				const ks = await createKnowledgeStore({
					name: wizardState.ksName,
					description: wizardState.ksDescription || '',
					chunking_strategy: wizardState.ksConfig.chunking_strategy,
					chunking_params: wizardState.ksConfig.chunking_params || {},
					embedding_vendor: wizardState.ksConfig.embedding_vendor,
					embedding_model: wizardState.ksConfig.embedding_model,
					embedding_endpoint: wizardState.ksConfig.embedding_endpoint || undefined,
					vector_db_backend: wizardState.ksConfig.vector_db_backend
				});
				ksId = ks.id;
				ksName = ks.name;

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
			if (wizardState.libraryPath === 'new') {
				itemsToIngest = newlyReadyIds;
			} else {
				itemsToIngest = [...(wizardState.selectedItemIds || [])];
			}

			// 5. Ingest content into KS.
			if (libraryId && ksId && itemsToIngest.length > 0) {
				progressMessage = $_('knowledge.wizard.step8.progressIngest', {
					default: 'Queuing {n} item(s) for ingestion...',
					values: { n: itemsToIngest.length }
				});
				try {
					await addContent(ksId, { libraryId, itemIds: itemsToIngest });
				} catch (e) {
					console.error('addContent failed', e);
					// Don't fail the whole wizard — KS and library exist.
				}
			}

			// 6. Done.
			dispatch('created', { libraryId, libraryName, ksId, ksName });
		} catch (/** @type {unknown} */ err) {
			error = err instanceof Error ? err.message : 'Failed to create';
		} finally {
			submitting = false;
			progressMessage = '';
		}
	}

	let summarySelectedCount = $derived.by(() => {
		if (wizardState.libraryPath === 'new') {
			return (wizardState.pendingFiles ?? []).length + (wizardState.pendingUrlSources ?? []).length;
		}
		return (wizardState.selectedItemIds ?? []).length;
	});
</script>

<div class="space-y-4">
	<h3 class="text-base font-semibold text-gray-900">
		{$_('knowledge.wizard.step8.heading', { default: 'Review & create' })}
	</h3>
	<p class="text-sm text-gray-600">
		{$_('knowledge.wizard.step8.description', {
			default:
				'Double-check the summary below. Nothing has been created yet — clicking "Create" will create the resources and queue the ingestion.'
		})}
	</p>

	{#if error}
		<div class="rounded border border-red-100 bg-red-50 p-3 text-sm text-red-700" role="alert">
			{error}
		</div>
	{/if}

	<div class="divide-y rounded-md border border-gray-200">
		<div class="p-3">
			<div class="text-xs tracking-wide text-gray-500 uppercase">
				{$_('knowledge.wizard.step8.libraryHeading', { default: 'Library' })}
			</div>
			<div class="text-sm font-medium text-gray-900">
				{wizardState.libraryName || '-'}
				<span class="ml-2 text-xs text-gray-400">
					({wizardState.libraryPath === 'existing'
						? $_('knowledge.wizard.useExisting', { default: 'Use existing' })
						: $_('knowledge.wizard.createNew', { default: 'Create new' })})
				</span>
			</div>
			{#if wizardState.libraryDescription}
				<div class="mt-1 text-xs text-gray-500">{wizardState.libraryDescription}</div>
			{/if}
			{#if wizardState.libraryPath === 'new'}
				<div class="mt-1 text-xs text-gray-500">
					{$_('knowledge.wizard.step8.libraryPlugin', {
						default: 'Import plugin: {plugin}',
						values: { plugin: wizardState.libraryImportConfig?.pluginName || 'simple_import' }
					})}
				</div>
				<div class="mt-1 text-xs text-gray-500">
					{$_('knowledge.wizard.step8.libraryFileCount', {
						default: '{n} file(s) to upload',
						values: { n: (wizardState.pendingFiles ?? []).length }
					})}
				</div>
				{#if (wizardState.pendingUrlSources ?? []).length > 0}
					<div class="mt-1 text-xs text-gray-500">
						{$_('knowledge.wizard.step8.libraryUrlCount', {
							default: '{n} URL/YouTube source(s) to import',
							values: { n: (wizardState.pendingUrlSources ?? []).length }
						})}
					</div>
				{/if}
			{/if}
		</div>

		<div class="p-3">
			<div class="text-xs tracking-wide text-gray-500 uppercase">
				{$_('knowledge.wizard.step8.ksHeading', { default: 'Knowledge Store' })}
			</div>
			<div class="text-sm font-medium text-gray-900">
				{wizardState.ksName || '-'}
				<span class="ml-2 text-xs text-gray-400">
					({wizardState.ksPath === 'existing'
						? $_('knowledge.wizard.useExisting', { default: 'Use existing' })
						: $_('knowledge.wizard.createNew', { default: 'Create new' })})
				</span>
			</div>
			{#if wizardState.ksPath === 'new'}
				<div class="mt-1 space-y-0.5 text-xs text-gray-500">
					<div>
						{$_('knowledge.wizard.step6.chunkingLabel', { default: 'Chunking strategy' })}: {wizardState
							.ksConfig?.chunking_strategy || '-'}
					</div>
					<div>
						{$_('knowledge.wizard.step6.vendorLabel', { default: 'Embedding vendor' })}: {wizardState
							.ksConfig?.embedding_vendor || '-'}
					</div>
					<div>
						{$_('knowledge.wizard.step6.modelLabel', { default: 'Embedding model' })}: {wizardState
							.ksConfig?.embedding_model || '-'}
					</div>
					<div>
						{$_('knowledge.wizard.step6.vectorDbLabel', { default: 'Vector DB' })}: {wizardState
							.ksConfig?.vector_db_backend || '-'}
					</div>
				</div>
			{/if}
		</div>

		<div class="p-3">
			<div class="text-xs tracking-wide text-gray-500 uppercase">
				{$_('knowledge.wizard.step8.ingestionHeading', { default: 'Ingestion' })}
			</div>
			<div class="text-sm text-gray-900">
				{$_('knowledge.wizard.step8.ingestionCount', {
					default: '{n} item(s) will be ingested',
					values: { n: summarySelectedCount }
				})}
			</div>
		</div>
	</div>

	{#if submitting && progressMessage}
		<div
			class="rounded-md border border-blue-200 bg-blue-50 p-3 text-sm text-blue-800"
			aria-live="polite"
		>
			{progressMessage}
		</div>
	{/if}

	<div class="flex justify-end">
		<button
			type="button"
			onclick={handleCreate}
			disabled={submitting}
			class="rounded-md bg-[#2271b3] px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-[#195a91] disabled:opacity-50"
		>
			{submitting
				? $_('knowledge.wizard.creating', { default: 'Creating...' })
				: $_('knowledge.wizard.create', { default: 'Create' })}
		</button>
	</div>
</div>
