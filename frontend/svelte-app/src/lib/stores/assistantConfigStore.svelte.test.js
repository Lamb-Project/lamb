import { it, expect, vi } from 'vitest';
import { get } from 'svelte/store';
vi.mock('$app/environment', () => ({browser:true}));
vi.mock('axios', () => ({default:{get:vi.fn(),isAxiosError:()=>false}}));
import axios from 'axios';
import { assistantConfigStore } from './assistantConfigStore.js';
it('discovers models at Creator even with a conflicting explicit lambServer, and rejects stale defaults', async () => {
 localStorage.clear();
 window.LAMB_CONFIG={api:{baseUrl:'http://localhost:19099/creator',lambServer:'http://localhost:9099'}};
 localStorage.setItem('userToken','synthetic-test-token');
 localStorage.setItem('userEmail','test@example.test');
 localStorage.setItem('lamb_assistant_capabilities_test@example.test', JSON.stringify({timestamp:Date.now(),value:{connectors:{openai:{available_llms:['gpt-4o-mini']}}}}));
 axios.get.mockImplementation(async url => ({data:url.endsWith('/capabilities') ? {connectors:{ollama:{available_llms:['qwen']}}} : {connector:'openai',llm:'gpt-4o-mini'}}));
 await assistantConfigStore.loadConfig();
 expect(axios.get.mock.calls.map(call=>call[0])).toEqual(['http://localhost:19099/creator/assistant/capabilities','http://localhost:19099/static/json/defaults.json','http://localhost:19099/creator/assistant/defaults']);
 expect(get(assistantConfigStore).configDefaults.config.connector).toBe('ollama');
 expect(get(assistantConfigStore).configDefaults.config.llm).toBe('qwen');
});
it.each([401,403])('surfaces capability authentication failure %s and clears cached choices', async status => {
 assistantConfigStore.reset();
 axios.get.mockRejectedValue({response:{status}});
 await assistantConfigStore.loadConfig();
 const state=get(assistantConfigStore);
 expect(state.error).toContain('Authentication failed');
 expect(state.systemCapabilities.connectors).toEqual({});
 expect(state.configDefaults.config.connector).toBe('');
 expect(state.loading).toBe(false);
});
it('does not conceal an organization-default authentication failure', async () => {
 assistantConfigStore.reset();
 axios.get.mockImplementation(async url => {
  if(url.endsWith('/assistant/defaults')) throw {response:{status:401}};
  return {data:url.endsWith('/capabilities') ? {connectors:{ollama:{available_llms:['qwen']}}} : {config:{connector:'ollama',llm:'qwen'}}};
 });
 await assistantConfigStore.loadConfig();
 expect(get(assistantConfigStore).error).toContain('Authentication failed');
 expect(get(assistantConfigStore).systemCapabilities.connectors).toEqual({});
});
