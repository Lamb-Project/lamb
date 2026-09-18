import {describe,it,expect,vi,beforeEach} from 'vitest';
import {render,screen,fireEvent,waitFor} from '@testing-library/svelte';
import {get} from 'svelte/store';
vi.mock('$app/navigation',()=>({beforeNavigate:vi.fn()}));
vi.mock('$lib/services/learningScenarios',()=>({listScenarios:vi.fn(),getScenario:vi.fn(),selectedScenario:vi.fn(),createScenario:vi.fn(),updateScenario:vi.fn(),removeScenario:vi.fn(),duplicateScenario:vi.fn(),defaultScenario:vi.fn()}));
vi.mock('$lib/services/aacService',()=>({createSession:vi.fn()}));
import {listScenarios,getScenario,selectedScenario,updateScenario} from '$lib/services/learningScenarios';
import {createSession} from '$lib/services/aacService';
import {sidebarBusy,activeTabId,resetSidebar,showSession} from '$lib/stores/aacStore.svelte';
import Editor from './LearningScenarios.svelte';
const item={id:'owned',title:'Teacher demonstrations',content:'Known audience and purpose',revision:1};
beforeEach(()=>{resetSidebar();vi.clearAllMocks();listScenarios.mockResolvedValue({scenarios:[item],default_id:null});getScenario.mockResolvedValue({...item});createSession.mockResolvedValue({id:'new-chat',title:'Scenario help'});});
it('keeps the document visible and reuses the matching conversation when asking the agent',async()=>{
 showSession('existing-chat');selectedScenario.mockResolvedValue({scenario_id:'owned'});
 render(Editor,{initialId:'owned'});
 await screen.findByText(item.content);
 await fireEvent.click(screen.getByRole('button',{name:'Edit with agent'}));
 await waitFor(()=>expect(selectedScenario).toHaveBeenCalledWith('existing-chat'));
 expect(createSession).not.toHaveBeenCalled();expect(get(activeTabId)).toBe('existing-chat');
 expect(screen.getByText(item.content)).toBeVisible();
});
it('refreshes saved content only after a turn, without polling',async()=>{
 render(Editor,{initialId:'owned'});await screen.findByText(item.content);
 getScenario.mockResolvedValue({...item,content:'Saved by agent',revision:2});
 const calls=getScenario.mock.calls.length;
 sidebarBusy.set(true);expect(getScenario.mock.calls.length).toBe(calls);
 sidebarBusy.set(false);
 await screen.findByText('Saved by agent');expect(getScenario.mock.calls.length).toBe(calls+1);
});
it('preserves an unsaved manual draft when a newer revision is saved elsewhere',async()=>{
 render(Editor,{initialId:'owned'});await screen.findByText(item.content);
 await fireEvent.click(screen.getByRole('button',{name:'Edit',exact:true}));
 const input=screen.getByRole('textbox',{name:'Content'});await fireEvent.input(input,{target:{value:'My unsaved draft'}});
 getScenario.mockResolvedValue({...item,content:'Agent version',revision:2});
 sidebarBusy.set(true);sidebarBusy.set(false);
 await screen.findByRole('status');expect(input.value).toBe('My unsaved draft');
 expect(screen.getByRole('button',{name:'Reload saved version'})).toBeVisible();
});

it('edits and displays the structured Moodle course link',async()=>{
 getScenario.mockResolvedValue({...item,links:{moodle_course_id:10}});
 updateScenario.mockImplementation(async draft=>({...draft,revision:2}));
 render(Editor,{initialId:'owned'});await screen.findByText('Moodle course ID: 10');
 await fireEvent.click(screen.getByRole('button',{name:'Edit',exact:true}));
 await fireEvent.input(screen.getByRole('spinbutton'),{target:{value:'20'}});
 await fireEvent.click(screen.getByRole('button',{name:'Save',exact:true}));
 await screen.findByText('Moodle course ID: 20');
 expect(updateScenario.mock.calls[0][0].links).toEqual({moodle_course_id:20});
});
