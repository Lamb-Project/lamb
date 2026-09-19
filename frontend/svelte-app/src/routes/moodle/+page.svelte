<script>
    import { onMount } from 'svelte';
    import { createSession } from '$lib/services/aacService';
    import { showSession, sidebarBusy } from '$lib/stores/aacStore.svelte';
    import { moodleStatus, connectMoodleQrImage, connectMoodle, disconnectMoodle } from '$lib/services/moodleService';
    import { clearWorkspaceDirty } from '$lib/services/frontendManage';
    let status = $state(null);
    let method = $state('passport');
    let qrImage = $state(null);
    let qrInput = $state(null);
    let credential = $state('');
    let busy = $state(false);
    let error = $state('');
    let notice = $state('');

    async function load() { status = await moodleStatus(); }
    onMount(() => {load().catch(e => error=e.message);});
    let onboardingPending = $state(false);
    async function launchAgent() {
        if ($sidebarBusy) {error='Finish or stop the current agent turn, then open the Moodle summary.'; return;}
        busy=true; error=''; notice='Reading your Moodle course list…';
        try {
            const session = await createSession({moodleOnboarding:true});
            showSession(session.id, session.title);
            onboardingPending=false; notice='Moodle course summary opened in LAMB AGENT.';
        } catch(e) {error='Connected, but the course summary could not be opened. '+e.message;}
        finally {busy=false;}
    }
    async function action(work, message, {form, clearCredential = false, onboard = false} = {}) {
        busy=true;error='';notice='';
        try {
            await work();
            if (clearCredential) credential = '';
            if (form) clearWorkspaceDirty(form);
            notice=message;
            await load();
            if (onboard) {onboardingPending=true; await launchAgent();}
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
    {#if onboardingPending}<button disabled={busy || $sidebarBusy} onclick={launchAgent}>Open Moodle summary in LAMB AGENT</button>{/if}
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
                <form data-aac-edit-form onsubmit={e => {
                    e.preventDefault();
                    if (!qrImage) return;
                    if (qrImage.size > 5 * 1024 * 1024) {error='Select a QR image smaller than 5 MiB.'; return;}
                    const selected = qrImage;
                    action(async () => {
                        try {await connectMoodleQrImage(selected);}
                        finally {qrImage=null; if(qrInput) qrInput.value='';}
                    }, 'Moodle identity verified and connected.', {form:e.currentTarget, onboard:true});
                }}>
                    <h3>Upload your Moodle login QR code</h3>
                    <p>In your Moodle profile, display a fresh QR code for automatic mobile login, then save an image or take a screenshot. Upload it within about three minutes.</p>
                    <label>QR code image
                        <input bind:this={qrInput} type="file" accept="image/png,image/jpeg,image/webp" disabled={busy}
                            onchange={e => {qrImage=e.currentTarget.files?.[0] || null; error='';}} />
                    </label>
                    <p>PNG, JPEG or WebP, up to 5 MiB. The image is used only to connect your account; it is not saved or sent to the agent.</p>
                    <button disabled={busy || !qrImage}>{busy ? 'Connecting…' : 'Connect with QR image'}</button>
                </form>
                <details>
                    <summary>Advanced options: paste a passport or token</summary>
                <form data-aac-edit-form onsubmit={e => {e.preventDefault();action(() => connectMoodle({[method]:credential}), 'Moodle identity verified and connected.', {form:e.currentTarget, clearCredential:true, onboard:true});}}>
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
                </details>
            {/if}
        </div>
    {:else if !error}<p role="status">Loading Moodle settings…</p>{/if}
</section>
<style>
    .moodle-settings{max-width:850px;margin:2rem auto;padding:0 1rem;color:#1f2937}
    h3{font-weight:600;font-size:1.1rem}summary{cursor:pointer;margin:1rem 0}input[type=file]{max-width:100%}
    h1{font-size:1.8rem;font-weight:700}h2{font-size:1.3rem;font-weight:600}p{margin:.8rem 0}
    .card{border:1px solid #cbd5e1;border-radius:.6rem;padding:1.25rem;margin:1.5rem 0;background:white}
    aside{background:#eff6ff;border-left:4px solid #2563eb;padding:.5rem 1rem;margin:1rem 0}
    label{display:flex;flex-direction:column;gap:.4rem;margin:1rem 0;font-weight:500}
    input:not([type=checkbox]),select{border:1px solid #94a3b8;border-radius:.3rem;padding:.6rem;width:100%;background:white}
    button{background:#173f64;color:white;padding:.6rem 1rem;border-radius:.35rem;min-height:44px;margin:.3rem 0}button.secondary{background:white;color:#173f64;border:1px solid #173f64}button:disabled{opacity:.55}
    .error{color:#991b1b;background:#fee2e2;padding:1rem}.notice{color:#166534;background:#dcfce7;padding:1rem}
</style>
