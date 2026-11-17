<script>
    import { onMount } from 'svelte';
    import { apiFetch } from '$lib/services/apiClient';

    /** @type {{ global?: boolean, org?: string | null }} */
    let { global = false, org = null } = $props();
    let loading = $state(true);
    let saving = $state(false);
    let error = $state('');
    let notice = $state('');
    let moodleUrl = $state('');
    let enabled = $state(false);
    let origins = $state('');
    /** @type {string[]} */
    let allowed = $state([]);
    let restrict = $state(false);
    let systemOrganization = $state(false);
    const endpoint = () => global ? '/admin/lti-access'
        : `/admin/org-admin/settings/lti-access${org ? `?org=${encodeURIComponent(org)}` : ''}`;

    /** @param {'GET' | 'PUT'} method @param {any} [body] */
    async function request(method, body) {
        const response = await apiFetch(endpoint(), {
            method, ...(body ? { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {})
        });
        const data = await response.json();
        if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Could not save LMS access settings.');
        return data;
    }

    /** @param {any} data */
    function apply(data) {
        moodleUrl = data.moodle_url || '';
        systemOrganization = Boolean(data.is_system);
        enabled = data.whitelist_enabled;
        allowed = data.allowed_origins;
        restrict = data.whitelist_enabled;
        origins = data.allowed_origins.join('\n');
    }

    onMount(async () => {
        try { apply(await request('GET')); }
        catch (e) { error = e instanceof Error ? e.message : 'Could not load LMS access settings.'; }
        finally { loading = false; }
    });

    /** @param {SubmitEvent} event */
    async function save(event) {
        event.preventDefault();
        saving = true; error = ''; notice = '';
        try {
            apply(await request('PUT', global
                ? { whitelist_enabled: enabled, allowed_origins: origins.split('\n').map(v => v.trim()).filter(Boolean) }
                : { moodle_url: moodleUrl.trim() }));
            notice = 'LMS access settings saved.';
        } catch (e) { error = e instanceof Error ? e.message : 'Could not save LMS access settings.'; }
        finally { saving = false; }
    }
</script>

<section class="my-6 rounded-lg border border-gray-200 bg-white p-5" data-lti-access={global ? 'global' : 'organization'}>
    <h3 class="text-lg font-medium text-gray-900 mb-2">{global ? 'Allowed LMS installations' : 'Moodle installation'}</h3>
    <p class="text-sm text-gray-600 mb-4">
        {global ? 'Limit which LMS installations can connect to LAMB through LTI. Each organization must also configure its own Moodle.'
            : 'Creator codes and LTI logins for this organization work only from this Moodle installation. Existing organizations must complete this setup too.'}
    </p>
    {#if error}<p role="alert" class="mb-3 text-red-700">{error}</p>{/if}
    {#if notice}<p role="status" class="mb-3 text-green-700">{notice}</p>{/if}
    {#if loading}<p>Loading LMS access settings...</p>
    {:else if !global && systemOrganization}
        <p class="text-sm text-gray-600">Configure Moodle on each regular organization. The system-wide whitelist is in Admin, LTI Settings.</p>
    {:else}
        <form onsubmit={save} class="space-y-4">
            {#if global}
                <label class="flex items-center gap-2"><input type="checkbox" bind:checked={enabled} /> Restrict LTI to the whitelist</label>
                <label class="block text-sm font-medium text-gray-700">
                    Allowed LMS URLs, one per line
                    <textarea bind:value={origins} rows="5" placeholder="https://moodle.example.edu" class="mt-1 w-full rounded border border-gray-300 p-2"></textarea>
                </label>
                <p class="text-sm text-gray-600">Include the installation path if Moodle is in a subdirectory. Matching is exact; wildcards are not supported. An enabled empty whitelist blocks all new LTI launches.</p>
            {:else}
                <label class="block text-sm font-medium text-gray-700">
                    Moodle URL
                    <input type="url" bind:value={moodleUrl} placeholder="https://moodle.example.edu" class="mt-1 w-full rounded border border-gray-300 p-2" />
                </label>
                <p class="text-sm text-gray-600">Use the installation's full URL, including its subdirectory if applicable. Leaving it empty blocks new LTI access to this organization.</p>
                {#if restrict}
                    <p class="text-sm text-gray-600">The system administrator allows: {allowed.join(', ') || 'no LMS installations'}.</p>
                {/if}
            {/if}
            <button type="submit" disabled={saving} class="rounded bg-brand px-4 py-2 text-white disabled:opacity-50">{saving ? 'Saving...' : 'Save LMS access'}</button>
        </form>
    {/if}
</section>
