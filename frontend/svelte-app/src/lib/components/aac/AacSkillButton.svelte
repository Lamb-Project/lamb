<script>
	import { createSession } from '$lib/services/aacService';
	import { openTab } from '$lib/stores/aacStore.svelte';
	import { _ } from 'svelte-i18n';

	/** @type {{ skill: string, label?: string, icon?: string, assistantId?: number|null, language?: string, onSessionCreated?: (session: {id: string, title: string, firstMessage: string}) => void }} */
	let {
		skill,
		label = '',
		icon = '🤖',
		assistantId = null,
		language = 'English',
		onSessionCreated = () => {}
	} = $props();

	/** @type {boolean} */
	let launching = $state(false);

	/** @type {string} */
	let error = $state('');

	async function launch() {
		launching = true;
		error = '';
		try {
			const session = await createSession({
				assistantId,
				skill,
				context: { language }
			});
			const title = session.title || `${skill}`;
			openTab(session.id, title, assistantId, skill);
			onSessionCreated({
				id: session.id,
				title,
				firstMessage: session.first_message || ''
			});
		} catch (e) {
			error = e.message;
		}
		launching = false;
	}
</script>

<button
	onclick={launch}
	disabled={launching}
	class="inline-flex items-center gap-1.5 rounded-md border border-blue-200 bg-blue-50 px-3
		   py-1.5 text-sm font-medium text-blue-700 transition-colors
		   hover:bg-blue-100 disabled:cursor-wait disabled:opacity-50"
>
	{#if launching}
		<span class="animate-spin">⏳</span>
		<span>Starting...</span>
	{:else}
		<span>{icon}</span>
		<span>{label || skill}</span>
	{/if}
</button>

{#if error}
	<p class="mt-1 text-xs text-red-500">{error}</p>
{/if}
