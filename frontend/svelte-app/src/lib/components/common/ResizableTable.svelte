<!--
  @component ResizableTable
  Wraps a <table> with per-column drag handles on <th> right borders.
  Total table width is fixed to the container — resizing column N shrinks column N+1.
  Column widths persist to localStorage keyed by tableId.

  API:
    <ResizableTable tableId="libraries" columns={[{key, label, defaultWidth}]}>
      {#snippet head()}<tr>...</tr>{/snippet}
      {#snippet body()}<tr>...</tr>{/snippet}
    </ResizableTable>
-->
<script>
	import { onMount, onDestroy } from 'svelte';
	import { _ } from '$lib/i18n';

	/** @type {{ tableId: string, columns: Array<{key: string, label: string, defaultWidth: number}>, children?: import('svelte').Snippet }} */
	let { tableId, columns, children } = $props();

	let STORAGE_KEY = $derived(`lamb.table.${tableId}.colWidths`);
	const MIN_COL_PX = 60;

	/** @type {number[]} */
	let colWidths = $state([]);
	/** @type {HTMLDivElement|null} */
	let container = $state(null);
	/** @type {HTMLTableElement|null} */
	let tableEl = $state(null);

	/**
	 * @type {{ active: boolean, colIdx: number, startX: number, startWidths: number[] }|null}
	 */
	let dragState = $state(null);

	onMount(() => {
		loadWidths();
	});

	function loadWidths() {
		try {
			const stored = localStorage.getItem(STORAGE_KEY);
			if (stored) {
				const parsed = JSON.parse(stored);
				if (Array.isArray(parsed) && parsed.length === columns.length) {
					colWidths = parsed;
					return;
				}
			}
		} catch {
			// ignore
		}
		colWidths = columns.map((c) => c.defaultWidth);
	}

	function saveWidths() {
		try {
			localStorage.setItem(STORAGE_KEY, JSON.stringify(colWidths));
		} catch {
			// ignore
		}
	}

	export function resetColumnWidths() {
		colWidths = columns.map((c) => c.defaultWidth);
		try {
			localStorage.removeItem(STORAGE_KEY);
		} catch {
			// ignore
		}
	}

	function totalWidth() {
		return colWidths.reduce((sum, w) => sum + w, 0);
	}

	/**
	 * @param {MouseEvent} e
	 * @param {number} colIdx
	 */
	function onHandleMouseDown(e, colIdx) {
		e.preventDefault();
		dragState = {
			active: true,
			colIdx,
			startX: e.clientX,
			startWidths: [...colWidths]
		};
		document.addEventListener('mousemove', onMouseMove);
		document.addEventListener('mouseup', onMouseUp);
		document.body.style.cursor = 'col-resize';
		document.body.style.userSelect = 'none';
	}

	/** @param {MouseEvent} e */
	function onMouseMove(e) {
		const ds = dragState;
		if (!ds) return;
		const dx = e.clientX - ds.startX;
		const { colIdx, startWidths } = ds;
		const nextIdx = colIdx + 1;
		if (nextIdx >= startWidths.length) return;

		let newLeft = startWidths[colIdx] + dx;
		let newRight = startWidths[nextIdx] - dx;

		if (newLeft < MIN_COL_PX) {
			newRight = newRight - (MIN_COL_PX - newLeft);
			newLeft = MIN_COL_PX;
		}
		if (newRight < MIN_COL_PX) {
			newLeft = newLeft - (MIN_COL_PX - newRight);
			newRight = MIN_COL_PX;
		}

		const updated = [...colWidths];
		updated[colIdx] = newLeft;
		updated[nextIdx] = newRight;
		colWidths = updated;
	}

	function onMouseUp() {
		if (!dragState) return;
		dragState = null;
		document.removeEventListener('mousemove', onMouseMove);
		document.removeEventListener('mouseup', onMouseUp);
		document.body.style.cursor = '';
		document.body.style.userSelect = '';
		saveWidths();
	}

	onDestroy(() => {
		document.removeEventListener('mousemove', onMouseMove);
		document.removeEventListener('mouseup', onMouseUp);
	});
</script>

<div class="relative w-full overflow-hidden" bind:this={container}>
	<!-- Reset columns link -->
	<div class="flex justify-end px-1 pb-1">
		<button
			type="button"
			onclick={resetColumnWidths}
			class="text-xs text-gray-400 hover:text-gray-600 hover:underline"
		>
			{$_('table.resetColumns', { default: 'Reset columns' })}
		</button>
	</div>

	<div class="overflow-x-auto">
		<table
			bind:this={tableEl}
			class="divide-y divide-gray-200"
			style="table-layout: fixed; width: {totalWidth()}px; min-width: 100%;"
		>
			<!-- Colgroup for explicit column widths -->
			<colgroup>
				{#each colWidths as w, ci (ci)}
					<col style="width: {w}px;" />
				{/each}
			</colgroup>

			<!-- Column headers with drag handles -->
			<thead class="bg-gray-50">
				<tr>
					{#each columns as col, i (col.key)}
						<th
							aria-label={col.label}
							class="relative overflow-hidden px-4 py-2.5 text-left text-xs font-medium text-gray-500 uppercase select-none"
							style="width: {colWidths[i]}px;"
						>
							<span class="block truncate">{col.label}</span>
							<!-- Drag handle (not on last column) -->
							{#if i < columns.length - 1}
								<button
									type="button"
									aria-hidden="true"
									tabindex="-1"
									title="Resize {col.label} column"
									onmousedown={(e) => onHandleMouseDown(e, i)}
									class="absolute top-0 right-0 h-full w-1.5 cursor-col-resize rounded-none border-0 bg-transparent p-0 select-none hover:bg-blue-400/40 active:bg-blue-500/60"
									style="touch-action: none;"
								></button>
							{/if}
						</th>
					{/each}
				</tr>
			</thead>

			<!-- Table body via slot/snippet -->
			{@render children?.()}
		</table>
	</div>
</div>
