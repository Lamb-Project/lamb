// assistantFormSubmit.js
/**
 * Pure functions for AssistantForm submission logic.
 * Extracted from AssistantForm.svelte to enable isolated testing.
 */

import { isKbBasedRag, isKsBasedRag, isSingleFileRag, isRubricRag } from '$lib/utils/ragProcessorHelpers.js';

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
		capabilities: {
			vision: form.visionEnabled,
			image_generation: form.imageGenerationEnabled
		}
	};

	if (form.documentRagEnabled) {
		metadataObj.document_rag = 'single_file_rag';
		metadataObj.library_id = form.selectedLibraryId || '';
		metadataObj.item_id = form.selectedItemId || '';
	} else if (isSingleFileRag(form.selectedRagProcessor) && form.selectedFilePath) {
		metadataObj.file_path = form.selectedFilePath;
	}

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
		RAG_collections: isKbBasedRag(form.selectedRagProcessor)
			? form.selectedKnowledgeBases.join(',')
			: isKsBasedRag(form.selectedRagProcessor)
				? form.selectedKnowledgeStores.join(',')
				: '',
		metadata: JSON.stringify(metadataObj),
		pre_retrieval_endpoint: '',
		post_retrieval_endpoint: '',
		RAG_endpoint: ''
	};
}
