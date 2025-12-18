import { writable } from 'svelte/store';
import { browser } from '$app/environment';
import { getApiUrl, getConfig } from '$lib/config';
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
			RAG_Top_k: '3',
			rag_placeholders: ['--- {context} --- ', '--- {user_input} ---']
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
		rag_processors: ['no_rag', 'simple_rag', 'context_aware_rag', 'single_file_rag'] // Keep RAG options
	};
	return capabilities;
}

// Restore caching helpers
/**
 * @param {unknown} value
 * @returns {boolean}
 */
function isPlainObject(value) {
	return value !== null && typeof value === 'object' && !Array.isArray(value);
}

async function fetchSystemCapabilities() {
	try {
		const config = getConfig();
		const lambServerBase = config?.api?.lambServer;
		if (!lambServerBase) {
			throw new Error('Lamb server base URL (lambServer) is not configured within config.api.');
		}
		const capabilitiesUrl = `${lambServerBase.replace(/\/$/, '')}/lamb/v1/completions/list`;
		console.log(`assistantConfigStore: Fetching capabilities from: ${capabilitiesUrl}`);

		const token = browser ? localStorage.getItem('userToken') : null;
		const headers = token ? { Authorization: `Bearer ${token}` } : {};

		const capsResponse = await axios.get(capabilitiesUrl, { headers });
		const capabilities = capsResponse.data;
		console.log('Fetched Capabilities (raw):', capabilities);
		return capabilities;
	} catch (error) {
		console.error('Error fetching system capabilities:', error);
		return getFallbackCapabilities();
	}
}

async function fetchStaticDefaults() {
	try {
		const config = getConfig();
		const lambServerBase = config?.api?.lambServer;
		if (!lambServerBase) {
			throw new Error('Lamb server base URL (lambServer) is not configured within config.api.');
		}
		const defaultsUrl = `${lambServerBase.replace(/\/$/, '')}/static/json/defaults.json`;
		console.log(`assistantConfigStore: Fetching defaults from: ${defaultsUrl}`);

		const defaultsResponse = await axios.get(defaultsUrl);
		const payload = defaultsResponse.data;
		console.log('Fetched static defaults:', payload);
		if (isPlainObject(payload?.config)) {
			return { ...payload.config };
		}
		return { ...getFallbackDefaults().config };
	} catch (error) {
		console.error('Error fetching defaults.json:', error);
		return { ...getFallbackDefaults().config };
	}
}

async function fetchOrganizationDefaults() {
	if (!browser) return null;

	const token = localStorage.getItem('userToken');
	if (!token) {
		console.warn(
			'assistantConfigStore: No auth token found; skipping organization defaults fetch.'
		);
		return null;
	}

	try {
		const defaultsUrl = getApiUrl('/assistant/defaults');
		console.log(`assistantConfigStore: Fetching organization defaults from: ${defaultsUrl}`);
		const response = await axios.get(defaultsUrl, {
			headers: { Authorization: `Bearer ${token}` }
		});
		const data = response.data;
		if (isPlainObject(data?.config)) {
			return { ...data.config };
		}
		if (isPlainObject(data)) {
			return { ...data };
		}
		console.warn(
			'assistantConfigStore: Organization defaults response was not an object; ignoring.'
		);
		return null;
	} catch (error) {
		if (axios.isAxiosError?.(error)) {
			if (error.response?.status === 404) {
				console.info('assistantConfigStore: No organization defaults configured yet.');
			} else {
				console.error(
					'Error fetching organization defaults:',
					error.response?.data || error.message
				);
			}
		} else {
			console.error('Error fetching organization defaults:', error);
		}
		return null;
	}
}

/**
 * @param {string} key
 * @returns {any | null}
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
	} catch (error) {
		console.error(`Error reading cache for ${key}:`, error);
	}
	localStorage.removeItem(key);
	return null;
}

/**
 * @param {string} key
 * @param {any} value
 */
function setCachedData(key, value) {
	if (!browser) return;
	try {
		const data = { value, timestamp: Date.now() };
		localStorage.setItem(key, JSON.stringify(data));
	} catch (error) {
		console.error(`Error setting cache for ${key}:`, error);
	}
}

function createAssistantConfigStore() {
	const { subscribe, set, update } = writable(initialState);

	async function loadConfig() {
		console.log('assistantConfigStore: loadConfig called (with caching).');
		if (!browser) {
			console.warn(
				'assistantConfigStore: Running in non-browser context, using fallback configuration.'
			);
			set({
				systemCapabilities: getFallbackCapabilities(),
				configDefaults: getFallbackDefaults(),
				loading: false,
				error: null,
				lastLoadedTimestamp: Date.now()
			});
			return;
		}

		let isLoading = false;
		update((s) => {
			isLoading = s.loading;
			return s;
		});
		if (isLoading) {
			console.log('assistantConfigStore: Config load already in progress...');
			return;
		}

		console.log('assistantConfigStore: Checking cache...');
		let capabilities = getCachedData(CAPABILITIES_CACHE_KEY);
		let cachedDefaults = getCachedData(DEFAULTS_CACHE_KEY);

		if (capabilities || cachedDefaults) {
			set({
				systemCapabilities: capabilities || null,
				configDefaults: cachedDefaults || null,
				loading: true,
				error: null,
				lastLoadedTimestamp: Date.now()
			});
		} else {
			update((s) => ({ ...s, loading: true, error: null }));
		}

		console.log('assistantConfigStore: Fetching latest configuration...');

		try {
			if (!capabilities) {
				capabilities = await fetchSystemCapabilities();
				setCachedData(CAPABILITIES_CACHE_KEY, capabilities);
			}

			const staticConfig = await fetchStaticDefaults();
			const organizationOverrides = await fetchOrganizationDefaults();
			const mergedConfig = {
				...staticConfig,
				...(organizationOverrides || {})
			};
			const defaults = { config: mergedConfig };
			setCachedData(DEFAULTS_CACHE_KEY, defaults);

			set({
				systemCapabilities: capabilities,
				configDefaults: defaults,
				loading: false,
				error: null,
				lastLoadedTimestamp: Date.now()
			});
		} catch (err) {
			console.error('Error in loadConfig process:', err);
			set({
				systemCapabilities: capabilities || getFallbackCapabilities(),
				configDefaults: cachedDefaults || getFallbackDefaults(),
				loading: false,
				error: err instanceof Error ? err.message : 'Failed to load assistant configuration',
				lastLoadedTimestamp: Date.now()
			});
		}
	}

	return {
		subscribe,
		loadConfig,
		reset: () => {
			console.log('assistantConfigStore: Resetting store to initial state.');
			set(initialState);
		},
		clearCache: () => {
			console.log('assistantConfigStore: Clearing cached capabilities and defaults.');
			if (browser) {
				localStorage.removeItem(CAPABILITIES_CACHE_KEY);
				localStorage.removeItem(DEFAULTS_CACHE_KEY);
			}
			set(initialState);
		}
	};
}

export const assistantConfigStore = createAssistantConfigStore();
