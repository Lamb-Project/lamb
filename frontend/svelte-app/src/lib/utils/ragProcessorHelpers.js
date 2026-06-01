// src/lib/utils/ragProcessorHelpers.js
/**
 * RAG Processor type classification helpers.
 *
 * Strategy Pattern: Instead of 16+ scattered if/else chains checking
 * specific RAG processor strings, we centralize the classification
 * logic here. Each function encapsulates a "strategy" for determining
 * which UI/behavior to apply based on the RAG processor type.
 *
 * To add a new RAG processor type, add it to the appropriate constant
 * array and all conditionals across the app update automatically.
 */

/** @readonly */
export const RAG_TYPES = Object.freeze({
	/** RAG processors that use knowledge base collections */
	KB_BASED: ['simple_rag', 'context_aware_rag', 'hierarchical_rag'],
	/** RAG processors that use knowledge stores (new KB Server v2) */
	KS_BASED: ['query_rewriting_ks_rag', 'knowledge_store_rag'],
	/** RAG processor that uses a single file */
	SINGLE_FILE: ['single_file_rag'],
	/** RAG processor that uses rubrics */
	RUBRIC: ['rubric_rag'],
	/** No RAG processing */
	NONE: ['no_rag']
});

/**
 * Returns true if the processor uses knowledge base collections.
 * @param {string} processor
 * @returns {boolean}
 */
export function isKbBasedRag(processor) {
	return RAG_TYPES.KB_BASED.includes(processor);
}

/**
 * Returns true if the processor uses knowledge stores.
 * @param {string} processor
 * @returns {boolean}
 */
export function isKsBasedRag(processor) {
	return RAG_TYPES.KS_BASED.includes(processor);
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
