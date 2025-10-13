<script>
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { rubricStore } from '$lib/stores/rubricStore.svelte.js';
  import {
    fetchRubric,
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
      rubricStore.loadRubric(rubricData.rubricData);
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
      rubricStore.loadRubric(response.rubric);

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
      const changes = rubricStore.getChanges(response.rubric);

      // For now, just apply the changes directly
      rubricStore.replaceRubric(response.rubric);

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

          <!-- Save Button -->
          <button
            onclick={saveRubric}
            disabled={saving || loading}
            class="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50"
          >
            {#if saving}
              <svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              Saving...
            {:else}
              <svg class="-ml-1 mr-2 h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
              </svg>
              Save
            {/if}
          </button>

          <!-- Save as New Version -->
          <button
            onclick={saveAsNewVersion}
            disabled={saving || loading}
            class="inline-flex items-center px-4 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50"
          >
            Save as New Version
          </button>
        </div>
      </div>
    </div>
  </div>

  <!-- Main Content -->
  <div class="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
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
      <div class="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <!-- Main Editor Area -->
        <div class="lg:col-span-3 space-y-6">
          <!-- Rubric Metadata -->
          <RubricMetadataForm />

          <!-- Rubric Table -->
          <RubricTable />
        </div>

        <!-- AI Chat Panel -->
        {#if showAIChat}
          <div class="lg:col-span-1">
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
