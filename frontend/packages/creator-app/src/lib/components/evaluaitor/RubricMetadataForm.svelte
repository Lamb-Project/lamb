<script>
  import { rubricStore } from '$lib/stores/rubricStore.svelte.js';
  import { _, locale } from '@lamb/ui/i18n';

  // Props
  let { isEditMode = false } = $props();

  // Local state for form inputs
  let title = $state('');
  let description = $state('');
  let scoringType = $state('points');
  let maxScore = $state(10);
  let subject = $state('');
  let gradeLevel = $state('');

  // Sync with store
  $effect(() => {
    if (rubricStore.rubric) {
      title = rubricStore.rubric.title || '';
      description = rubricStore.rubric.description || '';
      scoringType = rubricStore.rubric.scoringType || 'points';
      maxScore = rubricStore.rubric.maxScore || 10;
      subject = rubricStore.rubric.metadata?.subject || '';
      gradeLevel = rubricStore.rubric.metadata?.gradeLevel || '';
    }
  });

  // Handle input changes
  function handleTitleChange() {
    rubricStore.updateRubric({ title });
  }

  function handleDescriptionChange() {
    rubricStore.updateRubric({ description });
  }

  function handleSubjectChange() {
    rubricStore.updateMetadata({ subject });
  }

  function handleGradeLevelChange() {
    rubricStore.updateMetadata({ gradeLevel });
  }

  function handleScoringTypeChange() {
    rubricStore.updateRubric({ scoringType });
  }

  function handleMaxScoreChange() {
    rubricStore.updateRubric({ maxScore });
  }
</script>

<div class="bg-white shadow rounded-lg">
  <div class="px-6 py-4 border-b border-gray-200">
    <h3 class="text-lg font-medium text-gray-900">{$locale ? $_('rubrics.metadataForm.heading', { default: 'Rubric Information' }) : 'Rubric Information'}</h3>
  </div>

  <div class="px-8 py-6 space-y-6">
    <!-- Basic Information -->
    <div class="space-y-4">
      <!-- Title -->
      <div>
        <label for="title" class="block text-sm font-medium text-gray-700">
          {$locale ? $_('rubrics.form.title', { default: 'Title' }) : 'Title'} <span class="text-red-500">*</span>
        </label>
        <input
          id="title"
          type="text"
          bind:value={title}
          oninput={isEditMode ? handleTitleChange : null}
          placeholder={$locale ? $_('rubrics.metadataForm.titlePlaceholder', { default: 'Enter rubric title' }) : 'Enter rubric title'}
          class="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 text-lg"
          readonly={!isEditMode}
          required
        />
      </div>

      <!-- Description -->
      <div>
        <label for="description" class="block text-sm font-medium text-gray-700">
          {$locale ? $_('rubrics.form.descriptionLabel', { default: 'Description' }) : 'Description'} <span class="text-red-500">*</span>
        </label>
        <textarea
          id="description"
          bind:value={description}
          oninput={isEditMode ? handleDescriptionChange : null}
          rows="3"
          placeholder={$locale ? $_('rubrics.metadataForm.descriptionPlaceholder', { default: 'Describe the purpose and context of this rubric' }) : 'Describe the purpose and context of this rubric'}
          class="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
          readonly={!isEditMode}
          required
        ></textarea>
      </div>
    </div>

    <!-- Scoring Configuration -->
    <div class="pt-4 border-t border-gray-200">
      <h4 class="text-md font-medium text-gray-900 mb-4">{$locale ? $_('rubrics.metadataForm.scoringConfig', { default: 'Scoring Configuration' }) : 'Scoring Configuration'}</h4>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <!-- Scoring Type -->
        <div>
          <label for="scoringType" class="block text-sm font-medium text-gray-700">
            {$locale ? $_('rubrics.form.scoringType', { default: 'Scoring Type' }) : 'Scoring Type'} <span class="text-red-500">*</span>
          </label>
          {#if isEditMode}
            <select
              id="scoringType"
              bind:value={scoringType}
              onchange={handleScoringTypeChange}
              class="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="points">{$locale ? $_('rubrics.metadataForm.points', { default: 'Points' }) : 'Points'}</option>
              <option value="percentage">{$locale ? $_('rubrics.metadataForm.percentage', { default: 'Percentage' }) : 'Percentage'}</option>
              <option value="holistic">{$locale ? $_('rubrics.metadataForm.holistic', { default: 'Holistic' }) : 'Holistic'}</option>
              <option value="single-point">{$locale ? $_('rubrics.metadataForm.singlePoint', { default: 'Single Point' }) : 'Single Point'}</option>
              <option value="checklist">{$locale ? $_('rubrics.metadataForm.checklist', { default: 'Checklist' }) : 'Checklist'}</option>
            </select>
          {:else}
            <div class="mt-1 px-3 py-2 bg-gray-50 border border-gray-300 rounded-md text-sm text-gray-900">
              {scoringType || 'points'}
            </div>
          {/if}
        </div>

        <!-- Maximum Score -->
        <div>
          <label for="maxScore" class="block text-sm font-medium text-gray-700">
            {$locale ? $_('rubrics.form.maxScore', { default: 'Maximum Score' }) : 'Maximum Score'} <span class="text-red-500">*</span>
          </label>
          {#if isEditMode}
            <input
              id="maxScore"
              type="number"
              min="1"
              max="1000"
              bind:value={maxScore}
              oninput={handleMaxScoreChange}
              placeholder="10"
              class="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
            />
          {:else}
            <div class="mt-1 px-3 py-2 bg-gray-50 border border-gray-300 rounded-md text-sm text-gray-900">
              {maxScore || 10}
            </div>
          {/if}
        </div>
      </div>
    </div>

    <!-- Optional Metadata -->
    <div class="pt-4 border-t border-gray-200">
      <h4 class="text-md font-medium text-gray-900 mb-2">{$locale ? $_('rubrics.metadataForm.optionalInfo', { default: 'Optional Information' }) : 'Optional Information'}</h4>
      <p class="text-sm text-gray-500 mb-4">
        {$locale ? $_('rubrics.metadataForm.optionalHint', { default: 'These fields are completely optional. Leave blank if not applicable to your rubric.' }) : 'These fields are completely optional. Leave blank if not applicable to your rubric.'}
      </p>
      
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <!-- Subject (Optional) -->
        <div>
          <label for="subject" class="block text-sm font-medium text-gray-500">
            {$locale ? $_('rubrics.form.subject', { default: 'Subject' }) : 'Subject'} <span class="text-xs text-gray-400">({$locale ? $_('rubrics.metadataForm.optional', { default: 'optional' }) : 'optional'})</span>
          </label>
          <input
            id="subject"
            type="text"
            bind:value={subject}
            oninput={isEditMode ? handleSubjectChange : null}
            placeholder={$locale ? $_('rubrics.form.subjectPlaceholder', { default: 'e.g., Mathematics, English, Science' }) : 'e.g., Mathematics, English, Science'}
            class="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
            readonly={!isEditMode}
          />
        </div>

        <!-- Grade Level (Optional) -->
        <div>
          <label for="gradeLevel" class="block text-sm font-medium text-gray-500">
            {$locale ? $_('rubrics.form.gradeLevel', { default: 'Grade Level' }) : 'Grade Level'} <span class="text-xs text-gray-400">({$locale ? $_('rubrics.metadataForm.optional', { default: 'optional' }) : 'optional'})</span>
          </label>
          <input
            id="gradeLevel"
            type="text"
            bind:value={gradeLevel}
            oninput={isEditMode ? handleGradeLevelChange : null}
            placeholder={$locale ? $_('rubrics.metadataForm.gradeLevelPlaceholder', { default: 'e.g., 6-8, 9-12, K-2, Adult Education' }) : 'e.g., 6-8, 9-12, K-2, Adult Education'}
            class="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
            readonly={!isEditMode}
          />
        </div>
      </div>
    </div>

    <!-- Validation Errors -->
    {#if rubricStore.error}
      <div class="bg-red-50 border border-red-200 rounded-md p-4">
        <div class="text-sm text-red-700">{rubricStore.error}</div>
      </div>
    {/if}
  </div>
</div>
