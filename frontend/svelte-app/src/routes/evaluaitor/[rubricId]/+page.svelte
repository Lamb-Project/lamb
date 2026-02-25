<script>
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { base } from '$app/paths';
  import RubricEditor from '$lib/components/evaluaitor/RubricEditor.svelte';

  // Get rubric ID from URL params
  let rubricId = $derived($page.params.rubricId);

  // Auth is handled by layout-level guard in +layout.svelte

  // Redirect if no rubric ID (shouldn't happen with SvelteKit routing)
  $effect(() => {
    if (!rubricId) {
      goto(`${base}/evaluaitor`);
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
