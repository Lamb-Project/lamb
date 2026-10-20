<script>
    import { onMount } from 'svelte';
    import { getMoodleSettings, configureMoodle } from '$lib/services/moodleService';
    import { clearWorkspaceDirty } from '$lib/services/frontendManage';
    let {org = null} = $props();
    let status = $state(null);
    let settings = $state({enabled:false, base_url:'', mode:'readonly', write_groups:[], allow_grade_write:false});
    let forum = $state(false), busy = $state(false), error = $state(''), notice = $state('');
    async function load() {
        status = await getMoodleSettings(org);
        settings = {...status.settings}; forum = settings.write_groups.includes('forum');
    }
    onMount(() => {load().catch(e => error=e.message);});
    async function save(event) {
        event.preventDefault(); const form=event.currentTarget; busy=true; error=''; notice='';
        try {
            await configureMoodle({...settings,write_groups:forum ? ['forum'] : []},org);
            clearWorkspaceDirty(form);
            notice='Organization Moodle settings saved.';
            window.dispatchEvent(new Event('moodle-settings-changed'));
        } catch(e) {error=e.message;} finally {busy=false;}
    }
</script>
<section aria-label="Organization Moodle settings">
    {#if error}<p role="alert" class="error">{error}</p>{/if}
    {#if notice}<p role="status" class="notice">{notice}</p>{/if}
        {#if status}
            <form class="card" data-aac-edit-form onsubmit={save}>
                <h2>Moodle</h2>
                <label class="check"><input type="checkbox" bind:checked={settings.enabled} disabled={busy} /> Enable Moodle connector</label>
                <label>Allowed Moodle base URL<input type="url" bind:value={settings.base_url} required={settings.enabled} placeholder="https://moodle.example.org" disabled={busy} /></label>
                <label>Access mode<select bind:value={settings.mode} disabled={busy}><option value="readonly">Read only</option><option value="full">Allow selected writes</option></select></label>
                <label class="check"><input type="checkbox" bind:checked={forum} disabled={busy || settings.mode !== 'full'} /> Allow forum replies and new discussions</label>
                <label class="check"><input type="checkbox" bind:checked={settings.allow_grade_write} disabled={busy || settings.mode !== 'full'} /> Allow reviewed grade proposals to be saved</label>
                <p>Grade writes are off by default. The teacher must see the submission, proposed grade and rationale before confirming a save. AI assessment remains a proposal for teacher review.</p>
                <p>{status.privacy_notice}</p>
                <button disabled={busy}>Save organization settings</button>
            </form>
        {/if}
</section>
<style>
    h2{font-size:1.3rem;font-weight:600}p{margin:.8rem 0}
    .card{border:1px solid #cbd5e1;border-radius:.6rem;padding:1.25rem;margin:1.5rem 0;background:white}
    label{display:flex;flex-direction:column;gap:.4rem;margin:1rem 0;font-weight:500}.check{flex-direction:row;align-items:center}
    input:not([type=checkbox]),select{border:1px solid #94a3b8;border-radius:.3rem;padding:.6rem;width:100%;background:white}
    button{background:#173f64;color:white;padding:.6rem 1rem;border-radius:.35rem;min-height:44px;margin:.3rem 0}button:disabled{opacity:.55}
    .error{color:#991b1b;background:#fee2e2;padding:1rem}.notice{color:#166534;background:#dcfce7;padding:1rem}
</style>
