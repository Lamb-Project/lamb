<!--
  @component Step4_KSPath
  Knowledge Store path picker. Mirrors Step0_LibraryPath but for KSes.

  Emits:
    - update: { ksPath, existingKsId, ksName }
    - validity: { valid: boolean }
-->
<script>
    import { createEventDispatcher, tick } from 'svelte';
    import { getKnowledgeStores } from '$lib/services/knowledgeStoreService';
    import { _ } from '$lib/i18n';

    /** @type {{ wizardState: any }} */
    let { wizardState } = $props();

    const dispatch = createEventDispatcher();

    let stores = $state(/** @type {any[]} */ ([]));
    let loading = $state(false);
    let error = $state('');
    let path = $state(wizardState.ksPath || 'new');
    let selectedId = $state(wizardState.existingKsId || '');

    $effect(() => {
        if (path === 'existing' && stores.length === 0 && !loading) {
            loadStores();
        }
    });

    $effect(() => {
        const valid = path === 'new' || (path === 'existing' && !!selectedId);
        dispatch('validity', { valid });
        if (path === 'new') {
            dispatch('update', { ksPath: 'new', existingKsId: '' });
        } else if (selectedId) {
            const ks = stores.find((s) => s.id === selectedId);
            dispatch('update', {
                ksPath: 'existing',
                existingKsId: selectedId,
                ksName: ks?.name || wizardState.ksName
            });
        }
    });

    async function loadStores() {
        loading = true;
        error = '';
        try {
            stores = await getKnowledgeStores();
            if (!selectedId && stores.length > 0) {
                selectedId = stores[0].id;
            }
            await tick();
        } catch (/** @type {unknown} */ err) {
            error = err instanceof Error ? err.message : 'Failed to load knowledge stores';
        } finally {
            loading = false;
        }
    }
</script>

<div class="space-y-4">
    <h3 class="text-base font-semibold text-gray-900">
        {$_('knowledge.wizard.step4.heading', { default: 'Knowledge Store' })}
    </h3>
    <p class="text-sm text-gray-600">
        {$_('knowledge.wizard.step4.description', {
            default: 'Pick an existing Knowledge Store or create a new one. Existing stores keep their original chunking and embedding settings.'
        })}
    </p>

    <fieldset class="space-y-3">
        <legend class="sr-only">{$_('knowledge.wizard.step4.legend', { default: 'Knowledge Store path' })}</legend>

        <label class="flex items-start gap-3 p-3 border rounded-md cursor-pointer hover:bg-gray-50 {path === 'new' ? 'border-[#2271b3] bg-blue-50' : 'border-gray-200'}">
            <input type="radio" bind:group={path} value="new" class="mt-1" />
            <div>
                <div class="text-sm font-medium text-gray-900">
                    {$_('knowledge.wizard.createNew', { default: 'Create new' })}
                </div>
                <div class="text-xs text-gray-500">
                    {$_('knowledge.wizard.step4.createNewHint', {
                        default: 'Configure a new Knowledge Store with chunking and embedding settings.'
                    })}
                </div>
            </div>
        </label>

        <label class="flex items-start gap-3 p-3 border rounded-md cursor-pointer hover:bg-gray-50 {path === 'existing' ? 'border-[#2271b3] bg-blue-50' : 'border-gray-200'}">
            <input type="radio" bind:group={path} value="existing" class="mt-1" />
            <div class="flex-1">
                <div class="text-sm font-medium text-gray-900">
                    {$_('knowledge.wizard.useExisting', { default: 'Use existing' })}
                </div>
                <div class="text-xs text-gray-500">
                    {$_('knowledge.wizard.step4.useExistingHint', {
                        default: 'Pick a Knowledge Store you already created and ingest more content into it.'
                    })}
                </div>

                {#if path === 'existing'}
                    <div class="mt-3">
                        {#if loading}
                            <div class="text-sm text-gray-500">{$_('common.loading', { default: 'Loading...' })}</div>
                        {:else if error}
                            <div class="text-sm text-red-600" role="alert">{error}</div>
                        {:else if stores.length === 0}
                            <div class="text-sm text-gray-500">
                                {$_('knowledge.wizard.step4.noStores', {
                                    default: 'No knowledge stores available. Choose "Create new" instead.'
                                })}
                            </div>
                        {:else}
                            <label for="step4-ks-select" class="block text-xs font-medium text-gray-700 mb-1">
                                {$_('knowledge.wizard.step4.selectLabel', { default: 'Knowledge Store' })}
                            </label>
                            <select
                                id="step4-ks-select"
                                bind:value={selectedId}
                                class="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                            >
                                {#each stores as s (s.id)}
                                    <option value={s.id}>{s.name} ({s.embedding_vendor}/{s.embedding_model})</option>
                                {/each}
                            </select>
                        {/if}
                    </div>
                {/if}
            </div>
        </label>
    </fieldset>
</div>
