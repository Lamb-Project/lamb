<script>
    import { _ } from '$lib/i18n';
    
    /**
     * Shared Change Password Modal
     * Works for both super-admin and org-admin contexts
     */
    
    /**
     * @typedef {Object} PasswordChangeData
     * @property {string} [email]
     * @property {string} [user_name]
     * @property {string} [user_email]
     * @property {number|null} [user_id]
     * @property {string} new_password
     */
    
    /** @type {{
     *   isOpen?: boolean,
     *   userName?: string,
     *   userEmail?: string,
     *   newPassword?: string,
     *   isChanging?: boolean,
     *   error?: string | null,
     *   success?: boolean,
     *   localeLoaded?: boolean,
     *   onSubmit?: (e: Event) => void,
     *   onClose?: () => void,
     *   onPasswordChange?: (password: string) => void
     * }} */
    let {
        isOpen = false,
        userName = '',
        userEmail = '',
        newPassword = '',
        isChanging = false,
        error = null,
        success = false,
        localeLoaded = true,
        onSubmit = () => {},
        onClose = () => {},
        onPasswordChange = () => {}
    } = $props();
</script>

{#if isOpen}
    <div class="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50 flex items-center justify-center" role="dialog" aria-modal="true">
        <div class="relative mx-auto p-5 border w-full max-w-md shadow-lg rounded-md bg-white">
            <div class="mt-3 text-center">
                <h3 class="text-lg leading-6 font-medium text-gray-900">
                    {localeLoaded ? $_('admin.users.password.title', { default: 'Change Password' }) : 'Change Password'}
                </h3>
                <p class="text-sm text-gray-500 mt-1">
                    {localeLoaded 
                        ? $_('admin.users.password.subtitle', { default: 'Set a new password for' }) 
                        : 'Set a new password for'} {userName}
                    {#if userEmail}
                        <span class="block text-gray-400">({userEmail})</span>
                    {/if}
                </p>
                
                {#if success}
                    <div class="mt-4 bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded relative" role="alert">
                        <span class="block sm:inline">{localeLoaded ? $_('admin.users.password.success', { default: 'Password changed successfully!' }) : 'Password changed successfully!'}</span>
                    </div>
                {:else}
                    <form class="mt-4" onsubmit={onSubmit}>
                        {#if error}
                            <div class="mb-4 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative" role="alert">
                                <span class="block sm:inline">{error}</span>
                            </div>
                        {/if}
                        
                        <!-- Email field (readonly, for reference) -->
                        {#if userEmail}
                            <div class="mb-4 text-left">
                                <label for="pwd-email" class="block text-gray-700 text-sm font-bold mb-2">
                                    {localeLoaded ? $_('admin.users.password.email', { default: 'Email' }) : 'Email'}
                                </label>
                                <input 
                                    type="email" 
                                    id="pwd-email" 
                                    class="shadow appearance-none border rounded w-full py-2 px-3 text-gray-500 bg-gray-100 leading-tight" 
                                    value={userEmail} 
                                    disabled
                                    readonly
                                />
                            </div>
                        {/if}
                        
                        <div class="mb-6 text-left">
                            <label for="pwd-new-password" class="block text-gray-700 text-sm font-bold mb-2">
                                {localeLoaded ? $_('admin.users.password.newPassword', { default: 'New Password' }) : 'New Password'} *
                            </label>
                            <input 
                                type="password" 
                                id="pwd-new-password" 
                                class="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline" 
                                value={newPassword}
                                oninput={(e) => onPasswordChange(/** @type {HTMLInputElement} */ (e.target).value)}
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
                                onclick={onClose}
                                class="bg-gray-300 hover:bg-gray-400 text-gray-800 py-2 px-4 rounded focus:outline-none focus:shadow-outline" 
                            >
                                {localeLoaded ? $_('common.cancel', { default: 'Cancel' }) : 'Cancel'}
                            </button>
                            <button
                                type="submit"
                                class="bg-brand text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline disabled:opacity-50"
                                disabled={isChanging}
                            >
                                {isChanging 
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
