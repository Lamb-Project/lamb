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
	import { marked } from 'marked';

	marked.use({
		gfm: true,
		breaks: true
	});

	/**
	 * @param {string | null | undefined} md
	 * @returns {string}
	 */
	function aiFeedbackMarkdownToHtml(md) {
		if (md == null || md === '') return '';
		try {
			return String(marked.parse(md));
		} catch {
			return `<p class="whitespace-pre-wrap">${String(md)
				.replace(/&/g, '&amp;')
				.replace(/</g, '&lt;')
				.replace(/>/g, '&gt;')}</p>`;
		}
	}

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

	let editingConfig = $state(false);
	let editDescription = $state('');
	let editDeadlineDate = $state('');
	let editDeadlineTime = $state('');

	let sortField = $state('uploaded_at');
	let sortDirection = $state('desc');
	let currentPage = $state(1);
	let perPage = $state(10);
	const perPageOptions = [5, 10, 25, 50];

	/** @type {Set<string>} */
	let selectedIds = $state(new Set());

	/** @type {Set<string>} */
	let expandedAiCommentIds = $state(new Set());

	function isAiCommentExpanded(fsId) {
		return expandedAiCommentIds.has(fsId);
	}

	function setAiCommentExpanded(fsId, expanded) {
		const next = new Set(expandedAiCommentIds);
		if (expanded) next.add(fsId);
		else next.delete(fsId);
		expandedAiCommentIds = next;
	}

	function allSubmissionIds() {
		return (data?.submissions || []).map((s) => s.file_submission.id);
	}

	function isAllSelected() {
		const ids = allSubmissionIds();
		return ids.length > 0 && ids.every((id) => selectedIds.has(id));
	}

	function toggleSelectAll() {
		if (isAllSelected()) {
			selectedIds = new Set();
		} else {
			selectedIds = new Set(allSubmissionIds());
		}
	}

	function toggleSelected(fsId) {
		const next = new Set(selectedIds);
		if (next.has(fsId)) {
			next.delete(fsId);
		} else {
			next.add(fsId);
		}
		selectedIds = next;
	}

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

	function formatTime(ts) {
		if (!ts) return '';
		const d = new Date(typeof ts === 'number' ? ts * 1000 : ts);
		return d.toLocaleString();
	}

	function formatDeadlineDisplay(deadline) {
		const d = parseDeadline(deadline);
		if (!d) return '';
		return d.toLocaleDateString() + ' ' + d.toLocaleTimeString();
	}

	function isDeadlinePast(deadline) {
		const d = parseDeadline(deadline);
		if (!d) return false;
		return d.getTime() < Date.now();
	}

	function memberLabel(m) {
		if (!m) return '-';
		return (m.student_name || m.student_id || '').trim() || '-';
	}

	function studentSortKey(sub) {
		const m = sub.members?.[0];
		return (m?.student_name || m?.student_id || '').toLowerCase();
	}

	function formatFileSize(bytes) {
		if (!bytes) return '';
		if (bytes < 1024) return `${bytes} B`;
		if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
		return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
	}

	function startEditConfig() {
		editingConfig = true;
		editDescription = data?.activity_info?.description || '';
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
			success = $_('fileEval.grading.syncSuccess').replace(/synced.*/, 'updated');
		} catch (e) {
			error = e.message;
		}
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
					aVal = studentSortKey(a);
					bVal = studentSortKey(b);
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
				return sortDirection === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
			}
			return sortDirection === 'asc' ? aVal - bVal : bVal - aVal;
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
			selectedIds = new Set(allSubmissionIds());
		} catch (e) {
			error = e.message;
		}
		loading = false;
	}

	async function handleEvaluateSelected() {
		const ids = [...selectedIds];
		if (!ids.length) return;
		evaluating = true;
		error = '';
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
			if (['completed', 'completed_with_errors', 'idle'].includes(evalStatus.overall_status)) {
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
				const detail =
					result.error ||
					(result.results
						?.filter((r) => !r.success)
						.map((r) => `${r.student_id}: ${r.error || '?'}`)
						.join(' · ')) ||
					'Sync failed';
				error = detail;
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

	function statusBadgeClass(status) {
		switch (status) {
			case 'completed': return 'bg-green-100 text-green-800';
			case 'error': return 'bg-red-100 text-red-800';
			case 'processing': return 'bg-yellow-100 text-yellow-800';
			default: return 'bg-gray-100 text-gray-800';
		}
	}

	function isGroupActivity() {
		return (data?.setup_config?.submission_type || 'individual') === 'group';
	}

	function hasEvaluator() {
		return !!data?.setup_config?.evaluator_id?.trim();
	}
</script>

<div class="bg-gray-50 min-h-screen">
	<div class="max-w-5xl mx-auto px-4 py-6">

		{#if error}
			<div class="mb-4 rounded-xl border border-red-200 bg-red-50 p-4 text-red-700">{error}</div>
		{/if}
		{#if success}
			<div class="mb-4 rounded-xl border border-green-200 bg-green-50 p-4 text-green-700">{success}</div>
		{/if}

		{#if loading}
			<div class="flex justify-center p-12">
				<div class="h-8 w-8 animate-spin rounded-full border-b-2 border-blue-600"></div>
			</div>
		{:else if data}

			<!-- Header Card -->
			{#if data.activity_info}
				<div class="bg-white rounded-xl shadow-sm border p-6 mb-6">
					<div class="flex items-center gap-3">
						<div class="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center text-xl shrink-0">
							<svg class="h-5 w-5 text-purple-600" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
						</div>
						<div>
							<h1 class="text-xl font-bold text-gray-900">{data.activity_info.title || $_('fileEval.grading.title')}</h1>
							<p class="text-sm text-gray-500">
								{#if data.activity_info.context_title}{data.activity_info.context_title}{/if}{#if data.activity_info.context_title && data.activity_info.org_name} · {/if}{#if data.activity_info.org_name}{data.activity_info.org_name}{/if}
							</p>
							<p class="text-xs text-gray-400 mt-0.5">
								{#if data.activity_info.owner_display}{$_('fileEval.grading.owner')}: {data.activity_info.owner_display}{/if}
								{#if data.activity_info.created_at} · {$_('fileEval.grading.created')} {formatTime(data.activity_info.created_at)}{/if}
							</p>
						</div>
					</div>
				</div>
			{/if}

			<!-- Activity Settings Card -->
			{#if data.activity_info}
				<div class="bg-white rounded-xl shadow-sm border p-6 mb-6">
					<div class="flex items-center justify-between mb-4">
						<h2 class="text-lg font-semibold text-gray-900">{$_('fileEval.grading.activityConfig')}</h2>
						{#if editingConfig}
							<div class="flex gap-2">
								<button onclick={saveConfig} class="inline-flex items-center gap-1 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
									<svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>
									{$_('fileEval.grading.save')}
								</button>
								<button onclick={cancelEditConfig} class="rounded-lg bg-gray-100 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-200">
									{$_('fileEval.grading.cancel')}
								</button>
							</div>
						{:else}
							<button onclick={startEditConfig} class="rounded-lg bg-blue-50 px-4 py-2 text-sm font-medium text-blue-700 hover:bg-blue-100">
								{$_('fileEval.grading.editConfig')}
							</button>
						{/if}
					</div>

					{#if editingConfig}
						<div class="space-y-4">
							<div>
								<label class="block text-sm font-medium text-gray-700 mb-1">{$_('fileEval.grading.description')}</label>
								<textarea
									class="w-full rounded-lg border border-gray-300 p-3 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
									rows="3"
									bind:value={editDescription}
									placeholder={$_('fileEval.grading.descriptionPlaceholder')}
								></textarea>
							</div>
							<div class="flex gap-4">
								<div class="flex-1">
									<label class="block text-sm font-medium text-gray-700 mb-1">{$_('fileEval.grading.deadlineDate')}</label>
									<input type="date" class="w-full rounded-lg border border-gray-300 p-2 text-sm" bind:value={editDeadlineDate} />
								</div>
								<div class="w-40">
									<label class="block text-sm font-medium text-gray-700 mb-1">{$_('fileEval.grading.deadlineTime')}</label>
									<input type="time" class="w-full rounded-lg border border-gray-300 p-2 text-sm" bind:value={editDeadlineTime} />
								</div>
							</div>
						</div>
					{:else}
						<div class="space-y-3 text-sm text-gray-600">
							{#if data.activity_info.description}
								<p class="whitespace-pre-wrap">{data.activity_info.description}</p>
							{:else}
								<p class="italic text-gray-400">{$_('fileEval.grading.noDescription')}</p>
							{/if}
							{#if data.activity_info.deadline}
								<p class="flex items-center gap-2">
									<span class="font-medium">{$_('fileEval.grading.deadline')}:</span>
									<span class={isDeadlinePast(data.activity_info.deadline) ? 'text-red-600' : 'text-green-600'}>
										{formatDeadlineDisplay(data.activity_info.deadline)}
									</span>
									{#if isDeadlinePast(data.activity_info.deadline)}
										<span class="rounded bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">{$_('fileEval.grading.deadlinePassed')}</span>
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

			<!-- Stats Cards -->
			{#if data.stats}
				<div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
					<div class="bg-white rounded-xl shadow-sm border p-4 text-center">
						<div class="text-2xl font-bold text-gray-900">{data.stats.total_submissions || 0}</div>
						<div class="text-xs text-gray-500 mt-1">{$_('fileEval.grading.stats.total')}</div>
					</div>
					<div class="bg-white rounded-xl shadow-sm border p-4 text-center">
						<div class="text-2xl font-bold text-gray-900">{data.stats.evaluated || 0}</div>
						<div class="text-xs text-gray-500 mt-1">{$_('fileEval.grading.stats.evaluated')}</div>
					</div>
					<div class="bg-white rounded-xl shadow-sm border p-4 text-center">
						<div class="text-2xl font-bold text-gray-900">{data.stats.graded || 0}</div>
						<div class="text-xs text-gray-500 mt-1">{$_('fileEval.grading.stats.graded')}</div>
					</div>
					<div class="bg-white rounded-xl shadow-sm border p-4 text-center">
						<div class="text-2xl font-bold text-gray-900">{data.stats.sent_to_moodle || 0}</div>
						<div class="text-xs text-gray-500 mt-1">{$_('fileEval.grading.stats.sentToMoodle')}</div>
					</div>
				</div>
			{/if}

			<!-- Submissions Section -->
			<div class="bg-white rounded-xl shadow-sm border p-6">
				<div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
					<h2 class="text-lg font-semibold text-gray-900">
						{isGroupActivity() ? $_('fileEval.grading.submissionsTitleGroup') : $_('fileEval.grading.submissionsTitleIndividual')}
					</h2>

					{#if data.submissions?.length > 0}
						<div class="flex flex-wrap gap-2">
							<button
								onclick={handleEvaluateSelected}
								disabled={evaluating || !hasEvaluator() || selectedIds.size === 0}
								class="inline-flex items-center gap-1.5 rounded-lg bg-purple-600 px-4 py-2 text-sm font-medium text-white hover:bg-purple-700 disabled:opacity-50"
							>
								<svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" /></svg>
								{evaluating ? $_('fileEval.grading.evaluating') : $_('fileEval.grading.aiEvaluation')}
							</button>
							<button
								onclick={handleAcceptAll}
								class="inline-flex items-center gap-1.5 rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700"
							>
								<svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
								{$_('fileEval.grading.acceptAll')}
							</button>
							<button
								onclick={handleSyncMoodle}
								disabled={syncing}
								class="inline-flex items-center gap-1.5 rounded-lg bg-amber-600 px-4 py-2 text-sm font-medium text-white hover:bg-amber-700 disabled:opacity-50"
							>
								<svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" /></svg>
								{syncing ? $_('fileEval.grading.syncing') : $_('fileEval.grading.syncMoodle')}
							</button>
						</div>
					{/if}
				</div>

				<!-- Evaluator warning -->
				{#if !hasEvaluator()}
					<div class="mb-4 flex items-center gap-2 rounded-lg bg-amber-50 border border-amber-200 px-4 py-3 text-sm text-amber-800">
						<svg class="h-5 w-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
						{$_('fileEval.grading.evaluatorWarning')}
					</div>
				{/if}

				<!-- Evaluation progress -->
				{#if evaluating && evalStatus}
					<div class="mb-4 rounded-lg border bg-yellow-50 p-4">
						<div class="mb-2 flex items-center justify-between">
							<p class="font-medium">{$_('fileEval.grading.evalProgress')}</p>
							<p class="text-sm text-gray-600">{$_('fileEval.status.' + evalStatus.overall_status)}</p>
						</div>
						<div class="h-3 w-full overflow-hidden rounded-full bg-gray-200">
							<div
								class="h-full bg-gradient-to-r from-blue-500 to-purple-600 transition-all duration-500"
								style="width: {evalStatus.counts?.completed ? ((evalStatus.counts.completed / (evalStatus.counts.pending + evalStatus.counts.processing + evalStatus.counts.completed + evalStatus.counts.error || 1)) * 100) : 0}%"
							></div>
						</div>
						<div class="mt-2 flex flex-wrap gap-4 text-sm">
							<span class="text-gray-600">{$_('fileEval.status.pending')}: {evalStatus.counts?.pending || 0}</span>
							<span class="text-blue-600">{$_('fileEval.status.processing')}: {evalStatus.counts?.processing || 0}</span>
							<span class="text-green-600">{$_('fileEval.status.completed')}: {evalStatus.counts?.completed || 0}</span>
							<span class="text-red-600">{$_('fileEval.status.error')}: {evalStatus.counts?.error || 0}</span>
						</div>
					</div>
				{/if}

				{#if data.submissions?.length > 0}
					<!-- Submission count + sort & pagination controls -->
					<div class="mb-3 flex flex-wrap items-center justify-between gap-2 text-sm">
						<span class="text-gray-600 font-medium">
							{$_('fileEval.grading.submissionsFound', { values: { count: data.submissions.length } })}
						</span>
						<div class="flex items-center gap-3">
							<span class="text-gray-500">{$_('fileEval.grading.sortBy')}:</span>
							<div class="flex gap-1">
								<button onclick={() => handleSort('file_name')} class="rounded-md px-2 py-1 {sortField === 'file_name' ? 'bg-blue-100 text-blue-700 font-medium' : 'text-gray-600 hover:bg-gray-100'}">
									{$_('fileEval.grading.table.file')} {getSortIcon('file_name')}
								</button>
								<button onclick={() => handleSort('uploaded_at')} class="rounded-md px-2 py-1 {sortField === 'uploaded_at' ? 'bg-blue-100 text-blue-700 font-medium' : 'text-gray-600 hover:bg-gray-100'}">
									{$_('fileEval.grading.table.uploadedAt')} {getSortIcon('uploaded_at')}
								</button>
								<button onclick={() => handleSort('evaluation_status')} class="rounded-md px-2 py-1 {sortField === 'evaluation_status' ? 'bg-blue-100 text-blue-700 font-medium' : 'text-gray-600 hover:bg-gray-100'}">
									{$_('fileEval.grading.table.status')} {getSortIcon('evaluation_status')}
								</button>
							</div>
						</div>
						<div class="flex items-center gap-2">
							<label class="text-gray-500">{$_('fileEval.grading.perPage')}:</label>
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
					</div>

					<!-- Select all checkbox -->
					<label class="mb-4 flex items-center gap-2 text-sm text-gray-600 cursor-pointer select-none">
						<input
							type="checkbox"
							checked={isAllSelected()}
							onchange={toggleSelectAll}
							class="h-4 w-4 rounded border-gray-300 text-purple-600 focus:ring-purple-500"
						/>
						{$_('fileEval.grading.selectAll')}
					</label>

					<!-- Submission cards -->
					<div class="space-y-4">
						{#each getPaginatedSubmissions() as sub}
							{@const fs = sub.file_submission}
							{@const grade = sub.grade}
							{@const isEditing = editingGrade === fs?.id}
							<div class="rounded-lg border border-gray-200 bg-gray-50 overflow-hidden">
								<!-- Card header -->
								<div class="flex items-center justify-between px-5 py-3 bg-white border-b border-gray-100">
									<div class="flex items-center gap-3">
										<input
											type="checkbox"
											checked={selectedIds.has(fs?.id)}
											onchange={() => toggleSelected(fs?.id)}
											class="h-4 w-4 rounded border-gray-300 text-purple-600 focus:ring-purple-500"
										/>
										<span class="font-semibold text-gray-900">
											{fs?.group_display_name || memberLabel(sub.members?.[0])}
										</span>
										{#if (sub.member_count || sub.members?.length || 1) > 1}
											<span class="inline-flex items-center rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700">
												{sub.member_count || sub.members?.length || 1} {(sub.member_count || sub.members?.length || 1) === 1 ? $_('fileEval.grading.table.member') : $_('fileEval.grading.table.members')}
											</span>
										{/if}
										<span class="inline-block rounded-full px-2 py-0.5 text-xs font-medium {statusBadgeClass(fs?.evaluation_status)}">
											{$_('fileEval.status.' + (fs?.evaluation_status || 'not_started'))}
										</span>
									</div>
									<button
										onclick={() => handleDownload(fs.id, fs?.file_name)}
										class="inline-flex items-center gap-1 rounded-lg bg-gray-100 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-200"
									>
										<svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" /></svg>
										{$_('fileEval.grading.table.download')}
									</button>
								</div>

								<!-- Card body -->
								<div class="px-5 py-4 space-y-3">
									<!-- File info — filename is clickable for download -->
									<div class="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-gray-600">
										<button
											type="button"
											onclick={() => handleDownload(fs.id, fs?.file_name)}
											class="flex items-center gap-1 text-blue-600 hover:text-blue-800 hover:underline font-medium"
										>
											<svg class="h-4 w-4 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" /></svg>
											{fs?.file_name || 'N/A'}
										</button>
										{#if fs?.file_size}
											<span class="text-gray-400">{formatFileSize(fs.file_size)}</span>
										{/if}
										<span class="flex items-center gap-1 text-gray-400">
											<svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
											{formatTime(fs?.uploaded_at)}
										</span>
									</div>

									<!-- Student note — always visible -->
									<div class="rounded-lg bg-amber-50 border border-amber-100 px-4 py-2.5">
										<p class="text-xs font-medium text-amber-700 mb-0.5">
											<svg class="inline h-3.5 w-3.5 mr-0.5 -mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z" /></svg>
											{$_('fileEval.grading.studentNote')}
										</p>
										<p class="text-sm {fs?.student_note ? 'text-amber-900' : 'text-amber-400 italic'}">
											{fs?.student_note || $_('fileEval.grading.noStudentNote')}
										</p>
									</div>

									<!-- Members -->
									{#if sub.members?.length}
										<div class="text-sm">
											<p class="text-xs font-medium text-gray-500 mb-1">{isGroupActivity() ? $_('fileEval.grading.table.group') + ':' : $_('fileEval.grading.table.student') + ':'}</p>
											<div class="flex flex-wrap gap-2">
												{#each sub.members as m}
													<span class="inline-flex items-center gap-1 text-gray-700">
														{memberLabel(m)}
														{#if fs?.uploaded_by === m.student_id && fs?.group_code}
															<span class="rounded bg-blue-100 px-1.5 py-0.5 text-xs font-medium text-blue-700">{$_('fileEval.grading.leaderBadge')}</span>
														{/if}
													</span>
												{/each}
											</div>
										</div>
									{/if}

									<!-- Grading section -->
									<div class="border-t border-gray-200 pt-3">
										{#if isEditing}
											<div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
												<div>
													<label class="block text-xs font-medium text-gray-500 mb-1">{$_('fileEval.grading.finalScore')}</label>
													<input type="number" min="0" max="10" step="0.1" class="w-full rounded-lg border border-gray-300 p-2 text-sm" bind:value={editScore} placeholder="Ej: 8.5" />
												</div>
												<div class="sm:col-span-2">
													<label class="block text-xs font-medium text-gray-500 mb-1">{$_('fileEval.grading.comment')}</label>
													<textarea class="w-full rounded-lg border border-gray-300 p-2 text-sm" rows="2" bind:value={editComment} placeholder={$_('fileEval.grading.commentPlaceholder')}></textarea>
												</div>
											</div>
											<div class="flex gap-2 mt-2">
												<button onclick={() => saveGrade(fs.id)} class="rounded-lg bg-blue-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-blue-700">
													{$_('fileEval.grading.saveGrade')}
												</button>
												<button onclick={() => editingGrade = null} class="rounded-lg bg-gray-100 px-4 py-1.5 text-sm text-gray-700 hover:bg-gray-200">
													{$_('fileEval.grading.cancel')}
												</button>
											</div>
										{:else}
											<div class="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
												<div>
													<span class="text-gray-500">{$_('fileEval.grading.table.aiScore')}:</span>
													<span class="ml-1 font-medium">{grade?.ai_score != null ? `${grade.ai_score}/10` : '-'}</span>
												</div>
												{#if grade?.ai_score != null}
													<div class="basis-full mt-1">
														<div class="flex flex-wrap items-center gap-2 text-sm">
															<span class="text-gray-500">{$_('fileEval.grading.aiComment')}:</span>
															{#if !isAiCommentExpanded(fs.id)}
																<button
																	type="button"
																	onclick={() => setAiCommentExpanded(fs.id, true)}
																	class="rounded-md bg-gray-100 px-2 py-1 text-xs font-medium text-gray-700 hover:bg-gray-200"
																>
																	{$_('fileEval.grading.showAiComment')}
																</button>
															{:else}
																<button
																	type="button"
																	onclick={() => setAiCommentExpanded(fs.id, false)}
																	class="rounded-md bg-gray-100 px-2 py-1 text-xs font-medium text-gray-700 hover:bg-gray-200"
																>
																	{$_('fileEval.grading.hideAiComment')}
																</button>
															{/if}
														</div>
														{#if isAiCommentExpanded(fs.id) && grade?.ai_comment}
															<div
																class="ai-feedback-md prose prose-sm max-w-none mt-2 rounded-lg border border-gray-200 bg-white p-3 text-gray-800 [&_p]:my-2 [&_p:first-child]:mt-0 [&_p:last-child]:mb-0 [&_ul]:my-2 [&_ol]:my-2 [&_li]:my-0.5"
															>
																<!-- eslint-disable-next-line svelte/no-at-html-tags -->
																{@html aiFeedbackMarkdownToHtml(grade.ai_comment)}
															</div>
														{/if}
													</div>
												{/if}
												<div>
													<span class="text-gray-500">{$_('fileEval.grading.table.finalScore')}:</span>
													<span class="ml-1 font-medium">{grade?.score != null ? `${grade.score}/10` : '-'}</span>
												</div>
												{#if grade?.comment}
													<div class="basis-full text-gray-600 italic">{grade.comment}</div>
												{/if}
												<button
													onclick={() => startEditGrade(sub)}
													class="ml-auto rounded-lg bg-gray-100 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-200"
												>
													{$_('fileEval.grading.editGrade')}
												</button>
											</div>
										{/if}
									</div>
								</div>
							</div>
						{/each}
					</div>

					<!-- Pagination bottom -->
					<div class="mt-4 flex flex-wrap items-center justify-between gap-2">
						<div class="text-sm text-gray-600">
							{$_('fileEval.grading.showing', {
								values: {
									from: (currentPage - 1) * perPage + 1,
									to: Math.min(currentPage * perPage, data.submissions.length),
									total: data.submissions.length
								}
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
								{:else if pageNum === currentPage + 2 && getTotalPages() > currentPage + 2}
									<span class="px-2">...</span>
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
					<!-- Empty state -->
					<div class="py-16 text-center">
						<svg class="mx-auto h-12 w-12 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
						<h3 class="mt-3 text-base font-semibold text-gray-900">{$_('fileEval.grading.noSubmissions')}</h3>
						<p class="mt-1 text-sm text-gray-500">{$_('fileEval.grading.noSubmissionsHint')}</p>
					</div>
				{/if}
			</div>

		{/if}
	</div>
</div>
