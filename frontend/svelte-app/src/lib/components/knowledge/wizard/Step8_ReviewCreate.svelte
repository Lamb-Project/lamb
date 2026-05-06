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

			// 2. Upload pending files (only when new-library path; pendingFiles only collected then).
			/** @type {string[]} */
			const newlyReadyIds = [];
			const pending = wizardState.pendingFiles ?? [];
			if (wizardState.libraryPath === 'new' && pending.length > 0 && libraryId) {
				for (let i = 0; i < pending.length; i += 1) {
					const f = pending[i];
					pushStep(
						$_('knowledge.wizard.step8.progressUpload', {
							default: 'Uploading {name} ({n}/{total})...',
							values: { name: f.name, n: i + 1, total: pending.length }
						})
					);
					try {
						const result = await uploadFile(libraryId, f, {
							pluginName: wizardState.libraryImportConfig?.pluginName
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
			if (wizardState.libraryPath === 'new' && pendingUrlSources.length > 0 && libraryId) {
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
					vector_db_backend: wizardState.ksConfig.vector_db_backend
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
			if (wizardState.libraryPath === 'new') {
				itemsToIngest = newlyReadyIds;
			} else {
				itemsToIngest = [...(wizardState.selectedItemIds || [])];
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
			error = err instanceof Error ? err.message : 'Failed to create';
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

	let summarySelectedCount = $derived.by(() => {
		if (wizardState.libraryPath === 'new') {
			return (wizardState.pendingFiles ?? []).length + (wizardState.pendingUrlSources ?? []).length;
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
						{wizardState.libraryImportConfig?.pluginName || 'simple_import'}
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

		<!-- Content / Ingestion card -->
		<div class="rounded-lg border border-gray-200 bg-white p-4">
			<p class="mb-3 text-xs font-semibold tracking-wide text-gray-400 uppercase">
				{$_('knowledge.wizard.step8.ingestionHeading', { default: 'Ingestion' })}
			</p>
			<dl class="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-2 text-sm">
				<dt class="font-medium text-gray-500">
					{$_('knowledge.wizard.step8.itemsHeading', { default: 'Items to ingest' })}
				</dt>
				<dd class="text-gray-900">
					{$_('knowledge.wizard.step8.ingestionCount', {
						default: '{n} item(s) will be ingested',
						values: { n: summarySelectedCount }
					})}
				</dd>
			</dl>
		</div>
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

	<div class="flex justify-end pt-1">
		<button
			type="button"
			onclick={handleCreate}
			disabled={submitting}
			class="inline-flex items-center gap-2 rounded-md bg-[#2271b3] px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-[#195a91] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#2271b3] disabled:cursor-not-allowed disabled:opacity-50"
		>
			{#if submitting}
				<svg class="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
					<circle
						class="opacity-25"
						cx="12"
						cy="12"
						r="10"
						stroke="currentColor"
						stroke-width="4"
					/>
					<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
				</svg>
			{/if}
			{submitting
				? $_('knowledge.wizard.creating', { default: 'Creating...' })
				: $_('knowledge.wizard.step8.submit', { default: 'Create' })}
		</button>
	</div>
</div>
