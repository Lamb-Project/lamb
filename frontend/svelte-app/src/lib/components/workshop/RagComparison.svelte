<script>
	// src/lib/components/workshop/RagComparison.svelte
	// Side-by-side view of the same question asked with the knowledge base on
	// and off (D3).
	//
	// Seeing the two answers next to each other is the whole point of the
	// experiment: a student who only reads the "on" answer has no reason to
	// believe the document mattered. The inputs column is deliberately included
	// — the difference in the *answer* is only meaningful if you can see the
	// difference in what was sent.

	import { _ } from '$lib/i18n';
	import { compareRagRuns } from './logic/workshopObservations.svelte.js';

	/** @type {{ history?: Array<any> }} */
	let { history = [] } = $props();

	const pairs = $derived(compareRagRuns(history));

	/**
	 * One-sentence description of what a run sent, for the inputs column.
	 * @param {any} run
	 */
	function inputsSummary(run) {
		if (!run) return '';
		const sources = (run.sources || []).length;
		if (run.ragMode === 'off') {
			return $_('workshop.comparisonNoSources', {
				default: 'No excerpts were retrieved (the tool was removed too).'
			});
		}
		if (!sources) {
			return $_('workshop.comparisonNoHits', {
				default: 'No excerpts matched this question.'
			});
		}
		return $_('workshop.comparisonSourceCount', {
			values: { count: sources },
			default: `${sources} excerpt(s) were placed in the prompt.`
		});
	}
</script>

<div class="border rounded-lg p-4 bg-white shadow-sm" data-testid="rag-comparison">
	<h3 class="text-sm font-semibold mb-1">
		{$_('workshop.comparisonTitle', { default: 'With and without the knowledge base' })}
	</h3>

	{#if pairs.length === 0}
		<p class="text-xs text-gray-500">
			{$_('workshop.comparisonEmpty', { default: 'Run the same question in both modes to see the comparison.' })}
		</p>
	{:else}
		<div class="space-y-4">
			{#each pairs as pair, i (pair.question + i)}
				<div class="border-t pt-3 first:border-t-0 first:pt-0">
					<p class="text-xs text-gray-500 uppercase tracking-wide">
						{$_('workshop.comparisonQuestion', { default: 'Question' })}
					</p>
					<p class="text-sm font-medium text-gray-800 mb-2">{pair.question}</p>

					<div class="grid grid-cols-1 md:grid-cols-2 gap-3">
						{#each [{ run: pair.on, mode: 'on' }, { run: pair.off, mode: 'off' }] as column (column.mode)}
							<div
								class="border rounded p-3 {column.mode === 'off' ? 'bg-amber-50' : 'bg-green-50'}"
								data-testid="comparison-{column.mode}"
							>
								<div class="text-xs font-semibold uppercase text-gray-500">
									{column.mode === 'off'
										? $_('workshop.ragOffBadge', { default: 'Knowledge base off' })
										: $_('workshop.ragOnBadge', { default: 'Knowledge base on' })}
								</div>
								{#if column.run}
									<div class="mt-2">
										<p class="text-[10px] uppercase text-gray-500">
											{$_('workshop.comparisonInputs', { default: 'What was sent' })}
										</p>
										<p class="text-xs text-gray-700">{inputsSummary(column.run)}</p>
									</div>
									<div class="mt-2">
										<p class="text-[10px] uppercase text-gray-500">
											{$_('workshop.comparisonAnswers', { default: 'Answer' })}
										</p>
										<p class="text-sm text-gray-800 whitespace-pre-wrap">{column.run.answer || '—'}</p>
									</div>
								{:else}
									<p class="text-xs text-gray-500 mt-2">
										{$_('workshop.comparisonMissing', { default: 'Not run in this mode yet.' })}
									</p>
								{/if}
							</div>
						{/each}
					</div>
				</div>
			{/each}
		</div>
	{/if}
</div>