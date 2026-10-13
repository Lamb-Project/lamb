<script>
	// src/lib/components/workshop/FormativeFeedback.svelte
	// Renders the rubric-based formative feedback for a submitted workshop.
	// Purely presentational: the page owns the evaluate call and passes the
	// result here. The score is a *suggestion* — the final grade is the
	// teacher's; that is stated explicitly so students don't read it as a mark.

	import { _ } from '$lib/i18n';

	/**
	 * @type {{
	 *   evaluation?: any | null,
	 *   evaluating?: boolean
	 * }}
	 */
	let { evaluation = null, evaluating = false } = $props();

	/** @param {any} value */
	function display(value) {
		if (value === null || value === undefined || value === '') return '—';
		return String(value);
	}

	/** @param {any} value */
	function displayScore(value) {
		if (value === null || value === undefined || value === '') return '—';
		const n = Number(value);
		return Number.isFinite(n) ? String(n) : String(value);
	}

	/**
	 * Whether there is any number worth folding away.
	 *
	 * A rubric can score criteria without producing a total (the model may omit
	 * it, or the run may have been repaired), so both are considered.
	 */
	const hasScores = $derived(
		(evaluation?.total_score !== null && evaluation?.total_score !== undefined) ||
			(evaluation?.criteria || []).some(
				(/** @type {any} */ c) => c.score !== null && c.score !== undefined
			)
	);
</script>

{#if evaluating}
	<div class="border rounded-lg p-4 bg-blue-50 text-blue-800 text-sm">
		{$_('workshop.evaluating', { default: 'Generating your feedback…' })}
	</div>
{:else if evaluation}
	{#if evaluation.configured === false}
		<div class="border rounded-lg p-4 bg-gray-50 text-gray-600 text-sm">
			{$_('workshop.noRubric', { default: 'No rubric is configured for this activity, so no feedback was generated.' })}
		</div>
	{:else if evaluation.status === 'failed'}
		<div class="border rounded-lg p-4 bg-amber-50 text-amber-800 text-sm">
			<p class="font-medium">
				{$_('workshop.feedbackUnavailable', { default: 'Feedback could not be generated.' })}
			</p>
			{#if evaluation.error_message}
				<p class="mt-1 text-xs">{evaluation.error_message}</p>
			{/if}
		</div>
	{:else}
		<div class="border rounded-lg p-4 bg-white shadow-sm space-y-4">
			<div class="flex items-baseline justify-between">
				<h3 class="text-sm font-semibold">
					{$_('workshop.feedbackTitle', { default: 'Your formative feedback' })}
				</h3>
			</div>

			<!-- The model ran out of room mid-answer: the feedback below is real,
			     but its last sentence may be clipped. Saying so beats hiding the
			     recovered evaluation or presenting it as complete. -->
			{#if evaluation.error_message}
				<p
					class="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1"
					data-testid="feedback-truncated"
				>
					{$_('workshop.feedbackTruncated', { default: 'The model stopped before finishing, so the feedback below may end mid-sentence.' })}
				</p>
			{/if}

			<!-- All the numbers live behind ONE toggle (D6): a score shown first
			     invites students to read it as the mark and stop reading the
			     feedback, which is the part meant to teach. One toggle also keeps
			     the list readable — a per-row toggle repeated the same label for
			     every criterion. Teachers still see the scores directly (the
			     dashboard renders them from the API). -->
			{#if hasScores}
				<details class="border border-gray-200 rounded px-3 py-2" data-testid="score-details">
					<summary class="text-xs text-gray-600 cursor-pointer">
						{$_('workshop.showSuggestedScore', { default: 'Show the suggested score' })}
					</summary>
					<div class="mt-2 space-y-1">
						{#if evaluation.total_score !== null && evaluation.total_score !== undefined}
							<p class="text-sm text-gray-600">
								{$_('workshop.suggestedScore', { default: 'Suggested' })}:
								<span class="font-semibold">{displayScore(evaluation.total_score)}</span>
								{#if evaluation.max_score !== null && evaluation.max_score !== undefined}
									/ {displayScore(evaluation.max_score)}
								{/if}
							</p>
						{/if}
						<ul class="text-xs text-gray-500 space-y-0.5">
							{#each evaluation.criteria as c, i (i)}
								{#if c.score !== null && c.score !== undefined}
									<li class="flex justify-between gap-3">
										<span class="truncate">{c.criterion || `Criterion ${i + 1}`}</span>
										<span class="whitespace-nowrap">
											{#if c.level}{display(c.level)} · {/if}
											{$_('workshop.score', { default: 'Score' })}: {displayScore(c.score)}
											{#if c.weight !== null && c.weight !== undefined}
												({displayScore(c.weight)}%)
											{/if}
										</span>
									</li>
								{/if}
							{/each}
						</ul>
					</div>
				</details>
			{/if}

			{#if evaluation.criteria && evaluation.criteria.length > 0}
				<ul class="space-y-3">
					{#each evaluation.criteria as c, i (i)}
						<li class="border-t pt-3 first:border-t-0 first:pt-0">
							<div class="flex items-baseline justify-between gap-2">
								<span class="text-sm font-medium">{c.criterion || `Criterion ${i + 1}`}</span>
								{#if c.level}
									<span class="text-xs text-gray-500 whitespace-nowrap">
										{$_('workshop.level', { default: 'Level' })}: {display(c.level)}
									</span>
								{/if}
							</div>
							{#if c.feedback}
								<p class="text-sm text-gray-700 mt-1 whitespace-pre-wrap">{c.feedback}</p>
							{/if}
						</li>
					{/each}
				</ul>
			{/if}

			{#if evaluation.overall_feedback}
				<div class="border-t pt-3">
					<h4 class="text-xs font-semibold uppercase text-gray-500">
						{$_('workshop.overallFeedback', { default: 'Overall feedback' })}
					</h4>
					<p class="text-sm text-gray-700 mt-1 whitespace-pre-wrap">{evaluation.overall_feedback}</p>
				</div>
			{/if}

			<p class="text-xs text-gray-500 border-t pt-3">
				{$_('workshop.teacherDecides', { default: 'This is formative guidance, not a grade. Your teacher decides the final score.' })}
			</p>
		</div>
	{/if}
{/if}
