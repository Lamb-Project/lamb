<script module>
	/**
	 * The organization the setup page starts with: the one named in the page address (`?org=`,
	 * just added with a creator code) when it is one of the instructor's, else the only one,
	 * else none (the instructor chooses).
	 * @param {{ orgs_with_assistants?: Record<string, unknown> } | null | undefined} info answer of /lamb/v1/lti/setup/info
	 * @param {string | null | undefined} [preferred] value of `org` in the page address
	 * @returns {string}
	 */
	export function initialOrganization(info, preferred) {
		const ids = Object.keys(info?.orgs_with_assistants ?? {});
		if (preferred && ids.includes(String(preferred))) return String(preferred);
		return ids.length === 1 ? ids[0] : '';
	}
</script>

<script>
	import { _, locale } from '$lib/i18n.js';
	import CreatorAccess, { creatorAccountFor } from '$lib/CreatorAccess.svelte';

	// First step of the activity setup (issue 562): the instructor's organizations, one of them
	// chosen, and a way to add another with a creator code. Under the chosen organization, the way
	// into LAMB Creator for it, where assistants are built; the setup form follows on the page.

	const LINK =
		'underline decoration-gray-300 underline-offset-2 transition-colors hover:text-blue-700 hover:decoration-blue-400';

	/**
	 * @type {{
	 *   token: string,
	 *   info: any,
	 *   selected?: string,
	 *   creatorFirst?: boolean,
	 *   navigate?: (address: string) => void
	 * }}
	 * `info` is the answer of /lamb/v1/lti/setup/info; `selected` the id of the chosen organization
	 * (bindable); `creatorFirst` says the form cannot go on without LAMB Creator, which makes its
	 * button the main one.
	 */
	let {
		token,
		info,
		selected = $bindable(''),
		creatorFirst = false,
		navigate = undefined
	} = $props();

	let organizations = $derived(
		Object.entries(info?.orgs_with_assistants ?? {}).map(([id, assistants]) => ({
			id,
			name: info?.org_names?.[id] || '',
			count: Array.isArray(assistants) ? assistants.length : 0
		}))
	);
	/** One organization, already chosen: there is nothing to choose. */
	let settled = $derived(organizations.length === 1 && selected === organizations[0].id);
	/** The chosen organization's account for entering LAMB Creator from here, if it has one. */
	let account = $derived(selected ? creatorAccountFor(info?.creator_access, selected) : undefined);
</script>

{#snippet label(/** @type {{ id: string, name: string, count: number }} */ organization)}
	<div>
		<span class="font-medium text-gray-900">
			{organization.name ||
				$_('setupHub.organizationFallback', { values: { id: organization.id } })}
		</span>
		<span class="ml-2 text-sm text-gray-500">
			({$_('setupHub.assistantCount', { values: { count: organization.count } })})
		</span>
	</div>
{/snippet}

<!-- The texts need the locale, which the layout loads after the first render. -->
{#if $locale}
	<div class="mb-6">
		<h2 id="organization-step-title" class="mb-3 text-lg font-semibold text-gray-800">
			{settled ? $_('setupHub.yourOrganization') : $_('setupHub.chooseOrganization')}
		</h2>
		{#if organizations.length > 1}
			<p class="mb-4 text-sm text-gray-600">
				{$_('setupHub.chooseIntro')}
				<span class="font-medium text-amber-600">{$_('setupHub.cannotChange')}</span>
			</p>
		{/if}

		{#if settled}
			<div
				class="mb-2 flex items-center gap-3 rounded-lg border border-blue-500 bg-blue-50 p-3"
				aria-current="true"
			>
				<svg
					class="h-5 w-5 shrink-0 text-blue-600"
					fill="none"
					viewBox="0 0 24 24"
					stroke="currentColor"
					aria-hidden="true"
				>
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
					/>
				</svg>
				{@render label(organizations[0])}
			</div>
		{:else}
			<div role="radiogroup" aria-labelledby="organization-step-title">
				{#each organizations as organization (organization.id)}
					<label
						class="mb-2 flex cursor-pointer items-center gap-3 rounded-lg border p-3 transition-colors hover:bg-blue-50 {selected ===
						organization.id
							? 'border-blue-500 bg-blue-50'
							: ''}"
					>
						<input
							type="radio"
							name="organization_id"
							value={organization.id}
							bind:group={selected}
							class="text-blue-600 focus:ring-blue-500"
							required
						/>
						{@render label(organization)}
					</label>
				{/each}
			</div>
		{/if}

		{#if info?.can_add_organization === true}
			<p class="text-sm text-gray-500">
				<a href="/lamb/v1/lti/onboarding?token={encodeURIComponent(token)}" class={LINK}>
					{$_('setupHub.addOrganization')}
				</a>
			</p>
		{/if}

		{#if selected && account}
			<div
				class="mt-4 flex flex-col gap-3 rounded-lg border border-gray-200 bg-gray-50 p-3 sm:flex-row sm:items-center sm:justify-between"
			>
				<p class="text-sm text-gray-600">{$_('setupHub.creator')}</p>
				<!-- A refusal shown for one organization does not stay when another is chosen. -->
				{#key selected}
					<CreatorAccess
						{token}
						accounts={info?.creator_access}
						organizationId={selected}
						prominent={creatorFirst}
						{navigate}
						class="shrink-0 max-sm:items-start"
					/>
				{/key}
			</div>
		{:else if selected}
			<!-- No account to enter from this page: the four hours of the launch are over. The
			     instructor's accounts have no password, so the way in is the LMS, never a login
			     page (15 November 2026: only LTI creator accounts take part in LTI pages). -->
			{#if info?.creator_session}
				<a href="/activities" class="mt-4 inline-block text-sm text-blue-700">Activities</a>
			{:else}
				<p class="mt-4 text-sm text-gray-600" data-reopen-from-lms>{$_('setupHub.reopen')}</p>
			{/if}
		{/if}
	</div>
{/if}
