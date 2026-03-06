import { c as store_get, e as ensure_array_like, b as attr, a as attr_class, s as stringify, u as unsubscribe_stores, f as attr_style } from "../../../chunks/index2.js";
import { g as get, w as writable } from "../../../chunks/index.js";
import "@sveltejs/kit/internal";
import "../../../chunks/exports.js";
import "../../../chunks/utils.js";
import "@sveltejs/kit/internal/server";
import "../../../chunks/state.svelte.js";
import { u as user } from "../../../chunks/userStore.js";
import { g as getApiUrl } from "../../../chunks/config.js";
import "../../../chunks/i18n.js";
import { $ as $locale, a as $format } from "../../../chunks/runtime.js";
import { e as escape_html } from "../../../chunks/context.js";
import { F as FilterBar, u as userTemplates, s as sharedTemplates, t as templateSelectModalOpen, c as currentTab, a as currentLoading, b as templateError, d as currentTotal, e as selectedTemplateIds, f as deleteTemplate } from "../../../chunks/templateStore.js";
import { C as ConfirmationModal } from "../../../chunks/ConfirmationModal.js";
import { p as processListData } from "../../../chunks/listHelpers.js";
import "clsx";
import { s as sanitizeName } from "../../../chunks/nameSanitizer.js";
import { o as onDestroy } from "../../../chunks/index-server.js";
import "../../../chunks/AssistantSharingModal.svelte_svelte_type_style_lang.js";
import "marked";
import { p as page } from "../../../chunks/stores.js";
import { g as goto } from "../../../chunks/client.js";
import { b as base } from "../../../chunks/server.js";
function html(value) {
  var html2 = String(value ?? "");
  var open = "<!---->";
  return open + html2 + "<!---->";
}
function Pagination($$renderer, $$props) {
  $$renderer.component(($$renderer2) => {
    var $$store_subs;
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
    } = $$props;
    let startItem = totalItems === 0 ? 0 : (currentPage - 1) * itemsPerPage + 1;
    let endItem = Math.min(currentPage * itemsPerPage, totalItems);
    let visiblePages = getVisiblePages(currentPage, totalPages);
    function getVisiblePages(current, total) {
      if (total <= 7) {
        return Array.from({ length: total }, (_, i) => i + 1);
      }
      const pages = [];
      if (current <= 4) {
        for (let i = 1; i <= 5; i++) pages.push(i);
        pages.push("...");
        pages.push(total - 1);
        pages.push(total);
      } else if (current >= total - 3) {
        pages.push(1);
        pages.push(2);
        pages.push("...");
        for (let i = total - 4; i <= total; i++) pages.push(i);
      } else {
        pages.push(1);
        pages.push(2);
        pages.push("...");
        pages.push(current - 1);
        pages.push(current);
        pages.push(current + 1);
        pages.push("...");
        pages.push(total - 1);
        pages.push(total);
      }
      return pages;
    }
    function handleItemsPerPageChange(event) {
      parseInt(event.target.value, 10);
    }
    if (totalPages > 0) {
      $$renderer2.push("<!--[-->");
      $$renderer2.push(`<div class="flex flex-col sm:flex-row items-center justify-between gap-4 px-4 py-3 bg-white border-t border-gray-200"><div class="flex items-center gap-2"><label for="items-per-page" class="text-sm text-gray-700 whitespace-nowrap">${escape_html(store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("pagination.itemsPerPage", { default: "Items per page:" }) : "Items per page:")}</label> `);
      $$renderer2.select(
        {
          id: "items-per-page",
          value: itemsPerPage,
          onchange: handleItemsPerPageChange,
          class: "rounded-md border-gray-300 shadow-sm focus:border-brand focus:ring-brand text-sm py-1 px-2"
        },
        ($$renderer3) => {
          $$renderer3.push(`<!--[-->`);
          const each_array = ensure_array_like(itemsPerPageOptions);
          for (let $$index = 0, $$length = each_array.length; $$index < $$length; $$index++) {
            let option = each_array[$$index];
            $$renderer3.option({ value: option }, ($$renderer4) => {
              $$renderer4.push(`${escape_html(option)}`);
            });
          }
          $$renderer3.push(`<!--]-->`);
        }
      );
      $$renderer2.push(`</div> <div class="flex items-center gap-2"><button type="button"${attr("disabled", currentPage === 1, true)} class="px-2 py-1 text-sm rounded-md bg-white border border-gray-300 text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand disabled:opacity-50 disabled:cursor-not-allowed"${attr("aria-label", store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("pagination.firstPage", { default: "First page" }) : "First page")}>«</button> <button type="button"${attr("disabled", currentPage === 1, true)} class="px-3 py-1 text-sm rounded-md bg-white border border-gray-300 text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand disabled:opacity-50 disabled:cursor-not-allowed"${attr("aria-label", store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("pagination.previousPage", { default: "Previous page" }) : "Previous page")}>${escape_html(store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("pagination.previous", { default: "Previous" }) : "Previous")}</button> <div class="hidden sm:flex items-center gap-1"><!--[-->`);
      const each_array_1 = ensure_array_like(visiblePages);
      for (let $$index_1 = 0, $$length = each_array_1.length; $$index_1 < $$length; $$index_1++) {
        let page2 = each_array_1[$$index_1];
        if (page2 === "...") {
          $$renderer2.push("<!--[-->");
          $$renderer2.push(`<span class="px-2 py-1 text-sm text-gray-500">...</span>`);
        } else {
          $$renderer2.push("<!--[!-->");
          $$renderer2.push(`<button type="button"${attr_class(`${stringify(page2 === currentPage ? "bg-brand text-white hover:bg-brand-hover" : "bg-white border border-gray-300 text-gray-700 hover:bg-gray-50")} px-3 py-1 text-sm rounded-md focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand min-w-[2.5rem]`)}${attr("aria-label", store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("pagination.pageN", { default: "Page {page}", values: { page: page2 } }) : `Page ${page2}`)}${attr("aria-current", page2 === currentPage ? "page" : void 0)}>${escape_html(page2)}</button>`);
        }
        $$renderer2.push(`<!--]-->`);
      }
      $$renderer2.push(`<!--]--></div> <div class="sm:hidden px-3 py-1 text-sm text-gray-700">${escape_html(currentPage)} / ${escape_html(totalPages)}</div> <button type="button"${attr("disabled", currentPage === totalPages, true)} class="px-3 py-1 text-sm rounded-md bg-white border border-gray-300 text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand disabled:opacity-50 disabled:cursor-not-allowed"${attr("aria-label", store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("pagination.nextPage", { default: "Next page" }) : "Next page")}>${escape_html(store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("pagination.next", { default: "Next" }) : "Next")}</button> <button type="button"${attr("disabled", currentPage === totalPages, true)} class="px-2 py-1 text-sm rounded-md bg-white border border-gray-300 text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand disabled:opacity-50 disabled:cursor-not-allowed"${attr("aria-label", store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("pagination.lastPage", { default: "Last page" }) : "Last page")}>»</button></div> <div class="text-sm text-gray-700 whitespace-nowrap">`);
      if (totalItems > 0) {
        $$renderer2.push("<!--[-->");
        $$renderer2.push(`${escape_html(store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("pagination.showing", {
          default: "Showing {first} to {last} of {total} results",
          values: { first: startItem, last: endItem, total: totalItems }
        }) : `Showing ${startItem} to ${endItem} of ${totalItems}`)}`);
      } else {
        $$renderer2.push("<!--[!-->");
        $$renderer2.push(`${escape_html(store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("pagination.noResults", { default: "No results" }) : "No results")}`);
      }
      $$renderer2.push(`<!--]--></div></div>`);
    } else {
      $$renderer2.push("<!--[!-->");
    }
    $$renderer2.push(`<!--]-->`);
    if ($$store_subs) unsubscribe_stores($$store_subs);
  });
}
async function getAssistants(limit = 10, offset = 0) {
  {
    console.warn("getAssistants called outside browser context");
    return { assistants: [], total_count: 0 };
  }
}
async function deleteAssistant(id) {
  try {
    const token = localStorage.getItem("userToken");
    if (!token) {
      throw new Error("Not authenticated");
    }
    const userEmail = localStorage.getItem("userEmail");
    if (!userEmail) {
      throw new Error("User email not found in localStorage");
    }
    const apiUrl = getApiUrl(
      `/assistant/delete_assistant/${id}?owner=${encodeURIComponent(userEmail)}`
    );
    const response = await fetch(apiUrl, {
      method: "DELETE",
      headers: {
        Authorization: `Bearer ${token}`
      }
    });
    if (!response.ok) {
      let errorData = { detail: `Error: ${response.status}` };
      try {
        errorData = await response.json();
      } catch (e) {
      }
      if (response.status === 403) {
        throw new Error("You do not have permission to delete this assistant");
      } else if (response.status === 404) {
        throw new Error("Assistant not found");
      } else {
        throw new Error(errorData.detail || `Error: ${response.status}`);
      }
    }
    const text = await response.text();
    return text ? JSON.parse(text) : {};
  } catch (error) {
    console.error("Error deleting assistant:", error);
    if (error instanceof Error) {
      throw error;
    } else {
      throw new Error("An unknown error occurred during assistant deletion");
    }
  }
}
async function getSharedAssistants() {
  {
    console.warn("getSharedAssistants called outside browser context");
    return { assistants: [], count: 0 };
  }
}
function formatDate(timestamp, options = {}) {
  const { includeTime = true, relative = false } = options;
  if (!timestamp || timestamp === null || timestamp === void 0) {
    return "-";
  }
  try {
    const date = new Date(timestamp * 1e3);
    if (isNaN(date.getTime())) {
      return "-";
    }
    if (relative) {
      return getRelativeTime(date);
    }
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    if (includeTime) {
      const hours = String(date.getHours()).padStart(2, "0");
      const minutes = String(date.getMinutes()).padStart(2, "0");
      const seconds = String(date.getSeconds()).padStart(2, "0");
      return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
    } else {
      return `${year}-${month}-${day}`;
    }
  } catch (error) {
    console.error("Error formatting date:", error);
    return "-";
  }
}
function getRelativeTime(date) {
  const now = /* @__PURE__ */ new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSeconds = Math.floor(diffMs / 1e3);
  const diffMinutes = Math.floor(diffSeconds / 60);
  const diffHours = Math.floor(diffMinutes / 60);
  const diffDays = Math.floor(diffHours / 24);
  const diffWeeks = Math.floor(diffDays / 7);
  const diffMonths = Math.floor(diffDays / 30);
  const diffYears = Math.floor(diffDays / 365);
  if (diffSeconds < 60) {
    return "Just now";
  } else if (diffMinutes < 60) {
    return `${diffMinutes} minute${diffMinutes !== 1 ? "s" : ""} ago`;
  } else if (diffHours < 24) {
    return `${diffHours} hour${diffHours !== 1 ? "s" : ""} ago`;
  } else if (diffDays < 7) {
    return `${diffDays} day${diffDays !== 1 ? "s" : ""} ago`;
  } else if (diffWeeks < 4) {
    return `${diffWeeks} week${diffWeeks !== 1 ? "s" : ""} ago`;
  } else if (diffMonths < 12) {
    return `${diffMonths} month${diffMonths !== 1 ? "s" : ""} ago`;
  } else {
    return `${diffYears} year${diffYears !== 1 ? "s" : ""} ago`;
  }
}
function formatDateForTable(timestamp) {
  return formatDate(timestamp, { includeTime: true, relative: false });
}
function AssistantsList($$renderer, $$props) {
  $$renderer.component(($$renderer2) => {
    var $$store_subs;
    let showDeleteModal = false;
    let deleteTarget = { id: null, name: "", published: false };
    let isDeleting = false;
    async function handleDeleteConfirm() {
      if (!deleteTarget.id || isDeleting) return;
      isDeleting = true;
      try {
        await deleteAssistant(deleteTarget.id);
        await loadAllAssistants();
        showDeleteModal = false;
        deleteTarget = { id: null, name: "", published: false };
      } catch (err) {
        console.error("Error deleting assistant:", err);
      } finally {
        isDeleting = false;
      }
    }
    function handleDeleteCancel() {
      if (isDeleting) return;
      showDeleteModal = false;
      deleteTarget = { id: null, name: "", published: false };
    }
    let { showShared = false } = $$props;
    let localeLoaded = !!get($locale);
    let allAssistants = [];
    let displayAssistants = [];
    let loading = true;
    let error = null;
    let isRefreshing = false;
    let searchTerm = "";
    let filterStatus = "";
    let sortBy = "updated_at";
    let sortOrder = "desc";
    let currentPage = 1;
    let itemsPerPage = 10;
    let totalPages = 1;
    let totalItems = 0;
    async function loadAllAssistants(retryAttempt = false) {
      loading = true;
      error = null;
      try {
        console.log(showShared ? "Fetching shared assistants..." : "Fetching all assistants...");
        const response = showShared ? await getSharedAssistants() : await getAssistants(100, 0);
        console.log("Received assistants:", response);
        allAssistants = response.assistants || [];
        applyFiltersAndPagination();
      } catch (err) {
        console.error("Error loading assistants:", err);
        if (!retryAttempt) {
          console.log("Will retry loading assistants in 1 second...");
          loading = true;
          await new Promise((resolve) => setTimeout(resolve, 1e3));
          return loadAllAssistants(true);
        }
        error = err instanceof Error ? err.message : String(err);
        allAssistants = [];
        displayAssistants = [];
        totalItems = 0;
      } finally {
        loading = false;
      }
    }
    function applyFiltersAndPagination() {
      const result = processListData(allAssistants, {
        search: searchTerm,
        searchFields: ["name", "description", "owner"],
        filters: {
          published: null
        },
        sortBy,
        sortOrder,
        page: currentPage,
        itemsPerPage
      });
      displayAssistants = result.items;
      totalItems = result.filteredCount;
      totalPages = result.totalPages;
      currentPage = result.currentPage;
    }
    function parseMetadata(jsonString) {
      if (!jsonString) return {};
      try {
        return JSON.parse(jsonString);
      } catch (e) {
        console.error("Error parsing metadata:", e, jsonString);
        return {};
      }
    }
    const IconView = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M2.036 12.322a1.012 1.012 0 0 1 0-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178Z" /><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" /></svg>`;
    const IconDelete = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0" /></svg>`;
    const IconRefresh = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99" /></svg>`;
    const IconExport = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3" /></svg>`;
    let $$settled = true;
    let $$inner_renderer;
    function $$render_inner($$renderer3) {
      $$renderer3.push(`<div class="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">`);
      if (loading) {
        $$renderer3.push("<!--[-->");
        $$renderer3.push(`<p class="text-center text-gray-500 py-4">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("assistants.loading", { default: "Loading assistants..." }) : "Loading assistants...")}</p>`);
      } else {
        $$renderer3.push("<!--[!-->");
        if (error) {
          $$renderer3.push("<!--[-->");
          $$renderer3.push(`<div class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative" role="alert"><strong class="font-bold">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("assistants.errorTitle") : "Error:")}</strong> <span class="block sm:inline">${escape_html(error)}</span></div>`);
        } else {
          $$renderer3.push("<!--[!-->");
          FilterBar($$renderer3, {
            searchPlaceholder: localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("assistants.searchPlaceholder", { default: "Search assistants by name, description..." }) : "Search assistants by name, description...",
            searchValue: searchTerm,
            filters: [
              {
                key: "status",
                label: localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("assistants.filters.status", { default: "Status" }) : "Status",
                options: [
                  {
                    value: "published",
                    label: localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("assistants.status.published", { default: "Published" }) : "Published"
                  },
                  {
                    value: "unpublished",
                    label: localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("assistants.status.unpublished", { default: "Not Published" }) : "Not Published"
                  }
                ]
              }
            ],
            filterValues: { status: filterStatus },
            sortOptions: [
              {
                value: "name",
                label: localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("assistants.sort.name", { default: "Name" }) : "Name"
              },
              {
                value: "updated_at",
                label: localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("assistants.sort.updated", { default: "Last Modified" }) : "Last Modified"
              },
              {
                value: "created_at",
                label: localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("assistants.sort.created", { default: "Created Date" }) : "Created Date"
              }
            ],
            sortBy,
            sortOrder
          });
          $$renderer3.push(`<!----> <div class="flex justify-between items-center mb-4 px-4"><div class="text-sm text-gray-600">`);
          {
            $$renderer3.push("<!--[!-->");
            $$renderer3.push(`<span class="font-medium">${escape_html(totalItems)}</span> ${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("assistants.totalItems", { default: "assistants" }) : "assistants")}`);
          }
          $$renderer3.push(`<!--]--></div> <button${attr("disabled", loading || isRefreshing, true)}${attr("title", localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("common.refresh", { default: "Refresh" }) : "Refresh")} class="p-2 text-sm font-medium bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand disabled:opacity-50 disabled:cursor-not-allowed"><span${attr_class("", void 0, { "animate-spin": isRefreshing })}>${html(IconRefresh)}</span></button></div> `);
          if (displayAssistants.length === 0) {
            $$renderer3.push("<!--[-->");
            if (allAssistants.length === 0) {
              $$renderer3.push("<!--[-->");
              $$renderer3.push(`<div class="text-center py-12 bg-white border border-gray-200 rounded-lg"><p class="text-gray-500">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("assistants.noAssistants", { default: "No assistants found." }) : "No assistants found.")}</p></div>`);
            } else {
              $$renderer3.push("<!--[!-->");
              $$renderer3.push(`<div class="text-center py-12 bg-white border border-gray-200 rounded-lg"><p class="text-gray-500 mb-4">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("assistants.noMatches", { default: "No assistants match your filters" }) : "No assistants match your filters")}</p> <button class="text-brand hover:text-brand-hover hover:underline focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand rounded-md px-3 py-1">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("common.clearFilters", { default: "Clear filters" }) : "Clear filters")}</button></div>`);
            }
            $$renderer3.push(`<!--]-->`);
          } else {
            $$renderer3.push("<!--[!-->");
            $$renderer3.push(`<div class="overflow-x-auto shadow-md sm:rounded-lg mb-6 border border-gray-200"><table class="min-w-full divide-y divide-gray-200 table-fixed"><colgroup><col class="w-1/5"/><col class="w-2/5"/><col class="w-1/5"/><col class="w-1/5"/></colgroup><thead class="bg-gray-50"><tr><th scope="col" class="px-6 py-3 text-left text-xs font-medium text-brand uppercase tracking-wider cursor-pointer hover:bg-gray-100 select-none"><div class="flex items-center gap-1">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("assistants.table.name", { default: "Assistant Name" }) : "Assistant Name")} `);
            {
              $$renderer3.push("<!--[!-->");
            }
            $$renderer3.push(`<!--]--></div></th><th scope="col" class="px-6 py-3 text-left text-xs font-medium text-brand uppercase tracking-wider">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("assistants.table.description", { default: "Description" }) : "Description")}</th><th scope="col" class="px-6 py-3 text-left text-xs font-medium text-brand uppercase tracking-wider cursor-pointer hover:bg-gray-100 select-none whitespace-nowrap"><div class="flex items-center gap-1">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("assistants.table.createdUpdated", { default: "Created / Updated" }) : "Created / Updated")} `);
            {
              $$renderer3.push("<!--[-->");
              $$renderer3.push(`<span class="text-xs text-gray-500 ml-1">(${escape_html("Updated")})</span> `);
              {
                $$renderer3.push("<!--[!-->");
                $$renderer3.push(`<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4h13M3 8h9m-9 4h9m5-4v12m0 0l-4-4m4 4l4-4"></path></svg>`);
              }
              $$renderer3.push(`<!--]-->`);
            }
            $$renderer3.push(`<!--]--></div></th><th scope="col" class="px-6 py-3 text-left text-xs font-medium text-brand uppercase tracking-wider">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("assistants.table.actions", { default: "Actions" }) : "Actions")}</th></tr></thead><tbody class="bg-white divide-y divide-gray-200"><!--[-->`);
            const each_array = ensure_array_like(displayAssistants);
            for (let $$index = 0, $$length = each_array.length; $$index < $$length; $$index++) {
              let assistant = each_array[$$index];
              $$renderer3.push(`<tr class="hover:bg-gray-50"><td class="px-6 py-4 whitespace-normal align-top"><button class="text-sm font-medium text-brand hover:underline break-words text-left">${escape_html(assistant.name || "-")}</button> <div class="mt-1 flex flex-wrap gap-1">`);
              if (assistant.published) {
                $$renderer3.push("<!--[-->");
                $$renderer3.push(`<span class="inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800 px-2 py-0.5">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("assistants.status.published", { default: "Published" }) : "Published")}</span>`);
              } else {
                $$renderer3.push("<!--[!-->");
                $$renderer3.push(`<span class="inline-flex text-xs leading-5 font-semibold rounded-full bg-yellow-100 text-yellow-800 px-2 py-0.5">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("assistants.status.unpublished", { default: "Unpublished" }) : "Unpublished")}</span>`);
              }
              $$renderer3.push(`<!--]--> `);
              if (showShared) {
                $$renderer3.push("<!--[-->");
                $$renderer3.push(`<span class="inline-flex text-xs leading-5 font-semibold rounded-full bg-blue-100 text-blue-800 px-2 py-0.5">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("assistants.status.sharedWithYou", { default: "Shared with you" }) : "Shared with you")}</span>`);
              } else {
                $$renderer3.push("<!--[!-->");
              }
              $$renderer3.push(`<!--]--> `);
              if (assistant.metadata) {
                $$renderer3.push("<!--[-->");
                const callback = parseMetadata(assistant.metadata);
                if (callback.capabilities?.vision) {
                  $$renderer3.push("<!--[-->");
                  $$renderer3.push(`<span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800"><svg class="w-3 h-3 mr-1" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"></path></svg> ${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("assistants.table.visionEnabled", { default: "Vision" }) : "Vision")}</span>`);
                } else {
                  $$renderer3.push("<!--[!-->");
                }
                $$renderer3.push(`<!--]-->`);
              } else {
                $$renderer3.push("<!--[!-->");
              }
              $$renderer3.push(`<!--]--></div></td><td class="px-6 py-4 align-top"><div class="text-sm text-gray-500 break-words">${escape_html(assistant.description || (localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("assistants.noDescription", { default: "No description provided" }) : "No description provided"))}</div></td><td class="px-6 py-4 text-sm text-gray-500 align-top"><div class="flex flex-col gap-1"><div><span class="text-xs text-gray-400 font-medium">Created:</span> <div class="text-xs">${escape_html(formatDateForTable(assistant.created_at))}</div></div> <div><span class="text-xs text-gray-400 font-medium">Updated:</span> <div class="text-xs">${escape_html(formatDateForTable(assistant.updated_at))}</div></div></div></td><td class="px-6 py-4 whitespace-nowrap text-sm font-medium align-top"><div class="flex items-center space-x-1 sm:space-x-2"><button${attr("title", localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("assistants.actions.view", { default: "View" }) : "View")} class="text-green-600 hover:text-green-900 p-1 rounded hover:bg-green-100 transition-colors duration-150">${html(IconView)}</button> <button${attr("title", localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("assistants.actions.export", { default: "Export JSON" }) : "Export JSON")} class="text-green-600 hover:text-green-900 p-1 rounded hover:bg-green-100 transition-colors duration-150">${html(IconExport)}</button> `);
              if (!assistant.published) {
                $$renderer3.push("<!--[-->");
                $$renderer3.push(`<button${attr("title", localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("assistants.actions.delete", { default: "Delete" }) : "Delete")} class="text-red-600 hover:text-red-900 p-1 rounded hover:bg-red-100 transition-colors duration-150">${html(IconDelete)}</button>`);
              } else {
                $$renderer3.push("<!--[!-->");
              }
              $$renderer3.push(`<!--]--></div> <div class="text-xs text-gray-400 mt-2">ID: ${escape_html(assistant.id)}</div></td></tr> `);
              if (assistant.metadata) {
                $$renderer3.push("<!--[-->");
                const callback = parseMetadata(assistant.metadata);
                $$renderer3.push(`<tr class="bg-gray-50 border-b border-gray-200"><td colspan="2" class="px-6 py-2 text-sm"><div class="flex flex-wrap items-center"><span class="text-brand font-medium mr-1">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("assistants.table.promptProcessor", { default: "Prompt Processor" }) : "Prompt Processor")}:</span> <span class="mr-3">${escape_html(callback.prompt_processor || (localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("assistants.notSet", { default: "Not set" }) : "Not set"))}</span> <span class="text-brand font-medium mr-1">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("assistants.table.connector", { default: "Connector" }) : "Connector")}:</span> <span class="mr-3">${escape_html(callback.connector || (localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("assistants.notSet", { default: "Not set" }) : "Not set"))}</span> <span class="text-brand font-medium mr-1">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("assistants.table.llm", { default: "LLM" }) : "LLM")}:</span> <span class="mr-3">${escape_html(callback.llm || (localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("assistants.notSet", { default: "Not set" }) : "Not set"))}</span> <span class="text-brand font-medium mr-1">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("assistants.table.ragProcessor", { default: "RAG Processor" }) : "RAG Processor")}:</span> <span class="mr-3">${escape_html(callback.rag_processor || (localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("assistants.notSet", { default: "Not set" }) : "Not set"))}</span> `);
                if (callback.capabilities?.vision) {
                  $$renderer3.push("<!--[-->");
                  $$renderer3.push(`<span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 mr-3"><svg class="w-3 h-3 mr-1" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"></path></svg> ${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("assistants.table.visionEnabled", { default: "Vision Enabled" }) : "Vision Enabled")}</span>`);
                } else {
                  $$renderer3.push("<!--[!-->");
                }
                $$renderer3.push(`<!--]--></div></td><td class="px-6 py-2"></td></tr> `);
                if (callback.rag_processor === "simple_rag") {
                  $$renderer3.push("<!--[-->");
                  $$renderer3.push(`<tr class="bg-gray-50 border-b border-gray-200"><td colspan="2" class="px-6 py-2 text-sm"><div class="flex flex-wrap"><div class="mr-6 mb-1"><span class="text-brand font-medium">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("assistants.table.ragTopK", { default: "RAG Top K" }) : "RAG Top K")}:</span> <span class="ml-1">${escape_html(assistant.RAG_Top_k ?? (localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("assistants.notSet", { default: "Not set" }) : "Not set"))}</span></div> <div><span class="text-brand font-medium">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("assistants.table.ragCollections", { default: "RAG Collections" }) : "RAG Collections")}:</span> <span class="ml-1 truncate"${attr("title", assistant.RAG_collections || "")}>${escape_html(assistant.RAG_collections || (localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("assistants.notSet", { default: "Not set" }) : "Not set"))}</span></div></div></td><td class="px-6 py-2"></td></tr>`);
                } else {
                  $$renderer3.push("<!--[!-->");
                }
                $$renderer3.push(`<!--]-->`);
              } else {
                $$renderer3.push("<!--[!-->");
                $$renderer3.push(`<tr class="bg-gray-50 border-b border-gray-200"><td colspan="2" class="px-6 py-2 text-sm text-gray-500"><span class="text-brand font-medium">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("assistants.table.config", { default: "Configuration" }) : "Configuration")}:</span> <span class="ml-1">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("assistants.notSet", { default: "Not available" }) : "Not available")}</span></td><td class="px-6 py-2"></td></tr>`);
              }
              $$renderer3.push(`<!--]-->`);
            }
            $$renderer3.push(`<!--]--></tbody></table></div> `);
            if (totalPages > 1) {
              $$renderer3.push("<!--[-->");
              Pagination($$renderer3, {
                currentPage,
                totalPages,
                totalItems,
                itemsPerPage,
                itemsPerPageOptions: [5, 10, 25, 50, 100]
              });
            } else {
              $$renderer3.push("<!--[!-->");
            }
            $$renderer3.push(`<!--]-->`);
          }
          $$renderer3.push(`<!--]-->`);
        }
        $$renderer3.push(`<!--]-->`);
      }
      $$renderer3.push(`<!--]--></div> `);
      ConfirmationModal($$renderer3, {
        title: localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("assistants.deleteModal.title", { default: "Delete Assistant" }) : "Delete Assistant",
        message: localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("assistants.deleteModal.confirmation", {
          values: { name: deleteTarget.name },
          default: `Are you sure you want to delete the assistant "${deleteTarget.name}"? This action cannot be undone.`
        }) : `Are you sure you want to delete the assistant "${deleteTarget.name}"? This action cannot be undone.`,
        confirmText: localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("assistants.deleteModal.confirmButton", { default: "Delete" }) : "Delete",
        variant: "danger",
        onconfirm: handleDeleteConfirm,
        oncancel: handleDeleteCancel,
        get isOpen() {
          return showDeleteModal;
        },
        set isOpen($$value) {
          showDeleteModal = $$value;
          $$settled = false;
        },
        get isLoading() {
          return isDeleting;
        },
        set isLoading($$value) {
          isDeleting = $$value;
          $$settled = false;
        }
      });
      $$renderer3.push(`<!---->`);
    }
    do {
      $$settled = true;
      $$inner_renderer = $$renderer2.copy();
      $$render_inner($$inner_renderer);
    } while (!$$settled);
    $$renderer2.subsume($$inner_renderer);
    if ($$store_subs) unsubscribe_stores($$store_subs);
  });
}
const initialState = {
  systemCapabilities: null,
  configDefaults: null,
  loading: false,
  error: null,
  lastLoadedTimestamp: null
  // Restore timestamp
};
function getFallbackDefaults() {
  console.warn("Using hardcoded fallback defaults");
  const defaults = {
    config: {
      // Correctly nested under 'config' key
      // "lamb_helper_assistant": "lamb_assistant.1", // Remove non-defined property
      system_prompt: "You are a wise surfer dude and a helpful teaching assistant that uses Retrieval-Augmented Generation (RAG) to improve your answers.",
      prompt_template: "You are a wise surfer dude and a helpful teaching assistant that uses Retrieval-Augmented Generation (RAG) to improve your answers.\nThis is the user input: {user_input}\nThis is the context: {context}\nNow answer the question:",
      prompt_processor: "simple_augment",
      connector: "openai",
      llm: "gpt-4o-mini",
      rag_processor: "no_rag",
      // Use consistent key format
      RAG_Top_k: "3",
      rag_placeholders: ["--- {context} --- ", "--- {user_input} ---"]
    }
  };
  return (
    /** @type {ConfigDefaults} */
    defaults
  );
}
function getFallbackCapabilities() {
  console.warn("Using fallback capabilities (no models - org-specific models could not be loaded)");
  const capabilities = {
    prompt_processors: ["simple_augment"],
    connectors: {},
    rag_processors: ["no_rag", "simple_rag", "context_aware_rag", "single_file_rag"]
  };
  return capabilities;
}
function createAssistantConfigStore() {
  const { subscribe, set, update } = writable(initialState);
  async function loadConfig() {
    console.log("assistantConfigStore: loadConfig called (with caching).");
    {
      console.warn(
        "assistantConfigStore: Running in non-browser context, using fallback configuration."
      );
      set({
        systemCapabilities: getFallbackCapabilities(),
        configDefaults: getFallbackDefaults(),
        loading: false,
        error: null,
        lastLoadedTimestamp: Date.now()
      });
      return;
    }
  }
  return {
    subscribe,
    loadConfig,
    reset: () => {
      console.log("assistantConfigStore: Resetting store to initial state.");
      set(initialState);
    },
    clearCache: () => {
      console.log("assistantConfigStore: Clearing cached capabilities and defaults.");
      set(initialState);
    }
  };
}
const assistantConfigStore = createAssistantConfigStore();
function TemplateSelectModal($$renderer, $$props) {
  $$renderer.component(($$renderer2) => {
    var $$store_subs;
    let searchQuery = "";
    let selectedTemplate = null;
    let filteredUserTemplates = store_get($$store_subs ??= {}, "$userTemplates", userTemplates);
    let filteredSharedTemplates = store_get($$store_subs ??= {}, "$sharedTemplates", sharedTemplates);
    if (store_get($$store_subs ??= {}, "$templateSelectModalOpen", templateSelectModalOpen)) {
      $$renderer2.push("<!--[-->");
      $$renderer2.push(`<div class="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center z-50" role="button" tabindex="-1"><div class="bg-white rounded-lg shadow-xl w-full max-w-5xl max-h-[80vh] flex flex-col"><div class="px-6 py-4 border-b border-gray-200"><div class="flex items-center justify-between"><h2 class="text-xl font-bold text-gray-900">${escape_html(store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("promptTemplates.selectTemplate", { default: "Select Prompt Template" }) : "Select Prompt Template")}</h2> <button class="text-gray-400 hover:text-gray-500" aria-label="Close modal"><svg class="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg></button></div> <div class="mt-4"><input type="text"${attr("value", searchQuery)}${attr("placeholder", store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("promptTemplates.search", { default: "Search templates..." }) : "Search templates...")} class="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"/></div></div> <div class="flex border-b border-gray-200 px-6"><button${attr_class(`px-4 py-3 text-sm font-medium border-b-2 ${stringify(store_get($$store_subs ??= {}, "$currentTab", currentTab) === "my" ? "border-blue-500 text-blue-600" : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300")}`)}>${escape_html(store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("promptTemplates.myTemplates", { default: "My Templates" }) : "My Templates")} <span class="ml-2 text-xs">(${escape_html(filteredUserTemplates.length)})</span></button> <button${attr_class(`px-4 py-3 text-sm font-medium border-b-2 ${stringify(store_get($$store_subs ??= {}, "$currentTab", currentTab) === "shared" ? "border-blue-500 text-blue-600" : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300")}`)}>${escape_html(store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("promptTemplates.sharedTemplates", { default: "Shared Templates" }) : "Shared Templates")} <span class="ml-2 text-xs">(${escape_html(filteredSharedTemplates.length)})</span></button></div> <div class="flex-1 overflow-y-auto px-6 py-4">`);
      if (store_get($$store_subs ??= {}, "$currentLoading", currentLoading)) {
        $$renderer2.push("<!--[-->");
        $$renderer2.push(`<div class="text-center py-8 text-gray-500">${escape_html(store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("common.loading", { default: "Loading..." }) : "Loading...")}</div>`);
      } else {
        $$renderer2.push("<!--[!-->");
        if (store_get($$store_subs ??= {}, "$currentTab", currentTab) === "my") {
          $$renderer2.push("<!--[-->");
          if (filteredUserTemplates.length === 0) {
            $$renderer2.push("<!--[-->");
            $$renderer2.push(`<div class="text-center py-8 text-gray-500">${escape_html(store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("promptTemplates.noTemplates", { default: "No templates yet" }) : "No templates yet")}</div>`);
          } else {
            $$renderer2.push("<!--[!-->");
            $$renderer2.push(`<div class="space-y-2"><!--[-->`);
            const each_array = ensure_array_like(filteredUserTemplates);
            for (let $$index = 0, $$length = each_array.length; $$index < $$length; $$index++) {
              let template = each_array[$$index];
              $$renderer2.push(`<button${attr("data-template-id", template.id)}${attr_class(`w-full text-left px-4 py-3 rounded-lg border-2 transition-colors ${stringify(selectedTemplate?.id === template.id ? "border-blue-500 bg-blue-50" : "border-gray-200 hover:border-gray-300 hover:bg-gray-50")}`)}><div class="flex items-start justify-between"><div class="flex-1"><h3 class="font-medium text-gray-900">${escape_html(template.name)}</h3> `);
              if (template.description) {
                $$renderer2.push("<!--[-->");
                $$renderer2.push(`<p class="mt-1 text-sm text-gray-600">${escape_html(template.description)}</p>`);
              } else {
                $$renderer2.push("<!--[!-->");
              }
              $$renderer2.push(`<!--]--> <div class="mt-2 flex items-center space-x-2 text-xs text-gray-500">`);
              if (template.is_shared) {
                $$renderer2.push("<!--[-->");
                $$renderer2.push(`<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">Shared</span>`);
              } else {
                $$renderer2.push("<!--[!-->");
              }
              $$renderer2.push(`<!--]--> <span>Updated: ${escape_html(new Date(template.updated_at * 1e3).toLocaleDateString())}</span></div></div> `);
              if (selectedTemplate?.id === template.id) {
                $$renderer2.push("<!--[-->");
                $$renderer2.push(`<svg class="h-5 w-5 text-blue-500 flex-shrink-0 ml-2" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"></path></svg>`);
              } else {
                $$renderer2.push("<!--[!-->");
              }
              $$renderer2.push(`<!--]--></div></button>`);
            }
            $$renderer2.push(`<!--]--></div>`);
          }
          $$renderer2.push(`<!--]-->`);
        } else {
          $$renderer2.push("<!--[!-->");
          if (filteredSharedTemplates.length === 0) {
            $$renderer2.push("<!--[-->");
            $$renderer2.push(`<div class="text-center py-8 text-gray-500">${escape_html(store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("promptTemplates.noShared", { default: "No shared templates available" }) : "No shared templates available")}</div>`);
          } else {
            $$renderer2.push("<!--[!-->");
            $$renderer2.push(`<div class="space-y-2"><!--[-->`);
            const each_array_1 = ensure_array_like(filteredSharedTemplates);
            for (let $$index_1 = 0, $$length = each_array_1.length; $$index_1 < $$length; $$index_1++) {
              let template = each_array_1[$$index_1];
              $$renderer2.push(`<button${attr("data-template-id", template.id)}${attr_class(`w-full text-left px-4 py-3 rounded-lg border-2 transition-colors ${stringify(selectedTemplate?.id === template.id ? "border-blue-500 bg-blue-50" : "border-gray-200 hover:border-gray-300 hover:bg-gray-50")}`)}><div class="flex items-start justify-between"><div class="flex-1"><h3 class="font-medium text-gray-900">${escape_html(template.name)}</h3> `);
              if (template.description) {
                $$renderer2.push("<!--[-->");
                $$renderer2.push(`<p class="mt-1 text-sm text-gray-600">${escape_html(template.description)}</p>`);
              } else {
                $$renderer2.push("<!--[!-->");
              }
              $$renderer2.push(`<!--]--> <div class="mt-2 flex items-center space-x-2 text-xs text-gray-500">`);
              if (template.owner_name) {
                $$renderer2.push("<!--[-->");
                $$renderer2.push(`<span>By: ${escape_html(template.owner_name)}</span>`);
              } else {
                $$renderer2.push("<!--[!-->");
              }
              $$renderer2.push(`<!--]--> <span>Updated: ${escape_html(new Date(template.updated_at * 1e3).toLocaleDateString())}</span></div></div> `);
              if (selectedTemplate?.id === template.id) {
                $$renderer2.push("<!--[-->");
                $$renderer2.push(`<svg class="h-5 w-5 text-blue-500 flex-shrink-0 ml-2" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"></path></svg>`);
              } else {
                $$renderer2.push("<!--[!-->");
              }
              $$renderer2.push(`<!--]--></div></button>`);
            }
            $$renderer2.push(`<!--]--></div>`);
          }
          $$renderer2.push(`<!--]-->`);
        }
        $$renderer2.push(`<!--]-->`);
      }
      $$renderer2.push(`<!--]--></div> <div class="px-6 py-4 border-t border-gray-200 flex justify-end space-x-3"><button class="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-200 hover:bg-gray-300 rounded-md">${escape_html(store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("common.cancel", { default: "Cancel" }) : "Cancel")}</button> <button${attr("disabled", !selectedTemplate, true)} class="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed rounded-md">${escape_html(store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("promptTemplates.applyTemplate", { default: "Apply Template" }) : "Apply Template")}</button></div></div></div>`);
    } else {
      $$renderer2.push("<!--[!-->");
    }
    $$renderer2.push(`<!--]-->`);
    if ($$store_subs) unsubscribe_stores($$store_subs);
  });
}
function AssistantForm($$renderer, $$props) {
  $$renderer.component(($$renderer2) => {
    var $$store_subs;
    console.log("AssistantForm.svelte: Initializing script...");
    let {
      assistant = null,
      startInEdit = false
      // Add the new prop
    } = $$props;
    console.log(`[AssistantForm] Received props: assistant=${!!assistant}, startInEdit=${startInEdit}`);
    let initialMode = assistant ? "edit" : "create";
    console.log(`[AssistantForm] Calculated initialMode: ${initialMode}`);
    let formState = initialMode;
    let name = "";
    let sanitizedNameInfo = sanitizeName(name);
    formState === "create" && sanitizedNameInfo.wasModified;
    let selectedLlm = "";
    let currentModelsMetadata = [];
    let currentModelMetadata = currentModelsMetadata.find((m) => m.id === selectedLlm) || null;
    currentModelMetadata?.forced_capabilities?.image_generation === true;
    $$renderer2.push(`<div class="p-4 md:p-6 border rounded-md shadow-sm bg-white"><div class="mb-6 pb-4 border-b border-gray-200"><div class="flex justify-between items-center"><h2 class="text-2xl font-semibold text-brand">`);
    if (formState === "create") {
      $$renderer2.push("<!--[-->");
      $$renderer2.push(`${escape_html(store_get($$store_subs ??= {}, "$_", $format)("assistants.form.titleCreate", { default: "Create New Assistant" }))}`);
    } else {
      $$renderer2.push("<!--[!-->");
      $$renderer2.push(`${escape_html(store_get($$store_subs ??= {}, "$_", $format)("assistants.form.titleViewEdit", { default: "Assistant Details" }))} `);
      {
        $$renderer2.push("<!--[!-->");
      }
      $$renderer2.push(`<!--]-->`);
    }
    $$renderer2.push(`<!--]--></h2> `);
    if (formState === "create") {
      $$renderer2.push("<!--[-->");
      $$renderer2.push(`<div><button type="button" class="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand"><svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M9 19l3 3m0 0l3-3m-3 3V10"></path></svg> ${escape_html(store_get($$store_subs ??= {}, "$_", $format)("assistants.form.import.button", { default: "Import from JSON" }))}</button></div>`);
    } else {
      $$renderer2.push("<!--[!-->");
    }
    $$renderer2.push(`<!--]--></div> `);
    {
      $$renderer2.push("<!--[!-->");
    }
    $$renderer2.push(`<!--]--></div> `);
    if (store_get($$store_subs ??= {}, "$assistantConfigStore", assistantConfigStore).loading && true) {
      $$renderer2.push("<!--[-->");
      $$renderer2.push(`<p class="text-center text-gray-600 py-10">${escape_html(store_get($$store_subs ??= {}, "$_", $format)("assistants.loadingConfig", { default: "Loading configuration..." }))}</p>`);
    } else {
      $$renderer2.push("<!--[!-->");
      if (store_get($$store_subs ??= {}, "$assistantConfigStore", assistantConfigStore).error) {
        $$renderer2.push("<!--[-->");
        $$renderer2.push(`<p class="text-center text-red-600 py-10">${escape_html(store_get($$store_subs ??= {}, "$_", $format)("assistants.errorConfig", { default: "Error loading configuration:" }))} ${escape_html(store_get($$store_subs ??= {}, "$assistantConfigStore", assistantConfigStore).error)}</p>`);
      } else {
        $$renderer2.push("<!--[!-->");
        {
          $$renderer2.push("<!--[-->");
          $$renderer2.push(`<p class="text-center text-gray-600 py-10">${escape_html(store_get($$store_subs ??= {}, "$_", $format)("assistants.initializingForm", { default: "Initializing form..." }))}</p>`);
        }
        $$renderer2.push(`<!--]-->`);
      }
      $$renderer2.push(`<!--]-->`);
    }
    $$renderer2.push(`<!--]--> <input type="file" id="import-assistant-json" accept=".json" style="display: none;"/> `);
    TemplateSelectModal($$renderer2);
    $$renderer2.push(`<!----></div>`);
    if ($$store_subs) unsubscribe_stores($$store_subs);
  });
}
function PromptTemplatesContent($$renderer, $$props) {
  $$renderer.component(($$renderer2) => {
    var $$store_subs;
    let showDeleteModal = false;
    let templateToDelete = null;
    let isDeleting = false;
    let displayTemplates = [];
    let searchTerm = "";
    let sortBy = "updated_at";
    let sortOrder = "desc";
    let totalItems = 0;
    function handleCancelDeleteModal() {
      showDeleteModal = false;
      templateToDelete = null;
    }
    async function handleDeleteConfirm() {
      if (templateToDelete) {
        isDeleting = true;
        try {
          await deleteTemplate(templateToDelete.id);
          showDeleteModal = false;
          templateToDelete = null;
        } catch (error) {
        } finally {
          isDeleting = false;
        }
      }
    }
    let $$settled = true;
    let $$inner_renderer;
    function $$render_inner($$renderer3) {
      $$renderer3.push(`<div class="w-full">`);
      {
        $$renderer3.push("<!--[-->");
        if (store_get($$store_subs ??= {}, "$templateError", templateError)) {
          $$renderer3.push("<!--[-->");
          $$renderer3.push(`<div class="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded relative"><span class="block sm:inline">${escape_html(store_get($$store_subs ??= {}, "$templateError", templateError))}</span></div>`);
        } else {
          $$renderer3.push("<!--[!-->");
        }
        $$renderer3.push(`<!--]--> <div class="bg-white shadow rounded-lg"><div class="border-b border-gray-200"><div class="flex justify-between items-center px-6 py-4"><div class="flex space-x-4"><button${attr_class(`px-4 py-2 text-sm font-medium rounded-md ${stringify(store_get($$store_subs ??= {}, "$currentTab", currentTab) === "my" ? "bg-brand text-white" : "text-gray-600 hover:text-gray-900")}`)}>${escape_html(store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("promptTemplates.myTemplates", { default: "My Templates" }) : "My Templates")} `);
        if (store_get($$store_subs ??= {}, "$currentTab", currentTab) === "my") {
          $$renderer3.push("<!--[-->");
          $$renderer3.push(`<span class="ml-2 bg-white bg-opacity-30 text-white py-0.5 px-2 rounded-full text-xs">${escape_html(store_get($$store_subs ??= {}, "$currentTotal", currentTotal))}</span>`);
        } else {
          $$renderer3.push("<!--[!-->");
        }
        $$renderer3.push(`<!--]--></button> <button${attr_class(`px-4 py-2 text-sm font-medium rounded-md ${stringify(store_get($$store_subs ??= {}, "$currentTab", currentTab) === "shared" ? "bg-brand text-white" : "text-gray-600 hover:text-gray-900")}`)}>${escape_html(store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("promptTemplates.sharedTemplates", { default: "Shared Templates" }) : "Shared Templates")} `);
        if (store_get($$store_subs ??= {}, "$currentTab", currentTab) === "shared") {
          $$renderer3.push("<!--[-->");
          $$renderer3.push(`<span class="ml-2 bg-white bg-opacity-30 text-white py-0.5 px-2 rounded-full text-xs">${escape_html(store_get($$store_subs ??= {}, "$currentTotal", currentTotal))}</span>`);
        } else {
          $$renderer3.push("<!--[!-->");
        }
        $$renderer3.push(`<!--]--></button></div> <div class="flex space-x-2">`);
        if (store_get($$store_subs ??= {}, "$selectedTemplateIds", selectedTemplateIds).length > 0) {
          $$renderer3.push("<!--[-->");
          $$renderer3.push(`<button class="px-4 py-2 text-sm font-medium text-white bg-green-600 hover:bg-green-700 rounded-md">${escape_html(store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("promptTemplates.export", { default: "Export" }) : "Export")} (${escape_html(store_get($$store_subs ??= {}, "$selectedTemplateIds", selectedTemplateIds).length)})</button> <button class="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-200 hover:bg-gray-300 rounded-md">${escape_html(store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("common.clearSelection", { default: "Clear" }) : "Clear")}</button>`);
        } else {
          $$renderer3.push("<!--[!-->");
        }
        $$renderer3.push(`<!--]--> `);
        if (store_get($$store_subs ??= {}, "$currentTab", currentTab) === "my") {
          $$renderer3.push("<!--[-->");
          $$renderer3.push(`<button class="px-4 py-2 text-sm font-medium text-white bg-brand hover:bg-brand-hover rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand">+ ${escape_html(store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("promptTemplates.createNew", { default: "New Template" }) : "New Template")}</button>`);
        } else {
          $$renderer3.push("<!--[!-->");
        }
        $$renderer3.push(`<!--]--></div></div></div> `);
        if (store_get($$store_subs ??= {}, "$currentTab", currentTab) === "shared") {
          $$renderer3.push("<!--[-->");
          $$renderer3.push(`<div class="mx-6 mt-4 mb-4 p-3 bg-blue-50 border border-blue-200 rounded-md"><div class="flex"><div class="flex-shrink-0"><svg class="h-5 w-5 text-blue-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd"></path></svg></div> <div class="ml-3"><p class="text-sm text-blue-700">${escape_html(store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("promptTemplates.sharedTabInfo", {
            default: 'Note: Templates you own will not appear in this list, even if they are shared. Your own shared templates can be found in the "My Templates" tab.'
          }) : 'Note: Templates you own will not appear in this list, even if they are shared. Your own shared templates can be found in the "My Templates" tab.')}</p></div></div></div>`);
        } else {
          $$renderer3.push("<!--[!-->");
        }
        $$renderer3.push(`<!--]--> `);
        FilterBar($$renderer3, {
          searchPlaceholder: store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("promptTemplates.searchPlaceholder", { default: "Search templates..." }) : "Search templates...",
          searchValue: searchTerm,
          filters: [],
          filterValues: {},
          sortOptions: [
            {
              value: "name",
              label: store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("common.sortByName", { default: "Name" }) : "Name"
            },
            {
              value: "updated_at",
              label: store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("common.sortByUpdated", { default: "Last Modified" }) : "Last Modified"
            },
            {
              value: "created_at",
              label: store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("common.sortByCreated", { default: "Created Date" }) : "Created Date"
            }
          ],
          sortBy,
          sortOrder
        });
        $$renderer3.push(`<!----> <div class="flex justify-between items-center mb-4 px-6"><div class="text-sm text-gray-600">`);
        {
          $$renderer3.push("<!--[!-->");
          $$renderer3.push(`<span class="font-medium">${escape_html(totalItems)}</span> templates`);
        }
        $$renderer3.push(`<!--]--></div></div> <div class="divide-y divide-gray-200">`);
        if (store_get($$store_subs ??= {}, "$currentLoading", currentLoading)) {
          $$renderer3.push("<!--[-->");
          $$renderer3.push(`<div class="px-6 py-12 text-center text-gray-500">${escape_html(store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("common.loading", { default: "Loading..." }) : "Loading...")}</div>`);
        } else {
          $$renderer3.push("<!--[!-->");
          if (displayTemplates.length === 0) {
            $$renderer3.push("<!--[-->");
            if ((store_get($$store_subs ??= {}, "$currentTab", currentTab) === "my" ? store_get($$store_subs ??= {}, "$userTemplates", userTemplates).length : store_get($$store_subs ??= {}, "$sharedTemplates", sharedTemplates).length) === 0) {
              $$renderer3.push("<!--[-->");
              $$renderer3.push(`<div class="px-6 py-12 text-center"><p class="text-gray-500">${escape_html(store_get($$store_subs ??= {}, "$currentTab", currentTab) === "my" ? store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("promptTemplates.noTemplates", { default: "No templates yet. Create your first template!" }) : "No templates yet. Create your first template!" : store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("promptTemplates.noShared", { default: "No shared templates available" }) : "No shared templates available")}</p></div>`);
            } else {
              $$renderer3.push("<!--[!-->");
              $$renderer3.push(`<div class="px-6 py-12 text-center"><p class="text-gray-500 mb-4">No templates match your search</p> <button class="text-brand hover:text-brand-hover hover:underline focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand rounded-md px-3 py-1">Clear search</button></div>`);
            }
            $$renderer3.push(`<!--]-->`);
          } else {
            $$renderer3.push("<!--[!-->");
            $$renderer3.push(`<!--[-->`);
            const each_array = ensure_array_like(displayTemplates);
            for (let $$index = 0, $$length = each_array.length; $$index < $$length; $$index++) {
              let template = each_array[$$index];
              $$renderer3.push(`<div class="px-6 py-4 hover:bg-gray-50"><div class="flex items-start justify-between"><div class="flex items-start space-x-3 flex-1"><input type="checkbox"${attr("checked", store_get($$store_subs ??= {}, "$selectedTemplateIds", selectedTemplateIds).includes(template.id), true)}${attr("data-template-id", template.id)} class="mt-1 h-4 w-4 text-brand rounded"/> <button${attr("data-template-id", template.id)} class="flex-1 text-left hover:bg-gray-50 rounded p-2 -m-2"><h3 class="text-lg font-medium text-gray-900 hover:text-brand-hover">${escape_html(template.name)}</h3> `);
              if (template.description) {
                $$renderer3.push("<!--[-->");
                $$renderer3.push(`<p class="mt-1 text-sm text-gray-600">${escape_html(template.description)}</p>`);
              } else {
                $$renderer3.push("<!--[!-->");
              }
              $$renderer3.push(`<!--]--> <div class="mt-2 flex items-center space-x-4 text-xs text-gray-500">`);
              if (template.owner_name) {
                $$renderer3.push("<!--[-->");
                $$renderer3.push(`<span>By: ${escape_html(template.owner_name)}</span>`);
              } else {
                $$renderer3.push("<!--[!-->");
              }
              $$renderer3.push(`<!--]--> `);
              if (template.is_shared) {
                $$renderer3.push("<!--[-->");
                $$renderer3.push(`<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">Shared</span>`);
              } else {
                $$renderer3.push("<!--[!-->");
              }
              $$renderer3.push(`<!--]--> <span>Updated: ${escape_html(new Date(template.updated_at * 1e3).toLocaleDateString())}</span></div></button></div> <div class="flex space-x-2 ml-4">`);
              if (template.is_owner) {
                $$renderer3.push("<!--[-->");
                $$renderer3.push(`<button${attr("data-template-id", template.id)} class="px-3 py-1 text-sm text-brand hover:text-brand-hover">${escape_html(store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("common.edit", { default: "Edit" }) : "Edit")}</button> <button${attr("data-template-id", template.id)} class="px-3 py-1 text-sm text-gray-600 hover:text-gray-700">${escape_html(template.is_shared ? "Unshare" : "Share")}</button> <button${attr("data-template-id", template.id)} class="px-3 py-1 text-sm text-red-600 hover:text-red-700">${escape_html(store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("common.delete", { default: "Delete" }) : "Delete")}</button>`);
              } else {
                $$renderer3.push("<!--[!-->");
              }
              $$renderer3.push(`<!--]--> <button${attr("data-template-id", template.id)} class="px-3 py-1 text-sm text-gray-600 hover:text-gray-700">${escape_html(store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("common.duplicate", { default: "Duplicate" }) : "Duplicate")}</button></div></div></div>`);
            }
            $$renderer3.push(`<!--]-->`);
          }
          $$renderer3.push(`<!--]-->`);
        }
        $$renderer3.push(`<!--]--></div> `);
        {
          $$renderer3.push("<!--[!-->");
        }
        $$renderer3.push(`<!--]--></div>`);
      }
      $$renderer3.push(`<!--]--> `);
      ConfirmationModal($$renderer3, {
        title: store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("promptTemplates.confirmDelete", { default: "Delete Template?" }) : "Delete Template?",
        message: store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("promptTemplates.deleteWarning", {
          default: "This action cannot be undone. The template will be permanently deleted."
        }) : "This action cannot be undone. The template will be permanently deleted.",
        confirmText: store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("common.delete", { default: "Delete" }) : "Delete",
        cancelText: store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("common.cancel", { default: "Cancel" }) : "Cancel",
        variant: "danger",
        onconfirm: handleDeleteConfirm,
        oncancel: handleCancelDeleteModal,
        get isOpen() {
          return showDeleteModal;
        },
        set isOpen($$value) {
          showDeleteModal = $$value;
          $$settled = false;
        },
        get isLoading() {
          return isDeleting;
        },
        set isLoading($$value) {
          isDeleting = $$value;
          $$settled = false;
        }
      });
      $$renderer3.push(`<!----> `);
      {
        $$renderer3.push("<!--[!-->");
      }
      $$renderer3.push(`<!--]--></div>`);
    }
    do {
      $$settled = true;
      $$inner_renderer = $$renderer2.copy();
      $$render_inner($$inner_renderer);
    } while (!$$settled);
    $$renderer2.subsume($$inner_renderer);
    if ($$store_subs) unsubscribe_stores($$store_subs);
  });
}
function _page($$renderer, $$props) {
  $$renderer.component(($$renderer2) => {
    var $$store_subs;
    let currentView = "list";
    let selectedAssistantData = null;
    let loadingDetail = false;
    let detailSubView = store_get($$store_subs ??= {}, "$page", page).url.searchParams.get("startInEdit") === "true" ? "edit" : "properties";
    let isDeleteModalOpen = false;
    let assistantToDeleteId = null;
    let assistantToDeleteName = null;
    let isDeletingAssistant = false;
    let isOwner = /* @__PURE__ */ (() => {
      return false;
    })();
    let accessLevel = /* @__PURE__ */ (() => {
      return null;
    })();
    let canManageSharing = /* @__PURE__ */ (() => {
      return isOwner || accessLevel === "read_only";
    })();
    let canViewAnalytics = /* @__PURE__ */ (() => {
      return isOwner || accessLevel === "read_only";
    })();
    (() => {
      if (isOwner) return true;
      return store_get($$store_subs ??= {}, "$user", user).data?.role === "admin";
    })();
    function showList() {
      console.log("Navigating back to list view (assistants base path)");
      currentView = "list";
      goto(`${base}/assistants`, {});
    }
    onDestroy(() => {
      console.log("Assistants page unmounting");
    });
    async function handleDeleteConfirm() {
      console.log("[Delete Modal] handleDeleteConfirm called");
      if (!assistantToDeleteId) {
        console.log("[Delete Modal] No assistantToDeleteId, aborting delete");
        return;
      }
      isDeletingAssistant = true;
      try {
        console.log(`[Delete Modal] Attempting to delete assistant ID: ${assistantToDeleteId}`);
        await deleteAssistant(assistantToDeleteId);
        console.log(`[Delete Modal] Assistant ${assistantToDeleteId} deleted successfully.`);
        isDeleteModalOpen = false;
        const deletedId = assistantToDeleteId;
        assistantToDeleteId = null;
        assistantToDeleteName = null;
        if (currentView === "detail" && selectedAssistantData?.id === deletedId.toString()) {
          console.log("[Delete Modal] Deleted from detail view, navigating to list");
          showList();
        } else {
          console.log("[Delete Modal] Deleted from list view, navigating to list");
          showList();
        }
      } catch (error) {
        console.error(`[Delete Modal] Error deleting assistant ${assistantToDeleteId}:`, error);
        error instanceof Error ? error.message : store_get($$store_subs ??= {}, "$_", $format)("assistants.deleteModal.deleteError", { default: "Failed to delete assistant." });
      } finally {
        isDeletingAssistant = false;
        console.log("[Delete Modal] handleDeleteConfirm finished");
      }
    }
    let $$settled = true;
    let $$inner_renderer;
    function $$render_inner($$renderer3) {
      $$renderer3.push(`<h1 class="text-3xl font-bold mb-4 text-brand">${escape_html("Learning Assistants")}</h1> <div class="mb-6 border-b border-gray-200"><nav class="-mb-px flex space-x-4" aria-label="Tabs"><button${attr_class(`whitespace-nowrap py-2.5 px-4 font-medium text-sm rounded-lg transition-all duration-150 inline-flex items-center gap-1.5 ${stringify(currentView === "create" ? "bg-brand text-white shadow-md" : "bg-emerald-600 text-white hover:bg-emerald-700 shadow-sm hover:shadow-md")}`)}${attr_style(currentView === "create" ? "background-color: #2271b3;" : "")}><svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15"></path></svg> ${escape_html("Create Assistant")}</button> <div class="h-6 w-px bg-gray-300 mx-1"></div> <button${attr_class(`whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm rounded-t-md transition-colors duration-150 ${stringify(currentView === "list" ? "bg-brand text-white border-brand" : "border-transparent text-gray-800 hover:text-gray-900 hover:border-gray-400")}`)}${attr_style(currentView === "list" ? "background-color: #2271b3; color: white; border-color: #2271b3;" : "")}>${escape_html("My Assistants")}</button> <button${attr_class(`whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm rounded-t-md transition-colors duration-150 ${stringify(currentView === "shared" ? "bg-brand text-white border-brand" : "border-transparent text-gray-800 hover:text-gray-900 hover:border-gray-400")}`)}${attr_style(currentView === "shared" ? "background-color: #2271b3; color: white; border-color: #2271b3;" : "")}>${escape_html("Shared with Me")}</button> <button${attr_class(`whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm rounded-t-md transition-colors duration-150 ${stringify(currentView === "templates" ? "bg-brand text-white border-brand" : "border-transparent text-gray-800 hover:text-gray-900 hover:border-gray-400")}`)}${attr_style(currentView === "templates" ? "background-color: #2271b3; color: white; border-color: #2271b3;" : "")}>${escape_html("Prompt Templates")}</button> `);
      if (store_get($$store_subs ??= {}, "$user", user).owiUrl) {
        $$renderer3.push("<!--[-->");
        $$renderer3.push(`<a${attr("href", store_get($$store_subs ??= {}, "$user", user).owiUrl)} target="_blank" rel="noopener noreferrer" class="whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm rounded-t-md transition-colors duration-150 border-transparent text-gray-800 hover:text-gray-900 hover:border-gray-400 inline-flex items-center gap-1">${escape_html("OpenWebUI")} <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path></svg></a>`);
      } else {
        $$renderer3.push("<!--[!-->");
      }
      $$renderer3.push(`<!--]--> `);
      if (currentView === "detail" && loadingDetail) {
        $$renderer3.push("<!--[-->");
        $$renderer3.push(`<div class="relative"><button class="whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm rounded-t-md bg-brand text-white border-brand cursor-default" style="background-color: #2271b3; color: white; border-color: #2271b3;" disabled>${escape_html("Assistant Detail")} `);
        {
          $$renderer3.push("<!--[!-->");
        }
        $$renderer3.push(`<!--]--></button></div>`);
      } else {
        $$renderer3.push("<!--[!-->");
      }
      $$renderer3.push(`<!--]--></nav></div> `);
      if (currentView === "list") {
        $$renderer3.push("<!--[-->");
        $$renderer3.push(`<div class="mt-6"><div class="bg-white shadow rounded-lg p-4 border border-gray-200">`);
        AssistantsList($$renderer3, {});
        $$renderer3.push(`<!----></div></div>`);
      } else {
        $$renderer3.push("<!--[!-->");
        if (currentView === "create") {
          $$renderer3.push("<!--[-->");
          AssistantForm($$renderer3, { assistant: null });
        } else {
          $$renderer3.push("<!--[!-->");
          if (currentView === "detail") {
            $$renderer3.push("<!--[-->");
            $$renderer3.push(`<div class="mb-4 border-b border-gray-300 flex space-x-4"><button${attr_class(`py-2 px-4 text-sm font-medium rounded-t-md ${stringify(detailSubView === "properties" ? "bg-gray-100 border border-b-0 border-gray-300 text-brand" : "text-gray-600 hover:text-gray-800")}`)}>${escape_html("Properties")}</button> `);
            if (isOwner) {
              $$renderer3.push("<!--[-->");
              $$renderer3.push(`<button${attr_class(`py-2 px-4 text-sm font-medium rounded-t-md ${stringify(detailSubView === "edit" ? "bg-gray-100 border border-b-0 border-gray-300 text-brand" : "text-gray-600 hover:text-gray-800")}`)}>${escape_html("Edit")}</button>`);
            } else {
              $$renderer3.push("<!--[!-->");
            }
            $$renderer3.push(`<!--]--> `);
            if (isOwner || canManageSharing) {
              $$renderer3.push("<!--[-->");
              $$renderer3.push(`<button${attr_class(`py-2 px-4 text-sm font-medium rounded-t-md ${stringify(detailSubView === "share" ? "bg-gray-100 border border-b-0 border-gray-300 text-brand" : "text-gray-600 hover:text-gray-800")}`)}>${escape_html("Share")}</button>`);
            } else {
              $$renderer3.push("<!--[!-->");
            }
            $$renderer3.push(`<!--]--> <button${attr_class(`py-2 px-4 text-sm font-medium rounded-t-md ${stringify(detailSubView === "chat" ? "bg-gray-100 border border-b-0 border-gray-300 text-brand" : "text-gray-600 hover:text-gray-800")}`)}>${escape_html("Chat")} `);
            {
              $$renderer3.push("<!--[!-->");
            }
            $$renderer3.push(`<!--]--></button> `);
            if (canViewAnalytics) {
              $$renderer3.push("<!--[-->");
              $$renderer3.push(`<button${attr_class(`py-2 px-4 text-sm font-medium rounded-t-md ${stringify(detailSubView === "analytics" ? "bg-gray-100 border border-b-0 border-gray-300 text-brand" : "text-gray-600 hover:text-gray-800")}`)}>${escape_html("Activity")}</button>`);
            } else {
              $$renderer3.push("<!--[!-->");
            }
            $$renderer3.push(`<!--]--></div> <div class="bg-white shadow rounded-lg border border-gray-200">`);
            {
              $$renderer3.push("<!--[!-->");
              {
                $$renderer3.push("<!--[!-->");
                {
                  $$renderer3.push("<!--[!-->");
                }
                $$renderer3.push(`<!--]-->`);
              }
              $$renderer3.push(`<!--]-->`);
            }
            $$renderer3.push(`<!--]--></div>`);
          } else {
            $$renderer3.push("<!--[!-->");
            if (currentView === "shared") {
              $$renderer3.push("<!--[-->");
              $$renderer3.push(`<div class="mt-6"><div class="bg-white shadow rounded-lg p-4 border border-gray-200">`);
              AssistantsList($$renderer3, { showShared: true });
              $$renderer3.push(`<!----></div></div>`);
            } else {
              $$renderer3.push("<!--[!-->");
              if (currentView === "templates") {
                $$renderer3.push("<!--[-->");
                $$renderer3.push(`<div class="mt-6">`);
                PromptTemplatesContent($$renderer3);
                $$renderer3.push(`<!----></div>`);
              } else {
                $$renderer3.push("<!--[!-->");
                $$renderer3.push(`<p>${escape_html("Assistant data not available.")}</p>`);
              }
              $$renderer3.push(`<!--]-->`);
            }
            $$renderer3.push(`<!--]-->`);
          }
          $$renderer3.push(`<!--]-->`);
        }
        $$renderer3.push(`<!--]-->`);
      }
      $$renderer3.push(`<!--]--> `);
      ConfirmationModal($$renderer3, {
        title: "Delete Assistant",
        message: `Are you sure you want to delete the assistant "${assistantToDeleteName}"? This action cannot be undone.`,
        confirmText: "Delete",
        variant: "danger",
        onconfirm: handleDeleteConfirm,
        oncancel: () => {
          isDeleteModalOpen = false;
          assistantToDeleteId = null;
          assistantToDeleteName = null;
        },
        get isOpen() {
          return isDeleteModalOpen;
        },
        set isOpen($$value) {
          isDeleteModalOpen = $$value;
          $$settled = false;
        },
        get isLoading() {
          return isDeletingAssistant;
        },
        set isLoading($$value) {
          isDeletingAssistant = $$value;
          $$settled = false;
        }
      });
      $$renderer3.push(`<!----> `);
      {
        $$renderer3.push("<!--[!-->");
      }
      $$renderer3.push(`<!--]-->`);
    }
    do {
      $$settled = true;
      $$inner_renderer = $$renderer2.copy();
      $$render_inner($$inner_renderer);
    } while (!$$settled);
    $$renderer2.subsume($$inner_renderer);
    if ($$store_subs) unsubscribe_stores($$store_subs);
  });
}
export {
  _page as default
};
