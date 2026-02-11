<script>
    import { writable } from 'svelte/store';
    import { onMount } from 'svelte';
    import { marked } from 'marked';
    import ConfirmationModal from '$lib/components/modals/ConfirmationModal.svelte';

    // Configure marked to preserve line breaks (converts \n to <br>)
    marked.setOptions({
        breaks: true,      // Convert single newlines to <br>
        gfm: true          // GitHub Flavored Markdown (tables, strikethrough, etc.)
    });

    // Action to focus element on mount (avoids a11y autofocus warning)
    /** @param {HTMLElement} node */
    function focusOnMount(node) {
        node.focus();
    }

    /**
     * @typedef {Object} Message
     * @property {string} id - Unique ID for the message
     * @property {('user'|'assistant')} role - Role of the message sender
     * @property {string} content - Content of the message
     */

    /**
     * @typedef {Object} ChatSummary
     * @property {string} id - Chat UUID
     * @property {string} title - Chat title
     * @property {number} message_count - Number of messages
     * @property {number} created_at - Unix timestamp
     * @property {number} updated_at - Unix timestamp
     */

    /**
     * @typedef {Object} ChatInterfaceProps
     * @property {string} apiUrl - Base URL for the creator interface API.
     * @property {string} userToken - User authentication token.
     * @property {string | null} [initialModel] - Optional initial model to select.
     * @property {string} assistantId - Assistant ID to chat with (required).
     */
    
    // --- Component Props (using Svelte 5 runes) ---
    let { 
        apiUrl = '',            // Base URL for creator interface
        userToken = '',         // User authentication token (replaces apiKey)
        initialModel = null,
        assistantId = null      // Required for new proxy endpoint
    } = $props();

    // --- Component State (using Svelte 5 runes) ---
    let messages = $state(/** @type {Message[]} */([]));
    let input = $state('');
    let isLoading = $state(false);
    let models = $state(/** @type {string[]} */([]));
    let selectedModel = $state(initialModel ?? 'gpt-3.5-turbo');
    let isLoadingModels = $state(false);
    let renderMarkdown = $state(true);
    let modelsError = $state(/** @type {string|null} */ (null));
    let isStreaming = $state(false);
    let chatContainer = $state(/** @type {HTMLElement | null} */(null));

    // --- Chat History State ---
    let chatList = $state(/** @type {ChatSummary[]} */([]));
    let currentChatId = $state(/** @type {string|null} */(null));
    let currentChatTitle = $state('New Chat');
    let isLoadingChats = $state(false);
    let isEditingTitle = $state(false);
    let editTitleInput = $state('');
    let showSidebar = $state(true);
    
    // --- Delete Chat Modal State ---
    let showDeleteChatModal = $state(false);
    /** @type {string|null} */
    let chatToDeleteId = $state(null);
    let isDeletingChat = $state(false);

    // --- Helper Functions ---
    /**
     * Log message with timestamp
     * @param {string} message - Message to log
     */
    function logWithTime(message) {
        const timestamp = new Date().toISOString().split('T')[1].replace('Z', '');
        console.log(`[${timestamp}] CHAT: ${message}`);
    }

    /**
     * Format timestamp for display
     * @param {number} timestamp - Unix timestamp
     * @returns {string} Formatted date string
     */
    function formatTimestamp(timestamp) {
        const date = new Date(timestamp * 1000);
        const now = new Date();
        const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));
        
        if (diffDays === 0) {
            return 'Today';
        } else if (diffDays === 1) {
            return 'Yesterday';
        } else if (diffDays < 7) {
            return date.toLocaleDateString('en-US', { weekday: 'long' });
        } else {
            return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        }
    }

    /**
     * Group chats by date for sidebar display
     * @param {ChatSummary[]} chats
     * @returns {Map<string, ChatSummary[]>}
     */
    function groupChatsByDate(chats) {
        const groups = new Map();
        for (const chat of chats) {
            const dateKey = formatTimestamp(chat.updated_at);
            if (!groups.has(dateKey)) {
                groups.set(dateKey, []);
            }
            groups.get(dateKey).push(chat);
        }
        return groups;
    }

    // --- Chat List API Calls ---
    
    /**
     * Fetch chat list for current assistant
     */
    async function fetchChatList() {
        if (!apiUrl || !userToken || !assistantId) return;
        
        isLoadingChats = true;
        logWithTime(`Fetching chat list for assistant ${assistantId}`);
        
        try {
            const response = await fetch(
                `${apiUrl}/creator/chats?assistant_id=${assistantId}&per_page=50`,
                {
                    headers: { 'Authorization': `Bearer ${userToken}` }
                }
            );
            
            if (!response.ok) {
                throw new Error(`Failed to fetch chats: ${response.status}`);
            }
            
            const data = await response.json();
            chatList = data.chats || [];
            logWithTime(`Loaded ${chatList.length} chats`);
            
        } catch (error) {
            console.error('Error fetching chat list:', error);
            chatList = [];
        } finally {
            isLoadingChats = false;
        }
    }

    /**
     * Load a specific chat by ID
     * @param {string} chatId
     */
    async function loadChat(chatId) {
        if (!apiUrl || !userToken) return;
        
        logWithTime(`Loading chat ${chatId}`);
        isLoading = true;
        
        try {
            const response = await fetch(
                `${apiUrl}/creator/chats/${chatId}`,
                {
                    headers: { 'Authorization': `Bearer ${userToken}` }
                }
            );
            
            if (!response.ok) {
                throw new Error(`Failed to load chat: ${response.status}`);
            }
            
            const data = await response.json();
            
            // Convert messages from response to our format
            messages = (data.messages || []).map((msg, idx) => ({
                id: msg.id || `msg-${idx}`,
                role: msg.role,
                content: msg.content
            }));
            
            currentChatId = data.id;
            currentChatTitle = data.title;
            
            logWithTime(`Loaded chat with ${messages.length} messages`);
            
        } catch (error) {
            console.error('Error loading chat:', error);
        } finally {
            isLoading = false;
        }
    }

    /**
     * Start a new chat session
     */
    function startNewChat() {
        logWithTime('Starting new chat');
        messages = [];
        currentChatId = null;
        currentChatTitle = 'New Chat';
        isEditingTitle = false;
    }

    /**
     * Update chat title
     */
    async function updateChatTitle() {
        if (!currentChatId || !editTitleInput.trim()) {
            isEditingTitle = false;
            return;
        }
        
        const newTitle = editTitleInput.trim();
        logWithTime(`Updating chat title to: ${newTitle}`);
        
        try {
            const response = await fetch(
                `${apiUrl}/creator/chats/${currentChatId}`,
                {
                    method: 'PUT',
                    headers: {
                        'Authorization': `Bearer ${userToken}`,
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ title: newTitle })
                }
            );
            
            if (response.ok) {
                currentChatTitle = newTitle;
                // Update in chat list
                chatList = chatList.map(c => 
                    c.id === currentChatId ? { ...c, title: newTitle } : c
                );
                logWithTime('Title updated successfully');
            }
        } catch (error) {
            console.error('Error updating title:', error);
        } finally {
            isEditingTitle = false;
        }
    }

    /**
     * Open delete chat confirmation modal
     * @param {string} chatId
     */
    function deleteChat(chatId) {
        chatToDeleteId = chatId;
        showDeleteChatModal = true;
    }
    
    /**
     * Confirm chat deletion
     */
    async function confirmDeleteChat() {
        if (!chatToDeleteId || isDeletingChat) return;
        isDeletingChat = true;
        
        const deletingChatId = chatToDeleteId;
        logWithTime(`Deleting chat ${deletingChatId}`);
        
        try {
            const response = await fetch(
                `${apiUrl}/creator/chats/${deletingChatId}`,
                {
                    method: 'DELETE',
                    headers: { 'Authorization': `Bearer ${userToken}` }
                }
            );
            
            if (response.ok) {
                chatList = chatList.filter(c => c.id !== deletingChatId);
                if (currentChatId === deletingChatId) {
                    startNewChat();
                }
                logWithTime('Chat deleted');
                showDeleteChatModal = false;
                chatToDeleteId = null;
            }
        } catch (error) {
            console.error('Error deleting chat:', error);
        } finally {
            isDeletingChat = false;
        }
    }
    
    /**
     * Cancel delete chat modal
     */
    function cancelDeleteChat() {
        if (isDeletingChat) return;
        showDeleteChatModal = false;
        chatToDeleteId = null;
    }

    // --- API Calls ---
    /** Fetches available models */
    async function fetchModels() {
        if (!apiUrl || !userToken) {
            modelsError = 'API URL or user token is not configured.';
            console.error(modelsError);
            return;
        }
        isLoadingModels = true;
        modelsError = null;
        logWithTime(`Fetching models from ${apiUrl}/creator/models`);
        try {
            const response = await fetch(`${apiUrl}/creator/models`, {
                method: 'GET',
                headers: { 'Authorization': `Bearer ${userToken}` }
            });
            if (!response.ok) throw new Error(`Failed to fetch models: ${response.status}`);
            const data = await response.json();
            if (data.data && Array.isArray(data.data)) {
                const modelIds = data.data
                    .map(/** @param {{ id: string }} model */ (model) => model.id)
                    .sort();
                models = modelIds;
                logWithTime(`Models loaded: ${modelIds.join(', ')}`);
                if (modelIds.length > 0 && (!selectedModel || !modelIds.includes(selectedModel))) {
                    if (initialModel && modelIds.includes(initialModel)) {
                        selectedModel = initialModel;
                    } else {
                        const gptModels = modelIds.filter(/** @param {string} id */ (id) => id.includes('gpt'));
                        selectedModel = gptModels.length > 0 ? gptModels[0] : modelIds[0];
                    }
                    logWithTime(`Selected model set to: ${selectedModel}`);
                }
            } else {
                throw new Error('Invalid model data format');
            }
        } catch (/** @type {unknown} */ error) {
            const errorMessage = error instanceof Error ? error.message : 'Failed to load models';
            modelsError = errorMessage;
            console.error('Error fetching models:', error);
            models = ['gpt-3.5-turbo', 'gpt-4']; 
            if (!selectedModel || !models.includes(selectedModel)) {
                selectedModel = models[0];
            }
            logWithTime(`Using fallback models due to error. Selected: ${selectedModel}`);
        } finally {
            isLoadingModels = false;
        }
    }

    /**
     * Sends messages to the chat API and handles streaming response.
     */
    async function handleSubmit() {
        if (!input.trim() || isLoading || !apiUrl || !userToken) return;

        logWithTime(`Submitting message with model: ${selectedModel}`);
        isLoading = true;
        isStreaming = true;

        /** @type {Message} */
        const newUserMessage = { id: Date.now().toString(), role: 'user', content: input };
        messages = [...messages, newUserMessage];

        // Prepare payload with chat_id for persistence
        const payload = {
            model: assistantId ? `lamb_assistant.${assistantId}` : selectedModel,
            messages: messages.map(({ role, content }) => ({ role, content })),
            stream: true,
            chat_id: currentChatId,  // Include chat_id for persistence
            persist_chat: true
        };

        logWithTime(`Using model: ${payload.model}, chat_id: ${currentChatId || 'new'}`);

        const userInput = input;
        input = '';

        const assistantMessageId = (Date.now() + 1).toString();
        messages = [...messages, { id: assistantMessageId, role: 'assistant', content: '' }];

        let currentAssistantContent = '';

        try {
            if (!assistantId) {
                throw new Error('Assistant ID is required for chat');
            }
            if (!userToken) {
                throw new Error('User authentication token is required');
            }
            
            const endpoint = `${apiUrl}/creator/assistant/${assistantId}/chat/completions`;
            logWithTime(`Sending request to ${endpoint}`);
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${userToken}`
                },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`API Error: ${response.status} - ${errorText}`);
            }

            // Get chat_id from response header (for new chats)
            const responseChatId = response.headers.get('X-Chat-Id');
            if (responseChatId && !currentChatId) {
                currentChatId = responseChatId;
                logWithTime(`New chat created with ID: ${currentChatId}`);
                // Refresh chat list to show new chat
                fetchChatList();
            }

            if (!response.body) {
                throw new Error('Response body is null');
            }

            const contentType = response.headers.get('content-type');
            const isStreamingResponse = contentType && contentType.includes('text/event-stream');

            if (isStreamingResponse) {
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let buffer = '';
                logWithTime('Starting stream processing');

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) {
                        logWithTime('Stream finished.');
                        break;
                    }

                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split('\n');
                    buffer = lines.pop() || '';

                    for (const line of lines) {
                        if (line.trim() === '' || !line.startsWith('data: ')) continue;

                        const jsonData = line.substring(5).trim();
                        if (jsonData === '[DONE]') {
                            logWithTime('Received [DONE] signal');
                            continue;
                        }

                        try {
                            const parsedData = JSON.parse(jsonData);
                            if (parsedData.choices && parsedData.choices[0] && parsedData.choices[0].delta) {
                                const deltaContent = parsedData.choices[0].delta.content;
                                if (deltaContent) {
                                    currentAssistantContent += deltaContent;
                                    messages = messages.map(msg =>
                                        msg.id === assistantMessageId
                                        ? { ...msg, content: currentAssistantContent }
                                        : msg
                                    );
                                }
                            }
                            // Check for chat_id in response
                            if (parsedData.chat_id && !currentChatId) {
                                currentChatId = parsedData.chat_id;
                                logWithTime(`Chat ID from stream: ${currentChatId}`);
                            }
                        } catch (e) {
                            // Ignore parse errors for incomplete chunks
                        }
                    }
                }
                messages = messages.map(msg =>
                    msg.id === assistantMessageId
                    ? { ...msg, content: currentAssistantContent }
                    : msg
                );
            } else {
                logWithTime('Processing direct JSON response');
                const responseData = await response.json();
                
                // Get chat_id from response body
                if (responseData.chat_id && !currentChatId) {
                    currentChatId = responseData.chat_id;
                    logWithTime(`Chat ID from response: ${currentChatId}`);
                    fetchChatList();
                }

                if (responseData.object === 'image_generation' && responseData.images) {
                    messages = messages.map(msg =>
                        msg.id === assistantMessageId
                        ? { ...msg, images: responseData.images, content: responseData.images.length > 0 ? `Generated ${responseData.images.length} image(s)` : 'No images generated' }
                        : msg
                    );
                } else {
                    const content = responseData.choices?.[0]?.message?.content || JSON.stringify(responseData, null, 2);
                    messages = messages.map(msg =>
                        msg.id === assistantMessageId
                        ? { ...msg, content: content }
                        : msg
                    );
                }
            }

            // Update chat title if this was the first message
            if (messages.length === 2 && currentChatTitle === 'New Chat') {
                // Auto-generate title from first message
                const truncated = userInput.length > 35 
                    ? userInput.substring(0, 35) + '...' 
                    : userInput;
                currentChatTitle = truncated;
            }

            // Refresh chat list to update message counts
            fetchChatList();

        } catch (/** @type {any} */ error) {
            logWithTime(`Error during chat submission: ${error.message}`);
            console.error('Chat error:', error);
            messages = messages.map(msg => 
                msg.id === assistantMessageId 
                ? { ...msg, content: `Error: ${error.message}` } 
                : msg
            );
        } finally {
            isLoading = false;
            isStreaming = false;
            logWithTime('Chat submission finished.');
        }
    }

    /** Download generated image */
    function downloadImage(image, messageId) {
        const link = document.createElement('a');
        link.href = `data:${image.mime_type};base64,${image.image_base64}`;
        link.download = `generated_image_${messageId}_${image.index + 1}.${image.mime_type.split('/')[1]}`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    // --- Lifecycle & Effects ---
    onMount(() => {
        logWithTime("ChatInterface mounted.");
        fetchModels();
        fetchChatList();
    });

    // Auto-scroll effect
    $effect(() => {
        if (messages && chatContainer) {
            Promise.resolve().then(() => {
                if (chatContainer) {
                    chatContainer.scrollTop = chatContainer.scrollHeight;
                }
            });
        }
    });

    // Derived state for grouped chats
    let groupedChats = $derived(groupChatsByDate(chatList));

</script>

<div class="flex h-full chat-max-height border border-gray-300 rounded-md overflow-hidden shadow-sm">
    <!-- Sidebar: Chat History -->
    {#if showSidebar}
    <div class="w-64 flex-shrink-0 border-r border-gray-200 bg-gray-50 flex flex-col">
        <!-- Sidebar Header -->
        <div class="p-3 border-b border-gray-200 flex items-center justify-between">
            <span class="font-medium text-gray-700 text-sm">Chat History</span>
            <button
                onclick={() => startNewChat()}
                class="px-2 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 flex items-center gap-1"
                title="Start new chat"
            >
                <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
                </svg>
                New
            </button>
        </div>
        
        <!-- Chat List -->
        <div class="flex-grow overflow-y-auto">
            {#if isLoadingChats}
                <div class="p-4 text-center text-gray-500 text-sm">Loading...</div>
            {:else if chatList.length === 0}
                <div class="p-4 text-center text-gray-500 text-sm">No chats yet</div>
            {:else}
                {#each [...groupedChats] as [dateGroup, chats]}
                    <div class="px-3 py-2">
                        <div class="text-xs font-medium text-gray-400 uppercase tracking-wide mb-1">{dateGroup}</div>
                        {#each chats as chat (chat.id)}
                            <div
                                class="w-full text-left px-2 py-2 rounded text-sm hover:bg-gray-200 transition-colors group flex items-center justify-between cursor-pointer
                                    {currentChatId === chat.id ? 'bg-blue-100 text-blue-800' : 'text-gray-700'}"
                                role="button"
                                tabindex="0"
                                onclick={() => loadChat(chat.id)}
                                onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') loadChat(chat.id); }}
                            >
                                <span class="truncate flex-grow">{chat.title}</span>
                                <button
                                    onclick={(e) => { e.stopPropagation(); deleteChat(chat.id); }}
                                    onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.stopPropagation(); deleteChat(chat.id); } }}
                                    class="opacity-0 group-hover:opacity-100 p-1 text-gray-400 hover:text-red-600 transition-opacity"
                                    title="Delete chat"
                                >
                                    <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                                    </svg>
                                </button>
                            </div>
                        {/each}
                    </div>
                {/each}
            {/if}
        </div>
        
        <!-- Toggle Sidebar Button -->
        <button
            onclick={() => showSidebar = false}
            class="p-2 border-t border-gray-200 text-gray-500 hover:text-gray-700 text-xs flex items-center justify-center gap-1"
        >
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
            </svg>
            Hide
        </button>
    </div>
    {/if}

    <!-- Main Chat Area -->
    <div class="flex-grow flex flex-col min-w-0">
        <!-- Header -->
        <div class="p-2 border-b border-gray-200 bg-gray-50 flex items-center justify-between gap-2">
            <!-- Toggle Sidebar (when hidden) -->
            {#if !showSidebar}
                <button
                    onclick={() => showSidebar = true}
                    class="p-1 text-gray-500 hover:text-gray-700"
                    title="Show chat history"
                >
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
                    </svg>
                </button>
            {/if}
            
            <!-- Chat Title (editable) -->
            <div class="flex-grow min-w-0">
                {#if isEditingTitle}
                    <input
                       type="text"
                       bind:value={editTitleInput}
                       onblur={() => updateChatTitle()}
                       onkeydown={(e) => { if (e.key === 'Enter') updateChatTitle(); if (e.key === 'Escape') isEditingTitle = false; }}
                       class="w-full px-2 py-1 text-lg font-semibold text-gray-700 border border-blue-500 rounded focus:outline-none"
                       use:focusOnMount
                   />
                {:else}
                    <button
                        onclick={() => { if (currentChatId) { editTitleInput = currentChatTitle; isEditingTitle = true; } }}
                        class="text-lg font-semibold text-gray-700 hover:text-blue-600 truncate block w-full text-left"
                        title={currentChatId ? "Click to edit title" : "Start chatting to create a new chat"}
                        disabled={!currentChatId}
                    >
                        {currentChatTitle}
                    </button>
                {/if}
            </div>
            
            <!-- Markdown Toggle -->
            <label class="flex items-center space-x-2 text-sm text-gray-600 flex-shrink-0">
                <input type="checkbox" bind:checked={renderMarkdown} class="rounded" />
                <span class="hidden sm:inline">Render as markdown</span>
            </label>
        </div>

        <!-- Message Display Area -->
        <div bind:this={chatContainer} class="flex-grow p-4 overflow-y-auto space-y-4 bg-white">
            {#if messages.length === 0}
                <div class="flex items-center justify-center h-full text-gray-400">
                    <div class="text-center">
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-12 w-12 mx-auto mb-2 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                        </svg>
                        <p>Start a conversation</p>
                    </div>
                </div>
            {:else}
                {#each messages as message (message.id)}
                    <div class="flex {message.role === 'user' ? 'justify-end' : 'justify-start'}">
                        <div 
                            class="max-w-xs md:max-w-md lg:max-w-lg xl:max-w-xl px-4 py-2 rounded-lg shadow {message.role === 'user' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-800'}"
                        >
                            {#if message.role === 'assistant' && isStreaming && message.id === messages[messages.length - 1].id}
                                <span class="italic">{message.content || 'Thinking...'}</span>
                            {:else}
                                {#if message.images && message.images.length > 0}
                                    <div class="space-y-2">
                                        {#each message.images as image (image.index)}
                                            <div class="border rounded-lg overflow-hidden max-w-sm">
                                                <button
                                                    onclick={() => window.open(this.src, '_blank')}
                                                    onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); window.open(this.src, '_blank'); } }}
                                                    class="w-full p-0 border-0 bg-transparent cursor-pointer focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 rounded-lg overflow-hidden"
                                                    aria-label="View generated image in full size"
                                                    title="Click to view full size"
                                                >
                                                    <img
                                                        src="data:{image.mime_type};base64,{image.image_base64}"
                                                        alt="AI-generated artwork"
                                                        class="w-full h-auto max-h-96 object-contain hover:opacity-90 transition-opacity"
                                                    />
                                                </button>
                                                <div class="p-2 bg-gray-50 text-xs text-gray-600">
                                                    <div class="flex justify-between items-center">
                                                        <span>{image.width} × {image.height}</span>
                                                        <button
                                                            class="text-blue-600 hover:text-blue-800 underline"
                                                            onclick={() => downloadImage(image, message.id)}
                                                        >
                                                            Download
                                                        </button>
                                                    </div>
                                                </div>
                                            </div>
                                        {/each}
                                    </div>
                                {:else}
                                    {#if renderMarkdown}
                                        <div class="prose prose-sm {message.role === 'user' ? 'prose-invert' : ''}">{@html marked(message.content)}</div>
                                    {:else}
                                        <p class="whitespace-pre-wrap">{message.content}</p>
                                    {/if}
                                {/if}
                            {/if}
                        </div>
                    </div>
                {/each}
            {/if}
            {#if isLoading && !isStreaming && messages[messages.length - 1]?.role === 'user'}
                <div class="flex justify-start">
                    <div class="max-w-xs md:max-w-md lg:max-w-lg xl:max-w-xl px-4 py-2 rounded-lg shadow bg-gray-200 text-gray-800 italic">
                        Thinking...
                    </div>
                </div>
            {/if}
        </div>

        <!-- Input Area -->
        <div class="p-3 border-t border-gray-200 bg-gray-50">
            <form onsubmit={(e) => { e.preventDefault(); handleSubmit(); return false; }} class="flex items-center space-x-2">
                <input
                    type="text"
                    bind:value={input}
                    placeholder="Type your message..."
                    disabled={isLoading}
                    class="flex-grow border border-gray-300 rounded-md p-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
                />
                <button
                    type="submit"
                    disabled={isLoading || !input.trim()}
                    class="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    {#if isLoading}
                        <svg class="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                    {:else}
                        Send
                    {/if}
                </button>
            </form>
        </div>
    </div>
</div>

<!-- Delete Chat Confirmation Modal -->
<ConfirmationModal
    bind:isOpen={showDeleteChatModal}
    bind:isLoading={isDeletingChat}
    title="Delete Chat"
    message="Are you sure you want to delete this chat? This action cannot be undone."
    confirmText="Delete"
    variant="danger"
    onconfirm={confirmDeleteChat}
    oncancel={cancelDeleteChat}
/>

<style>
    .chat-max-height {
        max-height: calc(100vh - 200px);
        min-height: 400px;
    }
</style>
