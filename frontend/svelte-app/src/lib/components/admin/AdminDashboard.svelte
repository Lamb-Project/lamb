<script>
	import { _ } from '$lib/i18n';

	/**
	 * @typedef {Object} SystemStats
	 * @property {{ total: number, enabled: number, disabled: number, creators: number, end_users: number }} users
	 * @property {{ total: number, active: number, inactive: number }} organizations
	 * @property {{ total: number, published: number, unpublished: number }} assistants
	 * @property {{ total: number, shared: number }} knowledge_bases
	 * @property {{ total: number, public: number }} rubrics
	 * @property {{ total: number, shared: number }} templates
	 */

	// Props
	/** @type {{ systemStats?: SystemStats | null, isLoading?: boolean, error?: string | null, localeLoaded?: boolean, onRefresh?: () => void, onShowUsers?: () => void, onShowOrganizations?: () => void }} */
	let {
		systemStats = null,
		isLoading = false,
		error = null,
		localeLoaded = true,
		onRefresh = () => {},
		onShowUsers = () => {},
		onShowOrganizations = () => {}
	} = $props();
</script>

<div>
	<h1 class="mb-2 text-2xl font-semibold text-gray-800">
		{localeLoaded
			? $_('admin.dashboard.title', { default: 'System Dashboard' })
			: 'System Dashboard'}
	</h1>
	<p class="mb-8 text-sm text-gray-500">
		{localeLoaded
			? $_('admin.dashboard.welcome', { default: 'Overview of your LAMB platform statistics' })
			: 'Overview of your LAMB platform statistics'}
	</p>

	{#if isLoading}
		<!-- Loading skeleton -->
		<div class="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
			{#each Array(6) as _}
				<div class="animate-pulse rounded-2xl border border-gray-100 bg-white p-6 shadow-sm">
					<div class="mb-4 h-4 w-1/3 rounded bg-gray-200"></div>
					<div class="mb-4 h-10 w-1/2 rounded bg-gray-200"></div>
					<div class="flex gap-4">
						<div class="h-3 w-1/4 rounded bg-gray-200"></div>
						<div class="h-3 w-1/4 rounded bg-gray-200"></div>
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
			<button onclick={onRefresh} class="mt-3 text-sm text-red-600 underline hover:text-red-800">
				Try again
			</button>
		</div>
	{:else if systemStats}
		<!-- Stats Grid -->
		<div class="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
			<!-- Users Card -->
			<!-- svelte-ignore a11y_no_static_element_interactions -->
			<div
				class="cursor-pointer rounded-2xl border border-blue-100 bg-gradient-to-br from-blue-50 to-indigo-50 p-6 shadow-sm transition-all hover:scale-[1.02] hover:shadow-md"
				onclick={onShowUsers}
				onkeydown={(e) => e.key === 'Enter' && onShowUsers()}
				role="button"
				tabindex="0"
			>
				<div class="mb-4 flex items-center justify-between">
					<h3 class="text-sm font-medium tracking-wide text-blue-600 uppercase">Users</h3>
					<div class="rounded-xl bg-blue-100 p-2">
						<svg
							class="h-6 w-6 text-blue-600"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
						>
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="2"
								d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5-9a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0z"
							/>
						</svg>
					</div>
				</div>
				<div class="mb-3 text-4xl font-bold text-gray-900">{systemStats.users.total}</div>
				<div class="flex flex-wrap gap-x-4 gap-y-1 text-sm">
					<span class="flex items-center gap-1 text-emerald-600">
						<span class="h-2 w-2 rounded-full bg-emerald-500"></span>
						{systemStats.users.enabled} active
					</span>
					{#if systemStats.users.disabled > 0}
						<span class="flex items-center gap-1 text-gray-400">
							<span class="h-2 w-2 rounded-full bg-gray-300"></span>
							{systemStats.users.disabled} disabled
						</span>
					{/if}
				</div>
				<div class="mt-3 flex gap-4 border-t border-blue-100 pt-3 text-xs text-gray-500">
					<span>{systemStats.users.creators} creators</span>
					<span>{systemStats.users.end_users} end users</span>
				</div>
			</div>

			<!-- Organizations Card -->
			<div
				class="rounded-2xl border border-violet-100 bg-gradient-to-br from-violet-50 to-purple-50 p-6 shadow-sm transition-all hover:scale-[1.02] hover:shadow-md"
			>
				<div class="mb-4 flex items-center justify-between">
					<h3 class="text-sm font-medium tracking-wide text-violet-600 uppercase">Organizations</h3>
					<div class="rounded-xl bg-violet-100 p-2">
						<svg
							class="h-6 w-6 text-violet-600"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
						>
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="2"
								d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"
							/>
						</svg>
					</div>
				</div>
				<div class="mb-3 text-4xl font-bold text-gray-900">{systemStats.organizations.total}</div>
				<div class="flex flex-wrap gap-x-4 gap-y-1 text-sm">
					<span class="flex items-center gap-1 text-emerald-600">
						<span class="h-2 w-2 rounded-full bg-emerald-500"></span>
						{systemStats.organizations.active} active
					</span>
					{#if systemStats.organizations.inactive > 0}
						<span class="flex items-center gap-1 text-gray-400">
							<span class="h-2 w-2 rounded-full bg-gray-300"></span>
							{systemStats.organizations.inactive} inactive
						</span>
					{/if}
				</div>
			</div>

			<!-- Assistants Card -->
			<div
				class="rounded-2xl border border-emerald-100 bg-gradient-to-br from-emerald-50 to-teal-50 p-6 shadow-sm transition-all hover:scale-[1.02] hover:shadow-md"
			>
				<div class="mb-4 flex items-center justify-between">
					<h3 class="text-sm font-medium tracking-wide text-emerald-600 uppercase">Assistants</h3>
					<div class="rounded-xl bg-emerald-100 p-2">
						<svg
							class="h-6 w-6 text-emerald-600"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
						>
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="2"
								d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
							/>
						</svg>
					</div>
				</div>
				<div class="mb-3 text-4xl font-bold text-gray-900">{systemStats.assistants.total}</div>
				<div class="flex flex-wrap gap-x-4 gap-y-1 text-sm">
					<span class="flex items-center gap-1 text-emerald-600">
						<span class="h-2 w-2 rounded-full bg-emerald-500"></span>
						{systemStats.assistants.published} published
					</span>
					<span class="flex items-center gap-1 text-amber-600">
						<span class="h-2 w-2 rounded-full bg-amber-400"></span>
						{systemStats.assistants.unpublished} drafts
					</span>
				</div>
			</div>

			<!-- Knowledge Bases Card -->
			<div
				class="rounded-2xl border border-amber-100 bg-gradient-to-br from-amber-50 to-orange-50 p-6 shadow-sm transition-all hover:scale-[1.02] hover:shadow-md"
			>
				<div class="mb-4 flex items-center justify-between">
					<h3 class="text-sm font-medium tracking-wide text-amber-600 uppercase">
						Knowledge Bases
					</h3>
					<div class="rounded-xl bg-amber-100 p-2">
						<svg
							class="h-6 w-6 text-amber-600"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
						>
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="2"
								d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
							/>
						</svg>
					</div>
				</div>
				<div class="mb-3 text-4xl font-bold text-gray-900">{systemStats.knowledge_bases.total}</div>
				<div class="flex flex-wrap gap-x-4 gap-y-1 text-sm">
					<span class="flex items-center gap-1 text-cyan-600">
						<span class="h-2 w-2 rounded-full bg-cyan-500"></span>
						{systemStats.knowledge_bases.shared} shared
					</span>
					<span class="flex items-center gap-1 text-gray-400">
						<span class="h-2 w-2 rounded-full bg-gray-300"></span>
						{systemStats.knowledge_bases.total - systemStats.knowledge_bases.shared} private
					</span>
				</div>
			</div>

			<!-- Rubrics Card -->
			<div
				class="rounded-2xl border border-rose-100 bg-gradient-to-br from-rose-50 to-pink-50 p-6 shadow-sm transition-all hover:scale-[1.02] hover:shadow-md"
			>
				<div class="mb-4 flex items-center justify-between">
					<h3 class="text-sm font-medium tracking-wide text-rose-600 uppercase">Rubrics</h3>
					<div class="rounded-xl bg-rose-100 p-2">
						<svg
							class="h-6 w-6 text-rose-600"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
						>
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="2"
								d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"
							/>
						</svg>
					</div>
				</div>
				<div class="mb-3 text-4xl font-bold text-gray-900">{systemStats.rubrics.total}</div>
				<div class="flex flex-wrap gap-x-4 gap-y-1 text-sm">
					<span class="flex items-center gap-1 text-rose-600">
						<span class="h-2 w-2 rounded-full bg-rose-500"></span>
						{systemStats.rubrics.public} public
					</span>
					<span class="flex items-center gap-1 text-gray-400">
						<span class="h-2 w-2 rounded-full bg-gray-300"></span>
						{systemStats.rubrics.total - systemStats.rubrics.public} private
					</span>
				</div>
			</div>

			<!-- Templates Card -->
			<div
				class="rounded-2xl border border-slate-200 bg-gradient-to-br from-slate-50 to-gray-100 p-6 shadow-sm transition-all hover:scale-[1.02] hover:shadow-md"
			>
				<div class="mb-4 flex items-center justify-between">
					<h3 class="text-sm font-medium tracking-wide text-slate-600 uppercase">
						Prompt Templates
					</h3>
					<div class="rounded-xl bg-slate-200 p-2">
						<svg
							class="h-6 w-6 text-slate-600"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
						>
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="2"
								d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z"
							/>
						</svg>
					</div>
				</div>
				<div class="mb-3 text-4xl font-bold text-gray-900">{systemStats.templates.total}</div>
				<div class="flex flex-wrap gap-x-4 gap-y-1 text-sm">
					<span class="flex items-center gap-1 text-slate-600">
						<span class="h-2 w-2 rounded-full bg-slate-500"></span>
						{systemStats.templates.shared} shared
					</span>
					<span class="flex items-center gap-1 text-gray-400">
						<span class="h-2 w-2 rounded-full bg-gray-300"></span>
						{systemStats.templates.total - systemStats.templates.shared} private
					</span>
				</div>
			</div>
		</div>

		<!-- Quick Actions -->
		<div class="mt-8 border-t border-gray-200 pt-8">
			<h3 class="mb-4 text-sm font-medium tracking-wide text-gray-500 uppercase">Quick Actions</h3>
			<div class="flex flex-wrap gap-3">
				<button
					onclick={onShowUsers}
					class="inline-flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm text-gray-700 transition-colors hover:border-gray-300 hover:bg-gray-50"
				>
					<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197"
						/>
					</svg>
					Manage Users
				</button>
				<button
					onclick={onShowOrganizations}
					class="inline-flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm text-gray-700 transition-colors hover:border-gray-300 hover:bg-gray-50"
				>
					<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5"
						/>
					</svg>
					Manage Organizations
				</button>
				<button
					onclick={onRefresh}
					class="inline-flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm text-gray-700 transition-colors hover:border-gray-300 hover:bg-gray-50"
				>
					<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
						/>
					</svg>
					Refresh Stats
				</button>
			</div>
		</div>
	{:else}
		<!-- Initial state - prompt to load -->
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
			<p class="mb-4 text-gray-500">Loading system statistics...</p>
			<button
				onclick={onRefresh}
				class="bg-brand hover:bg-brand-hover inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm text-white transition-colors"
			>
				Load Statistics
			</button>
		</div>
	{/if}
</div>
