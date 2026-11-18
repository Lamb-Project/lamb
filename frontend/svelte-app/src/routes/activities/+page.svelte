<script>
  import { user } from '$lib/stores/userStore';
  import { locale } from '$lib/i18n';
  import { apiJson } from '$lib/services/apiClient';
  import { activitiesText, groupActivities } from '$lib/utils/activities';

  /** @type {any[]} */ let activities = $state([]);
  let loading = $state(true);
  let error = $state('');
  /** @type {number | null} */ let opening = $state(null);
  let text = $derived(activitiesText($locale));
  let groups = $derived(groupActivities(activities));

  $effect(() => {
    const token = $user.isLoggedIn && $user.token;
    const controller = new AbortController();
    activities = []; error = ''; opening = null;
    loading = !!token;
    if (token) apiJson('/activities', { token, signal: controller.signal })
      .then(result => { if (!controller.signal.aborted) activities = result.activities; })
      .catch(() => { if (!controller.signal.aborted) error = text.error; })
      .finally(() => { if (!controller.signal.aborted) loading = false; });
    return () => controller.abort();
  });

  /** @param {number} id */
  async function openActivity(id) {
    const token = $user.token || "";
    opening = id; error = '';
    try {
      const result = await apiJson(`/activities/${id}/open`, { method: 'POST', token });
      if ($user.token === token) window.location.assign(result.url);
    } catch (e) {
      if ($user.token === token) error = e instanceof Error ? e.message : text.error;
    } finally { opening = null; }
  }
</script>

<svelte:head><title>{text.title} · LAMB</title></svelte:head>
<main class="max-w-6xl mx-auto px-4 py-8">
  <h1 class="text-2xl font-bold text-gray-900">{text.title}</h1>
  <p class="mt-2 text-gray-600">{text.intro}</p>
  {#if error}<p role="alert" class="mt-4 p-4 bg-red-50 text-red-800 rounded-lg">{error}</p>{/if}
  {#if loading}<p class="mt-6" role="status">{text.loading}</p>
  {:else if groups.length === 0}<p class="mt-6 text-gray-600">{text.empty}</p>
  {:else}
    {#each groups as group (group.key)}
      <section class="mt-6 border rounded-xl bg-white overflow-hidden">
        <header class="bg-gray-50 px-5 py-4 border-b">
          <p class="text-sm text-gray-600 break-words">{group.lms || text.unknownLms}</p>
          <h2 class="text-lg font-semibold">{group.course || text.unknownCourse}</h2>
        </header>
        <ul class="divide-y">
          {#each group.activities as activity (activity.id)}
            <li class="p-5 flex flex-col sm:flex-row sm:items-center gap-4 justify-between">
              <div class="min-w-0">
                <h3 class="font-semibold break-words">{activity.activity_name || `#${activity.id}`}</h3>
                <p class="text-sm text-gray-600">{text[activity.activity_type] || activity.activity_type} · {text.owner}: {activity.owner_name}</p>
                <p class="text-sm mt-1 text-gray-600">{text[activity.relationship] || text.catalogue}{activity.status !== 'active' ? ` · ${text.archived}` : ''}</p>
              </div>
              {#if activity.can_manage}
                <button onclick={() => openActivity(activity.id)} disabled={opening !== null} class="shrink-0 rounded-lg bg-[#2271b3] px-4 py-2 text-white disabled:opacity-50">{text.open}</button>
              {:else}<p class="text-sm text-gray-500 sm:max-w-xs">{text.access}</p>{/if}
            </li>
          {/each}
        </ul>
      </section>
    {/each}
  {/if}
</main>
