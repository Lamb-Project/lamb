<script>
    import { untrack } from 'svelte';
    import { _ } from '$lib/i18n';
    import { getApiUrl } from '$lib/config';
    import axios from 'axios';

    /**
     * @typedef {Object} OrgConfig
     * @property {string} version
     * @property {Object} setups
     * @property {{rag_enabled: boolean, lti_publishing: boolean, signup_enabled: boolean}} features
     * @property {{usage: {tokens_per_month: number, max_assistants: number, max_assistants_per_user: number, storage_gb: number}}} limits
     */

    /**
     * @typedef {Object} OrgFormData
     * @property {string} slug
     * @property {string} name
     * @property {number|null} admin_user_id
     * @property {boolean} signup_enabled
     * @property {string} signup_key
     * @property {boolean} use_system_baseline
     * @property {OrgConfig} config
     */

    /**
     * @typedef {Object} SystemUser
     * @property {number} id
     * @property {string} email
     * @property {string} name
     * @property {string} role
     * @property {number} joined_at
     */

    // Props
    let {
        isOpen = $bindable(false),
        localeLoaded = false,
        getAuthToken,
        onSuccess = () => {},
        onClose = () => {}
    } = $props();

    // --- Form State ---
    /** @type {OrgFormData} */
    let newOrg = $state(getDefaultOrgData());
    let isCreatingOrg = $state(false);
    /** @type {string | null} */
    let createOrgError = $state(null);
    let createOrgSuccess = $state(false);

    // --- System Org Users for Admin Selection ---
    /** @type {Array<SystemUser>} */
    let systemOrgUsers = $state([]);
    let isLoadingSystemUsers = $state(false);
    /** @type {string | null} */
    let systemUsersError = $state(null);

    /**
     * Get default organization form data
     * @returns {OrgFormData}
     */
    function getDefaultOrgData() {
        return {
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
    }

    /**
     * Reset form to default state
     */
    function resetForm() {
        newOrg = getDefaultOrgData();
        createOrgError = null;
        createOrgSuccess = false;
    }

    /**
     * Fetch system organization users for admin selection
     */
    async function fetchSystemOrgUsers() {
        if (isLoadingSystemUsers) {
            return;
        }
        
        isLoadingSystemUsers = true;
        systemUsersError = null;
        
        try {
            const token = getAuthToken();
            if (!token) {
                throw new Error('Authentication token not found. Please log in again.');
            }

            const apiUrl = getApiUrl('/admin/organizations/system/users');

            const response = await axios.get(apiUrl, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (response.data && Array.isArray(response.data)) {
                systemOrgUsers = response.data;
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

    /**
     * Handle organization creation form submission
     * @param {SubmitEvent} e - The form submission event
     */
    async function handleCreateOrganization(e) {
        e.preventDefault();
        
        // Read values directly from DOM via FormData (more reliable with automated testing)
        const form = /** @type {HTMLFormElement} */ (e.target);
        const formDataObj = new FormData(form);
        const slug = /** @type {string} */ (formDataObj.get('org_slug') || '').toString().trim();
        const name = /** @type {string} */ (formDataObj.get('org_name') || '').toString().trim();
        const adminUserId = /** @type {string} */ (formDataObj.get('admin_user_id') || '').toString();
        const signupEnabled = formDataObj.get('signup_enabled') === 'on';
        const signupKey = /** @type {string} */ (formDataObj.get('signup_key') || '').toString();
        const useSystemBaseline = formDataObj.get('use_system_baseline') === 'on';
        
        // Basic form validation
        if (!slug || !name) {
            createOrgError = localeLoaded ? $_('admin.organizations.errors.fillRequired', { default: 'Please fill in all required fields.' }) : 'Please fill in all required fields.';
            return;
        }
        
        // Validate slug format (URL-friendly)
        if (!/^[a-z0-9-]+$/.test(slug)) {
            createOrgError = localeLoaded ? $_('admin.organizations.errors.slugInvalid', { default: 'Slug must contain only lowercase letters, numbers, and hyphens.' }) : 'Slug must contain only lowercase letters, numbers, and hyphens.';
            return;
        }
        
        // Validate signup key if signup is enabled
        if (signupEnabled && (!signupKey || signupKey.trim().length < 8)) {
            createOrgError = localeLoaded ? $_('admin.organizations.errors.signupKeyLength', { default: 'Signup key must be at least 8 characters long when signup is enabled.' }) : 'Signup key must be at least 8 characters long when signup is enabled.';
            return;
        }
        
        // Validate signup key format if provided
        if (signupKey && !/^[a-zA-Z0-9_-]+$/.test(signupKey)) {
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
            
            // Prepare the payload (admin_user_id is optional)
            const payload = {
                slug: slug,
                name: name,
                admin_user_id: (adminUserId && adminUserId !== 'null' && adminUserId !== '') ? parseInt(adminUserId) : null,
                signup_enabled: signupEnabled,
                signup_key: signupEnabled ? signupKey.trim() : null,
                use_system_baseline: useSystemBaseline
            };
            
            const response = await axios.post(apiUrl, payload, {
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            });
            
            if (response.data) {
                createOrgSuccess = true;
                // Wait 1.5 seconds to show success message, then close modal and refresh list
                setTimeout(() => {
                    closeModal();
                    onSuccess();
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
                createOrgError = localeLoaded 
                    ? $_('admin.organizations.errors.unknown', { default: 'An unknown error occurred while creating the organization.' })
                    : 'An unknown error occurred while creating the organization.';
            }
        } finally {
            isCreatingOrg = false;
        }
    }

    /**
     * Close the modal and reset state
     */
    function closeModal() {
        isOpen = false;
        // Clear any previous state
        createOrgError = null;
        onClose();
    }

    // Effect to fetch users and reset form when modal opens
    // Use untrack to prevent infinite loops - only track isOpen, not state inside the callbacks
    $effect(() => {
        if (isOpen) {
            untrack(() => {
                resetForm();
                fetchSystemOrgUsers();
            });
        }
    });
</script>

{#if isOpen}
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
                                    name="org_slug"
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
                                    name="org_name"
                                    class="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline" 
                                    bind:value={newOrg.name} 
                                    required 
                                />
                            </div>
                        </div>

                        <!-- Admin User Selection (Optional) -->
                        <div class="mb-4 text-left">
                            <label for="admin_user" class="block text-gray-700 text-sm font-bold mb-2">
                                Organization Admin
                                <span class="text-gray-400 font-normal text-xs ml-1">(optional)</span>
                            </label>
                            {#if isLoadingSystemUsers}
                                <div class="text-gray-500 text-sm">Loading system users...</div>
                            {:else if systemUsersError}
                                <div class="text-red-500 text-sm">{systemUsersError}</div>
                            {:else}
                                <select 
                                    id="admin_user"
                                    name="admin_user_id"
                                    class="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline"
                                    bind:value={newOrg.admin_user_id}
                                >
                                    <option value={null}>No admin (assign later)</option>
                                    {#each systemOrgUsers.filter(user => user.role !== 'admin') as user}
                                        <option value={user.id}>{user.name} ({user.email}) - {user.role}</option>
                                    {/each}
                                </select>
                            {/if}
                            <p class="text-gray-500 text-xs italic mt-1">
                                Optionally select a user from the system organization to become admin.
                                You can also create the organization without an admin and promote a member later from the organization's member list.
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
                                    <input type="checkbox" name="signup_enabled" bind:checked={newOrg.signup_enabled} class="mr-2">
                                    <span class="text-sm">Enable organization-specific signup</span>
                                </label>
                            </div>
                            
                            {#if newOrg.signup_enabled}
                                <div>
                                    <label for="signup_key" class="block text-gray-600 text-sm mb-1">Signup Key *</label>
                                    <input 
                                        type="text" 
                                        id="signup_key"
                                        name="signup_key"
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
                                <input type="checkbox" name="use_system_baseline" bind:checked={newOrg.use_system_baseline} class="mr-2">
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
                                onclick={closeModal}
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
