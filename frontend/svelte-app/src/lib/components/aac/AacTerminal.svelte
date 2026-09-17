<script>
	import { onMount, onDestroy, tick } from 'svelte';
	import { _ } from 'svelte-i18n';
	import { sidebarBusy, startupSessions, openTabs } from '$lib/stores/aacStore.svelte';
	import { splitCanvasContent, canvasFromMessages } from '$lib/utils/aacCanvas.js';
	import { sendMessageStream, getSession, sendMessage } from '$lib/services/aacService';
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
	let historyLoading = $state(resumed && !firstMessage && !skillStartup);
	$effect(() => { sidebarBusy.set(loading || historyLoading); });

	/** @type {string} */
	let statusText = $state('');
    let lastActivity = $state('');
    let activityStarted = $state(0);
    let activitySeconds = $state(0);
    $effect(() => {
        if (!loading) return;
        const timer = setInterval(() => {
            activitySeconds = Math.floor((Date.now() - activityStarted) / 1000);
        }, 1000);
        return () => clearInterval(timer);
    });
    function beginProgress() {
        lastActivity = '';
        updateProgress({status: 'thinking'});
    }
    let responsePolicy = $state(null);
    const languageNames = {en:'English',es:'Español',ca:'Català',eu:'Euskara'};
    function updateProgress(event) {
        if (event.status === 'policy') { responsePolicy = event.policy; return; }
        if (stopped) return;
        activityStarted = Date.now();
        activitySeconds = 0;
        if (event.status === 'thinking') {
            statusText = lastActivity ? 'Reviewing the tool result…' : 'Preparing a response…';
        } else if (event.status === 'tool') {
            statusText = event.command || 'Using a tool…';
        } else if (event.status === 'tool_done') {
            lastActivity = `${event.awaiting_user_confirmation ? 'Awaiting your approval; not executed' : event.success ? 'Tool completed' : 'Tool reported a problem'}: ${event.command || 'Command'}`;
            statusText = 'Reviewing the tool result…';
        } else if (event.status === 'responding') {
            statusText = '';
        }
        scrollToBottom();
    }

    let sessionTitle = $state('New conversation');
    let stopped = $state(false);
    async function refreshSessionInfo() {
        try {
            const session = await getSession(sessionId);
            if(!isMounted)return;
            responsePolicy=session.skill_info?.response_language_policy || null;
            sessionTitle=session.display_title || session.title || 'New conversation';
            openTabs.update(tabs=>tabs.map(t=>t.id===sessionId?{...t,title:sessionTitle}:t));
        } catch (_) { /* transcript remains usable if metadata refresh fails */ }
    }
    function stopResponse() {
        stopped=true;
        statusText='Stopped';
        streamAbort?.abort();
    }


	/** @type {boolean} */
	let darkMode = $state(false);

	/** @type {HTMLElement|null} */
	let scrollContainer = null;

	/** @type {HTMLTextAreaElement|null} */
	let inputEl = null;

	/** @type {Object|null} */
	let lastStats = $state(null);

	/** @type {boolean} */
	let showStats = $state(false);

	// Derive the latest canvas from the transcript, never mutate state while rendering.
	let dismissedCanvas = $state(null);
    let canvasDialog = $state(null);
    function expandCanvas() { canvasDialog?.showModal(); canvasDialog?.querySelector("[data-canvas-back]")?.focus(); }
	let latestCanvas = $derived(canvasFromMessages(messages));
	let canvasData = $derived(latestCanvas?.key === dismissedCanvas ? null : latestCanvas);

	function renderAssistantMessage(content) {
		return renderMarkdown(splitCanvasContent(content).text);
	}

	onMount(async () => {
		// Check system preference
		if (window.matchMedia?.('(prefers-color-scheme: dark)').matches) {
			darkMode = true;
		}

		if (skillStartup) {
            startupSessions.update(ids => { const next = new Set(ids); next.delete(sessionId); return next; });
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
                responsePolicy=session.skill_info?.response_language_policy || null;
            sessionTitle=session.display_title || session.title || 'New conversation';
				const conv = (session.conversation || []).filter(
					m => (m.role === 'user' && !(m.content || '').startsWith('[System:') && !(m.content || '').startsWith('[Application workflow instructions]'))
					  || (m.role === 'assistant' && m.content && !m.tool_calls)
				).map(m => ({ role: m.role, content: m.content || '' }));
				if (conv.length > 0) {
					messages = conv;
				}
			} catch (e) {
				if (!isMounted) return;
				if (e instanceof Error && e.message.startsWith('Session expired')) return;
				messages = [{ role: 'system', content: `Error loading session: ${e.message}` }];
			} finally {
				if (isMounted) historyLoading = false;
			}
		}

		if (!isMounted) return;
		await tick();
		scrollToBottom();
		inputEl?.focus();
	});


	async function triggerSkillStartup() {
		loading = true;
        stopped = false;
        beginProgress();
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
					messages[streamIdx] = { ...messages[streamIdx], content: messages[streamIdx].content + chunk };
					messages = messages;
					scrollToBottom();
				},
				(stats) => { lastStats = stats; statusText = ''; void refreshSessionInfo(); },
				(err) => { messages[streamIdx] = { role: 'system', content: `Error: ${err}` }; messages = messages; },
				updateProgress,
				streamAbort.signal,
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
		if (!text || loading || historyLoading) return;

		// Send the user's exact reply so resumed approvals and cancellations
		// reach the server's confirmation classifier without a hidden prefix.

		messages = [...messages, { role: 'user', content: text }];
		inputText = '';
		loading = true;
        stopped = false;
        beginProgress();
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
				text,
				(chunk) => {
					statusText = '';
					messages[streamIdx] = { ...messages[streamIdx], content: messages[streamIdx].content + chunk };
					messages = messages;
					scrollToBottom();
				},
				(stats) => {
					lastStats = stats;
                    void refreshSessionInfo();
					statusText = '';
				},
				(err) => {
					statusText = '';
					messages[streamIdx] = { role: 'system', content: `Error: ${err}` };
					messages = messages;
				},
				updateProgress,
				streamAbort.signal,
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
		if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
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

<div class="flex flex-col h-full min-h-0 gap-0">
{#if responsePolicy?.fallback_applied}
    <div role="status" class="px-3 py-2 text-sm bg-amber-50 text-amber-900 border-b border-amber-200">
        {languageNames[responsePolicy.requested_language]} → {languageNames[responsePolicy.effective_language]}
        <span> · LAMB AGENT · {$_('aacSettings.policyLabel')}</span>
    </div>
{/if}
<!-- Terminal panel -->
<div
	class="flex flex-col font-sans text-sm rounded-lg border overflow-hidden w-full h-full min-h-0"
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
		<span class="opacity-60 truncate" title={sessionTitle}>{sessionTitle}</span>
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
						<span style="white-space: pre-wrap; overflow-wrap: anywhere; min-width: 0" class="font-semibold" class:text-gray-100={darkMode} class:text-gray-800={!darkMode}>{msg.content}</span>
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

        {#if canvasData}
        <button class="canvas-preview" onclick={expandCanvas}><strong>{canvasData.title || 'Canvas'}</strong><span>Expand canvas</span></button>
        {/if}
        {#if stopped}<p role="status" class="text-sm">Stopped receiving the response. An action may still finish on the server; check its result before retrying.</p>{/if}
		{#if loading && statusText}
			<div class="pl-2 text-xs" class:text-yellow-300={darkMode} class:text-gray-600={!darkMode}>
                <span role="status" aria-live="polite">{statusText}</span>
                <span aria-hidden="true" class="ml-2 tabular-nums">{activitySeconds}s</span>
                {#if lastActivity}<div class="mt-1 text-xs">{lastActivity}</div>{/if}
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
        <textarea
            bind:this={inputEl}
            bind:value={inputText}
            onkeydown={handleKeydown}
            disabled={loading || historyLoading}
            rows="3"
            aria-label="Message LAMB AGENT"
            title="Enter to send; Shift+Enter for a new line"
            placeholder={historyLoading ? 'Loading conversation...' : loading ? 'Waiting for agent...' : 'Type a message...'}
            class="flex-1 min-w-0 resize-y min-h-[76px] max-h-[240px] bg-transparent outline-none placeholder:opacity-40"
        ></textarea>
        {#if loading}
        <button onclick={stopResponse} class="px-3 py-2 rounded border border-red-300 text-red-700" aria-label="Stop response">Stop</button>
        {:else}
		<button
			onclick={handleSend}
			disabled={loading || historyLoading || !inputText.trim()}
			class="px-2 py-0.5 rounded text-xs transition-opacity"
			class:opacity-60={loading || !inputText.trim()}
			class:hover:opacity-100={!loading && inputText.trim()}
			class:bg-green-800={darkMode}
			class:bg-blue-100={!darkMode}
		>
			Send
		</button>
        {/if}
	</div>
</div>
{#if canvasData}
<dialog bind:this={canvasDialog} class="canvas-dialog" aria-label={canvasData.title || 'Canvas'}>
    <div class="canvas-heading">
        <h2>{canvasData.title || 'Canvas'}</h2>
        {#if loading}<button onclick={stopResponse}>Stop response</button>{/if}
        <button onclick={() => canvasDialog.close()} data-canvas-back>Back to conversation</button>
    </div>
    <p class="canvas-caption">Agent canvas</p>
    <div class="canvas-body aac-md">{@html renderMarkdown(canvasData.content)}</div>
</dialog>
{/if}
</div>

<style>
    .canvas-preview { display: flex; justify-content: space-between; gap: 12px; width: 100%; padding: 14px; border: 1px solid #b3cce5; border-radius: 10px; background: #edf5fd; color: #173f64; text-align: left; }
    .canvas-preview span { flex-shrink: 0; }
    .canvas-dialog { position: fixed; inset: 0; margin: auto; width: min(960px, calc(100vw - 32px)); max-height: calc(100dvh - 32px); padding: 0; border: 1px solid #bcccdc; border-radius: 12px; background: white; color: #172b40; }
    .canvas-dialog::backdrop { background: #0c213b88; }
    .canvas-heading { display: flex; align-items: center; gap: 16px; padding: 16px; border-bottom: 1px solid #d6e0ea; position: sticky; top: 0; background: white; }
    .canvas-heading h2 { flex: 1; font-weight: 600; overflow-wrap: anywhere; }
    .canvas-heading button { border: 1px solid #94aec7; padding: 8px; border-radius: 6px; }
    .canvas-caption { padding: 8px 20px 0; font-size: 12px; color: #62758a; }
    .canvas-body { overflow: auto; padding: 20px; }
    @media (max-width: 919px) { .canvas-dialog { width: 100%; height: 100dvh; max-height: 100dvh; border-radius: 0; } }

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
