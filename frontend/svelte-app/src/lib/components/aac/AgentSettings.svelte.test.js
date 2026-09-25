import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/svelte';
import { addMessages, init, locale } from 'svelte-i18n';
import en from '$lib/locales/en.json';
import es from '$lib/locales/es.json';
import ca from '$lib/locales/ca.json';
import eu from '$lib/locales/eu.json';
vi.mock('axios', () => ({default: {get: vi.fn(), put: vi.fn()}}));
vi.mock('$lib/config', () => ({getApiUrl: path => '/creator'+path}));
import axios from 'axios';
import AgentSettings from './AgentSettings.svelte';

for (const [code, messages] of Object.entries({en, es, ca, eu})) addMessages(code, messages);
init({fallbackLocale:'en', initialLocale:'en'});
const settings = () => ({provider:'',model:'',language_fallbacks:{},pack_channel:'stable',pack_version:'',utility_provider:'',utility_model:''});
const response = (overrides={}) => ({settings:settings(),models:{ollama:['qwen'],openai:['hosted']},inherited_model:{provider:'ollama',model:'qwen'},pack_versions:['1.0.0','1.1.0'],...overrides});

describe('organisation agent settings', () => {
    beforeEach(() => {
        cleanup();vi.clearAllMocks();locale.set('en');localStorage.setItem('userToken','fixture-token');
        axios.get.mockResolvedValue({data:response()});
        axios.put.mockImplementation(async (_, payload) => ({data:{settings:JSON.parse(JSON.stringify(payload))}}));
    });
    it('saves explicit driver, fallback and pack pin for the selected organisation', async () => {
        render(AgentSettings,{org:'my school'});
        const provider = await screen.findByRole('combobox',{name:'Agent provider'});
        await fireEvent.change(provider,{target:{value:'ollama'}});
        await fireEvent.change(screen.getByRole('combobox',{name:'Agent model'}),{target:{value:'qwen'}});
        await fireEvent.change(screen.getByRole('combobox',{name:'Euskara fallback'}),{target:{value:'es'}});
        await fireEvent.change(screen.getByRole('combobox',{name:'Pinned version'}),{target:{value:'1.1.0'}});
        expect(screen.getByRole('combobox',{name:'Release channel'})).toBeDisabled();
        await fireEvent.click(screen.getByRole('button',{name:'Save agent settings'}));
        await screen.findByRole('status');
        expect(axios.put).toHaveBeenCalledWith('/creator/admin/org-admin/settings/aac?org=my%20school',expect.objectContaining({provider:'ollama',model:'qwen',language_fallbacks:{eu:'es'},pack_version:'1.1.0'}),{headers:{Authorization:'Bearer fixture-token'}});
    });
    it('renders labels in every frontend locale without changing API values', async () => {
        for (const [code, label] of [['es','Proveedor del agente'],['ca','Proveïdor de l’agent'],['eu','Agentearen hornitzailea']]) {
            locale.set(code);render(AgentSettings);
            const provider = await screen.findByRole('combobox',{name:label});
            expect(provider).toHaveValue('');
            expect(provider.querySelector('option[value="ollama"]')).not.toBeNull();
            cleanup();
        }
    });
    it('allows a named model when the catalogue is unknown and preserves saved utility selection', async () => {
        axios.get.mockResolvedValue({data:response({models:{ollama:[]},settings:{...settings(),provider:'ollama',model:'existing',utility_provider:'ollama',utility_model:'utility'}})});
        render(AgentSettings);
        const model = await screen.findByRole('textbox',{name:'Agent model'});
        expect(model).toHaveValue('existing');
        expect(screen.getByRole('textbox',{name:'Utility model'})).toHaveValue('utility');
        await fireEvent.input(model,{target:{value:'named-model'}});
        await fireEvent.click(screen.getByRole('button',{name:'Save agent settings'}));
        await screen.findByRole('status');
        expect(axios.put.mock.calls[0][1].model).toBe('named-model');
    });
    it('keeps the unsaved selection and exposes a rejected policy without claiming success', async () => {
        axios.put.mockRejectedValue({response:{data:{detail:'Fallbacks cannot form cycles'}}});
        render(AgentSettings);
        await screen.findByRole('combobox',{name:'Agent provider'});
        await fireEvent.change(screen.getByRole('combobox',{name:'Euskara fallback'}),{target:{value:'es'}});
        await fireEvent.click(screen.getByRole('button',{name:'Save agent settings'}));
        expect(await screen.findByRole('alert')).toHaveTextContent('Fallbacks cannot form cycles');
        expect(screen.queryByRole('status')).toBeNull();
        expect(screen.getByRole('combobox',{name:'Euskara fallback'})).toHaveValue('es');
    });
});
