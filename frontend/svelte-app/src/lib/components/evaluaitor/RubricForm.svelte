<script>
  import { createEventDispatcher } from 'svelte';
  import { _, locale } from '$lib/i18n';
  import { createRubric, updateRubric } from '$lib/services/rubricService';

  const dispatch = createEventDispatcher();

  // Default text for when i18n isn't loaded yet
  let localeLoaded = $state(!!$locale);

  // Props
  let { rubric = null } = $props();

  // Form state
  let formState = $state(rubric ? 'edit' : 'create');
  let isSubmitting = $state(false);
  let error = $state('');
  let success = $state('');

  // Form fields
  let title = $state('');
  let description = $state('');
  let subject = $state('');
  let gradeLevel = $state('undefined');
  let scoringType = $state('points');
  let maxScore = $state(10);


  // Criteria management
  let criteria = $state([
    {
      id: 'criterion-1',
      name: 'Content Knowledge',
      description: 'Understanding of subject matter',
      weight: 40,
      levels: [
        { id: 'level-1-1', score: 4, label: 'Exemplary', description: 'Demonstrates comprehensive understanding' },
        { id: 'level-1-2', score: 3, label: 'Proficient', description: 'Demonstrates adequate understanding' },
        { id: 'level-1-3', score: 2, label: 'Developing', description: 'Demonstrates partial understanding' },
        { id: 'level-1-4', score: 1, label: 'Beginning', description: 'Demonstrates limited understanding' }
      ]
    }
  ]);

  // Initialize form with rubric data if editing
  $effect(() => {
    if (rubric && rubric.rubricData) {
      const data = rubric.rubricData;
      title = data.title || '';
      description = data.description || '';
      const metadata = data.metadata || {};
      subject = metadata.subject || '';
      gradeLevel = metadata.gradeLevel || '';
      scoringType = data.scoringType || 'points';
      maxScore = data.maxScore || 100;
      criteria = data.criteria || criteria;
    }
  });

  // Handle form submission
  async function handleSubmit() {
    if (isSubmitting) return;

    isSubmitting = true;
    error = '';
    success = '';

    try {
      const rubricData = {
        title,
        description,
        metadata: {
          subject,
          gradeLevel,
          createdAt: new Date().toISOString(),
          modifiedAt: new Date().toISOString()
        },
        criteria,
        scoringType,
        maxScore
      };

      let result;
      if (formState === 'create') {
        result = await createRubric(rubricData);
      } else {
        // For edit, we need to include the rubricId
        rubricData.rubricId = rubric.rubricId;
        result = await updateRubric(rubric.rubricId, rubricData, rubric.owner_email);
      }

      success = localeLoaded ? $_('rubrics.form.successMessage', { default: 'Rubric saved successfully!' }) : 'Rubric saved successfully!';

      // Dispatch success event
      dispatch('formSuccess', { rubricId: result.rubricId || result.id });

    } catch (err) {
      error = err.message || (localeLoaded ? $_('rubrics.form.errorMessage', { default: 'Failed to save rubric' }) : 'Failed to save rubric');
    } finally {
      isSubmitting = false;
    }
  }


  // Criteria management
  function addCriterion() {
    const newId = `criterion-${criteria.length + 1}`;
    criteria = [...criteria, {
      id: newId,
      name: '',
      description: '',
      weight: 25,
      levels: [
        { id: `${newId}-1`, score: 4, label: 'Exemplary', description: '' },
        { id: `${newId}-2`, score: 3, label: 'Proficient', description: '' },
        { id: `${newId}-3`, score: 2, label: 'Developing', description: '' },
        { id: `${newId}-4`, score: 1, label: 'Beginning', description: '' }
      ]
    }];
  }

  function removeCriterion(index) {
    if (criteria.length > 1) {
      criteria = criteria.filter((_, i) => i !== index);
    }
  }

  function addLevel(criterionIndex) {
    const criterion = criteria[criterionIndex];
    const newLevelId = `${criterion.id}-${criterion.levels.length + 1}`;
    criterion.levels = [...criterion.levels, {
      id: newLevelId,
      score: Math.max(1, Math.min(...criterion.levels.map(l => l.score)) - 1),
      label: 'New Level',
      description: ''
    }];
    criteria = [...criteria]; // Trigger reactivity
  }

  function removeLevel(criterionIndex, levelIndex) {
    const criterion = criteria[criterionIndex];
    if (criterion.levels.length > 2) {
      criterion.levels = criterion.levels.filter((_, i) => i !== levelIndex);
      criteria = [...criteria]; // Trigger reactivity
    }
  }

  // Helper functions for max score and scoring type explanations
  function getMaxScoreHint(scoringType) {
    switch (scoringType) {
      case 'points':
        return localeLoaded ? $_('rubrics.form.pointsHint', { default: 'Total possible points (e.g., 10, 20, 100)' }) : 'Total possible points (e.g., 10, 20, 100)';
      case 'percentage':
        return localeLoaded ? $_('rubrics.form.percentageHint', { default: 'Always 100 for percentage scoring' }) : 'Always 100 for percentage scoring';
      case 'holistic':
        return localeLoaded ? $_('rubrics.form.holisticHint', { default: 'Highest performance level (e.g., 4, 5, 6)' }) : 'Highest performance level (e.g., 4, 5, 6)';
      case 'single-point':
        return localeLoaded ? $_('rubrics.form.singlePointHint', { default: 'Number of criteria (typically 3-6)' }) : 'Number of criteria (typically 3-6)';
      case 'checklist':
        return localeLoaded ? $_('rubrics.form.checklistHint', { default: 'Number of checklist items' }) : 'Number of checklist items';
      default:
        return '10';
    }
  }

  function getScoringTypeExplanation(scoringType) {
    switch (scoringType) {
      case 'points':
        return localeLoaded ? $_('rubrics.form.pointsExplanation', { default: 'Analytic scoring with points for each criterion' }) : 'Analytic scoring with points for each criterion';
      case 'percentage':
        return localeLoaded ? $_('rubrics.form.percentageExplanation', { default: 'Scores expressed as percentages (0-100%)' }) : 'Scores expressed as percentages (0-100%)';
      case 'holistic':
        return localeLoaded ? $_('rubrics.form.holisticExplanation', { default: 'Single overall score (e.g., 1-4 scale)' }) : 'Single overall score (e.g., 1-4 scale)';
      case 'single-point':
        return localeLoaded ? $_('rubrics.form.singlePointExplanation', { default: 'Focus on meeting/not meeting expectations' }) : 'Focus on meeting/not meeting expectations';
      case 'checklist':
        return localeLoaded ? $_('rubrics.form.checklistExplanation', { default: 'Simple present/absent or yes/no format' }) : 'Simple present/absent or yes/no format';
      default:
        return '';
    }
  }

  // Reactive logic to update max score when scoring type changes
  $effect(() => {
    if (scoringType === 'percentage') {
      maxScore = 100;
    } else if (scoringType === 'holistic') {
      maxScore = 4;
    } else if (scoringType === 'single-point') {
      maxScore = criteria.length || 3;
    } else if (scoringType === 'checklist') {
      maxScore = criteria.length || 5;
    } else if (scoringType === 'points') {
      if (maxScore === 100 || maxScore === 4) { // Reset from other types
        maxScore = 10;
      }
    }
  });
</script>

<div class="max-w-6xl mx-auto">
  <div class="bg-white shadow rounded-lg p-6">
    <div class="mb-6">
      <h2 class="text-2xl font-bold text-gray-900">
        {formState === 'create'
          ? (localeLoaded ? $_('rubrics.form.createTitle', { default: 'Create New Rubric' }) : 'Create New Rubric')
          : (localeLoaded ? $_('rubrics.form.editTitle', { default: 'Edit Rubric' }) : 'Edit Rubric')
        }
      </h2>
      <p class="mt-1 text-sm text-gray-600">
        {localeLoaded ? $_('rubrics.form.description', { default: 'Define your assessment criteria and performance levels' }) : 'Define your assessment criteria and performance levels'}
      </p>
    </div>

    <!-- AI Generation Button -->
    {#if formState === 'create'}
      <div class="mb-6">
        <button
          type="button"
          onclick={() => dispatch('openAIModal')}
          class="inline-flex items-center px-4 py-2 border border-blue-300 text-sm font-medium rounded-md text-blue-700 bg-blue-50 hover:bg-blue-100"
        >
          <svg class="-ml-1 mr-2 h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/>
          </svg>
          ⚡ {localeLoaded ? $_('rubrics.ai.generateButton', { default: 'Generate with AI' }) : 'Generate with AI'}
        </button>
      </div>
    {/if}

    <!-- Form -->
    <form onsubmit={handleSubmit}>
      <!-- Basic Information -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        <div>
          <label for="title" class="block text-sm font-medium text-gray-700">
            {localeLoaded ? $_('rubrics.form.title', { default: 'Title' }) : 'Title'} <span class="text-red-500">*</span>
          </label>
          <input
            type="text"
            id="title"
            bind:value={title}
            required
            class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
            placeholder={localeLoaded ? $_('rubrics.form.titlePlaceholder', { default: 'e.g., Essay Writing Rubric' }) : 'e.g., Essay Writing Rubric'}
          />
        </div>

        <div>
          <label for="subject" class="block text-sm font-medium text-gray-700">
            {localeLoaded ? $_('rubrics.form.subject', { default: 'Subject' }) : 'Subject'}
          </label>
          <input
            type="text"
            id="subject"
            bind:value={subject}
            class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
            placeholder={localeLoaded ? $_('rubrics.form.subjectPlaceholder', { default: 'e.g., Mathematics, English, Science' }) : 'e.g., Mathematics, English, Science'}
          />
        </div>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        <div>
          <label for="gradeLevel" class="block text-sm font-medium text-gray-700">
            {localeLoaded ? $_('rubrics.form.gradeLevel', { default: 'Grade Level' }) : 'Grade Level'}
          </label>
          <select
            id="gradeLevel"
            bind:value={gradeLevel}
            class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
          >
            <option value="undefined">{localeLoaded ? $_('rubrics.form.gradeUndefined', { default: 'Undefined' }) : 'Undefined'}</option>
            <option value="K-2">K-2</option>
            <option value="3-5">3-5</option>
            <option value="6-8">6-8</option>
            <option value="9-12">9-12</option>
            <option value="Higher Education">Higher Education</option>
          </select>
        </div>

        <div>
          <label for="scoringType" class="block text-sm font-medium text-gray-700">
            {localeLoaded ? $_('rubrics.form.scoringType', { default: 'Scoring Type' }) : 'Scoring Type'}
          </label>
          <select
            id="scoringType"
            bind:value={scoringType}
            class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
          >
            <option value="points">Points</option>
            <option value="percentage">Percentage</option>
            <option value="holistic">Holistic</option>
            <option value="single-point">Single Point</option>
            <option value="checklist">Checklist</option>
          </select>
        </div>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        <div>
          <label for="maxScore" class="block text-sm font-medium text-gray-700">
            {localeLoaded ? $_('rubrics.form.maxScore', { default: 'Maximum Score' }) : 'Maximum Score'}
          </label>
          <input
            type="number"
            id="maxScore"
            bind:value={maxScore}
            min="1"
            max="1000"
            class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
            placeholder={getMaxScoreHint(scoringType)}
          />
          <p class="mt-1 text-xs text-gray-500">
            {getMaxScoreHint(scoringType)}
          </p>
        </div>
        <div class="flex items-end">
          <div class="text-sm text-gray-600 bg-gray-50 p-3 rounded border">
            <strong>{localeLoaded ? $_('rubrics.form.scoringExplanation', { default: 'About Scoring Types:' }) : 'About Scoring Types:'}</strong><br>
            {getScoringTypeExplanation(scoringType)}
          </div>
        </div>
      </div>

      <div class="mb-6">
        <label for="description" class="block text-sm font-medium text-gray-700">
          {localeLoaded ? $_('rubrics.form.description', { default: 'Description' }) : 'Description'}
        </label>
        <textarea
          id="description"
          bind:value={description}
          rows="3"
          class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
          placeholder={localeLoaded ? $_('rubrics.form.descriptionPlaceholder', { default: 'Describe what this rubric assesses...' }) : 'Describe what this rubric assesses...'}
        ></textarea>
      </div>

      <!-- Criteria Section -->
      <div class="mb-6">
        <div class="flex justify-between items-center mb-4">
          <h3 class="text-lg font-medium text-gray-900">
            {localeLoaded ? $_('rubrics.form.criteria', { default: 'Assessment Criteria' }) : 'Assessment Criteria'}
          </h3>
          <button
            type="button"
            onclick={addCriterion}
            class="inline-flex items-center px-3 py-1 border border-transparent text-sm font-medium rounded text-blue-600 bg-blue-100 hover:bg-blue-200"
          >
            <svg class="-ml-1 mr-1 h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"/>
            </svg>
            {localeLoaded ? $_('rubrics.form.addCriterion', { default: 'Add Criterion' }) : 'Add Criterion'}
          </button>
        </div>

        {#each criteria as criterion, criterionIndex}
          <div class="border border-gray-200 rounded-md p-4 mb-4">
            <div class="flex justify-between items-start mb-3">
              <h4 class="text-md font-medium text-gray-900">
                {localeLoaded ? $_('rubrics.form.criterion', { default: 'Criterion' }) : 'Criterion'} {criterionIndex + 1}
              </h4>
              {#if criteria.length > 1}
                <button
                  type="button"
                  onclick={() => removeCriterion(criterionIndex)}
                  class="text-red-600 hover:text-red-800 p-1"
                  title={localeLoaded ? $_('common.remove', { default: 'Remove' }) : 'Remove'}
                >
                  <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                  </svg>
                </button>
              {/if}
            </div>

            <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-3">
              <div class="md:col-span-2">
                <label for="criterion-name-{criterionIndex}" class="block text-sm font-medium text-gray-700">
                  {localeLoaded ? $_('rubrics.form.criterionName', { default: 'Name' }) : 'Name'}
                </label>
                <input
                  id="criterion-name-{criterionIndex}"
                  type="text"
                  bind:value={criterion.name}
                  class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
                  placeholder={localeLoaded ? $_('rubrics.form.criterionNamePlaceholder', { default: 'e.g., Content Knowledge' }) : 'e.g., Content Knowledge'}
                />
              </div>
              <div>
                <label for="criterion-weight-{criterionIndex}" class="block text-sm font-medium text-gray-700">
                  {localeLoaded ? $_('rubrics.form.weight', { default: 'Weight (%)' }) : 'Weight (%)'}
                </label>
                <input
                  id="criterion-weight-{criterionIndex}"
                  type="number"
                  bind:value={criterion.weight}
                  min="0"
                  max="100"
                  class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
            </div>

            <div class="mb-3">
              <label for="criterion-description-{criterionIndex}" class="block text-sm font-medium text-gray-700">
                {localeLoaded ? $_('rubrics.form.criterionDescription', { default: 'Description' }) : 'Description'}
              </label>
              <textarea
                id="criterion-description-{criterionIndex}"
                bind:value={criterion.description}
                rows="2"
                class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
                placeholder={localeLoaded ? $_('rubrics.form.criterionDescriptionPlaceholder', { default: 'Describe what this criterion assesses...' }) : 'Describe what this criterion assesses...'}
              ></textarea>
            </div>

            <!-- Performance Levels -->
            <div class="mb-3">
              <div class="flex justify-between items-center mb-2">
                <h5 class="text-sm font-medium text-gray-700">
                  {localeLoaded ? $_('rubrics.form.performanceLevels', { default: 'Performance Levels' }) : 'Performance Levels'}
                </h5>
                <button
                  type="button"
                  onclick={() => addLevel(criterionIndex)}
                  class="inline-flex items-center px-2 py-1 border border-transparent text-xs font-medium rounded text-blue-600 bg-blue-100 hover:bg-blue-200"
                >
                  <svg class="-ml-1 mr-1 h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"/>
                  </svg>
                  {localeLoaded ? $_('rubrics.form.addLevel', { default: 'Add Level' }) : 'Add Level'}
                </button>
              </div>

              {#each criterion.levels as level, levelIndex}
                <div class="flex items-start space-x-2 mb-3">
                  <input
                    type="number"
                    bind:value={level.score}
                    class="w-16 border border-gray-300 rounded px-2 py-1 text-sm"
                    min="0"
                  />
                  <input
                    type="text"
                    bind:value={level.label}
                    class="w-32 border border-gray-300 rounded px-2 py-1 text-sm"
                    placeholder={localeLoaded ? $_('rubrics.form.levelLabel', { default: 'Label' }) : 'Label'}
                  />
                  <textarea
                    bind:value={level.description}
                    rows="3"
                    class="flex-1 border border-gray-300 rounded px-3 py-2 text-sm focus:ring-blue-500 focus:border-blue-500"
                    placeholder={localeLoaded ? $_('rubrics.form.levelDescription', { default: 'Description' }) : 'Description'}
                  ></textarea>
                  {#if criterion.levels.length > 2}
                    <button
                      type="button"
                      onclick={() => removeLevel(criterionIndex, levelIndex)}
                      class="text-red-600 hover:text-red-800 p-1 mt-1"
                      title={localeLoaded ? $_('common.remove', { default: 'Remove' }) : 'Remove'}
                    >
                      <svg class="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                      </svg>
                    </button>
                  {/if}
                </div>
              {/each}
            </div>
          </div>
        {/each}
      </div>

      <!-- Error/Success Messages -->
      {#if error}
        <div class="mb-4 bg-red-50 border border-red-200 rounded-md p-4">
          <div class="text-sm text-red-700">{error}</div>
        </div>
      {/if}

      {#if success}
        <div class="mb-4 bg-green-50 border border-green-200 rounded-md p-4">
          <div class="text-sm text-green-700">{success}</div>
        </div>
      {/if}

      <!-- Form Actions -->
      <div class="flex justify-end space-x-3">
        <button
          type="button"
          onclick={() => history.back()}
          class="px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"
        >
          {localeLoaded ? $_('common.cancel', { default: 'Cancel' }) : 'Cancel'}
        </button>
        <button
          type="submit"
          disabled={isSubmitting || !title.trim()}
          class="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50"
        >
          {#if isSubmitting}
            <svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            {localeLoaded ? $_('common.saving', { default: 'Saving...' }) : 'Saving...'}
          {:else}
            {formState === 'create'
              ? (localeLoaded ? $_('common.create', { default: 'Create Rubric' }) : 'Create Rubric')
              : (localeLoaded ? $_('common.save', { default: 'Save Changes' }) : 'Save Changes')
            }
          {/if}
        </button>
      </div>
    </form>
  </div>
</div>
