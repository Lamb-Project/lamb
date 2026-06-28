<script>
	import { Info, AlertTriangle, AlertCircle, CheckCircle2 } from 'lucide-svelte';

	/**
	 * Banner / inline alert primitive.
	 *
	 * Variants: info | warning | danger | success
	 * Sizes: sm | md
	 *
	 * Leading icon is always the canonical intent icon for the variant
	 * (override via `icon` prop). Optional `actions` snippet renders at
	 * the right of the banner (e.g., a Retry Button).
	 */

	/**
	 * @typedef {Object} BannerProps
	 * @property {'info'|'warning'|'danger'|'success'} [variant]
	 * @property {'sm'|'md'} [size]
	 * @property {string} [title]
	 * @property {string} [description]
	 * @property {any} [icon]
	 * @property {string} [class]
	 * @property {import('svelte').Snippet} [actions]
	 * @property {import('svelte').Snippet} [children]
	 */

	/** @type {BannerProps} */
	let {
		variant = 'info',
		size = 'md',
		title,
		description,
		icon,
		class: klass = '',
		actions,
		children
	} = $props();

	const DEFAULT_ICON = {
		info: Info,
		warning: AlertTriangle,
		danger: AlertCircle,
		success: CheckCircle2
	};

	const VARIANTS = {
		info: 'bg-info-subtle border-info-border text-info-text',
		warning: 'bg-warning-subtle border-warning-border text-warning-text',
		danger: 'bg-danger-subtle border-danger-border text-danger-text',
		success: 'bg-success-subtle border-success-border text-success-text'
	};

	const ICON_COLOR = {
		info: 'text-info',
		warning: 'text-warning',
		danger: 'text-danger',
		success: 'text-success'
	};

	const PAD = size === 'sm' ? 'px-3 py-2' : 'px-4 py-3';
	const IconCmp = $derived(icon || DEFAULT_ICON[variant] || Info);

	const role = $derived(variant === 'danger' ? 'alert' : 'status');
</script>

<div
	{role}
	class="flex items-start gap-3 rounded-md border {PAD} {VARIANTS[variant] ||
		VARIANTS.info} {klass}"
>
	<IconCmp
		size={16}
		class="mt-0.5 shrink-0 {ICON_COLOR[variant] || ICON_COLOR.info}"
		aria-hidden="true"
	/>
	<div class="min-w-0 flex-1">
		{#if title}
			<p class="text-sm font-medium">{title}</p>
		{/if}
		{#if description}
			<p class="text-sm {title ? 'mt-0.5' : ''}">{description}</p>
		{/if}
		{#if children}
			<div class="text-sm">{@render children()}</div>
		{/if}
	</div>
	{#if actions}
		<div class="shrink-0">{@render actions()}</div>
	{/if}
</div>
