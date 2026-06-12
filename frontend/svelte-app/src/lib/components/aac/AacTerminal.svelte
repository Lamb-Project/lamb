<script>
	import { onMount, onDestroy, tick } from 'svelte';
	import { sendMessageStream, getSession, sendMessage } from '$lib/services/aacService';
	import { recordTabActivity } from '$lib/stores/aacStore.svelte';
	import { renderMarkdownWithMath } from '$lib/utils/renderMarkdown.js';

	// Abort any in-flight stream when the component unmounts so the fetch
	// and getReader() loop stop running in the background (#352, H3).
	/** @type {AbortController|null} */
	let streamAbort = null;
	let isMounted = true;

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
			// Resumed session — load history, hide internal [System:...] messages.
			// Skip writes if the user navigated away while getSession was in flight
			// (rapid tab switching destroys this component before resolution). (#352, H5)
			try {
				const session = await getSession(sessionId);
				if (!isMounted) return;
				const conv = (session.conversation || [])
					.filter(
						(m) =>
							(m.role === 'user' && !(m.content || '').startsWith('[System:')) ||
							(m.role === 'assistant' && m.content && !m.tool_calls)
					)
					.map((m) => ({ role: m.role, content: m.content || '' }));
				if (conv.length > 0) {
					messages = conv;
					resumeNotice = true;
				}
			} catch (e) {
				if (!isMounted) return;
				if (e instanceof Error && e.message.startsWith('Session expired')) return;
				messages = [{ role: 'system', content: `Error loading session: ${e.message}` }];
			}
		}

		if (!isMounted) return;
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

		streamAbort?.abort();
		streamAbort = new AbortController();
		try {
			await sendMessageStream(
				sessionId,
				'[System: Skill startup]',
				(chunk) => {
					statusText = '';
					messages[streamIdx] = {
						...messages[streamIdx],
						content: messages[streamIdx].content + chunk
					};
					messages = messages;
					scrollToBottom();
				},
				(stats) => {
					lastStats = stats;
					statusText = '';
				},
				(err) => {
					messages[streamIdx] = { role: 'system', content: `Error: ${err}` };
					messages = messages;
				},
				(status) => {
					if (status.status === 'thinking') statusText = '🧠 Thinking...';
					else if (status.status === 'tool') statusText = `⚡ ${status.command || 'Running'}...`;
					else if (status.status === 'tool_done')
						statusText = `${status.success ? '✓' : '✗'} ${status.command || 'Done'}`;
					else if (status.status === 'responding') statusText = '';
					scrollToBottom();
				},
				streamAbort.signal
			);
		} catch (e) {
			if (isMounted && e?.name !== 'AbortError') {
				messages[streamIdx] = { role: 'system', content: `Error: ${e.message}` };
				messages = messages;
			}
		} finally {
			// Defensive: guarantee loading flag is cleared even if anything
			// above throws unexpectedly. (#352, Pattern A)
			if (isMounted) loading = false;
		}
		if (!isMounted) return;
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

		streamAbort?.abort();
		streamAbort = new AbortController();
		try {
			await sendMessageStream(
				sessionId,
				messageToSend,
				(chunk) => {
					statusText = '';
					messages[streamIdx] = {
						...messages[streamIdx],
						content: messages[streamIdx].content + chunk
					};
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
				streamAbort.signal
			);
		} catch (e) {
			if (isMounted && e?.name !== 'AbortError') {
				messages[streamIdx] = { role: 'system', content: `Error: ${e.message}` };
				messages = messages;
			}
		} finally {
			// Defensive: guarantee loading flag is cleared on every exit
			// path so the send button never gets stuck disabled. (#352, Pattern A)
			if (isMounted) loading = false;
		}

		if (!isMounted) return;
		await tick();
		scrollToBottom();
		inputEl?.focus();
	}

	onDestroy(() => {
		isMounted = false;
		streamAbort?.abort();
		streamAbort = null;
	});

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

	/**
	 * Render markdown to sanitized HTML (DOMPurify-backed; #417).
	 * @param {string} text
	 * @returns {string}
	 */
	function renderMarkdown(text) {
		if (!text) return '';
		// Sanitized render — agent/LLM output is untrusted (#417).
		return renderMarkdownWithMath(text);
	}
</script>

<div class="flex h-full flex-col gap-0 lg:flex-row">
	<!-- Terminal panel -->
	<div
		class="flex flex-col overflow-hidden rounded-lg border font-mono text-sm transition-all duration-200
	       {canvasData ? 'h-[60%] lg:h-full lg:w-[55%]' : 'h-full w-full'}"
		class:bg-gray-900={darkMode}
		class:text-green-400={darkMode}
		class:border-gray-700={darkMode}
		class:bg-gray-50={!darkMode}
		class:text-gray-800={!darkMode}
		class:border-gray-300={!darkMode}
	>
		<!-- Header -->
		<div
			class="flex items-center justify-between border-b px-3 py-1.5 text-xs"
			class:border-gray-700={darkMode}
			class:bg-gray-800={darkMode}
			class:border-gray-300={!darkMode}
			class:bg-gray-100={!darkMode}
		>
			<span class="opacity-60">AAC Agent — Session {sessionId.slice(0, 8)}...</span>
			<div class="flex items-center gap-2">
				{#if lastStats}
					<button
						onclick={() => (showStats = !showStats)}
						class="cursor-pointer opacity-40 transition-opacity hover:opacity-80"
						title="Toggle tool details"
					>
						{lastStats.tool_calls || 0} tools, {Math.round(lastStats.total_tool_time_ms || 0)}ms
						{showStats ? '▴' : '▾'}
					</button>
				{/if}
				<button
					onclick={toggleDarkMode}
					class="opacity-60 transition-opacity hover:opacity-100"
					title="Toggle dark/light mode"
				>
					{darkMode ? '☀️' : '🌙'}
				</button>
			</div>
		</div>

		<!-- Stats Panel (collapsible) -->
		{#if showStats && lastStats}
			<div
				class="flex flex-wrap gap-x-6 gap-y-1 border-b px-4 py-2 text-xs"
				class:border-gray-700={darkMode}
				class:bg-gray-800={darkMode}
				class:text-gray-400={darkMode}
				class:border-gray-200={!darkMode}
				class:bg-gray-50={!darkMode}
				class:text-gray-500={!darkMode}
			>
				<span
					>Model: <strong class:text-gray-200={darkMode} class:text-gray-700={!darkMode}
						>{lastStats.model || '?'}</strong
					></span
				>
				<span
					>Tool calls: <strong class:text-gray-200={darkMode} class:text-gray-700={!darkMode}
						>{lastStats.tool_calls || 0}</strong
					></span
				>
				<span
					>Errors: <strong class:text-gray-200={darkMode} class:text-gray-700={!darkMode}
						>{lastStats.tool_errors || 0}</strong
					></span
				>
				<span
					>Tool time: <strong class:text-gray-200={darkMode} class:text-gray-700={!darkMode}
						>{Math.round(lastStats.total_tool_time_ms || 0)}ms</strong
					></span
				>
				<span
					>Turns: <strong class:text-gray-200={darkMode} class:text-gray-700={!darkMode}
						>{lastStats.turns || 0}</strong
					></span
				>
			</div>
		{/if}

		<!-- Messages -->
		<div bind:this={scrollContainer} class="flex-1 space-y-3 overflow-y-auto px-4 py-3">
			{#each messages as msg}
				{#if msg.role === 'user'}
					<div class="my-3">
						<hr
							class="border-t-2"
							class:border-blue-400={darkMode}
							class:border-blue-300={!darkMode}
						/>
						<div
							class="flex gap-2 rounded px-2 py-2.5"
							class:bg-gray-800={darkMode}
							class:bg-blue-50={!darkMode}
						>
							<span
								class="shrink-0 font-bold"
								class:text-cyan-400={darkMode}
								class:text-blue-600={!darkMode}>$</span
							>
							<span
								class="font-semibold"
								class:text-gray-100={darkMode}
								class:text-gray-800={!darkMode}>{msg.content}</span
							>
						</div>
						<hr
							class="border-t-2"
							class:border-blue-400={darkMode}
							class:border-blue-300={!darkMode}
						/>
					</div>
				{:else if msg.role === 'assistant'}
					<div
						class="aac-md pl-2 font-sans text-sm leading-relaxed"
						class:text-green-300={darkMode}
						class:text-gray-700={!darkMode}
					>
						{@html renderAssistantMessage(msg.content)}
					</div>
				{:else if msg.role === 'system'}
					<div class="pl-2 text-xs italic opacity-50">
						{msg.content}
					</div>
				{/if}
			{/each}

			{#if loading && statusText}
				<div
					class="pl-2 text-xs opacity-60"
					class:text-yellow-400={darkMode}
					class:text-gray-500={!darkMode}
				>
					{statusText}
				</div>
			{:else if loading}
				<div class="animate-pulse pl-2 opacity-60">▌</div>
			{/if}
		</div>

		<!-- Input -->
		<div
			class="flex items-center gap-2 border-t px-3 py-2"
			class:border-gray-700={darkMode}
			class:bg-gray-800={darkMode}
			class:border-gray-300={!darkMode}
			class:bg-gray-100={!darkMode}
		>
			<span class="opacity-60" class:text-cyan-400={darkMode} class:text-blue-600={!darkMode}
				>$</span
			>
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
				class="rounded px-2 py-0.5 text-xs transition-opacity"
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
		<div
			class="mt-2 flex h-[40%] w-full flex-col overflow-hidden rounded-lg border lg:mt-0 lg:ml-2 lg:h-full lg:w-[45%]
	            {darkMode
				? 'border-gray-700 bg-gray-800 text-gray-200'
				: 'border-gray-300 bg-white text-gray-800'}"
		>
			<div
				class="flex items-center justify-between border-b px-4 py-2
		            {darkMode ? 'border-gray-700 bg-gray-900' : 'border-gray-200 bg-gray-50'}"
			>
				<h3 class="truncate text-sm font-semibold">{canvasData.title || 'Canvas'}</h3>
				<button
					onclick={() => (canvasData = null)}
					class="text-xs opacity-50 transition-opacity hover:opacity-100"
					title="Close canvas">✕</button
				>
			</div>
			<div class="aac-md flex-1 overflow-y-auto px-4 py-3 font-sans text-sm leading-relaxed">
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
	:global(.aac-md h1) {
		font-size: 1.1rem;
	}
	:global(.aac-md h2) {
		font-size: 1rem;
	}
	:global(.aac-md h3) {
		font-size: 0.9rem;
		opacity: 0.85;
	}
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
