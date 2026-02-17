/**
 * API Client - Centralized fetch wrapper with automatic session guard
 * 
 * Provides an authenticated fetch that:
 * 1. Automatically adds the Authorization header
 * 2. Inspects every response for "Account disabled" signals
 * 3. Forces logout if account is disabled
 * 
 * Usage:
 *   import { authenticatedFetch } from '$lib/utils/apiClient';
 *   const response = await authenticatedFetch('/creator/assistant/get_assistants');
 */

import { browser } from '$app/environment';
import { get } from 'svelte/store';
import { user } from '$lib/stores/userStore';
import { goto } from '$app/navigation';
import { base } from '$app/paths';
import { handleApiResponse } from './sessionGuard';

/**
 * Get the authentication token from the user store
 * @returns {string|null} The token or null if not found
 */
function getAuthToken() {
	if (!browser) return null;
	const currentUser = get(user);
	return currentUser?.token || null;
}

/**
 * Authenticated fetch wrapper that automatically:
 * - Adds Authorization header
 * - Detects disabled accounts and forces logout
 * 
 * @param {string} url - The URL to fetch
 * @param {RequestInit} [options={}] - Fetch options
 * @returns {Promise<Response>} The fetch response
 * 
 * @example
 * const response = await authenticatedFetch('/creator/assistant/get_assistants');
 * if (response.ok) {
 *   const data = await response.json();
 * }
 */
export async function authenticatedFetch(url, options = {}) {
	const token = getAuthToken();
	
	if (!token) {
		throw new Error('No authentication token available');
	}

	// Build default headers
	const defaultHeaders = {
		'Authorization': `Bearer ${token}`
	};

	// Only set Content-Type for non-FormData requests
	// FormData needs the browser to auto-generate the multipart boundary
	if (!(options.body instanceof FormData)) {
		defaultHeaders['Content-Type'] = 'application/json';
	}

	// Merge default options with provided options
	const defaultOptions = {
		headers: defaultHeaders
	};

	// Deep merge headers
	const mergedOptions = {
		...defaultOptions,
		...options,
		headers: {
			...defaultOptions.headers,
			...(options.headers || {})
		}
	};

	// Make the request
	const response = await fetch(url, mergedOptions);

	// Check for disabled account and force logout if detected
	// This happens BEFORE the caller processes the response
	await handleApiResponse(response);

	return response;
}

/**
 * Authenticated fetch that also parses JSON automatically
 * Throws if response is not ok
 * 
 * @param {string} url - The URL to fetch
 * @param {RequestInit} [options={}] - Fetch options
 * @returns {Promise<any>} The parsed JSON response
 * 
 * @example
 * try {
 *   const data = await authenticatedFetchJson('/creator/assistant/get_assistants');
 *   console.log(data.assistants);
 * } catch (error) {
 *   console.error('Failed to fetch:', error);
 * }
 */
export async function authenticatedFetchJson(url, options = {}) {
	const response = await authenticatedFetch(url, options);
	
	if (!response.ok) {
		const errorText = await response.text();
		let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
		
		try {
			const errorJson = JSON.parse(errorText);
			errorMessage = errorJson.detail || errorJson.message || errorMessage;
		} catch {
			// Not JSON, use text
			if (errorText) errorMessage = errorText;
		}
		
		throw new Error(errorMessage);
	}
	
	return await response.json();
}
