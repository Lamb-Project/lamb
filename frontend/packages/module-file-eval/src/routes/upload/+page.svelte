<script>
	import { onMount } from 'svelte';
	import { _ } from 'svelte-i18n';
	import {
		uploadFile,
		getMySubmission,
		joinGroup,
		downloadMyFile
	} from '$lib/services/submissionService.js';
	import { getActivityView } from '$lib/services/gradingService.js';
	import { getActivityId } from '$lib/services/api.js';

	let activityId = $state('');
	let activityView = $state(null);
	let submission = $state(null);
	let loading = $state(true);
	let uploading = $state(false);
	let joining = $state(false);
	let error = $state('');
	let success = $state('');

	/** Parses deadline from API: Unix seconds, ms, or ISO date string (setup_config). */
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

	function formatDate(deadline) {
		const d = parseDeadline(deadline);
		if (!d) return '';
		return d.toLocaleDateString() + ' ' + d.toLocaleTimeString();
	}

	function isDeadlinePast(deadline) {
		const d = parseDeadline(deadline);
		if (!d) return false;
		return Date.now() > d.getTime();
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
			success = $_('fileEval.upload.submitted');
			selectedFile = null;
			studentNote = '';
		} catch (e) {
			error = e.message;
		}
		uploading = false;
	}

	async function handleJoinGroup() {
		if (!groupCodeInput.trim()) return;
		joining = true;
		error = '';
		try {
			const result = await joinGroup(groupCodeInput.trim(), activityId);
			submission = result.submission || result;
			success = $_('fileEval.upload.submitted');
		} catch (e) {
			error = e.message;
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

	function formatFileSize(bytes) {
		if (!bytes) return '';
		if (bytes < 1024) return `${bytes} B`;
		if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
		return `${(bytes / 1048576).toFixed(1)} MB`;
	}
</script>

<div class="mx-auto max-w-2xl px-4 py-8">
	<h1 class="mb-6 text-2xl font-bold text-gray-800">{$_('fileEval.upload.title')}</h1>

	{#if loading}
		<div class="flex items-center justify-center py-12">
			<div class="h-8 w-8 animate-spin rounded-full border-b-2 border-blue-600"></div>
		</div>
	{:else if error}
		<div class="mb-4 rounded-lg border border-red-200 bg-red-50 p-4 text-red-700">{error}</div>
	{/if}

	{#if success}
		<div class="mb-4 rounded-lg border border-green-200 bg-green-50 p-4 text-green-700">
			{success}
		</div>
	{/if}

	<!-- Activity Info Section -->
	{#if activityView?.activity_info}
		<div class="mb-6 rounded-lg border bg-blue-50 p-5 shadow-sm">
			<h2 class="mb-3 text-lg font-semibold text-blue-900">{$_('fileEval.upload.activityInfo')}</h2>
			<div class="space-y-2 text-sm text-blue-800">
				{#if activityView.activity_info.description}
					<p class="whitespace-pre-wrap">{activityView.activity_info.description}</p>
				{/if}
				{#if activityView.activity_info.deadline}
					<p class="flex items-center gap-2">
						<span class="font-medium">{$_('fileEval.upload.deadline')}:</span>
						<span class="{isDeadlinePast(activityView.activity_info.deadline) ? 'text-red-600 font-medium' : 'text-green-600'}">
							{formatDate(activityView.activity_info.deadline)}
						</span>
						{#if isDeadlinePast(activityView.activity_info.deadline)}
							<span class="rounded bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">
								{$_('fileEval.upload.deadlinePassed')}
							</span>
						{/if}
					</p>
				{/if}
				{#if activityView.activity_info.course_name}
					<p>
						<span class="font-medium">{$_('fileEval.upload.course')}:</span>
						{activityView.activity_info.course_name}
					</p>
				{/if}
			</div>
		</div>
	{/if}

	{#if submission}
		<div class="rounded-lg border bg-white p-6 shadow-sm">
			<h2 class="mb-3 text-lg font-semibold">{$_('fileEval.upload.alreadySubmitted')}</h2>
			<div class="space-y-2 text-sm text-gray-600">
				<p>
					<span class="font-medium">File:</span>
					{submission.file_submission?.file_name || 'N/A'}
					({formatFileSize(submission.file_submission?.file_size)})
				</p>
				{#if submission.file_submission?.group_code}
					<div class="mt-3 rounded-lg bg-blue-50 p-3">
						<p class="font-medium text-blue-800">{$_('fileEval.upload.groupCode')}</p>
						<p class="font-mono text-xl tracking-widest text-blue-900">
							{submission.file_submission.group_code}
						</p>
						<p class="mt-1 text-xs text-blue-600">{$_('fileEval.upload.groupCodeHint')}</p>
					</div>
				{/if}
				{#if submission.grade}
					<div class="mt-3 rounded-lg bg-gray-50 p-3">
						{#if submission.grade.ai_score != null}
							<p>
								<span class="font-medium">{$_('fileEval.upload.aiGrade')}:</span>
								{submission.grade.ai_score}/10
							</p>
						{/if}
						{#if submission.grade.score != null}
							<p class="text-lg font-bold">
								{$_('fileEval.upload.grade')}: {submission.grade.score}/10
							</p>
						{/if}
					</div>
				{/if}
			</div>
			<div class="mt-4 flex gap-2">
				<button onclick={handleDownload} class="rounded bg-gray-100 px-4 py-2 text-sm hover:bg-gray-200">
					{$_('fileEval.upload.download')}
				</button>
			</div>
		</div>
	{/if}

	<div class="mt-6 rounded-lg border bg-white p-6 shadow-sm">
		{#if submission}
			<h3 class="mb-3 font-semibold">{$_('fileEval.upload.resubmit')}</h3>
		{/if}

		<div
			class="rounded-lg border-2 border-dashed p-8 text-center transition-colors
				{dragOver ? 'border-blue-500 bg-blue-50' : 'border-gray-300 bg-white'}"
			ondragover={(e) => {
				e.preventDefault();
				dragOver = true;
			}}
			ondragleave={() => (dragOver = false)}
			ondrop={handleDrop}
			role="button"
			tabindex="0"
		>
			{#if selectedFile}
				<p class="text-lg font-medium text-gray-800">{selectedFile.name}</p>
				<p class="text-sm text-gray-500">{formatFileSize(selectedFile.size)}</p>
			{:else}
				<p class="text-gray-500">{$_('fileEval.upload.dropzone')}</p>
				<p class="mt-1 text-xs text-gray-400">{$_('fileEval.upload.formats')}</p>
			{/if}
			<input type="file" class="mt-3" onchange={handleFileSelect} accept=".pdf,.docx,.doc,.txt,.md" />
		</div>

		<div class="mt-4">
			<label for="file-eval-student-note" class="mb-1 block text-sm font-medium text-gray-700">
				{$_('fileEval.upload.noteLabel')}
			</label>
			<textarea
				id="file-eval-student-note"
				class="w-full rounded-lg border p-3 text-sm"
				rows="3"
				placeholder={$_('fileEval.upload.notePlaceholder')}
				bind:value={studentNote}
			></textarea>
		</div>

		<button
			onclick={handleUpload}
			disabled={!selectedFile || uploading}
			class="mt-4 w-full rounded-lg bg-blue-600 px-6 py-3 font-medium text-white hover:bg-blue-700 disabled:opacity-50"
		>
			{uploading ? $_('fileEval.upload.submitting') : $_('fileEval.upload.submit')}
		</button>
	</div>

	{#if activityView?.setup_config?.submission_type === 'group' && !submission}
		<div class="mt-6 rounded-lg border bg-white p-6 shadow-sm">
			<h3 class="mb-3 font-semibold">{$_('fileEval.upload.joinGroup')}</h3>
			<div class="flex gap-2">
				<input
					type="text"
					class="flex-1 rounded-lg border px-4 py-2 font-mono uppercase"
					placeholder={$_('fileEval.upload.joinGroupPlaceholder')}
					bind:value={groupCodeInput}
				/>
				<button
					onclick={handleJoinGroup}
					disabled={joining || !groupCodeInput.trim()}
					class="rounded-lg bg-green-600 px-6 py-2 text-white hover:bg-green-700 disabled:opacity-50"
				>
					{joining ? $_('fileEval.upload.joining') : $_('fileEval.upload.joinGroup')}
				</button>
			</div>
		</div>
	{/if}
</div>
