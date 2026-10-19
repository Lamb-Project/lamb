<script>
    import { onMount } from 'svelte';
    import { getApiUrl, getLambApiUrl } from '$lib/config';

    let registrations = $state([]);
    let organizations = $state([]);
    let info = $state(null);
    let error = $state('');
    let message = $state('');
    let busy = $state(false);
    let editing = $state(null);
    const empty = () => ({ name: '', issuer: '', client_id: '', authorization_url: '', token_url: '', jwks_url: '',
        deployment_ids: '', organization_ids: [], service_origins: '', enabled: true });
    let form = $state(empty());

    async function call(url, options = {}) {
        const response = await fetch(url, { ...options, headers: {
            'Content-Type': 'application/json', 'Authorization': `Bearer ${localStorage.getItem('userToken')}`,
            ...(options.headers || {})
        }});
        const data = await response.json();
        if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Check the registration values.');
        return data;
    }
    const endpoint = path => getLambApiUrl(`/lamb/v1/lti/${path}`);
    const lines = value => value.split(/\r?\n/).map(v => v.trim()).filter(Boolean);

    async function refresh() {
        const [rows, orgs] = await Promise.all([call(endpoint('registrations')), call(getApiUrl('/admin/organizations/list'))]);
        registrations = rows;
        organizations = orgs.data || [];
        try { info = await call(endpoint('registration-info')); }
        catch (e) { error = e.message; }
    }
    onMount(async () => { try { await refresh(); } catch (e) { error = e.message; } });

    function edit(row) {
        editing = row.id;
        form = { name: row.name, issuer: row.issuer, client_id: row.client_id,
            authorization_url: row.authorization_url, token_url: row.token_url, jwks_url: row.jwks_url,
            deployment_ids: row.deployment_ids.join('\n'), organization_ids: [...row.organization_ids],
            service_origins: row.service_origins.join('\n'), enabled: row.enabled };
        error = ''; message = '';
    }
    function reset() { editing = null; form = empty(); error = ''; message = ''; }
    async function save(event) {
        event.preventDefault(); busy = true; error = ''; message = '';
        try {
            if (!form.organization_ids.length) throw new Error('Choose at least one allowed organization.');
            const data = { ...form, deployment_ids: lines(form.deployment_ids),
                organization_ids: form.organization_ids.map(Number), service_origins: lines(form.service_origins) };
            await call(endpoint(`registrations${editing ? `/${editing}` : ''}`), {
                method: editing ? 'PUT' : 'POST', body: JSON.stringify(data)
            });
            await refresh(); editing = null; form = empty(); message = 'LTI 1.3 registration saved.';
        } catch (e) { error = e.message; }
        finally { busy = false; }
    }
    async function rotate() {
        busy = true; error = ''; message = '';
        try { await call(endpoint('keys/rotate'), { method: 'POST' }); message = 'Signing key rotated. The previous public key remains available for 24 hours.'; }
        catch (e) { error = e.message; }
        finally { busy = false; }
    }
</script>

<section class="mt-8 bg-white shadow rounded-lg p-6" aria-labelledby="lti13-title">
    <h3 id="lti13-title" class="text-lg font-semibold text-gray-800">LTI 1.3 platform registrations</h3>
    <p class="mt-2 text-sm text-gray-600">Connect the unified activity tool to an LMS using LTI 1.3. Instructors link their LAMB account on their first launch. Grade return uses the LMS grade column and AGS score permission.</p>
    {#if error}<p role="alert" class="mt-4 text-red-700">{error}</p>{/if}
    {#if message}<p role="status" class="mt-4 text-green-700">{message}</p>{/if}
    {#if info}
        <div class="mt-4 rounded bg-gray-50 p-4">
            <h4 class="font-medium">Enter these tool values in your LMS</h4>
            {#each [['Login initiation URL', info.login_url], ['Launch and redirect URL', info.launch_url], ['Public keyset URL', info.jwks_url]] as entry}
                <label class="mt-3 block text-sm">{entry[0]}
                    <input class="mt-1 w-full rounded border border-gray-300 p-2 font-mono text-xs" readonly value={entry[1]} />
                </label>
            {/each}
            <p class="mt-3 text-xs text-gray-600">Manual registration; core resource launches and AGS grade return. Content selection, roster access and dynamic registration are not included.</p>
        </div>
    {/if}
    <div class="mt-5 overflow-x-auto">
        <table class="w-full text-sm text-left">
            <thead><tr class="border-b"><th class="p-2">Platform</th><th class="p-2">Client ID</th><th class="p-2">Status</th><th class="p-2">Action</th></tr></thead>
            <tbody>
                {#each registrations as row}
                    <tr class="border-b"><td class="p-2">{row.name}<div class="text-xs text-gray-500 break-all">{row.issuer}</div></td>
                        <td class="p-2 break-all">{row.client_id}</td><td class="p-2">{row.enabled ? 'Enabled' : 'Disabled'}</td>
                        <td class="p-2"><button type="button" class="text-brand underline" onclick={() => edit(row)}>Edit</button></td></tr>
                {:else}<tr><td colspan="4" class="p-3 text-gray-500">No LTI 1.3 platforms registered.</td></tr>{/each}
            </tbody>
        </table>
    </div>
    <form class="mt-6 space-y-4" onsubmit={save}>
        <h4 class="font-semibold">{editing ? 'Edit registration' : 'Add a platform'}</h4>
        {#if editing}<p class="text-sm text-gray-600">Saving invalidates LAMB activity-page sessions for this registration. Users can launch again from the LMS. Existing chat sessions and issued API keys have separate access controls.</p>{/if}
        <div class="grid gap-4 md:grid-cols-2">
            <label class="block text-sm">Name<input required maxlength="200" class="mt-1 w-full rounded border border-gray-300 p-2" bind:value={form.name} /></label>
            <label class="block text-sm">Client ID<input required readonly={!!editing} class="mt-1 w-full rounded border border-gray-300 p-2" bind:value={form.client_id} /></label>
            <label class="block text-sm md:col-span-2">Platform issuer<input required type="url" readonly={!!editing} placeholder="https://moodle.example.edu" class="mt-1 w-full rounded border border-gray-300 p-2" bind:value={form.issuer} /></label>
            <label class="block text-sm">Authorization URL<input required type="url" class="mt-1 w-full rounded border border-gray-300 p-2" bind:value={form.authorization_url} /></label>
            <label class="block text-sm">Token URL<input required type="url" class="mt-1 w-full rounded border border-gray-300 p-2" bind:value={form.token_url} /></label>
            <label class="block text-sm md:col-span-2">Platform public keyset URL<input required type="url" class="mt-1 w-full rounded border border-gray-300 p-2" bind:value={form.jwks_url} /></label>
            <label class="block text-sm">Deployment IDs, one per line<textarea required rows="3" class="mt-1 w-full rounded border border-gray-300 p-2" bind:value={form.deployment_ids}></textarea></label>
            <label class="block text-sm">Allowed grade-service origins, one per line<textarea required rows="3" placeholder="https://moodle.example.edu" class="mt-1 w-full rounded border border-gray-300 p-2" bind:value={form.service_origins}></textarea></label>
        </div>
        <fieldset><legend class="text-sm font-medium">Organizations this platform may use</legend>
            <div class="mt-2 flex flex-wrap gap-4">{#each organizations as org}<label class="text-sm"><input type="checkbox" value={Number(org.id)} bind:group={form.organization_ids} /> {org.name} ({org.slug})</label>{/each}</div>
        </fieldset>
        <label class="block text-sm"><input type="checkbox" bind:checked={form.enabled} /> Enabled</label>
        <div class="flex gap-3"><button type="submit" disabled={busy} class="rounded bg-brand px-4 py-2 text-white disabled:opacity-50">Save LTI 1.3 registration</button>
            {#if editing}<button type="button" onclick={reset} class="rounded border px-4 py-2">Cancel edit</button>{/if}</div>
    </form>
    <details class="mt-6 border-t pt-4"><summary class="cursor-pointer text-sm font-medium">Signing key rotation</summary>
        <p class="my-3 text-sm text-gray-600">LMS platforms fetch the public keyset URL above. Keep the persistent key directory with your database backups. Rotation retains the previous public key for 24 hours.</p>
        <button type="button" disabled={busy} onclick={rotate} class="rounded border px-4 py-2 text-sm">Rotate signing key</button>
    </details>
</section>
