/**
 * @fileoverview Lightweight client-side cache for Knowledge Stores list pages.
 *
 * Mirrors `librariesCache.js` (Phase B). The KB Server's
 * `/creator/knowledge-stores` endpoint returns the full list in a single
 * response today; pagination is client-side via `processListData`. This
 * cache keeps the most-recently fetched array in memory so navigating
 * back to the list paints from cache immediately while a background
 * revalidation fetches fresh data.
 *
 * Key design points:
 *  - Keyed by `orgId` so users in different orgs don't see each other's
 *    data.
 *  - Stores both the full list and a `fetchedAt` timestamp so consumers
 *    can decide whether the cache is fresh enough.
 *  - Not persisted across reloads — purely an in-memory perceived-
 *    performance cache that disappears on full page reload.
 */
import { writable, get } from 'svelte/store';

/**
 * @typedef {Object} KsCacheEntry
 * @property {import('$lib/services/knowledgeStoreService').KnowledgeStore[]} stores
 * @property {number} fetchedAt   ms since epoch
 */

/** @type {import('svelte/store').Writable<Record<string, KsCacheEntry>>} */
export const ksCache = writable({});

/**
 * Cache freshness window — entries older than this are still painted
 * from cache (so the user sees something instantly) but the consumer
 * should always revalidate in the background.
 */
export const STALE_MS = 30_000;

/**
 * @param {string|null|undefined} orgId
 * @returns {KsCacheEntry|null}
 */
export function readKsCache(orgId) {
	const key = orgId || '__noorg__';
	return get(ksCache)[key] || null;
}

/**
 * Write/replace the cache entry for an org.
 *
 * @param {string|null|undefined} orgId
 * @param {import('$lib/services/knowledgeStoreService').KnowledgeStore[]} stores
 */
export function writeKsCache(orgId, stores) {
	const key = orgId || '__noorg__';
	ksCache.update((c) => ({
		...c,
		[key]: { stores, fetchedAt: Date.now() }
	}));
}

/**
 * Patch a single KS row in the cached array — used by optimistic
 * updates (share toggle, rename) so the cached list stays in sync
 * without a full re-fetch.
 *
 * @param {string|null|undefined} orgId
 * @param {string} ksId
 * @param {Partial<import('$lib/services/knowledgeStoreService').KnowledgeStore>} patch
 */
export function patchKsInCache(orgId, ksId, patch) {
	const key = orgId || '__noorg__';
	ksCache.update((c) => {
		const entry = c[key];
		if (!entry) return c;
		return {
			...c,
			[key]: {
				...entry,
				stores: entry.stores.map((k) => (k.id === ksId ? { ...k, ...patch } : k))
			}
		};
	});
}

/**
 * Remove a single KS row from the cached array — used by optimistic
 * delete so the cache reflects the deletion immediately.
 *
 * @param {string|null|undefined} orgId
 * @param {string} ksId
 */
export function removeKsFromCache(orgId, ksId) {
	const key = orgId || '__noorg__';
	ksCache.update((c) => {
		const entry = c[key];
		if (!entry) return c;
		return {
			...c,
			[key]: {
				...entry,
				stores: entry.stores.filter((k) => k.id !== ksId)
			}
		};
	});
}

/**
 * Find a single KS row by id in the cache — used by KnowledgeStoreDetail
 * to seed its header card instantly from row data before the full detail
 * fetch resolves.
 *
 * @param {string|null|undefined} orgId
 * @param {string} ksId
 * @returns {import('$lib/services/knowledgeStoreService').KnowledgeStore|null}
 */
export function findKsInCache(orgId, ksId) {
	const entry = readKsCache(orgId);
	if (!entry) return null;
	return entry.stores.find((k) => k.id === ksId) || null;
}
