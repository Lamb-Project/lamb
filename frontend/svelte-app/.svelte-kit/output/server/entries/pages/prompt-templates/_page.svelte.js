import { c as store_get, a as attr_class, s as stringify, e as ensure_array_like, b as attr, u as unsubscribe_stores } from "../../../chunks/index2.js";
import "../../../chunks/i18n.js";
import { b as templateError, c as currentTab, d as currentTotal, e as selectedTemplateIds, F as FilterBar, a as currentLoading, u as userTemplates, s as sharedTemplates, f as deleteTemplate } from "../../../chunks/templateStore.js";
import { C as ConfirmationModal } from "../../../chunks/ConfirmationModal.js";
import { $ as $locale, a as $format } from "../../../chunks/runtime.js";
import { e as escape_html } from "../../../chunks/context.js";
function _page($$renderer, $$props) {
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
      $$renderer3.push(`<div class="min-h-screen bg-gray-50 py-8"><div class="w-full mx-auto">`);
      {
        $$renderer3.push("<!--[-->");
        $$renderer3.push(`<div class="mb-8 px-6"><h1 class="text-3xl font-bold text-gray-900">${escape_html(store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("promptTemplates.title", { default: "Prompt Templates" }) : "Prompt Templates")}</h1> <p class="mt-2 text-sm text-gray-600">${escape_html(store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("promptTemplates.description", {
          default: "Create and manage reusable prompt templates for your assistants"
        }) : "Create and manage reusable prompt templates for your assistants")}</p></div> `);
        if (store_get($$store_subs ??= {}, "$templateError", templateError)) {
          $$renderer3.push("<!--[-->");
          $$renderer3.push(`<div class="mb-4 mx-6 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded relative"><span class="block sm:inline">${escape_html(store_get($$store_subs ??= {}, "$templateError", templateError))}</span></div>`);
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
      $$renderer3.push(`<!--]--></div></div>`);
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
