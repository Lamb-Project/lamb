<!--
  @component KnowledgeStoreBenchmarkView
  KG-RAG benchmark panel for a Knowledge Store: pick a dataset, run the
  side-by-side comparison (simple_query vs kg_rag_query), and render the
  aggregate metrics + per-question scores.
-->
<script>
	import { onMount } from 'svelte';
	import { listDatasets, runBenchmark } from '$lib/services/benchmarkService';

	/** @type {{ ksId: string, graphEnabled: boolean }} */
	let { ksId, graphEnabled } = $props();

	let datasets = $state(/** @type {any[]} */ ([]));
	let selected = $state('educational');
	let topK = $state(5);
	let graphDepth = $state(2);
	let threshold = $state(0);
	let running = $state(false);
	let error = $state('');
	let result = $state(/** @type {any} */ (null));

	onMount(async () => {
		try {
			const data = await listDatasets();
			datasets = Array.isArray(data) ? data : [];
		} catch (/** @type {*} */ err) {
			error =
				err?.response?.data?.detail || err?.message || 'Failed to load datasets';
		}
	});

	async function run() {
		running = true;
		error = '';
		result = null;
		try {
			result = await runBenchmark(ksId, {
				dataset_id: selected,
				top_k: topK,
				graph_depth: graphDepth,
				threshold,
			});
		} catch (/** @type {*} */ err) {
			error =
				err?.response?.data?.detail || err?.message || 'Benchmark failed';
		} finally {
			running = false;
		}
	}

	/** @param {*} num */
	function fmt(num) {
		return typeof num === 'number' ? num.toFixed(3) : '-';
	}
	/** @param {*} num */
	function fmtMs(num) {
		return typeof num === 'number' ? `${num.toFixed(1)} ms` : '-';
	}
</script>

<div class="space-y-4">
	{#if !graphEnabled}
		<div class="rounded border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
			Graph RAG is not enabled on this Knowledge Store, so the
			<code class="font-mono">kg_rag_query</code> arm of the benchmark will
			degrade to the vector baseline. Enable the graph first for a meaningful
			comparison.
		</div>
	{/if}

	<div class="flex flex-wrap items-end gap-3 rounded border border-gray-200 bg-white p-3">
		<label class="flex flex-col text-xs text-gray-700">
			Dataset
			<select
				class="mt-1 rounded border border-gray-300 px-2 py-1 text-sm"
				bind:value={selected}
			>
				{#each datasets as ds (ds.id)}
					<option value={ds.id}>{ds.name}</option>
				{/each}
			</select>
		</label>
		<label class="flex flex-col text-xs text-gray-700">
			Top-K
			<input
				type="number"
				min="1"
				max="50"
				class="mt-1 w-20 rounded border border-gray-300 px-2 py-1 text-sm"
				bind:value={topK}
			/>
		</label>
		<label class="flex flex-col text-xs text-gray-700">
			Graph depth
			<input
				type="number"
				min="1"
				max="4"
				class="mt-1 w-20 rounded border border-gray-300 px-2 py-1 text-sm"
				bind:value={graphDepth}
			/>
		</label>
		<label class="flex flex-col text-xs text-gray-700">
			Threshold
			<input
				type="number"
				min="0"
				max="1"
				step="0.05"
				class="mt-1 w-24 rounded border border-gray-300 px-2 py-1 text-sm"
				bind:value={threshold}
			/>
		</label>
		<button
			type="button"
			class="rounded bg-blue-600 px-3 py-1 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
			onclick={run}
			disabled={running}
		>
			{running ? 'Running…' : 'Run benchmark'}
		</button>
	</div>

	{#if error}
		<div class="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700">{error}</div>
	{/if}

	{#if result}
		<section class="rounded border border-gray-200 bg-white p-3">
			<h3 class="mb-2 text-sm font-semibold text-gray-900">Summary</h3>
			<table class="w-full text-sm">
				<thead>
					<tr class="text-left text-xs uppercase text-gray-500">
						<th class="py-1"></th>
						<th class="py-1">P@k</th>
						<th class="py-1">R@k</th>
						<th class="py-1">MRR</th>
						<th class="py-1">Avg vector</th>
						<th class="py-1">Avg graph</th>
						<th class="py-1">Avg total</th>
					</tr>
				</thead>
				<tbody>
					<tr>
						<td class="py-1 font-medium">Baseline</td>
						<td>{fmt(result?.baseline?.precision_at_k)}</td>
						<td>{fmt(result?.baseline?.recall_at_k)}</td>
						<td>{fmt(result?.baseline?.mrr)}</td>
						<td>{fmtMs(result?.baseline?.avg_vector_ms)}</td>
						<td>{fmtMs(result?.baseline?.avg_graph_ms)}</td>
						<td>{fmtMs(result?.baseline?.avg_total_ms)}</td>
					</tr>
					<tr>
						<td class="py-1 font-medium">KG-RAG</td>
						<td>{fmt(result?.kg_rag?.precision_at_k)}</td>
						<td>{fmt(result?.kg_rag?.recall_at_k)}</td>
						<td>{fmt(result?.kg_rag?.mrr)}</td>
						<td>{fmtMs(result?.kg_rag?.avg_vector_ms)}</td>
						<td>{fmtMs(result?.kg_rag?.avg_graph_ms)}</td>
						<td>{fmtMs(result?.kg_rag?.avg_total_ms)}</td>
					</tr>
				</tbody>
			</table>
			{#if result?.comparison}
				<p class="mt-2 text-xs text-gray-600">
					ΔP@k {fmt(result.comparison.delta_precision_at_k)} · ΔR@k {fmt(
						result.comparison.delta_recall_at_k,
					)} · ΔMRR {fmt(result.comparison.delta_mrr)} · graph overhead {fmtMs(
						result.comparison.graph_overhead_ms,
					)}
				</p>
				<p class="text-xs text-gray-500">{result.comparison.expected_behavior}</p>
			{/if}
		</section>

		<section class="rounded border border-gray-200 bg-white p-3">
			<h3 class="mb-2 text-sm font-semibold text-gray-900">Per question</h3>
			<table class="w-full text-xs">
				<thead>
					<tr class="text-left uppercase text-gray-500">
						<th class="py-1">Question</th>
						<th class="py-1">Kind</th>
						<th class="py-1">Baseline P@k</th>
						<th class="py-1">KG-RAG P@k</th>
						<th class="py-1">ΔMRR</th>
					</tr>
				</thead>
				<tbody>
					{#each result?.results || [] as row (row.question_id)}
						<tr>
							<td class="py-1 pr-2">{row.question}</td>
							<td>{row.kind}</td>
							<td>{fmt(row?.baseline?.precision_at_k)}</td>
							<td>{fmt(row?.kg_rag?.precision_at_k)}</td>
							<td>
								{fmt(
									(row?.kg_rag?.mrr ?? 0) - (row?.baseline?.mrr ?? 0),
								)}
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</section>
	{/if}
</div>
