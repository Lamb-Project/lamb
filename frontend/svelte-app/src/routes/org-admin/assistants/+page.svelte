<script>
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { user } from '$lib/stores/userStore';
  import { getOrganizationAssistants } from '$lib/services/organizationService';
  import AssistantAccessManager from '$lib/components/AssistantAccessManager.svelte';
  
  let assistants = [];
  let loading = true;
  let errorMessage = '';
  let selectedAssistant = null;
  let showAccessModal = false;
  let searchQuery = '';
  let filterPublished = 'all'; // 'all', 'published', 'unpublished'
  
  $: if (!$user.isLoggedIn) {
    goto('/');
  }
  
  $: filteredAssistants = assistants.filter(asst => {
    // Search filter
    const matchesSearch = !searchQuery || 
      asst.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      asst.owner.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (asst.description && asst.description.toLowerCase().includes(searchQuery.toLowerCase()));
    
    // Published filter
    const matchesPublished = 
      filterPublished === 'all' ||
      (filterPublished === 'published' && asst.published) ||
      (filterPublished === 'unpublished' && !asst.published);
    
    return matchesSearch && matchesPublished;
  });
  
  onMount(async () => {
    await loadAssistants();
  });
  
  async function loadAssistants() {
    loading = true;
    errorMessage = '';
    
    try {
      const response = await getOrganizationAssistants($user.token);
      assistants = response.assistants || [];
    } catch (error) {
      errorMessage = error.message;
    } finally {
      loading = false;
    }
  }
  
  function manageAccess(assistant) {
    selectedAssistant = assistant;
    showAccessModal = true;
  }
  
  function closeAccessModal() {
    showAccessModal = false;
    selectedAssistant = null;
  }
  
  function handleAccessUpdated() {
    // Optionally reload the assistants list
    // loadAssistants();
  }
  
  function formatDate(timestamp) {
    if (!timestamp) return 'N/A';
    return new Date(timestamp * 1000).toLocaleDateString();
  }
</script>

<svelte:head>
  <title>Organization Assistants - LAMB</title>
</svelte:head>

<div class="container">
  <div class="header">
    <h1>Organization Assistants</h1>
    <p class="subtitle">View and manage access to all assistants in your organization</p>
  </div>
  
  <div class="controls">
    <div class="search-box">
      <input
        type="text"
        placeholder="Search assistants..."
        bind:value={searchQuery}
        class="search-input"
      />
    </div>
    
    <div class="filter-box">
      <label for="filter-published">Filter:</label>
      <select id="filter-published" bind:value={filterPublished} class="filter-select">
        <option value="all">All Assistants</option>
        <option value="published">Published Only</option>
        <option value="unpublished">Unpublished Only</option>
      </select>
    </div>
    
    <button class="btn-refresh" on:click={loadAssistants} disabled={loading}>
      {loading ? 'Loading...' : 'Refresh'}
    </button>
  </div>
  
  {#if errorMessage}
    <div class="error-message">
      {errorMessage}
    </div>
  {/if}
  
  {#if loading}
    <div class="loading">Loading assistants...</div>
  {:else if filteredAssistants.length === 0}
    <div class="empty-state">
      {#if searchQuery || filterPublished !== 'all'}
        <p>No assistants match your search criteria.</p>
        <button class="btn-secondary" on:click={() => { searchQuery = ''; filterPublished = 'all'; }}>
          Clear Filters
        </button>
      {:else}
        <p>No assistants found in your organization.</p>
      {/if}
    </div>
  {:else}
    <div class="assistants-table-container">
      <table class="assistants-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Description</th>
            <th>Owner</th>
            <th>Status</th>
            <th>Created</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {#each filteredAssistants as assistant}
            <tr>
              <td class="name-cell">{assistant.name}</td>
              <td class="description-cell">
                {assistant.description || '—'}
              </td>
              <td class="owner-cell">{assistant.owner}</td>
              <td>
                {#if assistant.published}
                  <span class="badge badge-published">Published</span>
                {:else}
                  <span class="badge badge-unpublished">Unpublished</span>
                {/if}
              </td>
              <td class="date-cell">{formatDate(assistant.created_at)}</td>
              <td class="actions-cell">
                <button
                  class="btn-action"
                  on:click={() => manageAccess(assistant)}
                  title="Manage user access"
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
</div>

<AssistantAccessManager
  assistant={selectedAssistant}
  bind:show={showAccessModal}
  on:close={closeAccessModal}
  on:updated={handleAccessUpdated}
/>

<style>
  .container {
    max-width: 1400px;
    margin: 0 auto;
    padding: 2rem;
  }
  
  .header {
    margin-bottom: 2rem;
  }
  
  .header h1 {
    font-size: 2rem;
    font-weight: 700;
    color: #111827;
    margin: 0 0 0.5rem 0;
  }
  
  .subtitle {
    color: #6b7280;
    margin: 0;
  }
  
  .controls {
    display: flex;
    gap: 1rem;
    margin-bottom: 1.5rem;
    flex-wrap: wrap;
    align-items: center;
  }
  
  .search-box {
    flex: 1;
    min-width: 200px;
  }
  
  .search-input {
    width: 100%;
    padding: 0.5rem 1rem;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    font-size: 1rem;
  }
  
  .search-input:focus {
    outline: none;
    border-color: #3b82f6;
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
  }
  
  .filter-box {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  
  .filter-box label {
    font-weight: 500;
    color: #374151;
  }
  
  .filter-select {
    padding: 0.5rem 1rem;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    font-size: 1rem;
    background-color: white;
    cursor: pointer;
  }
  
  .filter-select:focus {
    outline: none;
    border-color: #3b82f6;
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
  }
  
  .btn-refresh {
    padding: 0.5rem 1.5rem;
    background-color: #3b82f6;
    color: white;
    border: none;
    border-radius: 6px;
    font-weight: 500;
    cursor: pointer;
    transition: background-color 0.2s;
  }
  
  .btn-refresh:hover:not(:disabled) {
    background-color: #2563eb;
  }
  
  .btn-refresh:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  
  .error-message {
    padding: 1rem;
    background-color: #fee2e2;
    border: 1px solid #ef4444;
    border-radius: 6px;
    color: #991b1b;
    margin-bottom: 1.5rem;
  }
  
  .loading {
    text-align: center;
    padding: 3rem;
    color: #6b7280;
    font-size: 1.125rem;
  }
  
  .empty-state {
    text-align: center;
    padding: 3rem;
    background-color: #f9fafb;
    border-radius: 8px;
    color: #6b7280;
  }
  
  .empty-state p {
    margin-bottom: 1rem;
  }
  
  .btn-secondary {
    padding: 0.5rem 1.5rem;
    background-color: #f3f4f6;
    color: #374151;
    border: none;
    border-radius: 6px;
    font-weight: 500;
    cursor: pointer;
  }
  
  .btn-secondary:hover {
    background-color: #e5e7eb;
  }
  
  .assistants-table-container {
    background: white;
    border-radius: 8px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
    overflow-x: auto;
  }
  
  .assistants-table {
    width: 100%;
    border-collapse: collapse;
  }
  
  .assistants-table thead {
    background-color: #f9fafb;
  }
  
  .assistants-table th {
    padding: 1rem;
    text-align: left;
    font-weight: 600;
    color: #374151;
    border-bottom: 2px solid #e5e7eb;
  }
  
  .assistants-table tbody tr {
    border-bottom: 1px solid #e5e7eb;
    transition: background-color 0.2s;
  }
  
  .assistants-table tbody tr:hover {
    background-color: #f9fafb;
  }
  
  .assistants-table td {
    padding: 1rem;
  }
  
  .name-cell {
    font-weight: 500;
    color: #111827;
  }
  
  .description-cell {
    color: #6b7280;
    max-width: 300px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  
  .owner-cell {
    color: #374151;
    font-family: monospace;
    font-size: 0.875rem;
  }
  
  .date-cell {
    color: #6b7280;
    font-size: 0.875rem;
  }
  
  .badge {
    display: inline-block;
    padding: 0.25rem 0.75rem;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 500;
  }
  
  .badge-published {
    background-color: #d1fae5;
    color: #065f46;
  }
  
  .badge-unpublished {
    background-color: #fee2e2;
    color: #991b1b;
  }
  
  .actions-cell {
    text-align: right;
  }
  
  .btn-action {
    padding: 0.5rem 1rem;
    background-color: #3b82f6;
    color: white;
    border: none;
    border-radius: 6px;
    font-weight: 500;
    cursor: pointer;
    font-size: 0.875rem;
    transition: background-color 0.2s;
  }
  
  .btn-action:hover {
    background-color: #2563eb;
  }
</style>

