<script>
	import { onMount, tick } from 'svelte';
	import { sendMessageStream, getSession } from '$lib/services/aacService';

	/** @type {{ sessionId: string, firstMessage?: string, resumed?: boolean }} */
	let { sessionId, firstMessage = '', resumed = false } = $props();

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

	onMount(async () => {
		// Check system preference
		if (window.matchMedia?.('(prefers-color-scheme: dark)').matches) {
			darkMode = true;
		}

		if (firstMessage) {
			// Skill session — agent spoke first
			messages = [{ role: 'assistant', content: firstMessage }];
		} else if (resumed) {
			// Resumed session — load history
			try {
				const session = await getSession(sessionId);
				messages = (session.conversation || []).filter(
					m => m.role === 'user' || (m.role === 'assistant' && m.content && !m.tool_calls)
				).map(m => ({
					role: m.role,
					content: m.content || '',
				}));
				// Inject resume notice
				if (messages.length > 0) {
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

	async function handleSend() {
		const text = inputText.trim();
		if (!text || loading) return;

		// If resuming, prepend context note
		let messageToSend = text;
		if (resumeNotice) {
			messageToSend = `[System: User returned to session. Resources may have changed.]\n${text}`;
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

	/**
	 * Simple markdown-like rendering for terminal output.
	 * Handles bold, italic, code, headers, lists.
	 * @param {string} text
	 * @returns {string}
	 */
	function renderMarkdown(text) {
		if (!text) return '';
		return text
			.replace(/&/g, '&amp;')
			.replace(/</g, '&lt;')
			.replace(/>/g, '&gt;')
			.replace(/^### (.+)$/gm, '<strong class="text-sm opacity-80">$1</strong>')
			.replace(/^## (.+)$/gm, '<strong>$1</strong>')
			.replace(/^# (.+)$/gm, '<strong class="text-lg">$1</strong>')
			.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
			.replace(/\*(.+?)\*/g, '<em>$1</em>')
			.replace(/`(.+?)`/g, '<code class="px-1 rounded bg-black/10 dark:bg-white/10">$1</code>')
			.replace(/^- (.+)$/gm, '  • $1')
			.replace(/^\d+\. (.+)$/gm, (_, p1, offset, str) => `  ${str.substring(0, offset).split('\n').filter(l => /^\d+\./.test(l)).length}. ${p1}`)
			.replace(/\n/g, '<br>');
	}
</script>

<div
	class="flex flex-col h-full font-mono text-sm rounded-lg border overflow-hidden transition-colors duration-200"
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
		<div class="flex gap-2">
			{#if lastStats}
				<span class="opacity-40">
					{lastStats.tool_calls || 0} tools, {Math.round(lastStats.total_tool_time_ms || 0)}ms
				</span>
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

	<!-- Messages -->
	<div
		bind:this={scrollContainer}
		class="flex-1 overflow-y-auto px-4 py-3 space-y-3"
	>
		{#each messages as msg}
			{#if msg.role === 'user'}
				<div class="flex gap-2">
					<span class="shrink-0 opacity-60" class:text-cyan-400={darkMode} class:text-blue-600={!darkMode}>$</span>
					<span>{msg.content}</span>
				</div>
			{:else if msg.role === 'assistant'}
				<div class="pl-2 leading-relaxed" class:text-green-300={darkMode} class:text-gray-700={!darkMode}>
					{@html renderMarkdown(msg.content)}
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
