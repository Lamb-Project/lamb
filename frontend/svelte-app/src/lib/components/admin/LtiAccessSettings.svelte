<script>
    import { onMount } from 'svelte';
    import { _ } from '$lib/i18n';
    import { apiFetch } from '$lib/services/apiClient';

    // Optional LMS admission for LTI 1.1 (backend/lamb/lti_access.py). `global` is the system
    // administrator's whitelist; otherwise the lock of one organization. An installation is
    // named by the identifier its LMS sends, and is chosen rather than typed wherever possible.
    /** @type {{ global?: boolean, org?: string | null }} */
    let { global = false, org = null } = $props();
    let loading = $state(true);
    let saving = $state(false);
    let error = $state('');
    let notice = $state('');
    /** @type {string[]} */ let instances = $state([]);
    /** @type {string[]} */ let seen = $state([]);
    /** @type {string[]} */ let allowed = $state([]);
    let enabled = $state(false);
    let restricted = $state(false);
    let mine = $state('');
    let canType = $state(false);
    let typed = $state('');
    let suggestions = $derived(seen.filter(v => !instances.includes(v) && v !== mine));
    const endpoint = () => global ? '/admin/lti-access'
        : `/admin/org-admin/settings/lti-access${org ? `?org=${encodeURIComponent(org)}` : ''}`;

    /** @param {'GET' | 'PUT'} method @param {any} [body] */
    async function request(method, body) {
        const response = await apiFetch(endpoint(), {
            method, ...(body ? { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {})
        });
        const data = await response.json();
        if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : $_('ltiAccess.saveError'));
        return data;
    }

    /** @param {any} data */
    function apply(data) {
        seen = data.seen_instances || [];
        allowed = data.allowed_instances || [];
        restricted = Boolean(data.whitelist_enabled);
        if (global) { enabled = restricted; instances = [...allowed]; canType = true; }
        else { instances = data.locked_instances || []; mine = data.my_instance || ''; canType = Boolean(data.can_type); }
    }

    onMount(async () => {
        try { apply(await request('GET')); }
        catch (e) { error = e instanceof Error ? e.message : $_('ltiAccess.loadError'); }
        finally { loading = false; }
    });

    /** @param {any} body */
    async function save(body) {
        saving = true; error = ''; notice = '';
        try {
            apply(await request('PUT', body));
            notice = $_('ltiAccess.saved');
            window.dispatchEvent(new CustomEvent('lamb-lti-access-changed'));
        } catch (e) { error = e instanceof Error ? e.message : $_('ltiAccess.saveError'); }
        finally { saving = false; }
    }

    /** The whitelist is edited and then saved; the lock is saved at each step. @param {string[]} next */
    function change(next) {
        if (global) instances = next;
        else save({ locked_instances: next });
    }
    /** @param {string} value */
    const add = value => { const v = value.trim(); if (v && !instances.includes(v)) change([...instances, v]); };
    /** @param {string} value */
    const remove = value => change(instances.filter(v => v !== value));
    function addTyped() { add(typed); typed = ''; }
    /** @param {SubmitEvent} event */
    function saveWhitelist(event) {
        event.preventDefault();
        save({ whitelist_enabled: enabled, allowed_instances: instances });
    }
</script>

<section class="my-6 rounded-lg border border-gray-200 bg-white p-5" data-lti-access={global ? 'global' : 'organization'}>
    <h3 class="text-lg font-medium text-gray-900 mb-2">{$_(global ? 'ltiAccess.globalTitle' : 'ltiAccess.title')}</h3>
    <p class="text-sm text-gray-600 mb-4">{$_(global ? 'ltiAccess.globalIntro' : 'ltiAccess.intro')}</p>
    {#if error}<p role="alert" class="mb-3 text-red-700">{error}</p>{/if}
    {#if notice}<p role="status" class="mb-3 text-green-700">{notice}</p>{/if}
    {#if loading}<p>{$_('ltiAccess.loading')}</p>
    {:else}
        <form onsubmit={saveWhitelist} class="space-y-4">
            {#if global}
                <label class="flex items-center gap-2"><input type="checkbox" bind:checked={enabled} /> {$_('ltiAccess.restrict')}</label>
                {#if enabled && instances.length === 0}<p class="text-sm text-amber-700">{$_('ltiAccess.emptyWarning')}</p>{/if}
            {:else}
                <p class="text-sm font-medium text-gray-900" data-lti-lock-state={instances.length ? 'locked' : 'open'}>
                    {$_(instances.length ? 'ltiAccess.lockedTo' : 'ltiAccess.unlocked')}
                </p>
            {/if}
            {#if instances.length}
                <ul class="space-y-1" aria-label={$_('ltiAccess.listLabel')}>
                    {#each instances as instance (instance)}
                        <li class="flex items-center justify-between gap-3 rounded border border-gray-200 px-3 py-2">
                            <code class="break-all text-sm">{instance}</code>
                            <button type="button" disabled={saving} onclick={() => remove(instance)}
                                aria-label={$_('ltiAccess.removeNamed', { values: { instance } })}
                                class="shrink-0 text-sm text-red-700 underline disabled:opacity-50">{$_('ltiAccess.remove')}</button>
                        </li>
                    {/each}
                </ul>
            {/if}
            {#if !global}
                {#if mine && !instances.includes(mine)}
                    <p class="text-sm text-gray-700">{$_('ltiAccess.mine', { values: { instance: mine } })}</p>
                    <button type="button" disabled={saving} onclick={() => add(mine)}
                        class="rounded bg-brand px-4 py-2 text-white disabled:opacity-50">
                        {$_(instances.length ? 'ltiAccess.addMine' : 'ltiAccess.lockMine', { values: { instance: mine } })}
                    </button>
                {:else if !mine && !canType && suggestions.length === 0 && instances.length === 0}
                    <p class="text-sm text-gray-600">{$_('ltiAccess.noMine')}</p>
                {/if}
            {/if}
            {#if suggestions.length}
                <div>
                    <p class="text-sm text-gray-700 mb-1">{$_(global ? 'ltiAccess.seenGlobal' : 'ltiAccess.seen')}</p>
                    <ul class="space-y-1">
                        {#each suggestions as instance (instance)}
                            <li class="flex items-center justify-between gap-3 px-3 py-1">
                                <code class="break-all text-sm">{instance}</code>
                                <button type="button" disabled={saving} onclick={() => add(instance)}
                                    aria-label={$_('ltiAccess.addNamed', { values: { instance } })}
                                    class="shrink-0 text-sm text-blue-700 underline disabled:opacity-50">{$_('ltiAccess.add')}</button>
                            </li>
                        {/each}
                    </ul>
                </div>
            {/if}
            {#if canType}
                <div>
                    <label class="block text-sm font-medium text-gray-700">
                        {$_('ltiAccess.typeLabel')}
                        <input type="text" bind:value={typed} maxlength="255" placeholder="moodle.example.edu"
                            class="mt-1 w-full rounded border border-gray-300 p-2" />
                    </label>
                    <p class="mt-1 text-sm text-gray-600">{$_('ltiAccess.typeHelp')}</p>
                    <button type="button" disabled={saving || !typed.trim()} onclick={addTyped}
                        class="mt-2 rounded border border-gray-300 px-3 py-1 text-sm disabled:opacity-50">{$_('ltiAccess.addTyped')}</button>
                </div>
            {/if}
            {#if !global && restricted}
                <p class="text-sm text-gray-600">{$_('ltiAccess.whitelistNote', { values: { list: allowed.join(', ') || $_('ltiAccess.none') } })}</p>
            {/if}
            {#if global}
                <button type="submit" disabled={saving} class="rounded bg-brand px-4 py-2 text-white disabled:opacity-50">
                    {$_(saving ? 'ltiAccess.saving' : 'ltiAccess.save')}
                </button>
            {/if}
        </form>
    {/if}
</section>
