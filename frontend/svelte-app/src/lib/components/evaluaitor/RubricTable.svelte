<script>
  import { rubricStore } from '$lib/stores/rubricStore.svelte.js';

  // Props
  let { isEditMode = false } = $props();

  // Local state for inline editing
  let editingCell = $state(null); // {criterionId, levelId, field}
  let editValue = $state('');
  let ignoreNextBlur = $state(false); // Flag to prevent immediate blur on focus

  // Start editing a cell
  function startEditing(criterionId, levelId, field, currentValue) {
    editingCell = { criterionId, levelId, field };
    editValue = currentValue || '';
    ignoreNextBlur = true; // Set flag to ignore the first blur event
  }

  // Start editing a level cell, creating the level if it doesn't exist
  function startEditingLevel(criterion, levelTemplate, level) {
    if (!isEditMode) return;

    // If level doesn't exist, create it first
    if (!level) {
      const newLevel = {
        score: levelTemplate.score,
        label: levelTemplate.label,
        description: ''
      };
      
      rubricStore.addLevelToCriterion(criterion.id, newLevel);
      
      // After adding, find the newly created level in the updated criterion
      // We need to wait a tick for the store to update
      setTimeout(() => {
        const updatedCriterion = rubricStore.rubric.criteria.find(c => c.id === criterion.id);
        if (updatedCriterion) {
          const newlyAddedLevel = updatedCriterion.levels.find(l => l.score === levelTemplate.score);
          if (newlyAddedLevel) {
            startEditing(criterion.id, newlyAddedLevel.id, 'description', '');
          }
        }
      }, 0);
    } else {
      // Level exists, start editing directly
      startEditing(criterion.id, level.id, 'description', level.description || '');
    }
  }

  // Focus input helper
  function focusInput(node) {
    // Use setTimeout to ensure the element is fully rendered before focusing
    setTimeout(() => {
      node.focus();
      node.select();
      // Reset the ignore blur flag after a short delay
      setTimeout(() => {
        ignoreNextBlur = false;
      }, 100);
    }, 10);
  }

  // Save cell edit
  function saveCellEdit() {
    if (!editingCell) return;
    
    // Ignore the first blur event after opening the editor
    if (ignoreNextBlur) {
      return;
    }

    const { criterionId, levelId, field } = editingCell;

    // If levelId is present, we're editing a level cell, not a criterion field
    if (levelId) {
      rubricStore.updateCell(criterionId, levelId, field, editValue);
    } else {
      // Editing criterion fields (name, description, weight)
      if (field === 'name' || field === 'description') {
        rubricStore.updateCriterion(criterionId, { [field]: editValue });
      } else if (field === 'weight') {
        const weight = parseFloat(editValue);
        if (!isNaN(weight) && weight >= 0) {
          rubricStore.updateCriterion(criterionId, { weight });
        }
      }
    }

    editingCell = null;
    editValue = '';
    ignoreNextBlur = false;
  }

  // Cancel cell edit
  function cancelEdit() {
    editingCell = null;
    editValue = '';
  }

  // Handle keyboard events for input fields
  function handleKeydown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      saveCellEdit();
    } else if (event.key === 'Escape') {
      cancelEdit();
    }
  }

  // Handle keyboard events for textarea fields
  function handleTextareaKeydown(event) {
    // Allow Enter for new lines, save only on Ctrl+Enter or Escape to cancel
    if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      saveCellEdit();
    } else if (event.key === 'Escape') {
      cancelEdit();
    }
  }

  // Add new criterion
  function addCriterion() {
    const newCriterion = {
      name: 'New Criterion',
      description: 'Description of the new criterion',
      weight: 10,
      levels: []
    };

    // Copy levels from first criterion if it exists
    if (rubricStore.rubric?.criteria?.length > 0) {
      const firstCriterion = rubricStore.rubric.criteria[0];
      newCriterion.levels = firstCriterion.levels.map(level => ({
        score: level.score,
        label: level.label,
        description: 'Description for this level'
      }));
    } else {
      // Default levels
      newCriterion.levels = [
        { score: 4, label: 'Exemplary', description: 'Exemplary performance' },
        { score: 3, label: 'Proficient', description: 'Proficient performance' },
        { score: 2, label: 'Developing', description: 'Developing performance' },
        { score: 1, label: 'Beginning', description: 'Beginning performance' }
      ];
    }

    rubricStore.addCriterion(newCriterion);
  }

  // Remove criterion
  function removeCriterion(criterionId) {
    if (confirm('Are you sure you want to remove this criterion?')) {
      rubricStore.removeCriterion(criterionId);
    }
  }

  // Add new performance level
  function addLevel() {
    const newLevel = {
      score: 5,
      label: 'Advanced',
      description: 'Advanced performance level'
    };

    rubricStore.addLevel(newLevel);
  }

  // Remove performance level
  function removeLevel(levelId) {
    if (confirm('Are you sure you want to remove this performance level from all criteria?')) {
      rubricStore.removeLevel(levelId);
    }
  }

  // Get common level structure based on first criterion
  function getCommonLevels() {
    if (!rubricStore.rubric?.criteria?.length) return [];
    
    // Use the first criterion as the template for level structure
    const firstCriterion = rubricStore.rubric.criteria[0];
    return firstCriterion.levels || [];
  }

  // Get level for a specific criterion by score matching (more reliable than ID)
  function getCriterionLevel(criterion, targetScore) {
    return criterion.levels?.find(level => level.score === targetScore) || null;
  }

  // Calculate total weight percentage
  function getTotalWeight() {
    if (!rubricStore.rubric?.criteria?.length) return 0;
    
    return rubricStore.rubric.criteria.reduce((sum, criterion) => {
      const weight = parseFloat(criterion.weight) || 0;
      return sum + weight;
    }, 0);
  }

  // Derived state for total weight
  let totalWeight = $derived(getTotalWeight());
</script>

<div class="bg-white shadow rounded-lg">
  <div class="px-6 py-4 border-b border-gray-200">
    <div class="flex justify-between items-center">
      <h3 class="text-lg font-medium text-gray-900">Rubric Criteria</h3>
      <div class="flex space-x-2">
        <button
          onclick={isEditMode ? addCriterion : null}
          disabled={!isEditMode}
          class="inline-flex items-center px-3 py-1 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <svg class="-ml-1 mr-1 h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"/>
          </svg>
          Add Criterion
        </button>
        <button
          onclick={isEditMode ? addLevel : null}
          disabled={!isEditMode}
          class="inline-flex items-center px-3 py-1 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <svg class="-ml-1 mr-1 h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"/>
          </svg>
          Add Level
        </button>
      </div>
    </div>
  </div>

  <div class="overflow-x-auto">
    <table class="min-w-full divide-y divide-gray-200">
      <thead class="bg-gray-50">
        <tr>
          <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
            Criterion
          </th>
          <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
            Weight
          </th>
          {#each getCommonLevels() as levelTemplate}
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              <div class="flex items-center justify-between">
                <span>{levelTemplate.label || 'Level'} ({levelTemplate.score || '?'})</span>
                {#if getCommonLevels().length > 2}
                  <button
                    onclick={() => isEditMode && removeLevel(levelTemplate.id)}
                    disabled={!isEditMode}
                    class="ml-2 text-red-400 hover:text-red-600 disabled:opacity-50 disabled:cursor-not-allowed"
                    title="Remove this level"
                  >
                    <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                    </svg>
                  </button>
                {/if}
              </div>
            </th>
          {/each}
          <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
            Actions
          </th>
        </tr>
      </thead>
      <tbody class="bg-white divide-y divide-gray-200">
        {#each rubricStore.rubric?.criteria || [] as criterion, criterionIndex}
          <tr class="hover:bg-gray-50">
            <!-- Criterion Name and Description -->
            <td class="px-6 py-4">
              <div class="space-y-2">
                {#if editingCell?.criterionId === criterion.id && editingCell?.field === 'name' && !editingCell?.levelId}
                  <input
                    type="text"
                    bind:value={editValue}
                    onkeydown={handleKeydown}
                    onblur={saveCellEdit}
                    class="w-full px-2 py-1 border-2 border-blue-500 rounded text-sm focus:ring-blue-500 focus:border-blue-600 shadow-lg"
                    use:focusInput
                    placeholder="Enter criterion name (Enter to save, Esc to cancel)"
                  />
                {:else}
                  <div
                    onclick={() => isEditMode && startEditing(criterion.id, null, 'name', criterion.name)}
                    onkeydown={(e) => e.key === 'Enter' && isEditMode && startEditing(criterion.id, null, 'name', criterion.name)}
                    role="button"
                    tabindex="0"
                    class="{isEditMode ? 'cursor-pointer hover:bg-blue-50 hover:border-blue-200 border border-transparent' : 'cursor-default'} p-1 rounded text-sm font-medium text-gray-900"
                  >
                    {criterion.name || 'Unnamed Criterion'}
                  </div>
                {/if}

                {#if editingCell?.criterionId === criterion.id && editingCell?.field === 'description' && !editingCell?.levelId}
                  <textarea
                    bind:value={editValue}
                    onkeydown={handleTextareaKeydown}
                    onblur={saveCellEdit}
                    rows="2"
                    class="w-full px-2 py-1 border-2 border-blue-500 rounded text-sm focus:ring-blue-500 focus:border-blue-600 shadow-lg"
                    use:focusInput
                    placeholder="Enter criterion description (Ctrl+Enter to save, Esc to cancel)"
                  ></textarea>
                {:else}
                  <div
                    onclick={() => isEditMode && startEditing(criterion.id, null, 'description', criterion.description)}
                    onkeydown={(e) => e.key === 'Enter' && isEditMode && startEditing(criterion.id, null, 'description', criterion.description)}
                    role="button"
                    tabindex="0"
                    class="{isEditMode ? 'cursor-pointer hover:bg-blue-50 hover:border-blue-200 border border-transparent' : 'cursor-default'} p-1 rounded text-sm text-gray-600"
                  >
                    {criterion.description || 'No description'}
                  </div>
                {/if}
              </div>
            </td>

            <!-- Weight -->
            <td class="px-6 py-4 whitespace-nowrap">
              {#if editingCell?.criterionId === criterion.id && editingCell?.field === 'weight' && !editingCell?.levelId}
                <input
                  type="number"
                  min="0"
                  max="100"
                  bind:value={editValue}
                  onkeydown={handleKeydown}
                  onblur={saveCellEdit}
                  class="w-16 px-2 py-1 border-2 border-blue-500 rounded text-sm focus:ring-blue-500 focus:border-blue-600 shadow-lg"
                  use:focusInput
                  placeholder="%"
                />
              {:else}
                <div
                  onclick={() => isEditMode && startEditing(criterion.id, null, 'weight', criterion.weight?.toString())}
                  onkeydown={(e) => e.key === 'Enter' && isEditMode && startEditing(criterion.id, null, 'weight', criterion.weight?.toString())}
                  role="button"
                  tabindex="0"
                  class="{isEditMode ? 'cursor-pointer hover:bg-blue-50 hover:border-blue-200 border border-transparent' : 'cursor-default'} p-1 rounded text-sm text-center font-medium"
                >
                  {criterion.weight || 0}%
                </div>
              {/if}
            </td>

            <!-- Performance Levels -->
            {#each getCommonLevels() as levelTemplate}
              {@const level = getCriterionLevel(criterion, levelTemplate.score)}
              <td class="px-6 py-4">
                {#if editingCell?.criterionId === criterion.id && editingCell?.levelId === level?.id && editingCell?.field === 'description'}
                  <textarea
                    bind:value={editValue}
                    onkeydown={handleTextareaKeydown}
                    onblur={saveCellEdit}
                    rows="3"
                    class="w-full px-2 py-1 border-2 border-blue-500 rounded text-sm focus:ring-blue-500 focus:border-blue-600 shadow-lg"
                    use:focusInput
                    placeholder="Enter level description (Ctrl+Enter to save, Esc to cancel)"
                  ></textarea>
                {:else}
                  <div
                    onclick={() => isEditMode && startEditingLevel(criterion, levelTemplate, level)}
                    onkeydown={(e) => e.key === 'Enter' && isEditMode && startEditingLevel(criterion, levelTemplate, level)}
                    role="button"
                    tabindex={isEditMode ? 0 : -1}
                    class="{isEditMode ? 'cursor-pointer hover:bg-blue-50 hover:border-blue-200 border border-transparent' : 'cursor-default'} p-2 rounded text-sm text-gray-700 min-h-[60px]"
                  >
                    {level?.description || 'No description'}
                  </div>
                {/if}
              </td>
            {/each}

            <!-- Actions -->
            <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
              {#if rubricStore.rubric?.criteria?.length > 1}
                <button
                  onclick={() => isEditMode && removeCriterion(criterion.id)}
                  disabled={!isEditMode}
                  class="text-red-600 hover:text-red-900 disabled:opacity-50 disabled:cursor-not-allowed"
                  title="Remove criterion"
                >
                  <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                  </svg>
                </button>
              {/if}
            </td>
          </tr>
        {/each}

        <!-- Total Weight Row -->
        {#if rubricStore.rubric?.criteria?.length}
          <tr class="bg-gray-50 border-t-2 border-gray-300 font-semibold">
            <td class="px-6 py-4 text-sm text-gray-900" colspan="2">
              Total
            </td>
            <td class="px-6 py-4 text-sm text-center">
              <div class="flex items-center justify-center">
                <span class="{totalWeight === 100 ? 'text-green-600' : totalWeight > 100 ? 'text-red-600' : 'text-yellow-600'}">
                  {totalWeight.toFixed(1)}%
                </span>
                {#if totalWeight === 100}
                  <svg class="ml-2 h-5 w-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
                  </svg>
                {:else if totalWeight > 100}
                  <svg class="ml-2 h-5 w-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                  </svg>
                {:else}
                  <svg class="ml-2 h-5 w-5 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
                  </svg>
                {/if}
              </div>
              {#if totalWeight !== 100}
                <div class="text-xs {totalWeight > 100 ? 'text-red-500' : 'text-yellow-500'} mt-1">
                  {totalWeight > 100 ? 'Exceeds 100%' : 'Should equal 100%'}
                </div>
              {/if}
            </td>
            <!-- Empty cells for performance levels -->
            {#each getCommonLevels() as _}
              <td class="px-6 py-4"></td>
            {/each}
            <!-- Empty cell for actions -->
            {#if isEditMode}
              <td class="px-6 py-4"></td>
            {/if}
          </tr>
        {/if}
      </tbody>
    </table>
  </div>

  <!-- Validation Errors -->
  {#if rubricStore.error}
    <div class="px-6 py-4 bg-red-50 border-t border-red-200">
      <div class="text-sm text-red-700">{rubricStore.error}</div>
    </div>
  {/if}

  <!-- Empty State -->
  {#if !rubricStore.rubric?.criteria?.length}
    <div class="px-6 py-12 text-center">
      <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
      </svg>
      <h3 class="mt-2 text-sm font-medium text-gray-900">No criteria yet</h3>
      <p class="mt-1 text-sm text-gray-500">Get started by adding your first criterion.</p>
      <div class="mt-6">
        <button
          onclick={addCriterion}
          class="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700"
        >
          <svg class="-ml-1 mr-2 h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"/>
          </svg>
          Add Criterion
        </button>
      </div>
    </div>
  {/if}
</div>

