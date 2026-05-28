// src/lib/utils/ragProcessorHelpers.spec.js
import { describe, test, expect } from 'vitest';
import {
	isKbBasedRag,
	isSingleFileRag,
	isRubricRag,
	isNoRag,
	hasRagOptions,
	RAG_TYPES,
	normalizeRagProcessor
} from './ragProcessorHelpers.js';

describe('ragProcessorHelpers', () => {
	describe('isKbBasedRag', () => {
		test('returns true for simple_rag', () => {
			expect(isKbBasedRag('simple_rag')).toBe(true);
		});
		test('returns true for context_aware_rag', () => {
			expect(isKbBasedRag('context_aware_rag')).toBe(true);
		});
		test('returns true for hierarchical_rag', () => {
			expect(isKbBasedRag('hierarchical_rag')).toBe(true);
		});
		test('returns false for single_file_rag', () => {
			expect(isKbBasedRag('single_file_rag')).toBe(false);
		});
		test('returns false for no_rag', () => {
			expect(isKbBasedRag('no_rag')).toBe(false);
		});
		test('returns false for rubric_rag', () => {
			expect(isKbBasedRag('rubric_rag')).toBe(false);
		});
		test('returns false for empty string', () => {
			expect(isKbBasedRag('')).toBe(false);
		});
	});
	describe('isSingleFileRag', () => {
		test('returns true for single_file_rag', () => {
			expect(isSingleFileRag('single_file_rag')).toBe(true);
		});
		test('returns false for simple_rag', () => {
			expect(isSingleFileRag('simple_rag')).toBe(false);
		});
	});
	describe('isRubricRag', () => {
		test('returns true for rubric_rag', () => {
			expect(isRubricRag('rubric_rag')).toBe(true);
		});
		test('returns false for simple_rag', () => {
			expect(isRubricRag('simple_rag')).toBe(false);
		});
	});
	describe('isNoRag', () => {
		test('returns true for no_rag', () => {
			expect(isNoRag('no_rag')).toBe(true);
		});
		test('returns false for simple_rag', () => {
			expect(isNoRag('simple_rag')).toBe(false);
		});
	});
	describe('hasRagOptions', () => {
		test('returns true for any RAG that is not no_rag', () => {
			expect(hasRagOptions('simple_rag')).toBe(true);
			expect(hasRagOptions('rubric_rag')).toBe(true);
			expect(hasRagOptions('single_file_rag')).toBe(true);
		});
		test('returns false for no_rag', () => {
			expect(hasRagOptions('no_rag')).toBe(false);
		});
		test('returns false for empty string', () => {
			expect(hasRagOptions('')).toBe(false);
		});
	});
	describe('RAG_TYPES constant', () => {
		test('contains KB_BASED array', () => {
			expect(RAG_TYPES.KB_BASED).toEqual(['simple_rag', 'context_aware_rag', 'hierarchical_rag']);
		});
	});
	describe('normalizeRagProcessor', () => {
		test('converts "no rag" to "no_rag"', () => {
			expect(normalizeRagProcessor('no rag')).toBe('no_rag');
		});
		test('trims whitespace', () => {
			expect(normalizeRagProcessor(' simple_rag ')).toBe('simple_rag');
		});
		test('returns empty for falsy input', () => {
			expect(normalizeRagProcessor('')).toBe('');
		});
	});
});
