<script>
	/**
	 * ChatAnalytics Component
	 * Displays chat analytics and conversation history for a learning assistant
	 *
	 * Features:
	 * - Usage statistics cards
	 * - Date range filtering
	 * - Paginated chat list
	 * - Inline expandable chat details (no modal)
	 *
	 * Created: December 27, 2025
	 * Updated: December 28, 2025 - Replaced modal with inline expandable rows
	 */

	import { onMount } from 'svelte';
	import { _ } from '$lib/i18n';
	import Pagination from '$lib/components/common/Pagination.svelte';
	import {
		getAssistantChats,
		getAssistantStats,
		getAssistantTimeline,
		getChatDetail,
		formatDate,
		formatShortDate
	} from '$lib/services/analyticsService';

	// Props
	let { assistant = null } = $props();

	// State
	let loading = $state(true);
	let error = $state('');
	let stats = $state(null);
	let chats = $state([]);
	let timeline = $state([]);

	// Pagination state
	let currentPage = $state(1);
	let totalPages = $state(1);
	let totalItems = $state(0);
	let itemsPerPage = $state(20);

	// Filter state
	let startDate = $state('');
	let endDate = $state('');
	let selectedUserId = $state('');
	let searchContent = $state('');
	let showFilters = $state(false);
	let uniqueUsers = $state([]);

	// Expanded chats state (replaces modal)
	// Map of chat.id -> { loading: boolean, messages: [], error: string|null }
	let expandedChats = $state({});

	// Derived values
	let assistantId = $derived(assistant?.id);
	let assistantName = $derived(assistant?.name || 'Assistant');
	let hasActiveFilters = $derived(startDate || endDate || selectedUserId || searchContent);
	// Only show timeline if we have at least 3 days with activity - otherwise it's not meaningful
	let hasTimelineData = $derived(
		timeline.length >= 3 && timeline.filter((t) => t.chat_count > 0).length >= 2
	);

	// Load data on mount and when assistant changes
	$effect(() => {
		if (assistantId) {
			loadData();
		}
	});

	async function loadData() {
		loading = true;
		error = '';
		// Clear expanded chats when reloading data
		expandedChats = {};

		try {
			// Load stats and chats in parallel
			const [statsResult, chatsResult] = await Promise.all([
				getAssistantStats(assistantId),
				getAssistantChats(assistantId, {
					page: currentPage,
					perPage: itemsPerPage,
					startDate: startDate || undefined,
					endDate: endDate || undefined,
					userId: selectedUserId || undefined,
					searchContent: searchContent || undefined
				})
			]);

			stats = statsResult.stats;
			chats = chatsResult.chats;
			totalItems = chatsResult.total;
			totalPages = chatsResult.total_pages;

			// Extract unique users from all chats for filter dropdown
			// Only update on first load or when no user filter is active
			if (!selectedUserId && chatsResult.chats) {
				const userMap = new Map();
				chatsResult.chats.forEach((chat) => {
					if (chat.user_id && !userMap.has(chat.user_id)) {
						userMap.set(chat.user_id, {
							id: chat.user_id,
							name: chat.user_name || 'Anonymous'
						});
					}
				});
				uniqueUsers = Array.from(userMap.values());
			}

			// Also load timeline for recent activity
			try {
				const timelineResult = await getAssistantTimeline(assistantId, {
					period: 'day'
				});
				timeline = timelineResult.data.slice(-14); // Last 14 days
			} catch (e) {
				console.warn('Failed to load timeline:', e);
				timeline = [];
			}
		} catch (e) {
			console.error('Error loading analytics:', e);
			error = e.response?.data?.detail || e.message || 'Failed to load analytics';
		} finally {
			loading = false;
		}
	}

	async function handleFilter() {
		currentPage = 1;
		await loadData();
	}

	async function handleClearFilter() {
		startDate = '';
		endDate = '';
		selectedUserId = '';
		searchContent = '';
		showFilters = false;
		currentPage = 1;
		await loadData();
	}

	function handlePageChange(event) {
		currentPage = event.detail.page;
		loadData();
	}

	function handleItemsPerPageChange(event) {
		itemsPerPage = event.detail.itemsPerPage;
		currentPage = 1;
		loadData();
	}

	/**
	 * Toggle chat expansion - loads detail on first open
	 */
	async function toggleChatExpansion(chat) {
		const chatId = chat.id;

		// If already expanded, collapse it
		if (expandedChats[chatId]) {
			const { [chatId]: removed, ...rest } = expandedChats;
			expandedChats = rest;
			return;
		}

		// Expand and load details
		expandedChats = {
			...expandedChats,
			[chatId]: { loading: true, messages: [], error: null }
		};

		try {
			const detail = await getChatDetail(assistantId, chatId);
			expandedChats = {
				...expandedChats,
				[chatId]: { loading: false, messages: detail.messages || [], error: null }
			};
		} catch (e) {
			console.error('Error loading chat detail:', e);
			expandedChats = {
				...expandedChats,
				[chatId]: { loading: false, messages: [], error: 'Failed to load messages' }
			};
		}
	}

	/**
	 * Check if a chat is expanded
	 */
	function isExpanded(chatId) {
		return !!expandedChats[chatId];
	}
</script>

<div class="space-y-6">
	<!-- Header -->
	<div class="flex items-center justify-between">
		<div class="flex items-baseline gap-3">
			<h2 class="text-xl font-semibold text-gray-800">Activity</h2>
			<p class="text-sm text-gray-500">Chat history and usage for {assistantName}</p>
		</div>
		<button
			type="button"
			onclick={loadData}
			disabled={loading}
			class="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm hover:bg-gray-50 disabled:opacity-50"
		>
			{loading ? 'Loading...' : '🔄 Refresh'}
		</button>
	</div>

	{#if error}
		<div class="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-red-700">
			{error}
		</div>
	{/if}

	{#if loading && !stats}
		<div class="flex items-center justify-center py-12">
			<div class="text-gray-500">Loading analytics...</div>
		</div>
	{:else}
		<!-- Stats Summary (Compact) -->
		{#if stats}
			<div class="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
				<div class="flex items-center gap-1.5">
					<span class="text-gray-400">💬</span>
					<span class="font-semibold text-gray-900">{stats.total_chats}</span>
					<span class="text-gray-500">{$_('analytics.stats.chats')}</span>
				</div>
				<div class="flex items-center gap-1.5">
					<span class="text-gray-400">👥</span>
					<span class="font-semibold text-gray-900">{stats.unique_users}</span>
					<span class="text-gray-500">{$_('analytics.stats.users')}</span>
				</div>
				<div class="flex items-center gap-1.5">
					<span class="text-gray-400">✉️</span>
					<span class="font-semibold text-gray-900">{stats.total_messages}</span>
					<span class="text-gray-500">{$_('analytics.stats.messages')}</span>
				</div>
				<div class="flex items-center gap-1.5 text-gray-500">
					<span class="text-gray-400">⌀</span>
					<span class="font-medium text-gray-700">{stats.avg_messages_per_chat}</span>
					<span>{$_('analytics.stats.messagesPerChat')}</span>
				</div>
			</div>
		{/if}

		<!-- Activity Timeline (Simple Bar Chart) - Only show if there's meaningful data -->
		{#if hasTimelineData}
			<div class="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
				<h3 class="mb-3 text-sm font-medium text-gray-700">Recent Activity (Last 14 Days)</h3>
				<div class="flex h-24 items-end justify-between gap-1">
					{#each timeline as point}
						{@const maxChats = Math.max(...timeline.map((t) => t.chat_count)) || 1}
						{@const height = (point.chat_count / maxChats) * 100}
						<div class="group flex flex-1 flex-col items-center">
							<div
								class="w-full cursor-default rounded-t bg-indigo-500 transition-all duration-300 hover:bg-indigo-600"
								style="height: {point.chat_count > 0 ? Math.max(height, 8) : 2}%"
								title="{point.date}: {point.chat_count} chat{point.chat_count !== 1
									? 's'
									: ''}, {point.message_count} message{point.message_count !== 1 ? 's' : ''}"
							></div>
							<div class="mt-1 text-xs whitespace-nowrap text-gray-400">
								{point.date.slice(-5)}
							</div>
						</div>
					{/each}
				</div>
			</div>
		{/if}

		<!-- Filter Section - Collapsible -->
		<div class="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
			<!-- Filter Toggle Header -->
			<button
				type="button"
				onclick={() => (showFilters = !showFilters)}
				class="flex w-full items-center justify-between px-4 py-3 transition-colors hover:bg-gray-50"
			>
				<div class="flex items-center gap-2">
					<svg
						class="h-4 w-4 text-gray-500 transition-transform {showFilters ? 'rotate-90' : ''}"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M9 5l7 7-7 7"
						/>
					</svg>
					<span class="text-sm font-medium text-gray-700">
						{#if hasActiveFilters}
							Filters Active
						{:else}
							Filter Results
						{/if}
					</span>
					{#if hasActiveFilters}
						<span
							class="inline-flex items-center rounded-full bg-indigo-100 px-2 py-0.5 text-xs font-medium text-indigo-800"
						>
							{(startDate ? 1 : 0) +
								(endDate ? 1 : 0) +
								(selectedUserId ? 1 : 0) +
								(searchContent ? 1 : 0)} active
						</span>
					{/if}
				</div>
				<span class="text-xs text-gray-400">
					{showFilters ? 'Click to collapse' : 'Click to expand'}
				</span>
			</button>

			<!-- Filter Controls (Collapsible) -->
			{#if showFilters}
				<div class="border-t border-gray-100 bg-gray-50 px-4 pt-2 pb-4">
					<!-- Content Search - Full Width on Top -->
					<div class="mb-4 w-full">
						<label for="content-search" class="mb-1 block text-xs font-medium text-gray-600">
							Search Content
						</label>
						<div class="flex gap-2">
							<input
								type="text"
								id="content-search"
								bind:value={searchContent}
								placeholder="Search in chat messages..."
								class="flex-1 rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm focus:border-indigo-500 focus:ring-indigo-500"
							/>
							<div class="flex gap-1">
								<button
									type="button"
									onclick={() => (searchContent += '%')}
									title="Insert wildcard (%) - matches any characters"
									class="rounded border border-gray-300 bg-gray-100 px-2 py-1.5 text-xs text-gray-700 hover:bg-gray-200"
								>
									%
								</button>
								<button
									type="button"
									onclick={() => (searchContent += '_')}
									title="Insert single char wildcard (_) - matches one character"
									class="rounded border border-gray-300 bg-gray-100 px-2 py-1.5 text-xs text-gray-700 hover:bg-gray-200"
								>
									_
								</button>
							</div>
						</div>
						<p class="mt-1 text-xs text-gray-500">
							Use % for any characters, _ for single character
						</p>
					</div>

					<!-- Other Filters -->
					<div class="flex flex-wrap items-end gap-4">
						<!-- Date Range -->
						<div class="flex items-end gap-2">
							<div>
								<label for="start-date" class="mb-1 block text-xs font-medium text-gray-600">
									From
								</label>
								<input
									type="date"
									id="start-date"
									bind:value={startDate}
									class="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm focus:border-indigo-500 focus:ring-indigo-500"
								/>
							</div>
							<span class="pb-2 text-gray-400">–</span>
							<div>
								<label for="end-date" class="mb-1 block text-xs font-medium text-gray-600">
									To
								</label>
								<input
									type="date"
									id="end-date"
									bind:value={endDate}
									class="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm focus:border-indigo-500 focus:ring-indigo-500"
								/>
							</div>
						</div>

						<!-- User Filter -->
						{#if uniqueUsers.length > 0}
							<div>
								<label for="user-filter" class="mb-1 block text-xs font-medium text-gray-600">
									User
								</label>
								<select
									id="user-filter"
									bind:value={selectedUserId}
									class="min-w-[150px] rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm focus:border-indigo-500 focus:ring-indigo-500"
								>
									<option value="">All users</option>
									{#each uniqueUsers as user}
										<option value={user.id}>{user.name}</option>
									{/each}
								</select>
							</div>
						{/if}

						<!-- Action Buttons -->
						<div class="flex gap-2">
							<button
								type="button"
								onclick={handleFilter}
								class="rounded-md bg-indigo-600 px-4 py-1.5 text-sm text-white transition-colors hover:bg-indigo-700 focus:ring-2 focus:ring-indigo-500"
							>
								Apply
							</button>
							{#if hasActiveFilters}
								<button
									type="button"
									onclick={handleClearFilter}
									class="rounded-md border border-gray-300 bg-white px-4 py-1.5 text-sm text-gray-700 transition-colors hover:bg-gray-50"
								>
									Clear all
								</button>
							{/if}
						</div>
					</div>
				</div>
			{/if}
		</div>

		<!-- Chats Table -->
		<div class="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
			<div class="border-b border-gray-200 px-4 py-3">
				<h3 class="text-sm font-medium text-gray-700">Chat History</h3>
			</div>

			{#if chats.length === 0}
				<div class="px-4 py-8 text-center text-gray-500">
					No chat conversations found for this assistant.
				</div>
			{:else}
				<div class="overflow-x-auto">
					<table class="min-w-full divide-y divide-gray-200">
						<thead class="bg-gray-50">
							<tr>
								<th
									class="w-10 px-4 py-3 text-left text-xs font-medium tracking-wider text-gray-500 uppercase"
								>
									<!-- Eye toggle column -->
								</th>
								<th
									class="px-4 py-3 text-left text-xs font-medium tracking-wider text-gray-500 uppercase"
								>
									Date
								</th>
								<th
									class="px-4 py-3 text-left text-xs font-medium tracking-wider text-gray-500 uppercase"
								>
									User
								</th>
								<th
									class="px-4 py-3 text-left text-xs font-medium tracking-wider text-gray-500 uppercase"
								>
									Title
								</th>
								<th
									class="px-4 py-3 text-left text-xs font-medium tracking-wider text-gray-500 uppercase"
								>
									Messages
								</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-gray-200 bg-white">
							{#each chats as chat}
								{@const expanded = isExpanded(chat.id)}
								{@const chatDetail = expandedChats[chat.id]}
								<!-- Main row -->
								<tr
									class="cursor-pointer transition-colors hover:bg-gray-50 {expanded
										? 'bg-indigo-50'
										: ''}"
									onclick={() => toggleChatExpansion(chat)}
								>
									<td class="px-4 py-3 text-center whitespace-nowrap">
										<button
											type="button"
											class="text-xl transition-all duration-200 hover:scale-110 {expanded
												? 'text-indigo-600'
												: 'text-gray-400 hover:text-gray-600'}"
											title={expanded ? 'Hide conversation' : 'Show conversation'}
											aria-label={expanded ? 'Hide conversation' : 'Show conversation'}
										>
											{#if expanded}
												<!-- Open eye - conversation visible -->
												<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
													<path
														stroke-linecap="round"
														stroke-linejoin="round"
														stroke-width="2"
														d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
													/>
													<path
														stroke-linecap="round"
														stroke-linejoin="round"
														stroke-width="2"
														d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
													/>
												</svg>
											{:else}
												<!-- Closed eye - conversation hidden -->
												<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
													<path
														stroke-linecap="round"
														stroke-linejoin="round"
														stroke-width="2"
														d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21"
													/>
												</svg>
											{/if}
										</button>
									</td>
									<td class="px-4 py-3 text-sm whitespace-nowrap text-gray-500">
										{formatShortDate(chat.created_at)}
									</td>
									<td class="px-4 py-3 text-sm whitespace-nowrap text-gray-900">
										{chat.user_name || 'Anonymous'}
									</td>
									<td class="max-w-xs truncate px-4 py-3 text-sm text-gray-900">
										{chat.title || 'Untitled Chat'}
									</td>
									<td class="px-4 py-3 text-sm whitespace-nowrap text-gray-500">
										{chat.message_count}
									</td>
								</tr>

								<!-- Expandable content row -->
								{#if expanded}
									<tr class="bg-slate-50">
										<td colspan="5" class="p-0">
											<div class="mx-4 my-3 border-l-4 border-indigo-400">
												<!-- Chat header in expanded view -->
												<div
													class="border-b border-slate-200 bg-gradient-to-r from-slate-100 to-transparent px-4 py-2"
												>
													<div class="flex items-center justify-between">
														<div class="flex items-center gap-3">
															<span class="text-lg">💬</span>
															<div>
																<span class="font-medium text-gray-800"
																	>{chat.title || 'Chat Conversation'}</span
																>
																<span class="ml-2 text-sm text-gray-500">
																	{chat.user_name || 'User'} • {formatDate(chat.created_at)}
																</span>
															</div>
														</div>
														<button
															type="button"
															onclick={(e) => {
																e.stopPropagation();
																toggleChatExpansion(chat);
															}}
															class="rounded p-1 text-gray-400 transition-colors hover:bg-slate-200 hover:text-gray-600"
															title="Hide conversation"
														>
															<svg
																class="h-4 w-4"
																fill="none"
																stroke="currentColor"
																viewBox="0 0 24 24"
															>
																<path
																	stroke-linecap="round"
																	stroke-linejoin="round"
																	stroke-width="2"
																	d="M5 15l7-7 7 7"
																/>
															</svg>
														</button>
													</div>
												</div>

												<!-- Messages scrollable container -->
												<div class="max-h-80 space-y-3 overflow-y-auto bg-white px-4 py-3">
													{#if chatDetail?.loading}
														<div class="flex items-center justify-center py-6">
															<div class="flex items-center gap-2 text-gray-500">
																<svg class="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
																	<circle
																		class="opacity-25"
																		cx="12"
																		cy="12"
																		r="10"
																		stroke="currentColor"
																		stroke-width="4"
																	></circle>
																	<path
																		class="opacity-75"
																		fill="currentColor"
																		d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
																	></path>
																</svg>
																<span>Loading conversation...</span>
															</div>
														</div>
													{:else if chatDetail?.error}
														<div
															class="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
														>
															{chatDetail.error}
														</div>
													{:else if chatDetail?.messages && chatDetail.messages.length > 0}
														{#each chatDetail.messages as message}
															<div
																class="flex {message.role === 'user'
																	? 'justify-end'
																	: 'justify-start'}"
															>
																<div
																	class="max-w-[85%] {message.role === 'user'
																		? 'rounded-2xl rounded-br-md bg-indigo-600 text-white'
																		: 'rounded-2xl rounded-bl-md bg-gray-100 text-gray-900'} px-4 py-2.5 shadow-sm"
																>
																	<div
																		class="text-xs {message.role === 'user'
																			? 'text-indigo-200'
																			: 'text-gray-500'} mb-1 flex items-center gap-1"
																	>
																		{#if message.role === 'user'}
																			<svg class="h-3 w-3" fill="currentColor" viewBox="0 0 20 20">
																				<path
																					fill-rule="evenodd"
																					d="M10 9a3 3 0 100-6 3 3 0 000 6zm-7 9a7 7 0 1114 0H3z"
																					clip-rule="evenodd"
																				/>
																			</svg>
																			<span>User</span>
																		{:else}
																			<svg class="h-3 w-3" fill="currentColor" viewBox="0 0 20 20">
																				<path d="M2 10a8 8 0 018-8v8h8a8 8 0 11-16 0z" />
																				<path d="M12 2.252A8.014 8.014 0 0117.748 8H12V2.252z" />
																			</svg>
																			<span>Assistant</span>
																		{/if}
																		{#if message.timestamp}
																			<span class="ml-1 opacity-75"
																				>• {formatDate(message.timestamp)}</span
																			>
																		{/if}
																	</div>
																	<div
																		class="text-sm leading-relaxed break-words whitespace-pre-wrap"
																	>
																		{message.content}
																	</div>
																</div>
															</div>
														{/each}
													{:else}
														<div class="py-6 text-center text-sm text-gray-500">
															No messages in this conversation.
														</div>
													{/if}
												</div>
											</div>
										</td>
									</tr>
								{/if}
							{/each}
						</tbody>
					</table>
				</div>

				<!-- Pagination -->
				<Pagination
					{currentPage}
					{totalPages}
					{totalItems}
					{itemsPerPage}
					on:pageChange={handlePageChange}
					on:itemsPerPageChange={handleItemsPerPageChange}
				/>
			{/if}
		</div>
	{/if}
</div>
