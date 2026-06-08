// src/lib/utils/ragProcessorHelpers.js
/**
 * RAG Processor type classification helpers.
 *
 * Strategy Pattern: Instead of 16+ scattered if/else chains checking
 * specific RAG processor strings, we centralize the classification
 * logic here. Each function encapsulates a "strategy" for determining
 * which UI/behavior to apply based on the RAG processor type.
 */

/** @readonly */
export const RAG_TYPES = Object.freeze({
	/** RAG processors that use knowledge base collections (legacy, port 9090) */
	KB_BASED: ['simple_rag', 'context_aware_rag', 'hierarchical_rag'],
	/** RAG processors that use knowledge stores (new KB Server v2, port 9092) */
	KS_BASED: ['query_rewriting_ks_rag', 'knowledge_store_rag'],
	/** Processors hidden from the create dropdown (kept for edit/backward-compat only) */
	HIDDEN_IN_CREATE: ['simple_rag', 'context_aware_rag', 'hierarchical_rag', 'single_file_rag', 'knowledge_store_rag'],
	/** RAG processor that uses a single file */
	SINGLE_FILE: ['single_file_rag'],
	/** RAG processor that uses rubrics */
	RUBRIC: ['rubric_rag'],
	/** No RAG processing */
	NONE: ['no_rag']
});

/**
 * Returns true if the processor uses knowledge base collections (legacy).
 * @param {string} processor
 * @returns {boolean}
 */
export function isKbBasedRag(processor) {
	return RAG_TYPES.KB_BASED.includes(processor);
}

/**
 * Returns true if the processor uses knowledge stores (new).
 * @param {string} processor
 * @returns {boolean}
 */
export function isKsBasedRag(processor) {
	return RAG_TYPES.KS_BASED.includes(processor);
}

/**
 * Returns true if the processor should be hidden in the create dropdown.
 * @param {string} processor
 * @returns {boolean}
 */
export function isHiddenInCreate(processor) {
	return RAG_TYPES.HIDDEN_IN_CREATE.includes(processor);
}

/**
 * Returns true if the processor uses a single file.
 * @param {string} processor
 * @returns {boolean}
 */
export function isSingleFileRag(processor) {
	return RAG_TYPES.SINGLE_FILE.includes(processor);
}

/**
 * Returns true if the processor uses rubrics.
 * @param {string} processor
 * @returns {boolean}
 */
export function isRubricRag(processor) {
	return RAG_TYPES.RUBRIC.includes(processor);
}

/**
 * Returns true if no RAG processing is configured.
 * @param {string} processor
 * @returns {boolean}
 */
export function isNoRag(processor) {
	return !processor || RAG_TYPES.NONE.includes(processor);
}

/**
 * Returns true if the RAG processor has configurable options to show.
 * @param {string} processor
 * @returns {boolean}
 */
export function hasRagOptions(processor) {
	return !!processor && !isNoRag(processor);
}

/**
 * Normalizes RAG processor value from config (handles "no rag" -> "no_rag").
 * @param {string} processor
 * @returns {string}
 */
export function normalizeRagProcessor(processor) {
	if (!processor) return '';
	const normalized = processor.trim().toLowerCase();
	if (normalized === 'no rag') return 'no_rag';
	return normalized;
}

/**
 * Returns a human-readable display name for a RAG processor.
 * Maps internal names to user-friendly labels:
 *   query_rewriting_ks_rag → "Context Aware Rag"
 *   context_aware_rag      → "Context Aware Rag (Old)"
 *   knowledge_store_rag    → "Knowledge Store Rag (Legacy)"
 * @param {string} processor
 * @returns {string}
 */
export function getRagProcessorDisplayName(processor) {
	if (!processor) return '';
	const displayNames = {
		'query_rewriting_ks_rag': 'Context Aware Rag',
		'context_aware_rag': 'Context Aware Rag (Old)',
		'knowledge_store_rag': 'Knowledge Store Rag (Legacy)',
	};
	if (displayNames[processor]) {
		return displayNames[processor];
	}
	return processor.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase());
}
