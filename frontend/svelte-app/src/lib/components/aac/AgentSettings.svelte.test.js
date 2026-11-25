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
const settings = () => ({provider:'',model:'',language_fallbacks:{},pack_line:'stable',pack_dev_mode:false,utility_provider:'',utility_model:''});
const about = '## What changed\n\nGuides are advice.\n\n## Guides in this version\n\n| Guide | What it helps with |\n|---|---|\n| `create-assistant` | Guide through creating a new assistant |\n';
const lines = () => [
    {line:'stable',version:'1.13.6',development:false,summary:'The pack that ships with this LAMB.',about},
    {line:'legacy-1',version:null,development:false,summary:'',about:''},
    {line:'legacy-2',version:null,development:false,summary:'',about:''},
    {line:'rc',version:null,development:true,summary:'',about:''},
    {line:'beta',version:'2.0-beta.1',development:true,summary:'Being written: guidance only.',about:'## What changed\n\nNew.\n'},
];
const response = (overrides={}) => ({settings:settings(),models:{ollama:['qwen'],openai:['hosted']},inherited_model:{provider:'ollama',model:'qwen'},pack_lines:lines(),pack_notice:null,tools_reference:'# Installed command reference\n- lamb assistant create',...overrides});

describe('organisation agent settings', () => {
    beforeEach(() => {
        cleanup();vi.clearAllMocks();locale.set('en');localStorage.setItem('userToken','fixture-token');
        axios.get.mockResolvedValue({data:response()});
        axios.put.mockImplementation(async (_, payload) => ({data:{settings:JSON.parse(JSON.stringify(payload))}}));
    });
    it('saves explicit driver and fallback for the selected organisation, following the stable line', async () => {
        render(AgentSettings,{org:'my school'});
        const provider = await screen.findByRole('combobox',{name:'LAMB LEGATUS provider'});
        await fireEvent.change(provider,{target:{value:'ollama'}});
        await fireEvent.change(screen.getByRole('combobox',{name:'LAMB LEGATUS model'}),{target:{value:'qwen'}});
        await fireEvent.change(screen.getByRole('combobox',{name:'Euskara fallback'}),{target:{value:'es'}});
        await fireEvent.click(screen.getByRole('button',{name:'Save LAMB LEGATUS settings'}));
        await screen.findByRole('status');
        expect(axios.put).toHaveBeenCalledWith('/creator/admin/org-admin/settings/aac?org=my%20school',expect.objectContaining({provider:'ollama',model:'qwen',language_fallbacks:{eu:'es'},pack_line:'stable',pack_dev_mode:false}),{headers:{Authorization:'Bearer fixture-token'}});
        expect(axios.put.mock.calls[0][1]).not.toHaveProperty('pack_version');
    });
    it('offers only the stable line, with its version, summary and document, until development mode is on', async () => {
        const {container} = render(AgentSettings);
        const group = await screen.findByRole('radiogroup',{name:'Knowledge pack line'});
        expect([...container.querySelectorAll('[data-pack-line]')].map(e => e.dataset.packLine)).toEqual(['stable']);
        expect(group).toHaveTextContent('Stable');expect(group).toHaveTextContent('1.13.6');
        expect(group).toHaveTextContent('The pack that ships with this LAMB.');
        expect(screen.queryByRole('combobox',{name:'Pinned version'})).toBeNull();
        expect(container.querySelector('[data-pack-about]')).toBeNull();
        await fireEvent.click(screen.getByRole('button',{name:'What is in this version'}));
        const document = container.querySelector('[data-pack-about="stable"]');
        expect(document.querySelector('h2')).toHaveTextContent('What changed');
        expect(document.querySelector('table')).toHaveTextContent('create-assistant');
        expect(screen.getByText('Tools in this LAMB version')).toBeInTheDocument();
        expect(container.querySelector('details pre')).toHaveTextContent('lamb assistant create');
    });
    it('shows rc and beta in development mode, saves the beta, and returns to stable when the mode is left', async () => {
        const {container} = render(AgentSettings);
        await screen.findByRole('radiogroup',{name:'Knowledge pack line'});
        await fireEvent.click(screen.getByRole('checkbox',{name:/Development mode/}));
        expect([...container.querySelectorAll('[data-pack-line]')].map(e => e.dataset.packLine)).toEqual(['stable','rc','beta']);
        const [stable, rc, beta] = screen.getAllByRole('radio');
        expect(rc).toBeDisabled();
        expect(container.querySelector('[data-pack-line="rc"]')).toHaveTextContent('none at the moment');
        await fireEvent.click(beta);
        await fireEvent.click(screen.getByRole('button',{name:'Save LAMB LEGATUS settings'}));
        await screen.findByRole('status');
        expect(axios.put.mock.calls[0][1]).toEqual(expect.objectContaining({pack_line:'beta',pack_dev_mode:true}));
        await fireEvent.click(screen.getByRole('checkbox',{name:/Development mode/}));
        expect(screen.getAllByRole('radio')).toHaveLength(1);
        await fireEvent.click(screen.getByRole('button',{name:'Save LAMB LEGATUS settings'}));
        await waitFor(() => expect(axios.put).toHaveBeenCalledTimes(2));
        expect(axios.put.mock.calls[1][1]).toEqual(expect.objectContaining({pack_line:'stable',pack_dev_mode:false}));
        expect(stable).toBeDefined();
    });
    it('shows a previous version when one is installed and says once that an exact version is no longer followed', async () => {
        const rows = lines();rows[1] = {line:'legacy-1',version:'1.13.6',development:false,summary:'The pack of the previous LAMB.',about:''};rows[0].version='2.0';
        axios.get.mockResolvedValue({data:response({pack_lines:rows,pack_notice:{retired_version:'1.0.0',line:'stable'}})});
        const {container} = render(AgentSettings);
        await screen.findByRole('radiogroup',{name:'Knowledge pack line'});
        expect([...container.querySelectorAll('[data-pack-line]')].map(e => e.dataset.packLine)).toEqual(['stable','legacy-1']);
        expect(container.querySelector('[data-pack-line="legacy-1"]')).toHaveTextContent('Previous version');
        expect(container.querySelector('[data-pack-notice]')).toHaveTextContent('had chosen version 1.0.0, which is no longer installed');
        await fireEvent.click(screen.getAllByRole('radio')[1]);
        await fireEvent.click(screen.getByRole('button',{name:'Save LAMB LEGATUS settings'}));
        await screen.findByRole('status');
        expect(axios.put.mock.calls[0][1].pack_line).toBe('legacy-1');
        expect(container.querySelector('[data-pack-notice]')).toBeNull();
    });
    it('renders labels in every frontend locale without changing API values', async () => {
        for (const [code, label] of [['es','Proveedor de LAMB LEGATUS'],['ca','Proveïdor de LAMB LEGATUS'],['eu','LAMB LEGATUSen hornitzailea']]) {
            locale.set(code);render(AgentSettings);
            const provider = await screen.findByRole('combobox',{name:label});
            expect(provider).toHaveValue('');
            expect(provider.querySelector('option[value="ollama"]')).not.toBeNull();
            expect(screen.getByRole('radiogroup',{name:{es:'Línea del paquete de conocimiento',ca:'Línia del paquet de coneixement',eu:'Ezagutza-paketearen lerroa'}[code]})).toBeInTheDocument();
            cleanup();
        }
    });
    it('allows a named model when the catalogue is unknown and preserves saved utility selection', async () => {
        axios.get.mockResolvedValue({data:response({models:{ollama:[]},settings:{...settings(),provider:'ollama',model:'existing',utility_provider:'ollama',utility_model:'utility'}})});
        render(AgentSettings);
        const model = await screen.findByRole('textbox',{name:'LAMB LEGATUS model'});
        expect(model).toHaveValue('existing');
        expect(screen.getByRole('textbox',{name:'Utility model'})).toHaveValue('utility');
        await fireEvent.input(model,{target:{value:'named-model'}});
        await fireEvent.click(screen.getByRole('button',{name:'Save LAMB LEGATUS settings'}));
        await screen.findByRole('status');
        expect(axios.put.mock.calls[0][1].model).toBe('named-model');
    });
    it('keeps the unsaved selection and exposes a rejected policy without claiming success', async () => {
        axios.put.mockRejectedValue({response:{data:{detail:'Fallbacks cannot form cycles'}}});
        render(AgentSettings);
        await screen.findByRole('combobox',{name:'LAMB LEGATUS provider'});
        await fireEvent.change(screen.getByRole('combobox',{name:'Euskara fallback'}),{target:{value:'es'}});
        await fireEvent.click(screen.getByRole('button',{name:'Save LAMB LEGATUS settings'}));
        expect(await screen.findByRole('alert')).toHaveTextContent('Fallbacks cannot form cycles');
        expect(screen.queryByRole('status')).toBeNull();
        expect(screen.getByRole('combobox',{name:'Euskara fallback'})).toHaveValue('es');
    });
});
