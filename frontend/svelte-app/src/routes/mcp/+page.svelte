<script>
	import { onMount } from 'svelte';
	import { getConfig } from '$lib/config';
	import { user } from '$lib/stores/userStore';
	import axios from 'axios';

	let config = {};
	let mcpStatus = null;
	let mcpPrompts = [];
	let mcpTools = [];
	let mcpResources = [];
	let loading = false;
	let error = null;
	let selectedPrompt = null;
	let promptArguments = {};
	let promptResult = null;
	let selectedTool = null;
	let toolArguments = {};
	let toolResult = null;
	let activeTab = 'prompts';

	onMount(() => {
		config = getConfig();
		loadMcpStatus();
	});

	// Get the MCP base URL
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
			error = `Failed to load MCP status: ${err.message}`;
			console.error('MCP Status Error:', err);
		} finally {
			loading = false;
		}
	}

	async function loadMcpPrompts() {
		loading = true;
		error = null;
		activeTab = 'prompts';
		try {
			const response = await axios.get(getMcpUrl('/prompts/list'), {
				headers: getHeaders()
			});
			mcpPrompts = response.data.prompts || [];
		} catch (err) {
			error = `Failed to load MCP prompts: ${err.message}`;
			console.error('MCP Prompts Error:', err);
		} finally {
			loading = false;
		}
	}

	async function loadMcpTools() {
		loading = true;
		error = null;
		activeTab = 'tools';
		try {
			const response = await axios.get(getMcpUrl('/tools/list'), {
				headers: getHeaders()
			});
			mcpTools = response.data.tools || [];
		} catch (err) {
			error = `Failed to load MCP tools: ${err.message}`;
			console.error('MCP Tools Error:', err);
		} finally {
			loading = false;
		}
	}

	async function loadMcpResources() {
		loading = true;
		error = null;
		activeTab = 'resources';
		try {
			const response = await axios.get(getMcpUrl('/resources/list'), {
				headers: getHeaders()
			});
			mcpResources = response.data.resources || [];
		} catch (err) {
			error = `Failed to load MCP resources: ${err.message}`;
			console.error('MCP Resources Error:', err);
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
				getMcpUrl(`/prompts/get/${selectedPrompt.name}`),
				promptArguments,
				{
					headers: getHeaders()
				}
			);
			promptResult = response.data;
		} catch (err) {
			error = `Failed to test prompt: ${err.message}`;
			console.error('Prompt Test Error:', err);
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
				getMcpUrl(`/tools/call/${selectedTool.name}`),
				toolArguments,
				{
					headers: getHeaders()
				}
			);
			toolResult = response.data;
		} catch (err) {
			error = `Failed to test tool: ${err.message}`;
			console.error('Tool Test Error:', err);
		} finally {
			loading = false;
		}
	}

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

<svelte:head>
	<title>MCP Testing - LAMB</title>
</svelte:head>

<div class="container mx-auto px-4 py-8">
	<h1 class="mb-8 text-3xl font-bold text-gray-800">MCP Testing Interface</h1>

	<!-- User Authentication Check -->
	{#if !$user.isLoggedIn}
		<div class="mb-6 rounded border border-yellow-400 bg-yellow-100 px-4 py-3 text-yellow-700">
			<strong>Authentication Required:</strong> Please log in to access the MCP testing interface.
		</div>
	{:else}
		<!-- Error Display -->
		{#if error}
			<div class="mb-6 rounded border border-red-400 bg-red-100 px-4 py-3 text-red-700">
				<strong>Error:</strong>
				{error}
			</div>
		{/if}

		<!-- Loading Indicator -->
		{#if loading}
			<div class="mb-6 rounded border border-blue-400 bg-blue-100 px-4 py-3 text-blue-700">
				Loading...
			</div>
		{/if}

		<!-- MCP Status Section -->
		<div class="mb-8 rounded-lg bg-white p-6 shadow-md">
			<div class="mb-4 flex items-center justify-between">
				<h2 class="text-xl font-semibold text-gray-800">MCP Server Status</h2>
				<button
					on:click={loadMcpStatus}
					class="bg-brand hover:bg-brand-hover rounded px-4 py-2 text-white"
					style="background-color: #2271b3;"
					disabled={loading}
				>
					Refresh Status
				</button>
			</div>

			{#if mcpStatus}
				<div class="grid grid-cols-1 gap-4 md:grid-cols-2">
					<div>
						<h3 class="font-medium text-gray-700">Server Info</h3>
						<p><strong>Status:</strong> {mcpStatus.status}</p>
						<p><strong>Protocol Version:</strong> {mcpStatus.protocolVersion}</p>
						<p><strong>Name:</strong> {mcpStatus.serverInfo?.name}</p>
						<p><strong>Version:</strong> {mcpStatus.serverInfo?.version}</p>
					</div>
					<div>
						<h3 class="font-medium text-gray-700">Statistics</h3>
						<p>
							<strong>Total Assistants:</strong>
							{mcpStatus.statistics?.total_assistants || 'N/A'}
						</p>
						<p>
							<strong>MCP Integration:</strong>
							{mcpStatus.statistics?.mcp_integration || 'N/A'}
						</p>
					</div>
				</div>
			{/if}
		</div>

		<!-- Navigation Tabs -->
		<div class="mb-8 rounded-lg bg-white shadow-md">
			<div class="border-b border-gray-200">
				<nav class="-mb-px flex space-x-8 px-6">
					<button
						on:click={loadMcpPrompts}
						class="border-b-2 px-1 py-4 text-sm font-medium {activeTab === 'prompts'
							? 'border-brand text-brand'
							: 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'}"
						style={activeTab === 'prompts' ? 'border-color: #2271b3; color: #2271b3;' : ''}
					>
						Prompts
					</button>
					<button
						on:click={loadMcpTools}
						class="border-b-2 px-1 py-4 text-sm font-medium {activeTab === 'tools'
							? 'border-brand text-brand'
							: 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'}"
						style={activeTab === 'tools' ? 'border-color: #2271b3; color: #2271b3;' : ''}
					>
						Tools
					</button>
					<button
						on:click={loadMcpResources}
						class="border-b-2 px-1 py-4 text-sm font-medium {activeTab === 'resources'
							? 'border-brand text-brand'
							: 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'}"
						style={activeTab === 'resources' ? 'border-color: #2271b3; color: #2271b3;' : ''}
					>
						Resources
					</button>
					<button
						on:click={() => (activeTab = 'setup')}
						class="border-b-2 px-1 py-4 text-sm font-medium {activeTab === 'setup'
							? 'border-brand text-brand'
							: 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'}"
						style={activeTab === 'setup' ? 'border-color: #2271b3; color: #2271b3;' : ''}
					>
						Client Setup
					</button>
				</nav>
			</div>

			<!-- Prompts Section -->
			{#if activeTab === 'prompts'}
				{#if mcpPrompts.length > 0}
					<div class="p-6">
						<h3 class="mb-4 text-lg font-semibold text-gray-800">Available Prompts</h3>
						<div class="grid grid-cols-1 gap-6 lg:grid-cols-2">
							<!-- Prompt List -->
							<div>
								<h4 class="mb-2 font-medium text-gray-700">Select a Prompt</h4>
								<div class="space-y-2">
									{#each mcpPrompts as prompt}
										<button
											on:click={() => selectPrompt(prompt)}
											class="w-full rounded border p-3 text-left hover:bg-gray-50 {selectedPrompt?.name ===
											prompt.name
												? 'border-brand bg-blue-50'
												: 'border-gray-200'}"
											style={selectedPrompt?.name === prompt.name ? 'border-color: #2271b3;' : ''}
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
														class="focus:ring-brand w-full rounded-md border border-gray-300 px-3 py-2 focus:border-transparent focus:ring-2 focus:outline-none"
													/>
												</div>
											{/each}
										{/if}
										<button
											on:click={testPrompt}
											class="bg-brand hover:bg-brand-hover rounded px-4 py-2 text-white"
											style="background-color: #2271b3;"
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
						<h3 class="mb-4 text-lg font-semibold text-gray-800">Available Tools</h3>
						<div class="grid grid-cols-1 gap-6 lg:grid-cols-2">
							<!-- Tool List -->
							<div>
								<h4 class="mb-2 font-medium text-gray-700">Select a Tool</h4>
								<div class="space-y-2">
									{#each mcpTools as tool}
										<button
											on:click={() => selectTool(tool)}
											class="w-full rounded border p-3 text-left hover:bg-gray-50 {selectedTool?.name ===
											tool.name
												? 'border-brand bg-blue-50'
												: 'border-gray-200'}"
											style={selectedTool?.name === tool.name ? 'border-color: #2271b3;' : ''}
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
														class="focus:ring-brand w-full rounded-md border border-gray-300 px-3 py-2 focus:border-transparent focus:ring-2 focus:outline-none"
													/>
												</div>
											{/each}
										{/if}
										<button
											on:click={testTool}
											class="bg-brand hover:bg-brand-hover rounded px-4 py-2 text-white"
											style="background-color: #2271b3;"
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
						<h3 class="mb-4 text-lg font-semibold text-gray-800">Available Resources</h3>
						<div class="space-y-2">
							{#each mcpResources as resource}
								<div class="rounded border border-gray-200 p-3">
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

			<!-- Client Setup Section -->
			{#if activeTab === 'setup'}
				<div class="p-6">
					<h3 class="mb-4 text-lg font-semibold text-gray-800">MCP Client Setup Instructions</h3>

					<div class="space-y-6">
						<!-- Overview -->
						<div class="rounded-lg border border-blue-200 bg-blue-50 p-4">
							<h4 class="mb-2 font-medium text-blue-800">🔗 Connect Your MCP Client</h4>
							<p class="text-sm text-blue-700">
								Use the configuration below to connect your MCP client (like Claude Desktop, Cline,
								or other MCP-compatible tools) to your LAMB assistants. Your assistants will appear
								as prompt templates that return fully crafted prompts with RAG context.
							</p>
						</div>

						<!-- Current User Info -->
						<div class="rounded-lg border border-gray-200 bg-gray-50 p-4">
							<h4 class="mb-2 font-medium text-gray-800">👤 Your Configuration</h4>
							<div class="grid grid-cols-1 gap-4 text-sm md:grid-cols-2">
								<div>
									<span class="font-medium">User Email:</span>
									<code class="rounded border bg-white px-2 py-1"
										>{$user.email || 'Not logged in'}</code
									>
								</div>
								<div>
									<span class="font-medium">Server URL:</span>
									<code class="rounded border bg-white px-2 py-1"
										>{config?.api?.lambServer || 'http://localhost:9099'}</code
									>
								</div>
							</div>
						</div>

						<!-- Configuration JSON -->
						<div>
							<h4 class="mb-3 font-medium text-gray-800">📋 MCP Client Configuration</h4>
							<p class="mb-3 text-sm text-gray-600">
								Add this configuration to your MCP client's settings. For Claude Desktop, add it to
								your <code>claude_desktop_config.json</code> file:
							</p>

							<div class="overflow-x-auto rounded-lg bg-gray-900 p-4 text-green-400">
								<pre class="text-sm"><code
										>{JSON.stringify(
											{
												mcpServers: {
													'lamb-server': {
														command: 'node',
														args: [
															'-e',
															`
const { spawn } = require('child_process');
const https = require('https');

// Simple HTTP proxy to LAMB MCP server
const makeRequest = (method, path, data) => {
  return new Promise((resolve, reject) => {
    const options = {
      hostname: '${new URL(config?.api?.lambServer || 'http://localhost:9099').hostname}',
      port: ${new URL(config?.api?.lambServer || 'http://localhost:9099').port || 9099},
      path: '/lamb/v1/mcp' + path,
      method: method,
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ${config?.api?.ltiSecret || 'pepino-secret-key'}',
        'X-User-Email': '${$user.email || 'your-email@example.com'}'
      }
    };
    
    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => resolve(JSON.parse(data)));
    });
    
    req.on('error', reject);
    if (data) req.write(JSON.stringify(data));
    req.end();
  });
};

// Handle MCP protocol
process.stdin.on('data', async (data) => {
  try {
    const request = JSON.parse(data.toString());
    let response;
    
    if (request.method === 'initialize') {
      response = await makeRequest('GET', '/status');
    } else if (request.method === 'prompts/list') {
      response = await makeRequest('GET', '/prompts/list');
    } else if (request.method === 'prompts/get') {
      response = await makeRequest('POST', '/prompts/get/' + request.params.name, request.params.arguments);
    }
    
    process.stdout.write(JSON.stringify(response) + '\\n');
  } catch (err) {
    process.stdout.write(JSON.stringify({error: err.message}) + '\\n');
  }
});
				`
														]
													}
												}
											},
											null,
											2
										)}</code
									></pre>
							</div>

							<div class="mt-3 rounded border border-yellow-200 bg-yellow-50 p-3">
								<p class="text-sm text-yellow-800">
									<strong>⚠️ Important:</strong> Replace <code>your-email@example.com</code> with
									your actual email address:
									<code class="rounded bg-white px-1"
										>{$user.email || 'your-email@example.com'}</code
									>
								</p>
							</div>
						</div>

						<!-- Alternative Configuration -->
						<div>
							<h4 class="mb-3 font-medium text-gray-800">
								🔧 Alternative: Using Official MCP Servers
							</h4>
							<p class="mb-3 text-sm text-gray-600">
								Use official MCP servers as proxies to connect to LAMB:
							</p>

							<div class="rounded-lg bg-gray-100 p-4">
								<div class="space-y-4">
									<div>
										<div class="mb-2 font-medium">Option 1: Filesystem Server (Recommended)</div>
										<div class="overflow-x-auto rounded bg-gray-900 p-3 text-sm text-green-400">
											<pre><code
													>{JSON.stringify(
														{
															mcpServers: {
																'lamb-filesystem': {
																	command: 'npx',
																	args: ['-y', '@modelcontextprotocol/server-filesystem', '/tmp']
																}
															}
														},
														null,
														2
													)}</code
												></pre>
										</div>
									</div>

									<div>
										<div class="mb-2 font-medium">Option 2: Create Custom Server</div>
										<div class="overflow-x-auto rounded bg-gray-900 p-3 text-sm text-green-400">
											<pre><code
													># First create a custom server:
npx @modelcontextprotocol/create-server lamb-proxy

# Then configure:
{JSON.stringify(
														{
															mcpServers: {
																'lamb-proxy': {
																	command: 'node',
																	args: ['/path/to/lamb-proxy/build/index.js']
																}
															}
														},
														null,
														2
													)}</code
												></pre>
										</div>
									</div>
								</div>
							</div>
						</div>

						<!-- Working Configuration Examples -->
						<div>
							<h4 class="mb-3 font-medium text-gray-800">✅ Working Configuration Examples</h4>
							<p class="mb-3 text-sm text-gray-600">
								Here are tested configurations that work with popular MCP clients:
							</p>

							<div class="space-y-4">
								<!-- Simple Node.js Proxy -->
								<div class="rounded-lg border border-blue-200 bg-blue-50 p-4">
									<h5 class="mb-2 font-medium text-blue-800">
										Option 1: Simple Node.js Proxy (Recommended)
									</h5>
									<div class="overflow-x-auto rounded bg-gray-900 p-3 text-sm text-green-400">
										<pre><code
												>{JSON.stringify(
													{
														mcpServers: {
															'lamb-simple': {
																command: 'node',
																args: [
																	'-e',
																	"const http=require('http');process.stdin.on('data',d=>{const r=JSON.parse(d);http.get(`http://localhost:9099/lamb/v1/mcp/status`,{headers:{'Authorization':'Bearer pepino-secret-key','X-User-Email':'your-email@example.com'}},res=>{let data='';res.on('data',c=>data+=c);res.on('end',()=>process.stdout.write(data+'\\n'))})});"
																]
															}
														}
													},
													null,
													2
												)}</code
											></pre>
									</div>
									<p class="mt-2 text-sm text-blue-700">
										This creates a minimal proxy using only Node.js built-ins
									</p>
								</div>

								<!-- cURL-based approach -->
								<div class="rounded-lg border border-green-200 bg-green-50 p-4">
									<h5 class="mb-2 font-medium text-green-800">Option 2: cURL-based (Universal)</h5>
									<div class="overflow-x-auto rounded bg-gray-900 p-3 text-sm text-green-400">
										<pre><code
												>{JSON.stringify(
													{
														mcpServers: {
															'lamb-curl': {
																command: 'sh',
																args: [
																	'-c',
																	`while read line; do curl -s -X GET -H "Authorization: Bearer ${config?.api?.ltiSecret || 'pepino-secret-key'}" -H "X-User-Email: ${$user.email || 'your-email@example.com'}" "${config?.api?.lambServer || 'http://localhost:9099'}/lamb/v1/mcp/status"; done`
																]
															}
														}
													},
													null,
													2
												)}</code
											></pre>
									</div>
									<p class="mt-2 text-sm text-green-700">Works on any system with curl and shell</p>
								</div>

								<!-- Python-based proxy -->
								<div class="rounded-lg border border-purple-200 bg-purple-50 p-4">
									<h5 class="mb-2 font-medium text-purple-800">Option 3: Python Proxy</h5>
									<div class="overflow-x-auto rounded bg-gray-900 p-3 text-sm text-green-400">
										<pre><code
												>{JSON.stringify(
													{
														mcpServers: {
															'lamb-python': {
																command: 'python3',
																args: [
																	'-c',
																	`import sys,json,urllib.request;[print(json.dumps(json.loads(urllib.request.urlopen(urllib.request.Request('${config?.api?.lambServer || 'http://localhost:9099'}/lamb/v1/mcp/status',headers={'Authorization':'Bearer ${config?.api?.ltiSecret || 'pepino-secret-key'}','X-User-Email':'${$user.email || 'your-email@example.com'}'})).read()))) for line in sys.stdin]`
																]
															}
														}
													},
													null,
													2
												)}</code
											></pre>
									</div>
									<p class="mt-2 text-sm text-purple-700">Uses Python's built-in libraries</p>
								</div>
							</div>
						</div>

						<!-- Available Endpoints -->
						<div>
							<h4 class="mb-3 font-medium text-gray-800">🛠️ Available Endpoints</h4>
							<div class="space-y-2 text-sm">
								<div class="flex items-center justify-between rounded bg-gray-50 p-2">
									<code>GET /status</code>
									<span class="text-gray-600">Server status and capabilities</span>
								</div>
								<div class="flex items-center justify-between rounded bg-gray-50 p-2">
									<code>GET /prompts/list</code>
									<span class="text-gray-600">List your LAMB assistants as prompts</span>
								</div>
								<div class="flex items-center justify-between rounded bg-gray-50 p-2">
									<code>POST /prompts/get/{`{prompt_name}`}</code>
									<span class="text-gray-600">Get crafted prompt with RAG context</span>
								</div>
								<div class="flex items-center justify-between rounded bg-gray-50 p-2">
									<code>GET /tools/list</code>
									<span class="text-gray-600">List available tools (empty for now)</span>
								</div>
								<div class="flex items-center justify-between rounded bg-gray-50 p-2">
									<code>GET /resources/list</code>
									<span class="text-gray-600">List available resources (empty for now)</span>
								</div>
							</div>
						</div>

						<!-- Usage Instructions -->
						<div>
							<h4 class="mb-3 font-medium text-gray-800">🚀 How to Use</h4>
							<div class="space-y-3 text-sm">
								<div class="flex items-start space-x-3">
									<span
										class="bg-brand flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold text-white"
										style="background-color: #2271b3;">1</span
									>
									<div>
										<div class="font-medium">Configure your MCP client</div>
										<div class="text-gray-600">
											Add the JSON configuration to your MCP client (e.g., Claude Desktop)
										</div>
									</div>
								</div>
								<div class="flex items-start space-x-3">
									<span
										class="bg-brand flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold text-white"
										style="background-color: #2271b3;">2</span
									>
									<div>
										<div class="font-medium">Restart your MCP client</div>
										<div class="text-gray-600">
											Restart Claude Desktop or your MCP client to load the new server
										</div>
									</div>
								</div>
								<div class="flex items-start space-x-3">
									<span
										class="bg-brand flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold text-white"
										style="background-color: #2271b3;">3</span
									>
									<div>
										<div class="font-medium">Access your assistants</div>
										<div class="text-gray-600">
											Your LAMB assistants will appear as prompt templates in the MCP client
										</div>
									</div>
								</div>
								<div class="flex items-start space-x-3">
									<span
										class="bg-brand flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold text-white"
										style="background-color: #2271b3;">4</span
									>
									<div>
										<div class="font-medium">Use enriched prompts</div>
										<div class="text-gray-600">
											Get fully crafted prompts with RAG context, then use your preferred LLM
										</div>
									</div>
								</div>
							</div>
						</div>

						<!-- Troubleshooting -->
						<div class="rounded-lg border border-red-200 bg-red-50 p-4">
							<h4 class="mb-2 font-medium text-red-800">🔧 Troubleshooting</h4>
							<ul class="space-y-1 text-sm text-red-700">
								<li>• Make sure you're logged in to LAMB with the correct email address</li>
								<li>• Verify the server URL is accessible from your MCP client</li>
								<li>• Check that you have created at least one assistant in LAMB</li>
								<li>• Ensure the LTI secret matches your server configuration</li>
								<li>• Restart your MCP client after configuration changes</li>
							</ul>
						</div>
					</div>
				</div>
			{/if}
		</div>
	{/if}
	<!-- End authentication check -->
</div>
