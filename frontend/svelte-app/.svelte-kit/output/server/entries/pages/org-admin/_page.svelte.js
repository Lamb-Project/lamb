import { h as head, a as attr_class, s as stringify } from "../../../chunks/index2.js";
import { o as onDestroy } from "../../../chunks/index-server.js";
import "@sveltejs/kit/internal";
import "../../../chunks/exports.js";
import "../../../chunks/utils.js";
import "clsx";
import "@sveltejs/kit/internal/server";
import "../../../chunks/state.svelte.js";
import axios from "axios";
import "../../../chunks/userStore.js";
import { a as authenticatedFetch } from "../../../chunks/apiClient.js";
import "../../../chunks/runtime.js";
import "../../../chunks/AssistantSharingModal.svelte_svelte_type_style_lang.js";
import "../../../chunks/i18n.js";
import { C as ConfirmationModal } from "../../../chunks/ConfirmationModal.js";
import { U as UserForm, C as ChangePasswordModal, a as UserActionModal, b as disableUsersBulk, c as enableUsersBulk } from "../../../chunks/UserActionModal.js";
import { p as processListData } from "../../../chunks/listHelpers.js";
function _page($$renderer, $$props) {
  $$renderer.component(($$renderer2) => {
    const API_BASE = "/creator/admin";
    let orgUsers = [];
    let isLoadingUsers = false;
    let usersLoaded = false;
    let usersPage = 1;
    let usersPerPage = 25;
    let usersSearchQuery = "";
    let usersSortBy = "id";
    let usersSortOrder = "asc";
    let selectedUsers = (
      /** @type {number[]} */
      []
    );
    let isCreateUserModalOpen = false;
    let newUser = {
      email: "",
      name: "",
      password: "",
      enabled: void 0,
      user_type: ""
      // 'creator' or 'end_user'
    };
    let isCreatingUser = false;
    let createUserError = null;
    let createUserSuccess = false;
    let isChangePasswordModalOpen = false;
    let passwordChangeData = {
      user_id: null,
      user_name: "",
      user_email: "",
      new_password: ""
    };
    let isChangingPassword = false;
    let changePasswordError = null;
    let changePasswordSuccess = false;
    let isDeleteUserModalOpen = false;
    let userToDelete = null;
    let isDeletingUser = false;
    let deleteUserError = null;
    let showSingleUserDisableModal = false;
    let showSingleUserEnableModal = false;
    let userToToggle = null;
    let isTogglingUser = false;
    let toggleUserError = null;
    let isBulkDisableModalOpen = false;
    let isBulkEnableModalOpen = false;
    let isBulkProcessing = false;
    let bulkActionError = null;
    let kbSettings = {
      url: "",
      api_key_set: false,
      embedding_model: "",
      collection_defaults: {}
    };
    let newKbSettings = {
      url: "",
      api_key: "",
      embedding_model: "",
      embedding_api_key: "",
      collection_defaults: { chunk_size: 1e3, chunk_overlap: 200 }
    };
    let kbSettingsSuccess = false;
    let kbEmbeddingsConfig = {
      vendor: "",
      model: "",
      api_endpoint: "",
      apikey_configured: false,
      apikey_masked: "",
      config_source: "env"
    };
    let applyToAllKbResult = null;
    let applyToAllKbChecked = false;
    let embeddingApiKeyOriginal = "";
    let embeddingApiKeyDirty = false;
    let showResetKbConfigModal = false;
    let targetOrgSlug = null;
    let pendingChanges = [];
    function addPendingChange(description) {
      if (!pendingChanges.includes(description)) {
        pendingChanges = [...pendingChanges, description];
      }
    }
    function getAuthToken() {
      {
        console.error("No authentication token available. User must be logged in.");
        return null;
      }
    }
    function getApiUrl(endpoint) {
      return `${API_BASE}${endpoint}`;
    }
    async function fetchUsers() {
      if (isLoadingUsers) {
        console.log("Already loading users, skipping duplicate request");
        return;
      }
      console.log("Fetching organization users...");
      isLoadingUsers = true;
      try {
        const token = getAuthToken();
        if (!token) {
          throw new Error("Authentication token not found. Please log in again.");
        }
        const apiUrl = targetOrgSlug ? getApiUrl(`/org-admin/users?org=${targetOrgSlug}`) : getApiUrl("/org-admin/users");
        console.log(`Fetching users from: ${apiUrl}`);
        const response = await axios.get(apiUrl, { headers: { "Authorization": `Bearer ${token}` } });
        console.log("Users API Response:", response.data);
        orgUsers = response.data || [];
        console.log(`Fetched ${orgUsers.length} users`);
        usersLoaded = true;
        applyUsersFilters();
      } catch (err) {
        console.error("Error fetching users:", err);
        if (axios.isAxiosError(err) && err.response?.status === 403) ;
        else if (axios.isAxiosError(err) && err.response?.data?.detail) {
          err.response.data.detail;
        } else if (err instanceof Error) {
          err.message;
        } else ;
        orgUsers = [];
        usersLoaded = true;
      } finally {
        isLoadingUsers = false;
      }
    }
    function applyUsersFilters() {
      const filters = {};
      let result = processListData(orgUsers, {
        search: usersSearchQuery,
        searchFields: ["name", "email"],
        filters,
        sortBy: usersSortBy,
        sortOrder: usersSortOrder,
        page: usersPage,
        itemsPerPage: usersPerPage
      });
      result.items.map((u) => ({ ...u, selected: selectedUsers.includes(u.id) }));
      result.filteredCount;
      result.totalPages;
      usersPage = result.currentPage;
    }
    async function confirmToggleUserEnable() {
      if (!userToToggle) return;
      isTogglingUser = true;
      toggleUserError = null;
      try {
        const token = getAuthToken();
        if (!token) {
          throw new Error("Authentication token not found. Please log in again.");
        }
        const apiUrl = getApiUrl(`/org-admin/users/${userToToggle.id}`);
        console.log(`Enabling user ${userToToggle.email} at: ${apiUrl}`);
        const response = await axios.put(apiUrl, { enabled: true }, {
          headers: {
            "Authorization": `Bearer ${token}`,
            "Content-Type": "application/json"
          }
        });
        console.log("User enable response:", response.data);
        const userIndex = orgUsers.findIndex((u) => u.id === userToToggle.id);
        if (userIndex !== -1) {
          orgUsers[userIndex].enabled = true;
          orgUsers = [...orgUsers];
        }
        showSingleUserEnableModal = false;
        userToToggle = null;
      } catch (err) {
        console.error("Error enabling user:", err);
        let errorMessage = "Failed to enable user.";
        if (axios.isAxiosError(err) && err.response?.data?.detail) {
          errorMessage = err.response.data.detail;
        } else if (err instanceof Error) {
          errorMessage = err.message;
        }
        toggleUserError = errorMessage;
      } finally {
        isTogglingUser = false;
      }
    }
    async function confirmToggleUserDisable() {
      if (!userToToggle) return;
      isTogglingUser = true;
      toggleUserError = null;
      try {
        const token = getAuthToken();
        if (!token) {
          throw new Error("Authentication token not found. Please log in again.");
        }
        const apiUrl = getApiUrl(`/org-admin/users/${userToToggle.id}`);
        console.log(`Disabling user ${userToToggle.email} at: ${apiUrl}`);
        const response = await axios.put(apiUrl, { enabled: false }, {
          headers: {
            "Authorization": `Bearer ${token}`,
            "Content-Type": "application/json"
          }
        });
        console.log("User disable response:", response.data);
        const userIndex = orgUsers.findIndex((u) => u.id === userToToggle.id);
        if (userIndex !== -1) {
          orgUsers[userIndex].enabled = false;
          orgUsers = [...orgUsers];
        }
        showSingleUserDisableModal = false;
        userToToggle = null;
      } catch (err) {
        console.error("Error disabling user:", err);
        let errorMessage = "Failed to disable user.";
        if (axios.isAxiosError(err) && err.response?.data?.detail) {
          errorMessage = err.response.data.detail;
        } else if (err instanceof Error) {
          errorMessage = err.message;
        }
        toggleUserError = errorMessage;
      } finally {
        isTogglingUser = false;
      }
    }
    function closeSingleUserModal() {
      showSingleUserDisableModal = false;
      showSingleUserEnableModal = false;
      userToToggle = null;
      toggleUserError = null;
    }
    function closeBulkDisableModal() {
      isBulkDisableModalOpen = false;
      bulkActionError = null;
    }
    function closeBulkEnableModal() {
      isBulkEnableModalOpen = false;
      bulkActionError = null;
    }
    async function confirmBulkDisable() {
      if (selectedUsers.length === 0) return;
      isBulkProcessing = true;
      bulkActionError = null;
      try {
        const result = await disableUsersBulk(selectedUsers);
        if (result.success) {
          console.log(`Bulk disable: ${result.disabled} users disabled`);
          await fetchUsers();
          selectedUsers = [];
          closeBulkDisableModal();
        } else {
          throw new Error(result.message || "Bulk disable failed");
        }
      } catch (err) {
        console.error("Error in bulk disable:", err);
        bulkActionError = err instanceof Error ? err.message : "Failed to disable users";
      } finally {
        isBulkProcessing = false;
      }
    }
    async function confirmBulkEnable() {
      if (selectedUsers.length === 0) return;
      isBulkProcessing = true;
      bulkActionError = null;
      try {
        const token = getAuthToken();
        if (!token) {
          throw new Error("Authentication token not found");
        }
        const result = await enableUsersBulk(token, selectedUsers);
        if (result.success) {
          console.log(`Bulk enable: ${result.enabled} users enabled`);
          await fetchUsers();
          selectedUsers = [];
          closeBulkEnableModal();
        } else {
          throw new Error(result.message || "Bulk enable failed");
        }
      } catch (err) {
        console.error("Error in bulk enable:", err);
        bulkActionError = err instanceof Error ? err.message : "Failed to enable users";
      } finally {
        isBulkProcessing = false;
      }
    }
    function closeDeleteUserModal() {
      isDeleteUserModalOpen = false;
      userToDelete = null;
      deleteUserError = null;
      isDeletingUser = false;
    }
    async function confirmDeleteUser() {
      if (!userToDelete) return;
      isDeletingUser = true;
      deleteUserError = null;
      try {
        const token = getAuthToken();
        if (!token) {
          throw new Error("Authentication token not found. Please log in again.");
        }
        const apiUrl = getApiUrl(`/org-admin/users/${userToDelete.id}`);
        console.log(`Disabling user ${userToDelete.email} at: ${apiUrl}`);
        const response = await axios.put(apiUrl, { enabled: false }, {
          headers: {
            "Authorization": `Bearer ${token}`,
            "Content-Type": "application/json"
          }
        });
        console.log("User disable response:", response.data);
        const userIndex = orgUsers.findIndex((u) => u.id === userToDelete.id);
        if (userIndex !== -1) {
          orgUsers[userIndex].enabled = false;
          orgUsers = [...orgUsers];
          applyUsersFilters();
        }
        closeDeleteUserModal();
      } catch (err) {
        console.error("Error disabling user:", err);
        let errorMessage = "Failed to disable user.";
        if (axios.isAxiosError(err) && err.response?.data?.detail) {
          errorMessage = err.response.data.detail;
        } else if (err instanceof Error) {
          errorMessage = err.message;
        }
        deleteUserError = errorMessage;
      } finally {
        isDeletingUser = false;
      }
    }
    function closeCreateUserModal() {
      isCreateUserModalOpen = false;
      createUserError = null;
      createUserSuccess = false;
    }
    function closeChangePasswordModal() {
      isChangePasswordModalOpen = false;
      changePasswordError = null;
      changePasswordSuccess = false;
    }
    async function handleChangePassword(e) {
      e.preventDefault();
      if (!passwordChangeData.new_password) {
        changePasswordError = "Please enter a new password.";
        return;
      }
      if (passwordChangeData.new_password.length < 8) {
        changePasswordError = "Password should be at least 8 characters.";
        return;
      }
      changePasswordError = null;
      isChangingPassword = true;
      try {
        const apiUrl = getApiUrl(`/org-admin/users/${passwordChangeData.user_id}/password`);
        console.log(`Changing password for user ${passwordChangeData.user_email} at: ${apiUrl}`);
        const response = await authenticatedFetch(apiUrl, {
          method: "POST",
          body: JSON.stringify({ new_password: passwordChangeData.new_password })
        });
        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || "Failed to change password");
        }
        const data = await response.json();
        console.log("Change password response:", data);
        changePasswordSuccess = true;
        setTimeout(
          () => {
            closeChangePasswordModal();
          },
          1500
        );
      } catch (err) {
        console.error("Error changing password:", err);
        let errorMessage = "Failed to change password.";
        if (err instanceof Error) {
          errorMessage = err.message;
        }
        changePasswordError = errorMessage;
      } finally {
        isChangingPassword = false;
      }
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
      const userType = (
        /** @type {string} */
        (formDataObj.get("user_type") || "creator").toString()
      );
      const enabled = formDataObj.get("enabled") === "on";
      if (!email || !name || !password) {
        createUserError = "Please fill in all required fields.";
        return;
      }
      if (!email.includes("@")) {
        createUserError = "Please enter a valid email address.";
        return;
      }
      createUserError = null;
      isCreatingUser = true;
      try {
        const token = getAuthToken();
        if (!token) {
          throw new Error("Authentication token not found. Please log in again.");
        }
        const apiUrl = getApiUrl("/org-admin/users");
        console.log(`Creating user at: ${apiUrl}`);
        const response = await axios.post(apiUrl, { email, name, password, enabled, user_type: userType }, {
          headers: {
            "Authorization": `Bearer ${token}`,
            "Content-Type": "application/json"
          }
        });
        console.log("Create user response:", response.data);
        createUserSuccess = true;
        setTimeout(
          () => {
            closeCreateUserModal();
            fetchUsers();
          },
          1500
        );
      } catch (err) {
        console.error("Error creating user:", err);
        if (axios.isAxiosError(err) && err.response?.status === 403) {
          createUserError = "Access denied. Organization admin privileges required.";
        } else if (axios.isAxiosError(err) && err.response?.data?.detail) {
          createUserError = err.response.data.detail;
        } else if (err instanceof Error) {
          createUserError = err.message;
        } else {
          createUserError = "An unknown error occurred while creating user.";
        }
      } finally {
        isCreatingUser = false;
      }
    }
    async function fetchKbEmbeddingsConfig() {
      try {
        if (!kbSettings.url) {
          kbEmbeddingsConfig = {
            vendor: "",
            model: "",
            api_endpoint: "",
            apikey_configured: false,
            apikey_masked: "",
            config_source: "env"
          };
          return;
        }
        const token = getAuthToken();
        if (!token) {
          throw new Error("Authentication token not found");
        }
        const params = targetOrgSlug ? `?org=${targetOrgSlug}` : "";
        const response = await axios.get(getApiUrl(`/org-admin/settings/kb/embeddings-config${params}`), {
          headers: {
            "Authorization": `Bearer ${token}`,
            "Content-Type": "application/json"
          }
        });
        kbEmbeddingsConfig = response.data;
        if (kbEmbeddingsConfig.apikey_configured && kbEmbeddingsConfig.apikey_masked) {
          newKbSettings.embedding_api_key = kbEmbeddingsConfig.apikey_masked;
          embeddingApiKeyOriginal = kbEmbeddingsConfig.apikey_masked;
        } else {
          newKbSettings.embedding_api_key = "";
          embeddingApiKeyOriginal = "";
        }
        embeddingApiKeyDirty = false;
        applyToAllKbChecked = false;
      } catch (err) {
        console.error("Error fetching KB embeddings config:", err);
        kbEmbeddingsConfig = {
          vendor: "",
          model: "",
          api_endpoint: "",
          apikey_configured: false,
          apikey_masked: "",
          config_source: "env"
        };
      } finally {
      }
    }
    async function updateKbEmbeddingsConfig({ applyToAll = false } = {}) {
      try {
        if (!newKbSettings.url && !kbSettings.url) {
          throw new Error("KB server URL is not configured");
        }
        const token = getAuthToken();
        if (!token) {
          throw new Error("Authentication token not found. Please log in again.");
        }
        const payload = {};
        if (newKbSettings.embedding_api_key && newKbSettings.embedding_api_key !== kbEmbeddingsConfig.apikey_masked) {
          payload.apikey = newKbSettings.embedding_api_key;
          if (applyToAll) {
            payload.apply_to_all_kb = true;
          }
        }
        if (kbEmbeddingsConfig.vendor) {
          payload.vendor = kbEmbeddingsConfig.vendor;
        }
        if (kbEmbeddingsConfig.model) {
          payload.model = kbEmbeddingsConfig.model;
        }
        if (kbEmbeddingsConfig.api_endpoint) {
          payload.api_endpoint = kbEmbeddingsConfig.api_endpoint;
        }
        const params = targetOrgSlug ? `?org=${targetOrgSlug}` : "";
        const response = await axios.put(getApiUrl(`/org-admin/settings/kb/embeddings-config${params}`), payload, {
          headers: {
            "Authorization": `Bearer ${token}`,
            "Content-Type": "application/json"
          }
        });
        await fetchKbEmbeddingsConfig();
        if (response.data?.bulk_update) {
          const bulk = response.data.bulk_update;
          applyToAllKbResult = `Updated ${bulk.updated} of ${bulk.total} collections`;
        } else {
          applyToAllKbResult = null;
        }
        kbSettingsSuccess = true;
        if (response.data?.bulk_update) {
          const bulkResult = response.data.bulk_update;
          const message = `KB server embeddings configuration updated. ` + (bulkResult.updated > 0 ? `Applied new API key to ${bulkResult.updated} of ${bulkResult.total} knowledge base collections.` : "No existing collections needed updating.");
          addPendingChange(message);
        } else {
          addPendingChange("KB server embeddings configuration updated");
        }
        applyToAllKbChecked = false;
        setTimeout(
          () => {
            kbSettingsSuccess = false;
          },
          3e3
        );
      } catch (err) {
        console.error("Error updating KB embeddings config:", err);
        if (axios.isAxiosError(err) && err.response?.data?.detail) {
          err.response.data.detail;
        } else if (err instanceof Error) {
          err.message;
        } else ;
      } finally {
      }
    }
    onDestroy(() => {
      console.log("Organization admin page unmounting");
    });
    let $$settled = true;
    let $$inner_renderer;
    function $$render_inner($$renderer3) {
      head("ra63b7", $$renderer3, ($$renderer4) => {
        $$renderer4.title(($$renderer5) => {
          $$renderer5.push(`<title>Organization Admin - LAMB</title>`);
        });
      });
      $$renderer3.push(`<div class="min-h-screen bg-gray-50"><nav class="bg-white shadow-sm border-b border-gray-200"><div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8"><div class="flex justify-between h-16"><div class="flex"><div class="flex-shrink-0 flex items-center"><h1 class="text-xl font-semibold text-gray-800">Organization Admin</h1></div> <div class="ml-6 flex space-x-8"><button${attr_class(`inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium transition-colors duration-200 ${stringify(
        "border-[#2271b3] text-[#2271b3]"
      )}`)}>Dashboard</button> <button${attr_class(`inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium transition-colors duration-200 ${stringify("border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300")}`)}>Users</button> <button${attr_class(`inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium transition-colors duration-200 ${stringify("border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300")}`)}>Assistants Access</button> <button${attr_class(`inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium transition-colors duration-200 ${stringify("border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300")}`)}>LTI Activities</button> <button${attr_class(`inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium transition-colors duration-200 ${stringify("border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300")}`)}>Settings</button></div></div></div></div></nav> <main class="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8"><div class="px-4 py-6 sm:px-0">`);
      {
        $$renderer3.push("<!--[!-->");
      }
      $$renderer3.push(`<!--]--> `);
      {
        $$renderer3.push("<!--[-->");
        $$renderer3.push(`<div class="mb-6">`);
        {
          $$renderer3.push("<!--[!-->");
        }
        $$renderer3.push(`<!--]--> `);
        {
          $$renderer3.push("<!--[!-->");
          {
            $$renderer3.push("<!--[!-->");
          }
          $$renderer3.push(`<!--]-->`);
        }
        $$renderer3.push(`<!--]--></div>`);
      }
      $$renderer3.push(`<!--]--> `);
      {
        $$renderer3.push("<!--[!-->");
      }
      $$renderer3.push(`<!--]--> `);
      {
        $$renderer3.push("<!--[!-->");
      }
      $$renderer3.push(`<!--]--> `);
      {
        $$renderer3.push("<!--[!-->");
      }
      $$renderer3.push(`<!--]--> `);
      {
        $$renderer3.push("<!--[!-->");
      }
      $$renderer3.push(`<!--]--></div></main></div> `);
      {
        $$renderer3.push("<!--[!-->");
      }
      $$renderer3.push(`<!--]--> `);
      UserForm($$renderer3, {
        isOpen: isCreateUserModalOpen,
        isSuperAdmin: false,
        newUser,
        isCreating: isCreatingUser,
        error: createUserError,
        success: createUserSuccess,
        onSubmit: handleCreateUser,
        onClose: closeCreateUserModal,
        onUserChange: (user) => {
          newUser = user;
        }
      });
      $$renderer3.push(`<!----> `);
      ChangePasswordModal($$renderer3, {
        isOpen: isChangePasswordModalOpen,
        userName: passwordChangeData.user_name,
        userEmail: passwordChangeData.user_email,
        newPassword: passwordChangeData.new_password,
        isChanging: isChangingPassword,
        error: changePasswordError,
        success: changePasswordSuccess,
        onSubmit: handleChangePassword,
        onClose: closeChangePasswordModal,
        onPasswordChange: (pwd) => {
          passwordChangeData.new_password = pwd;
        }
      });
      $$renderer3.push(`<!----> `);
      UserActionModal($$renderer3, {
        isOpen: isDeleteUserModalOpen && userToDelete !== null,
        action: "disable",
        isBulk: false,
        targetUser: userToDelete,
        isProcessing: isDeletingUser,
        error: deleteUserError,
        onConfirm: confirmDeleteUser,
        onClose: closeDeleteUserModal
      });
      $$renderer3.push(`<!----> `);
      UserActionModal($$renderer3, {
        isOpen: showSingleUserDisableModal && userToToggle !== null,
        action: "disable",
        isBulk: false,
        targetUser: userToToggle,
        isProcessing: isTogglingUser,
        error: toggleUserError,
        onConfirm: confirmToggleUserDisable,
        onClose: closeSingleUserModal
      });
      $$renderer3.push(`<!----> `);
      UserActionModal($$renderer3, {
        isOpen: showSingleUserEnableModal && userToToggle !== null,
        action: "enable",
        isBulk: false,
        targetUser: userToToggle,
        isProcessing: isTogglingUser,
        error: toggleUserError,
        onConfirm: confirmToggleUserEnable,
        onClose: closeSingleUserModal
      });
      $$renderer3.push(`<!----> `);
      UserActionModal($$renderer3, {
        isOpen: isBulkDisableModalOpen,
        action: "disable",
        isBulk: true,
        selectedCount: selectedUsers.length,
        isProcessing: isBulkProcessing,
        error: bulkActionError,
        onConfirm: confirmBulkDisable,
        onClose: closeBulkDisableModal
      });
      $$renderer3.push(`<!----> `);
      UserActionModal($$renderer3, {
        isOpen: isBulkEnableModalOpen,
        action: "enable",
        isBulk: true,
        selectedCount: selectedUsers.length,
        isProcessing: isBulkProcessing,
        error: bulkActionError,
        onConfirm: confirmBulkEnable,
        onClose: closeBulkEnableModal
      });
      $$renderer3.push(`<!----> `);
      {
        $$renderer3.push("<!--[!-->");
      }
      $$renderer3.push(`<!--]--> `);
      {
        $$renderer3.push("<!--[!-->");
      }
      $$renderer3.push(`<!--]--> `);
      ConfirmationModal($$renderer3, {
        title: "Reset KB Configuration",
        message: "Reset to environment variables? This will remove the persisted configuration and use the defaults from your environment settings.",
        confirmText: "Reset",
        variant: "warning",
        onconfirm: async () => {
          await updateKbEmbeddingsConfig();
          showResetKbConfigModal = false;
        },
        oncancel: () => {
          showResetKbConfigModal = false;
        },
        get isOpen() {
          return showResetKbConfigModal;
        },
        set isOpen($$value) {
          showResetKbConfigModal = $$value;
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
  });
}
export {
  _page as default
};
