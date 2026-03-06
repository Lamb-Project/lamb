import { b as attr, e as ensure_array_like, c as store_get, a as attr_class, u as unsubscribe_stores, s as stringify } from "../../chunks/index2.js";
import "@sveltejs/kit/internal/server";
import { e as escape_html } from "../../chunks/context.js";
import { u as user } from "../../chunks/userStore.js";
import "@sveltejs/kit/internal";
import "../../chunks/exports.js";
import "../../chunks/utils.js";
import "../../chunks/state.svelte.js";
import "../../chunks/i18n.js";
import { a as $format } from "../../chunks/runtime.js";
import "marked";
import "../../chunks/apiClient.js";
function Login($$renderer, $$props) {
  $$renderer.component(($$renderer2) => {
    let email = "";
    let password = "";
    let loading = false;
    $$renderer2.push(`<div class="max-w-md mx-auto bg-white shadow-md rounded-lg overflow-hidden"><div class="p-6"><h2 class="text-2xl font-bold mb-6">${escape_html("Login")}</h2> <form class="space-y-4"><div class="space-y-2"><label for="email" class="block text-sm font-medium">${escape_html("Email")}</label> <input type="email" id="email"${attr("value", email)} required class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-brand focus:border-brand"/></div> <div class="space-y-2"><label for="password" class="block text-sm font-medium">${escape_html("Password")}</label> <input type="password" id="password"${attr("value", password)} required class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-brand focus:border-brand"/></div> `);
    {
      $$renderer2.push("<!--[!-->");
    }
    $$renderer2.push(`<!--]--> <button type="submit"${attr("disabled", loading, true)} class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-brand hover:bg-brand-hover focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand disabled:opacity-50">`);
    {
      $$renderer2.push("<!--[!-->");
      $$renderer2.push(`<span>${escape_html("Login")}</span>`);
    }
    $$renderer2.push(`<!--]--></button> <div class="text-center mt-4"><p class="text-sm text-gray-600">${escape_html("Don't have an account?")} <button type="button" class="text-brand hover:text-brand-hover font-medium">${escape_html("Sign up")}</button></p></div></form></div></div>`);
  });
}
function UserDashboard($$renderer, $$props) {
  $$renderer.component(($$renderer2) => {
    var $$store_subs;
    let {
      profile = null,
      isLoading = false,
      error = null
    } = $$props;
    let expandedOwned = {
      assistants: false,
      kbs: false,
      rubrics: false,
      templates: false
    };
    let expandedShared = {
      assistants: false,
      kbs: false,
      rubrics: false,
      templates: false
    };
    function formatDate(ts) {
      if (!ts) return "-";
      return new Date(ts * 1e3).toLocaleDateString(void 0, { year: "numeric", month: "short", day: "numeric" });
    }
    function orgRoleLabel(role) {
      if (!role) return "-";
      const key = `home.dashboard.orgRole.${role}`;
      return store_get($$store_subs ??= {}, "$_", $format)(key, { default: role.charAt(0).toUpperCase() + role.slice(1) });
    }
    $$renderer2.push(`<div>`);
    if (isLoading) {
      $$renderer2.push("<!--[-->");
      $$renderer2.push(`<div class="mb-6"><div class="h-6 bg-gray-200 rounded w-1/3 mb-2 animate-pulse"></div> <div class="h-4 bg-gray-200 rounded w-1/2 mb-6 animate-pulse"></div></div> <div class="space-y-6"><!--[-->`);
      const each_array = ensure_array_like(Array(3));
      for (let $$index = 0, $$length = each_array.length; $$index < $$length; $$index++) {
        each_array[$$index];
        $$renderer2.push(`<div class="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 animate-pulse"><div class="h-4 bg-gray-200 rounded w-1/4 mb-4"></div> <div class="space-y-3"><div class="h-3 bg-gray-200 rounded w-3/4"></div> <div class="h-3 bg-gray-200 rounded w-1/2"></div> <div class="h-3 bg-gray-200 rounded w-2/3"></div></div></div>`);
      }
      $$renderer2.push(`<!--]--></div>`);
    } else {
      $$renderer2.push("<!--[!-->");
      if (error) {
        $$renderer2.push("<!--[-->");
        $$renderer2.push(`<div class="bg-red-50 border border-red-200 text-red-700 px-6 py-4 rounded-xl mb-6" role="alert"><div class="flex items-center gap-3"><svg class="w-5 h-5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"></path></svg> <span class="font-medium">${escape_html(error)}</span></div> <button class="mt-3 text-red-600 hover:text-red-800 underline text-sm">${escape_html(store_get($$store_subs ??= {}, "$_", $format)("home.dashboard.retry", { default: "Try Again" }))}</button></div>`);
      } else {
        $$renderer2.push("<!--[!-->");
        if (profile) {
          $$renderer2.push("<!--[-->");
          $$renderer2.push(`<div class="mb-8"><h1 class="text-2xl font-semibold text-gray-800 mb-1">${escape_html(store_get($$store_subs ??= {}, "$_", $format)("home.dashboard.welcome", {
            default: `Welcome back, ${profile.user.name}!`,
            values: { name: profile.user.name || profile.user.email }
          }))}</h1> `);
          if (profile.organization) {
            $$renderer2.push("<!--[-->");
            $$renderer2.push(`<p class="text-gray-500 text-sm flex items-center gap-3 flex-wrap"><span class="inline-flex items-center gap-1"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5"></path></svg> ${escape_html(profile.organization.name)}</span> <span class="text-gray-300">|</span> <span>${escape_html(store_get($$store_subs ??= {}, "$_", $format)("home.dashboard.role", { default: "Role" }))}: ${escape_html(orgRoleLabel(profile.organization.role))}</span> <span class="text-gray-300">|</span> <span>${escape_html(store_get($$store_subs ??= {}, "$_", $format)("home.dashboard.memberSince", { default: "Member since" }))} ${escape_html(formatDate(profile.user.created_at))}</span></p>`);
          } else {
            $$renderer2.push("<!--[!-->");
          }
          $$renderer2.push(`<!--]--></div> <div class="grid grid-cols-1 xl:grid-cols-2 gap-8"><div class="space-y-4"><h2 class="text-sm font-medium text-gray-500 uppercase tracking-wide">${escape_html(store_get($$store_subs ??= {}, "$_", $format)("home.dashboard.owned", { default: "My Resources" }))}</h2> <div class="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-2xl shadow-sm border border-blue-100 overflow-hidden"><button class="w-full flex items-center justify-between p-5 cursor-pointer hover:bg-blue-50/50 transition-colors text-left"${attr("aria-expanded", expandedOwned.assistants)}><h3 class="text-sm font-medium text-blue-600 uppercase tracking-wide flex items-center gap-2"><svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path></svg> ${escape_html(store_get($$store_subs ??= {}, "$_", $format)("home.dashboard.assistants", { default: "Assistants" }))}</h3> <div class="flex items-center gap-3"><span class="text-xs text-gray-500">${escape_html(profile.owned.assistants.total)} ${escape_html(store_get($$store_subs ??= {}, "$_", $format)("home.dashboard.total", { default: "total" }))}
                                · ${escape_html(profile.owned.assistants.published)} ${escape_html(store_get($$store_subs ??= {}, "$_", $format)("home.dashboard.published", { default: "published" }))}</span> <svg${attr_class(`w-4 h-4 text-gray-400 transition-transform ${stringify("")}`)} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg></div></button> `);
          {
            $$renderer2.push("<!--[!-->");
          }
          $$renderer2.push(`<!--]--></div> <div class="bg-gradient-to-br from-amber-50 to-orange-50 rounded-2xl shadow-sm border border-amber-100 overflow-hidden"><button class="w-full flex items-center justify-between p-5 cursor-pointer hover:bg-amber-50/50 transition-colors text-left"${attr("aria-expanded", expandedOwned.kbs)}><h3 class="text-sm font-medium text-amber-600 uppercase tracking-wide flex items-center gap-2"><svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"></path></svg> ${escape_html(store_get($$store_subs ??= {}, "$_", $format)("home.dashboard.knowledgeBases", { default: "Knowledge Bases" }))}</h3> <div class="flex items-center gap-3"><span class="text-xs text-gray-500">${escape_html(profile.owned.knowledge_bases.total)} ${escape_html(store_get($$store_subs ??= {}, "$_", $format)("home.dashboard.total", { default: "total" }))}
                                · ${escape_html(profile.owned.knowledge_bases.shared)} ${escape_html(store_get($$store_subs ??= {}, "$_", $format)("home.dashboard.shared", { default: "shared" }))}</span> <svg${attr_class(`w-4 h-4 text-gray-400 transition-transform ${stringify("")}`)} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg></div></button> `);
          {
            $$renderer2.push("<!--[!-->");
          }
          $$renderer2.push(`<!--]--></div> <div class="bg-gradient-to-br from-rose-50 to-pink-50 rounded-2xl shadow-sm border border-rose-100 overflow-hidden"><button class="w-full flex items-center justify-between p-5 cursor-pointer hover:bg-rose-50/50 transition-colors text-left"${attr("aria-expanded", expandedOwned.rubrics)}><h3 class="text-sm font-medium text-rose-600 uppercase tracking-wide flex items-center gap-2"><svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"></path></svg> ${escape_html(store_get($$store_subs ??= {}, "$_", $format)("home.dashboard.rubrics", { default: "Rubrics" }))}</h3> <div class="flex items-center gap-3"><span class="text-xs text-gray-500">${escape_html(profile.owned.rubrics.total)} ${escape_html(store_get($$store_subs ??= {}, "$_", $format)("home.dashboard.total", { default: "total" }))}
                                · ${escape_html(profile.owned.rubrics.public)} ${escape_html(store_get($$store_subs ??= {}, "$_", $format)("home.dashboard.public", { default: "public" }))}</span> <svg${attr_class(`w-4 h-4 text-gray-400 transition-transform ${stringify("")}`)} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg></div></button> `);
          {
            $$renderer2.push("<!--[!-->");
          }
          $$renderer2.push(`<!--]--></div> <div class="bg-gradient-to-br from-slate-50 to-gray-100 rounded-2xl shadow-sm border border-slate-200 overflow-hidden"><button class="w-full flex items-center justify-between p-5 cursor-pointer hover:bg-slate-50/50 transition-colors text-left"${attr("aria-expanded", expandedOwned.templates)}><h3 class="text-sm font-medium text-slate-600 uppercase tracking-wide flex items-center gap-2"><svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z"></path></svg> ${escape_html(store_get($$store_subs ??= {}, "$_", $format)("home.dashboard.templates", { default: "Templates" }))}</h3> <div class="flex items-center gap-3"><span class="text-xs text-gray-500">${escape_html(profile.owned.templates.total)} ${escape_html(store_get($$store_subs ??= {}, "$_", $format)("home.dashboard.total", { default: "total" }))}
                                · ${escape_html(profile.owned.templates.shared)} ${escape_html(store_get($$store_subs ??= {}, "$_", $format)("home.dashboard.shared", { default: "shared" }))}</span> <svg${attr_class(`w-4 h-4 text-gray-400 transition-transform ${stringify("")}`)} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg></div></button> `);
          {
            $$renderer2.push("<!--[!-->");
          }
          $$renderer2.push(`<!--]--></div></div>  <div class="space-y-4"><h2 class="text-sm font-medium text-gray-500 uppercase tracking-wide">${escape_html(store_get($$store_subs ??= {}, "$_", $format)("home.dashboard.sharedWithMe", { default: "Shared with Me" }))}</h2> `);
          if (profile.shared_with_me.assistants.total === 0 && profile.shared_with_me.knowledge_bases.total === 0 && profile.shared_with_me.rubrics.total === 0 && profile.shared_with_me.templates.total === 0) {
            $$renderer2.push("<!--[-->");
            $$renderer2.push(`<div class="bg-white rounded-2xl shadow-sm border border-gray-200 p-8 text-center"><div class="inline-flex items-center justify-center w-12 h-12 bg-gray-100 rounded-full mb-3"><svg class="w-6 h-6 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z"></path></svg></div> <p class="text-sm text-gray-400">${escape_html(store_get($$store_subs ??= {}, "$_", $format)("home.dashboard.noSharedResources", { default: "Nothing shared with you yet" }))}</p></div>`);
          } else {
            $$renderer2.push("<!--[!-->");
            if (profile.shared_with_me.assistants.total > 0) {
              $$renderer2.push("<!--[-->");
              $$renderer2.push(`<div class="bg-white rounded-2xl shadow-sm border border-blue-100 overflow-hidden"><button class="w-full flex items-center justify-between p-5 cursor-pointer hover:bg-blue-50/30 transition-colors text-left"${attr("aria-expanded", expandedShared.assistants)}><h3 class="text-sm font-medium text-blue-600 uppercase tracking-wide flex items-center gap-2"><svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path></svg> ${escape_html(store_get($$store_subs ??= {}, "$_", $format)("home.dashboard.assistants", { default: "Assistants" }))}</h3> <div class="flex items-center gap-3"><span class="text-xs text-gray-500">${escape_html(profile.shared_with_me.assistants.total)}</span> <svg${attr_class(`w-4 h-4 text-gray-400 transition-transform ${stringify("")}`)} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg></div></button> `);
              {
                $$renderer2.push("<!--[!-->");
              }
              $$renderer2.push(`<!--]--></div>`);
            } else {
              $$renderer2.push("<!--[!-->");
            }
            $$renderer2.push(`<!--]--> `);
            if (profile.shared_with_me.knowledge_bases.total > 0) {
              $$renderer2.push("<!--[-->");
              $$renderer2.push(`<div class="bg-white rounded-2xl shadow-sm border border-amber-100 overflow-hidden"><button class="w-full flex items-center justify-between p-5 cursor-pointer hover:bg-amber-50/30 transition-colors text-left"${attr("aria-expanded", expandedShared.kbs)}><h3 class="text-sm font-medium text-amber-600 uppercase tracking-wide flex items-center gap-2"><svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"></path></svg> ${escape_html(store_get($$store_subs ??= {}, "$_", $format)("home.dashboard.knowledgeBases", { default: "Knowledge Bases" }))}</h3> <div class="flex items-center gap-3"><span class="text-xs text-gray-500">${escape_html(profile.shared_with_me.knowledge_bases.total)}</span> <svg${attr_class(`w-4 h-4 text-gray-400 transition-transform ${stringify("")}`)} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg></div></button> `);
              {
                $$renderer2.push("<!--[!-->");
              }
              $$renderer2.push(`<!--]--></div>`);
            } else {
              $$renderer2.push("<!--[!-->");
            }
            $$renderer2.push(`<!--]--> `);
            if (profile.shared_with_me.rubrics.total > 0) {
              $$renderer2.push("<!--[-->");
              $$renderer2.push(`<div class="bg-white rounded-2xl shadow-sm border border-rose-100 overflow-hidden"><button class="w-full flex items-center justify-between p-5 cursor-pointer hover:bg-rose-50/30 transition-colors text-left"${attr("aria-expanded", expandedShared.rubrics)}><h3 class="text-sm font-medium text-rose-600 uppercase tracking-wide flex items-center gap-2"><svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"></path></svg> ${escape_html(store_get($$store_subs ??= {}, "$_", $format)("home.dashboard.rubrics", { default: "Rubrics" }))}</h3> <div class="flex items-center gap-3"><span class="text-xs text-gray-500">${escape_html(profile.shared_with_me.rubrics.total)}</span> <svg${attr_class(`w-4 h-4 text-gray-400 transition-transform ${stringify("")}`)} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg></div></button> `);
              {
                $$renderer2.push("<!--[!-->");
              }
              $$renderer2.push(`<!--]--></div>`);
            } else {
              $$renderer2.push("<!--[!-->");
            }
            $$renderer2.push(`<!--]--> `);
            if (profile.shared_with_me.templates.total > 0) {
              $$renderer2.push("<!--[-->");
              $$renderer2.push(`<div class="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden"><button class="w-full flex items-center justify-between p-5 cursor-pointer hover:bg-slate-50/30 transition-colors text-left"${attr("aria-expanded", expandedShared.templates)}><h3 class="text-sm font-medium text-slate-600 uppercase tracking-wide flex items-center gap-2"><svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z"></path></svg> ${escape_html(store_get($$store_subs ??= {}, "$_", $format)("home.dashboard.templates", { default: "Templates" }))}</h3> <div class="flex items-center gap-3"><span class="text-xs text-gray-500">${escape_html(profile.shared_with_me.templates.total)}</span> <svg${attr_class(`w-4 h-4 text-gray-400 transition-transform ${stringify("")}`)} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg></div></button> `);
              {
                $$renderer2.push("<!--[!-->");
              }
              $$renderer2.push(`<!--]--></div>`);
            } else {
              $$renderer2.push("<!--[!-->");
            }
            $$renderer2.push(`<!--]-->`);
          }
          $$renderer2.push(`<!--]--></div></div>`);
        } else {
          $$renderer2.push("<!--[!-->");
          $$renderer2.push(`<div class="text-center py-12"><div class="inline-flex items-center justify-center w-16 h-16 bg-gray-100 rounded-full mb-4"><svg class="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path></svg></div> <p class="text-gray-500 mb-4">${escape_html(store_get($$store_subs ??= {}, "$_", $format)("home.dashboard.loading", { default: "Loading your dashboard..." }))}</p> <button class="inline-flex items-center gap-2 px-4 py-2 bg-[#2271b3] text-white rounded-lg text-sm hover:bg-[#195a91] transition-colors">${escape_html(store_get($$store_subs ??= {}, "$_", $format)("home.dashboard.retry", { default: "Try Again" }))}</button></div>`);
        }
        $$renderer2.push(`<!--]-->`);
      }
      $$renderer2.push(`<!--]-->`);
    }
    $$renderer2.push(`<!--]--></div>`);
    if ($$store_subs) unsubscribe_stores($$store_subs);
  });
}
function _page($$renderer, $$props) {
  $$renderer.component(($$renderer2) => {
    var $$store_subs;
    let profileData = null;
    let isLoadingProfile = false;
    let profileError = null;
    $$renderer2.push(`<div class="container mx-auto px-4 py-8">`);
    if (store_get($$store_subs ??= {}, "$user", user).isLoggedIn) {
      $$renderer2.push("<!--[-->");
      $$renderer2.push(`<div class="border-b border-gray-200 mb-6"><ul class="flex flex-wrap -mb-px"><li class="mr-2"><button${attr_class(`inline-block py-2 px-4 text-sm font-medium ${"text-white bg-[#2271b3] border-[#2271b3]"} rounded-t-lg border-b-2`)}${attr("aria-label", store_get($$store_subs ??= {}, "$_", $format)("home.tabs.dashboard", { default: "Dashboard" }))}><span class="inline-flex items-center gap-2"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path></svg> ${escape_html(store_get($$store_subs ??= {}, "$_", $format)("home.tabs.dashboard", { default: "Dashboard" }))}</span></button></li> <li class="mr-2"><button${attr_class(`inline-block py-2 px-4 text-sm font-medium ${"text-gray-500 hover:text-[#2271b3] border-transparent"} rounded-t-lg border-b-2`)}${attr("aria-label", store_get($$store_subs ??= {}, "$_", $format)("home.tabs.help", { default: "Help & News" }))}><span class="inline-flex items-center gap-2"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg> ${escape_html(store_get($$store_subs ??= {}, "$_", $format)("home.tabs.help", { default: "Help & News" }))}</span></button></li></ul></div> `);
      {
        $$renderer2.push("<!--[-->");
        UserDashboard($$renderer2, {
          profile: profileData,
          isLoading: isLoadingProfile,
          error: profileError
        });
      }
      $$renderer2.push(`<!--]-->`);
    } else {
      $$renderer2.push("<!--[!-->");
      $$renderer2.push(`<div class="max-w-md mx-auto bg-white shadow-md rounded-lg overflow-hidden">`);
      {
        $$renderer2.push("<!--[-->");
        Login($$renderer2);
      }
      $$renderer2.push(`<!--]--></div> <div class="text-center mt-8"><div class="mx-auto bg-[#e9ecef] p-4 rounded-lg" style="max-width: 400px;"><h2 class="text-3xl font-bold text-[#2271b3]">LAMB</h2> <p class="text-[#195a91]">Learning Assistants Manager and Builder</p></div></div>`);
    }
    $$renderer2.push(`<!--]--></div>`);
    if ($$store_subs) unsubscribe_stores($$store_subs);
  });
}
export {
  _page as default
};
