<script>
	import { onMount } from 'svelte';
	import { _ } from 'svelte-i18n';
	import { setLocale, supportedLocales } from '@lamb/ui';
	import {
		uploadFile,
		getMySubmission,
		joinGroup,
		downloadMyFile,
		getGroupMembers
	} from '$lib/services/submissionService.js';
	import { getActivityView } from '$lib/services/gradingService.js';
	import { getActivityId } from '$lib/services/api.js';

	let activityId = $state('');
	let activityView = $state(null);
	let submission = $state(null);
	/** @type {Array<{student_id: string, student_name?: string, joined_at?: number}>} */
	let groupMembers = $state([]);
	let loading = $state(true);
	let uploading = $state(false);
	let joining = $state(false);
	let error = $state('');
	let success = $state('');
	let codeCopied = $state(false);

	/** Unix seconds, ms, or ISO date string → Date | null */
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

	function formatDeadlineLong(deadline) {
		const d = parseDeadline(deadline);
		if (!d) return '';
		return new Intl.DateTimeFormat(undefined, {
			dateStyle: 'long',
			timeStyle: 'short'
		}).format(d);
	}

	/** @param {number | null | undefined} ts Unix seconds */
	function formatUploadedAt(ts) {
		if (!ts) return '';
		return new Intl.DateTimeFormat(undefined, {
			dateStyle: 'long',
			timeStyle: 'short'
		}).format(new Date(ts * 1000));
	}

	function isDeadlinePast(deadline) {
		const d = parseDeadline(deadline);
		if (!d) return false;
		return Date.now() > d.getTime();
	}

	function isGroupActivity() {
		return (activityView?.setup_config?.submission_type || 'individual') === 'group';
	}

	function maxGroupSize() {
		const n = Number(activityView?.setup_config?.max_group_size);
		return Number.isFinite(n) && n > 0 ? n : null;
	}

	/** True when the student is in a group activity and already has a submission */
	function showGroupSubmissionLayout() {
		return isGroupActivity() && !!submission;
	}

	/** True when the logged-in student is the group leader (uploaded the file) */
	function isGroupLeader() {
		return submission?.is_group_leader === true;
	}

	/** True when the student is in a group but did NOT upload the file */
	function isGroupMemberOnly() {
		return showGroupSubmissionLayout() && !isGroupLeader();
	}

	/**
	 * Returns true if the given member row represents the group leader.
	 * @param {{ student_id: string }} m
	 */
	function isLeaderMember(m) {
		return m?.student_id === submission?.file_submission?.uploaded_by;
	}

	let selectedFile = $state(null);
	let studentNote = $state('');
	let groupCodeInput = $state('');
	let dragOver = $state(false);

	onMount(async () => {
		activityId = getActivityId();

		if (!activityId) {
			error = 'No activity ID';
			loading = false;
			return;
		}

		try {
			activityView = await getActivityView(activityId);
			const actLang = activityView?.setup_config?.language?.toLowerCase();
			if (actLang && supportedLocales.includes(actLang)) {
				setLocale(actLang);
			}
			if (activityView?.submission) {
				submission = activityView.submission;
			}
		} catch (e) {
			try {
				submission = await getMySubmission(activityId);
			} catch {
				/* first visit, no submission yet */
			}
		}

		// Fetch group members if applicable
		if (submission?.file_submission?.id && isGroupActivity()) {
			try {
				groupMembers = await getGroupMembers(submission.file_submission.id);
			} catch {
				groupMembers = [];
			}
		}

		loading = false;
	});

	function handleDrop(e) {
		e.preventDefault();
		dragOver = false;
		if (e.dataTransfer?.files?.length) {
			selectedFile = e.dataTransfer.files[0];
		}
	}

	function handleFileSelect(e) {
		if (e.target?.files?.length) {
			selectedFile = e.target.files[0];
		}
	}

	async function handleUpload() {
		if (!selectedFile) return;
		uploading = true;
		error = '';
		success = '';
		try {
			const result = await uploadFile(activityId, selectedFile, studentNote);
			submission = result.submission || result;
			// Refresh members after (re)upload in group mode
			if (submission?.file_submission?.id && isGroupActivity()) {
				try {
					groupMembers = await getGroupMembers(submission.file_submission.id);
				} catch {
					groupMembers = [];
				}
			}
			success = $_('fileEval.upload.submitted');
			selectedFile = null;
			studentNote = '';
		} catch (e) {
			error = e.message;
		}
		uploading = false;
	}

	/** @type {Record<string, string>} */
	const joinErrorI18nMap = {
		group_full: 'fileEval.upload.groupJoinFull',
		invalid_group_code: 'fileEval.upload.groupJoinInvalidCode',
		already_in_group: 'fileEval.upload.groupJoinAlreadyMember',
		already_submitted_activity: 'fileEval.upload.groupJoinAlreadySubmitted'
	};

	async function handleJoinGroup() {
		if (!groupCodeInput.trim()) return;
		joining = true;
		error = '';
		try {
			const result = await joinGroup(groupCodeInput.trim(), activityId);
			submission = result.submission || result;
			if (submission?.file_submission?.id) {
				try {
					groupMembers = await getGroupMembers(submission.file_submission.id);
				} catch {
					groupMembers = [];
				}
			}
			success = $_('fileEval.upload.submitted');
		} catch (e) {
			const key = e.code && joinErrorI18nMap[e.code];
			error = key ? $_(key) : (e.message || String(e));
		}
		joining = false;
	}

	async function handleDownload() {
		try {
			await downloadMyFile(activityId);
		} catch (e) {
			error = e.message;
		}
	}

	async function copyGroupCode() {
		const code = submission?.file_submission?.group_code;
		if (!code) return;
		try {
			await navigator.clipboard.writeText(code);
			codeCopied = true;
			setTimeout(() => (codeCopied = false), 2500);
		} catch {
			/* clipboard not available — silently ignore */
		}
	}

	function formatFileSize(bytes) {
		if (!bytes) return '';
		if (bytes < 1024) return `${bytes} B`;
		if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
		return `${(bytes / 1048576).toFixed(1)} MB`;
	}
</script>

<div class="bg-gray-50 min-h-screen">
	<div class="max-w-5xl mx-auto px-4 py-8">

		{#if loading}
			<div class="flex items-center justify-center py-12">
				<div class="h-8 w-8 animate-spin rounded-full border-b-2 border-blue-600"></div>
			</div>
		{:else}

			<!-- Feedback banners -->
			{#if error}
				<div class="mb-4 rounded-lg border border-red-200 bg-red-50 p-4 text-red-700">{error}</div>
			{/if}
			{#if success}
				<div class="mb-4 rounded-lg border border-green-200 bg-green-50 p-4 text-green-700">{success}</div>
			{/if}

			<!-- Activity header -->
			<div class="bg-white rounded-xl shadow-sm border p-6 mb-4">
				<h1 class="text-2xl font-bold text-gray-900 mb-1">
					{activityView?.activity_info?.title || $_('fileEval.upload.title')}
				</h1>
				{#if activityView?.activity_info?.context_title}
					<p class="text-sm text-gray-500 mb-3">{activityView.activity_info.context_title}</p>
				{/if}
				{#if activityView?.activity_info?.description}
					<p class="text-gray-700 whitespace-pre-wrap">{activityView.activity_info.description}</p>
				{:else}
					<p class="text-gray-400 italic text-sm">{$_('fileEval.upload.noDescription')}</p>
				{/if}
			</div>

			<!-- Group banner -->
			{#if isGroupActivity() && maxGroupSize() !== null}
				<div class="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 mb-4 text-sm font-medium text-blue-800">
					{$_('fileEval.upload.groupMaxStudents', { values: { count: maxGroupSize() } })}
				</div>
			{/if}

			<!-- ═══════════════════════════════════════════════════════════
			     BRANCH A: Group member (joined, cannot replace)
			     ═══════════════════════════════════════════════════════════ -->
			{#if isGroupMemberOnly()}
				<!-- Status card — joined -->
				<div class="bg-green-50 rounded-xl border border-green-200 p-6 mb-4">
					<div class="flex items-center gap-2 mb-4">
						<svg class="h-5 w-5 text-green-600 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
						</svg>
						<h2 class="text-lg font-semibold text-green-900">{$_('fileEval.upload.statusJoinedGroup')}</h2>
					</div>

					<div class="space-y-1.5 text-sm text-gray-700 mb-4">
						<p>
							<span class="font-medium text-gray-500">{$_('fileEval.upload.submissionFileLabel')}:</span>
							{submission.file_submission?.file_name || '—'}
							{#if submission.file_submission?.file_size}
								<span class="text-gray-400 ml-1">({formatFileSize(submission.file_submission.file_size)})</span>
							{/if}
						</p>
						{#if submission.file_submission?.uploaded_at}
							<p>
								<span class="font-medium text-gray-500">{$_('fileEval.upload.submissionSentLabel')}:</span>
								{formatUploadedAt(submission.file_submission.uploaded_at)}
							</p>
						{/if}
						{#if submission.file_submission?.group_code}
							<p>
								<span class="font-medium text-gray-500">{$_('fileEval.upload.groupCode')}:</span>
								<span class="font-mono font-semibold tracking-widest">{submission.file_submission.group_code}</span>
							</p>
						{/if}
					</div>

					<button onclick={handleDownload} class="rounded-lg bg-white border border-gray-200 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50">
						{$_('fileEval.upload.download')}
					</button>
				</div>

				<!-- Grade info -->
				{#if submission.grade}
					<div class="bg-white rounded-xl shadow-sm border p-4 mb-4 text-sm space-y-1">
						{#if submission.grade.ai_score != null}
							<p><span class="font-medium">{$_('fileEval.upload.aiGrade')}:</span> {submission.grade.ai_score}/10</p>
						{/if}
						{#if submission.grade.score != null}
							<p class="text-lg font-bold">{$_('fileEval.upload.grade')}: {submission.grade.score}/10</p>
						{/if}
					</div>
				{:else if submission.student_submission && !submission.student_submission.sent_to_moodle}
					<p class="mb-4 rounded-lg bg-amber-50 border border-amber-100 p-3 text-sm text-amber-900">
						{$_('fileEval.upload.gradePendingMoodle')}
					</p>
				{/if}

				<!-- Group members list -->
				{#if groupMembers.length > 0}
					<div class="bg-white rounded-xl shadow-sm border p-5">
						<h3 class="text-sm font-semibold text-gray-700 mb-3">{$_('fileEval.upload.groupMembersTitle')}</h3>
						<ul class="divide-y divide-gray-100">
							{#each groupMembers as member}
								<li class="flex items-center justify-between py-2 text-sm">
									<span class="text-gray-800">{member.student_name || member.student_id}</span>
									{#if isLeaderMember(member)}
										<span class="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
											{$_('fileEval.grading.leaderBadge')}
										</span>
									{/if}
								</li>
							{/each}
						</ul>
					</div>
				{/if}

			<!-- ═══════════════════════════════════════════════════════════
			     BRANCH B: Group leader (can replace submission)
			     ═══════════════════════════════════════════════════════════ -->
			{:else if showGroupSubmissionLayout() && isGroupLeader()}
				<!-- Status card — leader -->
				<div class="bg-green-50 rounded-xl border border-green-200 p-6 mb-4">
					<div class="flex items-center gap-2 mb-4">
						<svg class="h-5 w-5 text-green-600 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
						</svg>
						<h2 class="text-lg font-semibold text-green-900">{$_('fileEval.upload.statusDocumentSentLeader')}</h2>
					</div>

					<div class="space-y-1.5 text-sm text-gray-700 mb-4">
						<p>
							<span class="font-medium text-gray-500">{$_('fileEval.upload.submissionFileLabel')}:</span>
							{submission.file_submission?.file_name || '—'}
							{#if submission.file_submission?.file_size}
								<span class="text-gray-400 ml-1">({formatFileSize(submission.file_submission.file_size)})</span>
							{/if}
						</p>
						{#if submission.file_submission?.uploaded_at}
							<p>
								<span class="font-medium text-gray-500">{$_('fileEval.upload.submissionSentLabel')}:</span>
								{formatUploadedAt(submission.file_submission.uploaded_at)}
							</p>
						{/if}
						{#if submission.file_submission?.group_display_name}
							<p>
								<span class="font-medium text-gray-500">{$_('fileEval.upload.groupLabel')}:</span>
								{submission.file_submission.group_display_name}
							</p>
						{/if}
					</div>

					<div class="flex flex-wrap gap-2">
						<button onclick={handleDownload} class="rounded-lg bg-white border border-gray-200 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50">
							{$_('fileEval.upload.download')}
						</button>
					</div>
				</div>

				<!-- Group code highlight block -->
				{#if submission.file_submission?.group_code}
					<div class="bg-white rounded-xl border border-amber-200 p-5 mb-4">
						<p class="text-xs font-medium text-amber-700 uppercase tracking-wide mb-1">{$_('fileEval.upload.groupCode')}</p>
						<div class="flex items-center gap-3">
							<span class="font-mono text-2xl font-bold tracking-widest text-amber-900 select-all">
								{submission.file_submission.group_code}
							</span>
							<button
								onclick={copyGroupCode}
								class="rounded-lg px-3 py-1.5 text-xs font-medium border
									{codeCopied
										? 'border-green-300 bg-green-50 text-green-700'
										: 'border-amber-200 bg-amber-50 text-amber-800 hover:bg-amber-100'}"
							>
								{codeCopied ? $_('fileEval.upload.codeCopied') : $_('fileEval.upload.copyGroupCode')}
							</button>
						</div>
					</div>
				{/if}

				<!-- Grade info -->
				{#if submission.grade}
					<div class="bg-white rounded-xl shadow-sm border p-4 mb-4 text-sm space-y-1">
						{#if submission.grade.ai_score != null}
							<p><span class="font-medium">{$_('fileEval.upload.aiGrade')}:</span> {submission.grade.ai_score}/10</p>
						{/if}
						{#if submission.grade.score != null}
							<p class="text-lg font-bold">{$_('fileEval.upload.grade')}: {submission.grade.score}/10</p>
						{/if}
					</div>
				{:else if submission.student_submission && !submission.student_submission.sent_to_moodle}
					<p class="mb-4 rounded-lg bg-amber-50 border border-amber-100 p-3 text-sm text-amber-900">
						{$_('fileEval.upload.gradePendingMoodle')}
					</p>
				{/if}

				<!-- Group members list -->
				{#if groupMembers.length > 0}
					<div class="bg-white rounded-xl shadow-sm border p-5 mb-4">
						<h3 class="text-sm font-semibold text-gray-700 mb-3">{$_('fileEval.upload.groupMembersTitle')}</h3>
						<ul class="divide-y divide-gray-100">
							{#each groupMembers as member}
								<li class="flex items-center justify-between py-2 text-sm">
									<span class="text-gray-800">{member.student_name || member.student_id}</span>
									{#if isLeaderMember(member)}
										<span class="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
											{$_('fileEval.grading.leaderBadge')}
										</span>
									{/if}
								</li>
							{/each}
						</ul>
					</div>
				{/if}

				<!-- Replace submission section -->
				<div class="bg-white rounded-xl shadow-sm border p-6">
					<div class="mb-5">
						<h2 class="text-lg font-semibold text-gray-900">
							{$_('fileEval.upload.sectionGroupSubmission')}
						</h2>
						{#if activityView?.activity_info?.deadline}
							<p class="mt-1 text-sm flex items-center gap-2">
								<span class="font-medium text-gray-600">{$_('fileEval.upload.deadlineLabel')}:</span>
								<span class="{isDeadlinePast(activityView.activity_info.deadline) ? 'text-red-600 font-medium' : 'text-green-600'}">
									{formatDeadlineLong(activityView.activity_info.deadline)}
								</span>
								{#if isDeadlinePast(activityView.activity_info.deadline)}
									<span class="rounded bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">
										{$_('fileEval.upload.deadlinePassed')}
									</span>
								{/if}
							</p>
						{/if}
					</div>
					<h3 class="font-medium text-gray-700 mb-3">{$_('fileEval.upload.resubmit')}</h3>

					<div
						class="rounded-lg border-2 border-dashed p-8 text-center transition-colors mb-4
							{dragOver ? 'border-blue-500 bg-blue-50' : 'border-gray-300 bg-gray-50'}"
						ondragover={(e) => { e.preventDefault(); dragOver = true; }}
						ondragleave={() => (dragOver = false)}
						ondrop={handleDrop}
						role="button"
						tabindex="0"
					>
						{#if selectedFile}
							<p class="text-lg font-medium text-gray-800">{selectedFile.name}</p>
							<p class="text-sm text-gray-500">{formatFileSize(selectedFile.size)}</p>
						{:else}
							<svg class="mx-auto mb-2 h-10 w-10 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" /></svg>
							<p class="text-gray-500">{$_('fileEval.upload.dropzone')}</p>
							<p class="mt-1 text-xs text-gray-400">{$_('fileEval.upload.formats')}</p>
						{/if}
						<input type="file" class="mt-3" onchange={handleFileSelect} accept=".pdf,.docx,.doc,.txt,.md" />
					</div>

					<label for="student-note-leader-replace" class="mb-1 block text-sm font-medium text-gray-700">
						{$_('fileEval.upload.noteLabel')}
					</label>
					<textarea
						id="student-note-leader-replace"
						class="w-full rounded-lg border border-gray-200 p-3 text-sm"
						rows="3"
						placeholder={$_('fileEval.upload.notePlaceholder')}
						bind:value={studentNote}
					></textarea>

					<button
						onclick={handleUpload}
						disabled={!selectedFile || uploading}
						class="mt-4 w-full rounded-lg bg-blue-600 px-6 py-3 font-medium text-white hover:bg-blue-700 disabled:opacity-50"
					>
						{uploading ? $_('fileEval.upload.submitting') : $_('fileEval.upload.submit')}
					</button>
				</div>

			<!-- ═══════════════════════════════════════════════════════════
			     BRANCH C: Group activity, no submission yet → two columns
			     ═══════════════════════════════════════════════════════════ -->
			{:else if isGroupActivity() && !submission}
				<div class="bg-white rounded-xl shadow-sm border p-6">
					<div class="mb-5">
						<h2 class="text-lg font-semibold text-gray-900">{$_('fileEval.upload.sectionGroupSubmission')}</h2>
						{#if activityView?.activity_info?.deadline}
							<p class="mt-1 text-sm flex items-center gap-2">
								<span class="font-medium text-gray-600">{$_('fileEval.upload.deadlineLabel')}:</span>
								<span class="{isDeadlinePast(activityView.activity_info.deadline) ? 'text-red-600 font-medium' : 'text-green-600'}">
									{formatDeadlineLong(activityView.activity_info.deadline)}
								</span>
								{#if isDeadlinePast(activityView.activity_info.deadline)}
									<span class="rounded bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">
										{$_('fileEval.upload.deadlinePassed')}
									</span>
								{/if}
							</p>
						{/if}
					</div>

					<div class="grid grid-cols-1 md:grid-cols-2 gap-6">
						<!-- Option 1: upload + create group -->
						<div class="rounded-lg border border-gray-200 p-5">
							<h3 class="font-semibold text-gray-900 mb-1">{$_('fileEval.upload.optionUploadLeader')}</h3>
							<p class="text-sm text-gray-500 mb-4">{$_('fileEval.upload.optionUploadLeaderHint')}</p>

							<div
								class="rounded-lg border-2 border-dashed p-6 text-center transition-colors mb-4
									{dragOver ? 'border-blue-500 bg-blue-50' : 'border-gray-300 bg-gray-50'}"
								ondragover={(e) => { e.preventDefault(); dragOver = true; }}
								ondragleave={() => (dragOver = false)}
								ondrop={handleDrop}
								role="button"
								tabindex="0"
							>
								{#if selectedFile}
									<p class="font-medium text-gray-800">{selectedFile.name}</p>
									<p class="text-xs text-gray-500">{formatFileSize(selectedFile.size)}</p>
								{:else}
									<svg class="mx-auto mb-2 h-8 w-8 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" /></svg>
									<p class="text-sm text-gray-500">{$_('fileEval.upload.dropzone')}</p>
									<p class="mt-1 text-xs text-gray-400">{$_('fileEval.upload.formats')}</p>
								{/if}
								<input type="file" class="mt-3 text-sm" onchange={handleFileSelect} accept=".pdf,.docx,.doc,.txt,.md" />
							</div>

							<label for="student-note-leader" class="block text-sm font-medium text-gray-700 mb-1">
								{$_('fileEval.upload.noteLabel')}
							</label>
							<textarea
								id="student-note-leader"
								class="w-full rounded-lg border border-gray-200 p-3 text-sm mb-4"
								rows="3"
								placeholder={$_('fileEval.upload.notePlaceholder')}
								bind:value={studentNote}
							></textarea>

							<button
								onclick={handleUpload}
								disabled={!selectedFile || uploading}
								class="w-full rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
							>
								{uploading ? $_('fileEval.upload.submitting') : $_('fileEval.upload.submitCreateGroup')}
							</button>
						</div>

						<!-- Option 2: join with code -->
						<div class="rounded-lg border border-gray-200 p-5">
							<h3 class="font-semibold text-gray-900 mb-1">{$_('fileEval.upload.optionJoinCode')}</h3>
							<p class="text-sm text-gray-500 mb-4">{$_('fileEval.upload.optionJoinHint')}</p>

							<label for="join-code-input" class="block text-sm font-medium text-gray-700 mb-1">
								{$_('fileEval.upload.groupCodeLabel')}
							</label>
							<input
								id="join-code-input"
								type="text"
								class="w-full rounded-lg border border-gray-200 px-4 py-2.5 font-mono uppercase tracking-widest text-sm mb-1"
								placeholder="EJ: ABC12345"
								maxlength="8"
								bind:value={groupCodeInput}
							/>
							<p class="text-xs text-gray-400 mb-4">{$_('fileEval.upload.groupCodeFormatHint')}</p>

							<button
								onclick={handleJoinGroup}
								disabled={joining || !groupCodeInput.trim()}
								class="w-full rounded-lg bg-green-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
							>
								{joining ? $_('fileEval.upload.joining') : $_('fileEval.upload.joinGroup')}
							</button>
						</div>
					</div>
				</div>

			<!-- ═══════════════════════════════════════════════════════════
			     BRANCH D: Individual activity (with or without submission)
			     ═══════════════════════════════════════════════════════════ -->
			{:else}
				<!-- Individual summary card (when already submitted) -->
				{#if submission}
					<div class="bg-white rounded-xl shadow-sm border p-6 mb-4">
						<h2 class="text-lg font-semibold text-gray-900 mb-3">{$_('fileEval.upload.alreadySubmitted')}</h2>
						<div class="space-y-1.5 text-sm text-gray-700">
							<p>
								<span class="font-medium text-gray-500">{$_('fileEval.upload.submissionFileLabel')}:</span>
								{submission.file_submission?.file_name || '—'}
								{#if submission.file_submission?.file_size}
									<span class="text-gray-400 ml-1">({formatFileSize(submission.file_submission.file_size)})</span>
								{/if}
							</p>
							{#if submission.file_submission?.uploaded_at}
								<p>
									<span class="font-medium text-gray-500">{$_('fileEval.upload.submissionSentLabel')}:</span>
									{formatUploadedAt(submission.file_submission.uploaded_at)}
								</p>
							{/if}
						</div>
						{#if submission.grade}
							<div class="mt-3 rounded-lg bg-gray-50 p-3 text-sm space-y-1">
								{#if submission.grade.ai_score != null}
									<p><span class="font-medium">{$_('fileEval.upload.aiGrade')}:</span> {submission.grade.ai_score}/10</p>
								{/if}
								{#if submission.grade.score != null}
									<p class="text-lg font-bold">{$_('fileEval.upload.grade')}: {submission.grade.score}/10</p>
								{/if}
							</div>
						{:else if submission.student_submission && !submission.student_submission.sent_to_moodle}
							<p class="mt-3 rounded-lg bg-amber-50 border border-amber-100 p-3 text-sm text-amber-900">
								{$_('fileEval.upload.gradePendingMoodle')}
							</p>
						{/if}
						<div class="mt-4">
							<button onclick={handleDownload} class="rounded-lg bg-gray-100 px-4 py-2 text-sm hover:bg-gray-200">
								{$_('fileEval.upload.download')}
							</button>
						</div>
					</div>
				{/if}

				<!-- Upload / replace form -->
				<div class="bg-white rounded-xl shadow-sm border p-6">
					<div class="mb-5">
						<h2 class="text-lg font-semibold text-gray-900">
							{$_('fileEval.upload.sectionIndividualSubmission')}
						</h2>
						{#if activityView?.activity_info?.deadline}
							<p class="mt-1 text-sm flex items-center gap-2">
								<span class="font-medium text-gray-600">{$_('fileEval.upload.deadlineLabel')}:</span>
								<span class="{isDeadlinePast(activityView.activity_info.deadline) ? 'text-red-600 font-medium' : 'text-green-600'}">
									{formatDeadlineLong(activityView.activity_info.deadline)}
								</span>
								{#if isDeadlinePast(activityView.activity_info.deadline)}
									<span class="rounded bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">
										{$_('fileEval.upload.deadlinePassed')}
									</span>
								{/if}
							</p>
						{/if}
					</div>

					{#if submission}
						<h3 class="font-medium text-gray-700 mb-3">{$_('fileEval.upload.resubmit')}</h3>
					{/if}

					<div
						class="rounded-lg border-2 border-dashed p-8 text-center transition-colors mb-4
							{dragOver ? 'border-blue-500 bg-blue-50' : 'border-gray-300 bg-gray-50'}"
						ondragover={(e) => { e.preventDefault(); dragOver = true; }}
						ondragleave={() => (dragOver = false)}
						ondrop={handleDrop}
						role="button"
						tabindex="0"
					>
						{#if selectedFile}
							<p class="text-lg font-medium text-gray-800">{selectedFile.name}</p>
							<p class="text-sm text-gray-500">{formatFileSize(selectedFile.size)}</p>
						{:else}
							<svg class="mx-auto mb-2 h-10 w-10 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" /></svg>
							<p class="text-gray-500">{$_('fileEval.upload.dropzone')}</p>
							<p class="mt-1 text-xs text-gray-400">{$_('fileEval.upload.formats')}</p>
						{/if}
						<input type="file" class="mt-3" onchange={handleFileSelect} accept=".pdf,.docx,.doc,.txt,.md" />
					</div>

					<label for="student-note-individual" class="mb-1 block text-sm font-medium text-gray-700">
						{$_('fileEval.upload.noteLabel')}
					</label>
					<textarea
						id="student-note-individual"
						class="w-full rounded-lg border border-gray-200 p-3 text-sm"
						rows="3"
						placeholder={$_('fileEval.upload.notePlaceholder')}
						bind:value={studentNote}
					></textarea>

					<button
						onclick={handleUpload}
						disabled={!selectedFile || uploading}
						class="mt-4 w-full rounded-lg bg-blue-600 px-6 py-3 font-medium text-white hover:bg-blue-700 disabled:opacity-50"
					>
						{uploading ? $_('fileEval.upload.submitting') : $_('fileEval.upload.submit')}
					</button>
				</div>
			{/if}

		{/if}
	</div>
</div>
