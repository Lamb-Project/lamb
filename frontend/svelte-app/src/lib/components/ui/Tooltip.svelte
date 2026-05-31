<script>
	/**
	 * Tooltip primitive.
	 *
	 * Wraps any element and renders a small popover on hover/focus. Sets
	 * `aria-describedby` on the wrapped content. 200ms enter delay; immediate
	 * exit.
	 *
	 * Usage:
	 * ```svelte
	 * <Tooltip text="Delete">
	 *   <button>...</button>
	 * </Tooltip>
	 * ```
	 *
	 * Inside modals: pass `inModal` so the panel uses a higher z-index so it
	 * floats above the modal's z-50 backdrop/panel.
	 */

	/**
	 * @typedef {Object} TooltipProps
	 * @property {string} text
	 * @property {'top'|'top-end'|'bottom'|'left'|'right'} [placement]
	 * @property {number} [delay] ms; default 200
	 * @property {boolean} [inModal]
	 * @property {string} [class] optional outer class
	 * @property {import('svelte').Snippet} [children]
	 */

	/** @type {TooltipProps} */
	let {
		text,
		placement = 'top',
		delay = 200,
		inModal = false,
		class: klass = '',
		children
	} = $props();

	let open = $state(false);
	let mounted = $state(false);
	/** @type {ReturnType<typeof setTimeout> | null} */
	let timer = null;
	const id = `tt-${Math.random().toString(36).slice(2, 9)}`;

	function show() {
		if (!text) return;
		if (timer) clearTimeout(timer);
		timer = setTimeout(() => {
			mounted = true;
			open = true;
		}, delay);
	}

	function hide() {
		if (timer) {
			clearTimeout(timer);
			timer = null;
		}
		open = false;
		// Allow exit animation room (not strictly needed without transitions).
		setTimeout(() => (mounted = false), 120);
	}

	const placementClass = $derived(
		{
			top: 'bottom-full left-1/2 -translate-x-1/2 mb-2',
			// Right-anchored top placement — used when the trigger sits near the
			// right viewport edge (e.g. row-end overflow menus) so the tooltip
			// extends up-left from the trigger instead of overflowing offscreen.
			'top-end': 'bottom-full right-0 mb-2',
			bottom: 'top-full left-1/2 -translate-x-1/2 mt-2',
			left: 'right-full top-1/2 -translate-y-1/2 mr-2',
			right: 'left-full top-1/2 -translate-y-1/2 ml-2'
		}[placement]
	);

	const zClass = $derived(inModal ? 'z-[60]' : 'z-50');
</script>

<span
	class="relative inline-flex {klass}"
	onmouseenter={show}
	onmouseleave={hide}
	onfocusin={show}
	onfocusout={hide}
	role="presentation"
>
	<span aria-describedby={open && text ? id : undefined} class="contents">
		{@render children?.()}
	</span>
	{#if mounted && text}
		<span
			role="tooltip"
			{id}
			class="pointer-events-none absolute {placementClass} {zClass} shadow-popover rounded-md bg-gray-900 px-2 py-1 text-xs whitespace-nowrap text-white transition-opacity duration-150 ease-out"
			style:opacity={open ? '1' : '0'}
		>
			{text}
		</span>
	{/if}
</span>
