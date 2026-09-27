import { apiJson, apiFetch } from '$lib/services/apiClient';

/** Personal API keys for the OpenAI-compatible API (#519). */
export const listApiKeys = () => apiJson('/api-keys');
export const createApiKey = (label, expiresInDays) => apiJson('/api-keys', {
	method: 'POST',
	body: JSON.stringify({ label: label || null, expires_in_days: expiresInDays || null })
});
export const revokeApiKey = id => apiJson(`/api-keys/${encodeURIComponent(id)}`, { method: 'DELETE' });

/** True when the caller's organization allows personal keys (the list endpoint answers 200). */
export async function apiKeysEnabled() {
	try { return (await apiFetch('/api-keys')).ok; } catch (_) { return false; }
}

const orgQuery = slug => (slug ? `?org=${encodeURIComponent(slug)}` : '');
export const getApiAccess = slug => apiJson(`/admin/org-admin/settings/api-access${orgQuery(slug)}`);
export const setApiAccess = (slug, enabled) => apiJson(`/admin/org-admin/settings/api-access${orgQuery(slug)}`, {
	method: 'PUT', body: JSON.stringify({ api_access: enabled })
});
