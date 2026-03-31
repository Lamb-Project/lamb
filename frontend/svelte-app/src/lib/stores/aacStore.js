/**
 * AAC Session Store — manages open session tabs and active state.
 *
 * Tracks which sessions are open as tabs, which one is active,
 * and persists tab state to sessionStorage for page navigation.
 */

/** @typedef {{ id: string, title: string, assistantId: number|null, skill: string|null }} TabInfo */

/** @type {TabInfo[]} */
let openTabs = $state([]);

/** @type {string|null} */
let activeTabId = $state(null);

/** @type {boolean} */
let showTabs = $state(false);

// Restore from sessionStorage on load
if (typeof window !== 'undefined') {
	try {
		const saved = sessionStorage.getItem('aac_tabs');
		if (saved) {
			const data = JSON.parse(saved);
			openTabs = data.tabs || [];
			activeTabId = data.activeId || null;
			showTabs = openTabs.length > 0;
		}
	} catch (_) { /* ignore */ }
}

function persist() {
	if (typeof window === 'undefined') return;
	sessionStorage.setItem('aac_tabs', JSON.stringify({
		tabs: openTabs,
		activeId: activeTabId,
	}));
}

/**
 * Open a new session as a tab.
 * @param {string} id - Session ID
 * @param {string} title - Tab title
 * @param {number|null} [assistantId]
 * @param {string|null} [skill]
 */
export function openTab(id, title, assistantId = null, skill = null) {
	// Don't duplicate
	if (openTabs.find(t => t.id === id)) {
		activeTabId = id;
		showTabs = true;
		persist();
		return;
	}
	openTabs = [...openTabs, { id, title, assistantId, skill }];
	activeTabId = id;
	showTabs = true;
	persist();
}

/**
 * Close a tab.
 * @param {string} id
 */
export function closeTab(id) {
	openTabs = openTabs.filter(t => t.id !== id);
	if (activeTabId === id) {
		activeTabId = openTabs.length > 0 ? openTabs[openTabs.length - 1].id : null;
	}
	showTabs = openTabs.length > 0;
	persist();
}

/**
 * Switch to a tab.
 * @param {string} id
 */
export function setActiveTab(id) {
	activeTabId = id;
	persist();
}

/** Hide the tab bar (go back to main view). */
export function hideTabs() {
	showTabs = false;
	activeTabId = null;
	persist();
}

/** @returns {TabInfo[]} */
export function getOpenTabs() {
	return openTabs;
}

/** @returns {string|null} */
export function getActiveTabId() {
	return activeTabId;
}

/** @returns {boolean} */
export function isTabsVisible() {
	return showTabs;
}
