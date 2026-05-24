<script>
	import { slide } from 'svelte/transition';
	import { cubicInOut } from 'svelte/easing';
	import { ChevronDown } from 'lucide-svelte';

	/**
	 * Collapsible disclosure — chevron + label header that expands a body.
	 *
	 * Replaces ad-hoc `<details>/<summary>` usages.
	 */

	/**
	 * @typedef {Object} CollapsibleProps
	 * @property {string} [label]
	 * @property {string} [description]
	 * @property {boolean} [open]
	 * @property {(open: boolean) => void} [onopenchange]
	 * @property {string} [class]
	 * @property {string} [bodyClass]
	 * @property {boolean} [bordered]
	 * @property {import('svelte').Snippet} [header]
	 * @property {import('svelte').Snippet} [children]
	 */

	/** @type {CollapsibleProps} */
	let {
		label,
		description,
		open = $bindable(false),
		onopenchange,
		class: klass = '',
		bodyClass = 'px-4 pb-4',
		bordered = true,
		header,
		children
	} = $props();

	function toggle() {
		open = !open;
		if (typeof onopenchange === 'function') onopenchange(open);
	}

	const shell = $derived(bordered ? 'rounded-md border border-border bg-surface' : '');
</script>

<div class="{shell} {klass}">
	<button
		type="button"
		class="flex w-full items-center justify-between gap-2 rounded-md px-4 py-3 text-left focus:outline-none focus-visible:shadow-[var(--shadow-focus)]"
		aria-expanded={open}
		onclick={toggle}
	>
		{#if header}
			<span class="min-w-0 flex-1">{@render header()}</span>
		{:else}
			<span class="min-w-0 flex-1">
				{#if label}<span class="text-text block text-sm font-medium">{label}</span>{/if}
				{#if description}<span class="text-text-muted block text-xs">{description}</span>{/if}
			</span>
		{/if}
		<ChevronDown
			size={16}
			class="text-text-muted shrink-0 transition-transform duration-300 {open ? 'rotate-180' : ''}"
			aria-hidden="true"
		/>
	</button>
	{#if open}
		<div transition:slide={{ duration: 420, easing: cubicInOut, axis: 'y' }} class={bodyClass}>
			{@render children?.()}
		</div>
	{/if}
</div>
