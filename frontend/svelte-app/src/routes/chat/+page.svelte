<script>
	import { page } from '$app/stores';
	import { base } from '$app/paths';

	/**
	 * @typedef {Object} Message
	 * @property {string} id - Unique ID for the message
	 * @property {('user'|'assistant')} role - Role of the message sender
	 * @property {string} content - Content of the message
	 */

	/**
	 * @typedef {Object} OpenAIModel
	 * @property {string} id - Model identifier
	 */

	// --- Component State (using Svelte 5 runes) ---
	/** @type {Message[]} */
	let messages = $state([]);
	let input = $state('');
	let isLoading = $state(false);
	/** @type {string[]} */
	let models = $state([]);
	let selectedModel = $state('gpt-3.5-turbo');
	let isLoadingModels = $state(false);
	/** @type {string|null} */
	let modelsError = $state(null);
	let isStreaming = $state(false);
	/** @type {HTMLElement | null} */
	let chatContainer = $state(null);

	// API base URL
	const API_URL = 'http://localhost:9099';
	const API_KEY = '0p3n-w3bu!';

	/**
	 * Log message with timestamp
	 * @param {string} message - Message to log
	 */
	function logWithTime(message) {
		const timestamp = new Date().toISOString().split('T')[1].replace('Z', '');
		console.log(`[${timestamp}] ${message}`);
	}

	/**
	 * Fetches the available models from the API
	 */
	async function fetchModels() {
		isLoadingModels = true;
		modelsError = null;

		try {
			const response = await fetch(`${API_URL}/models`, {
				method: 'GET',
				headers: {
					Authorization: `Bearer ${API_KEY}`
				}
			});

			if (!response.ok) {
				throw new Error(`Failed to fetch models: ${response.status}`);
			}

			const data = await response.json();

			// Extract model IDs from the OpenAI response format
			if (data.data && Array.isArray(data.data)) {
				// Sort models by ID for better organization
				const modelIds = data.data
					.map(/** @param {OpenAIModel} model */ (model) => model.id)
					.sort();

				models = modelIds;

				// Set a default model if available
				if (modelIds.length > 0) {
					// Prefer GPT models if available
					const gptModels = modelIds.filter(/** @param {string} id */ (id) => id.includes('gpt'));
					if (gptModels.length > 0) {
						selectedModel = gptModels[0];
					} else {
						selectedModel = modelIds[0];
					}
				}
			} else {
				throw new Error('Invalid model data format');
			}
		} catch (/** @type {unknown} */ error) {
			console.error('Error fetching models:', error);
			// Convert error to string message safely
			const errorMessage = error instanceof Error ? error.message : 'Failed to load models';
			modelsError = errorMessage;
			// Set some fallback models in case the API doesn't support model listing
			models = ['gpt-3.5-turbo', 'gpt-4'];
		} finally {
			isLoadingModels = false;
		}
	}

	// Auto-scroll to bottom when messages are added and clear messages on mount
	$effect(() => {
		// Auto-scroll when messages update
		const chatElement = document.getElementById('chat-messages');
		if (chatElement) {
			chatElement.scrollTop = chatElement.scrollHeight;
		}
	});

	// Fetch models and clear localStorage on component mount
	$effect(() => {
		// Clear messages from localStorage
		localStorage.removeItem('messages');
		localStorage.removeItem('userInputField');

		// Fetch models
		fetchModels();
	});

	/**
	 * Process an SSE stream and update UI
	 * @param {ReadableStreamDefaultReader<Uint8Array>} reader - Stream reader
	 * @returns {Promise<void>}
	 */
	async function processStream(reader) {
		const decoder = new TextDecoder();
		let currentText = '';
		let lastUpdateTime = Date.now();
		let chunkCount = 0;
		let buffer = '';

		logWithTime('Starting stream processing');

		try {
			while (true) {
				const readStart = Date.now();
				logWithTime('Reading from stream...');
				const { done, value } = await reader.read();
				const readDuration = Date.now() - readStart;

				if (readDuration > 1000) {
					logWithTime(`⚠️ SLOW READ: Stream read took ${readDuration}ms`);
				}

				const now = Date.now();

				if (done) {
					logWithTime('Stream completed');
					break;
				}

				logWithTime(`Received chunk of size: ${value.byteLength} bytes`);

				chunkCount++;
				const text = decoder.decode(value, { stream: true });
				buffer += text;
				logWithTime(`Chunk ${chunkCount} decoded`);

				logWithTime(
					`Decoded text: "${text.slice(0, 100)}${text.length > 100 ? '...' : ''}" (buffer size: ${buffer.length})`
				);

				// Process complete lines from the buffer
				const startProcess = Date.now();
				const lines = buffer.split('\n');
				buffer = lines.pop() || ''; // Keep the last incomplete line in the buffer

				for (const line of lines) {
					if (line.trim() === '') continue;

					logWithTime(`Processing line: "${line.slice(0, 50)}${line.length > 50 ? '...' : ''}"`);

					try {
						// Try parsing as JSON
						if (line.startsWith('data: ')) {
							const jsonData = line.slice(5).trim();
							if (jsonData === '[DONE]') {
								logWithTime('Received [DONE] signal');
								continue;
							}

							const data = JSON.parse(jsonData);
							logWithTime(`Parsed JSON data: ${JSON.stringify(data).slice(0, 100)}...`);

							// Handle chat completion response
							if (data.choices && data.choices[0]) {
								const delta = data.choices[0].delta;

								if (delta && delta.content) {
									const startTokenProcess = Date.now();
									currentText += delta.content;
									logWithTime(
										`Received new token: "${delta.content}" (current length: ${currentText.length})`
									);
									// Update UI immediately with each token
									updateAssistantMessage(currentText);
									logWithTime(`Token applied to UI in ${Date.now() - startTokenProcess}ms`);
								}
							}
						}
					} catch (e) {
						console.error('Error parsing line:', e, line);
					}
				}

				// If there's anything in the buffer, try to update with it too
				if (buffer.trim() !== '') {
					logWithTime(
						`Processing partial buffer: "${buffer.slice(0, 50)}${buffer.length > 50 ? '...' : ''}"`
					);
					try {
						if (buffer.startsWith('data: ')) {
							const jsonData = buffer.slice(5).trim();
							if (jsonData !== '[DONE]') {
								try {
									const data = JSON.parse(jsonData);
									if (data.choices && data.choices[0]) {
										const delta = data.choices[0].delta;
										if (delta && delta.content) {
											currentText += delta.content;
											updateAssistantMessage(currentText);
										}
									}
								} catch (e) {
									// Incomplete JSON, this is expected for partial chunks
								}
							}
						}
					} catch (e) {
						// Ignore errors in partial buffer processing
					}
				}

				const endProcess = Date.now();
				logWithTime(`Processed ${lines.length} lines in ${endProcess - startProcess}ms`);

				// Calculate how much time passed since last update
				const timeSinceLastUpdate = now - lastUpdateTime;
				logWithTime(`Time since last update: ${timeSinceLastUpdate}ms`);

				// Update the last update time
				lastUpdateTime = now;
			}

			logWithTime(`Stream processing complete. Total content length: ${currentText.length}`);
		} catch (/** @type {unknown} */ error) {
			logWithTime(
				`Error processing stream: ${error instanceof Error ? error.message : String(error)}`
			);
			console.error('Stream error details:', error);
		} finally {
			// Process any remaining text in the buffer
			if (buffer) {
				logWithTime(`Processing remaining buffer: ${buffer.length} bytes`);
				const lines = buffer.split('\n');
				for (const line of lines) {
					if (!line.trim() || !line.startsWith('data: ')) continue;

					const data = line.slice(6);
					if (data === '[DONE]') continue;

					try {
						const parsed = JSON.parse(data);
						if (parsed.choices && parsed.choices[0]?.delta?.content) {
							currentText += parsed.choices[0].delta.content;
							updateAssistantMessage(currentText);
							logWithTime(`Added final delta: "${parsed.choices[0].delta.content}"`);
						}
					} catch (/** @type {unknown} */ err) {
						logWithTime(
							`Error parsing final line: ${err instanceof Error ? err.message : String(err)}`
						);
					}
				}
			}

			// Ensure decoder is flushed
			const remaining = decoder.decode();
			if (remaining) {
				logWithTime(`Final decoder flush: ${remaining.length} bytes`);
			}

			logWithTime('Stream processing finished');
		}
	}

	/**
	 * Updates the assistant message with new content
	 * @param {string} content - The new content to set
	 */
	function updateAssistantMessage(content) {
		if (!content) return;

		const startUpdate = Date.now();
		logWithTime(`Starting UI update with content length: ${content.length}`);

		const lastIdx = messages.length - 1;
		if (lastIdx >= 0 && messages[lastIdx].role === 'assistant') {
			// Create a new array with the updated message to ensure reactivity
			logWithTime(`Found assistant message at index ${lastIdx}, updating content`);
			messages = [...messages.slice(0, lastIdx), { ...messages[lastIdx], content }];
		} else {
			logWithTime(`No assistant message found to update`);
		}

		logWithTime(`Message store updated in ${Date.now() - startUpdate}ms`);
	}

	/**
	 * Handle form submission and send message to API
	 * @param {Event} e - Form submission event
	 */
	async function handleSubmit(e) {
		e.preventDefault();

		const inputValue = input;
		if (!inputValue.trim()) return;

		logWithTime(`Submitting message: "${inputValue}"`);

		// Add user message
		/** @type {Message} */
		const userMessage = {
			id: Date.now().toString(),
			role: 'user',
			content: inputValue
		};

		messages = [...messages, userMessage];
		input = '';
		isLoading = true;
		isStreaming = true;

		try {
			// Convert messages to OpenAI format
			const openAIMessages = messages.map((msg) => ({
				role: msg.role,
				content: msg.content
			}));

			logWithTime(
				`Sending request with ${openAIMessages.length} messages to model: ${selectedModel}`
			);

			// Create assistant message as a placeholder
			/** @type {Message} */
			const assistantMessage = {
				id: (Date.now() + 1).toString(),
				role: 'assistant',
				content: ''
			};

			messages = [...messages, assistantMessage];
			logWithTime('Added placeholder assistant message');

			// Custom streaming implementation with anti-buffering techniques
			const fetchStart = Date.now();
			const streamOptions = {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					Authorization: `Bearer ${API_KEY}`
				},
				body: JSON.stringify({
					model: selectedModel,
					messages: openAIMessages,
					stream: true
				})
			};

			logWithTime(`Request details prepared, connecting to ${API_URL}/chat/completions`);

			try {
				const response = await fetch(`${API_URL}/chat/completions`, streamOptions);

				logWithTime(
					`API responded in ${Date.now() - fetchStart}ms with status: ${response.status}`
				);

				if (!response.ok) {
					throw new Error(`API error: ${response.status}`);
				}

				if (!response.body) {
					throw new Error('Response body is not readable');
				}

				// Get the response as a readable stream with small delay between chunks
				logWithTime('Starting to process response stream');

				const reader = response.body.getReader();
				const decoder = new TextDecoder();
				let currentText = '';
				let buffer = '';

				while (true) {
					const { done, value } = await reader.read();

					if (done) {
						logWithTime('Stream completed');
						break;
					}

					// Log when we get data, before processing
					logWithTime(`Received chunk of size: ${value.byteLength} bytes`);

					// Process text immediately when received
					const chunk = decoder.decode(value, { stream: true });
					buffer += chunk;

					// Parse complete lines from the buffer
					const lines = buffer.split('\n');
					buffer = lines.pop() || ''; // Keep the last incomplete line in buffer

					// Process each line immediately
					for (const line of lines) {
						if (!line.trim() || !line.startsWith('data: ')) continue;

						const content = line.slice(5).trim();
						if (content === '[DONE]') continue;

						try {
							const parsed = JSON.parse(content);
							const textContent = parsed.choices?.[0]?.delta?.content;

							if (textContent) {
								currentText += textContent;
								logWithTime(
									`Received text: "${textContent}" (current length: ${currentText.length})`
								);
								updateAssistantMessage(currentText);
							}
						} catch (/** @type {unknown} */ err) {
							const errorMsg = err instanceof Error ? err.message : String(err);
							logWithTime(`Error parsing: ${errorMsg}`);
						}
					}
				}

				logWithTime('Streaming completed successfully');
			} catch (/** @type {unknown} */ error) {
				logWithTime(`Stream error: ${error instanceof Error ? error.message : String(error)}`);
				throw error;
			}
		} catch (/** @type {unknown} */ error) {
			logWithTime(
				`Error during request: ${error instanceof Error ? error.message : 'Unknown error'}`
			);
			console.error('Error details:', error);

			// Add error message
			/** @type {Message} */
			const errorMessage = {
				id: Date.now().toString(),
				role: 'assistant',
				content: 'Sorry, an error occurred. Please try again.'
			};
			messages = [...messages, errorMessage];
		} finally {
			isLoading = false;
			isStreaming = false;
			logWithTime('Request handling completed');
		}
	}

	/**
	 * Retry loading models if they failed to load
	 */
	function retryLoadModels() {
		fetchModels();
	}
</script>

<div class="space-y-6">
	<h1 class="text-2xl font-bold text-gray-800">OpenAI Chat</h1>

	<!-- Connection Details (kept for reference) -->
	<div class="rounded-md border bg-white p-4 shadow-sm">
		<h2 class="text-lg font-semibold text-gray-700">Connection Details</h2>
		<p>Using API URL: {API_URL}</p>
		<p>Using API Key: {API_KEY}</p>
	</div>

	<!-- Model Selection -->
	<div class="rounded-md border bg-white p-4 shadow-sm">
		<h2 class="mb-2 text-lg font-semibold text-gray-700">Model Selection</h2>

		{#if isLoadingModels}
			<div class="flex items-center">
				<svg
					class="mr-3 h-5 w-5 animate-spin text-indigo-500"
					xmlns="http://www.w3.org/2000/svg"
					fill="none"
					viewBox="0 0 24 24"
				>
					<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"
					></circle>
					<path
						class="opacity-75"
						fill="currentColor"
						d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
					></path>
				</svg>
				<span>Loading available models...</span>
			</div>
		{:else if modelsError}
			<div class="mb-2 text-red-500">
				{modelsError}
			</div>
			<button
				onclick={retryLoadModels}
				class="rounded bg-indigo-500 px-4 py-1 text-white hover:bg-indigo-600"
			>
				Retry
			</button>
		{:else if models.length === 0}
			<p>No models available.</p>
		{:else}
			<div class="flex items-center">
				<label for="model-select" class="mr-2">Choose a model:</label>
				<select
					id="model-select"
					bind:value={selectedModel}
					class="rounded-md border p-2 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 focus:outline-none"
				>
					{#each models as model}
						<option value={model}>{model}</option>
					{/each}
				</select>
			</div>
		{/if}
	</div>

	<!-- Chat Interface -->
	<div class="space-y-4 rounded-md border bg-white p-4 shadow-sm">
		<h2 class="text-lg font-semibold text-gray-700">Chat</h2>

		<!-- Message List -->
		<div class="h-96 space-y-3 overflow-y-auto rounded border bg-gray-50 p-3" id="chat-messages">
			{#each messages as message}
				<div class={message.role === 'user' ? 'text-right' : 'text-left'}>
					<div
						class="inline-block rounded-lg px-4 py-2 {message.role === 'user'
							? 'bg-blue-500 text-white'
							: 'bg-gray-200 text-gray-800'}"
					>
						<!-- Display message content as plain text -->
						{message.content}

						<!-- Show indicator for streaming messages -->
						{#if isStreaming && message.role === 'assistant' && message === messages[messages.length - 1]}
							<span class="ml-1 inline-block h-4 w-2 animate-pulse bg-current"></span>
						{/if}
					</div>
				</div>
			{/each}

			{#if isLoading && messages.length === 0}
				<div class="text-left">
					<div class="inline-block animate-pulse rounded-lg bg-gray-200 px-4 py-2 text-gray-800">
						...
					</div>
				</div>
			{/if}
		</div>

		<!-- Input Form -->
		<form onsubmit={handleSubmit} class="flex space-x-2">
			<input
				bind:value={input}
				type="text"
				placeholder="Send a message..."
				class="flex-grow rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 focus:outline-none sm:text-sm"
				disabled={isLoading}
			/>
			<button
				type="submit"
				disabled={isLoading || !input.length}
				class="bg-brand hover:bg-brand-hover focus:ring-brand inline-flex items-center rounded-md border border-transparent px-4 py-2 text-sm font-medium text-white shadow-sm focus:ring-2 focus:ring-offset-2 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
				style="background-color: #2271b3;"
			>
				{#if isLoading}
					<svg
						class="mr-3 -ml-1 h-5 w-5 animate-spin text-white"
						xmlns="http://www.w3.org/2000/svg"
						fill="none"
						viewBox="0 0 24 24"
					>
						<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"
						></circle>
						<path
							class="opacity-75"
							fill="currentColor"
							d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
						></path>
					</svg>
					Sending...
				{:else}
					Send
				{/if}
			</button>
		</form>
	</div>
</div>
