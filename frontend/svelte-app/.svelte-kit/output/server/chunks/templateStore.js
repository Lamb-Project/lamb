import { a as attr_class, b as attr, e as ensure_array_like, s as stringify } from "./index2.js";
import { h as hasActiveFilters, c as countActiveFilters } from "./listHelpers.js";
import { e as escape_html } from "./context.js";
import { d as derived, w as writable, g as get } from "./index.js";
import axios from "axios";
import { a as getConfig } from "./config.js";
function FilterBar($$renderer, $$props) {
  $$renderer.component(($$renderer2) => {
    let {
      /** @type {string} Placeholder text for search input */
      searchPlaceholder = "Search...",
      /** @type {string} Current search value */
      searchValue = "",
      /** @type {Array<{key: string, label: string, options: Array<{value: any, label: string}>}>} Filter definitions */
      filters = [],
      /** @type {Record<string, any>} Current filter values */
      filterValues = {},
      /** @type {Array<{value: string, label: string}>} Sort options */
      sortOptions = [],
      /** @type {string} Current sort field */
      sortBy = "",
      /** @type {'asc'|'desc'} Current sort order */
      sortOrder = "asc",
      /** @type {boolean} Show/hide sort controls */
      showSort = true,
      /** @type {boolean} Collapsible on mobile */
      collapsible = false
    } = $$props;
    let isExpanded = !collapsible;
    let searchInput = searchValue;
    let hasFilters = hasActiveFilters(searchValue, filterValues);
    let filterCount = countActiveFilters(searchValue, filterValues);
    function handleFilterChange(key, event) {
      event.target.value;
    }
    function handleSortByChange(event) {
      event.target.value;
    }
    $$renderer2.push(`<div class="bg-white border-b border-gray-200">`);
    if (collapsible) {
      $$renderer2.push("<!--[-->");
      $$renderer2.push(`<div class="flex items-center justify-between px-4 py-3 sm:hidden"><button type="button" class="flex items-center gap-2 text-sm font-medium text-gray-700 hover:text-brand focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand rounded-md px-2 py-1"><svg${attr_class(`w-5 h-5 transition-transform ${stringify(isExpanded ? "rotate-180" : "")}`)} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg> <span>Filters</span> `);
      if (filterCount > 0) {
        $$renderer2.push("<!--[-->");
        $$renderer2.push(`<span class="inline-flex items-center justify-center px-2 py-0.5 text-xs font-bold leading-none text-white bg-brand rounded-full">${escape_html(filterCount)}</span>`);
      } else {
        $$renderer2.push("<!--[!-->");
      }
      $$renderer2.push(`<!--]--></button> `);
      if (hasFilters) {
        $$renderer2.push("<!--[-->");
        $$renderer2.push(`<button type="button" class="text-sm text-brand hover:text-brand-hover hover:underline focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand rounded-md px-2 py-1">Clear</button>`);
      } else {
        $$renderer2.push("<!--[!-->");
      }
      $$renderer2.push(`<!--]--></div>`);
    } else {
      $$renderer2.push("<!--[!-->");
    }
    $$renderer2.push(`<!--]--> <div${attr_class(collapsible && !isExpanded ? "hidden sm:block" : "block")}><div class="p-4"><div class="flex flex-col lg:flex-row gap-4"><div class="flex-1 min-w-0"><div class="relative"><div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none"><svg class="h-5 w-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg></div> <input type="text"${attr("value", searchInput)}${attr("placeholder", searchPlaceholder)} class="block w-full pl-10 pr-10 py-2 border-gray-300 rounded-md shadow-sm focus:border-brand focus:ring-brand sm:text-sm"/> `);
    if (searchInput) {
      $$renderer2.push("<!--[-->");
      $$renderer2.push(`<button type="button" class="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-600 focus:outline-none" aria-label="Clear search"><svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg></button>`);
    } else {
      $$renderer2.push("<!--[!-->");
    }
    $$renderer2.push(`<!--]--></div></div> <div class="flex flex-wrap gap-2 items-center"><!--[-->`);
    const each_array = ensure_array_like(filters);
    for (let $$index_1 = 0, $$length = each_array.length; $$index_1 < $$length; $$index_1++) {
      let filter = each_array[$$index_1];
      $$renderer2.select(
        {
          value: filterValues[filter.key] || "",
          onchange: (e) => handleFilterChange(filter.key, e),
          class: "rounded-md border-gray-300 shadow-sm focus:border-brand focus:ring-brand text-sm py-2 px-3 min-w-[140px]",
          "aria-label": filter.label
        },
        ($$renderer3) => {
          $$renderer3.option({ value: "" }, ($$renderer4) => {
            $$renderer4.push(`${escape_html(filter.label)}: All`);
          });
          $$renderer3.push(`<!--[-->`);
          const each_array_1 = ensure_array_like(filter.options);
          for (let $$index = 0, $$length2 = each_array_1.length; $$index < $$length2; $$index++) {
            let option = each_array_1[$$index];
            $$renderer3.option({ value: option.value }, ($$renderer4) => {
              $$renderer4.push(`${escape_html(option.label)}`);
            });
          }
          $$renderer3.push(`<!--]-->`);
        }
      );
    }
    $$renderer2.push(`<!--]--> `);
    if (showSort && sortOptions.length > 0) {
      $$renderer2.push("<!--[-->");
      $$renderer2.push(`<div class="flex items-center gap-1 bg-gray-50 rounded-md border border-gray-300 p-0.5">`);
      $$renderer2.select(
        {
          value: sortBy,
          onchange: handleSortByChange,
          class: "border-0 bg-transparent focus:border-brand focus:ring-brand text-sm py-1.5 px-2 pr-8",
          "aria-label": "Sort by"
        },
        ($$renderer3) => {
          $$renderer3.option({ value: "" }, ($$renderer4) => {
            $$renderer4.push(`Sort by...`);
          });
          $$renderer3.push(`<!--[-->`);
          const each_array_2 = ensure_array_like(sortOptions);
          for (let $$index_2 = 0, $$length = each_array_2.length; $$index_2 < $$length; $$index_2++) {
            let option = each_array_2[$$index_2];
            $$renderer3.option({ value: option.value }, ($$renderer4) => {
              $$renderer4.push(`${escape_html(option.label)}`);
            });
          }
          $$renderer3.push(`<!--]-->`);
        }
      );
      $$renderer2.push(` `);
      if (sortBy) {
        $$renderer2.push("<!--[-->");
        $$renderer2.push(`<button type="button" class="p-1.5 text-gray-600 hover:text-brand hover:bg-white rounded focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand"${attr("aria-label", `Toggle sort order: ${stringify(sortOrder === "asc" ? "ascending" : "descending")}`)}${attr("title", sortOrder === "asc" ? "Ascending" : "Descending")}>`);
        if (sortOrder === "asc") {
          $$renderer2.push("<!--[-->");
          $$renderer2.push(`<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4h13M3 8h9m-9 4h6m4 0l4-4m0 0l4 4m-4-4v12"></path></svg>`);
        } else {
          $$renderer2.push("<!--[!-->");
          $$renderer2.push(`<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4h13M3 8h9m-9 4h9m5-4v12m0 0l-4-4m4 4l4-4"></path></svg>`);
        }
        $$renderer2.push(`<!--]--></button>`);
      } else {
        $$renderer2.push("<!--[!-->");
      }
      $$renderer2.push(`<!--]--></div>`);
    } else {
      $$renderer2.push("<!--[!-->");
    }
    $$renderer2.push(`<!--]--> `);
    if (hasFilters) {
      $$renderer2.push("<!--[-->");
      $$renderer2.push(`<button type="button" class="px-3 py-2 bg-white border border-gray-300 text-gray-700 text-sm rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand whitespace-nowrap">Clear Filters <span class="ml-1.5 inline-flex items-center justify-center px-2 py-0.5 text-xs font-bold leading-none text-white bg-brand rounded-full">${escape_html(filterCount)}</span></button>`);
    } else {
      $$renderer2.push("<!--[!-->");
    }
    $$renderer2.push(`<!--]--></div></div></div></div></div>`);
  });
}
const config = getConfig();
const API_BASE = config.api.lambServer;
const TEMPLATES_BASE = `${API_BASE}/creator/prompt-templates`;
function getAuthHeaders() {
  const token = localStorage.getItem("userToken");
  if (!token) {
    throw new Error("No authentication token found");
  }
  return {
    "Authorization": `Bearer ${token}`,
    "Content-Type": "application/json"
  };
}
async function deleteTemplate$1(templateId) {
  try {
    await axios.delete(`${TEMPLATES_BASE}/${templateId}`, {
      headers: getAuthHeaders()
    });
  } catch (error) {
    console.error("Error deleting template:", error);
    throw error;
  }
}
const userTemplates = writable([]);
const userTemplatesTotal = writable(0);
const userTemplatesLimit = writable(20);
const userTemplatesLoading = writable(false);
const sharedTemplates = writable([]);
const sharedTemplatesTotal = writable(0);
const sharedTemplatesLimit = writable(20);
const sharedTemplatesLoading = writable(false);
const currentTab = writable("my");
const selectedTemplateIds = writable([]);
const templateSelectModalOpen = writable(false);
const templateError = writable(null);
async function deleteTemplate(templateId) {
  try {
    templateError.set(null);
    await deleteTemplate$1(templateId);
    const tab = get(currentTab);
    if (tab === "my") {
      userTemplates.update((templates) => templates.filter((t) => t.id !== templateId));
      userTemplatesTotal.update((total) => total - 1);
    } else {
      sharedTemplates.update((templates) => templates.filter((t) => t.id !== templateId));
      sharedTemplatesTotal.update((total) => total - 1);
    }
  } catch (error) {
    console.error("Error deleting template:", error);
    templateError.set(error.response?.data?.detail || error.message || "Failed to delete template");
    throw error;
  }
}
derived(
  [userTemplatesTotal, userTemplatesLimit],
  ([$total, $limit]) => Math.ceil($total / $limit) || 1
);
derived(
  [sharedTemplatesTotal, sharedTemplatesLimit],
  ([$total, $limit]) => Math.ceil($total / $limit) || 1
);
derived(
  [currentTab, userTemplates, sharedTemplates],
  ([$tab, $user, $shared]) => $tab === "my" ? $user : $shared
);
const currentLoading = derived(
  [currentTab, userTemplatesLoading, sharedTemplatesLoading],
  ([$tab, $userLoading, $sharedLoading]) => $tab === "my" ? $userLoading : $sharedLoading
);
const currentTotal = derived(
  [currentTab, userTemplatesTotal, sharedTemplatesTotal],
  ([$tab, $userTotal, $sharedTotal]) => $tab === "my" ? $userTotal : $sharedTotal
);
export {
  FilterBar as F,
  currentLoading as a,
  templateError as b,
  currentTab as c,
  currentTotal as d,
  selectedTemplateIds as e,
  deleteTemplate as f,
  sharedTemplates as s,
  templateSelectModalOpen as t,
  userTemplates as u
};
