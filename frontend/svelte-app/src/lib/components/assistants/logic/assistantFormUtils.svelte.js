// src/lib/components/assistants/assistantFormUtils.svelte.js
/**
 * Shared pure utilities for the AssistantForm component tree.
 *
 * Contains helper functions for model selection, placeholder handling,
 * connector data extraction, and text highlighting.
 */

/**
 * Select the best LLM model: target if available, else first in list.
 * Unifies the 3 duplicated model-fallback patterns.
 *
 * @param {string} targetLlm - Desired LLM model
 * @param {string[]} availableModels - List of available models
 * @returns {string}
 */
export function selectModel(targetLlm, availableModels) {
	if (targetLlm && availableModels.includes(targetLlm)) {
		return targetLlm;
	}
	return availableModels.length > 0 ? availableModels[0] : '';
}

/**
 * Load RAG placeholders from config with fallback.
 * Unifies the 2 duplicated placeholder-loading try/catch blocks.
 *
 * @param {any} config - Config defaults object
 * @returns {string[]}
 */
export function loadRagPlaceholders(config) {
	try {
		if (config && Array.isArray(config.rag_placeholders)) {
			return config.rag_placeholders;
		}
	} catch {
		// Fallback silently
	}
	return ['{context}', '{user_input}'];
}

/**
 * Extracts model IDs from various connector data structures.
 * Moved from AssistantForm.svelte to be reusable.
 *
 * @param {any} connectorData
 * @returns {string[]}
 */
export function extractModelsFromConnectorData(connectorData) {
	if (!connectorData) return [];
	if (Array.isArray(connectorData.models) && connectorData.models.length > 0) {
		if (typeof connectorData.models[0] === 'object' && connectorData.models[0].id) {
			return connectorData.models.map((m) => m.id);
		}
		return connectorData.models;
	}
	if (Array.isArray(connectorData.available_llms)) return connectorData.available_llms;
	if (
		typeof connectorData.models === 'object' &&
		connectorData.models !== null &&
		!Array.isArray(connectorData.models)
	)
		return Object.keys(connectorData.models);
	return [];
}

/**
 * Extracts model metadata objects from connector data.
 *
 * @param {any} connectorData
 * @returns {any[]}
 */
export function extractModelsMetadata(connectorData) {
	if (!connectorData) return [];
	if (Array.isArray(connectorData.models) && connectorData.models.length > 0) {
		if (typeof connectorData.models[0] === 'object' && connectorData.models[0].id) {
			return connectorData.models;
		}
	}
	return [];
}

/**
 * Escapes HTML characters for safe rendering.
 *
 * @param {string} text
 * @returns {string}
 */
function escapeHtml(text) {
	return text
		.replace(/&/g, '&amp;')
		.replace(/</g, '&lt;')
		.replace(/>/g, '&gt;')
		.replace(/"/g, '&quot;')
		.replace(/'/g, '&#39;');
}

/**
 * Highlights placeholders in prompt template text.
 * Moved from AssistantForm.svelte.
 *
 * @param {string} text
 * @param {string[]} placeholders
 * @returns {string}
 */
export function highlightPlaceholders(text, placeholders) {
	if (!text) return '';
	let result = escapeHtml(text);
	for (const placeholder of placeholders) {
		const escapedPlaceholder = escapeHtml(placeholder);
		result = result.replace(
			new RegExp(escapedPlaceholder.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g'),
			`<span class="bg-blue-100 text-blue-800 font-medium px-1 rounded">${escapedPlaceholder}</span>`
		);
	}
	return result;
}

/**
 * Extract auth token from localStorage or cookie.
 * Shared across components that need direct API access.
 * @returns {string}
 */
export function getAuthToken() {
	if (typeof localStorage !== 'undefined') {
		const token = localStorage.getItem('userToken');
		if (token) return token;
	}
	return document.cookie.replace(/(?:(?:^|.*;\s*)token\s*=\s*([^;]*).*$)|^.*$/, '$1');
}
