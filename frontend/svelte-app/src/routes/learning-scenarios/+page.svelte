<script>
import { page } from '$app/stores';
import LearningScenarios from '$lib/components/aac/LearningScenarios.svelte';
</script>
{#key $page.url.search}
<LearningScenarios initialId={$page.url.searchParams.get('id') || ''} initialTab={$page.url.searchParams.get('aacTab') || 'view'} />
{/key}
