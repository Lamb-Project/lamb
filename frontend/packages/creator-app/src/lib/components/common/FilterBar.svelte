<script>
  import { createEventDispatcher } from 'svelte';
  import { hasActiveFilters, countActiveFilters } from '$lib/utils/listHelpers';
  
  const dispatch = createEventDispatcher();
  
  /**
   * FilterBar Component
   * 
   * Provides search input, filter dropdowns, sorting controls, and clear filters button.
   * Pure UI component - state management handled by parent.
   * 
   * @component
   */
  
  // Props - must destructure all props in a single $props() call
  let { 
    /** @type {string} Placeholder text for search input */
    searchPlaceholder = 'Search...',
    /** @type {string} Current search value */
    searchValue = '',
    /** @type {Array<{key: string, label: string, options: Array<{value: any, label: string}>}>} Filter definitions */
    filters = [],
    /** @type {Record<string, any>} Current filter values */
    filterValues = {},
    /** @type {Array<{value: string, label: string}>} Sort options */
    sortOptions = [],
    /** @type {string} Current sort field */
    sortBy = '',
    /** @type {'asc'|'desc'} Current sort order */
    sortOrder = 'asc',
    /** @type {boolean} Show/hide sort controls */
    showSort = true,
    /** @type {boolean} Collapsible on mobile */
    collapsible = false
  } = $props();
  
  // Local state
  let isExpanded = $state(!collapsible); // Start expanded if not collapsible
  let searchInput = $state(searchValue);
  
  // Sync search input with prop
  $effect(() => {
    searchInput = searchValue;
  });
  
  // Computed
  let hasFilters = $derived(hasActiveFilters(searchValue, filterValues));
  let filterCount = $derived(countActiveFilters(searchValue, filterValues));
  
  // Event handlers
  function handleSearchInput(event) {
    const value = event.target.value;
    searchInput = value;
    dispatch('searchChange', { value });
  }
  
  function handleSearchClear() {
    searchInput = '';
    dispatch('searchChange', { value: '' });
  }
  
  function handleFilterChange(key, event) {
    const value = event.target.value;
    dispatch('filterChange', { key, value });
  }
  
  function handleSortByChange(event) {
    const newSortBy = event.target.value;
    dispatch('sortChange', { sortBy: newSortBy, sortOrder });
  }
  
  function handleSortOrderToggle() {
    const newSortOrder = sortOrder === 'asc' ? 'desc' : 'asc';
    dispatch('sortChange', { sortBy, sortOrder: newSortOrder });
  }
  
  function handleClearFilters() {
    searchInput = '';
    dispatch('clearFilters');
  }
  
  function toggleExpanded() {
    isExpanded = !isExpanded;
  }
</script>

<div class="bg-white border-b border-gray-200">
  <!-- Mobile toggle button (if collapsible) -->
  {#if collapsible}
    <div class="flex items-center justify-between px-4 py-3 sm:hidden">
      <button
        type="button"
        onclick={toggleExpanded}
        class="flex items-center gap-2 text-sm font-medium text-gray-700 hover:text-brand focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand rounded-md px-2 py-1"
      >
        <svg class="w-5 h-5 transition-transform {isExpanded ? 'rotate-180' : ''}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
        </svg>
        <span>Filters</span>
        {#if filterCount > 0}
          <span class="inline-flex items-center justify-center px-2 py-0.5 text-xs font-bold leading-none text-white bg-brand rounded-full">
            {filterCount}
          </span>
        {/if}
      </button>
      
      {#if hasFilters}
        <button
          type="button"
          onclick={handleClearFilters}
          class="text-sm text-brand hover:text-brand-hover hover:underline focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand rounded-md px-2 py-1"
        >
          Clear
        </button>
      {/if}
    </div>
  {/if}
  
  <!-- Filter controls -->
  <div class="{collapsible && !isExpanded ? 'hidden sm:block' : 'block'}">
    <div class="p-4">
      <div class="flex flex-col lg:flex-row gap-4">
        <!-- Search input -->
        <div class="flex-1 min-w-0">
          <div class="relative">
            <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <svg class="h-5 w-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </div>
            <input
              type="text"
              value={searchInput}
              oninput={handleSearchInput}
              placeholder={searchPlaceholder}
              class="block w-full pl-10 pr-10 py-2 border-gray-300 rounded-md shadow-sm focus:border-brand focus:ring-brand sm:text-sm"
            />
            {#if searchInput}
              <button
                type="button"
                onclick={handleSearchClear}
                class="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-600 focus:outline-none"
                aria-label="Clear search"
              >
                <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            {/if}
          </div>
        </div>
        
        <!-- Filter dropdowns and sort controls -->
        <div class="flex flex-wrap gap-2 items-center">
          <!-- Filter dropdowns -->
          {#each filters as filter}
            <select
              value={filterValues[filter.key] || ''}
              onchange={(e) => handleFilterChange(filter.key, e)}
              class="rounded-md border-gray-300 shadow-sm focus:border-brand focus:ring-brand text-sm py-2 px-3 min-w-[140px]"
              aria-label={filter.label}
            >
              <option value="">{filter.label}: All</option>
              {#each filter.options as option}
                <option value={option.value}>{option.label}</option>
              {/each}
            </select>
          {/each}
          
          <!-- Sort controls -->
          {#if showSort && sortOptions.length > 0}
            <div class="flex items-center gap-1 bg-gray-50 rounded-md border border-gray-300 p-0.5">
              <!-- Sort by dropdown -->
              <select
                value={sortBy}
                onchange={handleSortByChange}
                class="border-0 bg-transparent focus:border-brand focus:ring-brand text-sm py-1.5 px-2 pr-8"
                aria-label="Sort by"
              >
                <option value="">Sort by...</option>
                {#each sortOptions as option}
                  <option value={option.value}>{option.label}</option>
                {/each}
              </select>
              
              <!-- Sort order toggle button -->
              {#if sortBy}
                <button
                  type="button"
                  onclick={handleSortOrderToggle}
                  class="p-1.5 text-gray-600 hover:text-brand hover:bg-white rounded focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand"
                  aria-label="Toggle sort order: {sortOrder === 'asc' ? 'ascending' : 'descending'}"
                  title="{sortOrder === 'asc' ? 'Ascending' : 'Descending'}"
                >
                  {#if sortOrder === 'asc'}
                    <!-- Ascending icon (A→Z, 1→9) -->
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4h13M3 8h9m-9 4h6m4 0l4-4m0 0l4 4m-4-4v12" />
                    </svg>
                  {:else}
                    <!-- Descending icon (Z→A, 9→1) -->
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4h13M3 8h9m-9 4h9m5-4v12m0 0l-4-4m4 4l4-4" />
                    </svg>
                  {/if}
                </button>
              {/if}
            </div>
          {/if}
          
          <!-- Clear filters button -->
          {#if hasFilters}
            <button
              type="button"
              onclick={handleClearFilters}
              class="px-3 py-2 bg-white border border-gray-300 text-gray-700 text-sm rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand whitespace-nowrap"
            >
              Clear Filters
              <span class="ml-1.5 inline-flex items-center justify-center px-2 py-0.5 text-xs font-bold leading-none text-white bg-brand rounded-full">
                {filterCount}
              </span>
            </button>
          {/if}
        </div>
      </div>
    </div>
  </div>
</div>

