<script>
	import { getOpenTabs, getActiveTabId, setActiveTab, closeTab } from '$lib/stores/aacStore.svelte';

	/** @type {{ onTabChange?: (id: string|null) => void, onBackToMain?: () => void }} */
	let { onTabChange = () => {}, onBackToMain = () => {} } = $props();

	let tabs = $derived(getOpenTabs());
	let activeId = $derived(getActiveTabId());

	function handleTabClick(id) {
		setActiveTab(id);
		onTabChange(id);
	}

	function handleClose(e, id) {
		e.stopPropagation();
		closeTab(id);
		onTabChange(getActiveTabId());
	}

	function handleBack() {
		onBackToMain();
	}
</script>

{#if tabs.length > 0}
	<div class="flex items-center border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 overflow-x-auto">
		<!-- Main view tab -->
		<button
			onclick={handleBack}
			class="px-4 py-2 text-sm font-medium whitespace-nowrap border-b-2 transition-colors"
			class:border-blue-500={!activeId}
			class:text-blue-600={!activeId}
			class:border-transparent={activeId}
			class:text-gray-500={activeId}
			class:hover:text-gray-700={activeId}
		>
			📋 Assistant
		</button>

		<!-- Session tabs -->
		{#each tabs as tab}
			<button
				onclick={() => handleTabClick(tab.id)}
				class="group flex items-center gap-1.5 px-3 py-2 text-sm whitespace-nowrap border-b-2 transition-colors"
				class:border-blue-500={activeId === tab.id}
				class:text-blue-600={activeId === tab.id}
				class:border-transparent={activeId !== tab.id}
				class:text-gray-500={activeId !== tab.id}
				class:hover:text-gray-700={activeId !== tab.id}
			>
				<span>🤖</span>
				<span class="max-w-[150px] truncate">{tab.title || 'Session'}</span>
				<button
					onclick={(e) => handleClose(e, tab.id)}
					class="ml-1 opacity-0 group-hover:opacity-60 hover:opacity-100 transition-opacity text-xs"
					title="Close session"
				>
					✕
				</button>
			</button>
		{/each}
	</div>
{/if}
