// assistantFormSubmit.js
/**
 * Pure functions for AssistantForm submission logic.
 * Extracted from AssistantForm.svelte to enable isolated testing.
 */

import { isKbBasedRag, isSingleFileRag, isRubricRag, isGrepRag } from '$lib/utils/ragProcessorHelpers.js';

/**
 * Validates form data before submission.
 * @param {{ name: string, selectedRagProcessor: string, selectedRubricId: string }} form
 * @returns {string | null} Error message or null if valid
 */
export function validateSubmission(form) {
	if (!form.name?.trim()) return 'Assistant Name is required.';
	if (isRubricRag(form.selectedRagProcessor) && !form.selectedRubricId) {
		return 'Please select a rubric when using Rubric RAG.';
	}
	return null;
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

	if (isGrepRag(form.selectedRagProcessor)) {
		metadataObj.grep_mode = form.grepMode;
		metadataObj.grep_fallback_rag = form.grepFallbackRag;
		metadataObj.grep_max_tries = form.grepMaxTries;
		metadataObj.grep_context_lines = form.grepContextLines;
		metadataObj.grep_max_total_chars = form.grepMaxTotalChars;
	}

	return {
		name: form.name.trim(),
		description: form.description,
		system_prompt: form.system_prompt,
		prompt_template: form.prompt_template,
		RAG_Top_k: Number(form.RAG_Top_k) || 3,
		RAG_collections: (isKbBasedRag(form.selectedRagProcessor) || isGrepRag(form.selectedRagProcessor)) ? form.selectedKnowledgeBases.join(',') : '',
		metadata: JSON.stringify(metadataObj),
		pre_retrieval_endpoint: '',
		post_retrieval_endpoint: '',
		RAG_endpoint: ''
	};
}
