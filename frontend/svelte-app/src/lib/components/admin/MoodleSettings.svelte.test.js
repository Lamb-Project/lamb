import {beforeEach,it,expect,vi} from 'vitest';
import {render,screen,fireEvent,cleanup} from '@testing-library/svelte';
vi.mock('$lib/services/moodleService',()=>({getMoodleSettings:vi.fn(),configureMoodle:vi.fn()}));
vi.mock('$lib/services/frontendManage',()=>({clearWorkspaceDirty:vi.fn()}));
import {getMoodleSettings,configureMoodle} from '$lib/services/moodleService';
import {clearWorkspaceDirty} from '$lib/services/frontendManage';
import Settings from './MoodleSettings.svelte';
beforeEach(()=>{cleanup();vi.resetAllMocks();getMoodleSettings.mockResolvedValue({settings:{enabled:false,base_url:'',mode:'readonly',write_groups:[],allow_grade_write:false},privacy_notice:'Privacy'});configureMoodle.mockResolvedValue({});});
it('saves selected organization policy and refreshes navigation after success',async()=>{
 const changed=vi.fn();window.addEventListener('moodle-settings-changed',changed);
 render(Settings,{org:'fixture-org'});
 const enabled=await screen.findByLabelText('Enable Moodle connector');
 await fireEvent.click(enabled);
 await fireEvent.input(screen.getByLabelText('Allowed Moodle base URL'),{target:{value:'https://moodle.test'}});
 const form=enabled.closest('form');await fireEvent.submit(form);
 await screen.findByText('Organization Moodle settings saved.');
 expect(getMoodleSettings).toHaveBeenCalledWith('fixture-org');
 expect(configureMoodle).toHaveBeenCalledWith(expect.objectContaining({enabled:true,base_url:'https://moodle.test'}),'fixture-org');
 expect(clearWorkspaceDirty).toHaveBeenCalledWith(form);expect(changed).toHaveBeenCalledTimes(1);
 window.removeEventListener('moodle-settings-changed',changed);
});
it('failure preserves draft and does not report success',async()=>{
 configureMoodle.mockRejectedValue(new Error('Denied'));
 render(Settings);const enabled=await screen.findByLabelText('Enable Moodle connector');
 await fireEvent.click(enabled);await fireEvent.submit(enabled.closest('form'));
 expect(await screen.findByRole('alert')).toHaveTextContent('Denied');
 expect(enabled).toBeChecked();expect(clearWorkspaceDirty).not.toHaveBeenCalled();
});
