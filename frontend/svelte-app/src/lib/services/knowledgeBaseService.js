import axios from 'axios';
import { getApiUrl } from '$lib/config'; // Use the helper for API base
import { browser } from '$app/environment';

/**
 * @typedef {Object} KnowledgeBase
 * @property {string} id
 * @property {string} name
 * @property {string} [description]
 * @property {string} owner
 * @property {number} created_at
 * @property {object} [metadata]
 */

/**
 * Fetches all knowledge bases accessible by the authenticated user.
 * @returns {Promise<KnowledgeBase[]>} A promise that resolves to an array of knowledge bases.
 * @throws {Error} If the request fails or the user is not authenticated.
 */
export async function getKnowledgeBases() {
	if (!browser) {
		throw new Error('Knowledge base fetching is only available in the browser.');
	}

	const token = localStorage.getItem('userToken');
	if (!token) {
		// Re-throw or handle appropriately, maybe redirect to login
		throw new Error('User not authenticated.');
	}

	const url = getApiUrl('/knowledgebases');
	console.log(`Fetching knowledge bases from: ${url}`);

	try {
		const response = await axios.get(url, {
			headers: {
				Authorization: `Bearer ${token}`
			}
		});

		// *** Log the raw response data for debugging ***
		console.log('Raw KB Response Data:', response.data);

		// Validate the response structure based on the example
		if (response.data && Array.isArray(response.data.knowledge_bases)) {
			console.log('Successfully fetched knowledge bases:', response.data.knowledge_bases.length);
			return response.data.knowledge_bases;
		} else {
			// If structure is wrong, throw an error including the unexpected data
			console.error('Unexpected response structure for KBs:', response.data);
			// Try to extract a message if available, otherwise use a generic error
			const detail =
				response.data?.detail || response.data?.message || JSON.stringify(response.data);
			throw new Error(
				`Failed to fetch knowledge bases: Invalid response format. Received: ${detail}`
			);
		}
	} catch (error) {
		// *** Log the raw error object for debugging ***
		console.error('Raw Error fetching knowledge bases:', error);

		let errorMessage = 'Failed to fetch knowledge bases.';
		if (axios.isAxiosError(error)) {
			// Log response data even in case of Axios error status
			console.error('Axios Error Response Data:', error.response?.data);
			if (error.response) {
				errorMessage =
					error.response.data?.detail ||
					error.response.data?.message ||
					`Request failed with status ${error.response.status}`;
			}
		} else if (error instanceof Error) {
			errorMessage = error.message;
		}
		// Ensure we throw the potentially extracted message
		throw new Error(errorMessage);
	}
}

/**
 * Creates a new knowledge base.
 *
 * @typedef {Object} KnowledgeBaseCreate
 * @property {string} name - The name of the knowledge base
 * @property {string} [description] - Optional description of the knowledge base
 * @property {string} access_control - Access control setting ('private' or 'public')
 *
 * @typedef {Object} KnowledgeBaseCreateResponse
 * @property {string} kb_id - The ID of the newly created knowledge base
 * @property {string} name - The name of the knowledge base
 * @property {string} status - Status of the operation ('success' or 'error')
 * @property {string} message - Success or error message
 *
 * @param {KnowledgeBaseCreate} data - The knowledge base data to create
 * @returns {Promise<KnowledgeBaseCreateResponse>} A promise that resolves to the created knowledge base response
 * @throws {Error} If the request fails or the user is not authenticated
 */
export async function createKnowledgeBase(data) {
	if (!browser) {
		throw new Error('Knowledge base creation is only available in the browser.');
	}

	const token = localStorage.getItem('userToken');
	if (!token) {
		throw new Error('User not authenticated.');
	}

	const url = getApiUrl('/knowledgebases');
	console.log(`Creating knowledge base at: ${url}`);

	try {
		const response = await axios.post(url, data, {
			headers: {
				Authorization: `Bearer ${token}`,
				'Content-Type': 'application/json'
			}
		});

		console.log('Knowledge base creation response:', response.data);

		if (response.data && (response.data.kb_id || response.data.status === 'success')) {
			return response.data;
		} else {
			console.error('Unexpected response structure for KB creation:', response.data);
			const detail =
				response.data?.detail || response.data?.message || JSON.stringify(response.data);
			throw new Error(
				`Failed to create knowledge base: Invalid response format. Received: ${detail}`
			);
		}
	} catch (error) {
		console.error('Error creating knowledge base:', error);

		let errorMessage = 'Failed to create knowledge base.';
		if (axios.isAxiosError(error)) {
			console.error('Axios Error Response Data:', error.response?.data);
			// Check for KB server offline error
			if (error.response?.data?.kb_server_available === false) {
				errorMessage = 'Knowledge Base server offline. Please try again later.';
			} else if (error.response) {
				errorMessage =
					error.response.data?.detail ||
					error.response.data?.message ||
					`Request failed with status ${error.response.status}`;
			}
		} else if (error instanceof Error) {
			errorMessage = error.message;
		}

		throw new Error(errorMessage);
	}
}

/**
 * Fetches details of a specific knowledge base by ID.
 *
 * @typedef {Object} KnowledgeBaseFile
 * @property {string} id - The ID of the file
 * @property {string} filename - The name of the file
 *
 * @typedef {Object} KnowledgeBaseDetails
 * @property {string} id - The ID of the knowledge base
 * @property {string} name - The name of the knowledge base
 * @property {string} [description] - Optional description of the knowledge base
 * @property {KnowledgeBaseFile[]} [files] - Optional array of files in the knowledge base
 *
 * @param {string} kbId - The ID of the knowledge base to fetch
 * @returns {Promise<KnowledgeBaseDetails>} A promise that resolves to the knowledge base details
 * @throws {Error} If the request fails, the user is not authenticated, or the knowledge base is not found
 */
export async function getKnowledgeBaseDetails(kbId) {
	if (!browser) {
		throw new Error('Knowledge base operations are only available in the browser.');
	}

	const token = localStorage.getItem('userToken');
	if (!token) {
		throw new Error('User not authenticated.');
	}

	const url = getApiUrl(`/knowledgebases/kb/${kbId}`);
	console.log(`Fetching knowledge base details from: ${url}`);

	try {
		const response = await axios.get(url, {
			headers: {
				Authorization: `Bearer ${token}`
			}
		});

		console.log('Knowledge base details response:', response.data);

		// Check for KB server offline response
		if (response.data?.status === 'error' && response.data?.kb_server_available === false) {
			throw new Error('Knowledge Base server offline. Please try again later.');
		}

		// Validate the response structure
		if (response.data && response.data.id) {
			return response.data;
		} else {
			console.error('Unexpected response structure for KB details:', response.data);
			const detail =
				response.data?.detail || response.data?.message || JSON.stringify(response.data);
			throw new Error(
				`Failed to fetch knowledge base details: Invalid response format. Received: ${detail}`
			);
		}
	} catch (error) {
		console.error('Error fetching knowledge base details:', error);

		let errorMessage = 'Failed to fetch knowledge base details.';
		if (axios.isAxiosError(error)) {
			console.error('Axios Error Response Data:', error.response?.data);

			// Check for specific error cases
			if (error.response?.data?.kb_server_available === false) {
				errorMessage = 'Knowledge Base server offline. Please try again later.';
			} else if (error.response?.status === 404) {
				errorMessage = `Knowledge base not found. ID: ${kbId}`;
			} else if (error.response) {
				errorMessage =
					error.response.data?.detail ||
					error.response.data?.message ||
					`Request failed with status ${error.response.status}`;
			}
		} else if (error instanceof Error) {
			errorMessage = error.message;
		}

		throw new Error(errorMessage);
	}
}

/**
 * Fetches available ingestion plugins for knowledge bases
 *
 * @typedef {Object} IngestionParameterDetail
 * @property {string} type - Parameter type (e.g., "integer", "string", "boolean", "array")
 * @property {string} [description] - Description of the parameter
 * @property {any} [default] - Default value for the parameter
 * @property {boolean} required - Whether the parameter is required
 * @property {string[]} [enum] - Optional list of allowed string values
 *
 * @typedef {Object} IngestionPlugin
 * @property {string} name - Name of the plugin
 * @property {string} description - Description of the plugin
 * @property {'file-ingest' | 'base-ingest'} [kind] - The type of plugin (Added based on frontend logic)
 * @property {string[]} [supported_file_types] - Optional list of supported file types
 * @property {Object<string, IngestionParameterDetail>} [parameters] - Parameters for the plugin (object keyed by param name)
 *
 * @typedef {Object} IngestionPluginsResponse
 * @property {IngestionPlugin[]} plugins - Array of available plugins
 *
 * @returns {Promise<IngestionPlugin[]>} A promise that resolves to the array of available ingestion plugins
 * @throws {Error} If the request fails or the user is not authenticated
 */
export async function getIngestionPlugins() {
	if (!browser) {
		throw new Error('Knowledge base operations are only available in the browser.');
	}

	const token = localStorage.getItem('userToken');
	if (!token) {
		throw new Error('User not authenticated.');
	}

	const url = getApiUrl('/knowledgebases/ingestion-plugins');
	console.log(`Fetching ingestion plugins from: ${url}`);

	try {
		const response = await axios.get(url, {
			headers: {
				Authorization: `Bearer ${token}`
			}
		});

		console.log('Ingestion plugins response:', response.data);

		// Check for KB server offline response
		if (response.data?.status === 'error' && response.data?.kb_server_available === false) {
			throw new Error('Knowledge Base server offline. Please try again later.');
		}

		// Validate the response structure and return plugins array
		if (response.data && response.data.plugins && Array.isArray(response.data.plugins)) {
			return response.data.plugins;
		} else {
			console.error('Unexpected response structure for ingestion plugins:', response.data);
			const detail =
				response.data?.detail || response.data?.message || JSON.stringify(response.data);
			throw new Error(
				`Failed to fetch ingestion plugins: Invalid response format. Received: ${detail}`
			);
		}
	} catch (error) {
		console.error('Error fetching ingestion plugins:', error);

		let errorMessage = 'Failed to fetch ingestion plugins.';
		if (axios.isAxiosError(error)) {
			console.error('Axios Error Response Data:', error.response?.data);

			// Check for specific error cases
			if (error.response?.data?.kb_server_available === false) {
				errorMessage = 'Knowledge Base server offline. Please try again later.';
			} else if (error.response) {
				errorMessage =
					error.response.data?.detail ||
					error.response.data?.message ||
					`Request failed with status ${error.response.status}`;
			}
		} else if (error instanceof Error) {
			errorMessage = error.message;
		}

		throw new Error(errorMessage);
	}
}

/**
 * Uploads and ingests a file to a knowledge base using a specific plugin
 *
 * @param {string} kbId - The ID of the knowledge base to upload to
 * @param {File} file - The file to upload
 * @param {string} pluginName - The name of the ingestion plugin to use
 * @param {Object} pluginParams - Parameters for the ingestion plugin
 * @returns {Promise<Object>} A promise that resolves to the upload response
 * @throws {Error} If the request fails or the user is not authenticated
 */
export async function uploadFileWithPlugin(kbId, file, pluginName, pluginParams = {}) {
	if (!browser) {
		throw new Error('Knowledge base operations are only available in the browser.');
	}

	const token = localStorage.getItem('userToken');
	if (!token) {
		throw new Error('User not authenticated.');
	}

	const url = getApiUrl(`/knowledgebases/kb/${kbId}/plugin-ingest-file`);
	console.log(`Uploading file to KB ${kbId} using plugin ${pluginName}`);

	// Create FormData
	const formData = new FormData();
	formData.append('file', file);
	formData.append('plugin_name', pluginName);

	// Add plugin parameters to form data
	Object.entries(pluginParams).forEach(([key, value]) => {
		if (value !== null && value !== undefined) {
			formData.append(key, value.toString());
		}
	});

	try {
		const response = await axios.post(url, formData, {
			headers: {
				Authorization: `Bearer ${token}`,
				'Content-Type': 'multipart/form-data'
			}
		});

		console.log('File upload response:', response.data);

		// Check for KB server offline response
		if (response.data?.status === 'error' && response.data?.kb_server_available === false) {
			throw new Error('Knowledge Base server offline. Please try again later.');
		}

		return response.data;
	} catch (error) {
		console.error('Error uploading file:', error);

		let errorMessage = 'Failed to upload file.';
		if (axios.isAxiosError(error)) {
			console.error('Axios Error Response Data:', error.response?.data);

			// Check for specific error cases
			if (error.response?.data?.kb_server_available === false) {
				errorMessage = 'Knowledge Base server offline. Please try again later.';
			} else if (error.response) {
				errorMessage =
					error.response.data?.detail ||
					error.response.data?.message ||
					`Request failed with status ${error.response.status}`;
			}
		} else if (error instanceof Error) {
			errorMessage = error.message;
		}

		throw new Error(errorMessage);
	}
}

/**
 * Fetches available query plugins for knowledge bases
 *
 * @typedef {Object} QueryPluginParamDetail
 * @property {string} type - Parameter type (e.g., "integer", "string", "float")
 * @property {string} [description] - Description of the parameter
 * @property {any} [default] - Default value for the parameter
 * @property {boolean} required - Whether the parameter is required
 * @property {string[]} [enum] - Optional list of allowed string values
 *
 * @typedef {Object} QueryPlugin
 * @property {string} name - Name of the plugin
 * @property {string} description - Description of the plugin
 * @property {Object<string, QueryPluginParamDetail>} [parameters] - Parameters for the plugin (object keyed by param name)
 *
 * @returns {Promise<QueryPlugin[]>} A promise that resolves to the array of available query plugins
 * @throws {Error} If the request fails or the user is not authenticated
 */
export async function getQueryPlugins() {
	if (!browser) {
		throw new Error('Knowledge base operations are only available in the browser.');
	}

	const token = localStorage.getItem('userToken');
	if (!token) {
		throw new Error('User not authenticated.');
	}

	const url = getApiUrl('/knowledgebases/query-plugins');
	console.log(`Fetching query plugins from: ${url}`);

	try {
		const response = await axios.get(url, {
			headers: {
				Authorization: `Bearer ${token}`
			}
		});

		console.log('Query plugins response:', response.data);

		if (response.data?.status === 'error' && response.data?.kb_server_available === false) {
			throw new Error('Knowledge Base server offline. Please try again later.');
		}

		if (response.data && response.data.plugins && Array.isArray(response.data.plugins)) {
			return response.data.plugins;
		} else {
			console.error('Unexpected response structure for query plugins:', response.data);
			const detail =
				response.data?.detail || response.data?.message || JSON.stringify(response.data);
			throw new Error(
				`Failed to fetch query plugins: Invalid response format. Received: ${detail}`
			);
		}
	} catch (error) {
		console.error('Error fetching query plugins:', error);
		let errorMessage = 'Failed to fetch query plugins.';
		if (axios.isAxiosError(error)) {
			console.error('Axios Error Response Data:', error.response?.data);
			if (error.response?.data?.kb_server_available === false) {
				errorMessage = 'Knowledge Base server offline. Please try again later.';
			} else if (error.response) {
				errorMessage =
					error.response.data?.detail ||
					error.response.data?.message ||
					`Request failed with status ${error.response.status}`;
			}
		} else if (error instanceof Error) {
			errorMessage = error.message;
		}
		throw new Error(errorMessage);
	}
}

/**
 * Executes a query against a specific knowledge base.
 *
 * @typedef {Object} QueryResultItem
 * @property {string} [document_id] - ID of the source document (may vary based on KB server)
 * @property {string} [text] - The relevant text snippet
 * @property {number} [score] - Similarity score
 * @property {string} [data] - Alternative field for text snippet (seen in other responses)
 * @property {number} [similarity] - Alternative field for score
 * @property {object} [metadata] - Any additional metadata
 *
 * @typedef {Object} QueryResponse
 * @property {QueryResultItem[]} results - Array of query results
 * @property {string} status - Status of the query ('success', 'error')
 * @property {string} [message] - Optional message from the server
 *
 * @param {string} kbId - The ID of the knowledge base to query
 * @param {string} queryText - The text of the query
 * @param {string} pluginName - The name of the query plugin to use
 * @param {Object} pluginParams - Parameters for the query plugin
 * @returns {Promise<QueryResponse>} A promise that resolves to the query response
 * @throws {Error} If the request fails or the user is not authenticated
 */
export async function queryKnowledgeBase(kbId, queryText, pluginName, pluginParams = {}) {
	if (!browser) {
		throw new Error('Knowledge base operations are only available in the browser.');
	}

	const token = localStorage.getItem('userToken');
	if (!token) {
		throw new Error('User not authenticated.');
	}

	const url = getApiUrl(`/knowledgebases/kb/${kbId}/query`);
	const payload = {
		query_text: queryText,
		plugin_name: pluginName,
		plugin_params: pluginParams
	};
	console.log(`Querying KB ${kbId} using plugin ${pluginName} with query: ${queryText}`);
	console.log('Query payload:', payload);

	try {
		const response = await axios.post(url, payload, {
			headers: {
				Authorization: `Bearer ${token}`,
				'Content-Type': 'application/json'
			}
		});

		console.log('Query response:', response.data);

		if (response.data?.status === 'error' && response.data?.kb_server_available === false) {
			throw new Error('Knowledge Base server offline. Please try again later.');
		}

		// Basic validation: Check if results array exists if status is success
		if (
			response.data &&
			response.data.status === 'success' &&
			Array.isArray(response.data.results)
		) {
			return response.data;
		} else if (response.data && response.data.status !== 'success') {
			// If status is not success, throw an error with the message if available
			const detail =
				response.data?.detail || response.data?.message || JSON.stringify(response.data);
			throw new Error(`Query failed: ${detail}`);
		} else {
			// Handle unexpected successful response format
			console.error('Unexpected response structure for KB query:', response.data);
			throw new Error('Failed to execute query: Invalid response format.');
		}
	} catch (error) {
		console.error('Error querying knowledge base:', error);
		let errorMessage = 'Failed to execute query.';
		if (axios.isAxiosError(error)) {
			console.error('Axios Error Response Data:', error.response?.data);
			if (error.response?.data?.kb_server_available === false) {
				errorMessage = 'Knowledge Base server offline. Please try again later.';
			} else if (error.response) {
				errorMessage =
					error.response.data?.detail ||
					error.response.data?.message ||
					`Request failed with status ${error.response.status}`;
			}
		} else if (error instanceof Error) {
			errorMessage = error.message;
		}
		throw new Error(errorMessage);
	}
}

/**
 * Runs a base ingestion plugin (without file upload) on a knowledge base.
 *
 * @param {string} kbId - The ID of the knowledge base
 * @param {string} pluginName - The name of the ingestion plugin to use
 * @param {Object} pluginParams - Parameters for the ingestion plugin
 * @returns {Promise<Object>} A promise that resolves to the ingestion response
 * @throws {Error} If the request fails or the user is not authenticated
 */
export async function runBaseIngestionPlugin(kbId, pluginName, pluginParams = {}) {
	if (!browser) {
		throw new Error('Knowledge base operations are only available in the browser.');
	}

	const token = localStorage.getItem('userToken');
	if (!token) {
		throw new Error('User not authenticated.');
	}

	// Assume a new endpoint for base ingestion
	const url = getApiUrl(`/knowledgebases/kb/${kbId}/plugin-ingest-base`);
	console.log(`Running base ingestion on KB ${kbId} using plugin ${pluginName}`);

	const payload = {
		plugin_name: pluginName,
		parameters: pluginParams
	};

	try {
		const response = await axios.post(url, payload, {
			headers: {
				Authorization: `Bearer ${token}`,
				'Content-Type': 'application/json'
			}
		});

		console.log('Base ingestion response:', response.data);

		// Check for KB server offline response
		if (response.data?.status === 'error' && response.data?.kb_server_available === false) {
			throw new Error('Knowledge Base server offline. Please try again later.');
		}

		// Assuming success if no specific error status or message is present
		if (response.data?.status === 'error') {
			throw new Error(response.data.message || 'Base ingestion failed with an unspecified error.');
		}

		return response.data; // Return the response, e.g., { status: 'success', message: '... '} or similar
	} catch (error) {
		console.error('Error running base ingestion:', error);

		let errorMessage = 'Failed to run base ingestion.';
		if (axios.isAxiosError(error)) {
			console.error('Axios Error Response Data:', error.response?.data);

			// Check for specific error cases
			if (error.response?.data?.kb_server_available === false) {
				errorMessage = 'Knowledge Base server offline. Please try again later.';
			} else if (error.response) {
				errorMessage =
					error.response.data?.detail ||
					error.response.data?.message ||
					`Request failed with status ${error.response.status}`;
			}
		} else if (error instanceof Error) {
			errorMessage = error.message;
		}

		throw new Error(errorMessage);
	}
}

/**
 * Deletes a file from a knowledge base.
 *
 * @typedef {Object} DeleteFileResponse
 * @property {string} message - Success message
 * @property {string} knowledge_base_id - The ID of the knowledge base
 * @property {string} file_id - The ID of the deleted file
 *
 * @param {string} kbId - The ID of the knowledge base
 * @param {string} fileId - The ID of the file to delete
 * @returns {Promise<DeleteFileResponse>} A promise that resolves to the delete response
 * @throws {Error} If the request fails or the user is not authenticated
 */
export async function deleteFileFromKnowledgeBase(kbId, fileId) {
	if (!browser) {
		throw new Error('Knowledge base operations are only available in the browser.');
	}

	const token = localStorage.getItem('userToken');
	if (!token) {
		throw new Error('User not authenticated.');
	}

	const url = getApiUrl(`/knowledgebases/kb/${kbId}/files/${fileId}`);
	console.log(`Deleting file ${fileId} from knowledge base ${kbId}`);

	try {
		const response = await axios.delete(url, {
			headers: {
				Authorization: `Bearer ${token}`
			}
		});

		console.log('File delete response:', response.data);

		// Check for KB server offline response
		if (response.data?.status === 'error' && response.data?.kb_server_available === false) {
			throw new Error('Knowledge Base server offline. Please try again later.');
		}

		// Validate the response structure
		if (response.data && (response.data.message || response.data.status === 'success')) {
			return response.data;
		} else {
			console.error('Unexpected response structure for file deletion:', response.data);
			const detail =
				response.data?.detail || response.data?.message || JSON.stringify(response.data);
			throw new Error(`Failed to delete file: Invalid response format. Received: ${detail}`);
		}
	} catch (error) {
		console.error('Error deleting file from knowledge base:', error);

		let errorMessage = 'Failed to delete file.';
		if (axios.isAxiosError(error)) {
			console.error('Axios Error Response Data:', error.response?.data);

			// Check for specific error cases
			if (error.response?.data?.kb_server_available === false) {
				errorMessage = 'Knowledge Base server offline. Please try again later.';
			} else if (error.response?.status === 404) {
				errorMessage = 'File not found in knowledge base.';
			} else if (error.response?.status === 403) {
				errorMessage = "You don't have permission to delete files from this knowledge base.";
			} else if (error.response) {
				errorMessage =
					error.response.data?.detail ||
					error.response.data?.message ||
					`Request failed with status ${error.response.status}`;
			}
		} else if (error instanceof Error) {
			errorMessage = error.message;
		}

		throw new Error(errorMessage);
	}
}
