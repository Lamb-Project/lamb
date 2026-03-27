<script>
	import { onMount } from 'svelte';
	import { _ } from 'svelte-i18n';
	import {
		getActivityView,
		startEvaluation,
		getEvaluationStatus,
		updateGrade,
		acceptAiGrades,
		syncGradesToMoodle,
		downloadSubmission,
		updateActivityConfig
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

	// Activity config editing state
	let editingConfig = $state(false);
	let editDescription = $state('');
	let editDeadline = $state('');
	let editDeadlineDate = $state('');
	let editDeadlineTime = $state('');

	function parseDeadline(deadline) {
		if (deadline == null || deadline === '') return null;
		if (typeof deadline === 'number') {
			const ms = deadline > 1e12 ? deadline : deadline * 1000;
			const d = new Date(ms);
			return Number.isNaN(d.getTime()) ? null : d;
		}
		const d = new Date(deadline);
		return Number.isNaN(d.getTime()) ? null : d;
	}

	function formatDeadline(deadline) {
		const d = parseDeadline(deadline);
		if (!d) return { date: '', time: '' };
		return {
			date: d.toISOString().split('T')[0],
			time: d.toTimeString().slice(0, 5)
		};
	}

	function startEditConfig() {
		editingConfig = true;
		const desc = data?.activity_info?.description || '';
		editDescription = desc || '';
		const dl = parseDeadline(data?.activity_info?.deadline);
		if (dl) {
			editDeadlineDate = dl.toISOString().split('T')[0];
			editDeadlineTime = dl.toTimeString().slice(0, 5);
		} else {
			editDeadlineDate = '';
			editDeadlineTime = '';
		}
	}

	function cancelEditConfig() {
		editingConfig = false;
	}

	async function saveConfig() {
		try {
			let deadline = null;
			if (editDeadlineDate && editDeadlineTime) {
				const dlDate = new Date(`${editDeadlineDate}T${editDeadlineTime}`);
				deadline = Math.floor(dlDate.getTime() / 1000);
			}
			await updateActivityConfig(activityId, {
				description: editDescription,
				deadline: deadline
			});
			await refresh();
			editingConfig = false;
			success = 'Activity configuration updated';
		} catch (e) {
			error = e.message;
		}
	}

	// Sorting state
	let sortField = $state('uploaded_at');
	let sortDirection = $state('desc');

	// Pagination state
	let currentPage = $state(1);
	let perPage = $state(10);
	const perPageOptions = [2, 5, 10, 25, 50];

	function formatDate(timestamp) {
		if (!timestamp) return '';
		const date = new Date(timestamp * 1000);
		return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
	}

	function sortSubmissions(submissions) {
		if (!submissions) return [];
		return [...submissions].sort((a, b) => {
			let aVal, bVal;
			switch (sortField) {
				case 'file_name':
					aVal = a.file_submission?.file_name?.toLowerCase() || '';
					bVal = b.file_submission?.file_name?.toLowerCase() || '';
					break;
				case 'student_name':
					aVal = a.members?.[0]?.student_name?.toLowerCase() || '';
					bVal = b.members?.[0]?.student_name?.toLowerCase() || '';
					break;
				case 'uploaded_at':
					aVal = a.file_submission?.uploaded_at || 0;
					bVal = b.file_submission?.uploaded_at || 0;
					break;
				case 'ai_score':
					aVal = a.grade?.ai_score ?? -1;
					bVal = b.grade?.ai_score ?? -1;
					break;
				case 'final_score':
					aVal = a.grade?.score ?? -1;
					bVal = b.grade?.score ?? -1;
					break;
				case 'evaluation_status':
					aVal = a.file_submission?.evaluation_status || '';
					bVal = b.file_submission?.evaluation_status || '';
					break;
				default:
					aVal = a.file_submission?.uploaded_at || 0;
					bVal = b.file_submission?.uploaded_at || 0;
			}

			if (typeof aVal === 'string' && typeof bVal === 'string') {
				if (sortDirection === 'asc') return aVal.localeCompare(bVal);
				return bVal.localeCompare(aVal);
			}
			if (sortDirection === 'asc') return aVal - bVal;
			return bVal - aVal;
		});
	}

	function handleSort(field) {
		if (sortField === field) {
			sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
		} else {
			sortField = field;
			sortDirection = 'asc';
		}
		currentPage = 1;
	}

	function getSortIcon(field) {
		if (sortField !== field) return '↕';
		return sortDirection === 'asc' ? '↑' : '↓';
	}

	function getPaginatedSubmissions() {
		const sorted = sortSubmissions(data?.submissions);
		const start = (currentPage - 1) * perPage;
		return sorted.slice(start, start + perPage);
	}

	function getTotalPages() {
		if (!data?.submissions) return 0;
		return Math.ceil(data.submissions.length / perPage);
	}

	function goToPage(page) {
		const maxPage = getTotalPages();
		if (page < 1) page = 1;
		if (page > maxPage) page = maxPage;
		currentPage = page;
	}

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

	async function handleDownload(fsId, fileName) {
		try {
			await downloadSubmission(fsId, fileName);
		} catch (e) {
			error = e.message;
		}
	}
</script>

<div class="mx-auto max-w-7xl px-4 py-8">
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
		<!-- Activity Info Card with Edit -->
		{#if data.activity_info}
			<div class="mb-6 rounded-lg border bg-white p-5 shadow-sm">
				<div class="mb-3 flex items-center justify-between">
					<h2 class="text-lg font-semibold text-gray-800">{$_('fileEval.grading.activityConfig')}</h2>
					{#if editingConfig}
						<div class="flex gap-2">
							<button onclick={saveConfig} class="rounded bg-green-600 px-3 py-1 text-sm text-white hover:bg-green-700">
								{$_('fileEval.grading.save')}
							</button>
							<button onclick={cancelEditConfig} class="rounded bg-gray-200 px-3 py-1 text-sm hover:bg-gray-300">
								{$_('fileEval.grading.cancel')}
							</button>
						</div>
					{:else}
						<button onclick={startEditConfig} class="rounded bg-blue-100 px-3 py-1 text-sm text-blue-700 hover:bg-blue-200">
							{$_('fileEval.grading.editConfig')}
						</button>
					{/if}
				</div>
				{#if editingConfig}
					<div class="space-y-4">
						<div>
							<label class="mb-1 block text-sm font-medium text-gray-700">{$_('fileEval.grading.description')}</label>
							<textarea
								class="w-full rounded-lg border p-3 text-sm"
								rows="4"
								bind:value={editDescription}
								placeholder={$_('fileEval.grading.descriptionPlaceholder')}
							></textarea>
						</div>
						<div class="flex gap-4">
							<div class="flex-1">
								<label class="mb-1 block text-sm font-medium text-gray-700">{$_('fileEval.grading.deadlineDate')}</label>
								<input type="date" class="w-full rounded-lg border p-2 text-sm" bind:value={editDeadlineDate} />
							</div>
							<div class="w-40">
								<label class="mb-1 block text-sm font-medium text-gray-700">{$_('fileEval.grading.deadlineTime')}</label>
								<input type="time" class="w-full rounded-lg border p-2 text-sm" bind:value={editDeadlineTime} />
							</div>
						</div>
					</div>
				{:else}
					<div class="space-y-2 text-sm text-gray-600">
						{#if data.activity_info.description}
							<p class="whitespace-pre-wrap">{data.activity_info.description}</p>
						{:else}
							<p class="italic text-gray-400">{$_('fileEval.grading.noDescription')}</p>
						{/if}
						{#if data.activity_info.deadline}
							<p class="flex items-center gap-2">
								<span class="font-medium">{$_('fileEval.grading.deadline')}:</span>
								<span class="{isDeadlinePast(data.activity_info.deadline) ? 'text-red-600' : 'text-green-600'}">
									{formatDate(data.activity_info.deadline)}
								</span>
								{#if isDeadlinePast(data.activity_info.deadline)}
									<span class="rounded bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">
										{$_('fileEval.grading.deadlinePassed')}
									</span>
								{/if}
							</p>
						{/if}
						{#if data.activity_info.course_name}
							<p>
								<span class="font-medium">{$_('fileEval.grading.course')}:</span>
								{data.activity_info.course_name}
							</p>
						{/if}
					</div>
				{/if}
			</div>
		{/if}

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

		<!-- Evaluation progress modal -->
		{#if evaluating && evalStatus}
			<div class="mb-6 rounded-lg border bg-yellow-50 p-4">
				<div class="mb-2 flex items-center justify-between">
					<p class="font-medium">{$_('fileEval.grading.evalProgress')}</p>
					<p class="text-sm text-gray-600">{$_('fileEval.status.' + evalStatus.overall_status)}</p>
				</div>
				<div class="h-4 w-full overflow-hidden rounded-full bg-gray-200">
					<div
						class="h-full bg-gradient-to-r from-blue-500 to-purple-600 transition-all duration-500"
						style="width: {evalStatus.counts?.completed ? ((evalStatus.counts.completed / (evalStatus.counts.pending + evalStatus.counts.processing + evalStatus.counts.completed + evalStatus.counts.error || 1)) * 100) : 0}%"
					></div>
				</div>
				<div class="mt-2 flex gap-4 text-sm">
					<span class="text-gray-600">{$_('fileEval.status.pending')}: {evalStatus.counts?.pending || 0}</span>
					<span class="text-blue-600">{$_('fileEval.status.processing')}: {evalStatus.counts?.processing || 0}</span>
					<span class="text-green-600">{$_('fileEval.status.completed')}: {evalStatus.counts?.completed || 0}</span>
					<span class="text-red-600">{$_('fileEval.status.error')}: {evalStatus.counts?.error || 0}</span>
				</div>
			</div>
		{/if}

		<!-- Pagination controls top -->
		{#if data.submissions?.length > 0}
			<div class="mb-4 flex items-center justify-between">
				<div class="flex items-center gap-2">
					<label class="text-sm text-gray-600">{$_('fileEval.grading.perPage')}:</label>
					<select
						bind:value={perPage}
						onchange={() => (currentPage = 1)}
						class="rounded-lg border px-2 py-1 text-sm"
					>
						{#each perPageOptions as opt}
							<option value={opt}>{opt}</option>
						{/each}
					</select>
				</div>
				<div class="flex items-center gap-2 text-sm text-gray-600">
					<span>{$_('fileEval.grading.page')} {currentPage} / {getTotalPages()}</span>
					<button
						onclick={() => goToPage(currentPage - 1)}
						disabled={currentPage === 1}
						class="rounded border px-2 py-1 disabled:opacity-50"
					>
						←
					</button>
					<button
						onclick={() => goToPage(currentPage + 1)}
						disabled={currentPage === getTotalPages()}
						class="rounded border px-2 py-1 disabled:opacity-50"
					>
						→
					</button>
				</div>
			</div>
		{/if}

		<!-- Submissions table -->
		{#if getPaginatedSubmissions().length > 0}
			<div class="overflow-x-auto rounded-lg border bg-white shadow-sm">
				<table class="min-w-full divide-y divide-gray-200">
					<thead class="bg-gray-50">
						<tr>
							<th class="cursor-pointer px-4 py-3 text-left text-xs font-medium uppercase text-gray-500 hover:bg-gray-100" onclick={() => handleSort('file_name')}>
								{$_('fileEval.grading.table.file')} {getSortIcon('file_name')}
							</th>
							<th class="cursor-pointer px-4 py-3 text-left text-xs font-medium uppercase text-gray-500 hover:bg-gray-100" onclick={() => handleSort('student_name')}>
								{$_('fileEval.grading.table.student')} {getSortIcon('student_name')}
							</th>
							<th class="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">
								{$_('fileEval.grading.table.group')}
							</th>
							<th class="cursor-pointer px-4 py-3 text-left text-xs font-medium uppercase text-gray-500 hover:bg-gray-100" onclick={() => handleSort('uploaded_at')}>
								{$_('fileEval.grading.table.uploadedAt')} {getSortIcon('uploaded_at')}
							</th>
							<th class="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">
								{$_('fileEval.grading.table.studentNote')}
							</th>
							<th class="cursor-pointer px-4 py-3 text-left text-xs font-medium uppercase text-gray-500 hover:bg-gray-100" onclick={() => handleSort('ai_score')}>
								{$_('fileEval.grading.table.aiScore')} {getSortIcon('ai_score')}
							</th>
							<th class="cursor-pointer px-4 py-3 text-left text-xs font-medium uppercase text-gray-500 hover:bg-gray-100" onclick={() => handleSort('final_score')}>
								{$_('fileEval.grading.table.finalScore')} {getSortIcon('final_score')}
							</th>
							<th class="cursor-pointer px-4 py-3 text-left text-xs font-medium uppercase text-gray-500 hover:bg-gray-100" onclick={() => handleSort('evaluation_status')}>
								{$_('fileEval.grading.table.status')} {getSortIcon('evaluation_status')}
							</th>
							<th class="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">
								{$_('fileEval.grading.table.actions')}
							</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-gray-200">
						{#each getPaginatedSubmissions() as sub}
							<tr class="hover:bg-gray-50">
								<td class="px-4 py-3 text-sm">
									<div class="flex items-center gap-2">
										<span class="font-medium">{sub.file_submission?.file_name || 'N/A'}</span>
										<button
											onclick={() => handleDownload(sub.file_submission.id, sub.file_submission?.file_name)}
											class="rounded p-1 text-gray-500 hover:bg-gray-100 hover:text-blue-600"
											title={$_('fileEval.grading.table.download')}
										>
											<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
												<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
											</svg>
										</button>
									</div>
									<span class="block text-xs text-gray-400">
										{sub.member_count || 1} {sub.member_count === 1 ? $_('fileEval.grading.table.member') : $_('fileEval.grading.table.members')}
									</span>
								</td>
								<td class="px-4 py-3 text-sm">
									{sub.members?.[0]?.student_name || sub.members?.[0]?.student_id || '-'}
								</td>
								<td class="px-4 py-3 text-sm">
									{sub.file_submission?.group_display_name || '-'}
								</td>
								<td class="px-4 py-3 text-sm text-gray-500">
									{formatDate(sub.file_submission?.uploaded_at)}
								</td>
								<td class="px-4 py-3 text-sm">
									{#if sub.file_submission?.student_note}
										<span
											class="max-w-xs truncate text-gray-600"
											title={sub.file_submission.student_note}
										>
											{sub.file_submission.student_note}
										</span>
									{:else}
										-
									{/if}
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
										<div class="flex gap-1">
											<button
												onclick={() => saveGrade(sub.file_submission.id)}
												class="rounded bg-blue-600 px-3 py-1 text-xs text-white hover:bg-blue-700"
											>
												{$_('fileEval.grading.saveGrade')}
											</button>
											<button
												onclick={() => editingGrade = null}
												class="rounded bg-gray-200 px-3 py-1 text-xs hover:bg-gray-300"
											>
												Cancel
											</button>
										</div>
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

			<!-- Pagination controls bottom -->
			<div class="mt-4 flex items-center justify-between">
				<div class="text-sm text-gray-600">
					{$_('fileEval.grading.showing', {
						from: (currentPage - 1) * perPage + 1,
						to: Math.min(currentPage * perPage, data.submissions.length),
						total: data.submissions.length
					})}
				</div>
				<div class="flex items-center gap-2">
					<button
						onclick={() => goToPage(currentPage - 1)}
						disabled={currentPage === 1}
						class="rounded border px-3 py-1 text-sm disabled:opacity-50"
					>
						← {$_('fileEval.grading.previous')}
					</button>
					{#each Array.from({length: getTotalPages()}, (_, i) => i + 1) as pageNum}
						{#if pageNum === 1 || pageNum === getTotalPages() || (pageNum >= currentPage - 1 && pageNum <= currentPage + 1)}
							<button
								onclick={() => goToPage(pageNum)}
								class="rounded border px-3 py-1 text-sm {pageNum === currentPage ? 'bg-blue-600 text-white border-blue-600' : 'hover:bg-gray-100'}"
							>
								{pageNum}
							</button>
						{:else}
							{#if pageNum === currentPage + 2 && getTotalPages() > currentPage + 2}
								<span class="px-2">...</span>
							{/if}
						{/if}
					{/each}
					<button
						onclick={() => goToPage(currentPage + 1)}
						disabled={currentPage === getTotalPages()}
						class="rounded border px-3 py-1 text-sm disabled:opacity-50"
					>
						{$_('fileEval.grading.next')} →
					</button>
				</div>
			</div>
		{:else}
			<div class="rounded-lg border bg-white p-12 text-center text-gray-500">
				{$_('fileEval.grading.noSubmissions')}
			</div>
		{/if}
	{/if}
</div>