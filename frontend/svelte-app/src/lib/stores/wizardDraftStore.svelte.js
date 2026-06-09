/**
 * @fileoverview sessionStorage-backed draft store for the Create Knowledge
 * wizard and the Create Library quick-modal.
 *
 * Drafts are keyed by `lamb.draft.{userId}.{kind}` and are automatically
 * cleared when the tab is closed (sessionStorage behaviour).
 *
 * API:
 *   getDraft(userId, kind)          → { state, savedAt } | null
 *   saveDraft(userId, kind, state)  (debounced ~300 ms)
 *   clearDraft(userId, kind)
 *   hasDraft(userId, kind)          → boolean
 */

import { browser } from '$app/environment';
import { _ } from 'svelte-i18n';
import { get } from 'svelte/store';
// Use plain Map/Date — these structures must NOT be tracked as reactive
// dependencies, otherwise the wizard's auto-save $effect causes an
// effect_update_depth_exceeded loop (saveDraft mutates timers, which
// retriggers the effect, which calls saveDraft again, etc.).

/** @param {string | undefined | null} userId */
function resolveUserId(userId) {
	return userId && String(userId).trim() ? String(userId).trim() : '_anon';
}

/**
 * Build the sessionStorage key.
 * @param {string | undefined | null} userId
 * @param {string} kind
 */
function draftKey(userId, kind) {
	return `lamb.draft.${resolveUserId(userId)}.${kind}`;
}

/**
 * Retrieve a stored draft.
 * @param {string | undefined | null} userId
 * @param {string} kind
 * @returns {{ state: any, savedAt: string } | null}
 */
export function getDraft(userId, kind) {
	if (!browser) return null;
	try {
		const raw = sessionStorage.getItem(draftKey(userId, kind));
		if (!raw) return null;
		return JSON.parse(raw);
	} catch {
		return null;
	}
}

/** @type {Map<string, ReturnType<typeof setTimeout>>} */
const timers = new Map();

/**
 * Save a draft (debounced ~300 ms per key).
 * File objects cannot be serialised — they are stripped before saving.
 * @param {string | undefined | null} userId
 * @param {string} kind
 * @param {any} state
 */
export function saveDraft(userId, kind, state) {
	if (!browser) return;
	const key = draftKey(userId, kind);
	const existing = timers.get(key);
	if (existing !== undefined) clearTimeout(existing);
	const id = setTimeout(() => {
		timers.delete(key);
		try {
			// Strip non-serialisable File objects from pendingFiles.
			const serialisable = { ...state };
			if (Array.isArray(serialisable.pendingFiles)) {
				serialisable.pendingFiles = [];
			}
			const payload = { state: serialisable, savedAt: new Date().toISOString() };
			sessionStorage.setItem(key, JSON.stringify(payload));
		} catch {
			// sessionStorage quota exceeded or private-browsing restriction — ignore.
		}
	}, 300);
	timers.set(key, id);
}

/**
 * Clear a stored draft immediately (cancels any pending debounced save).
 * @param {string | undefined | null} userId
 * @param {string} kind
 */
export function clearDraft(userId, kind) {
	if (!browser) return;
	const key = draftKey(userId, kind);
	const existing = timers.get(key);
	if (existing !== undefined) {
		clearTimeout(existing);
		timers.delete(key);
	}
	try {
		sessionStorage.removeItem(key);
	} catch {
		// ignore
	}
}

/**
 * Returns true when a non-expired draft exists for the given key.
 * @param {string | undefined | null} userId
 * @param {string} kind
 * @returns {boolean}
 */
export function hasDraft(userId, kind) {
	return getDraft(userId, kind) !== null;
}

/**
 * Format a savedAt ISO string as a human-readable relative time.
 * e.g. "2 minutes ago", "just now".
 * @param {string} isoString
 * @returns {string}
 */
export function formatDraftAge(isoString) {
	try {
		const diff = Date.now() - new Date(isoString).getTime();
		const t = get(_);
		if (diff < 60_000) return t('wizard.draftAge.justNow');
		if (diff < 3_600_000)
			return t('wizard.draftAge.minutesAgo', { values: { count: Math.floor(diff / 60_000) } });
		if (diff < 86_400_000)
			return t('wizard.draftAge.hoursAgo', { values: { count: Math.floor(diff / 3_600_000) } });
		return t('wizard.draftAge.daysAgo', { values: { count: Math.floor(diff / 86_400_000) } });
	} catch {
		return '';
	}
}
