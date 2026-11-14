<script>
    // Creator codes of one organization and the text an instructor without an account reads (#562).
    // The backend is creator_interface/lti_onboarding_router.py; a code's value exists only in the
    // response that creates it, so it is kept here until the admin dismisses it and never reloaded.
    import { onMount, onDestroy } from 'svelte';
    import { _, locale } from '$lib/i18n';
    import { apiFetch } from '$lib/services/apiClient';
    import ConfirmationModal from '$lib/components/modals/ConfirmationModal.svelte';

    /** @type {{ org?: string | null }} */
    let { org = null } = $props();

    let loading = $state(true);
    let loadError = $state('');

    /** @type {any[]} */
    let codes = $state([]);
    let codesAvailable = $state(true);
    let codesError = $state('');
    let codesNotice = $state('');
    let creating = $state(false);
    /** @type {number | null} */
    let togglingId = $state(null);
    let form = $state({ label: '', expires: '', maxUses: '' });
    /** @type {{ code: string, label: string } | null} */
    let created = $state(null);
    let copied = $state(false);
    let copyFailed = $state(false);

    let pageText = $state(''); // the organization's own text; empty when it has none
    let effectiveText = $state(''); // what an instructor reads now
    let textLimit = $state(4000);
    let draft = $state('');
    let textError = $state('');
    let textNotice = $state('');
    let savingText = $state(false);
    let confirmRestore = $state(false);

    const LABEL_LIMIT = 120;
    /** @type {Record<string, string>} */
    const statusClasses = {
        active: 'bg-green-100 text-green-800',
        disabled: 'bg-red-100 text-red-800',
        expired: 'bg-yellow-100 text-yellow-800',
        used_up: 'bg-yellow-100 text-yellow-800'
    };

    let dateFormat = $derived(new Intl.DateTimeFormat($locale || 'en', { dateStyle: 'medium' }));
    let overLimit = $derived(draft.length > textLimit);
    let textChanged = $derived(draft !== pageText);

    /** @param {Date} date */
    const localDay = (date) =>
        `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
    const today = localDay(new Date());

    /**
     * A code with an expiry date works through that whole day, in the admin's own time zone.
     * @param {string} day - YYYY-MM-DD, as a date input gives it
     */
    function endOfDay(day) {
        const [year, month, date] = day.split('-').map(Number);
        return Math.floor(new Date(year, month - 1, date, 23, 59, 59).getTime() / 1000);
    }

    const endpoint = (suffix = '') =>
        `/admin/org-admin/settings/creator-codes${suffix}${org ? `?org=${encodeURIComponent(org)}` : ''}`;

    /**
     * @param {string} [suffix]
     * @param {string} [method]
     * @param {any} [body]
     */
    async function request(suffix = '', method = 'GET', body = undefined) {
        const response = await apiFetch(
            endpoint(suffix),
            body === undefined
                ? { method }
                : { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }
        );
        const data = await response.json().catch(() => null);
        if (!response.ok) {
            const detail = data?.detail;
            // A validation error (422) carries a list of problems instead of one sentence.
            const said = Array.isArray(detail) ? detail.map((item) => item?.msg).filter(Boolean).join(' ') : detail;
            throw Object.assign(new Error('creator codes request refused'), {
                detail: typeof said === 'string' ? said : ''
            });
        }
        return data;
    }

    /** What the API said, or a general message when it said nothing (network, expired session). */
    const messageOf = (/** @type {any} */ error) => error?.detail || $_('creatorCodes.requestFailed');

    /** @type {{ codes: any, text: any }} */
    const timers = { codes: null, text: null };
    /**
     * @param {'codes' | 'text'} area
     * @param {string} message
     */
    function notify(area, message) {
        const set = (/** @type {string} */ value) => {
            if (area === 'codes') codesNotice = value;
            else textNotice = value;
        };
        set(message);
        clearTimeout(timers[area]);
        timers[area] = setTimeout(() => set(''), 3000);
    }
    onDestroy(() => {
        clearTimeout(timers.codes);
        clearTimeout(timers.text);
    });

    async function load() {
        loading = true;
        loadError = '';
        try {
            const data = await request();
            codes = data.codes || [];
            codesAvailable = data.codes_available !== false;
            pageText = data.page_text || '';
            effectiveText = data.effective_page_text || data.default_page_text || '';
            textLimit = data.page_text_limit || 4000;
            draft = pageText;
        } catch (error) {
            loadError = messageOf(error);
        } finally {
            loading = false;
        }
    }
    onMount(load);

    /** @param {SubmitEvent} event */
    async function createCode(event) {
        event.preventDefault();
        codesError = '';
        const typed = form.maxUses === null || form.maxUses === undefined ? '' : String(form.maxUses).trim();
        const maxUses = typed === '' ? null : Number(typed);
        if (maxUses !== null && (!Number.isInteger(maxUses) || maxUses < 1)) {
            codesError = $_('creatorCodes.form.maxUsesInvalid');
            return;
        }
        creating = true;
        try {
            const { code, ...row } = await request('', 'POST', {
                label: form.label.trim(),
                expires_at: form.expires ? endOfDay(form.expires) : null,
                max_uses: maxUses
            });
            codes = [row, ...codes];
            created = { code, label: row.label || '' };
            copied = false;
            copyFailed = false;
            form = { label: '', expires: '', maxUses: '' };
        } catch (error) {
            codesError = messageOf(error);
        } finally {
            creating = false;
        }
    }

    async function copyCode() {
        if (!created) return;
        copyFailed = false;
        try {
            await navigator.clipboard.writeText(created.code);
            copied = true;
        } catch {
            copied = false;
            copyFailed = true;
        }
    }

    function dismissCode() {
        created = null;
        copied = false;
        copyFailed = false;
    }

    /** @param {any} code */
    async function toggleCode(code) {
        codesError = '';
        togglingId = code.id;
        try {
            const updated = await request(`/${code.id}`, 'PUT', { enabled: !code.enabled });
            codes = codes.map((item) => (item.id === updated.id ? updated : item));
            notify(
                'codes',
                $_(updated.enabled ? 'creatorCodes.list.enabledNotice' : 'creatorCodes.list.disabledNotice', {
                    values: { hint: updated.hint }
                })
            );
        } catch (error) {
            codesError = messageOf(error);
        } finally {
            togglingId = null;
        }
    }

    /** @param {string} text - empty restores the default */
    async function saveText(text) {
        textError = '';
        savingText = true;
        try {
            const data = await request('/page-text', 'PUT', { page_text: text });
            pageText = data.page_text || '';
            effectiveText = data.effective_page_text || effectiveText;
            draft = pageText;
            notify('text', $_(pageText ? 'creatorCodes.text.saved' : 'creatorCodes.text.restored'));
        } catch (error) {
            textError = messageOf(error);
        } finally {
            savingText = false;
            confirmRestore = false;
        }
    }

    /** @param {SubmitEvent} event */
    function submitText(event) {
        event.preventDefault();
        if (draft.trim() !== '') saveText(draft);
        // Saving nothing removes the organization's text, so it goes through the same question as the button.
        else if (pageText) confirmRestore = true;
        else draft = '';
    }
</script>

<section class="mt-6 bg-white overflow-hidden shadow rounded-lg" aria-labelledby="creator-codes-title" data-creator-codes>
    <div class="px-4 py-5 sm:p-6">
        <h3 id="creator-codes-title" class="text-lg leading-6 font-medium text-gray-900 mb-4">{$_('creatorCodes.title')}</h3>
        <p class="text-sm text-gray-600 mb-4">{$_('creatorCodes.intro')}</p>

        {#if loading}
            <div class="flex items-center justify-center py-8">
                <div class="inline-block animate-spin rounded-full h-6 w-6 border-b-2 border-brand mr-3"></div>
                <span class="text-gray-500">{$_('creatorCodes.loading')}</span>
            </div>
        {:else if loadError}
            <div class="mb-4 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative" role="alert">
                <span class="block sm:inline">{loadError}</span>
            </div>
        {:else}
            {#if codesAvailable}
                {#if codesError}
                    <div class="mb-4 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative" role="alert">
                        <span class="block sm:inline">{codesError}</span>
                    </div>
                {/if}
                {#if codesNotice}
                    <div class="mb-4 bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded relative" role="status">
                        <span class="block sm:inline">{codesNotice}</span>
                    </div>
                {/if}

                {#if codes.length === 0}
                    <p class="text-sm text-gray-500 italic" data-creator-codes-empty>{$_('creatorCodes.list.empty')}</p>
                {:else}
                    <div class="overflow-x-auto">
                        <table class="min-w-full divide-y divide-gray-200">
                            <thead class="bg-gray-50">
                                <tr>
                                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">{$_('creatorCodes.list.label')}</th>
                                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">{$_('creatorCodes.list.code')}</th>
                                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">{$_('creatorCodes.list.status')}</th>
                                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">{$_('creatorCodes.list.uses')}</th>
                                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">{$_('creatorCodes.list.expires')}</th>
                                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">{$_('creatorCodes.list.actions')}</th>
                                </tr>
                            </thead>
                            <tbody class="bg-white divide-y divide-gray-200">
                                {#each codes as code (code.id)}
                                    <tr class="hover:bg-gray-50" data-creator-code={code.id}>
                                        <td class="px-4 py-3 text-sm {code.label ? 'font-medium text-gray-900' : 'text-gray-400'}">
                                            {code.label || $_('creatorCodes.list.noLabel')}
                                        </td>
                                        <td class="px-4 py-3 text-sm text-gray-700 whitespace-nowrap"><code class="bg-gray-100 px-1 rounded font-mono">…{code.hint}</code></td>
                                        <td class="px-4 py-3 whitespace-nowrap">
                                            <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium {statusClasses[code.status] || 'bg-gray-100 text-gray-800'}">
                                                {statusClasses[code.status] ? $_(`creatorCodes.status.${code.status}`) : code.status}
                                            </span>
                                        </td>
                                        <td class="px-4 py-3 text-sm text-gray-700 whitespace-nowrap">
                                            {#if code.max_uses === null || code.max_uses === undefined}{code.use_count}{:else}{code.use_count} / {code.max_uses}{/if}
                                        </td>
                                        <td class="px-4 py-3 text-sm text-gray-500 whitespace-nowrap">
                                            {code.expires_at ? dateFormat.format(new Date(code.expires_at * 1000)) : $_('creatorCodes.list.noExpiry')}
                                        </td>
                                        <td class="px-4 py-3 text-sm whitespace-nowrap">
                                            <button
                                                type="button"
                                                class="text-sm font-medium disabled:opacity-50 {code.enabled ? 'text-red-600 hover:text-red-800' : 'text-green-600 hover:text-green-800'}"
                                                onclick={() => toggleCode(code)}
                                                disabled={togglingId === code.id}
                                            >
                                                {code.enabled ? $_('creatorCodes.list.disable') : $_('creatorCodes.list.enable')}
                                            </button>
                                        </td>
                                    </tr>
                                {/each}
                            </tbody>
                        </table>
                    </div>
                {/if}

                {#if created}
                    <!-- The only moment the code exists in clear: it stays until the admin says it is saved. -->
                    <div class="mt-6 p-4 bg-green-50 border-2 border-green-400 rounded-lg" aria-live="polite" data-new-creator-code>
                        <h4 class="text-sm font-medium text-green-900 mb-2">
                            {$_('creatorCodes.created.title')}{#if created.label}: {created.label}{/if}
                        </h4>
                        <code class="block select-all break-all bg-white border border-green-300 rounded px-4 py-3 font-mono text-2xl font-bold tracking-wider text-gray-900" data-new-creator-code-value>{created.code}</code>
                        <div class="mt-3 p-3 bg-yellow-50 border-l-4 border-yellow-400 rounded">
                            <p class="text-sm text-yellow-800"><strong>{$_('creatorCodes.created.warning')}</strong></p>
                        </div>
                        <div class="mt-3 flex flex-wrap items-center gap-3">
                            <button
                                type="button"
                                class="bg-brand hover:bg-brand-hover text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline"
                                onclick={copyCode}
                            >
                                {copied ? $_('creatorCodes.created.copied') : $_('creatorCodes.created.copy')}
                            </button>
                            <button
                                type="button"
                                class="bg-gray-200 hover:bg-gray-300 text-gray-800 font-semibold py-2 px-4 rounded focus:outline-none focus:shadow-outline"
                                onclick={dismissCode}
                            >
                                {$_('creatorCodes.created.dismiss')}
                            </button>
                            {#if copyFailed}<span class="text-sm text-red-700" role="alert">{$_('creatorCodes.created.copyFailed')}</span>{/if}
                        </div>
                    </div>
                {:else}
                    <form class="mt-6 p-4 bg-gray-50 rounded-lg" onsubmit={createCode} data-new-creator-code-form>
                        <h4 class="text-sm font-medium text-gray-700 mb-3">{$_('creatorCodes.form.title')}</h4>
                        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                            <div>
                                <label for="creator-code-label" class="block text-sm font-medium text-gray-700">{$_('creatorCodes.form.label')}</label>
                                <input
                                    id="creator-code-label"
                                    type="text"
                                    autocomplete="off"
                                    maxlength={LABEL_LIMIT}
                                    bind:value={form.label}
                                    placeholder={$_('creatorCodes.form.labelPlaceholder')}
                                    class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-brand focus:border-brand sm:text-sm"
                                >
                                <p class="mt-1 text-xs text-gray-500">{$_('creatorCodes.form.labelHint')}</p>
                            </div>
                            <div>
                                <label for="creator-code-expires" class="block text-sm font-medium text-gray-700">{$_('creatorCodes.form.expires')}</label>
                                <input
                                    id="creator-code-expires"
                                    type="date"
                                    min={today}
                                    bind:value={form.expires}
                                    class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-brand focus:border-brand sm:text-sm"
                                >
                                <p class="mt-1 text-xs text-gray-500">{$_('creatorCodes.form.expiresHint')}</p>
                            </div>
                            <div>
                                <label for="creator-code-max-uses" class="block text-sm font-medium text-gray-700">{$_('creatorCodes.form.maxUses')}</label>
                                <input
                                    id="creator-code-max-uses"
                                    type="number"
                                    min="1"
                                    step="1"
                                    bind:value={form.maxUses}
                                    class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-brand focus:border-brand sm:text-sm"
                                >
                                <p class="mt-1 text-xs text-gray-500">{$_('creatorCodes.form.maxUsesHint')}</p>
                            </div>
                        </div>
                        <button
                            type="submit"
                            class="mt-4 bg-brand hover:bg-brand-hover text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline disabled:opacity-50"
                            disabled={creating}
                        >
                            {creating ? $_('creatorCodes.form.creating') : $_('creatorCodes.form.create')}
                        </button>
                    </form>
                {/if}
            {:else}
                <div class="p-4 bg-blue-50 border-l-4 border-blue-400 rounded" data-creator-codes-system>
                    <p class="text-sm text-blue-800">{$_('creatorCodes.text.systemNote')}</p>
                </div>
            {/if}

            <form class="mt-6 pt-6 border-t border-gray-200" onsubmit={submitText} data-creator-codes-text>
                <h4 class="text-base font-medium text-gray-900 mb-2">{$_('creatorCodes.text.title')}</h4>
                <p class="text-sm text-gray-600 mb-4">{$_('creatorCodes.text.intro')}</p>

                {#if textError}
                    <div class="mb-4 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative" role="alert">
                        <span class="block sm:inline">{textError}</span>
                    </div>
                {/if}
                {#if textNotice}
                    <div class="mb-4 bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded relative" role="status">
                        <span class="block sm:inline">{textNotice}</span>
                    </div>
                {/if}

                {#if !pageText}
                    <div class="mb-4 p-4 bg-gray-50 rounded-lg" data-creator-codes-default-text>
                        <p class="text-sm font-medium text-gray-700 mb-2">{$_('creatorCodes.text.usingDefault')}</p>
                        <p class="text-sm text-gray-600 whitespace-pre-line">{effectiveText}</p>
                    </div>
                {/if}

                <label for="creator-codes-page-text" class="block text-sm font-medium text-gray-700">{$_('creatorCodes.text.label')}</label>
                <textarea
                    id="creator-codes-page-text"
                    rows="6"
                    maxlength={textLimit}
                    bind:value={draft}
                    aria-describedby="creator-codes-page-text-counter"
                    class="text-sm mt-1 block w-full border border-gray-300 rounded-md px-3 py-2 shadow-sm focus:outline-none focus:ring-brand focus:border-brand"
                ></textarea>
                <p id="creator-codes-page-text-counter" class="mt-1 text-xs text-right {overLimit ? 'text-red-600 font-semibold' : 'text-gray-500'}">
                    {$_('creatorCodes.text.counter', { values: { count: draft.length, limit: textLimit } })}
                </p>

                <div class="mt-3 flex flex-wrap items-center gap-3">
                    <button
                        type="submit"
                        class="bg-brand hover:bg-brand-hover text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline disabled:opacity-50"
                        disabled={!textChanged || overLimit || savingText}
                    >
                        {savingText ? $_('creatorCodes.text.saving') : $_('creatorCodes.text.save')}
                    </button>
                    {#if pageText}
                        <button
                            type="button"
                            class="bg-gray-200 hover:bg-gray-300 text-gray-800 font-semibold py-2 px-4 rounded focus:outline-none focus:shadow-outline disabled:opacity-50"
                            onclick={() => { confirmRestore = true; }}
                            disabled={savingText}
                        >
                            {$_('creatorCodes.text.restore')}
                        </button>
                    {/if}
                </div>
            </form>
        {/if}
    </div>
</section>

<ConfirmationModal
    bind:isOpen={confirmRestore}
    isLoading={savingText}
    title={$_('creatorCodes.text.restore')}
    message={$_('creatorCodes.text.restoreConfirm')}
    confirmText={$_('creatorCodes.text.restore')}
    variant="warning"
    onconfirm={() => saveText('')}
    oncancel={() => { confirmRestore = false; }}
/>
