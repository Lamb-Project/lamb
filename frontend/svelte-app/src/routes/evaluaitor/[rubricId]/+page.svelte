<script>
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { user } from '$lib/stores/userStore';
  import { goto } from '$app/navigation';
  import RubricEditor from '$lib/components/evaluaitor/RubricEditor.svelte';

  // Get rubric ID from URL params
  let rubricId = $derived($page.params.rubricId);

  // Redirect to login if not authenticated
  $effect(() => {
    if (!$user.isLoggedIn) {
      goto('/');
    }
  });

  // Redirect if no rubric ID (shouldn't happen with SvelteKit routing)
  $effect(() => {
    if (!rubricId) {
      goto('/evaluaitor');
    }
  });
</script>

<svelte:head>
  <title>Rubric Editor - Evaluaitor</title>
</svelte:head>

<div class="min-h-screen bg-gray-50">
  <div class="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
    <RubricEditor {rubricId} />
  </div>
</div>
