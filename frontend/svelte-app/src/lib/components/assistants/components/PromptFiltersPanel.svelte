<script>
	import { _ } from '$lib/i18n';
	import { getApiUrl } from '$lib/config';
	/** @type {{definition?: any, isAdvancedMode?: boolean, systemPrompt?: string, processor?: string, onchange?: () => void}} */
	let { definition = $bindable(null), isAdvancedMode = false, systemPrompt = '', processor = '', onchange } = $props();
	/** @type {string | null} */
	let preview = $state(null);
	let error = $state('');
	let loading = $state(false);
	/** @type {any[]} */
	let items = $derived(Array.isArray(definition?.items) ? definition.items : []);
	let active = $derived(items.filter((item) => item.enabled).length);
	let supported = $derived(!definition || (definition.version === 1 && Array.isArray(definition.items)));
	$effect(() => { systemPrompt; processor; definition; preview = null; });
	/** @param {any[]} next */
	function change(next) {
		definition = { version: 1, items: next };
		preview = null;
		error = '';
		onchange?.();
	}
	function add() {
		change([...items, { id: crypto.randomUUID(), type: 'random', enabled: true,
			target: 'system_prompt', run_on: 'conversation_start', options: {} }]);
	}
	/** @param {number} index @param {number} direction */
	function move(index, direction) {
		const next = [...items];
		[next[index], next[index + direction]] = [next[index + direction], next[index]];
		change(next);
	}
	async function sample() {
		loading = true;
		error = '';
		preview = null;
		try {
			const response = await fetch(getApiUrl('/assistant/prompt-filters/preview'), {
				method: 'POST',
				headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${localStorage.getItem('userToken')}` },
				body: JSON.stringify({ system_prompt: systemPrompt, metadata: { prompt_processor: processor, prompt_filters: definition } })
			});
			const result = await response.json();
			if (!response.ok) throw new Error(result.detail || $_('assistants.form.filters.previewError'));
			preview = result.system_prompt;
		} catch (err) {
			error = err instanceof Error ? err.message : String(err);
		} finally { loading = false; }
	}
</script>

{#if isAdvancedMode}
	<fieldset class="border p-4 rounded-md mb-4 space-y-3">
		<legend class="text-lg font-medium text-brand px-1">{$_('assistants.form.filters.title')}</legend>
		<p class="text-sm text-gray-600">{$_('assistants.form.filters.description')}</p>
		<code class="block text-sm">{'{{RANDOM:25-70}}'}</code>
		{#if !supported}
			<p role="alert" class="text-red-700">{$_('assistants.form.filters.unsupported')}</p>
		{:else}
			<ol class="space-y-2">
				{#each items as item, index (item.id)}
					<li class="border rounded p-2 space-y-2">
						<label class="flex items-center gap-2">
							<input type="checkbox" checked={item.enabled} onchange={(event) => change(items.map((entry, i) => i === index ? {...entry, enabled: event.currentTarget.checked} : entry))} />
							<span>{index + 1}. {item.type === 'random' ? $_('assistants.form.filters.random') : item.type}</span>
						</label>
						<div class="flex gap-2 text-sm">
							<button class="border rounded px-2 py-1 disabled:opacity-40" type="button" disabled={index === 0} onclick={() => move(index, -1)} aria-label={`${$_('assistants.form.filters.up')} ${index + 1}`}>{$_('assistants.form.filters.up')}</button>
							<button class="border rounded px-2 py-1 disabled:opacity-40" type="button" disabled={index === items.length - 1} onclick={() => move(index, 1)} aria-label={`${$_('assistants.form.filters.down')} ${index + 1}`}>{$_('assistants.form.filters.down')}</button>
							<button class="border rounded px-2 py-1" type="button" onclick={() => change(items.filter((_, i) => i !== index))} aria-label={`${$_('assistants.form.filters.remove')} ${index + 1}`}>{$_('assistants.form.filters.remove')}</button>
						</div>
					</li>
				{/each}
			</ol>
			<button class="border rounded px-3 py-1" type="button" disabled={items.length >= 20} onclick={add}>{$_('assistants.form.filters.add')}</button>
			<button class="border rounded px-3 py-1" type="button" disabled={loading || !active} onclick={sample}>{$_('assistants.form.filters.preview')}</button>
		{/if}
		{#if error}<p role="alert" class="text-red-700">{error}</p>{/if}
		{#if preview !== null}
			<p class="text-sm text-gray-600">{$_('assistants.form.filters.sampleOnly')}</p>
			<pre class="whitespace-pre-wrap break-words bg-gray-50 p-3 rounded text-sm" aria-label={$_('assistants.form.filters.preview')}>{preview}</pre>
		{/if}
	</fieldset>
{:else if active || !supported}
	<p class="mb-3 text-sm text-brand">{$_('assistants.form.filters.active', {values: {count: active}})}</p>
{/if}
