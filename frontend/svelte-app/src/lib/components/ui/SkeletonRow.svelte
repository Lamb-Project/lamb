<script>
	import Skeleton from './Skeleton.svelte';

	/**
	 * A horizontal row of N skeleton "columns" — convenient for table-like
	 * placeholders.
	 *
	 * @typedef {Object} SkeletonRowProps
	 * @property {number} [columns]
	 * @property {string} [class]
	 */

	/** @type {SkeletonRowProps} */
	let { columns = 4, class: klass = '' } = $props();
	const colKeys = $derived(Array.from({ length: columns }, (_v, i) => i));
</script>

<div class="flex items-center gap-3 {klass}">
	{#each colKeys as i (i)}
		<Skeleton variant="text" class="flex-1" />
	{/each}
</div>
