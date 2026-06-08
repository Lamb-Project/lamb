import { CheckCircle2, Loader2, AlertCircle, Lock, Users } from 'lucide-svelte';

/**
 * @typedef {Object} StatusBadgeProps
 * @property {'neutral'|'success'|'warning'|'danger'|'info'|'brand'} variant
 * @property {any} [icon]    lucide icon component (or undefined for plain pill)
 * @property {string} label
 * @property {boolean} [spin]   true for processing/queued/pending (Loader2)
 */

/**
 * Single source of truth for status -> Badge props.
 *
 * Locked mapping (see Phase A Consistency Contract):
 *  ready / completed     -> success  + CheckCircle2 + "Ready"
 *  processing / pending  -> info     + Loader2 (spin) + "Processing"
 *  queued                -> info     + Loader2 (spin) + "Queued"
 *  failed / error        -> danger   + AlertCircle + "Failed"
 *  empty (count===0)     -> warning  + AlertCircle + "Empty"
 *  private               -> neutral  + Lock        + "Private"
 *  shared                -> success  + Users       + "Shared"
 *  locked                -> neutral  + Lock        + "Locked"
 *
 * `label` is an English fallback - callers should localize via i18n if a key
 * exists for the status in question; this helper provides safe defaults so
 * a missing translation never strips the meaning from the pill.
 *
 * @param {string | null | undefined} status
 * @returns {StatusBadgeProps}
 */
export function statusBadgeProps(status) {
	const s = (status ?? '').toString().toLowerCase();

	switch (s) {
		case 'ready':
		case 'completed':
		case 'complete':
		case 'success':
		case 'done':
			return { variant: 'success', icon: CheckCircle2, label: 'Ready' };

		case 'processing':
		case 'pending':
		case 'in_progress':
		case 'running':
			return { variant: 'info', icon: Loader2, label: 'Processing', spin: true };

		case 'queued':
		case 'waiting':
			return { variant: 'info', icon: Loader2, label: 'Queued', spin: true };

		case 'failed':
		case 'error':
		case 'errored':
			return { variant: 'danger', icon: AlertCircle, label: 'Failed' };

		case 'empty':
			return { variant: 'warning', icon: AlertCircle, label: 'Empty' };

		case 'private':
			return { variant: 'neutral', icon: Lock, label: 'Private' };

		case 'shared':
			return { variant: 'success', icon: Users, label: 'Shared' };

		case 'locked':
			return { variant: 'neutral', icon: Lock, label: 'Locked' };

		default:
			// Render the raw status as label, neutral pill, no icon.
			return {
				variant: 'neutral',
				icon: undefined,
				label: status ? String(status) : 'Unknown'
			};
	}
}

export default statusBadgeProps;
