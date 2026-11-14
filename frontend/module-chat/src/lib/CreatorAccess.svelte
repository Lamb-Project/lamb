<script>
	import { _, locale } from '$lib/i18n.js';

	// Way into LAMB Creator for an instructor who reaches it only through the LMS (an LTI creator
	// has no password). The setup and dashboard pages get `creator_access` from the backend: the
	// Creator accounts this launch may enter. With no account, nothing is rendered.

	/** @typedef {{ creator_user_id: number, organization_id?: number, organization_name?: string, user_name?: string }} CreatorAccount */

	/** @type {{ token: string | null, accounts?: CreatorAccount[] | null, class?: string }} */
	let { token, accounts = [], class: className = '' } = $props();

	let list = $derived(Array.isArray(accounts) ? accounts : []);
	let busy = $state(false);
	/** @type {'' | 'blocked' | 'failed'} */
	let failure = $state('');
	/** The reason the backend gave for a refusal, when it gave one. */
	let detail = $state('');

	/** @param {CreatorAccount} account */
	function organizationOf(account) {
		return account.organization_name || account.user_name || `#${account.creator_user_id}`;
	}

	/**
	 * The address for the new tab, or '' when the answer carries none that a browser tab may open.
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
		failure = '';
		detail = '';
		// The tab has to open inside the click: opened after the request, the browser blocks it as
		// a pop-up. It starts blank and cannot reach this page; the address, which carries a
		// session token, goes to that tab only and is never shown or logged here.
		const tab = window.open('about:blank', '_blank');
		if (!tab) {
			failure = 'blocked';
			return;
		}
		tab.opener = null;
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
		busy = false;
		if (address) {
			if (!tab.closed) tab.location.replace(address);
			return;
		}
		tab.close();
		failure = 'failed';
	}
</script>

{#snippet entry(
	/** @type {CreatorAccount} */ account,
	/** @type {string} */ text,
	/** @type {string | undefined} */ name
)}
	<button
		type="button"
		class="inline-flex max-w-full cursor-pointer items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-left text-sm font-medium text-gray-700 transition-colors enabled:hover:border-blue-500 enabled:hover:bg-blue-50 enabled:hover:text-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
		aria-label={name}
		title={$_('creatorAccess.newTab')}
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
				d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
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
		{#if failure}
			<p role="alert" class="max-w-xs rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">
				{failure === 'blocked' ? $_('creatorAccess.blocked') : detail || $_('creatorAccess.failed')}
			</p>
		{/if}
	</div>
{/if}
