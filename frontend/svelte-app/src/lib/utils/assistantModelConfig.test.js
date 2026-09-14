import { describe, it, expect } from 'vitest';
import { reconcileModelDefaults } from './assistantModelConfig.js';
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
});

it('uses the Creator resolved choice even if stale form model is available', () => {
 const capabilities={connectors:{openai:{available_llms:['gpt-4o-mini']},ollama:{available_llms:['qwen']}},model_defaults:{connector:'ollama',llm:'qwen'}};
 expect(reconcileModelDefaults({connector:'openai',llm:'gpt-4o-mini',system_prompt:'keep'},capabilities)).toEqual({connector:'ollama',llm:'qwen',system_prompt:'keep'});
 expect(reconcileModelDefaults({connector:'openai',llm:'gpt-4o-mini'},{model_defaults:{connector:'',llm:''}})).toEqual({connector:'',llm:''});
});
