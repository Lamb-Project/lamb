// Plugin registry for multi-tool assistant components
// This maps tool plugin names to their corresponding Svelte components

import SimpleRagToolConfig from './SimpleRagToolConfig.svelte';
import RubricRagToolConfig from './RubricRagToolConfig.svelte';
import SingleFileRagToolConfig from './SingleFileRagToolConfig.svelte';

/**
 * Registry mapping tool plugin names to their configuration components
 * @type {Object<string, import('svelte').SvelteComponent>}
 */
export const TOOL_PLUGIN_COMPONENTS = {
    'simple_rag': SimpleRagToolConfig,
    'rubric_rag': RubricRagToolConfig,
    'single_file_rag': SingleFileRagToolConfig
};

/**
 * Get the component for a tool plugin
 * @param {string} pluginName - Name of the tool plugin
 * @returns {import('svelte').SvelteComponent|null} The component or null if not found
 */
export function getToolComponent(pluginName) {
    return TOOL_PLUGIN_COMPONENTS[pluginName] || null;
}

/**
 * Check if a tool plugin has a component
 * @param {string} pluginName - Name of the tool plugin
 * @returns {boolean} True if component exists
 */
export function hasToolComponent(pluginName) {
    return pluginName in TOOL_PLUGIN_COMPONENTS;
}

/**
 * Get all available tool components
 * @returns {string[]} Array of tool plugin names that have components
 */
export function getAvailableToolComponents() {
    return Object.keys(TOOL_PLUGIN_COMPONENTS);
}