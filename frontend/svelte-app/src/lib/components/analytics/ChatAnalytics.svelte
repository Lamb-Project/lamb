<script>
    /**
     * ChatAnalytics Component
     * Displays chat analytics and conversation history for a learning assistant
     * 
     * Features:
     * - Usage statistics cards
     * - Date range filtering
     * - Paginated chat list
     * - Chat detail modal with full conversation
     * 
     * Created: December 27, 2025
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
    
    // Modal state
    let showChatModal = $state(false);
    let selectedChat = $state(null);
    let loadingChatDetail = $state(false);
    
    // Derived values
    let assistantId = $derived(assistant?.id);
    let assistantName = $derived(assistant?.name || 'Assistant');
    
    // Load data on mount and when assistant changes
    $effect(() => {
        if (assistantId) {
            loadData();
        }
    });
    
    async function loadData() {
        loading = true;
        error = '';
        
        try {
            // Load stats and chats in parallel
            const [statsResult, chatsResult] = await Promise.all([
                getAssistantStats(assistantId),
                getAssistantChats(assistantId, {
                    page: currentPage,
                    perPage: itemsPerPage,
                    startDate: startDate || undefined,
                    endDate: endDate || undefined
                })
            ]);
            
            stats = statsResult.stats;
            chats = chatsResult.chats;
            totalItems = chatsResult.total;
            totalPages = chatsResult.total_pages;
            
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
    
    async function openChatDetail(chat) {
        selectedChat = chat;
        showChatModal = true;
        loadingChatDetail = true;
        
        try {
            const detail = await getChatDetail(assistantId, chat.id);
            selectedChat = { ...chat, ...detail };
        } catch (e) {
            console.error('Error loading chat detail:', e);
            selectedChat = { ...chat, messages: [], error: 'Failed to load messages' };
        } finally {
            loadingChatDetail = false;
        }
    }
    
    function closeChatModal() {
        showChatModal = false;
        selectedChat = null;
    }
    
    // Handle escape key to close modal
    function handleKeydown(event) {
        if (event.key === 'Escape' && showChatModal) {
            closeChatModal();
        }
    }
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
        <h2 class="text-xl font-semibold text-gray-800">
            📊 Chat Analytics
        </h2>
        <button
            type="button"
            onclick={loadData}
            disabled={loading}
            class="px-3 py-1.5 text-sm bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
        >
            {loading ? 'Loading...' : '🔄 Refresh'}
        </button>
    </div>
    
    {#if error}
        <div class="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md">
            {error}
        </div>
    {/if}
    
    {#if loading && !stats}
        <div class="flex items-center justify-center py-12">
            <div class="text-gray-500">Loading analytics...</div>
        </div>
    {:else}
        <!-- Stats Cards -->
        {#if stats}
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div class="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
                    <div class="text-sm text-gray-500 mb-1">Total Chats</div>
                    <div class="text-2xl font-bold text-gray-900">{stats.total_chats}</div>
                </div>
                <div class="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
                    <div class="text-sm text-gray-500 mb-1">Unique Users</div>
                    <div class="text-2xl font-bold text-gray-900">{stats.unique_users}</div>
                </div>
                <div class="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
                    <div class="text-sm text-gray-500 mb-1">Total Messages</div>
                    <div class="text-2xl font-bold text-gray-900">{stats.total_messages}</div>
                </div>
                <div class="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
                    <div class="text-sm text-gray-500 mb-1">Avg Messages/Chat</div>
                    <div class="text-2xl font-bold text-gray-900">{stats.avg_messages_per_chat}</div>
                </div>
            </div>
        {/if}
        
        <!-- Activity Timeline (Simple Bar Chart) -->
        {#if timeline.length > 0}
            <div class="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
                <h3 class="text-sm font-medium text-gray-700 mb-3">Recent Activity (Last 14 Days)</h3>
                <div class="flex items-end justify-between gap-1 h-24">
                    {#each timeline as point}
                        {@const maxChats = Math.max(...timeline.map(t => t.chat_count)) || 1}
                        {@const height = (point.chat_count / maxChats) * 100}
                        <div class="flex flex-col items-center flex-1">
                            <div 
                                class="w-full bg-indigo-500 rounded-t transition-all duration-300"
                                style="height: {Math.max(height, 4)}%"
                                title="{point.date}: {point.chat_count} chats, {point.message_count} messages"
                            ></div>
                            <div class="text-xs text-gray-400 mt-1 transform rotate-45 origin-left w-8 truncate">
                                {point.date.slice(-5)}
                            </div>
                        </div>
                    {/each}
                </div>
            </div>
        {/if}
        
        <!-- Filter Section -->
        <div class="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
            <div class="flex flex-wrap items-end gap-4">
                <div>
                    <label for="start-date" class="block text-sm font-medium text-gray-700 mb-1">
                        Start Date
                    </label>
                    <input
                        type="date"
                        id="start-date"
                        bind:value={startDate}
                        class="px-3 py-1.5 border border-gray-300 rounded-md text-sm focus:ring-indigo-500 focus:border-indigo-500"
                    />
                </div>
                <div>
                    <label for="end-date" class="block text-sm font-medium text-gray-700 mb-1">
                        End Date
                    </label>
                    <input
                        type="date"
                        id="end-date"
                        bind:value={endDate}
                        class="px-3 py-1.5 border border-gray-300 rounded-md text-sm focus:ring-indigo-500 focus:border-indigo-500"
                    />
                </div>
                <button
                    type="button"
                    onclick={handleFilter}
                    class="px-4 py-1.5 bg-indigo-600 text-white rounded-md text-sm hover:bg-indigo-700 focus:ring-2 focus:ring-indigo-500"
                >
                    🔍 Filter
                </button>
                {#if startDate || endDate}
                    <button
                        type="button"
                        onclick={handleClearFilter}
                        class="px-4 py-1.5 bg-gray-100 text-gray-700 rounded-md text-sm hover:bg-gray-200"
                    >
                        Clear
                    </button>
                {/if}
            </div>
        </div>
        
        <!-- Chats Table -->
        <div class="bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
            <div class="px-4 py-3 border-b border-gray-200">
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
                                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    Date
                                </th>
                                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    User
                                </th>
                                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    Title
                                </th>
                                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    Messages
                                </th>
                                <th class="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    Actions
                                </th>
                            </tr>
                        </thead>
                        <tbody class="bg-white divide-y divide-gray-200">
                            {#each chats as chat}
                                <tr class="hover:bg-gray-50">
                                    <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                                        {formatShortDate(chat.created_at)}
                                    </td>
                                    <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                                        {chat.user_name || 'Anonymous'}
                                    </td>
                                    <td class="px-4 py-3 text-sm text-gray-900 max-w-xs truncate">
                                        {chat.title || 'Untitled Chat'}
                                    </td>
                                    <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                                        {chat.message_count}
                                    </td>
                                    <td class="px-4 py-3 whitespace-nowrap text-right text-sm">
                                        <button
                                            type="button"
                                            onclick={() => openChatDetail(chat)}
                                            class="text-indigo-600 hover:text-indigo-900"
                                        >
                                            👁 View
                                        </button>
                                    </td>
                                </tr>
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

<!-- Chat Detail Modal -->
{#if showChatModal && selectedChat}
    <div 
        class="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4"
        onclick={closeChatModal}
        role="dialog"
        aria-modal="true"
        aria-labelledby="chat-modal-title"
    >
        <div 
            class="bg-white rounded-lg shadow-xl max-w-3xl w-full max-h-[90vh] flex flex-col"
            onclick={(e) => e.stopPropagation()}
        >
            <!-- Modal Header -->
            <div class="flex items-center justify-between px-6 py-4 border-b border-gray-200">
                <div>
                    <h3 id="chat-modal-title" class="text-lg font-semibold text-gray-900">
                        💬 {selectedChat.title || 'Chat Conversation'}
                    </h3>
                    <p class="text-sm text-gray-500 mt-1">
                        {selectedChat.user_name || 'User'} • {formatDate(selectedChat.created_at)}
                    </p>
                </div>
                <button
                    type="button"
                    onclick={closeChatModal}
                    class="text-gray-400 hover:text-gray-500"
                    aria-label="Close"
                >
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                </button>
            </div>
            
            <!-- Modal Body - Messages -->
            <div class="flex-1 overflow-y-auto px-6 py-4 space-y-4">
                {#if loadingChatDetail}
                    <div class="flex items-center justify-center py-8">
                        <div class="text-gray-500">Loading conversation...</div>
                    </div>
                {:else if selectedChat.error}
                    <div class="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md">
                        {selectedChat.error}
                    </div>
                {:else if selectedChat.messages && selectedChat.messages.length > 0}
                    {#each selectedChat.messages as message}
                        <div class="flex {message.role === 'user' ? 'justify-end' : 'justify-start'}">
                            <div class="max-w-[80%] {message.role === 'user' 
                                ? 'bg-indigo-600 text-white' 
                                : 'bg-gray-100 text-gray-900'} rounded-lg px-4 py-2">
                                <div class="text-xs {message.role === 'user' ? 'text-indigo-200' : 'text-gray-500'} mb-1">
                                    {message.role === 'user' ? '👤 User' : '🤖 Assistant'}
                                    {#if message.timestamp}
                                        <span class="ml-2">{formatDate(message.timestamp)}</span>
                                    {/if}
                                </div>
                                <div class="text-sm whitespace-pre-wrap break-words">
                                    {message.content}
                                </div>
                            </div>
                        </div>
                    {/each}
                {:else}
                    <div class="text-center text-gray-500 py-8">
                        No messages in this conversation.
                    </div>
                {/if}
            </div>
            
            <!-- Modal Footer -->
            <div class="px-6 py-4 border-t border-gray-200 flex justify-end">
                <button
                    type="button"
                    onclick={closeChatModal}
                    class="px-4 py-2 bg-gray-100 text-gray-700 rounded-md text-sm hover:bg-gray-200"
                >
                    Close
                </button>
            </div>
        </div>
    </div>
{/if}

