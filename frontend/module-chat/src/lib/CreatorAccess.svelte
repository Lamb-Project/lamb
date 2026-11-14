<script module>
	/** @typedef {{ creator_user_id: number, organization_id?: number | string, organization_name?: string, user_name?: string }} CreatorAccount */

	/**
	 * The account that enters LAMB Creator in one organization, if the backend offers one. An
	 * organization of the instructor may have none: a regular account, with a password.
	 * @param {CreatorAccount[] | null | undefined} accounts
	 * @param {number | string | null | undefined} organizationId
	 * @returns {CreatorAccount | undefined}
	 */
	export function creatorAccountFor(accounts, organizationId) {
		if (!Array.isArray(accounts) || organizationId === undefined || organizationId === null) {
			return undefined;
		}
		return accounts.find((account) => String(account.organization_id) === String(organizationId));
	}
</script>

<script>
	import { _, locale } from '$lib/i18n.js';

	// Way into LAMB Creator for an instructor who reaches it only through the LMS (an LTI creator
	// has no password). The setup and dashboard pages get `creator_access` from the backend: the
	// Creator accounts this launch may enter. With no account, nothing is rendered. LAMB Creator
	// opens in this same window: no new tab (issue 562).
	//
	// `organizationId` restricts the control to one organization: a single button for that
	// organization's account, or nothing when the organization has no account in the list.

	/**
	 * @type {{
	 *   token: string | null,
	 *   accounts?: CreatorAccount[] | null,
	 *   organizationId?: number | string | null,
	 *   prominent?: boolean,
	 *   navigate?: (address: string) => void,
	 *   class?: string
	 * }}
	 */
	let {
		token,
		accounts = [],
		organizationId = undefined,
		prominent = false,
		navigate = (address) => window.location.assign(address),
		class: className = ''
	} = $props();

	let list = $derived.by(() => {
		if (organizationId === undefined || organizationId === null) {
			return Array.isArray(accounts) ? accounts : [];
		}
		const account = creatorAccountFor(accounts, organizationId);
		return account ? [account] : [];
	});
	/** True from the click until the answer, and on while the browser leaves for LAMB Creator. */
	let busy = $state(false);
	let failed = $state(false);
	/** The reason the backend gave for a refusal, when it gave one. */
	let detail = $state('');

	/** @param {CreatorAccount} account */
	function organizationOf(account) {
		return account.organization_name || account.user_name || `#${account.creator_user_id}`;
	}

	/**
	 * The address to go to, or '' when the answer carries none that a browser window may open.
	 * @param {unknown} value
	 */
	function webAddress(value) {
		if (typeof value !== 'string' || !value) return '';
		try {
			const address = new URL(value, window.location.href);
			return address.protocol === 'https:' || address.protocol === 'http:' ? address.href : '';
		} catch {
			return '';
		}
	}

	/** @param {CreatorAccount} account */
	async function enter(account) {
		if (busy) return;
		failed = false;
		detail = '';
		busy = true;
		let address = '';
		try {
			const response = await fetch('/lamb/v1/lti/creator-session', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ token, creator_user_id: account.creator_user_id })
			});
			const data = await response.json().catch(() => ({}));
			if (response.ok) address = webAddress(data?.url);
			else if (typeof data?.detail === 'string') detail = data.detail;
		} catch {
			// No answer from the server: the translated message covers it.
		}
		if (address) {
			// The address carries a session token: it goes to the browser only and is never shown
			// or logged here. The control stays disabled while this page is being left.
			navigate(address);
			return;
		}
		busy = false;
		failed = true;
	}

	/**
	 * Back from LAMB Creator with the browser's Back button, the page may come out of the
	 * browser's cache exactly as it was left: with the control still disabled.
	 * @param {PageTransitionEvent} event
	 */
	function restored(event) {
		if (event.persisted) busy = false;
	}
</script>

<svelte:window onpageshow={restored} />

{#snippet entry(
	/** @type {CreatorAccount} */ account,
	/** @type {string} */ text,
	/** @type {string | undefined} */ name
)}
	<button
		type="button"
		class="inline-flex max-w-full cursor-pointer items-center gap-1.5 rounded-lg border text-left text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 {prominent
			? 'border-blue-600 bg-blue-600 px-4 py-2 text-white enabled:hover:border-blue-700 enabled:hover:bg-blue-700'
			: 'border-gray-300 bg-white px-3 py-1.5 text-gray-700 enabled:hover:border-blue-500 enabled:hover:bg-blue-50 enabled:hover:text-blue-700'}"
		aria-label={name}
		disabled={busy}
		onclick={() => enter(account)}
	>
		<span class={name ? '' : 'whitespace-nowrap'}>{text}</span>
		<svg
			class="h-4 w-4 shrink-0"
			fill="none"
			viewBox="0 0 24 24"
			stroke="currentColor"
			aria-hidden="true"
		>
			<path
				stroke-linecap="round"
				stroke-linejoin="round"
				stroke-width="2"
				d="M14 5l7 7m0 0l-7 7m7-7H3"
			/>
		</svg>
	</button>
{/snippet}

<!-- The texts need the locale, which the layout loads after the first render. -->
{#if $locale && list.length > 0}
	<div class="flex flex-col items-end gap-1.5 {className}">
		{#if list.length === 1}
			{@render entry(list[0], $_('creatorAccess.open'), undefined)}
		{:else}
			<div class="flex max-w-xs flex-wrap items-center justify-end gap-1.5 lg:max-w-lg">
				<span class="text-xs text-gray-500">{$_('creatorAccess.open')}</span>
				{#each list as account (account.creator_user_id)}
					{@const organization = organizationOf(account)}
					{@render entry(
						account,
						organization,
						$_('creatorAccess.openIn', { values: { organization } })
					)}
				{/each}
			</div>
		{/if}
		{#if failed}
			<p role="alert" class="max-w-xs rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">
				{detail || $_('creatorAccess.failed')}
			</p>
		{/if}
	</div>
{/if}
