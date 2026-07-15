import { describe, it, expect } from 'vitest';
import {
	filterCostData,
	computeCostTotals,
	validateQuotaLimit,
	parseQuotaLimit,
	validateAlertThresholds,
	parseAlertThresholds
} from './costManagementHelpers';

describe('filterCostData', () => {
	const sampleData = [
		{ name: 'Math Tutor', owner: 'alice@test.com', organization_name: 'MIT', model_name: 'gpt-4o' },
		{ name: 'History Bot', owner: 'bob@test.com', organization_name: 'Stanford', model_name: 'gpt-3.5' },
		{ name: 'Science Aid', owner: 'carol@test.com', organization_name: 'MIT', model_name: 'claude-3' }
	];

	it('returns all items when search is empty', () => {
		expect(filterCostData(sampleData, '')).toEqual(sampleData);
	});

	it('returns all items when search is null/undefined', () => {
		expect(filterCostData(sampleData, null)).toEqual(sampleData);
		expect(filterCostData(sampleData, undefined)).toEqual(sampleData);
	});

	it('filters by assistant name (case-insensitive)', () => {
		const result = filterCostData(sampleData, 'math');
		expect(result).toHaveLength(1);
		expect(result[0].name).toBe('Math Tutor');
	});

	it('filters by owner email', () => {
		const result = filterCostData(sampleData, 'bob');
		expect(result).toHaveLength(1);
		expect(result[0].owner).toBe('bob@test.com');
	});

	it('filters by organization name', () => {
		const result = filterCostData(sampleData, 'MIT');
		expect(result).toHaveLength(2);
	});

	it('filters by model name', () => {
		const result = filterCostData(sampleData, 'gpt-4');
		expect(result).toHaveLength(1);
		expect(result[0].model_name).toBe('gpt-4o');
	});

	it('returns empty array when nothing matches', () => {
		expect(filterCostData(sampleData, 'zzzzz')).toHaveLength(0);
	});

	it('handles items with null/undefined fields', () => {
		const sparse = [{ name: null, owner: undefined, organization_name: null, model_name: null }];
		expect(filterCostData(sparse, 'test')).toHaveLength(0);
	});
});

describe('computeCostTotals', () => {
	it('returns zeros for empty array', () => {
		expect(computeCostTotals([])).toEqual({
			total_cost: 0,
			total_tokens: 0,
			prompt_tokens: 0,
			completion_tokens: 0,
			cached_prompt_tokens: 0
		});
	});

	it('sums all cost and token fields', () => {
		const data = [
			{ cost_usd: 1.5, total_tokens: 1000, prompt_tokens: 600, completion_tokens: 400, cached_prompt_tokens: 500 },
			{ cost_usd: 2.5, total_tokens: 2000, prompt_tokens: 1200, completion_tokens: 800, cached_prompt_tokens: 900 }
		];
		expect(computeCostTotals(data)).toEqual({
			total_cost: 4.0,
			total_tokens: 3000,
			prompt_tokens: 1800,
			completion_tokens: 1200,
			cached_prompt_tokens: 1400
		});
	});

	it('treats missing fields as zero', () => {
		const data = [{ cost_usd: undefined, total_tokens: 100, prompt_tokens: null, completion_tokens: 50 }];
		const result = computeCostTotals(data);
		expect(result.total_cost).toBe(0);
		expect(result.total_tokens).toBe(100);
		expect(result.prompt_tokens).toBe(0);
		expect(result.completion_tokens).toBe(50);
		expect(result.cached_prompt_tokens).toBe(0);
	});
});

describe('computeCostTotals — cache fields', () => {
	it('includes cached_prompt_tokens in totals', () => {
		const data = [
			{ cost_usd: 1.0, total_tokens: 1000, prompt_tokens: 600, completion_tokens: 400, cached_prompt_tokens: 500 },
			{ cost_usd: 2.0, total_tokens: 2000, prompt_tokens: 1200, completion_tokens: 800, cached_prompt_tokens: 900 }
		];
		const result = computeCostTotals(data);
		expect(result.cached_prompt_tokens).toBe(1400);
	});

	it('treats missing cached_prompt_tokens as zero', () => {
		const data = [{ cost_usd: 1.0, total_tokens: 100, prompt_tokens: 60, completion_tokens: 40 }];
		expect(computeCostTotals(data).cached_prompt_tokens).toBe(0);
	});
});

describe('validateQuotaLimit', () => {
	it('returns null (valid) for empty string (unlimited)', () => {
		expect(validateQuotaLimit('')).toBeNull();
		expect(validateQuotaLimit('  ')).toBeNull();
	});

	it('returns null (valid) for a positive number string', () => {
		expect(validateQuotaLimit('5.00')).toBeNull();
		expect(validateQuotaLimit('0.01')).toBeNull();
	});

	it('returns error for negative number', () => {
		expect(validateQuotaLimit('-1')).toBeTruthy();
	});

	it('returns error for non-numeric string', () => {
		expect(validateQuotaLimit('abc')).toBeTruthy();
	});

	it('returns null (valid) for zero', () => {
		expect(validateQuotaLimit('0')).toBeNull();
	});
});

describe('parseQuotaLimit', () => {
	it('returns null for empty string', () => {
		expect(parseQuotaLimit('')).toBeNull();
		expect(parseQuotaLimit('  ')).toBeNull();
	});

	it('returns parsed float for valid number', () => {
		expect(parseQuotaLimit('5.00')).toBe(5.0);
		expect(parseQuotaLimit('0')).toBe(0);
	});
});

describe('validateAlertThresholds', () => {
	it('returns null for empty string', () => {
		expect(validateAlertThresholds('')).toBeNull();
		expect(validateAlertThresholds('  ')).toBeNull();
	});

	it('returns null for valid comma-separated positive numbers', () => {
		expect(validateAlertThresholds('50, 80')).toBeNull();
		expect(validateAlertThresholds('25')).toBeNull();
	});

	it('returns error for non-numeric values', () => {
		expect(validateAlertThresholds('abc, 50')).toBeTruthy();
	});

	it('returns error for zero or negative values', () => {
		expect(validateAlertThresholds('0, 50')).toBeTruthy();
		expect(validateAlertThresholds('-10')).toBeTruthy();
	});
});

describe('parseAlertThresholds', () => {
	it('returns empty array for empty string', () => {
		expect(parseAlertThresholds('')).toEqual([]);
	});

	it('returns parsed numbers for valid input', () => {
		expect(parseAlertThresholds('50, 80')).toEqual([50, 80]);
		expect(parseAlertThresholds('25')).toEqual([25]);
	});
});
