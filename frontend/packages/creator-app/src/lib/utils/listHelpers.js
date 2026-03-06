/**
 * List Helpers - Utility functions for client-side filtering, sorting, and pagination
 * 
 * These functions provide reusable logic for processing arrays of objects
 * with search, filtering, sorting, and pagination capabilities.
 */

/**
 * Get nested object value by dot-separated path
 * @param {Object} obj - Object to get value from
 * @param {string} path - Dot-separated path (e.g., "user.name" or "organization.slug")
 * @returns {any} Value at path, or undefined if not found
 * 
 * @example
 * getNestedValue({ user: { name: "John" } }, "user.name") // "John"
 */
function getNestedValue(obj, path) {
  if (!obj || !path) return undefined;
  return path.split('.').reduce((acc, part) => acc?.[part], obj);
}

/**
 * Filter array of objects by search term across multiple fields
 * @param {Array} items - Array to filter
 * @param {string} searchTerm - Search term (case-insensitive)
 * @param {Array<string>} searchFields - Fields to search in (supports dot notation)
 * @returns {Array} Filtered items
 * 
 * @example
 * filterBySearch(users, "john", ["name", "email"])
 * filterBySearch(assistants, "test", ["name", "description", "owner"])
 */
export function filterBySearch(items, searchTerm, searchFields) {
  if (!searchTerm || !searchTerm.trim() || !searchFields || searchFields.length === 0) {
    return items;
  }
  
  const lowerSearch = searchTerm.toLowerCase().trim();
  
  return items.filter(item => {
    return searchFields.some(field => {
      const value = getNestedValue(item, field);
      if (value == null) return false;
      return String(value).toLowerCase().includes(lowerSearch);
    });
  });
}

/**
 * Filter array by multiple filter criteria
 * @param {Array} items - Array to filter
 * @param {Record<string, any>} filters - Filter key-value pairs (supports dot notation for keys)
 * @returns {Array} Filtered items
 * 
 * @example
 * filterByFilters(users, { role: "admin", enabled: true })
 * filterByFilters(assistants, { published: true, "organization.slug": "engineering" })
 */
export function filterByFilters(items, filters) {
  if (!filters || Object.keys(filters).length === 0) {
    return items;
  }
  
  return items.filter(item => {
    return Object.entries(filters).every(([key, filterValue]) => {
      // Skip empty/null/undefined filter values
      if (filterValue === '' || filterValue === null || filterValue === undefined) {
        return true;
      }
      
      // Handle exclude_ prefix for negative matching
      if (key.startsWith('exclude_')) {
        const actualKey = key.substring(8); // Remove 'exclude_' prefix
        const itemValue = getNestedValue(item, actualKey);
        // Return true if item value does NOT match the filter value
        return itemValue !== filterValue;
      }
      
      const itemValue = getNestedValue(item, key);
      
      // Handle boolean filters (including string "true"/"false")
      if (typeof filterValue === 'boolean') {
        return Boolean(itemValue) === filterValue;
      }
      
      if (filterValue === 'true' || filterValue === 'false') {
        return Boolean(itemValue) === (filterValue === 'true');
      }
      
      // Handle array filters (item value is in array)
      if (Array.isArray(filterValue)) {
        return filterValue.includes(itemValue);
      }
      
      // Direct equality comparison
      return itemValue === filterValue;
    });
  });
}

/**
 * Sort array by field and order
 * @param {Array} items - Array to sort
 * @param {string} sortBy - Field to sort by (supports dot notation)
 * @param {'asc'|'desc'} sortOrder - Sort order (default: 'asc')
 * @returns {Array} Sorted items (new array, original unchanged)
 * 
 * @example
 * sortItems(users, "name", "asc")
 * sortItems(assistants, "updated_at", "desc")
 * sortItems(items, "organization.name", "asc")
 */
export function sortItems(items, sortBy, sortOrder = 'asc') {
  if (!sortBy || items.length === 0) {
    return items;
  }
  
  // Create a copy to avoid mutating original array
  const sorted = [...items].sort((a, b) => {
    const aVal = getNestedValue(a, sortBy);
    const bVal = getNestedValue(b, sortBy);
    
    // Handle null/undefined - always sort to end
    if (aVal == null && bVal == null) return 0;
    if (aVal == null) return 1;
    if (bVal == null) return -1;
    
    // Handle strings (case-insensitive)
    if (typeof aVal === 'string' && typeof bVal === 'string') {
      const comparison = aVal.toLowerCase().localeCompare(bVal.toLowerCase());
      return comparison;
    }
    
    // Handle numbers and dates
    if (aVal < bVal) return -1;
    if (aVal > bVal) return 1;
    return 0;
  });
  
  // Reverse for descending order
  return sortOrder === 'desc' ? sorted.reverse() : sorted;
}

/**
 * Paginate array
 * @param {Array} items - Array to paginate
 * @param {number} page - Current page (1-indexed)
 * @param {number} itemsPerPage - Items per page
 * @returns {Array} Page of items
 * 
 * @example
 * paginateItems(users, 1, 10) // First 10 items
 * paginateItems(users, 2, 10) // Items 11-20
 */
export function paginateItems(items, page, itemsPerPage) {
  if (page < 1) page = 1;
  if (itemsPerPage < 1) itemsPerPage = 10;
  
  const start = (page - 1) * itemsPerPage;
  const end = start + itemsPerPage;
  
  return items.slice(start, end);
}

/**
 * Apply all filters, sorting, and pagination to an array
 * This is the main function that combines all operations in the correct order:
 * 1. Filter by search
 * 2. Filter by filters
 * 3. Sort
 * 4. Paginate
 * 
 * @param {Array} items - Original items array
 * @param {Object} options - Processing options
 * @param {string} [options.search=''] - Search term
 * @param {Array<string>} [options.searchFields=[]] - Fields to search in
 * @param {Record<string, any>} [options.filters={}] - Filter criteria
 * @param {string} [options.sortBy=''] - Field to sort by
 * @param {'asc'|'desc'} [options.sortOrder='asc'] - Sort order
 * @param {number} [options.page=1] - Current page (1-indexed)
 * @param {number} [options.itemsPerPage=10] - Items per page
 * @returns {Object} Processed results with metadata
 * 
 * @example
 * processListData(users, {
 *   search: "john",
 *   searchFields: ["name", "email"],
 *   filters: { role: "admin" },
 *   sortBy: "name",
 *   sortOrder: "asc",
 *   page: 1,
 *   itemsPerPage: 10
 * })
 * // Returns:
 * // {
 * //   items: [...],           // Paginated items for current page
 * //   totalItems: 150,        // Total filtered items (before pagination)
 * //   totalPages: 15,         // Total pages
 * //   filteredCount: 150,     // Count after filtering
 * //   originalCount: 500      // Original array length
 * // }
 */
export function processListData(items, options = {}) {
  const {
    search = '',
    searchFields = [],
    filters = {},
    sortBy = '',
    sortOrder = 'asc',
    page = 1,
    itemsPerPage = 10
  } = options;
  
  // Ensure we have an array
  if (!Array.isArray(items)) {
    console.error('processListData: items must be an array');
    return {
      items: [],
      totalItems: 0,
      totalPages: 0,
      filteredCount: 0,
      originalCount: 0
    };
  }
  
  const originalCount = items.length;
  
  // Step 1: Filter by search
  let filtered = filterBySearch(items, search, searchFields);
  
  // Step 2: Filter by filters
  filtered = filterByFilters(filtered, filters);
  
  // Step 3: Sort
  const sorted = sortItems(filtered, sortBy, sortOrder);
  
  // Step 4: Calculate pagination metadata
  const filteredCount = sorted.length;
  const totalPages = Math.ceil(filteredCount / itemsPerPage) || 1;
  
  // Ensure page is within bounds
  const safePage = Math.max(1, Math.min(page, totalPages));
  
  // Step 5: Paginate
  const paginated = paginateItems(sorted, safePage, itemsPerPage);
  
  return {
    items: paginated,
    totalItems: filteredCount,
    totalPages: totalPages,
    filteredCount: filteredCount,
    originalCount: originalCount,
    currentPage: safePage
  };
}

/**
 * Check if any filters are active
 * @param {string} search - Search term
 * @param {Record<string, any>} filters - Filter object
 * @returns {boolean} True if any filters are active
 * 
 * @example
 * hasActiveFilters("test", { role: "admin" }) // true
 * hasActiveFilters("", {}) // false
 */
export function hasActiveFilters(search, filters) {
  if (search && search.trim()) {
    return true;
  }
  
  if (!filters || typeof filters !== 'object') {
    return false;
  }
  
  return Object.values(filters).some(value => {
    return value !== '' && value !== null && value !== undefined;
  });
}

/**
 * Count active filters
 * @param {string} search - Search term
 * @param {Record<string, any>} filters - Filter object
 * @returns {number} Number of active filters
 * 
 * @example
 * countActiveFilters("test", { role: "admin", enabled: true }) // 3
 */
export function countActiveFilters(search, filters) {
  let count = 0;
  
  if (search && search.trim()) {
    count++;
  }
  
  if (filters && typeof filters === 'object') {
    count += Object.values(filters).filter(value => {
      return value !== '' && value !== null && value !== undefined;
    }).length;
  }
  
  return count;
}

