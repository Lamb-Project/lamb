import { beforeEach, expect, it, vi } from 'vitest';
import { render, screen, fireEvent, cleanup, waitFor } from '@testing-library/svelte';
vi.mock('$app/stores', async () => {const {writable}=await import('svelte/store');return {page:writable({url:new URL('http://localhost/moodle')})};});
vi.mock('$lib/services/moodleService', () => ({moodleStatus:vi.fn(),moodleConnectionSummary:vi.fn(),prepareMoodleQrCommand:vi.fn(),connectMoodle:vi.fn(),disconnectMoodle:vi.fn(),setApprovalPreferences:vi.fn()}));
vi.mock('$lib/services/frontendManage', () => ({clearWorkspaceDirty:vi.fn()}));
import { moodleStatus, moodleConnectionSummary, prepareMoodleQrCommand, connectMoodle, disconnectMoodle, setApprovalPreferences } from '$lib/services/moodleService';
import { clearWorkspaceDirty } from '$lib/services/frontendManage';
import Page from './+page.svelte';
const connection = {base_url:'https://moodle.test',username:'teacher',moodle_user_id:7};
const status = () => ({connected:false,settings:{enabled:true,base_url:'https://moodle.test',mode:'readonly'},approval_preferences:{advanced_mode:false},effective_driver:{provider:'openai',model:'fixture'},privacy_notice:'Student data reaches the configured provider.',connection:null});
const summary = () => ({connection,release:'4.5.2',courses:[
    {id:10,fullname:'Teaching course',shortname:'TEACH',my_roles:[{shortname:'editingteacher'}],my_roles_status:'available'},
    {id:20,fullname:'Learning course',shortname:'LEARN',my_roles:[{shortname:'student'}],my_roles_status:'available'},
    {id:30,fullname:'Unclassified course',shortname:'UNKNOWN',my_roles:null,my_roles_status:'unavailable'}
]});
beforeEach(() => {cleanup();vi.resetAllMocks();moodleStatus.mockResolvedValue(status());moodleConnectionSummary.mockResolvedValue(summary());connectMoodle.mockResolvedValue({connected:true,connection});prepareMoodleQrCommand.mockResolvedValue({command:'sh fixture-command'});disconnectMoodle.mockResolvedValue({connected:false});setApprovalPreferences.mockResolvedValue({advanced_mode:true});});
it('disconnected page shows QR flow and bottom preferences without provider notices', async () => {
    render(Page);
    await screen.findByLabelText('QR code image');
    expect(screen.queryByText(/Student data reaches/)).toBeNull();
    expect(screen.queryByText(/Effective AAC provider/)).toBeNull();
    expect(screen.queryByLabelText('Allowed Moodle base URL')).toBeNull();
    expect(moodleConnectionSummary).not.toHaveBeenCalled();
    expect(screen.getByRole('checkbox',{name:'Advanced mode'}).compareDocumentPosition(screen.getByLabelText('QR code image')) & Node.DOCUMENT_POSITION_PRECEDING).toBeTruthy();
});
it('connected page shows actual site version identity and roles, with no QR or token forms', async () => {
    moodleStatus.mockResolvedValue({...status(),connected:true,connection});
    render(Page);
    await screen.findByText('Moodle 4.5.2');
    expect(screen.getByText('teacher')).toBeInTheDocument();
    expect(screen.getByText('Teaching course').closest('section')).toHaveAttribute('aria-label','You are a teacher');
    expect(screen.getByText('Learning course').closest('section')).toHaveAttribute('aria-label','You are a student');
    expect(screen.getByText('Unclassified course').closest('section')).toHaveAttribute('aria-label','Other or unavailable roles');
    expect(screen.queryByLabelText('QR code image')).toBeNull();
    expect(screen.queryByLabelText('QR passport')).toBeNull();
});
it('disabled organization has no connection forms', async () => {
    moodleStatus.mockResolvedValue({...status(),settings:{...status().settings,enabled:false}});
    render(Page); await screen.findByText(/connector is disabled/);
    expect(screen.queryByLabelText('QR code image')).toBeNull();
});
it('inactive saved connection must be disconnected before a new QR is offered', async () => {
    moodleStatus.mockResolvedValue({...status(),connection});render(Page);
    await screen.findByText('Stored connection is inactive');
    expect(screen.queryByLabelText('QR code image')).toBeNull();
    expect(moodleConnectionSummary).not.toHaveBeenCalled();
    await fireEvent.click(screen.getByRole('button',{name:'Disconnect Moodle'}));
    await screen.findByLabelText('QR code image');
});
it('failed token verification preserves draft and dirty state', async () => {
    connectMoodle.mockRejectedValue(new Error('Moodle identity verification failed'));render(Page);
    const secret=await screen.findByLabelText('Mobile-service token');
    await fireEvent.input(secret,{target:{value:'fixture-passport'}});await fireEvent.submit(secret.closest('form'));
    await screen.findByRole('alert');expect(secret).toHaveValue('fixture-passport');expect(clearWorkspaceDirty).not.toHaveBeenCalled();
});
it('QR connect shows the summary here and hides the credentials', async () => {
    render(Page);const input=await screen.findByLabelText('QR code image');
    const image=new File(['synthetic'],'qr.png',{type:'image/png'});
    await fireEvent.change(input,{target:{files:[image]}});await fireEvent.submit(input.closest('form'));
    await screen.findByLabelText('Local connection command');
    expect(prepareMoodleQrCommand).toHaveBeenCalledWith(image, expect.any(String));expect(connectMoodle).not.toHaveBeenCalled();
    const token = screen.getByLabelText('Mobile-service token');
    await fireEvent.input(token,{target:{value:'fixture-token'}});await fireEvent.submit(token.closest('form'));
    await screen.findByText('Moodle 4.5.2');
    expect(connectMoodle).toHaveBeenCalledWith({token:'fixture-token'});
    expect(screen.queryByLabelText('QR code image')).toBeNull();expect(clearWorkspaceDirty).toHaveBeenCalled();
});
it('QR errors allow a new attempt', async () => {
    prepareMoodleQrCommand.mockRejectedValue(new Error('Use a fresh login QR'));render(Page);
    const input=await screen.findByLabelText('QR code image');await fireEvent.change(input,{target:{files:[new File(['x'],'qr.png')]}});await fireEvent.submit(input.closest('form'));
    expect(await screen.findByRole('alert')).toHaveTextContent('fresh login QR');
    expect(screen.queryByLabelText('Local connection command')).toBeNull();
    expect(screen.getByRole('button',{name:'Prepare local command'})).toBeEnabled();
});
it('summary failure keeps disconnect available and retries without reconnecting', async () => {
    moodleStatus.mockResolvedValue({...status(),connected:true,connection});moodleConnectionSummary.mockRejectedValueOnce(new Error('unavailable'));render(Page);
    expect(await screen.findByRole('alert')).toHaveTextContent('saved connection has been kept');
    expect(screen.getByRole('button',{name:'Disconnect Moodle'})).toBeEnabled();
    await fireEvent.click(screen.getByRole('button',{name:'Try again'}));await screen.findByText('Moodle 4.5.2');expect(connectMoodle).not.toHaveBeenCalled();
});
it('disconnect hides courses and ignores a late summary response', async () => {
    let resolve;moodleConnectionSummary.mockReturnValue(new Promise(r=>resolve=r));moodleStatus.mockResolvedValue({...status(),connected:true,connection});render(Page);
    await fireEvent.click(await screen.findByRole('button',{name:'Disconnect Moodle'}));await screen.findByLabelText('QR code image');
    resolve(summary());await waitFor(()=>expect(screen.queryByText('Teaching course')).toBeNull());expect(screen.queryByRole('button',{name:'Disconnect Moodle'})).toBeNull();
});
it('failed disconnect leaves connected state and courses intact', async () => {
    moodleStatus.mockResolvedValue({...status(),connected:true,connection});disconnectMoodle.mockRejectedValue(new Error('Could not disconnect'));render(Page);
    await screen.findByText('Teaching course');await fireEvent.click(screen.getByRole('button',{name:'Disconnect Moodle'}));
    await screen.findByRole('alert');expect(screen.getByText('Teaching course')).toBeInTheDocument();expect(screen.queryByLabelText('QR code image')).toBeNull();
});
it('empty courses and missing version have truthful empty states', async () => {
    moodleStatus.mockResolvedValue({...status(),connected:true,connection});moodleConnectionSummary.mockResolvedValue({connection,release:'',courses:[]});render(Page);
    await screen.findByText('No enrolled courses were returned by Moodle.');expect(screen.getByText('Moodle version unavailable')).toBeInTheDocument();
});
it('preference feedback is local to the bottom section and saves the existing setting', async () => {
    render(Page);await fireEvent.click(await screen.findByRole('checkbox',{name:'Advanced mode'}));
    const saved=await screen.findByText('Preference saved.');expect(saved.closest('section')).toHaveAttribute('aria-label','Advanced mode');expect(setApprovalPreferences).toHaveBeenCalledWith(true);
});

it('changing platform discards the old command and copy failure offers manual selection', async () => {
    Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:vi.fn().mockRejectedValue(new Error('denied'))}});
    render(Page);const input=await screen.findByLabelText('QR code image');
    await fireEvent.change(input,{target:{files:[new File(['x'],'qr.png')]}});await fireEvent.submit(input.closest('form'));
    await screen.findByLabelText('Local connection command');
    await fireEvent.click(screen.getByRole('button',{name:'Copy command'}));
    await screen.findByText(/Automatic copy is unavailable/);
    await fireEvent.change(screen.getByLabelText('Your computer'),{target:{value:'windows'}});
    expect(screen.queryByLabelText('Local connection command')).toBeNull();
    await fireEvent.submit(input.closest('form'));
    await screen.findByLabelText('Local connection command');
    expect(prepareMoodleQrCommand).toHaveBeenLastCalledWith(expect.any(File),'windows');
});
