<!--
  @component StepLibrarySetup
  Combined Step 1 of the 5-step wizard.
  Radio: "Create new library" / "Use existing library".

  When "Use existing": shows library dropdown (from former Step0).
  When "Create new": shows name + description + sharing toggle + collapsible
    "Advanced: import plugin & params" (from former Step2).

  Emits:
    - update: partial WizardState patch
    - validity: { valid: boolean }
-->
<script>
	import { createEventDispatcher, tick, untrack } from 'svelte';
	import { getLibraries, getPlugins } from '$lib/services/libraryService';
	import { _ } from '$lib/i18n';

	/** @type {{ wizardState: any }} */
	let { wizardState } = $props();

	const dispatch = createEventDispatcher();

	// ── Path ────────────────────────────────────────────────────────────────
	let path = $state(wizardState.libraryPath || 'new');
	let selectedId = $state(wizardState.existingLibraryId || '');

	let libraries = $state(/** @type {any[]} */ ([]));
	let loadingLibraries = $state(false);
	let libraryError = $state('');

	$effect(() => {
		if (path === 'existing' && libraries.length === 0 && !loadingLibraries) {
			loadLibraries();
		}
	});

	async function loadLibraries() {
		loadingLibraries = true;
		libraryError = '';
		try {
			libraries = await getLibraries();
			if (!selectedId && libraries.length > 0) {
				selectedId = libraries[0].id;
			}
			await tick();
		} catch (/** @type {unknown} */ err) {
			libraryError = err instanceof Error ? err.message : 'Failed to load libraries';
		} finally {
			loadingLibraries = false;
		}
	}

	// ── New library fields ───────────────────────────────────────────────────
	let name = $state(wizardState.libraryName || '');
	let description = $state(wizardState.libraryDescription || '');
	let isShared = $state(!!wizardState.libraryIsShared);
	let nameError = $state('');

	// ── Plugin config (advanced) ─────────────────────────────────────────────
	let plugins = $state(/** @type {any[]} */ ([]));
	let pluginName = $state(wizardState.libraryImportConfig?.pluginName || 'simple_import');
	let loadingPlugins = $state(false);
	let pluginError = $state('');

	$effect(() => {
		if (path === 'new' && plugins.length === 0 && !loadingPlugins) {
			loadPlugins();
		}
	});

	async function loadPlugins() {
		loadingPlugins = true;
		pluginError = '';
		try {
			plugins = await getPlugins();
			if (plugins.length > 0 && !plugins.find((p) => p.name === pluginName)) {
				const simple = plugins.find((p) => p.name === 'simple_import');
				pluginName = simple?.name || plugins[0].name;
			}
		} catch (/** @type {unknown} */ err) {
			pluginError = err instanceof Error ? err.message : 'Failed to load plugins';
		} finally {
			loadingPlugins = false;
		}
	}

	let selectedPlugin = $derived(plugins.find((p) => p.name === pluginName));

	// ── Validity + dispatch ──────────────────────────────────────────────────
	$effect(() => {
		const _path = path;
		const _selectedId = selectedId;
		const _name = name;
		const _description = description;
		const _isShared = isShared;
		const _pluginName = pluginName;
		void _path;
		void _selectedId;
		void _name;
		void _description;
		void _isShared;
		void _pluginName;

		untrack(() => {
			if (path === 'existing') {
				const valid = !!selectedId;
				dispatch('validity', { valid });
				if (selectedId) {
					const lib = libraries.find((l) => l.id === selectedId);
					dispatch('update', {
						libraryPath: 'existing',
						existingLibraryId: selectedId,
						libraryName: lib?.name || wizardState.libraryName
					});
				} else {
					dispatch('update', { libraryPath: 'existing', existingLibraryId: '' });
				}
				return;
			}

			// path === 'new'
			const trimmed = name.trim();
			if (!trimmed) {
				nameError = $_('knowledge.wizard.libraryStep.nameRequired', {
					default: 'Name is required'
				});
				dispatch('validity', { valid: false });
				return;
			}
			if (trimmed.length > 100) {
				nameError = $_('knowledge.wizard.libraryStep.nameTooLong', {
					default: 'Name must be less than 100 characters'
				});
				dispatch('validity', { valid: false });
				return;
			}
			nameError = '';
			dispatch('validity', { valid: true });
			dispatch('update', {
				libraryPath: 'new',
				existingLibraryId: '',
				libraryName: trimmed,
				libraryDescription: description,
				libraryIsShared: isShared,
				libraryImportConfig: { pluginName, params: {} }
			});
		});
	});

	$effect(() => {
		if (path === 'new') {
			(async () => {
				await tick();
				document.getElementById('wizard-library-name')?.focus();
			})();
		}
	});
</script>

<div class="space-y-4">
	<h3 class="text-base font-semibold text-gray-900">
		{$_('knowledge.wizard.libraryStep.heading', { default: 'Library' })}
	</h3>
	<p class="text-sm text-gray-600">
		{$_('knowledge.wizard.libraryStep.description', {
			default:
				'Pick an existing Library or create a new one. A Knowledge Store is always populated from a Library.'
		})}
	</p>

	<!-- Path radio -->
	<fieldset class="space-y-3">
		<legend class="sr-only">
			{$_('knowledge.wizard.libraryStep.legend', { default: 'Library path' })}
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
					{$_('knowledge.wizard.libraryStep.createNewHint', {
						default: 'Start a fresh Library and import documents.'
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
					{$_('knowledge.wizard.libraryStep.useExistingHint', {
						default: 'Pick a Library you already have and skip ahead to the Knowledge Store steps.'
					})}
				</div>

				{#if path === 'existing'}
					<div class="mt-3">
						{#if loadingLibraries}
							<div class="text-sm text-gray-500">
								{$_('common.loading', { default: 'Loading...' })}
							</div>
						{:else if libraryError}
							<div class="text-sm text-red-600" role="alert">{libraryError}</div>
						{:else if libraries.length === 0}
							<div class="text-sm text-gray-500">
								{$_('knowledge.wizard.libraryStep.noLibraries', {
									default: 'No libraries available. Choose "Create new" instead.'
								})}
							</div>
						{:else}
							<label
								for="wizard-library-select"
								class="mb-1 block text-xs font-medium text-gray-700"
							>
								{$_('knowledge.wizard.libraryStep.selectLabel', { default: 'Library' })}
							</label>
							<select
								id="wizard-library-select"
								bind:value={selectedId}
								class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
							>
								{#each libraries as lib (lib.id)}
									<option value={lib.id}>{lib.name} ({lib.item_count} items)</option>
								{/each}
							</select>
						{/if}
					</div>
				{/if}
			</div>
		</label>
	</fieldset>

	<!-- New library fields -->
	{#if path === 'new'}
		<div class="space-y-4 rounded-md border border-gray-100 bg-gray-50 p-4">
			<div>
				<label for="wizard-library-name" class="block text-sm font-medium text-gray-700">
					{$_('libraries.name', { default: 'Name' })} <span class="text-red-500">*</span>
				</label>
				<input
					type="text"
					id="wizard-library-name"
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
				<label for="wizard-library-description" class="block text-sm font-medium text-gray-700">
					{$_('libraries.description', { default: 'Description' })}
				</label>
				<textarea
					id="wizard-library-description"
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
						{$_('knowledge.wizard.libraryStep.shareLabel', {
							default: 'Share with my organization'
						})}
					</span>
					<span class="block text-xs text-gray-500">
						{$_('knowledge.wizard.libraryStep.shareHint', {
							default: 'You can change this later from the Library detail view.'
						})}
					</span>
				</span>
			</label>

			<!-- Advanced: import plugin -->
			<details class="rounded-md border border-gray-200 bg-white">
				<summary
					class="cursor-pointer px-3 py-2 text-sm font-medium text-[#2271b3] select-none hover:underline"
				>
					{$_('knowledge.wizard.libraryStep.advancedLabel', {
						default: 'Advanced: import plugin & params'
					})}
				</summary>
				<div class="space-y-3 p-3">
					{#if loadingPlugins}
						<div class="text-sm text-gray-500">
							{$_('common.loading', { default: 'Loading...' })}
						</div>
					{:else if pluginError}
						<div
							class="rounded border border-red-100 bg-red-50 p-3 text-sm text-red-700"
							role="alert"
						>
							{pluginError}
						</div>
					{:else if plugins.length === 0}
						<div class="text-sm text-gray-500">
							{$_('knowledge.wizard.libraryStep.noPlugins', {
								default: 'No import plugins available.'
							})}
						</div>
					{:else}
						<div>
							<label for="wizard-library-plugin" class="block text-sm font-medium text-gray-700">
								{$_('knowledge.wizard.libraryStep.pluginLabel', { default: 'Import plugin' })}
							</label>
							<select
								id="wizard-library-plugin"
								bind:value={pluginName}
								class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
							>
								{#each plugins as p (p.name)}
									<option value={p.name}>{p.name}</option>
								{/each}
							</select>
							{#if selectedPlugin?.description}
								<p class="mt-1 text-xs text-gray-500">{selectedPlugin.description}</p>
							{/if}
						</div>
						<p class="text-xs text-gray-500">
							{$_('knowledge.wizard.libraryStep.pluginNote', {
								default:
									'Per-plugin parameters can be customized later from the library detail view.'
							})}
						</p>
					{/if}
				</div>
			</details>
		</div>
	{/if}
</div>
