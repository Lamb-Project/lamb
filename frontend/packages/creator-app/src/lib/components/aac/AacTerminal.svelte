<script>
	import { onMount, tick } from 'svelte';
	import { sendMessageStream, getSession, sendMessage } from '$lib/services/aacService';
	import { recordTabActivity } from '$lib/stores/aacStore.svelte';
	import { marked } from 'marked';

	/** @type {{ sessionId: string, firstMessage?: string, resumed?: boolean, skillStartup?: boolean }} */
	let { sessionId, firstMessage = '', resumed = false, skillStartup = false } = $props();

	/** @type {Array<{role: string, content: string}>} */
	let messages = $state([]);

	/** @type {string} */
	let inputText = $state('');

	/** @type {boolean} */
	let loading = $state(false);

	/** @type {string} */
	let statusText = $state('');

	/** @type {boolean} */
	let darkMode = $state(false);

	/** @type {HTMLElement|null} */
	let scrollContainer = null;

	/** @type {HTMLInputElement|null} */
	let inputEl = null;

	/** @type {Object|null} */
	let lastStats = $state(null);

	/** @type {boolean} */
	let showStats = $state(false);

	/** @type {{ title: string, content: string } | null} */
	let canvasData = $state(null);

	/**
	 * Split canvas directives from agent response.
	 * @param {string} text
	 * @returns {{ text: string, canvas: { title: string, content: string } | null }}
	 */
	function splitCanvasContent(text) {
		if (!text) return { text: '', canvas: null };
		const match = text.match(/<<<CANVAS(?:\s+title="([^"]*)")?>>>([\s\S]*?)<<<END_CANVAS>>>/);
		if (!match) {
			// Check for clear directive
			if (text.includes('<<<CANVAS_CLEAR>>>')) {
				return { text: text.replace(/<<<CANVAS_CLEAR>>>/g, '').trim(), canvas: null };
			}
			return { text, canvas: null };
		}
		const title = match[1] || '';
		const canvasContent = match[2].trim();
		const cleanText = text.replace(/<<<CANVAS[\s\S]*?<<<END_CANVAS>>>/, '').trim();
		return { text: cleanText, canvas: { title, content: canvasContent } };
	}

	/**
	 * Render an assistant message, extracting any canvas content.
	 * @param {string} content
	 * @returns {string}
	 */
	function renderAssistantMessage(content) {
		const { text, canvas } = splitCanvasContent(content);
		if (canvas) {
			canvasData = canvas;
		}
		return renderMarkdown(text);
	}

	onMount(async () => {
		// Check system preference
		if (window.matchMedia?.('(prefers-color-scheme: dark)').matches) {
			darkMode = true;
		}

		if (skillStartup) {
			// New skill session — trigger startup stream immediately
			await triggerSkillStartup();
		} else if (firstMessage) {
			messages = [{ role: 'assistant', content: firstMessage }];
		} else if (resumed) {
			// Resumed session — load history, hide internal [System:...] messages
			try {
				const session = await getSession(sessionId);
				const conv = (session.conversation || []).filter(
					m => (m.role === 'user' && !(m.content || '').startsWith('[System:'))
					  || (m.role === 'assistant' && m.content && !m.tool_calls)
				).map(m => ({ role: m.role, content: m.content || '' }));
				if (conv.length > 0) {
					messages = conv;
					resumeNotice = true;
				}
			} catch (e) {
				messages = [{ role: 'system', content: `Error loading session: ${e.message}` }];
			}
		}

		await tick();
		scrollToBottom();
		inputEl?.focus();
	});

	let resumeNotice = $state(false);

	async function triggerSkillStartup() {
		loading = true;
		let streamIdx = messages.length;
		messages = [...messages, { role: 'assistant', content: '' }];
		await tick();

		try {
			await sendMessageStream(
				sessionId,
				'[System: Skill startup]',
				(chunk) => {
					statusText = '';
					messages[streamIdx] = { ...messages[streamIdx], content: messages[streamIdx].content + chunk };
					messages = messages;
					scrollToBottom();
				},
				(stats) => { lastStats = stats; statusText = ''; },
				(err) => { messages[streamIdx] = { role: 'system', content: `Error: ${err}` }; messages = messages; },
				(status) => {
					if (status.status === 'thinking') statusText = '🧠 Thinking...';
					else if (status.status === 'tool') statusText = `⚡ ${status.command || 'Running'}...`;
					else if (status.status === 'tool_done') statusText = `${status.success ? '✓' : '✗'} ${status.command || 'Done'}`;
					else if (status.status === 'responding') statusText = '';
					scrollToBottom();
				},
			);
		} catch (e) {
			messages[streamIdx] = { role: 'system', content: `Error: ${e.message}` };
			messages = messages;
		}

		loading = false;
		await tick();
		scrollToBottom();
		inputEl?.focus();
	}

	async function handleSend() {
		const text = inputText.trim();
		if (!text || loading) return;

		// Check if user was away >5 min — prepend context note
		const wasAway = recordTabActivity(sessionId);
		let messageToSend = text;
		if (wasAway || resumeNotice) {
			messageToSend = `[System: User returned after being away. Things may have changed — don't assume earlier data is still current.]\n${text}`;
			resumeNotice = false;
		}

		messages = [...messages, { role: 'user', content: text }];
		inputText = '';
		loading = true;
		lastStats = null;

		await tick();
		scrollToBottom();

		// Add empty assistant message that will be filled by streaming
		let streamIdx = messages.length;
		messages = [...messages, { role: 'assistant', content: '' }];
		await tick();
		scrollToBottom();

		try {
			await sendMessageStream(
				sessionId,
				messageToSend,
				(chunk) => {
					statusText = '';
					messages[streamIdx] = { ...messages[streamIdx], content: messages[streamIdx].content + chunk };
					messages = messages;
					scrollToBottom();
				},
				(stats) => {
					lastStats = stats;
					statusText = '';
				},
				(err) => {
					statusText = '';
					messages[streamIdx] = { role: 'system', content: `Error: ${err}` };
					messages = messages;
				},
				(status) => {
					if (status.status === 'thinking') {
						statusText = '🧠 Thinking...';
					} else if (status.status === 'tool') {
						statusText = `⚡ ${status.command || 'Running command'}...`;
					} else if (status.status === 'tool_done') {
						statusText = `${status.success ? '✓' : '✗'} ${status.command || 'Done'}`;
					} else if (status.status === 'responding') {
						statusText = '';
					}
					scrollToBottom();
				},
			);
		} catch (e) {
			messages[streamIdx] = { role: 'system', content: `Error: ${e.message}` };
			messages = messages;
		}

		loading = false;
		await tick();
		scrollToBottom();
		inputEl?.focus();
	}

	function handleKeydown(e) {
		if (e.key === 'Enter' && !e.shiftKey) {
			e.preventDefault();
			handleSend();
		}
	}

	function scrollToBottom() {
		if (scrollContainer) {
			scrollContainer.scrollTop = scrollContainer.scrollHeight;
		}
	}

	function toggleDarkMode() {
		darkMode = !darkMode;
	}

	// Configure marked for terminal-style rendering
	marked.setOptions({ breaks: true, gfm: true });

	/**
	 * Render markdown to HTML using marked.
	 * @param {string} text
	 * @returns {string}
	 */
	function renderMarkdown(text) {
		if (!text) return '';
		return marked.parse(text);
	}
</script>

<div class="flex flex-col lg:flex-row h-full gap-0">
<!-- Terminal panel -->
<div
	class="flex flex-col font-mono text-sm rounded-lg border overflow-hidden transition-all duration-200
	       {canvasData ? 'lg:w-[55%] h-[60%] lg:h-full' : 'w-full h-full'}"
	class:bg-gray-900={darkMode}
	class:text-green-400={darkMode}
	class:border-gray-700={darkMode}
	class:bg-gray-50={!darkMode}
	class:text-gray-800={!darkMode}
	class:border-gray-300={!darkMode}
>
	<!-- Header -->
	<div
		class="flex items-center justify-between px-3 py-1.5 border-b text-xs"
		class:border-gray-700={darkMode}
		class:bg-gray-800={darkMode}
		class:border-gray-300={!darkMode}
		class:bg-gray-100={!darkMode}
	>
		<span class="opacity-60">AAC Agent — Session {sessionId.slice(0, 8)}...</span>
		<div class="flex gap-2 items-center">
			{#if lastStats}
				<button
					onclick={() => showStats = !showStats}
					class="opacity-40 hover:opacity-80 transition-opacity cursor-pointer"
					title="Toggle tool details"
				>
					{lastStats.tool_calls || 0} tools, {Math.round(lastStats.total_tool_time_ms || 0)}ms
					{showStats ? '▴' : '▾'}
				</button>
			{/if}
			<button
				onclick={toggleDarkMode}
				class="opacity-60 hover:opacity-100 transition-opacity"
				title="Toggle dark/light mode"
			>
				{darkMode ? '☀️' : '🌙'}
			</button>
		</div>
	</div>

	<!-- Stats Panel (collapsible) -->
	{#if showStats && lastStats}
		<div
			class="px-4 py-2 text-xs border-b flex flex-wrap gap-x-6 gap-y-1"
			class:border-gray-700={darkMode}
			class:bg-gray-800={darkMode}
			class:text-gray-400={darkMode}
			class:border-gray-200={!darkMode}
			class:bg-gray-50={!darkMode}
			class:text-gray-500={!darkMode}
		>
			<span>Model: <strong class:text-gray-200={darkMode} class:text-gray-700={!darkMode}>{lastStats.model || '?'}</strong></span>
			<span>Tool calls: <strong class:text-gray-200={darkMode} class:text-gray-700={!darkMode}>{lastStats.tool_calls || 0}</strong></span>
			<span>Errors: <strong class:text-gray-200={darkMode} class:text-gray-700={!darkMode}>{lastStats.tool_errors || 0}</strong></span>
			<span>Tool time: <strong class:text-gray-200={darkMode} class:text-gray-700={!darkMode}>{Math.round(lastStats.total_tool_time_ms || 0)}ms</strong></span>
			<span>Turns: <strong class:text-gray-200={darkMode} class:text-gray-700={!darkMode}>{lastStats.turns || 0}</strong></span>
		</div>
	{/if}

	<!-- Messages -->
	<div
		bind:this={scrollContainer}
		class="flex-1 overflow-y-auto px-4 py-3 space-y-3"
	>
		{#each messages as msg}
			{#if msg.role === 'user'}
				<div class="my-3">
					<hr class="border-t-2" class:border-blue-400={darkMode} class:border-blue-300={!darkMode}>
					<div class="flex gap-2 py-2.5 px-2 rounded" class:bg-gray-800={darkMode} class:bg-blue-50={!darkMode}>
						<span class="shrink-0 font-bold" class:text-cyan-400={darkMode} class:text-blue-600={!darkMode}>$</span>
						<span class="font-semibold" class:text-gray-100={darkMode} class:text-gray-800={!darkMode}>{msg.content}</span>
					</div>
					<hr class="border-t-2" class:border-blue-400={darkMode} class:border-blue-300={!darkMode}>
				</div>
			{:else if msg.role === 'assistant'}
				<div class="aac-md pl-2 leading-relaxed font-sans text-sm" class:text-green-300={darkMode} class:text-gray-700={!darkMode}>
					{@html renderAssistantMessage(msg.content)}
				</div>
			{:else if msg.role === 'system'}
				<div class="pl-2 opacity-50 italic text-xs">
					{msg.content}
				</div>
			{/if}
		{/each}

		{#if loading && statusText}
			<div class="pl-2 opacity-60 text-xs" class:text-yellow-400={darkMode} class:text-gray-500={!darkMode}>
				{statusText}
			</div>
		{:else if loading}
			<div class="pl-2 opacity-60 animate-pulse">
				▌
			</div>
		{/if}
	</div>

	<!-- Input -->
	<div
		class="flex items-center gap-2 px-3 py-2 border-t"
		class:border-gray-700={darkMode}
		class:bg-gray-800={darkMode}
		class:border-gray-300={!darkMode}
		class:bg-gray-100={!darkMode}
	>
		<span class="opacity-60" class:text-cyan-400={darkMode} class:text-blue-600={!darkMode}>$</span>
		<input
			bind:this={inputEl}
			bind:value={inputText}
			onkeydown={handleKeydown}
			disabled={loading}
			placeholder={loading ? 'Waiting for agent...' : 'Type a message...'}
			class="flex-1 bg-transparent outline-none placeholder:opacity-40"
		/>
		<button
			onclick={handleSend}
			disabled={loading || !inputText.trim()}
			class="px-2 py-0.5 rounded text-xs transition-opacity"
			class:opacity-60={loading || !inputText.trim()}
			class:hover:opacity-100={!loading && inputText.trim()}
			class:bg-green-800={darkMode}
			class:bg-blue-100={!darkMode}
		>
			Send
		</button>
	</div>
</div>
<!-- Canvas panel (side panel for structured content) -->
{#if canvasData}
	<div class="lg:w-[45%] w-full h-[40%] lg:h-full flex flex-col border rounded-lg overflow-hidden lg:ml-2 mt-2 lg:mt-0
	            {darkMode ? 'bg-gray-800 border-gray-700 text-gray-200' : 'bg-white border-gray-300 text-gray-800'}">
		<div class="flex items-center justify-between px-4 py-2 border-b
		            {darkMode ? 'border-gray-700 bg-gray-900' : 'border-gray-200 bg-gray-50'}">
			<h3 class="text-sm font-semibold truncate">{canvasData.title || 'Canvas'}</h3>
			<button
				onclick={() => canvasData = null}
				class="text-xs opacity-50 hover:opacity-100 transition-opacity"
				title="Close canvas"
			>✕</button>
		</div>
		<div class="flex-1 overflow-y-auto px-4 py-3 aac-md font-sans text-sm leading-relaxed">
			{@html renderMarkdown(canvasData.content)}
		</div>
	</div>
{/if}
</div>

<style>
	/* Markdown rendering inside the terminal */
	:global(.aac-md table) {
		border-collapse: collapse;
		font-size: 0.8rem;
		margin: 0.5rem 0;
		width: 100%;
	}
	:global(.aac-md th),
	:global(.aac-md td) {
		border: 1px solid rgba(128, 128, 128, 0.3);
		padding: 0.25rem 0.5rem;
		text-align: left;
	}
	:global(.aac-md th) {
		font-weight: 600;
		opacity: 0.8;
	}
	:global(.aac-md ul) {
		padding-left: 1.25rem;
		margin: 0.25rem 0;
		list-style: disc;
	}
	:global(.aac-md ol) {
		padding-left: 1.5rem;
		margin: 0.25rem 0;
		list-style: decimal;
	}
	:global(.aac-md li) {
		margin: 0.1rem 0;
		display: list-item;
	}
	:global(.aac-md p) {
		margin: 0.25rem 0;
	}
	:global(.aac-md h1),
	:global(.aac-md h2),
	:global(.aac-md h3) {
		font-weight: 600;
		margin: 0.5rem 0 0.25rem;
	}
	:global(.aac-md h1) { font-size: 1.1rem; }
	:global(.aac-md h2) { font-size: 1rem; }
	:global(.aac-md h3) { font-size: 0.9rem; opacity: 0.85; }
	:global(.aac-md code) {
		font-family: ui-monospace, monospace;
		font-size: 0.8rem;
		padding: 0.1rem 0.3rem;
		border-radius: 0.2rem;
		background: rgba(128, 128, 128, 0.15);
	}
	:global(.aac-md pre) {
		font-family: ui-monospace, monospace;
		font-size: 0.8rem;
		padding: 0.5rem;
		border-radius: 0.3rem;
		background: rgba(0, 0, 0, 0.1);
		overflow-x: auto;
		margin: 0.25rem 0;
	}
	:global(.aac-md strong) {
		font-weight: 600;
	}
	:global(.aac-md hr) {
		border: none;
		border-top: 1px solid rgba(128, 128, 128, 0.2);
		margin: 0.5rem 0;
	}
</style>
