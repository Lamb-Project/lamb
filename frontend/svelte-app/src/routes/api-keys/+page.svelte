<script>
    import { onMount } from 'svelte';
    import { locale } from '$lib/i18n';
    import { getConfig } from '$lib/config.js';
    import { listApiKeys, createApiKey, revokeApiKey } from '$lib/services/apiKeysService';
    import { apiKeysText } from '$lib/utils/apiKeysText';

    const text = $derived(apiKeysText($locale));
    let keys = $state([]), loading = $state(true), enabled = $state(true), error = $state('');
    let label = $state(''), days = $state(''), busy = $state(false), created = $state(null), copied = $state(false);
    const apiBase = (getConfig().api?.lambServer || (typeof window !== 'undefined' ? window.location.origin : '')).replace(/\/$/, '') + '/v1';

    async function load() {
        loading = true; error = '';
        try { keys = await listApiKeys(); enabled = true; }
        catch (e) { if (/not enabled/i.test(e.message)) enabled = false; else error = text.error; }
        finally { loading = false; }
    }
    onMount(load);

    async function create(event) {
        event.preventDefault();
        busy = true; error = ''; copied = false;
        try {
            created = await createApiKey(label.trim(), days ? Number(days) : null);
            label = ''; days = '';
            await load();
        } catch (_) { error = text.error; }
        finally { busy = false; }
    }
    async function copy() {
        try { await navigator.clipboard.writeText(created.api_key); copied = true; } catch (_) { copied = false; }
    }
    async function revoke(key) {
        if (!confirm(text.confirmRevoke)) return;
        error = '';
        try { await revokeApiKey(key.id); await load(); } catch (_) { error = text.error; }
    }
    function when(seconds) {
        return seconds ? new Intl.DateTimeFormat($locale || 'en', {dateStyle:'medium', timeStyle:'short'}).format(new Date(seconds * 1000)) : text.never;
    }
</script>

<svelte:head><title>{text.title} · LAMB</title></svelte:head>

<div class="api-keys" data-api-keys>
    <h1>{text.title}</h1>
    <p class="intro">{text.intro}</p>

    {#if error}<p class="error" role="alert">{error}</p>{/if}

    {#if loading}
        <p role="status">{text.loading}</p>
    {:else if !enabled}
        <p class="notice" role="status" data-api-keys-disabled>{text.disabled}</p>
    {:else}
        {#if created}
            <section class="created" aria-live="polite" data-new-key>
                <p><strong>{text.created}</strong></p>
                <code data-new-key-value>{created.api_key}</code>
                <div class="row">
                    <button onclick={copy}>{copied ? text.copied : text.copy}</button>
                    <button class="secondary" onclick={() => { created = null; }}>{text.done}</button>
                </div>
            </section>
        {/if}

        <form onsubmit={create} class="create">
            <label>{text.label}<input bind:value={label} maxlength="100" placeholder={text.labelHint} /></label>
            <label>{text.expires}<input type="number" min="1" max="365" bind:value={days} /></label>
            <button type="submit" disabled={busy}>{text.create}</button>
        </form>

        {#if !keys.length}
            <p>{text.none}</p>
        {:else}
            <div class="table-wrap">
                <table>
                    <thead><tr><th>{text.prefix}</th><th>{text.label}</th><th>{text.status}</th><th>{text.createdAt}</th><th>{text.lastUsed}</th><th>{text.expiresAt}</th><th></th></tr></thead>
                    <tbody>
                        {#each keys as key (key.id)}
                            <tr data-api-key={key.id}>
                                <td><code>{key.key_prefix}…</code></td>
                                <td>{key.label || ''}</td>
                                <td>{key.status === 'active' ? text.active : text.revoked}</td>
                                <td>{when(key.created_at)}</td>
                                <td>{when(key.last_used_at)}</td>
                                <td>{when(key.expires_at)}</td>
                                <td>{#if key.status === 'active'}<button class="danger" onclick={() => revoke(key)}>{text.revoke}</button>{/if}</td>
                            </tr>
                        {/each}
                    </tbody>
                </table>
            </div>
        {/if}

        <section class="usage">
            <h2>{text.usage}</h2>
            <pre><code>curl {apiBase}/models \
  -H "Authorization: Bearer $LAMB_API_KEY"

curl {apiBase}/chat/completions \
  -H "Authorization: Bearer $LAMB_API_KEY" -H "Content-Type: application/json" \
  -d '{"{"}"model": "lamb_assistant.ID", "messages": [{"{"}"role": "user", "content": "Hello"{"}"}]{"}"}'</code></pre>
        </section>
    {/if}
</div>

<style>
    .api-keys {max-width:960px;margin:0 auto;padding:1.5rem 1rem;}
    h1 {font-size:1.5rem;font-weight:600;margin-bottom:.5rem;}
    h2 {font-size:1.1rem;font-weight:600;margin:1.5rem 0 .5rem;}
    .intro {color:#374151;margin-bottom:1rem;}
    .error {color:#b91c1c;margin:.5rem 0;}
    .notice {background:#fef3c7;border:1px solid #f59e0b;padding:.75rem;border-radius:.375rem;}
    .created {background:#ecfdf5;border:1px solid #10b981;padding:.75rem;border-radius:.375rem;margin-bottom:1rem;}
    .created code {display:block;word-break:break-all;margin:.5rem 0;font-size:.9rem;}
    .row {display:flex;gap:.5rem;flex-wrap:wrap;}
    .create {display:flex;gap:.75rem;flex-wrap:wrap;align-items:flex-end;margin:1rem 0;}
    .create label {display:flex;flex-direction:column;font-size:.875rem;gap:.25rem;}
    input {border:1px solid #d1d5db;border-radius:.375rem;padding:.4rem .5rem;}
    button {background:#2271b3;color:#fff;border-radius:.375rem;padding:.45rem .8rem;font-size:.875rem;}
    button.secondary {background:#6b7280;}
    button.danger {background:#b91c1c;}
    button:disabled {opacity:.6;}
    .table-wrap {overflow-x:auto;}
    table {width:100%;border-collapse:collapse;font-size:.875rem;}
    th, td {text-align:left;padding:.4rem .5rem;border-bottom:1px solid #e5e7eb;white-space:nowrap;}
    pre {background:#f3f4f6;padding:.75rem;border-radius:.375rem;overflow-x:auto;font-size:.8rem;}
</style>
