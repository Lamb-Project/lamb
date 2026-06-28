<script>
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { _ } from 'svelte-i18n';
	import { getSessions } from '$lib/services/aacService';

	let launching = $state(false);
	let hasActiveSession = $state(false);

	onMount(async () => {
		try {
			const sessions = await getSessions();
			const today = new Date().toISOString().slice(0, 10);
			hasActiveSession = sessions.some(
				(s) => s.status === 'active' && s.title === 'LAMB Helper' && s.created_at?.startsWith(today)
			);
		} catch (_) {
			/* ignore */
		}
	});

	async function launchNew() {
		launching = true;
		await goto('/agent?new=true');
		launching = false;
	}

	async function launchContinue() {
		launching = true;
		await goto('/agent');
		launching = false;
	}
</script>

<div class="rounded-2xl bg-gradient-to-br from-indigo-600 to-blue-700 p-6 text-white shadow-lg">
	<div class="flex items-start gap-4">
		<div class="flex-shrink-0 text-4xl">🤖</div>
		<div class="min-w-0 flex-1">
			<h2 class="mb-1 text-xl font-semibold">
				{$_('home.dashboard.agent.title', { default: 'LAMB Agent' })}
			</h2>
			<p class="mb-4 text-sm leading-relaxed text-blue-100">
				{$_('home.dashboard.agent.description', {
					default:
						'Talk to the AI assistant to get help, create assistants, learn about LAMB, or troubleshoot issues.'
				})}
			</p>
			<div class="flex flex-wrap gap-2">
				<button
					onclick={launchNew}
					disabled={launching}
					class="inline-flex items-center gap-2 rounded-lg bg-white px-5 py-2.5 font-semibold text-indigo-700
						   shadow-sm transition-colors hover:bg-blue-50 disabled:cursor-wait disabled:opacity-60"
				>
					{#if launching}
						<span class="animate-spin">⏳</span>
						<span>{$_('home.dashboard.agent.starting', { default: 'Starting...' })}</span>
					{:else}
						<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="2"
								d="M12 4v16m8-8H4"
							/>
						</svg>
						<span>{$_('home.dashboard.agent.startNew', { default: 'Start new conversation' })}</span
						>
					{/if}
				</button>
				{#if hasActiveSession && !launching}
					<button
						onclick={launchContinue}
						class="inline-flex items-center gap-2 rounded-lg border border-white/30 bg-indigo-500/30 px-5 py-2.5
							   font-semibold text-white transition-colors hover:bg-indigo-500/50"
					>
						<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="2"
								d="M14 5l7 7m0 0l-7 7m7-7H3"
							/>
						</svg>
						<span
							>{$_('home.dashboard.agent.continue', {
								default: "Continue today's conversation"
							})}</span
						>
					</button>
				{/if}
			</div>
		</div>
	</div>
</div>
