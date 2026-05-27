<script>
	/**
	 * Canonical Tabs primitive — underline pattern, brand active color.
	 *
	 * Props:
	 *  - `tabs`: array of `{ value, label, icon?, badge?, disabled? }`
	 *  - `value` ($bindable): current active value
	 *  - `onchange`: optional callback `(value) => void`
	 *
	 * The control is purely visual — content panels live outside and switch
	 * on `value`. Always rendered with `role="tablist"`; consumers should mark
	 * their panel containers with `role="tabpanel"`.
	 */

	/**
	 * @typedef {Object} TabItem
	 * @property {string} value
	 * @property {string} label
	 * @property {any} [icon]
	 * @property {string|number} [badge]
	 * @property {boolean} [disabled]
	 */

	/**
	 * @typedef {Object} TabsProps
	 * @property {TabItem[]} tabs
	 * @property {string} value
	 * @property {(v: string) => void} [onchange]
	 * @property {string} [class]
	 * @property {string} [ariaLabel]
	 */

	/** @type {TabsProps} */
	let { tabs = [], value = $bindable(''), onchange, class: klass = '', ariaLabel } = $props();

	/** @param {string} v */
	function select(v) {
		if (v === value) return;
		value = v;
		if (typeof onchange === 'function') onchange(v);
	}

	/** @param {KeyboardEvent} e @param {number} idx */
	function onKey(e, idx) {
		if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
		e.preventDefault();
		const dir = e.key === 'ArrowRight' ? 1 : -1;
		let i = idx;
		for (let step = 0; step < tabs.length; step++) {
			i = (i + dir + tabs.length) % tabs.length;
			if (!tabs[i].disabled) {
				select(tabs[i].value);
				const next = document.getElementById(`tab-${tabs[i].value}`);
				next?.focus();
				return;
			}
		}
	}
</script>

<div
	role="tablist"
	aria-label={ariaLabel}
	class="border-border flex items-center gap-1 border-b {klass}"
>
	{#each tabs as tab, i (tab.value)}
		{@const Icon = tab.icon}
		{@const active = tab.value === value}
		<button
			id={`tab-${tab.value}`}
			role="tab"
			type="button"
			aria-selected={active}
			tabindex={active ? 0 : -1}
			disabled={tab.disabled}
			onclick={() => !tab.disabled && select(tab.value)}
			onkeydown={(e) => onKey(e, i)}
			class="-mb-px inline-flex items-center gap-2 border-b-2 px-3 py-2 text-sm font-medium transition-colors duration-[120ms] focus:outline-none focus-visible:shadow-[var(--shadow-focus)] disabled:cursor-not-allowed disabled:opacity-50 {active
				? 'border-brand text-brand'
				: 'text-text-muted hover:text-text border-transparent'}"
		>
			{#if Icon}
				<Icon size={14} aria-hidden="true" />
			{/if}
			<span>{tab.label}</span>
			{#if tab.badge !== undefined && tab.badge !== null && tab.badge !== ''}
				<span
					class="rounded-pill bg-surface-sunken text-text-muted ml-1 inline-flex h-5 min-w-[1.25rem] items-center justify-center px-1.5 text-xs font-medium"
				>
					{tab.badge}
				</span>
			{/if}
		</button>
	{/each}
</div>
