<script>
	import { onMount } from 'svelte';
	import { _ } from '$lib/i18n';
	import { base } from '$app/paths';
	import AgentLaunchCard from '$lib/components/aac/AgentLaunchCard.svelte';

	/** @type {{ profile?: any, isLoading?: boolean, error?: string | null, onRetry?: () => void }} */
	let { profile = null, isLoading = false, error = null, onRetry = () => {} } = $props();

	// Auto-retry: if dashboard has no data 1.5s after mount, trigger reload
	onMount(() => {
		const timer = setTimeout(() => {
			if (!profile && !isLoading && !error) {
				onRetry();
			}
		}, 1500);
		return () => clearTimeout(timer);
	});

	// Collapse state for each section (all collapsed by default)
	let expandedOwned = $state({ assistants: false, kbs: false, rubrics: false, templates: false });
	let expandedShared = $state({ assistants: false, kbs: false, rubrics: false, templates: false });

	/**
	 * Format a unix timestamp to a readable date
	 * @param {number|null|undefined} ts
	 */
	function formatDate(ts) {
		if (!ts) return '-';
		return new Date(ts * 1000).toLocaleDateString(undefined, {
			year: 'numeric',
			month: 'short',
			day: 'numeric'
		});
	}

	/**
	 * Get a translated org role label
	 * @param {string|null|undefined} role
	 */
	function orgRoleLabel(role) {
		if (!role) return '-';
		const key = `home.dashboard.orgRole.${role}`;
		return $_(key, { default: role.charAt(0).toUpperCase() + role.slice(1) });
	}
</script>

<div>
	{#if isLoading}
		<!-- Loading skeleton -->
		<div class="mb-6">
			<div class="mb-2 h-6 w-1/3 animate-pulse rounded bg-gray-200"></div>
			<div class="mb-6 h-4 w-1/2 animate-pulse rounded bg-gray-200"></div>
		</div>
		<div class="space-y-6">
			{#each Array(3) as _}
				<div class="animate-pulse rounded-2xl border border-gray-100 bg-white p-6 shadow-sm">
					<div class="mb-4 h-4 w-1/4 rounded bg-gray-200"></div>
					<div class="space-y-3">
						<div class="h-3 w-3/4 rounded bg-gray-200"></div>
						<div class="h-3 w-1/2 rounded bg-gray-200"></div>
						<div class="h-3 w-2/3 rounded bg-gray-200"></div>
					</div>
				</div>
			{/each}
		</div>
	{:else if error}
		<div
			class="mb-6 rounded-xl border border-red-200 bg-red-50 px-6 py-4 text-red-700"
			role="alert"
		>
			<div class="flex items-center gap-3">
				<svg class="h-5 w-5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
					<path
						fill-rule="evenodd"
						d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
						clip-rule="evenodd"
					/>
				</svg>
				<span class="font-medium">{error}</span>
			</div>
			<button onclick={onRetry} class="mt-3 text-sm text-red-600 underline hover:text-red-800">
				{$_('home.dashboard.retry', { default: 'Try Again' })}
			</button>
		</div>
	{:else if profile}
		<!-- Welcome header + org info -->
		<div class="mb-8">
			<h1 class="mb-1 text-2xl font-semibold text-gray-800">
				{$_('home.dashboard.welcome', {
					default: `Welcome back, ${profile.user.name}!`,
					values: { name: profile.user.name || profile.user.email }
				})}
			</h1>
			{#if profile.organization}
				<p class="flex flex-wrap items-center gap-3 text-sm text-gray-500">
					<span class="inline-flex items-center gap-1">
						<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="2"
								d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5"
							/>
						</svg>
						{profile.organization.name}
					</span>
					<span class="text-gray-300">|</span>
					<span
						>{$_('home.dashboard.role', { default: 'Role' })}: {orgRoleLabel(
							profile.organization.role
						)}</span
					>
					<span class="text-gray-300">|</span>
					<span
						>{$_('home.dashboard.memberSince', { default: 'Member since' })}
						{formatDate(profile.user.created_at)}</span
					>
				</p>
			{/if}
		</div>

		<!-- LAMB Agent card -->
		<div class="mb-8">
			<AgentLaunchCard />
		</div>

		<!-- Two-column layout: My Resources / Shared with Me -->
		<div class="grid grid-cols-1 gap-8 xl:grid-cols-2">
			<!-- ============================================ -->
			<!-- LEFT COLUMN: MY RESOURCES                    -->
			<!-- ============================================ -->
			<div class="space-y-4">
				<h2 class="text-sm font-medium tracking-wide text-gray-500 uppercase">
					{$_('home.dashboard.owned', { default: 'My Resources' })}
				</h2>

				<!-- My Assistants -->
				<div
					class="overflow-hidden rounded-2xl border border-blue-100 bg-gradient-to-br from-blue-50 to-indigo-50 shadow-sm"
				>
					<!-- svelte-ignore a11y_no_static_element_interactions -->
					<button
						class="flex w-full cursor-pointer items-center justify-between p-5 text-left transition-colors hover:bg-blue-50/50"
						onclick={() => (expandedOwned.assistants = !expandedOwned.assistants)}
						aria-expanded={expandedOwned.assistants}
					>
						<h3
							class="flex items-center gap-2 text-sm font-medium tracking-wide text-blue-600 uppercase"
						>
							<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									stroke-width="2"
									d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
								/>
							</svg>
							{$_('home.dashboard.assistants', { default: 'Assistants' })}
						</h3>
						<div class="flex items-center gap-3">
							<span class="text-xs text-gray-500">
								{profile.owned.assistants.total}
								{$_('home.dashboard.total', { default: 'total' })}
								· {profile.owned.assistants.published}
								{$_('home.dashboard.published', { default: 'published' })}
							</span>
							<svg
								class="h-4 w-4 text-gray-400 transition-transform {expandedOwned.assistants
									? 'rotate-180'
									: ''}"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
							>
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									stroke-width="2"
									d="M19 9l-7 7-7-7"
								/>
							</svg>
						</div>
					</button>
					{#if expandedOwned.assistants}
						<div class="border-t border-blue-100 px-5 pb-5">
							{#if profile.owned.assistants.items.length > 0}
								<ul class="divide-y divide-blue-100">
									{#each profile.owned.assistants.items as assistant}
										<li class="flex items-center justify-between gap-3 py-2">
											<div class="min-w-0 flex-1">
												<a
													href="{base}/assistants?view=detail&id={assistant.id}"
													class="block truncate text-sm font-medium text-gray-900 hover:text-blue-700 hover:underline"
												>
													{assistant.name}
												</a>
												{#if assistant.description}
													<p class="truncate text-xs text-gray-500">{assistant.description}</p>
												{/if}
											</div>
											<div class="flex flex-shrink-0 items-center gap-2">
												{#if assistant.published}
													<span
														class="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-semibold text-emerald-700"
													>
														{$_('common.published', { default: 'Published' })}
													</span>
												{:else}
													<span
														class="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-semibold text-gray-500"
													>
														Draft
													</span>
												{/if}
											</div>
										</li>
									{/each}
								</ul>
							{:else}
								<p class="py-2 text-sm text-gray-400 italic">
									{$_('home.dashboard.noResources', { default: 'No resources yet' })}
								</p>
							{/if}
							<div class="mt-3 border-t border-blue-100 pt-2">
								<a
									href="{base}/assistants"
									class="text-xs text-blue-600 hover:text-blue-800 hover:underline"
								>
									{$_('home.dashboard.manageAssistants', { default: 'Manage Assistants' })} →
								</a>
							</div>
						</div>
					{/if}
				</div>

				<!-- My Knowledge Bases -->
				<div
					class="overflow-hidden rounded-2xl border border-amber-100 bg-gradient-to-br from-amber-50 to-orange-50 shadow-sm"
				>
					<button
						class="flex w-full cursor-pointer items-center justify-between p-5 text-left transition-colors hover:bg-amber-50/50"
						onclick={() => (expandedOwned.kbs = !expandedOwned.kbs)}
						aria-expanded={expandedOwned.kbs}
					>
						<h3
							class="flex items-center gap-2 text-sm font-medium tracking-wide text-amber-600 uppercase"
						>
							<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									stroke-width="2"
									d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
								/>
							</svg>
							{$_('home.dashboard.knowledgeBases', { default: 'Knowledge Bases' })}
						</h3>
						<div class="flex items-center gap-3">
							<span class="text-xs text-gray-500">
								{profile.owned.knowledge_bases.total}
								{$_('home.dashboard.total', { default: 'total' })}
								· {profile.owned.knowledge_bases.shared}
								{$_('home.dashboard.shared', { default: 'shared' })}
							</span>
							<svg
								class="h-4 w-4 text-gray-400 transition-transform {expandedOwned.kbs
									? 'rotate-180'
									: ''}"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
							>
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									stroke-width="2"
									d="M19 9l-7 7-7-7"
								/>
							</svg>
						</div>
					</button>
					{#if expandedOwned.kbs}
						<div class="border-t border-amber-100 px-5 pb-5">
							{#if profile.owned.knowledge_bases.items.length > 0}
								<ul class="divide-y divide-amber-100">
									{#each profile.owned.knowledge_bases.items as kb}
										<li class="flex items-center justify-between gap-3 py-2">
											<div class="min-w-0 flex-1">
												<a
													href="{base}/knowledgebases?view=detail&id={kb.kb_id}"
													class="block truncate text-sm font-medium text-gray-900 hover:text-amber-700 hover:underline"
												>
													{kb.kb_name}
												</a>
											</div>
											<div class="flex flex-shrink-0 items-center gap-2">
												{#if kb.is_shared}
													<span
														class="rounded-full bg-cyan-100 px-2 py-0.5 text-xs font-semibold text-cyan-700"
													>
														{$_('home.dashboard.shared', { default: 'Shared' })}
													</span>
												{:else}
													<span
														class="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-semibold text-gray-500"
													>
														{$_('home.dashboard.private', { default: 'Private' })}
													</span>
												{/if}
											</div>
										</li>
									{/each}
								</ul>
							{:else}
								<p class="py-2 text-sm text-gray-400 italic">
									{$_('home.dashboard.noResources', { default: 'No resources yet' })}
								</p>
							{/if}
							<div class="mt-3 border-t border-amber-100 pt-2">
								<a
									href="{base}/knowledgebases"
									class="text-xs text-amber-600 hover:text-amber-800 hover:underline"
								>
									{$_('home.dashboard.createKnowledgeBase', { default: 'Create Knowledge Base' })} →
								</a>
							</div>
						</div>
					{/if}
				</div>

				<!-- My Rubrics -->
				<div
					class="overflow-hidden rounded-2xl border border-rose-100 bg-gradient-to-br from-rose-50 to-pink-50 shadow-sm"
				>
					<button
						class="flex w-full cursor-pointer items-center justify-between p-5 text-left transition-colors hover:bg-rose-50/50"
						onclick={() => (expandedOwned.rubrics = !expandedOwned.rubrics)}
						aria-expanded={expandedOwned.rubrics}
					>
						<h3
							class="flex items-center gap-2 text-sm font-medium tracking-wide text-rose-600 uppercase"
						>
							<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									stroke-width="2"
									d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"
								/>
							</svg>
							{$_('home.dashboard.rubrics', { default: 'Rubrics' })}
						</h3>
						<div class="flex items-center gap-3">
							<span class="text-xs text-gray-500">
								{profile.owned.rubrics.total}
								{$_('home.dashboard.total', { default: 'total' })}
								· {profile.owned.rubrics.public}
								{$_('home.dashboard.public', { default: 'public' })}
							</span>
							<svg
								class="h-4 w-4 text-gray-400 transition-transform {expandedOwned.rubrics
									? 'rotate-180'
									: ''}"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
							>
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									stroke-width="2"
									d="M19 9l-7 7-7-7"
								/>
							</svg>
						</div>
					</button>
					{#if expandedOwned.rubrics}
						<div class="border-t border-rose-100 px-5 pb-5">
							{#if profile.owned.rubrics.items.length > 0}
								<ul class="divide-y divide-rose-100">
									{#each profile.owned.rubrics.items as rubric}
										<li class="flex items-center justify-between gap-3 py-2">
											<div class="min-w-0 flex-1">
												<span class="block truncate text-sm font-medium text-gray-900">
													{rubric.title}
												</span>
												{#if rubric.description}
													<p class="truncate text-xs text-gray-500">{rubric.description}</p>
												{/if}
											</div>
											<div class="flex flex-shrink-0 items-center gap-2">
												{#if rubric.is_public}
													<span
														class="rounded-full bg-rose-100 px-2 py-0.5 text-xs font-semibold text-rose-700"
													>
														{$_('home.dashboard.public', { default: 'Public' })}
													</span>
												{:else}
													<span
														class="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-semibold text-gray-500"
													>
														{$_('home.dashboard.private', { default: 'Private' })}
													</span>
												{/if}
											</div>
										</li>
									{/each}
								</ul>
							{:else}
								<p class="py-2 text-sm text-gray-400 italic">
									{$_('home.dashboard.noResources', { default: 'No resources yet' })}
								</p>
							{/if}
							<div class="mt-3 border-t border-rose-100 pt-2">
								<a
									href="{base}/rubrics"
									class="text-xs text-rose-600 hover:text-rose-800 hover:underline"
								>
									{$_('home.dashboard.createRubric', { default: 'Create Rubric' })} →
								</a>
							</div>
						</div>
					{/if}
				</div>

				<!-- My Templates -->
				<div
					class="overflow-hidden rounded-2xl border border-slate-200 bg-gradient-to-br from-slate-50 to-gray-100 shadow-sm"
				>
					<button
						class="flex w-full cursor-pointer items-center justify-between p-5 text-left transition-colors hover:bg-slate-50/50"
						onclick={() => (expandedOwned.templates = !expandedOwned.templates)}
						aria-expanded={expandedOwned.templates}
					>
						<h3
							class="flex items-center gap-2 text-sm font-medium tracking-wide text-slate-600 uppercase"
						>
							<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									stroke-width="2"
									d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z"
								/>
							</svg>
							{$_('home.dashboard.templates', { default: 'Templates' })}
						</h3>
						<div class="flex items-center gap-3">
							<span class="text-xs text-gray-500">
								{profile.owned.templates.total}
								{$_('home.dashboard.total', { default: 'total' })}
								· {profile.owned.templates.shared}
								{$_('home.dashboard.shared', { default: 'shared' })}
							</span>
							<svg
								class="h-4 w-4 text-gray-400 transition-transform {expandedOwned.templates
									? 'rotate-180'
									: ''}"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
							>
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									stroke-width="2"
									d="M19 9l-7 7-7-7"
								/>
							</svg>
						</div>
					</button>
					{#if expandedOwned.templates}
						<div class="border-t border-slate-200 px-5 pb-5">
							{#if profile.owned.templates.items.length > 0}
								<ul class="divide-y divide-slate-200">
									{#each profile.owned.templates.items as template}
										<li class="flex items-center justify-between gap-3 py-2">
											<div class="min-w-0 flex-1">
												<span class="block truncate text-sm font-medium text-gray-900">
													{template.name}
												</span>
												{#if template.description}
													<p class="truncate text-xs text-gray-500">{template.description}</p>
												{/if}
											</div>
											<div class="flex flex-shrink-0 items-center gap-2">
												{#if template.is_shared}
													<span
														class="rounded-full bg-slate-200 px-2 py-0.5 text-xs font-semibold text-slate-700"
													>
														{$_('home.dashboard.shared', { default: 'Shared' })}
													</span>
												{:else}
													<span
														class="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-semibold text-gray-500"
													>
														{$_('home.dashboard.private', { default: 'Private' })}
													</span>
												{/if}
											</div>
										</li>
									{/each}
								</ul>
							{:else}
								<p class="py-2 text-sm text-gray-400 italic">
									{$_('home.dashboard.noResources', { default: 'No resources yet' })}
								</p>
							{/if}
							<div class="mt-3 border-t border-slate-200 pt-2">
								<a
									href="{base}/prompt-templates"
									class="text-xs text-slate-600 hover:text-slate-800 hover:underline"
								>
									{$_('home.dashboard.createTemplate', { default: 'Create Template' })} →
								</a>
							</div>
						</div>
					{/if}
				</div>
			</div>

			<!-- ============================================ -->
			<!-- RIGHT COLUMN: SHARED WITH ME                 -->
			<!-- ============================================ -->
			<div class="space-y-4">
				<h2 class="text-sm font-medium tracking-wide text-gray-500 uppercase">
					{$_('home.dashboard.sharedWithMe', { default: 'Shared with Me' })}
				</h2>

				{#if profile.shared_with_me.assistants.total === 0 && profile.shared_with_me.knowledge_bases.total === 0 && profile.shared_with_me.rubrics.total === 0 && profile.shared_with_me.templates.total === 0}
					<div class="rounded-2xl border border-gray-200 bg-white p-8 text-center shadow-sm">
						<div
							class="mb-3 inline-flex h-12 w-12 items-center justify-center rounded-full bg-gray-100"
						>
							<svg
								class="h-6 w-6 text-gray-400"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
							>
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									stroke-width="2"
									d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z"
								/>
							</svg>
						</div>
						<p class="text-sm text-gray-400">
							{$_('home.dashboard.noSharedResources', { default: 'Nothing shared with you yet' })}
						</p>
					</div>
				{:else}
					<!-- Shared Assistants -->
					{#if profile.shared_with_me.assistants.total > 0}
						<div class="overflow-hidden rounded-2xl border border-blue-100 bg-white shadow-sm">
							<button
								class="flex w-full cursor-pointer items-center justify-between p-5 text-left transition-colors hover:bg-blue-50/30"
								onclick={() => (expandedShared.assistants = !expandedShared.assistants)}
								aria-expanded={expandedShared.assistants}
							>
								<h3
									class="flex items-center gap-2 text-sm font-medium tracking-wide text-blue-600 uppercase"
								>
									<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path
											stroke-linecap="round"
											stroke-linejoin="round"
											stroke-width="2"
											d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
										/>
									</svg>
									{$_('home.dashboard.assistants', { default: 'Assistants' })}
								</h3>
								<div class="flex items-center gap-3">
									<span class="text-xs text-gray-500"
										>{profile.shared_with_me.assistants.total}</span
									>
									<svg
										class="h-4 w-4 text-gray-400 transition-transform {expandedShared.assistants
											? 'rotate-180'
											: ''}"
										fill="none"
										stroke="currentColor"
										viewBox="0 0 24 24"
									>
										<path
											stroke-linecap="round"
											stroke-linejoin="round"
											stroke-width="2"
											d="M19 9l-7 7-7-7"
										/>
									</svg>
								</div>
							</button>
							{#if expandedShared.assistants}
								<div class="border-t border-blue-100 px-5 pb-5">
									<ul class="divide-y divide-gray-100">
										{#each profile.shared_with_me.assistants.items as assistant}
											<li class="py-2">
												<a
													href="{base}/assistants?view=detail&id={assistant.id}"
													class="block truncate text-sm font-medium text-gray-900 hover:text-blue-700 hover:underline"
												>
													{assistant.name}
												</a>
												<p class="text-xs text-gray-400">
													{$_('home.dashboard.sharedBy', { default: 'Shared by' })}
													{assistant.owner_name || assistant.owner_email}
													{#if assistant.shared_at}
														· {formatDate(assistant.shared_at)}
													{/if}
												</p>
											</li>
										{/each}
									</ul>
								</div>
							{/if}
						</div>
					{/if}

					<!-- Shared Knowledge Bases -->
					{#if profile.shared_with_me.knowledge_bases.total > 0}
						<div class="overflow-hidden rounded-2xl border border-amber-100 bg-white shadow-sm">
							<button
								class="flex w-full cursor-pointer items-center justify-between p-5 text-left transition-colors hover:bg-amber-50/30"
								onclick={() => (expandedShared.kbs = !expandedShared.kbs)}
								aria-expanded={expandedShared.kbs}
							>
								<h3
									class="flex items-center gap-2 text-sm font-medium tracking-wide text-amber-600 uppercase"
								>
									<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path
											stroke-linecap="round"
											stroke-linejoin="round"
											stroke-width="2"
											d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
										/>
									</svg>
									{$_('home.dashboard.knowledgeBases', { default: 'Knowledge Bases' })}
								</h3>
								<div class="flex items-center gap-3">
									<span class="text-xs text-gray-500"
										>{profile.shared_with_me.knowledge_bases.total}</span
									>
									<svg
										class="h-4 w-4 text-gray-400 transition-transform {expandedShared.kbs
											? 'rotate-180'
											: ''}"
										fill="none"
										stroke="currentColor"
										viewBox="0 0 24 24"
									>
										<path
											stroke-linecap="round"
											stroke-linejoin="round"
											stroke-width="2"
											d="M19 9l-7 7-7-7"
										/>
									</svg>
								</div>
							</button>
							{#if expandedShared.kbs}
								<div class="border-t border-amber-100 px-5 pb-5">
									<ul class="divide-y divide-gray-100">
										{#each profile.shared_with_me.knowledge_bases.items as kb}
											<li class="py-2">
												<a
													href="{base}/knowledgebases?view=detail&id={kb.kb_id}"
													class="block truncate text-sm font-medium text-gray-900 hover:text-amber-700 hover:underline"
												>
													{kb.kb_name}
												</a>
												<p class="text-xs text-gray-400">
													{$_('home.dashboard.ownedBy', { default: 'by' })}
													{kb.owner_name || kb.owner_email}
												</p>
											</li>
										{/each}
									</ul>
								</div>
							{/if}
						</div>
					{/if}

					<!-- Shared Rubrics -->
					{#if profile.shared_with_me.rubrics.total > 0}
						<div class="overflow-hidden rounded-2xl border border-rose-100 bg-white shadow-sm">
							<button
								class="flex w-full cursor-pointer items-center justify-between p-5 text-left transition-colors hover:bg-rose-50/30"
								onclick={() => (expandedShared.rubrics = !expandedShared.rubrics)}
								aria-expanded={expandedShared.rubrics}
							>
								<h3
									class="flex items-center gap-2 text-sm font-medium tracking-wide text-rose-600 uppercase"
								>
									<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path
											stroke-linecap="round"
											stroke-linejoin="round"
											stroke-width="2"
											d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"
										/>
									</svg>
									{$_('home.dashboard.rubrics', { default: 'Rubrics' })}
								</h3>
								<div class="flex items-center gap-3">
									<span class="text-xs text-gray-500">{profile.shared_with_me.rubrics.total}</span>
									<svg
										class="h-4 w-4 text-gray-400 transition-transform {expandedShared.rubrics
											? 'rotate-180'
											: ''}"
										fill="none"
										stroke="currentColor"
										viewBox="0 0 24 24"
									>
										<path
											stroke-linecap="round"
											stroke-linejoin="round"
											stroke-width="2"
											d="M19 9l-7 7-7-7"
										/>
									</svg>
								</div>
							</button>
							{#if expandedShared.rubrics}
								<div class="border-t border-rose-100 px-5 pb-5">
									<ul class="divide-y divide-gray-100">
										{#each profile.shared_with_me.rubrics.items as rubric}
											<li class="py-2">
												<span class="block truncate text-sm font-medium text-gray-900">
													{rubric.title}
												</span>
												<p class="text-xs text-gray-400">
													{$_('home.dashboard.ownedBy', { default: 'by' })}
													{rubric.owner_name || rubric.owner_email}
												</p>
											</li>
										{/each}
									</ul>
								</div>
							{/if}
						</div>
					{/if}

					<!-- Shared Templates -->
					{#if profile.shared_with_me.templates.total > 0}
						<div class="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
							<button
								class="flex w-full cursor-pointer items-center justify-between p-5 text-left transition-colors hover:bg-slate-50/30"
								onclick={() => (expandedShared.templates = !expandedShared.templates)}
								aria-expanded={expandedShared.templates}
							>
								<h3
									class="flex items-center gap-2 text-sm font-medium tracking-wide text-slate-600 uppercase"
								>
									<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path
											stroke-linecap="round"
											stroke-linejoin="round"
											stroke-width="2"
											d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z"
										/>
									</svg>
									{$_('home.dashboard.templates', { default: 'Templates' })}
								</h3>
								<div class="flex items-center gap-3">
									<span class="text-xs text-gray-500">{profile.shared_with_me.templates.total}</span
									>
									<svg
										class="h-4 w-4 text-gray-400 transition-transform {expandedShared.templates
											? 'rotate-180'
											: ''}"
										fill="none"
										stroke="currentColor"
										viewBox="0 0 24 24"
									>
										<path
											stroke-linecap="round"
											stroke-linejoin="round"
											stroke-width="2"
											d="M19 9l-7 7-7-7"
										/>
									</svg>
								</div>
							</button>
							{#if expandedShared.templates}
								<div class="border-t border-slate-200 px-5 pb-5">
									<ul class="divide-y divide-gray-100">
										{#each profile.shared_with_me.templates.items as template}
											<li class="py-2">
												<span class="block truncate text-sm font-medium text-gray-900">
													{template.name}
												</span>
												<p class="text-xs text-gray-400">
													{$_('home.dashboard.ownedBy', { default: 'by' })}
													{template.owner_name || template.owner_email}
												</p>
											</li>
										{/each}
									</ul>
								</div>
							{/if}
						</div>
					{/if}
				{/if}
			</div>
		</div>
	{:else}
		<!-- Empty state -->
		<div class="py-12 text-center">
			<div class="mb-4 inline-flex h-16 w-16 items-center justify-center rounded-full bg-gray-100">
				<svg class="h-8 w-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
					/>
				</svg>
			</div>
			<p class="mb-4 text-gray-500">
				{$_('home.dashboard.loading', { default: 'Loading your dashboard...' })}
			</p>
			<button
				onclick={onRetry}
				class="inline-flex items-center gap-2 rounded-lg bg-[#2271b3] px-4 py-2 text-sm text-white transition-colors hover:bg-[#195a91]"
			>
				{$_('home.dashboard.retry', { default: 'Try Again' })}
			</button>
		</div>
	{/if}
</div>
