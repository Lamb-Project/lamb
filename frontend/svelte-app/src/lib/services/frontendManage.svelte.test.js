import { describe, it, expect, vi, beforeEach } from 'vitest';
vi.mock('$app/navigation', () => ({ goto: vi.fn() }));
vi.mock('$app/paths', () => ({ base: '' }));
vi.mock('$lib/services/apiClient', () => ({ apiJson: vi.fn() }));
import { apiJson } from '$lib/services/apiClient';
import { goto } from '$app/navigation';
import { destinationUrl, applyFrontendAction, serveFrontendAction, markWorkspaceDirty, clearWorkspaceDirty } from './frontendManage';

describe('frontend navigation contract', () => {
    beforeEach(() => { document.body.innerHTML = ''; clearWorkspaceDirty(); vi.clearAllMocks(); });
    it('maps only valid resource IDs and tabs, never arbitrary URLs', () => {
        expect(destinationUrl({ resource: 'assistant', id: '80', tab: 'tests' })).toBe('/assistants?view=detail&id=80&aacTab=tests');
        expect(destinationUrl({ resource: 'kb', id: '15', tab: 'ingest' })).toBe('/knowledgebases?view=detail&id=15&aacTab=ingest');
        for (const target of [{ resource: 'url', id: '1', tab: 'tests' }, { resource: 'assistant', id: '../1', tab: 'tests' }, { resource: 'assistant', id: '1', tab: 'delete' }]) expect(() => destinationUrl(target)).toThrow();
    });
    it('opens named pages, activity, edit and rubrics only after their ready marker appears', async () => {
        const cases = [
            [{resource:'moodle-result',id:'11111111-1111-4111-8111-111111111111',tab:'view'}, '/moodle?result=11111111-1111-4111-8111-111111111111'],
            [{resource:'assistants',id:'',tab:''}, '/assistants?view=list'],
            [{resource:'assistant-create',id:'',tab:''}, '/assistants?view=create'],
            [{resource:'assistant',id:'80',tab:'activity'}, '/assistants?view=detail&id=80&aacTab=activity'],
            [{resource:'assistant',id:'80',tab:'edit'}, '/assistants?view=detail&id=80&aacTab=edit'],
            [{resource:'rubric',id:'12345678-1234-4234-8234-123456789012',tab:'view'}, '/evaluaitor/12345678-1234-4234-8234-123456789012?aacTab=view']
        ];
        for (const [target, url] of cases) {
            document.body.innerHTML = '<main></main>';
            expect(destinationUrl(target)).toBe(url);
            goto.mockImplementationOnce(async () => {
                document.querySelector('main').innerHTML = `<span data-aac-resource="${target.resource}" data-aac-id="${target.id}" data-aac-tab="${target.tab}"></span>`;
            });
            expect(await applyFrontendAction({operation:'open', ...target})).toMatchObject({status:'opened', ...target});
        }
        for (const target of [{resource:'assistant-create',id:'1',tab:''}, {resource:'rubric',id:'../../x',tab:'view'}]) expect(() => destinationUrl(target)).toThrow();
    });
    it('requires a server claim before navigation, regardless of browser clock', async () => {
        const action={operation:'open',resource:'assistant',id:'80',tab:'tests',action_id:'a',expires:1};
        apiJson.mockRejectedValueOnce(new Error('409 expired'));
        await serveFrontendAction('s','c',action);
        expect(goto).not.toHaveBeenCalled();
        document.body.innerHTML='<main><span data-aac-resource="assistant" data-aac-id="80" data-aac-tab="tests"></span></main>';
        apiJson.mockResolvedValue({success:true,valid_for_ms:5000});
        await serveFrontendAction('s','c',action);
        expect(goto).toHaveBeenCalledOnce();
        expect(apiJson.mock.lastCall[0]).toBe('/aac/sessions/s/frontend/a');
        expect(JSON.parse(apiJson.mock.lastCall[1].body)).toMatchObject({channel:'c',status:'opened'});
    });
    it('ignores filters and queries, but retains real edits until saved or discarded', async () => {
        document.body.innerHTML='<main><input id="search"><form data-aac-transient><textarea id="query"></textarea></form><form id="edit"><input id="name"></form><form id="second"><input id="other"></form><span data-aac-resource="assistant" data-aac-id="80" data-aac-tab="tests"></span></main>';
        const action={operation:'open',resource:'assistant',id:'80',tab:'tests'};
        for(const id of ['search','query']) markWorkspaceDirty({target:document.getElementById(id)});
        expect((await applyFrontendAction(action)).status).toBe('opened');
        markWorkspaceDirty({target:document.getElementById('name')});
        markWorkspaceDirty({target:document.getElementById('other')});
        expect((await applyFrontendAction(action)).status).toBe('blocked');
        clearWorkspaceDirty(document.getElementById('edit'));
        expect((await applyFrontendAction(action)).status).toBe('blocked');
        document.getElementById('second').remove();
        expect((await applyFrontendAction(action)).status).toBe('opened');
    });
    it('blocks unsaved input without navigating', async () => {
        markWorkspaceDirty();
        expect((await applyFrontendAction({ operation: 'open', resource: 'assistant', id: '80', tab: 'tests' })).status).toBe('blocked');
        expect(goto).not.toHaveBeenCalled();
    });
    it('acknowledges the rendered target and reports current context', async () => {
        document.body.innerHTML = '<main><span data-aac-resource="assistant" data-aac-id="80" data-aac-tab="tests"></span></main>';
        const result = await applyFrontendAction({ operation: 'open', resource: 'assistant', id: '80', tab: 'tests' });
        expect(result).toMatchObject({ status: 'opened', resource: 'assistant', id: '80', tab: 'tests' });
        expect((await applyFrontendAction({ operation: 'current' })).status).toBe('current');
    });
    it('does not navigate an ended turn or claim rejected navigation worked', async () => {
        const controller = new AbortController();controller.abort();
        expect((await applyFrontendAction({ operation: 'open' }, controller.signal)).status).toBe('failed');
        expect(goto).not.toHaveBeenCalled();
        goto.mockRejectedValueOnce(new Error('navigation cancelled'));
        expect((await applyFrontendAction({ operation: 'open', resource: 'kb', id: '15', tab: 'files' })).status).toBe('failed');
    });
});
