import { d as bind_props, c as store_get, b as attr, a as attr_class, s as stringify, u as unsubscribe_stores } from "../../../chunks/index2.js";
import "../../../chunks/i18n.js";
import "../../../chunks/userStore.js";
import "@sveltejs/kit/internal/server";
import { s as sanitizeName } from "../../../chunks/nameSanitizer.js";
import { a as $format } from "../../../chunks/runtime.js";
import { e as escape_html } from "../../../chunks/context.js";
import { C as ConfirmationModal } from "../../../chunks/ConfirmationModal.js";
import { p as processListData } from "../../../chunks/listHelpers.js";
import "@sveltejs/kit/internal";
import "../../../chunks/exports.js";
import "../../../chunks/utils.js";
import "clsx";
import "../../../chunks/state.svelte.js";
async function deleteKnowledgeBase(kbId) {
  throw new Error("Knowledge base operations are only available in the browser.");
}
function CreateKnowledgeBaseModal($$renderer, $$props) {
  $$renderer.component(($$renderer2) => {
    var $$store_subs;
    let isOpen = false;
    let isSubmitting = false;
    let error = "";
    let name = "";
    let description = "";
    let sanitizedNameInfo = sanitizeName(name);
    let showSanitizationPreview = sanitizedNameInfo.wasModified && name.trim() !== "";
    let nameError = "";
    function open() {
      isOpen = true;
      resetForm();
    }
    function resetForm() {
      name = "";
      description = "";
      error = "";
      nameError = "";
      isSubmitting = false;
    }
    if (isOpen) {
      $$renderer2.push("<!--[-->");
      $$renderer2.push(`<div class="fixed inset-0 z-40 overflow-y-auto"><div class="fixed inset-0 bg-black bg-opacity-50 transition-opacity" aria-hidden="true"></div> <div class="flex min-h-screen items-center justify-center p-4"><div class="relative bg-white rounded-lg shadow-xl max-w-lg w-full mx-auto p-6" tabindex="-1" role="dialog" aria-modal="true" aria-labelledby="modal-title"><div class="mb-4"><h3 id="modal-title" class="text-lg font-medium text-gray-900">${escape_html(store_get($$store_subs ??= {}, "$_", $format)("knowledgeBases.createPageTitle", { default: "Create Knowledge Base" }))}</h3> <p class="text-sm text-gray-500 mt-1">${escape_html(store_get($$store_subs ??= {}, "$_", $format)("knowledgeBases.createModal.description", {
        default: "Create a new knowledge base to store and retrieve documents."
      }))}</p></div> `);
      if (error) {
        $$renderer2.push("<!--[-->");
        $$renderer2.push(`<div class="mb-4 p-2 bg-red-50 text-red-500 text-sm rounded">${escape_html(error)}</div>`);
      } else {
        $$renderer2.push("<!--[!-->");
      }
      $$renderer2.push(`<!--]--> <form class="space-y-4"><div><label for="kb-name" class="block text-sm font-medium text-gray-700">${escape_html(store_get($$store_subs ??= {}, "$_", $format)("knowledgeBases.name", { default: "Name" }))} *</label> <input type="text" id="kb-name"${attr("value", name)}${attr_class(`mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-[#2271b3] focus:border-[#2271b3] sm:text-sm ${stringify(nameError ? "border-red-300 focus:ring-red-500 focus:border-red-500" : "")}`)}${attr("placeholder", store_get($$store_subs ??= {}, "$_", $format)("knowledgeBases.namePlaceholder", { default: "Enter knowledge base name" }))}/> `);
      if (showSanitizationPreview) {
        $$renderer2.push("<!--[-->");
        $$renderer2.push(`<div class="mt-2 p-2 bg-blue-50 border border-blue-200 rounded-md"><p class="text-sm text-blue-800"><span class="font-semibold">${escape_html(store_get($$store_subs ??= {}, "$_", $format)("knowledgeBases.createModal.willBeSaved", { default: "Will be saved as:" }))}</span> <code class="ml-2 px-2 py-1 bg-blue-100 rounded text-blue-900 font-mono">${escape_html(sanitizedNameInfo.sanitized)}</code></p></div>`);
      } else {
        $$renderer2.push("<!--[!-->");
        if (!name.trim()) {
          $$renderer2.push("<!--[-->");
          $$renderer2.push(`<p class="mt-1 text-xs text-gray-500">${escape_html(store_get($$store_subs ??= {}, "$_", $format)("knowledgeBases.createModal.nameHint", {
            default: "Special characters and spaces will be converted to underscores"
          }))}</p>`);
        } else {
          $$renderer2.push("<!--[!-->");
        }
        $$renderer2.push(`<!--]-->`);
      }
      $$renderer2.push(`<!--]--> `);
      if (nameError) {
        $$renderer2.push("<!--[-->");
        $$renderer2.push(`<p class="mt-1 text-sm text-red-600">${escape_html(nameError)}</p>`);
      } else {
        $$renderer2.push("<!--[!-->");
      }
      $$renderer2.push(`<!--]--></div> <div><label for="kb-description" class="block text-sm font-medium text-gray-700">${escape_html(store_get($$store_subs ??= {}, "$_", $format)("knowledgeBases.description", { default: "Description" }))}</label> <textarea id="kb-description" rows="3" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-[#2271b3] focus:border-[#2271b3] sm:text-sm"${attr("placeholder", store_get($$store_subs ??= {}, "$_", $format)("knowledgeBases.descriptionPlaceholder", { default: "Enter a description for this knowledge base" }))}>`);
      const $$body = escape_html(description);
      if ($$body) {
        $$renderer2.push(`${$$body}`);
      }
      $$renderer2.push(`</textarea></div> `);
      if (showSanitizationPreview) {
        $$renderer2.push("<!--[-->");
        $$renderer2.push(`<div class="mt-4 p-3 bg-blue-50 border border-blue-200 rounded-md"><div class="flex items-center"><svg class="w-5 h-5 text-blue-600 mr-2 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg> <div class="flex-1"><p class="text-sm font-semibold text-blue-800">${escape_html(store_get($$store_subs ??= {}, "$_", $format)("knowledgeBases.createModal.willBeSaved", { default: "Will be saved as:" }))}</p> <code class="inline-block mt-1 px-3 py-1 bg-blue-100 rounded text-blue-900 font-mono text-sm">${escape_html(sanitizedNameInfo.sanitized)}</code></div></div></div>`);
      } else {
        $$renderer2.push("<!--[!-->");
      }
      $$renderer2.push(`<!--]--> <div class="mt-5 sm:mt-6 sm:grid sm:grid-cols-2 sm:gap-3 sm:grid-flow-row-dense"><button type="submit" class="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-brand text-base font-medium text-white hover:bg-brand-hover focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand sm:col-start-2 sm:text-sm"${attr("disabled", isSubmitting, true)}>`);
      if (isSubmitting) {
        $$renderer2.push("<!--[-->");
        $$renderer2.push(`${escape_html(store_get($$store_subs ??= {}, "$_", $format)("knowledgeBases.creating", { default: "Creating..." }))}`);
      } else {
        $$renderer2.push("<!--[!-->");
        $$renderer2.push(`${escape_html(store_get($$store_subs ??= {}, "$_", $format)("knowledgeBases.create", { default: "Create Knowledge Base" }))}`);
      }
      $$renderer2.push(`<!--]--></button> <button type="button" class="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-500 sm:mt-0 sm:col-start-1 sm:text-sm"${attr("disabled", isSubmitting, true)}>${escape_html(store_get($$store_subs ??= {}, "$_", $format)("knowledgeBases.cancel", { default: "Cancel" }))}</button></div></form></div></div></div>`);
    } else {
      $$renderer2.push("<!--[!-->");
    }
    $$renderer2.push(`<!--]-->`);
    if ($$store_subs) unsubscribe_stores($$store_subs);
    bind_props($$props, { open });
  });
}
function KnowledgeBasesList($$renderer, $$props) {
  $$renderer.component(($$renderer2) => {
    var $$store_subs;
    let allKnowledgeBases = [];
    let ownedKnowledgeBases = [];
    let sharedKnowledgeBases = [];
    let successMessage = "";
    let searchTerm = "";
    let sortBy = "created_at";
    let sortOrder = "desc";
    let currentPage = 1;
    let itemsPerPage = 10;
    let showDeleteModal = false;
    let deleteTarget = { id: null, name: "" };
    let isDeleting = false;
    function applyFiltersAndPagination() {
      const kbList = ownedKnowledgeBases;
      const result = processListData(kbList, {
        search: searchTerm,
        searchFields: ["name", "description", "id"],
        filters: {},
        sortBy,
        sortOrder,
        page: currentPage,
        itemsPerPage
      });
      result.items;
      result.filteredCount;
      result.totalPages;
      currentPage = result.currentPage;
    }
    async function handleDeleteConfirm() {
      if (!deleteTarget.id || isDeleting) return;
      isDeleting = true;
      try {
        await deleteKnowledgeBase(deleteTarget.id);
        allKnowledgeBases = allKnowledgeBases.filter((k) => k.id !== deleteTarget.id);
        ownedKnowledgeBases = ownedKnowledgeBases.filter((k) => k.id !== deleteTarget.id);
        sharedKnowledgeBases = sharedKnowledgeBases.filter((k) => k.id !== deleteTarget.id);
        applyFiltersAndPagination();
        showDeleteModal = false;
        deleteTarget = { id: null, name: "" };
        successMessage = store_get($$store_subs ??= {}, "$_", $format)("knowledgeBases.list.deleteSuccess", { default: "Knowledge base deleted." });
        setTimeout(
          () => {
            successMessage = "";
          },
          4e3
        );
      } catch (e) {
        console.error("Error deleting knowledge base:", e);
        e instanceof Error ? e.message : "Deletion failed";
        setTimeout(
          () => {
          },
          8e3
        );
      } finally {
        isDeleting = false;
      }
    }
    function handleDeleteCancel() {
      if (isDeleting) return;
      showDeleteModal = false;
      deleteTarget = { id: null, name: "" };
    }
    let $$settled = true;
    let $$inner_renderer;
    function $$render_inner($$renderer3) {
      $$renderer3.push(`<div class="bg-white shadow overflow-hidden sm:rounded-md"><div class="p-4 border-b border-gray-200 sm:flex sm:items-center sm:justify-between"><h3 class="text-lg leading-6 font-medium text-gray-900">${escape_html(store_get($$store_subs ??= {}, "$_", $format)("knowledgeBases.list.title", { default: "Knowledge Bases" }))}</h3> <div class="mt-3 sm:mt-0 sm:ml-4"><button class="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-brand hover:bg-brand-hover focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand">${escape_html(store_get($$store_subs ??= {}, "$_", $format)("knowledgeBases.list.createButton", { default: "Create Knowledge Base" }))}</button></div></div> `);
      if (successMessage) {
        $$renderer3.push("<!--[-->");
        $$renderer3.push(`<div class="p-4 bg-green-50 border-b border-green-100"><div class="text-sm text-green-700">${escape_html(successMessage)}</div></div>`);
      } else {
        $$renderer3.push("<!--[!-->");
      }
      $$renderer3.push(`<!--]--> `);
      {
        $$renderer3.push("<!--[-->");
        $$renderer3.push(`<div class="p-6 text-center"><div class="animate-pulse text-gray-500">${escape_html(store_get($$store_subs ??= {}, "$_", $format)("knowledgeBases.list.loading", { default: "Loading knowledge bases..." }))}</div></div>`);
      }
      $$renderer3.push(`<!--]--> `);
      CreateKnowledgeBaseModal($$renderer3, {});
      $$renderer3.push(`<!----></div> `);
      ConfirmationModal($$renderer3, {
        title: store_get($$store_subs ??= {}, "$_", $format)("knowledgeBases.deleteModal.title", { default: "Delete Knowledge Base" }),
        message: store_get($$store_subs ??= {}, "$_", $format)("knowledgeBases.deleteModal.confirmation", {
          values: { name: deleteTarget.name },
          default: `Are you sure you want to delete the knowledge base "${deleteTarget.name}" and all its data? This action cannot be undone.`
        }),
        confirmText: store_get($$store_subs ??= {}, "$_", $format)("knowledgeBases.deleteModal.confirmButton", { default: "Delete" }),
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
function _page($$renderer, $$props) {
  $$renderer.component(($$renderer2) => {
    var $$store_subs;
    $$renderer2.push(`<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6"><div class="pb-5 border-b border-gray-200">`);
    {
      $$renderer2.push("<!--[!-->");
      $$renderer2.push(`<h1 class="text-2xl font-bold leading-7 text-gray-900 sm:text-3xl sm:truncate">${escape_html(store_get($$store_subs ??= {}, "$_", $format)("knowledgeBases.pageTitle", { default: "Knowledge Bases" }))}</h1> <p class="mt-1 text-sm text-gray-500">${escape_html(store_get($$store_subs ??= {}, "$_", $format)("knowledgeBases.pageDescription", {
        default: "Manage your knowledge bases for use with learning assistants."
      }))}</p>`);
    }
    $$renderer2.push(`<!--]--></div> <div class="mt-6">`);
    {
      $$renderer2.push("<!--[!-->");
      KnowledgeBasesList($$renderer2);
    }
    $$renderer2.push(`<!--]--></div></div>`);
    if ($$store_subs) unsubscribe_stores($$store_subs);
  });
}
export {
  _page as default
};
