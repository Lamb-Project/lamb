// assistantFormSubmit.js
/**
 * Pure functions for AssistantForm submission logic.
 * Extracted from AssistantForm.svelte to enable isolated testing.
 */

import {
	isKbBasedRag,
	isKsBasedRag,
	isSingleFileRag,
	isRubricRag,
	PPS_COMPATIBLE_RAG,
	ppsSupportsDocumentRag
} from '$lib/utils/ragProcessorHelpers.js';

/**
 * @param {string} pps
 * @param {string} rag
 * @returns {boolean}
 */
function isRagCompatibleWithPps(pps, rag) {
	if (!rag) return true;
	const compatible = PPS_COMPATIBLE_RAG[pps];
	if (!compatible) return true;
	return compatible.includes(rag);
}

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

	if (
		form.selectedRagProcessor &&
		!isRagCompatibleWithPps(form.selectedPromptProcessor, form.selectedRagProcessor)
	) {
		return (
			`RAG processor '${form.selectedRagProcessor}' is not compatible with ` +
			`prompt processor '${form.selectedPromptProcessor}'.`
		);
	}

	if (form.documentRagEnabled && !ppsSupportsDocumentRag(form.selectedPromptProcessor)) {
		return (
			`Reference Document is not supported with prompt processor ` +
			`'${form.selectedPromptProcessor}'.`
		);
	}

	if (form.documentRagEnabled && ppsSupportsDocumentRag(form.selectedPromptProcessor)) {
		if (!form.selectedLibraryId?.trim() || !form.selectedItemId?.trim()) {
			return 'Please select a library and document for Reference Document.';
		}
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

	const supportsDocumentRag =
		form.documentRagEnabled && ppsSupportsDocumentRag(form.selectedPromptProcessor);

	if (supportsDocumentRag) {
		metadataObj.document_rag = 'library_file_rag';
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
