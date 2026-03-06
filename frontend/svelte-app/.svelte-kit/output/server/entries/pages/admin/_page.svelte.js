import { c as store_get, e as ensure_array_like, u as unsubscribe_stores, b as attr, d as bind_props, a as attr_class } from "../../../chunks/index2.js";
import { o as onDestroy } from "../../../chunks/index-server.js";
import "@sveltejs/kit/internal";
import "../../../chunks/exports.js";
import "../../../chunks/utils.js";
import "@sveltejs/kit/internal/server";
import "../../../chunks/state.svelte.js";
import "../../../chunks/i18n.js";
import axios from "axios";
import { g as getApiUrl } from "../../../chunks/config.js";
import { u as user } from "../../../chunks/userStore.js";
import { a as authenticatedFetch } from "../../../chunks/apiClient.js";
import { C as ChangePasswordModal, U as UserForm, a as UserActionModal, d as disableUser, b as disableUsersBulk, e as enableUser, c as enableUsersBulk } from "../../../chunks/UserActionModal.js";
import { C as ConfirmationModal } from "../../../chunks/ConfirmationModal.js";
import { p as processListData } from "../../../chunks/listHelpers.js";
import { a as $format } from "../../../chunks/runtime.js";
import { e as escape_html } from "../../../chunks/context.js";
function AdminDashboard($$renderer, $$props) {
  $$renderer.component(($$renderer2) => {
    var $$store_subs;
    let {
      systemStats = null,
      isLoading = false,
      error = null,
      localeLoaded = true
    } = $$props;
    $$renderer2.push(`<div><h1 class="text-2xl font-semibold text-gray-800 mb-2">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("admin.dashboard.title", { default: "System Dashboard" }) : "System Dashboard")}</h1> <p class="text-gray-500 mb-8 text-sm">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("admin.dashboard.welcome", { default: "Overview of your LAMB platform statistics" }) : "Overview of your LAMB platform statistics")}</p> `);
    if (isLoading) {
      $$renderer2.push("<!--[-->");
      $$renderer2.push(`<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"><!--[-->`);
      const each_array = ensure_array_like(Array(6));
      for (let $$index = 0, $$length = each_array.length; $$index < $$length; $$index++) {
        each_array[$$index];
        $$renderer2.push(`<div class="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 animate-pulse"><div class="h-4 bg-gray-200 rounded w-1/3 mb-4"></div> <div class="h-10 bg-gray-200 rounded w-1/2 mb-4"></div> <div class="flex gap-4"><div class="h-3 bg-gray-200 rounded w-1/4"></div> <div class="h-3 bg-gray-200 rounded w-1/4"></div></div></div>`);
      }
      $$renderer2.push(`<!--]--></div>`);
    } else {
      $$renderer2.push("<!--[!-->");
      if (error) {
        $$renderer2.push("<!--[-->");
        $$renderer2.push(`<div class="bg-red-50 border border-red-200 text-red-700 px-6 py-4 rounded-xl mb-6" role="alert"><div class="flex items-center gap-3"><svg class="w-5 h-5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"></path></svg> <span class="font-medium">${escape_html(error)}</span></div> <button class="mt-3 text-red-600 hover:text-red-800 underline text-sm">Try again</button></div>`);
      } else {
        $$renderer2.push("<!--[!-->");
        if (systemStats) {
          $$renderer2.push("<!--[-->");
          $$renderer2.push(`<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"><div class="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-2xl shadow-sm border border-blue-100 p-6 transition-all hover:shadow-md hover:scale-[1.02] cursor-pointer" role="button" tabindex="0"><div class="flex items-center justify-between mb-4"><h3 class="text-sm font-medium text-blue-600 uppercase tracking-wide">Users</h3> <div class="p-2 bg-blue-100 rounded-xl"><svg class="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5-9a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0z"></path></svg></div></div> <div class="text-4xl font-bold text-gray-900 mb-3">${escape_html(systemStats.users.total)}</div> <div class="flex flex-wrap gap-x-4 gap-y-1 text-sm"><span class="text-emerald-600 flex items-center gap-1"><span class="w-2 h-2 bg-emerald-500 rounded-full"></span> ${escape_html(systemStats.users.enabled)} active</span> `);
          if (systemStats.users.disabled > 0) {
            $$renderer2.push("<!--[-->");
            $$renderer2.push(`<span class="text-gray-400 flex items-center gap-1"><span class="w-2 h-2 bg-gray-300 rounded-full"></span> ${escape_html(systemStats.users.disabled)} disabled</span>`);
          } else {
            $$renderer2.push("<!--[!-->");
          }
          $$renderer2.push(`<!--]--></div> <div class="mt-3 pt-3 border-t border-blue-100 flex gap-4 text-xs text-gray-500"><span>${escape_html(systemStats.users.creators)} creators</span> <span>${escape_html(systemStats.users.end_users)} end users</span></div></div> <div class="bg-gradient-to-br from-violet-50 to-purple-50 rounded-2xl shadow-sm border border-violet-100 p-6 transition-all hover:shadow-md hover:scale-[1.02]"><div class="flex items-center justify-between mb-4"><h3 class="text-sm font-medium text-violet-600 uppercase tracking-wide">Organizations</h3> <div class="p-2 bg-violet-100 rounded-xl"><svg class="w-6 h-6 text-violet-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"></path></svg></div></div> <div class="text-4xl font-bold text-gray-900 mb-3">${escape_html(systemStats.organizations.total)}</div> <div class="flex flex-wrap gap-x-4 gap-y-1 text-sm"><span class="text-emerald-600 flex items-center gap-1"><span class="w-2 h-2 bg-emerald-500 rounded-full"></span> ${escape_html(systemStats.organizations.active)} active</span> `);
          if (systemStats.organizations.inactive > 0) {
            $$renderer2.push("<!--[-->");
            $$renderer2.push(`<span class="text-gray-400 flex items-center gap-1"><span class="w-2 h-2 bg-gray-300 rounded-full"></span> ${escape_html(systemStats.organizations.inactive)} inactive</span>`);
          } else {
            $$renderer2.push("<!--[!-->");
          }
          $$renderer2.push(`<!--]--></div></div> <div class="bg-gradient-to-br from-emerald-50 to-teal-50 rounded-2xl shadow-sm border border-emerald-100 p-6 transition-all hover:shadow-md hover:scale-[1.02]"><div class="flex items-center justify-between mb-4"><h3 class="text-sm font-medium text-emerald-600 uppercase tracking-wide">Assistants</h3> <div class="p-2 bg-emerald-100 rounded-xl"><svg class="w-6 h-6 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path></svg></div></div> <div class="text-4xl font-bold text-gray-900 mb-3">${escape_html(systemStats.assistants.total)}</div> <div class="flex flex-wrap gap-x-4 gap-y-1 text-sm"><span class="text-emerald-600 flex items-center gap-1"><span class="w-2 h-2 bg-emerald-500 rounded-full"></span> ${escape_html(systemStats.assistants.published)} published</span> <span class="text-amber-600 flex items-center gap-1"><span class="w-2 h-2 bg-amber-400 rounded-full"></span> ${escape_html(systemStats.assistants.unpublished)} drafts</span></div></div> <div class="bg-gradient-to-br from-amber-50 to-orange-50 rounded-2xl shadow-sm border border-amber-100 p-6 transition-all hover:shadow-md hover:scale-[1.02]"><div class="flex items-center justify-between mb-4"><h3 class="text-sm font-medium text-amber-600 uppercase tracking-wide">Knowledge Bases</h3> <div class="p-2 bg-amber-100 rounded-xl"><svg class="w-6 h-6 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"></path></svg></div></div> <div class="text-4xl font-bold text-gray-900 mb-3">${escape_html(systemStats.knowledge_bases.total)}</div> <div class="flex flex-wrap gap-x-4 gap-y-1 text-sm"><span class="text-cyan-600 flex items-center gap-1"><span class="w-2 h-2 bg-cyan-500 rounded-full"></span> ${escape_html(systemStats.knowledge_bases.shared)} shared</span> <span class="text-gray-400 flex items-center gap-1"><span class="w-2 h-2 bg-gray-300 rounded-full"></span> ${escape_html(systemStats.knowledge_bases.total - systemStats.knowledge_bases.shared)} private</span></div></div> <div class="bg-gradient-to-br from-rose-50 to-pink-50 rounded-2xl shadow-sm border border-rose-100 p-6 transition-all hover:shadow-md hover:scale-[1.02]"><div class="flex items-center justify-between mb-4"><h3 class="text-sm font-medium text-rose-600 uppercase tracking-wide">Rubrics</h3> <div class="p-2 bg-rose-100 rounded-xl"><svg class="w-6 h-6 text-rose-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"></path></svg></div></div> <div class="text-4xl font-bold text-gray-900 mb-3">${escape_html(systemStats.rubrics.total)}</div> <div class="flex flex-wrap gap-x-4 gap-y-1 text-sm"><span class="text-rose-600 flex items-center gap-1"><span class="w-2 h-2 bg-rose-500 rounded-full"></span> ${escape_html(systemStats.rubrics.public)} public</span> <span class="text-gray-400 flex items-center gap-1"><span class="w-2 h-2 bg-gray-300 rounded-full"></span> ${escape_html(systemStats.rubrics.total - systemStats.rubrics.public)} private</span></div></div> <div class="bg-gradient-to-br from-slate-50 to-gray-100 rounded-2xl shadow-sm border border-slate-200 p-6 transition-all hover:shadow-md hover:scale-[1.02]"><div class="flex items-center justify-between mb-4"><h3 class="text-sm font-medium text-slate-600 uppercase tracking-wide">Prompt Templates</h3> <div class="p-2 bg-slate-200 rounded-xl"><svg class="w-6 h-6 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z"></path></svg></div></div> <div class="text-4xl font-bold text-gray-900 mb-3">${escape_html(systemStats.templates.total)}</div> <div class="flex flex-wrap gap-x-4 gap-y-1 text-sm"><span class="text-slate-600 flex items-center gap-1"><span class="w-2 h-2 bg-slate-500 rounded-full"></span> ${escape_html(systemStats.templates.shared)} shared</span> <span class="text-gray-400 flex items-center gap-1"><span class="w-2 h-2 bg-gray-300 rounded-full"></span> ${escape_html(systemStats.templates.total - systemStats.templates.shared)} private</span></div></div></div> <div class="mt-8 pt-8 border-t border-gray-200"><h3 class="text-sm font-medium text-gray-500 uppercase tracking-wide mb-4">Quick Actions</h3> <div class="flex flex-wrap gap-3"><button class="inline-flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 rounded-lg text-sm text-gray-700 hover:bg-gray-50 hover:border-gray-300 transition-colors"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197"></path></svg> Manage Users</button> <button class="inline-flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 rounded-lg text-sm text-gray-700 hover:bg-gray-50 hover:border-gray-300 transition-colors"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5"></path></svg> Manage Organizations</button> <button class="inline-flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 rounded-lg text-sm text-gray-700 hover:bg-gray-50 hover:border-gray-300 transition-colors"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg> Refresh Stats</button></div></div>`);
        } else {
          $$renderer2.push("<!--[!-->");
          $$renderer2.push(`<div class="text-center py-12"><div class="inline-flex items-center justify-center w-16 h-16 bg-gray-100 rounded-full mb-4"><svg class="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path></svg></div> <p class="text-gray-500 mb-4">Loading system statistics...</p> <button class="inline-flex items-center gap-2 px-4 py-2 bg-brand text-white rounded-lg text-sm hover:bg-brand-hover transition-colors">Load Statistics</button></div>`);
        }
        $$renderer2.push(`<!--]-->`);
      }
      $$renderer2.push(`<!--]-->`);
    }
    $$renderer2.push(`<!--]--></div>`);
    if ($$store_subs) unsubscribe_stores($$store_subs);
  });
}
function OrgForm($$renderer, $$props) {
  $$renderer.component(($$renderer2) => {
    var $$store_subs;
    let {
      isOpen = false,
      localeLoaded = false,
      getAuthToken,
      onSuccess = () => {
      },
      onClose = () => {
      }
    } = $$props;
    let newOrg = getDefaultOrgData();
    let isCreatingOrg = false;
    let systemOrgUsers = [];
    function getDefaultOrgData() {
      return {
        slug: "",
        name: "",
        admin_user_id: null,
        signup_enabled: false,
        signup_key: "",
        use_system_baseline: true,
        config: {
          version: "1.0",
          setups: {
            default: { name: "Default Setup", providers: {}, knowledge_base: {} }
          },
          features: {
            rag_enabled: true,
            lti_publishing: true,
            signup_enabled: false
          },
          limits: {
            usage: {
              tokens_per_month: 1e6,
              max_assistants: 100,
              max_assistants_per_user: 10,
              storage_gb: 10
            }
          }
        }
      };
    }
    if (
      // Effect to fetch users and reset form when modal opens
      // Use untrack to prevent infinite loops - only track isOpen, not state inside the callbacks
      isOpen
    ) {
      $$renderer2.push("<!--[-->");
      $$renderer2.push(`<div class="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50 flex items-center justify-center"><div class="relative mx-auto p-5 border w-full max-w-2xl shadow-lg rounded-md bg-white"><div class="mt-3"><h3 class="text-lg leading-6 font-medium text-gray-900 text-center">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("admin.organizations.create.title", { default: "Create New Organization" }) : "Create New Organization")}</h3> `);
      {
        $$renderer2.push("<!--[!-->");
        $$renderer2.push(`<form class="mt-4">`);
        {
          $$renderer2.push("<!--[!-->");
        }
        $$renderer2.push(`<!--]--> <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4"><div class="text-left"><label for="org_slug" class="block text-gray-700 text-sm font-bold mb-2">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("admin.organizations.create.slug", { default: "Slug" }) : "Slug")} *</label> <input type="text" id="org_slug" name="org_slug" class="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline"${attr("value", newOrg.slug)} required pattern="[a-z0-9-]+" title="Only lowercase letters, numbers, and hyphens allowed"/> <p class="text-gray-500 text-xs italic mt-1">URL-friendly identifier (lowercase, numbers, hyphens only)</p></div> <div class="text-left"><label for="org_name" class="block text-gray-700 text-sm font-bold mb-2">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("admin.organizations.create.name", { default: "Name" }) : "Name")} *</label> <input type="text" id="org_name" name="org_name" class="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline"${attr("value", newOrg.name)} required/></div></div> <div class="mb-4 text-left"><label for="admin_user" class="block text-gray-700 text-sm font-bold mb-2">Organization Admin <span class="text-gray-400 font-normal text-xs ml-1">(optional)</span></label> `);
        {
          $$renderer2.push("<!--[!-->");
          {
            $$renderer2.push("<!--[!-->");
            $$renderer2.select(
              {
                id: "admin_user",
                name: "admin_user_id",
                class: "shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline",
                value: newOrg.admin_user_id
              },
              ($$renderer3) => {
                $$renderer3.option({ value: null }, ($$renderer4) => {
                  $$renderer4.push(`No admin (assign later)`);
                });
                $$renderer3.push(`<!--[-->`);
                const each_array = ensure_array_like(systemOrgUsers.filter((user2) => user2.role !== "admin"));
                for (let $$index = 0, $$length = each_array.length; $$index < $$length; $$index++) {
                  let user2 = each_array[$$index];
                  $$renderer3.option({ value: user2.id }, ($$renderer4) => {
                    $$renderer4.push(`${escape_html(user2.name)} (${escape_html(user2.email)}) - ${escape_html(user2.role)}`);
                  });
                }
                $$renderer3.push(`<!--]-->`);
              }
            );
          }
          $$renderer2.push(`<!--]-->`);
        }
        $$renderer2.push(`<!--]--> <p class="text-gray-500 text-xs italic mt-1">Optionally select a user from the system organization to become admin.
                                You can also create the organization without an admin and promote a member later from the organization's member list. <strong>Note:</strong> System admins are not eligible as they must remain in the system organization.</p></div> <div class="mb-4 text-left"><label for="signup_config_section" class="block text-gray-700 text-sm font-bold mb-2">Signup Configuration</label> <div id="signup_config_section" class="mb-3"><label class="flex items-center"><input type="checkbox" name="signup_enabled"${attr("checked", newOrg.signup_enabled, true)} class="mr-2"/> <span class="text-sm">Enable organization-specific signup</span></label></div> `);
        {
          $$renderer2.push("<!--[!-->");
        }
        $$renderer2.push(`<!--]--></div> <div class="mb-4 text-left"><label class="flex items-center"><input type="checkbox" name="use_system_baseline"${attr("checked", newOrg.use_system_baseline, true)} class="mr-2"/> <span class="text-sm">Copy system organization configuration as baseline</span></label> <p class="text-gray-500 text-xs italic mt-1">Inherit providers and settings from the system organization</p></div> <div class="mb-4 text-left"><label for="org_features" class="block text-gray-700 text-sm font-bold mb-2">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("admin.organizations.create.features", { default: "Features" }) : "Features")}</label> <div class="grid grid-cols-2 gap-2"><label class="flex items-center"><input type="checkbox"${attr("checked", newOrg.config.features.rag_enabled, true)} class="mr-2"/> <span class="text-sm">RAG Enabled</span></label> <label class="flex items-center"><input type="checkbox"${attr("checked", newOrg.config.features.lti_publishing, true)} class="mr-2"/> <span class="text-sm">LTI Publishing</span></label> <label class="flex items-center"><input type="checkbox"${attr("checked", newOrg.config.features.signup_enabled, true)} class="mr-2"/> <span class="text-sm">Signup Enabled</span></label></div></div> <div class="mb-4 text-left" style="display: none;"><label for="org_limits" class="block text-gray-700 text-sm font-bold mb-2">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("admin.organizations.create.limits", { default: "Usage Limits" }) : "Usage Limits")}</label> <div class="grid grid-cols-1 md:grid-cols-3 gap-4"><div><label for="tokens_per_month" class="block text-gray-600 text-xs mb-1">Tokens/Month</label> <input type="number" id="tokens_per_month" class="shadow appearance-none border rounded w-full py-1 px-2 text-gray-700 text-sm leading-tight focus:outline-none focus:shadow-outline"${attr("value", newOrg.config.limits.usage.tokens_per_month)} min="0"/></div> <div><label for="max_assistants" class="block text-gray-600 text-xs mb-1">Max Assistants</label> <input type="number" id="max_assistants" class="shadow appearance-none border rounded w-full py-1 px-2 text-gray-700 text-sm leading-tight focus:outline-none focus:shadow-outline"${attr("value", newOrg.config.limits.usage.max_assistants)} min="1"/></div> <div><label for="storage_gb" class="block text-gray-600 text-xs mb-1">Storage (GB)</label> <input type="number" id="storage_gb" class="shadow appearance-none border rounded w-full py-1 px-2 text-gray-700 text-sm leading-tight focus:outline-none focus:shadow-outline"${attr("value", newOrg.config.limits.usage.storage_gb)} min="0" step="0.1"/></div></div></div> <div class="flex items-center justify-between"><button type="button" class="bg-gray-300 hover:bg-gray-400 text-gray-800 py-2 px-4 rounded focus:outline-none focus:shadow-outline">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("admin.organizations.create.cancel", { default: "Cancel" }) : "Cancel")}</button> <button type="submit" class="bg-brand text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline disabled:opacity-50"${attr("disabled", isCreatingOrg, true)}>${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("admin.organizations.create.create", { default: "Create Organization" }) : "Create Organization")}</button></div></form>`);
      }
      $$renderer2.push(`<!--]--></div></div></div>`);
    } else {
      $$renderer2.push("<!--[!-->");
    }
    $$renderer2.push(`<!--]-->`);
    if ($$store_subs) unsubscribe_stores($$store_subs);
    bind_props($$props, { isOpen });
  });
}
function _page($$renderer, $$props) {
  $$renderer.component(($$renderer2) => {
    var $$store_subs;
    let localeLoaded = true;
    let allUsers = [];
    let displayUsers = [];
    let isLoadingUsers = false;
    let usersSearch = "";
    let usersSortBy = "id";
    let usersSortOrder = "asc";
    let usersPage = 1;
    let usersPerPage = 10;
    let users = displayUsers;
    let selectedUsers = (
      /** @type {number[]} */
      []
    );
    let showDisableConfirm = false;
    let showEnableConfirm = false;
    let actionType = "";
    let targetUser = null;
    let isCreateUserModalOpen = false;
    let newUser = {
      email: "",
      name: "",
      password: "",
      role: "user",
      // Default role
      organization_id: null,
      // Default to no organization selected
      user_type: "creator"
      // Default type: 'creator' or 'end_user'
    };
    let isCreatingUser = false;
    let createUserError = null;
    let createUserSuccess = false;
    let organizationsForUsers = [];
    let isLoadingOrganizationsForUsers = false;
    let organizationsForUsersError = null;
    let isChangePasswordModalOpen = false;
    let passwordChangeData = { email: "", new_password: "" };
    let isChangingPassword = false;
    let changePasswordError = null;
    let changePasswordSuccess = false;
    let selectedUserName = "";
    let systemStats = null;
    let isLoadingStats = false;
    let statsError = null;
    let organizations = [];
    let isLoadingOrganizations = false;
    let showDeleteOrgModal = false;
    let orgToDelete = null;
    let isDeletingOrg = false;
    let isCreateOrgModalOpen = false;
    function closeCreateUserModal() {
      isCreateUserModalOpen = false;
      createUserError = null;
    }
    function closeChangePasswordModal() {
      isChangePasswordModalOpen = false;
      changePasswordError = null;
      selectedUserName = "";
    }
    function clearSelection() {
      users.forEach((u) => u.selected = false);
    }
    async function confirmDisable() {
      try {
        if (actionType === "single") ;
        else {
          const result = await disableUsersBulk(selectedUsers);
          console.log(`Disabled ${result.disabled} user(s)`);
          alert(`Successfully disabled ${result.disabled} user(s)${result.failed > 0 ? `. Failed: ${result.failed}` : ""}`);
        }
        clearSelection();
        await fetchUsers();
      } catch (error) {
        console.error("Failed to disable user(s):", error);
        alert(`Error: ${error.message || "Failed to disable user(s)"}`);
      } finally {
        showDisableConfirm = false;
        targetUser = null;
      }
    }
    async function confirmEnable() {
      try {
        if (actionType === "single") ;
        else {
          const result = await enableUsersBulk(selectedUsers);
          console.log(`Enabled ${result.enabled} user(s)`);
          alert(`Successfully enabled ${result.enabled} user(s)${result.failed > 0 ? `. Failed: ${result.failed}` : ""}`);
        }
        clearSelection();
        await fetchUsers();
      } catch (error) {
        console.error("Failed to enable user(s):", error);
        alert(`Error: ${error.message || "Failed to enable user(s)"}`);
      } finally {
        showEnableConfirm = false;
        targetUser = null;
      }
    }
    function closeCreateOrgModal() {
      isCreateOrgModalOpen = false;
    }
    async function handleCreateUser(e) {
      e.preventDefault();
      const form = (
        /** @type {HTMLFormElement} */
        e.target
      );
      const formDataObj = new FormData(form);
      const email = (
        /** @type {string} */
        (formDataObj.get("email") || "").toString().trim()
      );
      const name = (
        /** @type {string} */
        (formDataObj.get("name") || "").toString().trim()
      );
      const password = (
        /** @type {string} */
        (formDataObj.get("password") || "").toString()
      );
      const role = (
        /** @type {string} */
        (formDataObj.get("role") || "user").toString()
      );
      const userTypeFromForm = (
        /** @type {string} */
        (formDataObj.get("user_type") || "creator").toString()
      );
      const organizationId = formDataObj.get("organization_id");
      if (!email || !name || !password) {
        createUserError = store_get($$store_subs ??= {}, "$_", $format)("admin.users.errors.fillRequired", { default: "Please fill in all required fields." });
        return;
      }
      if (!email.includes("@")) {
        createUserError = store_get($$store_subs ??= {}, "$_", $format)("admin.users.errors.invalidEmail", { default: "Please enter a valid email address." });
        return;
      }
      createUserError = null;
      isCreatingUser = true;
      try {
        const token = getAuthToken();
        if (!token) {
          throw new Error(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("admin.users.errors.authTokenNotFound", {
            default: "Authentication token not found. Please log in again."
          }) : "Authentication token not found. Please log in again.");
        }
        const formData = new URLSearchParams();
        formData.append("email", email);
        formData.append("name", name);
        formData.append("password", password);
        formData.append("role", role);
        const userType = role === "admin" ? "creator" : userTypeFromForm;
        formData.append("user_type", userType);
        if (organizationId && organizationId !== "null" && organizationId !== "") {
          formData.append("organization_id", String(organizationId));
        }
        const apiUrl = getApiUrl("/admin/users/create");
        console.log(`Creating user at: ${apiUrl}`);
        const response = await axios.post(apiUrl, formData, {
          headers: {
            "Authorization": `Bearer ${token}`,
            "Content-Type": "application/x-www-form-urlencoded"
          }
        });
        console.log("Create user response:", response.data);
        if (response.data && response.data.success) {
          createUserSuccess = true;
          setTimeout(
            () => {
              closeCreateUserModal();
              fetchUsers();
            },
            1500
          );
        } else {
          throw new Error(response.data.error || (localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("admin.users.errors.createFailed", { default: "Failed to create user." }) : "Failed to create user."));
        }
      } catch (err) {
        console.error("Error creating user:", err);
        if (axios.isAxiosError(err) && err.response?.data?.error) {
          createUserError = err.response.data.error;
        } else if (axios.isAxiosError(err) && err.response?.data?.detail) {
          if (Array.isArray(err.response.data.detail)) {
            const details = err.response.data.detail;
            createUserError = details.map((d) => d.msg).join(", ");
          } else {
            createUserError = err.response.data.detail;
          }
        } else if (err instanceof Error) {
          createUserError = err.message;
        } else {
          createUserError = store_get($$store_subs ??= {}, "$_", $format)("admin.users.errors.unknownError", {
            default: "An unknown error occurred while creating the user."
          });
        }
      } finally {
        isCreatingUser = false;
      }
    }
    async function handleChangePassword(e) {
      e.preventDefault();
      if (!passwordChangeData.new_password) {
        changePasswordError = store_get($$store_subs ??= {}, "$_", $format)("admin.users.errors.passwordRequired", { default: "Please enter a new password." });
        return;
      }
      if (passwordChangeData.new_password.length < 8) {
        changePasswordError = store_get($$store_subs ??= {}, "$_", $format)("admin.users.errors.passwordMinLength", { default: "Password should be at least 8 characters." });
        return;
      }
      changePasswordError = null;
      isChangingPassword = true;
      try {
        const formData = new URLSearchParams();
        formData.append("email", passwordChangeData.email);
        formData.append("new_password", passwordChangeData.new_password);
        const apiUrl = getApiUrl("/admin/users/update-password");
        console.log(`Changing password at: ${apiUrl}`);
        const response = await authenticatedFetch(apiUrl, {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: formData.toString()
        });
        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.error || errorData.detail || (localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("admin.users.errors.passwordChangeFailed", { default: "Failed to change password." }) : "Failed to change password."));
        }
        const data = await response.json();
        console.log("Change password response:", data);
        if (data && data.success) {
          changePasswordSuccess = true;
          setTimeout(
            () => {
              closeChangePasswordModal();
            },
            1500
          );
        } else {
          throw new Error(data.error || data.message || (localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("admin.users.errors.passwordChangeFailed", { default: "Failed to change password." }) : "Failed to change password."));
        }
      } catch (err) {
        console.error("Error changing password:", err);
        if (err instanceof Error) {
          changePasswordError = err.message;
        } else {
          changePasswordError = store_get($$store_subs ??= {}, "$_", $format)("admin.users.errors.passwordChangeUnknownError", {
            default: "An unknown error occurred while changing the password."
          });
        }
      } finally {
        isChangingPassword = false;
      }
    }
    onDestroy(() => {
      console.log("Admin page unmounting");
    });
    function getAuthToken() {
      const userData = store_get($$store_subs ??= {}, "$user", user);
      if (!userData.isLoggedIn || !userData.token) {
        console.error("No authentication token available. User must be logged in.");
        return null;
      }
      return userData.token;
    }
    async function fetchUsers() {
      if (isLoadingUsers) {
        console.log("Already loading users, skipping duplicate request");
        return;
      }
      console.log("Fetching all users...");
      isLoadingUsers = true;
      try {
        const token = getAuthToken();
        if (!token) {
          throw new Error("Authentication token not found. Please log in again.");
        }
        const apiUrl = getApiUrl("/users");
        console.log(`Fetching users from: ${apiUrl}`);
        const response = await axios.get(apiUrl, { headers: { "Authorization": `Bearer ${token}` } });
        console.log("API Response:", response.data);
        if (response.data && response.data.success) {
          allUsers = (response.data.data || []).map((u) => ({ ...u, selected: false }));
          console.log(`Fetched ${allUsers.length} users`);
          applyUsersFilters();
        } else {
          throw new Error(response.data.error || "Failed to fetch users.");
        }
      } catch (err) {
        console.error("Error fetching users:", err);
        if (axios.isAxiosError(err) && err.response?.status === 401) ;
        else if (axios.isAxiosError(err) && err.response?.data?.error) {
          err.response.data.error;
        } else if (err instanceof Error) {
          err.message;
        } else ;
        allUsers = [];
        displayUsers = [];
      } finally {
        isLoadingUsers = false;
      }
    }
    function applyUsersFilters() {
      const filters = {
        enabled: null,
        "organization.name": null
      };
      let result = processListData(allUsers, {
        search: usersSearch,
        searchFields: ["name", "email", "organization.name"],
        filters,
        sortBy: usersSortBy,
        sortOrder: usersSortOrder,
        page: usersPage,
        itemsPerPage: usersPerPage
      });
      displayUsers = result.items.map((u) => ({ ...u, selected: u.selected || false }));
      result.filteredCount;
      result.totalPages;
      usersPage = result.currentPage;
    }
    async function fetchOrganizations() {
      if (isLoadingOrganizations) {
        console.log("Already loading organizations, skipping duplicate request");
        return;
      }
      console.log("Fetching organizations...");
      isLoadingOrganizations = true;
      try {
        const token = getAuthToken();
        if (!token) {
          throw new Error("Authentication token not found. Please log in again.");
        }
        const apiUrl = getApiUrl("/admin/organizations");
        console.log(`Fetching organizations from: ${apiUrl}`);
        const response = await axios.get(apiUrl, { headers: { "Authorization": `Bearer ${token}` } });
        console.log("Organizations API Response:", response.data);
        if (response.data && Array.isArray(response.data)) {
          organizations = response.data;
          console.log(`Fetched ${organizations.length} organizations`);
        } else {
          throw new Error("Invalid response format.");
        }
      } catch (err) {
        console.error("Error fetching organizations:", err);
        if (axios.isAxiosError(err) && err.response?.status === 401) ;
        else if (axios.isAxiosError(err) && err.response?.data?.detail) {
          err.response.data.detail;
        } else if (err instanceof Error) {
          err.message;
        } else ;
        organizations = [];
      } finally {
        isLoadingOrganizations = false;
      }
    }
    async function confirmDeleteOrganization() {
      if (!orgToDelete || isDeletingOrg) return;
      isDeletingOrg = true;
      try {
        const token = getAuthToken();
        if (!token) {
          throw new Error("Authentication token not found. Please log in again.");
        }
        const apiUrl = getApiUrl(`/admin/organizations/${orgToDelete}`);
        console.log(`Deleting organization at: ${apiUrl}`);
        const response = await axios.delete(apiUrl, { headers: { "Authorization": `Bearer ${token}` } });
        console.log("Delete organization response:", response.data);
        fetchOrganizations();
        showDeleteOrgModal = false;
        orgToDelete = null;
        alert(`Organization deleted successfully!`);
      } catch (err) {
        console.error("Error deleting organization:", err);
        let errorMessage = "Failed to delete organization.";
        if (axios.isAxiosError(err) && err.response?.data?.detail) {
          errorMessage = err.response.data.detail;
        } else if (err instanceof Error) {
          errorMessage = err.message;
        }
        alert(`Error: ${errorMessage}`);
      } finally {
        isDeletingOrg = false;
      }
    }
    function cancelDeleteOrganization() {
      if (isDeletingOrg) return;
      showDeleteOrgModal = false;
      orgToDelete = null;
    }
    let $$settled = true;
    let $$inner_renderer;
    function $$render_inner($$renderer3) {
      $$renderer3.push(`<div class="container mx-auto px-4 py-8"><div class="border-b border-gray-200 mb-6"><ul class="flex flex-wrap -mb-px"><li class="mr-2"><button${attr_class(`inline-block py-2 px-4 text-sm font-medium ${"text-white bg-brand border-brand"} rounded-t-lg border-b-2`)}${attr(
        "aria-label",
        store_get($$store_subs ??= {}, "$_", $format)("admin.tabs.dashboard", { default: "Dashboard" })
      )}>${escape_html(
        store_get($$store_subs ??= {}, "$_", $format)("admin.tabs.dashboard", { default: "Dashboard" })
      )}</button></li> <li class="mr-2"><button${attr_class(`inline-block py-2 px-4 text-sm font-medium ${"text-gray-500 hover:text-brand border-transparent"} rounded-t-lg border-b-2`)}${attr(
        "aria-label",
        store_get($$store_subs ??= {}, "$_", $format)("admin.tabs.users", { default: "Users" })
      )}>${escape_html(
        store_get($$store_subs ??= {}, "$_", $format)("admin.tabs.users", { default: "Users" })
      )}</button></li> <li class="mr-2"><button${attr_class(`inline-block py-2 px-4 text-sm font-medium ${"text-gray-500 hover:text-brand border-transparent"} rounded-t-lg border-b-2`)}${attr(
        "aria-label",
        store_get($$store_subs ??= {}, "$_", $format)("admin.tabs.organizations", { default: "Organizations" })
      )}>${escape_html(
        store_get($$store_subs ??= {}, "$_", $format)("admin.tabs.organizations", { default: "Organizations" })
      )}</button></li> <li class="mr-2"><button${attr_class(`inline-block py-2 px-4 text-sm font-medium ${"text-gray-500 hover:text-brand border-transparent"} rounded-t-lg border-b-2`)} aria-label="LTI Settings">LTI Settings</button></li></ul></div> `);
      {
        $$renderer3.push("<!--[-->");
        AdminDashboard($$renderer3, {
          systemStats,
          isLoading: isLoadingStats,
          error: statsError,
          localeLoaded
        });
      }
      $$renderer3.push(`<!--]--></div> `);
      ChangePasswordModal($$renderer3, {
        isOpen: isChangePasswordModalOpen,
        userName: selectedUserName,
        userEmail: passwordChangeData.email,
        newPassword: passwordChangeData.new_password,
        isChanging: isChangingPassword,
        error: changePasswordError,
        success: changePasswordSuccess,
        localeLoaded,
        onSubmit: handleChangePassword,
        onClose: closeChangePasswordModal,
        onPasswordChange: (pwd) => {
          passwordChangeData.new_password = pwd;
        }
      });
      $$renderer3.push(`<!----> `);
      UserForm($$renderer3, {
        isOpen: isCreateUserModalOpen,
        isSuperAdmin: true,
        newUser,
        organizations: organizationsForUsers,
        isLoadingOrganizations: isLoadingOrganizationsForUsers,
        organizationsError: organizationsForUsersError,
        isCreating: isCreatingUser,
        error: createUserError,
        success: createUserSuccess,
        localeLoaded,
        onSubmit: handleCreateUser,
        onClose: closeCreateUserModal,
        onUserChange: (user2) => {
          newUser = user2;
        }
      });
      $$renderer3.push(`<!----> `);
      OrgForm($$renderer3, {
        localeLoaded,
        getAuthToken,
        onSuccess: () => fetchOrganizations(),
        onClose: closeCreateOrgModal,
        get isOpen() {
          return isCreateOrgModalOpen;
        },
        set isOpen($$value) {
          isCreateOrgModalOpen = $$value;
          $$settled = false;
        }
      });
      $$renderer3.push(`<!----> `);
      {
        $$renderer3.push("<!--[!-->");
      }
      $$renderer3.push(`<!--]--> `);
      UserActionModal($$renderer3, {
        isOpen: showDisableConfirm,
        action: "disable",
        isBulk: actionType === "bulk",
        targetUser: null,
        selectedCount: selectedUsers.length,
        localeLoaded,
        onConfirm: confirmDisable,
        onClose: () => {
          showDisableConfirm = false;
        }
      });
      $$renderer3.push(`<!----> `);
      UserActionModal($$renderer3, {
        isOpen: showEnableConfirm,
        action: "enable",
        isBulk: actionType === "bulk",
        targetUser: null,
        selectedCount: selectedUsers.length,
        localeLoaded,
        onConfirm: confirmEnable,
        onClose: () => {
          showEnableConfirm = false;
        }
      });
      $$renderer3.push(`<!----> `);
      {
        $$renderer3.push("<!--[!-->");
      }
      $$renderer3.push(`<!--]--> `);
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
      $$renderer3.push(`<!--]--> `);
      {
        $$renderer3.push("<!--[!-->");
      }
      $$renderer3.push(`<!--]--> `);
      ConfirmationModal($$renderer3, {
        title: "Delete Organization",
        message: `Are you sure you want to delete organization '${orgToDelete}'? This action cannot be undone and will remove all associated data.`,
        confirmText: "Delete",
        variant: "danger",
        onconfirm: confirmDeleteOrganization,
        oncancel: cancelDeleteOrganization,
        get isOpen() {
          return showDeleteOrgModal;
        },
        set isOpen($$value) {
          showDeleteOrgModal = $$value;
          $$settled = false;
        },
        get isLoading() {
          return isDeletingOrg;
        },
        set isLoading($$value) {
          isDeletingOrg = $$value;
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
export {
  _page as default
};
