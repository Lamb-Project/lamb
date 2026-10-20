import { apiFetch } from './api.js';

/** @param {number|string} activityId */
export async function getActivityView(activityId) {
	return apiFetch(`/activities/${activityId}/view`);
}

/** @param {number|string} activityId */
export async function getSubmissions(activityId) {
	return apiFetch(`/activities/${activityId}/submissions`);
}

/** @param {number|string} activityId @param {string[]} fileSubmissionIds */
export async function startEvaluation(activityId, fileSubmissionIds) {
	return apiFetch(`/activities/${activityId}/evaluate`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ file_submission_ids: fileSubmissionIds })
	});
}

/** @param {number|string} activityId */
export async function getEvaluationStatus(activityId) {
	return apiFetch(`/activities/${activityId}/evaluation-status`);
}

/** @param {string} fileSubmissionId @param {number} score @param {string} [comment] */
export async function updateGrade(fileSubmissionId, score, comment) {
	return apiFetch(`/grades/${fileSubmissionId}`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ score, comment })
	});
}

/** @param {number|string} activityId */
export async function acceptAiGrades(activityId) {
	return apiFetch(`/grades/activity/${activityId}/accept-ai-grades`, { method: 'POST' });
}

/** @param {number|string} activityId */
export async function syncGradesToMoodle(activityId) {
	return apiFetch(`/activities/${activityId}/grades/sync`, { method: 'POST' });
}

/**
 * Download a submission file by file_submission_id
 * @param {string} fileSubmissionId
 * @param {string} fileName
 */
export async function downloadSubmission(fileSubmissionId, fileName) {
	const token = new URLSearchParams(window.location.search).get('token') || '';
	const cfg = /** @type {any} */ (window).LAMB_CONFIG || {};
	const base = cfg.API_BASE_URL || '';
	const url = `${base}/lamb/v1/modules/file_evaluation/submissions/${fileSubmissionId}/download?token=${token}`;
	const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
	if (!res.ok) throw new Error(`HTTP ${res.status}`);
	const blob = await res.blob();
	const a = document.createElement('a');
	a.href = URL.createObjectURL(blob);
	const cd = res.headers.get('content-disposition') || '';
	const match = cd.match(/filename="?([^"]+)"?/);
	a.download = match ? match[1] : fileName || 'download';
	a.click();
	URL.revokeObjectURL(a.href);
}

/**
 * Update activity configuration (description, deadline)
 * @param {number|string} activityId
 * @param {Object} config
 * @param {string} [config.description]
 * @param {number} [config.deadline] Unix timestamp in seconds
 */
export async function updateActivityConfig(activityId, config) {
	return apiFetch(`/activities/${activityId}/setup-config`, {
		method: 'PUT',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(config)
	});
}
