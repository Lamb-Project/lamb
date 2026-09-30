<script>
    import { onMount } from 'svelte';
    import { locale } from '$lib/i18n';
    import { moodleStatus, moodleConnectionSummary, connectMoodleQrImage, connectMoodle, disconnectMoodle, setApprovalPreferences } from '$lib/services/moodleService';
    import { clearWorkspaceDirty } from '$lib/services/frontendManage';
    import { moodleConnectionText, courseGroups } from '$lib/utils/moodleConnectionText';
    let status = $state(null);
    let summary = $state(null);
    let summaryLoading = $state(false);
    let summaryError = $state(false);
    let requestVersion = 0;
    let method = $state('passport');
    let credential = $state('');
    let qrImage = $state(null);
    let qrInput = $state(null);
    let busy = $state(false);
    let error = $state('');
    let notice = $state('');
    let savingPreferences = $state(false);
    let preferenceNotice = $state('');
    let preferenceError = $state('');
    const text = $derived(moodleConnectionText($locale));
    const groups = $derived(courseGroups(summary?.courses));
    const connection = $derived(summary?.connection || status?.connection);
    const release = $derived(summary?.release || connection?.release);
    function siteLabel(url) {
        try { const parsed = new URL(url); return parsed.host + parsed.pathname.replace(/\/$/, ''); }
        catch { return url || ''; }
    }
    async function loadSummary() {
        const version = ++requestVersion;
        summaryLoading = true; summaryError = false;
        try {
            const result = await moodleConnectionSummary();
            if (version === requestVersion) summary = result;
        } catch {
            if (version === requestVersion) summaryError = true;
        } finally {
            if (version === requestVersion) summaryLoading = false;
        }
    }
    onMount(() => {
        let mounted = true;
        moodleStatus().then(result => {
            if (!mounted) return;
            status = result;
            if (status.connected) loadSummary();
        }).catch(e => { if (mounted) error = e.message; });
        return () => { mounted = false; requestVersion++; };
    });
    async function saveAdvanced(event) {
        const input = event.currentTarget;
        const prior = status.approval_preferences?.advanced_mode === true;
        savingPreferences = true; preferenceError = ''; preferenceNotice = '';
        try {
            status.approval_preferences = await setApprovalPreferences(input.checked);
            preferenceNotice = text.saved;
        } catch (e) { input.checked = prior; preferenceError = e.message; }
        finally { savingPreferences = false; }
    }
    async function connect(work, form) {
        busy = true; error = ''; notice = '';
        try {
            const result = await work();
            clearWorkspaceDirty(form);
            credential = ''; summary = null;
            status = {...status, ...result};
            if (status.connected) loadSummary();
        } catch (e) { error = e.message; }
        finally { busy = false; }
    }
    async function disconnect() {
        busy = true; error = ''; notice = '';
        try {
            await disconnectMoodle();
            requestVersion++;
            summary = null; summaryLoading = false; summaryError = false;
            status = {...status, connected: false, connection: null};
            credential = ''; qrImage = null;
            notice = text.disconnected;
        } catch (e) { error = e.message; }
        finally { busy = false; }
    }
</script>
<div class="connection-page">
    <h1>{text.title}</h1>
    {#if status}<p class="muted intro">{status.connected ? text.connectedIntro : text.disconnectedIntro}</p>{/if}
    {#if error}<p role="alert" class="error">{error}</p>{/if}
    {#if notice}<p role="status" class="notice">{notice}</p>{/if}
    {#if status}
        {#if status.connection}
            <section class="connection-card" aria-label={text.title}>
                <span class:inactive={!status.connected} class="connection-status"><span aria-hidden="true">●</span> {status.connected ? text.connected : text.inactive}</span>
                <h2 class="site">{siteLabel(connection.base_url)}</h2>
                <p class="muted">{release ? `Moodle ${release}` : text.versionUnknown}</p>
                <p class="account">{status.connected ? text.account : text.storedAccount} <strong>{connection.username}</strong>.</p>
                {#if !status.connected}<p class="muted">{text.inactiveHelp}</p>{/if}
                <button type="button" class="secondary disconnect" disabled={busy} onclick={disconnect}>{text.disconnect}</button>
            </section>
            {#if status.connected}
                <section class="courses" aria-labelledby="moodle-course-heading">
                    <div class="course-heading"><h2 id="moodle-course-heading">{text.courses}</h2>{#if summary}<span class="muted">{text.courseCount(summary.courses.length)}</span>{/if}</div>
                    {#if summaryLoading}<p role="status" class="muted">{text.loadingCourses}</p>{/if}
                    {#if summaryError}<div class="summary-error"><p role="alert">{text.coursesError}</p><button type="button" class="secondary" onclick={loadSummary}>{text.retry}</button></div>{/if}
                    {#if summary}
                        {#if summary.courses.length === 0}<p class="muted">{text.noCourses}</p>
                        {:else}
                            <div class="course-groups">
                                {#each ['teacher', 'student', ...(groups.other.length ? ['other'] : [])] as role}
                                    <section class="course-group" class:other={role === 'other'} aria-label={text[role]}>
                                        <h3>{text[role]} <span class="muted count">{text.courseCount(groups[role].length)}</span></h3>
                                        <ul>
                                            {#each groups[role] as course (course.id)}
                                                <li>{course.fullname}<span class="course-detail muted">{course.shortname}</span>
                                                    {#if role === 'other'}<span class="course-detail muted">{course.my_roles_status !== 'available' ? text.unknownRole : course.my_roles?.length ? course.my_roles.map(r => r.name || r.shortname).join(', ') : text.noRole}</span>{/if}
                                                </li>
                                            {:else}<li class="muted">{role === 'teacher' ? text.noTeacher : text.noStudent}</li>{/each}
                                        </ul>
                                    </section>
                                {/each}
                            </div>
                        {/if}
                    {/if}
                </section>
            {/if}
        {:else if status.settings.enabled}
            <section class="connection-card" aria-label={text.connect}>
                <h2>{text.connectTo} {siteLabel(status.settings.base_url)}</h2>
                <p class="muted">{text.qrIntro}</p>
                <ol>{#each text.steps as step}<li>{step}</li>{/each}</ol>
                <form data-aac-edit-form onsubmit={e => {
                    e.preventDefault();
                    if (!qrImage) return;
                    if (qrImage.size > 5 * 1024 * 1024) { error = text.imageTooLarge; return; }
                    const selected = qrImage;
                    connect(async () => {
                        try { return await connectMoodleQrImage(selected); }
                        finally { qrImage = null; if (qrInput) qrInput.value = ''; }
                    }, e.currentTarget);
                }}>
                    <div class="upload">
                        <label>{text.qrLabel}<input bind:this={qrInput} type="file" accept="image/png,image/jpeg,image/webp" disabled={busy}
                            onchange={e => { qrImage = e.currentTarget.files?.[0] || null; error = ''; }} /></label>
                        <p class="muted formats">{text.formats}</p>
                    </div>
                    <button disabled={busy || !qrImage}>{busy ? text.connecting : text.connect}</button>
                </form>
                <details>
                    <summary>{text.alternative}</summary>
                    <form data-aac-edit-form onsubmit={e => { e.preventDefault(); connect(() => connectMoodle({[method]: credential}), e.currentTarget); }}>
                        <label>{text.method}<select bind:value={method} disabled={busy}><option value="passport">{text.passport}</option><option value="token">{text.token}</option></select></label>
                        <p class="muted">{method === 'passport' ? text.passportHelp : text.tokenHelp}</p>
                        <label>{method === 'passport' ? text.passport : text.token}<input type="password" autocomplete="off" spellcheck="false" bind:value={credential} required disabled={busy} /></label>
                        <button disabled={busy || !credential.trim()}>{busy ? text.connecting : text.connect}</button>
                    </form>
                </details>
            </section>
        {:else}<p class="disabled-connector">{text.disabled}</p>{/if}
        <section class="preferences" aria-label={text.advanced}>
            <label class="toggle"><input type="checkbox" checked={status.approval_preferences?.advanced_mode === true} disabled={savingPreferences}
                onchange={saveAdvanced} aria-labelledby="moodle-advanced-label" aria-describedby="moodle-advanced-help" /><span><strong id="moodle-advanced-label">{text.advanced}</strong><span class="muted help" id="moodle-advanced-help">{text.advancedHelp}</span></span></label>
            {#if preferenceNotice}<p role="status" class="notice">{preferenceNotice}</p>{/if}
            {#if preferenceError}<p role="alert" class="error">{preferenceError}</p>{/if}
        </section>
    {:else if !error}<p role="status">{text.loading}</p>{/if}
</div>
<style>
    .connection-page {color:#1f2937}
    h1 {font-size:1.8rem;font-weight:700;margin:0 0 .5rem} h2 {font-size:1.25rem;font-weight:600} h3 {font-size:1rem;font-weight:600}
    p {margin:.5rem 0}.muted {color:#58697d}.intro {margin-bottom:1.5rem}
    .connection-card {background:white;border:1px solid #dce3ec;border-radius:10px;padding:24px;margin:24px 0}
    .connection-status {display:inline-flex;gap:7px;align-items:center;padding:4px 10px;border-radius:20px;color:#176544;background:#edf8f1;font-size:.85rem;font-weight:600;margin-bottom:16px}
    .connection-status.inactive {color:#765414;background:#fff4da}.connection-status span {font-size:.65rem}
    h2.site {font-size:1.45rem;overflow-wrap:anywhere}.account {margin-top:12px}.disconnect {margin-top:18px}
    .course-heading {display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:12px}
    .course-groups {display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}.course-group {border:1px solid #dce3ec;border-radius:9px;background:white;padding:18px;overflow-wrap:anywhere}.course-group.other {grid-column:1/-1}
    .course-group h3 {display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;margin:0 0 14px}.count {font-size:.85rem;font-weight:400}
    ul {list-style:none;padding:0;margin:0}ul li+li {border-top:1px solid #dce3ec;margin-top:12px;padding-top:12px}.course-detail {display:block;font-size:.8rem;margin-top:3px}
    ol {list-style:decimal;padding-left:22px;margin:18px 0}ol li+li {margin-top:8px}
    button {background:#245fc4;color:white;border:1px solid #245fc4;border-radius:7px;padding:9px 15px;min-height:44px;margin-top:14px;font-weight:500}
    button.secondary {background:white;color:#1f2937;border-color:#cbd5e1}button:hover {filter:brightness(.96)}button:disabled {opacity:.55;cursor:default}
    .upload {border:1px dashed #cbd5e1;border-radius:8px;padding:20px;background:#f6f8fb;margin-top:20px}.formats {font-size:.85rem}
    label {display:flex;flex-direction:column;gap:.5rem;font-weight:500;margin:1rem 0}input:not([type=checkbox]),select {border:1px solid #94a3b8;border-radius:6px;padding:.6rem;width:100%;background:white;min-width:0;font-size:1rem}input[type=file] {padding:0;border:0;background:transparent;max-width:100%}
    details {margin-top:22px}summary {cursor:pointer;color:#58697d;min-height:44px;display:list-item;align-content:center}
    .preferences {border-top:1px solid #dce3ec;padding-top:22px;margin-top:32px}.toggle {flex-direction:row;align-items:flex-start;gap:12px;cursor:pointer;margin:0}.toggle input {width:18px;height:18px;flex:none;margin-top:3px;accent-color:#245fc4}.help {display:block;font-size:.85rem;font-weight:400;margin-top:4px}
    .error {color:#991b1b;background:#fee2e2;padding:12px;border-radius:6px;overflow-wrap:anywhere}.notice {color:#176544;font-size:.9rem}.summary-error {padding:12px;background:#fff4da;border-radius:6px}.disabled-connector {padding:20px 0}
    @media(max-width:600px){.course-groups {grid-template-columns:1fr}.connection-card {padding:18px}.course-group {padding:16px}}
</style>
