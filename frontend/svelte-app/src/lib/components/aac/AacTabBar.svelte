<script>
	import { openTabs, activeTabId, setActiveTab, closeTab } from '$lib/stores/aacStore.svelte';
	import { get } from 'svelte/store';

	/** @type {{ onTabChange?: (id: string|null) => void, onBackToMain?: () => void }} */
	let { onTabChange = () => {}, onBackToMain = () => {} } = $props();

	function handleTabClick(id) {
		setActiveTab(id);
		onTabChange(id);
	}

	function handleClose(e, id) {
		e.stopPropagation();
		closeTab(id);
		onTabChange(get(activeTabId));
	}

	function handleBack() {
		onBackToMain();
	}
</script>

{#if $openTabs.length > 0}
	<div
		class="flex items-center overflow-x-auto border-b border-gray-200 bg-gray-50 dark:border-gray-700 dark:bg-gray-800"
	>
		<!-- Main view tab -->
		<button
			onclick={handleBack}
			class="border-b-2 px-4 py-2 text-sm font-medium whitespace-nowrap transition-colors"
			class:border-blue-500={!$activeTabId}
			class:text-blue-600={!$activeTabId}
			class:border-transparent={$activeTabId}
			class:text-gray-500={$activeTabId}
			class:hover:text-gray-700={$activeTabId}
		>
			📋 Assistant
		</button>

		<!-- Session tabs -->
		{#each $openTabs as tab}
			<button
				onclick={() => handleTabClick(tab.id)}
				class="group flex items-center gap-1.5 border-b-2 px-3 py-2 text-sm whitespace-nowrap transition-colors"
				class:border-blue-500={$activeTabId === tab.id}
				class:text-blue-600={$activeTabId === tab.id}
				class:border-transparent={$activeTabId !== tab.id}
				class:text-gray-500={$activeTabId !== tab.id}
				class:hover:text-gray-700={$activeTabId !== tab.id}
			>
				<span>🤖</span>
				<span class="max-w-[150px] truncate">{tab.title || 'Session'}</span>
				<button
					onclick={(e) => handleClose(e, tab.id)}
					class="ml-1 text-xs opacity-0 transition-opacity group-hover:opacity-60 hover:opacity-100"
					title="Close session"
				>
					✕
				</button>
			</button>
		{/each}
	</div>
{/if}
