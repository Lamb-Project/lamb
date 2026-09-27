// assistantFormSubmit.js
/**
 * Pure functions for AssistantForm submission logic.
 * Extracted from AssistantForm.svelte to enable isolated testing.
 */

import { isKbBasedRag, isSingleFileRag, isRubricRag } from '$lib/utils/ragProcessorHelpers.js';

/**
 * Validates form data before submission.
 * @param {Record<string, any>} form
 * @returns {string | null} Error message or null if valid
 */
export function validateSubmission(form) {
	if (!form.name?.trim()) return 'Assistant Name is required.';
	if (isRubricRag(form.selectedRagProcessor) && !form.selectedRubricId) {
		return 'Please select a rubric when using Rubric RAG.';
	}
	// An edit that leaves the configuration as stored is not blocked by rules newer than it (#335).
	if (form.formState === 'edit' && form.initialAssistantData && !ragConfigChanged(form)) return null;
	const problems = ragConfigErrors(form);
	return problems.length ? problems.join(' ') : null;
}

/**
 * @param {any} metadata
 * @param {string} template
 * @param {string} collections
 */
function ruleInputs(metadata, template, collections) {
	let meta = metadata;
	if (typeof meta === 'string') {
		try { meta = meta.trim() ? JSON.parse(meta) : {}; } catch { meta = {}; }
	}
	meta = meta && typeof meta === 'object' ? meta : {};
	return JSON.stringify([meta.prompt_processor || 'simple_augment', meta.rag_processor || 'no_rag', template || '',
		(collections || '').trim(), meta.file_path || '', String(meta.rubric_id || '')]);
}

/** @param {Record<string, any>} form */
function ragConfigChanged(form) {
	const stored = form.initialAssistantData;
	const payload = buildAssistantPayload(form);
	return ruleInputs(payload.metadata, payload.prompt_template, payload.RAG_collections) !==
		ruleInputs(stored.metadata ?? stored.api_callback, stored.prompt_template, stored.RAG_collections);
}

/** @type {Record<string, string>} */
const RAG_NAMES = {
	simple_rag: 'Simple RAG',
	context_aware_rag: 'Context-aware RAG',
	hierarchical_rag: 'Hierarchical RAG',
	single_file_rag: 'Single file RAG',
	rubric_rag: 'Rubric RAG'
};

/**
 * What the selected RAG configuration needs to work; same rules as the server
 * (backend/lamb/services/assistant_config_rules.py, #335). Custom prompt processors are not checked.
 * @param {Record<string, any>} form
 * @returns {string[]}
 */
export function ragConfigErrors(form) {
	if ((form.selectedPromptProcessor || 'simple_augment') !== 'simple_augment') return [];
	const rag = form.selectedRagProcessor || 'no_rag';
	const template = form.prompt_template || '';
	if (rag === 'no_rag') {
		return template.trim() && !template.includes('{user_input}')
			? ["The prompt template needs {user_input}, where the student's message goes (or leave the template empty)."]
			: [];
	}
	const name = RAG_NAMES[rag];
	if (!name) return [];
	const errors = [];
	if (!template.includes('{user_input}')) errors.push(`${name} needs {user_input} in the prompt template, where the student's message goes.`);
	if (!template.includes('{context}')) errors.push(`${name} needs {context} in the prompt template, where the retrieved content goes.`);
	if (isKbBasedRag(rag) && !(form.selectedKnowledgeBases || []).length) errors.push(`${name} needs at least one knowledge base.`);
	if (isSingleFileRag(rag) && !form.selectedFilePath) errors.push('Single file RAG needs a file.');
	return errors;
}

/**
 * Builds the API payload from form state.
 * @param {Record<string, any>} form
 * @returns {Record<string, any>}
 */
export function buildAssistantPayload(form) {
	const metadataObj = {
		prompt_processor: form.selectedPromptProcessor,
		connector: form.selectedConnector,
		llm: form.selectedLlm,
		rag_processor: form.selectedRagProcessor,
		file_path: isSingleFileRag(form.selectedRagProcessor) ? form.selectedFilePath : '',
		capabilities: {
			vision: form.visionEnabled,
			image_generation: form.imageGenerationEnabled
		}
	};

	if (isRubricRag(form.selectedRagProcessor)) {
		metadataObj.rubric_id = form.selectedRubricId;
		metadataObj.rubric_format = form.rubricFormat;
	}

	return {
		name: form.name.trim(),
		description: form.description,
		system_prompt: form.system_prompt,
		prompt_template: form.prompt_template,
		RAG_Top_k: Number(form.RAG_Top_k) || 3,
		RAG_collections: isKbBasedRag(form.selectedRagProcessor) ? form.selectedKnowledgeBases.join(',') : '',
		metadata: JSON.stringify(metadataObj),
		pre_retrieval_endpoint: '',
		post_retrieval_endpoint: '',
		RAG_endpoint: ''
	};
}
