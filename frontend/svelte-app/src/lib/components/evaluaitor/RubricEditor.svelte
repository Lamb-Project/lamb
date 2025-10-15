<script>
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { rubricStore } from '$lib/stores/rubricStore.svelte.js';
  import {
    fetchRubric,
    createRubric,
    updateRubric,
    aiGenerateRubric,
    aiModifyRubric
  } from '$lib/services/rubricService';
  import RubricTable from './RubricTable.svelte';
  import RubricMetadataForm from './RubricMetadataForm.svelte';
  import RubricAIChat from './RubricAIChat.svelte';

  // Props
  let { rubricId } = $props();

  // Local state
  let loading = $state(true);
  let saving = $state(false);
  let error = $state(null);
  let showAIChat = $state(false);
  let aiGenerating = $state(false);

  // Check if this is a new rubric (generated from template)
  let isNewRubric = $state(false);

  // Check if we're in edit mode - default to false (view mode)
  let isEditMode = $state(false);

  // Check URL params for edit mode
  $effect(() => {
    const urlParams = new URLSearchParams($page.url.search);
    if (urlParams.has('edit')) {
      isEditMode = urlParams.get('edit') === 'true';
    }
  });

  // Enter edit mode
  function enterEditMode() {
    isEditMode = true;
  }

  // Cancel edit mode (reload rubric to discard changes)
  function cancelEdit() {
    if (confirm('Discard all changes and exit edit mode?')) {
      loadRubric(); // Reload from backend to discard changes
      isEditMode = false;
    }
  }

  // Load rubric data
  async function loadRubric() {
    if (!rubricId) {
      error = 'No rubric ID provided';
      loading = false;
      return;
    }

    try {
      loading = true;
      const rubricData = await fetchRubric(rubricId);
      rubricStore.loadRubric(rubricData.rubric_data);
    } catch (err) {
      error = err.message || 'Failed to load rubric';
      console.error('Error loading rubric:', err);
    } finally {
      loading = false;
    }
  }

  // Save rubric
  async function saveRubric() {
    const rubricData = rubricStore.getRubricData();
    if (!rubricData) {
      error = 'No rubric data to save';
      return;
    }

    // Validate rubric
    const validation = rubricStore.validate();
    if (!validation.isValid) {
      error = `Validation errors: ${validation.errors.join(', ')}`;
      return;
    }

    try {
      saving = true;
      error = null;

      // Prepare full rubric data for API
      const fullRubricData = {
        ...rubricData,
        rubricId: rubricId,
        metadata: {
          ...rubricData.metadata,
          modifiedAt: new Date().toISOString()
        }
      };

      await updateRubric(rubricId, fullRubricData);

      // Show success message (you could add a toast notification here)
      console.log('Rubric saved successfully');
    } catch (err) {
      error = err.message || 'Failed to save rubric';
      console.error('Error saving rubric:', err);
    } finally {
      saving = false;
    }
  }

  // Save as new version
  async function saveAsNewVersion() {
    const rubricData = rubricStore.getRubricData();
    if (!rubricData) {
      error = 'No rubric data to save';
      return;
    }

    // Validate rubric
    const validation = rubricStore.validate();
    if (!validation.isValid) {
      error = `Validation errors: ${validation.errors.join(', ')}`;
      return;
    }

    try {
      saving = true;
      error = null;

      // Modify title to indicate it's a version
      const versionedData = {
        ...rubricData,
        title: `${rubricData.title} (Copy)`,
        metadata: {
          ...rubricData.metadata,
          modifiedAt: new Date().toISOString()
        }
      };

      const newRubric = await createRubric(versionedData);

      // Navigate to the new rubric
      goto(`/evaluaitor/${newRubric.rubricId}`);
    } catch (err) {
      error = err.message || 'Failed to create new version';
      console.error('Error creating new version:', err);
    } finally {
      saving = false;
    }
  }

  // Handle AI generation
  async function handleAIGenerate(prompt) {
    try {
      aiGenerating = true;
      error = null;

      const response = await aiGenerateRubric(prompt);

      // Load the generated rubric into the store
      rubricStore.loadRubric(response.rubric_data);

      // Mark as new rubric (not saved yet)
      isNewRubric = true;

      showAIChat = false;

      console.log('AI generation completed:', response.explanation);
    } catch (err) {
      error = err.message || 'Failed to generate rubric with AI';
      console.error('Error generating rubric:', err);
    } finally {
      aiGenerating = false;
    }
  }

  // Handle AI modification
  async function handleAIModify(prompt) {
    const currentRubricData = rubricStore.getRubricData();
    if (!currentRubricData) {
      error = 'No rubric to modify';
      return;
    }

    try {
      aiGenerating = true;
      error = null;

      const response = await aiModifyRubric(rubricId, prompt);

      // Show changes preview (you could add a modal here)
      const changes = rubricStore.getChanges(response.rubric_data);

      // For now, just apply the changes directly
      rubricStore.replaceRubric(response.rubric_data);

      console.log('AI modification completed:', response.explanation);
      console.log('Changes:', changes);
    } catch (err) {
      error = err.message || 'Failed to modify rubric with AI';
      console.error('Error modifying rubric:', err);
    } finally {
      aiGenerating = false;
    }
  }

  // Handle undo/redo
  function handleUndo() {
    rubricStore.undo();
  }

  function handleRedo() {
    rubricStore.redo();
  }

  // Handle back navigation
  function handleBack() {
    goto('/evaluaitor');
  }

  // Initialize
  onMount(() => {
    loadRubric();
  });

  // Reactive effects
  $effect(() => {
    // Update document title when rubric title changes
    if (rubricStore.rubric?.title) {
      document.title = `${rubricStore.rubric.title} - Evaluaitor`;
    }
  });
</script>

<div class="min-h-screen bg-gray-50">
  <!-- Header -->
  <div class="bg-white shadow">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex justify-between items-center py-4">
        <div class="flex items-center">
          <button
            onclick={handleBack}
            class="mr-4 p-2 rounded-md text-gray-400 hover:text-gray-500 hover:bg-gray-100"
            aria-label="Go back"
          >
            <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/>
            </svg>
          </button>
          <div>
            <h1 class="text-xl font-semibold text-gray-900">
              {rubricStore.rubric?.title || 'Loading...'}
            </h1>
            <p class="text-sm text-gray-500">
              {rubricStore.rubric?.description || ''}
            </p>
          </div>
        </div>

        <div class="flex items-center space-x-3">
          {#if isEditMode || isNewRubric}
            <!-- EDIT MODE: Show action buttons -->
            
            <!-- Undo/Redo buttons -->
            <button
              onclick={handleUndo}
              disabled={!rubricStore.canUndo}
              class="p-2 rounded-md text-gray-400 hover:text-gray-500 hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
              title="Undo"
            >
              <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6"/>
              </svg>
            </button>
            <button
              onclick={handleRedo}
              disabled={!rubricStore.canRedo}
              class="p-2 rounded-md text-gray-400 hover:text-gray-500 hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
              title="Redo"
            >
              <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 10H11a8 8 0 00-8 8v2M21 10l-6 6m6-6l-6-6"/>
              </svg>
            </button>

            <!-- AI Chat Toggle -->
            <button
              onclick={() => showAIChat = !showAIChat}
              class="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"
            >
              <svg class="-ml-0.5 mr-2 h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-4l-4 4-4-4z"/>
              </svg>
              AI Assistant
            </button>

            {#if !isNewRubric}
            <!-- Cancel Edit Button -->
            <button
              onclick={cancelEdit}
              disabled={saving || loading}
              class="inline-flex items-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <svg class="-ml-1 mr-2 h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
              </svg>
              Cancel Edit
            </button>
            {/if}

            <!-- Update/Save Button -->
            <button
              onclick={saveRubric}
              disabled={saving || loading}
              class="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {#if saving}
                <svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                {isNewRubric ? 'Saving...' : 'Updating...'}
              {:else}
                <svg class="-ml-1 mr-2 h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                </svg>
                {isNewRubric ? 'Save' : 'Update Rubric'}
              {/if}
            </button>

            <!-- Save as New Version -->
            {#if !isNewRubric}
            <button
              onclick={saveAsNewVersion}
              disabled={saving || loading}
              class="inline-flex items-center px-4 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Save as New Version
            </button>
            {/if}
          {:else}
            <!-- VIEW MODE: Show view label and edit button -->
            
            <!-- View Only Label/Badge -->
            <span class="inline-flex items-center px-3 py-1 rounded-md text-sm font-medium bg-gray-100 text-gray-700 border border-gray-300">
              <svg class="-ml-0.5 mr-2 h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/>
              </svg>
              View Only
            </span>

            <!-- Edit Button -->
            <button
              onclick={enterEditMode}
              class="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700"
            >
              <svg class="-ml-1 mr-2 h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
              </svg>
              Edit
            </button>
          {/if}
        </div>
      </div>
    </div>
  </div>

  <!-- Main Content -->
  <div class="max-w-none mx-auto py-6 px-6 lg:px-12">
    {#if loading}
      <div class="text-center py-12">
        <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
        <p class="mt-4 text-lg text-gray-600">Loading rubric...</p>
      </div>
    {:else if error}
      <div class="bg-red-50 border border-red-200 rounded-md p-4 mb-6">
        <div class="flex">
          <div class="flex-shrink-0">
            <svg class="h-5 w-5 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z"/>
            </svg>
          </div>
          <div class="ml-3">
            <h3 class="text-sm font-medium text-red-800">Error</h3>
            <div class="mt-2 text-sm text-red-700">{error}</div>
            <div class="mt-4">
              <button
                onclick={() => goto('/evaluaitor')}
                class="bg-red-100 px-3 py-2 rounded-md text-sm font-medium text-red-800 hover:bg-red-200"
              >
                Back to Rubrics
              </button>
            </div>
          </div>
        </div>
      </div>
    {:else}
      <div class="grid grid-cols-1 {showAIChat ? 'xl:grid-cols-4' : ''} gap-8">
        <!-- Main Editor Area -->
        <div class="{showAIChat ? 'xl:col-span-3' : ''} space-y-8">
          <!-- Rubric Metadata -->
          <RubricMetadataForm {isEditMode} />

          <!-- Rubric Table -->
          <RubricTable {isEditMode} />
        </div>

        <!-- AI Chat Panel -->
        {#if showAIChat}
          <div class="xl:col-span-1">
            <RubricAIChat
              {rubricId}
              {aiGenerating}
              onGenerate={handleAIGenerate}
              onModify={handleAIModify}
            />
          </div>
        {/if}
      </div>
    {/if}
  </div>
</div>

<style>
  /* Custom styles if needed */
</style>
