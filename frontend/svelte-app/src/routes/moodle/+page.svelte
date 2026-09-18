<script>
    import { onMount } from 'svelte';
    import { moodleStatus, connectMoodle, disconnectMoodle, configureMoodle } from '$lib/services/moodleService';
    import { clearWorkspaceDirty } from '$lib/services/frontendManage';
    let status = $state(null);
    let settings = $state({enabled:false, base_url:'', mode:'readonly', write_groups:[], allow_grade_write:false});
    let method = $state('passport');
    let credential = $state('');
    let busy = $state(false);
    let error = $state('');
    let notice = $state('');
    let forum = $state(false);
    async function load(resetSettings = false) {
        status = await moodleStatus();
        if (resetSettings) {
            settings = {...status.settings};
            forum = settings.write_groups.includes('forum');
        }
    }
    onMount(() => { load(true).catch(e => error=e.message); });
    async function action(work, message, {form, resetSettings = false, clearCredential = false} = {}) {
        busy=true;error='';notice='';
        try {
            await work();
            if (clearCredential) credential = '';
            if (form) clearWorkspaceDirty(form);
            notice=message;
            await load(resetSettings);
        }
        catch(e) {error=e.message;}
        finally {busy=false;}
    }
</script>
<svelte:head><title>Moodle connection | LAMB</title></svelte:head>
<section class="moodle-settings">
    <h1>Moodle connection</h1>
    <p>Connect your instructor account to the Moodle site allowed by your organization. Enter credentials here, never in the agent chat.</p>
    {#if error}<p role="alert" class="error">{error}</p>{/if}
    {#if notice}<p role="status" class="notice">{notice}</p>{/if}
    {#if status}
        <aside aria-label="Moodle data and AI provider">
            <p>{status.privacy_notice}</p>
            <p>Effective AAC provider: <strong>{status.effective_driver.provider || 'Not configured'}</strong>
                {#if status.effective_driver.model} · {status.effective_driver.model}{/if}</p>
            {#if status.effective_driver.error}<p role="alert">{status.effective_driver.error}</p>{/if}
        </aside>
        <div class="card">
            <h2>Your connection</h2>
            {#if !status.settings.enabled}
                <p>The Moodle connector is disabled. Your organization administrator can enable it.</p>
            {:else}
                <p>Allowed Moodle site: <strong>{status.settings.base_url}</strong></p>
                <p>Access: {status.settings.mode === 'readonly' ? 'Read only' : 'Reads and explicitly permitted writes'}. Writes require your confirmation.</p>
            {/if}
            {#if status.connection}
                <p>{status.connected ? 'Connected' : 'Stored connection is inactive'} as <strong>{status.connection.username}</strong> at {status.connection.base_url}.</p>
                <button class="secondary" disabled={busy} onclick={() => action(disconnectMoodle, 'Moodle disconnected. Stored credentials removed.')}>Disconnect Moodle</button>
            {/if}
            {#if status.settings.enabled}
                <form data-aac-edit-form onsubmit={e => {e.preventDefault();action(() => connectMoodle({[method]:credential}), 'Moodle identity verified and connected.', {form:e.currentTarget, clearCredential:true});}}>
                    <label>Connection method
                        <select bind:value={method} disabled={busy}>
                            <option value="passport">Mobile QR passport</option>
                            <option value="token">Mobile-service token</option>
                        </select>
                    </label>
                    <p>{method === 'passport' ? 'Paste the moodlemobile:// address decoded from a fresh QR code. It is single-use and expires in about three minutes.' : 'Paste the mobile-service token for your own instructor account.'}</p>
                    <label>{method === 'passport' ? 'QR passport' : 'Mobile-service token'}
                        <input type="password" autocomplete="off" spellcheck="false" bind:value={credential} required disabled={busy} />
                    </label>
                    <button disabled={busy || !credential.trim()}>{busy ? 'Working…' : status.connection ? 'Reconnect Moodle' : 'Connect Moodle'}</button>
                </form>
            {/if}
        </div>
        {#if status.can_configure}
            <form class="card" data-aac-edit-form onsubmit={e => {e.preventDefault();action(() => configureMoodle({...settings, write_groups:forum ? ['forum'] : []}), 'Organization Moodle settings saved.', {form:e.currentTarget, resetSettings:true});}}>
                <h2>Organization settings</h2>
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
    {:else if !error}<p role="status">Loading Moodle settings…</p>{/if}
</section>
<style>
    .moodle-settings{max-width:850px;margin:2rem auto;padding:0 1rem;color:#1f2937}
    h1{font-size:1.8rem;font-weight:700}h2{font-size:1.3rem;font-weight:600}p{margin:.8rem 0}
    .card{border:1px solid #cbd5e1;border-radius:.6rem;padding:1.25rem;margin:1.5rem 0;background:white}
    aside{background:#eff6ff;border-left:4px solid #2563eb;padding:.5rem 1rem;margin:1rem 0}
    label{display:flex;flex-direction:column;gap:.4rem;margin:1rem 0;font-weight:500}.check{flex-direction:row;align-items:center}
    input:not([type=checkbox]),select{border:1px solid #94a3b8;border-radius:.3rem;padding:.6rem;width:100%;background:white}
    button{background:#173f64;color:white;padding:.6rem 1rem;border-radius:.35rem;min-height:44px;margin:.3rem 0}button.secondary{background:white;color:#173f64;border:1px solid #173f64}button:disabled{opacity:.55}
    .error{color:#991b1b;background:#fee2e2;padding:1rem}.notice{color:#166534;background:#dcfce7;padding:1rem}
</style>
