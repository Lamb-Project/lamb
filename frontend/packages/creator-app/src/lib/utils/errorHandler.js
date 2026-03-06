/**
 * Standardized error handling utilities for the LAMB frontend.
 * 
 * Provides consistent error message extraction from various error types
 * including Axios errors, fetch Response errors, and standard Error objects.
 * 
 * @example
 * import { handleApiError, extractErrorMessage } from '$lib/utils/errorHandler';
 * 
 * try {
 *   await saveAssistant(data);
 * } catch (error) {
 *   const message = handleApiError(error, 'AssistantForm');
 *   showError(message);
 * }
 */

import { logger } from './logger.js';

/**
 * @typedef {Object} ApiErrorResponse
 * @property {string} [detail] - Error detail from FastAPI
 * @property {string} [message] - Alternative error message field
 * @property {string} [error] - Another alternative error field
 */

/**
 * Extracts a user-friendly error message from various error types.
 * 
 * @param {unknown} error - The error to extract message from
 * @returns {string} A user-friendly error message
 */
export function extractErrorMessage(error) {
	// Handle null/undefined
	if (!error) {
		return 'An unexpected error occurred';
	}

	// Handle Axios errors (have response.data structure)
	if (typeof error === 'object' && 'response' in error) {
		const axiosError = /** @type {{ response?: { data?: ApiErrorResponse, status?: number } }} */ (error);
		if (axiosError.response?.data) {
			const data = axiosError.response.data;
			if (data.detail) return data.detail;
			if (data.message) return data.message;
			if (data.error) return data.error;
		}
		if (axiosError.response?.status) {
			return `Request failed with status ${axiosError.response.status}`;
		}
	}

	// Handle standard Error objects
	if (error instanceof Error) {
		return error.message || 'An error occurred';
	}

	// Handle string errors
	if (typeof error === 'string') {
		return error;
	}

	// Handle objects with message property
	if (typeof error === 'object' && 'message' in error) {
		return String(error.message);
	}

	// Fallback
	return 'An unexpected error occurred';
}

/**
 * Handles API errors with logging and returns a user-friendly message.
 * 
 * @param {unknown} error - The error to handle
 * @param {string} [context='API'] - Context for logging (e.g., component name)
 * @returns {string} A user-friendly error message
 */
export function handleApiError(error, context = 'API') {
	const message = extractErrorMessage(error);
	
	// Log the full error for debugging
	logger.error(`[${context}]`, error);
	
	return message;
}

/**
 * Creates an error handler function bound to a specific context.
 * Useful for components that need to handle multiple errors.
 * 
 * @param {string} context - The context name for logging
 * @returns {function(unknown): string} A bound error handler function
 * 
 * @example
 * const handleError = createErrorHandler('AssistantForm');
 * // Later:
 * const message = handleError(error);
 */
export function createErrorHandler(context) {
	return (error) => handleApiError(error, context);
}

/**
 * Checks if an error is a network error (no response from server).
 * 
 * @param {unknown} error - The error to check
 * @returns {boolean} True if the error is a network error
 */
export function isNetworkError(error) {
	if (!error) return false;
	
	// Axios network errors have no response
	if (typeof error === 'object' && 'response' in error) {
		const axiosError = /** @type {{ response?: unknown, request?: unknown }} */ (error);
		return !axiosError.response && !!axiosError.request;
	}
	
	// Check for common network error messages
	if (error instanceof Error) {
		const message = error.message.toLowerCase();
		return (
			message.includes('network') ||
			message.includes('fetch') ||
			message.includes('failed to fetch') ||
			message.includes('networkerror')
		);
	}
	
	return false;
}

/**
 * Checks if an error is an authentication error (401/403).
 * 
 * @param {unknown} error - The error to check
 * @returns {boolean} True if the error is an auth error
 */
export function isAuthError(error) {
	if (!error) return false;
	
	// Check Axios error response status
	if (typeof error === 'object' && 'response' in error) {
		const axiosError = /** @type {{ response?: { status?: number } }} */ (error);
		const status = axiosError.response?.status;
		return status === 401 || status === 403;
	}
	
	// Check error message for auth-related keywords
	if (error instanceof Error) {
		const message = error.message.toLowerCase();
		return (
			message.includes('unauthorized') ||
			message.includes('not authenticated') ||
			message.includes('forbidden') ||
			message.includes('authentication')
		);
	}
	
	return false;
}

export default {
	extractErrorMessage,
	handleApiError,
	createErrorHandler,
	isNetworkError,
	isAuthError
};
