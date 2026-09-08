<script>
	/* eslint-disable svelte/no-navigation-without-resolve */
	import Tooltip from './Tooltip.svelte';
	import { Loader2 } from 'lucide-svelte';

	/**
	 * Square icon-only button. Always renders a Tooltip. Always requires
	 * an `ariaLabel` (the `title=` attribute is forbidden — pass `tooltip`).
	 *
	 * Variants: primary | secondary | ghost | danger | danger-ghost
	 * Sizes: xs | sm | md | lg
	 *
	 * `icon` is the lucide component to render (mandatory). For loading states
	 * pass `loading=true` and the icon will swap to `Loader2`.
	 */

	/**
	 * @typedef {Object} IconButtonProps
	 * @property {any} icon
	 * @property {string} ariaLabel
	 * @property {string} [tooltip] (defaults to ariaLabel)
	 * @property {'primary'|'secondary'|'ghost'|'danger'|'danger-ghost'} [variant]
	 * @property {'xs'|'sm'|'md'|'lg'} [size]
	 * @property {'button'|'submit'|'reset'} [type]
	 * @property {boolean} [disabled]
	 * @property {boolean} [loading]
	 * @property {string} [href]
	 * @property {string} [target]
	 * @property {string} [rel]
	 * @property {'top'|'top-end'|'bottom'|'left'|'right'} [tooltipPlacement]
	 * @property {boolean} [inModal] use z-[60] for the tooltip (set inside modals)
	 * @property {string} [class]
	 * @property {number} [tabindex]
	 * @property {(e: MouseEvent) => void} [onclick]
	 */

	/** @type {IconButtonProps & Record<string, any>} */
	let {
		icon,
		ariaLabel,
		tooltip,
		variant = 'ghost',
		size = 'md',
		type = 'button',
		disabled = false,
		loading = false,
		href,
		target,
		rel,
		tooltipPlacement = 'top',
		inModal = false,
		class: klass = '',
		tabindex,
		onclick,
		...rest
	} = $props();

	// Dev-only warning if ariaLabel missing.
	$effect(() => {
		if (typeof window !== 'undefined' && import.meta.env?.DEV) {
			if (!ariaLabel || !ariaLabel.trim()) {
				console.warn(
					'[IconButton] `ariaLabel` is required for accessibility. Pass an i18n string.'
				);
			}
		}
	});

	const BASE =
		'inline-flex items-center justify-center rounded-md border transition-colors duration-[120ms] focus:outline-none focus-visible:shadow-[var(--shadow-focus)] disabled:cursor-not-allowed disabled:opacity-50';

	const VARIANTS = {
		primary:
			'bg-brand text-brand-fg border-transparent hover:bg-brand-hover active:bg-brand-active',
		secondary: 'bg-surface text-text border-border-strong hover:bg-surface-sunken',
		ghost: 'bg-transparent text-text border-transparent hover:bg-surface-sunken',
		danger:
			'bg-danger text-danger-fg border-transparent hover:bg-danger-hover focus-visible:shadow-[var(--shadow-focus-danger)]',
		'danger-ghost': 'bg-transparent text-danger border-transparent hover:bg-danger-subtle'
	};

	const SIZES = {
		xs: 'h-6 w-6',
		sm: 'h-7 w-7',
		md: 'h-8 w-8',
		lg: 'h-10 w-10'
	};

	const ICON_PX = { xs: 12, sm: 14, md: 16, lg: 20 };

	const computed = $derived(
		[BASE, VARIANTS[variant] || VARIANTS.ghost, SIZES[size] || SIZES.md, klass]
			.filter(Boolean)
			.join(' ')
	);

	const isDisabled = $derived(Boolean(disabled || loading));
	const ResolvedIcon = $derived(loading ? Loader2 : icon);
	const iconPx = $derived(ICON_PX[size] || 16);
	const ttText = $derived(tooltip ?? ariaLabel ?? '');
</script>

<Tooltip text={ttText} placement={tooltipPlacement} {inModal}>
	{#if href}
		<a
			{href}
			{target}
			{rel}
			role="button"
			aria-label={ariaLabel}
			aria-disabled={isDisabled || undefined}
			tabindex={isDisabled ? -1 : (tabindex ?? 0)}
			class={computed}
			onclick={isDisabled ? (e) => e.preventDefault() : onclick}
			{...rest}
		>
			{#if ResolvedIcon}
				<ResolvedIcon size={iconPx} class={loading ? 'animate-spin' : ''} aria-hidden="true" />
			{/if}
		</a>
	{:else}
		<button
			{type}
			aria-label={ariaLabel}
			disabled={isDisabled}
			{tabindex}
			class={computed}
			{onclick}
			{...rest}
		>
			{#if ResolvedIcon}
				<ResolvedIcon size={iconPx} class={loading ? 'animate-spin' : ''} aria-hidden="true" />
			{/if}
		</button>
	{/if}
</Tooltip>
