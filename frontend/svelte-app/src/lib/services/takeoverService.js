import { apiJson, apiFetch } from '$lib/services/apiClient';

/** Administrators acting as a creator (#523). */
/** @param {number | string} userId */
export const startTakeover = userId => apiJson(`/admin/users/${encodeURIComponent(userId)}/takeover`, { method: 'POST' });
/**
 * The takeover this session belongs to. A rejected token means it ended or expired, which is
 * expected here, so the global 401 handler (which clears the session) is bypassed.
 * @param {string} token
 */
export async function currentTakeover(token) {
	const res = await apiFetch('/takeover/current', { skipAuth: true, headers: { Authorization: `Bearer ${token}` } });
	return res.ok ? res.json() : { active: false };
}
export const endTakeover = () => apiJson('/takeover/end', { method: 'POST' });
export const takeoverNotices = () => apiJson('/user/takeover-notices');
/** @param {string[]} ids */
export const dismissTakeoverNotices = ids => apiJson('/user/takeover-notices/ack', { method: 'POST', body: JSON.stringify({ ids }) });
