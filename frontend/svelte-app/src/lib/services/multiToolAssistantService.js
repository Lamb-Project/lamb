// Multi-tool assistant service for handling multi-tool specific API calls
import { getApiUrl, getConfig } from '$lib/config';
import { browser } from '$app/environment';
import axios from 'axios';

/**
 * @typedef {Object} MultiToolAssistant
 * @property {number} id
 * @property {string} name
 * @property {string} [description]
 * @property {string} [owner]
 * @property {boolean} [published]
 * @property {string} [system_prompt]
 * @property {string} [prompt_template]
 * @property {string} [metadata] - JSON string containing multi-tool configuration
 * @property {string} [group_id]
 * @property {string} [group_name]
 * @property {string} [oauth_consumer_name]
 * @property {number} [published_at]
 */

/**
 * @typedef {Object} ToolConfig
 * @property {string} plugin - Tool plugin name (e.g., "simple_rag")
 * @property {string} placeholder - Placeholder this tool fills (e.g., "1_context")
 * @property {boolean} [enabled] - Whether to execute (default: true)
 * @property {Object} [config] - Tool-specific configuration
 */

/**
 * @typedef {Object} MultiToolMetadata
 * @property {string} assistant_type - Should be "multi_tool"
 * @property {string} [orchestrator] - Orchestrator strategy ("sequential", "parallel")
 * @property {string} [connector] - LLM connector
 * @property {string} [llm] - LLM model
 * @property {boolean} [verbose] - Enable verbose reporting
 * @property {ToolConfig[]} tools - Array of tool configurations
 */

/**
 * Helper function to check browser environment and authentication
 * @returns {string} The token
 * @throws {Error} If not in browser or not authenticated
 */
function checkBrowserAndAuth() {
    if (!browser) {
        throw new Error('This operation is only available in the browser');
    }

    const token = localStorage.getItem('userToken');
    if (!token) {
        throw new Error('Please log in to continue');
    }

    return token;
}

/**
 * Create a new multi-tool assistant
 * @param {Object} assistantData - Assistant data
 * @param {string} assistantData.name - Assistant name
 * @param {string} [assistantData.description] - Assistant description
 * @param {string} [assistantData.system_prompt] - System prompt
 * @param {string} [assistantData.prompt_template] - Prompt template
 * @param {string} [assistantData.orchestrator] - Orchestrator strategy
 * @param {string} [assistantData.connector] - LLM connector
 * @param {string} [assistantData.llm] - LLM model
 * @param {boolean} [assistantData.verbose] - Enable verbose reporting
 * @param {ToolConfig[]} assistantData.tools - Tool configurations
 * @returns {Promise<MultiToolAssistant>} Created assistant
 * @throws {Error} If creation fails
 */
export async function createMultiToolAssistant(assistantData) {
    const token = checkBrowserAndAuth();

    // Build metadata object
    const metadata = {
        assistant_type: "multi_tool",
        orchestrator: assistantData.orchestrator || "sequential",
        connector: assistantData.connector || "openai",
        llm: assistantData.llm || "gpt-4o-mini",
        verbose: assistantData.verbose || false,
        tools: assistantData.tools || []
    };

    // Prepare request payload
    const payload = {
        name: assistantData.name,
        description: assistantData.description || "",
        system_prompt: assistantData.system_prompt || "",
        prompt_template: assistantData.prompt_template || "",
        metadata: JSON.stringify(metadata)
    };

    try {
        const apiUrl = getApiUrl('lamb');
        const response = await axios.post(`${apiUrl}/creator/assistant/create_assistant`, payload, {
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });

        return response.data;
    } catch (error) {
        console.error('Error creating multi-tool assistant:', error);
        if (error.response) {
            throw new Error(`Failed to create assistant: ${error.response.data.detail || error.response.statusText}`);
        } else {
            throw new Error('Failed to create assistant: Network error');
        }
    }
}

/**
 * Update an existing multi-tool assistant
 * @param {number} assistantId - Assistant ID
 * @param {Object} assistantData - Updated assistant data
 * @returns {Promise<MultiToolAssistant>} Updated assistant
 * @throws {Error} If update fails
 */
export async function updateMultiToolAssistant(assistantId, assistantData) {
    const token = checkBrowserAndAuth();

    // Build metadata object
    const metadata = {
        assistant_type: "multi_tool",
        orchestrator: assistantData.orchestrator || "sequential",
        connector: assistantData.connector || "openai",
        llm: assistantData.llm || "gpt-4o-mini",
        verbose: assistantData.verbose || false,
        tools: assistantData.tools || []
    };

    // Prepare request payload
    const payload = {
        name: assistantData.name,
        description: assistantData.description || "",
        system_prompt: assistantData.system_prompt || "",
        prompt_template: assistantData.prompt_template || "",
        metadata: JSON.stringify(metadata)
    };

    try {
        const apiUrl = getApiUrl('lamb');
        const response = await axios.put(`${apiUrl}/creator/assistant/update_assistant/${assistantId}`, payload, {
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });

        return response.data;
    } catch (error) {
        console.error('Error updating multi-tool assistant:', error);
        if (error.response) {
            throw new Error(`Failed to update assistant: ${error.response.data.detail || error.response.statusText}`);
        } else {
            throw new Error('Failed to update assistant: Network error');
        }
    }
}

/**
 * Parse multi-tool metadata from assistant object
 * @param {MultiToolAssistant} assistant - Assistant object
 * @returns {MultiToolMetadata} Parsed metadata
 */
export function parseMultiToolMetadata(assistant) {
    try {
        if (!assistant.metadata) {
            return {
                assistant_type: "multi_tool",
                orchestrator: "sequential",
                connector: "openai",
                llm: "gpt-4o-mini",
                verbose: false,
                tools: []
            };
        }

        const metadata = typeof assistant.metadata === 'string'
            ? JSON.parse(assistant.metadata)
            : assistant.metadata;

        return {
            assistant_type: metadata.assistant_type || "multi_tool",
            orchestrator: metadata.orchestrator || "sequential",
            connector: metadata.connector || "openai",
            llm: metadata.llm || "gpt-4o-mini",
            verbose: metadata.verbose || false,
            tools: metadata.tools || []
        };
    } catch (error) {
        console.error('Error parsing multi-tool metadata:', error);
        return {
            assistant_type: "multi_tool",
            orchestrator: "sequential",
            connector: "openai",
            llm: "gpt-4o-mini",
            verbose: false,
            tools: []
        };
    }
}

/**
 * Validate multi-tool configuration
 * @param {MultiToolMetadata} metadata - Metadata to validate
 * @returns {string[]} Array of validation errors (empty if valid)
 */
export function validateMultiToolConfig(metadata) {
    const errors = [];

    if (!metadata.tools || !Array.isArray(metadata.tools)) {
        errors.push("Tools configuration is required");
        return errors;
    }

    if (metadata.tools.length === 0) {
        errors.push("At least one tool must be configured");
    }

    // Check for duplicate placeholders
    const placeholders = new Set();
    metadata.tools.forEach((tool, index) => {
        if (!tool.plugin) {
            errors.push(`Tool ${index + 1}: plugin is required`);
        }
        if (!tool.placeholder) {
            errors.push(`Tool ${index + 1}: placeholder is required`);
        } else if (placeholders.has(tool.placeholder)) {
            errors.push(`Tool ${index + 1}: duplicate placeholder "${tool.placeholder}"`);
        } else {
            placeholders.add(tool.placeholder);
        }
    });

    return errors;
}

/**
 * Get available tools from the backend
 * @returns {Promise<Array>} Array of available tool definitions
 */
export async function getAvailableTools() {
    try {
        const apiUrl = getConfig().api.lambServer || 'http://localhost:9099';
        const token = checkBrowserAndAuth();

        const response = await axios.get(`${apiUrl}/lamb/v1/completions/tools`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        return response.data.tools || [];
    } catch (error) {
        console.error('Error fetching available tools:', error);
        return [];
    }
}

/**
 * Get available orchestrators from the backend
 * @returns {Promise<Array>} Array of available orchestrator definitions
 */
export async function getAvailableOrchestrators() {
    try {
        const apiUrl = getConfig().api.lambServer || 'http://localhost:9099';
        const token = checkBrowserAndAuth();

        const response = await axios.get(`${apiUrl}/lamb/v1/completions/orchestrators`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        return response.data.orchestrators || [];
    } catch (error) {
        console.error('Error fetching available orchestrators:', error);
        return [];
    }
}