import { beforeEach, expect, it, vi } from 'vitest';
import { render, screen, fireEvent, cleanup, waitFor } from '@testing-library/svelte';
vi.mock('$lib/services/moodleService', () => ({moodleStatus:vi.fn(),connectMoodleQrImage:vi.fn(),connectMoodle:vi.fn(),disconnectMoodle:vi.fn(),configureMoodle:vi.fn()}));
vi.mock('$lib/services/aacService', () => ({createSession:vi.fn()}));
vi.mock('$lib/stores/aacStore.svelte', async () => {const {writable}=await import('svelte/store');return {showSession:vi.fn(),sidebarBusy:writable(false)};});
import {createSession} from '$lib/services/aacService';
import {showSession} from '$lib/stores/aacStore.svelte';
vi.mock('$lib/services/frontendManage', () => ({clearWorkspaceDirty:vi.fn()}));
import { moodleStatus, connectMoodleQrImage, connectMoodle, configureMoodle } from '$lib/services/moodleService';
import { clearWorkspaceDirty } from '$lib/services/frontendManage';
import Page from './+page.svelte';
const status = () => ({settings:{enabled:true,base_url:'https://moodle.test',mode:'readonly',write_groups:[],allow_grade_write:false},can_configure:true,effective_driver:{provider:'ollama',model:'fixture'},privacy_notice:'Student data reaches the configured provider.',connection:null});
beforeEach(() => {cleanup();vi.resetAllMocks();createSession.mockResolvedValue({id:"onboarding",title:"Moodle"});moodleStatus.mockImplementation(async () => status());connectMoodle.mockResolvedValue({});configureMoodle.mockResolvedValue({});});
it('connection page excludes organization policy even for administrators', async () => {
    render(Page);
    await screen.findByLabelText('QR passport');
    expect(screen.queryByLabelText('Allowed Moodle base URL')).toBeNull();
    expect(screen.queryByText('Enable Moodle connector')).toBeNull();
});
it('disabled organization has no connection forms', async () => {
    moodleStatus.mockResolvedValue({...status(),settings:{...status().settings,enabled:false}});
    render(Page);
    await screen.findByText(/connector is disabled/);
    expect(screen.queryByLabelText('QR code image')).toBeNull();
});
it('failed verification preserves the credential draft and dirty state', async () => {
    connectMoodle.mockRejectedValue(new Error('Moodle identity verification failed'));
    render(Page);
    const secret=await screen.findByLabelText('QR passport');
    await fireEvent.input(secret,{target:{value:'fixture-passport'}});
    await fireEvent.submit(secret.closest('form'));
    await screen.findByRole('alert');
    expect(secret).toHaveValue('fixture-passport');
    expect(clearWorkspaceDirty).not.toHaveBeenCalled();
});
it('members have no organization settings form', async () => {
    moodleStatus.mockResolvedValue({...status(),can_configure:false});
    render(Page);
    await screen.findByLabelText('QR passport');
    expect(screen.queryByRole('button',{name:'Save organization settings'})).toBeNull();
});
it('shows an unavailable driver while preserving connection controls', async () => {
    moodleStatus.mockResolvedValue({...status(),effective_driver:{provider:'',model:'',error:'Ask the organization administrator to correct the model.'}});
    render(Page);
    expect(await screen.findByRole('alert')).toHaveTextContent('correct the model');
    expect(screen.getByLabelText('QR passport')).toBeInTheDocument();
});

it('uploads QR as an image and clears it after success', async () => {
    connectMoodleQrImage.mockResolvedValue({});
    render(Page);
    const input=await screen.findByLabelText('QR code image');
    const image=new File(['synthetic'], 'qr.png', {type:'image/png'});
    await fireEvent.change(input,{target:{files:[image]}});
    await fireEvent.submit(input.closest('form'));
    await screen.findByText('Moodle course summary opened in LAMB AGENT.');
    expect(createSession).toHaveBeenCalledWith({moodleOnboarding:true});
    expect(showSession).toHaveBeenCalledWith('onboarding','Moodle');
    expect(connectMoodleQrImage).toHaveBeenCalledWith(image);
    expect(connectMoodle).not.toHaveBeenCalled();
    await waitFor(() => expect(screen.getByRole('button',{name:'Connect with QR image'})).toBeDisabled());
});
it('shows QR errors, clears stale image and allows a new attempt', async () => {
    connectMoodleQrImage.mockRejectedValue(new Error('Use a fresh login QR'));
    render(Page);
    const input=await screen.findByLabelText('QR code image');
    await fireEvent.change(input,{target:{files:[new File(['x'],'qr.png')]}});
    await fireEvent.submit(input.closest('form'));
    expect(await screen.findByRole('alert')).toHaveTextContent('fresh login QR');
    await waitFor(() => expect(screen.getByRole('button',{name:'Connect with QR image'})).toBeDisabled());
    expect(clearWorkspaceDirty).not.toHaveBeenCalled();
});

it('onboarding failure preserves connection and retries without reusing QR', async () => {
    connectMoodleQrImage.mockResolvedValue({});
    createSession.mockRejectedValueOnce(new Error('Course list unavailable'));
    render(Page);
    const input=await screen.findByLabelText('QR code image');
    await fireEvent.change(input,{target:{files:[new File(['synthetic'],'qr.png')]}});
    await fireEvent.submit(input.closest('form'));
    expect(await screen.findByRole('alert')).toHaveTextContent('Connected, but');
    expect(showSession).not.toHaveBeenCalled();
    await fireEvent.click(screen.getByRole('button',{name:'Open Moodle summary in LAMB AGENT'}));
    await screen.findByText('Moodle course summary opened in LAMB AGENT.');
    expect(connectMoodleQrImage).toHaveBeenCalledTimes(1);
});
