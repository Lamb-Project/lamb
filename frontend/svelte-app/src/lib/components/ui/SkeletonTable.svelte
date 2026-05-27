<script>
	import Skeleton from './Skeleton.svelte';

	/**
	 * Skeleton block shaped like a data table.
	 *
	 * @typedef {Object} SkeletonTableProps
	 * @property {number} [rows]
	 * @property {number} [columns]
	 * @property {string} [class]
	 */

	/** @type {SkeletonTableProps} */
	let { rows = 5, columns = 4, class: klass = '' } = $props();
	const rowKeys = $derived(Array.from({ length: rows }, (_v, i) => i));
	const colKeys = $derived(Array.from({ length: columns }, (_v, i) => i));
</script>

<div class="border-border bg-surface shadow-card overflow-hidden rounded-lg border {klass}">
	<!-- Header bar -->
	<div class="border-border bg-surface-muted flex items-center gap-3 border-b px-4 py-3">
		{#each colKeys as i (i)}
			<Skeleton variant="text" class="flex-1" height="0.75rem" />
		{/each}
	</div>
	<!-- Body rows -->
	<div>
		{#each rowKeys as r (r)}
			<div class="border-border flex items-center gap-3 border-b px-4 py-3 last:border-b-0">
				{#each colKeys as c (c)}
					<Skeleton variant="text" class="flex-1" />
				{/each}
			</div>
		{/each}
	</div>
</div>
