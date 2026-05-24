<script>
	import { MoreHorizontal } from 'lucide-svelte';
	import IconButton from './IconButton.svelte';
	import Dropdown from './Dropdown.svelte';

	/**
	 * Opinionated 3-dots overflow menu.
	 *
	 * Wraps `Dropdown` with a canonical trigger: `IconButton(MoreHorizontal,
	 * ghost, sm)`. Pre-set `placement="bottom-end"` so the menu opens to the
	 * left of its trigger (so it doesn't get clipped at the right edge of a
	 * table row).
	 *
	 * Items take the shape:
	 *   { label, onClick, icon?, danger?, disabled?, divider? }
	 *
	 * A divider item is rendered as a thin `border-t` line instead of a row.
	 *
	 * `ariaLabel` defaults to "More actions" — override per the i18n key
	 * `list.moreActions` at call sites.
	 */

	/**
	 * @typedef {Object} MenuItem
	 * @property {string} [label]
	 * @property {() => void} [onClick]
	 * @property {any} [icon]
	 * @property {boolean} [danger]
	 * @property {boolean} [disabled]
	 * @property {boolean} [divider]
	 */

	/**
	 * @typedef {Object} OverflowMenuProps
	 * @property {MenuItem[]} items
	 * @property {string} [ariaLabel]
	 * @property {string} [tooltip]
	 * @property {'sm'|'md'|'lg'} [size]
	 * @property {boolean} [inModal]
	 * @property {string} [class]
	 */

	/** @type {OverflowMenuProps} */
	let {
		items = [],
		ariaLabel = 'More actions',
		tooltip,
		size = 'sm',
		inModal = false,
		class: klass = ''
	} = $props();

	let open = $state(false);
	/** @type {HTMLElement | null} */
	let triggerEl = $state(null);

	function toggle() {
		open = !open;
	}

	/** @param {MenuItem} item @param {() => void} close */
	function handleItem(item, close) {
		if (item.disabled) return;
		try {
			item.onClick?.();
		} finally {
			close();
		}
	}
</script>

<span bind:this={triggerEl} class="inline-flex {klass}">
	<IconButton
		icon={MoreHorizontal}
		{ariaLabel}
		tooltip={tooltip ?? ariaLabel}
		variant="ghost"
		{size}
		{inModal}
		tooltipPlacement="top-end"
		onclick={toggle}
	/>
</span>

<Dropdown
	{open}
	anchor={triggerEl}
	placement="bottom-end"
	minWidth={180}
	onclose={() => (open = false)}
>
	{#snippet children({ close })}
		<div class="py-1">
			{#each items as item, i (i)}
				{#if item.divider}
					<div class="border-border my-1 border-t"></div>
				{:else}
					{@const Icon = item.icon}
					<button
						type="button"
						role="menuitem"
						disabled={item.disabled}
						onclick={() => handleItem(item, close)}
						class="flex w-full items-center gap-2 px-3 py-2 text-sm transition-colors disabled:cursor-not-allowed disabled:opacity-50 {item.danger
							? 'text-danger hover:bg-danger-subtle focus-visible:bg-danger-subtle'
							: 'text-text hover:bg-surface-sunken focus-visible:bg-surface-sunken'} focus:outline-none"
					>
						{#if Icon}
							<Icon size={14} aria-hidden="true" />
						{/if}
						<span>{item.label}</span>
					</button>
				{/if}
			{/each}
		</div>
	{/snippet}
</Dropdown>
