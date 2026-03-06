import { c as store_get, a as attr_class, u as unsubscribe_stores, b as attr, h as head, f as attr_style, s as stringify } from "../../../chunks/index2.js";
import { o as onDestroy } from "../../../chunks/index-server.js";
import "@sveltejs/kit/internal";
import "../../../chunks/exports.js";
import "../../../chunks/utils.js";
import { e as escape_html } from "../../../chunks/context.js";
import "clsx";
import "@sveltejs/kit/internal/server";
import "../../../chunks/state.svelte.js";
import "../../../chunks/i18n.js";
import { $ as $locale, a as $format } from "../../../chunks/runtime.js";
function RubricsList($$renderer, $$props) {
  $$renderer.component(($$renderer2) => {
    var $$store_subs;
    let localeLoaded = !!store_get($$store_subs ??= {}, "$locale", $locale);
    $$renderer2.push(`<div class="container mx-auto px-4 py-8"><div class="border-b border-gray-200 mb-6"><nav class="-mb-px flex space-x-8" aria-label="Tabs"><button${attr_class(`py-2 px-1 border-b-2 font-medium text-sm ${"border-blue-500 text-blue-600"}`)}>${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("rubrics.tabs.myRubrics", { default: "My Rubrics" }) : "My Rubrics")}</button> <button${attr_class(`py-2 px-1 border-b-2 font-medium text-sm ${"border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"}`)}>${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("rubrics.tabs.templates", { default: "Templates" }) : "Templates")}</button></nav></div> `);
    {
      $$renderer2.push("<!--[!-->");
    }
    $$renderer2.push(`<!--]--> `);
    {
      $$renderer2.push("<!--[-->");
      $$renderer2.push(`<p class="text-center text-gray-500 py-4">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("rubrics.loading", { default: "Loading rubrics..." }) : "Loading rubrics...")}</p>`);
    }
    $$renderer2.push(`<!--]--></div>`);
    if ($$store_subs) unsubscribe_stores($$store_subs);
  });
}
function RubricAIGenerationModal($$renderer, $$props) {
  $$renderer.component(($$renderer2) => {
    var $$store_subs;
    let { show = false } = $$props;
    let localeLoaded = !!store_get($$store_subs ??= {}, "$locale", $locale);
    let userPrompt = "";
    let isGenerating = false;
    let currentLanguage = store_get($$store_subs ??= {}, "$locale", $locale) || "en";
    if (show) {
      $$renderer2.push("<!--[-->");
      $$renderer2.push(`<div class="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center z-50 p-4"><div class="bg-white rounded-lg shadow-xl w-full max-w-6xl max-h-[90vh] overflow-y-auto">`);
      {
        $$renderer2.push("<!--[-->");
        $$renderer2.push(`<div class="p-6"><div class="flex justify-between items-start mb-4"><div><h2 class="text-2xl font-bold text-gray-900">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("rubrics.ai.generateTitle", { default: "Generate Rubric with AI" }) : "Generate Rubric with AI")}</h2> <p class="mt-1 text-sm text-gray-600">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("rubrics.ai.generateDescription", {
          default: "Describe the rubric you want to create, and AI will generate it for you."
        }) : "Describe the rubric you want to create, and AI will generate it for you.")}</p></div> <button type="button" class="text-gray-400 hover:text-gray-600" aria-label="Close"><svg class="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg></button></div> <div class="mb-4"><label for="ai-prompt" class="block text-sm font-medium text-gray-700 mb-2">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("rubrics.ai.promptLabel", { default: "Describe your rubric" }) : "Describe your rubric")}</label> <textarea id="ai-prompt" rows="6" class="w-full border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 p-3"${attr("placeholder", localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("rubrics.ai.promptPlaceholder", {
          default: "e.g., Create a rubric for evaluating 5-paragraph argumentative essays for 9th grade English students"
        }) : "e.g., Create a rubric for evaluating 5-paragraph argumentative essays for 9th grade English students")}${attr("disabled", isGenerating, true)}>`);
        const $$body = escape_html(userPrompt);
        if ($$body) {
          $$renderer2.push(`${$$body}`);
        }
        $$renderer2.push(`</textarea> <p class="mt-1 text-xs text-gray-500">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("rubrics.ai.languageNote", { default: "Language" }) : "Language")}: <strong>${escape_html(currentLanguage.toUpperCase())}</strong></p></div> <div class="mb-4"><button type="button" class="text-sm text-blue-600 hover:text-blue-800 flex items-center"><svg class="h-4 w-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"${attr("d", "M9 5l7 7-7 7")}></path></svg> ${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("rubrics.ai.advancedOptions", { default: "Advanced Options" }) : "Advanced Options")}</button> `);
        {
          $$renderer2.push("<!--[!-->");
        }
        $$renderer2.push(`<!--]--></div> `);
        {
          $$renderer2.push("<!--[!-->");
        }
        $$renderer2.push(`<!--]--> <div class="flex justify-end space-x-3"><button type="button"${attr("disabled", isGenerating, true)} class="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("common.cancel", { default: "Cancel" }) : "Cancel")}</button> <button type="button"${attr("disabled", !userPrompt.trim(), true)} class="inline-flex items-center px-6 py-2 border border-transparent rounded-md text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50">`);
        {
          $$renderer2.push("<!--[!-->");
          $$renderer2.push(`⚡ ${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("rubrics.ai.generateButton", { default: "Generate with AI" }) : "Generate with AI")}`);
        }
        $$renderer2.push(`<!--]--></button></div></div>`);
      }
      $$renderer2.push(`<!--]--></div></div>`);
    } else {
      $$renderer2.push("<!--[!-->");
    }
    $$renderer2.push(`<!--]-->`);
    if ($$store_subs) unsubscribe_stores($$store_subs);
  });
}
function _page($$renderer, $$props) {
  $$renderer.component(($$renderer2) => {
    var $$store_subs;
    let localeLoaded = !!store_get($$store_subs ??= {}, "$locale", $locale);
    let showAIModal = false;
    onDestroy(() => {
    });
    head("k4p5jd", $$renderer2, ($$renderer3) => {
      $$renderer3.title(($$renderer4) => {
        $$renderer4.push(`<title>Evaluaitor - Educational Rubrics</title>`);
      });
    });
    $$renderer2.push(`<h1 class="text-3xl font-bold mb-4 text-brand">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("evaluaitor.title", { default: "Evaluaitor" }) : "Evaluaitor")}</h1> <div class="mb-6 border-b border-gray-200"><nav class="-mb-px flex space-x-8 items-center" aria-label="Tabs"><button${attr_class(`whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm rounded-t-md transition-colors duration-150 ${stringify(
      "bg-brand text-white border-brand"
    )}`)}${attr_style(
      "background-color: #2271b3; color: white; border-color: #2271b3;"
    )}>${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("evaluaitor.myRubricsTab", { default: "My Rubrics" }) : "My Rubrics")}</button> <button${attr_class(`whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm rounded-t-md ${stringify("border-transparent text-gray-800 hover:text-gray-900 hover:border-gray-400")}`)}${attr_style("")}>${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("evaluaitor.createRubricTab", { default: "Create Rubric" }) : "Create Rubric")}</button></nav></div> `);
    {
      $$renderer2.push("<!--[-->");
      $$renderer2.push(`<div class="mt-6"><div class="bg-white shadow rounded-lg p-4 border border-gray-200">`);
      RubricsList($$renderer2);
      $$renderer2.push(`<!----></div></div>`);
    }
    $$renderer2.push(`<!--]--> `);
    RubricAIGenerationModal($$renderer2, {
      show: showAIModal
    });
    $$renderer2.push(`<!---->`);
    if ($$store_subs) unsubscribe_stores($$store_subs);
  });
}
export {
  _page as default
};
