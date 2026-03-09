<script>
    import { onMount } from 'svelte';
    import { page } from '$app/stores';

    let token = $state('');
    let resourceLinkId = $state('');
    let loading = $state(true);
    let error = $state(null);

    let activityInfo = $state(null);
    let stats = $state(null);
    let students = $state({ students: [], total: 0 });
    let chatsInfo = $state({ chats: [], total: 0 });
    
    // Chat state
    let chatFilterAsst = $state('');
    let expandedChats = $state({});
    let chatTranscripts = $state({});
    let loadingTranscripts = $state({});

    onMount(async () => {
        token = $page.url.searchParams.get('token');
        resourceLinkId = $page.url.searchParams.get('resource_link_id');

        if (!token) {
            error = "Missing LTI authorization token.";
            loading = false;
            return;
        }

        try {
            // We'll create the /info endpoint in the backend shortly to return the header info
            const reqs = [
                fetch(`/lamb/v1/lti/dashboard/info?token=${token}&resource_link_id=${resourceLinkId || ''}`).then(r => r.ok ? r.json() : Promise.reject('Info error')),
                fetch(`/lamb/v1/lti/dashboard/stats?token=${token}&resource_link_id=${resourceLinkId || ''}`).then(r => r.ok ? r.json() : Promise.reject('Stats error')),
                fetch(`/lamb/v1/lti/dashboard/students?token=${token}&resource_link_id=${resourceLinkId || ''}`).then(r => r.ok ? r.json() : Promise.reject('Students error'))
            ];
            
            // First batch
            const [infoData, statsData, studentsData] = await Promise.all(reqs);
            
            activityInfo = infoData;
            stats = statsData;
            students = studentsData;

            // Secondary load for chats if visibility is enabled
            if (activityInfo.chat_visibility_enabled) {
                await loadChatsList();
            }

        } catch (e) {
            error = e.message || "Failed to load dashboard data.";
        } finally {
            loading = false;
        }
    });

    async function loadChatsList() {
        try {
            const asstParam = chatFilterAsst ? `&assistant_id=${chatFilterAsst}` : '';
            const res = await fetch(`/lamb/v1/lti/dashboard/chats?token=${token}&resource_link_id=${resourceLinkId || ''}${asstParam}`);
            if (res.ok) {
                chatsInfo = await res.json();
            }
        } catch (e) {
            console.error('Failed to load chats list', e);
        }
    }

    $effect(() => {
        // When filter changes, reload the chat list
        if (!loading && chatFilterAsst !== undefined) {
            loadChatsList();
        }
    });

    function formatTime(ts) {
        if (!ts) return 'Never';
        try {
            // ts could be seconds or ISO string
            const d = new Date(typeof ts === 'number' ? ts * 1000 : ts);
            return d.toLocaleString();
        } catch {
            return String(ts);
        }
    }

    async function toggleChat(chatId) {
        expandedChats[chatId] = !expandedChats[chatId];
        
        // Load transcript if expanding and not already loaded
        if (expandedChats[chatId] && !chatTranscripts[chatId] && !loadingTranscripts[chatId]) {
            loadingTranscripts[chatId] = true;
            try {
                const res = await fetch(`/lamb/v1/lti/dashboard/chats/${chatId}?token=${token}&resource_link_id=${resourceLinkId || ''}`);
                if (res.ok) {
                    const data = await res.json();
                    chatTranscripts[chatId] = data;
                } else {
                    chatTranscripts[chatId] = { error: 'Failed to load' };
                }
            } catch (e) {
                chatTranscripts[chatId] = { error: 'Failed to load' };
            } finally {
                loadingTranscripts[chatId] = false;
            }
        }
    }
</script>

<div class="bg-gray-50 min-h-screen">
    <div class="max-w-5xl mx-auto px-4 py-6">
        {#if loading}
            <div class="flex justify-center p-12">
                <span class="text-gray-500 text-lg">Loading Dashboard Data...</span>
            </div>
        {:else if error}
            <div class="bg-red-50 text-red-600 p-6 rounded-xl shadow-sm border border-red-100">
                <strong class="block text-lg mb-2">Dashboard Error</strong>
                <p>{error}</p>
            </div>
        {:else if activityInfo && stats}
            <!-- Header -->
            <div class="bg-white rounded-xl shadow-sm border p-6 mb-6">
                <div class="flex flex-col md:flex-row md:items-start justify-between gap-4">
                    <div class="flex items-center gap-3">
                        <div class="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center text-xl shrink-0">🐑</div>
                        <div>
                            <h1 class="text-xl font-bold text-gray-900">{activityInfo.activity_name || 'LTI Activity'}</h1>
                            <p class="text-sm text-gray-500">
                                {#if activityInfo.context_title}{activityInfo.context_title} · {/if}
                                {activityInfo.org_name || ''}
                            </p>
                            <p class="text-xs text-gray-400 mt-0.5">
                                Owner: {activityInfo.owner_name}
                                {#if activityInfo.created_at} · Created {formatTime(activityInfo.created_at)}{/if}
                            </p>
                        </div>
                    </div>
                    <a href={`/lamb/v1/lti/enter-chat?resource_link_id=${resourceLinkId}&token=${token}`}
                       class="inline-flex items-center gap-2 bg-blue-600 text-white px-5 py-2.5 rounded-lg font-medium hover:bg-blue-700 transition-colors text-sm whitespace-nowrap">
                        <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" /></svg>
                        Open Chat
                    </a>
                </div>
            </div>

            <!-- Stats Cards -->
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                <div class="bg-white rounded-xl shadow-sm border p-4 text-center">
                    <div class="text-2xl font-bold text-gray-900">{stats.total_students || 0}</div>
                    <div class="text-xs text-gray-500 mt-1">Students</div>
                </div>
                <div class="bg-white rounded-xl shadow-sm border p-4 text-center">
                    <div class="text-2xl font-bold text-gray-900">{stats.total_chats || 0}</div>
                    <div class="text-xs text-gray-500 mt-1">Chats</div>
                </div>
                <div class="bg-white rounded-xl shadow-sm border p-4 text-center">
                    <div class="text-2xl font-bold text-gray-900">{stats.total_messages || 0}</div>
                    <div class="text-xs text-gray-500 mt-1">Messages</div>
                </div>
                <div class="bg-white rounded-xl shadow-sm border p-4 text-center">
                    <div class="text-2xl font-bold text-gray-900">{stats.active_last_7d || 0}</div>
                    <div class="text-xs text-gray-500 mt-1">Active (7d)</div>
                </div>
            </div>

            <!-- Assistants -->
            <div class="bg-white rounded-xl shadow-sm border p-6 mb-6">
                <div class="flex items-center justify-between mb-4">
                    <h2 class="text-lg font-semibold text-gray-900">Assistants</h2>
                    {#if activityInfo.is_owner}
                        <!-- We link to the specific setup URL -->
                        <a href={`/m/chat/setup?token=${token}&reconfigure=true`}
                           class="text-sm text-blue-600 hover:text-blue-800 font-medium flex items-center gap-1">
                            <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" /></svg>
                            Manage
                        </a>
                    {/if}
                </div>
                <div class="space-y-2">
                    {#each (stats.assistants || []) as asst}
                        <div class="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                            <div class="flex flex-wrap items-center gap-2">
                                <span class="w-2 h-2 rounded-full bg-green-500 shrink-0"></span>
                                <span class="font-medium text-gray-900 text-sm whitespace-nowrap">{asst.name}</span>
                                <span class="text-xs text-gray-400 whitespace-nowrap">by {asst.owner}</span>
                            </div>
                            <div class="text-xs text-gray-500 text-right shrink-0 ml-2">
                                {asst.chat_count} chats · {asst.message_count} msgs
                            </div>
                        </div>
                    {/each}
                    {#if !(stats.assistants?.length)}
                        <p class="text-sm text-gray-400 italic">No assistants configured.</p>
                    {/if}
                </div>
            </div>

            <!-- Student Access Log -->
            <div class="bg-white rounded-xl shadow-sm border p-6 mb-6">
                <div class="flex items-center justify-between mb-4">
                    <h2 class="text-lg font-semibold text-gray-900">Student Access Log</h2>
                    <span class="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded">Anonymized</span>
                </div>
                <div class="overflow-x-auto">
                    <table class="w-full text-sm">
                        <thead>
                            <tr class="border-b text-left text-gray-500 text-xs uppercase tracking-wider">
                                <th class="pb-3 pr-4 font-medium">Student (Anonymous ID)</th>
                                <th class="pb-3 pr-4 font-medium">First Access</th>
                                <th class="pb-3 pr-4 font-medium">Last Access</th>
                                <th class="pb-3 pl-4 text-center font-medium">Visits</th>
                            </tr>
                        </thead>
                        <tbody>
                            {#each (students.students || []) as s}
                                <tr class="border-b border-gray-100 hover:bg-gray-50 transition-colors">
                                    <td class="py-3 pr-4 font-medium text-gray-700 font-mono text-xs">{s.anonymous_id}</td>
                                    <td class="py-3 pr-4 text-gray-600">{formatTime(s.first_access)}</td>
                                    <td class="py-3 pr-4 text-gray-600">{formatTime(s.last_access)}</td>
                                    <td class="py-3 pl-4 text-center text-gray-600 font-medium">{s.access_count}</td>
                                </tr>
                            {/each}
                            {#if !(students.students?.length)}
                                <tr><td colspan="4" class="py-6 text-center text-gray-400 italic">No students have accessed this activity yet.</td></tr>
                            {/if}
                        </tbody>
                    </table>
                </div>
                {#if students.total > 20}
                    <div class="mt-4 flex justify-center pt-2">
                        <span class="text-sm text-gray-500">Showing {students.students.length} of {students.total} students</span>
                    </div>
                {/if}
            </div>

            <!-- Chat Transcripts -->
            {#if activityInfo.chat_visibility_enabled}
                <div class="bg-white rounded-xl shadow-sm border p-6 mb-6">
                    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4">
                        <h2 class="text-lg font-semibold text-gray-900">Chat Transcripts</h2>
                        <div class="flex flex-wrap items-center gap-2">
                            <span class="inline-flex items-center gap-1 text-xs bg-green-100 text-green-700 px-2 py-1 rounded-full font-medium">
                                <svg class="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" /></svg>
                                Visibility ON
                            </span>
                            <select bind:value={chatFilterAsst} class="text-sm border border-gray-300 rounded-lg px-3 py-1.5 focus:border-blue-500 focus:ring-blue-500 outline-none">
                                <option value="">All Assistants</option>
                                {#each (stats.assistants || []) as asst}
                                    <option value={asst.id}>{asst.name}</option>
                                {/each}
                            </select>
                        </div>
                    </div>

                    <p class="text-xs text-gray-500 mb-6 bg-blue-50 p-2 rounded text-blue-800">
                        <strong>Privacy Notice:</strong> All student identities are anonymized. You cannot see who wrote each message.
                    </p>

                    <div class="space-y-3">
                        {#each (chatsInfo.chats || []) as chat}
                            <div class="border border-gray-200 rounded-lg overflow-hidden bg-white hover:border-blue-300 transition-colors">
                                <button onclick={() => toggleChat(chat.chat_id)}
                                        class="w-full text-left px-4 py-3 bg-gray-50 hover:bg-gray-100 transition-colors flex items-center justify-between group">
                                    <div>
                                        <span class="font-medium text-gray-900 text-sm group-hover:text-blue-700 transition-colors">{chat.title || 'Untitled Chat'}</span>
                                        <div class="text-xs text-gray-500 mt-1 flex items-center gap-2 flex-wrap">
                                            <span class="bg-gray-200 text-gray-700 px-1.5 py-0.5 rounded font-mono">{chat.anonymous_student}</span> 
                                            <span class="text-gray-400">→</span> 
                                            <span class="font-medium text-gray-700">{chat.assistant_name}</span>
                                            <span class="text-gray-300">|</span>
                                            {chat.message_count} messages
                                            <span class="text-gray-300">|</span>
                                            {formatTime(chat.updated_at)}
                                        </div>
                                    </div>
                                    <svg class="h-5 w-5 text-gray-400 transform transition-transform duration-200 {expandedChats[chat.chat_id] ? 'rotate-180 text-blue-500' : ''}" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
                                    </svg>
                                </button>
                                
                                {#if expandedChats[chat.chat_id]}
                                    <div class="border-t border-gray-100 bg-white">
                                        {#if loadingTranscripts[chat.chat_id]}
                                            <div class="text-center py-8 text-sm text-gray-400 flex items-center justify-center gap-2">
                                                <svg class="animate-spin h-4 w-4 text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                                                Loading Transcript...
                                            </div>
                                        {:else if chatTranscripts[chat.chat_id]?.error}
                                            <div class="text-center py-6 text-sm text-red-500">
                                                {chatTranscripts[chat.chat_id].error}
                                            </div>
                                        {:else}
                                            <div class="p-4 space-y-3 bg-gray-50/50 max-h-[500px] overflow-y-auto">
                                                {#each (chatTranscripts[chat.chat_id]?.messages || []) as msg}
                                                    {@const isUser = msg.role === 'user'}
                                                    {@const bubbleClass = isUser ? 'bg-blue-50 border-l-4 border-blue-500' : 'bg-green-50 border-l-4 border-green-500'}
                                                    {@const speaker = msg.speaker || (isUser ? chatTranscripts[chat.chat_id].anonymous_student : 'Assistant')}
                                                    <div class="{bubbleClass} rounded-r-lg p-3 shadow-sm">
                                                        <div class="text-xs font-semibold {isUser ? 'text-blue-800' : 'text-green-800'} mb-1.5">{speaker}</div>
                                                        <div class="text-sm text-gray-800 whitespace-pre-wrap leading-relaxed">{msg.content}</div>
                                                    </div>
                                                {/each}
                                                {#if !(chatTranscripts[chat.chat_id]?.messages?.length)}
                                                    <p class="text-sm text-gray-400 italic py-2 text-center">No messages in this chat.</p>
                                                {/if}
                                            </div>
                                        {/if}
                                    </div>
                                {/if}
                            </div>
                        {/each}
                        {#if !(chatsInfo.chats?.length)}
                            <div class="py-8 text-center bg-gray-50 rounded-lg border border-gray-200 border-dashed">
                                <p class="text-sm text-gray-500 italic">No chat transcripts found matching the criteria.</p>
                            </div>
                        {/if}
                    </div>

                    {#if chatsInfo.total > 20}
                        <div class="mt-6 flex justify-center">
                            <span class="text-sm px-3 py-1 bg-gray-100 rounded-full text-gray-600 font-medium">
                                Showing {chatsInfo.chats.length} of {chatsInfo.total} chats
                            </span>
                        </div>
                    {/if}
                </div>
            {:else}
                <!-- Visibility disabled state -->
                <div class="bg-white rounded-xl shadow-sm border p-6 mb-6">
                    <h2 class="text-lg font-semibold text-gray-900 mb-3">Chat Transcripts</h2>
                    <div class="flex items-center gap-3 text-gray-500 bg-gray-50 p-4 rounded-lg">
                        <svg class="h-6 w-6 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" /></svg>
                        <div>
                            <p class="text-sm font-medium text-gray-700">Transcript review is disabled</p>
                            <p class="text-sm mt-0.5">Chat reading is not enabled for this activity to protect student privacy.</p>
                        </div>
                        {#if activityInfo.is_owner}
                            <a href={`/m/chat/setup?token=${token}&reconfigure=true`} class="inline-flex items-center gap-1 bg-white border border-gray-300 shadow-sm text-gray-700 text-sm font-medium px-3 py-1.5 rounded-lg hover:bg-gray-50 transition-colors ml-auto">
                                Enable in settings
                            </a>
                        {/if}
                    </div>
                </div>
            {/if}
        {/if}
    </div>
</div>
