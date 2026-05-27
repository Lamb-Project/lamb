<script>
	/**
	 * Badge / pill primitive.
	 *
	 * Variants: neutral | success | warning | danger | info | brand
	 * Sizes: sm | md
	 *
	 * Optional `icon` (lucide component) and `dot` (small colored dot before
	 * the label). When `spin=true`, the icon spins (used for processing
	 * states with Loader2).
	 */

	/**
	 * @typedef {Object} BadgeProps
	 * @property {'neutral'|'success'|'warning'|'danger'|'info'|'brand'} [variant]
	 * @property {'sm'|'md'} [size]
	 * @property {any} [icon]
	 * @property {boolean} [dot]
	 * @property {boolean} [spin]
	 * @property {string} [class]
	 * @property {string} [title]
	 * @property {import('svelte').Snippet} [children]
	 */

	/** @type {BadgeProps & Record<string, any>} */
	let {
		variant = 'neutral',
		size = 'sm',
		icon,
		dot = false,
		spin = false,
		class: klass = '',
		title,
		children,
		...rest
	} = $props();

	const BASE = 'inline-flex items-center gap-1.5 rounded-pill font-medium border whitespace-nowrap';

	const VARIANTS = {
		neutral: 'bg-surface-sunken text-text-muted border-border',
		success: 'bg-success-subtle text-success-text border-success-border',
		warning: 'bg-warning-subtle text-warning-text border-warning-border',
		danger: 'bg-danger-subtle text-danger-text border-danger-border',
		info: 'bg-info-subtle text-info-text border-info-border',
		brand: 'bg-brand-subtle text-brand border-brand/30'
	};

	const DOT_COLORS = {
		neutral: 'bg-text-subtle',
		success: 'bg-success',
		warning: 'bg-warning',
		danger: 'bg-danger',
		info: 'bg-info',
		brand: 'bg-brand'
	};

	const SIZES = {
		sm: 'px-2 py-0.5 text-xs',
		md: 'px-2.5 py-1 text-xs'
	};

	const ICON_PX = { sm: 12, md: 14 };

	const computed = $derived(
		[BASE, VARIANTS[variant] || VARIANTS.neutral, SIZES[size] || SIZES.sm, klass]
			.filter(Boolean)
			.join(' ')
	);
	const dotClass = $derived(DOT_COLORS[variant] || DOT_COLORS.neutral);
	const iconPx = $derived(ICON_PX[size] || 12);
	const Icon = $derived(icon);
</script>

<span class={computed} {title} {...rest}>
	{#if dot}
		<span class="inline-block h-1.5 w-1.5 rounded-full {dotClass}" aria-hidden="true"></span>
	{/if}
	{#if Icon}
		<Icon size={iconPx} class={spin ? 'animate-spin' : ''} aria-hidden="true" />
	{/if}
	<span>{@render children?.()}</span>
</span>
