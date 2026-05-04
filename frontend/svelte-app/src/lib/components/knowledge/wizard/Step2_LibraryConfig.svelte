<!--
  @component Step2_LibraryConfig
  Library import config. Defaults pre-filled inside an "Edit defaults"
  collapsible — user can click Next without expanding.

  Emits:
    - update: { libraryImportConfig: { pluginName, params } }
    - validity: { valid: boolean }
-->
<script>
	import { createEventDispatcher } from 'svelte';
	import { getPlugins } from '$lib/services/libraryService';
	import { _ } from '$lib/i18n';

	/** @type {{ wizardState: any }} */
	let { wizardState } = $props();

	const dispatch = createEventDispatcher();

	let plugins = $state(/** @type {any[]} */ ([]));
	let loading = $state(false);
	let error = $state('');
	let pluginName = $state(wizardState.libraryImportConfig?.pluginName || 'simple_import');
	let expanded = $state(false);

	$effect(() => {
		loadPlugins();
	});

	async function loadPlugins() {
		loading = true;
		error = '';
		try {
			plugins = await getPlugins();
			if (plugins.length > 0 && !plugins.find((p) => p.name === pluginName)) {
				// Fall back to simple_import if available, else first plugin.
				const simple = plugins.find((p) => p.name === 'simple_import');
				pluginName = simple?.name || plugins[0].name;
			}
		} catch (/** @type {unknown} */ err) {
			error = err instanceof Error ? err.message : 'Failed to load plugins';
		} finally {
			loading = false;
		}
	}

	$effect(() => {
		// Always valid — defaults are usable as-is.
		dispatch('validity', { valid: true });
		dispatch('update', {
			libraryImportConfig: { pluginName, params: {} }
		});
	});

	let selectedPlugin = $derived(plugins.find((p) => p.name === pluginName));
</script>

<div class="space-y-4">
	<h3 class="text-base font-semibold text-gray-900">
		{$_('knowledge.wizard.step2.heading', { default: 'Library import config' })}
	</h3>
	<p class="text-sm text-gray-600">
		{$_('knowledge.wizard.step2.description', {
			default:
				'Sensible defaults are pre-selected. Click "Edit defaults" to customize, or just continue.'
		})}
	</p>

	{#if loading}
		<div class="text-sm text-gray-500">{$_('common.loading', { default: 'Loading...' })}</div>
	{:else if error}
		<div class="rounded border border-red-100 bg-red-50 p-3 text-sm text-red-700" role="alert">
			{error}
		</div>
	{:else if plugins.length === 0}
		<div class="text-sm text-gray-500">
			{$_('knowledge.wizard.step2.noPlugins', { default: 'No import plugins available.' })}
		</div>
	{:else}
		<div class="rounded-md border border-gray-200 bg-gray-50 p-3 text-sm text-gray-700">
			<div>
				<span class="font-medium"
					>{$_('knowledge.wizard.step2.defaultPlugin', { default: 'Default import plugin' })}:</span
				>
				<span class="ml-1">{pluginName}</span>
			</div>
			{#if selectedPlugin?.description}
				<div class="mt-1 text-xs text-gray-500">{selectedPlugin.description}</div>
			{/if}
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
					<label for="wizard-library-plugin" class="block text-sm font-medium text-gray-700">
						{$_('knowledge.wizard.step2.pluginLabel', { default: 'Import plugin' })}
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
					{$_('knowledge.wizard.step2.pluginNote', {
						default: 'Per-plugin parameters can be customized later from the library detail view.'
					})}
				</p>
			</div>
		{/if}
	{/if}
</div>
