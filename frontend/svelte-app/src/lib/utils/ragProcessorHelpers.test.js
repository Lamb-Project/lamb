// src/lib/utils/ragProcessorHelpers.test.js
import { describe, test, expect } from 'vitest';
import {
	isKbBasedRag,
	isSingleFileRag,
	isRubricRag,
	isNoRag,
	hasRagOptions,
	normalizeRagProcessor
} from './ragProcessorHelpers.js';

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
	test('returns false for no_rag', () => {
		expect(isKbBasedRag('no_rag')).toBe(false);
	});
	test('returns false for single_file_rag', () => {
		expect(isKbBasedRag('single_file_rag')).toBe(false);
	});
	test('returns false for rubric_rag', () => {
		expect(isKbBasedRag('rubric_rag')).toBe(false);
	});
	test('returns false for undefined', () => {
		expect(isKbBasedRag(undefined)).toBe(false);
	});
	test('returns false for null', () => {
		expect(isKbBasedRag(null)).toBe(false);
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
	test('returns false for no_rag', () => {
		expect(isSingleFileRag('no_rag')).toBe(false);
	});
	test('returns false for undefined', () => {
		expect(isSingleFileRag(undefined)).toBe(false);
	});
	test('returns false for null', () => {
		expect(isSingleFileRag(null)).toBe(false);
	});
	test('returns false for empty string', () => {
		expect(isSingleFileRag('')).toBe(false);
	});
});

describe('isRubricRag', () => {
	test('returns true for rubric_rag', () => {
		expect(isRubricRag('rubric_rag')).toBe(true);
	});
	test('returns false for simple_rag', () => {
		expect(isRubricRag('simple_rag')).toBe(false);
	});
	test('returns false for no_rag', () => {
		expect(isRubricRag('no_rag')).toBe(false);
	});
	test('returns false for undefined', () => {
		expect(isRubricRag(undefined)).toBe(false);
	});
	test('returns false for null', () => {
		expect(isRubricRag(null)).toBe(false);
	});
	test('returns false for empty string', () => {
		expect(isRubricRag('')).toBe(false);
	});
});

describe('isNoRag', () => {
	test('returns true for no_rag', () => {
		expect(isNoRag('no_rag')).toBe(true);
	});
	test('returns true for undefined', () => {
		expect(isNoRag(undefined)).toBe(true);
	});
	test('returns true for null', () => {
		expect(isNoRag(null)).toBe(true);
	});
	test('returns true for empty string', () => {
		expect(isNoRag('')).toBe(true);
	});
	test('returns false for simple_rag', () => {
		expect(isNoRag('simple_rag')).toBe(false);
	});
});

describe('hasRagOptions', () => {
	test('returns true for simple_rag', () => {
		expect(hasRagOptions('simple_rag')).toBe(true);
	});
	test('returns false for no_rag', () => {
		expect(hasRagOptions('no_rag')).toBe(false);
	});
	test('returns false for undefined', () => {
		expect(hasRagOptions(undefined)).toBe(false);
	});
	test('returns false for null', () => {
		expect(hasRagOptions(null)).toBe(false);
	});
	test('returns false for empty string', () => {
		expect(hasRagOptions('')).toBe(false);
	});
});

describe('normalizeRagProcessor', () => {
	test('returns simple_rag unchanged', () => {
		expect(normalizeRagProcessor('simple_rag')).toBe('simple_rag');
	});
	test('converts "no rag" to no_rag', () => {
		expect(normalizeRagProcessor('no rag')).toBe('no_rag');
	});
	test('trims and lowercases', () => {
		expect(normalizeRagProcessor('  Simple_RAG  ')).toBe('simple_rag');
	});
	test('returns empty string for undefined', () => {
		expect(normalizeRagProcessor(undefined)).toBe('');
	});
	test('returns empty string for null', () => {
		expect(normalizeRagProcessor(null)).toBe('');
	});
	test('returns empty string for empty string', () => {
		expect(normalizeRagProcessor('')).toBe('');
	});
});
