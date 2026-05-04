<script>
	import { onMount } from 'svelte';
	import { getOpenTabs, getActiveTabId, setActiveTab, closeTab } from '$lib/stores/aacStore.svelte';
	import { deleteSession } from '$lib/services/aacService';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { _ } from '$lib/i18n';

	/** @type {Array<{id: string, title: string, assistantId: number|null, skill: string|null}>} */
	let tabs = $state([]);
	/** @type {string|null} */
	let activeId = $state(null);

	// Poll the store periodically since cross-module $state reactivity
	// doesn't work reliably in Svelte 5 built mode
	onMount(() => {
		function sync() {
			tabs = [...getOpenTabs()];
			activeId = getActiveTabId();
		}
		sync();
		const interval = setInterval(sync, 500);
		return () => clearInterval(interval);
	});

	const skillIcons = {
		'about-lamb': '🤖',
		'create-assistant': '➕',
		'improve-assistant': '✨',
		'explain-assistant': '🔍',
		'test-and-evaluate': '🧪',
		'test-lti-tools': '🔗'
	};

	function icon(skill) {
		return skillIcons[skill] || '💬';
	}

	async function switchToTab(id) {
		setActiveTab(id);
		activeId = id;
		if (!$page.url.pathname.startsWith('/agent') || $page.url.pathname.includes('/history')) {
			await goto(`/agent?session=${id}`);
		}
	}

	async function closeSessionTab(e, id) {
		e.stopPropagation();
		try {
			await deleteSession(id);
		} catch (_) {
			/* might already be archived */
		}
		closeTab(id);
		tabs = [...getOpenTabs()];
		activeId = getActiveTabId();
		if (id === activeId && $page.url.pathname.startsWith('/agent')) {
			if (tabs.length > 0) {
				await goto(`/agent?session=${tabs[tabs.length - 1].id}`);
			} else {
				await goto('/agent/history');
			}
		}
	}
</script>

{#if tabs.length > 0}
	<div class="border-b border-gray-200 bg-white px-4 sm:px-6 lg:px-8">
		<div class="mx-auto flex max-w-7xl items-center gap-1 overflow-x-auto py-1">
			{#each tabs as tab}
				<button
					onclick={() => switchToTab(tab.id)}
					class="group flex items-center gap-1.5 rounded-t-md border border-b-0 px-3 py-1.5
                           text-sm whitespace-nowrap transition-colors
                           {activeId === tab.id && !$page.url.pathname.includes('/history')
						? 'border-blue-300 bg-blue-50 font-medium text-blue-700'
						: 'border-transparent text-gray-500 hover:bg-gray-50 hover:text-gray-700'}"
				>
					<span class="text-xs">{icon(tab.skill)}</span>
					<span class="max-w-[150px] truncate">{tab.title || tab.id.slice(0, 8)}</span>
					<span
						role="button"
						tabindex="0"
						onclick={(e) => closeSessionTab(e, tab.id)}
						onkeydown={(e) => {
							if (e.key === 'Enter') closeSessionTab(e, tab.id);
						}}
						class="ml-1 cursor-pointer text-xs text-gray-400 opacity-0 transition-opacity group-hover:opacity-100 hover:text-red-500"
						title={$_('agent.tabs.close', { default: 'Close session' })}
					>
						✕
					</span>
				</button>
			{/each}
			<a
				href="/agent/history"
				class="flex items-center gap-1.5 rounded-t-md border border-b-0 px-3 py-1.5
                       text-sm whitespace-nowrap transition-colors
                       {$page.url.pathname.includes('/history')
					? 'border-blue-300 bg-blue-50 font-medium text-blue-700'
					: 'border-transparent text-gray-500 hover:bg-gray-50 hover:text-gray-700'}"
			>
				<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
					/>
				</svg>
				<span>{$_('agent.history.title', { default: 'History' })}</span>
			</a>
		</div>
	</div>
{/if}
