import { describe, expect, it } from 'vitest';
import { keepOrFirst, kindsFor } from './activityKinds.js';

const chat = { name: 'chat', display_name: 'AI Chat Activity', requires_assistants: true };
const fileEvaluation = { name: 'file_evaluation', display_name: 'Supervised Assessment', requires_assistants: true };
const llmAccess = { name: 'llm_access', display_name: 'LLM access', requires_assistants: false };

// Engineering has a published assistant and no LLM access; Education has LLM access and nothing
// published; in Law nothing can be created yet.
const info = {
	modules: [chat, fileEvaluation, llmAccess],
	org_modules: { 9: ['chat'], 4: ['llm_access'], 7: [] }
};

describe('kindsFor', () => {
	it('offers nothing until an organization is chosen', () => {
		expect(kindsFor(info, '')).toEqual([]);
		expect(kindsFor(info, null)).toEqual([]);
	});

	it('offers each organization its own kinds, and only those', () => {
		expect(kindsFor(info, '9')).toEqual([chat]);
		expect(kindsFor(info, '4')).toEqual([llmAccess]);
		expect(kindsFor(info, 9)).toEqual([chat]);
	});

	it('offers nothing where nothing can be created, or for an organization the answer does not list', () => {
		expect(kindsFor(info, '7')).toEqual([]);
		expect(kindsFor(info, '12')).toEqual([]);
	});

	it('keeps the order in which the server describes the kinds', () => {
		const both = { modules: [chat, fileEvaluation, llmAccess], org_modules: { 9: ['llm_access', 'chat'] } };
		expect(kindsFor(both, '9').map((kind) => kind.name)).toEqual(['chat', 'llm_access']);
	});

	it('offers every described kind when the server sends no lists', () => {
		expect(kindsFor({ modules: [chat, llmAccess] }, '9')).toEqual([chat, llmAccess]);
	});

	it('survives an answer that has not arrived', () => {
		expect(kindsFor(null, '9')).toEqual([]);
		expect(kindsFor(undefined, '9')).toEqual([]);
	});
});

describe('keepOrFirst', () => {
	it('keeps the selected kind while it is still offered', () => {
		expect(keepOrFirst('llm_access', [chat, llmAccess])).toBe('llm_access');
	});

	it('moves to the first kind when the selected one is no longer offered', () => {
		expect(keepOrFirst('llm_access', [chat, fileEvaluation])).toBe('chat');
		expect(keepOrFirst('', [fileEvaluation])).toBe('file_evaluation');
	});

	it('selects nothing when nothing is offered', () => {
		expect(keepOrFirst('chat', [])).toBe('');
	});
});
