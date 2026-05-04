import { writable } from 'svelte/store';
import { browser } from '$app/environment';
import { getAssistants } from '$lib/services/assistantService'; // We'll port this service next
import { user } from './userStore';

/**
 * @typedef {Object} Assistant
 * @property {string} id - The assistant's ID
 * @property {string} name - The assistant's name
 * @property {string} [description] - The assistant's description (optional)
 * @property {string} owner - The owner's email
 * @property {boolean} is_published - Whether the assistant is published
 * @property {string} [published_group_id] - The group ID if published
 * @property {string} [group_name] - The group name if published
 * @property {string} [api_callback] - Deprecated, use metadata instead
 * @property {string} [metadata] - JSON string containing plugin configuration
 * @property {string} [system_prompt] - System prompt (optional)
 * @property {string} [prompt_template] - Prompt template (optional)
 * @property {number} [RAG_Top_k] - RAG Top K value (optional, defaults might apply elsewhere)
 * @property {string} [RAG_collections] - RAG collections string (optional)
 * @property {any} [key] - Allow any other properties (index signature) - Consider removing if not needed
 */

/**
 * @typedef {Object} AssistantsState
 * @property {Array<Assistant>} items - List of assistants
 * @property {boolean} loading - Whether assistants are being loaded
 * @property {string|null} error - Error message if loading failed
 * @property {Date|null} lastLoaded - When assistants were last loaded
 */

/** @type {AssistantsState} */
const initialState = {
	items: [],
	loading: false,
	error: null,
	lastLoaded: null
};

/**
 * Creates a store for managing assistants.
 * The returned object includes the Svelte store methods (subscribe, set, update)
 * plus custom methods loadAssistants, reset, and destroy.
 */
const createAssistantsStore = () => {
	// Create the writable store with initial state and explicit type
	const { subscribe, set, update } = writable(initialState);

	// Initialize user subscription to handle login/logout
	/** @type {() => void | undefined} */
	let unsubscribe;
	if (browser) {
		unsubscribe = user.subscribe((userData) => {
			if (!userData.isLoggedIn) {
				// Clear assistants when user logs out
				set(initialState); // Reset to initial state
			}
		});
	}

	return {
		subscribe,
		set, // Expose set if needed directly
		update, // Expose update if needed directly

		/**
		 * Load assistants from the backend
		 * @returns {Promise<void>}
		 */
		loadAssistants: async () => {
			// Only run in browser
			if (!browser) return;

			// Update store to loading state
			update((state) => ({
				...state,
				loading: true,
				error: null
			}));

			try {
				// Fetch fresh data from the backend
				// getAssistants returns an object: { assistants: Assistant[], total_count: number }
				const response = await getAssistants();

				// Update store with new data - extract the array
				set({
					items: response.assistants, // Assign the array to items
					loading: false,
					error: null,
					lastLoaded: new Date()
				});

				// Log the length of the assistants array
				console.log(
					'Assistants store updated with fresh data:',
					response.assistants?.length || 0,
					'items'
				);
			} catch (error) {
				console.error('Error loading assistants:', error);
				let message = 'Failed to load assistants';
				if (error instanceof Error) {
					message = error.message;
				}
				// Update store with error
				update((state) => ({
					...state,
					loading: false,
					error: message
				}));
			}
		},

		/**
		 * Reset the store to its initial state
		 */
		reset: () => {
			set(initialState); // Reset to initial state
		},

		/**
		 * Clean up any subscriptions
		 */
		destroy: () => {
			if (unsubscribe) unsubscribe();
		}
	};
};

// Create and export the store
export const assistants = createAssistantsStore();
