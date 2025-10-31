<script>
    import { onMount, onDestroy } from 'svelte';
    import { browser } from '$app/environment';
    import { page } from '$app/stores'; // Import page store to read URL params
    import { goto } from '$app/navigation';
    import { base } from '$app/paths';
    import { _ } from '$lib/i18n'; // Assuming i18n setup
    import axios from 'axios';
    import { getApiUrl } from '$lib/config';
    import { user } from '$lib/stores/userStore'; // Import user store for auth token
    import * as adminService from '$lib/services/adminService'; // Import admin service for bulk operations
    
    // Import filtering/pagination components
    import Pagination from '$lib/components/common/Pagination.svelte';
    import FilterBar from '$lib/components/common/FilterBar.svelte';
    import { processListData } from '$lib/utils/listHelpers';

    // --- State Management ---
    /** @type {'dashboard' | 'users' | 'organizations'} */
    let currentView = $state('users'); // Changed default view to users
    let localeLoaded = $state(true); // Assume loaded for now
    
    // Current user data for self-disable prevention
    /** @type {any} */
    let currentUserData = $state(null);

    // --- Users Management State ---
    /** @type {Array<any>} */
    let allUsers = $state([]); // All users (fetched once)
    /** @type {Array<any>} */
    let displayUsers = $state([]); // Filtered/paginated users (for display)
    let isLoadingUsers = $state(false);
    /** @type {string | null} */
    let usersError = $state(null);
    
    // Users filtering state
    let usersSearch = $state('');
    let usersFilterType = $state('');
    let usersFilterEnabled = $state('');
    let usersFilterOrg = $state('');
    
    // Users sorting state
    let usersSortBy = $state('id');
    let usersSortOrder = $state('asc');
    
    // Users pagination state
    let usersPage = $state(1);
    let usersPerPage = $state(10);
    let usersTotalPages = $state(1);
    let usersTotalItems = $state(0);
    
    // Keep reference to users for table (will point to displayUsers)
    let users = $derived(displayUsers);
    
    // --- Bulk Selection State ---
    let selectedUsers = $state(/** @type {number[]} */ ([]));
    
    // Sync selectedUsers with user.selected checkboxes
    $effect(() => {
        if (users.length > 0) {
            selectedUsers = users.filter(u => u.selected).map(u => u.id);
        }
    });
    
    // --- Enable/Disable Confirmation Modals ---
    let showDisableConfirm = $state(false);
    let showEnableConfirm = $state(false);
    let actionType = $state(''); // 'single' or 'bulk'
    /** @type {any | null} */
    let targetUser = $state(null);

    // --- Create User Modal State ---
    let isCreateUserModalOpen = $state(false);
    let newUser = $state({
        email: '',
        name: '',
        password: '',
        role: 'user', // Default role
        organization_id: null, // Default to no organization selected
        user_type: 'creator' // Default type: 'creator' or 'end_user'
    });
    let isCreatingUser = $state(false);
    /** @type {string | null} */
    let createUserError = $state(null);
    let createUserSuccess = $state(false);
    
    // --- Organizations for User Creation ---
    /** @type {Array<{id: number, name: string, slug: string, is_system: boolean}>} */
    let organizationsForUsers = $state([]);
    let isLoadingOrganizationsForUsers = $state(false);
    /** @type {string | null} */
    let organizationsForUsersError = $state(null);

    // --- Change Password Modal State ---
    let isChangePasswordModalOpen = $state(false);
    let passwordChangeData = $state({
        email: '',
        new_password: ''
    });
    let isChangingPassword = $state(false);
    /** @type {string | null} */
    let changePasswordError = $state(null);
    let changePasswordSuccess = $state(false);
    let selectedUserName = $state('');

    // --- Organizations Management State ---
    /** @type {Array<any>} */
    let organizations = $state([]);
    let isLoadingOrganizations = $state(false);
    /** @type {string | null} */
    let organizationsError = $state(null);

    // --- Create Organization Modal State ---
    let isCreateOrgModalOpen = $state(false);
    let newOrg = $state({
        slug: '',
        name: '',
        admin_user_id: null,
        signup_enabled: false,
        signup_key: '',
        use_system_baseline: true,
        config: {
            version: "1.0",
            setups: {
                default: {
                    name: "Default Setup",
                    providers: {},
                    knowledge_base: {}
                }
            },
            features: {
                rag_enabled: true,
                lti_publishing: true,
                signup_enabled: false
            },
            limits: {
                usage: {
                    tokens_per_month: 1000000,
                    max_assistants: 100,
                    max_assistants_per_user: 10,
                    storage_gb: 10
                }
            }
        }
    });
    let isCreatingOrg = $state(false);
    /** @type {string | null} */
    let createOrgError = $state(null);
    let createOrgSuccess = $state(false);

    // --- System Org Users for Admin Selection ---
    /** @type {Array<{id: number, email: string, name: string, role: string, joined_at: number}>} */
    let systemOrgUsers = $state([]);
    let isLoadingSystemUsers = $state(false);
    /** @type {string | null} */
    let systemUsersError = $state(null);

    // --- View Organization Config Modal State ---
    let isViewConfigModalOpen = $state(false);
    /** @type {any | null} */
    let selectedOrg = $state(null);
    /** @type {any | null} */
    let selectedOrgConfig = $state(null);
    let isLoadingOrgConfig = $state(false);
    /** @type {string | null} */
    let configError = $state(null);

    // --- URL Handling ---
    /** @type {Function|null} */
    let unsubscribePage = null;
    /** @type {Function|null} */
    let unsubscribeUser = null;

    // --- Navigation Functions ---
    function showDashboard() {
        currentView = 'dashboard';
        goto(`${base}/admin`, { replaceState: true });
    }

    function showUsers() {
        currentView = 'users';
        goto(`${base}/admin?view=users`, { replaceState: true });
        // Always fetch users when this view is explicitly selected
        fetchUsers();
    }

    function showOrganizations() {
        currentView = 'organizations';
        goto(`${base}/admin?view=organizations`, { replaceState: true });
        // Always fetch organizations when this view is explicitly selected
        fetchOrganizations();
    }

    // --- Modal Functions ---
    function openCreateUserModal() {
        // Reset form state
        newUser = {
            email: '',
            name: '',
            password: '',
            role: 'user',
            organization_id: null,
            user_type: 'creator'
        };
        createUserError = null;
        createUserSuccess = false;
        isCreateUserModalOpen = true;
        
        // Fetch organizations for the dropdown
        fetchOrganizationsForUsers();
    }

    function closeCreateUserModal() {
        isCreateUserModalOpen = false;
        // Clear any previous state
        createUserError = null;
    }

    /**
     * Open the change password modal for a specific user
     * @param {string} email - User's email
     * @param {string} name - User's name for display
     */
    function openChangePasswordModal(email, name) {
        // Reset form state
        passwordChangeData = {
            email: email,
            new_password: ''
        };
        selectedUserName = name;
        changePasswordError = null;
        changePasswordSuccess = false;
        isChangePasswordModalOpen = true;
    }

    function closeChangePasswordModal() {
        isChangePasswordModalOpen = false;
        // Clear any previous state
        changePasswordError = null;
        selectedUserName = '';
    }

    // User enable/disable functions for system admin  
    // --- Bulk Selection Functions ---
    function handleSelectAll() {
        const selectAllCheckbox = /** @type {HTMLInputElement|null} */ (document.querySelector('input[aria-label="Select all users"]'));
        if (selectAllCheckbox?.checked) {
            // Select all users except current user
            users.forEach(u => {
                if (!(currentUserData && currentUserData.email === u.email)) {
                    u.selected = true;
                }
            });
        } else {
            users.forEach(u => u.selected = false);
        }
    }

    function clearSelection() {
        users.forEach(u => u.selected = false);
    }

    // --- Enable/Disable Dialog Functions ---
    /**
     * @param {any} user
     */
    function showDisableDialog(user) {
        targetUser = user;
        actionType = 'single';
        showDisableConfirm = true;
    }

    /**
     * @param {any} user
     */
    function showEnableDialog(user) {
        targetUser = user;
        actionType = 'single';
        showEnableConfirm = true;
    }

    function handleBulkDisable() {
        if (selectedUsers.length === 0) return;
        actionType = 'bulk';
        showDisableConfirm = true;
    }

    function handleBulkEnable() {
        if (selectedUsers.length === 0) return;
        actionType = 'bulk';
        showEnableConfirm = true;
    }

    async function confirmDisable() {
        try {
            const token = getAuthToken();
            if (!token) {
                throw new Error('Authentication token not found');
            }

            if (actionType === 'single') {
                await adminService.disableUser(token, targetUser.id);
                console.log(`User ${targetUser.email} disabled`);
                alert(`User ${targetUser.name} has been disabled successfully.`);
            } else {
                const result = await adminService.disableUsersBulk(token, selectedUsers);
                console.log(`Disabled ${result.disabled} user(s)`);
                alert(`Successfully disabled ${result.disabled} user(s)${result.failed > 0 ? `. Failed: ${result.failed}` : ''}`);
            }
            
            clearSelection();
            await fetchUsers(); // Refresh list
        } catch (error) {
            console.error('Failed to disable user(s):', error);
            alert(`Error: ${error.message || 'Failed to disable user(s)'}`);
        } finally {
            showDisableConfirm = false;
            targetUser = null;
        }
    }

    async function confirmEnable() {
        try {
            const token = getAuthToken();
            if (!token) {
                throw new Error('Authentication token not found');
            }

            if (actionType === 'single') {
                await adminService.enableUser(token, targetUser.id);
                console.log(`User ${targetUser.email} enabled`);
                alert(`User ${targetUser.name} has been enabled successfully.`);
            } else {
                const result = await adminService.enableUsersBulk(token, selectedUsers);
                console.log(`Enabled ${result.enabled} user(s)`);
                alert(`Successfully enabled ${result.enabled} user(s)${result.failed > 0 ? `. Failed: ${result.failed}` : ''}`);
            }
            
            clearSelection();
            await fetchUsers(); // Refresh list
        } catch (error) {
            console.error('Failed to enable user(s):', error);
            alert(`Error: ${error.message || 'Failed to enable user(s)'}`);
        } finally {
            showEnableConfirm = false;
            targetUser = null;
        }
    }

    /**
     * @param {any} user
     */
    async function toggleUserStatusAdmin(user) {
        // Use the new modal-based approach
        if (user.enabled) {
            showDisableDialog(user);
        } else {
            showEnableDialog(user);
        }
    }

    function openCreateOrgModal() {
        // Reset form state
        newOrg = {
            slug: '',
            name: '',
            admin_user_id: null,
            signup_enabled: false,
            signup_key: '',
            use_system_baseline: true,
            config: {
                version: "1.0",
                setups: {
                    default: {
                        name: "Default Setup",
                        providers: {},
                        knowledge_base: {}
                    }
                },
                features: {
                    rag_enabled: true,
                    lti_publishing: true,
                    signup_enabled: false
                },
                limits: {
                    usage: {
                        tokens_per_month: 1000000,
                        max_assistants: 100,
                        max_assistants_per_user: 10,
                        storage_gb: 10
                    }
                }
            }
        };
        createOrgError = null;
        createOrgSuccess = false;
        isCreateOrgModalOpen = true;
        
        // Fetch system org users for admin selection
        fetchSystemOrgUsers();
    }

    function closeCreateOrgModal() {
        isCreateOrgModalOpen = false;
        // Clear any previous state
        createOrgError = null;
    }

    /**
     * Open the view configuration modal for a specific organization
     * @param {any} org - Organization object
     */
    function openViewConfigModal(org) {
        selectedOrg = org;
        selectedOrgConfig = null;
        configError = null;
        isViewConfigModalOpen = true;
        fetchOrganizationConfig(org.slug);
    }

    function closeViewConfigModal() {
        isViewConfigModalOpen = false;
        selectedOrg = null;
        selectedOrgConfig = null;
        configError = null;
    }

    /**
     * Navigate to organization admin interface for a specific organization
     * @param {any} org - Organization object
     */
    function administerOrganization(org) {
        // Navigate to org-admin with organization parameter
        goto(`${base}/org-admin?org=${org.slug}`);
    }

    // --- Form Handling ---
    /**
     * @param {Event} e - The form submission event
     */
    async function handleCreateUser(e) {
        e.preventDefault();
        
        // Basic form validation
        if (!newUser.email || !newUser.name || !newUser.password) {
            createUserError = localeLoaded ? $_('admin.users.errors.fillRequired', { default: 'Please fill in all required fields.' }) : 'Please fill in all required fields.';
            return;
        }
        
        if (!newUser.email.includes('@')) {
            createUserError = localeLoaded ? $_('admin.users.errors.invalidEmail', { default: 'Please enter a valid email address.' }) : 'Please enter a valid email address.';
            return;
        }
        
        createUserError = null;
        isCreatingUser = true;
        
        try {
            const token = getAuthToken();
            if (!token) {
                throw new Error(localeLoaded ? $_('admin.users.errors.authTokenNotFound', { default: 'Authentication token not found. Please log in again.' }) : 'Authentication token not found. Please log in again.');
            }
            
            // Construct form data in URL-encoded format
            const formData = new URLSearchParams();
            formData.append('email', newUser.email);
            formData.append('name', newUser.name);
            formData.append('password', newUser.password);
            formData.append('role', newUser.role);
            // Ensure admin users have user_type='creator'
            const userType = newUser.role === 'admin' ? 'creator' : newUser.user_type;
            formData.append('user_type', userType);
            
            // Add organization_id if selected
            if (newUser.organization_id) {
                formData.append('organization_id', String(newUser.organization_id));
            }
            
            const apiUrl = getApiUrl('/admin/users/create');
            console.log(`Creating user at: ${apiUrl}`);
            
            const response = await axios.post(apiUrl, formData, {
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/x-www-form-urlencoded'
                }
            });
            
            console.log('Create user response:', response.data);
            
            if (response.data && response.data.success) {
                createUserSuccess = true;
                // Wait 1.5 seconds to show success message, then close modal and refresh list
                setTimeout(() => {
                    closeCreateUserModal();
                    fetchUsers(); // Refresh the users list
                }, 1500);
            } else {
                throw new Error(response.data.error || (localeLoaded ? $_('admin.users.errors.createFailed', { default: 'Failed to create user.' }) : 'Failed to create user.'));
            }
        } catch (err) {
            console.error('Error creating user:', err);
            if (axios.isAxiosError(err) && err.response?.data?.error) {
                createUserError = err.response.data.error;
            } else if (axios.isAxiosError(err) && err.response?.data?.detail) {
                // Handle validation errors from FastAPI
                if (Array.isArray(err.response.data.detail)) {
                    /** @type {Array<{msg: string}>} */
                    const details = err.response.data.detail;
                    createUserError = details.map(d => d.msg).join(', ');
                } else {
                    createUserError = err.response.data.detail;
                }
            } else if (err instanceof Error) {
                createUserError = err.message;
            } else {
                createUserError = localeLoaded ? $_('admin.users.errors.unknownError', { default: 'An unknown error occurred while creating the user.' }) : 'An unknown error occurred while creating the user.';
            }
        } finally {
            isCreatingUser = false;
        }
    }

    /**
     * Handle password change form submission
     * @param {Event} e - The form submission event
     */
    async function handleChangePassword(e) {
        e.preventDefault();
        
        // Basic form validation
        if (!passwordChangeData.new_password) {
            changePasswordError = localeLoaded ? $_('admin.users.errors.passwordRequired', { default: 'Please enter a new password.' }) : 'Please enter a new password.';
            return;
        }
        
        if (passwordChangeData.new_password.length < 8) {
            changePasswordError = localeLoaded ? $_('admin.users.errors.passwordMinLength', { default: 'Password should be at least 8 characters.' }) : 'Password should be at least 8 characters.';
            return;
        }
        
        changePasswordError = null;
        isChangingPassword = true;
        
        try {
            const token = getAuthToken();
            if (!token) {
                throw new Error(localeLoaded ? $_('admin.users.errors.authTokenNotFound', { default: 'Authentication token not found. Please log in again.' }) : 'Authentication token not found. Please log in again.');
            }
            
            // Construct form data in URL-encoded format
            const formData = new URLSearchParams();
            formData.append('email', passwordChangeData.email);
            formData.append('new_password', passwordChangeData.new_password);
            
            const apiUrl = getApiUrl('/admin/users/update-password');
            console.log(`Changing password at: ${apiUrl}`);
            
            const response = await axios.post(apiUrl, formData, {
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/x-www-form-urlencoded'
                }
            });
            
            console.log('Change password response:', response.data);
            
            if (response.data && response.data.success) {
                changePasswordSuccess = true;
                // Wait 1.5 seconds to show success message, then close modal
                setTimeout(() => {
                    closeChangePasswordModal();
                }, 1500);
            } else {
                throw new Error(response.data.error || response.data.message || (localeLoaded ? $_('admin.users.errors.passwordChangeFailed', { default: 'Failed to change password.' }) : 'Failed to change password.'));
            }
        } catch (err) {
            console.error('Error changing password:', err);
            if (axios.isAxiosError(err) && err.response?.data?.error) {
                changePasswordError = err.response.data.error;
            } else if (axios.isAxiosError(err) && err.response?.data?.detail) {
                // Handle validation errors from FastAPI
                if (Array.isArray(err.response.data.detail)) {
                    /** @type {Array<{msg: string}>} */
                    const details = err.response.data.detail;
                    changePasswordError = details.map(d => d.msg).join(', ');
                } else {
                    changePasswordError = err.response.data.detail;
                }
            } else if (err instanceof Error) {
                changePasswordError = err.message;
            } else {
                changePasswordError = localeLoaded ? $_('admin.users.errors.passwordChangeUnknownError', { default: 'An unknown error occurred while changing the password.' }) : 'An unknown error occurred while changing the password.';
            }
        } finally {
            isChangingPassword = false;
        }
    }

    /**
     * Handle organization creation form submission
     * @param {Event} e - The form submission event
     */
    async function handleCreateOrganization(e) {
        e.preventDefault();
        
        // Basic form validation
        if (!newOrg.slug || !newOrg.name) {
            createOrgError = localeLoaded ? $_('admin.organizations.errors.fillRequired', { default: 'Please fill in all required fields.' }) : 'Please fill in all required fields.';
            return;
        }
        
        // Validate admin user selection
        if (!newOrg.admin_user_id) {
            createOrgError = localeLoaded ? $_('admin.organizations.errors.selectAdmin', { default: 'Please select an admin user for the organization.' }) : 'Please select an admin user for the organization.';
            return;
        }
        
        // Validate slug format (URL-friendly)
        if (!/^[a-z0-9-]+$/.test(newOrg.slug)) {
            createOrgError = localeLoaded ? $_('admin.organizations.errors.slugInvalid', { default: 'Slug must contain only lowercase letters, numbers, and hyphens.' }) : 'Slug must contain only lowercase letters, numbers, and hyphens.';
            return;
        }
        
        // Validate signup key if signup is enabled
        if (newOrg.signup_enabled && (!newOrg.signup_key || newOrg.signup_key.trim().length < 8)) {
            createOrgError = localeLoaded ? $_('admin.organizations.errors.signupKeyLength', { default: 'Signup key must be at least 8 characters long when signup is enabled.' }) : 'Signup key must be at least 8 characters long when signup is enabled.';
            return;
        }
        
        // Validate signup key format if provided
        if (newOrg.signup_key && !/^[a-zA-Z0-9_-]+$/.test(newOrg.signup_key)) {
            createOrgError = localeLoaded ? $_('admin.organizations.errors.signupKeyInvalid', { default: 'Signup key can only contain letters, numbers, hyphens, and underscores.' }) : 'Signup key can only contain letters, numbers, hyphens, and underscores.';
            return;
        }
        
        createOrgError = null;
        isCreatingOrg = true;
        
        try {
            const token = getAuthToken();
            if (!token) {
                throw new Error(localeLoaded ? $_('admin.organizations.errors.authTokenNotFound', { default: 'Authentication token not found. Please log in again.' }) : 'Authentication token not found. Please log in again.');
            }
            
            // Use the enhanced endpoint with admin assignment
            const apiUrl = getApiUrl('/admin/organizations/enhanced');
            console.log(`Creating organization with admin assignment at: ${apiUrl}`);
            
            // Prepare the payload
            const payload = {
                slug: newOrg.slug,
                name: newOrg.name,
                admin_user_id: parseInt(newOrg.admin_user_id),
                signup_enabled: newOrg.signup_enabled,
                signup_key: newOrg.signup_enabled ? newOrg.signup_key.trim() : null,
                use_system_baseline: newOrg.use_system_baseline
            };
            
            console.log('Organization creation payload:', payload);
            
            const response = await axios.post(apiUrl, payload, {
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            });
            
            console.log('Create organization response:', response.data);
            
            if (response.data) {
                createOrgSuccess = true;
                // Wait 1.5 seconds to show success message, then close modal and refresh list
                setTimeout(() => {
                    closeCreateOrgModal();
                    fetchOrganizations(); // Refresh the organizations list
                }, 1500);
            } else {
                throw new Error(localeLoaded ? $_('admin.organizations.errors.createFailed', { default: 'Failed to create organization.' }) : 'Failed to create organization.');
            }
        } catch (err) {
            console.error('Error creating organization:', err);
            if (axios.isAxiosError(err) && err.response?.data?.detail) {
                createOrgError = err.response.data.detail;
            } else if (err instanceof Error) {
                createOrgError = err.message;
            } else {
                createOrgError = localeLoaded ? $_('admin.organizations.errors.unknownError', { default: 'An unknown error occurred while creating the organization.' }) : 'An unknown error occurred while creating the organization.';
            }
        } finally {
            isCreatingOrg = false;
        }
    }

    // --- Keyboard Event Handlers ---
    function handleKeydown(event) {
        // Handle ESC key to close modals
        if (event.key === 'Escape') {
            if (isCreateOrgModalOpen) {
                closeCreateOrgModal();
            } else if (isViewConfigModalOpen) {
                closeViewConfigModal();
            } else if (isChangePasswordModalOpen) {
                closeChangePasswordModal();
            }
        }
    }

    // --- Lifecycle ---
    onMount(() => {
        console.log("Admin page mounted");
        
        // Add global keydown listener for ESC key
        document.addEventListener('keydown', handleKeydown);
        
        // Check if user is logged in and is admin
        unsubscribeUser = user.subscribe(userData => {
            currentUserData = userData; // Store current user data for self-disable prevention
            
            if (userData.isLoggedIn) {
                console.log("User is logged in:", userData.email);
                // Check if user is admin (based on role in userData)
                const userRole = userData.data?.role;
                if (userRole === 'admin') {
                    console.log("User has admin role, can access admin features");
                } else {
                    console.warn("User doesn't have admin role:", userRole);
                    // Optionally redirect non-admin users
                    // goto(`${base}/`);
                }
            } else {
                console.warn("User not logged in, redirecting...");
                // Redirect to login page
                // goto(`${base}/login`);
            }
        });

        unsubscribePage = page.subscribe(currentPage => {
            console.log("Admin page store updated:", currentPage.url.searchParams.toString());
            const viewParam = currentPage.url.searchParams.get('view');
            
            if (viewParam === 'users') {
                console.log("URL indicates 'users' view.");
                currentView = 'users';
                fetchUsers(); // Always fetch when the view is users
            } else if (viewParam === 'organizations') {
                console.log("URL indicates 'organizations' view.");
                currentView = 'organizations';
                fetchOrganizations(); // Always fetch when the view is organizations
            } else {
                console.log("URL indicates 'dashboard' view.");
                currentView = 'dashboard';
            }
        });

        // Initial fetch if needed based on the current view
        if (currentView === 'users') {
            fetchUsers();
        } else if (currentView === 'organizations') {
            fetchOrganizations();
        }
    });

    onDestroy(() => {
        console.log("Admin page unmounting");
        
        // Remove global keydown listener (only on client)
        if (browser) {
            document.removeEventListener('keydown', handleKeydown);
        }
        
        if (unsubscribePage) {
            unsubscribePage();
        }
        if (unsubscribeUser) {
            unsubscribeUser();
        }
    });

    // --- Data Fetching ---
    // Get auth token from user store
    function getAuthToken() {
        const userData = $user;
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
        usersError = null;
        
        try {
            const token = getAuthToken();
            if (!token) {
                throw new Error('Authentication token not found. Please log in again.');
            }

            const apiUrl = getApiUrl('/users');
            console.log(`Fetching users from: ${apiUrl}`);

            const response = await axios.get(apiUrl, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            console.log('API Response:', response.data);

            if (response.data && response.data.success) {
                allUsers = (response.data.data || []).map(u => ({...u, selected: false}));
                console.log(`Fetched ${allUsers.length} users`);
                applyUsersFilters();
            } else {
                throw new Error(response.data.error || 'Failed to fetch users.');
            }
        } catch (err) {
            console.error('Error fetching users:', err);
            if (axios.isAxiosError(err) && err.response?.status === 401) {
                usersError = 'Access denied. Admin privileges required.';
            } else if (axios.isAxiosError(err) && err.response?.data?.error) {
                usersError = err.response.data.error;
            } else if (err instanceof Error) {
                usersError = err.message;
            } else {
                usersError = 'An unknown error occurred while fetching users.';
            }
            allUsers = [];
            displayUsers = [];
        } finally {
            isLoadingUsers = false;
        }
    }
    
    // Apply filters, sorting, and pagination to users
    function applyUsersFilters() {
        // Build filters object with custom logic for merged user_type filter
        /** @type {Record<string, any>} */
        const filters = {
            enabled: usersFilterEnabled === '' ? null : usersFilterEnabled,
            'organization.id': usersFilterOrg ? parseInt(usersFilterOrg) : null
        };
        
        // Handle merged user_type filter (can be 'admin', 'creator', or 'end_user')
        if (usersFilterType === 'admin') {
            // Admin users: filter by role === 'admin'
            filters.role = 'admin';
        } else if (usersFilterType === 'end_user') {
            // End users: filter by user_type === 'end_user'
            filters.user_type = 'end_user';
        }
        
        /** @type {any} */
        let result = processListData(allUsers, {
            search: usersSearch,
            searchFields: ['name', 'email', 'organization.name'],
            filters: filters,
            sortBy: usersSortBy,
            sortOrder: usersSortOrder,
            page: usersPage,
            itemsPerPage: usersPerPage
        });
        
        // Additional filtering for 'creator' type (non-admin creators)
        if (usersFilterType === 'creator') {
            result.items = result.items.filter((/** @type {any} */ u) => u.role !== 'admin' && u.user_type === 'creator');
            result.filteredCount = result.items.length;
            result.totalPages = Math.ceil(result.filteredCount / usersPerPage) || 1;
            const safePage = Math.max(1, Math.min(usersPage, result.totalPages));
            result.currentPage = safePage;
            result.items = result.items.slice((safePage - 1) * usersPerPage, safePage * usersPerPage);
        }
        
        displayUsers = result.items.map((/** @type {any} */ u) => ({...u, selected: u.selected || false}));
        usersTotalItems = result.filteredCount;
        usersTotalPages = result.totalPages;
        usersPage = result.currentPage;
    }
    
    // Users filter/sort/pagination event handlers
    function handleUsersSearchChange(event) {
        usersSearch = event.detail.value;
        usersPage = 1;
        applyUsersFilters();
    }
    
    function handleUsersFilterChange(event) {
        const { key, value } = event.detail;
        if (key === 'user_type') usersFilterType = value;
        else if (key === 'enabled') usersFilterEnabled = value;
        else if (key === 'organization') usersFilterOrg = value;
        usersPage = 1;
        applyUsersFilters();
    }
    
    function handleUsersSortChange(event) {
        usersSortBy = event.detail.sortBy;
        usersSortOrder = event.detail.sortOrder;
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
    
    function handleUsersClearFilters() {
        usersSearch = '';
        usersFilterType = '';
        usersFilterEnabled = '';
        usersFilterOrg = '';
        usersSortBy = 'id';
        usersSortOrder = 'asc';
        usersPage = 1;
        applyUsersFilters();
    }

    async function fetchOrganizations() {
        if (isLoadingOrganizations) {
            console.log("Already loading organizations, skipping duplicate request");
            return;
        }
        
        console.log("Fetching organizations...");
        isLoadingOrganizations = true;
        organizationsError = null;
        
        try {
            const token = getAuthToken();
            if (!token) {
                throw new Error('Authentication token not found. Please log in again.');
            }

            const apiUrl = getApiUrl('/admin/organizations');
            console.log(`Fetching organizations from: ${apiUrl}`);

            const response = await axios.get(apiUrl, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            console.log('Organizations API Response:', response.data);

            if (response.data && Array.isArray(response.data)) {
                organizations = response.data;
                console.log(`Fetched ${organizations.length} organizations`);
            } else {
                throw new Error('Invalid response format.');
            }
        } catch (err) {
            console.error('Error fetching organizations:', err);
            if (axios.isAxiosError(err) && err.response?.status === 401) {
                organizationsError = 'Access denied. Admin privileges required.';
            } else if (axios.isAxiosError(err) && err.response?.data?.detail) {
                organizationsError = err.response.data.detail;
            } else if (err instanceof Error) {
                organizationsError = err.message;
            } else {
                organizationsError = 'An unknown error occurred while fetching organizations.';
            }
            organizations = [];
        } finally {
            isLoadingOrganizations = false;
        }
    }

    async function fetchSystemOrgUsers() {
        if (isLoadingSystemUsers) {
            console.log("Already loading system users, skipping duplicate request");
            return;
        }
        
        console.log("Fetching system organization users...");
        isLoadingSystemUsers = true;
        systemUsersError = null;
        
        try {
            const token = getAuthToken();
            if (!token) {
                throw new Error('Authentication token not found. Please log in again.');
            }

            const apiUrl = getApiUrl('/admin/organizations/system/users');
            console.log(`Fetching system users from: ${apiUrl}`);

            const response = await axios.get(apiUrl, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            console.log('System Users API Response:', response.data);

            if (response.data && Array.isArray(response.data)) {
                systemOrgUsers = response.data;
                console.log(`Fetched ${systemOrgUsers.length} system org users`);
            } else {
                throw new Error('Invalid response format.');
            }
        } catch (err) {
            console.error('Error fetching system org users:', err);
            if (axios.isAxiosError(err) && err.response?.status === 401) {
                systemUsersError = 'Access denied. Admin privileges required.';
            } else if (axios.isAxiosError(err) && err.response?.data?.detail) {
                systemUsersError = err.response.data.detail;
            } else if (err instanceof Error) {
                systemUsersError = err.message;
            } else {
                systemUsersError = 'An unknown error occurred while fetching system users.';
            }
            systemOrgUsers = [];
        } finally {
            isLoadingSystemUsers = false;
        }
    }

    async function fetchOrganizationsForUsers() {
        if (isLoadingOrganizationsForUsers) {
            console.log("Already loading organizations for users, skipping duplicate request");
            return;
        }
        
        console.log("Fetching organizations for user creation...");
        isLoadingOrganizationsForUsers = true;
        organizationsForUsersError = null;
        
        try {
            const token = getAuthToken();
            if (!token) {
                throw new Error('Authentication token not found. Please log in again.');
            }

            const apiUrl = getApiUrl('/admin/organizations/list');
            console.log(`Fetching organizations for users from: ${apiUrl}`);

            const response = await axios.get(apiUrl, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            console.log('Organizations for Users API Response:', response.data);

            if (response.data && response.data.success && Array.isArray(response.data.data)) {
                organizationsForUsers = response.data.data;
                console.log(`Fetched ${organizationsForUsers.length} organizations for user assignment`);
            } else {
                throw new Error('Invalid response format.');
            }
        } catch (err) {
            console.error('Error fetching organizations for users:', err);
            if (axios.isAxiosError(err) && err.response?.status === 401) {
                organizationsForUsersError = 'Access denied. Admin privileges required.';
            } else if (axios.isAxiosError(err) && err.response?.data?.detail) {
                organizationsForUsersError = err.response.data.detail;
            } else if (err instanceof Error) {
                organizationsForUsersError = err.message;
            } else {
                organizationsForUsersError = 'An unknown error occurred while fetching organizations.';
            }
            organizationsForUsers = [];
        } finally {
            isLoadingOrganizationsForUsers = false;
        }
    }

    /**
     * @param {string} slug - Organization slug
     */
    async function fetchOrganizationConfig(slug) {
        if (!slug) return;
        
        isLoadingOrgConfig = true;
        configError = null;
        
        try {
            const token = getAuthToken();
            if (!token) {
                throw new Error('Authentication token not found. Please log in again.');
            }

            const apiUrl = getApiUrl(`/admin/organizations/${slug}/config`);
            console.log(`Fetching organization config from: ${apiUrl}`);

            const response = await axios.get(apiUrl, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            console.log('Organization config response:', response.data);
            selectedOrgConfig = response.data;
        } catch (err) {
            console.error('Error fetching organization config:', err);
            if (axios.isAxiosError(err) && err.response?.data?.detail) {
                configError = err.response.data.detail;
            } else if (err instanceof Error) {
                configError = err.message;
            } else {
                configError = 'An unknown error occurred while fetching configuration.';
            }
        } finally {
            isLoadingOrgConfig = false;
        }
    }

    async function syncSystemOrganization() {
        try {
            const token = getAuthToken();
            if (!token) {
                throw new Error('Authentication token not found. Please log in again.');
            }

            const apiUrl = getApiUrl('/admin/organizations/system/sync');
            console.log(`Syncing system organization at: ${apiUrl}`);

            const response = await axios.post(apiUrl, {}, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            console.log('Sync system organization response:', response.data);
            
            // Refresh organizations list
            fetchOrganizations();
            
            // Show success message (you might want to add a toast notification here)
            alert('System organization synced successfully!');
        } catch (err) {
            console.error('Error syncing system organization:', err);
            let errorMessage = 'Failed to sync system organization.';
            
            if (axios.isAxiosError(err) && err.response?.data?.detail) {
                errorMessage = err.response.data.detail;
            } else if (err instanceof Error) {
                errorMessage = err.message;
            }
            
            alert(`Error: ${errorMessage}`);
        }
    }

    /**
     * @param {string} slug - Organization slug
     */
    async function deleteOrganization(slug) {
        if (!confirm(`Are you sure you want to delete organization '${slug}'? This action cannot be undone.`)) {
            return;
        }
        
        try {
            const token = getAuthToken();
            if (!token) {
                throw new Error('Authentication token not found. Please log in again.');
            }

            const apiUrl = getApiUrl(`/admin/organizations/${slug}`);
            console.log(`Deleting organization at: ${apiUrl}`);

            const response = await axios.delete(apiUrl, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            console.log('Delete organization response:', response.data);
            
            // Refresh organizations list
            fetchOrganizations();
            
            // Show success message
            alert(`Organization '${slug}' deleted successfully!`);
        } catch (err) {
            console.error('Error deleting organization:', err);
            let errorMessage = 'Failed to delete organization.';
            
            if (axios.isAxiosError(err) && err.response?.data?.detail) {
                errorMessage = err.response.data.detail;
            } else if (err instanceof Error) {
                errorMessage = err.message;
            }
            
            alert(`Error: ${errorMessage}`);
        }
    }

    // --- Migration Modal State ---
    let isMigrationModalOpen = $state(false);
    let migrationSourceOrg = $state(null);
    let migrationTargetOrgSlug = $state('');
    let migrationValidationResult = $state(null);
    let isValidatingMigration = $state(false);
    let migrationValidationError = $state(null);
    let isMigrating = $state(false);
    let migrationPreserveAdminRoles = $state(false);
    let migrationDeleteSource = $state(false);
    let migrationConflictStrategy = $state('rename');
    let migrationError = $state(null);
    let migrationSuccess = $state(false);
    let migrationReport = $state(null);

    /**
     * Open migration modal and validate migration
     * @param {any} org - Source organization
     */
    async function openMigrationModal(org) {
        migrationSourceOrg = org;
        migrationTargetOrgSlug = '';
        migrationValidationResult = null;
        migrationValidationError = null;
        migrationPreserveAdminRoles = false;
        migrationDeleteSource = false;
        migrationConflictStrategy = 'rename';
        migrationError = null;
        migrationSuccess = false;
        migrationReport = null;
        isMigrationModalOpen = true;
    }

    function closeMigrationModal() {
        isMigrationModalOpen = false;
        migrationSourceOrg = null;
        migrationTargetOrgSlug = '';
        migrationValidationResult = null;
        migrationValidationError = null;
        migrationError = null;
        migrationSuccess = false;
        migrationReport = null;
    }

    /**
     * Validate migration before execution
     */
    async function validateMigration() {
        if (!migrationTargetOrgSlug || !migrationSourceOrg) {
            migrationValidationError = 'Please select a target organization';
            return;
        }

        isValidatingMigration = true;
        migrationValidationError = null;

        try {
            const token = getAuthToken();
            if (!token) {
                throw new Error('Authentication token not found. Please log in again.');
            }

            const apiUrl = getApiUrl(`/admin/organizations/${migrationSourceOrg.slug}/migration/validate`);
            const response = await axios.post(apiUrl, {
                target_organization_slug: migrationTargetOrgSlug
            }, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            migrationValidationResult = response.data;
            
            if (!migrationValidationResult.can_migrate) {
                migrationValidationError = migrationValidationResult.error || 'Migration validation failed';
            }
        } catch (err) {
            console.error('Error validating migration:', err);
            migrationValidationError = 'Failed to validate migration';
            
            if (axios.isAxiosError(err) && err.response?.data?.detail) {
                migrationValidationError = err.response.data.detail;
            } else if (err instanceof Error) {
                migrationValidationError = err.message;
            }
        } finally {
            isValidatingMigration = false;
        }
    }

    /**
     * Execute organization migration
     */
    async function executeMigration() {
        if (!migrationTargetOrgSlug || !migrationSourceOrg) {
            migrationError = 'Please select a target organization';
            return;
        }

        if (!migrationValidationResult || !migrationValidationResult.can_migrate) {
            migrationError = 'Please validate migration first';
            return;
        }

        isMigrating = true;
        migrationError = null;
        migrationSuccess = false;

        try {
            const token = getAuthToken();
            if (!token) {
                throw new Error('Authentication token not found. Please log in again.');
            }

            const apiUrl = getApiUrl(`/admin/organizations/${migrationSourceOrg.slug}/migrate`);
            const response = await axios.post(apiUrl, {
                target_organization_slug: migrationTargetOrgSlug,
                conflict_strategy: migrationConflictStrategy,
                preserve_admin_roles: migrationPreserveAdminRoles,
                delete_source: migrationDeleteSource
            }, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            migrationReport = response.data;
            migrationSuccess = true;
            
            // Refresh organizations list
            fetchOrganizations();
            
            // Close modal after 3 seconds if successful
            if (migrationSuccess) {
                setTimeout(() => {
                    closeMigrationModal();
                }, 3000);
            }
        } catch (err) {
            console.error('Error executing migration:', err);
            migrationError = 'Failed to migrate organization';
            
            if (axios.isAxiosError(err) && err.response?.data?.detail) {
                migrationError = err.response.data.detail;
            } else if (err instanceof Error) {
                migrationError = err.message;
            }
        } finally {
            isMigrating = false;
        }
    }

</script>

<div class="container mx-auto px-4 py-8">
    <!-- Admin Navigation Tabs -->
    <div class="border-b border-gray-200 mb-6">
        <ul class="flex flex-wrap -mb-px">
            <li class="mr-2">
                <button
                    class={`inline-block py-2 px-4 text-sm font-medium ${currentView === 'dashboard' ? 'text-white bg-brand border-brand' : 'text-gray-500 hover:text-brand border-transparent'} rounded-t-lg border-b-2`}
                    onclick={showDashboard}
                    aria-label={localeLoaded ? $_('admin.tabs.dashboard', { default: 'Dashboard' }) : 'Dashboard'}
                >
                    {localeLoaded ? $_('admin.tabs.dashboard', { default: 'Dashboard' }) : 'Dashboard'}
                </button>
            </li>
            <li class="mr-2">
                <button
                    class={`inline-block py-2 px-4 text-sm font-medium ${currentView === 'users' ? 'text-white bg-brand border-brand' : 'text-gray-500 hover:text-brand border-transparent'} rounded-t-lg border-b-2`}
                    onclick={showUsers}
                    aria-label={localeLoaded ? $_('admin.tabs.users', { default: 'User Management' }) : 'User Management'}
                >
                    {localeLoaded ? $_('admin.tabs.users', { default: 'User Management' }) : 'User Management'}
                </button>
            </li>
            <li class="mr-2">
                <button
                    class={`inline-block py-2 px-4 text-sm font-medium ${currentView === 'organizations' ? 'text-white bg-brand border-brand' : 'text-gray-500 hover:text-brand border-transparent'} rounded-t-lg border-b-2`}
                    onclick={showOrganizations}
                    aria-label={localeLoaded ? $_('admin.tabs.organizations', { default: 'Organizations' }) : 'Organizations'}
                >
                    {localeLoaded ? $_('admin.tabs.organizations', { default: 'Organizations' }) : 'Organizations'}
                </button>
            </li>
        </ul>
    </div>

    <!-- View Content -->
    {#if currentView === 'dashboard'}
        <div>
            <h1 class="text-2xl font-semibold text-gray-800 mb-6">{localeLoaded ? $_('admin.dashboard.title', { default: 'Admin Dashboard' }) : 'Admin Dashboard'}</h1>
            <p class="text-gray-600">{localeLoaded ? $_('admin.dashboard.welcome', { default: 'Welcome to the administration area. Use the tabs above to navigate.' }) : 'Welcome to the administration area. Use the tabs above to navigate.'}</p>
        </div>
    {:else if currentView === 'users'}
        <!-- Users Management View -->
        <div class="flex justify-between items-center mb-6">
            <h1 class="text-2xl font-semibold text-gray-800">{localeLoaded ? $_('admin.users.title', { default: 'User Management' }) : 'User Management'}</h1>
            <button
                onclick={openCreateUserModal}
                class="bg-brand text-white py-2 px-4 rounded hover:bg-brand-hover focus:outline-none focus:ring-2 focus:ring-brand focus:ring-opacity-50"
                aria-label={localeLoaded ? $_('admin.users.actions.create', { default: 'Create User' }) : 'Create User'}
            >
                {localeLoaded ? $_('admin.users.actions.create', { default: 'Create User' }) : 'Create User'}
            </button>
        </div>

        {#if isLoadingUsers}
            <p class="text-center text-gray-500 py-4">{localeLoaded ? $_('admin.users.loading', { default: 'Loading users...' }) : 'Loading users...'}</p>
        {:else if usersError}
            <div class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative mb-6" role="alert">
                <strong class="font-bold">{localeLoaded ? $_('admin.users.errorTitle', { default: 'Error:' }) : 'Error:'}</strong>
                <span class="block sm:inline"> {usersError}</span>
            </div>
            <!-- Button to retry fetching -->
            <div class="text-center">
                <button
                    onclick={fetchUsers}
                    class="bg-brand text-white py-2 px-4 rounded hover:bg-brand-hover focus:outline-none focus:ring-2 focus:ring-brand focus:ring-opacity-50"
                >
                    {localeLoaded ? $_('admin.users.retry', { default: 'Retry' }) : 'Retry'}
                </button>
            </div>
        {:else}
            <!-- Filter Bar -->
            <FilterBar
                searchPlaceholder={localeLoaded ? $_('admin.users.searchPlaceholder', { default: 'Search users by name, email, organization...' }) : 'Search users by name, email, organization...'}
                searchValue={usersSearch}
                filters={[
                    {
                        key: 'user_type',
                        label: localeLoaded ? $_('admin.users.filters.type', { default: 'User Type' }) : 'User Type',
                        options: [
                            { value: 'admin', label: localeLoaded ? $_('admin.users.filtersOptions.admin', { default: 'Admin' }) : 'Admin' },
                            { value: 'creator', label: localeLoaded ? $_('admin.users.filtersOptions.creator', { default: 'Creator' }) : 'Creator' },
                            { value: 'end_user', label: localeLoaded ? $_('admin.users.filtersOptions.endUser', { default: 'End User' }) : 'End User' }
                        ]
                    },
                    {
                        key: 'enabled',
                        label: localeLoaded ? $_('admin.users.filters.status', { default: 'Status' }) : 'Status',
                        options: [
                            { value: 'true', label: localeLoaded ? $_('admin.users.filtersOptions.active', { default: 'Active' }) : 'Active' },
                            { value: 'false', label: localeLoaded ? $_('admin.users.filtersOptions.disabled', { default: 'Disabled' }) : 'Disabled' }
                        ]
                    },
                    ...(organizationsForUsers.length > 0 ? [{
                        key: 'organization',
                        label: localeLoaded ? $_('admin.users.table.organization', { default: 'Organization' }) : 'Organization',
                        options: organizationsForUsers.map(org => ({
                            value: String(org.id),
                            label: org.name
                        }))
                    }] : [])
                ]}
                filterValues={{ 
                    user_type: usersFilterType, 
                    enabled: usersFilterEnabled,
                    organization: usersFilterOrg
                }}
                sortOptions={[
                    { value: 'name', label: localeLoaded ? $_('admin.users.sortOptions.name', { default: 'Name' }) : 'Name' },
                    { value: 'email', label: localeLoaded ? $_('admin.users.sortOptions.email', { default: 'Email' }) : 'Email' },
                    { value: 'id', label: localeLoaded ? $_('admin.users.sortOptions.userId', { default: 'User ID' }) : 'User ID' }
                ]}
                sortBy={usersSortBy}
                sortOrder={usersSortOrder}
                on:searchChange={handleUsersSearchChange}
                on:filterChange={handleUsersFilterChange}
                on:sortChange={handleUsersSortChange}
                on:clearFilters={handleUsersClearFilters}
            />
            
            <!-- Results count -->
            <div class="flex justify-between items-center mb-4 px-4">
                <div class="text-sm text-gray-600">
                    {#if usersSearch || usersFilterType || usersFilterEnabled || usersFilterOrg}
                        {localeLoaded ? $_('admin.users.resultsCount.showing', { default: 'Showing {filtered} of {total} users', values: { filtered: usersTotalItems, total: allUsers.length } }) : `Showing ${usersTotalItems} of ${allUsers.length} users`}
                    {:else}
                        {localeLoaded ? $_('admin.users.resultsCount.total', { default: '{count} users', values: { count: usersTotalItems } }) : `${usersTotalItems} users`}
                    {/if}
                </div>
            </div>

            {#if displayUsers.length === 0}
                {#if allUsers.length === 0}
                    <!-- No users at all -->
                    <div class="text-center py-12 bg-white border border-gray-200 rounded-lg">
                        <p class="text-gray-500">{localeLoaded ? $_('admin.users.noUsers', { default: 'No users found.' }) : 'No users found.'}</p>
                    </div>
                {:else}
                    <!-- No results match filters -->
                    <div class="text-center py-12 bg-white border border-gray-200 rounded-lg">
                        <p class="text-gray-500 mb-4">{localeLoaded ? $_('admin.users.resultsCount.noMatch', { default: 'No users match your filters' }) : 'No users match your filters'}</p>
                        <button 
                            onclick={handleUsersClearFilters}
                            class="text-brand hover:text-brand-hover hover:underline focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand rounded-md px-3 py-1"
                        >
                            {localeLoaded ? $_('admin.users.resultsCount.clearFilters', { default: 'Clear filters' }) : 'Clear filters'}
                        </button>
                    </div>
                {/if}
            {:else}
            <!-- Bulk Actions Toolbar -->
            {#if selectedUsers.length > 0}
                <div class="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4 shadow-sm">
                    <div class="flex items-center justify-between">
                        <span class="text-sm font-medium text-gray-700">
                            {selectedUsers.length === 1 
                                ? (localeLoaded ? $_('admin.users.bulkActions.selected', { default: '{count} user selected', values: { count: selectedUsers.length } }) : `${selectedUsers.length} user selected`)
                                : (localeLoaded ? $_('admin.users.bulkActions.selectedPlural', { default: '{count} users selected', values: { count: selectedUsers.length } }) : `${selectedUsers.length} users selected`)
                            }
                        </span>
                        <div class="flex gap-2">
                            <button 
                                class="bg-amber-600 hover:bg-amber-700 text-white py-2 px-4 rounded text-sm font-medium transition-colors"
                                onclick={handleBulkDisable}
                            >
                                {localeLoaded ? $_('admin.users.bulkActions.disableSelected', { default: 'Disable Selected' }) : 'Disable Selected'}
                            </button>
                            <button 
                                class="bg-green-600 hover:bg-green-700 text-white py-2 px-4 rounded text-sm font-medium transition-colors"
                                onclick={handleBulkEnable}
                            >
                                {localeLoaded ? $_('admin.users.bulkActions.enableSelected', { default: 'Enable Selected' }) : 'Enable Selected'}
                            </button>
                            <button 
                                class="bg-gray-500 hover:bg-gray-600 text-white py-2 px-4 rounded text-sm font-medium transition-colors"
                                onclick={clearSelection}
                            >
                                {localeLoaded ? $_('admin.users.bulkActions.clear', { default: 'Clear' }) : 'Clear'}
                            </button>
                        </div>
                    </div>
                </div>
            {/if}

            <!-- Responsive Table Wrapper -->
            <div class="overflow-x-auto shadow-md sm:rounded-lg mb-6 border border-gray-200">
                <table class="min-w-full divide-y divide-gray-200">
                    <thead class="bg-gray-50">
                        <tr>
                            <th scope="col" class="px-6 py-3 text-left">
                                <input 
                                    type="checkbox" 
                                    checked={selectedUsers.length > 0 && selectedUsers.length === users.filter(u => !(currentUserData && currentUserData.email === u.email)).length}
                                    onchange={handleSelectAll}
                                    class="w-5 h-5 text-blue-600 bg-white border-2 border-gray-400 rounded cursor-pointer focus:ring-2 focus:ring-blue-500 checked:bg-blue-600 checked:border-blue-600"
                                    style="accent-color: #2563eb;"
                                    aria-label="Select all users"
                                />
                            </th>
                            <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-brand uppercase tracking-wider">
                                {localeLoaded ? $_('admin.users.table.name', { default: 'Name' }) : 'Name'}
                            </th>
                            <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-brand uppercase tracking-wider">
                                {localeLoaded ? $_('admin.users.table.email', { default: 'Email' }) : 'Email'}
                            </th>
                            <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-brand uppercase tracking-wider hidden md:table-cell">
                                {localeLoaded ? $_('admin.users.table.userType', { default: 'User Type' }) : 'User Type'}
                            </th>
                            <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-brand uppercase tracking-wider hidden lg:table-cell">
                                {localeLoaded ? $_('admin.users.table.organization', { default: 'Organization' }) : 'Organization'}
                            </th>
                            <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-brand uppercase tracking-wider hidden md:table-cell">
                                {localeLoaded ? $_('admin.users.table.status', { default: 'Status' }) : 'Status'}
                            </th>
                            <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-brand uppercase tracking-wider">
                                {localeLoaded ? $_('admin.users.table.actions', { default: 'Actions' }) : 'Actions'}
                            </th>
                        </tr>
                    </thead>
                    <tbody class="bg-white divide-y divide-gray-200">
                        {#each users as user (user.id)}
                            <tr class="hover:bg-gray-50" class:opacity-60={!user.enabled}>
                                <td class="px-6 py-4 whitespace-nowrap align-top">
                                    <input 
                                        type="checkbox" 
                                        bind:checked={user.selected}
                                        disabled={currentUserData && currentUserData.email === user.email}
                                        class="w-5 h-5 text-blue-600 bg-white border-2 border-gray-400 rounded cursor-pointer focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed checked:bg-blue-600 checked:border-blue-600"
                                        style="accent-color: #2563eb;"
                                        aria-label={`Select ${user.name}`}
                                    />
                                </td>
                                <td class="px-6 py-4 whitespace-nowrap align-top">
                                    <div class="text-sm font-medium text-gray-900">{user.name || '-'}</div>
                                </td>
                                <td class="px-6 py-4 whitespace-nowrap align-top">
                                    <div class="text-sm text-gray-800">{user.email}</div>
                                </td>
                                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-800 hidden md:table-cell">
                                    {#if user.role === 'admin'}
                                        <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-red-100 text-red-800">
                                            {localeLoaded ? $_('admin.users.filtersOptions.admin', { default: 'Admin' }) : 'Admin'}
                                        </span>
                                    {:else if user.user_type === 'end_user'}
                                        <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-purple-100 text-purple-800">
                                            {localeLoaded ? $_('admin.users.filtersOptions.endUser', { default: 'End User' }) : 'End User'}
                                        </span>
                                    {:else}
                                        <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800">
                                            {localeLoaded ? $_('admin.users.filtersOptions.creator', { default: 'Creator' }) : 'Creator'}
                                        </span>
                                    {/if}
                                </td>
                                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-800 hidden lg:table-cell">
                                    {#if user.organization}
                                        <div class="flex items-center">
                                            <span class="text-sm font-medium text-gray-900">{user.organization.name || '-'}</span>
                                            {#if user.organization.is_system}
                                                <span class="ml-2 px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-yellow-100 text-yellow-800">
                                                    {localeLoaded ? $_('admin.users.tableValues.system', { default: 'System' }) : 'System'}
                                                </span>
                                            {/if}
                                        </div>
                                        {#if user.organization_role && user.organization_role !== 'member'}
                                            <div class="text-xs text-gray-500">
                                                {user.organization_role}
                                            </div>
                                        {/if}
                                    {:else}
                                        <span class="text-gray-400">{localeLoaded ? $_('admin.users.tableValues.noOrganization', { default: 'No Organization' }) : 'No Organization'}</span>
                                    {/if}
                                </td>
                                <td class="px-6 py-4 whitespace-nowrap text-sm hidden md:table-cell">
                                    <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full {user.enabled ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}">
                                        {user.enabled 
                                            ? (localeLoaded ? $_('admin.users.filtersOptions.active', { default: 'Active' }) : 'Active')
                                            : (localeLoaded ? $_('admin.users.filtersOptions.disabled', { default: 'Disabled' }) : 'Disabled')
                                        }
                                    </span>
                                </td>
                                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium">
                                    <!-- Action buttons - Edit and Delete buttons removed -->
                                    <button 
                                        class="text-amber-600 hover:text-amber-800 mr-3" 
                                        title={localeLoaded ? $_('admin.users.actions.changePassword', { default: 'Change Password' }) : 'Change Password'}
                                        aria-label={localeLoaded ? $_('admin.users.actions.changePassword', { default: 'Change Password' }) : 'Change Password'}
                                        onclick={() => openChangePasswordModal(user.email, user.name)}
                                    >
                                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5">
                                          <path stroke-linecap="round" stroke-linejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25-2.25v6.75a2.25 2.25 0 002.25 2.25z" />
                                        </svg>
                                    </button>
                                    <button
                                        class={currentUserData && currentUserData.email === user.email && user.enabled 
                                            ? "text-gray-400 cursor-not-allowed" 
                                            : "text-blue-600 hover:text-blue-800"}
                                        title={currentUserData && currentUserData.email === user.email && user.enabled 
                                            ? (localeLoaded ? $_('admin.users.actions.cannotDisableSelf', { default: 'You cannot disable your own account' }) : 'You cannot disable your own account')
                                            : (user.enabled 
                                                ? (localeLoaded ? $_('admin.users.actions.disable', { default: 'Disable User' }) : 'Disable User')
                                                : (localeLoaded ? $_('admin.users.actions.enable', { default: 'Enable User' }) : 'Enable User')
                                            )}
                                        aria-label={currentUserData && currentUserData.email === user.email && user.enabled 
                                            ? (localeLoaded ? $_('admin.users.actions.cannotDisableSelf', { default: 'You cannot disable your own account' }) : 'You cannot disable your own account')
                                            : (user.enabled 
                                                ? (localeLoaded ? $_('admin.users.actions.disable', { default: 'Disable User' }) : 'Disable User')
                                                : (localeLoaded ? $_('admin.users.actions.enable', { default: 'Enable User' }) : 'Enable User')
                                            )}
                                        onclick={() => toggleUserStatusAdmin(user)}
                                        disabled={currentUserData && currentUserData.email === user.email && user.enabled}
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
            
            <!-- Pagination -->
            {#if usersTotalPages > 1}
                <Pagination
                    currentPage={usersPage}
                    totalPages={usersTotalPages}
                    totalItems={usersTotalItems}
                    itemsPerPage={usersPerPage}
                    itemsPerPageOptions={[10, 25, 50, 100]}
                    on:pageChange={handleUsersPageChange}
                    on:itemsPerPageChange={handleUsersPerPageChange}
                />
            {/if}
            {/if}
        {/if}
    {:else if currentView === 'organizations'}
        <!-- Organizations Management View -->
        <div class="flex justify-between items-center mb-6">
            <h1 class="text-2xl font-semibold text-gray-800">{localeLoaded ? $_('admin.organizations.title', { default: 'Organization Management' }) : 'Organization Management'}</h1>
            <div class="flex space-x-2">
                <button 
                    onclick={syncSystemOrganization}
                    class="bg-green-600 text-white py-2 px-4 rounded hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-600 focus:ring-opacity-50"
                    aria-label={localeLoaded ? $_('admin.organizations.actions.syncSystem', { default: 'Sync System Organization' }) : 'Sync System Organization'}
                >
                    {localeLoaded ? $_('admin.organizations.actions.syncSystem', { default: 'Sync System' }) : 'Sync System'}
                </button>
                <button
                    onclick={openCreateOrgModal}
                    class="bg-brand text-white py-2 px-4 rounded hover:bg-brand-hover focus:outline-none focus:ring-2 focus:ring-brand focus:ring-opacity-50"
                    aria-label={localeLoaded ? $_('admin.organizations.actions.create', { default: 'Create Organization' }) : 'Create Organization'}
                >
                    {localeLoaded ? $_('admin.organizations.actions.create', { default: 'Create Organization' }) : 'Create Organization'}
                </button>
            </div>
        </div>

        {#if isLoadingOrganizations}
            <p class="text-center text-gray-500 py-4">{localeLoaded ? $_('admin.organizations.loading', { default: 'Loading organizations...' }) : 'Loading organizations...'}</p>
        {:else if organizationsError}
            <div class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative mb-6" role="alert">
                <strong class="font-bold">{localeLoaded ? $_('admin.organizations.errorTitle', { default: 'Error:' }) : 'Error:'}</strong>
                <span class="block sm:inline"> {organizationsError}</span>
            </div>
            <!-- Button to retry fetching -->
            <div class="text-center">
                <button
                    onclick={fetchOrganizations}
                    class="bg-brand text-white py-2 px-4 rounded hover:bg-brand-hover focus:outline-none focus:ring-2 focus:ring-brand focus:ring-opacity-50"
                >
                    {localeLoaded ? $_('admin.organizations.retry', { default: 'Retry' }) : 'Retry'}
                </button>
            </div>
        {:else if organizations.length === 0}
            <p class="text-center text-gray-500 py-4">{localeLoaded ? $_('admin.organizations.noOrganizations', { default: 'No organizations found.' }) : 'No organizations found.'}</p>
        {:else}
            <!-- Responsive Table Wrapper -->
            <div class="overflow-x-auto shadow-md sm:rounded-lg mb-6 border border-gray-200">
                <table class="min-w-full divide-y divide-gray-200">
                    <thead class="bg-gray-50">
                        <tr>
                            <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-brand uppercase tracking-wider">
                                {localeLoaded ? $_('admin.organizations.table.name', { default: 'Name' }) : 'Name'}
                            </th>
                            <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-brand uppercase tracking-wider">
                                {localeLoaded ? $_('admin.organizations.table.slug', { default: 'Slug' }) : 'Slug'}
                            </th>
                            <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-brand uppercase tracking-wider hidden md:table-cell">
                                {localeLoaded ? $_('admin.organizations.table.status', { default: 'Status' }) : 'Status'}
                            </th>
                            <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-brand uppercase tracking-wider hidden lg:table-cell">
                                {localeLoaded ? $_('admin.organizations.table.type', { default: 'Type' }) : 'Type'}
                            </th>
                            <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-brand uppercase tracking-wider">
                                {localeLoaded ? $_('admin.organizations.table.actions', { default: 'Actions' }) : 'Actions'}
                            </th>
                        </tr>
                    </thead>
                    <tbody class="bg-white divide-y divide-gray-200">
                        {#each organizations as org (org.id)}
                            <tr class="hover:bg-gray-50">
                                <td class="px-6 py-4 whitespace-nowrap align-top">
                                    <div class="text-sm font-medium text-gray-900">{org.name || '-'}</div>
                                </td>
                                <td class="px-6 py-4 whitespace-nowrap align-top">
                                    <div class="text-sm text-gray-800 font-mono">{org.slug}</div>
                                </td>
                                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-800 hidden md:table-cell">
                                    <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full {org.status === 'active' ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'}">
                                        {org.status}
                                    </span>
                                </td>
                                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-800 hidden lg:table-cell">
                                    <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full {org.is_system ? 'bg-blue-100 text-blue-800' : 'bg-gray-100 text-gray-800'}">
                                        {org.is_system ? 'System' : 'Regular'}
                                    </span>
                                </td>
                                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium">
                                    <div class="flex space-x-2">
                                        <button 
                                            class="text-green-600 hover:text-green-800" 
                                            title="Administer Organization"
                                            aria-label="Administer Organization"
                                            onclick={() => administerOrganization(org)}
                                        >
                                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5">
                                                <path stroke-linecap="round" stroke-linejoin="round" d="M10.343 3.94c.09-.542.56-.94 1.11-.94h1.093c.55 0 1.02.398 1.11.94l.149.894c.07.424.384.764.78.93.398.164.855.142 1.205-.108l.737-.527a1.125 1.125 0 011.45.12l.773.774c.39.389.44 1.002.12 1.45l-.527.737c-.25.35-.272.806-.107 1.204.165.397.505.71.93.78l.893.15c.543.09.94.56.94 1.109v1.094c0 .55-.397 1.02-.94 1.11l-.893.149c-.425.07-.765.383-.93.78-.165.398-.143.854.107 1.204l.527.738c.32.447.269 1.06-.12 1.45l-.774.773a1.125 1.125 0 01-1.449.12l-.738-.527c-.35-.25-.806-.272-1.203-.107-.397.165-.71.505-.781.929l-.149.894c-.09.542-.56.94-1.11.94h-1.094c-.55 0-1.019-.398-1.11-.94l-.148-.894c-.071-.424-.384-.764-.781-.93-.398-.164-.854-.142-1.204.108l-.738.527c-.447.32-1.06.269-1.45-.12l-.773-.774a1.125 1.125 0 01-.12-1.45l.527-.737c.25-.35.273-.806.108-1.204-.165-.397-.505-.71-.93-.78l-.894-.15c-.542-.09-.94-.56-.94-1.109v-1.094c0-.55.398-1.02.94-1.11l.894-.149c.424-.07.765-.383.93-.78.165-.398.143-.854-.107-1.204l-.527-.738a1.125 1.125 0 01.12-1.45l.773-.773a1.125 1.125 0 011.45-.12l.737.527c.35.25.807.272 1.204.107.397-.165.71-.505.78-.929l.15-.894z" />
                                                <path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                            </svg>
                                        </button>
                                        <button 
                                            class="text-blue-600 hover:text-blue-800" 
                                            title={localeLoaded ? $_('admin.organizations.actions.viewConfig', { default: 'View Configuration' }) : 'View Configuration'}
                                            aria-label={localeLoaded ? $_('admin.organizations.actions.viewConfig', { default: 'View Configuration' }) : 'View Configuration'}
                                            onclick={() => openViewConfigModal(org)}
                                        >
                                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5">
                                                <path stroke-linecap="round" stroke-linejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" />
                                                <path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                            </svg>
                                        </button>
                                        {#if !org.is_system}
                                            <button 
                                                class="text-purple-600 hover:text-purple-800" 
                                                title={localeLoaded ? $_('admin.organizations.actions.migrate', { default: 'Migrate Organization' }) : 'Migrate Organization'}
                                                aria-label={localeLoaded ? $_('admin.organizations.actions.migrate', { default: 'Migrate Organization' }) : 'Migrate Organization'}
                                                onclick={() => openMigrationModal(org)}
                                            >
                                                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5">
                                                    <path stroke-linecap="round" stroke-linejoin="round" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" />
                                                </svg>
                                            </button>
                                            <button 
                                                class="text-red-600 hover:text-red-800" 
                                                title={localeLoaded ? $_('admin.organizations.actions.delete', { default: 'Delete Organization' }) : 'Delete Organization'}
                                                aria-label={localeLoaded ? $_('admin.organizations.actions.delete', { default: 'Delete Organization' }) : 'Delete Organization'}
                                                onclick={() => deleteOrganization(org.slug)}
                                            >
                                                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5">
                                                    <path stroke-linecap="round" stroke-linejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                                                </svg>
                                            </button>
                                        {/if}
                                    </div>
                                </td>
                            </tr>
                        {/each}
                    </tbody>
                </table>
            </div>
        {/if}
    {/if}
</div>

<!-- Change Password Modal -->
{#if isChangePasswordModalOpen}
    <div class="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50 flex items-center justify-center">
        <div class="relative mx-auto p-5 border w-full max-w-md shadow-lg rounded-md bg-white">
            <div class="mt-3 text-center">
                <h3 class="text-lg leading-6 font-medium text-gray-900">
                    {localeLoaded ? $_('admin.users.password.title', { default: 'Change Password' }) : 'Change Password'}
                </h3>
                <p class="text-sm text-gray-500 mt-1">
                    {localeLoaded 
                        ? $_('admin.users.password.subtitle', { default: 'Set a new password for' }) 
                        : 'Set a new password for'} {selectedUserName}
                </p>
                
                {#if changePasswordSuccess}
                    <div class="mt-4 bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded relative" role="alert">
                        <span class="block sm:inline">{localeLoaded ? $_('admin.users.password.success', { default: 'Password changed successfully!' }) : 'Password changed successfully!'}</span>
                    </div>
                {:else}
                    <form class="mt-4" onsubmit={handleChangePassword}>
                        {#if changePasswordError}
                            <div class="mb-4 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative" role="alert">
                                <span class="block sm:inline">{changePasswordError}</span>
                            </div>
                        {/if}
                        
                        <div class="mb-4 text-left">
                            <label for="email" class="block text-gray-700 text-sm font-bold mb-2">
                                {localeLoaded ? $_('admin.users.password.email', { default: 'Email' }) : 'Email'}
                            </label>
                            <input 
                                type="email" 
                                id="email" 
                                class="shadow appearance-none border rounded w-full py-2 px-3 text-gray-500 bg-gray-100 leading-tight" 
                                value={passwordChangeData.email} 
                                disabled
                                readonly
                            />
                        </div>
                        
                        <div class="mb-6 text-left">
                            <label for="new_password" class="block text-gray-700 text-sm font-bold mb-2">
                                {localeLoaded ? $_('admin.users.password.newPassword', { default: 'New Password' }) : 'New Password'} *
                            </label>
                            <input 
                                type="password" 
                                id="new_password" 
                                class="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline" 
                                bind:value={passwordChangeData.new_password} 
                                required 
                                autocomplete="new-password"
                                minlength="8"
                            />
                            <p class="text-gray-500 text-xs italic mt-1">
                                {localeLoaded ? $_('admin.users.password.hint', { default: 'At least 8 characters recommended' }) : 'At least 8 characters recommended'}
                            </p>
                        </div>
                        
                        <div class="flex items-center justify-between">
                            <button 
                                type="button" 
                                onclick={closeChangePasswordModal}
                                class="bg-gray-300 hover:bg-gray-400 text-gray-800 py-2 px-4 rounded focus:outline-none focus:shadow-outline" 
                            >
                                {localeLoaded ? $_('admin.users.password.cancel', { default: 'Cancel' }) : 'Cancel'}
                            </button>
                            <button
                                type="submit"
                                class="bg-brand text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline disabled:opacity-50"
                                disabled={isChangingPassword}
                            >
                                {isChangingPassword 
                                    ? (localeLoaded ? $_('admin.users.password.changing', { default: 'Changing...' }) : 'Changing...') 
                                    : (localeLoaded ? $_('admin.users.password.change', { default: 'Change Password' }) : 'Change Password')}
                            </button>
                        </div>
                    </form>
                {/if}
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
                    {localeLoaded ? $_('admin.users.create.title', { default: 'Create New User' }) : 'Create New User'}
                </h3>
                
                {#if createUserSuccess}
                    <div class="mt-4 bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded relative" role="alert">
                        <span class="block sm:inline">{localeLoaded ? $_('admin.users.create.success', { default: 'User created successfully!' }) : 'User created successfully!'}</span>
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
                                {localeLoaded ? $_('admin.users.create.email', { default: 'Email' }) : 'Email'} *
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
                                {localeLoaded ? $_('admin.users.create.name', { default: 'Name' }) : 'Name'} *
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
                                {localeLoaded ? $_('admin.users.create.password', { default: 'Password' }) : 'Password'} *
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
                            <label for="role" class="block text-gray-700 text-sm font-bold mb-2">
                                {localeLoaded ? $_('admin.users.create.role', { default: 'Role' }) : 'Role'}
                            </label>
                            <select 
                                id="role" 
                                class="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline" 
                                bind:value={newUser.role}
                                onchange={(e) => {
                                    // If admin is selected, automatically set user_type to 'creator'
                                    const target = /** @type {HTMLSelectElement} */ (e.target);
                                    if (target.value === 'admin') {
                                        newUser.user_type = 'creator';
                                    }
                                }}
                            >
                                <option value="user">{localeLoaded ? $_('admin.users.create.roleUser', { default: 'User' }) : 'User'}</option>
                                <option value="admin">{localeLoaded ? $_('admin.users.create.roleAdmin', { default: 'Admin' }) : 'Admin'}</option>
                            </select>
                        </div>

                        <div class="mb-4 text-left">
                            <label for="user_type" class="block text-gray-700 text-sm font-bold mb-2">
                                User Type
                            </label>
                            <select 
                                id="user_type" 
                                class="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline" 
                                bind:value={newUser.user_type}
                                disabled={newUser.role === 'admin'}
                            >
                                <option value="creator">Creator (Can create assistants)</option>
                                <option value="end_user">End User (Redirects to Open WebUI)</option>
                            </select>
                            {#if newUser.role === 'admin'}
                                <p class="text-xs text-gray-500 mt-1">Admin users are automatically creators</p>
                            {/if}
                        </div>

                        <div class="mb-6 text-left">
                            <label for="organization" class="block text-gray-700 text-sm font-bold mb-2">
                                Organization
                            </label>
                            {#if isLoadingOrganizationsForUsers}
                                <div class="text-gray-500 text-sm">Loading organizations...</div>
                            {:else if organizationsForUsersError}
                                <div class="text-red-500 text-sm">{organizationsForUsersError}</div>
                            {:else}
                                <select 
                                    id="organization" 
                                    class="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline" 
                                    bind:value={newUser.organization_id}
                                >
                                    <option value={null}>Select an organization (optional)</option>
                                    {#each organizationsForUsers as org}
                                        <option value={org.id}>
                                            {org.name}
                                            {#if org.is_system}
                                                (System)
                                            {/if}
                                        </option>
                                    {/each}
                                </select>
                            {/if}
                            <p class="text-gray-500 text-xs italic mt-1">
                                If no organization is selected, the user will be assigned to the system organization by default.
                            </p>
                        </div>
                        
                        <div class="flex items-center justify-between">
                            <button 
                                type="button" 
                                onclick={closeCreateUserModal}
                                class="bg-gray-300 hover:bg-gray-400 text-gray-800 py-2 px-4 rounded focus:outline-none focus:shadow-outline" 
                            >
                                {localeLoaded ? $_('admin.users.create.cancel', { default: 'Cancel' }) : 'Cancel'}
                            </button>
                            <button 
                                type="submit" 
                                class="bg-brand text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline disabled:opacity-50"
                                disabled={isCreatingUser}
                            >
                                {isCreatingUser 
                                    ? (localeLoaded ? $_('admin.users.create.creating', { default: 'Creating...' }) : 'Creating...') 
                                    : (localeLoaded ? $_('admin.users.create.create', { default: 'Create User' }) : 'Create User')}
                            </button>
                        </div>
                    </form>
                {/if}
            </div>
        </div>
    </div>
{/if}

<!-- Create Organization Modal -->
{#if isCreateOrgModalOpen}
    <div class="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50 flex items-center justify-center">
        <div class="relative mx-auto p-5 border w-full max-w-2xl shadow-lg rounded-md bg-white">
            <div class="mt-3">
                <h3 class="text-lg leading-6 font-medium text-gray-900 text-center">
                    {localeLoaded ? $_('admin.organizations.create.title', { default: 'Create New Organization' }) : 'Create New Organization'}
                </h3>
                
                {#if createOrgSuccess}
                    <div class="mt-4 bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded relative" role="alert">
                        <span class="block sm:inline">{localeLoaded ? $_('admin.organizations.create.success', { default: 'Organization created successfully!' }) : 'Organization created successfully!'}</span>
                    </div>
                {:else}
                    <form class="mt-4" onsubmit={handleCreateOrganization}>
                        {#if createOrgError}
                            <div class="mb-4 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative" role="alert">
                                <span class="block sm:inline">{createOrgError}</span>
                            </div>
                        {/if}
                        
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                            <div class="text-left">
                                <label for="org_slug" class="block text-gray-700 text-sm font-bold mb-2">
                                    {localeLoaded ? $_('admin.organizations.create.slug', { default: 'Slug' }) : 'Slug'} *
                                </label>
                                <input 
                                    type="text" 
                                    id="org_slug" 
                                    class="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline" 
                                    bind:value={newOrg.slug} 
                                    required 
                                    pattern="[a-z0-9-]+"
                                    title="Only lowercase letters, numbers, and hyphens allowed"
                                />
                                <p class="text-gray-500 text-xs italic mt-1">
                                    URL-friendly identifier (lowercase, numbers, hyphens only)
                                </p>
                            </div>
                            
                            <div class="text-left">
                                <label for="org_name" class="block text-gray-700 text-sm font-bold mb-2">
                                    {localeLoaded ? $_('admin.organizations.create.name', { default: 'Name' }) : 'Name'} *
                                </label>
                                <input 
                                    type="text" 
                                    id="org_name" 
                                    class="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline" 
                                    bind:value={newOrg.name} 
                                    required 
                                />
                            </div>
                        </div>

                        <!-- Admin User Selection -->
                        <div class="mb-4 text-left">
                            <label for="admin_user" class="block text-gray-700 text-sm font-bold mb-2">
                                Organization Admin *
                            </label>
                            {#if isLoadingSystemUsers}
                                <div class="text-gray-500 text-sm">Loading system users...</div>
                            {:else if systemUsersError}
                                <div class="text-red-500 text-sm">{systemUsersError}</div>
                            {:else}
                                <select 
                                    id="admin_user"
                                    class="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline"
                                    bind:value={newOrg.admin_user_id}
                                    required
                                >
                                    <option value={null}>Select a user from system organization...</option>
                                    {#each systemOrgUsers.filter(user => user.role !== 'admin') as user}
                                        <option value={user.id}>{user.name} ({user.email}) - {user.role}</option>
                                    {/each}
                                </select>
                            {/if}
                            <p class="text-gray-500 text-xs italic mt-1">
                                Select a user from the system organization to become admin of this organization. 
                                <strong>Note:</strong> System admins are not eligible as they must remain in the system organization.
                            </p>
                        </div>

                        <!-- Signup Configuration -->
                        <div class="mb-4 text-left">
                            <label for="signup_config_section" class="block text-gray-700 text-sm font-bold mb-2">
                                Signup Configuration
                            </label>
                            <div id="signup_config_section" class="mb-3">
                                <label class="flex items-center">
                                    <input type="checkbox" bind:checked={newOrg.signup_enabled} class="mr-2">
                                    <span class="text-sm">Enable organization-specific signup</span>
                                </label>
                            </div>
                            
                            {#if newOrg.signup_enabled}
                                <div>
                                    <label for="signup_key" class="block text-gray-600 text-sm mb-1">Signup Key *</label>
                                    <input 
                                        type="text" 
                                        id="signup_key"
                                        class="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline" 
                                        bind:value={newOrg.signup_key} 
                                        required={newOrg.signup_enabled}
                                        pattern="[a-zA-Z0-9_-]+"
                                        title="Only letters, numbers, hyphens, and underscores allowed"
                                        minlength="8"
                                        maxlength="64"
                                    />
                                    <p class="text-gray-500 text-xs italic mt-1">
                                        Unique key for users to signup to this organization (8-64 characters)
                                    </p>
                                </div>
                            {/if}
                        </div>

                        <!-- System Baseline Option -->
                        <div class="mb-4 text-left">
                            <label class="flex items-center">
                                <input type="checkbox" bind:checked={newOrg.use_system_baseline} class="mr-2">
                                <span class="text-sm">Copy system organization configuration as baseline</span>
                            </label>
                            <p class="text-gray-500 text-xs italic mt-1">
                                Inherit providers and settings from the system organization
                            </p>
                        </div>

                        <div class="mb-4 text-left">
                            <label for="org_features" class="block text-gray-700 text-sm font-bold mb-2">
                                {localeLoaded ? $_('admin.organizations.create.features', { default: 'Features' }) : 'Features'}
                            </label>
                            <div class="grid grid-cols-2 gap-2">
                                <label class="flex items-center">
                                    <input type="checkbox" bind:checked={newOrg.config.features.rag_enabled} class="mr-2">
                                    <span class="text-sm">RAG Enabled</span>
                                </label>
                                <label class="flex items-center">
                                    <input type="checkbox" bind:checked={newOrg.config.features.lti_publishing} class="mr-2">
                                    <span class="text-sm">LTI Publishing</span>
                                </label>
                                <label class="flex items-center">
                                    <input type="checkbox" bind:checked={newOrg.config.features.signup_enabled} class="mr-2">
                                    <span class="text-sm">Signup Enabled</span>
                                </label>
                            </div>
                        </div>

                        <div class="mb-4 text-left" style="display: none;">
                            <label for="org_limits" class="block text-gray-700 text-sm font-bold mb-2">
                                {localeLoaded ? $_('admin.organizations.create.limits', { default: 'Usage Limits' }) : 'Usage Limits'}
                            </label>
                            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                                <div>
                                    <label for="tokens_per_month" class="block text-gray-600 text-xs mb-1">Tokens/Month</label>
                                    <input 
                                        type="number" 
                                        id="tokens_per_month"
                                        class="shadow appearance-none border rounded w-full py-1 px-2 text-gray-700 text-sm leading-tight focus:outline-none focus:shadow-outline" 
                                        bind:value={newOrg.config.limits.usage.tokens_per_month}
                                        min="0"
                                    />
                                </div>
                                <div>
                                    <label for="max_assistants" class="block text-gray-600 text-xs mb-1">Max Assistants</label>
                                    <input 
                                        type="number" 
                                        id="max_assistants"
                                        class="shadow appearance-none border rounded w-full py-1 px-2 text-gray-700 text-sm leading-tight focus:outline-none focus:shadow-outline" 
                                        bind:value={newOrg.config.limits.usage.max_assistants}
                                        min="1"
                                    />
                                </div>
                                <div>
                                    <label for="storage_gb" class="block text-gray-600 text-xs mb-1">Storage (GB)</label>
                                    <input 
                                        type="number" 
                                        id="storage_gb"
                                        class="shadow appearance-none border rounded w-full py-1 px-2 text-gray-700 text-sm leading-tight focus:outline-none focus:shadow-outline" 
                                        bind:value={newOrg.config.limits.usage.storage_gb}
                                        min="0"
                                        step="0.1"
                                    />
                                </div>
                            </div>
                        </div>
                        
                        <div class="flex items-center justify-between">
                            <button 
                                type="button" 
                                onclick={closeCreateOrgModal}
                                class="bg-gray-300 hover:bg-gray-400 text-gray-800 py-2 px-4 rounded focus:outline-none focus:shadow-outline" 
                            >
                                {localeLoaded ? $_('admin.organizations.create.cancel', { default: 'Cancel' }) : 'Cancel'}
                            </button>
                            <button 
                                type="submit" 
                                class="bg-brand text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline disabled:opacity-50"
                                disabled={isCreatingOrg}
                            >
                                {isCreatingOrg 
                                    ? (localeLoaded ? $_('admin.organizations.create.creating', { default: 'Creating...' }) : 'Creating...') 
                                    : (localeLoaded ? $_('admin.organizations.create.create', { default: 'Create Organization' }) : 'Create Organization')}
                            </button>
                        </div>
                    </form>
                {/if}
            </div>
        </div>
    </div>
{/if}

<!-- View Configuration Modal -->
{#if isViewConfigModalOpen && selectedOrg}
    <div class="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50 flex items-center justify-center">
        <div class="relative mx-auto p-5 border w-full max-w-4xl shadow-lg rounded-md bg-white max-h-[90vh] overflow-y-auto">
            <div class="mt-3">
                <div class="flex justify-between items-center mb-4">
                    <h3 class="text-lg leading-6 font-medium text-gray-900">
                        Configuration: {selectedOrg.name} ({selectedOrg.slug})
                    </h3>
                    <button 
                        onclick={closeViewConfigModal}
                        class="text-gray-400 hover:text-gray-600"
                        aria-label="Close"
                    >
                        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                        </svg>
                    </button>
                </div>

                {#if isLoadingOrgConfig}
                    <div class="text-center py-8">
                        <p class="text-gray-500">Loading configuration...</p>
                    </div>
                {:else if configError}
                    <div class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative" role="alert">
                        <strong class="font-bold">Error:</strong>
                        <span class="block sm:inline"> {configError}</span>
                    </div>
                {:else if selectedOrgConfig}
                    <div class="bg-gray-50 rounded-lg p-4">
                        <h4 class="text-sm font-medium text-gray-700 mb-2">Configuration JSON:</h4>
                        <pre class="bg-white p-4 rounded border text-xs overflow-x-auto"><code>{JSON.stringify(selectedOrgConfig, null, 2)}</code></pre>
                        
                        {#if selectedOrgConfig.setups}
                            <div class="mt-6">
                                <h4 class="text-sm font-medium text-gray-700 mb-2">Setups Summary:</h4>
                                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    {#each Object.entries(selectedOrgConfig.setups) as [setupName, setup]}
                                        <div class="bg-white p-3 rounded border">
                                            <h5 class="font-medium text-sm text-gray-800">{setup.name || setupName}</h5>
                                            <p class="text-xs text-gray-600 mb-1">
                                                {setup.is_default ? '(Default)' : ''}
                                            </p>
                                            {#if setup.providers}
                                                <div class="text-xs">
                                                    <strong>Providers:</strong> {Object.keys(setup.providers).join(', ') || 'None'}
                                                </div>
                                            {/if}
                                        </div>
                                    {/each}
                                </div>
                            </div>
                        {/if}

                        {#if selectedOrgConfig.features}
                            <div class="mt-4">
                                <h4 class="text-sm font-medium text-gray-700 mb-2">Features:</h4>
                                <div class="grid grid-cols-2 md:grid-cols-4 gap-2">
                                    {#each Object.entries(selectedOrgConfig.features) as [feature, enabled]}
                                        <div class="flex items-center text-xs">
                                            <span class="w-2 h-2 rounded-full mr-2 {enabled ? 'bg-green-500' : 'bg-gray-300'}"></span>
                                            <span class="capitalize">{feature.replace('_', ' ')}</span>
                                        </div>
                                    {/each}
                                </div>
                            </div>
                        {/if}

                        {#if selectedOrgConfig.limits && selectedOrgConfig.limits.usage}
                            <div class="mt-4">
                                <h4 class="text-sm font-medium text-gray-700 mb-2">Usage Limits:</h4>
                                <div class="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
                                    <div>
                                        <strong>Tokens/Month:</strong> {selectedOrgConfig.limits.usage.tokens_per_month?.toLocaleString() || 'Unlimited'}
                                    </div>
                                    <div>
                                        <strong>Max Assistants:</strong> {selectedOrgConfig.limits.usage.max_assistants || 'Unlimited'}
                                    </div>
                                    <div>
                                        <strong>Storage:</strong> {selectedOrgConfig.limits.usage.storage_gb || 'Unlimited'} GB
                                    </div>
                                </div>
                            </div>
                        {/if}
                    </div>
                {/if}
                
                <div class="mt-6 text-center">
                    <button 
                        onclick={closeViewConfigModal}
                        class="bg-gray-300 hover:bg-gray-400 text-gray-800 py-2 px-4 rounded focus:outline-none focus:shadow-outline"
                    >
                        Close
                    </button>
                </div>
            </div>
        </div>
    </div>
{/if}

<!-- Disable User Confirmation Modal -->
{#if showDisableConfirm}
    <div class="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50 flex items-center justify-center">
        <div class="relative mx-auto p-5 border w-full max-w-md shadow-lg rounded-md bg-white">
            <div class="mt-3">
                <div class="flex items-center mb-4">
                    <svg class="w-6 h-6 text-amber-600 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
                    </svg>
                    <h3 class="text-lg font-medium text-gray-900">Confirm Disable</h3>
                </div>
                <div class="mt-2 px-7 py-3">
                    <p class="text-sm text-gray-700">
                        {#if actionType === 'single'}
                            Are you sure you want to disable <strong>{targetUser?.name}</strong> ({targetUser?.email})?
                        {:else}
                            Are you sure you want to disable <strong>{selectedUsers.length}</strong> user(s)?
                        {/if}
                    </p>
                    <p class="text-sm text-gray-600 mt-3">
                        Disabled users will not be able to login, but their published assistants and shared resources will remain available.
                    </p>
                </div>
                <div class="flex items-center justify-end gap-3 px-4 py-3">
                    <button 
                        onclick={() => showDisableConfirm = false}
                        class="bg-gray-300 hover:bg-gray-400 text-gray-800 py-2 px-4 rounded focus:outline-none focus:shadow-outline"
                    >
                        Cancel
                    </button>
                    <button 
                        onclick={confirmDisable}
                        class="bg-amber-600 hover:bg-amber-700 text-white py-2 px-4 rounded focus:outline-none focus:shadow-outline"
                    >
                        Disable
                    </button>
                </div>
            </div>
        </div>
    </div>
{/if}

<!-- Enable User Confirmation Modal -->
{#if showEnableConfirm}
    <div class="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50 flex items-center justify-center">
        <div class="relative mx-auto p-5 border w-full max-w-md shadow-lg rounded-md bg-white">
            <div class="mt-3">
                <div class="flex items-center mb-4">
                    <svg class="w-6 h-6 text-green-600 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                    </svg>
                    <h3 class="text-lg font-medium text-gray-900">Confirm Enable</h3>
                </div>
                <div class="mt-2 px-7 py-3">
                    <p class="text-sm text-gray-700">
                        {#if actionType === 'single'}
                            Are you sure you want to enable <strong>{targetUser?.name}</strong> ({targetUser?.email})?
                        {:else}
                            Are you sure you want to enable <strong>{selectedUsers.length}</strong> user(s)?
                        {/if}
                    </p>
                    <p class="text-sm text-gray-600 mt-3">
                        Enabled users will be able to login and access the system.
                    </p>
                </div>
                <div class="flex items-center justify-end gap-3 px-4 py-3">
                    <button 
                        onclick={() => showEnableConfirm = false}
                        class="bg-gray-300 hover:bg-gray-400 text-gray-800 py-2 px-4 rounded focus:outline-none focus:shadow-outline"
                    >
                        Cancel
                    </button>
                    <button 
                        onclick={confirmEnable}
                        class="bg-green-600 hover:bg-green-700 text-white py-2 px-4 rounded focus:outline-none focus:shadow-outline"
                    >
                        Enable
                    </button>
                </div>
            </div>
        </div>
    </div>
{/if}

<!-- Organization Migration Modal -->
{#if isMigrationModalOpen && migrationSourceOrg}
    <div class="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50 flex items-center justify-center">
        <div class="relative mx-auto p-5 border w-full max-w-2xl shadow-lg rounded-md bg-white max-h-[90vh] overflow-y-auto">
            <div class="mt-3">
                <div class="flex justify-between items-center mb-4">
                    <h3 class="text-lg leading-6 font-medium text-gray-900">
                        {localeLoaded ? $_('admin.organizations.migration.title', { default: 'Migrate Organization' }) : 'Migrate Organization'}
                    </h3>
                    <button 
                        onclick={closeMigrationModal}
                        class="text-gray-400 hover:text-gray-600"
                        aria-label="Close"
                    >
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-6 h-6">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>
                
                <p class="text-sm text-gray-600 mb-4">
                    {localeLoaded 
                        ? $_('admin.organizations.migration.description', { default: 'Migrate all resources from' }) 
                        : 'Migrate all resources from'} <strong>{migrationSourceOrg.name}</strong> to another organization.
                </p>

                {#if migrationSuccess && migrationReport}
                    <!-- Success State -->
                    <div class="bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded relative mb-4" role="alert">
                        <strong class="font-bold">{localeLoaded ? $_('admin.organizations.migration.success', { default: 'Migration completed successfully!' }) : 'Migration completed successfully!'}</strong>
                        <div class="mt-2 text-sm">
                            <p><strong>Resources migrated:</strong></p>
                            <ul class="list-disc list-inside mt-1">
                                <li>{migrationReport.resources_migrated?.users || 0} users</li>
                                <li>{migrationReport.resources_migrated?.assistants || 0} assistants</li>
                                <li>{migrationReport.resources_migrated?.templates || 0} templates</li>
                                <li>{migrationReport.resources_migrated?.kbs || 0} knowledge bases</li>
                            </ul>
                            {#if migrationReport.warnings && migrationReport.warnings.length > 0}
                                <div class="mt-2">
                                    <p class="font-semibold">Warnings:</p>
                                    <ul class="list-disc list-inside">
                                        {#each migrationReport.warnings as warning}
                                            <li>{warning}</li>
                                        {/each}
                                    </ul>
                                </div>
                            {/if}
                        </div>
                    </div>
                {:else}
                    <!-- Migration Form -->
                    <div class="space-y-4">
                        <!-- Step 1: Target Organization Selection -->
                        <div>
                            <label for="target_org_slug" class="block text-sm font-medium text-gray-700 mb-2">
                                {localeLoaded ? $_('admin.organizations.migration.targetOrg', { default: 'Target Organization' }) : 'Target Organization'} *
                            </label>
                            <select
                                id="target_org_slug"
                                bind:value={migrationTargetOrgSlug}
                                class="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline"
                                disabled={isValidatingMigration || isMigrating}
                            >
                                <option value="">{localeLoaded ? $_('admin.organizations.migration.selectTarget', { default: 'Select target organization...' }) : 'Select target organization...'}</option>
                                {#each organizations.filter(o => !o.is_system && o.slug !== migrationSourceOrg.slug) as org}
                                    <option value={org.slug}>{org.name} ({org.slug})</option>
                                {/each}
                            </select>
                            <button
                                type="button"
                                onclick={validateMigration}
                                disabled={!migrationTargetOrgSlug || isValidatingMigration || isMigrating}
                                class="mt-2 bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                {isValidatingMigration 
                                    ? (localeLoaded ? $_('admin.organizations.migration.validating', { default: 'Validating...' }) : 'Validating...') 
                                    : (localeLoaded ? $_('admin.organizations.migration.validate', { default: 'Validate Migration' }) : 'Validate Migration')}
                            </button>
                        </div>

                        <!-- Validation Results -->
                        {#if migrationValidationError}
                            <div class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative" role="alert">
                                <span class="block sm:inline">{migrationValidationError}</span>
                            </div>
                        {/if}

                        {#if migrationValidationResult && migrationValidationResult.can_migrate}
                            <!-- Step 2: Validation Results Display -->
                            <div class="bg-blue-50 border border-blue-200 rounded p-4">
                                <h4 class="font-semibold text-gray-800 mb-2">
                                    {localeLoaded ? $_('admin.organizations.migration.resources', { default: 'Resources to Migrate' }) : 'Resources to Migrate'}
                                </h4>
                                <ul class="text-sm text-gray-700 space-y-1">
                                    <li>• {migrationValidationResult.resources?.users || 0} users</li>
                                    <li>• {migrationValidationResult.resources?.assistants || 0} assistants</li>
                                    <li>• {migrationValidationResult.resources?.templates || 0} templates</li>
                                    <li>• {migrationValidationResult.resources?.kbs || 0} knowledge bases</li>
                                    <li>• {migrationValidationResult.resources?.usage_logs || 0} usage logs</li>
                                </ul>

                                {#if migrationValidationResult.conflicts.assistants.length > 0 || migrationValidationResult.conflicts.templates.length > 0}
                                    <div class="mt-3 pt-3 border-t border-blue-300">
                                        <h5 class="font-semibold text-orange-700 mb-2">
                                            {localeLoaded ? $_('admin.organizations.migration.conflicts', { default: 'Conflicts Detected' }) : 'Conflicts Detected'}
                                        </h5>
                                        {#if migrationValidationResult.conflicts.assistants.length > 0}
                                            <p class="text-sm text-gray-700 mb-1">
                                                {migrationValidationResult.conflicts.assistants.length} assistant(s) will be renamed:
                                            </p>
                                            <ul class="text-xs text-gray-600 list-disc list-inside ml-2">
                                                {#each migrationValidationResult.conflicts.assistants.slice(0, 3) as conflict}
                                                    <li>{conflict.name} (by {conflict.owner})</li>
                                                {/each}
                                                {#if migrationValidationResult.conflicts.assistants.length > 3}
                                                    <li>... and {migrationValidationResult.conflicts.assistants.length - 3} more</li>
                                                {/if}
                                            </ul>
                                        {/if}
                                        {#if migrationValidationResult.conflicts.templates.length > 0}
                                            <p class="text-sm text-gray-700 mb-1 mt-2">
                                                {migrationValidationResult.conflicts.templates.length} template(s) will be renamed:
                                            </p>
                                            <ul class="text-xs text-gray-600 list-disc list-inside ml-2">
                                                {#each migrationValidationResult.conflicts.templates.slice(0, 3) as conflict}
                                                    <li>{conflict.name} (by {conflict.owner_email})</li>
                                                {/each}
                                                {#if migrationValidationResult.conflicts.templates.length > 3}
                                                    <li>... and {migrationValidationResult.conflicts.templates.length - 3} more</li>
                                                {/if}
                                            </ul>
                                        {/if}
                                    </div>
                                {/if}
                            </div>

                            <!-- Step 3: Migration Options -->
                            <div class="space-y-4 border-t pt-4">
                                <h4 class="font-semibold text-gray-800">
                                    {localeLoaded ? $_('admin.organizations.migration.options', { default: 'Migration Options' }) : 'Migration Options'}
                                </h4>

                                <!-- Conflict Strategy -->
                                <div>
                                    <label for="migration-conflict-strategy" class="block text-sm font-medium text-gray-700 mb-2">
                                        {localeLoaded ? $_('admin.organizations.migration.conflictStrategy', { default: 'Conflict Resolution Strategy' }) : 'Conflict Resolution Strategy'}
                                    </label>
                                    <select
                                        id="migration-conflict-strategy"
                                        bind:value={migrationConflictStrategy}
                                        disabled={isMigrating}
                                        class="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline"
                                    >
                                        <option value="rename">{localeLoaded ? $_('admin.organizations.migration.rename', { default: 'Rename conflicting resources' }) : 'Rename conflicting resources'}</option>
                                        <option value="skip">{localeLoaded ? $_('admin.organizations.migration.skip', { default: 'Skip conflicting resources' }) : 'Skip conflicting resources'}</option>
                                        <option value="fail">{localeLoaded ? $_('admin.organizations.migration.fail', { default: 'Fail on conflicts' }) : 'Fail on conflicts'}</option>
                                    </select>
                                </div>

                                <!-- Preserve Admin Roles - CRITICAL -->
                                <div class="flex items-start">
                                    <input
                                        type="checkbox"
                                        id="preserve_admin_roles"
                                        bind:checked={migrationPreserveAdminRoles}
                                        disabled={isMigrating}
                                        class="mt-1 mr-3 h-4 w-4 text-brand focus:ring-brand border-gray-300 rounded"
                                    />
                                    <div class="flex-1">
                                        <label for="preserve_admin_roles" class="block text-sm font-medium text-gray-700 cursor-pointer">
                                            {localeLoaded ? $_('admin.organizations.migration.preserveAdminRoles', { default: 'Preserve admin roles from source organization' }) : 'Preserve admin roles from source organization'}
                                        </label>
                                        <p class="text-xs text-gray-500 mt-1">
                                            {localeLoaded 
                                                ? $_('admin.organizations.migration.preserveAdminRolesHint', { default: 'If unchecked, admins from the source organization will be migrated as regular members. If checked, they will keep their admin privileges in the target organization.' }) 
                                                : 'If unchecked, admins from the source organization will be migrated as regular members. If checked, they will keep their admin privileges in the target organization.'}
                                        </p>
                                    </div>
                                </div>

                                <!-- Delete Source Organization -->
                                <div class="flex items-start">
                                    <input
                                        type="checkbox"
                                        id="delete_source"
                                        bind:checked={migrationDeleteSource}
                                        disabled={isMigrating}
                                        class="mt-1 mr-3 h-4 w-4 text-brand focus:ring-brand border-gray-300 rounded"
                                    />
                                    <div class="flex-1">
                                        <label for="delete_source" class="block text-sm font-medium text-gray-700 cursor-pointer">
                                            {localeLoaded ? $_('admin.organizations.migration.deleteSource', { default: 'Delete source organization after migration' }) : 'Delete source organization after migration'}
                                        </label>
                                        <p class="text-xs text-gray-500 mt-1">
                                            {localeLoaded 
                                                ? $_('admin.organizations.migration.deleteSourceHint', { default: 'If checked, the source organization will be permanently deleted after successful migration. This action cannot be undone.' }) 
                                                : 'If checked, the source organization will be permanently deleted after successful migration. This action cannot be undone.'}
                                        </p>
                                    </div>
                                </div>
                            </div>

                            <!-- Migration Error -->
                            {#if migrationError}
                                <div class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative" role="alert">
                                    <span class="block sm:inline">{migrationError}</span>
                                </div>
                            {/if}

                            <!-- Action Buttons -->
                            <div class="flex items-center justify-end gap-3 mt-6 pt-4 border-t">
                                <button 
                                    type="button"
                                    onclick={closeMigrationModal}
                                    disabled={isMigrating}
                                    class="bg-gray-300 hover:bg-gray-400 text-gray-800 py-2 px-4 rounded focus:outline-none focus:shadow-outline disabled:opacity-50"
                                >
                                    {localeLoaded ? $_('admin.organizations.migration.cancel', { default: 'Cancel' }) : 'Cancel'}
                                </button>
                                <button 
                                    type="button"
                                    onclick={executeMigration}
                                    disabled={isMigrating || !migrationValidationResult?.can_migrate}
                                    class="bg-purple-600 hover:bg-purple-700 text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                    {isMigrating 
                                        ? (localeLoaded ? $_('admin.organizations.migration.migrating', { default: 'Migrating...' }) : 'Migrating...') 
                                        : (localeLoaded ? $_('admin.organizations.migration.execute', { default: 'Execute Migration' }) : 'Execute Migration')}
                                </button>
                            </div>
                        {/if}
                    </div>
                {/if}
            </div>
        </div>
    </div>
{/if}

<style>
    /* Add specific styles if needed, though Tailwind should cover most */
</style> 