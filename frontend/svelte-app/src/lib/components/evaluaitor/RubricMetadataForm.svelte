<script>
  import { rubricStore } from '$lib/stores/rubricStore.svelte.js';

  // Local state for form inputs
  let title = $state('');
  let description = $state('');
  let subject = $state('');
  let gradeLevel = $state('');

  // Sync with store
  $effect(() => {
    if (rubricStore.rubric) {
      title = rubricStore.rubric.title || '';
      description = rubricStore.rubric.description || '';
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

  // Subject options
  const subjectOptions = [
    'English', 'Math', 'Science', 'History', 'Art', 'Music', 'Physical Education',
    'Foreign Language', 'Social Studies', 'Computer Science', 'Other'
  ];

  // Grade level options
  const gradeLevelOptions = [
    'Pre-K', 'K', '1st', '2nd', '3rd', '4th', '5th', '6th', '7th', '8th',
    '9th', '10th', '11th', '12th', 'Higher Education', 'Professional Development'
  ];
</script>

<div class="bg-white shadow rounded-lg">
  <div class="px-6 py-4 border-b border-gray-200">
    <h3 class="text-lg font-medium text-gray-900">Rubric Information</h3>
  </div>

  <div class="px-6 py-4 space-y-4">
    <!-- Title -->
    <div>
      <label for="title" class="block text-sm font-medium text-gray-700">
        Title <span class="text-red-500">*</span>
      </label>
      <input
        id="title"
        type="text"
        bind:value={title}
        oninput={handleTitleChange}
        placeholder="Enter rubric title"
        class="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
        required
      />
    </div>

    <!-- Description -->
    <div>
      <label for="description" class="block text-sm font-medium text-gray-700">
        Description <span class="text-red-500">*</span>
      </label>
      <textarea
        id="description"
        bind:value={description}
        oninput={handleDescriptionChange}
        rows="3"
        placeholder="Describe the purpose and context of this rubric"
        class="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
        required
      ></textarea>
    </div>

    <!-- Subject and Grade Level -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div>
        <label for="subject" class="block text-sm font-medium text-gray-700">
          Subject <span class="text-red-500">*</span>
        </label>
        <select
          id="subject"
          bind:value={subject}
          onchange={handleSubjectChange}
          class="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
        >
          <option value="">Select a subject</option>
          {#each subjectOptions as option}
            <option value={option}>{option}</option>
          {/each}
        </select>
      </div>

      <div>
        <label for="gradeLevel" class="block text-sm font-medium text-gray-700">
          Grade Level <span class="text-red-500">*</span>
        </label>
        <select
          id="gradeLevel"
          bind:value={gradeLevel}
          onchange={handleGradeLevelChange}
          class="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
        >
          <option value="">Select grade level</option>
          {#each gradeLevelOptions as option}
            <option value={option}>{option}</option>
          {/each}
        </select>
      </div>
    </div>

    <!-- Scoring Information -->
    {#if rubricStore.rubric}
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4 pt-4 border-t border-gray-200">
        <div>
          <div class="block text-sm font-medium text-gray-700">Scoring Type</div>
          <div class="mt-1 text-sm text-gray-900">
            {rubricStore.rubric.scoringType || 'points'}
          </div>
        </div>

        <div>
          <div class="block text-sm font-medium text-gray-700">Maximum Score</div>
          <div class="mt-1 text-sm text-gray-900">
            {rubricStore.rubric.maxScore || 100}
          </div>
        </div>

        <div>
          <div class="block text-sm font-medium text-gray-700">Total Weight</div>
          <div class="mt-1 text-sm text-gray-900">
            {rubricStore.rubric.criteria?.reduce((sum, c) => sum + (c.weight || 0), 0) || 0}%
          </div>
        </div>
      </div>
    {/if}

    <!-- Validation Errors -->
    {#if rubricStore.error}
      <div class="bg-red-50 border border-red-200 rounded-md p-4">
        <div class="text-sm text-red-700">{rubricStore.error}</div>
      </div>
    {/if}
  </div>
</div>
