<script>
	import { onMount } from 'svelte';
	import { getConfig } from '$lib/config';
	import { user } from '$lib/stores/userStore';
	import axios from 'axios';

	let config = {};
	/** @type {any} */
	let mcpStatus = null;
	/** @type {any[]} */
	let mcpPrompts = [];
	/** @type {any[]} */
	let mcpTools = [];
	/** @type {any[]} */
	let mcpResources = [];
	let loading = false;
	/** @type {string | null} */
	let error = null;
	/** @type {any} */
	let selectedPrompt = null;
	/** @type {any} */
	let promptArguments = {};
	/** @type {any} */
	let promptResult = null;
	/** @type {any} */
	let selectedTool = null;
	/** @type {any} */
	let toolArguments = {};
	/** @type {any} */
	let toolResult = null;
	let activeTab = 'prompts';

	onMount(() => {
		config = getConfig();
		loadMcpStatus();
	});

	// Get the MCP base URL
	/**
	 * @param {string} endpoint
	 */
	function getMcpUrl(endpoint) {
		const lambServer = config?.api?.lambServer || 'http://localhost:9099';
		return `${lambServer.replace(/\/$/, '')}/lamb/v1/mcp${endpoint}`;
	}

	// Get API headers with authentication
	function getHeaders() {
		const ltiSecret = config?.api?.ltiSecret || 'pepino-secret-key';
		const userEmail = $user.email || 'test@example.com'; // Get from user store

		return {
			Authorization: `Bearer ${ltiSecret}`,
			'X-User-Email': userEmail,
			'Content-Type': 'application/json'
		};
	}

	async function loadMcpStatus() {
		loading = true;
		error = null;
		try {
			const response = await axios.get(getMcpUrl('/status'), {
				headers: getHeaders()
			});
			mcpStatus = response.data;
		} catch (err) {
			console.error('Error loading MCP status:', err);
			error = err.response?.data?.detail || err.message || 'Failed to load MCP status';
		} finally {
			loading = false;
		}
	}

	async function loadMcpPrompts() {
		activeTab = 'prompts';
		loading = true;
		error = null;
		try {
			const response = await axios.get(getMcpUrl('/prompts'), {
				headers: getHeaders()
			});
			mcpPrompts = response.data.prompts || [];
		} catch (err) {
			console.error('Error loading MCP prompts:', err);
			error = err.response?.data?.detail || err.message || 'Failed to load MCP prompts';
		} finally {
			loading = false;
		}
	}

	async function loadMcpTools() {
		activeTab = 'tools';
		loading = true;
		error = null;
		try {
			const response = await axios.get(getMcpUrl('/tools'), {
				headers: getHeaders()
			});
			mcpTools = response.data.tools || [];
		} catch (err) {
			console.error('Error loading MCP tools:', err);
			error = err.response?.data?.detail || err.message || 'Failed to load MCP tools';
		} finally {
			loading = false;
		}
	}

	async function loadMcpResources() {
		activeTab = 'resources';
		loading = true;
		error = null;
		try {
			const response = await axios.get(getMcpUrl('/resources'), {
				headers: getHeaders()
			});
			mcpResources = response.data.resources || [];
		} catch (err) {
			console.error('Error loading MCP resources:', err);
			error = err.response?.data?.detail || err.message || 'Failed to load MCP resources';
		} finally {
			loading = false;
		}
	}

	async function testPrompt() {
		if (!selectedPrompt) return;

		loading = true;
		error = null;
		try {
			const response = await axios.post(
				getMcpUrl('/prompts/get'),
				{
					name: selectedPrompt.name,
					arguments: promptArguments
				},
				{
					headers: getHeaders()
				}
			);
			promptResult = response.data;
		} catch (err) {
			console.error('Error testing prompt:', err);
			error = err.response?.data?.detail || err.message || 'Failed to test prompt';
		} finally {
			loading = false;
		}
	}

	async function testTool() {
		if (!selectedTool) return;

		loading = true;
		error = null;
		try {
			const response = await axios.post(
				getMcpUrl('/tools/call'),
				{
					name: selectedTool.name,
					arguments: toolArguments
				},
				{
					headers: getHeaders()
				}
			);
			toolResult = response.data;
		} catch (err) {
			console.error('Error testing tool:', err);
			error = err.response?.data?.detail || err.message || 'Failed to test tool';
		} finally {
			loading = false;
		}
	}

	/**
	 * @param {any} prompt
	 */
	function selectPrompt(prompt) {
		selectedPrompt = prompt;
		promptArguments = {};
		promptResult = null;
		// Initialize arguments based on prompt schema
		if (prompt.arguments) {
			prompt.arguments.forEach((arg) => {
				promptArguments[arg.name] = '';
			});
		}
	}

	/**
	 * @param {any} tool
	 */
	function selectTool(tool) {
		selectedTool = tool;
		toolArguments = {};
		toolResult = null;
		// Initialize arguments based on tool schema
		if (tool.inputSchema && tool.inputSchema.properties) {
			Object.keys(tool.inputSchema.properties).forEach((key) => {
				toolArguments[key] = '';
			});
		}
	}
</script>

<div class="space-y-6">
	<!-- User Authentication Check -->
	{#if !$user.isLoggedIn}
		<div class="rounded border border-yellow-400 bg-yellow-100 px-4 py-3 text-yellow-700">
			<strong>Authentication Required:</strong> Please log in to access the MCP testing interface.
		</div>
	{:else}
		<!-- Error Display -->
		{#if error}
			<div class="rounded border border-red-400 bg-red-100 px-4 py-3 text-red-700">
				<strong>Error:</strong>
				{error}
			</div>
		{/if}

		<!-- Loading Indicator -->
		{#if loading}
			<div class="rounded border border-blue-400 bg-blue-100 px-4 py-3 text-blue-700">
				Loading...
			</div>
		{/if}

		<!-- MCP Status Section -->
		<div class="rounded-lg bg-white p-6 shadow-md">
			<h3 class="mb-4 text-lg font-semibold text-gray-800">MCP Server Status</h3>
			{#if mcpStatus}
				<div class="space-y-3">
					<div class="flex items-center">
						<span class="w-24 font-medium text-gray-700">Status:</span>
						<span class="rounded-full bg-green-100 px-2 py-1 text-sm text-green-800">Connected</span
						>
					</div>
					<div class="flex items-center">
						<span class="w-24 font-medium text-gray-700">Version:</span>
						<span class="text-gray-600">{mcpStatus.version || 'Unknown'}</span>
					</div>
					<div class="flex items-center">
						<span class="w-24 font-medium text-gray-700">Capabilities:</span>
						<div class="flex flex-wrap gap-2">
							{#each mcpStatus.capabilities || [] as capability}
								<span class="rounded bg-blue-100 px-2 py-1 text-sm text-blue-800">{capability}</span
								>
							{/each}
						</div>
					</div>
				</div>
			{:else}
				<p class="text-gray-500">Loading status...</p>
			{/if}
		</div>

		<!-- Navigation Tabs -->
		<div class="rounded-lg bg-white shadow-md">
			<div class="border-b border-gray-200">
				<nav class="-mb-px flex space-x-8 px-6">
					<button
						on:click={loadMcpPrompts}
						class="border-b-2 px-1 py-4 text-sm font-medium {activeTab === 'prompts'
							? 'border-[#2271b3] text-[#2271b3]'
							: 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'}"
					>
						Prompts
					</button>
					<button
						on:click={loadMcpTools}
						class="border-b-2 px-1 py-4 text-sm font-medium {activeTab === 'tools'
							? 'border-[#2271b3] text-[#2271b3]'
							: 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'}"
					>
						Tools
					</button>
					<button
						on:click={loadMcpResources}
						class="border-b-2 px-1 py-4 text-sm font-medium {activeTab === 'resources'
							? 'border-[#2271b3] text-[#2271b3]'
							: 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'}"
					>
						Resources
					</button>
					<button
						on:click={() => (activeTab = 'setup')}
						class="border-b-2 px-1 py-4 text-sm font-medium {activeTab === 'setup'
							? 'border-[#2271b3] text-[#2271b3]'
							: 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'}"
					>
						Client Setup
					</button>
				</nav>
			</div>

			<!-- Prompts Section -->
			{#if activeTab === 'prompts'}
				{#if mcpPrompts.length > 0}
					<div class="p-6">
						<div class="grid grid-cols-1 gap-6 lg:grid-cols-2">
							<!-- Prompts List -->
							<div>
								<h4 class="mb-3 font-medium text-gray-700">Available Prompts</h4>
								<div class="space-y-2">
									{#each mcpPrompts as prompt}
										<button
											on:click={() => selectPrompt(prompt)}
											class="w-full rounded border p-3 text-left hover:bg-gray-50 {selectedPrompt?.name ===
											prompt.name
												? 'border-[#2271b3] bg-blue-50'
												: 'border-gray-200'}"
										>
											<div class="font-medium">{prompt.name}</div>
											<div class="text-sm text-gray-600">{prompt.description}</div>
										</button>
									{/each}
								</div>
							</div>

							<!-- Prompt Testing -->
							{#if selectedPrompt}
								<div>
									<h4 class="mb-2 font-medium text-gray-700">Test Prompt: {selectedPrompt.name}</h4>
									<div class="space-y-3">
										{#if selectedPrompt.arguments}
											{#each selectedPrompt.arguments as arg}
												<div>
													<label
														for="prompt-arg-{arg.name}"
														class="mb-1 block text-sm font-medium text-gray-700"
													>
														{arg.name}
														{arg.required ? '*' : ''}
													</label>
													<input
														id="prompt-arg-{arg.name}"
														type="text"
														bind:value={promptArguments[arg.name]}
														placeholder={arg.description}
														class="w-full rounded-md border border-gray-300 px-3 py-2 focus:border-transparent focus:ring-2 focus:ring-[#2271b3] focus:outline-none"
													/>
												</div>
											{/each}
										{/if}
										<button
											on:click={testPrompt}
											class="rounded bg-[#2271b3] px-4 py-2 text-white hover:bg-[#1e5a8a]"
											disabled={loading}
										>
											Test Prompt
										</button>
									</div>

									{#if promptResult}
										<div class="mt-4">
											<h5 class="mb-2 font-medium text-gray-700">Result:</h5>
											<pre class="overflow-auto rounded bg-gray-100 p-3 text-sm">{JSON.stringify(
													promptResult,
													null,
													2
												)}</pre>
										</div>
									{/if}
								</div>
							{/if}
						</div>
					</div>
				{:else}
					<div class="p-6 text-center text-gray-500">
						<p>No prompts available. You need to create assistants first.</p>
					</div>
				{/if}
			{/if}

			<!-- Tools Section -->
			{#if activeTab === 'tools'}
				{#if mcpTools.length > 0}
					<div class="p-6">
						<div class="grid grid-cols-1 gap-6 lg:grid-cols-2">
							<!-- Tools List -->
							<div>
								<h4 class="mb-3 font-medium text-gray-700">Available Tools</h4>
								<div class="space-y-2">
									{#each mcpTools as tool}
										<button
											on:click={() => selectTool(tool)}
											class="w-full rounded border p-3 text-left hover:bg-gray-50 {selectedTool?.name ===
											tool.name
												? 'border-[#2271b3] bg-blue-50'
												: 'border-gray-200'}"
										>
											<div class="font-medium">{tool.name}</div>
											<div class="text-sm text-gray-600">{tool.description}</div>
										</button>
									{/each}
								</div>
							</div>

							<!-- Tool Testing -->
							{#if selectedTool}
								<div>
									<h4 class="mb-2 font-medium text-gray-700">Test Tool: {selectedTool.name}</h4>
									<div class="space-y-3">
										{#if selectedTool.inputSchema?.properties}
											{#each Object.entries(selectedTool.inputSchema.properties) as [key, prop]}
												<div>
													<label
														for="tool-arg-{key}"
														class="mb-1 block text-sm font-medium text-gray-700"
													>
														{key}
														{selectedTool.inputSchema.required?.includes(key) ? '*' : ''}
													</label>
													<input
														id="tool-arg-{key}"
														type="text"
														bind:value={toolArguments[key]}
														placeholder={prop.description || ''}
														class="w-full rounded-md border border-gray-300 px-3 py-2 focus:border-transparent focus:ring-2 focus:ring-[#2271b3] focus:outline-none"
													/>
												</div>
											{/each}
										{/if}
										<button
											on:click={testTool}
											class="rounded bg-[#2271b3] px-4 py-2 text-white hover:bg-[#1e5a8a]"
											disabled={loading}
										>
											Test Tool
										</button>
									</div>

									{#if toolResult}
										<div class="mt-4">
											<h5 class="mb-2 font-medium text-gray-700">Result:</h5>
											<pre class="overflow-auto rounded bg-gray-100 p-3 text-sm">{JSON.stringify(
													toolResult,
													null,
													2
												)}</pre>
										</div>
									{/if}
								</div>
							{/if}
						</div>
					</div>
				{:else}
					<div class="p-6 text-center text-gray-500">
						<p>No tools available yet.</p>
					</div>
				{/if}
			{/if}

			<!-- Resources Section -->
			{#if activeTab === 'resources'}
				{#if mcpResources.length > 0}
					<div class="p-6">
						<h4 class="mb-3 font-medium text-gray-700">Available Resources</h4>
						<div class="space-y-3">
							{#each mcpResources as resource}
								<div class="rounded border p-3">
									<div class="font-medium">{resource.name}</div>
									<div class="text-sm text-gray-600">{resource.description}</div>
									<div class="mt-1 text-xs text-gray-500">URI: {resource.uri}</div>
								</div>
							{/each}
						</div>
					</div>
				{:else}
					<div class="p-6 text-center text-gray-500">
						<p>No resources available yet.</p>
					</div>
				{/if}
			{/if}

			<!-- Setup Section -->
			{#if activeTab === 'setup'}
				<div class="p-6">
					<h4 class="mb-3 font-medium text-gray-700">MCP Client Setup</h4>
					<div class="space-y-4">
						<div class="rounded bg-gray-50 p-4">
							<h5 class="mb-2 font-medium">Server Configuration</h5>
							<pre class="text-sm text-gray-700">{JSON.stringify(
									{
										command: 'python',
										args: ['-m', 'lamb.mcp_server'],
										env: {
											LAMB_SERVER_URL: config?.api?.lambServer || 'http://localhost:9099',
											LAMB_API_KEY: '***REDACTED***'
										}
									},
									null,
									2
								)}</pre>
						</div>
						<div class="text-sm text-gray-600">
							<p>Add this configuration to your MCP client to connect to the LAMB server.</p>
							<p class="mt-2">
								<strong>Note:</strong> Replace the API key with your actual LAMB API key.
							</p>
						</div>
					</div>
				</div>
			{/if}
		</div>
	{/if}
</div>
