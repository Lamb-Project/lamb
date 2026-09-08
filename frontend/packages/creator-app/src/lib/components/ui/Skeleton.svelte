<script>
	/**
	 * Skeleton placeholder with shimmer animation.
	 *
	 * Variants: text | circle | rect
	 *
	 * Composed helpers below for the common cases (Row, Card, Table) — these
	 * are NOT static methods because Svelte 5 components are functions, not
	 * classes. Import them as `Skeleton, SkeletonRow, SkeletonCard, SkeletonTable`
	 * from `$lib/components/ui` and use whichever fits.
	 *
	 * Why a shimmer instead of `animate-pulse`? Shimmer reads as "data is on
	 * the way" rather than "this thing is broken." It also matches the rest
	 * of the design system (top-down sweep, brand-neutral hue).
	 */

	/**
	 * @typedef {Object} SkeletonProps
	 * @property {'text'|'circle'|'rect'} [variant]
	 * @property {string} [width]  CSS width (e.g. '60%', '12rem')
	 * @property {string} [height] CSS height (defaults to 1em for text)
	 * @property {string} [class]
	 */

	/** @type {SkeletonProps} */
	let { variant = 'rect', width, height, class: klass = '' } = $props();

	const SHAPE = {
		text: 'rounded',
		rect: 'rounded-md',
		circle: 'rounded-full'
	};

	const defaultHeight = $derived(
		height ?? (variant === 'circle' ? width || '2rem' : variant === 'text' ? '0.85em' : '1rem')
	);

	const defaultWidth = $derived(
		width ?? (variant === 'circle' ? height || '2rem' : variant === 'text' ? '100%' : '100%')
	);
</script>

<span
	class="bg-surface-sunken relative inline-block overflow-hidden {SHAPE[variant]} {klass}"
	style:width={defaultWidth}
	style:height={defaultHeight}
	aria-hidden="true"
>
	<span
		class="absolute inset-0"
		style="background: linear-gradient(90deg, transparent, rgba(255,255,255,0.6), transparent); animation: shimmer 1.4s infinite;"
	></span>
</span>
