/** Finite frontend command vocabulary. No model-provided URLs or DOM selectors. */
import { frontendDestination } from '$lib/stores/aacStore.svelte';
import { goto } from '$app/navigation';
import { base } from '$app/paths';
import { apiJson } from '$lib/services/apiClient';
export const tabs = { assistant: ['properties', 'tests', 'chat', 'activity', 'edit'], kb: ['files', 'ingest', 'query'], rubric: ['view'] };
const dirtyForms = new Set();
let manualDirty = false;
export function markWorkspaceDirty(event) {
    if (!event) { manualDirty = true; return; }
    const target = event.target;
    if (!target?.matches?.('input, textarea, select') || target.disabled || target.readOnly) return;
    const form = target.closest('form, [data-aac-edit-form]');
    if (form && !form.matches('[data-aac-transient], [role="search"]')) dirtyForms.add(form);
}
export function clearWorkspaceDirty(form) {
    if (form) dirtyForms.delete(form);
    else { dirtyForms.clear(); manualDirty = false; }
}
function hasUnsavedChanges() {
    for (const form of dirtyForms) {
        if (!form.isConnected || form.closest('dialog:not([open]), [hidden]')) dirtyForms.delete(form);
    }
    return manualDirty || dirtyForms.size > 0;
}
export function destinationUrl(target) {
    if (target.resource === 'moodle-result' && target.tab === 'view' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(target.id)) return `${base}/moodle?result=${target.id}`;
    if (target.resource === 'learning-scenarios' && target.id === '' && target.tab === '') return `${base}/learning-scenarios?view=list`;
    if (target.resource === 'learning-scenario' && ['view','edit'].includes(target.tab) && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(target.id)) return `${base}/learning-scenarios?id=${target.id}&aacTab=${target.tab}`;

    if (['assistants', 'assistant-create'].includes(target.resource) && target.id === '' && target.tab === '') return `${base}/assistants?view=${target.resource === 'assistants' ? 'list' : 'create'}`;
    if (target.resource === 'rubric' && target.tab === 'view' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(target.id)) return `${base}/evaluaitor/${target.id}?aacTab=view`;
    if (target.resource === 'rubric') throw new Error('Unsupported rubric destination');
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
    if (hasUnsavedChanges()) return { status: 'blocked', reason: 'The workspace has input changes. Finish your edits and navigate manually; AAC will not move this page.' };
    try {
        const url = destinationUrl(action) + `&aacRequest=${encodeURIComponent(action.action_id || crypto.randomUUID())}`;
        await goto(url, { keepFocus: true });
        for (let i = 0; i < 80; i++) {
            if (signal?.aborted) return { status: 'failed', reason: 'Turn ended before navigation was confirmed' };
            const current = workspaceContext();
            if (current.resource === action.resource && current.id === String(action.id) && current.tab === action.tab) {
                frontendDestination.set(current);
                return { status: 'opened', ...current };
            }
            await new Promise(resolve => setTimeout(resolve, 100));
        }
        return { status: 'failed', reason: 'The requested resource/tab did not finish loading' };
    } catch (_) { return { status: 'failed', reason: 'Unable to open the requested resource' }; }
}
/** Live stream events only. A server-side claim rejects expired or replayed actions. */
export async function serveFrontendAction(sessionId, channel, action, signal) {
    if (signal?.aborted) return;
    try {
        const started = performance.now();
        const grant = await apiJson(`/aac/sessions/${sessionId}/frontend/${action.action_id}/claim`, {
            method: 'POST', body: JSON.stringify({ channel }), signal,
        });
        if (signal?.aborted || grant?.valid_for_ms !== 5000 || performance.now() - started >= grant.valid_for_ms) return;
        const result = await applyFrontendAction(action, signal);
        if (!signal?.aborted) await apiJson(`/aac/sessions/${sessionId}/frontend/${action.action_id}`, {
            method: 'POST', body: JSON.stringify({ channel, ...result }), signal,
        });
    } catch (_) { /* No confirmed ack: the server reports an unconfirmed action. */ }
}
