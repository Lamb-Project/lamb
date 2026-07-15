/**
 * AAC Session Store — manages open session tabs and active state.
 *
 * Tracks which sessions are open as tabs, which one is active,
 * and persists tab state to sessionStorage for page navigation.
 *
 * Implementation note: this module previously used Svelte 5 `$state` runes
 * directly, but cross-module reactivity to runes did not propagate reliably
 * to subscriber components in production builds. Components compensated by
 * polling `getOpenTabs()` every 500ms — high CPU and reactivity churn (#352, H6).
 *
 * Now backed by `writable()` stores from `svelte/store`, which propagate
 * across modules cleanly. Components subscribe via `$openTabs` / `$activeTabId`
 * rather than polling. The named function exports are preserved so non-reactive
 * call sites (mutations from event handlers) keep working.
 */

import { writable, get } from 'svelte/store';

/** @typedef {{ id: string, title: string, assistantId: number|null, skill: string|null, lastMessageAt: number }} TabInfo */

/** @type {import('svelte/store').Writable<TabInfo[]>} */
export const openTabs = writable([]);

/** @type {import('svelte/store').Writable<string|null>} */
export const activeTabId = writable(null);

/** @type {import('svelte/store').Writable<boolean>} */
export const showTabs = writable(false);

// Restore from sessionStorage on load (browser only).
if (typeof window !== 'undefined') {
	try {
		const saved = sessionStorage.getItem('aac_tabs');
		if (saved) {
			const data = JSON.parse(saved);
			const tabs = data.tabs || [];
			openTabs.set(tabs);
			activeTabId.set(data.activeId || null);
			showTabs.set(tabs.length > 0);
		}
	} catch (_) {
		/* ignore */
	}
}

function persist() {
	if (typeof window === 'undefined') return;
	sessionStorage.setItem(
		'aac_tabs',
		JSON.stringify({
			tabs: get(openTabs),
			activeId: get(activeTabId)
		})
	);
}

/**
 * Open a new session as a tab.
 * @param {string} id - Session ID
 * @param {string} title - Tab title
 * @param {number|null} [assistantId]
 * @param {string|null} [skill]
 */
export function openTab(id, title, assistantId = null, skill = null) {
	const current = get(openTabs);
	if (current.find((t) => t.id === id)) {
		// Don't duplicate; just activate.
		activeTabId.set(id);
		showTabs.set(true);
		persist();
		return;
	}
	openTabs.set([...current, { id, title, assistantId, skill, lastMessageAt: Date.now() }]);
	activeTabId.set(id);
	showTabs.set(true);
	persist();
}

/**
 * Close a tab.
 * @param {string} id
 */
export function closeTab(id) {
	const remaining = get(openTabs).filter((t) => t.id !== id);
	openTabs.set(remaining);
	if (get(activeTabId) === id) {
		activeTabId.set(remaining.length > 0 ? remaining[remaining.length - 1].id : null);
	}
	showTabs.set(remaining.length > 0);
	persist();
}

/**
 * Switch to a tab.
 * @param {string} id
 */
export function setActiveTab(id) {
	activeTabId.set(id);
	persist();
}

/** Hide the tab bar (go back to main view). */
export function hideTabs() {
	showTabs.set(false);
	activeTabId.set(null);
	persist();
}

/** Clear all tabs and remove from sessionStorage. Call on logout. */
export function resetTabs() {
	openTabs.set([]);
	activeTabId.set(null);
	showTabs.set(false);
	if (typeof window !== 'undefined') {
		sessionStorage.removeItem('aac_tabs');
	}
}

/** @returns {TabInfo[]} */
export function getOpenTabs() {
	return get(openTabs);
}

/** @returns {string|null} */
export function getActiveTabId() {
	return get(activeTabId);
}

/** @returns {boolean} */
export function isTabsVisible() {
	return get(showTabs);
}

/**
 * Record that a message was sent in a tab. Returns true if user was away >5 min.
 * @param {string} id
 * @returns {boolean}
 */
export function recordTabActivity(id) {
	const AWAY_THRESHOLD_MS = 5 * 60 * 1000; // 5 minutes
	const tabs = get(openTabs);
	const tab = tabs.find((t) => t.id === id);
	if (!tab) return false;
	const wasAway = Date.now() - (tab.lastMessageAt || 0) > AWAY_THRESHOLD_MS;
	// Replace the tab to trigger reactivity (mutating the existing object
	// would not notify subscribers).
	openTabs.set(tabs.map((t) => (t.id === id ? { ...t, lastMessageAt: Date.now() } : t)));
	persist();
	return wasAway;
}
