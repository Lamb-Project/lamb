// src/lib/workshop/workshopRoute.js
/**
 * Shared predicate for the student workshop shell.
 *
 * The workshop wizard is served inside the LMS iframe and must not render the
 * Creator chrome (Assistants / Knowledge bases / user menu) — students are
 * virtual principals with no Creator session, so those links are dead ends.
 * Both the root layout (which hides the chrome) and its tests use this one
 * predicate, so "what counts as a workshop route" is defined exactly once.
 */

/** Path prefix of the student workshop routes (relative to the SPA base). */
export const WORKSHOP_ROUTE_PREFIX = '/m/workshop/';

/**
 * Whether a pathname belongs to the student workshop shell.
 *
 * @param {string} pathname - `$page.url.pathname`
 * @param {string} [basePath] - SvelteKit `base` ('' for a root deployment)
 * @returns {boolean}
 */
export function isWorkshopPath(pathname, basePath = '') {
	if (!pathname) return false;
	return pathname.startsWith(`${basePath}${WORKSHOP_ROUTE_PREFIX}`);
}