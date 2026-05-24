<script>
	/**
	 * Card primitive.
	 *
	 * Container with rounded corners, border, white background, and a subtle
	 * card shadow. Optionally renders a header with title + description and
	 * an `actions` snippet on the right.
	 *
	 * Body padding defaults to `p-6`. Pass `padded={false}` for raw children
	 * (e.g., when you want a table or list to bleed to the edges).
	 */

	/**
	 * @typedef {Object} CardProps
	 * @property {string} [title]
	 * @property {string} [description]
	 * @property {boolean} [padded]
	 * @property {boolean} [divided] adds a bottom border to the header
	 * @property {string} [class]
	 * @property {string} [bodyClass]
	 * @property {string} [headerClass]
	 * @property {import('svelte').Snippet} [actions]
	 * @property {import('svelte').Snippet} [header]
	 * @property {import('svelte').Snippet} [footer]
	 * @property {import('svelte').Snippet} [children]
	 */

	/** @type {CardProps} */
	let {
		title,
		description,
		padded = true,
		divided = true,
		class: klass = '',
		bodyClass = '',
		headerClass = '',
		actions,
		header,
		footer,
		children
	} = $props();

	const SHELL = 'rounded-lg border border-border bg-surface shadow-card';
	const hasHeader = $derived(Boolean(header) || Boolean(title) || Boolean(description));
	const bodyPadding = $derived(padded ? 'p-6' : '');
	const headerBorder = $derived(divided ? 'border-b border-border' : '');
</script>

<section class="{SHELL} {klass}">
	{#if hasHeader}
		<header class="flex items-start justify-between gap-4 px-6 py-4 {headerBorder} {headerClass}">
			{#if header}
				{@render header()}
			{:else}
				<div class="min-w-0 flex-1">
					{#if title}
						<h3 class="type-card-title truncate">{title}</h3>
					{/if}
					{#if description}
						<p class="type-body-muted mt-1">{description}</p>
					{/if}
				</div>
			{/if}
			{#if actions}
				<div class="flex shrink-0 items-center gap-2">{@render actions()}</div>
			{/if}
		</header>
	{/if}
	<div class="{bodyPadding} {bodyClass}">
		{@render children?.()}
	</div>
	{#if footer}
		<footer class="border-border bg-surface-muted border-t px-6 py-4">
			{@render footer()}
		</footer>
	{/if}
</section>
