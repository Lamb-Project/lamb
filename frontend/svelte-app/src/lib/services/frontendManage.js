/** Finite frontend command vocabulary. No model-provided URLs or DOM selectors. */
import { goto } from '$app/navigation';
import { base } from '$app/paths';
import { apiJson } from '$lib/services/apiClient';
export const tabs = { assistant: ['properties', 'tests', 'chat'], kb: ['files', 'ingest', 'query'] };
let dirty = false;
export function markWorkspaceDirty() { dirty = true; }
export function clearWorkspaceDirty() { dirty = false; }
export function destinationUrl(target) {
    if (!tabs[target.resource]?.includes(target.tab) || !/^[1-9]\d*$/.test(String(target.id))) throw new Error('Unsupported frontend destination');
    const route = target.resource === 'assistant' ? 'assistants' : 'knowledgebases';
    return `${base}/${route}?view=detail&id=${target.id}&aacTab=${target.tab}`;
}
export function workspaceContext() {
    const el = document.querySelector('main [data-aac-resource]');
    return { route: window.location.pathname, ...(el ? { resource: el.dataset.aacResource, id: el.dataset.aacId, tab: el.dataset.aacTab } : {}) };
}
export async function applyFrontendAction(action, signal) {
    if (signal?.aborted) return { status: 'failed', reason: 'Turn ended' };
    if (action.operation === 'current') return { status: 'current', ...workspaceContext() };
    if (action.operation !== 'open') return { status: 'failed', reason: 'Unsupported frontend operation' };
    if (dirty) return { status: 'blocked', reason: 'The workspace has unsaved input. Finish saving or navigate manually before asking again.' };
    try {
        const url = destinationUrl(action) + `&aacRequest=${encodeURIComponent(action.action_id || crypto.randomUUID())}`;
        await goto(url, { keepFocus: true });
        for (let i = 0; i < 80; i++) {
            if (signal?.aborted) return { status: 'failed', reason: 'Turn ended before navigation was confirmed' };
            const current = workspaceContext();
            if (current.resource === action.resource && current.id === String(action.id) && current.tab === action.tab) return { status: 'opened', ...current };
            await new Promise(resolve => setTimeout(resolve, 100));
        }
        return { status: 'failed', reason: 'The requested resource/tab did not finish loading' };
    } catch (_) { return { status: 'failed', reason: 'Unable to open the requested resource' }; }
}
/** Poll only for this live turn. Never replay a session transcript. */
export async function serveFrontend(sessionId, channel, signal) {
    const seen = new Set();
    while (!signal.aborted) {
        try {
            const actions = await apiJson(`/aac/sessions/${sessionId}/frontend?channel=${channel}`, { signal });
            for (const action of actions) {
                if (signal.aborted || seen.has(action.action_id)) continue;
                seen.add(action.action_id);
                const result = await applyFrontendAction(action, signal);
                if (!signal.aborted) await apiJson(`/aac/sessions/${sessionId}/frontend/${action.action_id}`, {
                    method: 'POST', body: JSON.stringify({ channel, ...result }), signal,
                });
            }
        } catch (_) { if (signal.aborted) return; }
        await new Promise(resolve => setTimeout(resolve, 400));
    }
}
