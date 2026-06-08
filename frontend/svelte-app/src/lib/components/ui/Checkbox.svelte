<script>
	/**
	 * Styled checkbox primitive.
	 *
	 * Renders a native `<input type="checkbox">` styled with the brand
	 * tokens. Pair with a `label` for the visible text — pass `label` for a
	 * convenience inline label or wrap externally.
	 */

	/**
	 * @typedef {Object} CheckboxProps
	 * @property {boolean} [checked]
	 * @property {boolean} [indeterminate]
	 * @property {boolean} [disabled]
	 * @property {string} [label]
	 * @property {string} [description]
	 * @property {string} [id]
	 * @property {string} [name]
	 * @property {string} [value]
	 * @property {string} [class]
	 * @property {(e: Event) => void} [onchange]
	 * @property {string} [ariaLabel]
	 */

	/** @type {CheckboxProps & Record<string, any>} */
	let {
		checked = $bindable(false),
		indeterminate = false,
		disabled = false,
		label,
		description,
		id,
		name,
		value,
		class: klass = '',
		onchange,
		ariaLabel,
		...rest
	} = $props();

	const cid = id || `cb-${Math.random().toString(36).slice(2, 9)}`;

	/** @type {HTMLInputElement | undefined} */
	let inputEl;
	$effect(() => {
		if (inputEl) inputEl.indeterminate = !!indeterminate;
	});
</script>

<label class="inline-flex items-start gap-2 {klass}" for={cid}>
	<input
		bind:this={inputEl}
		id={cid}
		{name}
		{value}
		type="checkbox"
		bind:checked
		{disabled}
		aria-label={ariaLabel}
		class="border-border-strong text-brand focus:ring-brand mt-0.5 h-4 w-4 rounded focus:ring-offset-0 disabled:opacity-50"
		{onchange}
		{...rest}
	/>
	{#if label || description}
		<span class="select-none">
			{#if label}
				<span class="text-text block text-sm {disabled ? 'text-text-disabled' : ''}">{label}</span>
			{/if}
			{#if description}
				<span class="text-text-muted block text-xs">{description}</span>
			{/if}
		</span>
	{/if}
</label>
