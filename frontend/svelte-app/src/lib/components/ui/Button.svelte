<script>
	/* eslint-disable svelte/no-navigation-without-resolve */
	import { Loader2 } from 'lucide-svelte';

	/**
	 * Canonical Button primitive.
	 *
	 * Variants: primary | secondary | ghost | danger | danger-ghost
	 * Sizes: sm | md | lg
	 *
	 * Pass `iconLeft` / `iconRight` as snippets (or as a component via the
	 * `iconLeftComponent` / `iconRightComponent` props for the common case of
	 * "I just want a lucide icon left of the label").
	 *
	 * When `href` is set, renders `<a role="button">` instead of `<button>`.
	 *
	 * `loading=true` swaps the left icon for an animated `Loader2` and forces
	 * `disabled`.
	 */

	/**
	 * @typedef {Object} ButtonProps
	 * @property {'primary'|'secondary'|'ghost'|'danger'|'danger-ghost'} [variant]
	 * @property {'sm'|'md'|'lg'} [size]
	 * @property {'button'|'submit'|'reset'} [type]
	 * @property {boolean} [disabled]
	 * @property {boolean} [loading]
	 * @property {string} [href]
	 * @property {string} [target]
	 * @property {string} [rel]
	 * @property {string} [ariaLabel]
	 * @property {string} [title]
	 * @property {string} [class] additional classes appended to the computed class
	 * @property {(e: MouseEvent) => void} [onclick]
	 * @property {any} [iconLeftComponent]
	 * @property {any} [iconRightComponent]
	 * @property {import('svelte').Snippet} [iconLeft]
	 * @property {import('svelte').Snippet} [iconRight]
	 * @property {import('svelte').Snippet} [children]
	 * @property {boolean} [fullWidth]
	 */

	/** @type {ButtonProps & Record<string, any>} */
	let {
		variant = 'primary',
		size = 'md',
		type = 'button',
		disabled = false,
		loading = false,
		href,
		target,
		rel,
		ariaLabel,
		title,
		class: klass = '',
		onclick,
		iconLeftComponent,
		iconRightComponent,
		iconLeft,
		iconRight,
		children,
		fullWidth = false,
		...rest
	} = $props();

	const BASE =
		'inline-flex items-center justify-center gap-2 font-medium rounded-md border whitespace-nowrap transition-colors duration-[120ms] focus:outline-none focus-visible:shadow-[var(--shadow-focus)] disabled:cursor-not-allowed disabled:opacity-50';

	const VARIANTS = {
		primary:
			'bg-brand text-brand-fg border-transparent hover:bg-brand-hover active:bg-brand-active',
		secondary: 'bg-surface text-text border-border-strong hover:bg-surface-sunken',
		ghost: 'bg-transparent text-text border-transparent hover:bg-surface-sunken',
		danger:
			'bg-danger text-danger-fg border-transparent hover:bg-danger-hover active:bg-danger-active focus-visible:shadow-[var(--shadow-focus-danger)]',
		'danger-ghost': 'bg-transparent text-danger border-transparent hover:bg-danger-subtle'
	};

	const SIZES = {
		sm: 'px-2.5 py-1.5 text-xs',
		md: 'px-3.5 py-2 text-sm',
		lg: 'px-4 py-2.5 text-base'
	};

	const ICON_SIZE = { sm: 14, md: 16, lg: 18 };

	const computed = $derived(
		[
			BASE,
			VARIANTS[variant] || VARIANTS.primary,
			SIZES[size] || SIZES.md,
			fullWidth ? 'w-full' : '',
			klass
		]
			.filter(Boolean)
			.join(' ')
	);

	const isDisabled = $derived(Boolean(disabled || loading));
	const LeftCmp = $derived(loading ? Loader2 : iconLeftComponent);
	const RightCmp = $derived(iconRightComponent);
	const iconPx = $derived(ICON_SIZE[size] || 16);
</script>

{#if href}
	<a
		{href}
		{target}
		{rel}
		role="button"
		aria-label={ariaLabel}
		aria-disabled={isDisabled || undefined}
		tabindex={isDisabled ? -1 : 0}
		{title}
		class={computed}
		onclick={isDisabled ? (e) => e.preventDefault() : onclick}
		{...rest}
	>
		{#if LeftCmp}
			<LeftCmp size={iconPx} class={loading ? 'animate-spin' : ''} aria-hidden="true" />
		{:else if iconLeft}
			{@render iconLeft()}
		{/if}
		{@render children?.()}
		{#if RightCmp}
			<RightCmp size={iconPx} aria-hidden="true" />
		{:else if iconRight}
			{@render iconRight()}
		{/if}
	</a>
{:else}
	<button
		{type}
		aria-label={ariaLabel}
		disabled={isDisabled}
		{title}
		class={computed}
		{onclick}
		{...rest}
	>
		{#if LeftCmp}
			<LeftCmp size={iconPx} class={loading ? 'animate-spin' : ''} aria-hidden="true" />
		{:else if iconLeft}
			{@render iconLeft()}
		{/if}
		{@render children?.()}
		{#if RightCmp}
			<RightCmp size={iconPx} aria-hidden="true" />
		{:else if iconRight}
			{@render iconRight()}
		{/if}
	</button>
{/if}
