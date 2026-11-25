<script>
    import { onMount } from 'svelte';
    import { _ } from 'svelte-i18n';
    import axios from 'axios';
    import { getApiUrl } from '$lib/config';
    import { renderMarkdownSafe } from '$lib/utils/sanitize';
    let { org = null } = $props();
    const blank = () => ({provider:'', model:'', language_fallbacks:{},pack_line:'stable',pack_dev_mode:false,utility_provider:'',utility_model:''});
    let settings = $state(blank());
    // An organization follows a line of the knowledge pack (stable, a previous stable, rc or beta), never a version.
    /** @type {{line:string, version:string|null, development:boolean, summary:string, about:string}[]} */
    let packLines = $state([]);
    /** @type {{retired_version:string, line:string}|null} */
    let packNotice = $state(null);
    let toolsReference = $state('');
    let openLine = $state('');
    const lineLabels = {stable:'aacSettings.stable', 'legacy-1':'aacSettings.legacy1', 'legacy-2':'aacSettings.legacy2', rc:'aacSettings.rc', beta:'aacSettings.beta'};
    // rc and beta appear only in development mode; an empty previous-version line is not shown at all.
    let visibleLines = $derived(packLines.filter(row => row.development ? settings.pack_dev_mode : (row.line === 'stable' || row.version)));
    let warnings = $state([]);
    let models = $state({});
    let inherited = $state({});
    let loading = $state(true); let saving = $state(false); let error = $state(''); let saved = $state(false);
    const languages = {en:'English',es:'Español',ca:'Català',eu:'Euskara'};
    const endpoint = () => getApiUrl('/admin/org-admin/settings/aac') + (org ? `?org=${encodeURIComponent(org)}` : '');
    const headers = () => ({Authorization: `Bearer ${localStorage.getItem('userToken')}`});
    onMount(async () => {
        try { const {data} = await axios.get(endpoint(), {headers:headers()});
            settings = {...blank(),...data.settings}; models=data.models; inherited=data.inherited_model; warnings=data.warnings || [];
            packLines=data.pack_lines || []; packNotice=data.pack_notice || null; toolsReference=data.tools_reference || '';
        } catch(e) { error=e.response?.data?.detail || e.message; } finally {loading=false;}
    });
    function setFallback(source, target) {
        const next={...settings.language_fallbacks};if(target)next[source]=target;else delete next[source];
        settings={...settings,language_fallbacks:next};saved=false;
    }
    function setDevelopmentMode(on) {
        const line = !on && packLines.find(row => row.line === settings.pack_line)?.development ? 'stable' : settings.pack_line;
        settings={...settings,pack_dev_mode:on,pack_line:line};saved=false;
    }
    async function save() {
        saving=true;error='';saved=false;
        try { const {data}=await axios.put(endpoint(),settings,{headers:headers()});settings={...blank(),...data.settings};saved=true;packNotice=null; }
        catch(e) { error=e.response?.data?.detail || e.message; } finally {saving=false;}
    }
</script>
<section class="my-6 rounded-lg border border-blue-200 bg-blue-50 p-6" aria-label={$_('aacSettings.settingsTitle')}>
    <h3 class="text-lg font-semibold">LAMB LEGATUS</h3>
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
    <p class="text-sm my-2">{$_('aacSettings.packIntro')}</p>
    {#if packNotice}<p role="note" class="my-2 rounded border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900" data-pack-notice>{$_('aacSettings.retiredNotice', {values:{version:packNotice.retired_version, line:$_(lineLabels[packNotice.line] || lineLabels.stable)}})}</p>{/if}
    <div role="radiogroup" aria-label={$_('aacSettings.packChoice')} class="space-y-2">
        {#each visibleLines as row (row.line)}
        <div class="rounded border bg-white p-3" data-pack-line={row.line}>
            <label class="flex items-start gap-3">
                <input type="radio" name="pack-line" class="mt-1" value={row.line} checked={settings.pack_line === row.line} disabled={!row.version}
                    onchange={() => {settings={...settings,pack_line:row.line};saved=false;}} />
                <span class="min-w-0">
                    <span class="font-medium">{$_(lineLabels[row.line])}</span>
                    {#if row.version}<code class="ml-2 text-sm">{row.version}</code>{:else}<span class="ml-2 text-sm text-gray-600">{$_('aacSettings.lineEmpty')}</span>{/if}
                    {#if row.summary}<span class="block text-sm text-gray-700">{row.summary}</span>{/if}
                </span>
            </label>
            {#if row.about}
            <button type="button" class="ml-7 mt-1 text-sm text-blue-800 underline" aria-expanded={openLine === row.line}
                onclick={() => openLine = openLine === row.line ? '' : row.line}>{$_(openLine === row.line ? 'aacSettings.hideVersion' : 'aacSettings.whatsInVersion')}</button>
            {#if openLine === row.line}
            <article class="pack-about prose prose-sm max-w-none mt-3 overflow-x-auto border-t pt-3" data-pack-about={row.line}>{@html renderMarkdownSafe(row.about, {breaks:false})}</article>
            {/if}
            {/if}
        </div>
        {/each}
    </div>
    <label class="mt-3 flex items-start gap-2">
        <input type="checkbox" class="mt-1" checked={settings.pack_dev_mode} onchange={e => setDevelopmentMode(e.currentTarget.checked)} />
        <span>{$_('aacSettings.devMode')}<span class="block text-sm text-gray-700">{$_('aacSettings.devModeHelp')}</span></span>
    </label>
    {#if toolsReference}
    <details class="mt-3 rounded border bg-white p-3">
        <summary class="cursor-pointer font-medium">{$_('aacSettings.toolsTitle')}</summary>
        <p class="my-2 text-sm text-gray-700">{$_('aacSettings.toolsIntro')}</p>
        <pre class="max-h-80 overflow-auto whitespace-pre-wrap text-xs">{toolsReference}</pre>
    </details>
    {/if}
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

<style>
    .pack-about :global(table) { border-collapse: collapse; font-size: 0.85rem; }
    .pack-about :global(th), .pack-about :global(td) { border: 1px solid #d1d5db; padding: 0.3rem 0.5rem; text-align: left; vertical-align: top; }
    .pack-about :global(h2) { font-size: 1rem; font-weight: 600; margin: 0.9rem 0 0.3rem; }
    /* The typography styles print backticks around inline code; a guide name is shown without them. */
    .pack-about :global(code)::before, .pack-about :global(code)::after { content: none; }
</style>
