<script>
    import { onMount, onDestroy } from 'svelte';
    import { browser } from '$app/environment';
    import { page } from '$app/stores'; // Import page store to read URL params
    import { goto } from '$app/navigation';
    import { base } from '$app/paths';
    import { _ } from '$lib/i18n'; // Assuming i18n setup
    import axios from 'axios';
    import { getApiUrl, getConfig } from '$lib/config';
    import { user } from '$lib/stores/userStore'; // Import user store for auth token
    import * as adminService from '$lib/services/adminService'; // Import admin service for bulk operations
    import ConfirmationModal from '$lib/components/modals/ConfirmationModal.svelte';
    
    // Import filtering/pagination components
    import Pagination from '$lib/components/common/Pagination.svelte';
    import FilterBar from '$lib/components/common/FilterBar.svelte';
    import { processListData } from '$lib/utils/listHelpers';
    
    // Import admin components
    import AdminDashboard from '$lib/components/admin/AdminDashboard.svelte';
    import UserDashboard from '$lib/components/UserDashboard.svelte';
    import UserForm from '$lib/components/admin/shared/UserForm.svelte';
    import ChangePasswordModal from '$lib/components/admin/shared/ChangePasswordModal.svelte';
    import UserActionModal from '$lib/components/admin/shared/UserActionModal.svelte';
    import OrgForm from '$lib/components/admin/OrgForm.svelte';

    // --- State Management ---
    /** @type {'dashboard' | 'users' | 'organizations' | 'lti-settings' | 'user-detail'} */
    let currentView = $state('dashboard'); // Default view is dashboard
    let localeLoaded = $state(true); // Assume loaded for now
    
    // Current user data for self-disable prevention
    /** @type {any} */
    let currentUserData = $state(null);

    // --- User Detail State ---
    /** @type {any} */
    let userDetailProfile = $state(null);
    let isLoadingUserDetail = $state(false);
    /** @type {string | null} */
    let userDetailError = $state(null);
    /** @type {number | null} */
    let userDetailId = $state(null);

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

    // --- Dashboard System Stats State ---
    /** @type {any | null} */
    let systemStats = $state(null);
    let isLoadingStats = $state(false);
    /** @type {string | null} */
    let statsError = $state(null);

    // --- Organizations Management State ---
    /** @type {Array<any>} */
    let organizations = $state([]);
    let isLoadingOrganizations = $state(false);
    /** @type {string | null} */
    let organizationsError = $state(null);
    
    // Delete organization modal state
    let showDeleteOrgModal = $state(false);
    /** @type {string | null} */
    let orgToDelete = $state(null);
    let isDeletingOrg = $state(false);

    // --- Create Organization Modal State ---
    // Note: Form state is now managed by OrgForm component
    let isCreateOrgModalOpen = $state(false);

    // --- View Organization Config Modal State ---
    let isViewConfigModalOpen = $state(false);
    /** @type {any | null} */
    let selectedOrg = $state(null);
    /** @type {any | null} */
    let selectedOrgConfig = $state(null);
    let isLoadingOrgConfig = $state(false);
    /** @type {string | null} */
    let configError = $state(null);

    // --- Organization Members Modal State ---
    let isMembersModalOpen = $state(false);
    /** @type {any | null} */
    let membersModalOrg = $state(null);
    /** @type {Array<any>} */
    let orgMembers = $state([]);
    let isLoadingMembers = $state(false);
    /** @type {string | null} */
    let membersError = $state(null);
    let isUpdatingRole = $state(false);
    /** @type {string | null} */
    let roleUpdateSuccess = $state(null);

    // --- Global LTI Settings State ---
    let ltiGlobalConfig = $state({ oauth_consumer_key: '', oauth_consumer_secret_masked: '', updated_at: null, source: 'environment' });
    let ltiGlobalForm = $state({ consumer_key: '', consumer_secret: '' });
    let isLoadingLtiGlobal = $state(false);
    let ltiGlobalError = $state(null);
    let ltiGlobalSuccess = $state(null);
    let showLtiSecret = $state(false);
    let ltiHasSecret = $derived(ltiGlobalConfig.oauth_consumer_secret_masked && ltiGlobalConfig.oauth_consumer_secret_masked !== '(not set)');
    let ltiCopied = $state('');
    
    // Dirty tracking for global LTI settings
    let ltiGlobalDirty = $derived.by(() => {
        if (!ltiHasSecret) {
            // First-time setup: dirty if either field has content
            return !!(ltiGlobalForm.consumer_key || ltiGlobalForm.consumer_secret);
        }
        // Existing config: dirty if key changed or secret entered
        return (
            ltiGlobalForm.consumer_key !== (ltiGlobalConfig.oauth_consumer_key || '') ||
            ltiGlobalForm.consumer_secret !== ''
        );
    });

    // Build the full LTI Launch URL from config
    let ltiLaunchUrl = $derived(() => {
        const config = getConfig();
        const server = config?.api?.lambServer || 'http://localhost:9099';
        return `${server.replace(/\/$/, '')}/lamb/v1/lti/launch`;
    });

    /** @param {string} text @param {string} label */
    async function copyToClipboard(text, label) {
        try {
            await navigator.clipboard.writeText(text);
            ltiCopied = label;
            setTimeout(() => { ltiCopied = ''; }, 2000);
        } catch {
            // Fallback
            const textarea = document.createElement('textarea');
            textarea.value = text;
            document.body.appendChild(textarea);
            textarea.select();
            document.execCommand('copy');
            document.body.removeChild(textarea);
            ltiCopied = label;
            setTimeout(() => { ltiCopied = ''; }, 2000);
        }
    }

    async function fetchLtiGlobalConfig() {
        isLoadingLtiGlobal = true;
        ltiGlobalError = null;
        try {
            const token = localStorage.getItem('userToken');
            if (!token) throw new Error('Not authenticated');
            const response = await axios.get(getApiUrl('/admin/lti-global-config'), {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            ltiGlobalConfig = response.data;
            ltiGlobalForm = {
                consumer_key: response.data.oauth_consumer_key || '',
                consumer_secret: ''
            };
        } catch (err) {
            ltiGlobalError = err?.response?.data?.detail || err.message || 'Failed to load LTI config';
        } finally {
            isLoadingLtiGlobal = false;
        }
    }

    async function saveLtiGlobalConfig() {
        ltiGlobalError = null;
        ltiGlobalSuccess = null;
        try {
            const token = localStorage.getItem('userToken');
            if (!token) throw new Error('Not authenticated');
            if (!ltiGlobalForm.consumer_key) {
                ltiGlobalError = 'Consumer key is required';
                return;
            }
            if (!ltiHasSecret && !ltiGlobalForm.consumer_secret) {
                ltiGlobalError = 'Consumer secret is required for first-time setup';
                return;
            }
            const payload = { oauth_consumer_key: ltiGlobalForm.consumer_key };
            if (ltiGlobalForm.consumer_secret) {
                payload.oauth_consumer_secret = ltiGlobalForm.consumer_secret;
            }
            await axios.put(getApiUrl('/admin/lti-global-config'), payload, {
                headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' }
            });
            ltiGlobalSuccess = 'Global LTI configuration saved successfully.';
            ltiGlobalForm.consumer_secret = '';
            await fetchLtiGlobalConfig();
            setTimeout(() => { ltiGlobalSuccess = null; }, 4000);
        } catch (err) {
            ltiGlobalError = err?.response?.data?.detail || err.message || 'Failed to save LTI config';
        }
    }

    // --- URL Handling ---
    /** @type {Function|null} */
    let unsubscribePage = null;
    /** @type {Function|null} */
    let unsubscribeUser = null;

    // --- Navigation Functions ---
    function showDashboard() {
        currentView = 'dashboard';
        goto(`${base}/admin`, { replaceState: true });
        // Fetch system stats when dashboard is shown
        fetchSystemStats();
    }

    function showUsers() {
        currentView = 'users';
        goto(`${base}/admin?view=users`, { replaceState: true });
        // Always fetch users when this view is explicitly selected
        fetchUsers();
    }

    function showLtiSettings() {
        currentView = 'lti-settings';
        goto(`${base}/admin?view=lti-settings`, { replaceState: true });
        fetchLtiGlobalConfig();
    }

    function showOrganizations() {
        currentView = 'organizations';
        goto(`${base}/admin?view=organizations`, { replaceState: true });
        // Always fetch organizations when this view is explicitly selected
        fetchOrganizations();
    }

    /**
     * Navigate to user detail view for a specific user
     * @param {number} userId
     */
    function showUserDetail(userId) {
        currentView = 'user-detail';
        userDetailId = userId;
        goto(`${base}/admin?view=user-detail&id=${userId}`, { replaceState: true });
        fetchUserDetail(userId);
    }

    /**
     * Fetch user profile/detail for the admin user-detail view
     * @param {number} userId
     */
    async function fetchUserDetail(userId) {
        isLoadingUserDetail = true;
        userDetailError = null;
        userDetailProfile = null;
        try {
            const token = $user?.token;
            if (!token) throw new Error('Not authenticated');
            const profile = await adminService.getUserProfile(token, userId);
            userDetailProfile = profile;
        } catch (err) {
            userDetailError = err instanceof Error ? err.message : String(err);
        } finally {
            isLoadingUserDetail = false;
        }
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

    // --- Delete User Dialog Functions ---
    let showDeleteConfirm = $state(false);
    let deleteTargetUser = $state(/** @type {any | null} */ (null));
    let userDependencies = $state(/** @type {any | null} */ (null));
    let isCheckingDependencies = $state(false);

    /**
     * @param {any} user
     */
    async function showDeleteDialog(user) {
        deleteTargetUser = user;
        isCheckingDependencies = true;
        showDeleteConfirm = true;
        
        // Check if user has dependencies
        try {
            const token = getAuthToken();
            if (!token) {
                throw new Error('Authentication token not found');
            }
            
            userDependencies = await adminService.checkUserDependencies(token, user.id);
        } catch (error) {
            console.error('Error checking user dependencies:', error);
            userDependencies = null;
        } finally {
            isCheckingDependencies = false;
        }
    }

    async function confirmDelete() {
        if (!deleteTargetUser) return;
        
        try {
            const token = getAuthToken();
            if (!token) {
                throw new Error('Authentication token not found');
            }

            await adminService.deleteUser(token, deleteTargetUser.id);
            console.log(`User ${deleteTargetUser.email} deleted`);
            alert(`User ${deleteTargetUser.name} has been deleted successfully.`);
            
            await fetchUsers(); // Refresh list
        } catch (err) {
            const error = err instanceof Error ? err : new Error('Unknown error');
            console.error('Failed to delete user:', error);
            alert(`Error: ${error.message || 'Failed to delete user'}`);
        } finally {
            showDeleteConfirm = false;
            deleteTargetUser = null;
            userDependencies = null;
        }
    }

    function closeDeleteDialog() {
        showDeleteConfirm = false;
        deleteTargetUser = null;
        userDependencies = null;
    }

    function openCreateOrgModal() {
        // Form state is now managed by OrgForm component
        isCreateOrgModalOpen = true;
    }

    function closeCreateOrgModal() {
        isCreateOrgModalOpen = false;
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

    // --- Organization Members Management ---

    /**
     * Open the members modal for an organization
     * @param {any} org - Organization object
     */
    function openMembersModal(org) {
        membersModalOrg = org;
        orgMembers = [];
        membersError = null;
        roleUpdateSuccess = null;
        isMembersModalOpen = true;
        fetchOrgMembers(org.slug);
    }

    /**
     * Close the members modal
     */
    function closeMembersModal() {
        isMembersModalOpen = false;
        membersModalOrg = null;
        orgMembers = [];
        membersError = null;
        roleUpdateSuccess = null;
    }

    /**
     * Fetch members for an organization
     * @param {string} orgSlug - Organization slug
     */
    async function fetchOrgMembers(orgSlug) {
        isLoadingMembers = true;
        membersError = null;
        try {
            const token = getAuthToken();
            if (!token) throw new Error('Authentication required');
            
            const response = await axios.get(getApiUrl(`/admin/org-admin/users?org=${orgSlug}`), {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            
            if (response.data && Array.isArray(response.data)) {
                orgMembers = response.data;
            } else {
                throw new Error('Invalid response');
            }
        } catch (err) {
            console.error('Error fetching org members:', err);
            if (axios.isAxiosError(err) && err.response?.data?.detail) {
                membersError = err.response.data.detail;
            } else if (err instanceof Error) {
                membersError = err.message;
            } else {
                membersError = 'Failed to load organization members.';
            }
        } finally {
            isLoadingMembers = false;
        }
    }

    /**
     * Update a member's role in an organization
     * @param {number} userId - User ID
     * @param {string} newRole - New role ('admin' or 'member')
     */
    async function updateMemberRole(userId, newRole) {
        if (!membersModalOrg) return;
        
        isUpdatingRole = true;
        roleUpdateSuccess = null;
        membersError = null;
        
        try {
            const token = getAuthToken();
            if (!token) throw new Error('Authentication required');
            
            const response = await axios.put(
                getApiUrl(`/admin/organizations/${membersModalOrg.slug}/members/${userId}/role`),
                { role: newRole },
                { headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' } }
            );
            
            if (response.data?.success) {
                roleUpdateSuccess = response.data.message;
                // Refresh the members list
                await fetchOrgMembers(membersModalOrg.slug);
                // Clear success message after 3 seconds
                setTimeout(() => { roleUpdateSuccess = null; }, 3000);
            }
        } catch (err) {
            console.error('Error updating member role:', err);
            if (axios.isAxiosError(err) && err.response?.data?.detail) {
                membersError = err.response.data.detail;
            } else if (err instanceof Error) {
                membersError = err.message;
            } else {
                membersError = 'Failed to update user role.';
            }
        } finally {
            isUpdatingRole = false;
        }
    }

    // --- Form Handling ---
    /**
     * @param {SubmitEvent} e - The form submission event
     */
    async function handleCreateUser(e) {
        e.preventDefault();
        
        // Read values directly from DOM via FormData (more reliable with automated testing)
        const form = /** @type {HTMLFormElement} */ (e.target);
        const formDataObj = new FormData(form);
        const email = /** @type {string} */ (formDataObj.get('email') || '').toString().trim();
        const name = /** @type {string} */ (formDataObj.get('name') || '').toString().trim();
        const password = /** @type {string} */ (formDataObj.get('password') || '').toString();
        const role = /** @type {string} */ (formDataObj.get('role') || 'user').toString();
        const userTypeFromForm = /** @type {string} */ (formDataObj.get('user_type') || 'creator').toString();
        const organizationId = formDataObj.get('organization_id');
        
        // Basic form validation
        if (!email || !name || !password) {
            createUserError = localeLoaded ? $_('admin.users.errors.fillRequired', { default: 'Please fill in all required fields.' }) : 'Please fill in all required fields.';
            return;
        }
        
        if (!email.includes('@')) {
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
            formData.append('email', email);
            formData.append('name', name);
            formData.append('password', password);
            formData.append('role', role);
            // Ensure admin users have user_type='creator'
            const userType = role === 'admin' ? 'creator' : userTypeFromForm;
            formData.append('user_type', userType);
            
            // Add organization_id if selected
            if (organizationId && organizationId !== 'null' && organizationId !== '') {
                formData.append('organization_id', String(organizationId));
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
                fetchOrganizationsForUsers(); // Fetch organizations for filter dropdown
            } else if (viewParam === 'organizations') {
                console.log("URL indicates 'organizations' view.");
                currentView = 'organizations';
                fetchOrganizations(); // Always fetch when the view is organizations
            } else if (viewParam === 'lti-settings') {
                console.log("URL indicates 'lti-settings' view.");
                currentView = 'lti-settings';
                fetchLtiGlobalConfig();
            } else if (viewParam === 'user-detail') {
                const idParam = currentPage.url.searchParams.get('id');
                if (idParam) {
                    console.log("URL indicates 'user-detail' view for user:", idParam);
                    const userId = parseInt(idParam, 10);
                    if (!isNaN(userId)) {
                        currentView = 'user-detail';
                        userDetailId = userId;
                        fetchUserDetail(userId);
                    } else {
                        currentView = 'users';
                        fetchUsers();
                    }
                } else {
                    currentView = 'users';
                    fetchUsers();
                }
            } else {
                console.log("URL indicates 'dashboard' view.");
                currentView = 'dashboard';
                fetchSystemStats(); // Fetch system stats for dashboard
            }
        });

        // Initial fetch if needed based on the current view
        if (currentView === 'users') {
            fetchUsers();
            fetchOrganizationsForUsers(); // Fetch organizations for filter dropdown
        } else if (currentView === 'organizations') {
            fetchOrganizations();
        } else if (currentView === 'dashboard') {
            fetchSystemStats();
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

    // Fetch system-wide statistics for dashboard
    async function fetchSystemStats() {
        if (isLoadingStats) {
            console.log("Already loading stats, skipping duplicate request");
            return;
        }
        
        console.log("Fetching system statistics...");
        isLoadingStats = true;
        statsError = null;
        
        try {
            const token = getAuthToken();
            if (!token) {
                throw new Error('Authentication token not found. Please log in again.');
            }

            const apiUrl = getApiUrl('/admin/system-stats');
            console.log(`Fetching stats from: ${apiUrl}`);

            const response = await axios.get(apiUrl, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            console.log('System Stats Response:', response.data);
            systemStats = response.data;
        } catch (err) {
            console.error('Error fetching system stats:', err);
            if (axios.isAxiosError(err) && err.response?.status === 401) {
                statsError = 'Access denied. Admin privileges required.';
            } else if (axios.isAxiosError(err) && err.response?.status === 403) {
                statsError = 'Admin privileges required to view system statistics.';
            } else if (axios.isAxiosError(err) && err.response?.data?.detail) {
                statsError = err.response.data.detail;
            } else if (err instanceof Error) {
                statsError = err.message;
            } else {
                statsError = 'An unknown error occurred while fetching statistics.';
            }
            systemStats = null;
        } finally {
            isLoadingStats = false;
        }
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
        
        // Handle merged user_type filter (can be 'admin', 'creator', 'lti_creator', or 'end_user')
        if (usersFilterType === 'admin') {
            // Admin users: filter by role === 'admin'
            filters.role = 'admin';
        } else if (usersFilterType === 'end_user') {
            // End users: filter by user_type === 'end_user'
            filters.user_type = 'end_user';
        } else if (usersFilterType === 'lti_creator') {
            // LTI Creator users: filter by auth_provider === 'lti_creator'
            filters.auth_provider = 'lti_creator';
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
        
        // Additional filtering for 'creator' type (non-admin, non-LTI creators)
        if (usersFilterType === 'creator') {
            result.items = result.items.filter((/** @type {any} */ u) => u.role !== 'admin' && u.user_type === 'creator' && u.auth_provider !== 'lti_creator');
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
    
    /** @param {string} column */
    function handleColumnSort(column) {
        if (usersSortBy === column) {
            // Toggle order if clicking same column
            usersSortOrder = usersSortOrder === 'asc' ? 'desc' : 'asc';
        } else {
            // New column, default to ascending
            usersSortBy = column;
            usersSortOrder = 'asc';
        }
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
     * Open delete organization confirmation modal
     * @param {string} slug - Organization slug
     */
    function deleteOrganization(slug) {
        orgToDelete = slug;
        showDeleteOrgModal = true;
    }
    
    /**
     * Confirm organization deletion
     */
    async function confirmDeleteOrganization() {
        if (!orgToDelete || isDeletingOrg) return;
        isDeletingOrg = true;
        
        try {
            const token = getAuthToken();
            if (!token) {
                throw new Error('Authentication token not found. Please log in again.');
            }

            const apiUrl = getApiUrl(`/admin/organizations/${orgToDelete}`);
            console.log(`Deleting organization at: ${apiUrl}`);

            const response = await axios.delete(apiUrl, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            console.log('Delete organization response:', response.data);
            
            // Refresh organizations list
            fetchOrganizations();
            
            // Close modal and reset state
            showDeleteOrgModal = false;
            orgToDelete = null;
            
            // Show success message
            alert(`Organization deleted successfully!`);
        } catch (err) {
            console.error('Error deleting organization:', err);
            let errorMessage = 'Failed to delete organization.';
            
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
    
    /**
     * Cancel organization deletion
     */
    function cancelDeleteOrganization() {
        if (isDeletingOrg) return;
        showDeleteOrgModal = false;
        orgToDelete = null;
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
                    aria-label={localeLoaded ? $_('admin.tabs.users', { default: 'Users' }) : 'Users'}
                >
                    {localeLoaded ? $_('admin.tabs.users', { default: 'Users' }) : 'Users'}
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
            <li class="mr-2">
                <button
                    class={`inline-block py-2 px-4 text-sm font-medium ${currentView === 'lti-settings' ? 'text-white bg-brand border-brand' : 'text-gray-500 hover:text-brand border-transparent'} rounded-t-lg border-b-2`}
                    onclick={showLtiSettings}
                    aria-label="LTI Settings"
                >
                    LTI Settings
                </button>
            </li>
        </ul>
    </div>

    <!-- View Content -->
    {#if currentView === 'dashboard'}
        <AdminDashboard
            {systemStats}
            isLoading={isLoadingStats}
            error={statsError}
            {localeLoaded}
            onRefresh={fetchSystemStats}
            onShowUsers={showUsers}
            onShowOrganizations={showOrganizations}
        />
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
                            { value: 'lti_creator', label: localeLoaded ? $_('admin.users.filtersOptions.ltiCreator', { default: 'LTI Creator' }) : 'LTI Creator' },
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
                showSort={false}
                on:searchChange={handleUsersSearchChange}
                on:filterChange={handleUsersFilterChange}
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
                                <div class="flex flex-col gap-1">
                                    <button 
                                        onclick={() => handleColumnSort('name')}
                                        class="flex items-center gap-1 hover:text-brand-hover focus:outline-none group"
                                    >
                                        {localeLoaded ? $_('admin.users.table.name', { default: 'Name' }) : 'Name'}
                                        <span class="inline-flex flex-col {usersSortBy === 'name' ? 'text-brand' : 'text-gray-400 group-hover:text-gray-600'}">
                                            {#if usersSortBy === 'name'}
                                                {#if usersSortOrder === 'asc'}
                                                    <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20"><path d="M5.293 9.707a1 1 0 010-1.414l4-4a1 1 0 011.414 0l4 4a1 1 0 01-1.414 1.414L10 6.414l-3.293 3.293a1 1 0 01-1.414 0z"/></svg>
                                                {:else}
                                                    <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20"><path d="M14.707 10.293a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 111.414-1.414L10 13.586l3.293-3.293a1 1 0 011.414 0z"/></svg>
                                                {/if}
                                            {:else}
                                                <svg class="w-4 h-4 opacity-0 group-hover:opacity-50" fill="currentColor" viewBox="0 0 20 20"><path d="M5.293 9.707a1 1 0 010-1.414l4-4a1 1 0 011.414 0l4 4a1 1 0 01-1.414 1.414L10 6.414l-3.293 3.293a1 1 0 01-1.414 0z"/></svg>
                                            {/if}
                                        </span>
                                    </button>
                                    <button 
                                        onclick={() => handleColumnSort('email')}
                                        class="flex items-center gap-1 hover:text-brand-hover focus:outline-none group text-gray-400"
                                    >
                                        {localeLoaded ? $_('admin.users.table.email', { default: 'Email' }) : 'Email'}
                                        <span class="inline-flex flex-col {usersSortBy === 'email' ? 'text-brand' : 'text-gray-400 group-hover:text-gray-600'}">
                                            {#if usersSortBy === 'email'}
                                                {#if usersSortOrder === 'asc'}
                                                    <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20"><path d="M5.293 9.707a1 1 0 010-1.414l4-4a1 1 0 011.414 0l4 4a1 1 0 01-1.414 1.414L10 6.414l-3.293 3.293a1 1 0 01-1.414 0z"/></svg>
                                                {:else}
                                                    <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20"><path d="M14.707 10.293a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 111.414-1.414L10 13.586l3.293-3.293a1 1 0 011.414 0z"/></svg>
                                                {/if}
                                            {:else}
                                                <svg class="w-4 h-4 opacity-0 group-hover:opacity-50" fill="currentColor" viewBox="0 0 20 20"><path d="M5.293 9.707a1 1 0 010-1.414l4-4a1 1 0 011.414 0l4 4a1 1 0 01-1.414 1.414L10 6.414l-3.293 3.293a1 1 0 01-1.414 0z"/></svg>
                                            {/if}
                                        </span>
                                    </button>
                                </div>
                            </th>
                            <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-brand uppercase tracking-wider hidden md:table-cell">
                                <div class="flex flex-col">
                                    <span>{localeLoaded ? $_('admin.users.table.userType', { default: 'User Type' }) : 'User Type'}</span>
                                    <span class="text-gray-400">{localeLoaded ? $_('admin.users.table.status', { default: 'Status' }) : 'Status'}</span>
                                </div>
                            </th>
                            <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-brand uppercase tracking-wider hidden md:table-cell">
                                <button 
                                    onclick={() => handleColumnSort('organization.name')}
                                    class="flex items-center gap-1 hover:text-brand-hover focus:outline-none group"
                                >
                                    {localeLoaded ? $_('admin.users.table.organization', { default: 'Organization' }) : 'Organization'}
                                    <span class="inline-flex flex-col {usersSortBy === 'organization.name' ? 'text-brand' : 'text-gray-400 group-hover:text-gray-600'}">
                                        {#if usersSortBy === 'organization.name'}
                                            {#if usersSortOrder === 'asc'}
                                                <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20"><path d="M5.293 9.707a1 1 0 010-1.414l4-4a1 1 0 011.414 0l4 4a1 1 0 01-1.414 1.414L10 6.414l-3.293 3.293a1 1 0 01-1.414 0z"/></svg>
                                            {:else}
                                                <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20"><path d="M14.707 10.293a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 111.414-1.414L10 13.586l3.293-3.293a1 1 0 011.414 0z"/></svg>
                                            {/if}
                                        {:else}
                                            <svg class="w-4 h-4 opacity-0 group-hover:opacity-50" fill="currentColor" viewBox="0 0 20 20"><path d="M5.293 9.707a1 1 0 010-1.414l4-4a1 1 0 011.414 0l4 4a1 1 0 01-1.414 1.414L10 6.414l-3.293 3.293a1 1 0 01-1.414 0z"/></svg>
                                        {/if}
                                    </span>
                                </button>
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
                                    <div class="text-sm font-medium">
                                        <button
                                            class="text-brand hover:text-brand/80 hover:underline font-medium text-left"
                                            onclick={() => showUserDetail(user.id)}
                                            title={localeLoaded ? $_('admin.users.viewProfile', { default: 'View user profile' }) : 'View user profile'}
                                        >
                                            {user.name || '-'}
                                        </button>
                                    </div>
                                    <div class="text-xs text-gray-500">{user.email}</div>
                                </td>
                                <td class="px-6 py-4 whitespace-nowrap hidden md:table-cell" style="font-size: 0.8125rem;">
                                    <div>
                                        {#if user.role === 'admin'}
                                            <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-red-100 text-red-800">
                                                {localeLoaded ? $_('admin.users.filtersOptions.admin', { default: 'Admin' }) : 'Admin'}
                                            </span>
                                        {:else if user.auth_provider === 'lti_creator'}
                                            <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-blue-100 text-blue-800">
                                                {localeLoaded ? $_('admin.users.filtersOptions.ltiCreator', { default: 'LTI Creator' }) : 'LTI Creator'}
                                            </span>
                                        {:else if user.user_type === 'end_user'}
                                            <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-purple-100 text-purple-800">
                                                {localeLoaded ? $_('admin.users.filtersOptions.endUser', { default: 'End User' }) : 'End User'}
                                            </span>
                                        {:else if user.organization_role === 'admin' || user.organization_role === 'owner'}
                                            <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-orange-100 text-orange-800">
                                                {localeLoaded ? $_('admin.users.tableValues.orgAdmin', { default: 'Org Admin' }) : 'Org Admin'}
                                            </span>
                                        {:else}
                                            <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800">
                                                {localeLoaded ? $_('admin.users.filtersOptions.creator', { default: 'Creator' }) : 'Creator'}
                                            </span>
                                        {/if}
                                    </div>
                                    <div class="mt-1">
                                        <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full {user.enabled ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}">
                                            {user.enabled 
                                                ? (localeLoaded ? $_('admin.users.filtersOptions.active', { default: 'Active' }) : 'Active')
                                                : (localeLoaded ? $_('admin.users.filtersOptions.disabled', { default: 'Disabled' }) : 'Disabled')
                                            }
                                        </span>
                                    </div>
                                </td>
                                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-800 hidden md:table-cell">
                                    {#if user.organization}
                                        <div class="flex items-center flex-wrap gap-1">
                                            <span class="text-sm font-medium text-gray-900">{user.organization.name || '-'}</span>
                                            {#if user.organization.is_system}
                                                <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-yellow-100 text-yellow-800">
                                                    {localeLoaded ? $_('admin.users.tableValues.system', { default: 'System' }) : 'System'}
                                                </span>
                                            {/if}
                                        </div>
                                    {:else}
                                        <span class="text-gray-400">{localeLoaded ? $_('admin.users.tableValues.noOrganization', { default: 'No Organization' }) : 'No Organization'}</span>
                                    {/if}
                                </td>
                                <td class="px-6 py-4 whitespace-nowrap text-xs font-medium">
                                    <div class="flex flex-col gap-1">
                                        <!-- Change Password (only for non-LTI users) -->
                                        {#if user.auth_provider !== 'lti_creator'}
                                            <button 
                                                class="inline-flex items-center gap-1 text-amber-600 hover:text-amber-800" 
                                                title={localeLoaded ? $_('admin.users.actions.changePassword', { default: 'Change Password' }) : 'Change Password'}
                                                aria-label={localeLoaded ? $_('admin.users.actions.changePassword', { default: 'Change Password' }) : 'Change Password'}
                                                onclick={() => openChangePasswordModal(user.email, user.name)}
                                            >
                                                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-4 h-4">
                                                  <path stroke-linecap="round" stroke-linejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
                                                </svg>
                                                {localeLoaded ? $_('admin.users.actions.changePassword', { default: 'Password' }) : 'Password'}
                                            </button>
                                        {/if}
                                        <!-- Enable/Disable Toggle -->
                                        {#if !(currentUserData && currentUserData.email === user.email)}
                                            {#if user.enabled}
                                                <button
                                                    class="inline-flex items-center gap-1 text-red-500 hover:text-red-700"
                                                    title={localeLoaded ? $_('admin.users.actions.disable', { default: 'Disable User' }) : 'Disable User'}
                                                    aria-label={localeLoaded ? $_('admin.users.actions.disable', { default: 'Disable User' }) : 'Disable User'}
                                                    onclick={() => toggleUserStatusAdmin(user)}
                                                >
                                                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-4 h-4">
                                                        <path stroke-linecap="round" stroke-linejoin="round" d="M22 10.5h-6m-2.25-4.125a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zM4 19.235v-.11a6.375 6.375 0 0112.75 0v.109A12.318 12.318 0 0110.374 21c-2.331 0-4.512-.645-6.374-1.766z" />
                                                    </svg>
                                                    {localeLoaded ? $_('admin.users.actions.disable', { default: 'Disable' }) : 'Disable'}
                                                </button>
                                            {:else}
                                                <button
                                                    class="inline-flex items-center gap-1 text-green-600 hover:text-green-800"
                                                    title={localeLoaded ? $_('admin.users.actions.enable', { default: 'Enable User' }) : 'Enable User'}
                                                    aria-label={localeLoaded ? $_('admin.users.actions.enable', { default: 'Enable User' }) : 'Enable User'}
                                                    onclick={() => toggleUserStatusAdmin(user)}
                                                >
                                                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-4 h-4">
                                                        <path stroke-linecap="round" stroke-linejoin="round" d="M18 7.5v3m0 0v3m0-3h3m-3 0h-3m-2.25-4.125a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zM4 19.235v-.11a6.375 6.375 0 0112.75 0v.109A12.318 12.318 0 0110.374 21c-2.331 0-4.512-.645-6.374-1.766z" />
                                                    </svg>
                                                    {localeLoaded ? $_('admin.users.actions.enable', { default: 'Enable' }) : 'Enable'}
                                                </button>
                                            {/if}
                                        {/if}
                                        <!-- Delete button - only shown for disabled users -->
                                        {#if !user.enabled && !(currentUserData && currentUserData.email === user.email)}
                                            <button
                                                class="inline-flex items-center gap-1 text-red-600 hover:text-red-900"
                                                title="Delete User"
                                                aria-label="Delete User"
                                                onclick={() => showDeleteDialog(user)}
                                            >
                                                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-4 h-4">
                                                    <path stroke-linecap="round" stroke-linejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                                                </svg>
                                                Delete
                                            </button>
                                        {/if}
                                    </div>
                                </td>
                            </tr>
                        {/each}
                    </tbody>
                </table>
            </div>
            
            <!-- Pagination -->
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
                                    <button 
                                        class="text-sm font-medium text-blue-600 hover:text-blue-800 hover:underline cursor-pointer bg-transparent border-none p-0"
                                        onclick={() => administerOrganization(org)}
                                        title="Go to organization settings"
                                    >
                                        {org.name || '-'}
                                    </button>
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
                                            class="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-white bg-green-600 hover:bg-green-700 rounded-md shadow-sm transition-colors" 
                                            title="Manage Organization"
                                            aria-label="Manage Organization"
                                            onclick={() => administerOrganization(org)}
                                        >
                                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-4 h-4">
                                                <path stroke-linecap="round" stroke-linejoin="round" d="M10.343 3.94c.09-.542.56-.94 1.11-.94h1.093c.55 0 1.02.398 1.11.94l.149.894c.07.424.384.764.78.93.398.164.855.142 1.205-.108l.737-.527a1.125 1.125 0 011.45.12l.773.774c.39.389.44 1.002.12 1.45l-.527.737c-.25.35-.272.806-.107 1.204.165.397.505.71.93.78l.893.15c.543.09.94.56.94 1.109v1.094c0 .55-.397 1.02-.94 1.11l-.893.149c-.425.07-.765.383-.93.78-.165.398-.143.854.107 1.204l.527.738c.32.447.269 1.06-.12 1.45l-.774.773a1.125 1.125 0 01-1.449.12l-.738-.527c-.35-.25-.806-.272-1.203-.107-.397.165-.71.505-.781.929l-.149.894c-.09.542-.56.94-1.11.94h-1.094c-.55 0-1.019-.398-1.11-.94l-.148-.894c-.071-.424-.384-.764-.781-.93-.398-.164-.854-.142-1.204.108l-.738.527c-.447.32-1.06.269-1.45-.12l-.773-.774a1.125 1.125 0 01-.12-1.45l.527-.737c.25-.35.273-.806.108-1.204-.165-.397-.505-.71-.93-.78l-.894-.15c-.542-.09-.94-.56-.94-1.109v-1.094c0-.55.398-1.02.94-1.11l.894-.149c.424-.07.765-.383.93-.78.165-.398.143-.854-.107-1.204l-.527-.738a1.125 1.125 0 01.12-1.45l.773-.773a1.125 1.125 0 011.45-.12l.737.527c.35.25.807.272 1.204.107.397-.165.71-.505.78-.929l.15-.894z" />
                                                <path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                            </svg>
                                            Manage
                                        </button>
                                        {#if !org.is_system}
                                            <button 
                                                class="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-md shadow-sm transition-colors" 
                                                title="Manage Members & Roles"
                                                aria-label="Manage Members & Roles"
                                                onclick={() => openMembersModal(org)}
                                            >
                                                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-4 h-4">
                                                    <path stroke-linecap="round" stroke-linejoin="round" d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z" />
                                                </svg>
                                                Members
                                            </button>
                                        {/if}
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

<!-- Change Password Modal (Shared Component) -->
<ChangePasswordModal
    isOpen={isChangePasswordModalOpen}
    userName={selectedUserName}
    userEmail={passwordChangeData.email}
    newPassword={passwordChangeData.new_password}
    isChanging={isChangingPassword}
    error={changePasswordError}
    success={changePasswordSuccess}
    {localeLoaded}
    onSubmit={handleChangePassword}
    onClose={closeChangePasswordModal}
    onPasswordChange={(pwd) => { passwordChangeData.new_password = pwd; }}
/>

<!-- Create User Modal (Shared Component) -->
<UserForm
    isOpen={isCreateUserModalOpen}
    isSuperAdmin={true}
    {newUser}
    organizations={organizationsForUsers}
    isLoadingOrganizations={isLoadingOrganizationsForUsers}
    organizationsError={organizationsForUsersError}
    isCreating={isCreatingUser}
    error={createUserError}
    success={createUserSuccess}
    {localeLoaded}
    onSubmit={handleCreateUser}
    onClose={closeCreateUserModal}
    onUserChange={(user) => { newUser = user; }}
/>

<!-- Create Organization Modal -->
<OrgForm
    bind:isOpen={isCreateOrgModalOpen}
    {localeLoaded}
    {getAuthToken}
    onSuccess={() => fetchOrganizations()}
    onClose={closeCreateOrgModal}
/>

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

<!-- Disable User Confirmation Modal (Shared Component) -->
<UserActionModal
    isOpen={showDisableConfirm}
    action="disable"
    isBulk={actionType === 'bulk'}
    targetUser={actionType === 'single' ? targetUser : null}
    selectedCount={selectedUsers.length}
    {localeLoaded}
    onConfirm={confirmDisable}
    onClose={() => { showDisableConfirm = false; }}
/>

<!-- Enable User Confirmation Modal (Shared Component) -->
<UserActionModal
    isOpen={showEnableConfirm}
    action="enable"
    isBulk={actionType === 'bulk'}
    targetUser={actionType === 'single' ? targetUser : null}
    selectedCount={selectedUsers.length}
    {localeLoaded}
    onConfirm={confirmEnable}
    onClose={() => { showEnableConfirm = false; }}
/>

<!-- Delete User Confirmation Modal -->
{#if showDeleteConfirm}
    <div class="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50 flex items-center justify-center">
        <div class="relative mx-auto p-5 border w-full max-w-lg shadow-lg rounded-md bg-white">
            <div class="mt-3">
                <div class="flex items-center mb-4">
                    <svg class="w-6 h-6 text-red-600 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
                    </svg>
                    <h3 class="text-lg font-medium text-gray-900">Delete User</h3>
                </div>
                <div class="mt-2 px-7 py-3">
                    {#if isCheckingDependencies}
                        <p class="text-sm text-gray-600">Checking user dependencies...</p>
                    {:else if userDependencies}
                        <p class="text-sm text-gray-700 mb-3">
                            Are you sure you want to permanently delete <strong>{deleteTargetUser?.name}</strong> ({deleteTargetUser?.email})?
                        </p>
                        
                        {#if userDependencies.has_dependencies}
                            <div class="bg-red-50 border border-red-200 rounded p-3 mb-3">
                                <p class="text-sm text-red-800 font-semibold mb-2">
                                    ⚠️ Cannot delete user - has dependencies:
                                </p>
                                {#if userDependencies.assistant_count > 0}
                                    <div class="mb-2">
                                        <p class="text-sm text-red-700 font-medium">
                                            {userDependencies.assistant_count} Assistant(s):
                                        </p>
                                        <ul class="text-xs text-red-600 list-disc list-inside ml-2">
                                            {#each userDependencies.assistants.slice(0, 5) as assistant}
                                                <li>{assistant.name}</li>
                                            {/each}
                                            {#if userDependencies.assistants.length > 5}
                                                <li>... and {userDependencies.assistants.length - 5} more</li>
                                            {/if}
                                        </ul>
                                    </div>
                                {/if}
                                {#if userDependencies.kb_count > 0}
                                    <div>
                                        <p class="text-sm text-red-700 font-medium">
                                            {userDependencies.kb_count} Knowledge Base(s):
                                        </p>
                                        <ul class="text-xs text-red-600 list-disc list-inside ml-2">
                                            {#each userDependencies.kbs.slice(0, 5) as kb}
                                                <li>{kb.name}</li>
                                            {/each}
                                            {#if userDependencies.kbs.length > 5}
                                                <li>... and {userDependencies.kbs.length - 5} more</li>
                                            {/if}
                                        </ul>
                                    </div>
                                {/if}
                                <p class="text-xs text-red-700 mt-2">
                                    Please delete or reassign these resources before deleting the user.
                                </p>
                            </div>
                        {:else}
                            <div class="bg-green-50 border border-green-200 rounded p-3 mb-3">
                                <p class="text-sm text-green-800">
                                    ✓ User has no dependencies and can be safely deleted.
                                </p>
                            </div>
                        {/if}
                        
                        <p class="text-xs text-gray-600 mt-3">
                            <strong>Note:</strong> This action cannot be undone.
                        </p>
                    {/if}
                </div>
                <div class="flex items-center justify-end gap-3 px-4 py-3">
                    <button 
                        onclick={closeDeleteDialog}
                        class="bg-gray-300 hover:bg-gray-400 text-gray-800 py-2 px-4 rounded focus:outline-none focus:shadow-outline"
                    >
                        Cancel
                    </button>
                    <button 
                        onclick={confirmDelete}
                        disabled={isCheckingDependencies || (userDependencies && userDependencies.has_dependencies)}
                        class="bg-red-600 hover:bg-red-700 text-white py-2 px-4 rounded focus:outline-none focus:shadow-outline disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        Delete
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

    {:else if currentView === 'lti-settings'}
        <!-- Global LTI Settings View -->
        <div class="mb-6">
            <h2 class="text-xl font-semibold text-gray-800 mb-2">LTI Tool Configuration</h2>
            <p class="text-sm text-gray-600">
                Use these values when creating an External Tool (LTI 1.1) in your LMS (Moodle, Canvas, etc.).
            </p>
        </div>

        {#if isLoadingLtiGlobal}
            <div class="bg-white overflow-hidden shadow rounded-lg p-8">
                <div class="flex items-center justify-center">
                    <div class="inline-block animate-spin rounded-full h-6 w-6 border-b-2 border-brand mr-3"></div>
                    <span class="text-gray-500">Loading LTI configuration...</span>
                </div>
            </div>
        {:else}
            <!-- Error Message -->
            {#if ltiGlobalError}
                <div class="mb-4 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative" role="alert">
                    <strong class="font-bold">Error: </strong>
                    <span class="block sm:inline">{ltiGlobalError}</span>
                </div>
            {/if}

            <!-- Success Message -->
            {#if ltiGlobalSuccess}
                <div class="mb-4 bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded relative" role="alert">
                    <strong class="font-bold">Success! </strong>
                    <span class="block sm:inline">{ltiGlobalSuccess}</span>
                </div>
            {/if}

            <!-- ===== LMS Setup Information ===== -->
            <div class="bg-white overflow-hidden shadow rounded-lg mb-6">
                <div class="px-4 py-5 sm:p-6">
                    <h3 class="text-lg leading-6 font-medium text-gray-900 mb-1">LMS Setup Information</h3>
                    <p class="text-sm text-gray-500 mb-5">Copy these three values into your LMS External Tool configuration.</p>

                    <!-- Launch URL -->
                    <div class="mb-5">
                        <label for="lti-launch-url" class="block text-sm font-medium text-gray-700 mb-1">Launch URL</label>
                        <div class="flex items-center gap-2">
                            <input
                                id="lti-launch-url"
                                type="text"
                                readonly
                                value={ltiLaunchUrl()}
                                class="flex-1 bg-gray-50 border border-gray-300 rounded-md shadow-sm py-2 px-3 text-sm font-mono text-gray-900 cursor-text select-all"
                            >
                            <button
                                type="button"
                                onclick={() => copyToClipboard(ltiLaunchUrl(), 'url')}
                                class="inline-flex items-center px-3 py-2 border border-gray-300 rounded-md text-sm font-medium {ltiCopied === 'url' ? 'bg-green-50 text-green-700 border-green-300' : 'bg-white text-gray-700 hover:bg-gray-50'} transition-colors"
                            >
                                {#if ltiCopied === 'url'}
                                    <svg class="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>
                                    Copied
                                {:else}
                                    <svg class="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>
                                    Copy
                                {/if}
                            </button>
                        </div>
                        <p class="mt-1 text-xs text-gray-500">This is the URL the LMS sends the LTI launch POST to.</p>
                    </div>

                    <!-- Consumer Key (read-only display) -->
                    <div class="mb-5">
                        <label for="lti-display-key" class="block text-sm font-medium text-gray-700 mb-1">Consumer Key</label>
                        <div class="flex items-center gap-2">
                            <input
                                id="lti-display-key"
                                type="text"
                                readonly
                                value={ltiGlobalConfig.oauth_consumer_key || '(not set)'}
                                class="flex-1 bg-gray-50 border border-gray-300 rounded-md shadow-sm py-2 px-3 text-sm font-mono text-gray-900 cursor-text select-all"
                            >
                            <button
                                type="button"
                                onclick={() => copyToClipboard(ltiGlobalConfig.oauth_consumer_key || '', 'key')}
                                class="inline-flex items-center px-3 py-2 border border-gray-300 rounded-md text-sm font-medium {ltiCopied === 'key' ? 'bg-green-50 text-green-700 border-green-300' : 'bg-white text-gray-700 hover:bg-gray-50'} transition-colors"
                                disabled={!ltiGlobalConfig.oauth_consumer_key}
                            >
                                {#if ltiCopied === 'key'}
                                    <svg class="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>
                                    Copied
                                {:else}
                                    <svg class="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>
                                    Copy
                                {/if}
                            </button>
                        </div>
                    </div>

                    <!-- Secret Status (read-only display) -->
                    <div>
                        <p class="block text-sm font-medium text-gray-700 mb-1">Shared Secret</p>
                        <div class="flex items-center gap-3">
                            {#if ltiHasSecret}
                                <span class="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                                    <svg class="h-3.5 w-3.5 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" /></svg>
                                    Configured ({ltiGlobalConfig.oauth_consumer_secret_masked})
                                </span>
                            {:else}
                                <span class="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-red-100 text-red-800">
                                    <svg class="h-3.5 w-3.5 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" /></svg>
                                    Not set — configure below
                                </span>
                            {/if}
                            <span class="text-xs text-gray-500">
                                Source: {ltiGlobalConfig.source === 'database' ? 'Database' : '.env file'}
                                {#if ltiGlobalConfig.updated_at}
                                    &middot; Updated {new Date(ltiGlobalConfig.updated_at * 1000).toLocaleDateString()}
                                {/if}
                            </span>
                        </div>
                        <p class="mt-1.5 text-xs text-gray-500">
                            The secret is never displayed in full. Enter it in your LMS exactly as configured below.
                        </p>
                    </div>
                </div>
            </div>

            <!-- ===== Edit Credentials ===== -->
            <div class="bg-white overflow-hidden shadow rounded-lg">
                <div class="px-4 py-5 sm:p-6">
                    <h3 class="text-lg leading-6 font-medium text-gray-900 mb-1">Edit LTI Credentials</h3>
                    <p class="text-sm text-gray-500 mb-5">
                        Change the consumer key or secret. Saving stores them in the database and overrides any <code class="text-xs bg-gray-100 px-1 rounded">.env</code> values.
                    </p>

                    <div class="space-y-4">
                        <!-- Consumer Key -->
                        <div>
                            <label for="lti-global-key" class="block text-sm font-medium text-gray-700">OAuth Consumer Key</label>
                            <input
                                id="lti-global-key"
                                type="text"
                                bind:value={ltiGlobalForm.consumer_key}
                                placeholder="e.g., lamb"
                                class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-brand focus:border-brand sm:text-sm"
                            >
                            <p class="mt-1 text-xs text-gray-500">The LMS sends this as <code>oauth_consumer_key</code>. Must match on both sides.</p>
                        </div>

                        <!-- Consumer Secret -->
                        <div>
                            <label for="lti-global-secret" class="block text-sm font-medium text-gray-700">
                                OAuth Shared Secret
                            </label>
                            <div class="relative mt-1">
                                <input
                                    id="lti-global-secret"
                                    type={showLtiSecret && ltiGlobalForm.consumer_secret ? 'text' : 'password'}
                                    bind:value={ltiGlobalForm.consumer_secret}
                                    placeholder={ltiHasSecret ? '••••••••  (leave blank to keep current)' : 'Enter a strong secret key'}
                                    class="block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 {ltiGlobalForm.consumer_secret ? 'pr-10' : ''} focus:outline-none focus:ring-brand focus:border-brand sm:text-sm"
                                >
                                {#if ltiGlobalForm.consumer_secret}
                                    <button
                                        type="button"
                                        onclick={() => showLtiSecret = !showLtiSecret}
                                        class="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-600"
                                        title={showLtiSecret ? 'Hide secret' : 'Show secret'}
                                    >
                                        {#if showLtiSecret}
                                            <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" /></svg>
                                        {:else}
                                            <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" /></svg>
                                        {/if}
                                    </button>
                                {/if}
                            </div>
                            <p class="mt-1 text-xs text-gray-500">Used to sign and verify LTI launch requests (HMAC-SHA1). Must match in the LMS.</p>
                        </div>

                        <!-- Action Buttons -->
                        <div class="flex items-center pt-4 border-t border-gray-200">
                            <button
                                class="text-white font-semibold py-2 px-4 rounded focus:outline-none focus:shadow-outline transition-colors {ltiGlobalDirty ? 'bg-brand hover:bg-brand-hover' : 'bg-gray-300 cursor-not-allowed'}"
                                onclick={saveLtiGlobalConfig}
                                disabled={!ltiGlobalDirty}
                            >
                                Save LTI Configuration
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            <!-- ===== How it works ===== -->
            <div class="mt-6 p-4 bg-blue-50 border-l-4 border-blue-400 rounded">
                <h4 class="text-sm font-semibold text-blue-800 mb-2">How the Unified LTI Endpoint Works</h4>
                <ol class="text-xs text-blue-700 space-y-1.5 list-decimal list-inside">
                    <li>In your LMS, create a new <strong>External Tool (LTI 1.1)</strong>.</li>
                    <li>Paste the <strong>Launch URL</strong>, <strong>Consumer Key</strong>, and <strong>Secret</strong> from above.</li>
                    <li>When an <strong>instructor</strong> launches the tool for the first time, they choose which assistants to assign.</li>
                    <li>Subsequent <strong>student</strong> launches go directly to Open WebUI with those assistants available.</li>
                </ol>
            </div>
        {/if}

    {:else if currentView === 'user-detail'}
        <!-- User Detail / Profile View -->
        <div class="mb-4">
            <button
                onclick={showUsers}
                class="inline-flex items-center text-sm text-brand hover:text-brand/80 font-medium gap-1"
            >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
                </svg>
                {localeLoaded ? $_('admin.users.backToList', { default: 'Back to Users' }) : 'Back to Users'}
            </button>
        </div>
        <UserDashboard
            profile={userDetailProfile}
            isLoading={isLoadingUserDetail}
            error={userDetailError}
            onRetry={() => { if (userDetailId) fetchUserDetail(userDetailId); }}
        />
    {/if}

<!-- Organization Members & Roles Modal -->
{#if isMembersModalOpen && membersModalOrg}
    <div class="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50 flex items-center justify-center">
        <div class="relative mx-auto p-5 border w-full max-w-3xl shadow-lg rounded-md bg-white max-h-[90vh] overflow-y-auto">
            <div class="flex justify-between items-center mb-4">
                <h3 class="text-lg leading-6 font-medium text-gray-900">
                    Members: {membersModalOrg.name}
                    <span class="text-sm text-gray-500 font-normal ml-2">({membersModalOrg.slug})</span>
                </h3>
                <button 
                    onclick={closeMembersModal}
                    class="text-gray-400 hover:text-gray-600 transition-colors"
                >
                    <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                </button>
            </div>

            {#if roleUpdateSuccess}
                <div class="mb-4 bg-green-100 border border-green-400 text-green-700 px-4 py-2 rounded text-sm">
                    {roleUpdateSuccess}
                </div>
            {/if}

            {#if membersError}
                <div class="mb-4 bg-red-100 border border-red-400 text-red-700 px-4 py-2 rounded text-sm">
                    {membersError}
                </div>
            {/if}

            {#if isLoadingMembers}
                <div class="text-center py-8 text-gray-500">Loading members...</div>
            {:else if orgMembers.length === 0}
                <div class="text-center py-8">
                    <p class="text-gray-500">No members in this organization.</p>
                    <p class="text-gray-400 text-sm mt-2">Users can join via signup or be assigned by a system admin.</p>
                </div>
            {:else}
                <div class="overflow-x-auto">
                    <table class="min-w-full divide-y divide-gray-200">
                        <thead class="bg-gray-50">
                            <tr>
                                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">User</th>
                                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
                                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Role</th>
                                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
                            </tr>
                        </thead>
                        <tbody class="bg-white divide-y divide-gray-200">
                            {#each orgMembers as member (member.id)}
                                <tr class="hover:bg-gray-50">
                                    <td class="px-4 py-3">
                                        <div class="text-sm font-medium text-gray-900">{member.name || '-'}</div>
                                        <div class="text-xs text-gray-500">{member.email}</div>
                                    </td>
                                    <td class="px-4 py-3">
                                        {#if member.auth_provider === 'lti_creator'}
                                            <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-blue-100 text-blue-800">LTI Creator</span>
                                        {:else}
                                            <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800">Creator</span>
                                        {/if}
                                    </td>
                                    <td class="px-4 py-3">
                                        {#if member.role === 'admin'}
                                            <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-purple-100 text-purple-800">Admin</span>
                                        {:else}
                                            <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-gray-100 text-gray-800">Member</span>
                                        {/if}
                                    </td>
                                    <td class="px-4 py-3">
                                        {#if member.enabled}
                                            <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800">Active</span>
                                        {:else}
                                            <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-red-100 text-red-800">Disabled</span>
                                        {/if}
                                    </td>
                                    <td class="px-4 py-3">
                                        {#if member.role === 'admin'}
                                            <button
                                                class="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-amber-700 bg-amber-50 hover:bg-amber-100 border border-amber-200 rounded transition-colors disabled:opacity-50"
                                                title="Demote to Member"
                                                disabled={isUpdatingRole}
                                                onclick={() => updateMemberRole(member.id, 'member')}
                                            >
                                                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-3.5 h-3.5">
                                                    <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 13.5L12 21m0 0l-7.5-7.5M12 21V3" />
                                                </svg>
                                                Demote
                                            </button>
                                        {:else}
                                            <button
                                                class="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-indigo-700 bg-indigo-50 hover:bg-indigo-100 border border-indigo-200 rounded transition-colors disabled:opacity-50"
                                                title="Promote to Admin"
                                                disabled={isUpdatingRole}
                                                onclick={() => updateMemberRole(member.id, 'admin')}
                                            >
                                                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-3.5 h-3.5">
                                                    <path stroke-linecap="round" stroke-linejoin="round" d="M4.5 10.5L12 3m0 0l7.5 7.5M12 3v18" />
                                                </svg>
                                                Promote
                                            </button>
                                        {/if}
                                    </td>
                                </tr>
                            {/each}
                        </tbody>
                    </table>
                </div>
                <p class="mt-3 text-xs text-gray-500 italic">
                    Any user, including LTI Creator users, can be promoted to organization admin.
                </p>
            {/if}

            <div class="mt-4 flex justify-end">
                <button 
                    onclick={closeMembersModal}
                    class="bg-gray-300 hover:bg-gray-400 text-gray-800 py-2 px-4 rounded transition-colors"
                >
                    Close
                </button>
            </div>
        </div>
    </div>
{/if}

<!-- Delete Organization Confirmation Modal -->
<ConfirmationModal
    bind:isOpen={showDeleteOrgModal}
    bind:isLoading={isDeletingOrg}
    title="Delete Organization"
    message={`Are you sure you want to delete organization '${orgToDelete}'? This action cannot be undone and will remove all associated data.`}
    confirmText="Delete"
    variant="danger"
    onconfirm={confirmDeleteOrganization}
    oncancel={cancelDeleteOrganization}
/>

<style>
    /* Add specific styles if needed, though Tailwind should cover most */
</style> 