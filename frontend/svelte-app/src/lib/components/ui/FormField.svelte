<script>
	import { AlertCircle } from 'lucide-svelte';

	/**
	 * FormField primitive — label + input + helper + error.
	 *
	 * `type`:
	 *   text | textarea | number | select | url | search | checkbox | password | email
	 *
	 * For `select`, pass `options: [{ value, label, disabled? }]`.
	 *
	 * `validateOnBlur` is an optional `(value) => string | undefined` —
	 * returning a non-empty string sets the inline error message after the
	 * field loses focus. Passing `error` directly overrides it.
	 *
	 * `leadingIcon` / `trailingIcon` render fixed icons inside the input on
	 * either side (text variants only).
	 *
	 * Canonical input class is the same across all variants so they look
	 * identical anywhere in the app.
	 */

	/**
	 * @typedef {Object} SelectOption
	 * @property {string|number} value
	 * @property {string} label
	 * @property {boolean} [disabled]
	 */

	/**
	 * @typedef {Object} FormFieldProps
	 * @property {string} [label]
	 * @property {string} [id]
	 * @property {string} [name]
	 * @property {string} [type]
	 * @property {*} [value]
	 * @property {boolean} [checked]   for checkbox
	 * @property {string} [placeholder]
	 * @property {string} [helper]
	 * @property {string} [error]
	 * @property {boolean} [required]
	 * @property {boolean} [disabled]
	 * @property {boolean} [readonly]
	 * @property {number} [rows]       textarea rows
	 * @property {number|string} [min]
	 * @property {number|string} [max]
	 * @property {number|string} [step]
	 * @property {string} [autocomplete]
	 * @property {string} [pattern]
	 * @property {SelectOption[]} [options]   for select
	 * @property {(v: any) => string | undefined} [validateOnBlur]
	 * @property {any} [leadingIcon]
	 * @property {any} [trailingIcon]
	 * @property {string} [class]
	 * @property {string} [inputClass]
	 * @property {(e: Event) => void} [oninput]
	 * @property {(e: Event) => void} [onchange]
	 * @property {(e: FocusEvent) => void} [onblur]
	 * @property {(e: FocusEvent) => void} [onfocus]
	 * @property {(e: KeyboardEvent) => void} [onkeydown]
	 */

	/** @type {FormFieldProps & Record<string, any>} */
	let {
		label,
		id,
		name,
		type = 'text',
		value = $bindable(''),
		checked = $bindable(false),
		placeholder,
		helper,
		error,
		required = false,
		disabled = false,
		readonly = false,
		rows = 3,
		min,
		max,
		step,
		autocomplete,
		pattern,
		options = [],
		validateOnBlur,
		leadingIcon,
		trailingIcon,
		class: klass = '',
		inputClass = '',
		oninput,
		onchange,
		onblur,
		onfocus,
		onkeydown,
		...rest
	} = $props();

	const fallbackId = `ff-${Math.random().toString(36).slice(2, 9)}`;
	const fid = $derived(id || fallbackId);
	const autoComplete = /** @type {AutoFill | undefined} */ (autocomplete);
	let localError = $state('');
	const shownError = $derived(error || localError);
	const helperId = $derived(helper ? `${fid}-helper` : undefined);
	const errorId = $derived(shownError ? `${fid}-error` : undefined);
	const describedBy = $derived([helperId, errorId].filter(Boolean).join(' ') || undefined);

	const INPUT_BASE =
		'w-full rounded-md border border-border-strong bg-surface px-3 py-2 text-sm text-text placeholder:text-text-subtle focus:border-brand focus:outline-none focus-visible:shadow-[var(--shadow-focus)] disabled:bg-surface-sunken disabled:text-text-disabled';
	const ERR_RING = $derived(
		shownError
			? 'border-danger focus:border-danger focus-visible:shadow-[var(--shadow-focus-danger)]'
			: ''
	);
	const LeadingCmp = $derived(leadingIcon);
	const TrailingCmp = $derived(trailingIcon);
	const hasLeading = $derived(
		Boolean(LeadingCmp) && type !== 'checkbox' && type !== 'select' && type !== 'textarea'
	);
	const hasTrailing = $derived(
		Boolean(TrailingCmp) && type !== 'checkbox' && type !== 'select' && type !== 'textarea'
	);
	const paddingClass = $derived(`${hasLeading ? 'pl-9' : ''} ${hasTrailing ? 'pr-9' : ''}`);

	/** @param {FocusEvent} e */
	function runBlur(e) {
		if (typeof validateOnBlur === 'function') {
			try {
				const v = type === 'checkbox' ? checked : value;
				const msg = validateOnBlur(v);
				localError = msg && typeof msg === 'string' ? msg : '';
			} catch {
				localError = '';
			}
		}
		if (typeof onblur === 'function') onblur(e);
	}
</script>

<div class={klass}>
	{#if label && type !== 'checkbox'}
		<label for={fid} class="text-text mb-1 block text-sm font-medium">
			{label}{#if required}<span class="text-danger ml-0.5" aria-hidden="true">*</span>{/if}
		</label>
	{/if}

	{#if type === 'checkbox'}
		<label class="text-text inline-flex items-start gap-2 text-sm" for={fid}>
			<input
				id={fid}
				{name}
				type="checkbox"
				bind:checked
				{disabled}
				{readonly}
				aria-describedby={describedBy}
				aria-invalid={shownError ? 'true' : undefined}
				class="border-border-strong text-brand focus:ring-brand mt-0.5 h-4 w-4 rounded"
				{oninput}
				{onchange}
				onblur={runBlur}
				{onfocus}
				{onkeydown}
				{...rest}
			/>
			<span>
				{label}{#if required}<span class="text-danger ml-0.5" aria-hidden="true">*</span>{/if}
				{#if helper}
					<span id={helperId} class="text-text-muted block text-xs">{helper}</span>
				{/if}
			</span>
		</label>
	{:else if type === 'textarea'}
		<textarea
			id={fid}
			{name}
			bind:value
			{placeholder}
			{required}
			{disabled}
			{readonly}
			{rows}
			aria-describedby={describedBy}
			aria-invalid={shownError ? 'true' : undefined}
			class="{INPUT_BASE} {ERR_RING} {inputClass} resize-y"
			{oninput}
			{onchange}
			onblur={runBlur}
			{onfocus}
			{onkeydown}
			{...rest}
		></textarea>
	{:else if type === 'select'}
		<select
			id={fid}
			{name}
			bind:value
			{required}
			{disabled}
			aria-describedby={describedBy}
			aria-invalid={shownError ? 'true' : undefined}
			class="{INPUT_BASE} {ERR_RING} {inputClass} pr-8"
			{onchange}
			onblur={runBlur}
			{onfocus}
			{onkeydown}
			{...rest}
		>
			{#each options as opt (opt.value)}
				<option value={opt.value} disabled={opt.disabled}>{opt.label}</option>
			{/each}
		</select>
	{:else}
		<div class="relative">
			{#if hasLeading}
				<span
					class="text-text-subtle pointer-events-none absolute inset-y-0 left-0 flex items-center pl-2"
				>
					<LeadingCmp size={16} aria-hidden="true" />
				</span>
			{/if}
			<input
				id={fid}
				{name}
				{type}
				bind:value
				{placeholder}
				{required}
				{disabled}
				{readonly}
				{min}
				{max}
				{step}
				autocomplete={autoComplete}
				{pattern}
				aria-describedby={describedBy}
				aria-invalid={shownError ? 'true' : undefined}
				class="{INPUT_BASE} {ERR_RING} {inputClass} {paddingClass}"
				{oninput}
				{onchange}
				onblur={runBlur}
				{onfocus}
				{onkeydown}
				{...rest}
			/>
			{#if hasTrailing}
				<span
					class="text-text-subtle pointer-events-none absolute inset-y-0 right-0 flex items-center pr-2"
				>
					<TrailingCmp size={16} aria-hidden="true" />
				</span>
			{/if}
		</div>
	{/if}

	{#if helper && type !== 'checkbox' && !shownError}
		<p id={helperId} class="text-text-muted mt-1 text-xs">{helper}</p>
	{/if}
	{#if shownError}
		<p id={errorId} role="alert" class="text-danger mt-1 inline-flex items-center gap-1 text-xs">
			<AlertCircle size={12} aria-hidden="true" />
			<span>{shownError}</span>
		</p>
	{/if}
</div>
