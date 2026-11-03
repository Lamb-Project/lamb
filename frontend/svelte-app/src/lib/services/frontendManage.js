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

/** Saved results are validated on click; no model or expiring mailbox action.
 * @param {string} sessionId
 * @param {string} reportId
 */
export async function openSavedResult(sessionId, reportId) {
    if (hasUnsavedChanges()) return {status: 'blocked', reason: 'Save your current edits before opening the result.'};
    const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
    if (!uuid.test(sessionId) || !uuid.test(reportId)) return {status: 'failed', reason: 'Invalid result reference'};
    try {
        await apiJson(`/aac/sessions/${sessionId}/reports/${reportId}`);
        await goto(`${base}/agent/reports/${sessionId}/${reportId}`, {keepFocus: true});
        return {status: 'opened'};
    } catch (e) { return {status: 'failed', reason: e instanceof Error ? e.message : String(e)}; }
}

/** @param {any} report */
export async function openReportTests(report) {
    if (hasUnsavedChanges()) return {status: 'blocked', reason: 'Save your current edits before opening the result.'};
    try {
        const url = destinationUrl(report.destination);
        const selected = report.run_ids?.[0];
        await goto(url + (selected ? `&aacRun=${encodeURIComponent(selected)}` : ''), {keepFocus: true});
        return {status: 'opened'};
    } catch (e) { return {status: 'failed', reason: e instanceof Error ? e.message : String(e)}; }
}
/** @param {any} target Saved finite destination; verify current access on every click. */
export async function openTaskResult(target) {
    if (hasUnsavedChanges()) return {status: 'blocked', reason: 'Save your current edits before opening the result.'};
    /** @type {Record<string,string>} */
    const paths = {assistant: '/assistant/get_assistant/', kb: '/knowledgebases/kb/', rubric: '/rubrics/',
        'learning-scenario': '/aac/learning-scenarios/', 'moodle-result': '/moodle/results/'};
    try {
        const url = destinationUrl(target);
        if (!paths[target.resource]) throw new Error('Unsupported result destination');
        await apiJson(paths[target.resource] + target.id);
        await goto(url, {keepFocus: true});
        return {status: 'opened'};
    } catch (e) { return {status: 'failed', reason: e instanceof Error ? e.message : String(e)}; }
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
