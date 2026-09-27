<script>
    import { locale } from '$lib/i18n';
    import { getApiAccess, setApiAccess } from '$lib/services/apiKeysService';
    import { apiKeysText } from '$lib/utils/apiKeysText';
    let { orgSlug = null } = $props();
    const text = $derived(apiKeysText($locale));
    let enabled = $state(false), loaded = $state(false), saving = $state(false), saved = $state(false), error = $state('');
    $effect(() => {
        const slug = orgSlug;
        loaded = false; error = '';
        getApiAccess(slug).then(r => { enabled = r.api_access === true; loaded = true; }).catch(() => { error = text.error; });
    });
    async function save() {
        saving = true; saved = false; error = '';
        try { enabled = (await setApiAccess(orgSlug, enabled)).api_access === true; saved = true; }
        catch (_) { error = text.error; }
        finally { saving = false; }
    }
</script>

<div class="bg-white overflow-hidden shadow rounded-lg mb-6" data-org-api-access>
    <div class="px-4 py-5 sm:p-6">
        <h3 class="text-lg leading-6 font-medium text-gray-900 mb-4">{text.adminTitle}</h3>
        {#if error}<p class="mb-3 text-red-700" role="alert">{error}</p>{/if}
        <div class="flex items-center">
            <input id="org-api-access" type="checkbox" bind:checked={enabled} disabled={!loaded}
                   class="h-4 w-4 text-brand focus:ring-brand border-gray-300 rounded">
            <label for="org-api-access" class="ml-2 block text-sm text-gray-900">{text.adminLabel}</label>
        </div>
        <p class="mt-2 text-sm text-gray-500">{text.adminHint}</p>
        <button onclick={save} disabled={!loaded || saving}
                class="mt-4 bg-brand hover:bg-brand-hover text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline">{text.save}</button>
        {#if saved}<span class="ml-3 text-sm text-green-700" role="status">{text.saved}</span>{/if}
    </div>
</div>
