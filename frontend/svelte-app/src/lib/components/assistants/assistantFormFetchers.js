// assistantFormFetchers.js
/**
 * Pure fetch functions for AssistantForm data dependencies.
 * Extracted from AssistantForm.svelte to enable isolated testing.
 */

import { getUserKnowledgeBases, getSharedKnowledgeBases } from '$lib/services/knowledgeBaseService';
import { fetchAccessibleRubrics } from '$lib/services/rubricService';
import { apiJson } from '$lib/services/apiClient';
import { isKbBasedRag, isRubricRag } from '$lib/utils/ragProcessorHelpers.js';
import { getAssistantMetadataObject } from '$lib/utils/assistantData';

/**
 * Fetches accessible knowledge bases (owned + shared).
 * @param {import('./assistantFormState.svelte.js').createAssistantFormState} form
 */
export async function fetchKnowledgeBases(form) {
	if (form.loadingKnowledgeBases || form.kbFetchAttempted) return;
	if (!isKbBasedRag(form.selectedRagProcessor)) return;

	form.loadingKnowledgeBases = true;
	form.knowledgeBaseError = '';

	try {
		const [owned, shared] = await Promise.all([
			getUserKnowledgeBases(),
			getSharedKnowledgeBases()
		]);
		owned.sort((a, b) => a.name.localeCompare(b.name));
		shared.sort((a, b) => a.name.localeCompare(b.name));
		form.ownedKnowledgeBases = owned;
		form.sharedKnowledgeBases = shared;
	} catch (err) {
		if (err instanceof Error && err.message.startsWith('Session expired')) return;
		console.error('Error fetching knowledge bases:', err);
		form.knowledgeBaseError = err instanceof Error ? err.message : 'Failed to load knowledge bases';
		form.ownedKnowledgeBases = [];
		form.sharedKnowledgeBases = [];
	} finally {
		form.loadingKnowledgeBases = false;
		form.kbFetchAttempted = true;
	}
}

/**
 * Fetches accessible rubrics.
 * @param {import('./assistantFormState.svelte.js').createAssistantFormState} form
 */
export async function fetchRubricsList(form) {
	if (form.loadingRubrics || form.rubricsFetchAttempted) return;
	if (!isRubricRag(form.selectedRagProcessor)) return;

	form.loadingRubrics = true;
	form.rubricError = '';

	try {
		const response = await fetchAccessibleRubrics();
		form.accessibleRubrics = response.rubrics || [];
	} catch (err) {
		console.error('Error fetching accessible rubrics:', err);
		form.rubricError = err instanceof Error ? err.message : 'Failed to load rubrics';
		form.accessibleRubrics = [];
	} finally {
		form.loadingRubrics = false;
		form.rubricsFetchAttempted = true;
	}
}

/**
 * Fetches the user's files.
 * @param {import('./assistantFormState.svelte.js').createAssistantFormState} form
 * @param {{ force?: boolean, assistant?: any }} options
 */
export async function fetchUserFiles(form, { force = false, assistant = null } = {}) {
	if (form.loadingFiles || (!force && form.filesFetchAttempted)) return;
	form.loadingFiles = true;
	form.fileError = '';

	try {
		const data = await apiJson('/files/list');
		form.userFiles = data;
		const callbackData = getAssistantMetadataObject(assistant);
		if (callbackData.file_path && form.userFiles.some(file => file.path === callbackData.file_path)) {
			form.selectedFilePath = callbackData.file_path;
		}
	} catch (err) {
		if (err instanceof Error && err.message.startsWith('Session expired')) return;
		form.fileError = err instanceof Error ? err.message : 'Failed to load files';
		form.userFiles = [];
	} finally {
		form.loadingFiles = false;
		form.filesFetchAttempted = true;
	}
}
