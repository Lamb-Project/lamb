<script>
    import { onMount, onDestroy } from 'svelte';
    import { page } from '$app/stores';
    import { goto } from '$app/navigation';
    import { base } from '$app/paths';
    import axios from 'axios';
    import { user } from '$lib/stores/userStore';
    import AssistantSharingModal from '$lib/components/assistants/AssistantSharingModal.svelte';
    import Pagination from '$lib/components/common/Pagination.svelte';
    import ConfirmationModal from '$lib/components/modals/ConfirmationModal.svelte';
    // BulkUserImport component not yet implemented
    // import BulkUserImport from '$lib/components/admin/BulkUserImport.svelte';
    import * as adminService from '$lib/services/adminService';
    import { processListData } from '$lib/utils/listHelpers';
    import { getLambApiUrl } from '$lib/config';

    // Get user data  
    /** @type {any} */
    let userData = $state(null);

    // API base URL
    const API_BASE = '/creator/admin';

    // State variables
    let currentView = $state('dashboard');
    let isLoading = $state(false);
    /** @type {string | null} */
    let error = $state(null);

    // Assistants management state
    /** @type {any[]} */
    let orgAssistants = $state([]);
    let isLoadingAssistants = $state(false);
    let assistantsLoaded = $state(false); // Track if assistants have been loaded at least once
    /** @type {string | null} */
    let assistantsError = $state(null);
    let assistantsSearchQuery = $state('');
    let assistantsFilterPublished = $state('all');
    
    // Assistant sharing state
    let assistantShareCounts = $state({}); // Map of assistant_id -> share count
    let showSharingModal = $state(false);
    let modalAssistant = $state(null); // Assistant being shared in modal

    // Dashboard data
    /** @type {any} */
    let dashboardData = $state(null);
    let isLoadingDashboard = $state(false);

    // User management state
    /** @type {any[]} */
    let orgUsers = $state([]); // All users (unfiltered)
    /** @type {any[]} */
    let displayUsers = $state([]); // Filtered/paginated users for display
    let isLoadingUsers = $state(false);
    let usersLoaded = $state(false); // Track if users have been loaded at least once
    /** @type {string | null} */
    let usersError = $state(null);
    
    // Pagination state for users
    let usersPage = $state(1);
    let usersPerPage = $state(25);
    let usersTotalPages = $state(1);
    let usersTotalItems = $state(0);
    
    // Filter state for users
    let usersSearchQuery = $state('');
    let usersFilterUserType = $state('all'); // 'all', 'creator', 'end_user'
    let usersFilterStatus = $state('all'); // 'all', 'enabled', 'disabled'
    let usersSortBy = $state('id'); // 'id', 'name', 'email'
    let usersSortOrder = $state('asc'); // 'asc', 'desc'
    
    // Bulk selection state
    let selectedUsers = $state(/** @type {number[]} */ ([]));

    // Create user modal state
    let isCreateUserModalOpen = $state(false);
    let newUser = $state({
        email: '',
        name: '',
        password: '',
        enabled: undefined,
        user_type: '' // 'creator' or 'end_user'
    });
    let isCreatingUser = $state(false);
    /** @type {string | null} */
    let createUserError = $state(null);
    let createUserSuccess = $state(false);

    // Change password modal state
    let isChangePasswordModalOpen = $state(false);
    let passwordChangeData = $state({
        user_id: null,
        user_name: '',
        user_email: '',
        new_password: ''
    });
    let isChangingPassword = $state(false);
    /** @type {string | null} */
    let changePasswordError = $state(null);
    let changePasswordSuccess = $state(false);

    // Delete user modal state (now used for disable)
    let isDeleteUserModalOpen = $state(false);
    let userToDelete = $state(null);
    let isDeletingUser = $state(false);
    /** @type {string | null} */
    let deleteUserError = $state(null);
    
    // Bulk enable/disable modal states
    let isBulkDisableModalOpen = $state(false);
    let isBulkEnableModalOpen = $state(false);
    let isBulkProcessing = $state(false);
    /** @type {string | null} */
    let bulkActionError = $state(null);

    // Settings state
    /** @type {any} */
    let signupSettings = $state({
        signup_enabled: false,
        signup_key: '',
        signup_key_masked: false
    });
    /** @type {any} */
    let apiSettings = $state({
        openai_api_key_set: false,
        openai_base_url: 'https://api.openai.com/v1',
        ollama_base_url: 'http://localhost:11434',
        available_models: [],
        model_limits: {},
        api_endpoints: {}
    });
    let isLoadingSettings = $state(false);
    /** @type {string | null} */
    let settingsError = $state(null);
    
    // Signup settings specific errors and success
    /** @type {string | null} */
    let signupSettingsError = $state(null);
    let signupSettingsSuccess = $state(false);
    
    // Assistant defaults (org-scoped)
    /** @type {any} */
    let assistantDefaults = $state(null);
    /** @type {string} */
    let assistantDefaultsJson = $state('');
    let isLoadingAssistantDefaults = $state(false);
    /** @type {string | null} */
    let assistantDefaultsError = $state(null);
    let assistantDefaultsSuccess = $state(false);
    const assistantDefaultsPlaceholder = '{"connector":"openai","llm":"gpt-4o-mini","system_prompt":"..."}';

    // Settings sub-view navigation
    let settingsSubView = $state('general');

    // New settings for editing
    /** @type {any} */
    let newSignupSettings = $state({
        signup_enabled: false,
        signup_key: ''
    });
    /** @type {any} */
    let newApiSettings = $state({
        openai_api_key: '',
        openai_base_url: '',
        ollama_base_url: '',
        available_models: [],
        model_limits: {},
        selected_models: {},
        default_models: {},
        global_default_model: {provider: '', model: ''},
        small_fast_model: {provider: '', model: ''}
    });

    // KB settings state
    /** @type {any} */
    let kbSettings = $state({
        url: '',
        api_key_set: false,
        embedding_model: '',
        collection_defaults: {}
    });
    /** @type {any} */
    let newKbSettings = $state({
        url: '',
        api_key: '',
        embedding_model: '',
        embedding_api_key: '',
        collection_defaults: {
            chunk_size: 1000,
            chunk_overlap: 200
        }
    });
    let isLoadingKbSettings = $state(false);
    /** @type {string | null} */
    let kbSettingsError = $state(null);
    let kbSettingsSuccess = $state(false);
    /** @type {any} */
    let kbTestResult = $state(null);
    let isTesting = $state(false);
    /** @type {boolean} */
    let showKbAdvanced = $state(false);
    /** @type {boolean} */
    let showKbApiKey = $state(false);
    /** @type {boolean} */
    let showEmbeddingApiKey = $state(false);
    
    // KB server embeddings config state
    /** @type {any} */
    let kbEmbeddingsConfig = $state({
        vendor: '',
        model: '',
        api_endpoint: '',
        apikey_configured: false,
        apikey_masked: '',
        config_source: 'env'
    });
    let isLoadingKbEmbeddingsConfig = $state(false);
    /** @type {string | null} */
    let kbEmbeddingsConfigError = $state(null);
    let isUpdatingKbEmbeddingsConfig = $state(false);
    let showApplyToAllKbConfirmation = $state(false);
    let isApplyingToAllKb = $state(false);
    /** @type {string | null} */
    let applyToAllKbResult = $state(null);
    let applyToAllKbChecked = $state(false);
    let embeddingApiKeyOriginal = $state('');
    let embeddingApiKeyDirty = $state(false);
    
    // Reset KB embeddings config modal state
    let showResetKbConfigModal = $state(false);

    // Model selection modal state
    let isModelModalOpen = $state(false);
    /** @type {string} */
    let modalProviderName = $state('');
    /** @type {string[]} */
    let modalAvailableModels = $state([]);
    /** @type {string[]} */
    let modalEnabledModels = $state([]);
    /** @type {string[]} */
    let modalDisabledModels = $state([]);
    /** @type {string[]} */
    let selectedEnabledModels = $state([]);
    /** @type {string[]} */
    let selectedDisabledModels = $state([]);
    let enabledSearchTerm = $state('');
    let disabledSearchTerm = $state('');

    // Signup key display state
    let signupKey = $state('');
    let showSignupKey = $state(false);

    // Target organization for system admin
    let targetOrgSlug = $state(null);

    // Change tracking for better UX
    let hasUnsavedChanges = $state(false);
    let pendingChanges = $state([]);

    // Model selection modal functions
    function openModelModal(providerName, availableModels) {
        modalProviderName = providerName;
        modalAvailableModels = [...availableModels];
        
        // Initialize enabled and disabled model lists
        const currentlyEnabled = newApiSettings.selected_models?.[providerName] || [];
        modalEnabledModels = [...currentlyEnabled];
        modalDisabledModels = availableModels.filter(model => !currentlyEnabled.includes(model));
        
        // Clear selections and search terms
        selectedEnabledModels = [];
        selectedDisabledModels = [];
        enabledSearchTerm = '';
        disabledSearchTerm = '';
        
        isModelModalOpen = true;
    }
    
    function closeModelModal() {
        isModelModalOpen = false;
    }
    
    function saveModelSelection() {
        // Update the main settings with the modal selections
        if (!newApiSettings.selected_models) {
            newApiSettings.selected_models = {};
        }
        newApiSettings.selected_models[modalProviderName] = [...modalEnabledModels];
        newApiSettings.selected_models = { ...newApiSettings.selected_models };

        // Ensure default model is valid after model changes
        if (!newApiSettings.default_models) {
            newApiSettings.default_models = {};
        }

        const currentDefault = newApiSettings.default_models[modalProviderName] || "";
        const enabledModels = newApiSettings.selected_models[modalProviderName] || [];

        if (currentDefault && !enabledModels.includes(currentDefault)) {
            // Current default is not in enabled models
            if (enabledModels.length > 0) {
                // Auto-select first enabled model as default
                newApiSettings.default_models[modalProviderName] = enabledModels[0];
                addPendingChange(`Default model auto-corrected for ${modalProviderName}`);
            } else {
                // No models enabled, clear default
                newApiSettings.default_models[modalProviderName] = "";
            }
        } else if (!currentDefault && enabledModels.length > 0) {
            // No default set but models are enabled, auto-select first one
            newApiSettings.default_models[modalProviderName] = enabledModels[0];
            addPendingChange(`Default model set for ${modalProviderName}`);
        }

        // Ensure default_models is reactive
        newApiSettings.default_models = { ...newApiSettings.default_models };

        // Track this as a pending change
        addPendingChange(`Model selection updated for ${modalProviderName}`);
        closeModelModal();
    }

    // Change tracking functions
    function addPendingChange(description) {
        if (!pendingChanges.includes(description)) {
            pendingChanges = [...pendingChanges, description];
        }
        hasUnsavedChanges = true;
    }

    function clearPendingChanges() {
        pendingChanges = [];
        hasUnsavedChanges = false;
    }
    
    // Transfer functions for the modal
    function moveAllToEnabled() {
        modalEnabledModels = [...modalEnabledModels, ...modalDisabledModels];
        modalDisabledModels = [];
        selectedDisabledModels = [];
    }
    
    function moveSelectedToEnabled() {
        modalEnabledModels = [...modalEnabledModels, ...selectedDisabledModels];
        modalDisabledModels = modalDisabledModels.filter(model => !selectedDisabledModels.includes(model));
        selectedDisabledModels = [];
    }
    
    function moveSelectedToDisabled() {
        modalDisabledModels = [...modalDisabledModels, ...selectedEnabledModels];
        modalEnabledModels = modalEnabledModels.filter(model => !selectedEnabledModels.includes(model));
        selectedEnabledModels = [];
    }
    
    function moveAllToDisabled() {
        modalDisabledModels = [...modalDisabledModels, ...modalEnabledModels];
        modalEnabledModels = [];
        selectedEnabledModels = [];
    }

    // Helper functions
    function getAuthToken() {
        if (!userData || !userData.isLoggedIn || !userData.token) {
            console.error("No authentication token available. User must be logged in.");
            return null;
        }
        return userData.token;
    }

    /**
     * @param {string} endpoint
     */
    function getApiUrl(endpoint) {
        return `${API_BASE}${endpoint}`;
    }

    // Navigation functions
    function showDashboard() {
        currentView = 'dashboard';
        goto(`${base}/org-admin?view=dashboard`, { replaceState: true });
        fetchDashboard();
    }

    function showUsers() {
        currentView = 'users';
        goto(`${base}/org-admin?view=users`, { replaceState: true });
        fetchUsers();
    }

    function showAssistants() {
        currentView = 'assistants';
        goto(`${base}/org-admin?view=assistants`, { replaceState: true });
        fetchAssistants();
    }

    function showSettings() {
        currentView = 'settings';
        goto(`${base}/org-admin?view=settings`, { replaceState: true });
        fetchSettings();
    }

    function showBulkImport() {
        currentView = 'bulk-import';
        goto(`${base}/org-admin?view=bulk-import`, { replaceState: true });
    }

    // Dashboard functions
    async function fetchDashboard() {
        if (isLoadingDashboard) {
            console.log("Already loading dashboard, skipping duplicate request");
            return;
        }

        console.log("Fetching organization dashboard...");
        isLoadingDashboard = true;
        error = null;

        try {
            const token = getAuthToken();
            if (!token) {
                throw new Error('Authentication token not found. Please log in again.');
            }

            const apiUrl = targetOrgSlug 
                ? getApiUrl(`/org-admin/dashboard?org=${targetOrgSlug}`)
                : getApiUrl('/org-admin/dashboard');
            console.log(`Fetching dashboard from: ${apiUrl}`);

            const response = await axios.get(apiUrl, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            console.log('Dashboard API Response:', response.data);
            dashboardData = response.data;
        } catch (err) {
            console.error('Error fetching dashboard:', err);
            if (axios.isAxiosError(err) && err.response?.status === 403) {
                error = 'Access denied. Organization admin privileges required.';
            } else if (axios.isAxiosError(err) && err.response?.data?.detail) {
                error = err.response.data.detail;
            } else if (err instanceof Error) {
                error = err.message;
            } else {
                error = 'An unknown error occurred while fetching dashboard.';
            }
            dashboardData = null;
        } finally {
            isLoadingDashboard = false;
        }
    }

    // Signup key functions
    async function fetchSignupKey() {
        try {
            const token = getAuthToken();
            if (!token) {
                throw new Error('Authentication token not found');
            }

            const signupUrl = targetOrgSlug 
                ? getApiUrl(`/org-admin/settings/signup?org=${targetOrgSlug}`)
                : getApiUrl('/org-admin/settings/signup');
            const response = await axios.get(signupUrl, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            signupKey = response.data.signup_key || '';
        } catch (err) {
            console.error('Error fetching signup key:', err);
            signupKey = '';
        }
    }

    function toggleSignupKeyVisibility() {
        if (!showSignupKey && !signupKey) {
            // Fetch the key when showing for the first time
            fetchSignupKey();
        }
        showSignupKey = !showSignupKey;
    }

    // User management functions
    async function fetchUsers() {
        if (isLoadingUsers) {
            console.log("Already loading users, skipping duplicate request");
            return;
        }

        console.log("Fetching organization users...");
        isLoadingUsers = true;
        usersError = null;

        try {
            const token = getAuthToken();
            if (!token) {
                throw new Error('Authentication token not found. Please log in again.');
            }

            const apiUrl = targetOrgSlug 
                ? getApiUrl(`/org-admin/users?org=${targetOrgSlug}`)
                : getApiUrl('/org-admin/users');
            console.log(`Fetching users from: ${apiUrl}`);

            const response = await axios.get(apiUrl, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            console.log('Users API Response:', response.data);
            orgUsers = response.data || [];
            console.log(`Fetched ${orgUsers.length} users`);
            usersLoaded = true; // Mark as loaded even if empty
            applyUsersFilters(); // Apply filters and pagination
        } catch (err) {
            console.error('Error fetching users:', err);
            if (axios.isAxiosError(err) && err.response?.status === 403) {
                usersError = 'Access denied. Organization admin privileges required.';
            } else if (axios.isAxiosError(err) && err.response?.data?.detail) {
                usersError = err.response.data.detail;
            } else if (err instanceof Error) {
                usersError = err.message;
            } else {
                usersError = 'An unknown error occurred while fetching users.';
            }
            orgUsers = [];
            usersLoaded = true; // Mark as loaded even on error to prevent infinite loops
        } finally {
            isLoadingUsers = false;
        }
    }
    
    // Apply filters, sorting, and pagination to users
    function applyUsersFilters() {
        // Build filters object
        /** @type {Record<string, any>} */
        const filters = {};
        
        // Filter by user type
        if (usersFilterUserType !== 'all') {
            filters.user_type = usersFilterUserType;
        }
        
        // Filter by enabled status
        if (usersFilterStatus === 'enabled') {
            filters.enabled = true;
        } else if (usersFilterStatus === 'disabled') {
            filters.enabled = false;
        }
        
        /** @type {any} */
        let result = processListData(orgUsers, {
            search: usersSearchQuery,
            searchFields: ['name', 'email'],
            filters: filters,
            sortBy: usersSortBy,
            sortOrder: usersSortOrder,
            page: usersPage,
            itemsPerPage: usersPerPage
        });
        
        displayUsers = result.items.map((/** @type {any} */ u) => ({...u, selected: selectedUsers.includes(u.id)}));
        usersTotalItems = result.filteredCount;
        usersTotalPages = result.totalPages;
        usersPage = result.currentPage;
    }
    
    // Users filter/sort/pagination event handlers
    function handleUsersSearchChange() {
        usersPage = 1;
        applyUsersFilters();
    }
    
    function handleUsersFilterChange() {
        usersPage = 1;
        applyUsersFilters();
    }
    
    function handleUsersSortChange() {
        applyUsersFilters();
    }
    
    function handleUsersPageChange(event) {
        usersPage = event.detail.page;
        applyUsersFilters();
    }
    
    function handleUsersPerPageChange(event) {
        usersPerPage = event.detail.itemsPerPage;
        usersPage = 1;
        applyUsersFilters();
    }
    
    // Sync selectedUsers with user.selected checkboxes
    $effect(() => {
        if (displayUsers && displayUsers.length > 0) {
            selectedUsers = displayUsers.filter(u => u.selected).map(u => u.id);
        }
    });

    // Create user functions
    function openCreateUserModal() {
        newUser = {
            email: '',
            name: '',
            password: '',
            enabled: undefined,
            user_type: ''
        };
        createUserError = null;
        createUserSuccess = false;
        isCreateUserModalOpen = true;
    }

    // User enable/disable functions
    async function toggleUserStatus(user) {
        const newStatus = !user.enabled;
        const action = newStatus ? 'enable' : 'disable';
        
        // Prevent users from disabling themselves
        if (userData && userData.email === user.email && !newStatus) {
            return;
        }

        try {
            const token = getAuthToken();
            if (!token) {
                throw new Error('Authentication token not found. Please log in again.');
            }

            const apiUrl = getApiUrl(`/org-admin/users/${user.id}`);
            console.log(`${action === 'enable' ? 'Enabling' : 'Disabling'} user ${user.email} at: ${apiUrl}`);

            const response = await axios.put(apiUrl, {
                enabled: newStatus
            }, {
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            });

            console.log(`User ${action} response:`, response.data);

            // Update the user in the local list
            const userIndex = orgUsers.findIndex(u => u.id === user.id);
            if (userIndex !== -1) {
                orgUsers[userIndex].enabled = newStatus;
                orgUsers = [...orgUsers]; // Trigger reactivity
            }

        } catch (err) {
            console.error(`Error ${action}ing user:`, err);
            
            let errorMessage = `Failed to ${action} user.`;
            if (axios.isAxiosError(err) && err.response?.data?.detail) {
                errorMessage = err.response.data.detail;
            } else if (err instanceof Error) {
                errorMessage = err.message;
            }
            
            // Log error but don't show alert - could add a toast notification here
            console.error(errorMessage);
        }
    }

    // --- Sharing Permission Functions ---
    
    function getUserCanShare(user) {
        // Get user's can_share permission from user_config
        const config = user.user_config || {};
        const userConfig = typeof config === 'string' ? JSON.parse(config || '{}') : config;
        return userConfig.can_share !== false; // Default to true
    }

    async function toggleUserSharingPermission(user, canShare) {
        // Toggle user's ability to share assistants (admin only)
        try {
            const token = getAuthToken();
            if (!token) {
                throw new Error('Authentication token not found');
            }

            const response = await axios.put(
                `${getLambApiUrl(`/creator/lamb/assistant-sharing/user-permission/${user.id}`)}?can_share=${canShare}`,
                {},
                {
                    headers: {
                        'Authorization': `Bearer ${token}`
                    }
                }
            );

            console.log('Updated user sharing permission:', response.data);

            // Update the user in the local list
            const userIndex = orgUsers.findIndex(u => u.id === user.id);
            if (userIndex !== -1) {
                const config = orgUsers[userIndex].user_config || {};
                const userConfig = typeof config === 'string' ? JSON.parse(config || '{}') : config;
                userConfig.can_share = canShare;
                orgUsers[userIndex].user_config = userConfig;
                orgUsers = [...orgUsers]; // Trigger reactivity
            }

        } catch (err) {
            console.error('Error updating sharing permission:', err);
            
            let errorMessage = 'Failed to update sharing permission.';
            if (axios.isAxiosError(err) && err.response?.data?.detail) {
                errorMessage = err.response.data.detail;
            } else if (err instanceof Error) {
                errorMessage = err.message;
            }
            
            console.error(errorMessage);
            // Revert the checkbox state by reloading users
            await fetchUsers();
        }
    }
    
    // Bulk enable/disable functions
    function openBulkDisableModal() {
        if (selectedUsers.length === 0) return;
        isBulkDisableModalOpen = true;
        bulkActionError = null;
    }
    
    function closeBulkDisableModal() {
        isBulkDisableModalOpen = false;
        bulkActionError = null;
    }
    
    function openBulkEnableModal() {
        if (selectedUsers.length === 0) return;
        isBulkEnableModalOpen = true;
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
            const token = getAuthToken();
            if (!token) {
                throw new Error('Authentication token not found');
            }
            
            const result = await adminService.disableUsersBulk(token, selectedUsers);
            
            if (result.success) {
                console.log(`Bulk disable: ${result.disabled} users disabled`);
                // Refresh user list
                await fetchUsers();
                // Clear selection
                selectedUsers = [];
                closeBulkDisableModal();
            } else {
                throw new Error(result.message || 'Bulk disable failed');
            }
        } catch (err) {
            console.error('Error in bulk disable:', err);
            bulkActionError = err instanceof Error ? err.message : 'Failed to disable users';
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
                throw new Error('Authentication token not found');
            }
            
            const result = await adminService.enableUsersBulk(token, selectedUsers);
            
            if (result.success) {
                console.log(`Bulk enable: ${result.enabled} users enabled`);
                // Refresh user list
                await fetchUsers();
                // Clear selection
                selectedUsers = [];
                closeBulkEnableModal();
            } else {
                throw new Error(result.message || 'Bulk enable failed');
            }
        } catch (err) {
            console.error('Error in bulk enable:', err);
            bulkActionError = err instanceof Error ? err.message : 'Failed to enable users';
        } finally {
            isBulkProcessing = false;
        }
    }

    // User delete function
    function openDeleteUserModal(user) {
        // Prevent users from deleting themselves
        if (userData && userData.email === user.email) {
            return;
        }
        
        userToDelete = user;
        deleteUserError = null;
        isDeleteUserModalOpen = true;
    }

    function closeDeleteUserModal() {
        isDeleteUserModalOpen = false;
        userToDelete = null;
        deleteUserError = null;
        isDeletingUser = false;
    }

    async function confirmDeleteUser() {
        // This function now DISABLES the user instead of deleting
        if (!userToDelete) return;

        isDeletingUser = true;
        deleteUserError = null;

        try {
            const token = getAuthToken();
            if (!token) {
                throw new Error('Authentication token not found. Please log in again.');
            }

            const apiUrl = getApiUrl(`/org-admin/users/${userToDelete.id}`);
            console.log(`Disabling user ${userToDelete.email} at: ${apiUrl}`);

            // Update to disable the user instead of deleting
            const response = await axios.put(apiUrl, {
                enabled: false
            }, {
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            });

            console.log('User disable response:', response.data);

            // Update the user in the local list
            const userIndex = orgUsers.findIndex(u => u.id === userToDelete.id);
            if (userIndex !== -1) {
                orgUsers[userIndex].enabled = false;
                orgUsers = [...orgUsers]; // Trigger reactivity
                applyUsersFilters(); // Re-apply filters
            }

            // Close modal
            closeDeleteUserModal();

        } catch (err) {
            console.error('Error disabling user:', err);
            
            let errorMessage = 'Failed to disable user.';
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

    // NOTE: Bulk enable/disable actions now use modal-based approach
    // See openBulkEnableModal/openBulkDisableModal and confirmBulkEnable/confirmBulkDisable

    function closeCreateUserModal() {
        isCreateUserModalOpen = false;
        createUserError = null;
        createUserSuccess = false;
    }

    // Change password functions
    function openChangePasswordModal(user) {
        passwordChangeData = {
            user_id: user.id,
            user_name: user.name,
            user_email: user.email,
            new_password: ''
        };
        changePasswordError = null;
        changePasswordSuccess = false;
        isChangePasswordModalOpen = true;
    }

    function closeChangePasswordModal() {
        isChangePasswordModalOpen = false;
        changePasswordError = null;
        changePasswordSuccess = false;
    }

    async function handleChangePassword(e) {
        e.preventDefault();

        // Basic form validation
        if (!passwordChangeData.new_password) {
            changePasswordError = 'Please enter a new password.';
            return;
        }

        if (passwordChangeData.new_password.length < 8) {
            changePasswordError = 'Password should be at least 8 characters.';
            return;
        }

        changePasswordError = null;
        isChangingPassword = true;

        try {
            const token = getAuthToken();
            if (!token) {
                throw new Error('Authentication token not found. Please log in again.');
            }

            const apiUrl = getApiUrl(`/org-admin/users/${passwordChangeData.user_id}/password`);
            console.log(`Changing password for user ${passwordChangeData.user_email} at: ${apiUrl}`);

            const response = await axios.post(apiUrl, {
                new_password: passwordChangeData.new_password
            }, {
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            });

            console.log('Change password response:', response.data);

            changePasswordSuccess = true;
            // Wait 1.5 seconds to show success message, then close modal
            setTimeout(() => {
                closeChangePasswordModal();
            }, 1500);

        } catch (err) {
            console.error('Error changing password:', err);

            let errorMessage = 'Failed to change password.';
            if (axios.isAxiosError(err) && err.response?.data?.detail) {
                errorMessage = err.response.data.detail;
            } else if (err instanceof Error) {
                errorMessage = err.message;
            }

            changePasswordError = errorMessage;
        } finally {
            isChangingPassword = false;
        }
    }

    /**
     * @param {SubmitEvent} e
     */
    async function handleCreateUser(e) {
        e.preventDefault();

        // Read values directly from DOM via FormData (more reliable with automated testing)
        const form = /** @type {HTMLFormElement} */ (e.target);
        const formDataObj = new FormData(form);
        const email = /** @type {string} */ (formDataObj.get('email') || '').toString().trim();
        const name = /** @type {string} */ (formDataObj.get('name') || '').toString().trim();
        const password = /** @type {string} */ (formDataObj.get('password') || '').toString();
        const userType = /** @type {string} */ (formDataObj.get('user_type') || 'creator').toString();
        const enabled = formDataObj.get('enabled') === 'on';

        // Basic form validation
        if (!email || !name || !password) {
            createUserError = 'Please fill in all required fields.';
            return;
        }

        if (!email.includes('@')) {
            createUserError = 'Please enter a valid email address.';
            return;
        }

        createUserError = null;
        isCreatingUser = true;

        try {
            const token = getAuthToken();
            if (!token) {
                throw new Error('Authentication token not found. Please log in again.');
            }

            const apiUrl = getApiUrl('/org-admin/users');
            console.log(`Creating user at: ${apiUrl}`);

            const response = await axios.post(apiUrl, {
                email: email,
                name: name,
                password: password,
                enabled: enabled,
                user_type: userType
            }, {
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            });

            console.log('Create user response:', response.data);

            createUserSuccess = true;
            // Wait 1.5 seconds to show success message, then close modal and refresh list
            setTimeout(() => {
                closeCreateUserModal();
                fetchUsers(); // Refresh the users list
            }, 1500);

        } catch (err) {
            console.error('Error creating user:', err);
            if (axios.isAxiosError(err) && err.response?.status === 403) {
                createUserError = 'Access denied. Organization admin privileges required.';
            } else if (axios.isAxiosError(err) && err.response?.data?.detail) {
                createUserError = err.response.data.detail;
            } else if (err instanceof Error) {
                createUserError = err.message;
            } else {
                createUserError = 'An unknown error occurred while creating user.';
            }
        } finally {
            isCreatingUser = false;
        }
    }

    // Assistants management functions
    async function fetchAssistants() {
        if (isLoadingAssistants) {
            console.log("Already loading assistants, skipping duplicate request");
            return;
        }

        isLoadingAssistants = true;
        assistantsError = null;
        
        try {
            const headers = {
                'Authorization': `Bearer ${$user.token}`,
                'Content-Type': 'application/json'
            };
            
            const response = await axios.get(`${API_BASE}/org-admin/assistants`, { headers });
            orgAssistants = response.data.assistants || [];
            assistantsLoaded = true; // Mark as loaded even if empty
            
            // Load share counts for all assistants
            await loadAssistantShareCounts();
        } catch (err) {
            console.error('Error fetching assistants:', err);
            assistantsError = err.response?.data?.detail || 'Failed to fetch assistants';
            assistantsLoaded = true; // Mark as loaded even on error to prevent infinite loops
        } finally {
            isLoadingAssistants = false;
        }
    }

    async function loadAssistantShareCounts() {
        // Load share counts for all assistants
        const counts = {};
        
        for (const assistant of orgAssistants) {
            try {
                const response = await axios.get(
                    getLambApiUrl(`/creator/lamb/assistant-sharing/shares/${assistant.id}`),
                    {
                        headers: {
                            'Authorization': `Bearer ${$user.token}`
                        }
                    }
                );
                
                const shares = response.data || [];
                counts[assistant.id] = shares.length;
            } catch (error) {
                console.error(`Error loading shares for assistant ${assistant.id}:`, error);
                counts[assistant.id] = 0;
            }
        }
        
        assistantShareCounts = counts;
    }

    function openAssistantSharingModal(assistant) {
        modalAssistant = assistant;
        showSharingModal = true;
    }

    function closeAssistantSharingModal() {
        showSharingModal = false;
        modalAssistant = null;
    }

    function handleSharingModalSaved() {
        // Reload share counts after sharing changes
        loadAssistantShareCounts();
    }


    function formatDate(timestamp) {
        if (!timestamp) return 'N/A';
        return new Date(timestamp * 1000).toLocaleDateString();
    }

    // Settings functions
    
    /**
     * Validate signup key format
     * @param {string} signupKey - The signup key to validate
     * @returns {{ valid: boolean, error: string | null }} Validation result
     */
    function validateSignupKey(signupKey) {
        if (!signupKey || signupKey.trim().length === 0) {
            return { valid: false, error: 'Signup key is required when signup is enabled' };
        }
        
        const trimmedKey = signupKey.trim();
        
        // Check minimum length
        if (trimmedKey.length < 8) {
            return { valid: false, error: 'Signup key must be at least 8 characters long' };
        }
        
        // Check maximum length
        if (trimmedKey.length > 64) {
            return { valid: false, error: 'Signup key must be no more than 64 characters long' };
        }
        
        // Check allowed characters (alphanumeric, hyphens, underscores)
        if (!/^[a-zA-Z0-9_-]+$/.test(trimmedKey)) {
            return { valid: false, error: 'Signup key can only contain letters, numbers, hyphens, and underscores' };
        }
        
        // Check that it doesn't start or end with hyphen or underscore
        if (trimmedKey.startsWith('-') || trimmedKey.startsWith('_') || 
            trimmedKey.endsWith('-') || trimmedKey.endsWith('_')) {
            return { valid: false, error: 'Signup key cannot start or end with a hyphen or underscore' };
        }
        
        return { valid: true, error: null };
    }
    
    async function fetchSettings() {
        if (isLoadingSettings) {
            console.log("Already loading settings, skipping duplicate request");
            return;
        }

        console.log("Fetching organization settings...");
        isLoadingSettings = true;
        settingsError = null;

        try {
            const token = getAuthToken();
            if (!token) {
                throw new Error('Authentication token not found. Please log in again.');
            }

            // Fetch signup settings (for General tab)
            const signupUrl = targetOrgSlug 
                ? getApiUrl(`/org-admin/settings/signup?org=${targetOrgSlug}`)
                : getApiUrl('/org-admin/settings/signup');
            const signupResponse = await axios.get(signupUrl, {
                headers: { 'Authorization': `Bearer ${token}` }
            });

            signupSettings = signupResponse.data;

            // Initialize signup edit form
            newSignupSettings = {
                signup_enabled: signupSettings.signup_enabled,
                signup_key: signupSettings.signup_key || ''
            };

            // Don't fetch dashboard data on initial settings load
            // It will be loaded when needed (contains slow API tests)

        } catch (err) {
            console.error('Error fetching settings:', err);
            if (axios.isAxiosError(err) && err.response?.status === 403) {
                settingsError = 'Access denied. Organization admin privileges required.';
            } else if (axios.isAxiosError(err) && err.response?.data?.detail) {
                settingsError = err.response.data.detail;
            } else if (err instanceof Error) {
                settingsError = err.message;
            } else {
                settingsError = 'An unknown error occurred while fetching settings.';
            }
        } finally {
            isLoadingSettings = false;
        }
    }

    // Assistant defaults helpers
    function getTargetSlug() {
        // Prefer explicit target from URL; otherwise use dashboard data
        if (targetOrgSlug) return targetOrgSlug;
        return dashboardData?.organization?.slug || null;
    }

    async function fetchAssistantDefaults() {
        if (isLoadingAssistantDefaults) return;
        isLoadingAssistantDefaults = true;
        assistantDefaultsError = null;
        assistantDefaultsSuccess = false;
        try {
            const token = getAuthToken();
            if (!token) {
                throw new Error('Authentication token not found. Please log in again.');
            }

            // Use non-admin endpoint to read defaults for current org
            const url = getApiUrl('/assistant/defaults').replace('/admin', ''); // maps to /creator/assistant/defaults
            const response = await axios.get(url, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            assistantDefaults = response.data || {};
            assistantDefaultsJson = JSON.stringify(assistantDefaults, null, 2);
        } catch (err) {
            console.error('Error fetching assistant defaults:', err);
            if (axios.isAxiosError(err) && err.response?.data?.detail) {
                assistantDefaultsError = err.response.data.detail;
            } else if (err instanceof Error) {
                assistantDefaultsError = err.message;
            } else {
                assistantDefaultsError = 'Failed to fetch assistant defaults.';
            }
        } finally {
            isLoadingAssistantDefaults = false;
        }
    }

    async function updateAssistantDefaults() {
        assistantDefaultsError = null;
        assistantDefaultsSuccess = false;
        try {
            const token = getAuthToken();
            if (!token) throw new Error('Authentication token not found. Please log in again.');

            let parsed;
            try {
                parsed = JSON.parse(assistantDefaultsJson || '{}');
                if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
                    throw new Error('Assistant defaults must be a JSON object.');
                }
            } catch (e) {
                throw new Error(`Invalid JSON: ${(e instanceof Error) ? e.message : 'Parsing error'}`);
            }

            // Determine target organization slug
            let slug = getTargetSlug();
            if (!slug) {
                // Ensure dashboard is loaded to get slug
                await fetchDashboard();
                slug = getTargetSlug();
            }
            if (!slug) throw new Error('Unable to resolve organization slug.');

            const putUrl = getApiUrl(`/organizations/${slug}/assistant-defaults`);
            await axios.put(putUrl, parsed, {
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            });

            assistantDefaults = parsed;
            assistantDefaultsSuccess = true;
            addPendingChange('Assistant defaults updated');
        } catch (err) {
            console.error('Error updating assistant defaults:', err);
            if (err instanceof Error) {
                assistantDefaultsError = err.message;
            } else if (axios.isAxiosError(err) && err.response?.data?.detail) {
                assistantDefaultsError = err.response.data.detail;
            } else {
                assistantDefaultsError = 'Failed to update assistant defaults.';
            }
        }
    }

    // API Settings function
    async function fetchApiSettings() {
        try {
            const token = getAuthToken();
            if (!token) {
                throw new Error('Authentication token not found. Please log in again.');
            }

            // Fetch API settings
            const apiUrl = targetOrgSlug 
                ? getApiUrl(`/org-admin/settings/api?org=${targetOrgSlug}`)
                : getApiUrl('/org-admin/settings/api');
            const apiResponse = await axios.get(apiUrl, {
                headers: { 'Authorization': `Bearer ${token}` }
            });

            apiSettings = apiResponse.data;

            // Initialize API edit form
            newApiSettings = {
                openai_api_key: '',
                openai_base_url: apiSettings.openai_base_url || 'https://api.openai.com/v1',
                ollama_base_url: apiSettings.ollama_base_url || 'http://localhost:11434',
                available_models: Array.isArray(apiSettings.available_models) ? [...apiSettings.available_models] : [],
                model_limits: { ...(apiSettings.model_limits || {}) },
                selected_models: { ...(apiSettings.selected_models || {}) },
                default_models: { ...(apiSettings.default_models || {}) },
                global_default_model: apiSettings.global_default_model || {provider: '', model: ''},
                small_fast_model: apiSettings.small_fast_model || {provider: '', model: ''}
            };

            // Auto-initialize default models for providers that have enabled models but no default set
            if (newApiSettings.selected_models) {
                for (const [providerName, enabledModels] of Object.entries(newApiSettings.selected_models)) {
                    if (enabledModels && enabledModels.length > 0 && !newApiSettings.default_models[providerName]) {
                        // No default set, auto-select first enabled model
                        newApiSettings.default_models[providerName] = enabledModels[0];
                    }
                }
            }
        } catch (err) {
            console.error('Error fetching API settings:', err);
        }
    }

    // KB Settings functions
    async function fetchKbSettings() {
        isLoadingKbSettings = true;
        kbSettingsError = null;
        kbSettingsSuccess = false;
        kbTestResult = null;
        
        try {
            const token = getAuthToken();
            if (!token) {
                throw new Error('Authentication token not found. Please log in again.');
            }

            const params = targetOrgSlug ? `?org=${targetOrgSlug}` : '';
            const response = await axios.get(getApiUrl(`/org-admin/settings/kb${params}`), {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            
            kbSettings = response.data;
            newKbSettings = {
                url: kbSettings.url || '',
                api_key: '', // Never populate with actual key
                embedding_model: kbSettings.embedding_model || '',
                embedding_api_key: '', // Will be populated from KB server config
                collection_defaults: kbSettings.collection_defaults || {
                    chunk_size: 1000,
                    chunk_overlap: 200
                }
            };
            
            // Fetch embeddings config from KB server
            await fetchKbEmbeddingsConfig();
        } catch (err) {
            console.error('Error fetching KB settings:', err);
            if (axios.isAxiosError(err) && err.response?.data?.detail) {
                kbSettingsError = err.response.data.detail;
            } else if (err instanceof Error) {
                kbSettingsError = err.message;
            } else {
                kbSettingsError = 'Failed to fetch KB settings.';
            }
        } finally {
            isLoadingKbSettings = false;
        }
    }

    async function testKbConnection() {
        isTesting = true;
        kbTestResult = null;
        
        if (!newKbSettings.url) {
            kbTestResult = {
                success: false,
                message: 'Please enter a KB server URL'
            };
            isTesting = false;
            return;
        }
        
        // Use existing API key if not changed (allow testing current config)
        const apiKeyToTest = newKbSettings.api_key || 'USE_EXISTING';
        
        if (apiKeyToTest === 'USE_EXISTING' && !kbSettings.api_key_set) {
            kbTestResult = {
                success: false,
                message: 'Please enter an API key or configure one first'
            };
            isTesting = false;
            return;
        }
        
        try {
            const token = getAuthToken();
            const params = targetOrgSlug ? `?org=${targetOrgSlug}` : '';
            const response = await axios.post(
                getApiUrl(`/org-admin/settings/kb/test${params}`),
                {
                    url: newKbSettings.url,
                    api_key: apiKeyToTest
                },
                {
                    headers: {
                        'Authorization': `Bearer ${token}`,
                        'Content-Type': 'application/json'
                    }
                }
            );
            
            kbTestResult = response.data;
        } catch (err) {
            console.error('Error testing KB connection:', err);
            if (axios.isAxiosError(err) && err.response?.data) {
                kbTestResult = err.response.data;
            } else {
                kbTestResult = {
                    success: false,
                    message: err instanceof Error ? err.message : 'Test failed'
                };
            }
        } finally {
            isTesting = false;
        }
    }

    async function updateKbSettings() {
        kbSettingsError = null;
        kbSettingsSuccess = false;
        kbTestResult = null;
        
        // Test connection first (mandatory)
        await testKbConnection();
        
        if (!kbTestResult || !kbTestResult.success) {
            kbSettingsError = 'Connection test failed. Please fix configuration before saving.';
            return;
        }
        
        try {
            const token = getAuthToken();
            const params = targetOrgSlug ? `?org=${targetOrgSlug}` : '';
            
            const payload = {
                url: newKbSettings.url,
                embedding_model: newKbSettings.embedding_model || null,
                collection_defaults: newKbSettings.collection_defaults || null
            };
            
            // Only include API key if it was changed
            if (newKbSettings.api_key) {
                payload.api_key = newKbSettings.api_key;
            }
            
            await axios.put(
                getApiUrl(`/org-admin/settings/kb${params}`),
                payload,
                {
                    headers: {
                        'Authorization': `Bearer ${token}`,
                        'Content-Type': 'application/json'
                    }
                }
            );
            
            kbSettingsSuccess = true;
            addPendingChange('KB server settings updated');
            
            // Preserve the API key that was just saved (if any) before reloading
            const savedApiKey = newKbSettings.api_key;
            
            // Reload to refresh api_key_set status
            await fetchKbSettings();
            
            // If we just saved an API key, preserve it in the form (user can see what they entered)
            // Note: We don't show the actual saved key from server (security), but preserve what user typed
            if (savedApiKey) {
                newKbSettings.api_key = savedApiKey;
                showKbApiKey = true; // Auto-show the key they just entered
            }
        } catch (err) {
            console.error('Error updating KB settings:', err);
            if (axios.isAxiosError(err) && err.response?.data?.detail) {
                kbSettingsError = err.response.data.detail;
            } else if (err instanceof Error) {
                kbSettingsError = err.message;
            } else {
                kbSettingsError = 'Failed to update KB settings.';
            }
        }
    }

        /**
     * Fetch the current embeddings configuration from the KB server
     */
    async function fetchKbEmbeddingsConfig() {
        isLoadingKbEmbeddingsConfig = true;
        kbEmbeddingsConfigError = null;

        try {
            if (!kbSettings.url) {
                kbEmbeddingsConfig = {
                    vendor: '',
                    model: '',
                    api_endpoint: '',
                    apikey_configured: false,
                    apikey_masked: '',
                    config_source: 'env'
                };
                return;
            }

            // Use LAMB backend proxy endpoint instead of calling KB server directly
            const token = getAuthToken();
            if (!token) {
                throw new Error('Authentication token not found');
            }

            const params = targetOrgSlug ? `?org=${targetOrgSlug}` : '';
            const response = await axios.get(getApiUrl(`/org-admin/settings/kb/embeddings-config${params}`), {
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            });

            kbEmbeddingsConfig = response.data;

            // Initialize embedding API key form field with masked key if configured
            if (kbEmbeddingsConfig.apikey_configured && kbEmbeddingsConfig.apikey_masked) {
                // Store the masked key for display purposes and dirty tracking
                newKbSettings.embedding_api_key = kbEmbeddingsConfig.apikey_masked;
                embeddingApiKeyOriginal = kbEmbeddingsConfig.apikey_masked;
            } else {
                // No key configured
                newKbSettings.embedding_api_key = '';
                embeddingApiKeyOriginal = '';
            }
            
            // Reset dirty state and checkbox when loading fresh config
            embeddingApiKeyDirty = false;
            applyToAllKbChecked = false;

        } catch (err) {
            console.error('Error fetching KB embeddings config:', err);
            // Don't show error to user - this is optional configuration
            kbEmbeddingsConfigError = null;
            kbEmbeddingsConfig = {
                vendor: '',
                model: '',
                api_endpoint: '',
                apikey_configured: false,
                apikey_masked: '',
                config_source: 'env'
            };
        } finally {
            isLoadingKbEmbeddingsConfig = false;
        }
    }

    /**
     * Update the embeddings configuration on the KB server
     */
    /**
     * Update the embeddings configuration on the KB server.
     * @param {{ applyToAll?: boolean }} [options]
     */
    async function updateKbEmbeddingsConfig({ applyToAll = false } = {}) {
        kbEmbeddingsConfigError = null;
        isUpdatingKbEmbeddingsConfig = true;

        try {
            if (!newKbSettings.url && !kbSettings.url) {
                throw new Error('KB server URL is not configured');
            }

            const token = getAuthToken();
            if (!token) {
                throw new Error('Authentication token not found. Please log in again.');
            }

            // Build payload with only provided fields
            /** @type {any} */
            const payload = {};

            if (newKbSettings.embedding_api_key &&
                newKbSettings.embedding_api_key !== kbEmbeddingsConfig.apikey_masked) {
                payload.apikey = newKbSettings.embedding_api_key;

                // Add flag to apply to all KB collections only after explicit confirmation
                if (applyToAll) {
                    payload.apply_to_all_kb = true;
                }
            }

            // Add other fields from current config to preserve them
            if (kbEmbeddingsConfig.vendor) {
                payload.vendor = kbEmbeddingsConfig.vendor;
            }
            if (kbEmbeddingsConfig.model) {
                payload.model = kbEmbeddingsConfig.model;
            }
            if (kbEmbeddingsConfig.api_endpoint) {
                payload.api_endpoint = kbEmbeddingsConfig.api_endpoint;
            }

            // Use LAMB backend proxy endpoint instead of calling KB server directly
            const params = targetOrgSlug ? `?org=${targetOrgSlug}` : '';
            const response = await axios.put(
                getApiUrl(`/org-admin/settings/kb/embeddings-config${params}`),
                payload,
                {
                    headers: {
                        'Authorization': `Bearer ${token}`,
                        'Content-Type': 'application/json'
                    }
                }
            );

            // Refresh the config to get updated state
            await fetchKbEmbeddingsConfig();

            // Capture bulk update result for UI display
            if (response.data?.bulk_update) {
                const bulk = response.data.bulk_update;
                applyToAllKbResult = `Updated ${bulk.updated} of ${bulk.total} collections`;
            } else {
                applyToAllKbResult = null;
            }

            // Show success message
            kbSettingsSuccess = true;
            
            // Handle bulk update results
            if (response.data?.bulk_update) {
                const bulkResult = response.data.bulk_update;
                const message = `KB server embeddings configuration updated. ` +
                    (bulkResult.updated > 0 
                        ? `Applied new API key to ${bulkResult.updated} of ${bulkResult.total} knowledge base collections.` 
                        : 'No existing collections needed updating.');
                addPendingChange(message);
            } else {
                addPendingChange('KB server embeddings configuration updated');
            }

            // Reset apply-to-all checkbox after a successful save
            applyToAllKbChecked = false;

            // Clear success message after 3 seconds
            setTimeout(() => {
                kbSettingsSuccess = false;
            }, 3000);

        } catch (err) {
            console.error('Error updating KB embeddings config:', err);
            if (axios.isAxiosError(err) && err.response?.data?.detail) {
                kbEmbeddingsConfigError = err.response.data.detail;
            } else if (err instanceof Error) {
                kbEmbeddingsConfigError = err.message;
            } else {
                kbEmbeddingsConfigError = 'Failed to update embeddings configuration. Make sure the KB server is accessible.';
            }
        } finally {
            isUpdatingKbEmbeddingsConfig = false;
        }
    }

    async function saveKbEmbeddingsConfig() {
        // If user requested a bulk update, require explicit confirmation.
        if (applyToAllKbChecked && embeddingApiKeyDirty) {
            showApplyToAllKbConfirmation = true;
            return;
        }

        await updateKbEmbeddingsConfig({ applyToAll: false });
    }

    async function confirmApplyToAllKb() {
        showApplyToAllKbConfirmation = false;
        isApplyingToAllKb = true;
        try {
            await updateKbEmbeddingsConfig({ applyToAll: true });
        } finally {
            isApplyingToAllKb = false;
        }
    }

    function cancelApplyToAllKb() {
        showApplyToAllKbConfirmation = false;
    }

    async function updateSignupSettings() {
        // Reset error and success states
        signupSettingsError = null;
        signupSettingsSuccess = false;
        
        try {
            // Validate signup key if signup is enabled
            if (newSignupSettings.signup_enabled) {
                const validation = validateSignupKey(newSignupSettings.signup_key);
                if (!validation.valid) {
                    signupSettingsError = validation.error;
                    return;
                }
            }
            
            const token = getAuthToken();
            if (!token) {
                throw new Error('Authentication token not found. Please log in again.');
            }

            const signupUrl = targetOrgSlug 
                ? getApiUrl(`/org-admin/settings/signup?org=${targetOrgSlug}`)
                : getApiUrl('/org-admin/settings/signup');

            await axios.put(signupUrl, newSignupSettings, {
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            });

            // Refresh settings
            await fetchSettings();
            
            // Show success message
            signupSettingsSuccess = true;
            
            // Clear success message after 3 seconds
            setTimeout(() => {
                signupSettingsSuccess = false;
            }, 3000);

        } catch (err) {
            console.error('Error updating signup settings:', err);
            
            // Display user-friendly error message
            if (axios.isAxiosError(err)) {
                if (err.response?.data?.detail) {
                    signupSettingsError = err.response.data.detail;
                } else if (err.response?.status === 400) {
                    signupSettingsError = 'Invalid signup settings. Please check your input.';
                } else if (err.response?.status === 403) {
                    signupSettingsError = 'Access denied. Organization admin privileges required.';
                } else {
                    signupSettingsError = 'Failed to update signup settings. Please try again.';
                }
            } else if (err instanceof Error) {
                signupSettingsError = err.message;
            } else {
                signupSettingsError = 'An unknown error occurred while updating signup settings.';
            }
        }
    }

        async function updateApiSettings() {
        try {
            const token = getAuthToken();
            if (!token) {
                throw new Error('Authentication token not found. Please log in again.');
            }

            const apiUrl = targetOrgSlug 
                ? getApiUrl(`/org-admin/settings/api?org=${targetOrgSlug}`)
                : getApiUrl('/org-admin/settings/api');

            await axios.put(apiUrl, newApiSettings, {
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            });

            // Clear pending changes after successful save
            clearPendingChanges();
            
            // Clear capabilities cache so assistant form gets updated models
            if (typeof window !== 'undefined') {
                try {
                    const { assistantConfigStore } = await import('$lib/stores/assistantConfigStore');
                    assistantConfigStore.clearCache();
                    console.log('Cleared assistant capabilities cache after API settings update');
                } catch (cacheErr) {
                    console.warn('Could not clear capabilities cache:', cacheErr);
                }
            }

            // Refresh settings and dashboard data
            await fetchSettings();
            await fetchDashboard();
            // Success - data refreshed

        } catch (err) {
            console.error('Error updating API settings:', err);
            // Error is logged to console
        }
    }

    // Lifecycle
    onMount(() => {
        console.log("Organization admin page mounted");

        // Subscribe to user store
        const unsubscribe = user.subscribe(userState => {
            userData = userState;
        });

        // Check if user is logged in
        if (!userData || !userData.isLoggedIn) {
            console.log("User not logged in, redirecting to login");
            goto(`${base}/auth`, { replaceState: true });
            return;
        }

        // Get view from URL params
        const urlView = $page.url.searchParams.get('view') || 'dashboard';
        currentView = urlView;

        // Get target organization from URL params (for system admin)
        targetOrgSlug = $page.url.searchParams.get('org');

        // Load initial data based on view
        if (currentView === 'dashboard') {
            fetchDashboard();
        } else if (currentView === 'users') {
            fetchUsers();
        } else if (currentView === 'assistants') {
            fetchAssistants();
        } else if (currentView === 'settings') {
            fetchSettings();
        }
    });

    onDestroy(() => {
        console.log("Organization admin page unmounting");
    });

    // Reactive statements to handle view changes
    $effect(() => {
        if (currentView === 'dashboard' && !dashboardData) {
            fetchDashboard();
        } else if (currentView === 'users' && !usersLoaded) {
            fetchUsers();
        } else if (currentView === 'assistants' && !assistantsLoaded) {
            fetchAssistants();
        } else if (currentView === 'settings' && !signupSettings) {
            fetchSettings();
        }
    });
</script>

<svelte:head>
    <title>Organization Admin - LAMB</title>
</svelte:head>

<div class="min-h-screen bg-gray-50">
    <!-- Navigation Header -->
    <nav class="bg-white shadow-sm border-b border-gray-200">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex justify-between h-16">
                <div class="flex">
                    <div class="flex-shrink-0 flex items-center">
                        <h1 class="text-xl font-semibold text-gray-800">Organization Admin</h1>
                    </div>
                    <div class="ml-6 flex space-x-8">
                        <button
                            class="inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium transition-colors duration-200 {currentView === 'dashboard' ? 'border-[#2271b3] text-[#2271b3]' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'}"
                            onclick={showDashboard}
                        >
                            Dashboard
                        </button>
                        <button
                            class="inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium transition-colors duration-200 {currentView === 'users' ? 'border-[#2271b3] text-[#2271b3]' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'}"
                            onclick={showUsers}
                        >
                            Users
                        </button>
                        <button
                            class="inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium transition-colors duration-200 {currentView === 'bulk-import' ? 'border-[#2271b3] text-[#2271b3]' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'}"
                            onclick={showBulkImport}
                        >
                            Bulk Import
                        </button>
                        <button
                            class="inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium transition-colors duration-200 {currentView === 'assistants' ? 'border-[#2271b3] text-[#2271b3]' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'}"
                            onclick={showAssistants}
                        >
                            Assistants Access
                        </button>
                        <button
                            class="inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium transition-colors duration-200 {currentView === 'settings' ? 'border-[#2271b3] text-[#2271b3]' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'}"
                            onclick={showSettings}
                        >
                            Settings
                        </button>
                    </div>
                </div>
            </div>
        </div>
    </nav>

    <!-- Main Content -->
    <main class="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div class="px-4 py-6 sm:px-0">
            
            <!-- Error Display -->
            {#if error}
                <div class="mb-6 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative" role="alert">
                    <span class="block sm:inline">{error}</span>
                </div>
            {/if}

            <!-- Dashboard View -->
            {#if currentView === 'dashboard'}
                <div class="mb-6">
                    <!-- Organization Header -->
                    {#if dashboardData}
                        <div class="bg-gradient-to-r from-brand to-brand-hover rounded-lg shadow-lg mb-6">
                            <div class="px-6 py-6 text-white">
                                <div class="flex items-center justify-between">
                                    <div>
                                        <h1 class="text-3xl font-bold mb-2">
                                            {dashboardData.organization.name}
                                        </h1>
                                        <p class="text-blue-100 text-lg">Organization Administration</p>
                                    </div>
                                    <div class="text-right">
                                        {#if targetOrgSlug}
                                            <div class="text-blue-200 text-xs mb-1">
                                                <svg class="inline h-3 w-3 mr-1" fill="currentColor" viewBox="0 0 20 20">
                                                    <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"></path>
                                                </svg>
                                                System Admin View
                                            </div>
                                        {/if}
                                        <div class="text-blue-100 text-sm mb-1">Organization ID</div>
                                        <div class="font-mono text-white">{dashboardData.organization.slug}</div>
                                    </div>
                                </div>
                                
                                <!-- Signup Key Display -->
                                {#if dashboardData.settings.signup_key_set}
                                    <div class="mt-4 bg-blue-800 bg-opacity-50 rounded-md p-4">
                                        <div class="flex items-center justify-between">
                                            <div>
                                                <h4 class="text-sm font-medium text-blue-100 mb-1">Organization Signup Key</h4>
                                                <div class="font-mono text-white text-lg" id="signup-key-display">
                                                    {showSignupKey ? signupKey : '••••••••••••••••'}
                                                </div>
                                            </div>
                                            <button
                                                type="button"
                                                class="ml-4 px-3 py-1 bg-brand hover:bg-brand-hover text-white text-sm rounded-md transition-colors"
                                                onclick={toggleSignupKeyVisibility}
                                            >
                                                {showSignupKey ? 'Hide' : 'Show'}
                                            </button>
                                        </div>
                                        <p class="text-blue-200 text-xs mt-2">
                                            Share this key with users to allow them to sign up for your organization
                                        </p>
                                    </div>
                                {:else}
                                    <div class="mt-4 bg-yellow-600 bg-opacity-50 rounded-md p-3">
                                        <p class="text-yellow-100 text-sm">
                                            <svg class="inline h-4 w-4 mr-1" fill="currentColor" viewBox="0 0 20 20">
                                                <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"></path>
                                            </svg>
                                            No signup key configured. Users cannot self-register for this organization.
                                        </p>
                                    </div>
                                {/if}
                            </div>
                        </div>
                    {/if}
                    
                    {#if isLoadingDashboard}
                        <div class="text-center py-12">
                            <div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-brand"></div>
                            <p class="mt-2 text-gray-600">Loading dashboard...</p>
                        </div>
                    {:else if dashboardData}
                        <!-- Organization Stats -->
                        <div class="bg-white overflow-hidden shadow rounded-lg mb-6">
                            <div class="px-4 py-5 sm:p-6">
                                <h3 class="text-lg leading-6 font-medium text-gray-900 mb-4">
                                    Organization Statistics
                                </h3>
                                <div class="grid grid-cols-1 gap-5 sm:grid-cols-3">
                                    <!-- Total Users -->
                                    <div class="bg-blue-50 overflow-hidden shadow rounded-lg">
                                        <div class="p-5">
                                            <div class="flex items-center">
                                                <div class="flex-shrink-0">
                                                    <svg class="h-6 w-6 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5-9a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0z" />
                                                    </svg>
                                                </div>
                                                <div class="ml-5 w-0 flex-1">
                                                    <dl>
                                                        <dt class="text-sm font-medium text-gray-500 truncate">
                                                            Total Users
                                                        </dt>
                                                        <dd class="text-lg font-medium text-gray-900">
                                                            {dashboardData.stats.total_users}
                                                        </dd>
                                                    </dl>
                                                </div>
                                            </div>
                                        </div>
                                    </div>

                                    <!-- Active Users -->
                                    <div class="bg-green-50 overflow-hidden shadow rounded-lg">
                                        <div class="p-5">
                                            <div class="flex items-center">
                                                <div class="flex-shrink-0">
                                                    <svg class="h-6 w-6 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                                                    </svg>
                                                </div>
                                                <div class="ml-5 w-0 flex-1">
                                                    <dl>
                                                        <dt class="text-sm font-medium text-gray-500 truncate">
                                                            Active Users
                                                        </dt>
                                                        <dd class="text-lg font-medium text-gray-900">
                                                            {dashboardData.stats.active_users}
                                                        </dd>
                                                    </dl>
                                                </div>
                                            </div>
                                        </div>
                                    </div>

                                    <!-- Settings Status -->
                                    <div class="bg-yellow-50 overflow-hidden shadow rounded-lg">
                                        <div class="p-5">
                                            <div class="flex items-center">
                                                <div class="flex-shrink-0">
                                                    <svg class="h-6 w-6 text-yellow-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                                    </svg>
                                                </div>
                                                <div class="ml-5 w-0 flex-1">
                                                    <dl>
                                                        <dt class="text-sm font-medium text-gray-500 truncate">
                                                            Configuration
                                                        </dt>
                                                        <dd class="text-lg font-medium text-gray-900">
                                                            {#if dashboardData.api_status}
                                                                {#if dashboardData.api_status.overall_status === 'working'}
                                                                    <span class="text-green-600">✓ APIs Working</span>
                                                                    <div class="text-sm text-gray-500 mt-1">
                                                                        {dashboardData.api_status.summary.total_models} models available
                                                                    </div>
                                                                {:else if dashboardData.api_status.overall_status === 'partial'}
                                                                    <span class="text-yellow-600">⚠ Partial Setup</span>
                                                                    <div class="text-sm text-gray-500 mt-1">
                                                                        {dashboardData.api_status.summary.working_count}/{dashboardData.api_status.summary.configured_count} providers working
                                                                    </div>
                                                                {:else if dashboardData.api_status.overall_status === 'error'}
                                                                    <span class="text-red-600">❌ API Errors</span>
                                                                    <div class="text-sm text-gray-500 mt-1">
                                                                        Check configuration
                                                                    </div>
                                                                {:else}
                                                                    <span class="text-gray-600">⚠ Not Configured</span>
                                                                {/if}
                                                            {:else}
                                                            {dashboardData.settings.api_configured ? '✓' : '⚠'} API Setup
                                                            {/if}
                                                        </dd>
                                                    </dl>
                                                </div>
                                            </div>
                                        </div>

                                        <!-- Enabled Models per Connector -->
                                        {#if dashboardData.api_status && Object.keys(dashboardData.api_status.providers).length > 0}
                                            <div class="mt-6">
                                                <h4 class="text-sm font-medium text-gray-900 mb-3">Enabled Models by Connector</h4>
                                                <div class="space-y-3">
                                                    {#each Object.entries(dashboardData.api_status.providers) as [providerName, providerStatus]}
                                                        <div class="bg-gray-50 rounded-lg p-3">
                                                            <div class="flex items-center justify-between mb-2">
                                                                <h5 class="font-medium text-gray-900 capitalize">{providerName}</h5>
                                                                <span class="px-2 py-1 text-xs rounded-full {
                                                                    providerStatus.status === 'working' ? 'bg-green-100 text-green-800' :
                                                                    'bg-gray-100 text-gray-800'
                                                                }">
                                                                    {providerStatus.status}
                                                                </span>
                                                            </div>

                                                            {#if providerStatus.enabled_models && providerStatus.enabled_models.length > 0}
                                                                <div class="mb-2">
                                                                    <div class="text-xs text-gray-600 mb-1">
                                                                        <strong>{providerStatus.enabled_models.length}</strong> models enabled
                                                                        {#if providerStatus.default_model}
                                                                            <span class="text-brand">• Default: {providerStatus.default_model}</span>
                                                                        {/if}
                                                                    </div>
                                                                    <div class="flex flex-wrap gap-1">
                                                                        {#each providerStatus.enabled_models.slice(0, 8) as model}
                                                                            <span class="inline-block px-2 py-1 text-xs bg-brand/10 text-brand rounded {
                                                                                model === providerStatus.default_model ? 'ring-2 ring-brand' : ''
                                                                            }">
                                                                                {model}
                                                                            </span>
                                                                        {/each}
                                                                        {#if providerStatus.enabled_models.length > 8}
                                                                            <span class="inline-block px-2 py-1 text-xs bg-gray-100 text-gray-600 rounded">
                                                                                +{providerStatus.enabled_models.length - 8} more
                                                                            </span>
                                                                        {/if}
                                                                    </div>
                                                                </div>
                                                            {:else}
                                                                <div class="text-xs text-gray-500 italic">
                                                                    No models enabled
                                                                </div>
                                                            {/if}
                                                        </div>
                                                    {/each}
                                                </div>
                                            </div>
                                        {/if}
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- Quick Settings -->
                        <div class="bg-white overflow-hidden shadow rounded-lg">
                            <div class="px-4 py-5 sm:p-6">
                                <h3 class="text-lg leading-6 font-medium text-gray-900 mb-4">Quick Settings</h3>
                                <div class="space-y-3">
                                    <div class="flex items-center justify-between">
                                        <span class="text-sm text-gray-600">Signup Enabled</span>
                                        <span class="text-sm font-medium {dashboardData.settings.signup_enabled ? 'text-green-600' : 'text-gray-400'}">
                                            {dashboardData.settings.signup_enabled ? 'Yes' : 'No'}
                                        </span>
                                    </div>
                                    <div class="flex items-center justify-between">
                                        <span class="text-sm text-gray-600">Signup Key Set</span>
                                        <span class="text-sm font-medium {dashboardData.settings.signup_key_set ? 'text-green-600' : 'text-gray-400'}">
                                            {dashboardData.settings.signup_key_set ? 'Yes' : 'No'}
                                        </span>
                                    </div>
                                    <div class="flex items-center justify-between">
                                        <span class="text-sm text-gray-600">API Configured</span>
                                        <span class="text-sm font-medium {dashboardData.settings.api_configured ? 'text-green-600' : 'text-gray-400'}">
                                            {dashboardData.settings.api_configured ? 'Yes' : 'No'}
                                        </span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    {/if}
                </div>
            {/if}

            <!-- Users View -->
            {#if currentView === 'users'}
                <div class="mb-6">
                    <!-- Organization Header for Users -->
                    {#if dashboardData}
                        <div class="bg-white border-l-4 border-brand shadow-sm rounded-lg mb-4">
                            <div class="px-4 py-3">
                                <div class="flex items-center justify-between">
                                    <div>
                                        <h1 class="text-xl font-semibold text-gray-900">{dashboardData.organization.name}</h1>
                                        <p class="text-sm text-gray-600">User Management</p>
                                    </div>
                                    <div class="text-right text-sm text-gray-500">
                                        {#if targetOrgSlug}
                                            <div class="text-xs text-brand mb-1">
                                                <svg class="inline h-3 w-3 mr-1" fill="currentColor" viewBox="0 0 20 20">
                                                    <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"></path>
                                                </svg>
                                                System Admin View
                                            </div>
                                        {/if}
                                        {usersTotalItems} users total
                                    </div>
                                </div>
                            </div>
                        </div>
                    {/if}
                    
                    <!-- Header with Create Button -->
                    <div class="flex justify-between items-center mb-4">
                        <h2 class="text-2xl font-semibold text-gray-800">Manage Users</h2>
                        <button
                            class="bg-brand hover:bg-brand-hover text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline"
                            onclick={openCreateUserModal}
                        >
                            Create User
                        </button>
                    </div>

                    {#if usersError}
                        <div class="mb-4 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative" role="alert">
                            <span class="block sm:inline">{usersError}</span>
                        </div>
                    {/if}

                    <!-- Filters and Search Controls -->
                    <div class="bg-white shadow-sm rounded-lg p-4 mb-4">
                        <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
                            <!-- Search -->
                            <div class="md:col-span-2">
                                <label for="users-search" class="block text-sm font-medium text-gray-700 mb-1">Search</label>
                                <input
                                    id="users-search"
                                    type="text"
                                    placeholder="Search by name or email..."
                                    bind:value={usersSearchQuery}
                                    oninput={handleUsersSearchChange}
                                    class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent"
                                />
                            </div>
                            
                            <!-- User Type Filter -->
                            <div>
                                <label for="filter-user-type" class="block text-sm font-medium text-gray-700 mb-1">User Type</label>
                                <select
                                    id="filter-user-type"
                                    bind:value={usersFilterUserType}
                                    onchange={handleUsersFilterChange}
                                    class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-brand"
                                >
                                    <option value="all">All Types</option>
                                    <option value="creator">Creator</option>
                                    <option value="end_user">End User</option>
                                </select>
                            </div>
                            
                            <!-- Status Filter -->
                            <div>
                                <label for="filter-status" class="block text-sm font-medium text-gray-700 mb-1">Status</label>
                                <select
                                    id="filter-status"
                                    bind:value={usersFilterStatus}
                                    onchange={handleUsersFilterChange}
                                    class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-brand"
                                >
                                    <option value="all">All Statuses</option>
                                    <option value="enabled">Enabled</option>
                                    <option value="disabled">Disabled</option>
                                </select>
                            </div>
                        </div>
                    </div>

                    {#if isLoadingUsers}
                        <div class="text-center py-12">
                            <div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-brand"></div>
                            <p class="mt-2 text-gray-600">Loading users...</p>
                        </div>
                    {:else}
                        <!-- Bulk Actions Toolbar -->
                        {#if selectedUsers.length > 0}
                            <div class="bg-blue-50 border-l-4 border-blue-500 p-4 mb-4 rounded-r-lg shadow-sm">
                                <div class="flex items-center justify-between flex-wrap gap-3">
                                    <div class="flex items-center">
                                        <svg class="h-5 w-5 text-blue-600 mr-2" fill="currentColor" viewBox="0 0 20 20">
                                            <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd" />
                                        </svg>
                                        <span class="text-sm font-medium text-blue-900">
                                            {selectedUsers.length} user{selectedUsers.length > 1 ? 's' : ''} selected
                                        </span>
                                    </div>
                                    <div class="flex gap-2">
                                        <button
                                            onclick={openBulkDisableModal}
                                            class="inline-flex items-center px-3 py-1.5 border border-transparent text-sm font-medium rounded-md text-white bg-yellow-600 hover:bg-yellow-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-yellow-500"
                                        >
                                            <svg class="w-4 h-4 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728L5.636 5.636m12.728 12.728L18.364 5.636M5.636 18.364l12.728-12.728" />
                                            </svg>
                                            Disable Selected
                                        </button>
                                        <button
                                            onclick={openBulkEnableModal}
                                            class="inline-flex items-center px-3 py-1.5 border border-transparent text-sm font-medium rounded-md text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500"
                                        >
                                            <svg class="w-4 h-4 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                            </svg>
                                            Enable Selected
                                        </button>
                                        <button
                                            onclick={() => { displayUsers.forEach(u => u.selected = false); selectedUsers = []; }}
                                            class="inline-flex items-center px-3 py-1.5 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand"
                                        >
                                            Clear
                                        </button>
                                    </div>
                                </div>
                            </div>
                        {/if}

                        <!-- Users Table -->
                        <div class="overflow-x-auto shadow-md sm:rounded-lg mb-6 border border-gray-200">
                            <table class="min-w-full divide-y divide-gray-200">
                                <thead class="bg-gray-50">
                                    <tr>
                                        <!-- Select All Checkbox -->
                                        <th scope="col" class="px-3 py-3 text-left">
                                            <input
                                                type="checkbox"
                                                checked={selectedUsers.length > 0 && selectedUsers.length === displayUsers.filter(u => !(userData && userData.email === u.email)).length}
                                                onchange={(e) => {
                                                    const checked = e.target?.checked;
                                                    displayUsers = displayUsers.map(u => {
                                                        // Don't allow selection of current user
                                                        if (userData && userData.email === u.email) {
                                                            return u;
                                                        }
                                                        return {...u, selected: checked};
                                                    });
                                                }}
                                                class="h-4 w-4 text-brand focus:ring-brand border-gray-300 rounded"
                                            />
                                        </th>
                                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-brand uppercase tracking-wider">
                                            Name
                                        </th>
                                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-brand uppercase tracking-wider">
                                            Email
                                        </th>
                                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-brand uppercase tracking-wider">
                                            User Type
                                        </th>
                                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-brand uppercase tracking-wider">
                                            Status
                                        </th>
                                        <th scope="col" class="px-6 py-3 text-center text-xs font-medium text-brand uppercase tracking-wider">
                                            Can Share
                                        </th>
                                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-brand uppercase tracking-wider">
                                            Actions
                                        </th>
                                    </tr>
                                </thead>
                                <tbody class="bg-white divide-y divide-gray-200">
                                    {#if displayUsers.length === 0}
                                        <tr>
                                            <td colspan="6" class="px-6 py-8 text-center text-gray-500">
                                                {#if usersSearchQuery || usersFilterUserType !== 'all' || usersFilterStatus !== 'all'}
                                                    No users match your filters. Try adjusting the search or filters.
                                                {:else}
                                                    No users found in your organization.
                                                {/if}
                                            </td>
                                        </tr>
                                    {:else}
                                        {#each displayUsers as user (user.id)}
                                            <tr class="hover:bg-gray-50 {user.selected ? 'bg-blue-50' : ''}">
                                                <!-- Checkbox -->
                                                <td class="px-3 py-4 whitespace-nowrap">
                                                    <input
                                                        type="checkbox"
                                                        bind:checked={user.selected}
                                                        disabled={userData && userData.email === user.email}
                                                        class="h-4 w-4 text-brand focus:ring-brand border-gray-300 rounded disabled:opacity-50 disabled:cursor-not-allowed"
                                                    />
                                                </td>
                                                <!-- Name -->
                                                <td class="px-6 py-4 whitespace-nowrap">
                                                    <div class="text-sm font-medium text-gray-900">{user.name || '-'}</div>
                                                </td>
                                                <!-- Email -->
                                                <td class="px-6 py-4 whitespace-nowrap">
                                                    <div class="text-sm text-gray-800">{user.email}</div>
                                                    {#if userData && userData.email === user.email}
                                                        <span class="text-xs text-gray-500 italic">(You)</span>
                                                    {/if}
                                                </td>
                                                <!-- User Type -->
                                                <td class="px-6 py-4 whitespace-nowrap text-sm">
                                                    <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full {user.user_type === 'end_user' ? 'bg-purple-100 text-purple-800' : 'bg-brand/10 text-brand'}">
                                                        {user.user_type === 'end_user' ? 'End User' : 'Creator'}
                                                    </span>
                                                </td>
                                                <!-- Status -->
                                                <td class="px-6 py-4 whitespace-nowrap text-sm">
                                                    <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full {user.enabled ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}">
                                                        {user.enabled ? 'Enabled' : 'Disabled'}
                                                    </span>
                                                </td>
                                                <!-- Can Share Permission -->
                                                <td class="px-6 py-4 whitespace-nowrap text-center">
                                                    <label class="relative inline-flex items-center cursor-pointer">
                                                        <input 
                                                            type="checkbox" 
                                                            class="sr-only peer"
                                                            checked={getUserCanShare(user)}
                                                            onchange={(e) => toggleUserSharingPermission(user, e.target?.checked)}
                                                        />
                                                        <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                                                    </label>
                                                </td>
                                                <!-- Actions -->
                                                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium">
                                                    <!-- Change Password -->
                                                    <button
                                                        class="text-amber-600 hover:text-amber-800 mr-3"
                                                        title="Change Password"
                                                        aria-label="Change Password for {user.name}"
                                                        onclick={() => openChangePasswordModal(user)}
                                                    >
                                                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5">
                                                            <path stroke-linecap="round" stroke-linejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
                                                        </svg>
                                                    </button>
                                                    
                                                    <!-- Enable/Disable Toggle -->
                                                    {#if user.enabled}
                                                        <button
                                                            class={userData && userData.email === user.email
                                                                ? "text-gray-400 cursor-not-allowed mr-3"
                                                                : "text-yellow-600 hover:text-yellow-800 mr-3"}
                                                            title={userData && userData.email === user.email 
                                                                ? "You cannot disable your own account" 
                                                                : 'Disable User'}
                                                            aria-label="Disable {user.name}"
                                                            onclick={() => toggleUserStatus(user)}
                                                            disabled={userData && userData.email === user.email}
                                                        >
                                                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5">
                                                                <path stroke-linecap="round" stroke-linejoin="round" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728L5.636 5.636m12.728 12.728L18.364 5.636M5.636 18.364l12.728-12.728" />
                                                            </svg>
                                                        </button>
                                                    {:else}
                                                        <button
                                                            class="text-green-600 hover:text-green-800 mr-3"
                                                            title="Enable User"
                                                            aria-label="Enable {user.name}"
                                                            onclick={() => toggleUserStatus(user)}
                                                        >
                                                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5">
                                                                <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                                            </svg>
                                                        </button>
                                                    {/if}
                                                    
                                                    <!-- Disable (Block) Button -->
                                                    <button
                                                        class={userData && userData.email === user.email 
                                                            ? "text-gray-400 cursor-not-allowed" 
                                                            : "text-red-600 hover:text-red-800"}
                                                        title={userData && userData.email === user.email 
                                                            ? "You cannot disable your own account" 
                                                            : 'Disable User'}
                                                        aria-label="Disable {user.name}"
                                                        onclick={() => openDeleteUserModal(user)}
                                                        disabled={userData && userData.email === user.email}
                                                    >
                                                        <!-- Block Icon -->
                                                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5">
                                                            <path stroke-linecap="round" stroke-linejoin="round" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728A9 9 0 015.636 5.636" />
                                                        </svg>
                                                    </button>
                                                </td>
                                            </tr>
                                        {/each}
                                    {/if}
                                </tbody>
                            </table>
                        </div>
                        
                        <!-- Pagination -->
                        {#if usersTotalPages > 1}
                            <Pagination
                                currentPage={usersPage}
                                totalPages={usersTotalPages}
                                on:pageChange={handleUsersPageChange}
                                itemsPerPage={usersPerPage}
                                itemsPerPageOptions={[10, 25, 50, 100]}
                                on:itemsPerPageChange={handleUsersPerPageChange}
                            />
                        {/if}
                    {/if}
                </div>
            {/if}

            <!-- Assistants Access View -->
            {#if currentView === 'assistants'}
                <div class="mb-6">
                    <!-- Assistants Header -->
                    <div class="bg-white shadow-sm rounded-lg p-4 mb-6">
                        <div class="flex justify-between items-center">
                            <div>
                                <h2 class="text-xl font-semibold text-gray-800">Organization Assistants</h2>
                                <p class="text-sm text-gray-600 mt-1">View and manage user access to all assistants in your organization</p>
                            </div>
                        </div>
                    </div>

                    <!-- Controls -->
                    <div class="bg-white shadow-sm rounded-lg p-4 mb-4">
                        <div class="flex gap-4 flex-wrap items-center">
                            <div class="flex-1 min-w-[200px]">
                                <input
                                    type="text"
                                    placeholder="Search assistants..."
                                    bind:value={assistantsSearchQuery}
                                    class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                />
                            </div>
                            <div class="flex items-center gap-2">
                                <label for="filter-published" class="text-sm font-medium text-gray-700">Filter:</label>
                                <select
                                    id="filter-published"
                                    bind:value={assistantsFilterPublished}
                                    class="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                >
                                    <option value="all">All Assistants</option>
                                    <option value="published">Published Only</option>
                                    <option value="unpublished">Unpublished Only</option>
                                </select>
                            </div>
                            <button
                                onclick={fetchAssistants}
                                disabled={isLoadingAssistants}
                                class="bg-brand hover:bg-brand-hover px-4 py-2 text-white rounded-md disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                {isLoadingAssistants ? 'Loading...' : 'Refresh'}
                            </button>
                        </div>
                    </div>

                    <!-- Error Message -->
                    {#if assistantsError}
                        <div class="mb-4 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded-md">
                            {assistantsError}
                        </div>
                    {/if}

                    <!-- Loading State -->
                    {#if isLoadingAssistants}
                        <div class="bg-white shadow-sm rounded-lg p-8 text-center">
                            <div class="text-gray-600">Loading assistants...</div>
                        </div>
                    {:else}
                        {#if orgAssistants.filter(asst => {
                            const matchesSearch = !assistantsSearchQuery || 
                                asst.name.toLowerCase().includes(assistantsSearchQuery.toLowerCase()) ||
                                asst.owner.toLowerCase().includes(assistantsSearchQuery.toLowerCase()) ||
                                (asst.description && asst.description.toLowerCase().includes(assistantsSearchQuery.toLowerCase()));
                            const matchesPublished = 
                                assistantsFilterPublished === 'all' ||
                                (assistantsFilterPublished === 'published' && asst.published) ||
                                (assistantsFilterPublished === 'unpublished' && !asst.published);
                            return matchesSearch && matchesPublished;
                        }).length === 0}
                            <!-- Empty State -->
                            <div class="bg-white shadow-sm rounded-lg p-8 text-center">
                                <div class="text-gray-600">
                                    {#if assistantsSearchQuery || assistantsFilterPublished !== 'all'}
                                        <p>No assistants match your search criteria.</p>
                                        <button
                                            onclick={() => { assistantsSearchQuery = ''; assistantsFilterPublished = 'all'; }}
                                            class="mt-4 px-4 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300"
                                        >
                                            Clear Filters
                                        </button>
                                    {:else}
                                        <p>No assistants found in your organization.</p>
                                    {/if}
                                </div>
                            </div>
                        {:else}
                            <!-- Assistants Table -->
                            <div class="bg-white shadow-sm rounded-lg overflow-x-auto">
                                <table class="min-w-full divide-y divide-gray-200">
                                    <thead class="bg-gray-50">
                                        <tr>
                                            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
                                            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Description</th>
                                            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Owner</th>
                                            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                                            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Shared</th>
                                            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Created</th>
                                            <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody class="bg-white divide-y divide-gray-200">
                                        {#each orgAssistants.filter(asst => {
                                            const matchesSearch = !assistantsSearchQuery || 
                                                asst.name.toLowerCase().includes(assistantsSearchQuery.toLowerCase()) ||
                                                asst.owner.toLowerCase().includes(assistantsSearchQuery.toLowerCase()) ||
                                                (asst.description && asst.description.toLowerCase().includes(assistantsSearchQuery.toLowerCase()));
                                            const matchesPublished = 
                                                assistantsFilterPublished === 'all' ||
                                                (assistantsFilterPublished === 'published' && asst.published) ||
                                                (assistantsFilterPublished === 'unpublished' && !asst.published);
                                            return matchesSearch && matchesPublished;
                                        }) as assistant}
                                            <tr class="hover:bg-gray-50">
                                                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                                                    {assistant.name}
                                                </td>
                                                <td class="px-6 py-4 text-sm text-gray-600 max-w-xs truncate">
                                                    {assistant.description || '—'}
                                                </td>
                                                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-600 font-mono text-xs">
                                                    {assistant.owner}
                                                </td>
                                                <td class="px-6 py-4 whitespace-nowrap">
                                                    {#if assistant.published}
                                                        <span class="px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800">
                                                            Published
                                                        </span>
                                                    {:else}
                                                        <span class="px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded-full bg-red-100 text-red-800">
                                                            Unpublished
                                                        </span>
                                                    {/if}
                                                </td>
                                                <!-- Shared Column -->
                                                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                                                    {#if assistantShareCounts[assistant.id] !== undefined}
                                                        {#if assistantShareCounts[assistant.id] === 0}
                                                            <span class="text-gray-400">Not shared</span>
                                                        {:else}
                                                            <span class="text-blue-600 font-medium">
                                                                Shared with {assistantShareCounts[assistant.id]} {assistantShareCounts[assistant.id] === 1 ? 'user' : 'users'}
                                                            </span>
                                                        {/if}
                                                    {:else}
                                                        <span class="text-gray-400">—</span>
                                                    {/if}
                                                </td>
                                                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                                                    {formatDate(assistant.created_at)}
                                                </td>
                                                <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                                                    <button
                                                        onclick={() => openAssistantSharingModal(assistant)}
                                                        class="bg-brand hover:bg-brand-hover px-3 py-1 text-white rounded-md text-xs"
                                                    >
                                                        Manage Sharing
                                                    </button>
                                                </td>
                                            </tr>
                                        {/each}
                                    </tbody>
                                </table>
                            </div>
                        {/if}
                    {/if}
                </div>
            {/if}

            <!-- Settings View -->
            {#if currentView === 'settings'}
                <div class="mb-6">
                    <!-- Organization Header for Settings -->
                    {#if dashboardData}
                        <div class="bg-white border-l-4 border-brand shadow-sm rounded-lg mb-4">
                            <div class="px-4 py-3">
                                <div class="flex items-center justify-between">
                                    <div>
                                        <h1 class="text-xl font-semibold text-gray-900">{dashboardData.organization.name}</h1>
                                        <p class="text-sm text-gray-600">Organization Settings</p>
                                    </div>
                                    <div class="text-right text-sm text-gray-500">
                                        {#if targetOrgSlug}
                                            <div class="text-xs text-brand mb-1">
                                                <svg class="inline h-3 w-3 mr-1" fill="currentColor" viewBox="0 0 20 20">
                                                    <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"></path>
                                                </svg>
                                                System Admin View
                                            </div>
                                        {/if}
                                        ID: {dashboardData.organization.slug}
                                    </div>
                                </div>
                            </div>
                        </div>
                    {/if}
                    
                    <h2 class="text-2xl font-semibold text-gray-800 mb-4">Configuration</h2>

                    {#if settingsError}
                        <div class="mb-4 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative" role="alert">
                            <span class="block sm:inline">{settingsError}</span>
                        </div>
                    {/if}

                    {#if isLoadingSettings}
                        <div class="text-center py-12">
                            <div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-brand"></div>
                            <p class="mt-2 text-gray-600">Loading settings...</p>
                        </div>
                    {:else}
                        <!-- Settings Sub-Navigation -->
                        <div class="bg-white shadow-sm rounded-lg mb-4">
                            <div class="border-b border-gray-200">
                                <nav class="flex -mb-px" aria-label="Settings Tabs">
                                    <button
                                        class="px-6 py-3 border-b-2 font-medium text-sm transition-colors duration-200 {settingsSubView === 'general' ? 'border-brand text-brand' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'}"
                                        onclick={() => { settingsSubView = 'general'; }}
                                    >
                                        General
                                    </button>
                                    <button
                                        class="px-6 py-3 border-b-2 font-medium text-sm transition-colors duration-200 {settingsSubView === 'api' ? 'border-brand text-brand' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'}"
                                        onclick={async () => { 
                                            settingsSubView = 'api';
                                            // Lazy load API settings and dashboard (for API status) when tab is clicked
                                            // Check if available_models exists and has data (it's initialized as empty array)
                                            const hasModels = apiSettings.available_models && 
                                                ((Array.isArray(apiSettings.available_models) && apiSettings.available_models.length > 0) ||
                                                 (typeof apiSettings.available_models === 'object' && Object.keys(apiSettings.available_models).length > 0));
                                            
                                            if (!hasModels) {
                                                await fetchApiSettings();
                                            }
                                            if (!dashboardData) {
                                                await fetchDashboard();
                                            }
                                        }}
                                    >
                                        API
                                    </button>
                                    <button
                                        class="px-6 py-3 border-b-2 font-medium text-sm transition-colors duration-200 {settingsSubView === 'kb' ? 'border-brand text-brand' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'}"
                                        onclick={() => { 
                                            settingsSubView = 'kb';
                                            // Lazy load KB settings only when tab is clicked
                                            if (!kbSettings.url) {
                                                fetchKbSettings();
                                            }
                                        }}
                                    >
                                        Knowledge Base
                                    </button>
                                    <button
                                        class="px-6 py-3 border-b-2 font-medium text-sm transition-colors duration-200 {settingsSubView === 'defaults' ? 'border-brand text-brand' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'}"
                                        onclick={() => { 
                                            settingsSubView = 'defaults';
                                            // Lazy load assistant defaults only when tab is clicked
                                            if (!assistantDefaults) {
                                                fetchAssistantDefaults();
                                            }
                                        }}
                                    >
                                        Assistant Defaults
                                    </button>
                                </nav>
                            </div>
                        </div>

                        <!-- General Settings Tab -->
                        {#if settingsSubView === 'general'}
                        <!-- Signup Settings -->
                        <div class="bg-white overflow-hidden shadow rounded-lg mb-6">
                            <div class="px-4 py-5 sm:p-6">
                                <h3 class="text-lg leading-6 font-medium text-gray-900 mb-4">Signup Settings</h3>
                                
                                <!-- Error Message -->
                                {#if signupSettingsError}
                                    <div class="mb-4 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative" role="alert">
                                        <strong class="font-bold">Error: </strong>
                                        <span class="block sm:inline">{signupSettingsError}</span>
                                    </div>
                                {/if}
                                
                                <!-- Success Message -->
                                {#if signupSettingsSuccess}
                                    <div class="mb-4 bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded relative" role="alert">
                                        <strong class="font-bold">Success! </strong>
                                        <span class="block sm:inline">Signup settings updated successfully.</span>
                                    </div>
                                {/if}
                                
                                <div class="space-y-4">
                                    <div class="flex items-center">
                                        <input
                                            id="signup-enabled"
                                            type="checkbox"
                                            bind:checked={newSignupSettings.signup_enabled}
                                            class="h-4 w-4 text-brand focus:ring-brand border-gray-300 rounded"
                                        >
                                        <label for="signup-enabled" class="ml-2 block text-sm text-gray-900">
                                            Enable organization-specific signup
                                        </label>
                                    </div>

                                    {#if newSignupSettings.signup_enabled}
                                        <div>
                                            <label for="signup-key" class="block text-sm font-medium text-gray-700">Signup Key *</label>
                                            <input
                                                type="text"
                                                id="signup-key"
                                                bind:value={newSignupSettings.signup_key}
                                                class="mt-1 block w-full border border-gray-300 rounded-md px-3 py-2 shadow-sm focus:outline-none focus:ring-brand focus:border-brand"
                                                placeholder="Enter unique signup key"
                                                required={newSignupSettings.signup_enabled}
                                                pattern="[a-zA-Z0-9_-]+"
                                                minlength="8"
                                                maxlength="64"
                                                title="Signup key must be 8-64 characters long and can only contain letters, numbers, hyphens, and underscores. Cannot start or end with hyphens or underscores."
                                            >
                                            <p class="mt-1 text-sm text-gray-500">
                                                Unique key for users to signup to this organization (8-64 characters, letters, numbers, hyphens, and underscores only)
                                            </p>
                                        </div>
                                    {/if}

                                    <button
                                        onclick={updateSignupSettings}
                                        class="bg-brand hover:bg-brand-hover text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline"
                                    >
                                        Update Signup Settings
                                    </button>
                                </div>
                            </div>
                        </div>
                        {/if}

                        <!-- API Configuration Tab -->
                        {#if settingsSubView === 'api'}
                        <!-- API Status Overview -->
                        {#if isLoadingDashboard}
                            <div class="bg-white overflow-hidden shadow rounded-lg mb-6">
                                <div class="px-4 py-5 sm:p-6">
                                    <h3 class="text-lg leading-6 font-medium text-gray-900 mb-4">API Status Overview</h3>
                                    <div class="flex items-center justify-center py-8">
                                        <div class="inline-block animate-spin rounded-full h-6 w-6 border-b-2 border-brand mr-3"></div>
                                        <span class="text-gray-500">Checking API connections...</span>
                                    </div>
                                </div>
                            </div>
                        {:else if dashboardData && dashboardData.api_status}
                            <div class="bg-white overflow-hidden shadow rounded-lg mb-6">
                                <div class="px-4 py-5 sm:p-6">
                                    <h3 class="text-lg leading-6 font-medium text-gray-900 mb-4">API Status Overview</h3>
                                    
                                    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                                        {#each Object.entries(dashboardData.api_status.providers) as [providerName, providerStatus]}
                                            <div class="border rounded-lg p-4">
                                                <div class="flex items-center justify-between mb-2">
                                                    <h4 class="font-medium text-gray-900 capitalize">{providerName}</h4>
                                                    <span class="px-2 py-1 text-xs rounded-full {
                                                        providerStatus.status === 'working' ? 'bg-green-100 text-green-800' :
                                                        providerStatus.status === 'error' ? 'bg-red-100 text-red-800' :
                                                        'bg-gray-100 text-gray-800'
                                                    }">
                                                        {providerStatus.status}
                                                    </span>
                                                </div>
                                                
                                                {#if providerStatus.status === 'working'}
                                                    <div class="text-sm text-gray-600 mb-2">
                                                        <strong>{providerStatus.model_count}</strong> models available
                                                        {#if providerStatus.enabled_models && providerStatus.enabled_models.length > 0}
                                                            <span class="text-brand">• <strong>{providerStatus.enabled_models.length}</strong> selected</span>
                                                            {#if providerStatus.default_model}
                                                                <span class="text-brand">• Default: {providerStatus.default_model}</span>
                                                            {/if}
                                                        {:else}
                                                            <span class="text-gray-500">• No models selected</span>
                                                        {/if}
                                                    </div>
                                                    
                                                    <!-- Warning message (e.g., needs model selection) -->
                                                    {#if providerStatus.warning}
                                                        <div class="bg-yellow-50 border border-yellow-200 rounded p-2 mb-2">
                                                            <div class="flex items-start">
                                                                <span class="text-yellow-500 mr-2">⚠️</span>
                                                                <span class="text-sm text-yellow-800">{providerStatus.warning}</span>
                                                            </div>
                                                            {#if providerStatus.needs_model_selection}
                                                                <div class="mt-2">
                                                                    <button
                                                                        type="button"
                                                                        class="text-xs bg-yellow-100 hover:bg-yellow-200 text-yellow-800 px-2 py-1 rounded"
                                                                        onclick={() => openModelModal(providerName, providerStatus.models || [])}
                                                                    >
                                                                        Select Models →
                                                                    </button>
                                                                </div>
                                                            {/if}
                                                        </div>
                                                    {/if}
                                                    
                                                    {#if providerStatus.models && providerStatus.models.length > 0}
                                                        <div class="text-xs text-gray-500">
                                                            <div class="max-h-20 overflow-y-auto">
                                                                {#each providerStatus.models.slice(0, 10) as model}
                                                                    <div class="py-1">{model}</div>
                                                                {/each}
                                                                {#if providerStatus.models.length > 10}
                                                                    <div class="py-1 font-medium">...and {providerStatus.models.length - 10} more</div>
                                                                {/if}
                                                            </div>
                                                        </div>
                                                    {/if}
                                                {:else if providerStatus.error}
                                                    <div class="text-sm text-red-600 mb-2">
                                                        <strong>Error:</strong> {providerStatus.error}
                                                    </div>
                                                    {#if providerStatus.error_code}
                                                        <div class="text-xs text-gray-500">
                                                            Error code: {providerStatus.error_code}
                                                        </div>
                                                    {/if}
                                                    <!-- Show models if available even on error (e.g., model test failed but list succeeded) -->
                                                    {#if providerStatus.models && providerStatus.models.length > 0}
                                                        <div class="mt-2 pt-2 border-t border-gray-200">
                                                            <div class="text-xs text-gray-600 mb-1">
                                                                <strong>{providerStatus.model_count}</strong> models available (connection works, but test failed)
                                                            </div>
                                                            <button
                                                                type="button"
                                                                class="text-xs bg-blue-100 hover:bg-blue-200 text-blue-800 px-2 py-1 rounded"
                                                                onclick={() => openModelModal(providerName, providerStatus.models || [])}
                                                            >
                                                                Manage Models →
                                                            </button>
                                                        </div>
                                                    {/if}
                                                {/if}
                                                
                                                {#if providerStatus.api_base}
                                                    <div class="text-xs text-gray-400 mt-2">
                                                        {providerStatus.api_base}
                                                    </div>
                                                {/if}
                                            </div>
                                        {/each}
                                    </div>
                                    
                                    {#if Object.keys(dashboardData.api_status.providers).length === 0}
                                        <div class="text-center py-8 text-gray-500">
                                            <p>No API providers configured</p>
                                            <p class="text-sm mt-1">Configure OpenAI or Ollama below to get started</p>
                                        </div>
                                    {/if}
                                </div>
                            </div>
                        {:else}
                            <div class="bg-white overflow-hidden shadow rounded-lg mb-6">
                                <div class="px-4 py-5 sm:p-6">
                                    <h3 class="text-lg leading-6 font-medium text-gray-900 mb-4">API Status Overview</h3>
                                    <div class="text-center py-8 text-gray-500">
                                        <p>API status not available</p>
                                        <p class="text-sm mt-1">Configure your API settings below, then save to check connection status</p>
                                    </div>
                                </div>
                            </div>
                        {/if}

                        <!-- API Settings -->
                        <div class="bg-white overflow-hidden shadow rounded-lg">
                            <div class="px-4 py-5 sm:p-6">
                                <h3 class="text-lg leading-6 font-medium text-gray-900 mb-4">API Configuration</h3>
                                
                                <div class="space-y-4">
                                    <div>
                                        <label for="openai-key" class="block text-sm font-medium text-gray-700">OpenAI API Key</label>
                                        <input
                                            type="password"
                                            id="openai-key"
                                            bind:value={newApiSettings.openai_api_key}
                                            class="mt-1 block w-full border border-gray-300 rounded-md px-3 py-2 shadow-sm focus:outline-none focus:ring-brand focus:border-brand"
                                            placeholder={apiSettings.openai_api_key_set ? "••••••••••••••••" : "Enter OpenAI API key"}
                                            onchange={() => newApiSettings.openai_api_key && addPendingChange('OpenAI API key updated')}
                                        >
                                        <p class="mt-1 text-sm text-gray-500">
                                            {#if apiSettings.openai_api_key_set}
                                                API key is currently set. Enter a new key to replace it.
                                            {:else}
                                                Enter your OpenAI API key to enable AI features.
                                            {/if}
                                        </p>
                                    </div>

                                    <div>
                                        <label for="openai-base-url" class="block text-sm font-medium text-gray-700">OpenAI Base URL</label>
                                        <input
                                            type="url"
                                            id="openai-base-url"
                                            bind:value={newApiSettings.openai_base_url}
                                            class="mt-1 block w-full border border-gray-300 rounded-md px-3 py-2 shadow-sm focus:outline-none focus:ring-brand focus:border-brand"
                                            placeholder="https://api.openai.com/v1"
                                        >
                                        <p class="mt-1 text-sm text-gray-500">
                                            Custom OpenAI API endpoint. Leave empty to use default (https://api.openai.com/v1).
                                        </p>
                                    </div>

                                    <div>
                                        <label for="ollama-base-url" class="block text-sm font-medium text-gray-700">Ollama Server URL</label>
                                        <input
                                            type="url"
                                            id="ollama-base-url"
                                            bind:value={newApiSettings.ollama_base_url}
                                            class="mt-1 block w-full border border-gray-300 rounded-md px-3 py-2 shadow-sm focus:outline-none focus:ring-brand focus:border-brand"
                                            placeholder="http://localhost:11434"
                                        >
                                        <p class="mt-1 text-sm text-gray-500">
                                            URL of your Ollama server. This can be a local or remote Ollama installation.
                                        </p>
                                    </div>

                                    <!-- Model Selection -->
                                    <div>
                                        <h4 class="block text-sm font-medium text-gray-700 mb-3">Model Selection</h4>
                                        <p class="text-sm text-gray-500 mb-4">
                                            Configure which models are available to users in your organization
                                        </p>
                                        
                                        <!-- Show loading state while checking API status -->
                                        {#if isLoadingDashboard}
                                            <div class="border rounded-lg p-6 bg-gray-50">
                                                <div class="flex items-center justify-center">
                                                    <div class="inline-block animate-spin rounded-full h-5 w-5 border-b-2 border-brand mr-3"></div>
                                                    <span class="text-gray-500">Loading available models...</span>
                                                </div>
                                            </div>
                                        <!-- Use fresh models from API status check (dashboardData) as primary source -->
                                        {:else if dashboardData?.api_status?.providers && Object.keys(dashboardData.api_status.providers).length > 0}
                                            {#each Object.entries(dashboardData.api_status.providers) as [providerName, providerStatus]}
                                                {@const freshModels = providerStatus.models || []}
                                                <div class="mb-6 border rounded-lg p-4">
                                                    <div class="flex items-center justify-between mb-3">
                                                        <h4 class="font-medium text-gray-900 capitalize">{providerName}</h4>
                                                        <button
                                                            type="button"
                                                            class="bg-brand hover:bg-brand-hover px-3 py-1 text-sm text-white rounded"
                                                            onclick={() => openModelModal(providerName, freshModels)}
                                                        >
                                                            Manage Models
                                                        </button>
                                                    </div>
                                                    
                                                    <div class="text-sm text-gray-600 mb-2">
                                                        <strong>{newApiSettings.selected_models?.[providerName]?.length || 0}</strong> of {freshModels.length} models enabled
                                                    </div>
                                                    
                                                    <div class="bg-gray-50 rounded p-3 max-h-32 overflow-y-auto">
                                                        {#if newApiSettings.selected_models?.[providerName]?.length > 0}
                                                            <div class="flex flex-wrap gap-1">
                                                                {#each newApiSettings.selected_models[providerName] as model}
                                                                    <span class="inline-block px-2 py-1 text-xs bg-brand/10 text-brand rounded">
                                                                        {model}
                                                                    </span>
                                                                {/each}
                                                            </div>
                                                        {:else}
                                                            <p class="text-gray-500 text-sm italic">No models enabled</p>
                                                        {/if}
                                                    </div>

                                                    <!-- Default Model Selection - uses selected_models which user can choose from fresh models -->
                                                    {#if newApiSettings.selected_models?.[providerName]?.length > 0}
                                                        <div class="mt-3">
                                                            <label for="default-model-{providerName}" class="block text-sm font-medium text-gray-700 mb-2">
                                                                Default Model
                                                            </label>
                                                            <select
                                                                id="default-model-{providerName}"
                                                                bind:value={newApiSettings.default_models[providerName]}
                                                                class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                                                onchange={() => addPendingChange(`Default model changed for ${providerName}`)}
                                                            >
                                                                <option value="">Select a default model...</option>
                                                                {#each newApiSettings.selected_models[providerName] as model}
                                                                    <option value={model}>{model}</option>
                                                                {/each}
                                                            </select>
                                                            <p class="mt-1 text-xs text-gray-500">
                                                                This model will be used as the default when creating new assistants for this provider.
                                                            </p>
                                                        </div>
                                                    {/if}
                                                </div>
                                            {/each}
                                        {:else if apiSettings.available_models && Object.keys(apiSettings.available_models || {}).length > 0}
                                            <!-- Fallback to cached apiSettings if dashboard not loaded -->
                                            {#each Object.entries(apiSettings.available_models) as [providerName, models]}
                                                <div class="mb-6 border rounded-lg p-4">
                                                    <div class="flex items-center justify-between mb-3">
                                                        <h4 class="font-medium text-gray-900 capitalize">{providerName}</h4>
                                                        <button
                                                            type="button"
                                                            class="bg-brand hover:bg-brand-hover px-3 py-1 text-sm text-white rounded"
                                                            onclick={() => openModelModal(providerName, models)}
                                                        >
                                                            Manage Models
                                                        </button>
                                                    </div>
                                                    
                                                    <div class="text-sm text-gray-600 mb-2">
                                                        <strong>{newApiSettings.selected_models?.[providerName]?.length || 0}</strong> of {models.length} models enabled
                                                        <span class="text-yellow-600 text-xs ml-2">(cached - refresh to get latest)</span>
                                                    </div>
                                                    
                                                    <div class="bg-gray-50 rounded p-3 max-h-32 overflow-y-auto">
                                                        {#if newApiSettings.selected_models?.[providerName]?.length > 0}
                                                            <div class="flex flex-wrap gap-1">
                                                                {#each newApiSettings.selected_models[providerName] as model}
                                                                    <span class="inline-block px-2 py-1 text-xs bg-brand/10 text-brand rounded">
                                                                        {model}
                                                                    </span>
                                                                {/each}
                                                            </div>
                                                        {:else}
                                                            <p class="text-gray-500 text-sm italic">No models enabled</p>
                                                        {/if}
                                                    </div>

                                                    <!-- Default Model Selection -->
                                                    {#if newApiSettings.selected_models?.[providerName]?.length > 0}
                                                        <div class="mt-3">
                                                            <label for="default-model-{providerName}" class="block text-sm font-medium text-gray-700 mb-2">
                                                                Default Model
                                                            </label>
                                                            <select
                                                                id="default-model-{providerName}"
                                                                bind:value={newApiSettings.default_models[providerName]}
                                                                class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                                                onchange={() => addPendingChange(`Default model changed for ${providerName}`)}
                                                            >
                                                                <option value="">Select a default model...</option>
                                                                {#each newApiSettings.selected_models[providerName] as model}
                                                                    <option value={model}>{model}</option>
                                                                {/each}
                                                            </select>
                                                            <p class="mt-1 text-xs text-gray-500">
                                                                This model will be used as the default when creating new assistants for this provider.
                                                            </p>
                                                        </div>
                                                    {/if}
                                                </div>
                                            {/each}
                                        {:else}
                                            <div class="border rounded-lg p-6 bg-gray-50">
                                                <div class="text-center text-gray-500">
                                                    <svg class="mx-auto h-10 w-10 text-gray-400 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                                                    </svg>
                                                    <p class="font-medium">No API providers configured</p>
                                                    <p class="text-sm mt-1">Enter your API credentials above and save to see available models</p>
                                                </div>
                                            </div>
                                        {/if}
                                    </div>

                                    <!-- Global Model Configurations -->
                                    <div class="mt-8 space-y-6">
                                        <h3 class="text-lg font-semibold text-gray-900 border-b pb-2">
                                            Global Model Configuration
                                        </h3>
                                        <p class="text-sm text-gray-600">
                                            Configure organization-wide default models that apply across all assistants and operations.
                                        </p>

                                        <!-- Global Default Model Configuration -->
                                        <div class="p-4 bg-indigo-50 border border-indigo-200 rounded-md">
                                            <h4 class="text-md font-semibold text-indigo-900 mb-3">
                                                Global Default Model
                                            </h4>
                                            <p class="text-sm text-indigo-700 mb-4">
                                                The primary model for this organization. Used for assistants and completions when 
                                                no specific model is configured. This overrides per-provider defaults.
                                            </p>
                                            
                                            <div class="grid grid-cols-2 gap-4">
                                                <!-- Provider Selection -->
                                                <div>
                                                    <label for="global-default-provider" class="block text-sm font-medium text-gray-700 mb-2">
                                                        Provider
                                                    </label>
                                                    <select
                                                        id="global-default-provider"
                                                        bind:value={newApiSettings.global_default_model.provider}
                                                        class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
                                                        onchange={() => {
                                                            // Reset model when provider changes
                                                            newApiSettings.global_default_model.model = '';
                                                            addPendingChange('Global default model provider changed');
                                                        }}
                                                    >
                                                        <option value="">-- None --</option>
                                                        {#each Object.keys(newApiSettings.selected_models || {}) as providerName}
                                                            {#if newApiSettings.selected_models[providerName]?.length > 0}
                                                                <option value={providerName}>{providerName}</option>
                                                            {/if}
                                                        {/each}
                                                    </select>
                                                </div>
                                                
                                                <!-- Model Selection -->
                                                <div>
                                                    <label for="global-default-model" class="block text-sm font-medium text-gray-700 mb-2">
                                                        Model
                                                    </label>
                                                    <select
                                                        id="global-default-model"
                                                        bind:value={newApiSettings.global_default_model.model}
                                                        class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
                                                        disabled={!newApiSettings.global_default_model.provider}
                                                        onchange={() => addPendingChange('Global default model changed')}
                                                    >
                                                        <option value="">-- Select Model --</option>
                                                        {#if newApiSettings.global_default_model.provider && newApiSettings.selected_models[newApiSettings.global_default_model.provider]}
                                                            {#each newApiSettings.selected_models[newApiSettings.global_default_model.provider] as model}
                                                                <option value={model}>{model}</option>
                                                            {/each}
                                                        {/if}
                                                    </select>
                                                </div>
                                            </div>
                                            
                                            {#if newApiSettings.global_default_model.provider && newApiSettings.global_default_model.model}
                                                <div class="mt-3 p-2 bg-indigo-100 border border-indigo-300 rounded text-sm text-indigo-900">
                                                    ✓ Global default model configured: 
                                                    <strong>{newApiSettings.global_default_model.provider}/{newApiSettings.global_default_model.model}</strong>
                                                </div>
                                            {:else}
                                                <div class="mt-3 p-2 bg-gray-50 border border-gray-200 rounded text-sm text-gray-600">
                                                    ℹ️ No global default model configured. Per-provider defaults will be used.
                                                </div>
                                            {/if}
                                        </div>

                                        <!-- Small Fast Model Configuration -->
                                        <div class="mt-6 p-4 bg-blue-50 border border-blue-200 rounded-md">
                                            <h4 class="text-md font-semibold text-blue-900 mb-3">
                                                Small Fast Model (Optional)
                                            </h4>
                                            <p class="text-sm text-blue-700 mb-4">
                                                Configure a lightweight model for auxiliary plugin operations like query rewriting, 
                                                classification, and data extraction. This can reduce costs and improve performance 
                                                for internal processing tasks.
                                            </p>
                                            
                                            <div class="grid grid-cols-2 gap-4">
                                                <!-- Provider Selection -->
                                                <div>
                                                    <label for="small-fast-provider" class="block text-sm font-medium text-gray-700 mb-2">
                                                        Provider
                                                    </label>
                                                    <select
                                                        id="small-fast-provider"
                                                        bind:value={newApiSettings.small_fast_model.provider}
                                                        class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                                        onchange={() => {
                                                            // Reset model when provider changes
                                                            newApiSettings.small_fast_model.model = '';
                                                            addPendingChange('Small fast model provider changed');
                                                        }}
                                                    >
                                                        <option value="">-- None --</option>
                                                        {#each Object.keys(newApiSettings.selected_models || {}) as providerName}
                                                            {#if newApiSettings.selected_models[providerName]?.length > 0}
                                                                <option value={providerName}>{providerName}</option>
                                                            {/if}
                                                        {/each}
                                                    </select>
                                                </div>
                                                
                                                <!-- Model Selection -->
                                                <div>
                                                    <label for="small-fast-model" class="block text-sm font-medium text-gray-700 mb-2">
                                                        Model
                                                    </label>
                                                    <select
                                                        id="small-fast-model"
                                                        bind:value={newApiSettings.small_fast_model.model}
                                                        class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                                        disabled={!newApiSettings.small_fast_model.provider}
                                                        onchange={() => addPendingChange('Small fast model changed')}
                                                    >
                                                        <option value="">-- Select Model --</option>
                                                        {#if newApiSettings.small_fast_model.provider && newApiSettings.selected_models[newApiSettings.small_fast_model.provider]}
                                                            {#each newApiSettings.selected_models[newApiSettings.small_fast_model.provider] as model}
                                                                <option value={model}>{model}</option>
                                                            {/each}
                                                        {/if}
                                                    </select>
                                                </div>
                                            </div>
                                            
                                            {#if newApiSettings.small_fast_model.provider && newApiSettings.small_fast_model.model}
                                                <div class="mt-3 p-2 bg-green-50 border border-green-200 rounded text-sm text-green-800">
                                                    ✓ Small fast model configured: 
                                                    <strong>{newApiSettings.small_fast_model.provider}/{newApiSettings.small_fast_model.model}</strong>
                                                </div>
                                            {:else}
                                                <div class="mt-3 p-2 bg-gray-50 border border-gray-200 rounded text-sm text-gray-600">
                                                    ℹ️ No small fast model configured. Plugins will use default models for auxiliary operations.
                                                </div>
                                            {/if}
                                        </div>
                                    </div>

                                    <!-- Pending Changes Indicator -->
                                    {#if hasUnsavedChanges}
                                        <div class="mb-4 p-3 bg-yellow-50 border-l-4 border-yellow-400 rounded">
                                            <div class="flex items-center">
                                                <div class="flex-shrink-0">
                                                    <svg class="h-5 w-5 text-yellow-400" viewBox="0 0 20 20" fill="currentColor">
                                                        <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
                                                    </svg>
                                                </div>
                                                <div class="ml-3">
                                                    <p class="text-sm text-yellow-700 font-medium">
                                                        Unsaved Changes
                                                    </p>
                                                    <div class="mt-1 text-sm text-yellow-600">
                                                        {#each pendingChanges as change}
                                                            <div class="flex items-center">
                                                                <span class="inline-block w-1 h-1 bg-yellow-600 rounded-full mr-2"></span>
                                                                {change}
                                                            </div>
                                                        {/each}
                                                    </div>
                                                    <p class="mt-2 text-sm text-yellow-600">
                                                        Click "Commit Changes" below to save all modifications to the database.
                                                    </p>
                                                </div>
                                            </div>
                                        </div>
                                    {/if}

                                    <button
                                        onclick={updateApiSettings}
                                        class="text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline transition-all duration-200 hover:opacity-90 {hasUnsavedChanges ? 'ring-2 ring-green-300' : ''}"
                                        style="background-color: {hasUnsavedChanges ? '#16a34a' : '#2271b3'};"
                                    >
                                        {hasUnsavedChanges ? '💾 Commit Changes' : 'Update API Settings'}
                                    </button>
                                </div>
                            </div>
                        </div>
                        {/if}

                        <!-- Knowledge Base Settings Tab -->
                        {#if settingsSubView === 'kb'}
                        <div class="bg-white overflow-hidden shadow rounded-lg">
                            <div class="px-4 py-5 sm:p-6">
                                <h3 class="text-lg leading-6 font-medium text-gray-900 mb-4">Knowledge Base Server</h3>
                                <p class="text-sm text-gray-600 mb-4">
                                    Configure the Knowledge Base server connection for RAG (Retrieval-Augmented Generation) functionality.
                                    Connection will be tested before saving.
                                </p>

                                <!-- Error Message -->
                                {#if kbSettingsError}
                                    <div class="mb-4 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative" role="alert">
                                        <strong class="font-bold">Error: </strong>
                                        <span class="block sm:inline">{kbSettingsError}</span>
                                    </div>
                                {/if}

                                <!-- Success Message -->
                                {#if kbSettingsSuccess}
                                    <div class="mb-4 bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded relative" role="alert">
                                        <strong class="font-bold">Success! </strong>
                                        <span class="block sm:inline">KB server settings updated successfully.</span>
                                    </div>
                                {/if}

                                <!-- Connection Test Result -->
                                {#if kbTestResult}
                                    <div class="mb-4 {kbTestResult.success ? 'bg-green-100 border-green-400 text-green-700' : 'bg-red-100 border-red-400 text-red-700'} border px-4 py-3 rounded relative" role="alert">
                                        <strong class="font-bold">{kbTestResult.success ? '✅ Success' : '❌ Failed'}</strong>
                                        <span class="block sm:inline mt-1">{kbTestResult.message}</span>
                                        {#if kbTestResult.success && kbTestResult.version}
                                            <div class="text-sm mt-1">Server Version: {kbTestResult.version}</div>
                                        {/if}
                                    </div>
                                {/if}

                                <div class="space-y-4">
                                    <!-- KB Server URL -->
                                    <div>
                                        <label for="kb-url" class="block text-sm font-medium text-gray-700">KB Server URL *</label>
                                        <input
                                            type="text"
                                            id="kb-url"
                                            bind:value={newKbSettings.url}
                                            class="mt-1 block w-full border border-gray-300 rounded-md px-3 py-2 shadow-sm focus:outline-none focus:ring-brand focus:border-brand"
                                            placeholder="http://kb:9090"
                                            required
                                            oninput={() => kbTestResult = null}
                                        >
                                        <p class="mt-1 text-sm text-gray-500">
                                            URL of the Knowledge Base server (e.g., http://kb:9090 or http://192.168.1.100:9090)
                                        </p>
                                    </div>

                                    <!-- KB Server API Key -->
                                    <div>
                                        <div class="flex items-center justify-between mb-1">
                                            <label for="kb-api-key" class="block text-sm font-medium text-gray-700">API Key</label>
                                            {#if kbSettings.api_key_set || newKbSettings.api_key}
                                            <button
                                                type="button"
                                                class="text-sm text-brand hover:text-brand-hover"
                                                onclick={() => showKbApiKey = !showKbApiKey}
                                            >
                                                {showKbApiKey ? 'Hide' : 'Show'} API Key
                                            </button>
                                            {/if}
                                        </div>
                                        <input
                                            type={showKbApiKey ? 'text' : 'password'}
                                            id="kb-api-key"
                                            bind:value={newKbSettings.api_key}
                                            class="mt-1 block w-full border border-gray-300 rounded-md px-3 py-2 shadow-sm focus:outline-none focus:ring-brand focus:border-brand"
                                            placeholder={kbSettings.api_key_set ? '••••••••••••••••' : 'Enter API key'}
                                            oninput={() => {
                                                kbTestResult = null;
                                                // Auto-show API key when user starts typing
                                                if (newKbSettings.api_key && !showKbApiKey) {
                                                    showKbApiKey = true;
                                                }
                                            }}
                                        >
                                        <p class="mt-1 text-sm text-gray-500">
                                            {#if kbSettings.api_key_set}
                                                API key is currently set. {showKbApiKey ? 'You can view it above.' : 'Click "Show API Key" to view or leave empty to keep existing.'}
                                            {:else}
                                                Enter the API key for KB server authentication.
                                            {/if}
                                        </p>
                                    </div>

                                    <!-- Advanced Options Checkbox -->
                                    <div class="flex items-center">
                                        <input
                                            id="show-kb-advanced"
                                            type="checkbox"
                                            bind:checked={showKbAdvanced}
                                            class="h-4 w-4 text-brand focus:ring-brand border-gray-300 rounded"
                                        >
                                        <label for="show-kb-advanced" class="ml-2 block text-sm text-gray-900">
                                            Show advanced options
                                        </label>
                                    </div>

                                    {#if showKbAdvanced}
                                    <!-- Embedding API Key (NEW - at top of advanced options) -->
                                    <div>
                                        <div class="flex items-center justify-between mb-1">
                                            <label for="kb-embedding-api-key" class="block text-sm font-medium text-gray-700">
                                                Embedding API Key (Optional)
                                                <span class="ml-1 text-gray-400 cursor-help" title="Set or update the API key used for embeddings (e.g., OpenAI). Requires KB Server connection to be configured first.">ℹ️</span>
                                            </label>
                                            {#if kbEmbeddingsConfig.apikey_configured || newKbSettings.embedding_api_key}
                                            <button
                                                type="button"
                                                class="text-sm text-brand hover:text-brand-hover"
                                                onclick={() => showEmbeddingApiKey = !showEmbeddingApiKey}
                                            >
                                                {showEmbeddingApiKey ? 'Hide' : 'Show'} API Key
                                            </button>
                                            {/if}
                                        </div>

                                        {#if !kbSettings.url}
                                        <!-- Warning when KB server is not configured -->
                                        <div class="mb-3 p-3 bg-blue-50 border border-blue-200 rounded-md">
                                            <div class="flex items-start">
                                                <span class="text-blue-600 mr-2">ℹ️</span>
                                                <div class="flex-1">
                                                    <p class="text-sm text-blue-800 font-medium">KB Server Connection Required</p>
                                                    <p class="mt-1 text-xs text-blue-700">
                                                        Before setting an embedding API key, you must first configure and save the KB Server URL and API Key above, then click "Update KB Settings".
                                                    </p>
                                                </div>
                                            </div>
                                        </div>
                                        {/if}

                                        <input
                                            type={showEmbeddingApiKey ? 'text' : 'password'}
                                            id="kb-embedding-api-key"
                                            bind:value={newKbSettings.embedding_api_key}
                                            class="mt-1 block w-full border border-gray-300 rounded-md px-3 py-2 shadow-sm focus:outline-none focus:ring-brand focus:border-brand disabled:bg-gray-100 disabled:cursor-not-allowed"
                                            placeholder={kbEmbeddingsConfig.apikey_configured ? '••••••••••••••••••••••••••••' : 'Enter embedding API key'}
                                            disabled={!kbSettings.url}
                                            oninput={() => {
                                                kbTestResult = null;
                                                // Auto-show API key when user starts typing
                                                if (newKbSettings.embedding_api_key && !showEmbeddingApiKey) {
                                                    showEmbeddingApiKey = true;
                                                }
                                                // Track if field is dirty (different from original)
                                                embeddingApiKeyDirty = newKbSettings.embedding_api_key !== embeddingApiKeyOriginal;
                                            }}
                                        >
                                        <p class="mt-1 text-sm text-gray-500">
                                            {#if kbEmbeddingsConfig.apikey_configured}
                                                API key is currently set on KB server ({kbEmbeddingsConfig.config_source === 'file' ? 'persisted config' : 'from env vars'}). {showEmbeddingApiKey ? 'You can view it above.' : 'Click "Show API Key" to view or leave empty to keep existing.'}
                                            {:else}
                                                Enter the API key for embeddings service (e.g., OpenAI). This will be set on the KB server.
                                            {/if}
                                        </p>
                                        
                                        <!-- Conditional: Bulk Update Checkbox (only show when key is dirty) -->
                                        {#if embeddingApiKeyDirty}
                                        <div class="mt-3 p-3 bg-yellow-50 border border-yellow-200 rounded-md">
                                            <div class="flex items-start">
                                                <input
                                                    id="apply-to-all-kb"
                                                    type="checkbox"
                                                    bind:checked={applyToAllKbChecked}
                                                    class="h-4 w-4 text-brand focus:ring-brand border-gray-300 rounded mt-0.5"
                                                >
                                                <div class="ml-3">
                                                    <label for="apply-to-all-kb" class="block text-sm font-medium text-gray-900 cursor-pointer">
                                                        Apply this key to all existing knowledge bases in this organization
                                                    </label>
                                                    <p class="mt-1 text-xs text-yellow-700 flex items-start">
                                                        <span class="mr-1">⚠️</span>
                                                        <span>This will update the embedding API key for all knowledge base collections. Use this when rotating API keys.</span>
                                                    </p>
                                                </div>
                                            </div>
                                        </div>
                                        {/if}
                                        
                                        <div class="mt-2 flex gap-2">
                                            <button
                                                type="button"
                                                onclick={saveKbEmbeddingsConfig}
                                                class="text-sm bg-gray-100 hover:bg-gray-200 text-gray-700 px-3 py-1 rounded disabled:opacity-50 disabled:cursor-not-allowed"
                                                disabled={isUpdatingKbEmbeddingsConfig || !newKbSettings.embedding_api_key || !kbSettings.url}
                                                title={!kbSettings.url ? 'Please save KB Server connection first' : !newKbSettings.embedding_api_key ? 'Please enter an API key' : 'Save embedding API key to KB server'}
                                            >
                                                {isUpdatingKbEmbeddingsConfig ? '🔄 Saving...' : '💾 Save to KB Server'}
                                            </button>
                                            {#if kbEmbeddingsConfig.config_source === 'file'}
                                                <button
                                                    type="button"
                                                    class="text-sm text-gray-500 hover:text-gray-700 underline"
                                                    onclick={() => { showResetKbConfigModal = true; }}
                                                >
                                                    Reset to Env
                                                </button>
                                            {/if}
                                        </div>
                                        {#if kbEmbeddingsConfigError}
                                            <p class="mt-1 text-sm text-red-600">{kbEmbeddingsConfigError}</p>
                                        {/if}

                                        {#if applyToAllKbResult}
                                            <p class="mt-2 text-sm text-green-700">{applyToAllKbResult}</p>
                                        {/if}
                                    </div>

                                    <!-- Embedding Model -->
                                    <div>
                                        <label for="kb-embedding-model" class="block text-sm font-medium text-gray-700">Embedding Model (Optional)</label>
                                        <input
                                            type="text"
                                            id="kb-embedding-model"
                                            bind:value={newKbSettings.embedding_model}
                                            class="mt-1 block w-full border border-gray-300 rounded-md px-3 py-2 shadow-sm focus:outline-none focus:ring-brand focus:border-brand"
                                            placeholder="all-MiniLM-L6-v2"
                                        >
                                        <p class="mt-1 text-sm text-gray-500">
                                            Default embedding model for new collections (leave empty for KB server default)
                                        </p>
                                    </div>

                                    <!-- Collection Defaults -->
                                    <fieldset class="mb-2">
                                        <legend class="block text-sm font-medium text-gray-700 mb-2">Collection Defaults (Optional)</legend>
                                        <div class="grid grid-cols-2 gap-4">
                                            <div>
                                                <label for="kb-chunk-size" class="block text-xs font-medium text-gray-600">Chunk Size</label>
                                                <input
                                                    type="number"
                                                    id="kb-chunk-size"
                                                    bind:value={newKbSettings.collection_defaults.chunk_size}
                                                    class="mt-1 block w-full border border-gray-300 rounded-md px-3 py-2 shadow-sm focus:outline-none focus:ring-brand focus:border-brand"
                                                    min="100"
                                                    max="5000"
                                                >
                                            </div>
                                            <div>
                                                <label for="kb-chunk-overlap" class="block text-xs font-medium text-gray-600">Chunk Overlap</label>
                                                <input
                                                    type="number"
                                                    id="kb-chunk-overlap"
                                                    bind:value={newKbSettings.collection_defaults.chunk_overlap}
                                                    class="mt-1 block w-full border border-gray-300 rounded-md px-3 py-2 shadow-sm focus:outline-none focus:ring-brand focus:border-brand"
                                                    min="0"
                                                    max="1000"
                                                >
                                            </div>
                                        </div>
                                        <p class="mt-1 text-sm text-gray-500">
                                            Default chunking parameters for new collections
                                        </p>
                                    </fieldset>
                                    {/if}

                                    <!-- Action Buttons -->
                                    <div class="flex gap-3">
                                        <button
                                            type="button"
                                            onclick={testKbConnection}
                                            class="bg-gray-200 hover:bg-gray-300 text-gray-800 font-semibold py-2 px-4 rounded focus:outline-none focus:shadow-outline disabled:opacity-50"
                                            disabled={isTesting || !newKbSettings.url}
                                        >
                                            {isTesting ? '🔄 Testing...' : '🔌 Test Connection'}
                                        </button>
                                        <button
                                            onclick={updateKbSettings}
                                            class="bg-brand hover:bg-brand-hover text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline disabled:opacity-50"
                                            disabled={isTesting || !newKbSettings.url}
                                        >
                                            Update KB Settings
                                        </button>
                                    </div>

                                    <p class="mt-2 text-xs text-gray-500">
                                        💡 <strong>Tip:</strong> You can test the current configuration by clicking "Test Connection" without entering a new API key.
                                    </p>
                                    <p class="mt-1 text-xs text-gray-500">
                                        ⚠️ Connection will be tested automatically before saving. Changes will not be saved if the test fails.
                                    </p>
                                </div>
                            </div>
                        </div>
                        {/if}

                        <!-- Assistant Defaults Tab -->
                        {#if settingsSubView === 'defaults'}
                        <!-- Assistant Defaults (Organization-Scoped) -->
                        <div class="bg-white overflow-hidden shadow rounded-lg mt-6">
                            <div class="px-4 py-5 sm:p-6">
                                <h3 class="text-lg leading-6 font-medium text-gray-900 mb-4">Assistant Defaults</h3>
                                <p class="text-sm text-gray-600 mb-4">These values seed the Create/Edit Assistant form for users in this organization. Edit as raw JSON to add or change fields dynamically.</p>

                                {#if assistantDefaultsError}
                                    <div class="mb-4 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative" role="alert">
                                        <span class="block sm:inline">{assistantDefaultsError}</span>
                                    </div>
                                {/if}

                                {#if assistantDefaultsSuccess}
                                    <div class="mb-4 bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded relative" role="alert">
                                        <span class="block sm:inline">Assistant defaults saved successfully.</span>
                                    </div>
                                {/if}

                                <div class="space-y-3">
                                    <label for="assistant-defaults-json" class="block text-sm font-medium text-gray-700">assistant_defaults (JSON)</label>
                                    <textarea
                                        id="assistant-defaults-json"
                                        class="font-mono text-sm mt-1 block w-full border border-gray-300 rounded-md px-3 py-2 shadow-sm focus:outline-none focus:ring-brand focus:border-brand min-h-[280px]"
                                        bind:value={assistantDefaultsJson}
                                        placeholder={assistantDefaultsPlaceholder}
                                    ></textarea>

                                    <div class="flex items-center gap-3">
                                        <button
                                            class="bg-brand hover:bg-brand-hover text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline disabled:opacity-50"
                                            onclick={updateAssistantDefaults}
                                            disabled={isLoadingAssistantDefaults}
                                        >
                                            Save Assistant Defaults
                                        </button>
                                        <button
                                            class="bg-gray-200 hover:bg-gray-300 text-gray-800 font-semibold py-2 px-4 rounded focus:outline-none focus:shadow-outline"
                                            onclick={fetchAssistantDefaults}
                                        >
                                            Reload
                                        </button>
                                    </div>
                                    <p class="text-xs text-gray-500">Tip: Fields are dynamic. Unknown keys will be preserved. Ensure the `connector` and `llm` are enabled in this organization.</p>
                                </div>
                            </div>
                        </div>
                        {/if}
                    {/if}
                </div>
            {/if}

            <!-- Bulk Import View -->
            {#if currentView === 'bulk-import'}
                <div class="mb-6">
                    <p class="text-gray-500">Bulk user import feature coming soon...</p>
                    <!-- <BulkUserImport /> -->
                </div>
            {/if}
        </div>
    </main>
</div>

<!-- Apply Embedding Key To All KBs Confirmation Modal -->
{#if showApplyToAllKbConfirmation}
    <div class="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50 flex items-center justify-center">
        <div class="relative mx-auto p-5 border w-full max-w-md shadow-lg rounded-md bg-white">
            <div class="mt-3">
                <div class="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-yellow-100">
                    <svg class="h-6 w-6 text-yellow-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                </div>

                <h3 class="text-lg leading-6 font-medium text-gray-900 text-center mt-4">
                    Apply embedding API key to all knowledge bases?
                </h3>

                <div class="mt-4 text-center">
                    <p class="text-sm text-gray-600">
                        This will update the embedding API key for <strong>all existing KB collections</strong> in this organization.
                    </p>
                    <div class="mt-4 bg-yellow-50 border-l-4 border-yellow-400 p-3 rounded">
                        <p class="text-sm text-gray-700">
                            Use this when rotating keys. Model/vendor/endpoint are unchanged — only the key is updated.
                        </p>
                    </div>
                </div>

                <div class="flex items-center justify-between mt-6 gap-3">
                    <button
                        type="button"
                        onclick={cancelApplyToAllKb}
                        class="flex-1 bg-gray-300 hover:bg-gray-400 text-gray-800 font-semibold py-2 px-4 rounded focus:outline-none focus:shadow-outline disabled:opacity-50"
                        disabled={isApplyingToAllKb || isUpdatingKbEmbeddingsConfig}
                    >
                        Cancel
                    </button>
                    <button
                        type="button"
                        onclick={confirmApplyToAllKb}
                        class="flex-1 bg-yellow-600 hover:bg-yellow-700 text-white font-semibold py-2 px-4 rounded focus:outline-none focus:shadow-outline disabled:opacity-50"
                        disabled={isApplyingToAllKb || isUpdatingKbEmbeddingsConfig}
                    >
                        {isApplyingToAllKb ? 'Applying...' : 'Apply to All KBs'}
                    </button>
                </div>
            </div>
        </div>
    </div>
{/if}

<!-- Create User Modal -->
{#if isCreateUserModalOpen}
    <div class="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50 flex items-center justify-center">
        <div class="relative mx-auto p-5 border w-full max-w-md shadow-lg rounded-md bg-white">
            <div class="mt-3 text-center">
                <h3 class="text-lg leading-6 font-medium text-gray-900">
                    Create New User
                </h3>
                
                {#if createUserSuccess}
                    <div class="mt-4 bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded relative" role="alert">
                        <span class="block sm:inline">User created successfully!</span>
                    </div>
                {:else}
                    <form class="mt-4" onsubmit={handleCreateUser}>
                        {#if createUserError}
                            <div class="mb-4 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative" role="alert">
                                <span class="block sm:inline">{createUserError}</span>
                            </div>
                        {/if}
                        
                        <div class="mb-4 text-left">
                            <label for="email" class="block text-gray-700 text-sm font-bold mb-2">
                                Email *
                            </label>
                            <input 
                                type="email" 
                                id="email" 
                                name="email"
                                class="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline" 
                                bind:value={newUser.email} 
                                required 
                            />
                        </div>
                        
                        <div class="mb-4 text-left">
                            <label for="name" class="block text-gray-700 text-sm font-bold mb-2">
                                Name *
                            </label>
                            <input 
                                type="text" 
                                id="name" 
                                name="name"
                                class="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline" 
                                bind:value={newUser.name} 
                                required 
                            />
                        </div>
                        
                        <div class="mb-4 text-left">
                            <label for="password" class="block text-gray-700 text-sm font-bold mb-2">
                                Password *
                            </label>
                            <input 
                                type="password" 
                                id="password" 
                                name="password"
                                class="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline" 
                                bind:value={newUser.password} 
                                required 
                            />
                        </div>

                        <div class="mb-4 text-left">
                            <label for="user_type" class="block text-gray-700 text-sm font-bold mb-2">
                                User Type
                            </label>
                            <select 
                                id="user_type" 
                                name="user_type"
                                class="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline" 
                                bind:value={newUser.user_type}
                            >
                                <option value="creator">Creator (Can create assistants)</option>
                                <option value="end_user">End User (Redirects to Open WebUI)</option>
                            </select>
                        </div>

                        <div class="mb-6 text-left">
                            <div class="flex items-center">
                                <input 
                                    type="checkbox" 
                                    id="enabled" 
                                    name="enabled"
                                    bind:checked={newUser.enabled}
                                    class="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                                />
                                <label for="enabled" class="ml-2 block text-sm text-gray-900">
                                    User enabled
                                </label>
                            </div>
                        </div>
                        
                        <div class="flex items-center justify-between">
                            <button 
                                type="button" 
                                onclick={closeCreateUserModal}
                                class="bg-gray-300 hover:bg-gray-400 text-gray-800 py-2 px-4 rounded focus:outline-none focus:shadow-outline" 
                            >
                                Cancel
                            </button>
                            <button
                                type="submit"
                                class="bg-brand hover:bg-brand-hover text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline disabled:opacity-50"
                                disabled={isCreatingUser}
                            >
                                {#if isCreatingUser}
                                    Creating...
                                {:else}
                                    Create User
                                {/if}
                            </button>
                        </div>
                    </form>
                {/if}
            </div>
        </div>
    </div>
{/if}

<!-- Change Password Modal -->
{#if isChangePasswordModalOpen}
    <div class="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50 flex items-center justify-center">
        <div class="relative mx-auto p-5 border w-full max-w-md shadow-lg rounded-md bg-white">
            <div class="mt-3 text-center">
                <h3 class="text-lg leading-6 font-medium text-gray-900">
                    Change Password
                </h3>
                <p class="text-sm text-gray-500 mt-1">
                    Set a new password for {passwordChangeData.user_name} ({passwordChangeData.user_email})
                </p>
                
                {#if changePasswordSuccess}
                    <div class="mt-4 bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded relative" role="alert">
                        <span class="block sm:inline">Password changed successfully!</span>
                    </div>
                {:else}
                    <form class="mt-4" onsubmit={handleChangePassword}>
                        {#if changePasswordError}
                            <div class="mb-4 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative" role="alert">
                                <span class="block sm:inline">{changePasswordError}</span>
                            </div>
                        {/if}
                        
                        <div class="mb-4 text-left">
                            <label for="new-password" class="block text-gray-700 text-sm font-bold mb-2">
                                New Password *
                            </label>
                            <input 
                                type="password" 
                                id="new-password" 
                                class="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline" 
                                bind:value={passwordChangeData.new_password} 
                                required 
                                autocomplete="new-password"
                                minlength="8"
                            />
                            <p class="text-gray-500 text-xs italic mt-1">
                                At least 8 characters recommended
                            </p>
                        </div>
                        
                        <div class="flex items-center justify-between">
                            <button 
                                type="button" 
                                onclick={closeChangePasswordModal}
                                class="bg-gray-300 hover:bg-gray-400 text-gray-800 py-2 px-4 rounded focus:outline-none focus:shadow-outline" 
                            >
                                Cancel
                            </button>
                            <button
                                type="submit"
                                class="bg-brand hover:bg-brand-hover text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline disabled:opacity-50"
                                disabled={isChangingPassword}
                            >
                                {isChangingPassword ? 'Changing...' : 'Change Password'}
                            </button>
                        </div>
                    </form>
                {/if}
            </div>
        </div>
    </div>
{/if}

<!-- Disable User Modal (formerly Delete User Modal) -->
{#if isDeleteUserModalOpen && userToDelete}
    <div class="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50 flex items-center justify-center">
        <div class="relative mx-auto p-5 border w-full max-w-md shadow-lg rounded-md bg-white">
            <div class="mt-3">
                <!-- Warning Icon -->
                <div class="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-yellow-100">
                    <svg class="h-6 w-6 text-yellow-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                </div>
                
                <!-- Modal Header -->
                <h3 class="text-lg leading-6 font-medium text-gray-900 text-center mt-4">
                    Disable User Account
                </h3>
                
                <!-- Modal Content -->
                <div class="mt-4 text-center">
                    <p class="text-sm text-gray-600">
                        Are you sure you want to disable the account for
                    </p>
                    <p class="text-base font-semibold text-gray-900 mt-2">
                        {userToDelete.name}
                    </p>
                    <p class="text-sm text-gray-600 mt-1">
                        ({userToDelete.email})
                    </p>
                    <div class="mt-4 bg-yellow-50 border-l-4 border-yellow-400 p-3 rounded">
                        <p class="text-sm text-gray-700">
                            <strong>Note:</strong> The user will not be able to log in, but their resources (assistants, templates, rubrics) will remain accessible to other users.
                        </p>
                    </div>
                </div>

                {#if deleteUserError}
                    <div class="mt-4 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative" role="alert">
                        <span class="block sm:inline">{deleteUserError}</span>
                    </div>
                {/if}
                
                <!-- Modal Actions -->
                <div class="flex items-center justify-between mt-6 gap-3">
                    <button 
                        type="button" 
                        onclick={closeDeleteUserModal}
                        class="flex-1 bg-gray-300 hover:bg-gray-400 text-gray-800 font-semibold py-2 px-4 rounded focus:outline-none focus:shadow-outline disabled:opacity-50" 
                        disabled={isDeletingUser}
                    >
                        Cancel
                    </button>
                    <button 
                        type="button" 
                        onclick={confirmDeleteUser}
                        class="flex-1 bg-yellow-600 hover:bg-yellow-700 text-white font-semibold py-2 px-4 rounded focus:outline-none focus:shadow-outline disabled:opacity-50" 
                        disabled={isDeletingUser}
                    >
                        {isDeletingUser ? 'Disabling...' : 'Disable User'}
                    </button>
                </div>
            </div>
        </div>
    </div>
{/if}

<!-- Bulk Disable Users Modal -->
{#if isBulkDisableModalOpen}
    <div class="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50 flex items-center justify-center">
        <div class="relative mx-auto p-5 border w-full max-w-md shadow-lg rounded-md bg-white">
            <div class="mt-3">
                <!-- Warning Icon -->
                <div class="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-yellow-100">
                    <svg class="h-6 w-6 text-yellow-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                </div>
                
                <!-- Modal Header -->
                <h3 class="text-lg leading-6 font-medium text-gray-900 text-center mt-4">
                    Disable Multiple Users
                </h3>
                
                <!-- Modal Content -->
                <div class="mt-4 text-center">
                    <p class="text-sm text-gray-600">
                        Are you sure you want to disable <strong>{selectedUsers.length}</strong> user{selectedUsers.length > 1 ? 's' : ''}?
                    </p>
                    <div class="mt-4 bg-yellow-50 border-l-4 border-yellow-400 p-3 rounded">
                        <p class="text-sm text-gray-700">
                            These users will not be able to log in, but their resources will remain accessible to other users.
                        </p>
                    </div>
                </div>

                {#if bulkActionError}
                    <div class="mt-4 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative" role="alert">
                        <span class="block sm:inline">{bulkActionError}</span>
                    </div>
                {/if}
                
                <!-- Modal Actions -->
                <div class="flex items-center justify-between mt-6 gap-3">
                    <button 
                        type="button" 
                        onclick={closeBulkDisableModal}
                        class="flex-1 bg-gray-300 hover:bg-gray-400 text-gray-800 font-semibold py-2 px-4 rounded focus:outline-none focus:shadow-outline disabled:opacity-50" 
                        disabled={isBulkProcessing}
                    >
                        Cancel
                    </button>
                    <button 
                        type="button" 
                        onclick={confirmBulkDisable}
                        class="flex-1 bg-yellow-600 hover:bg-yellow-700 text-white font-semibold py-2 px-4 rounded focus:outline-none focus:shadow-outline disabled:opacity-50" 
                        disabled={isBulkProcessing}
                    >
                        {isBulkProcessing ? 'Disabling...' : 'Disable Users'}
                    </button>
                </div>
            </div>
        </div>
    </div>
{/if}

<!-- Bulk Enable Users Modal -->
{#if isBulkEnableModalOpen}
    <div class="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50 flex items-center justify-center">
        <div class="relative mx-auto p-5 border w-full max-w-md shadow-lg rounded-md bg-white">
            <div class="mt-3">
                <!-- Success Icon -->
                <div class="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-green-100">
                    <svg class="h-6 w-6 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                </div>
                
                <!-- Modal Header -->
                <h3 class="text-lg leading-6 font-medium text-gray-900 text-center mt-4">
                    Enable Multiple Users
                </h3>
                
                <!-- Modal Content -->
                <div class="mt-4 text-center">
                    <p class="text-sm text-gray-600">
                        Are you sure you want to enable <strong>{selectedUsers.length}</strong> user{selectedUsers.length > 1 ? 's' : ''}?
                    </p>
                    <div class="mt-4 bg-green-50 border-l-4 border-green-400 p-3 rounded">
                        <p class="text-sm text-gray-700">
                            These users will be able to log in and access the system.
                        </p>
                    </div>
                </div>

                {#if bulkActionError}
                    <div class="mt-4 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative" role="alert">
                        <span class="block sm:inline">{bulkActionError}</span>
                    </div>
                {/if}
                
                <!-- Modal Actions -->
                <div class="flex items-center justify-between mt-6 gap-3">
                    <button 
                        type="button" 
                        onclick={closeBulkEnableModal}
                        class="flex-1 bg-gray-300 hover:bg-gray-400 text-gray-800 font-semibold py-2 px-4 rounded focus:outline-none focus:shadow-outline disabled:opacity-50" 
                        disabled={isBulkProcessing}
                    >
                        Cancel
                    </button>
                    <button 
                        type="button" 
                        onclick={confirmBulkEnable}
                        class="flex-1 bg-green-600 hover:bg-green-700 text-white font-semibold py-2 px-4 rounded focus:outline-none focus:shadow-outline disabled:opacity-50" 
                        disabled={isBulkProcessing}
                    >
                        {isBulkProcessing ? 'Enabling...' : 'Enable Users'}
                    </button>
                </div>
            </div>
        </div>
    </div>
{/if}

<!-- Model Selection Modal -->
{#if isModelModalOpen}
    <div class="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
        <div class="relative top-20 mx-auto p-5 border w-11/12 max-w-4xl shadow-lg rounded-md bg-white">
            <div class="mt-3">
                <!-- Modal Header -->
                <div class="flex items-center justify-between mb-4">
                    <h3 class="text-lg font-medium text-gray-900 capitalize">
                        Manage {modalProviderName} Models
                    </h3>
                    <button
                        type="button"
                        class="text-gray-400 hover:text-gray-600"
                        onclick={closeModelModal}
                        aria-label="Close modal"
                    >
                        <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>

                <!-- Modal Content -->
                <div class="grid grid-cols-1 md:grid-cols-5 gap-4 h-96">
                    <!-- Enabled Models (Left) -->
                    <div class="md:col-span-2 border rounded-lg p-4">
                        <div class="flex items-center justify-between mb-3">
                            <h4 class="font-medium text-gray-900">Enabled Models</h4>
                            <span class="text-sm text-gray-500">({modalEnabledModels.length})</span>
                        </div>
                        
                        <!-- Search for enabled models -->
                        <input
                            type="text"
                            placeholder="Search enabled models..."
                            class="w-full mb-3 px-3 py-2 border border-gray-300 rounded-md text-sm"
                            bind:value={enabledSearchTerm}
                        />
                        
                        <!-- Enabled models list -->
                        <div class="border rounded max-h-64 overflow-y-auto">
                            {#each modalEnabledModels.filter(model => model.toLowerCase().includes(enabledSearchTerm.toLowerCase())) as model}
                                <label class="flex items-center p-2 hover:bg-gray-50 border-b last:border-b-0">
                                    <input
                                        type="checkbox"
                                        class="mr-2 h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                                        checked={selectedEnabledModels.includes(model)}
                                        onchange={(e) => {
                                            if (e.target.checked) {
                                                selectedEnabledModels = [...selectedEnabledModels, model];
                                            } else {
                                                selectedEnabledModels = selectedEnabledModels.filter(m => m !== model);
                                            }
                                        }}
                                    />
                                    <span class="text-sm truncate" title={model}>{model}</span>
                                </label>
                            {/each}
                            {#if modalEnabledModels.length === 0}
                                <div class="p-4 text-center text-gray-500 text-sm">
                                    No models enabled
                                </div>
                            {/if}
                        </div>
                    </div>

                    <!-- Transfer Buttons (Center) -->
                    <div class="flex flex-col justify-center items-center space-y-2">
                        <button
                            type="button"
                            class="bg-brand hover:bg-brand-hover px-3 py-2 text-white rounded disabled:opacity-50"
                            onclick={moveAllToEnabled}
                            disabled={modalDisabledModels.length === 0}
                            title="Move all models to enabled"
                        >
                            &lt;&lt;
                        </button>
                        <button
                            type="button"
                            class="bg-brand hover:bg-brand-hover px-3 py-2 text-white rounded disabled:opacity-50"
                            onclick={moveSelectedToEnabled}
                            disabled={selectedDisabledModels.length === 0}
                            title="Move selected models to enabled"
                        >
                            &lt;
                        </button>
                        <button
                            type="button"
                            class="px-3 py-2 bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50"
                            onclick={moveSelectedToDisabled}
                            disabled={selectedEnabledModels.length === 0}
                            title="Move selected models to disabled"
                        >
                            &gt;
                        </button>
                        <button
                            type="button"
                            class="px-3 py-2 bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50"
                            onclick={moveAllToDisabled}
                            disabled={modalEnabledModels.length === 0}
                            title="Move all models to disabled"
                        >
                            &gt;&gt;
                        </button>
                    </div>

                    <!-- Available Models (Right) -->
                    <div class="md:col-span-2 border rounded-lg p-4">
                        <div class="flex items-center justify-between mb-3">
                            <h4 class="font-medium text-gray-900">Available Models</h4>
                            <span class="text-sm text-gray-500">({modalDisabledModels.length})</span>
                        </div>
                        
                        <!-- Search for available models -->
                        <input
                            type="text"
                            placeholder="Search available models..."
                            class="w-full mb-3 px-3 py-2 border border-gray-300 rounded-md text-sm"
                            bind:value={disabledSearchTerm}
                        />
                        
                        <!-- Available models list -->
                        <div class="border rounded max-h-64 overflow-y-auto">
                            {#each modalDisabledModels.filter(model => model.toLowerCase().includes(disabledSearchTerm.toLowerCase())) as model}
                                <label class="flex items-center p-2 hover:bg-gray-50 border-b last:border-b-0">
                                    <input
                                        type="checkbox"
                                        class="mr-2 h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                                        checked={selectedDisabledModels.includes(model)}
                                        onchange={(e) => {
                                            if (e.target.checked) {
                                                selectedDisabledModels = [...selectedDisabledModels, model];
                                            } else {
                                                selectedDisabledModels = selectedDisabledModels.filter(m => m !== model);
                                            }
                                        }}
                                    />
                                    <span class="text-sm truncate" title={model}>{model}</span>
                                </label>
                            {/each}
                            {#if modalDisabledModels.length === 0}
                                <div class="p-4 text-center text-gray-500 text-sm">
                                    All models enabled
                                </div>
                            {/if}
                        </div>
                    </div>
                </div>

                <!-- Modal Footer -->
                <div class="flex items-center justify-end mt-6 pt-4 border-t space-x-3">
                    <button
                        type="button"
                        class="px-4 py-2 bg-gray-300 text-gray-700 rounded hover:bg-gray-400"
                        onclick={closeModelModal}
                    >
                        Cancel
                    </button>
                        <button
                            type="button"
                            class="bg-brand hover:bg-brand-hover px-4 py-2 text-white rounded"
                            onclick={saveModelSelection}
                        >
                            Save Changes
                        </button>
                </div>
            </div>
        </div>
    </div>
{/if}


<!-- Assistant Sharing Modal -->
{#if showSharingModal && modalAssistant}
    <AssistantSharingModal
        assistant={modalAssistant}
        token={$user.token}
        onClose={closeAssistantSharingModal}
        onSaved={handleSharingModalSaved}
    />
{/if}

<!-- Reset KB Embeddings Config Modal -->
<ConfirmationModal
    bind:isOpen={showResetKbConfigModal}
    title="Reset KB Configuration"
    message="Reset to environment variables? This will remove the persisted configuration and use the defaults from your environment settings."
    confirmText="Reset"
    variant="warning"
    onconfirm={async () => {
        await updateKbEmbeddingsConfig();
        showResetKbConfigModal = false;
    }}
    oncancel={() => { showResetKbConfigModal = false; }}
/>

<style>
    /* Custom scrollbar styles */
    .overflow-x-auto::-webkit-scrollbar {
        height: 8px;
    }
    
    .overflow-x-auto::-webkit-scrollbar-track {
        background: #f1f1f1;
        border-radius: 4px;
    }
    
    .overflow-x-auto::-webkit-scrollbar-thumb {
        background: #c1c1c1;
        border-radius: 4px;
    }
    
    .overflow-x-auto::-webkit-scrollbar-thumb:hover {
        background: #a8a8a8;
    }
</style>