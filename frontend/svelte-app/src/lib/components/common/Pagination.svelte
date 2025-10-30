<script>
  import { createEventDispatcher } from 'svelte';
  
  const dispatch = createEventDispatcher();
  
  /**
   * Pagination Component
   * 
   * Provides page navigation, items per page selection, and results display.
   * Pure UI component - state management handled by parent.
   * 
   * @component
   */
  
  // Props - must destructure all props in a single $props() call
  let { 
    /** @type {number} Current page (1-indexed) */
    currentPage = 1,
    /** @type {number} Total number of pages */
    totalPages = 1,
    /** @type {number} Total number of items (across all pages) */
    totalItems = 0,
    /** @type {number} Items per page */
    itemsPerPage = 10,
    /** @type {number[]} Available items per page options */
    itemsPerPageOptions = [5, 10, 25, 50, 100]
  } = $props();
  
  // Computed values
  let startItem = $derived(totalItems === 0 ? 0 : (currentPage - 1) * itemsPerPage + 1);
  let endItem = $derived(Math.min(currentPage * itemsPerPage, totalItems));
  
  // Generate page numbers to display (with ellipsis for large page counts)
  let visiblePages = $derived(getVisiblePages(currentPage, totalPages));
  
  /**
   * Calculate which page numbers to show (max 7 with ellipsis)
   * Examples:
   * - Pages 1-7: [1, 2, 3, 4, 5, 6, 7]
   * - Page 1 of 20: [1, 2, 3, '...', 18, 19, 20]
   * - Page 10 of 20: [1, 2, '...', 9, 10, 11, '...', 19, 20]
   * - Page 20 of 20: [1, 2, 3, '...', 18, 19, 20]
   */
  function getVisiblePages(current, total) {
    if (total <= 7) {
      // Show all pages
      return Array.from({ length: total }, (_, i) => i + 1);
    }
    
    // Always show first 2 and last 2
    const pages = [];
    
    if (current <= 4) {
      // Near start: [1, 2, 3, 4, 5, ..., 19, 20]
      for (let i = 1; i <= 5; i++) pages.push(i);
      pages.push('...');
      pages.push(total - 1);
      pages.push(total);
    } else if (current >= total - 3) {
      // Near end: [1, 2, ..., 16, 17, 18, 19, 20]
      pages.push(1);
      pages.push(2);
      pages.push('...');
      for (let i = total - 4; i <= total; i++) pages.push(i);
    } else {
      // Middle: [1, 2, ..., 9, 10, 11, ..., 19, 20]
      pages.push(1);
      pages.push(2);
      pages.push('...');
      pages.push(current - 1);
      pages.push(current);
      pages.push(current + 1);
      pages.push('...');
      pages.push(total - 1);
      pages.push(total);
    }
    
    return pages;
  }
  
  // Event handlers
  function handlePageChange(newPage) {
    if (newPage >= 1 && newPage <= totalPages && newPage !== currentPage) {
      dispatch('pageChange', { page: newPage });
    }
  }
  
  function handleItemsPerPageChange(event) {
    const newItemsPerPage = parseInt(event.target.value, 10);
    if (!isNaN(newItemsPerPage) && newItemsPerPage > 0) {
      dispatch('itemsPerPageChange', { itemsPerPage: newItemsPerPage });
    }
  }
  
  function handleFirstPage() {
    handlePageChange(1);
  }
  
  function handlePreviousPage() {
    handlePageChange(currentPage - 1);
  }
  
  function handleNextPage() {
    handlePageChange(currentPage + 1);
  }
  
  function handleLastPage() {
    handlePageChange(totalPages);
  }
</script>

{#if totalPages > 0}
  <div class="flex flex-col sm:flex-row items-center justify-between gap-4 px-4 py-3 bg-white border-t border-gray-200">
    <!-- Items per page selector -->
    <div class="flex items-center gap-2">
      <label for="items-per-page" class="text-sm text-gray-700 whitespace-nowrap">
        Items per page:
      </label>
      <select
        id="items-per-page"
        value={itemsPerPage}
        onchange={handleItemsPerPageChange}
        class="rounded-md border-gray-300 shadow-sm focus:border-brand focus:ring-brand text-sm py-1 px-2"
      >
        {#each itemsPerPageOptions as option}
          <option value={option}>{option}</option>
        {/each}
      </select>
    </div>
    
    <!-- Page navigation -->
    <div class="flex items-center gap-2">
      <!-- First page -->
      <button
        type="button"
        onclick={handleFirstPage}
        disabled={currentPage === 1}
        class="px-2 py-1 text-sm rounded-md bg-white border border-gray-300 text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand disabled:opacity-50 disabled:cursor-not-allowed"
        aria-label="First page"
      >
        «
      </button>
      
      <!-- Previous page -->
      <button
        type="button"
        onclick={handlePreviousPage}
        disabled={currentPage === 1}
        class="px-3 py-1 text-sm rounded-md bg-white border border-gray-300 text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand disabled:opacity-50 disabled:cursor-not-allowed"
        aria-label="Previous page"
      >
        Previous
      </button>
      
      <!-- Page numbers -->
      <div class="hidden sm:flex items-center gap-1">
        {#each visiblePages as page}
          {#if page === '...'}
            <span class="px-2 py-1 text-sm text-gray-500">...</span>
          {:else}
            <button
              type="button"
              onclick={() => handlePageChange(page)}
              class="{page === currentPage 
                ? 'bg-brand text-white hover:bg-brand-hover' 
                : 'bg-white border border-gray-300 text-gray-700 hover:bg-gray-50'} 
                px-3 py-1 text-sm rounded-md focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand min-w-[2.5rem]"
              aria-label="Page {page}"
              aria-current={page === currentPage ? 'page' : undefined}
            >
              {page}
            </button>
          {/if}
        {/each}
      </div>
      
      <!-- Mobile: Current page indicator -->
      <div class="sm:hidden px-3 py-1 text-sm text-gray-700">
        {currentPage} / {totalPages}
      </div>
      
      <!-- Next page -->
      <button
        type="button"
        onclick={handleNextPage}
        disabled={currentPage === totalPages}
        class="px-3 py-1 text-sm rounded-md bg-white border border-gray-300 text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand disabled:opacity-50 disabled:cursor-not-allowed"
        aria-label="Next page"
      >
        Next
      </button>
      
      <!-- Last page -->
      <button
        type="button"
        onclick={handleLastPage}
        disabled={currentPage === totalPages}
        class="px-2 py-1 text-sm rounded-md bg-white border border-gray-300 text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand disabled:opacity-50 disabled:cursor-not-allowed"
        aria-label="Last page"
      >
        »
      </button>
    </div>
    
    <!-- Results info -->
    <div class="text-sm text-gray-700 whitespace-nowrap">
      {#if totalItems > 0}
        Showing <span class="font-medium">{startItem}</span> to <span class="font-medium">{endItem}</span> of <span class="font-medium">{totalItems}</span>
      {:else}
        No results
      {/if}
    </div>
  </div>
{/if}

