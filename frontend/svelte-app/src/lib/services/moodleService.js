import { apiJson } from './apiClient';
export const moodleStatus = () => apiJson('/moodle/connection');
export const connectMoodle = credentials => apiJson('/moodle/connection', {method:'POST', body:JSON.stringify(credentials)});
export const disconnectMoodle = () => apiJson('/moodle/connection', {method:'DELETE'});
export const configureMoodle = settings => apiJson('/moodle/settings', {method:'PUT', body:JSON.stringify(settings)});

export const connectMoodleQrImage = image => apiJson('/moodle/connection/qr-image', {method:'POST', body:image, headers:{'Content-Type':'application/octet-stream'}});
