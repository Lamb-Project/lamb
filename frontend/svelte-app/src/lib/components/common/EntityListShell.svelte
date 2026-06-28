<!--
  @component EntityListShell
  Shared shell for LibrariesList and KnowledgeStoresList.
  Handles header row, FilterBar, filter chips, skeleton loading,
  error state, empty state, table area, and Pagination.

  Usage:
    <EntityListShell
      title="My Libraries"
      {filters}
      {filterValues}
      {activeChips}
      {searchValue}
      {searchPlaceholder}
      {sortOptions}
      {sortBy}
      {sortOrder}
      {isLoading}
      {isError}
      errorMessage="..."
      {isEmpty}
      {isFiltered}
      {currentPage}
      {totalPages}
      {totalItems}
      {itemsPerPage}
      onRetry={...}
      onSearchChange={...}
      onFilterChange={...}
      onSortChange={...}
      onClearFilters={...}
      onClearChip={...}
      onPageChange={...}
      onItemsPerPageChange={...}
    >
      {#snippet headerActions()}<button>...</button>{/snippet}
      {#snippet emptyState()}<p>No items.</p>{/snippet}
      {#snippet table()}<tbody>...</tbody>{/snippet}
    </EntityListShell>
-->
<script>
	import FilterBar from '$lib/components/common/FilterBar.svelte';
	import FilterChip from '$lib/components/common/FilterChip.svelte';
	import Pagination from '$lib/components/common/Pagination.svelte';
	import { _ } from '$lib/i18n';
	import { Banner, Button, SkeletonTable } from '$lib/components/ui';
	import { Inbox } from '$lib/components/ui/icons.js';
	import { RefreshCw } from 'lucide-svelte';

	let {
		/** @type {string} */
		title = '',
		/** @type {Array<{key: string, label: string, options: Array<{value: any, label: string}>}>} */
		filters = [],
		/** @type {Record<string, any>} */
		filterValues = {},
		/** @type {Array<{id: string, label: string, value: string, onClear: () => void}>} */
		activeChips = [],
		/** @type {string} */
		searchValue = '',
		/** @type {string} */
		searchPlaceholder = '',
		/** @type {Array<{value: string, label: string}>} */
		sortOptions = [],
		/** @type {string} */
		sortBy = '',
		/** @type {'asc'|'desc'} */
		sortOrder = 'asc',
		/** @type {boolean} */
		isLoading = false,
		/** @type {boolean} */
		isError = false,
		/** @type {string} */
		errorMessage = '',
		/** @type {boolean} */
		isEmpty = false,
		/** @type {boolean} Is empty because of filters vs truly empty */
		isFiltered = false,
		/** @type {number} */
		currentPage = 1,
		/** @type {number} */
		totalPages = 1,
		/** @type {number} */
		totalItems = 0,
		/** @type {number} */
		itemsPerPage = 10,
		/** @type {() => void} */
		onRetry = /** @type {() => void} */ (() => {}),
		/** @type {(event: CustomEvent<any>) => void} */
		onSearchChange = /** @type {(event: CustomEvent<any>) => void} */ (() => {}),
		/** @type {(event: CustomEvent<any>) => void} */
		onFilterChange = /** @type {(event: CustomEvent<any>) => void} */ (() => {}),
		/** @type {(event: CustomEvent<any>) => void} */
		onSortChange = /** @type {(event: CustomEvent<any>) => void} */ (() => {}),
		/** @type {() => void} */
		onClearFilters = /** @type {() => void} */ (() => {}),
		/** @type {() => void} */
		onClearAllChips = /** @type {() => void} */ (() => {}),
		/** @type {(event: CustomEvent<any>) => void} */
		onPageChange = /** @type {(event: CustomEvent<any>) => void} */ (() => {}),
		/** @type {(event: CustomEvent<any>) => void} */
		onItemsPerPageChange = /** @type {(event: CustomEvent<any>) => void} */ (() => {}),
		/** @type {import('svelte').Snippet|undefined} */
		headerActions = undefined,
		/** @type {import('svelte').Snippet|undefined} */
		emptyState = undefined,
		/** @type {import('svelte').Snippet|undefined} */
		table = undefined
	} = $props();

	let showClearAll = $derived(activeChips.length >= 2);
</script>

<div class="border-border bg-surface shadow-card overflow-hidden rounded-lg border">
	<!-- Header row: title + actions slot -->
	{#if title || headerActions}
		<div class="border-border flex items-center justify-between border-b px-4 py-4 sm:px-6">
			{#if title}
				<h2 class="type-section-title">{title}</h2>
			{/if}
			{#if headerActions}
				{@render headerActions()}
			{/if}
		</div>
	{/if}

	<!-- Filter bar + chip row (always show filter bar for search) -->
	<div class="border-border border-b">
		<FilterBar
			{searchValue}
			{searchPlaceholder}
			{filters}
			{filterValues}
			{sortOptions}
			{sortBy}
			{sortOrder}
			on:searchChange={(e) => onSearchChange(e)}
			on:filterChange={(e) => onFilterChange(e)}
			on:sortChange={(e) => onSortChange(e)}
			on:clearFilters={() => onClearFilters()}
		/>
		<!-- Active filter chips -->
		{#if activeChips.length > 0}
			<div class="flex flex-wrap items-center gap-2 px-4 pt-4 pb-2">
				{#each activeChips as chip (chip.id)}
					<FilterChip id={chip.id} label={chip.label} value={chip.value} onClear={chip.onClear} />
				{/each}
				{#if showClearAll}
					<button
						type="button"
						onclick={() => onClearAllChips()}
						class="text-muted hover:text-danger text-xs hover:underline"
					>
						{$_('list.clearAll', { default: 'Clear all' })}
					</button>
				{/if}
			</div>
		{/if}
	</div>

	<!-- Loading skeleton -->
	{#if isLoading}
		<div class="p-4" aria-busy="true" aria-label="Loading">
			<SkeletonTable rows={itemsPerPage || 4} columns={5} class="border-0 shadow-none" />
		</div>

		<!-- Error state -->
	{:else if isError}
		<div class="p-4">
			<Banner
				variant="danger"
				title={$_('list.errorTitle', { default: 'Failed to load' })}
				description={errorMessage}
			>
				{#snippet actions()}
					<Button
						variant="secondary"
						size="sm"
						iconLeftComponent={RefreshCw}
						onclick={() => onRetry()}
					>
						{$_('common.retry', { default: 'Retry' })}
					</Button>
				{/snippet}
			</Banner>
		</div>

		<!-- Empty state -->
	{:else if isEmpty}
		<div class="flex flex-col items-center px-4 py-16 text-center">
			<Inbox class="text-muted mb-4 h-12 w-12" />
			{#if emptyState}
				{@render emptyState()}
			{:else}
				<p class="text-muted text-sm">
					{isFiltered
						? $_('list.noResults', { default: 'No items match your filters.' })
						: $_('list.noItems', { default: 'No items yet.' })}
				</p>
			{/if}
		</div>

		<!-- Table content -->
	{:else}
		<div class="overflow-x-auto">
			{#if table}
				{@render table()}
			{/if}
		</div>

		<!-- Pagination -->
		<div class="border-border border-t">
			<Pagination
				{currentPage}
				{totalPages}
				{totalItems}
				{itemsPerPage}
				on:pageChange={(e) => onPageChange(e)}
				on:itemsPerPageChange={(e) => onItemsPerPageChange(e)}
			/>
		</div>
	{/if}
</div>
