<!--
  @component StepKSSetup
  Combined Step 3 of the 5-step wizard.
  Radio: "Create new KS" / "Use existing KS".

  When "Use existing": shows KS dropdown.
  When "Create new": shows name + description + sharing + a Collapsible
    "Advanced" section split into Chunking / Embedding / Storage
    sub-sections (each preceded by a `type-label` heading).

  Phase C consistency contract:
    * `<details>` is replaced by `<Collapsible>`.
    * 10+ field wall split into three labeled sub-sections.
    * Locked notice rendered via `<Banner variant="warning">`.
    * Each immutable field gets a trailing `<Lock>` icon with tooltip
      "Locked after creation".
    * All inputs are `<FormField>` instances.

  Emits:
    - update: partial WizardState patch
    - validity: { valid: boolean }
-->
<script>
	import { createEventDispatcher, tick, untrack } from 'svelte';
	import axios from 'axios';
	import {
		getKnowledgeStores,
		getOptions,
		KnowledgeStoreUnavailableError
	} from '$lib/services/knowledgeStoreService';
	import PluginParamFields from '$lib/components/plugins/PluginParamFields.svelte';
	import { _ } from '$lib/i18n';
	import { FormField, Collapsible, Banner, Button, Checkbox, Tooltip } from '$lib/components/ui';
	import { Lock } from 'lucide-svelte';

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

	/** @type {{ wizardState: any }} */
	let { wizardState } = $props();

	const dispatch = createEventDispatcher();

	// ── Path ────────────────────────────────────────────────────────────────
	let path = $state(wizardState.ksPath || 'new');
	let selectedId = $state(wizardState.existingKsId || '');

	let stores = $state(/** @type {any[]} */ ([]));
	let loadingStores = $state(false);
	let storesLoaded = $state(false);
	let storeError = $state('');

	$effect(() => {
		if (path === 'existing' && !storesLoaded && !loadingStores) {
			loadStores();
		}
	});

	async function loadStores() {
		loadingStores = true;
		storeError = '';
		try {
			stores = await getKnowledgeStores();
			if (!selectedId && stores.length > 0) {
				selectedId = stores[0].id;
			}
			await tick();
		} catch (/** @type {unknown} */ err) {
			storeError = readableError(err, 'Failed to load knowledge stores');
			console.error('loadStores failed', err);
		} finally {
			loadingStores = false;
			storesLoaded = true;
		}
	}

	// ── New KS fields ────────────────────────────────────────────────────────
	let name = $state(wizardState.ksName || '');
	let description = $state(wizardState.ksDescription || '');
	let isShared = $state(!!wizardState.ksIsShared);
	let nameError = $state('');

	// ── KS config (advanced, locked after create) ────────────────────────────
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

	let chunkingStrategy = $state(wizardState.ksConfig?.chunking_strategy || '');
	let chunkingParams = $state(
		/** @type {Record<string, unknown>} */ (wizardState.ksConfig?.chunking_params || {})
	);
	let chunkingParamErrors = $state(/** @type {Record<string, string>} */ ({}));
	let embeddingVendor = $state(wizardState.ksConfig?.embedding_vendor || '');
	let embeddingModel = $state(wizardState.ksConfig?.embedding_model || '');
	let embeddingEndpoint = $state(wizardState.ksConfig?.embedding_endpoint || '');
	let embeddingParams = $state(
		/** @type {Record<string, unknown>} */ (wizardState.ksConfig?.embedding_params || {})
	);
	let embeddingParamErrors = $state(/** @type {Record<string, string>} */ ({}));
	let vectorDb = $state(wizardState.ksConfig?.vector_db_backend || '');
	let vectorDbParams = $state(
		/** @type {Record<string, unknown>} */ (wizardState.ksConfig?.vector_db_params || {})
	);
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

	let lastChunkingStrategy = $state(chunkingStrategy);
	$effect(() => {
		if (chunkingStrategy !== lastChunkingStrategy) {
			untrack(() => {
				chunkingParams = {};
				lastChunkingStrategy = chunkingStrategy;
			});
		}
	});

	let lastEmbeddingVendor = $state(embeddingVendor);
	$effect(() => {
		if (embeddingVendor !== lastEmbeddingVendor) {
			untrack(() => {
				embeddingParams = {};
				lastEmbeddingVendor = embeddingVendor;
			});
		}
	});

	let lastVectorDb = $state(vectorDb);
	$effect(() => {
		if (vectorDb !== lastVectorDb) {
			untrack(() => {
				vectorDbParams = {};
				lastVectorDb = vectorDb;
			});
		}
	});

	$effect(() => {
		if (path === 'new' && !loadingOptions && !optionsLoaded) {
			loadOptions();
		}
	});

	async function loadOptions() {
		loadingOptions = true;
		optionsError = '';
		optionsUnavailable = false;
		try {
			options = await getOptions();
			if (!chunkingStrategy && options.chunking_strategies?.length) {
				chunkingStrategy = options.chunking_strategies[0].name;
			}
			const enabledVendors = (options.embedding_vendors || []).filter(
				(/** @type {any} */ v) => v.api_key_configured !== false
			);
			const draftVendor = embeddingVendor;
			const draftIsValid =
				draftVendor && enabledVendors.some((/** @type {any} */ v) => v.name === draftVendor);
			if (!draftIsValid) {
				embeddingVendor = enabledVendors.length > 0 ? enabledVendors[0].name : '';
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

	$effect(() => {
		if (availableModels.length > 0 && !availableModels.includes(embeddingModel)) {
			embeddingModel = availableModels[0];
		}
	});

	let advancedOpen = $state(false);
	$effect(() => {
		if (path !== 'new' || !optionsLoaded) return;
		const missing = !chunkingStrategy || !embeddingVendor || !embeddingModel || !vectorDb;
		if (missing) advancedOpen = true;
	});

	// ── Validity + dispatch ──────────────────────────────────────────────────
	$effect(() => {
		const _path = path;
		const _selectedId = selectedId;
		const _name = name;
		const _description = description;
		const _isShared = isShared;
		const _chunking = chunkingStrategy;
		const _params = chunkingParams;
		const _paramErrors = chunkingParamErrors;
		const _vendor = embeddingVendor;
		const _model = embeddingModel;
		const _endpoint = embeddingEndpoint;
		const _embParams = embeddingParams;
		const _embErrors = embeddingParamErrors;
		const _vectorDb = vectorDb;
		const _vdbParams = vectorDbParams;
		const _vdbErrors = vectorDbParamErrors;
		void _path;
		void _selectedId;
		void _name;
		void _description;
		void _isShared;
		void _chunking;
		void _params;
		void _paramErrors;
		void _vendor;
		void _model;
		void _endpoint;
		void _embParams;
		void _embErrors;
		void _vectorDb;
		void _vdbParams;
		void _vdbErrors;
		for (const k of Object.keys(_params || {})) void _params[k];
		for (const k of Object.keys(_paramErrors || {})) void _paramErrors[k];
		for (const k of Object.keys(_embParams || {})) void _embParams[k];
		for (const k of Object.keys(_embErrors || {})) void _embErrors[k];
		for (const k of Object.keys(_vdbParams || {})) void _vdbParams[k];
		for (const k of Object.keys(_vdbErrors || {})) void _vdbErrors[k];

		untrack(() => {
			dispatch('update', { ksPath: path });

			if (path === 'existing') {
				const valid = !!selectedId;
				dispatch('validity', { valid });
				if (selectedId) {
					const ks = stores.find((s) => s.id === selectedId);
					dispatch('update', {
						ksPath: 'existing',
						existingKsId: selectedId,
						ksName: ks?.name || wizardState.ksName
					});
				} else {
					dispatch('update', { ksPath: 'existing', existingKsId: '' });
				}
				return;
			}

			const trimmed = name.trim();
			if (!trimmed) {
				nameError = $_('knowledge.wizard.ksStep.nameRequired', { default: 'Name is required' });
				dispatch('validity', { valid: false });
				return;
			}
			if (trimmed.length > 100) {
				nameError = $_('knowledge.wizard.ksStep.nameTooLong', {
					default: 'Name must be less than 100 characters'
				});
				dispatch('validity', { valid: false });
				return;
			}
			const configValid = !!chunkingStrategy && !!embeddingVendor && !!embeddingModel && !!vectorDb;
			const paramsValid =
				Object.keys(chunkingParamErrors).length === 0 &&
				Object.keys(embeddingParamErrors).length === 0 &&
				Object.keys(vectorDbParamErrors).length === 0;
			if (!configValid || !paramsValid) {
				nameError = '';
				dispatch('validity', { valid: false });
				return;
			}
			nameError = '';
			dispatch('validity', { valid: true });
			dispatch('update', {
				ksPath: 'new',
				existingKsId: '',
				ksName: trimmed,
				ksDescription: description,
				ksIsShared: isShared,
				ksConfig: {
					chunking_strategy: chunkingStrategy,
					chunking_params: { ...chunkingParams },
					embedding_vendor: embeddingVendor,
					embedding_model: embeddingModel,
					embedding_endpoint: embeddingEndpoint,
					embedding_params: { ...embeddingParams },
					vector_db_backend: vectorDb,
					vector_db_params: { ...vectorDbParams }
				}
			});
		});
	});

	$effect(() => {
		if (path === 'new') {
			(async () => {
				await tick();
				document.getElementById('wizard-ks-name')?.focus();
			})();
		}
	});

	/** @param {string} v */
	function validateName(v) {
		const trimmed = (v || '').trim();
		if (!trimmed) {
			return $_('knowledge.wizard.ksStep.nameRequired', { default: 'Name is required' });
		}
		if (trimmed.length > 100) {
			return $_('knowledge.wizard.ksStep.nameTooLong', {
				default: 'Name must be less than 100 characters'
			});
		}
		return undefined;
	}
</script>

<div class="space-y-4">
	<h3 class="type-section-title">
		{$_('knowledge.wizard.ksStep.heading', { default: 'Knowledge Store' })}
	</h3>
	<p class="type-body-muted">
		{$_('knowledge.wizard.ksStep.description', {
			default:
				'Pick an existing Knowledge Store or create a new one. Existing stores keep their original chunking and embedding settings.'
		})}
	</p>

	<!-- Path radio (radio-as-card) -->
	<fieldset class="space-y-3">
		<legend class="sr-only">
			{$_('knowledge.wizard.ksStep.legend', { default: 'Knowledge Store path' })}
		</legend>

		<label
			class="hover:bg-surface-sunken flex cursor-pointer items-start gap-3 rounded-md border p-3 {path ===
			'new'
				? 'border-brand bg-brand-subtle'
				: 'border-border'}"
		>
			<input
				type="radio"
				bind:group={path}
				value="new"
				class="border-border-strong text-brand focus:ring-brand mt-1"
			/>
			<div>
				<div class="text-text text-sm font-medium">
					{$_('knowledge.wizard.createNew', { default: 'Create new' })}
				</div>
				<div class="type-caption">
					{$_('knowledge.wizard.ksStep.createNewHint', {
						default: 'Configure a new Knowledge Store with chunking and embedding settings.'
					})}
				</div>
			</div>
		</label>

		<label
			class="hover:bg-surface-sunken flex cursor-pointer items-start gap-3 rounded-md border p-3 {path ===
			'existing'
				? 'border-brand bg-brand-subtle'
				: 'border-border'}"
		>
			<input
				type="radio"
				bind:group={path}
				value="existing"
				class="border-border-strong text-brand focus:ring-brand mt-1"
			/>
			<div class="flex-1">
				<div class="text-text text-sm font-medium">
					{$_('knowledge.wizard.useExisting', { default: 'Use existing' })}
				</div>
				<div class="type-caption">
					{$_('knowledge.wizard.ksStep.useExistingHint', {
						default: 'Pick a Knowledge Store you already created and ingest more content into it.'
					})}
				</div>

				{#if path === 'existing'}
					<div class="mt-3">
						{#if loadingStores}
							<p class="type-body-muted">{$_('common.loading', { default: 'Loading...' })}</p>
						{:else if storeError}
							<Banner variant="danger" size="sm" description={storeError} />
						{:else if stores.length === 0}
							<p class="type-body-muted">
								{$_('knowledge.wizard.ksStep.noStores', {
									default: 'No knowledge stores available. Choose "Create new" instead.'
								})}
							</p>
						{:else}
							<FormField
								id="wizard-ks-select"
								label={$_('knowledge.wizard.ksStep.selectLabel', { default: 'Knowledge Store' })}
								type="select"
								bind:value={selectedId}
								options={stores.map((/** @type {any} */ s) => ({
									value: s.id,
									label: `${s.name} (${s.embedding_vendor}/${s.embedding_model})`
								}))}
							/>
						{/if}
					</div>
				{/if}
			</div>
		</label>
	</fieldset>

	<!-- New KS fields -->
	{#if path === 'new'}
		<div class="border-border bg-surface-muted space-y-4 rounded-md border p-4">
			<FormField
				id="wizard-ks-name"
				label={$_('libraries.name', { default: 'Name' })}
				type="text"
				bind:value={name}
				required
				error={nameError}
				validateOnBlur={validateName}
				maxlength={200}
				helper={`${(name || '').length}/200`}
			/>

			<FormField
				id="wizard-ks-description"
				label={$_('libraries.description', { default: 'Description' })}
				type="textarea"
				rows={2}
				bind:value={description}
				placeholder={$_('libraries.descriptionPlaceholder', { default: 'Optional description' })}
				maxlength={500}
				helper={`${(description || '').length}/500`}
			/>

			<Checkbox
				bind:checked={isShared}
				label={$_('knowledge.wizard.ksStep.shareLabel', {
					default: 'Share with my organization'
				})}
				description={$_('knowledge.wizard.ksStep.shareHint', {
					default: 'You can change this later from the Knowledge Store detail view.'
				})}
			/>

			<Collapsible
				bind:open={advancedOpen}
				label={$_('knowledge.wizard.advancedLabel', { default: 'Advanced settings' })}
				description={$_('knowledge.wizard.ksStep.advancedLabel', {
					default: 'Advanced: chunking, embedding vendor/model, vector DB'
				})}
			>
				<div class="space-y-5">
					<Banner
						variant="warning"
						title={$_('knowledge.wizard.lockedConfigNotice.title', {
							default: 'Some of these settings cannot be changed later.'
						})}
					>
						<p>
							{$_('knowledge.wizard.lockedConfigNotice.body', {
								default:
									'Chunking strategy, embedding vendor / model, and vector DB are locked once the Knowledge Store is created — to change them, create a new Knowledge Store.'
							})}
						</p>
						<p class="mt-1">
							{$_('knowledge.wizard.lockedConfigNotice.paramsBody', {
								default:
									'Chunking parameters can be edited later, but changes only apply to newly ingested content — existing chunks keep the parameters they were originally created with.'
							})}
						</p>
					</Banner>

					{#if loadingOptions}
						<p class="type-body-muted">{$_('common.loading', { default: 'Loading...' })}</p>
					{:else if optionsUnavailable}
						<Banner
							variant="warning"
							title={$_('knowledgeStores.options.unavailableTitle', {
								default: 'Knowledge Store server unavailable'
							})}
							description={optionsError}
						>
							{#snippet actions()}
								<Button variant="secondary" size="sm" onclick={retryLoadOptions}>
									{$_('common.retry', { default: 'Retry' })}
								</Button>
							{/snippet}
						</Banner>
					{:else if optionsError}
						<Banner variant="danger" size="sm" description={optionsError} />
					{:else}
						<!-- ── Chunking sub-section ─────────────────────────────── -->
						<section class="space-y-3">
							<h4 class="type-label">
								{$_('knowledge.wizard.ksStep.chunkingHeading', { default: 'Chunking' })}
							</h4>
							<div class="flex items-end gap-2">
								<div class="flex-1">
									<FormField
										id="wizard-ks-chunking"
										label={$_('knowledge.wizard.step6.chunkingLabel', {
											default: 'Chunking strategy'
										})}
										type="select"
										bind:value={chunkingStrategy}
										required
										options={(options.chunking_strategies ?? []).map((/** @type {any} */ s) => ({
											value: s.name,
											label: s.name
										}))}
									/>
								</div>
								<Tooltip
									text={$_('knowledge.wizard.lockedAfterCreation', {
										default: 'Locked after creation'
									})}
								>
									<Lock size={14} class="text-text-subtle mb-3" aria-hidden="true" />
								</Tooltip>
							</div>

							{#if currentStrategyParams.length > 0}
								<fieldset class="border-border bg-surface space-y-2 rounded-md border p-3">
									<legend class="type-label px-1">
										{$_('knowledge.wizard.ksStep.chunkingParamsLabel', {
											values: { strategy: chunkingStrategy },
											default: `${chunkingStrategy} parameters`
										})}
									</legend>
									<p class="type-caption">
										{$_('knowledge.wizard.ksStep.chunkingParamsHint', {
											default:
												'Defaults work for most documents — adjust only if you have a reason to. You can change these later from the Knowledge Store detail view, but changes only apply to content ingested after the edit.'
										})}
									</p>
									<PluginParamFields
										parameters={currentStrategyParams}
										bind:values={chunkingParams}
										bind:errors={chunkingParamErrors}
										idPrefix="wizard-ks-chunking-param"
									/>
								</fieldset>
							{/if}
						</section>

						<!-- ── Embedding sub-section ────────────────────────────── -->
						<section class="space-y-3">
							<h4 class="type-label">
								{$_('knowledge.wizard.ksStep.embeddingHeading', { default: 'Embedding' })}
							</h4>
							<div class="flex items-end gap-2">
								<div class="flex-1">
									<FormField
										id="wizard-ks-vendor"
										label={$_('knowledge.wizard.step6.vendorLabel', {
											default: 'Embedding vendor'
										})}
										type="select"
										bind:value={embeddingVendor}
										required
										disabled={hasNoConfiguredVendor}
										options={(options.embedding_vendors ?? []).map((/** @type {any} */ v) => ({
											value: v.name,
											label: `${v.name}${v.api_key_configured === false ? ' — not configured' : ''}`,
											disabled: v.api_key_configured === false
										}))}
									/>
								</div>
								<Tooltip
									text={$_('knowledge.wizard.lockedAfterCreation', {
										default: 'Locked after creation'
									})}
								>
									<Lock size={14} class="text-text-subtle mb-3" aria-hidden="true" />
								</Tooltip>
							</div>
							{#if hasNoConfiguredVendor}
								<Banner
									variant="warning"
									size="sm"
									description={$_('knowledge.wizard.step6.noVendorConfigured', {
										default:
											'Your organization has no embedding providers configured. Ask an admin to add an API key in the organization settings.'
									})}
								/>
							{/if}

							<div class="flex items-end gap-2">
								<div class="flex-1">
									{#if availableModels.length > 0}
										<FormField
											id="wizard-ks-model"
											label={$_('knowledge.wizard.step6.modelLabel', {
												default: 'Embedding model'
											})}
											type="select"
											bind:value={embeddingModel}
											required
											options={availableModels.map((/** @type {string} */ m) => ({
												value: m,
												label: m
											}))}
										/>
									{:else}
										<FormField
											id="wizard-ks-model"
											label={$_('knowledge.wizard.step6.modelLabel', {
												default: 'Embedding model'
											})}
											type="text"
											bind:value={embeddingModel}
											required
											placeholder="e.g. text-embedding-3-small"
											error={!embeddingModel
												? $_('knowledge.wizard.step6.modelRequired', {
														default:
															'No models returned by the API for this vendor — type a model name to continue.'
													})
												: ''}
										/>
									{/if}
								</div>
								<Tooltip
									text={$_('knowledge.wizard.lockedAfterCreation', {
										default: 'Locked after creation'
									})}
								>
									<Lock size={14} class="text-text-subtle mb-3" aria-hidden="true" />
								</Tooltip>
							</div>

							<FormField
								id="wizard-ks-endpoint"
								label={$_('knowledge.wizard.step6.endpointLabel', {
									default: 'Embedding endpoint (optional)'
								})}
								type="text"
								bind:value={embeddingEndpoint}
								placeholder="https://..."
							/>

							{#if currentVendorParams.filter((/** @type {any} */ p) => !['model', 'api_endpoint', 'api_key'].includes(p.name)).length > 0}
								<fieldset class="border-border bg-surface space-y-2 rounded-md border p-3">
									<legend class="type-label px-1">
										{$_('knowledge.wizard.ksStep.embeddingParamsLabel', {
											values: { vendor: embeddingVendor },
											default: `${embeddingVendor} parameters`
										})}
									</legend>
									<PluginParamFields
										parameters={currentVendorParams}
										bind:values={embeddingParams}
										bind:errors={embeddingParamErrors}
										idPrefix="wizard-ks-embedding-param"
										exclude={['model', 'api_endpoint', 'api_key']}
									/>
								</fieldset>
							{/if}
						</section>

						<!-- ── Storage sub-section ──────────────────────────────── -->
						<section class="space-y-3">
							<h4 class="type-label">
								{$_('knowledge.wizard.ksStep.storageHeading', { default: 'Storage' })}
							</h4>
							<div class="flex items-end gap-2">
								<div class="flex-1">
									<FormField
										id="wizard-ks-vectordb"
										label={$_('knowledge.wizard.step6.vectorDbLabel', {
											default: 'Vector DB'
										})}
										type="select"
										bind:value={vectorDb}
										required
										options={(options.vector_db_backends ?? []).map((/** @type {any} */ b) => ({
											value: b.name,
											label: b.name
										}))}
									/>
								</div>
								<Tooltip
									text={$_('knowledge.wizard.lockedAfterCreation', {
										default: 'Locked after creation'
									})}
								>
									<Lock size={14} class="text-text-subtle mb-3" aria-hidden="true" />
								</Tooltip>
							</div>

							{#if currentBackendParams.length > 0}
								<fieldset class="border-border bg-surface space-y-2 rounded-md border p-3">
									<legend class="type-label px-1">
										{$_('knowledge.wizard.ksStep.vectorDbParamsLabel', {
											values: { backend: vectorDb },
											default: `${vectorDb} parameters`
										})}
									</legend>
									<PluginParamFields
										parameters={currentBackendParams}
										bind:values={vectorDbParams}
										bind:errors={vectorDbParamErrors}
										idPrefix="wizard-ks-vectordb-param"
									/>
								</fieldset>
							{/if}
						</section>
					{/if}
				</div>
			</Collapsible>
		</div>
	{/if}
</div>
