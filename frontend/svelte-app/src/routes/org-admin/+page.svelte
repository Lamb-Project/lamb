<script>
    import { onMount, onDestroy } from 'svelte';
    import { page } from '$app/stores';
    import { goto } from '$app/navigation';
    import { base } from '$app/paths';
    import axios from 'axios';
    import { user } from '$lib/stores/userStore';
    import AssistantAccessManager from '$lib/components/AssistantAccessManager.svelte';

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
    /** @type {string | null} */
    let assistantsError = $state(null);
    let selectedAssistant = $state(null);
    let showAccessModal = $state(false);
    let assistantsSearchQuery = $state('');
    let assistantsFilterPublished = $state('all');

    // Dashboard data
    /** @type {any} */
    let dashboardData = $state(null);
    let isLoadingDashboard = $state(false);

    // User management state
    /** @type {any[]} */
    let orgUsers = $state([]);
    let isLoadingUsers = $state(false);
    /** @type {string | null} */
    let usersError = $state(null);

    // Create user modal state
    let isCreateUserModalOpen = $state(false);
    let newUser = $state({
        email: '',
        name: '',
        password: '',
        enabled: true,
        user_type: 'creator' // 'creator' or 'end_user'
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
        selected_models: {}
    });

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
        } finally {
            isLoadingUsers = false;
        }
    }

    // Create user functions
    function openCreateUserModal() {
        newUser = {
            email: '',
            name: '',
            password: '',
            enabled: true,
            user_type: 'creator'
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
            alert("You cannot disable your own account. Please ask another administrator to disable your account if needed.");
            return;
        }
        
        if (!confirm(`Are you sure you want to ${action} ${user.name} (${user.email})?`)) {
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

            // Show success message (you could use a toast library here)
            alert(`User ${user.name} has been ${newStatus ? 'enabled' : 'disabled'} successfully.`);

        } catch (err) {
            console.error(`Error ${action}ing user:`, err);
            
            let errorMessage = `Failed to ${action} user.`;
            if (axios.isAxiosError(err) && err.response?.data?.detail) {
                errorMessage = err.response.data.detail;
            } else if (err instanceof Error) {
                errorMessage = err.message;
            }
            
            alert(`Error: ${errorMessage}`);
        }
    }

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
     * @param {Event} e
     */
    async function handleCreateUser(e) {
        e.preventDefault();

        // Basic form validation
        if (!newUser.email || !newUser.name || !newUser.password) {
            createUserError = 'Please fill in all required fields.';
            return;
        }

        if (!newUser.email.includes('@')) {
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
                email: newUser.email,
                name: newUser.name,
                password: newUser.password,
                enabled: newUser.enabled,
                user_type: newUser.user_type
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
        } catch (err) {
            console.error('Error fetching assistants:', err);
            assistantsError = err.response?.data?.detail || 'Failed to fetch assistants';
        } finally {
            isLoadingAssistants = false;
        }
    }

    function manageAssistantAccess(assistant) {
        selectedAssistant = assistant;
        showAccessModal = true;
    }

    function closeAccessModal() {
        showAccessModal = false;
        selectedAssistant = null;
    }

    function handleAccessUpdated() {
        // Optionally reload assistants
        fetchAssistants();
    }

    function formatDate(timestamp) {
        if (!timestamp) return 'N/A';
        return new Date(timestamp * 1000).toLocaleDateString();
    }

    // Settings functions
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

            // Fetch signup settings
            const signupUrl = targetOrgSlug 
                ? getApiUrl(`/org-admin/settings/signup?org=${targetOrgSlug}`)
                : getApiUrl('/org-admin/settings/signup');
            const signupResponse = await axios.get(signupUrl, {
                headers: { 'Authorization': `Bearer ${token}` }
            });

            // Fetch API settings
            const apiUrl = targetOrgSlug 
                ? getApiUrl(`/org-admin/settings/api?org=${targetOrgSlug}`)
                : getApiUrl('/org-admin/settings/api');
            const apiResponse = await axios.get(apiUrl, {
                headers: { 'Authorization': `Bearer ${token}` }
            });

            signupSettings = signupResponse.data;
            apiSettings = apiResponse.data;

            // Initialize edit forms
            newSignupSettings = {
                signup_enabled: signupSettings.signup_enabled,
                signup_key: signupSettings.signup_key || ''
            };

            newApiSettings = {
                openai_api_key: '',
                openai_base_url: apiSettings.openai_base_url || 'https://api.openai.com/v1',
                ollama_base_url: apiSettings.ollama_base_url || 'http://localhost:11434',
                available_models: Array.isArray(apiSettings.available_models) ? [...apiSettings.available_models] : [],
                model_limits: { ...(apiSettings.model_limits || {}) },
                selected_models: { ...(apiSettings.selected_models || {}) },
                default_models: { ...(apiSettings.default_models || {}) }
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

            // Fetch assistant defaults for this organization
            await fetchAssistantDefaults();

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

    async function updateSignupSettings() {
        try {
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
            // Success - settings refreshed

        } catch (err) {
            console.error('Error updating signup settings:', err);
            // Error is logged to console
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
        } else if (currentView === 'users' && orgUsers.length === 0) {
            fetchUsers();
        } else if (currentView === 'assistants' && orgAssistants.length === 0) {
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
                <div class="flex items-center">
                    <span class="text-sm text-gray-600">
                        {userData?.email || 'Organization Admin'}
                    </span>
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
                        <div class="bg-gradient-to-r from-blue-600 to-blue-700 rounded-lg shadow-lg mb-6">
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
                                                class="ml-4 px-3 py-1 text-white text-sm rounded-md transition-colors hover:opacity-90"
                                                style="background-color: #2271b3;"
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
                            <div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
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
                                                                            <span class="text-blue-600">• Default: {providerStatus.default_model}</span>
                                                                        {/if}
                                                                    </div>
                                                                    <div class="flex flex-wrap gap-1">
                                                                        {#each providerStatus.enabled_models.slice(0, 8) as model}
                                                                            <span class="inline-block px-2 py-1 text-xs bg-blue-100 text-blue-800 rounded {
                                                                                model === providerStatus.default_model ? 'ring-2 ring-blue-300' : ''
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
                        <div class="bg-white border-l-4 border-blue-500 shadow-sm rounded-lg mb-4">
                            <div class="px-4 py-3">
                                <div class="flex items-center justify-between">
                                    <div>
                                        <h1 class="text-xl font-semibold text-gray-900">{dashboardData.organization.name}</h1>
                                        <p class="text-sm text-gray-600">User Management</p>
                                    </div>
                                                            <div class="text-right text-sm text-gray-500">
                            {#if targetOrgSlug}
                                <div class="text-xs text-blue-600 mb-1">
                                    <svg class="inline h-3 w-3 mr-1" fill="currentColor" viewBox="0 0 20 20">
                                        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"></path>
                                    </svg>
                                    System Admin View
                                </div>
                            {/if}
                            {dashboardData.stats.total_users} users • {dashboardData.stats.active_users} active
                        </div>
                                </div>
                            </div>
                        </div>
                    {/if}
                    
                    <div class="flex justify-between items-center mb-4">
                        <h2 class="text-2xl font-semibold text-gray-800">Manage Users</h2>
                        <button
                            class="text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline hover:opacity-90"
                            style="background-color: #2271b3;"
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

                    {#if isLoadingUsers}
                        <div class="text-center py-12">
                            <div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                            <p class="mt-2 text-gray-600">Loading users...</p>
                        </div>
                    {:else}
                        <!-- Users Table -->
                        <div class="overflow-x-auto shadow-md sm:rounded-lg mb-6 border border-gray-200">
                            <table class="min-w-full divide-y divide-gray-200">
                                <thead class="bg-gray-50">
                                    <tr>
                                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider" style="color: #2271b3;">
                                            Name
                                        </th>
                                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider" style="color: #2271b3;">
                                            Email
                                        </th>
                                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider" style="color: #2271b3;">
                                            Role
                                        </th>
                                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider" style="color: #2271b3;">
                                            Status
                                        </th>
                                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider" style="color: #2271b3;">
                                            Actions
                                        </th>
                                    </tr>
                                </thead>
                                <tbody class="bg-white divide-y divide-gray-200">
                                    {#each orgUsers as user (user.id)}
                                        <tr class="hover:bg-gray-50">
                                            <td class="px-6 py-4 whitespace-nowrap align-top">
                                                <div class="text-sm font-medium text-gray-900">{user.name || '-'}</div>
                                            </td>
                                            <td class="px-6 py-4 whitespace-nowrap align-top">
                                                <div class="text-sm text-gray-800">{user.email}</div>
                                            </td>
                                            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-800">
                                                <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full {user.role === 'admin' ? 'bg-red-100 text-red-800' : 'bg-gray-100 text-gray-800'}">
                                                    {user.role}
                                                </span>
                                            </td>
                                            <td class="px-6 py-4 whitespace-nowrap text-sm">
                                                <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full {user.enabled ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}">
                                                    {user.enabled ? 'Active' : 'Disabled'}
                                                </span>
                                            </td>
                                            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium">
                                                <button
                                                    class="text-amber-600 hover:text-amber-800 mr-3"
                                                    title="Change Password"
                                                    aria-label="Change Password"
                                                    onclick={() => openChangePasswordModal(user)}
                                                >
                                                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5">
                                                        <path stroke-linecap="round" stroke-linejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
                                                    </svg>
                                                </button>
                                                <button
                                                    class={userData && userData.email === user.email && user.enabled 
                                                        ? "text-gray-400 cursor-not-allowed" 
                                                        : "hover:opacity-80"}
                                                    style={userData && userData.email === user.email && user.enabled ? "" : "color: #2271b3;"}
                                                    title={userData && userData.email === user.email && user.enabled 
                                                        ? "You cannot disable your own account" 
                                                        : (user.enabled ? 'Disable User' : 'Enable User')}
                                                    aria-label={userData && userData.email === user.email && user.enabled 
                                                        ? "You cannot disable your own account" 
                                                        : (user.enabled ? 'Disable User' : 'Enable User')}
                                                    onclick={() => toggleUserStatus(user)}
                                                    disabled={userData && userData.email === user.email && user.enabled}
                                                >
                                                    {#if user.enabled}
                                                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5">
                                                            <path stroke-linecap="round" stroke-linejoin="round" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728L5.636 5.636m12.728 12.728L18.364 5.636M5.636 18.364l12.728-12.728" />
                                                        </svg>
                                                    {:else}
                                                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5">
                                                            <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                                        </svg>
                                                    {/if}
                                                </button>
                                            </td>
                                        </tr>
                                    {/each}
                                </tbody>
                            </table>
                        </div>
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
                                class="px-4 py-2 text-white rounded-md disabled:opacity-50 disabled:cursor-not-allowed hover:opacity-90"
                                style="background-color: #2271b3;"
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
                                                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                                                    {formatDate(assistant.created_at)}
                                                </td>
                                                <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                                                    <button
                                                        onclick={() => manageAssistantAccess(assistant)}
                                                        class="px-3 py-1 text-white rounded-md text-xs hover:opacity-90"
                                                        style="background-color: #2271b3;"
                                                    >
                                                        Manage Access
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
                        <div class="bg-white border-l-4 border-green-500 shadow-sm rounded-lg mb-4">
                            <div class="px-4 py-3">
                                <div class="flex items-center justify-between">
                                    <div>
                                        <h1 class="text-xl font-semibold text-gray-900">{dashboardData.organization.name}</h1>
                                        <p class="text-sm text-gray-600">Organization Settings</p>
                                    </div>
                                    <div class="text-right text-sm text-gray-500">
                                        {#if targetOrgSlug}
                                            <div class="text-xs text-blue-600 mb-1">
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
                            <div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                            <p class="mt-2 text-gray-600">Loading settings...</p>
                        </div>
                    {:else}
                        <!-- Signup Settings -->
                        <div class="bg-white overflow-hidden shadow rounded-lg mb-6">
                            <div class="px-4 py-5 sm:p-6">
                                <h3 class="text-lg leading-6 font-medium text-gray-900 mb-4">Signup Settings</h3>
                                
                                <div class="space-y-4">
                                    <div class="flex items-center">
                                        <input
                                            id="signup-enabled"
                                            type="checkbox"
                                            bind:checked={newSignupSettings.signup_enabled}
                                            class="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                                        >
                                        <label for="signup-enabled" class="ml-2 block text-sm text-gray-900">
                                            Enable organization-specific signup
                                        </label>
                                    </div>

                                    {#if newSignupSettings.signup_enabled}
                                        <div>
                                            <label for="signup-key" class="block text-sm font-medium text-gray-700">Signup Key</label>
                                            <input
                                                type="text"
                                                id="signup-key"
                                                bind:value={newSignupSettings.signup_key}
                                                class="mt-1 block w-full border border-gray-300 rounded-md px-3 py-2 shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                                                placeholder="Enter unique signup key"
                                            >
                                            <p class="mt-1 text-sm text-gray-500">
                                                Unique key for users to signup to this organization (8-64 characters)
                                            </p>
                                        </div>
                                    {/if}

                                    <button
                                        onclick={updateSignupSettings}
                                        class="text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline hover:opacity-90"
                                        style="background-color: #2271b3;"
                                    >
                                        Update Signup Settings
                                    </button>
                                </div>
                            </div>
                        </div>

                        <!-- API Status Overview -->
                        {#if dashboardData && dashboardData.api_status}
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
                                                            <span class="text-blue-600">• <strong>{providerStatus.enabled_models.length}</strong> selected</span>
                                                            {#if providerStatus.default_model}
                                                                <span class="text-green-600">• Default: {providerStatus.default_model}</span>
                                                            {/if}
                                                        {:else}
                                                            <span class="text-gray-500">• No models selected</span>
                                                        {/if}
                                                    </div>
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
                                                    <div class="text-sm text-red-600">
                                                        {providerStatus.error}
                                                    </div>
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
                                            class="mt-1 block w-full border border-gray-300 rounded-md px-3 py-2 shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                                            placeholder={apiSettings.openai_api_key_set ? "••••••••••••••••" : "Enter OpenAI API key"}
                                            oninput={() => newApiSettings.openai_api_key && addPendingChange('OpenAI API key updated')}
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
                                            class="mt-1 block w-full border border-gray-300 rounded-md px-3 py-2 shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
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
                                            class="mt-1 block w-full border border-gray-300 rounded-md px-3 py-2 shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
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
                                        
                                        {#if apiSettings.available_models && Object.keys(apiSettings.available_models).length > 0}
                                            {#each Object.entries(apiSettings.available_models) as [providerName, models]}
                                                <div class="mb-6 border rounded-lg p-4">
                                                    <div class="flex items-center justify-between mb-3">
                                                        <h4 class="font-medium text-gray-900 capitalize">{providerName}</h4>
                                                        <button
                                                            type="button"
                                                            class="px-3 py-1 text-sm text-white rounded hover:opacity-90"
                                                            style="background-color: #2271b3;"
                                                            onclick={() => openModelModal(providerName, models)}
                                                        >
                                                            Manage Models
                                                        </button>
                                                    </div>
                                                    
                                                    <div class="text-sm text-gray-600 mb-2">
                                                        <strong>{newApiSettings.selected_models?.[providerName]?.length || 0}</strong> of {models.length} models enabled
                                                    </div>
                                                    
                                                    <div class="bg-gray-50 rounded p-3 max-h-32 overflow-y-auto">
                                                        {#if newApiSettings.selected_models?.[providerName]?.length > 0}
                                                            <div class="flex flex-wrap gap-1">
                                                                {#each newApiSettings.selected_models[providerName] as model}
                                                                    <span class="inline-block px-2 py-1 text-xs bg-blue-100 text-blue-800 rounded">
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
                                            <div class="text-center py-8 text-gray-500">
                                                <p>No API providers configured or available.</p>
                                            </div>
                                        {/if}
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
                                        class="font-mono text-sm mt-1 block w-full border border-gray-300 rounded-md px-3 py-2 shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 min-h-[280px]"
                                        bind:value={assistantDefaultsJson}
                                        placeholder={assistantDefaultsPlaceholder}
                                    ></textarea>

                                    <div class="flex items-center gap-3">
                                        <button
                                            class="text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline disabled:opacity-50 hover:opacity-90"
                                            style="background-color: #2271b3;"
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
                </div>
            {/if}
        </div>
    </main>
</div>

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
                                class="text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline disabled:opacity-50 hover:opacity-90" 
                                style="background-color: #2271b3;"
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
                                class="text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline disabled:opacity-50 hover:opacity-90" 
                                style="background-color: #2271b3;"
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
                            class="px-3 py-2 text-white rounded disabled:opacity-50 hover:opacity-90"
                            style="background-color: #2271b3;"
                            onclick={moveAllToEnabled}
                            disabled={modalDisabledModels.length === 0}
                            title="Move all models to enabled"
                        >
                            &lt;&lt;
                        </button>
                        <button
                            type="button"
                            class="px-3 py-2 text-white rounded disabled:opacity-50 hover:opacity-90"
                            style="background-color: #2271b3;"
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
                            class="px-4 py-2 text-white rounded hover:opacity-90"
                            style="background-color: #2271b3;"
                            onclick={saveModelSelection}
                        >
                            Save Changes
                        </button>
                </div>
            </div>
        </div>
    </div>
{/if}

<!-- Assistant Access Manager Modal -->
<AssistantAccessManager
    assistant={selectedAssistant}
    bind:show={showAccessModal}
    on:close={closeAccessModal}
    on:updated={handleAccessUpdated}
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