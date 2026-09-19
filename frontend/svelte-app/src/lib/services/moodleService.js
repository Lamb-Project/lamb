import { apiJson } from './apiClient';
export const moodleStatus = () => apiJson('/moodle/connection');
export const connectMoodle = credentials => apiJson('/moodle/connection', {method:'POST', body:JSON.stringify(credentials)});
export const disconnectMoodle = () => apiJson('/moodle/connection', {method:'DELETE'});
const settingsUrl = org => '/admin/org-admin/settings/moodle' + (org ? `?org=${encodeURIComponent(org)}` : '');
export const getMoodleSettings = org => apiJson(settingsUrl(org));
export const configureMoodle = (settings, org = null) => apiJson(settingsUrl(org), {method:'PUT', body:JSON.stringify(settings)});

export const connectMoodleQrImage = image => apiJson('/moodle/connection/qr-image', {method:'POST', body:image, headers:{'Content-Type':'application/octet-stream'}});
