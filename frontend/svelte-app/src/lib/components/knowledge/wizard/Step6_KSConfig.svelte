<!--
  @component Step6_KSConfig
  Locked Knowledge Store configuration. Driven by getOptions(); first
  allowed option pre-selected for each field. Includes a clearly-marked
  "immutable after creation" notice and an "Edit defaults" expander.

  Emits:
    - update: { ksConfig }
    - validity: { valid: boolean }
-->
<script>
	import { createEventDispatcher } from 'svelte';
	import { getOptions } from '$lib/services/knowledgeStoreService';
	import { _ } from '$lib/i18n';

	/** @type {{ wizardState: any }} */
	let { wizardState } = $props();

	const dispatch = createEventDispatcher();

	let options = $state(
		/** @type {any} */ ({
			chunking_strategies: [],
			embedding_vendors: [],
			embedding_models: {},
			vector_db_backends: []
		})
	);
	let loading = $state(false);
	let error = $state('');
	let expanded = $state(false);

	let chunkingStrategy = $state(wizardState.ksConfig?.chunking_strategy || '');
	let embeddingVendor = $state(wizardState.ksConfig?.embedding_vendor || '');
	let embeddingModel = $state(wizardState.ksConfig?.embedding_model || '');
	let embeddingEndpoint = $state(wizardState.ksConfig?.embedding_endpoint || '');
	let vectorDb = $state(wizardState.ksConfig?.vector_db_backend || '');

	$effect(() => {
		loadOptions();
	});

	async function loadOptions() {
		loading = true;
		error = '';
		try {
			options = await getOptions();
			// Pre-select first allowed option for each field if not already set.
			if (!chunkingStrategy && options.chunking_strategies?.length) {
				chunkingStrategy = options.chunking_strategies[0].name;
			}
			if (!embeddingVendor && options.embedding_vendors?.length) {
				embeddingVendor = options.embedding_vendors[0].name;
			}
			if (!vectorDb && options.vector_db_backends?.length) {
				vectorDb = options.vector_db_backends[0].name;
			}
		} catch (/** @type {unknown} */ err) {
			error = err instanceof Error ? err.message : 'Failed to load options';
		} finally {
			loading = false;
		}
	}

	let availableModels = $derived.by(() => {
		if (!embeddingVendor) return [];
		return options.embedding_models?.[embeddingVendor] ?? [];
	});

	$effect(() => {
		// Reset model selection when vendor changes.
		if (availableModels.length > 0 && !availableModels.includes(embeddingModel)) {
			embeddingModel = availableModels[0];
		}
	});

	$effect(() => {
		const valid = !!chunkingStrategy && !!embeddingVendor && !!embeddingModel && !!vectorDb;
		dispatch('validity', { valid });
		if (valid) {
			dispatch('update', {
				ksConfig: {
					chunking_strategy: chunkingStrategy,
					chunking_params: {},
					embedding_vendor: embeddingVendor,
					embedding_model: embeddingModel,
					embedding_endpoint: embeddingEndpoint,
					vector_db_backend: vectorDb
				}
			});
		}
	});
</script>

<div class="space-y-4">
	<h3 class="text-base font-semibold text-gray-900">
		{$_('knowledge.wizard.step6.heading', { default: 'Knowledge Store configuration' })}
	</h3>

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

	{#if loading}
		<div class="text-sm text-gray-500">{$_('common.loading', { default: 'Loading...' })}</div>
	{:else if error}
		<div class="rounded border border-red-100 bg-red-50 p-3 text-sm text-red-700" role="alert">
			{error}
		</div>
	{:else}
		<div class="space-y-1 rounded-md border border-gray-200 bg-gray-50 p-3 text-sm text-gray-700">
			<div>
				<span class="font-medium"
					>{$_('knowledge.wizard.step6.chunkingLabel', { default: 'Chunking strategy' })}:</span
				>
				{chunkingStrategy || '-'}
			</div>
			<div>
				<span class="font-medium"
					>{$_('knowledge.wizard.step6.vendorLabel', { default: 'Embedding vendor' })}:</span
				>
				{embeddingVendor || '-'}
			</div>
			<div>
				<span class="font-medium"
					>{$_('knowledge.wizard.step6.modelLabel', { default: 'Embedding model' })}:</span
				>
				{embeddingModel || '-'}
			</div>
			<div>
				<span class="font-medium"
					>{$_('knowledge.wizard.step6.vectorDbLabel', { default: 'Vector DB' })}:</span
				>
				{vectorDb || '-'}
			</div>
		</div>

		<button
			type="button"
			class="text-sm text-[#2271b3] hover:underline"
			onclick={() => (expanded = !expanded)}
			aria-expanded={expanded}
		>
			{expanded
				? $_('knowledge.wizard.editDefaults.collapse', { default: 'Hide options' })
				: $_('knowledge.wizard.editDefaults', { default: 'Edit defaults' })}
		</button>

		{#if expanded}
			<div class="space-y-3 rounded-md border border-gray-200 p-3">
				<div>
					<label for="wizard-ks-chunking" class="block text-sm font-medium text-gray-700">
						{$_('knowledge.wizard.step6.chunkingLabel', { default: 'Chunking strategy' })}
					</label>
					<select
						id="wizard-ks-chunking"
						bind:value={chunkingStrategy}
						class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
					>
						{#each options.chunking_strategies ?? [] as s (s.name)}
							<option value={s.name}>{s.name}</option>
						{/each}
					</select>
				</div>

				<div>
					<label for="wizard-ks-vendor" class="block text-sm font-medium text-gray-700">
						{$_('knowledge.wizard.step6.vendorLabel', { default: 'Embedding vendor' })}
					</label>
					<select
						id="wizard-ks-vendor"
						bind:value={embeddingVendor}
						class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
					>
						{#each options.embedding_vendors ?? [] as v (v.name)}
							<option value={v.name}>{v.name}</option>
						{/each}
					</select>
				</div>

				<div>
					<label for="wizard-ks-model" class="block text-sm font-medium text-gray-700">
						{$_('knowledge.wizard.step6.modelLabel', { default: 'Embedding model' })}
					</label>
					<select
						id="wizard-ks-model"
						bind:value={embeddingModel}
						class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
					>
						{#each availableModels as m (m)}
							<option value={m}>{m}</option>
						{/each}
					</select>
				</div>

				<div>
					<label for="wizard-ks-vectordb" class="block text-sm font-medium text-gray-700">
						{$_('knowledge.wizard.step6.vectorDbLabel', { default: 'Vector DB' })}
					</label>
					<select
						id="wizard-ks-vectordb"
						bind:value={vectorDb}
						class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
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
			</div>
		{/if}
	{/if}
</div>
