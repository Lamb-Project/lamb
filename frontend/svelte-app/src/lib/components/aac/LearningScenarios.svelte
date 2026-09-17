<script>
    import { beforeNavigate } from '$app/navigation';
    import { onMount, onDestroy } from 'svelte';
    import { locale } from '$lib/i18n';
    import { scenarioText } from '$lib/utils/learningScenarioText';
    import { listScenarios, getScenario, createScenario, updateScenario, removeScenario, duplicateScenario, defaultScenario, selectedScenario } from '$lib/services/learningScenarios';
    import { createSession } from '$lib/services/aacService';
    import { showSession, sidebarBusy, activeTabId, frontendDestination } from '$lib/stores/aacStore.svelte';
    import { clearWorkspaceDirty, markWorkspaceDirty } from '$lib/services/frontendManage';
    let { initialId = '', initialTab = 'view', onclose = null, onchange = () => {} } = $props();
    let t = $derived(scenarioText($locale));
    let data = $state({scenarios:[], default_id:null});
    let item = $state(null); let editing = $state(false); let busy = $state(false); let error = $state(''); let form = $state();
    let remoteChanged = $state(false);
    let original = ''; let loadedId = $state('');
    function clearDraft() { if(form) clearWorkspaceDirty(form); }
    function dirty() { return editing && JSON.stringify(item) !== original; }
    export function canLeave() { return !busy && discard(); }
    function discard() { return !dirty() || window.confirm(t.discard); }
    async function load() { data = await listScenarios(); onchange(); }
    async function action(fn) { busy=true; error=''; try { await fn(); } catch(e) { error=e.message; } finally { busy=false; } }
    async function open(id, edit=false) { if (!discard()) return; await action(async()=> { item=await getScenario(id); original=JSON.stringify(item); editing=edit; loadedId=id; remoteChanged=false; }); }
    function fresh() { if (!discard()) return; item={title:'',content:''}; original=JSON.stringify(item); loadedId=''; editing=true; }
    async function save(event) { event.preventDefault(); await action(async()=> { item=item.id ? await updateScenario(item) : await createScenario(item.title,item.content); original=JSON.stringify(item); remoteChanged=false; loadedId=item.id; editing=false; clearDraft(); await load(); }); }
    function back() { if (!discard()) return; clearDraft(); editing=false; item=null; loadedId=''; }
    function close() { if (discard()) { clearDraft(); onclose?.(); } }
    async function refreshFromServer() {
        const id=item?.id;
        try {
            await load();
            if(!id) return;
            const fresh=await getScenario(id);
            if(item?.id!==id) return;
            if(fresh.revision!==item.revision) {
                if(editing) remoteChanged=true;
                else { item=fresh; original=JSON.stringify(fresh); remoteChanged=false; }
            }
        } catch(e) { error=e.message; }
    }
    beforeNavigate(({cancel})=>{if(dirty() && !window.confirm(t.discard)) cancel();});
    async function help() {
        if(!discard()) return;
        await action(async()=> {
            const id=item?.id || null;
            if(editing) { item=id ? await getScenario(id):null; editing=false; clearDraft(); }
            let session=$activeTabId;
            let selected=null;
            if(session) { try { selected=await selectedScenario(session); } catch(_) {} }
            if(!id || selected?.scenario_id!==id) {
                const created=await createSession({learningScenarioId:id, skill:'manage-learning-scenarios'});
                session=created.id;
                showSession(session,created.title,null,null,false);
            } else showSession(session);
            if(id) {
                frontendDestination.set({resource:'learning-scenario',id,tab:'view',route:'/learning-scenarios'});
            }
            onclose?.();
        });
    }
    onMount(()=> {
        let wasBusy=false;
        return sidebarBusy.subscribe(value=> { if(wasBusy && !value) void refreshFromServer(); wasBusy=value; });
    });
    onDestroy(()=>clearDraft());
    onMount(()=>action(async()=> { await load(); if(initialId) { item=await getScenario(initialId); original=JSON.stringify(item); loadedId=item.id; editing=initialTab==='edit'; } }));
</script>
<section class="scenarios" data-aac-resource={loadedId ? 'learning-scenario' : 'learning-scenarios'} data-aac-id={loadedId} data-aac-tab={loadedId ? (editing ? 'edit':'view') : ''}>
    <header><h2>{t.plural}</h2>{#if onclose}<button onclick={close}>{t.close}</button>{/if}</header>
    {#if error}<p role="alert">{error}</p>{/if}
    <p>{t.hint}</p>
    {#if remoteChanged}<p role="status">{t.remoteChanged} <button onclick={()=>open(item.id, true)}>{t.reload}</button></p>{/if}
    {#if item}
        <button onclick={back} disabled={busy}>{t.back}</button>
        {#if editing}
        <form bind:this={form} onsubmit={save} oninput={markWorkspaceDirty} onchange={markWorkspaceDirty}>
            <label>{t.title}<input required maxlength="200" bind:value={item.title} /></label>
            <label>{t.content}<textarea rows="14" maxlength="20000" bind:value={item.content}></textarea></label>
            <button disabled={busy} type="submit">{t.save}</button>
            <button disabled={busy} type="button" onclick={()=> { if(discard()) { item=JSON.parse(original); editing=false; clearDraft(); if(!item.id) item=null; } }}>{t.cancel}</button>
        </form>
        {:else}
            <h3>{item.title}</h3><div class="content">{item.content}</div>
            <button disabled={busy} onclick={()=>{ original=JSON.stringify(item); editing=true; }}>{t.edit}</button>
            <button disabled={busy} onclick={()=>action(async()=>{item=await duplicateScenario(item.id, `${item.title.slice(0,180)} (${t.copy})`); loadedId=item.id; await load();})}>{t.duplicate}</button>
            <button disabled={busy} onclick={()=>action(async()=>{await defaultScenario(data.default_id===item.id ? null:item.id); await load();})}>{data.default_id===item.id ? t.clearDefault:t.setDefault}</button>
            <button disabled={busy} onclick={()=>{if(window.confirm(t.confirmRemove)) action(async()=>{await removeScenario(item); item=null; loadedId=''; await load();});}}>{t.remove}</button>
        {/if}
    {:else}
        <button disabled={busy} onclick={fresh}>{t.create}</button>
        {#each data.scenarios as scenario}<button class="row" disabled={busy} onclick={()=>open(scenario.id)}>{scenario.title}{data.default_id===scenario.id ? ` (${t.default})`:''}</button>{/each}
    {/if}
    <button class="agent-edit" disabled={busy || $sidebarBusy || (editing && !item?.id)} onclick={help}>{item?.id ? t.editWithAgent : t.help}</button>
</section>
<style>
.scenarios {box-sizing:border-box; min-width:0; width:100%; max-width:100%; overflow-wrap:anywhere; padding:20px; overflow:auto; height:100%; color:#173f64;} header {display:flex;justify-content:space-between;gap:12px;} h2,h3 {font-weight:600;margin-bottom:12px;} p {margin:12px 0;} [role=alert] {color:#a12727;} button {white-space:normal; max-width:100%; overflow-wrap:anywhere; padding:9px 12px;margin:5px 4px 5px 0;border:1px solid #cad8e5;border-radius:6px;} button:disabled {opacity:.5;} label {display:block;margin:16px 0;} input,textarea {display:block;width:100%;padding:10px;border:1px solid #94a3b8;border-radius:6px;} .content {white-space:pre-wrap;overflow-wrap:anywhere;padding:12px 0;} .agent-edit {background:#173f64;color:white;} .row {display:block;width:100%;margin-right:0;text-align:left;} button:focus-visible {outline:2px solid #2271b3;}
</style>
