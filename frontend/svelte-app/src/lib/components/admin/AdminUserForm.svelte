<script>
    import { _ } from '$lib/i18n';
    
    /**
     * @typedef {Object} NewUserData
     * @property {string} email
     * @property {string} name
     * @property {string} password
     * @property {string} [role]
     * @property {string} user_type
     * @property {number|null} [organization_id]
     */
    
    /**
     * @typedef {Object} Organization
     * @property {number} id
     * @property {string} name
     * @property {boolean} [is_system]
     */
    
    /** @type {{ 
     *   isOpen?: boolean, 
     *   newUser?: NewUserData, 
     *   organizations?: Organization[], 
     *   isLoadingOrganizations?: boolean, 
     *   organizationsError?: string | null,
     *   isCreating?: boolean, 
     *   error?: string | null, 
     *   success?: boolean, 
     *   localeLoaded?: boolean,
     *   onSubmit?: (e: Event) => void,
     *   onClose?: () => void,
     *   onUserChange?: (user: NewUserData) => void
     * }} */
    let { 
        isOpen = false,
        newUser = { email: '', name: '', password: '', role: 'user', user_type: 'creator', organization_id: null },
        organizations = [],
        isLoadingOrganizations = false,
        organizationsError = null,
        isCreating = false,
        error = null,
        success = false,
        localeLoaded = true,
        onSubmit = () => {},
        onClose = () => {},
        onUserChange = () => {}
    } = $props();
    
    /**
     * Handle role change - auto-set user_type for admins
     * @param {Event} e
     */
    function handleRoleChange(e) {
        const target = /** @type {HTMLSelectElement} */ (e.target);
        if (target.value === 'admin') {
            onUserChange({ ...newUser, role: target.value, user_type: 'creator' });
        } else {
            onUserChange({ ...newUser, role: target.value });
        }
    }
</script>

{#if isOpen}
    <div class="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50 flex items-center justify-center">
        <div class="relative mx-auto p-5 border w-full max-w-md shadow-lg rounded-md bg-white">
            <div class="mt-3 text-center">
                <h3 class="text-lg leading-6 font-medium text-gray-900">
                    {localeLoaded ? $_('admin.users.create.title', { default: 'Create New User' }) : 'Create New User'}
                </h3>
                
                {#if success}
                    <div class="mt-4 bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded relative" role="alert">
                        <span class="block sm:inline">{localeLoaded ? $_('admin.users.create.success', { default: 'User created successfully!' }) : 'User created successfully!'}</span>
                    </div>
                {:else}
                    <form class="mt-4" onsubmit={onSubmit}>
                        {#if error}
                            <div class="mb-4 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative" role="alert">
                                <span class="block sm:inline">{error}</span>
                            </div>
                        {/if}
                        
                        <div class="mb-4 text-left">
                            <label for="email" class="block text-gray-700 text-sm font-bold mb-2">
                                {localeLoaded ? $_('admin.users.create.email', { default: 'Email' }) : 'Email'} *
                            </label>
                            <input 
                                type="email" 
                                id="email" 
                                name="email"
                                class="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline" 
                                value={newUser.email}
                                oninput={(e) => onUserChange({ ...newUser, email: /** @type {HTMLInputElement} */ (e.target).value })}
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
                                name="name"
                                class="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline" 
                                value={newUser.name}
                                oninput={(e) => onUserChange({ ...newUser, name: /** @type {HTMLInputElement} */ (e.target).value })}
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
                                name="password"
                                class="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline" 
                                value={newUser.password}
                                oninput={(e) => onUserChange({ ...newUser, password: /** @type {HTMLInputElement} */ (e.target).value })}
                                required 
                            />
                        </div>
                        
                        <div class="mb-4 text-left">
                            <label for="role" class="block text-gray-700 text-sm font-bold mb-2">
                                {localeLoaded ? $_('admin.users.create.role', { default: 'Role' }) : 'Role'}
                            </label>
                            <select 
                                id="role" 
                                name="role"
                                class="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline" 
                                value={newUser.role}
                                onchange={handleRoleChange}
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
                                name="user_type"
                                class="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline" 
                                value={newUser.user_type}
                                onchange={(e) => onUserChange({ ...newUser, user_type: /** @type {HTMLSelectElement} */ (e.target).value })}
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
                            {#if isLoadingOrganizations}
                                <div class="text-gray-500 text-sm">Loading organizations...</div>
                            {:else if organizationsError}
                                <div class="text-red-500 text-sm">{organizationsError}</div>
                            {:else}
                                <select 
                                    id="organization" 
                                    name="organization_id"
                                    class="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline" 
                                    value={newUser.organization_id}
                                    onchange={(e) => {
                                        const val = /** @type {HTMLSelectElement} */ (e.target).value;
                                        onUserChange({ ...newUser, organization_id: val ? parseInt(val, 10) : null });
                                    }}
                                >
                                    <option value="">Select an organization (optional)</option>
                                    {#each organizations as org}
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
                                onclick={onClose}
                                class="bg-gray-300 hover:bg-gray-400 text-gray-800 py-2 px-4 rounded focus:outline-none focus:shadow-outline" 
                            >
                                {localeLoaded ? $_('admin.users.create.cancel', { default: 'Cancel' }) : 'Cancel'}
                            </button>
                            <button 
                                type="submit" 
                                class="bg-brand text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline disabled:opacity-50"
                                disabled={isCreating}
                            >
                                {isCreating 
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
