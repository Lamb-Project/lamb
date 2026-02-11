import axios from 'axios';
import { getApiUrl } from '$lib/config'; // Use the helper for API base
import { browser } from '$app/environment';

/**
 * @typedef {Object} IngestionConfig
 * @property {number} refresh_rate - Polling interval in seconds
 */

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
 * Get ingestion configuration from backend.
 * 
 * @returns {Promise<IngestionConfig>} Configuration including refresh rate
 * @throws {Error} If the request fails
 */
export async function getIngestionConfig() {
    if (!browser) {
        throw new Error('Configuration fetching is only available in the browser.');
    }

    const url = getApiUrl('/config/ingestion');
    console.log(`Fetching ingestion config from: ${url}`);

    try {
        const response = await axios.get(url);
        console.log('Ingestion config response:', response.data);
        return response.data;
    } catch (error) {
        console.error('Error fetching ingestion config:', error);
        // Return default values if fetch fails
        return { refresh_rate: 3 };
    }
}

/**
 * Fetches user's owned knowledge bases.
 * @returns {Promise<KnowledgeBase[]>} A promise that resolves to an array of owned knowledge bases.
 * @throws {Error} If the request fails or the user is not authenticated.
 */
export async function getUserKnowledgeBases() {
    if (!browser) {
        throw new Error('Knowledge base fetching is only available in the browser.');
    }

    const token = localStorage.getItem('userToken');
    if (!token) {
        throw new Error('User not authenticated.'); 
    }

    const url = getApiUrl('/knowledgebases/user');
    console.log(`Fetching owned knowledge bases from: ${url}`);

    try {
        const response = await axios.get(url, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        console.log('Raw Owned KB Response Data:', response.data);

        // Validate the response structure
        if (response.data && Array.isArray(response.data.knowledge_bases)) {
            console.log('Successfully fetched owned knowledge bases:', response.data.knowledge_bases.length);
            return response.data.knowledge_bases;
        } else {
            console.error('Unexpected response structure for owned KBs:', response.data);
            const detail = response.data?.detail || response.data?.message || JSON.stringify(response.data);
            throw new Error(`Failed to fetch owned knowledge bases: Invalid response format. Received: ${detail}`);
        }
    } catch (error) {       
        console.error('Raw Error fetching owned knowledge bases:', error);
        
        let errorMessage = 'Failed to fetch owned knowledge bases.';
        if (axios.isAxiosError(error)) {
            console.error('Axios Error Response Data:', error.response?.data);
            if (error.response) {
                errorMessage = error.response.data?.detail || error.response.data?.message || `Request failed with status ${error.response.status}`;
            }
        } else if (error instanceof Error) {
            errorMessage = error.message;
        }
        throw new Error(errorMessage);
    }
}

/**
 * Fetches organization shared knowledge bases (excluding user's own).
 * @returns {Promise<KnowledgeBase[]>} A promise that resolves to an array of shared knowledge bases.
 * @throws {Error} If the request fails or the user is not authenticated.
 */
export async function getSharedKnowledgeBases() {
    if (!browser) {
        throw new Error('Knowledge base fetching is only available in the browser.');
    }

    const token = localStorage.getItem('userToken');
    if (!token) {
        throw new Error('User not authenticated.'); 
    }

    const url = getApiUrl('/knowledgebases/shared');
    console.log(`Fetching shared knowledge bases from: ${url}`);

    try {
        const response = await axios.get(url, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        console.log('Raw Shared KB Response Data:', response.data);

        // Validate the response structure
        if (response.data && Array.isArray(response.data.knowledge_bases)) {
            console.log('Successfully fetched shared knowledge bases:', response.data.knowledge_bases.length);
            return response.data.knowledge_bases;
        } else {
            console.error('Unexpected response structure for shared KBs:', response.data);
            const detail = response.data?.detail || response.data?.message || JSON.stringify(response.data);
            throw new Error(`Failed to fetch shared knowledge bases: Invalid response format. Received: ${detail}`);
        }
    } catch (error) {       
        console.error('Raw Error fetching shared knowledge bases:', error);
        
        let errorMessage = 'Failed to fetch shared knowledge bases.';
        if (axios.isAxiosError(error)) {
            console.error('Axios Error Response Data:', error.response?.data);
            if (error.response) {
                errorMessage = error.response.data?.detail || error.response.data?.message || `Request failed with status ${error.response.status}`;
            }
        } else if (error instanceof Error) {
            errorMessage = error.message;
        }
        throw new Error(errorMessage);
    }
}

/**
 * @deprecated Use getUserKnowledgeBases() and getSharedKnowledgeBases() separately instead.
 * Fetches all knowledge bases accessible by the authenticated user.
 * @returns {Promise<KnowledgeBase[]>} A promise that resolves to an array of knowledge bases.
 * @throws {Error} If the request fails or the user is not authenticated.
 */
export async function getKnowledgeBases() {
    // For backward compatibility, fetch both and combine
    const [owned, shared] = await Promise.all([
        getUserKnowledgeBases().catch(() => []),
        getSharedKnowledgeBases().catch(() => [])
    ]);
    return [...owned, ...shared];
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
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });

        console.log('Knowledge base creation response:', response.data);
        
        if (response.data && (response.data.kb_id || response.data.status === 'success')) {
            return response.data;
        } else {
            console.error('Unexpected response structure for KB creation:', response.data);
            const detail = response.data?.detail || response.data?.message || JSON.stringify(response.data);
            throw new Error(`Failed to create knowledge base: Invalid response format. Received: ${detail}`);
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
                errorMessage = error.response.data?.detail || error.response.data?.message || `Request failed with status ${error.response.status}`;
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
                'Authorization': `Bearer ${token}`
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
            const detail = response.data?.detail || response.data?.message || JSON.stringify(response.data);
            throw new Error(`Failed to fetch knowledge base details: Invalid response format. Received: ${detail}`);
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
                errorMessage = error.response.data?.detail || error.response.data?.message || 
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
 * @property {string} type - Parameter type (e.g., "integer", "string", "boolean", "array", "long-string")
 * @property {string} [description] - Description of the parameter
 * @property {any} [default] - Default value for the parameter
 * @property {boolean} required - Whether the parameter is required
 * @property {string[]} [enum] - Optional list of allowed string values
 * @property {Object<string, string>} [enum_labels] - Human-readable labels for enum values
 * @property {Object<string, string[]>} [visible_when] - Conditions for showing this parameter (e.g., {"chunking_mode": ["standard"]})
 * @property {string} [help_text] - Additional help text for the parameter
 * @property {string} [ui_hint] - UI rendering hint (e.g., "slider", "select", "textarea", "number")
 * @property {number} [min] - Minimum value for numeric parameters
 * @property {number} [max] - Maximum value for numeric parameters
 * @property {string[]} [applicable_to] - File types this parameter applies to
 * 
 * @typedef {Object} IngestionPlugin
 * @property {string} name - Name of the plugin
 * @property {string} description - Description of the plugin
 * @property {'file-ingest' | 'base-ingest' | 'remote-ingest'} [kind] - The type of plugin
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
                'Authorization': `Bearer ${token}`
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
            const detail = response.data?.detail || response.data?.message || JSON.stringify(response.data);
            throw new Error(`Failed to fetch ingestion plugins: Invalid response format. Received: ${detail}`);
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
                errorMessage = error.response.data?.detail || error.response.data?.message || 
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
                'Authorization': `Bearer ${token}`,
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
                errorMessage = error.response.data?.detail || error.response.data?.message || 
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
                'Authorization': `Bearer ${token}`
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
            const detail = response.data?.detail || response.data?.message || JSON.stringify(response.data);
            throw new Error(`Failed to fetch query plugins: Invalid response format. Received: ${detail}`);
        }
    } catch (error) {
        console.error('Error fetching query plugins:', error);
        let errorMessage = 'Failed to fetch query plugins.';
        if (axios.isAxiosError(error)) {
            console.error('Axios Error Response Data:', error.response?.data);
            if (error.response?.data?.kb_server_available === false) {
                errorMessage = 'Knowledge Base server offline. Please try again later.';
            } else if (error.response) {
                errorMessage = error.response.data?.detail || error.response.data?.message || 
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
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });

        console.log('Query response:', response.data);
        
        if (response.data?.status === 'error' && response.data?.kb_server_available === false) {
            throw new Error('Knowledge Base server offline. Please try again later.');
        }
        
        // Basic validation: Check if results array exists if status is success
        if (response.data && response.data.status === 'success' && Array.isArray(response.data.results)) {
             return response.data;
        } else if (response.data && response.data.status !== 'success') {
            // If status is not success, throw an error with the message if available
            const detail = response.data?.detail || response.data?.message || JSON.stringify(response.data);
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
                errorMessage = error.response.data?.detail || error.response.data?.message || 
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
                'Authorization': `Bearer ${token}`,
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
                errorMessage = error.response.data?.detail || error.response.data?.message || 
                             `Request failed with status ${error.response.status}`;
            }
        } else if (error instanceof Error) {
            errorMessage = error.message;
        }
        
        throw new Error(errorMessage);
    }
} 

/**
 * Deletes a file from a knowledge base
 * @param {string} kbId
 * @param {string|number} fileId
 * @param {boolean} hard
 */
export async function deleteKnowledgeBaseFile(kbId, fileId, hard = true) {
    if (!browser) {
        throw new Error('Knowledge base operations are only available in the browser.');
    }
    const token = localStorage.getItem('userToken');
    if (!token) {
        throw new Error('User not authenticated.');
    }
    const url = getApiUrl(`/knowledgebases/kb/${kbId}/files/${fileId}`) + `?hard=${hard}`;
    try {
        const response = await axios.delete(url, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        return response.data;
    } catch (error) {
        let msg = 'Failed to delete file.';
        if (axios.isAxiosError(error)) {
            msg = error.response?.data?.detail || error.response?.data?.message || msg;
        } else if (error instanceof Error) {
            msg = error.message;
        }
        throw new Error(msg);
    }
}

/**
 * Delete an entire knowledge base
 * @param {string|number} kbId
 */
export async function deleteKnowledgeBase(kbId) {
    if (!browser) throw new Error('Knowledge base operations are only available in the browser.');
    const token = localStorage.getItem('userToken');
    if (!token) throw new Error('User not authenticated.');
    const url = getApiUrl(`/knowledgebases/kb/${kbId}`);
    try {
        const response = await axios.delete(url, { headers: { 'Authorization': `Bearer ${token}` } });
        return response.data;
    } catch (error) {
        let msg = 'Failed to delete knowledge base.';
        if (axios.isAxiosError(error)) {
            msg = error.response?.data?.detail || error.response?.data?.message || msg;
        } else if (error instanceof Error) {
            msg = error.message;
        }
        throw new Error(msg);
    }
}

// --- Ingestion Status API Methods --- //

/**
 * @typedef {Object} IngestionProgress
 * @property {number} current - Current progress count
 * @property {number} total - Total items to process
 * @property {number} percentage - Progress percentage (0-100)
 * @property {string} message - Current status message
 */

/**
 * @typedef {Object} LLMCallDetail
 * @property {string} image - Image filename that was processed
 * @property {number} duration_ms - Time taken in milliseconds
 * @property {number} [tokens_used] - Estimated tokens used
 * @property {boolean} success - Whether the call succeeded
 * @property {string} [error] - Error message if failed
 */

/**
 * @typedef {Object} ChunkStats
 * @property {number} count - Total number of chunks created
 * @property {number} avg_size - Average chunk size in characters
 * @property {number} min_size - Minimum chunk size
 * @property {number} max_size - Maximum chunk size
 */

/**
 * @typedef {Object} StageTiming
 * @property {string} stage - Stage name (e.g., 'conversion', 'chunking')
 * @property {number} duration_ms - Duration in milliseconds
 * @property {string} message - Human-readable description
 * @property {string} [timestamp] - ISO timestamp when stage completed
 */

/**
 * @typedef {Object} OutputFiles
 * @property {string} [markdown_url] - URL to converted markdown file
 * @property {string} [images_folder_url] - URL to extracted images folder
 * @property {string} [original_file_url] - URL to original uploaded file
 */

/**
 * @typedef {Object} ProcessingStats
 * @property {number} content_length - Total characters processed
 * @property {number} images_extracted - Number of images extracted
 * @property {number} images_with_llm_descriptions - Images with LLM descriptions
 * @property {LLMCallDetail[]} llm_calls - Details of individual LLM API calls
 * @property {number} total_llm_duration_ms - Total LLM processing time (ms)
 * @property {string} [chunking_strategy] - Chunking strategy used
 * @property {ChunkStats} [chunk_stats] - Chunk statistics
 * @property {StageTiming[]} stage_timings - Stage-by-stage timing
 * @property {OutputFiles} [output_files] - Generated output file URLs
 * @property {string} [markdown_preview] - Preview of markdown content
 */

/**
 * @typedef {Object} IngestionJob
 * @property {number} id - Job ID
 * @property {number} job_id - Alias for id
 * @property {number} collection_id - Collection ID
 * @property {string} [collection_name] - Collection name
 * @property {string} original_filename - Original uploaded filename
 * @property {string} [file_path] - Path to the file
 * @property {string} [file_url] - URL to access the file
 * @property {number} [file_size] - File size in bytes
 * @property {string} [content_type] - MIME type
 * @property {string} plugin_name - Name of the ingestion plugin used
 * @property {Object} [plugin_params] - Parameters passed to the plugin
 * @property {'pending' | 'processing' | 'completed' | 'failed' | 'cancelled' | 'deleted'} status - Job status
 * @property {number} document_count - Number of documents/chunks created
 * @property {string} [created_at] - ISO timestamp of creation
 * @property {string} [updated_at] - ISO timestamp of last update
 * @property {string} [processing_started_at] - ISO timestamp when processing started
 * @property {string} [processing_completed_at] - ISO timestamp when processing completed
 * @property {number} [processing_duration_seconds] - Processing duration in seconds
 * @property {IngestionProgress} [progress] - Progress information
 * @property {string} [error_message] - Error message if failed
 * @property {Object} [error_details] - Detailed error information
 * @property {ProcessingStats} [processing_stats] - Detailed processing statistics (completed jobs only)
 * @property {string} [owner] - Owner of the job
 */

/**
 * @typedef {Object} IngestionJobListResponse
 * @property {number} total - Total number of jobs
 * @property {IngestionJob[]} items - Array of ingestion jobs
 * @property {number} limit - Max items returned
 * @property {number} offset - Items skipped
 * @property {boolean} has_more - Whether more items exist
 */

/**
 * @typedef {Object} IngestionStatusSummary
 * @property {number} collection_id - Collection ID
 * @property {string} [collection_name] - Collection name
 * @property {number} total_jobs - Total number of jobs
 * @property {Object<string, number>} by_status - Count of jobs by status
 * @property {number} currently_processing - Number of currently processing jobs
 * @property {Array<Object>} recent_failures - Recent failed jobs
 * @property {Object} [oldest_processing_job] - Oldest job still processing
 */

/**
 * List ingestion jobs for a knowledge base with filtering and pagination.
 * 
 * @param {string} kbId - The ID of the knowledge base
 * @param {Object} [options] - Query options
 * @param {string} [options.status] - Filter by status (pending, processing, completed, failed, cancelled)
 * @param {number} [options.limit=50] - Max items to return (1-200)
 * @param {number} [options.offset=0] - Items to skip for pagination
 * @param {string} [options.sort_by='created_at'] - Field to sort by
 * @param {string} [options.sort_order='desc'] - Sort order (asc, desc)
 * @returns {Promise<IngestionJobListResponse>} List of ingestion jobs
 * @throws {Error} If the request fails or the user is not authenticated
 */
export async function listIngestionJobs(kbId, options = {}) {
    if (!browser) {
        throw new Error('Knowledge base operations are only available in the browser.');
    }

    const token = localStorage.getItem('userToken');
    if (!token) {
        throw new Error('User not authenticated.');
    }

    const { status, limit = 50, offset = 0, sort_by = 'created_at', sort_order = 'desc' } = options;
    
    const params = new URLSearchParams({
        limit: limit.toString(),
        offset: offset.toString(),
        sort_by,
        sort_order
    });
    if (status) {
        params.append('status', status);
    }

    const url = getApiUrl(`/knowledgebases/kb/${kbId}/ingestion-jobs?${params.toString()}`);
    console.log(`Listing ingestion jobs from: ${url}`);

    try {
        const response = await axios.get(url, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        console.log('Ingestion jobs response:', response.data);
        
        if (response.data?.status === 'error' && response.data?.kb_server_available === false) {
            throw new Error('Knowledge Base server offline. Please try again later.');
        }
        
        return response.data;
    } catch (error) {
        console.error('Error listing ingestion jobs:', error);
        
        let errorMessage = 'Failed to list ingestion jobs.';
        if (axios.isAxiosError(error)) {
            if (error.response?.data?.kb_server_available === false) {
                errorMessage = 'Knowledge Base server offline. Please try again later.';
            } else if (error.response) {
                errorMessage = error.response.data?.detail || error.response.data?.message || 
                             `Request failed with status ${error.response.status}`;
            }
        } else if (error instanceof Error) {
            errorMessage = error.message;
        }
        
        throw new Error(errorMessage);
    }
}

/**
 * Get status of a specific ingestion job. Use this for polling progress.
 * 
 * @param {string} kbId - The ID of the knowledge base
 * @param {number} jobId - The ID of the ingestion job
 * @returns {Promise<IngestionJob>} The ingestion job status
 * @throws {Error} If the request fails or the user is not authenticated
 */
export async function getIngestionJobStatus(kbId, jobId) {
    if (!browser) {
        throw new Error('Knowledge base operations are only available in the browser.');
    }

    const token = localStorage.getItem('userToken');
    if (!token) {
        throw new Error('User not authenticated.');
    }

    const url = getApiUrl(`/knowledgebases/kb/${kbId}/ingestion-jobs/${jobId}`);
    console.log(`Getting ingestion job status from: ${url}`);

    try {
        const response = await axios.get(url, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        console.log('Ingestion job status response:', response.data);
        
        if (response.data?.status === 'error' && response.data?.kb_server_available === false) {
            throw new Error('Knowledge Base server offline. Please try again later.');
        }
        
        return response.data;
    } catch (error) {
        console.error('Error getting ingestion job status:', error);
        
        let errorMessage = 'Failed to get ingestion job status.';
        if (axios.isAxiosError(error)) {
            if (error.response?.status === 404) {
                errorMessage = 'Ingestion job not found.';
            } else if (error.response?.data?.kb_server_available === false) {
                errorMessage = 'Knowledge Base server offline. Please try again later.';
            } else if (error.response) {
                errorMessage = error.response.data?.detail || error.response.data?.message || 
                             `Request failed with status ${error.response.status}`;
            }
        } else if (error instanceof Error) {
            errorMessage = error.message;
        }
        
        throw new Error(errorMessage);
    }
}

/**
 * Get a summary of all ingestion jobs for a knowledge base.
 * 
 * @param {string} kbId - The ID of the knowledge base
 * @returns {Promise<IngestionStatusSummary>} Summary of ingestion job statuses
 * @throws {Error} If the request fails or the user is not authenticated
 */
export async function getIngestionStatusSummary(kbId) {
    if (!browser) {
        throw new Error('Knowledge base operations are only available in the browser.');
    }

    const token = localStorage.getItem('userToken');
    if (!token) {
        throw new Error('User not authenticated.');
    }

    const url = getApiUrl(`/knowledgebases/kb/${kbId}/ingestion-status`);
    console.log(`Getting ingestion status summary from: ${url}`);

    try {
        const response = await axios.get(url, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        console.log('Ingestion status summary response:', response.data);
        
        if (response.data?.status === 'error' && response.data?.kb_server_available === false) {
            throw new Error('Knowledge Base server offline. Please try again later.');
        }
        
        return response.data;
    } catch (error) {
        console.error('Error getting ingestion status summary:', error);
        
        let errorMessage = 'Failed to get ingestion status summary.';
        if (axios.isAxiosError(error)) {
            if (error.response?.data?.kb_server_available === false) {
                errorMessage = 'Knowledge Base server offline. Please try again later.';
            } else if (error.response) {
                errorMessage = error.response.data?.detail || error.response.data?.message || 
                             `Request failed with status ${error.response.status}`;
            }
        } else if (error instanceof Error) {
            errorMessage = error.message;
        }
        
        throw new Error(errorMessage);
    }
}

/**
 * Retry a failed ingestion job.
 * 
 * @param {string} kbId - The ID of the knowledge base
 * @param {number} jobId - The ID of the ingestion job
 * @param {Object} [overrideParams] - Optional parameters to override the original
 * @returns {Promise<IngestionJob>} The updated ingestion job
 * @throws {Error} If the request fails, job can't be retried, or user is not authenticated
 */
export async function retryIngestionJob(kbId, jobId, overrideParams = null) {
    if (!browser) {
        throw new Error('Knowledge base operations are only available in the browser.');
    }

    const token = localStorage.getItem('userToken');
    if (!token) {
        throw new Error('User not authenticated.');
    }

    const url = getApiUrl(`/knowledgebases/kb/${kbId}/ingestion-jobs/${jobId}/retry`);
    console.log(`Retrying ingestion job at: ${url}`);

    const body = overrideParams ? { override_params: overrideParams } : {};

    try {
        const response = await axios.post(url, body, {
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });

        console.log('Retry ingestion job response:', response.data);
        
        if (response.data?.status === 'error' && response.data?.kb_server_available === false) {
            throw new Error('Knowledge Base server offline. Please try again later.');
        }
        
        return response.data;
    } catch (error) {
        console.error('Error retrying ingestion job:', error);
        
        let errorMessage = 'Failed to retry ingestion job.';
        if (axios.isAxiosError(error)) {
            if (error.response?.status === 400) {
                errorMessage = 'Only failed jobs can be retried.';
            } else if (error.response?.status === 403) {
                errorMessage = 'You are not authorized to retry this job.';
            } else if (error.response?.status === 404) {
                errorMessage = 'Ingestion job not found.';
            } else if (error.response?.data?.kb_server_available === false) {
                errorMessage = 'Knowledge Base server offline. Please try again later.';
            } else if (error.response) {
                errorMessage = error.response.data?.detail || error.response.data?.message || 
                             `Request failed with status ${error.response.status}`;
            }
        } else if (error instanceof Error) {
            errorMessage = error.message;
        }
        
        throw new Error(errorMessage);
    }
}

/**
 * Cancel a pending or processing ingestion job.
 * 
 * @param {string} kbId - The ID of the knowledge base
 * @param {number} jobId - The ID of the ingestion job
 * @returns {Promise<IngestionJob>} The updated ingestion job
 * @throws {Error} If the request fails, job can't be cancelled, or user is not authenticated
 */
export async function cancelIngestionJob(kbId, jobId) {
    if (!browser) {
        throw new Error('Knowledge base operations are only available in the browser.');
    }

    const token = localStorage.getItem('userToken');
    if (!token) {
        throw new Error('User not authenticated.');
    }

    const url = getApiUrl(`/knowledgebases/kb/${kbId}/ingestion-jobs/${jobId}/cancel`);
    console.log(`Cancelling ingestion job at: ${url}`);

    try {
        const response = await axios.post(url, {}, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        console.log('Cancel ingestion job response:', response.data);
        
        if (response.data?.status === 'error' && response.data?.kb_server_available === false) {
            throw new Error('Knowledge Base server offline. Please try again later.');
        }
        
        return response.data;
    } catch (error) {
        console.error('Error cancelling ingestion job:', error);
        
        let errorMessage = 'Failed to cancel ingestion job.';
        if (axios.isAxiosError(error)) {
            if (error.response?.status === 400) {
                errorMessage = 'Only pending or processing jobs can be cancelled.';
            } else if (error.response?.status === 403) {
                errorMessage = 'You are not authorized to cancel this job.';
            } else if (error.response?.status === 404) {
                errorMessage = 'Ingestion job not found.';
            } else if (error.response?.data?.kb_server_available === false) {
                errorMessage = 'Knowledge Base server offline. Please try again later.';
            } else if (error.response) {
                errorMessage = error.response.data?.detail || error.response.data?.message || 
                             `Request failed with status ${error.response.status}`;
            }
        } else if (error instanceof Error) {
            errorMessage = error.message;
        }
        
        throw new Error(errorMessage);
    }
}

// --- End Ingestion Status API Methods --- //

/**
 * Toggle KB sharing status
 * @param {string} kbId - The KB ID
 * @param {boolean} isShared - New sharing status
 * @returns {Promise<Object>} Response with updated KB info
 */
export async function toggleKBSharing(kbId, isShared) {
    if (!browser) {
        throw new Error('Knowledge base operations are only available in the browser.');
    }

    const token = localStorage.getItem('userToken');
    if (!token) {
        throw new Error('User not authenticated.');
    }

    const url = getApiUrl(`/knowledgebases/kb/${kbId}/share`);
    console.log(`Toggling KB ${kbId} sharing to ${isShared}`);

    try {
        const response = await axios.put(
            url,
            { is_shared: isShared },
            {
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            }
        );

        console.log('KB sharing toggle response:', response.data);
        return response.data;
    } catch (error) {
        console.error('Error toggling KB sharing:', error);
        
        let errorMessage = 'Failed to toggle sharing status.';
        if (axios.isAxiosError(error)) {
            console.error('Axios Error Response Data:', error.response?.data);
            if (error.response) {
                errorMessage = error.response.data?.detail || error.response.data?.message || 
                             `Request failed with status ${error.response.status}`;
            }
        } else if (error instanceof Error) {
            errorMessage = error.message;
        }
        
        throw new Error(errorMessage);
    }
}
