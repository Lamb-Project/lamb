/**
 * Centralized logging utility for the LAMB frontend.
 * 
 * In development mode (import.meta.env.DEV), all log levels are active.
 * In production mode, only warn and error levels are active.
 * 
 * @example
 * import { logger } from '$lib/utils/logger';
 * 
 * logger.debug('Fetching assistants...', { limit: 10 });
 * logger.info('User logged in', { email: user.email });
 * logger.warn('API returned unexpected format');
 * logger.error('Failed to save assistant', error);
 */

const isDev = import.meta.env.DEV;

/**
 * @typedef {Object} Logger
 * @property {function(...any): void} debug - Debug level logging (dev only)
 * @property {function(...any): void} info - Info level logging (dev only)
 * @property {function(...any): void} warn - Warning level logging (always active)
 * @property {function(...any): void} error - Error level logging (always active)
 */

/** @type {Logger} */
export const logger = {
	/**
	 * Log debug information (only in development)
	 * @param {...any} args - Arguments to log
	 */
	debug: (...args) => {
		if (isDev) {
			console.log('[DEBUG]', ...args);
		}
	},

	/**
	 * Log informational messages (only in development)
	 * @param {...any} args - Arguments to log
	 */
	info: (...args) => {
		if (isDev) {
			console.info('[INFO]', ...args);
		}
	},

	/**
	 * Log warnings (always active)
	 * @param {...any} args - Arguments to log
	 */
	warn: (...args) => {
		console.warn('[WARN]', ...args);
	},

	/**
	 * Log errors (always active)
	 * @param {...any} args - Arguments to log
	 */
	error: (...args) => {
		console.error('[ERROR]', ...args);
	}
};

export default logger;
