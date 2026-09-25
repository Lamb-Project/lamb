// src/lib/components/workshop/logic/workshopFormState.svelte.test.js
import { describe, test, expect } from 'vitest';
import { createWorkshopFormState } from './workshopFormState.svelte.js';

describe('createWorkshopFormState — step navigation', () => {
	// S1: nextStep/prevStep move correctly, bounded to 1..5
	test('nextStep advances within 1..5', () => {
		const { form, nextStep } = createWorkshopFormState();
		expect(form.currentStep).toBe(1);
		nextStep();
		expect(form.currentStep).toBe(2);
		nextStep();
		nextStep();
		nextStep();
		expect(form.currentStep).toBe(5);
		nextStep(); // at bound — no-op
		expect(form.currentStep).toBe(5);
	});

	test('prevStep moves back within 1..5', () => {
		const { form, prevStep } = createWorkshopFormState({ currentStep: 3 });
		expect(form.currentStep).toBe(3);
		prevStep();
		expect(form.currentStep).toBe(2);
		prevStep();
		expect(form.currentStep).toBe(1);
		prevStep(); // at bound — no-op
		expect(form.currentStep).toBe(1);
	});

	test('goToStep jumps but stays in range', () => {
		const { form, goToStep } = createWorkshopFormState();
		goToStep(4);
		expect(form.currentStep).toBe(4);
		goToStep(0); // out of range — ignored
		expect(form.currentStep).toBe(4);
		goToStep(9); // out of range — ignored
		expect(form.currentStep).toBe(4);
	});
});

describe('createWorkshopFormState — step validity', () => {
	test('step 1 valid only when instructions are non-empty', () => {
		const { form, isStepComplete } = createWorkshopFormState();
		expect(isStepComplete(1)).toBe(false);
		form.instructions = '   ';
		expect(isStepComplete(1)).toBe(false); // whitespace-only invalid
		form.instructions = 'Make a tutor that explains fractions';
		expect(isStepComplete(1)).toBe(true);
	});

	test('step 2 valid only once the document is ingested', () => {
		const { form, isStepComplete } = createWorkshopFormState();
		expect(isStepComplete(2)).toBe(false);
		form.attachedFilePath = '/uploads/lab.pdf';
		form.attachedFileMeta = { name: 'lab.pdf', path: '/uploads/lab.pdf' };
		expect(isStepComplete(2)).toBe(false); // still ingesting
		form.documentStatus = 'completed';
		expect(isStepComplete(2)).toBe(true);
	});

	test('step 3 valid when a KB is selected', () => {
		const { form, isStepComplete } = createWorkshopFormState();
		expect(isStepComplete(3)).toBe(false);
		form.selectedKbId = 'kb-1';
		form.kbCollection = 'students';
		expect(isStepComplete(3)).toBe(true);
	});

	test('step 4 valid when at least one tool is selected', () => {
		const { form, isStepComplete } = createWorkshopFormState();
		expect(isStepComplete(4)).toBe(true); // calculator default
		form.selectedTools = [];
		expect(isStepComplete(4)).toBe(false);
		form.selectedTools = ['kb_query'];
		expect(isStepComplete(4)).toBe(true);
	});

	test('step 5 is always actionable', () => {
		const { isStepComplete } = createWorkshopFormState();
		expect(isStepComplete(5)).toBe(false);
	});
});

describe('createWorkshopFormState — serialize', () => {
	test('serialize() returns the full build_state JSON', () => {
		const { form, serialize } = createWorkshopFormState({
			instructions: 'Teach me',
			selectedKbId: 'kb-9',
			selectedTools: ['calculator', 'kb_query'],
		});
		form.assistantName = 'My Tutor';
		const out = serialize();
		expect(out.instructions).toBe('Teach me');
		expect(out.selectedKbId).toBe('kb-9');
		expect(out.selectedTools).toEqual(['calculator', 'kb_query']);
		expect(out.assistantName).toBe('My Tutor');
		expect(out.currentStep).toBe(1);
	});

	test('serialize() deep-copies chatMessages', () => {
		const { form, serialize } = createWorkshopFormState();
		form.chatMessages = [{ role: 'user', content: 'hi' }];
		const out = serialize();
		out.chatMessages[0].content = 'mutated';
		expect(form.chatMessages[0].content).toBe('hi'); // live store untouched
	});
});

describe('createWorkshopFormState — reflection persisted', () => {
	test('reflection writes to state and serializes', () => {
		const { form, serialize } = createWorkshopFormState();
		form.reflection = 'The tool timeline helped me see what the LLM received.';
		expect(form.reflection).toMatch(/tool timeline/);
		expect(serialize().reflection).toBe(form.reflection);
	});

	test('rehydration from persisted build_state restores currentStep', () => {
		const { form } = createWorkshopFormState({ currentStep: 4, reflection: 'x' });
		expect(form.currentStep).toBe(4);
		expect(form.reflection).toBe('x');
	});
});

describe('createWorkshopFormState — independent instances', () => {
	test('each call returns isolated state', () => {
		const a = createWorkshopFormState();
		const b = createWorkshopFormState();
		a.form.instructions = 'A';
		b.form.instructions = 'B';
		expect(a.form.instructions).toBe('A');
		expect(b.form.instructions).toBe('B');
	});
});