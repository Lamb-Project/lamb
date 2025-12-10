<script>
    import { writable } from 'svelte/store';
    import { onMount } from 'svelte';
    // Note: 'ai' and '@ai-sdk/openai' might not be strictly necessary if only using fetch
    // import { streamText } from 'ai'; 
    // import { openai } from '@ai-sdk/openai'; 

    /**
     * @typedef {Object} Message
     * @property {string} id - Unique ID for the message
     * @property {('user'|'assistant')} role - Role of the message sender
     * @property {string} content - Content of the message
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
    let selectedModel = $state(initialModel ?? 'gpt-3.5-turbo'); // Use initialModel prop if provided
    let isLoadingModels = $state(false);
    let modelsError = $state(/** @type {string|null} */ (null));
    let isStreaming = $state(false);
    let chatContainer = $state(/** @type {HTMLElement | null} */(null)); // For autoscroll

    // --- Helper Functions ---
    /**
     * Log message with timestamp
     * @param {string} message - Message to log
     */
    function logWithTime(message) {
        const timestamp = new Date().toISOString().split('T')[1].replace('Z', '');
        console.log(`[${timestamp}] CHAT: ${message}`);
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
                // Set initial model if not already set or if current selection isn't valid
                if (modelIds.length > 0 && (!selectedModel || !modelIds.includes(selectedModel))) {
                     // Prefer initialModel prop if it's valid, else try GPT, else first model
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
            // Fallback models might be useful
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
        isStreaming = true; // Indicate streaming start

        /** @type {Message} */
        const newUserMessage = { id: Date.now().toString(), role: 'user', content: input };
        messages = [...messages, newUserMessage];

        // Prepare payload for OpenAI-compatible API
        const payload = {
            model: assistantId ? `lamb_assistant.${assistantId}` : selectedModel, // Use lamb_assistant.ID format if assistantId is provided
            messages: messages.map(({ role, content }) => ({ role, content })), // Send current message history
            stream: true // Request streaming response
        };

        logWithTime(`Using model: ${payload.model}`);

        // Clear input field
        input = '';

        // Add a placeholder for the assistant's response
        const assistantMessageId = (Date.now() + 1).toString();
        messages = [...messages, { id: assistantMessageId, role: 'assistant', content: '' }];

        let currentAssistantContent = '';

        try {
            // Validate required props
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

            if (!response.body) {
                throw new Error('Response body is null');
            }

            // --- Process Stream ---
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
                buffer = lines.pop() || ''; // Keep incomplete line in buffer

                for (const line of lines) {
                    if (line.trim() === '' || !line.startsWith('data: ')) continue;

                    const jsonData = line.substring(5).trim(); // Get content after "data: "
                    if (jsonData === '[DONE]') {
                        logWithTime('Received [DONE] signal');
                        continue; // Move to next line or break if this was the last useful data
                    }

                    try {
                        const parsedData = JSON.parse(jsonData);
                        // Check structure for OpenAI compatible stream chunk
                        if (parsedData.choices && parsedData.choices[0] && parsedData.choices[0].delta) {
                            const deltaContent = parsedData.choices[0].delta.content;
                            if (deltaContent) {
                                currentAssistantContent += deltaContent;
                                // Update the specific assistant message by ID
                                messages = messages.map(msg => 
                                    msg.id === assistantMessageId 
                                    ? { ...msg, content: currentAssistantContent } 
                                    : msg
                                );
                            }
                        } else {
                             logWithTime(`Received non-delta data chunk: ${jsonData.slice(0,100)}...`);
                        }
                    } catch (e) {
                        logWithTime(`Error parsing JSON line: ${line} - Error: ${e}`);
                        // Decide if you want to show partial content or wait
                    }
                }
                 // Process any remaining content in the buffer if needed, though usually not necessary with SSE line breaks
                if(buffer.startsWith('data: ')){
                    // Simplified handling for potential final partial chunk, full parsing recommended if needed
                    const jsonData = buffer.substring(5).trim();
                    if(jsonData !== '[DONE]') {
                        // Attempt to parse and extract content if possible...
                    }
                }
            }
            // Final update in case the last chunk didn't trigger map update
            messages = messages.map(msg => 
                msg.id === assistantMessageId 
                ? { ...msg, content: currentAssistantContent } 
                : msg
            );

        } catch (/** @type {any} */ error) {
            logWithTime(`Error during chat submission: ${error.message}`);
            console.error('Chat error:', error);
            // Update the assistant message with an error message
            messages = messages.map(msg => 
                msg.id === assistantMessageId 
                ? { ...msg, content: `Error: ${error.message}` } 
                : msg
            );
        } finally {
            isLoading = false;
            isStreaming = false; // Indicate streaming end
            logWithTime('Chat submission finished.');
        }
    }

    /** Update assistant message content by ID */
    function updateAssistantMessage(/** @type {string} */ newContent) {
        const assistantMsgIndex = messages.findIndex(msg => msg.role === 'assistant' && msg.id === messages[messages.length - 1].id);
        if (assistantMsgIndex !== -1) {
             messages[assistantMsgIndex].content = newContent;
             messages = messages; // Trigger reactivity
        }
    }

    // --- Lifecycle & Effects ---
    onMount(() => {
        logWithTime("ChatInterface mounted.");
        fetchModels(); // Fetch models when component mounts
    });

    // Auto-scroll effect
    $effect(() => {
        if (messages && chatContainer) {
            // Wait a tick for DOM update before scrolling
            Promise.resolve().then(() => {
                if (chatContainer) { // Extra check just in case
                    chatContainer.scrollTop = chatContainer.scrollHeight;
                    logWithTime("Scrolled chat container to bottom.");
                }
            });
        }
    });

</script>

<div class="flex flex-col h-full chat-max-height border border-gray-300 rounded-md overflow-hidden shadow-sm">
    <!-- Header / Model Selector -->
    <div class="p-2 border-b border-gray-200 bg-gray-50 flex items-center justify-between">
        <h2 class="text-lg font-semibold text-gray-700">Chat</h2>
        {#if false} <!-- Start: Hide model selector -->
        {#if isLoadingModels}
            <span class="text-sm text-gray-500">Loading models...</span>
        {:else if modelsError}
            <span class="text-sm text-red-600">Error: {modelsError}</span>
        {:else if models.length > 0}
            <select bind:value={selectedModel} class="text-sm border border-gray-300 rounded px-2 py-1 bg-white">
                {#each models as modelId}
                    <option value={modelId}>{modelId}</option>
                {/each}
            </select>
        {:else}
             <span class="text-sm text-gray-500">No models available</span>
        {/if}
        {/if} <!-- End: Hide model selector -->
    </div>

    <!-- Message Display Area -->
    <div bind:this={chatContainer} class="flex-grow p-4 overflow-y-auto space-y-4 bg-white">
        {#each messages as message (message.id)}
            <div class="flex {message.role === 'user' ? 'justify-end' : 'justify-start'}">
                <div 
                    class="max-w-xs md:max-w-md lg:max-w-lg xl:max-w-xl px-4 py-2 rounded-lg shadow {message.role === 'user' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-800'}"
                >
                     {#if message.role === 'assistant' && isStreaming && message.id === messages[messages.length - 1].id}
                        <!-- Basic streaming indicator -->
                         <span class="italic">{message.content || 'Thinking...'}</span> 
                     {:else}
                        <!-- Render markdown or plain text here eventually -->
                        <p class="whitespace-pre-wrap">{message.content}</p> 
                     {/if}
                </div>
            </div>
        {/each}
         {#if isLoading && !isStreaming && messages[messages.length - 1]?.role === 'user'}
             <!-- Show thinking indicator only after user submits and before stream starts -->
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

<style>
    /* Optional: Add any specific styles needed for the chat interface */
    /* Ensure the container respects max height - Adjust 200px based on surrounding layout */
     .chat-max-height {
         max-height: calc(100vh - 200px);
    }
</style> 