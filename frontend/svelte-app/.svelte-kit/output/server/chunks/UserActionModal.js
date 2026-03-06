import { g as getApiUrl } from "./config.js";
import { a as authenticatedFetch } from "./apiClient.js";
import { c as store_get, b as attr, e as ensure_array_like, u as unsubscribe_stores, a as attr_class, s as stringify } from "./index2.js";
import "./i18n.js";
import { a as $format } from "./runtime.js";
import { e as escape_html } from "./context.js";
async function disableUser(userId) {
  try {
    const response = await authenticatedFetch(getApiUrl(`/admin/users/${userId}/disable`), {
      method: "PUT"
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || error.detail || "Failed to disable user");
    }
    return await response.json();
  } catch (error) {
    console.error("Error disabling user:", error);
    throw error;
  }
}
async function enableUser(userId) {
  try {
    const response = await authenticatedFetch(getApiUrl(`/admin/users/${userId}/enable`), {
      method: "PUT"
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || error.detail || "Failed to enable user");
    }
    return await response.json();
  } catch (error) {
    console.error("Error enabling user:", error);
    throw error;
  }
}
async function disableUsersBulk(userIds) {
  try {
    const response = await authenticatedFetch(getApiUrl("/admin/users/disable-bulk"), {
      method: "POST",
      body: JSON.stringify({ user_ids: userIds })
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || error.detail || "Failed to disable users");
    }
    return await response.json();
  } catch (error) {
    console.error("Error disabling users:", error);
    throw error;
  }
}
async function enableUsersBulk(userIds) {
  try {
    const response = await authenticatedFetch(getApiUrl("/admin/users/enable-bulk"), {
      method: "POST",
      body: JSON.stringify({ user_ids: userIds })
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || error.detail || "Failed to enable users");
    }
    return await response.json();
  } catch (error) {
    console.error("Error enabling users:", error);
    throw error;
  }
}
function UserForm($$renderer, $$props) {
  $$renderer.component(($$renderer2) => {
    var $$store_subs;
    let {
      isOpen = false,
      isSuperAdmin = false,
      newUser,
      organizations = [],
      isLoadingOrganizations = false,
      organizationsError = null,
      isCreating = false,
      error = null,
      success = false,
      localeLoaded = true,
      onSubmit = () => {
      },
      onClose = () => {
      },
      onUserChange = () => {
      }
    } = $$props;
    function handleRoleChange(e) {
      const target = (
        /** @type {HTMLSelectElement} */
        e.target
      );
      if (target.value === "admin") {
        onUserChange({ ...newUser, role: target.value, user_type: "creator" });
      } else {
        onUserChange({ ...newUser, role: target.value });
      }
    }
    function updateField(field, value) {
      onUserChange({ ...newUser, [field]: value });
    }
    if (isOpen) {
      $$renderer2.push("<!--[-->");
      $$renderer2.push(`<div class="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50 flex items-center justify-center" role="dialog" aria-modal="true"><div class="relative mx-auto p-5 border w-full max-w-md shadow-lg rounded-md bg-white"><div class="mt-3 text-center"><h3 class="text-lg leading-6 font-medium text-gray-900">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("admin.users.create.title", { default: "Create New User" }) : "Create New User")}</h3> `);
      if (success) {
        $$renderer2.push("<!--[-->");
        $$renderer2.push(`<div class="mt-4 bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded relative" role="alert"><span class="block sm:inline">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("admin.users.create.success", { default: "User created successfully!" }) : "User created successfully!")}</span></div>`);
      } else {
        $$renderer2.push("<!--[!-->");
        $$renderer2.push(`<form class="mt-4">`);
        if (error) {
          $$renderer2.push("<!--[-->");
          $$renderer2.push(`<div class="mb-4 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative" role="alert"><span class="block sm:inline">${escape_html(error)}</span></div>`);
        } else {
          $$renderer2.push("<!--[!-->");
        }
        $$renderer2.push(`<!--]--> <div class="mb-4 text-left"><label for="email" class="block text-gray-700 text-sm font-bold mb-2">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("admin.users.create.email", { default: "Email" }) : "Email")} *</label> <input type="email" id="email" name="email" class="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline"${attr("value", newUser.email)} required/></div> <div class="mb-4 text-left"><label for="name" class="block text-gray-700 text-sm font-bold mb-2">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("admin.users.create.name", { default: "Name" }) : "Name")} *</label> <input type="text" id="name" name="name" class="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline"${attr("value", newUser.name)} required/></div> <div class="mb-4 text-left"><label for="password" class="block text-gray-700 text-sm font-bold mb-2">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("admin.users.create.password", { default: "Password" }) : "Password")} *</label> <input type="password" id="password" name="password" class="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline"${attr("value", newUser.password)} required/></div> `);
        if (isSuperAdmin) {
          $$renderer2.push("<!--[-->");
          $$renderer2.push(`<div class="mb-4 text-left"><label for="role" class="block text-gray-700 text-sm font-bold mb-2">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("admin.users.create.role", { default: "Role" }) : "Role")}</label> `);
          $$renderer2.select(
            {
              id: "role",
              name: "role",
              class: "shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline",
              value: newUser.role || "user",
              onchange: handleRoleChange
            },
            ($$renderer3) => {
              $$renderer3.option({ value: "user" }, ($$renderer4) => {
                $$renderer4.push(`${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("admin.users.create.roleUser", { default: "User" }) : "User")}`);
              });
              $$renderer3.option({ value: "admin" }, ($$renderer4) => {
                $$renderer4.push(`${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("admin.users.create.roleAdmin", { default: "Admin" }) : "Admin")}`);
              });
            }
          );
          $$renderer2.push(`</div>`);
        } else {
          $$renderer2.push("<!--[!-->");
        }
        $$renderer2.push(`<!--]--> <div class="mb-4 text-left"><label for="user_type" class="block text-gray-700 text-sm font-bold mb-2">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("admin.users.create.userType", { default: "User Type" }) : "User Type")}</label> `);
        $$renderer2.select(
          {
            id: "user_type",
            name: "user_type",
            class: "shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline",
            value: newUser.user_type || "creator",
            onchange: (e) => updateField("user_type", e.target.value),
            disabled: isSuperAdmin && newUser.role === "admin"
          },
          ($$renderer3) => {
            $$renderer3.option({ value: "creator" }, ($$renderer4) => {
              $$renderer4.push(`${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("admin.users.create.typeCreator", { default: "Creator (Can create assistants)" }) : "Creator (Can create assistants)")}`);
            });
            $$renderer3.option({ value: "end_user" }, ($$renderer4) => {
              $$renderer4.push(`${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("admin.users.create.typeEndUser", { default: "End User (Redirects to Open WebUI)" }) : "End User (Redirects to Open WebUI)")}`);
            });
          }
        );
        $$renderer2.push(` `);
        if (isSuperAdmin && newUser.role === "admin") {
          $$renderer2.push("<!--[-->");
          $$renderer2.push(`<p class="text-xs text-gray-500 mt-1">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("admin.users.create.adminAutoCreator", { default: "Admin users are automatically creators" }) : "Admin users are automatically creators")}</p>`);
        } else {
          $$renderer2.push("<!--[!-->");
        }
        $$renderer2.push(`<!--]--></div> `);
        if (isSuperAdmin) {
          $$renderer2.push("<!--[-->");
          $$renderer2.push(`<div class="mb-4 text-left"><label for="organization" class="block text-gray-700 text-sm font-bold mb-2">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("admin.users.create.organization", { default: "Organization" }) : "Organization")}</label> `);
          if (isLoadingOrganizations) {
            $$renderer2.push("<!--[-->");
            $$renderer2.push(`<div class="text-gray-500 text-sm">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("common.loading", { default: "Loading..." }) : "Loading...")}</div>`);
          } else {
            $$renderer2.push("<!--[!-->");
            if (organizationsError) {
              $$renderer2.push("<!--[-->");
              $$renderer2.push(`<div class="text-red-500 text-sm">${escape_html(organizationsError)}</div>`);
            } else {
              $$renderer2.push("<!--[!-->");
              $$renderer2.select(
                {
                  id: "organization",
                  name: "organization_id",
                  class: "shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline",
                  value: newUser.organization_id ?? "",
                  onchange: (e) => {
                    const val = (
                      /** @type {HTMLSelectElement} */
                      e.target.value
                    );
                    updateField("organization_id", val ? parseInt(val, 10) : null);
                  }
                },
                ($$renderer3) => {
                  $$renderer3.option({ value: "" }, ($$renderer4) => {
                    $$renderer4.push(`${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("admin.users.create.selectOrg", { default: "Select an organization (optional)" }) : "Select an organization (optional)")}`);
                  });
                  $$renderer3.push(`<!--[-->`);
                  const each_array = ensure_array_like(organizations);
                  for (let $$index = 0, $$length = each_array.length; $$index < $$length; $$index++) {
                    let org = each_array[$$index];
                    $$renderer3.option({ value: org.id }, ($$renderer4) => {
                      $$renderer4.push(`${escape_html(org.name)} `);
                      if (org.is_system) {
                        $$renderer4.push("<!--[-->");
                        $$renderer4.push(`(System)`);
                      } else {
                        $$renderer4.push("<!--[!-->");
                      }
                      $$renderer4.push(`<!--]-->`);
                    });
                  }
                  $$renderer3.push(`<!--]-->`);
                }
              );
            }
            $$renderer2.push(`<!--]-->`);
          }
          $$renderer2.push(`<!--]--> <p class="text-gray-500 text-xs italic mt-1">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("admin.users.create.orgHelp", {
            default: "If no organization is selected, the user will be assigned to the system organization by default."
          }) : "If no organization is selected, the user will be assigned to the system organization by default.")}</p></div>`);
        } else {
          $$renderer2.push("<!--[!-->");
        }
        $$renderer2.push(`<!--]--> `);
        if (!isSuperAdmin) {
          $$renderer2.push("<!--[-->");
          $$renderer2.push(`<div class="mb-6 text-left"><div class="flex items-center"><input type="checkbox" id="enabled" name="enabled"${attr("checked", newUser.enabled !== false, true)} class="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"/> <label for="enabled" class="ml-2 block text-sm text-gray-900">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("admin.users.create.enabled", { default: "User enabled" }) : "User enabled")}</label></div></div>`);
        } else {
          $$renderer2.push("<!--[!-->");
        }
        $$renderer2.push(`<!--]--> <div class="flex items-center justify-between mt-6"><button type="button" class="bg-gray-300 hover:bg-gray-400 text-gray-800 py-2 px-4 rounded focus:outline-none focus:shadow-outline">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("common.cancel", { default: "Cancel" }) : "Cancel")}</button> <button type="submit" class="bg-brand text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline disabled:opacity-50"${attr("disabled", isCreating, true)}>${escape_html(isCreating ? localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("admin.users.create.creating", { default: "Creating..." }) : "Creating..." : localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("admin.users.create.create", { default: "Create User" }) : "Create User")}</button></div></form>`);
      }
      $$renderer2.push(`<!--]--></div></div></div>`);
    } else {
      $$renderer2.push("<!--[!-->");
    }
    $$renderer2.push(`<!--]-->`);
    if ($$store_subs) unsubscribe_stores($$store_subs);
  });
}
function ChangePasswordModal($$renderer, $$props) {
  $$renderer.component(($$renderer2) => {
    var $$store_subs;
    let {
      isOpen = false,
      userName = "",
      userEmail = "",
      newPassword = "",
      isChanging = false,
      error = null,
      success = false,
      localeLoaded = true,
      onSubmit = () => {
      },
      onClose = () => {
      },
      onPasswordChange = () => {
      }
    } = $$props;
    if (isOpen) {
      $$renderer2.push("<!--[-->");
      $$renderer2.push(`<div class="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50 flex items-center justify-center" role="dialog" aria-modal="true"><div class="relative mx-auto p-5 border w-full max-w-md shadow-lg rounded-md bg-white"><div class="mt-3 text-center"><h3 class="text-lg leading-6 font-medium text-gray-900">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("admin.users.password.title", { default: "Change Password" }) : "Change Password")}</h3> <p class="text-sm text-gray-500 mt-1">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("admin.users.password.subtitle", { default: "Set a new password for" }) : "Set a new password for")} ${escape_html(userName)} `);
      if (userEmail) {
        $$renderer2.push("<!--[-->");
        $$renderer2.push(`<span class="block text-gray-400">(${escape_html(userEmail)})</span>`);
      } else {
        $$renderer2.push("<!--[!-->");
      }
      $$renderer2.push(`<!--]--></p> `);
      if (success) {
        $$renderer2.push("<!--[-->");
        $$renderer2.push(`<div class="mt-4 bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded relative" role="alert"><span class="block sm:inline">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("admin.users.password.success", { default: "Password changed successfully!" }) : "Password changed successfully!")}</span></div>`);
      } else {
        $$renderer2.push("<!--[!-->");
        $$renderer2.push(`<form class="mt-4">`);
        if (error) {
          $$renderer2.push("<!--[-->");
          $$renderer2.push(`<div class="mb-4 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative" role="alert"><span class="block sm:inline">${escape_html(error)}</span></div>`);
        } else {
          $$renderer2.push("<!--[!-->");
        }
        $$renderer2.push(`<!--]--> `);
        if (userEmail) {
          $$renderer2.push("<!--[-->");
          $$renderer2.push(`<div class="mb-4 text-left"><label for="pwd-email" class="block text-gray-700 text-sm font-bold mb-2">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("admin.users.password.email", { default: "Email" }) : "Email")}</label> <input type="email" id="pwd-email" class="shadow appearance-none border rounded w-full py-2 px-3 text-gray-500 bg-gray-100 leading-tight"${attr("value", userEmail)} disabled readonly/></div>`);
        } else {
          $$renderer2.push("<!--[!-->");
        }
        $$renderer2.push(`<!--]--> <div class="mb-6 text-left"><label for="pwd-new-password" class="block text-gray-700 text-sm font-bold mb-2">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("admin.users.password.newPassword", { default: "New Password" }) : "New Password")} *</label> <input type="password" id="pwd-new-password" class="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline"${attr("value", newPassword)} required autocomplete="new-password" minlength="8"/> <p class="text-gray-500 text-xs italic mt-1">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("admin.users.password.hint", { default: "At least 8 characters recommended" }) : "At least 8 characters recommended")}</p></div> <div class="flex items-center justify-between"><button type="button" class="bg-gray-300 hover:bg-gray-400 text-gray-800 py-2 px-4 rounded focus:outline-none focus:shadow-outline">${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("common.cancel", { default: "Cancel" }) : "Cancel")}</button> <button type="submit" class="bg-brand text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline disabled:opacity-50"${attr("disabled", isChanging, true)}>${escape_html(isChanging ? localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("admin.users.password.changing", { default: "Changing..." }) : "Changing..." : localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("admin.users.password.change", { default: "Change Password" }) : "Change Password")}</button></div></form>`);
      }
      $$renderer2.push(`<!--]--></div></div></div>`);
    } else {
      $$renderer2.push("<!--[!-->");
    }
    $$renderer2.push(`<!--]-->`);
    if ($$store_subs) unsubscribe_stores($$store_subs);
  });
}
function UserActionModal($$renderer, $$props) {
  $$renderer.component(($$renderer2) => {
    var $$store_subs;
    let {
      isOpen = false,
      action = "disable",
      isBulk = false,
      targetUser = null,
      selectedCount = 0,
      isProcessing = false,
      error = null,
      localeLoaded = true,
      onConfirm = () => {
      },
      onClose = () => {
      }
    } = $$props;
    const isDisable = action === "disable";
    const iconColor = isDisable ? "text-amber-600" : "text-green-600";
    const iconBgColor = isDisable ? "bg-amber-100" : "bg-green-100";
    const buttonColor = isDisable ? "bg-amber-600 hover:bg-amber-700" : "bg-green-600 hover:bg-green-700";
    if (isOpen) {
      $$renderer2.push("<!--[-->");
      $$renderer2.push(`<div class="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50 flex items-center justify-center" role="dialog" aria-modal="true"><div class="relative mx-auto p-5 border w-full max-w-md shadow-lg rounded-md bg-white"><div class="mt-3"><div${attr_class(`mx-auto flex items-center justify-center h-12 w-12 rounded-full ${stringify(iconBgColor)}`)}>`);
      if (isDisable) {
        $$renderer2.push("<!--[-->");
        $$renderer2.push(`<svg${attr_class(`h-6 w-6 ${stringify(iconColor)}`)} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>`);
      } else {
        $$renderer2.push("<!--[!-->");
        $$renderer2.push(`<svg${attr_class(`h-6 w-6 ${stringify(iconColor)}`)} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>`);
      }
      $$renderer2.push(`<!--]--></div> <h3 class="text-lg leading-6 font-medium text-gray-900 text-center mt-4">`);
      if (isBulk) {
        $$renderer2.push("<!--[-->");
        $$renderer2.push(`${escape_html(isDisable ? localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("admin.users.modal.bulkDisableTitle", { default: "Disable Multiple Users" }) : "Disable Multiple Users" : localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("admin.users.modal.bulkEnableTitle", { default: "Enable Multiple Users" }) : "Enable Multiple Users")}`);
      } else {
        $$renderer2.push("<!--[!-->");
        $$renderer2.push(`${escape_html(isDisable ? localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("admin.users.modal.disableTitle", { default: "Disable User Account" }) : "Disable User Account" : localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("admin.users.modal.enableTitle", { default: "Enable User Account" }) : "Enable User Account")}`);
      }
      $$renderer2.push(`<!--]--></h3> <div class="mt-4 text-center">`);
      if (isBulk) {
        $$renderer2.push("<!--[-->");
        $$renderer2.push(`<p class="text-sm text-gray-600">${escape_html(isDisable ? localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("admin.users.modal.bulkDisableConfirm", {
          default: "Are you sure you want to disable {count} user(s)?",
          values: { count: selectedCount }
        }) : `Are you sure you want to disable ${selectedCount} user(s)?` : localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("admin.users.modal.bulkEnableConfirm", {
          default: "Are you sure you want to enable {count} user(s)?",
          values: { count: selectedCount }
        }) : `Are you sure you want to enable ${selectedCount} user(s)?`)}</p>`);
      } else {
        $$renderer2.push("<!--[!-->");
        if (targetUser) {
          $$renderer2.push("<!--[-->");
          $$renderer2.push(`<p class="text-sm text-gray-600">${escape_html(isDisable ? localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("admin.users.modal.disableConfirm", { default: "Are you sure you want to disable the account for" }) : "Are you sure you want to disable the account for" : localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("admin.users.modal.enableConfirm", { default: "Are you sure you want to enable the account for" }) : "Are you sure you want to enable the account for")}</p> <p class="text-base font-semibold text-gray-900 mt-2">${escape_html(targetUser.name)}</p> <p class="text-sm text-gray-600 mt-1">(${escape_html(targetUser.email)})</p>`);
        } else {
          $$renderer2.push("<!--[!-->");
        }
        $$renderer2.push(`<!--]-->`);
      }
      $$renderer2.push(`<!--]--> <div${attr_class(`mt-4 border-l-4 p-3 rounded ${stringify(isDisable ? "bg-yellow-50 border-yellow-400" : "bg-green-50 border-green-400")}`)}><p class="text-sm text-gray-700">`);
      if (isDisable) {
        $$renderer2.push("<!--[-->");
        $$renderer2.push(`<strong>${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("common.note", { default: "Note" }) : "Note")}:</strong> ${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("admin.users.modal.disableNote", {
          default: "Disabled users will not be able to log in, but their resources (assistants, templates, rubrics) will remain accessible to other users."
        }) : "Disabled users will not be able to log in, but their resources (assistants, templates, rubrics) will remain accessible to other users.")}`);
      } else {
        $$renderer2.push("<!--[!-->");
        $$renderer2.push(`${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("admin.users.modal.enableNote", {
          default: "Enabled users will be able to log in and access the system."
        }) : "Enabled users will be able to log in and access the system.")}`);
      }
      $$renderer2.push(`<!--]--></p></div></div> `);
      if (error) {
        $$renderer2.push("<!--[-->");
        $$renderer2.push(`<div class="mt-4 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative" role="alert"><span class="block sm:inline">${escape_html(error)}</span></div>`);
      } else {
        $$renderer2.push("<!--[!-->");
      }
      $$renderer2.push(`<!--]--> <div class="flex items-center justify-between mt-6 gap-3"><button type="button" class="flex-1 bg-gray-300 hover:bg-gray-400 text-gray-800 font-semibold py-2 px-4 rounded focus:outline-none focus:shadow-outline disabled:opacity-50"${attr("disabled", isProcessing, true)}>${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("common.cancel", { default: "Cancel" }) : "Cancel")}</button> <button type="button"${attr_class(`flex-1 ${stringify(buttonColor)} text-white font-semibold py-2 px-4 rounded focus:outline-none focus:shadow-outline disabled:opacity-50`)}${attr("disabled", isProcessing, true)}>`);
      if (isProcessing) {
        $$renderer2.push("<!--[-->");
        $$renderer2.push(`${escape_html(isDisable ? localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("admin.users.modal.disabling", { default: "Disabling..." }) : "Disabling..." : localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("admin.users.modal.enabling", { default: "Enabling..." }) : "Enabling...")}`);
      } else {
        $$renderer2.push("<!--[!-->");
        $$renderer2.push(`${escape_html(isDisable ? localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("admin.users.modal.disableAction", { default: "Disable" }) : "Disable" : localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("admin.users.modal.enableAction", { default: "Enable" }) : "Enable")} `);
        if (isBulk) {
          $$renderer2.push("<!--[-->");
          $$renderer2.push(`(${escape_html(selectedCount)})`);
        } else {
          $$renderer2.push("<!--[!-->");
        }
        $$renderer2.push(`<!--]-->`);
      }
      $$renderer2.push(`<!--]--></button></div></div></div></div>`);
    } else {
      $$renderer2.push("<!--[!-->");
    }
    $$renderer2.push(`<!--]-->`);
    if ($$store_subs) unsubscribe_stores($$store_subs);
  });
}
export {
  ChangePasswordModal as C,
  UserForm as U,
  UserActionModal as a,
  disableUsersBulk as b,
  enableUsersBulk as c,
  disableUser as d,
  enableUser as e
};
