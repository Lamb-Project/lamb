<!--
  @component StepKSSetup
  Combined Step 3 of the 5-step wizard.
  Radio: "Create new KS" / "Use existing KS".

  When "Use existing": shows KS dropdown (from former Step4).
  When "Create new": shows name + description + sharing + collapsible
    "Advanced: chunking, embedding, vector DB" with the locked-after-create
    notice (from former Step6).

  Emits:
    - update: partial WizardState patch
    - validity: { valid: boolean }
-->
<script>
	import { createEventDispatcher, tick, untrack } from 'svelte';
	import axios from 'axios';
	import { getKnowledgeStores, getOptions } from '$lib/services/knowledgeStoreService';
	import { _ } from '$lib/i18n';

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

	let chunkingStrategy = $state(wizardState.ksConfig?.chunking_strategy || '');
	let embeddingVendor = $state(wizardState.ksConfig?.embedding_vendor || '');
	let embeddingModel = $state(wizardState.ksConfig?.embedding_model || '');
	let embeddingEndpoint = $state(wizardState.ksConfig?.embedding_endpoint || '');
	let vectorDb = $state(wizardState.ksConfig?.vector_db_backend || '');

	$effect(() => {
		if (path === 'new' && !loadingOptions && !optionsLoaded) {
			loadOptions();
		}
	});

	async function loadOptions() {
		loadingOptions = true;
		optionsError = '';
		try {
			options = await getOptions();
			if (!chunkingStrategy && options.chunking_strategies?.length) {
				chunkingStrategy = options.chunking_strategies[0].name;
			}
			// Default to a vendor the org has actually configured. The backend
			// tags each vendor with `api_key_configured`; vendors without a key
			// are kept in the list (so the UI can explain the gap) but are not
			// chosen as the default and the option is shown as disabled below.
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
		} catch (/** @type {unknown} */ err) {
			optionsError = readableError(err, 'Failed to load options');
			console.error('loadOptions failed', err);
		} finally {
			loadingOptions = false;
			optionsLoaded = true;
		}
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

	// Auto-expand the Advanced section so users can see (and fill) any
	// required field that the API didn't auto-populate — otherwise Next
	// stays disabled with no visible reason why.
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
		const _vendor = embeddingVendor;
		const _model = embeddingModel;
		const _endpoint = embeddingEndpoint;
		const _vectorDb = vectorDb;
		void _path;
		void _selectedId;
		void _name;
		void _description;
		void _isShared;
		void _chunking;
		void _vendor;
		void _model;
		void _endpoint;
		void _vectorDb;

		untrack(() => {
			// Persist the radio choice immediately so the draft retains the
			// last-clicked path even when the rest of the form is still
			// incomplete (e.g. name empty → early-return below).
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

			// path === 'new'
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
			if (!configValid) {
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
					chunking_params: {},
					embedding_vendor: embeddingVendor,
					embedding_model: embeddingModel,
					embedding_endpoint: embeddingEndpoint,
					vector_db_backend: vectorDb
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
</script>

<div class="space-y-4">
	<h3 class="text-base font-semibold text-gray-900">
		{$_('knowledge.wizard.ksStep.heading', { default: 'Knowledge Store' })}
	</h3>
	<p class="text-sm text-gray-600">
		{$_('knowledge.wizard.ksStep.description', {
			default:
				'Pick an existing Knowledge Store or create a new one. Existing stores keep their original chunking and embedding settings.'
		})}
	</p>

	<!-- Path radio -->
	<fieldset class="space-y-3">
		<legend class="sr-only">
			{$_('knowledge.wizard.ksStep.legend', { default: 'Knowledge Store path' })}
		</legend>

		<label
			class="flex cursor-pointer items-start gap-3 rounded-md border p-3 hover:bg-gray-50 {path ===
			'new'
				? 'border-[#2271b3] bg-blue-50'
				: 'border-gray-200'}"
		>
			<input type="radio" bind:group={path} value="new" class="mt-1" />
			<div>
				<div class="text-sm font-medium text-gray-900">
					{$_('knowledge.wizard.createNew', { default: 'Create new' })}
				</div>
				<div class="text-xs text-gray-500">
					{$_('knowledge.wizard.ksStep.createNewHint', {
						default: 'Configure a new Knowledge Store with chunking and embedding settings.'
					})}
				</div>
			</div>
		</label>

		<label
			class="flex cursor-pointer items-start gap-3 rounded-md border p-3 hover:bg-gray-50 {path ===
			'existing'
				? 'border-[#2271b3] bg-blue-50'
				: 'border-gray-200'}"
		>
			<input type="radio" bind:group={path} value="existing" class="mt-1" />
			<div class="flex-1">
				<div class="text-sm font-medium text-gray-900">
					{$_('knowledge.wizard.useExisting', { default: 'Use existing' })}
				</div>
				<div class="text-xs text-gray-500">
					{$_('knowledge.wizard.ksStep.useExistingHint', {
						default: 'Pick a Knowledge Store you already created and ingest more content into it.'
					})}
				</div>

				{#if path === 'existing'}
					<div class="mt-3">
						{#if loadingStores}
							<div class="text-sm text-gray-500">
								{$_('common.loading', { default: 'Loading...' })}
							</div>
						{:else if storeError}
							<div class="text-sm text-red-600" role="alert">{storeError}</div>
						{:else if stores.length === 0}
							<div class="text-sm text-gray-500">
								{$_('knowledge.wizard.ksStep.noStores', {
									default: 'No knowledge stores available. Choose "Create new" instead.'
								})}
							</div>
						{:else}
							<label for="wizard-ks-select" class="mb-1 block text-xs font-medium text-gray-700">
								{$_('knowledge.wizard.ksStep.selectLabel', { default: 'Knowledge Store' })}
							</label>
							<select
								id="wizard-ks-select"
								bind:value={selectedId}
								class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
							>
								{#each stores as s (s.id)}
									<option value={s.id}>{s.name} ({s.embedding_vendor}/{s.embedding_model})</option>
								{/each}
							</select>
						{/if}
					</div>
				{/if}
			</div>
		</label>
	</fieldset>

	<!-- New KS fields -->
	{#if path === 'new'}
		<div class="space-y-4 rounded-md border border-gray-100 bg-gray-50 p-4">
			<div>
				<label for="wizard-ks-name" class="block text-sm font-medium text-gray-700">
					{$_('libraries.name', { default: 'Name' })} <span class="text-red-500">*</span>
				</label>
				<input
					type="text"
					id="wizard-ks-name"
					bind:value={name}
					class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-[#2271b3] focus:ring-[#2271b3] {nameError
						? 'border-red-500'
						: ''}"
				/>
				{#if nameError}
					<p class="mt-1 text-sm text-red-600" role="alert">{nameError}</p>
				{/if}
			</div>

			<div>
				<label for="wizard-ks-description" class="block text-sm font-medium text-gray-700">
					{$_('libraries.description', { default: 'Description' })}
				</label>
				<textarea
					id="wizard-ks-description"
					bind:value={description}
					rows="2"
					class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-[#2271b3] focus:ring-[#2271b3]"
					placeholder={$_('libraries.descriptionPlaceholder', { default: 'Optional description' })}
				></textarea>
			</div>

			<label class="flex items-start gap-3">
				<input type="checkbox" bind:checked={isShared} class="mt-1" />
				<span>
					<span class="block text-sm font-medium text-gray-700">
						{$_('knowledge.wizard.ksStep.shareLabel', {
							default: 'Share with my organization'
						})}
					</span>
					<span class="block text-xs text-gray-500">
						{$_('knowledge.wizard.ksStep.shareHint', {
							default: 'You can change this later from the Knowledge Store detail view.'
						})}
					</span>
				</span>
			</label>

			<!-- Advanced: locked config -->
			<details bind:open={advancedOpen} class="rounded-md border border-gray-200 bg-white">
				<summary
					class="cursor-pointer px-3 py-2 text-sm font-medium text-[#2271b3] select-none hover:underline"
				>
					{$_('knowledge.wizard.ksStep.advancedLabel', {
						default: 'Advanced: chunking, embedding vendor/model, vector DB'
					})}
				</summary>
				<div class="space-y-3 p-3">
					<!-- Locked notice (preserved from Step6) -->
					<div
						class="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800"
						role="note"
					>
						<strong class="font-semibold">
							{$_('knowledge.wizard.lockedConfigNotice.title', {
								default: 'These settings cannot be changed later.'
							})}
						</strong>
						<p class="mt-1 text-xs">
							{$_('knowledge.wizard.lockedConfigNotice.body', {
								default:
									'Chunking strategy, embedding vendor / model, and vector DB are locked once the Knowledge Store is created. To change them, create a new Knowledge Store.'
							})}
						</p>
					</div>

					{#if loadingOptions}
						<div class="text-sm text-gray-500">
							{$_('common.loading', { default: 'Loading...' })}
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
							<label for="wizard-ks-chunking" class="block text-sm font-medium text-gray-700">
								{$_('knowledge.wizard.step6.chunkingLabel', { default: 'Chunking strategy' })}
								<span class="text-red-500">*</span>
							</label>
							<select
								id="wizard-ks-chunking"
								bind:value={chunkingStrategy}
								class="mt-1 block w-full rounded-md border px-3 py-2 text-sm {chunkingStrategy
									? 'border-gray-300'
									: 'border-red-500'}"
							>
								{#each options.chunking_strategies ?? [] as s (s.name)}
									<option value={s.name}>{s.name}</option>
								{/each}
							</select>
						</div>

						<div>
							<label for="wizard-ks-vendor" class="block text-sm font-medium text-gray-700">
								{$_('knowledge.wizard.step6.vendorLabel', { default: 'Embedding vendor' })}
								<span class="text-red-500">*</span>
							</label>
							<select
								id="wizard-ks-vendor"
								bind:value={embeddingVendor}
								disabled={hasNoConfiguredVendor}
								class="mt-1 block w-full rounded-md border px-3 py-2 text-sm disabled:cursor-not-allowed disabled:bg-gray-50 disabled:text-gray-400 {embeddingVendor
									? 'border-gray-300'
									: 'border-red-500'}"
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
							<label for="wizard-ks-model" class="block text-sm font-medium text-gray-700">
								{$_('knowledge.wizard.step6.modelLabel', { default: 'Embedding model' })}
								<span class="text-red-500">*</span>
							</label>
							{#if availableModels.length > 0}
								<select
									id="wizard-ks-model"
									bind:value={embeddingModel}
									class="mt-1 block w-full rounded-md border px-3 py-2 text-sm {embeddingModel
										? 'border-gray-300'
										: 'border-red-500'}"
								>
									{#each availableModels as m (m)}
										<option value={m}>{m}</option>
									{/each}
								</select>
							{:else}
								<input
									type="text"
									id="wizard-ks-model"
									bind:value={embeddingModel}
									placeholder="e.g. text-embedding-3-small"
									class="mt-1 block w-full rounded-md border px-3 py-2 text-sm {embeddingModel
										? 'border-gray-300'
										: 'border-red-500'}"
								/>
								{#if !embeddingModel}
									<p class="mt-1 text-xs text-red-600" role="alert">
										{$_('knowledge.wizard.step6.modelRequired', {
											default:
												'No models returned by the API for this vendor — type a model name to continue.'
										})}
									</p>
								{/if}
							{/if}
						</div>

						<div>
							<label for="wizard-ks-vectordb" class="block text-sm font-medium text-gray-700">
								{$_('knowledge.wizard.step6.vectorDbLabel', { default: 'Vector DB' })}
								<span class="text-red-500">*</span>
							</label>
							<select
								id="wizard-ks-vectordb"
								bind:value={vectorDb}
								class="mt-1 block w-full rounded-md border px-3 py-2 text-sm {vectorDb
									? 'border-gray-300'
									: 'border-red-500'}"
							>
								{#each options.vector_db_backends ?? [] as b (b.name)}
									<option value={b.name}>{b.name}</option>
								{/each}
							</select>
						</div>

						<div>
							<label for="wizard-ks-endpoint" class="block text-sm font-medium text-gray-700">
								{$_('knowledge.wizard.step6.endpointLabel', {
									default: 'Embedding endpoint (optional)'
								})}
							</label>
							<input
								type="text"
								id="wizard-ks-endpoint"
								bind:value={embeddingEndpoint}
								placeholder="https://..."
								class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
							/>
						</div>
					{/if}
				</div>
			</details>
		</div>
	{/if}
</div>
