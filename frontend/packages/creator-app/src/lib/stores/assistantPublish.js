import { writable } from 'svelte/store';

/** @type {import('svelte/store').Writable<boolean>} */
export const publishModalOpen = writable(false);

/** 
 * @typedef {{ id: string; name: string; }} SelectedAssistantData
 */

/** @type {import('svelte/store').Writable<SelectedAssistantData | null>} */
export const selectedAssistant = writable(null);

/**
 * @typedef {Object} PublishingStatus
 * @property {boolean} loading
 * @property {string | null} error
 * @property {boolean} success
 */

/** @type {import('svelte/store').Writable<PublishingStatus>} */
export const publishingStatus = writable({
    loading: false,
    error: null,
    success: false
});

/** Resets the publishing status store to its initial state. */
export const resetPublishingStatus = () => {
    publishingStatus.set({
        loading: false,
        error: null,
        success: false
    });
};

// Note: API call functions (publishAssistant, unpublishAssistant) are kept in assistantService.js 