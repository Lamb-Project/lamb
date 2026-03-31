<script>
	import { createSession } from '$lib/services/aacService';
	import { openTab } from '$lib/stores/aacStore.svelte';
	import { _ } from 'svelte-i18n';

	/** @type {{ skill: string, label?: string, icon?: string, assistantId?: number|null, language?: string, onSessionCreated?: (session: {id: string, title: string, firstMessage: string}) => void }} */
	let { skill, label = '', icon = '🤖', assistantId = null, language = 'English', onSessionCreated = () => {} } = $props();

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
				context: { language },
			});
			const title = session.title || `${skill}`;
			openTab(session.id, title, assistantId, skill);
			onSessionCreated({
				id: session.id,
				title,
				firstMessage: session.first_message || '',
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
	class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium
		   bg-blue-50 text-blue-700 hover:bg-blue-100 border border-blue-200
		   disabled:opacity-50 disabled:cursor-wait transition-colors"
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
	<p class="text-xs text-red-500 mt-1">{error}</p>
{/if}
