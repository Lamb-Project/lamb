function getNestedValue(obj, path) {
  if (!obj || !path) return void 0;
  return path.split(".").reduce((acc, part) => acc?.[part], obj);
}
function filterBySearch(items, searchTerm, searchFields) {
  if (!searchTerm || !searchTerm.trim() || !searchFields || searchFields.length === 0) {
    return items;
  }
  const lowerSearch = searchTerm.toLowerCase().trim();
  return items.filter((item) => {
    return searchFields.some((field) => {
      const value = getNestedValue(item, field);
      if (value == null) return false;
      return String(value).toLowerCase().includes(lowerSearch);
    });
  });
}
function filterByFilters(items, filters) {
  if (!filters || Object.keys(filters).length === 0) {
    return items;
  }
  return items.filter((item) => {
    return Object.entries(filters).every(([key, filterValue]) => {
      if (filterValue === "" || filterValue === null || filterValue === void 0) {
        return true;
      }
      if (key.startsWith("exclude_")) {
        const actualKey = key.substring(8);
        const itemValue2 = getNestedValue(item, actualKey);
        return itemValue2 !== filterValue;
      }
      const itemValue = getNestedValue(item, key);
      if (typeof filterValue === "boolean") {
        return Boolean(itemValue) === filterValue;
      }
      if (filterValue === "true" || filterValue === "false") {
        return Boolean(itemValue) === (filterValue === "true");
      }
      if (Array.isArray(filterValue)) {
        return filterValue.includes(itemValue);
      }
      return itemValue === filterValue;
    });
  });
}
function sortItems(items, sortBy, sortOrder = "asc") {
  if (!sortBy || items.length === 0) {
    return items;
  }
  const sorted = [...items].sort((a, b) => {
    const aVal = getNestedValue(a, sortBy);
    const bVal = getNestedValue(b, sortBy);
    if (aVal == null && bVal == null) return 0;
    if (aVal == null) return 1;
    if (bVal == null) return -1;
    if (typeof aVal === "string" && typeof bVal === "string") {
      const comparison = aVal.toLowerCase().localeCompare(bVal.toLowerCase());
      return comparison;
    }
    if (aVal < bVal) return -1;
    if (aVal > bVal) return 1;
    return 0;
  });
  return sortOrder === "desc" ? sorted.reverse() : sorted;
}
function paginateItems(items, page, itemsPerPage) {
  if (page < 1) page = 1;
  if (itemsPerPage < 1) itemsPerPage = 10;
  const start = (page - 1) * itemsPerPage;
  const end = start + itemsPerPage;
  return items.slice(start, end);
}
function processListData(items, options = {}) {
  const {
    search = "",
    searchFields = [],
    filters = {},
    sortBy = "",
    sortOrder = "asc",
    page = 1,
    itemsPerPage = 10
  } = options;
  if (!Array.isArray(items)) {
    console.error("processListData: items must be an array");
    return {
      items: [],
      totalItems: 0,
      totalPages: 0,
      filteredCount: 0,
      originalCount: 0
    };
  }
  const originalCount = items.length;
  let filtered = filterBySearch(items, search, searchFields);
  filtered = filterByFilters(filtered, filters);
  const sorted = sortItems(filtered, sortBy, sortOrder);
  const filteredCount = sorted.length;
  const totalPages = Math.ceil(filteredCount / itemsPerPage) || 1;
  const safePage = Math.max(1, Math.min(page, totalPages));
  const paginated = paginateItems(sorted, safePage, itemsPerPage);
  return {
    items: paginated,
    totalItems: filteredCount,
    totalPages,
    filteredCount,
    originalCount,
    currentPage: safePage
  };
}
function hasActiveFilters(search, filters) {
  if (search && search.trim()) {
    return true;
  }
  if (!filters || typeof filters !== "object") {
    return false;
  }
  return Object.values(filters).some((value) => {
    return value !== "" && value !== null && value !== void 0;
  });
}
function countActiveFilters(search, filters) {
  let count = 0;
  if (search && search.trim()) {
    count++;
  }
  if (filters && typeof filters === "object") {
    count += Object.values(filters).filter((value) => {
      return value !== "" && value !== null && value !== void 0;
    }).length;
  }
  return count;
}
export {
  countActiveFilters as c,
  hasActiveFilters as h,
  processListData as p
};
