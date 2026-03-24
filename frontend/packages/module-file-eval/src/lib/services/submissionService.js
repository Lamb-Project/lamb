import { apiFetch, apiUpload } from './api.js';

/**
 * @param {number|string} activityId
 * @param {File} file
 * @param {string} [studentNote]
 */
export async function uploadFile(activityId, file, studentNote = '') {
	const fd = new FormData();
	fd.append('file', file);
	if (studentNote) fd.append('student_note', studentNote);
	return apiUpload(`/activities/${activityId}/submissions`, fd);
}

/** @param {number|string} activityId */
export async function getMySubmission(activityId) {
	return apiFetch(`/submissions/me?activity_id=${activityId}`);
}

/** @param {string} groupCode @param {number|string} activityId */
export async function joinGroup(groupCode, activityId) {
	return apiFetch(`/submissions/join?activity_id=${activityId}`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ group_code: groupCode })
	});
}

/** @param {string} fileSubmissionId */
export async function getGroupMembers(fileSubmissionId) {
	return apiFetch(`/submissions/${fileSubmissionId}/members`);
}

/** @param {number|string} activityId */
export async function downloadMyFile(activityId) {
	const token = new URLSearchParams(window.location.search).get('token') || '';
	const cfg = /** @type {any} */ (window).LAMB_CONFIG || {};
	const base = cfg.API_BASE_URL || '';
	const url = `${base}/lamb/v1/modules/file_evaluation/submissions/my-file/download?activity_id=${activityId}&token=${token}`;
	const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
	if (!res.ok) throw new Error(`HTTP ${res.status}`);
	const blob = await res.blob();
	const a = document.createElement('a');
	a.href = URL.createObjectURL(blob);
	const cd = res.headers.get('content-disposition') || '';
	const match = cd.match(/filename="?([^"]+)"?/);
	a.download = match ? match[1] : 'download';
	a.click();
	URL.revokeObjectURL(a.href);
}
