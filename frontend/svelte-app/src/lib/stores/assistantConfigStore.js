import { writable } from 'svelte/store';
import { browser } from '$app/environment';
import { getApiUrl, getConfig } from '$lib/config'; // Import getConfig
import axios from 'axios';

/**
 * @typedef {Object} SystemCapabilities
 * @property {string[]} [prompt_processors]
 * @property {Object.<string, any>} [connectors]
 * @property {string[]} [rag_processors]
 */

/**
 * @typedef {Object} ConfigDefaults
 * @property {{system_prompt?: string, prompt_template?: string, prompt_processor?: string, connector?: string, llm?: string, rag_processor?: string, RAG_Top_k?: string}} [config]
 */

/**
 * @typedef {Object} AssistantConfigState
 * @property {SystemCapabilities | null} systemCapabilities
 * @property {ConfigDefaults | null} configDefaults
 * @property {boolean} loading
 * @property {string | null} error
 * @property {number | null} lastLoadedTimestamp // Restore timestamp
 */

// Restore cache constants
const CAPABILITIES_CACHE_KEY = 'lamb_assistant_capabilities';
const DEFAULTS_CACHE_KEY = 'lamb_assistant_defaults';
const CACHE_DURATION_MS = 60 * 60 * 1000; // Cache for 1 hour

/** @type {AssistantConfigState} */
const initialState = {
	systemCapabilities: null,
	configDefaults: null,
	loading: false,
	error: null,
	lastLoadedTimestamp: null // Restore timestamp
};

// Helper to get fallback defaults matching legacy code
/** @returns {ConfigDefaults} */
function getFallbackDefaults() {
	console.warn('Using hardcoded fallback defaults');
	// Ensure the structure matches ConfigDefaults type
	const defaults = {
		config: {
			// Correctly nested under 'config' key
			// "lamb_helper_assistant": "lamb_assistant.1", // Remove non-defined property
			system_prompt:
				'You are a wise surfer dude and a helpful teaching assistant that uses Retrieval-Augmented Generation (RAG) to improve your answers.',
			prompt_template:
				'You are a wise surfer dude and a helpful teaching assistant that uses Retrieval-Augmented Generation (RAG) to improve your answers.\nThis is the user input: {user_input}\nThis is the context: {context}\nNow answer the question:',
			prompt_processor: 'simple_augment',
			connector: 'openai',
			llm: 'gpt-4o-mini',
			rag_processor: 'no_rag', // Use consistent key format
			RAG_Top_k: '3'
		}
	};
	// Cast to the defined type to help type checker
	return /** @type {ConfigDefaults} */ (defaults);
}

// Helper to get fallback capabilities matching legacy code
/** @returns {SystemCapabilities} */
function getFallbackCapabilities() {
	console.warn('Using hardcoded fallback capabilities');
	/** @type {SystemCapabilities} */
	const capabilities = {
		prompt_processors: ['simple_augment'], // Keep simple_augment as fallback, zero_shot removed
		connectors: { openai: { models: ['gpt-4o-mini', 'gpt-4'] } }, // Keep basic connector/model fallback
		rag_processors: ['no_rag', 'simple_rag', 'single_file_rag'] // Keep RAG options
	};
	return capabilities;
}

// Restore caching helpers
/**
 * @param {string} key The cache key
 * @returns {any | null} The cached data or null
 */
function getCachedData(key) {
	if (!browser) return null;
	const item = localStorage.getItem(key);
	if (!item) return null;
	try {
		const data = JSON.parse(item);
		if (Date.now() - data.timestamp < CACHE_DURATION_MS) {
			return data.value;
		}
	} catch (e) {
		console.error(`Error reading cache for ${key}:`, e);
	}
	localStorage.removeItem(key); // Remove invalid/expired cache
	return null;
}

/**
 * @param {string} key The cache key
 * @param {any} value The data to cache
 */
function setCachedData(key, value) {
	if (!browser) return;
	try {
		const data = { value, timestamp: Date.now() };
		localStorage.setItem(key, JSON.stringify(data));
	} catch (e) {
		console.error(`Error setting cache for ${key}:`, e);
	}
}

// --- Create Store ---
function createAssistantConfigStore() {
	const { subscribe, set, update } = writable(initialState);

	async function loadConfig() {
		console.log('assistantConfigStore: loadConfig called (with caching).');
		let isLoading = false;
		update((s) => {
			isLoading = s.loading;
			return s;
		});
		if (isLoading) {
			console.log('assistantConfigStore: Config load already in progress...');
			return;
		}

		// Try loading from cache first
		console.log('assistantConfigStore: Checking cache...');
		let capabilities = getCachedData(CAPABILITIES_CACHE_KEY);
		let defaults = getCachedData(DEFAULTS_CACHE_KEY);

		if (capabilities && defaults) {
			console.log('assistantConfigStore: Config loaded from cache.');
			set({
				systemCapabilities: capabilities,
				configDefaults: defaults,
				loading: false,
				error: null,
				lastLoadedTimestamp: Date.now() // Mark as loaded from cache
			});
			return; // Exit early
		}

		// If cache miss or expired, proceed to fetch
		update((s) => ({ ...s, loading: true, error: null })); // Keep existing data while loading? Or clear?
		// Let's clear for simplicity on fetch, use initialState base.
		update((s) => ({
			...initialState,
			loading: true,
			systemCapabilities: capabilities,
			configDefaults: defaults
		})); // Keep cached item if only one expired

		console.log('assistantConfigStore: Cache miss or expired. Fetching fresh config...');
		// Fetch logic remains the same, but now we re-assign to capabilities/defaults
		try {
			// Fetch Capabilities (only if not loaded from cache)
			if (!capabilities) {
				try {
					const config = getConfig();
					const lambServerBase = config?.api?.lambServer;
					if (!lambServerBase) {
						throw new Error(
							'Lamb server base URL (lambServer) is not configured within config.api.'
						);
					}
					const capabilitiesUrl = `${lambServerBase.replace(/\/$/, '')}/lamb/v1/completions/list`;
					console.log(`assistantConfigStore: Fetching capabilities from: ${capabilitiesUrl}`);
					const capsResponse = await axios.get(capabilitiesUrl);
					capabilities = capsResponse.data; // Assign fetched data
					console.log('Fetched Capabilities (raw):', capabilities);
					setCachedData(CAPABILITIES_CACHE_KEY, capabilities); // Save to cache
				} catch (capError) {
					console.error('Error fetching system capabilities:', capError);
					capabilities = getFallbackCapabilities(); // Use fallback on error
				}
			}

			// Fetch Defaults (only if not loaded from cache)
			if (!defaults) {
				try {
					const config = getConfig();
					const lambServerBase = config?.api?.lambServer;
					if (!lambServerBase) {
						throw new Error(
							'Lamb server base URL (lambServer) is not configured within config.api.'
						);
					}
					const defaultsUrl = `${lambServerBase.replace(/\/$/, '')}/static/json/defaults.json`;
					console.log(`assistantConfigStore: Fetching defaults from: ${defaultsUrl}`);
					const defaultsResponse = await axios.get(defaultsUrl);
					defaults = defaultsResponse.data; // Assign fetched data
					console.log('Fetched Defaults:', defaults);
					setCachedData(DEFAULTS_CACHE_KEY, defaults); // Save to cache
				} catch (defError) {
					console.error('Error fetching defaults.json:', defError);
					defaults = getFallbackDefaults(); // Use fallback on error
				}
			}

			// Final update to store after fetches (or cache load)
			set({
				systemCapabilities: capabilities,
				configDefaults: defaults,
				loading: false,
				error: null,
				lastLoadedTimestamp: Date.now() // Set timestamp after successful load/fetch
			});
		} catch (err) {
			console.error('Error in loadConfig process:', err);
			update((s) => ({
				...s,
				systemCapabilities: s.systemCapabilities || getFallbackCapabilities(), // Keep existing or use fallback
				configDefaults: s.configDefaults || getFallbackDefaults(), // Keep existing or use fallback
				loading: false,
				error: err instanceof Error ? err.message : 'Failed to load assistant configuration'
				// Don't update timestamp on error
			}));
		}
	}

	return {
		subscribe, // Use original subscribe
		loadConfig,
		reset: () => {
			console.log('assistantConfigStore: Resetting store to initial state.');
			set(initialState); // Resets timestamp as well
		}
	};
}

export const assistantConfigStore = createAssistantConfigStore();
