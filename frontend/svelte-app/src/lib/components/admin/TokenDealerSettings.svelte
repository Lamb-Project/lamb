<script>
    import { onMount } from 'svelte';
    import { getTokenDealerSettings, saveTokenDealerSettings, getTokenDealerUsage } from '$lib/services/tokenDealerService';
    let {org = null} = $props();
    let status = $state(null), usage = $state(null);
    let form = $state({enabled:false, policy:'per_student', teacher_allowance_tokens:'', models:[], slot_minutes:10, timezone:'UTC'});
    let exceptions = $state([]);
    let infra = $state({proxy_url:'', public_url:'', proxy_admin_key:''});
    let busy = $state(false), error = $state(''), notice = $state('');
    const POLICIES = [
        {value:'pool', label:'Shared pool per activity', help:'The teacher gives each activity one pot of tokens that all its students share.'},
        {value:'per_student', label:'Allowance per student', help:'Each student gets their own limit per time slot and/or in total. No shared pot.'},
        {value:'both', label:'Both', help:'A shared pool caps the activity, and each student also has a personal limit, so a few heavy users cannot drain the pool.'}
    ];
    const fmt = n => (n === null || n === undefined) ? 'no limit' : Number(n).toLocaleString('en-US');
    function fill(s) {
        status = s;
        const v = s.settings;
        form = {enabled:v.enabled, policy:v.policy, teacher_allowance_tokens:v.teacher_allowance_tokens ?? '',
                models:[...v.models], slot_minutes:v.slot_minutes, timezone:v.timezone};
        exceptions = Object.entries(v.teacher_allowances).map(([email, tokens]) => ({email, tokens}));
        infra = {proxy_url:v.proxy_url || '', public_url:v.public_url || '', proxy_admin_key:''};
    }
    async function load() {
        fill(await getTokenDealerSettings(org));
        usage = await getTokenDealerUsage(org).catch(() => null);
    }
    onMount(() => {load().catch(e => error = e.message);});
    let modelChoices = $derived([...new Set([...(status?.proxy_models || []), ...form.models])].sort());
    function toggleModel(m) {
        form.models = form.models.includes(m) ? form.models.filter(x => x !== m) : [...form.models, m];
    }
    async function save(event) {
        event.preventDefault(); busy = true; error = ''; notice = '';
        const body = {...form, teacher_allowance_tokens: form.teacher_allowance_tokens === '' ? null : Number(form.teacher_allowance_tokens),
            slot_minutes:Number(form.slot_minutes),
            teacher_allowances:Object.fromEntries(exceptions.filter(x => x.email.trim()).map(x => [x.email.trim(), Number(x.tokens)]))};
        if (status.settings.can_edit_infrastructure) Object.assign(body, infra);
        try {
            fill(await saveTokenDealerSettings(body, org));
            notice = 'LLM access settings saved.';
        } catch (e) { error = e.message; } finally { busy = false; }
    }
</script>
<section aria-label="Organization LLM access settings" data-testid="token-dealer-settings">
    {#if error}<p role="alert" class="error">{error}</p>{/if}
    {#if notice}<p role="status" class="notice">{notice}</p>{/if}
    {#if status}
        <div class="card">
            <h2>LLM access</h2>
            <p>Teachers can add an <strong>LLM access</strong> activity to their course. Each student of that activity gets a personal API key for the organization's models, with token limits and a timetable set by the teacher inside the rules below.</p>
            <dl class="facts">
                <dt>Proxy</dt><dd data-testid="proxy-status">{status.settings.proxy_configured ? `connected, ${status.proxy_status}` : 'not connected (ask the system administrator)'}</dd>
                <dt>Address for students</dt><dd>{status.settings.public_url || 'not set'}</dd>
                <dt>Models the proxy serves</dt><dd>{status.proxy_models ? status.proxy_models.join(', ') || 'none' : 'unknown'}</dd>
            </dl>
        </div>
        <form class="card" onsubmit={save}>
            {#if status.settings.can_edit_infrastructure}
                <h3>Proxy connection <span class="tag">system administrator</span></h3>
                <p class="help">Where LAMB creates the students' keys. Leave a field empty to use the deployment's default.</p>
                <label>Proxy admin URL<input name="proxy_url" bind:value={infra.proxy_url} placeholder="http://litellm:4000" disabled={busy} /></label>
                <label>Public URL for students<input name="public_url" bind:value={infra.public_url} placeholder="https://llm.example.edu/v1" disabled={busy} /></label>
                <label>Proxy admin key<input name="proxy_admin_key" type="password" autocomplete="new-password" bind:value={infra.proxy_admin_key}
                    placeholder={status.settings.proxy_admin_key_set ? 'set; leave empty to keep it' : 'not set'} disabled={busy} /></label>
            {/if}
            <h3>Policy</h3>
            <label class="check"><input type="checkbox" name="enabled" bind:checked={form.enabled} disabled={busy} /> Teachers may create LLM access activities</label>
            <fieldset><legend>How tokens are limited</legend>
                {#each POLICIES as p}
                    <label class="check option"><input type="radio" name="policy" value={p.value} bind:group={form.policy} disabled={busy} />
                        <span><strong>{p.label}</strong><br /><span class="help">{p.help}</span></span></label>
                {/each}
            </fieldset>
            <label>Default allowance per teacher (tokens)
                <input name="teacher_allowance_tokens" type="number" min="0" step="1000" bind:value={form.teacher_allowance_tokens} placeholder="empty = no limit" disabled={busy} />
                <span class="help">What one teacher may hand out across all their activities: pools, plus each student's total.</span></label>
            <div class="exceptions"><span class="label">Exceptions for individual teachers</span>
                {#each exceptions as row, i}
                    <div class="row"><input aria-label="Teacher email" type="email" bind:value={row.email} placeholder="teacher@example.edu" disabled={busy} />
                        <input aria-label="Tokens" type="number" min="0" step="1000" bind:value={row.tokens} disabled={busy} />
                        <button type="button" class="secondary" onclick={() => exceptions = exceptions.filter((_, j) => j !== i)}>Remove</button></div>
                {/each}
                <button type="button" class="secondary" onclick={() => exceptions = [...exceptions, {email:'', tokens:0}]} disabled={busy}>Add exception</button>
            </div>
            <fieldset><legend>Models teachers may offer</legend>
                {#each modelChoices as m}
                    <label class="check"><input type="checkbox" checked={form.models.includes(m)} onchange={() => toggleModel(m)} disabled={busy} /> {m}</label>
                {:else}<p class="help">The proxy lists no models yet.</p>{/each}
            </fieldset>
            <div class="two">
                <label>Time slot<select name="slot_minutes" bind:value={form.slot_minutes} disabled={busy}>
                    {#each [5, 10, 15, 20, 30, 60] as m}<option value={m}>{m} minutes</option>{/each}</select>
                    <span class="help">Per-student slot limits refill at the start of each slot.</span></label>
                <label>Time zone of timetables<input name="timezone" bind:value={form.timezone} placeholder="Europe/Madrid" disabled={busy} /></label>
            </div>
            <button disabled={busy}>Save LLM access settings</button>
        </form>
        {#if usage}
            <div class="card" data-testid="token-dealer-usage">
                <h3>Use by teacher</h3>
                {#if usage.teachers.length === 0}<p class="help">No LLM access activities yet.</p>{:else}
                <table><thead><tr><th>Teacher</th><th>Allowance</th><th>Committed</th><th>Used</th><th>Activities</th></tr></thead>
                    <tbody>{#each usage.teachers as t}
                        <tr><td>{t.name}<br /><span class="help">{t.email}</span></td><td>{fmt(t.allowance)}</td><td>{fmt(t.allocated)}</td><td>{fmt(t.used)}</td>
                            <td>{#each t.activities as a}<div>{a.name}{a.course ? ` · ${a.course}` : ''}: {a.students} students, {fmt(a.used)} used{a.refused ? `, ${a.refused} refused` : ''}{a.override !== 'auto' ? ` (${a.override})` : ''}</div>{/each}</td></tr>
                    {/each}</tbody></table>
                <p class="help">Committed = pools plus each student's total allowance. Used = tokens counted by the proxy, refreshed about every 20 seconds.</p>
                {/if}
            </div>
        {/if}
    {/if}
</section>
<style>
    h2{font-size:1.3rem;font-weight:600}h3{font-size:1.1rem;font-weight:600;margin-top:1.2rem}p{margin:.6rem 0}
    .card{border:1px solid #cbd5e1;border-radius:.6rem;padding:1.25rem;margin:1.5rem 0;background:white}
    label{display:flex;flex-direction:column;gap:.4rem;margin:1rem 0;font-weight:500}.check{flex-direction:row;align-items:flex-start;gap:.6rem}
    .option{margin:.6rem 0}fieldset{margin:1rem 0}legend{font-weight:500;margin-bottom:.3rem}
    input:not([type=checkbox]):not([type=radio]),select{border:1px solid #94a3b8;border-radius:.3rem;padding:.6rem;width:100%;background:white}
    button{background:#173f64;color:white;padding:.6rem 1rem;border-radius:.35rem;min-height:44px;margin:.3rem 0}button:disabled{opacity:.55}
    button.secondary{background:white;color:#173f64;border:1px solid #173f64;min-height:36px;padding:.3rem .8rem}
    .help{color:#475569;font-weight:400;font-size:.9rem}.tag{font-size:.75rem;background:#e2e8f0;border-radius:.3rem;padding:.1rem .4rem;font-weight:500}
    .facts{display:grid;grid-template-columns:max-content 1fr;gap:.3rem 1rem;margin-top:.8rem}.facts dt{font-weight:500}
    .exceptions .row{display:grid;grid-template-columns:2fr 1fr auto;gap:.5rem;align-items:center;margin:.4rem 0}.label{font-weight:500}
    .two{display:grid;grid-template-columns:1fr 1fr;gap:1rem}
    table{width:100%;border-collapse:collapse;margin-top:.6rem}th,td{text-align:left;padding:.5rem;border-bottom:1px solid #e2e8f0;vertical-align:top}
    .error{color:#991b1b;background:#fee2e2;padding:1rem}.notice{color:#166534;background:#dcfce7;padding:1rem}
</style>
