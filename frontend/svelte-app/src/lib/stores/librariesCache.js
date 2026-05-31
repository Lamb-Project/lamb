/**
 * @fileoverview Lightweight client-side cache for libraries list pages.
 *
 * The Library Manager `/creator/libraries` endpoint currently returns the full
 * list in a single response; pagination is performed client-side via
 * `processListData`. This cache keeps the most-recently fetched array of
 * libraries in memory so navigating back to the list paints from cache
 * immediately while a background revalidation fetches fresh data.
 *
 * Key design points:
 *  - Keyed by `orgId` so users in different orgs don't see each other's data.
 *  - Stores both the full list and a `fetchedAt` timestamp so consumers can
 *    decide whether the cache is fresh enough.
 *  - Not persisted across reloads — purely an in-memory perceived-performance
 *    cache that disappears on full page reload.
 */
import { writable, get } from 'svelte/store';

/**
 * @typedef {Object} LibrariesCacheEntry
 * @property {import('$lib/services/libraryService').Library[]} libraries
 * @property {number} fetchedAt   ms since epoch
 */

/** @type {import('svelte/store').Writable<Record<string, LibrariesCacheEntry>>} */
export const librariesCache = writable({});

/**
 * Cache freshness window — entries older than this are still painted from
 * cache (so the user sees something instantly) but the consumer should
 * always revalidate in the background.
 */
export const STALE_MS = 30_000;

/**
 * @param {string|null|undefined} orgId
 * @returns {LibrariesCacheEntry|null}
 */
export function readLibrariesCache(orgId) {
	const key = orgId || '__noorg__';
	return get(librariesCache)[key] || null;
}

/**
 * Write/replace the cache entry for an org.
 *
 * @param {string|null|undefined} orgId
 * @param {import('$lib/services/libraryService').Library[]} libraries
 */
export function writeLibrariesCache(orgId, libraries) {
	const key = orgId || '__noorg__';
	librariesCache.update((c) => ({
		...c,
		[key]: { libraries, fetchedAt: Date.now() }
	}));
}

/**
 * Patch a single library row in the cached array — used by optimistic
 * updates (share toggle, rename) so the cached list stays in sync without
 * a full re-fetch.
 *
 * @param {string|null|undefined} orgId
 * @param {string} libId
 * @param {Partial<import('$lib/services/libraryService').Library>} patch
 */
export function patchLibraryInCache(orgId, libId, patch) {
	const key = orgId || '__noorg__';
	librariesCache.update((c) => {
		const entry = c[key];
		if (!entry) return c;
		return {
			...c,
			[key]: {
				...entry,
				libraries: entry.libraries.map((l) => (l.id === libId ? { ...l, ...patch } : l))
			}
		};
	});
}

/**
 * Remove a single library row from the cached array — used by optimistic
 * delete so the cache reflects the deletion immediately.
 *
 * @param {string|null|undefined} orgId
 * @param {string} libId
 */
export function removeLibraryFromCache(orgId, libId) {
	const key = orgId || '__noorg__';
	librariesCache.update((c) => {
		const entry = c[key];
		if (!entry) return c;
		return {
			...c,
			[key]: {
				...entry,
				libraries: entry.libraries.filter((l) => l.id !== libId)
			}
		};
	});
}

/**
 * Find a single library row by id in the cache — used by LibraryDetail to
 * seed its header card instantly from row data before the full detail fetch
 * resolves.
 *
 * @param {string|null|undefined} orgId
 * @param {string} libId
 * @returns {import('$lib/services/libraryService').Library|null}
 */
export function findLibraryInCache(orgId, libId) {
	const entry = readLibrariesCache(orgId);
	if (!entry) return null;
	return entry.libraries.find((l) => l.id === libId) || null;
}
