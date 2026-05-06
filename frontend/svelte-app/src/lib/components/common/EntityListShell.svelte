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

<div class="overflow-hidden rounded-lg bg-white shadow">
	<!-- Header row: title + actions slot -->
	{#if title || headerActions}
		<div class="flex items-center justify-between border-b border-gray-200 px-4 py-4 sm:px-6">
			{#if title}
				<h2 class="text-base font-semibold text-gray-900">{title}</h2>
			{/if}
			{#if headerActions}
				{@render headerActions()}
			{/if}
		</div>
	{/if}

	<!-- Filter bar + chip row (always show filter bar for search) -->
	<div class="border-b border-gray-100">
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
			<div class="flex flex-wrap items-center gap-2 px-4 pb-3">
				{#each activeChips as chip (chip.id)}
					<FilterChip id={chip.id} label={chip.label} value={chip.value} onClear={chip.onClear} />
				{/each}
				{#if showClearAll}
					<button
						type="button"
						onclick={() => onClearAllChips()}
						class="text-xs text-gray-500 hover:text-red-600 hover:underline"
					>
						{$_('list.clearAll', { default: 'Clear all' })}
					</button>
				{/if}
			</div>
		{/if}
	</div>

	<!-- Loading skeleton -->
	{#if isLoading}
		<div class="divide-y divide-gray-100" aria-busy="true" aria-label="Loading">
			{#each Array.from({ length: 4 }, (__, idx) => idx) as i (i)}
				<div class="flex animate-pulse gap-4 px-4 py-3">
					<div class="h-4 w-1/3 rounded bg-gray-200"></div>
					<div class="h-4 w-1/6 rounded bg-gray-200"></div>
					<div class="h-4 w-1/6 rounded bg-gray-200"></div>
					<div class="ml-auto h-4 w-1/8 rounded bg-gray-200"></div>
				</div>
			{/each}
		</div>

		<!-- Error state -->
	{:else if isError}
		<div class="m-4 rounded-md border border-red-200 bg-red-50 p-4" role="alert">
			<div class="flex items-start gap-3">
				<svg
					class="mt-0.5 h-5 w-5 flex-shrink-0 text-red-500"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
				>
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
					/>
				</svg>
				<div>
					<p class="text-sm font-medium text-red-800">
						{$_('list.errorTitle', { default: 'Failed to load' })}
					</p>
					{#if errorMessage}
						<p class="mt-1 text-sm text-red-700">{errorMessage}</p>
					{/if}
					<button
						onclick={() => onRetry()}
						class="mt-3 rounded-md bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-700 focus:outline-none"
					>
						{$_('list.retry', { default: 'Retry' })}
					</button>
				</div>
			</div>
		</div>

		<!-- Empty state -->
	{:else if isEmpty}
		<div class="flex flex-col items-center px-4 py-16 text-center">
			<svg
				class="mb-4 h-12 w-12 text-gray-300"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
			>
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="1.5"
					d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"
				/>
			</svg>
			{#if emptyState}
				{@render emptyState()}
			{:else}
				<p class="text-sm text-gray-500">
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
		<div class="border-t border-gray-100">
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
