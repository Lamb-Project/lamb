import "clsx";
import { a as attr_class, b as attr, s as stringify, c as store_get, u as unsubscribe_stores } from "../../chunks/index2.js";
import { u as user } from "../../chunks/userStore.js";
import { p as page } from "../../chunks/stores.js";
import { b as base } from "../../chunks/server.js";
import "@sveltejs/kit/internal/server";
import "../../chunks/i18n.js";
import { $ as $locale, a as $format } from "../../chunks/runtime.js";
import { e as escape_html } from "../../chunks/context.js";
import { o as onDestroy } from "../../chunks/index-server.js";
import "@sveltejs/kit/internal";
import "../../chunks/exports.js";
import "../../chunks/utils.js";
import "../../chunks/state.svelte.js";
import "../../chunks/apiClient.js";
function LanguageSelector($$renderer, $$props) {
  $$renderer.component(($$renderer2) => {
    let { size = "normal" } = $$props;
    let open = false;
    let currentLang = "en";
    $$renderer2.push(`<div class="lang-selector relative"><button${attr_class(`inline-flex items-center border border-gray-300 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 ${stringify(
      // Use $effect for adding/removing the global listener
      // Only run in browser
      /** @param {MouseEvent} e */
      // Add listener
      // Return a cleanup function to remove the listener
      size === "small" ? "px-1.5 py-0.5 text-xs" : "px-3 py-1 text-sm"
    )}`)} aria-haspopup="true"${attr("aria-expanded", open)}>${escape_html(currentLang?.toUpperCase() ?? "")} <svg${attr_class(size === "small" ? "ml-0.5 h-3 w-3" : "ml-1 h-4 w-4")} xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clip-rule="evenodd"></path></svg></button> `);
    {
      $$renderer2.push("<!--[!-->");
    }
    $$renderer2.push(`<!--]--></div>`);
  });
}
const VERSION_INFO = {
  "version": "0.5",
  "commit": "3b7af3a",
  "branch": "feature/issue#277/Architecture_Activity_Module_System_Extensible_LTI_App_Framework",
  "buildDate": "2026-03-06"
};
function Nav($$renderer, $$props) {
  $$renderer.component(($$renderer2) => {
    var $$store_subs;
    let versionDisplay = `v${VERSION_INFO.version}`;
    let toolsMenuOpen = false;
    $$renderer2.push(`<nav class="bg-white shadow"><div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8"><div class="flex justify-between h-16"><div class="flex"><div class="flex-shrink-0 flex items-center"><div class="flex items-center space-x-2"><img${attr("src", `${stringify(base)}/img/lamb_1.png`)} alt="LAMB Logo" class="h-14"/> <div class="text-lg font-bold"><a${attr("href", `${stringify(base)}/`)}>${escape_html("LAMB")}</a> <span class="text-xs bg-gray-200 px-1 py-0.5 rounded"${attr("title", `Version: ${stringify(VERSION_INFO.version)}, Commit: ${stringify(VERSION_INFO.commit)}, Branch: ${stringify(VERSION_INFO.branch)}`)}>${escape_html(versionDisplay)}</span></div></div></div> <div class="hidden sm:ml-4 sm:flex sm:items-center sm:gap-1"><a${attr("href", `${stringify(base)}/assistants`)}${attr_class(`inline-flex items-center px-2 pt-1 border-b-2 text-sm font-medium whitespace-nowrap ${stringify(store_get($$store_subs ??= {}, "$page", page).url.pathname === base + "/assistants" ? "border-[#2271b3] text-gray-900" : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700")} ${stringify(!store_get($$store_subs ??= {}, "$user", user).isLoggedIn ? "opacity-50 pointer-events-none" : "")}`)}${attr("aria-disabled", !store_get($$store_subs ??= {}, "$user", user).isLoggedIn)}>${escape_html("Learning Assistants")}</a> `);
    if (store_get($$store_subs ??= {}, "$user", user).isLoggedIn && store_get($$store_subs ??= {}, "$user", user).data?.role === "admin") {
      $$renderer2.push("<!--[-->");
      $$renderer2.push(`<a${attr("href", `${stringify(base)}/admin`)}${attr_class(`inline-flex items-center px-2 pt-1 border-b-2 text-sm font-medium whitespace-nowrap ${stringify(store_get($$store_subs ??= {}, "$page", page).url.pathname === base + "/admin" ? "border-[#2271b3] text-gray-900" : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700")}`)}>${escape_html("Admin")}</a>`);
    } else {
      $$renderer2.push("<!--[!-->");
    }
    $$renderer2.push(`<!--]--> `);
    if (store_get($$store_subs ??= {}, "$user", user).isLoggedIn && store_get($$store_subs ??= {}, "$user", user).data?.organization_role === "admin" && store_get($$store_subs ??= {}, "$user", user).data?.role !== "admin") {
      $$renderer2.push("<!--[-->");
      $$renderer2.push(`<a${attr("href", `${stringify(base)}/org-admin`)}${attr_class(`inline-flex items-center px-2 pt-1 border-b-2 text-sm font-medium whitespace-nowrap ${stringify(store_get($$store_subs ??= {}, "$page", page).url.pathname === base + "/org-admin" ? "border-[#2271b3] text-gray-900" : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700")}`)}>${escape_html("Org Admin")}</a>`);
    } else {
      $$renderer2.push("<!--[!-->");
    }
    $$renderer2.push(`<!--]--> <div class="relative tools-menu h-full flex items-center"><button type="button"${attr_class(`inline-flex items-center h-full px-2 py-4 border-b-2 text-sm font-medium cursor-pointer select-none whitespace-nowrap ${stringify(store_get($$store_subs ??= {}, "$page", page).url.pathname.startsWith(base + "/knowledgebases") || store_get($$store_subs ??= {}, "$page", page).url.pathname.startsWith(base + "/evaluaitor") ? "border-[#2271b3] text-gray-900" : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700")} ${stringify(!store_get($$store_subs ??= {}, "$user", user).isLoggedIn ? "opacity-50 pointer-events-none" : "")}`)}${attr("aria-disabled", !store_get($$store_subs ??= {}, "$user", user).isLoggedIn)}${attr("aria-expanded", toolsMenuOpen)} aria-haspopup="true"><span class="pointer-events-none">${escape_html("Sources of Knowledge")}</span> <svg${attr_class(`ml-1 h-4 w-4 transition-transform duration-200 pointer-events-none ${stringify("")}`)} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg></button> `);
    {
      $$renderer2.push("<!--[!-->");
    }
    $$renderer2.push(`<!--]--></div></div></div> <div class="flex items-center gap-3">`);
    if (store_get($$store_subs ??= {}, "$user", user).isLoggedIn) {
      $$renderer2.push("<!--[-->");
      $$renderer2.push(`<span class="text-sm font-medium text-gray-600 hidden sm:block">${escape_html(store_get($$store_subs ??= {}, "$user", user).name || store_get($$store_subs ??= {}, "$user", user).email || "")}</span>`);
    } else {
      $$renderer2.push("<!--[!-->");
    }
    $$renderer2.push(`<!--]--> <div class="flex flex-col items-end gap-0.5">`);
    if (store_get($$store_subs ??= {}, "$user", user).isLoggedIn) {
      $$renderer2.push("<!--[-->");
      $$renderer2.push(`<button class="inline-flex items-center justify-center px-2 py-1 text-xs font-medium rounded text-white bg-red-600 hover:bg-red-700">${escape_html("Logout")}</button>`);
    } else {
      $$renderer2.push("<!--[!-->");
    }
    $$renderer2.push(`<!--]--> `);
    LanguageSelector($$renderer2, { size: "small" });
    $$renderer2.push(`<!----></div></div></div></div></nav>`);
    if ($$store_subs) unsubscribe_stores($$store_subs);
  });
}
function Footer($$renderer, $$props) {
  $$renderer.component(($$renderer2) => {
    var $$store_subs;
    let versionDisplay = `v${VERSION_INFO.version} (${VERSION_INFO.commit})`;
    $$renderer2.push(`<footer class="bg-white border-t border-gray-200 mt-auto"><div class="max-w-7xl mx-auto py-4 px-4 sm:px-6 lg:px-8"><div class="flex items-center justify-center space-x-3 text-sm text-gray-600"><img${attr("src", `${stringify(base)}/img/lamb_1.png`)} alt="LAMB Logo" class="h-8"/> <div class="flex flex-wrap items-center justify-center gap-x-2"><span class="font-semibold text-gray-900">LAMB</span> <span>${escape_html(store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("app.tagline", { default: "Learning Assistants Manager and Builder" }) : "Learning Assistants Manager and Builder")}</span> <span class="text-gray-400"${attr("title", `Version: ${stringify(VERSION_INFO.version)}, Commit: ${stringify(VERSION_INFO.commit)}, Branch: ${stringify(VERSION_INFO.branch)}, Build Date: ${stringify(VERSION_INFO.buildDate)}`)}>${escape_html(versionDisplay)}</span> <span class="text-gray-400">•</span> <a href="https://lamb-project.org" target="_blank" rel="noopener noreferrer" class="text-[#2271b3] hover:text-[#195a91] underline">lamb-project.org</a></div></div></div></footer>`);
    if ($$store_subs) unsubscribe_stores($$store_subs);
  });
}
function _layout($$renderer, $$props) {
  $$renderer.component(($$renderer2) => {
    let { children } = $$props;
    onDestroy(() => {
    });
    $$renderer2.push(`<div class="min-h-screen bg-gray-50 text-gray-900 flex flex-col">`);
    Nav($$renderer2);
    $$renderer2.push(`<!----> <main class="w-full mx-auto py-6 sm:px-6 lg:px-8 flex-grow">`);
    children($$renderer2);
    $$renderer2.push(`<!----></main> `);
    Footer($$renderer2);
    $$renderer2.push(`<!----></div>`);
  });
}
export {
  _layout as default
};
