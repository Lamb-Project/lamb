import { apiJson } from '$lib/services/apiClient';

/** Administrators acting as a creator (#523). */
/** @param {number | string} userId */
export const startTakeover = userId => apiJson(`/admin/users/${encodeURIComponent(userId)}/takeover`, { method: 'POST' });
export const currentTakeover = () => apiJson('/takeover/current');
export const endTakeover = () => apiJson('/takeover/end', { method: 'POST' });
export const takeoverNotices = () => apiJson('/user/takeover-notices');
/** @param {string[]} ids */
export const dismissTakeoverNotices = ids => apiJson('/user/takeover-notices/ack', { method: 'POST', body: JSON.stringify({ ids }) });
