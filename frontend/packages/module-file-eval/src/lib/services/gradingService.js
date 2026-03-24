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
