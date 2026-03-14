/**
 * Parse assistant metadata from the canonical metadata field or legacy api_callback.
 * Returns an empty object if the payload is missing or invalid.
 *
 * @param {any} assistant
 * @returns {Record<string, any>}
 */
export function getAssistantMetadataObject(assistant) {
	if (!assistant || typeof assistant !== 'object') return {};

	const rawMetadata = assistant.metadata ?? assistant.api_callback ?? '';
	if (!rawMetadata) return {};

	if (typeof rawMetadata === 'object') {
		return rawMetadata;
	}

	if (typeof rawMetadata !== 'string') {
		return {};
	}

	try {
		const parsed = JSON.parse(rawMetadata);
		return parsed && typeof parsed === 'object' ? parsed : {};
	} catch (error) {
		console.error('Failed to parse assistant metadata:', error);
		return {};
	}
}

/** Keys that are safe to promote from metadata to top-level assistant fields. */
const METADATA_PROMOTED_KEYS = [
	'prompt_processor',
	'connector',
	'llm',
	'rag_processor',
	'capabilities',
	'rubric_id',
	'rubric_format',
	'file_path'
];

/**
 * Normalize assistant data so plugin settings stored in metadata are always
 * available as top-level fields for frontend consumers.
 *
 * Only a known allowlist of metadata keys is promoted to avoid accidentally
 * shadowing real assistant properties like name, description, or id.
 *
 * @param {any} assistant
 * @returns {any}
 */
export function normalizeAssistantData(assistant) {
	if (!assistant || typeof assistant !== 'object') return assistant;

	const metadataObject = getAssistantMetadataObject(assistant);
	const metadataString =
		typeof assistant.metadata === 'string'
			? assistant.metadata
			: typeof assistant.api_callback === 'string'
				? assistant.api_callback
				: assistant.metadata
					? JSON.stringify(assistant.metadata)
					: '';

	/** @type {Record<string, any>} */
	const promoted = {};
	for (const key of METADATA_PROMOTED_KEYS) {
		if (key in metadataObject) {
			promoted[key] = metadataObject[key];
		}
	}

	return {
		...assistant,
		metadata: metadataString,
		api_callback: assistant.api_callback ?? metadataString,
		...promoted
	};
}
