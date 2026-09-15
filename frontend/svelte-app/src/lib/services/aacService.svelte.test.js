import {describe,it,expect,vi} from 'vitest';
vi.mock('$lib/i18n',async()=>{const {writable}=await import('svelte/store');return {locale:writable('es')};});
vi.mock('$lib/services/frontendManage',()=>({serveFrontend:vi.fn()}));
vi.mock('$lib/services/apiClient',()=>({apiJson:vi.fn(),apiFetch:vi.fn()}));
import {locale} from '$lib/i18n';
import {apiFetch,apiJson} from '$lib/services/apiClient';
import {sendMessage,sendMessageStream} from './aacService';
describe('AAC language metadata',()=>{
 it('reads the current UI locale for each normal or startup turn and preserves exact user text',async()=>{
  for(const language of ['es','en','ca','eu']){
   locale.set(language);
   await sendMessage('existing','sí');
   expect(JSON.parse(apiJson.mock.lastCall[1].body)).toEqual({message:'sí',ui_language:language});
   apiFetch.mockResolvedValue({ok:true,body:{getReader:()=>({read:async()=>({done:true}),cancel:vi.fn(),releaseLock:vi.fn()})}});
   await sendMessageStream('existing','[System: Skill startup]',vi.fn());
   expect(JSON.parse(apiFetch.mock.lastCall[1].body)).toMatchObject({message:'[System: Skill startup]',ui_language:language});
  }
 });
});
