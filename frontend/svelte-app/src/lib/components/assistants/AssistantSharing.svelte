<script>
    import { onMount } from 'svelte';
    import { browser } from '$app/environment';
    import { _ } from '$lib/i18n';
    import { getApiUrl } from '$lib/config';
    
    // ✅ CORRECT: Props using $props()
    let { 
        assistant = null, 
        token = '', 
        currentUserEmail = '' 
    } = $props();
    
    // ✅ CORRECT: State using $state()
    let organizationUsers = $state([]);
    let sharedUsers = $state([]);
    let selectedUsers = $state([]);
    let ltiUsers = $state([]);
    let showLtiUsers = $state(false);
    let loading = $state(false);
    let loadingUsers = $state(false);
    let errorMessage = $state('');
    let successMessage = $state('');
    let canShare = $state(true);
    let checkingPermission = $state(true);
    
    // ✅ CORRECT: Browser guard
    onMount(() => {
        if (browser && assistant) {
            checkSharingPermission();
            loadSharedUsers();
            loadOrganizationUsers();
        }
    });
    
    // Check if sharing is enabled for organization
    async function checkSharingPermission() {
        if (!browser || !token) return;
        
        checkingPermission = true;
        try {
            const apiUrl = getApiUrl('/creator/lamb/assistant-sharing/check-permission');
            const response = await fetch(apiUrl, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            
            if (!response.ok) {
                throw new Error('Failed to check sharing permission');
            }
            
            const data = await response.json();
            canShare = data.can_share ?? true;
        } catch (error) {
            console.error('Error checking sharing permission:', error);
            canShare = true; // Default to true on error
        } finally {
            checkingPermission = false;
        }
    }
    
    // Load users the assistant is currently shared with
    async function loadSharedUsers() {
        if (!browser || !token || !assistant?.id) return;
        
        loading = true;
        errorMessage = '';
        try {
            const apiUrl = getApiUrl(`/creator/lamb/assistant-sharing/shares/${assistant.id}`);
            const response = await fetch(apiUrl, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            
            if (!response.ok) {
                throw new Error('Failed to load shared users');
            }
            
            const data = await response.json();
            sharedUsers = data.shares || [];
        } catch (error) {
            console.error('Error loading shared users:', error);
            errorMessage = $_('error_loading_shares') || 'Error loading shared users';
        } finally {
            loading = false;
        }
    }
    
    // Load organization users for sharing selection
    async function loadOrganizationUsers() {
        if (!browser || !token) return;
        
        loadingUsers = true;
        try {
            const apiUrl = getApiUrl('/creator/lamb/assistant-sharing/organization-users');
            const response = await fetch(apiUrl, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            
            if (!response.ok) {
                throw new Error('Failed to load organization users');
            }
            
            const users = await response.json();
            organizationUsers = users || [];
        } catch (error) {
            console.error('Error loading organization users:', error);
            errorMessage = $_('error_loading_users') || 'Error loading organization users';
        } finally {
            loadingUsers = false;
        }
    }
    
    // Load LTI users who have accessed the assistant
    async function loadLtiUsers() {
        if (!browser || !token || !assistant?.id) return;
        
        loading = true;
        errorMessage = '';
        try {
            const apiUrl = getApiUrl(`/creator/lamb/assistant-sharing/lti-users/${assistant.id}`);
            const response = await fetch(apiUrl, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            
            if (!response.ok) {
                throw new Error('Failed to load LTI users');
            }
            
            const data = await response.json();
            ltiUsers = data.lti_users || [];
        } catch (error) {
            console.error('Error loading LTI users:', error);
            errorMessage = $_('error_loading_lti_users') || 'Error loading LTI users';
        } finally {
            loading = false;
        }
    }
    
    // Share assistant with selected users
    async function handleShare() {
        if (!browser || !token || !assistant?.id || selectedUsers.length === 0) return;
        
        loading = true;
        errorMessage = '';
        successMessage = '';
        
        try {
            const apiUrl = getApiUrl('/creator/lamb/assistant-sharing/share');
            const response = await fetch(apiUrl, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    assistant_id: assistant.id,
                    user_ids: selectedUsers
                })
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to share assistant');
            }
            
            const result = await response.json();
            successMessage = $_('share_success', { values: { count: result.shared_count } }) || 
                           `Successfully shared with ${result.shared_count} user(s)`;
            
            // Reload shared users and clear selection
            await loadSharedUsers();
            selectedUsers = [];
            
            // Clear success message after 3 seconds
            setTimeout(() => { successMessage = ''; }, 3000);
        } catch (error) {
            console.error('Error sharing assistant:', error);
            errorMessage = error.message || ($_('error_sharing') || 'Error sharing assistant');
        } finally {
            loading = false;
        }
    }
    
    // Unshare assistant from specific user
    async function handleUnshare(userId) {
        if (!browser || !token || !assistant?.id) return;
        
        loading = true;
        errorMessage = '';
        successMessage = '';
        
        try {
            const apiUrl = getApiUrl('/creator/lamb/assistant-sharing/unshare');
            const response = await fetch(apiUrl, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    assistant_id: assistant.id,
                    user_ids: [userId]
                })
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to unshare assistant');
            }
            
            successMessage = $_('unshare_success') || 'Successfully removed access';
            
            // Reload shared users
            await loadSharedUsers();
            
            // Clear success message after 3 seconds
            setTimeout(() => { successMessage = ''; }, 3000);
        } catch (error) {
            console.error('Error unsharing assistant:', error);
            errorMessage = error.message || ($_('error_unsharing') || 'Error removing access');
        } finally {
            loading = false;
        }
    }
    
    // Toggle checkbox for user selection
    function toggleUserSelection(userId) {
        if (selectedUsers.includes(userId)) {
            selectedUsers = selectedUsers.filter(id => id !== userId);
        } else {
            selectedUsers = [...selectedUsers, userId];
        }
    }
    
    // Toggle LTI users visibility
    async function toggleLtiUsers() {
        showLtiUsers = !showLtiUsers;
        if (showLtiUsers && ltiUsers.length === 0) {
            await loadLtiUsers();
        }
    }
</script>

<div class="assistant-sharing-container p-4">
    {#if checkingPermission}
        <div class="text-center py-4">
            <span class="loading loading-spinner loading-md"></span>
            <p class="text-sm text-gray-600 mt-2">{$_('checking_permissions') || 'Checking permissions...'}</p>
        </div>
    {:else if !canShare}
        <div class="alert alert-warning">
            <svg xmlns="http://www.w3.org/2000/svg" class="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <span>{$_('sharing_not_enabled') || 'Sharing is not enabled for your organization'}</span>
        </div>
    {:else}
        <!-- Success/Error Messages -->
        {#if successMessage}
            <div class="alert alert-success mb-4">
                <svg xmlns="http://www.w3.org/2000/svg" class="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span>{successMessage}</span>
            </div>
        {/if}
        
        {#if errorMessage}
            <div class="alert alert-error mb-4">
                <svg xmlns="http://www.w3.org/2000/svg" class="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span>{errorMessage}</span>
            </div>
        {/if}
        
        <!-- Current Shares Section -->
        <div class="mb-6">
            <h3 class="text-lg font-semibold mb-3">{$_('current_shares') || 'Current Shares'}</h3>
            {#if loading && sharedUsers.length === 0}
                <div class="flex justify-center py-4">
                    <span class="loading loading-spinner loading-md"></span>
                </div>
            {:else if sharedUsers.length === 0}
                <p class="text-gray-500 text-sm">{$_('no_shares_yet') || 'This assistant is not shared with anyone yet'}</p>
            {:else}
                <div class="overflow-x-auto">
                    <table class="table table-zebra w-full">
                        <thead>
                            <tr>
                                <th>{$_('user_name') || 'Name'}</th>
                                <th>{$_('email') || 'Email'}</th>
                                <th>{$_('shared_at') || 'Shared At'}</th>
                                <th>{$_('actions') || 'Actions'}</th>
                            </tr>
                        </thead>
                        <tbody>
                            {#each sharedUsers as share}
                                <tr>
                                    <td>{share.user_name}</td>
                                    <td>{share.user_email}</td>
                                    <td>{new Date(share.shared_at * 1000).toLocaleDateString()}</td>
                                    <td>
                                        <button 
                                            class="btn btn-sm btn-error"
                                            onclick={() => handleUnshare(share.user_id)}
                                            disabled={loading}
                                        >
                                            {$_('remove') || 'Remove'}
                                        </button>
                                    </td>
                                </tr>
                            {/each}
                        </tbody>
                    </table>
                </div>
            {/if}
        </div>
        
        <div class="divider"></div>
        
        <!-- Share with Organization Users Section -->
        <div class="mb-6">
            <h3 class="text-lg font-semibold mb-3">{$_('share_with_users') || 'Share with Organization Users'}</h3>
            {#if loadingUsers}
                <div class="flex justify-center py-4">
                    <span class="loading loading-spinner loading-md"></span>
                </div>
            {:else if organizationUsers.length === 0}
                <p class="text-gray-500 text-sm">{$_('no_users_to_share') || 'No other users in your organization'}</p>
            {:else}
                <div class="bg-base-200 p-4 rounded-lg max-h-96 overflow-y-auto">
                    {#each organizationUsers as user}
                        {@const isAlreadyShared = sharedUsers.some(s => s.user_id === user.id)}
                        <div class="form-control">
                            <label class="label cursor-pointer justify-start gap-3">
                                <input 
                                    type="checkbox" 
                                    class="checkbox checkbox-primary"
                                    checked={selectedUsers.includes(user.id)}
                                    disabled={isAlreadyShared || loading}
                                    onchange={() => toggleUserSelection(user.id)}
                                />
                                <div class="flex-1">
                                    <span class="label-text font-medium">{user.name}</span>
                                    <span class="label-text text-gray-500 ml-2">({user.email})</span>
                                    {#if user.user_type === 'end_user'}
                                        <span class="badge badge-sm badge-secondary ml-2">{$_('end_user') || 'End User'}</span>
                                    {/if}
                                    {#if isAlreadyShared}
                                        <span class="badge badge-sm badge-success ml-2">{$_('already_shared') || 'Already Shared'}</span>
                                    {/if}
                                </div>
                            </label>
                        </div>
                    {/each}
                </div>
                
                {#if selectedUsers.length > 0}
                    <div class="mt-4">
                        <button 
                            class="btn btn-primary"
                            onclick={handleShare}
                            disabled={loading}
                        >
                            {#if loading}
                                <span class="loading loading-spinner loading-sm"></span>
                            {/if}
                            {$_('share_with_selected', { values: { count: selectedUsers.length } }) || `Share with ${selectedUsers.length} user(s)`}
                        </button>
                    </div>
                {/if}
            {/if}
        </div>
        
        <!-- LTI Users Section (Collapsible) -->
        {#if assistant?.published}
            <div class="divider"></div>
            
            <div class="mb-4">
                <button 
                    class="btn btn-outline btn-sm"
                    onclick={toggleLtiUsers}
                >
                    {showLtiUsers ? '▼' : '▶'} {$_('lti_users') || 'LTI Users'} ({ltiUsers.length})
                </button>
                
                {#if showLtiUsers}
                    <div class="mt-4">
                        {#if loading && ltiUsers.length === 0}
                            <div class="flex justify-center py-4">
                                <span class="loading loading-spinner loading-md"></span>
                            </div>
                        {:else if ltiUsers.length === 0}
                            <p class="text-gray-500 text-sm">{$_('no_lti_users') || 'No LTI users have accessed this assistant yet'}</p>
                        {:else}
                            <div class="overflow-x-auto">
                                <table class="table table-zebra w-full">
                                    <thead>
                                        <tr>
                                            <th>{$_('user_name') || 'Name'}</th>
                                            <th>{$_('email') || 'Email'}</th>
                                            <th>{$_('role') || 'Role'}</th>
                                            <th>{$_('first_access') || 'First Access'}</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {#each ltiUsers as ltiUser}
                                            <tr>
                                                <td>{ltiUser.user_display_name}</td>
                                                <td>{ltiUser.user_email}</td>
                                                <td>
                                                    <span class="badge badge-sm">
                                                        {ltiUser.user_role || 'student'}
                                                    </span>
                                                </td>
                                                <td>{new Date(ltiUser.created_at * 1000).toLocaleDateString()}</td>
                                            </tr>
                                        {/each}
                                    </tbody>
                                </table>
                            </div>
                        {/if}
                    </div>
                {/if}
            </div>
        {/if}
    {/if}
</div>

<style>
    .assistant-sharing-container {
        max-width: 100%;
    }
</style>
