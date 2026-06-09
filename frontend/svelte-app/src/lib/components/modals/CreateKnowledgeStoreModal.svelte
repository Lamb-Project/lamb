<!--
  @component CreateKnowledgeStoreModal
  Simple single-page modal for creating a Knowledge Store. Matches the
  CreateLibraryModal layout: name + description and a Create button, with
  a collapsed "Advanced" panel exposing the locked-at-create config
  (chunking strategy + params, embedding vendor/model, vector DB,
  embedding endpoint). The Advanced panel auto-populates with sensible
  defaults from /knowledge-stores/options so a user can hit Create
  immediately without touching it.

  Emits 'created' on success with { id, name } so the parent can refresh
  and show a success toast — same pattern as CreateLibraryModal.
-->
<script>
	import { createEventDispatcher, tick } from 'svelte';
	import axios from 'axios';
	import {
		getOptions,
		createKnowledgeStore,
		toggleSharing,
		KnowledgeStoreUnavailableError
	} from '$lib/services/knowledgeStoreService';
	import PluginParamFields from '$lib/components/plugins/PluginParamFields.svelte';
	import { _ } from '$lib/i18n';

	const dispatch = createEventDispatcher();

	let isOpen = $state(false);
	let isSubmitting = $state(false);
	let error = $state('');
	let nameError = $state('');
	let name = $state('');
	let description = $state('');
	let isShared = $state(false);
	let advancedOpen = $state(false);

	// ── Options + config ──────────────────────────────────────────────
	let options = $state(
		/** @type {any} */ ({
			chunking_strategies: [],
			embedding_vendors: [],
			embedding_models: {},
			vector_db_backends: []
		})
	);
	let loadingOptions = $state(false);
	let optionsLoaded = $state(false);
	let optionsError = $state('');
	let optionsUnavailable = $state(false);

	let chunkingStrategy = $state('');
	let chunkingParams = $state(/** @type {Record<string, unknown>} */ ({}));
	let chunkingParamErrors = $state(/** @type {Record<string, string>} */ ({}));
	let embeddingVendor = $state('');
	let embeddingModel = $state('');
	let embeddingEndpoint = $state('');
	let embeddingParams = $state(/** @type {Record<string, unknown>} */ ({}));
	let embeddingParamErrors = $state(/** @type {Record<string, string>} */ ({}));
	let vectorDb = $state('');
	let vectorDbParams = $state(/** @type {Record<string, unknown>} */ ({}));
	let vectorDbParamErrors = $state(/** @type {Record<string, string>} */ ({}));

	let currentStrategyParams = $derived.by(() => {
		const s = (options.chunking_strategies ?? []).find(
			(/** @type {any} */ s) => s.name === chunkingStrategy
		);
		return s?.parameters ?? [];
	});
	let currentVendorParams = $derived.by(() => {
		const v = (options.embedding_vendors ?? []).find(
			(/** @type {any} */ v) => v.name === embeddingVendor
		);
		return v?.parameters ?? [];
	});
	let currentBackendParams = $derived.by(() => {
		const b = (options.vector_db_backends ?? []).find(
			(/** @type {any} */ b) => b.name === vectorDb
		);
		return b?.parameters ?? [];
	});

	let enabledVendors = $derived.by(() =>
		(options.embedding_vendors || []).filter(
			(/** @type {any} */ v) => v.api_key_configured !== false
		)
	);
	let hasNoConfiguredVendor = $derived(
		!loadingOptions && (options.embedding_vendors || []).length > 0 && enabledVendors.length === 0
	);
	let availableModels = $derived.by(() => {
		if (!embeddingVendor) return [];
		return options.embedding_models?.[embeddingVendor] ?? [];
	});

	// Reset plugin-param dicts when the user picks a different
	// strategy / vendor / backend so stale keys from a different plugin
	// don't carry over. The renderer re-initialises from the new schema's
	// defaults on next mount.
	let lastChunkingStrategy = $state(chunkingStrategy);
	$effect(() => {
		if (chunkingStrategy !== lastChunkingStrategy) {
			chunkingParams = {};
			lastChunkingStrategy = chunkingStrategy;
		}
	});
	let lastEmbeddingVendor = $state(embeddingVendor);
	$effect(() => {
		if (embeddingVendor !== lastEmbeddingVendor) {
			embeddingParams = {};
			lastEmbeddingVendor = embeddingVendor;
		}
	});
	let lastVectorDb = $state(vectorDb);
	$effect(() => {
		if (vectorDb !== lastVectorDb) {
			vectorDbParams = {};
			lastVectorDb = vectorDb;
		}
	});

	// When the vendor changes, snap the model selection to one the new vendor
	// actually offers — otherwise the dropdown shows a stale value.
	$effect(() => {
		if (availableModels.length > 0 && !availableModels.includes(embeddingModel)) {
			embeddingModel = availableModels[0];
		}
	});

	function suggestDefaultName() {
		const today = new Date().toISOString().slice(0, 10);
		return `My Knowledge Store ${today}`;
	}

	/** Open the modal and load defaults if not already loaded. */
	export async function open() {
		isOpen = true;
		resetForm();
		name = suggestDefaultName();
		await tick();
		const input = /** @type {HTMLInputElement|null} */ (document.getElementById('ks-name'));
		input?.focus();
		input?.select();
		if (!optionsLoaded && !loadingOptions) {
			await loadOptions();
		}
	}

	async function loadOptions() {
		loadingOptions = true;
		optionsError = '';
		optionsUnavailable = false;
		try {
			options = await getOptions();
			if (!chunkingStrategy && options.chunking_strategies?.length) {
				chunkingStrategy = options.chunking_strategies[0].name;
			}
			const enabled = (options.embedding_vendors || []).filter(
				(/** @type {any} */ v) => v.api_key_configured !== false
			);
			if (!embeddingVendor || !enabled.some((v) => v.name === embeddingVendor)) {
				embeddingVendor = enabled.length > 0 ? enabled[0].name : '';
			}
			if (!vectorDb && options.vector_db_backends?.length) {
				vectorDb = options.vector_db_backends[0].name;
			}
			optionsLoaded = true;
		} catch (/** @type {unknown} */ err) {
			if (err instanceof KnowledgeStoreUnavailableError) {
				optionsUnavailable = true;
				optionsError =
					err.detail ||
					$_('knowledgeStores.options.unavailableBody', {
						default:
							'Knowledge Store server unavailable. Please ensure lamb-kb-server is running and retry.'
					});
				// Allow retry — do NOT mark optionsLoaded so the next open()
				// will refetch automatically too.
				optionsLoaded = false;
			} else {
				optionsError = readableError(err, 'Failed to load options');
				optionsLoaded = true;
			}
			console.error('loadOptions failed', err);
		} finally {
			loadingOptions = false;
		}
	}

	async function retryLoadOptions() {
		await loadOptions();
	}

	/** @param {unknown} err @param {string} fallback @returns {string} */
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

	function close() {
		if (isSubmitting) return;
		isOpen = false;
		dispatch('close');
	}

	function resetForm() {
		name = '';
		description = '';
		isShared = false;
		error = '';
		nameError = '';
		isSubmitting = false;
		advancedOpen = false;
		// Keep loaded options + selected defaults across open() calls so the
		// user doesn't refetch and re-resolve every time they open the modal.
	}

	function validate() {
		nameError = '';
		if (!name.trim()) {
			nameError = $_('knowledgeStores.createModal.nameRequired', { default: 'Name is required' });
			return false;
		}
		if (name.trim().length > 100) {
			nameError = $_('knowledgeStores.createModal.nameTooLong', {
				default: 'Name must be less than 100 characters'
			});
			return false;
		}
		if (!chunkingStrategy || !embeddingVendor || !embeddingModel || !vectorDb) {
			error = $_('knowledgeStores.createModal.advancedIncomplete', {
				default:
					'Some required fields are missing. Open the Advanced section to review chunking and embedding settings.'
			});
			advancedOpen = true;
			return false;
		}
		const paramsValid =
			Object.keys(chunkingParamErrors).length === 0 &&
			Object.keys(embeddingParamErrors).length === 0 &&
			Object.keys(vectorDbParamErrors).length === 0;
		if (!paramsValid) {
			error = $_('knowledgeStores.createModal.invalidParams', {
				default: 'Some plugin parameters are invalid.'
			});
			advancedOpen = true;
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
			const ks = await createKnowledgeStore({
				name: name.trim(),
				description: description.trim() || '',
				chunking_strategy: chunkingStrategy,
				chunking_params: { ...chunkingParams },
				embedding_vendor: embeddingVendor,
				embedding_model: embeddingModel,
				embedding_endpoint: embeddingEndpoint.trim() || undefined,
				embedding_params: { ...embeddingParams },
				vector_db_backend: vectorDb,
				vector_db_params: { ...vectorDbParams }
			});
			if (isShared) {
				// Sharing is a separate endpoint; failure here shouldn't
				// roll back the KS — just surface in the console so the
				// user can flip it from the detail view.
				try {
					await toggleSharing(ks.id, true);
				} catch (e) {
					console.warn('toggleSharing after KS create failed', e);
				}
			}
			isOpen = false;
			dispatch('created', { id: ks.id, name: ks.name });
			resetForm();
		} catch (/** @type {unknown} */ err) {
			error = readableError(err, 'Failed to create Knowledge Store');
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
		aria-labelledby="create-ks-title"
		tabindex="-1"
		onclick={handleBackdropClick}
		onkeydown={handleKeydown}
	>
		<div
			class="mx-4 max-h-[90vh] w-full max-w-md overflow-y-auto rounded-lg bg-white shadow-xl"
			role="presentation"
			onclick={stopPropagation}
		>
			<div class="border-b border-gray-200 px-6 py-4">
				<h2 id="create-ks-title" class="text-lg font-semibold text-gray-900">
					{$_('knowledgeStores.createModal.title', { default: 'Create Knowledge Store' })}
				</h2>
				<p class="mt-1 text-sm text-gray-500">
					{$_('knowledgeStores.createModal.description', {
						default: 'Create a vector index that library content can be ingested into.'
					})}
				</p>
			</div>

			<form onsubmit={handleSubmit} class="space-y-4 px-6 py-4">
				{#if error}
					<div class="rounded-md bg-red-50 p-3 text-sm text-red-700" role="alert">{error}</div>
				{/if}

				<div>
					<label for="ks-name" class="block text-sm font-medium text-gray-700">
						{$_('knowledgeStores.name', { default: 'Name' })}
						<span class="text-red-500">*</span>
					</label>
					<input
						type="text"
						id="ks-name"
						bind:value={name}
						maxlength={200}
						class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-[#2271b3] focus:ring-[#2271b3] {nameError
							? 'border-red-500'
							: ''}"
						placeholder={$_('knowledgeStores.namePlaceholder', {
							default: 'Enter Knowledge Store name'
						})}
						disabled={isSubmitting}
					/>
					<p class="mt-1 text-xs text-gray-500">{(name || '').length}/200</p>
					{#if nameError}
						<p class="mt-1 text-sm text-red-600" role="alert">{nameError}</p>
					{/if}
				</div>

				<div>
					<label for="ks-description" class="block text-sm font-medium text-gray-700">
						{$_('knowledgeStores.description', { default: 'Description' })}
					</label>
					<textarea
						id="ks-description"
						bind:value={description}
						rows="3"
						maxlength={500}
						class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-[#2271b3] focus:ring-[#2271b3]"
						placeholder={$_('libraries.descriptionPlaceholder', {
							default: 'Optional description'
						})}
						disabled={isSubmitting}
					></textarea>
					<p class="mt-1 text-xs text-gray-500">{(description || '').length}/500</p>
				</div>

				<label class="flex items-start gap-3">
					<input type="checkbox" bind:checked={isShared} class="mt-1" disabled={isSubmitting} />
					<span>
						<span class="block text-sm font-medium text-gray-700">
							{$_('knowledgeStores.createModal.shareLabel', {
								default: 'Share with my organization'
							})}
						</span>
						<span class="block text-xs text-gray-500">
							{$_('knowledgeStores.createModal.shareHint', {
								default: 'You can change this later from the detail view.'
							})}
						</span>
					</span>
				</label>

				<!-- Advanced: locked-at-create config. Defaults come from the
				     server-provided options so a user can ignore this panel. -->
				<details bind:open={advancedOpen} class="rounded-md border border-gray-200 bg-gray-50">
					<summary
						class="cursor-pointer px-3 py-2 text-sm font-medium text-[#2271b3] select-none hover:underline"
					>
						{$_('knowledgeStores.createModal.advancedLabel', {
							default: 'Advanced: chunking, embedding, vector DB'
						})}
					</summary>

					<div class="space-y-3 p-3">
						<div
							class="rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800"
							role="note"
						>
							{$_('knowledgeStores.createModal.lockedNotice', {
								default:
									'Chunking strategy, embedding vendor/model, and vector DB are locked once the Knowledge Store is created. Chunking parameters can be edited later but only apply to newly ingested content.'
							})}
						</div>

						{#if loadingOptions}
							<div class="text-sm text-gray-500">
								{$_('common.loading', { default: 'Loading...' })}
							</div>
						{:else if optionsUnavailable}
							<div
								class="space-y-2 rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900"
								role="alert"
							>
								<p class="font-medium">
									{$_('knowledgeStores.options.unavailableTitle', {
										default: 'Knowledge Store server unavailable'
									})}
								</p>
								<p class="text-xs">{optionsError}</p>
								<button
									type="button"
									onclick={retryLoadOptions}
									class="rounded-md border border-amber-300 bg-white px-3 py-1 text-xs font-medium text-amber-900 hover:bg-amber-100"
								>
									{$_('common.retry', { default: 'Retry' })}
								</button>
							</div>
						{:else if optionsError}
							<div
								class="rounded border border-red-100 bg-red-50 p-3 text-sm text-red-700"
								role="alert"
							>
								{optionsError}
							</div>
						{:else}
							<div>
								<label for="ks-chunking" class="block text-xs font-medium text-gray-700">
									{$_('knowledge.wizard.step6.chunkingLabel', { default: 'Chunking strategy' })}
								</label>
								<select
									id="ks-chunking"
									bind:value={chunkingStrategy}
									class="mt-1 block w-full rounded-md border border-gray-300 px-2 py-1 text-sm"
									disabled={isSubmitting}
								>
									{#each options.chunking_strategies ?? [] as s (s.name)}
										<option value={s.name}>{s.name}</option>
									{/each}
								</select>
							</div>

							{#if currentStrategyParams.length > 0}
								<fieldset class="space-y-2 rounded-md border border-gray-200 bg-white p-2">
									<legend class="px-1 text-xs font-medium text-gray-700">
										{$_('knowledge.wizard.ksStep.chunkingParamsLabel', {
											values: { strategy: chunkingStrategy },
											default: `${chunkingStrategy} parameters`
										})}
									</legend>
									<PluginParamFields
										parameters={currentStrategyParams}
										bind:values={chunkingParams}
										bind:errors={chunkingParamErrors}
										idPrefix="ks-modal-chunking-param"
									/>
								</fieldset>
							{/if}

							<div>
								<label for="ks-vendor" class="block text-xs font-medium text-gray-700">
									{$_('knowledge.wizard.step6.vendorLabel', { default: 'Embedding vendor' })}
								</label>
								<select
									id="ks-vendor"
									bind:value={embeddingVendor}
									disabled={isSubmitting || hasNoConfiguredVendor}
									class="mt-1 block w-full rounded-md border border-gray-300 px-2 py-1 text-sm disabled:cursor-not-allowed disabled:bg-gray-50 disabled:text-gray-400"
								>
									{#each options.embedding_vendors ?? [] as v (v.name)}
										<option value={v.name} disabled={v.api_key_configured === false}>
											{v.name}{v.api_key_configured === false ? ' — not configured' : ''}
										</option>
									{/each}
								</select>
								{#if hasNoConfiguredVendor}
									<p
										class="mt-2 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900"
									>
										{$_('knowledge.wizard.step6.noVendorConfigured', {
											default:
												'Your organization has no embedding providers configured. Ask an admin to add an API key in the organization settings.'
										})}
									</p>
								{/if}
							</div>

							<div>
								<label for="ks-model" class="block text-xs font-medium text-gray-700">
									{$_('knowledge.wizard.step6.modelLabel', { default: 'Embedding model' })}
								</label>
								{#if availableModels.length > 0}
									<select
										id="ks-model"
										bind:value={embeddingModel}
										class="mt-1 block w-full rounded-md border border-gray-300 px-2 py-1 text-sm"
										disabled={isSubmitting}
									>
										{#each availableModels as m (m)}
											<option value={m}>{m}</option>
										{/each}
									</select>
								{:else}
									<input
										type="text"
										id="ks-model"
										bind:value={embeddingModel}
										placeholder="e.g. text-embedding-3-small"
										class="mt-1 block w-full rounded-md border border-gray-300 px-2 py-1 text-sm"
										disabled={isSubmitting}
									/>
								{/if}
							</div>

							<div>
								<label for="ks-endpoint" class="block text-xs font-medium text-gray-700">
									{$_('knowledge.wizard.step6.endpointLabel', {
										default: 'Embedding endpoint (optional)'
									})}
								</label>
								<input
									type="text"
									id="ks-endpoint"
									bind:value={embeddingEndpoint}
									placeholder="https://..."
									class="mt-1 block w-full rounded-md border border-gray-300 px-2 py-1 text-sm"
									disabled={isSubmitting}
								/>
							</div>

							{#if currentVendorParams.filter((/** @type {any} */ p) => !['model', 'api_endpoint', 'api_key'].includes(p.name)).length > 0}
								<fieldset class="space-y-2 rounded-md border border-gray-200 bg-white p-2">
									<legend class="px-1 text-xs font-medium text-gray-700">
										{$_('knowledge.wizard.ksStep.embeddingParamsLabel', {
											values: { vendor: embeddingVendor },
											default: `${embeddingVendor} parameters`
										})}
									</legend>
									<PluginParamFields
										parameters={currentVendorParams}
										bind:values={embeddingParams}
										bind:errors={embeddingParamErrors}
										idPrefix="ks-modal-embedding-param"
										exclude={['model', 'api_endpoint', 'api_key']}
									/>
								</fieldset>
							{/if}

							<div>
								<label for="ks-vectordb" class="block text-xs font-medium text-gray-700">
									{$_('knowledge.wizard.step6.vectorDbLabel', { default: 'Vector DB' })}
								</label>
								<select
									id="ks-vectordb"
									bind:value={vectorDb}
									class="mt-1 block w-full rounded-md border border-gray-300 px-2 py-1 text-sm"
									disabled={isSubmitting}
								>
									{#each options.vector_db_backends ?? [] as b (b.name)}
										<option value={b.name}>{b.name}</option>
									{/each}
								</select>
							</div>

							{#if currentBackendParams.length > 0}
								<fieldset class="space-y-2 rounded-md border border-gray-200 bg-white p-2">
									<legend class="px-1 text-xs font-medium text-gray-700">
										{$_('knowledge.wizard.ksStep.vectorDbParamsLabel', {
											values: { backend: vectorDb },
											default: `${vectorDb} parameters`
										})}
									</legend>
									<PluginParamFields
										parameters={currentBackendParams}
										bind:values={vectorDbParams}
										bind:errors={vectorDbParamErrors}
										idPrefix="ks-modal-vectordb-param"
									/>
								</fieldset>
							{/if}
						{/if}
					</div>
				</details>

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
							{$_('knowledgeStores.creating', { default: 'Creating...' })}
						{:else}
							{$_('knowledgeStores.createButton', { default: 'Create Knowledge Store' })}
						{/if}
					</button>
				</div>
			</form>
		</div>
	</div>
{/if}
