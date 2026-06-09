<!--
  @component PluginPickerModal
  Tie-break modal shown when an uploaded file matches more than one import
  plugin (e.g. a PDF matches both ``markitdown_import`` and
  ``markitdown_plus_import``). The user picks which plugin to use.

  Pure presentation — wiring (matching the file against the plugin list,
  routing the upload after a pick) lives in the parent component. See the
  callers in ``LibraryDetail.svelte`` and ``Step8_ReviewCreate.svelte``.

  Props:
    - isOpen: $bindable(boolean)
    - matches: PluginMeta[] (the plugins that matched the file)
    - file: File | { name?: string } | string  (for context line)
    - onselect: (plugin: PluginMeta) => void
    - oncancel: () => void
-->
<script>
	import { _ } from '$lib/i18n';
	import { Modal, Button } from '$lib/components/ui';

	/**
	 * @typedef {Object} PluginMeta
	 * @property {string} name
	 * @property {string} [description]
	 * @property {string} [human_label]
	 * @property {string[]} [file_extensions]
	 */

	let {
		isOpen = $bindable(false),
		/** @type {PluginMeta[]} */
		matches = [],
		/** @type {File|{name?: string}|string} */
		file = '',
		/** @type {(plugin: PluginMeta) => void} */
		onselect = () => {},
		oncancel = () => {}
	} = $props();

	let filename = $derived.by(() => {
		if (typeof file === 'string') return file;
		if (file && typeof file === 'object' && 'name' in file) {
			const n = /** @type {{ name?: unknown }} */ (file).name;
			return typeof n === 'string' ? n : '';
		}
		return '';
	});

	function close() {
		oncancel();
		isOpen = false;
	}

	/** @param {PluginMeta} plugin */
	function pick(plugin) {
		onselect(plugin);
		isOpen = false;
	}
</script>

<Modal
	open={isOpen}
	onclose={close}
	size="md"
	closeAriaLabel={$_('common.close', { default: 'Close' })}
>
	{#snippet header({ close: closeFn })}
		<div class="border-border flex items-start justify-between gap-3 border-b px-6 py-4">
			<div class="min-w-0 flex-1">
				<h2 class="type-section-title truncate">
					{$_('libraries.pluginPicker.title', { default: 'Choose how to import this file' })}
				</h2>
				{#if filename}
					<p class="type-caption mt-0.5 truncate" title={filename}>{filename}</p>
				{/if}
			</div>
			<div class="-mt-2 -mr-2 shrink-0">
				<Button
					variant="ghost"
					size="sm"
					onclick={closeFn}
					ariaLabel={$_('common.close', { default: 'Close' })}
				>
					{$_('common.close', { default: 'Close' })}
				</Button>
			</div>
		</div>
	{/snippet}

	<p class="type-body-muted mb-4">
		{$_('libraries.pluginPicker.body', {
			default:
				'More than one importer can handle this file. Pick the one that best fits your needs.'
		})}
	</p>
	{#if matches.length === 0}
		<p class="type-body-muted">
			{$_('libraries.pluginPicker.empty', { default: 'No matching plugins.' })}
		</p>
	{:else}
		<ul class="space-y-2" role="listbox">
			{#each matches as plugin (plugin.name)}
				<li>
					<button
						type="button"
						role="option"
						aria-selected="false"
						onclick={() => pick(plugin)}
						class="border-border bg-surface hover:border-brand hover:bg-brand-subtle focus:border-brand focus:bg-brand-subtle block w-full rounded-lg border px-4 py-3 text-left transition-colors focus:outline-none"
					>
						<div class="text-text text-sm font-medium">
							{plugin.human_label || plugin.name}
						</div>
						{#if plugin.description}
							<div class="type-caption mt-1">{plugin.description}</div>
						{/if}
					</button>
				</li>
			{/each}
		</ul>
	{/if}

	{#snippet footer({ close: closeFn })}
		<Button variant="secondary" onclick={closeFn}>
			{$_('common.cancel', { default: 'Cancel' })}
		</Button>
	{/snippet}
</Modal>
