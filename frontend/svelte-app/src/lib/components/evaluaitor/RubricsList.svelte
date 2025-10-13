<script>
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import {
    fetchRubrics,
    fetchPublicRubrics,
    fetchShowcaseRubrics,
    createRubric,
    duplicateRubric,
    deleteRubric,
    exportRubricJSON,
    exportRubricMarkdown,
    importRubric,
    toggleRubricVisibility
  } from '$lib/services/rubricService';

  // State
  let activeTab = $state('my-rubrics'); // 'my-rubrics' or 'templates'
  let rubrics = $state([]);
  let showcaseRubrics = $state([]);
  let loading = $state(false);
  let error = $state(null);
  let searchQuery = $state('');
  let subjectFilter = $state('');
  let gradeLevelFilter = $state('');
  let currentPage = $state(1);
  let totalRubrics = $state(0);
  let pageSize = $state(10);

  // Computed filters
  let filters = $derived({
    subject: subjectFilter,
    gradeLevel: gradeLevelFilter
  });

  // Load rubrics based on active tab
  async function loadRubrics() {
    loading = true;
    error = null;

    try {
      if (activeTab === 'my-rubrics') {
        const response = await fetchRubrics(pageSize, (currentPage - 1) * pageSize, filters);
        rubrics = response.rubrics;
        totalRubrics = response.total;
      } else if (activeTab === 'templates') {
        const response = await fetchPublicRubrics(pageSize, (currentPage - 1) * pageSize, filters);
        rubrics = response.rubrics;
        totalRubrics = response.total;
      }
    } catch (err) {
      error = err.message || 'Failed to load rubrics';
      console.error('Error loading rubrics:', err);
    } finally {
      loading = false;
    }
  }

  // Load showcase rubrics (always visible)
  async function loadShowcaseRubrics() {
    try {
      showcaseRubrics = await fetchShowcaseRubrics();
    } catch (err) {
      console.error('Error loading showcase rubrics:', err);
    }
  }

  // Handle tab change
  function changeTab(tab) {
    activeTab = tab;
    currentPage = 1; // Reset to first page
    loadRubrics();
  }

  // Handle search
  function handleSearch() {
    currentPage = 1; // Reset to first page
    loadRubrics();
  }

  // Clear filters
  function clearFilters() {
    searchQuery = '';
    subjectFilter = '';
    gradeLevelFilter = '';
    currentPage = 1;
    loadRubrics();
  }

  // Handle rubric actions
  async function handleCreateRubric() {
    try {
      // Create a basic rubric structure
      const newRubric = {
        title: 'New Rubric',
        description: 'A new assessment rubric',
        metadata: {
          subject: 'General',
          gradeLevel: 'K-12'
        },
        criteria: [
          {
            name: 'Content Knowledge',
            description: 'Understanding of subject matter',
            weight: 40,
            levels: [
              { score: 4, label: 'Exemplary', description: 'Demonstrates comprehensive understanding' },
              { score: 3, label: 'Proficient', description: 'Demonstrates adequate understanding' },
              { score: 2, label: 'Developing', description: 'Demonstrates partial understanding' },
              { score: 1, label: 'Beginning', description: 'Demonstrates limited understanding' }
            ]
          }
        ],
        scoringType: 'points',
        maxScore: 100
      };

      const createdRubric = await createRubric(newRubric);
      goto(`/evaluaitor/${createdRubric.rubricId}`);
    } catch (err) {
      error = err.message || 'Failed to create rubric';
    }
  }

  async function handleDuplicateRubric(rubricId) {
    try {
      await duplicateRubric(rubricId);
      loadRubrics(); // Refresh the list
    } catch (err) {
      error = err.message || 'Failed to duplicate rubric';
    }
  }

  async function handleDeleteRubric(rubricId, title) {
    if (!confirm(`Are you sure you want to delete "${title}"? This action cannot be undone.`)) {
      return;
    }

    try {
      await deleteRubric(rubricId);
      loadRubrics(); // Refresh the list
    } catch (err) {
      error = err.message || 'Failed to delete rubric';
    }
  }

  async function handleToggleVisibility(rubricId, isPublic) {
    try {
      await toggleRubricVisibility(rubricId, isPublic);
      loadRubrics(); // Refresh the list
    } catch (err) {
      error = err.message || 'Failed to update visibility';
    }
  }

  async function handleExportJSON(rubricId) {
    try {
      await exportRubricJSON(rubricId);
    } catch (err) {
      error = err.message || 'Failed to export rubric';
    }
  }

  async function handleExportMarkdown(rubricId) {
    try {
      await exportRubricMarkdown(rubricId);
    } catch (err) {
      error = err.message || 'Failed to export rubric';
    }
  }

  async function handleImportRubric(event) {
    const file = event.target.files[0];
    if (!file) return;

    try {
      await importRubric(file);
      loadRubrics(); // Refresh the list
      event.target.value = ''; // Clear file input
    } catch (err) {
      error = err.message || 'Failed to import rubric';
    }
  }

  // Pagination
  function nextPage() {
    if (currentPage * pageSize < totalRubrics) {
      currentPage++;
      loadRubrics();
    }
  }

  function prevPage() {
    if (currentPage > 1) {
      currentPage--;
      loadRubrics();
    }
  }

  // Initialize
  onMount(() => {
    loadRubrics();
    loadShowcaseRubrics();
  });

  // Reactive loading when filters change
  $effect(() => {
    // This will trigger when activeTab changes
    loadRubrics();
  });
</script>

<div class="bg-white shadow rounded-lg">
  <!-- Header -->
  <div class="px-4 py-5 sm:p-6">
    <div class="flex justify-between items-center mb-4">
      <h2 class="text-lg font-medium text-gray-900">My Rubrics</h2>
      <div class="flex space-x-3">
        <button
          onclick={handleCreateRubric}
          disabled={loading}
          class="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50"
        >
          <svg class="-ml-1 mr-2 h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"/>
          </svg>
          Create New Rubric
        </button>
        <label class="inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 cursor-pointer">
          <svg class="-ml-1 mr-2 h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"/>
          </svg>
          Import Rubric
          <input
            type="file"
            accept=".json"
            onchange={handleImportRubric}
            class="hidden"
          />
        </label>
      </div>
    </div>

    <!-- Tabs -->
    <div class="border-b border-gray-200 mb-4">
      <nav class="-mb-px flex space-x-8">
        <button
          onclick={() => changeTab('my-rubrics')}
          class="py-2 px-1 border-b-2 font-medium text-sm {activeTab === 'my-rubrics' ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'}"
        >
          My Rubrics
        </button>
        <button
          onclick={() => changeTab('templates')}
          class="py-2 px-1 border-b-2 font-medium text-sm {activeTab === 'templates' ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'}"
        >
          Templates
          {#if showcaseRubrics.length > 0}
            <span class="ml-2 inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
              {showcaseRubrics.length} featured
            </span>
          {/if}
        </button>
      </nav>
    </div>

    <!-- Search and Filters -->
    <div class="mb-4 flex flex-col sm:flex-row gap-4">
      <div class="flex-1">
        <input
          type="text"
          placeholder="Search rubrics..."
          bind:value={searchQuery}
          oninput={handleSearch}
          class="block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
        />
      </div>
      <div class="flex gap-2">
        <select
          bind:value={subjectFilter}
          onchange={handleSearch}
          class="block border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
        >
          <option value="">All Subjects</option>
          <option value="English">English</option>
          <option value="Math">Math</option>
          <option value="Science">Science</option>
          <option value="History">History</option>
          <option value="Art">Art</option>
          <option value="Other">Other</option>
        </select>
        <select
          bind:value={gradeLevelFilter}
          onchange={handleSearch}
          class="block border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
        >
          <option value="">All Grade Levels</option>
          <option value="K-2">K-2</option>
          <option value="3-5">3-5</option>
          <option value="6-8">6-8</option>
          <option value="9-12">9-12</option>
          <option value="Higher Education">Higher Education</option>
        </select>
        <button
          onclick={clearFilters}
          class="px-3 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
        >
          Clear
        </button>
      </div>
    </div>

    <!-- Error Message -->
    {#if error}
      <div class="mb-4 bg-red-50 border border-red-200 rounded-md p-4">
        <div class="text-sm text-red-700">{error}</div>
      </div>
    {/if}

    <!-- Loading State -->
    {#if loading}
      <div class="text-center py-8">
        <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
        <p class="mt-2 text-sm text-gray-600">Loading rubrics...</p>
      </div>
    {:else}
      <!-- Rubrics Grid -->
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {#each rubrics as rubric}
          <div class="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow">
            <div class="flex justify-between items-start mb-2">
              <h3 class="text-lg font-medium text-gray-900 truncate" title={rubric.title}>
                {rubric.title}
              </h3>
              {#if rubric.isShowcase}
                <span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                  Featured
                </span>
              {:else if rubric.isPublic}
                <span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                  Public
                </span>
              {/if}
            </div>

            <p class="text-sm text-gray-600 mb-2 line-clamp-2" title={rubric.description}>
              {rubric.description || 'No description'}
            </p>

            <div class="text-xs text-gray-500 mb-3">
              <span class="font-medium">Subject:</span> {rubric.subject || 'Not specified'} |
              <span class="font-medium">Grade:</span> {rubric.gradeLevel || 'Not specified'}
            </div>

            <div class="text-xs text-gray-400 mb-4">
              Modified: {new Date(rubric.updatedAt * 1000).toLocaleDateString()}
            </div>

            <!-- Actions -->
            <div class="flex flex-wrap gap-2">
              <button
                onclick={() => goto(`/evaluaitor/${rubric.rubricId}`)}
                class="inline-flex items-center px-2 py-1 border border-gray-300 text-xs font-medium rounded text-gray-700 bg-white hover:bg-gray-50"
              >
                Edit
              </button>

              {#if activeTab === 'my-rubrics'}
                <button
                  onclick={() => handleDuplicateRubric(rubric.rubricId)}
                  class="inline-flex items-center px-2 py-1 border border-gray-300 text-xs font-medium rounded text-gray-700 bg-white hover:bg-gray-50"
                >
                  Duplicate
                </button>

                <button
                  onclick={() => handleToggleVisibility(rubric.rubricId, !rubric.isPublic)}
                  class="inline-flex items-center px-2 py-1 border border-gray-300 text-xs font-medium rounded text-gray-700 bg-white hover:bg-gray-50"
                >
                  {rubric.isPublic ? 'Make Private' : 'Make Public'}
                </button>

                <button
                  onclick={() => handleExportJSON(rubric.rubricId)}
                  class="inline-flex items-center px-2 py-1 border border-gray-300 text-xs font-medium rounded text-gray-700 bg-white hover:bg-gray-50"
                >
                  Export JSON
                </button>

                <button
                  onclick={() => handleExportMarkdown(rubric.rubricId)}
                  class="inline-flex items-center px-2 py-1 border border-gray-300 text-xs font-medium rounded text-gray-700 bg-white hover:bg-gray-50"
                >
                  Export MD
                </button>

                <button
                  onclick={() => handleDeleteRubric(rubric.rubricId, rubric.title)}
                  class="inline-flex items-center px-2 py-1 border border-red-300 text-xs font-medium rounded text-red-700 bg-white hover:bg-red-50"
                >
                  Delete
                </button>
              {:else}
                <button
                  onclick={() => handleDuplicateRubric(rubric.rubricId)}
                  class="inline-flex items-center px-2 py-1 border border-gray-300 text-xs font-medium rounded text-gray-700 bg-white hover:bg-gray-50"
                >
                  Use as Template
                </button>
              {/if}
            </div>
          </div>
        {/each}
      </div>

      <!-- Empty State -->
      {#if rubrics.length === 0}
        <div class="text-center py-12">
          <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
          </svg>
          <h3 class="mt-2 text-sm font-medium text-gray-900">
            {activeTab === 'my-rubrics' ? 'No rubrics yet' : 'No public rubrics available'}
          </h3>
          <p class="mt-1 text-sm text-gray-500">
            {activeTab === 'my-rubrics' ? 'Get started by creating your first rubric.' : 'Check back later for public templates.'}
          </p>
          {#if activeTab === 'my-rubrics'}
            <div class="mt-6">
              <button
                onclick={handleCreateRubric}
                class="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700"
              >
                <svg class="-ml-1 mr-2 h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"/>
                </svg>
                Create New Rubric
              </button>
            </div>
          {/if}
        </div>
      {/if}

      <!-- Pagination -->
      {#if totalRubrics > pageSize}
        <div class="mt-6 flex items-center justify-between">
          <div class="text-sm text-gray-700">
            Showing {((currentPage - 1) * pageSize) + 1} to {Math.min(currentPage * pageSize, totalRubrics)} of {totalRubrics} results
          </div>
          <div class="flex space-x-2">
            <button
              onclick={prevPage}
              disabled={currentPage === 1}
              class="px-3 py-1 border border-gray-300 rounded-md text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
            >
              Previous
            </button>
            <button
              onclick={nextPage}
              disabled={currentPage * pageSize >= totalRubrics}
              class="px-3 py-1 border border-gray-300 rounded-md text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
            >
              Next
            </button>
          </div>
        </div>
      {/if}
    {/if}
  </div>
</div>
