<script>
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { _, locale } from '$lib/i18n';
	import { user } from '$lib/stores/userStore';
	import { createSession, getSessions, deleteSession } from '$lib/services/aacService';
	import { openTab, setActiveTab, getActiveTabId, closeTab } from '$lib/stores/aacStore.svelte';
	import AacTerminal from '$lib/components/aac/AacTerminal.svelte';
	import { goto } from '$app/navigation';

	let sessionId = $state(/** @type {string|null} */ (null));
	let isNewSession = $state(false);
	let loading = $state(true);
	let error = $state('');

	// React to global tab bar switches
	let storeActiveId = $derived(getActiveTabId());
	$effect(() => {
		if (storeActiveId && storeActiveId !== sessionId && !loading) {
			sessionId = storeActiveId;
			isNewSession = false;
		}
	});

	const localeToLanguage = { en: 'English', es: 'Spanish', ca: 'Catalan', eu: 'Basque' };

	onMount(async () => {
		const forceNew = $page.url.searchParams.get('new') === 'true';

		// Check URL for a specific session ID (highest priority)
		const urlSession = $page.url.searchParams.get('session');
		if (urlSession && !forceNew) {
			sessionId = urlSession;
			isNewSession = false; // resuming
			setActiveTab(sessionId);
			loading = false;
			return;
		}

		// If forceNew, archive today's existing session first
		if (forceNew) {
			try {
				const sessions = await getSessions();
				const today = new Date().toISOString().slice(0, 10);
				const existing = sessions.find(
					(s) =>
						s.status === 'active' && s.title === 'LAMB Helper' && s.created_at?.startsWith(today)
				);
				if (existing) {
					await deleteSession(existing.id);
					closeTab(existing.id);
				}
			} catch (_) {
				/* continue anyway */
			}
		} else {
			// Default behavior: resume today's active about-lamb session if exists
			try {
				const sessions = await getSessions();
				const today = new Date().toISOString().slice(0, 10);
				const active = sessions.find(
					(s) =>
						s.status === 'active' && s.title === 'LAMB Helper' && s.created_at?.startsWith(today)
				);
				if (active) {
					sessionId = active.id;
					isNewSession = false;
					openTab(sessionId, active.title || 'LAMB Helper', null, 'about-lamb');
					loading = false;
					return;
				}
			} catch (_) {
				/* no existing session */
			}
		}

		// Create a new session
		try {
			const session = await createSession({
				assistantId: null,
				skill: 'about-lamb',
				context: { language: localeToLanguage[$locale] || 'English' }
			});
			sessionId = session.id;
			isNewSession = true;
			openTab(sessionId, session.title || 'LAMB Helper', null, 'about-lamb');
		} catch (e) {
			error = e.message || 'Failed to start agent session';
		}
		loading = false;
	});

	async function startNewConversation() {
		if (!sessionId) return;
		const confirmed = confirm(
			$_('home.dashboard.agent.confirmNew', {
				default: 'End this conversation and start a new one?'
			})
		);
		if (!confirmed) return;

		loading = true;
		const oldId = sessionId;
		try {
			await deleteSession(oldId);
		} catch (_) {
			/* ignore */
		}
		closeTab(oldId);
		sessionId = null;

		try {
			const session = await createSession({
				assistantId: null,
				skill: 'about-lamb',
				context: { language: localeToLanguage[$locale] || 'English' }
			});
			sessionId = session.id;
			isNewSession = true;
			openTab(sessionId, session.title || 'LAMB Helper', null, 'about-lamb');
		} catch (e) {
			error = e.message || 'Failed to start new session';
		}
		loading = false;
	}
</script>

<div class="mx-auto max-w-7xl px-4 py-6">
	<div class="mb-6 flex items-center justify-between">
		<h1 class="text-brand text-3xl font-bold">
			🤖 {$_('home.dashboard.agent.title', { default: 'LAMB Agent' })}
		</h1>
		<div class="flex gap-2">
			<a
				href="/agent/history"
				class="inline-flex items-center gap-1.5 rounded-md border border-gray-300 bg-gray-100 px-3
                       py-1.5 text-sm font-medium text-gray-700 transition-colors
                       hover:bg-gray-200"
			>
				<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
					/>
				</svg>
				{$_('agent.history.title', { default: 'History' })}
			</a>
			{#if sessionId && !loading}
				<button
					onclick={startNewConversation}
					class="inline-flex items-center gap-1.5 rounded-md border border-gray-300 bg-gray-100 px-3
                           py-1.5 text-sm font-medium text-gray-700 transition-colors
                           hover:bg-gray-200"
					title={$_('home.dashboard.agent.newConversation', {
						default: 'Start a new conversation'
					})}
				>
					<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M12 4v16m8-8H4"
						/>
					</svg>
					{$_('home.dashboard.agent.newConversation', { default: 'New conversation' })}
				</button>
			{/if}
		</div>
	</div>

	{#if loading}
		<div class="rounded-lg border border-gray-200 bg-white p-12 text-center shadow">
			<div class="mb-3 animate-spin text-3xl">⏳</div>
			<p class="text-gray-500">{$_('home.dashboard.agent.starting', { default: 'Starting...' })}</p>
		</div>
	{:else if error}
		<div class="rounded-xl border border-red-200 bg-red-50 px-6 py-4 text-red-700">
			<p class="font-medium">{error}</p>
		</div>
	{:else if sessionId}
		<div class="overflow-hidden rounded-lg border border-gray-200 bg-white shadow">
			{#key sessionId}
				<div class="h-[700px]">
					<AacTerminal
						{sessionId}
						firstMessage=""
						resumed={!isNewSession}
						skillStartup={isNewSession}
					/>
				</div>
			{/key}
		</div>
	{/if}
</div>
