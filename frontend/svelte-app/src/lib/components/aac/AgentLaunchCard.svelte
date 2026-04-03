<script>
	import { goto } from '$app/navigation';
	import { _ } from 'svelte-i18n';

	let launching = $state(false);

	async function launch() {
		launching = true;
		await goto('/agent');
		launching = false;
	}
</script>

<div class="bg-gradient-to-br from-indigo-600 to-blue-700 rounded-2xl shadow-lg p-6 text-white">
	<div class="flex items-start gap-4">
		<div class="text-4xl flex-shrink-0">🤖</div>
		<div class="flex-1 min-w-0">
			<h2 class="text-xl font-semibold mb-1">
				{$_('home.dashboard.agent.title', { default: 'LAMB Agent' })}
			</h2>
			<p class="text-blue-100 text-sm mb-4 leading-relaxed">
				{$_('home.dashboard.agent.description', {
					default: 'Talk to the AI assistant to get help, create assistants, learn about LAMB, or troubleshoot issues.'
				})}
			</p>
			<button
				onclick={launch}
				disabled={launching}
				class="inline-flex items-center gap-2 px-5 py-2.5 bg-white text-indigo-700 font-semibold rounded-lg
					   hover:bg-blue-50 disabled:opacity-60 disabled:cursor-wait transition-colors shadow-sm"
			>
				{#if launching}
					<span class="animate-spin">⏳</span>
					<span>{$_('home.dashboard.agent.starting', { default: 'Starting...' })}</span>
				{:else}
					<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/>
					</svg>
					<span>{$_('home.dashboard.agent.cta', { default: 'Start conversation' })}</span>
				{/if}
			</button>
		</div>
	</div>
</div>
