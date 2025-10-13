<script>
  import { rubricStore } from '$lib/stores/rubricStore.svelte.js';

  // Local state for inline editing
  let editingCell = $state(null); // {criterionId, levelId, field}
  let editValue = $state('');

  // Start editing a cell
  function startEditing(criterionId, levelId, field, currentValue) {
    editingCell = { criterionId, levelId, field };
    editValue = currentValue || '';
  }

  // Focus input helper
  function focusInput(node) {
    node.focus();
    node.select();
  }

  // Save cell edit
  function saveCellEdit() {
    if (!editingCell) return;

    const { criterionId, levelId, field } = editingCell;

    if (field === 'name' || field === 'description') {
      rubricStore.updateCriterion(criterionId, { [field]: editValue });
    } else if (field === 'weight') {
      const weight = parseFloat(editValue);
      if (!isNaN(weight) && weight >= 0) {
        rubricStore.updateCriterion(criterionId, { weight });
      }
    } else {
      rubricStore.updateCell(criterionId, levelId, field, editValue);
    }

    editingCell = null;
    editValue = '';
  }

  // Cancel cell edit
  function cancelEdit() {
    editingCell = null;
    editValue = '';
  }

  // Handle keyboard events
  function handleKeydown(event) {
    if (event.key === 'Enter') {
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

  // Get all unique level IDs across criteria
  function getLevelIds() {
    if (!rubricStore.rubric?.criteria?.length) return [];

    const levelIds = new Set();
    rubricStore.rubric.criteria.forEach(criterion => {
      criterion.levels?.forEach(level => {
        levelIds.add(level.id);
      });
    });

    return Array.from(levelIds);
  }

  // Get level data for a specific level ID
  function getLevelData(levelId) {
    if (!rubricStore.rubric?.criteria?.length) return null;

    // Find the level in the first criterion (they should all have the same levels)
    const firstCriterion = rubricStore.rubric.criteria[0];
    return firstCriterion.levels?.find(level => level.id === levelId) || null;
  }
</script>

<div class="bg-white shadow rounded-lg">
  <div class="px-6 py-4 border-b border-gray-200">
    <div class="flex justify-between items-center">
      <h3 class="text-lg font-medium text-gray-900">Rubric Criteria</h3>
      <div class="flex space-x-2">
        <button
          onclick={addCriterion}
          class="inline-flex items-center px-3 py-1 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
        >
          <svg class="-ml-1 mr-1 h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"/>
          </svg>
          Add Criterion
        </button>
        <button
          onclick={addLevel}
          class="inline-flex items-center px-3 py-1 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
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
          {#each getLevelIds() as levelId}
            {@const levelData = getLevelData(levelId)}
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              <div class="flex items-center justify-between">
                <span>{levelData?.label || 'Level'} ({levelData?.score || '?'})</span>
                {#if getLevelIds().length > 2}
                  <button
                    onclick={() => removeLevel(levelId)}
                    class="ml-2 text-red-400 hover:text-red-600"
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
                {#if editingCell?.criterionId === criterion.id && editingCell?.field === 'name'}
                  <input
                    type="text"
                    bind:value={editValue}
                    onkeydown={handleKeydown}
                    onblur={saveCellEdit}
                    class="w-full px-2 py-1 border border-gray-300 rounded text-sm focus:ring-blue-500 focus:border-blue-500"
                    use:focusInput
                  />
                {:else}
                  <div
                    onclick={() => startEditing(criterion.id, null, 'name', criterion.name)}
                    onkeydown={(e) => e.key === 'Enter' && startEditing(criterion.id, null, 'name', criterion.name)}
                    role="button"
                    tabindex="0"
                    class="cursor-pointer hover:bg-gray-100 p-1 rounded text-sm font-medium text-gray-900"
                  >
                    {criterion.name || 'Unnamed Criterion'}
                  </div>
                {/if}

                {#if editingCell?.criterionId === criterion.id && editingCell?.field === 'description'}
                  <textarea
                    bind:value={editValue}
                    onkeydown={handleKeydown}
                    onblur={saveCellEdit}
                    rows="2"
                    class="w-full px-2 py-1 border border-gray-300 rounded text-sm focus:ring-blue-500 focus:border-blue-500"
                    use:focusInput
                  ></textarea>
                {:else}
                  <div
                    onclick={() => startEditing(criterion.id, null, 'description', criterion.description)}
                    onkeydown={(e) => e.key === 'Enter' && startEditing(criterion.id, null, 'description', criterion.description)}
                    role="button"
                    tabindex="0"
                    class="cursor-pointer hover:bg-gray-100 p-1 rounded text-sm text-gray-600"
                  >
                    {criterion.description || 'No description'}
                  </div>
                {/if}
              </div>
            </td>

            <!-- Weight -->
            <td class="px-6 py-4 whitespace-nowrap">
              {#if editingCell?.criterionId === criterion.id && editingCell?.field === 'weight'}
                <input
                  type="number"
                  min="0"
                  max="100"
                  bind:value={editValue}
                  onkeydown={handleKeydown}
                  onblur={saveCellEdit}
                  class="w-16 px-2 py-1 border border-gray-300 rounded text-sm focus:ring-blue-500 focus:border-blue-500"
                  use:focusInput
                />
              {:else}
                <div
                  onclick={() => startEditing(criterion.id, null, 'weight', criterion.weight?.toString())}
                  onkeydown={(e) => e.key === 'Enter' && startEditing(criterion.id, null, 'weight', criterion.weight?.toString())}
                  role="button"
                  tabindex="0"
                  class="cursor-pointer hover:bg-gray-100 p-1 rounded text-sm text-center font-medium"
                >
                  {criterion.weight || 0}%
                </div>
              {/if}
            </td>

            <!-- Performance Levels -->
            {#each getLevelIds() as levelId}
              {@const level = criterion.levels?.find(l => l.id === levelId)}
              <td class="px-6 py-4">
                {#if editingCell?.criterionId === criterion.id && editingCell?.levelId === levelId && editingCell?.field === 'description'}
                  <textarea
                    bind:value={editValue}
                    onkeydown={handleKeydown}
                    onblur={saveCellEdit}
                    rows="3"
                    class="w-full px-2 py-1 border border-gray-300 rounded text-sm focus:ring-blue-500 focus:border-blue-500"
                    use:focusInput
                  ></textarea>
                {:else}
                  <div
                    onclick={() => startEditing(criterion.id, levelId, 'description', level?.description)}
                    onkeydown={(e) => e.key === 'Enter' && startEditing(criterion.id, levelId, 'description', level?.description)}
                    role="button"
                    tabindex="0"
                    class="cursor-pointer hover:bg-gray-100 p-2 rounded text-sm text-gray-600 min-h-[60px]"
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
                  onclick={() => removeCriterion(criterion.id)}
                  class="text-red-600 hover:text-red-900"
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

