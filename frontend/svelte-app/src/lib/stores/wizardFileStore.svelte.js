/**
 * @fileoverview IndexedDB-backed store for File objects queued in the
 * Create Knowledge wizard.
 *
 * Files (PDFs, screenshots, etc.) cannot be persisted via sessionStorage —
 * `File` is not JSON-serialisable. IndexedDB supports structured cloning,
 * which preserves File/Blob, so we use it as a sibling of `wizardDraftStore`
 * specifically for the `pendingFiles` array. The textual draft (names,
 * descriptions, URL sources, KS config, current step, …) keeps living in
 * sessionStorage; only the file array routes through here.
 *
 * Lifetime mirrors the textual draft: cleared on successful create or on
 * explicit Discard. Tab close also wipes IDB entries via the same logout/
 * close-tab semantics the user expects from a "draft" — except that, unlike
 * sessionStorage, IDB outlives a single tab. We therefore wipe entries the
 * first time the wizard's textual draft is gone (i.e. sessionStorage was
 * cleared) so stale files never resurrect themselves.
 */

import { browser } from '$app/environment';

const DB_NAME = 'lamb-wizard-files';
const DB_VERSION = 1;
const STORE_NAME = 'files';

/** @type {Promise<IDBDatabase> | null} */
let dbPromise = null;

function openDb() {
	if (!browser) return Promise.reject(new Error('not in browser'));
	if (dbPromise) return dbPromise;
	dbPromise = new Promise((resolve, reject) => {
		const req = indexedDB.open(DB_NAME, DB_VERSION);
		req.onupgradeneeded = () => {
			const db = req.result;
			if (!db.objectStoreNames.contains(STORE_NAME)) {
				db.createObjectStore(STORE_NAME, { keyPath: 'key' });
			}
		};
		req.onsuccess = () => resolve(req.result);
		req.onerror = () => reject(req.error);
	});
	return dbPromise;
}

/** @param {string | undefined | null} userId */
function resolveUserId(userId) {
	return userId && String(userId).trim() ? String(userId).trim() : '_anon';
}

/** @param {string | undefined | null} userId @param {string} kind */
function fileKey(userId, kind) {
	return `lamb.draft.${resolveUserId(userId)}.${kind}.files`;
}

/**
 * Per-key debounce so rapid keystrokes don't hammer IndexedDB.
 * @type {Map<string, ReturnType<typeof setTimeout>>}
 */
const timers = new Map();

/**
 * Persist the given File array under the user/kind key. Debounced ~300ms.
 * @param {string | undefined | null} userId
 * @param {string} kind
 * @param {File[]} files
 */
export function saveFiles(userId, kind, files) {
	if (!browser) return;
	const key = fileKey(userId, kind);
	const existing = timers.get(key);
	if (existing !== undefined) clearTimeout(existing);
	// Snapshot the array now — by the time the timer fires the caller's
	// reference may have shifted (rapid keystrokes / navigation), and we
	// want THIS save to reflect THIS moment's queue.
	const snapshot = Array.isArray(files) ? [...files] : [];
	const id = setTimeout(async () => {
		timers.delete(key);
		try {
			const db = await openDb();
			const tx = db.transaction(STORE_NAME, 'readwrite');
			tx.objectStore(STORE_NAME).put({ key, files: snapshot });
		} catch {
			// IndexedDB unavailable (private browsing, quota, …) — skip silently.
		}
	}, 300);
	timers.set(key, id);
}

/**
 * Retrieve previously-stored files. Returns [] on miss or any failure.
 * @param {string | undefined | null} userId
 * @param {string} kind
 * @returns {Promise<File[]>}
 */
export async function getFiles(userId, kind) {
	if (!browser) return [];
	try {
		const db = await openDb();
		return await new Promise((resolve) => {
			const req = db
				.transaction(STORE_NAME, 'readonly')
				.objectStore(STORE_NAME)
				.get(fileKey(userId, kind));
			req.onsuccess = () => {
				const value = req.result;
				resolve(Array.isArray(value?.files) ? value.files : []);
			};
			req.onerror = () => resolve([]);
		});
	} catch {
		return [];
	}
}

/**
 * Drop the persisted files for this user/kind. Cancels any pending
 * debounced save so it doesn't resurrect the entry.
 * @param {string | undefined | null} userId
 * @param {string} kind
 */
export async function clearFiles(userId, kind) {
	if (!browser) return;
	const key = fileKey(userId, kind);
	const existing = timers.get(key);
	if (existing !== undefined) {
		clearTimeout(existing);
		timers.delete(key);
	}
	try {
		const db = await openDb();
		db.transaction(STORE_NAME, 'readwrite').objectStore(STORE_NAME).delete(key);
	} catch {
		// ignore
	}
}
