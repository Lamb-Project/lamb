<script>
	import { _ } from '@lamb/ui';
	import { Modal, Button } from '$lib/components/ui';
	import { Search } from '$lib/components/ui/icons';
	import { searchOrganizations } from '$lib/services/adminService';
	import { user } from '@lamb/ui';

	let { onApply, onClose } = $props();

	let searchQuery = $state('');
	let searchResults = $state([]);
	let isSearching = $state(false);
	let searchError = $state(null);
	let selectedOrg = $state(null);

	async function doSearch() {
		if (searchQuery.length < 2) return;
		isSearching = true;
		searchError = null;
		try {
			const data = await searchOrganizations(searchQuery);
			searchResults = data.organizations || [];
		} catch (e) {
			searchError = e?.message || 'Unknown error';
		} finally {
			isSearching = false;
		}
	}

	function selectOrg(org) {
		selectedOrg = org;
	}

	function handleApply() {
		if (selectedOrg) onApply(selectedOrg);
	}

	function handleKeydown(e) {
		if (e.key === 'Enter') doSearch();
	}
</script>

<svelte:window onkeydown={handleKeydown} />

<Modal open={true} onclose={onClose} title={$_('admin.costManagement.orgFilter.title', { default: 'Filter by organization' })}>
	<div class="p-5">
		<div class="flex gap-2 mb-4">
			<input
				type="text"
				bind:value={searchQuery}
				placeholder={$_('admin.costManagement.orgFilter.placeholder', { default: 'Type organization name...' })}
				class="flex-1 border border-border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-brand focus:outline-none"
			/>
			<Button variant="primary" onclick={doSearch} disabled={isSearching || searchQuery.length < 2} iconLeftComponent={Search}>
				{isSearching ? '...' : $_('admin.costManagement.orgFilter.search', { default: 'Search' })}
			</Button>
		</div>

		{#if searchError}
			<p class="text-sm text-danger mb-3">{searchError}</p>
		{/if}

		<div class="max-h-60 overflow-y-auto mb-4 space-y-1">
			{#each searchResults as org}
				<label
					class="flex items-center gap-3 w-full px-3 py-2 rounded-lg text-sm cursor-pointer hover:bg-surface-hover {selectedOrg?.id === org.id ? 'bg-brand/10 font-medium' : ''}"
				>
					<input
						type="radio"
						name="org-filter"
						value={org.id}
						checked={selectedOrg?.id === org.id}
						onchange={() => selectOrg(org)}
						class="accent-brand"
					/>
					<span>{org.name}</span>
				</label>
			{/each}
		</div>

		<div class="flex justify-end gap-2 border-t border-border pt-3">
			<Button variant="ghost" onclick={onClose}>
				{$_('common.cancel', { default: 'Cancel' })}
			</Button>
			<Button variant="primary" onclick={handleApply} disabled={!selectedOrg}>
				{$_('admin.costManagement.orgFilter.apply', { default: 'Apply' })}
			</Button>
		</div>
	</div>
</Modal>
