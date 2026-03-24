<script>
	import { onMount } from 'svelte';
	import { _ } from 'svelte-i18n';
	import {
		getActivityView,
		startEvaluation,
		getEvaluationStatus,
		updateGrade,
		acceptAiGrades,
		syncGradesToMoodle
	} from '$lib/services/gradingService.js';
	import { getActivityId } from '$lib/services/api.js';

	let activityId = $state('');
	let data = $state(null);
	let loading = $state(true);
	let error = $state('');
	let success = $state('');

	let evaluating = $state(false);
	let evalStatus = $state(null);
	let syncing = $state(false);

	let editingGrade = $state(null);
	let editScore = $state(0);
	let editComment = $state('');

	let pollInterval = $state(null);

	onMount(async () => {
		activityId = getActivityId();
		if (!activityId) {
			error = 'No activity ID';
			loading = false;
			return;
		}
		await refresh();
		return () => {
			if (pollInterval) clearInterval(pollInterval);
		};
	});

	async function refresh() {
		loading = true;
		try {
			data = await getActivityView(activityId);
		} catch (e) {
			error = e.message;
		}
		loading = false;
	}

	async function handleEvaluateAll() {
		if (!data?.submissions?.length) return;
		evaluating = true;
		error = '';
		const ids = data.submissions.map((s) => s.file_submission.id);
		try {
			await startEvaluation(activityId, ids);
			pollInterval = setInterval(pollEvalStatus, 3000);
		} catch (e) {
			error = e.message;
			evaluating = false;
		}
	}

	async function pollEvalStatus() {
		try {
			evalStatus = await getEvaluationStatus(activityId);
			if (evalStatus.overall_status === 'completed' || evalStatus.overall_status === 'completed_with_errors' || evalStatus.overall_status === 'idle') {
				clearInterval(pollInterval);
				pollInterval = null;
				evaluating = false;
				await refresh();
			}
		} catch (e) {
			clearInterval(pollInterval);
			pollInterval = null;
			evaluating = false;
		}
	}

	function startEditGrade(sub) {
		editingGrade = sub.file_submission.id;
		editScore = sub.grade?.score ?? sub.grade?.ai_score ?? 0;
		editComment = sub.grade?.comment ?? sub.grade?.ai_comment ?? '';
	}

	async function saveGrade(fsId) {
		try {
			await updateGrade(fsId, editScore, editComment);
			editingGrade = null;
			await refresh();
		} catch (e) {
			error = e.message;
		}
	}

	async function handleAcceptAll() {
		try {
			await acceptAiGrades(activityId);
			success = 'AI grades accepted';
			await refresh();
		} catch (e) {
			error = e.message;
		}
	}

	async function handleSyncMoodle() {
		syncing = true;
		error = '';
		try {
			const result = await syncGradesToMoodle(activityId);
			if (result.success) {
				success = $_('fileEval.grading.syncSuccess');
			} else {
				error = result.error || 'Sync failed';
			}
			await refresh();
		} catch (e) {
			error = e.message;
		}
		syncing = false;
	}
</script>

<div class="mx-auto max-w-6xl px-4 py-8">
	<h1 class="mb-6 text-2xl font-bold text-gray-800">{$_('fileEval.grading.title')}</h1>

	{#if error}
		<div class="mb-4 rounded-lg border border-red-200 bg-red-50 p-4 text-red-700">{error}</div>
	{/if}
	{#if success}
		<div class="mb-4 rounded-lg border border-green-200 bg-green-50 p-4 text-green-700">{success}</div>
	{/if}

	{#if loading}
		<div class="flex items-center justify-center py-12">
			<div class="h-8 w-8 animate-spin rounded-full border-b-2 border-blue-600"></div>
		</div>
	{:else if data}
		<!-- Stats cards -->
		{#if data.stats}
			<div class="mb-6 grid grid-cols-2 gap-4 md:grid-cols-4">
				<div class="rounded-lg bg-white p-4 shadow-sm">
					<p class="text-sm text-gray-500">{$_('fileEval.grading.stats.total')}</p>
					<p class="text-2xl font-bold">{data.stats.total_submissions || 0}</p>
				</div>
				<div class="rounded-lg bg-white p-4 shadow-sm">
					<p class="text-sm text-gray-500">{$_('fileEval.grading.stats.evaluated')}</p>
					<p class="text-2xl font-bold">{data.stats.evaluated || 0}</p>
				</div>
				<div class="rounded-lg bg-white p-4 shadow-sm">
					<p class="text-sm text-gray-500">{$_('fileEval.grading.stats.graded')}</p>
					<p class="text-2xl font-bold">{data.stats.graded || 0}</p>
				</div>
				<div class="rounded-lg bg-white p-4 shadow-sm">
					<p class="text-sm text-gray-500">{$_('fileEval.grading.stats.sentToMoodle')}</p>
					<p class="text-2xl font-bold">{data.stats.sent_to_moodle || 0}</p>
				</div>
			</div>
		{/if}

		<!-- Action buttons -->
		<div class="mb-6 flex flex-wrap gap-3">
			<button
				onclick={handleEvaluateAll}
				disabled={evaluating || !data.submissions?.length}
				class="rounded-lg bg-purple-600 px-5 py-2 text-white hover:bg-purple-700 disabled:opacity-50"
			>
				{evaluating ? $_('fileEval.grading.evaluating') : $_('fileEval.grading.evaluateAll')}
			</button>
			<button
				onclick={handleAcceptAll}
				class="rounded-lg bg-blue-600 px-5 py-2 text-white hover:bg-blue-700"
			>
				{$_('fileEval.grading.acceptAll')}
			</button>
			<button
				onclick={handleSyncMoodle}
				disabled={syncing}
				class="rounded-lg bg-green-600 px-5 py-2 text-white hover:bg-green-700 disabled:opacity-50"
			>
				{syncing ? $_('fileEval.grading.syncing') : $_('fileEval.grading.syncMoodle')}
			</button>
		</div>

		<!-- Evaluation progress -->
		{#if evaluating && evalStatus}
			<div class="mb-6 rounded-lg border bg-yellow-50 p-4">
				<p class="font-medium">
					{$_('fileEval.status.' + evalStatus.overall_status)}
				</p>
				<div class="mt-2 flex gap-4 text-sm">
					<span>Pending: {evalStatus.counts?.pending || 0}</span>
					<span>Processing: {evalStatus.counts?.processing || 0}</span>
					<span>Completed: {evalStatus.counts?.completed || 0}</span>
					<span>Errors: {evalStatus.counts?.error || 0}</span>
				</div>
			</div>
		{/if}

		<!-- Submissions table -->
		{#if data.submissions?.length}
			<div class="overflow-x-auto rounded-lg border bg-white shadow-sm">
				<table class="min-w-full divide-y divide-gray-200">
					<thead class="bg-gray-50">
						<tr>
							<th class="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">
								{$_('fileEval.grading.table.file')}
							</th>
							<th class="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">
								{$_('fileEval.grading.table.group')}
							</th>
							<th class="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">
								{$_('fileEval.grading.table.aiScore')}
							</th>
							<th class="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">
								{$_('fileEval.grading.table.finalScore')}
							</th>
							<th class="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">
								{$_('fileEval.grading.table.status')}
							</th>
							<th class="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">
								{$_('fileEval.grading.table.actions')}
							</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-gray-200">
						{#each data.submissions as sub}
							<tr class="hover:bg-gray-50">
								<td class="px-4 py-3 text-sm">
									{sub.file_submission?.file_name || 'N/A'}
									<span class="block text-xs text-gray-400">
										{sub.member_count || 1} member(s)
									</span>
								</td>
								<td class="px-4 py-3 text-sm">
									{sub.file_submission?.group_display_name || '-'}
								</td>
								<td class="px-4 py-3 text-sm">
									{sub.grade?.ai_score != null ? `${sub.grade.ai_score}/10` : '-'}
								</td>
								<td class="px-4 py-3 text-sm">
									{#if editingGrade === sub.file_submission?.id}
										<input
											type="number"
											min="0"
											max="10"
											step="0.1"
											class="w-20 rounded border p-1 text-sm"
											bind:value={editScore}
										/>
									{:else}
										{sub.grade?.score != null ? `${sub.grade.score}/10` : '-'}
									{/if}
								</td>
								<td class="px-4 py-3 text-sm">
									<span
										class="inline-block rounded-full px-2 py-1 text-xs font-medium
											{sub.file_submission?.evaluation_status === 'completed'
											? 'bg-green-100 text-green-800'
											: sub.file_submission?.evaluation_status === 'error'
												? 'bg-red-100 text-red-800'
												: sub.file_submission?.evaluation_status === 'processing'
													? 'bg-yellow-100 text-yellow-800'
													: 'bg-gray-100 text-gray-800'}"
									>
										{$_('fileEval.status.' + (sub.file_submission?.evaluation_status || 'not_started'))}
									</span>
								</td>
								<td class="px-4 py-3 text-sm">
									{#if editingGrade === sub.file_submission?.id}
										<button
											onclick={() => saveGrade(sub.file_submission.id)}
											class="rounded bg-blue-600 px-3 py-1 text-xs text-white hover:bg-blue-700"
										>
											{$_('fileEval.grading.saveGrade')}
										</button>
									{:else}
										<button
											onclick={() => startEditGrade(sub)}
											class="rounded bg-gray-100 px-3 py-1 text-xs hover:bg-gray-200"
										>
											{$_('fileEval.grading.editGrade')}
										</button>
									{/if}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{:else}
			<div class="rounded-lg border bg-white p-12 text-center text-gray-500">
				{$_('fileEval.grading.noSubmissions')}
			</div>
		{/if}
	{/if}
</div>
