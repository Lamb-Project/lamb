import { writable } from 'svelte/store';

/**
 * @typedef {Object} ToastAction
 * @property {string} label
 * @property {() => void} onClick
 */

/**
 * @typedef {Object} ToastEntry
 * @property {string} id
 * @property {'success'|'error'|'info'|'loading'} variant
 * @property {string} title
 * @property {string} [description]
 * @property {number} duration   ms; 0 / Infinity = no auto-dismiss
 * @property {ToastAction} [action]
 * @property {number} createdAt
 */

/** @type {import('svelte/store').Writable<ToastEntry[]>} */
export const toasts = writable([]);

/** @type {Map<string, ReturnType<typeof setTimeout>>} */
const timers = new Map();

/** Default auto-dismiss durations (ms). 0 disables auto-dismiss. */
const DEFAULTS = {
	success: 5000,
	error: 5000,
	info: 5000,
	loading: 0
};

function makeId() {
	if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
		return crypto.randomUUID();
	}
	return `t_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

/**
 * @param {ToastEntry['variant']} variant
 * @param {string} title
 * @param {{ description?: string, duration?: number, action?: ToastAction }} [opts]
 */
function push(variant, title, opts = {}) {
	const id = makeId();
	const duration =
		typeof opts.duration === 'number'
			? opts.duration
			: opts.action
				? Math.max(DEFAULTS[variant] || 5000, 6000)
				: (DEFAULTS[variant] ?? 5000);

	const entry = {
		id,
		variant,
		title,
		description: opts.description,
		duration,
		action: opts.action,
		createdAt: Date.now()
	};

	toasts.update((list) => [...list, entry]);

	if (duration && duration > 0 && Number.isFinite(duration)) {
		const handle = setTimeout(() => dismiss(id), duration);
		timers.set(id, handle);
	}

	return id;
}

/** Remove a toast by id.
 * @param {string} id
 */
export function dismiss(id) {
	const handle = timers.get(id);
	if (handle) {
		clearTimeout(handle);
		timers.delete(id);
	}
	toasts.update((list) => list.filter((t) => t.id !== id));
}

/**
 * Patch an existing toast (e.g., flip a loading toast → success).
 * @param {string} id
 * @param {Partial<ToastEntry>} patch
 */
export function update(id, patch) {
	toasts.update((list) =>
		list.map((t) => {
			if (t.id !== id) return t;
			const next = { ...t, ...patch };
			// If duration changed and is finite + positive, restart the timer.
			if (Object.prototype.hasOwnProperty.call(patch, 'duration')) {
				const existing = timers.get(id);
				if (existing) {
					clearTimeout(existing);
					timers.delete(id);
				}
				const d = next.duration;
				if (d && d > 0 && Number.isFinite(d)) {
					const handle = setTimeout(() => dismiss(id), d);
					timers.set(id, handle);
				}
			}
			return next;
		})
	);
}

export const toast = {
	/** @param {string} title @param {{ description?: string, duration?: number, action?: ToastAction }} [opts] */
	success: (title, opts) => push('success', title, opts),
	/** @param {string} title @param {{ description?: string, duration?: number, action?: ToastAction }} [opts] */
	error: (title, opts) => push('error', title, opts),
	/** @param {string} title @param {{ description?: string, duration?: number, action?: ToastAction }} [opts] */
	info: (title, opts) => push('info', title, opts),
	/** @param {string} title @param {{ description?: string, duration?: number, action?: ToastAction }} [opts] */
	loading: (title, opts) => push('loading', title, opts),
	dismiss,
	update
};

export default toast;
