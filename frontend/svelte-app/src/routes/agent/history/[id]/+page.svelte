<script>
	import { onMount, onDestroy } from 'svelte';
	import { page } from '$app/stores';
	import { _ } from '$lib/i18n';
	import { getSession } from '$lib/services/aacService';
	import { openTab } from '$lib/stores/aacStore.svelte';
	import { goto } from '$app/navigation';
	import { marked } from 'marked';

	let session = $state(/** @type {any} */ (null));
	let loading = $state(true);
	let error = $state('');
	let showAudit = $state(false);

	// Don't write state on a destroyed component if the user navigates away
	// while the session fetch is in flight. (#352, L1)
	let isMounted = true;
	onDestroy(() => {
		isMounted = false;
	});

	function renderMarkdown(text) {
		if (!text) return '';
		return marked.parse(text, { breaks: true });
	}

	onMount(async () => {
		const id = $page.params.id;
		try {
			const data = await getSession(id);
			if (!isMounted) return;
			session = data;
		} catch (e) {
			if (!isMounted) return;
			if (e instanceof Error && e.message.startsWith('Session expired')) return;
			error = e.message || 'Session not found';
		} finally {
			if (isMounted) loading = false;
		}
	});

	function getVisibleMessages() {
		if (!session) return [];
		return (session.conversation || []).filter(
			(m) =>
				(m.role === 'user' && !(m.content || '').startsWith('[System:')) ||
				(m.role === 'assistant' && m.content && !m.tool_calls)
		);
	}

	function formatDate(iso) {
		if (!iso) return '-';
		return `${iso.slice(0, 10)} ${iso.slice(11, 16)}`;
	}

	async function resumeSession() {
		if (!session) return;
		openTab(
			session.id,
			session.title || 'Session',
			session.assistant_id,
			session.skill_info?.skill_id
		);
		await goto(`/agent?session=${session.id}`);
	}
</script>

<div class="mx-auto max-w-4xl px-4 py-6">
	<div class="mb-6 flex items-center justify-between">
		<a href="/agent/history" class="text-sm text-blue-600 hover:text-blue-800">
			&larr; {$_('agent.history.backToHistory', { default: 'Back to sessions' })}
		</a>
	</div>

	{#if loading}
		<div class="py-12 text-center text-gray-400">Loading...</div>
	{:else if error}
		<div class="rounded-xl border border-red-200 bg-red-50 px-6 py-4 text-red-700">
			<p class="font-medium">{error}</p>
		</div>
	{:else if session}
		<!-- Header -->
		<div class="mb-6 rounded-lg border border-gray-200 bg-white p-6 shadow">
			<div class="flex items-start justify-between">
				<div>
					<h1 class="mb-1 text-2xl font-bold text-gray-900">
						{session.title || session.id.slice(0, 12)}
					</h1>
					<div class="flex flex-wrap gap-4 text-sm text-gray-500">
						<span
							>Status: <strong
								class={session.status === 'active' ? 'text-green-600' : 'text-gray-400'}
								>{session.status}</strong
							></span
						>
						<span>Created: {formatDate(session.created_at)}</span>
						<span>Updated: {formatDate(session.updated_at)}</span>
						{#if session.assistant_id}
							<span>Assistant: #{session.assistant_id}</span>
						{/if}
					</div>
				</div>
				{#if session.status === 'active'}
					<button
						onclick={resumeSession}
						class="bg-brand hover:bg-brand/90 rounded-lg px-4 py-2 text-sm font-medium text-white"
						>Resume</button
					>
				{/if}
			</div>
		</div>

		<!-- Stats -->
		{#if session.tool_audit?.length}
			<div class="mb-6 rounded-lg border border-gray-200 bg-white shadow">
				<button
					onclick={() => (showAudit = !showAudit)}
					class="flex w-full items-center justify-between px-6 py-3 text-sm font-medium text-gray-700 hover:bg-gray-50"
				>
					<span
						>Tool Audit ({session.tool_audit.length} calls, {session.tool_audit.filter(
							(e) => !e.success
						).length} errors)</span
					>
					<span>{showAudit ? '▴' : '▾'}</span>
				</button>
				{#if showAudit}
					<div class="border-t border-gray-100 px-6 pb-4">
						<table class="mt-2 w-full text-xs">
							<thead>
								<tr class="text-left text-gray-500">
									<th class="py-1 pr-3">Time</th>
									<th class="py-1 pr-3">Status</th>
									<th class="py-1 pr-3">Duration</th>
									<th class="py-1">Command</th>
								</tr>
							</thead>
							<tbody>
								{#each session.tool_audit as e}
									<tr class="border-t border-gray-50">
										<td class="py-1 pr-3 font-mono text-gray-400">{(e.ts || '').slice(11, 19)}</td>
										<td class="py-1 pr-3 {e.success ? 'text-green-600' : 'text-red-600'}"
											>{e.success ? 'ok' : 'FAIL'}</td
										>
										<td class="py-1 pr-3 text-gray-500">{Math.round(e.elapsed_ms || 0)}ms</td>
										<td class="py-1 font-mono text-gray-700">{e.command || '?'}</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				{/if}
			</div>
		{/if}

		<!-- Conversation transcript -->
		<div class="overflow-hidden rounded-lg border border-gray-200 bg-white shadow">
			<div class="border-b border-gray-200 bg-gray-50 px-6 py-3">
				<h2 class="text-sm font-semibold text-gray-700">Conversation</h2>
			</div>
			<div class="space-y-4 px-6 py-4">
				{#each getVisibleMessages() as msg}
					{#if msg.role === 'user'}
						<div class="my-3">
							<hr class="border-t-2 border-blue-300" />
							<div class="flex gap-2 rounded bg-blue-50 px-2 py-2.5">
								<span class="shrink-0 font-bold text-blue-600">$</span>
								<span class="font-semibold text-gray-800">{msg.content}</span>
							</div>
							<hr class="border-t-2 border-blue-300" />
						</div>
					{:else if msg.role === 'assistant'}
						<div class="prose prose-sm max-w-none pl-2 text-sm leading-relaxed text-gray-700">
							{@html renderMarkdown(msg.content)}
						</div>
					{/if}
				{/each}
				{#if getVisibleMessages().length === 0}
					<p class="py-4 text-center text-gray-400 italic">No messages in this session.</p>
				{/if}
			</div>
		</div>
	{/if}
</div>
