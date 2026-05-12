// importAssistantValidator.js — Pure validation for assistant import JSON
// Extracted from AssistantForm.svelte handleFileSelect (Task Extra: SRP)

/**
 * @typedef {Object} ImportValidationResult
 * @property {any} parsedData - The parsed JSON data (null on error)
 * @property {any} callbackData - Parsed metadata/fallback (null on error)
 * @property {string[]} validationLog - Ordered log of validation messages
 * @property {boolean} hasErrors - True if any ❌ entries exist
 */

/**
 * Validates an imported assistant JSON against system capabilities.
 * Pure function — no DOM access, no state mutation, no side effects.
 *
 * @param {string | null} jsonContent - Raw JSON string from the import file
 * @param {any} capabilities - systemCapabilities from the config store (or null)
 * @param {function(any): string[]} modelExtractor - function to extract model IDs from connector data
 * @returns {ImportValidationResult}
 */
export function validateImportedAssistant(jsonContent, capabilities, modelExtractor) {
    const validationLog = ['Starting validation...'];
    let parsedData = null;
    let callbackData = null;

    if (typeof jsonContent !== 'string') {
        validationLog.push('❌ Empty or invalid file content');
        return { parsedData: null, callbackData: null, validationLog, hasErrors: true };
    }

    // Parse JSON
    try {
        parsedData = /** @type {any} */ (JSON.parse(jsonContent));
        validationLog.push('✅ JSON parsed successfully.');
    } catch (jsonError) {
        validationLog.push(`❌ Invalid JSON format: ${jsonError instanceof Error ? jsonError.message : 'Unknown JSON error'}`);
        return { parsedData: null, callbackData: null, validationLog, hasErrors: true };
    }

    if (!parsedData || typeof parsedData !== 'object' || Array.isArray(parsedData)) {
        validationLog.push('❌ Imported data is not a valid JSON object.');
        return { parsedData, callbackData: null, validationLog, hasErrors: true };
    }

    if (!capabilities) {
        validationLog.push('⚠️ System capabilities not loaded. Skipping detailed validation.');
        return { parsedData, callbackData: null, validationLog, hasErrors: false };
    }

    validationLog.push('ℹ️ System capabilities loaded. Performing detailed checks...');

    // Validate required fields
    const requiredFields = ['name', 'system_prompt', 'metadata'];
    for (const field of requiredFields) {
        if (!(field in parsedData)) {
            validationLog.push(`❌ Missing required field: ${field}`);
        }
    }

    // Validate metadata content (fallback to api_callback for backward compatibility)
    const metadataStr = parsedData.metadata || parsedData.api_callback;
    if (metadataStr && typeof metadataStr === 'string') {
        try {
            callbackData = JSON.parse(metadataStr);
            validationLog.push('✅ Parsed metadata successfully.');

            // Validate against capabilities
            if (callbackData.prompt_processor && !capabilities.prompt_processors?.includes(callbackData.prompt_processor)) {
                validationLog.push(`⚠️ Invalid prompt_processor: ${callbackData.prompt_processor}. Available: ${capabilities.prompt_processors?.join(', ')}`);
            }
            if (callbackData.connector && !capabilities.connectors?.[callbackData.connector]) {
                validationLog.push(`⚠️ Invalid connector: ${callbackData.connector}. Available: ${Object.keys(capabilities.connectors || {}).join(', ')}`);
            } else if (callbackData.connector && callbackData.llm) {
                const connectorCaps = capabilities.connectors?.[callbackData.connector];
                if (connectorCaps) {
                    const availableLLMs = modelExtractor(connectorCaps);
                    if (!availableLLMs.includes(callbackData.llm)) {
                        validationLog.push(`⚠️ Invalid llm for connector ${callbackData.connector}: ${callbackData.llm}. Available: ${availableLLMs.join(', ')}`);
                    }
                } else {
                    validationLog.push(`⚠️ Could not retrieve capabilities for connector ${callbackData.connector}.`);
                }
            }
            if (callbackData.rag_processor && !capabilities.rag_processors?.includes(callbackData.rag_processor)) {
                validationLog.push(`⚠️ Invalid rag_processor: ${callbackData.rag_processor}. Available: ${capabilities.rag_processors?.join(', ')}`);
            }

            // Specific checks based on rag_processor
            if (callbackData.rag_processor === 'single_file_rag' && !callbackData.file_path) {
                validationLog.push('❌ Missing file_path in metadata for single_file_rag processor.');
            }
        } catch (callbackError) {
            validationLog.push(`❌ Error parsing metadata JSON: ${callbackError instanceof Error ? callbackError.message : 'Unknown error'}`);
        }
    } else {
        validationLog.push('❌ metadata field is missing or not a string.');
    }

    // Validate top-level RAG fields if processor requires them
    const isKbBased =
        callbackData?.rag_processor === 'simple_rag' ||
        callbackData?.rag_processor === 'context_aware_rag' ||
        callbackData?.rag_processor === 'hierarchical_rag';
    if (isKbBased) {
        if (parsedData.RAG_Top_k === undefined || typeof parsedData.RAG_Top_k !== 'number') {
            validationLog.push(`⚠️ RAG_Top_k is missing or not a number (Required for ${callbackData.rag_processor}). Found: ${typeof parsedData.RAG_Top_k}`);
        }
        if (parsedData.RAG_collections === undefined || typeof parsedData.RAG_collections !== 'string') {
            validationLog.push(`⚠️ RAG_collections is missing or not a string (Required for ${callbackData.rag_processor}). Found: ${typeof parsedData.RAG_collections}`);
        }
    }

    const hasErrors = validationLog.some(log => log.startsWith('❌'));

    return { parsedData, callbackData, validationLog, hasErrors };
}
