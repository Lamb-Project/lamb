<script>
  import { createEventDispatcher } from 'svelte';
  import { getAssistantAccess, updateAssistantAccess } from '$lib/services/organizationService';
  import { user } from '$lib/stores/userStore';
  
  export let assistant = null;
  export let show = false;
  
  const dispatch = createEventDispatcher();
  
  let loading = false;
  let accessInfo = null;
  let selectedUsers = new Set();
  let errorMessage = '';
  let successMessage = '';
  
  $: if (show && assistant) {
    loadAccessInfo();
  }
  
  $: if (!show) {
    // Reset state when modal closes
    resetState();
  }
  
  async function loadAccessInfo() {
    loading = true;
    errorMessage = '';
    
    try {
      accessInfo = await getAssistantAccess($user.token, assistant.id);
      
      // Initialize selected users with current access
      selectedUsers = new Set(accessInfo.users_with_access);
    } catch (error) {
      errorMessage = error.message;
    } finally {
      loading = false;
    }
  }
  
  function toggleUser(email) {
    const newSet = new Set(selectedUsers);
    if (newSet.has(email)) {
      newSet.delete(email);
    } else {
      newSet.add(email);
    }
    selectedUsers = newSet;
  }
  
  async function saveChanges() {
    if (!accessInfo) return;
    
    loading = true;
    errorMessage = '';
    successMessage = '';
    
    try {
      const currentAccess = new Set(accessInfo.users_with_access);
      const newAccess = selectedUsers;
      
      // Find users to add and remove
      const usersToAdd = [...newAccess].filter(email => !currentAccess.has(email));
      const usersToRemove = [...currentAccess].filter(email => !newAccess.has(email));
      
      // Perform grant operations
      if (usersToAdd.length > 0) {
        await updateAssistantAccess(
          $user.token,
          assistant.id,
          usersToAdd,
          'grant'
        );
      }
      
      // Perform revoke operations
      if (usersToRemove.length > 0) {
        await updateAssistantAccess(
          $user.token,
          assistant.id,
          usersToRemove,
          'revoke'
        );
      }
      
      successMessage = 'Access updated successfully';
      
      // Refresh access info
      await loadAccessInfo();
      
      // Notify parent component
      dispatch('updated');
      
      // Close modal after a short delay
      setTimeout(() => {
        close();
      }, 1500);
    } catch (error) {
      errorMessage = error.message;
    } finally {
      loading = false;
    }
  }
  
  function close() {
    dispatch('close');
  }
  
  function resetState() {
    accessInfo = null;
    selectedUsers = new Set();
    errorMessage = '';
    successMessage = '';
  }
  
  function getUserTypeLabel(userType) {
    return userType === 'creator' ? 'Creator' : 'End User';
  }
</script>

{#if show && assistant}
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div class="modal-overlay" onclick={close} role="presentation">
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <!-- svelte-ignore a11y-no-static-element-interactions -->
    <div class="modal-content" onclick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-labelledby="modal-title" tabindex="-1">
      <div class="modal-header">
        <h2 id="modal-title">Manage Access: {assistant.name}</h2>
        <button class="close-btn" onclick={close}>&times;</button>
      </div>
      
      <div class="modal-body">
        {#if loading && !accessInfo}
          <div class="loading">Loading...</div>
        {:else if errorMessage}
          <div class="error-message">{errorMessage}</div>
        {:else if accessInfo}
          <div class="assistant-info">
            <p><strong>Owner:</strong> {accessInfo.assistant.owner}</p>
          </div>
          
          {#if successMessage}
            <div class="success-message">{successMessage}</div>
          {/if}
          
          <div class="users-list">
            <h3>Select users with access:</h3>
            <div class="users-grid">
              {#each accessInfo.organization_users as user}
                <label class="user-item" class:is-owner={user.is_owner}>
                  <input
                    type="checkbox"
                    checked={selectedUsers.has(user.email)}
                    disabled={user.is_owner || loading}
                    onchange={() => toggleUser(user.email)}
                  />
                  <div class="user-info">
                    <span class="user-name">{user.name}</span>
                    <span class="user-email">{user.email}</span>
                    <span class="user-type-badge">{getUserTypeLabel(user.user_type)}</span>
                    {#if user.is_owner}
                      <span class="owner-badge">Owner</span>
                    {/if}
                  </div>
                </label>
              {/each}
            </div>
          </div>
        {/if}
      </div>
      
      <div class="modal-footer">
        <button class="btn btn-secondary" onclick={close} disabled={loading}>
          Cancel
        </button>
        <button 
          class="btn btn-primary" 
          onclick={saveChanges}
          disabled={loading || !accessInfo}
        >
          {loading ? 'Saving...' : 'Save Changes'}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  }
  
  .modal-content {
    background: white;
    border-radius: 8px;
    max-width: 600px;
    width: 90%;
    max-height: 80vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  }
  
  .modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1.5rem;
    border-bottom: 1px solid #e5e7eb;
  }
  
  .modal-header h2 {
    margin: 0;
    font-size: 1.5rem;
    color: #111827;
  }
  
  .close-btn {
    background: none;
    border: none;
    font-size: 2rem;
    color: #6b7280;
    cursor: pointer;
    padding: 0;
    width: 2rem;
    height: 2rem;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  
  .close-btn:hover {
    color: #111827;
  }
  
  .modal-body {
    padding: 1.5rem;
    overflow-y: auto;
    flex: 1;
  }
  
  .assistant-info {
    margin-bottom: 1.5rem;
    padding: 1rem;
    background-color: #f9fafb;
    border-radius: 6px;
  }
  
  .assistant-info p {
    margin: 0.5rem 0;
  }
  
  .error-message {
    padding: 1rem;
    background-color: #fee2e2;
    border: 1px solid #ef4444;
    border-radius: 6px;
    color: #991b1b;
    margin-bottom: 1rem;
  }
  
  .success-message {
    padding: 1rem;
    background-color: #d1fae5;
    border: 1px solid #10b981;
    border-radius: 6px;
    color: #065f46;
    margin-bottom: 1rem;
  }
  
  .loading {
    text-align: center;
    padding: 2rem;
    color: #6b7280;
  }
  
  .users-list h3 {
    margin: 0 0 1rem 0;
    font-size: 1.125rem;
    color: #111827;
  }
  
  .users-grid {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  
  .user-item {
    display: flex;
    align-items: center;
    padding: 0.75rem;
    border: 1px solid #e5e7eb;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.2s;
  }
  
  .user-item:hover {
    background-color: #f9fafb;
    border-color: #3b82f6;
  }
  
  .user-item.is-owner {
    background-color: #eff6ff;
    border-color: #3b82f6;
  }
  
  .user-item input[type="checkbox"] {
    margin-right: 0.75rem;
    width: 1.25rem;
    height: 1.25rem;
    cursor: pointer;
  }
  
  .user-item input[type="checkbox"]:disabled {
    cursor: not-allowed;
    opacity: 0.5;
  }
  
  .user-info {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    flex: 1;
  }
  
  .user-name {
    font-weight: 500;
    color: #111827;
  }
  
  .user-email {
    font-size: 0.875rem;
    color: #6b7280;
  }
  
  .user-type-badge,
  .owner-badge {
    display: inline-block;
    padding: 0.125rem 0.5rem;
    border-radius: 0.25rem;
    font-size: 0.75rem;
    font-weight: 500;
    margin-top: 0.25rem;
    width: fit-content;
  }
  
  .user-type-badge {
    background-color: #dbeafe;
    color: #1e40af;
  }
  
  .owner-badge {
    background-color: #fef3c7;
    color: #92400e;
  }
  
  .modal-footer {
    display: flex;
    justify-content: flex-end;
    gap: 1rem;
    padding: 1.5rem;
    border-top: 1px solid #e5e7eb;
  }
  
  .btn {
    padding: 0.5rem 1.5rem;
    border-radius: 6px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
    border: none;
    font-size: 1rem;
  }
  
  .btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  
  .btn-primary {
    background-color: #3b82f6;
    color: white;
  }
  
  .btn-primary:hover:not(:disabled) {
    background-color: #2563eb;
  }
  
  .btn-secondary {
    background-color: #f3f4f6;
    color: #374151;
  }
  
  .btn-secondary:hover:not(:disabled) {
    background-color: #e5e7eb;
  }
</style>

