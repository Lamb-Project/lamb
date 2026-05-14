<!--
  @component SimpleTable
  Wraps a <table> with column headers defined by the `columns` prop.
  Body rows are rendered via the default slot/snippet.

  API:
    <ResizableTable tableId="libraries" columns={[{key, label, defaultWidth}]}>
      <tbody>...</tbody>
    </ResizableTable>
-->
<script>
	/** @type {{ tableId: string, columns: Array<{key: string, label: string, defaultWidth: number, align?: 'left'|'right'|'center'}>, children?: import('svelte').Snippet }} */
	let { columns, children } = $props();

	export function resetColumnWidths() {}

	/** @param {{defaultWidth: number, align?: string}} col */
	function thStyle(col) {
		const parts = [];
		if (col.defaultWidth) parts.push(`width: ${col.defaultWidth}px`);
		parts.push(`text-align: ${col.align ?? 'left'}`);
		return parts.join('; ');
	}
</script>

<div class="overflow-x-auto">
	<table class="w-full divide-y divide-gray-200" style="table-layout: fixed;">
		<thead class="bg-gray-50">
			<tr>
				{#each columns as col (col.key)}
					<th
						aria-label={col.label}
						class="overflow-hidden px-4 py-2.5 text-xs font-medium text-gray-500 uppercase"
						style:width={col.defaultWidth ? `${col.defaultWidth}px` : null}
						style:text-align={col.align ?? 'left'}
					>
						{col.label}
					</th>
				{/each}
			</tr>
		</thead>

		{@render children?.()}
	</table>
</div>
