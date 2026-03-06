<script>
  import { createEventDispatcher } from 'svelte';

  // Props
  let { rubricId, aiGenerating } = $props();

  // Events
  const dispatch = createEventDispatcher();

  // Local state
  let messages = $state([]);
  let currentPrompt = $state('');
  let isMinimized = $state(false);

  // Add a message to the chat
  function addMessage(role, content) {
    messages.push({
      id: Date.now(),
      role,
      content,
      timestamp: new Date()
    });
  }

  // Handle sending a prompt
  async function handleSendPrompt() {
    if (!currentPrompt.trim()) return;

    const prompt = currentPrompt.trim();
    currentPrompt = '';

    // Add user message
    addMessage('user', prompt);

    try {
      if (rubricId) {
        // Modify existing rubric
        dispatch('modify', { prompt });
      } else {
        // Generate new rubric
        dispatch('generate', { prompt });
      }
    } catch (error) {
      addMessage('assistant', `Error: ${error.message}`);
    }
  }

  // Handle key press in textarea
  function handleKeydown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSendPrompt();
    }
  }

  // Clear chat
  function clearChat() {
    messages = [];
  }

  // Toggle minimize
  function toggleMinimize() {
    isMinimized = !isMinimized;
  }

  // Example prompts
  const examplePrompts = [
    "Create a rubric for evaluating 5-paragraph essays in 8th grade English",
    "Make this rubric suitable for 6th graders by simplifying the language",
    "Add a creativity criterion to this rubric",
    "Convert this to a 4-point scale instead of 5-point",
    "Make the descriptions more specific and observable"
  ];

  // Use example prompt
  function useExamplePrompt(prompt) {
    currentPrompt = prompt;
  }
</script>

<div class="bg-white shadow rounded-lg h-fit">
  <!-- Header -->
  <div class="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
    <h3 class="text-sm font-medium text-gray-900 flex items-center">
      <svg class="mr-2 h-4 w-4 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-4l-4 4-4-4z"/>
      </svg>
      AI Assistant
    </h3>
    <button
      onclick={toggleMinimize}
      class="text-gray-400 hover:text-gray-600"
      aria-label={isMinimized ? "Maximize AI chat" : "Minimize AI chat"}
    >
      <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d={isMinimized ? "M19 9l-7 7-7-7" : "M5 15l7-7 7 7"}/>
      </svg>
    </button>
  </div>

  {#if !isMinimized}
    <!-- Chat Messages -->
    <div class="flex-1 overflow-y-auto p-4 space-y-4 max-h-96">
      {#if messages.length === 0}
        <!-- Welcome message and examples -->
        <div class="text-center py-4">
          <div class="text-sm text-gray-600 mb-4">
            Ask me to help you create or modify this rubric. Here are some examples:
          </div>
          <div class="space-y-2">
            {#each examplePrompts as prompt}
              <button
                onclick={() => useExamplePrompt(prompt)}
                class="block w-full text-left px-3 py-2 text-xs bg-gray-50 hover:bg-gray-100 rounded border text-gray-700"
              >
                "{prompt}"
              </button>
            {/each}
          </div>
        </div>
      {:else}
        {#each messages as message}
          <div class="flex {message.role === 'user' ? 'justify-end' : 'justify-start'}">
            <div class="max-w-xs lg:max-w-md px-4 py-2 rounded-lg {message.role === 'user' ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-800'}">
              <div class="text-sm whitespace-pre-wrap">{message.content}</div>
              <div class="text-xs opacity-70 mt-1">
                {message.timestamp.toLocaleTimeString()}
              </div>
            </div>
          </div>
        {/each}
      {/if}

      <!-- Loading indicator -->
      {#if aiGenerating}
        <div class="flex justify-start">
          <div class="bg-gray-200 text-gray-800 px-4 py-2 rounded-lg">
            <div class="flex items-center space-x-2">
              <div class="animate-spin rounded-full h-4 w-4 border-b-2 border-gray-600"></div>
              <span class="text-sm">Thinking...</span>
            </div>
          </div>
        </div>
      {/if}
    </div>

    <!-- Input Area -->
    <div class="border-t border-gray-200 p-4">
      <div class="flex space-x-2">
        <textarea
          bind:value={currentPrompt}
          onkeydown={handleKeydown}
          placeholder={rubricId ? "Ask me to modify this rubric..." : "Describe the rubric you want to create..."}
          rows="2"
          class="flex-1 px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 resize-none"
          disabled={aiGenerating}
        ></textarea>
        <div class="flex flex-col space-y-2">
          <button
            onclick={handleSendPrompt}
            disabled={!currentPrompt.trim() || aiGenerating}
            class="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {#if aiGenerating}
              <svg class="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
            {:else}
              <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"/>
              </svg>
            {/if}
          </button>
          {#if messages.length > 0}
            <button
              onclick={clearChat}
              class="px-2 py-1 text-xs text-gray-500 hover:text-gray-700"
              title="Clear chat"
            >
              Clear
            </button>
          {/if}
        </div>
      </div>

      <!-- Help text -->
      <div class="mt-2 text-xs text-gray-500">
        Press Enter to send, Shift+Enter for new line
      </div>
    </div>
  {/if}
</div>
