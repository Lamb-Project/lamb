import { writable } from 'svelte/store';
import { browser } from '$app/environment';

/**
 * @typedef {Object} ToolConfig
 * @property {string} plugin - Tool plugin name (e.g., "simple_rag")
 * @property {string} placeholder - Placeholder this tool fills (e.g., "1_context")
 * @property {boolean} [enabled] - Whether to execute (default: true)
 * @property {Object} [config] - Tool-specific configuration
 */

/**
 * @typedef {Object} MultiToolAssistantState
 * @property {string} name - Assistant name
 * @property {string} description - Assistant description
 * @property {string} system_prompt - System prompt
 * @property {string} prompt_template - Prompt template
 * @property {string} orchestrator - Orchestrator strategy ("sequential", "parallel")
 * @property {string} connector - LLM connector
 * @property {string} llm - LLM model
 * @property {boolean} verbose - Enable verbose reporting
 * @property {ToolConfig[]} tools - Tool configurations
 * @property {Object[]} availableTools - Available tool definitions from backend
 * @property {Object[]} availableOrchestrators - Available orchestrator definitions from backend
 * @property {boolean} loading - Loading state
 * @property {string|null} error - Error message
 * @property {boolean} saving - Saving state
 */

// Initial state
const initialState = {
    name: '',
    description: '',
    system_prompt: '',
    prompt_template: '',
    orchestrator: 'sequential',
    connector: 'openai',
    llm: 'gpt-4o-mini',
    verbose: false,
    tools: [],
    availableTools: [],
    availableOrchestrators: [],
    loading: false,
    error: null,
    saving: false
};

// Create the store
const multiToolStore = writable(initialState);

// Helper functions for state management
const multiToolStoreActions = {
    /**
     * Reset the store to initial state
     */
    reset: () => {
        multiToolStore.set({ ...initialState });
    },

    /**
     * Update a single field
     * @param {string} field - Field name
     * @param {any} value - Field value
     */
    updateField: (field, value) => {
        multiToolStore.update(state => ({
            ...state,
            [field]: value
        }));
    },

    /**
     * Load data from an existing assistant
     * @param {Object} assistant - Assistant data
     */
    loadFromAssistant: (assistant) => {
        try {
            const metadata = assistant.metadata ? JSON.parse(assistant.metadata) : {};

            multiToolStore.update(state => ({
                ...state,
                name: assistant.name || '',
                description: assistant.description || '',
                system_prompt: assistant.system_prompt || '',
                prompt_template: assistant.prompt_template || '',
                orchestrator: metadata.orchestrator || 'sequential',
                connector: metadata.connector || 'openai',
                llm: metadata.llm || 'gpt-4o-mini',
                verbose: metadata.verbose || false,
                tools: metadata.tools || []
            }));
        } catch (error) {
            console.error('Error loading assistant data into store:', error);
            multiToolStore.update(state => ({
                ...state,
                error: 'Failed to load assistant data'
            }));
        }
    },

    /**
     * Add a new tool to the pipeline
     * @param {string} pluginName - Tool plugin name
     */
    addTool: (pluginName) => {
        multiToolStore.update(state => {
            // Find the tool definition
            const toolDef = state.availableTools.find(t => t.name === pluginName);
            if (!toolDef) {
                console.error(`Tool definition not found: ${pluginName}`);
                return state;
            }

            // Generate placeholder (next number for this tool type)
            const toolType = toolDef.placeholder; // e.g., "context" for simple_rag
            const existingNumbers = state.tools
                .filter(t => t.placeholder.endsWith(`_${toolType}`))
                .map(t => {
                    const match = t.placeholder.match(/^(\d+)_/);
                    return match ? parseInt(match[1]) : 0;
                });

            const nextNumber = existingNumbers.length > 0 ? Math.max(...existingNumbers) + 1 : 1;
            const placeholder = `${nextNumber}_${toolType}`;

            // Create new tool config
            const newTool = {
                plugin: pluginName,
                placeholder: placeholder,
                enabled: true,
                config: {}
            };

            return {
                ...state,
                tools: [...state.tools, newTool]
            };
        });
    },

    /**
     * Remove a tool from the pipeline
     * @param {number} index - Tool index
     */
    removeTool: (index) => {
        multiToolStore.update(state => ({
            ...state,
            tools: state.tools.filter((_, i) => i !== index)
        }));
    },

    /**
     * Update a tool configuration
     * @param {number} index - Tool index
     * @param {Object} updates - Updates to apply
     */
    updateTool: (index, updates) => {
        multiToolStore.update(state => ({
            ...state,
            tools: state.tools.map((tool, i) =>
                i === index ? { ...tool, ...updates } : tool
            )
        }));
    },

    /**
     * Reorder tools in the pipeline
     * @param {number} fromIndex - Source index
     * @param {number} toIndex - Target index
     */
    reorderTools: (fromIndex, toIndex) => {
        multiToolStore.update(state => {
            const tools = [...state.tools];
            const [moved] = tools.splice(fromIndex, 1);
            tools.splice(toIndex, 0, moved);

            // Renumber placeholders after reordering
            const renumberedTools = tools.map((tool, index) => {
                const toolDef = state.availableTools.find(t => t.name === tool.plugin);
                if (toolDef) {
                    const toolType = toolDef.placeholder;
                    const newPlaceholder = `${index + 1}_${toolType}`;
                    return { ...tool, placeholder: newPlaceholder };
                }
                return tool;
            });

            return {
                ...state,
                tools: renumberedTools
            };
        });
    },

    /**
     * Set available tools from backend
     * @param {Array} tools - Available tools
     */
    setAvailableTools: (tools) => {
        multiToolStore.update(state => ({
            ...state,
            availableTools: tools
        }));
    },

    /**
     * Set available orchestrators from backend
     * @param {Array} orchestrators - Available orchestrators
     */
    setAvailableOrchestrators: (orchestrators) => {
        multiToolStore.update(state => ({
            ...state,
            availableOrchestrators: orchestrators
        }));
    },

    /**
     * Set loading state
     * @param {boolean} loading - Loading state
     */
    setLoading: (loading) => {
        multiToolStore.update(state => ({
            ...state,
            loading
        }));
    },

    /**
     * Set saving state
     * @param {boolean} saving - Saving state
     */
    setSaving: (saving) => {
        multiToolStore.update(state => ({
            ...state,
            saving
        }));
    },

    /**
     * Set error message
     * @param {string|null} error - Error message
     */
    setError: (error) => {
        multiToolStore.update(state => ({
            ...state,
            error
        }));
    },

    /**
     * Clear error message
     */
    clearError: () => {
        multiToolStore.update(state => ({
            ...state,
            error: null
        }));
    }
};

// Export the store and actions
export { multiToolStoreActions };

// Export the store for direct access
export default multiToolStore;