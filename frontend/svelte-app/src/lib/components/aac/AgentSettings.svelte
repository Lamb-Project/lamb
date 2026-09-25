<script>
    import { onMount } from 'svelte';
    import { _ } from 'svelte-i18n';
    import axios from 'axios';
    import { getApiUrl } from '$lib/config';
    let { org = null } = $props();
    let settings = $state({provider:'', model:'', language_fallbacks:{},pack_channel:'stable',pack_version:'',utility_provider:'',utility_model:''});
    let packVersions = $state([]);
    let warnings = $state([]);
    let models = $state({});
    let inherited = $state({});
    let loading = $state(true); let saving = $state(false); let error = $state(''); let saved = $state(false);
    const languages = {en:'English',es:'Español',ca:'Català',eu:'Euskara'};
    const endpoint = () => getApiUrl('/admin/org-admin/settings/aac') + (org ? `?org=${encodeURIComponent(org)}` : '');
    const headers = () => ({Authorization: `Bearer ${localStorage.getItem('userToken')}`});
    onMount(async () => {
        try { const {data} = await axios.get(endpoint(), {headers:headers()});
            settings = {provider:'',model:'',language_fallbacks:{},pack_channel:'stable',pack_version:'',utility_provider:'',utility_model:'',...data.settings}; models=data.models; inherited=data.inherited_model; packVersions=data.pack_versions || []; warnings=data.warnings || [];
        } catch(e) { error=e.response?.data?.detail || e.message; } finally {loading=false;}
    });
    function setFallback(source, target) {
        const next={...settings.language_fallbacks};if(target)next[source]=target;else delete next[source];
        settings={...settings,language_fallbacks:next};saved=false;
    }
    async function save() {
        saving=true;error='';saved=false;
        try { const {data}=await axios.put(endpoint(),settings,{headers:headers()});settings=data.settings;saved=true; }
        catch(e) { error=e.response?.data?.detail || e.message; } finally {saving=false;}
    }
</script>
<section class="my-6 rounded-lg border border-blue-200 bg-blue-50 p-6" aria-label={$_('aacSettings.settingsTitle')}>
    <h3 class="text-lg font-semibold">LAMB AGENT</h3>
    <p class="text-sm my-3">{$_('aacSettings.settingsIntro')}</p>
    {#if error}<p role="alert" class="text-red-700">{error}</p>{/if}
    {#each warnings as warning}<p role="alert" class="text-amber-800">{warning}</p>{/each}
    {#if loading}<p>{$_('aacSettings.loadingSettings')}</p>{:else}
    <div class="grid sm:grid-cols-2 gap-4">
        <label>{$_('aacSettings.provider')}<select aria-label={$_('aacSettings.provider')} class="block w-full rounded border p-2" bind:value={settings.provider} onchange={() => {settings.model='';saved=false;}}>
            <option value="">{$_('aacSettings.useDefault')}</option>
            {#each Object.keys(models) as provider}<option value={provider}>{provider}</option>{/each}
            {#if settings.provider && !(settings.provider in models)}<option value={settings.provider}>{settings.provider} ({$_('aacSettings.notEnabled')})</option>{/if}
        </select></label>
        {#if settings.provider && !(models[settings.provider] || []).length}
        <label>{$_('aacSettings.model')}<input aria-label={$_('aacSettings.model')} class="block w-full rounded border p-2" bind:value={settings.model} oninput={() => saved=false} /></label>
        {:else}
        <label>{$_('aacSettings.model')}<select aria-label={$_('aacSettings.model')} class="block w-full rounded border p-2" bind:value={settings.model} disabled={!settings.provider} onchange={() => saved=false}>
            <option value="">{settings.provider ? $_('aacSettings.selectModel') : ([inherited.provider, inherited.model].filter(Boolean).join('/') || $_('aacSettings.orgDefault'))}</option>
            {#each models[settings.provider] || [] as model}<option value={model}>{model}</option>{/each}
            {#if settings.model && !(models[settings.provider] || []).includes(settings.model)}<option value={settings.model}>{settings.model} ({$_('aacSettings.savedSelection')})</option>{/if}
        </select></label>
        {/if}
    </div>
    <h4 class="font-semibold mt-5">{$_('aacSettings.knowledgePack')}</h4>
    <div class="grid sm:grid-cols-2 gap-4">
        <label>{$_('aacSettings.channel')}<select aria-label={$_('aacSettings.channel')} class="block w-full rounded border p-2" bind:value={settings.pack_channel} disabled={!!settings.pack_version} onchange={() => saved=false}>
            <option value="stable">{$_('aacSettings.stable')}</option><option value="rc">{$_('aacSettings.rc')}</option><option value="beta">{$_('aacSettings.beta')}</option>
        </select></label>
        <label>{$_('aacSettings.version')}<select aria-label={$_('aacSettings.version')} class="block w-full rounded border p-2" bind:value={settings.pack_version} onchange={() => saved=false}>
            <option value="">{$_('aacSettings.followChannel')}</option>{#each packVersions as version}<option value={version}>{version}</option>{/each}
            {#if settings.pack_version && !packVersions.includes(settings.pack_version)}<option value={settings.pack_version}>{settings.pack_version} ({$_('aacSettings.savedSelection')})</option>{/if}
        </select></label>
    </div>
    <h4 class="font-semibold mt-5">{$_('aacSettings.utilityTitle')}</h4>
    <p class="text-sm my-2">{$_('aacSettings.utilityIntro')}</p>
    <div class="grid sm:grid-cols-2 gap-4">
        <label>{$_('aacSettings.utilityProvider')}<select aria-label={$_('aacSettings.utilityProvider')} class="block w-full rounded border p-2" bind:value={settings.utility_provider} onchange={() => {settings.utility_model='';saved=false;}}>
            <option value="">{$_('aacSettings.disabled')}</option>{#each Object.keys(models) as provider}<option value={provider}>{provider}</option>{/each}
            {#if settings.utility_provider && !(settings.utility_provider in models)}<option value={settings.utility_provider}>{settings.utility_provider} ({$_('aacSettings.notEnabled')})</option>{/if}
        </select></label>
        {#if settings.utility_provider && !(models[settings.utility_provider] || []).length}
        <label>{$_('aacSettings.utilityModel')}<input aria-label={$_('aacSettings.utilityModel')} class="block w-full rounded border p-2" bind:value={settings.utility_model} oninput={() => saved=false} /></label>
        {:else}
        <label>{$_('aacSettings.utilityModel')}<select aria-label={$_('aacSettings.utilityModel')} class="block w-full rounded border p-2" bind:value={settings.utility_model} disabled={!settings.utility_provider} onchange={() => saved=false}>
            <option value="">{$_('aacSettings.selectModel')}</option>{#each models[settings.utility_provider] || [] as model}<option value={model}>{model}</option>{/each}
            {#if settings.utility_model && !(models[settings.utility_provider] || []).includes(settings.utility_model)}<option value={settings.utility_model}>{settings.utility_model} ({$_('aacSettings.savedSelection')})</option>{/if}
        </select></label>
        {/if}
    </div>
    <h4 class="font-semibold mt-5">{$_('aacSettings.languageSupport')}</h4>
    <p class="text-sm my-2">{$_('aacSettings.languageIntro')}</p>
    <div class="grid sm:grid-cols-2 gap-3">
        {#each Object.entries(languages) as [code,name]}
        <label>{name}<select aria-label={$_('aacSettings.fallback', {values:{name}})} class="block w-full rounded border p-2" value={settings.language_fallbacks[code] || ''} onchange={e => setFallback(code,e.target.value)}>
            <option value="">{$_('aacSettings.supported', {values:{name}})}</option>
            {#each Object.entries(languages).filter(([other]) => other!==code) as [other,label]}<option value={other}>{$_('aacSettings.unsupported', {values:{name:label}})}</option>{/each}
        </select></label>
        {/each}
    </div>
    <button class="mt-4 rounded bg-blue-700 text-white px-4 py-2" onclick={save} disabled={saving || (!!settings.provider && !settings.model) || (!!settings.utility_provider && !settings.utility_model)}>{saving?$_('aacSettings.saving'):$_('aacSettings.saveSettings')}</button>
    {#if saved}<span role="status" class="ml-3 text-green-800">{$_('aacSettings.settingsSaved')}</span>{/if}
    {/if}
</section>
