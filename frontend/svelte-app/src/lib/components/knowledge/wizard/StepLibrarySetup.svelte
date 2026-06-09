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
	import axios from 'axios';

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
	import { getLibraries, getPlugins } from '$lib/services/libraryService';
	import PluginParamFields from '$lib/components/plugins/PluginParamFields.svelte';
	import { _ } from '$lib/i18n';
	import { FormField, Collapsible, Banner, Checkbox } from '$lib/components/ui';

	/** @type {{ wizardState: any }} */
	let { wizardState } = $props();

	const dispatch = createEventDispatcher();

	// ── Path ────────────────────────────────────────────────────────────────
	let path = $state(wizardState.libraryPath || 'new');
	let selectedId = $state(wizardState.existingLibraryId || '');

	let libraries = $state(/** @type {any[]} */ ([]));
	let loadingLibraries = $state(false);
	let librariesLoaded = $state(false);
	let libraryError = $state('');

	$effect(() => {
		if (path === 'existing' && !librariesLoaded && !loadingLibraries) {
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
			libraryError = readableError(err, 'Failed to load libraries');
			console.error('loadLibraries failed', err);
		} finally {
			loadingLibraries = false;
			librariesLoaded = true;
		}
	}

	// ── New library fields ───────────────────────────────────────────────────
	let name = $state(wizardState.libraryName || '');
	let description = $state(wizardState.libraryDescription || '');
	let isShared = $state(!!wizardState.libraryIsShared);
	let nameError = $state('');

	// ── Plugin config (advanced) ─────────────────────────────────────────────
	let plugins = $state(/** @type {any[]} */ ([]));
	let pluginName = $state(wizardState.libraryImportConfig?.pluginName || '');
	let loadingPlugins = $state(false);
	let pluginError = $state('');

	let pluginParamsByName = $state(
		/** @type {Record<string, Record<string, unknown>>} */ (
			wizardState.libraryImportConfig?.pluginName && wizardState.libraryImportConfig?.params
				? {
						[wizardState.libraryImportConfig.pluginName]: {
							...wizardState.libraryImportConfig.params
						}
					}
				: {}
		)
	);
	let pluginParamErrors = $state(/** @type {Record<string, string>} */ ({}));

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
				const fileDefault = plugins.find((p) => p.source_type === 'file');
				pluginName = fileDefault?.name || plugins[0].name;
			}
		} catch (/** @type {unknown} */ err) {
			pluginError = readableError(err, 'Failed to load plugins');
			console.error('loadPlugins failed', err);
		} finally {
			loadingPlugins = false;
		}
	}

	let selectedPlugin = $derived(plugins.find((p) => p.name === pluginName));
	let selectedPluginParameters = $derived(selectedPlugin?.parameters ?? []);

	$effect(() => {
		if (!pluginName) return;
		if (!(pluginName in pluginParamsByName)) {
			pluginParamsByName = { ...pluginParamsByName, [pluginName]: {} };
		}
	});

	// ── Validity + dispatch ──────────────────────────────────────────────────
	$effect(() => {
		const _path = path;
		const _selectedId = selectedId;
		const _name = name;
		const _description = description;
		const _isShared = isShared;
		const _pluginName = pluginName;
		const _params = pluginParamsByName[pluginName];
		const _paramErrors = pluginParamErrors;
		void _path;
		void _selectedId;
		void _name;
		void _description;
		void _isShared;
		void _pluginName;
		void _params;
		void _paramErrors;
		for (const k of Object.keys(_params || {})) void (/** @type {any} */ (_params)[k]);
		for (const k of Object.keys(_paramErrors || {})) void _paramErrors[k];

		untrack(() => {
			dispatch('update', { libraryPath: path });

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
			const paramsValid = Object.keys(pluginParamErrors).length === 0;
			dispatch('validity', { valid: paramsValid });
			dispatch('update', {
				libraryPath: 'new',
				existingLibraryId: '',
				libraryName: trimmed,
				libraryDescription: description,
				libraryIsShared: isShared,
				libraryImportConfig: {
					pluginName,
					params: { ...(pluginParamsByName[pluginName] || {}) }
				}
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

	/** @param {string} v */
	function validateName(v) {
		const trimmed = (v || '').trim();
		if (!trimmed) {
			return $_('knowledge.wizard.libraryStep.nameRequired', { default: 'Name is required' });
		}
		if (trimmed.length > 100) {
			return $_('knowledge.wizard.libraryStep.nameTooLong', {
				default: 'Name must be less than 100 characters'
			});
		}
		return undefined;
	}
</script>

<div class="space-y-4">
	<h3 class="type-section-title">
		{$_('knowledge.wizard.libraryStep.heading', { default: 'Library' })}
	</h3>
	<p class="type-body-muted">
		{$_('knowledge.wizard.libraryStep.description', {
			default:
				'Pick an existing Library or create a new one. A Knowledge Store is always populated from a Library.'
		})}
	</p>

	<!-- Path radio (radio-as-card pattern) -->
	<fieldset class="space-y-3">
		<legend class="sr-only">
			{$_('knowledge.wizard.libraryStep.legend', { default: 'Library path' })}
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
					{$_('knowledge.wizard.libraryStep.createNewHint', {
						default: 'Start a fresh Library and import documents.'
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
					{$_('knowledge.wizard.libraryStep.useExistingHint', {
						default: 'Pick a Library you already have and skip ahead to the Knowledge Store steps.'
					})}
				</div>

				{#if path === 'existing'}
					<div class="mt-3">
						{#if loadingLibraries}
							<p class="type-body-muted">{$_('common.loading', { default: 'Loading...' })}</p>
						{:else if libraryError}
							<Banner variant="danger" size="sm" description={libraryError} />
						{:else if libraries.length === 0}
							<p class="type-body-muted">
								{$_('knowledge.wizard.libraryStep.noLibraries', {
									default: 'No libraries available. Choose "Create new" instead.'
								})}
							</p>
						{:else}
							<FormField
								id="wizard-library-select"
								label={$_('knowledge.wizard.libraryStep.selectLabel', { default: 'Library' })}
								type="select"
								bind:value={selectedId}
								options={libraries.map((/** @type {any} */ lib) => ({
									value: lib.id,
									label: `${lib.name} (${lib.item_count ?? 0} items)`
								}))}
							/>
						{/if}
					</div>
				{/if}
			</div>
		</label>
	</fieldset>

	<!-- New library fields -->
	{#if path === 'new'}
		<div class="border-border bg-surface-muted space-y-4 rounded-md border p-4">
			<FormField
				id="wizard-library-name"
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
				id="wizard-library-description"
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
				label={$_('knowledge.wizard.libraryStep.shareLabel', {
					default: 'Share with my organization'
				})}
				description={$_('knowledge.wizard.libraryStep.shareHint', {
					default: 'You can change this later from the Library detail view.'
				})}
			/>

			<!-- Advanced: import plugin -->
			<Collapsible
				label={$_('knowledge.wizard.libraryStep.advancedLabel', {
					default: 'Advanced: import plugin & params'
				})}
			>
				<div class="space-y-3">
					{#if loadingPlugins}
						<p class="type-body-muted">{$_('common.loading', { default: 'Loading...' })}</p>
					{:else if pluginError}
						<Banner variant="danger" size="sm" description={pluginError} />
					{:else if plugins.length === 0}
						<p class="type-body-muted">
							{$_('knowledge.wizard.libraryStep.noPlugins', {
								default: 'No import plugins available.'
							})}
						</p>
					{:else}
						<FormField
							id="wizard-library-plugin"
							label={$_('knowledge.wizard.libraryStep.pluginLabel', { default: 'Import plugin' })}
							type="select"
							bind:value={pluginName}
							options={plugins.map((/** @type {any} */ p) => ({
								value: p.name,
								label: p.name
							}))}
							helper={selectedPlugin?.description}
						/>

						{#if selectedPluginParameters.length > 0}
							<fieldset class="border-border bg-surface space-y-2 rounded-md border p-3">
								<legend class="type-label px-1">
									{$_('knowledge.wizard.libraryStep.pluginParamsLabel', {
										values: { plugin: selectedPlugin?.human_label || pluginName },
										default: 'Plugin parameters'
									})}
								</legend>
								<p class="type-caption">
									{$_('knowledge.wizard.libraryStep.pluginParamsHint', {
										default:
											'Defaults come from the plugin and work for most documents — override only if needed.'
									})}
								</p>
								<PluginParamFields
									parameters={selectedPluginParameters}
									bind:values={pluginParamsByName[pluginName]}
									bind:errors={pluginParamErrors}
									idPrefix="wizard-library-plugin-param"
									mode={selectedPlugin?.mode === 'ADVANCED' ? 'advanced' : 'simplified'}
								/>
							</fieldset>
						{/if}
					{/if}
				</div>
			</Collapsible>
		</div>
	{/if}
</div>
