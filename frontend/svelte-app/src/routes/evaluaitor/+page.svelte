<script>
  import { onMount } from 'svelte';
  import { user } from '$lib/stores/userStore';
  import RubricsList from '$lib/components/evaluaitor/RubricsList.svelte';

  // Redirect to login if not authenticated
  $effect(() => {
    if (!$user.isLoggedIn) {
      window.location.href = '/';
    }
  });
</script>

<svelte:head>
  <title>Evaluaitor - Educational Rubrics</title>
</svelte:head>

<div class="min-h-screen bg-gray-50">
  <div class="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
    <div class="mb-8">
      <h1 class="text-3xl font-bold text-gray-900">Evaluaitor</h1>
      <p class="mt-2 text-sm text-gray-600">
        Create and manage educational assessment rubrics for your courses and assignments.
      </p>
    </div>

    <RubricsList />
  </div>
</div>
