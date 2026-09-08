/**
 * Filters cost data rows by search query across name, owner, org, and model.
 * @param {Array<any>} costData
 * @param {string|null|undefined} search
 * @returns {Array<any>}
 */
export function filterCostData(costData, search) {
	if (!search) return costData;
	const q = search.toLowerCase();
	return costData.filter(
		(a) =>
			(a.name || '').toLowerCase().includes(q) ||
			(a.owner || '').toLowerCase().includes(q) ||
			(a.organization_name || '').toLowerCase().includes(q) ||
			(a.model_name || '').toLowerCase().includes(q)
	);
}

/**
 * Computes aggregate totals from cost data rows.
 * @param {Array<any>} costData
 * @returns {{ total_cost: number, total_tokens: number, prompt_tokens: number, completion_tokens: number }}
 */
export function computeCostTotals(costData) {
	return {
		total_cost: costData.reduce((s, a) => s + (a.cost_usd || 0), 0),
		total_tokens: costData.reduce((s, a) => s + (a.total_tokens || 0), 0),
		prompt_tokens: costData.reduce((s, a) => s + (a.prompt_tokens || 0), 0),
		completion_tokens: costData.reduce((s, a) => s + (a.completion_tokens || 0), 0),
		cache_read_tokens: costData.reduce((s, a) => s + (a.cache_read_tokens || a.cached_prompt_tokens || 0), 0),
		cache_write_tokens: costData.reduce((s, a) => s + (a.cache_write_tokens || 0), 0)
	};
}

/**
 * Validates a cost limit string. Returns null if valid, error message string if invalid.
 * Valid: empty/whitespace (unlimited), or a non-negative number.
 * @param {string} limitStr
 * @returns {string|null}
 */
export function validateQuotaLimit(limitStr) {
	const trimmed = String(limitStr ?? '').trim();
	if (trimmed === '') return null;
	const val = parseFloat(trimmed);
	if (isNaN(val) || val < 0) {
		return 'Cost limit must be a positive number (or leave blank for unlimited).';
	}
	return null;
}

/**
 * Parses a cost limit string to a number or null (unlimited).
 * @param {string} limitStr
 * @returns {number|null}
 */
export function parseQuotaLimit(limitStr) {
	const trimmed = String(limitStr ?? '').trim();
	if (trimmed === '') return null;
	return parseFloat(trimmed);
}

/**
 * Validates alert thresholds string. Returns null if valid, error message if invalid.
 * Valid: empty/whitespace, or comma-separated positive numbers.
 * @param {string} thresholdsStr
 * @returns {string|null}
 */
export function validateAlertThresholds(thresholdsStr) {
	const trimmed = String(thresholdsStr ?? '').trim();
	if (trimmed === '') return null;
	const parts = trimmed.split(',').map((s) => parseFloat(s.trim()));
	if (parts.some(isNaN) || parts.some((p) => p <= 0)) {
		return 'Alert thresholds must be a comma-separated list of positive numbers (e.g. 50, 80).';
	}
	return null;
}

/**
 * Parses alert thresholds string into an array of numbers.
 * @param {string} thresholdsStr
 * @returns {number[]}
 */
export function parseAlertThresholds(thresholdsStr) {
	const trimmed = String(thresholdsStr ?? '').trim();
	if (trimmed === '') return [];
	return trimmed.split(',').map((s) => parseFloat(s.trim()));
}
