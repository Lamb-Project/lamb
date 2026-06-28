<script>
	/**
	 * EmptyState primitive — used in place of bespoke empty blocks.
	 *
	 * Sizes:
	 *  - `sm` for inline empties (inside a card, inside a tab pane).
	 *  - `md` for page-level empties.
	 *
	 * @typedef {Object} EmptyStateProps
	 * @property {any} [icon]
	 * @property {string} [title]
	 * @property {string} [description]
	 * @property {'sm'|'md'} [size]
	 * @property {string} [class]
	 * @property {import('svelte').Snippet} [actions]
	 * @property {import('svelte').Snippet} [children]
	 */

	/** @type {EmptyStateProps} */
	let { icon, title, description, size = 'md', class: klass = '', actions, children } = $props();

	const PAD = $derived(size === 'sm' ? 'py-6 px-4' : 'py-12 px-6');
	const ICON_PX = $derived(size === 'sm' ? 24 : 40);
	const Icon = $derived(icon);
</script>

<div
	class="flex flex-col items-center justify-center text-center {PAD} {klass}"
	role="status"
	aria-live="polite"
>
	{#if Icon}
		<div
			class="bg-surface-sunken mb-3 flex items-center justify-center rounded-full {size === 'sm'
				? 'h-10 w-10'
				: 'h-14 w-14'} text-text-subtle"
		>
			<Icon size={ICON_PX} aria-hidden="true" />
		</div>
	{/if}
	{#if title}
		<h3 class={size === 'sm' ? 'type-card-title' : 'type-section-title'}>{title}</h3>
	{/if}
	{#if description}
		<p class="type-body-muted mt-1 max-w-md">{description}</p>
	{/if}
	{#if children}
		<div class="mt-3">{@render children()}</div>
	{/if}
	{#if actions}
		<div class="mt-4 flex flex-wrap items-center justify-center gap-2">{@render actions()}</div>
	{/if}
</div>
