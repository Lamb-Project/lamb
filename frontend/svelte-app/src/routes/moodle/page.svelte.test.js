import { beforeEach, expect, it, vi } from 'vitest';
import { render, screen, fireEvent, cleanup, waitFor } from '@testing-library/svelte';
vi.mock('$lib/services/moodleService', () => ({moodleStatus:vi.fn(),connectMoodle:vi.fn(),disconnectMoodle:vi.fn(),configureMoodle:vi.fn()}));
vi.mock('$lib/services/frontendManage', () => ({clearWorkspaceDirty:vi.fn()}));
import { moodleStatus, connectMoodle, configureMoodle } from '$lib/services/moodleService';
import { clearWorkspaceDirty } from '$lib/services/frontendManage';
import Page from './+page.svelte';
const status = () => ({settings:{enabled:true,base_url:'https://moodle.test',mode:'readonly',write_groups:[],allow_grade_write:false},can_configure:true,configured_driver:{provider:'ollama',model:'fixture'},privacy_notice:'Student data reaches the configured provider.',connection:null});
beforeEach(() => {cleanup();vi.resetAllMocks();moodleStatus.mockImplementation(async () => status());connectMoodle.mockResolvedValue({});configureMoodle.mockResolvedValue({});});
it('connecting clears only its credential and preserves unsaved organization settings', async () => {
    render(Page);
    const url=await screen.findByLabelText('Allowed Moodle base URL');
    await fireEvent.input(url,{target:{value:'https://draft.test'}});
    const secret=screen.getByLabelText('QR passport');
    await fireEvent.input(secret,{target:{value:'fixture-passport'}});
    const form=secret.closest('form');
    await fireEvent.submit(form);
    await screen.findByText('Moodle identity verified and connected.');
    expect(connectMoodle).toHaveBeenCalledWith({passport:'fixture-passport'});
    expect(url).toHaveValue('https://draft.test');
    expect(secret).toHaveValue('');
    expect(clearWorkspaceDirty).toHaveBeenCalledExactlyOnceWith(form);
});
it('saving organization settings preserves the separate connection draft', async () => {
    render(Page);
    const secret=await screen.findByLabelText('QR passport');
    await fireEvent.input(secret,{target:{value:'fixture-passport'}});
    const form=screen.getByRole('button',{name:'Save organization settings'}).closest('form');
    await fireEvent.submit(form);
    await screen.findByText('Organization Moodle settings saved.');
    expect(secret).toHaveValue('fixture-passport');
    expect(clearWorkspaceDirty).toHaveBeenCalledExactlyOnceWith(form);
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
