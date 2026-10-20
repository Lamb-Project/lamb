import { apiJson } from './apiClient';
const q = org => (org ? `?org=${encodeURIComponent(org)}` : '');
export const getTokenDealerSettings = org => apiJson('/admin/org-admin/settings/token-dealer' + q(org));
export const saveTokenDealerSettings = (settings, org = null) =>
    apiJson('/admin/org-admin/settings/token-dealer' + q(org), {method:'PUT', body:JSON.stringify(settings)});
export const getTokenDealerUsage = org => apiJson('/admin/org-admin/token-dealer/usage' + q(org));
