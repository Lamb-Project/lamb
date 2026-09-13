import { describe, it, expect } from 'vitest';
import { reconcileModelDefaults, validateModelSelection } from './assistantModelConfig.js';
const caps = { connectors: { bypass: { available_llms: ['debug-bypass'] }, ollama: { available_llms: ['qwen', 'other'] } } };
describe('model configuration', () => {
 it('replaces stale OpenAI defaults with enabled real models', () => {
  expect(reconcileModelDefaults({connector:'openai',llm:'gpt-4o-mini',system_prompt:'keep'}, caps)).toEqual({connector:'ollama',llm:'qwen',system_prompt:'keep'});
 });
 it('preserves a valid configured choice', () => {
  expect(reconcileModelDefaults({connector:'ollama',llm:'other'}, caps).llm).toBe('other');
 });
 it('does not invent models or silently default to bypass', () => {
  for (const c of [{}, {connectors:{bypass:caps.connectors.bypass}}]) {
   expect(reconcileModelDefaults({connector:'openai',llm:'bad'},c)).toEqual({connector:'',llm:''});
  }
 });
 it('allows an explicitly configured bypass default', () => {
  expect(reconcileModelDefaults({connector:'bypass',llm:'debug-bypass'}, caps).connector).toBe('bypass');
 });
 it('rejects missing, stale, wrong-connector and loading selections', () => {
  for (const [c,m,loading] of [['openai','qwen'],['ollama','bad'],['ollama',''],['ollama','qwen',true]]) expect(validateModelSelection(c,m,caps,loading)).toBeTruthy();
  expect(validateModelSelection('ollama','qwen',caps)).toBeNull();
 });
});
