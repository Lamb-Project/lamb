<!--
  @component PluginParamFields
  Generic schema-driven renderer for a plugin's PluginParameter[] array.

  One input per parameter, keyed by `type`:
    - "int" / "float" → number input with min/max/step
    - "string"        → text input
    - "bool"          → checkbox
    - "enum"          → <select> populated from `choices`

  Each field's label, description, default, choices, and min/max bounds come
  from the schema returned by the plugin's ``get_parameters()`` method —
  there are no hardcoded plugin-specific assumptions here. Drop a new plugin
  on the backend, add a fresh ``PluginParameter`` to its schema, and the
  field appears here automatically.

  Props:
    - parameters: PluginParameter[]   — the schema
    - values: Record<string, unknown> ($bindable) — the value dict
    - idPrefix: string                — unique id prefix for inputs
    - mode?: 'simplified' | 'advanced' — when 'simplified', params marked
      ``advanced: true`` go behind a collapsed <details>. KB Server omits
      the ``advanced`` field; missing is treated as ``false``.
    - exclude?: string[]              — parameter names to skip (e.g. the
      embedding vendor's ``model`` / ``api_endpoint`` already have bespoke
      widgets in StepKSSetup).
    - errors: Record<string, string> ($bindable) — client-side validation
      errors keyed by parameter name.
-->
<script>
	import { _ } from '$lib/i18n';

	/**
	 * @typedef {Object} PluginParameter
	 * @property {string} name
	 * @property {string} type           "string" | "int" | "float" | "bool" | "enum"
	 * @property {string} [description]
	 * @property {unknown} [default]
	 * @property {boolean} [required]
	 * @property {string[]|null} [choices]
	 * @property {number|null} [min_value]
	 * @property {number|null} [max_value]
	 * @property {boolean} [advanced]
	 */

	/**
	 * @type {{
	 *   parameters: PluginParameter[],
	 *   values: Record<string, unknown>,
	 *   idPrefix: string,
	 *   mode?: 'simplified' | 'advanced',
	 *   exclude?: string[],
	 *   errors?: Record<string, string>
	 * }}
	 */
	let {
		parameters,
		values = $bindable({}),
		idPrefix,
		mode = 'simplified',
		exclude = [],
		errors = $bindable({})
	} = $props();

	// Visible params (after applying `exclude`). The `advanced` filter happens
	// inside the template so the two groups can render in separate sections.
	let visibleParams = $derived(parameters.filter((p) => !exclude.includes(p.name)));
	let basicParams = $derived(visibleParams.filter((p) => !p.advanced));
	let advancedParams = $derived(visibleParams.filter((p) => p.advanced));

	// Whether to show the <details> wrapper around advanced params. In
	// 'advanced' mode they render flat alongside the basic ones; in
	// 'simplified' mode they collapse under a toggle.
	let collapseAdvanced = $derived(mode === 'simplified' && advancedParams.length > 0);

	// Initialise any missing keys from the schema's `default`. Runs whenever
	// the parameter list changes (e.g. user picks a different plugin) so the
	// values dict always carries one entry per declared param. We only fill
	// missing keys — existing values (even `false` / `0` / `""`) are kept so
	// an explicit user choice isn't silently overwritten.
	$effect(() => {
		const params = visibleParams;
		let mutated = false;
		const next = { ...values };
		for (const p of params) {
			if (!(p.name in next)) {
				next[p.name] = p.default ?? defaultByType(p.type);
				mutated = true;
			}
		}
		if (mutated) values = next;
	});

	// Client-side validation. Re-runs on every value change. The errors map
	// is exposed via $bindable so the parent form can disable submit while
	// any error is present.
	$effect(() => {
		const params = visibleParams;
		const errs = /** @type {Record<string, string>} */ ({});
		for (const p of params) {
			const v = values[p.name];
			const isNumeric = p.type === 'int' || p.type === 'float';

			if (p.required) {
				if (v === undefined || v === null || v === '') {
					errs[p.name] = $_('plugins.params.required', { default: 'Required' });
					continue;
				}
				if (isNumeric && Number.isNaN(v)) {
					errs[p.name] = $_('plugins.params.required', { default: 'Required' });
					continue;
				}
			}

			if (isNumeric && typeof v === 'number' && !Number.isNaN(v)) {
				if (typeof p.min_value === 'number' && v < p.min_value) {
					errs[p.name] = $_('plugins.params.tooSmall', {
						values: { min: p.min_value },
						default: `Must be ≥ ${p.min_value}`
					});
					continue;
				}
				if (typeof p.max_value === 'number' && v > p.max_value) {
					errs[p.name] = $_('plugins.params.tooLarge', {
						values: { max: p.max_value },
						default: `Must be ≤ ${p.max_value}`
					});
				}
			}
		}
		errors = errs;
	});

	/** @param {string} type @returns {unknown} */
	function defaultByType(type) {
		if (type === 'bool') return false;
		if (type === 'int' || type === 'float') return Number.NaN;
		return '';
	}

	/** @param {PluginParameter} p @param {Event} e */
	function onNumberInput(p, e) {
		const raw = /** @type {HTMLInputElement} */ (e.currentTarget).value;
		const v = raw === '' ? Number.NaN : Number(raw);
		values = { ...values, [p.name]: v };
	}

	/** @param {PluginParameter} p @param {Event} e */
	function onTextInput(p, e) {
		const raw = /** @type {HTMLInputElement} */ (e.currentTarget).value;
		values = { ...values, [p.name]: raw };
	}

	/** @param {PluginParameter} p @param {Event} e */
	function onBoolInput(p, e) {
		const checked = /** @type {HTMLInputElement} */ (e.currentTarget).checked;
		values = { ...values, [p.name]: checked };
	}

	/** @param {PluginParameter} p @param {Event} e */
	function onSelectInput(p, e) {
		const raw = /** @type {HTMLSelectElement} */ (e.currentTarget).value;
		values = { ...values, [p.name]: raw };
	}
</script>

{#snippet field(/** @type {PluginParameter} */ p)}
	{@const inputId = `${idPrefix}-${p.name}`}
	{@const hasError = !!errors[p.name]}
	<div class="flex flex-col gap-1 sm:flex-row sm:items-center sm:gap-3">
		<label
			for={inputId}
			class="block w-full text-xs font-medium text-gray-700 sm:w-1/3"
			title={p.description}
		>
			{p.name}
			{#if p.required}<span class="text-red-500">*</span>{/if}
			{#if (p.type === 'int' || p.type === 'float') && (typeof p.min_value === 'number' || typeof p.max_value === 'number')}
				<span class="font-normal text-gray-400">
					({p.min_value ?? '−∞'}–{p.max_value ?? '∞'})
				</span>
			{/if}
		</label>

		{#if p.type === 'int' || p.type === 'float'}
			<input
				id={inputId}
				type="number"
				min={p.min_value ?? undefined}
				max={p.max_value ?? undefined}
				step={p.type === 'float' ? 'any' : '1'}
				value={values[p.name] ?? ''}
				oninput={(e) => onNumberInput(p, e)}
				class="block w-full rounded-md border px-2 py-1 text-sm sm:w-40 {hasError
					? 'border-red-500'
					: 'border-gray-300'}"
			/>
		{:else if p.type === 'bool'}
			<input
				id={inputId}
				type="checkbox"
				checked={!!values[p.name]}
				onchange={(e) => onBoolInput(p, e)}
				class="h-4 w-4 rounded border-gray-300"
			/>
		{:else if p.type === 'enum' && Array.isArray(p.choices)}
			<select
				id={inputId}
				value={values[p.name] ?? ''}
				onchange={(e) => onSelectInput(p, e)}
				class="block w-full rounded-md border px-2 py-1 text-sm sm:w-auto {hasError
					? 'border-red-500'
					: 'border-gray-300'}"
			>
				{#each p.choices as choice (choice)}
					<option value={choice}>{choice}</option>
				{/each}
			</select>
		{:else}
			<input
				id={inputId}
				type="text"
				value={values[p.name] ?? ''}
				oninput={(e) => onTextInput(p, e)}
				class="block w-full rounded-md border px-2 py-1 text-sm sm:flex-1 {hasError
					? 'border-red-500'
					: 'border-gray-300'}"
			/>
		{/if}

		{#if p.description}
			<span class="grow text-xs text-gray-500 sm:text-right">{p.description}</span>
		{/if}
	</div>
	{#if hasError}
		<p class="text-xs text-red-600 sm:pl-[33%]" role="alert">{errors[p.name]}</p>
	{/if}
{/snippet}

{#if visibleParams.length > 0}
	<div class="space-y-2">
		{#each basicParams as p (p.name)}
			{@render field(p)}
		{/each}

		{#if advancedParams.length > 0}
			{#if collapseAdvanced}
				<details class="rounded-md border border-gray-200 bg-white">
					<summary
						class="cursor-pointer px-3 py-2 text-xs font-medium text-[#2271b3] select-none hover:underline"
					>
						{$_('plugins.params.advancedLabel', { default: 'Advanced parameters' })}
					</summary>
					<div class="space-y-2 p-3">
						{#each advancedParams as p (p.name)}
							{@render field(p)}
						{/each}
					</div>
				</details>
			{:else}
				{#each advancedParams as p (p.name)}
					{@render field(p)}
				{/each}
			{/if}
		{/if}
	</div>
{/if}
