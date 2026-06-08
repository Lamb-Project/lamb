<script>
	import Skeleton from './Skeleton.svelte';

	/**
	 * Skeleton block shaped like a Card (title + a few text lines).
	 *
	 * @typedef {Object} SkeletonCardProps
	 * @property {number} [lines]
	 * @property {string} [class]
	 */

	/** @type {SkeletonCardProps} */
	let { lines = 3, class: klass = '' } = $props();
	const lineKeys = $derived(Array.from({ length: lines }, (_v, i) => i));
</script>

<div class="border-border bg-surface shadow-card rounded-lg border p-6 {klass}">
	<Skeleton variant="text" width="40%" height="1.25rem" class="mb-4 block" />
	<div class="space-y-3">
		{#each lineKeys as i (i)}
			<Skeleton variant="text" width={i === lines - 1 ? '60%' : '100%'} />
		{/each}
	</div>
</div>
