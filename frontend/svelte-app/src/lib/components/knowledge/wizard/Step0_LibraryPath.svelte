<!--
  @component Step0_LibraryPath
  First step of the create-knowledge wizard. User picks whether to use an
  existing library or create a new one. If "existing" is picked, a dropdown
  of all accessible libraries is shown.

  Emits:
    - update: { libraryPath, existingLibraryId, libraryName }
    - validity: { valid: boolean }
-->
<script>
    import { createEventDispatcher, tick, untrack } from 'svelte';
    import { getLibraries } from '$lib/services/libraryService';
    import { _ } from '$lib/i18n';

    /** @type {{ wizardState: any }} */
    let { wizardState } = $props();

    const dispatch = createEventDispatcher();

    let libraries = $state(/** @type {any[]} */ ([]));
    let loading = $state(false);
    let error = $state('');
    let path = $state(wizardState.libraryPath || 'new');
    let selectedId = $state(wizardState.existingLibraryId || '');

    $effect(() => {
        if (path === 'existing' && libraries.length === 0 && !loading) {
            loadLibraries();
        }
    });

    $effect(() => {
        // Track local form state only. Reading wizardState/libraries inside
        // the effect would track the parent's mutations and cause an
        // infinite dispatch ↔ update loop.
        const _p = path; const _s = selectedId;
        void _p; void _s;
        untrack(() => {
            const valid = path === 'new' || (path === 'existing' && !!selectedId);
            dispatch('validity', { valid });
            if (path === 'new') {
                dispatch('update', { libraryPath: 'new', existingLibraryId: '' });
            } else if (selectedId) {
                const lib = libraries.find((l) => l.id === selectedId);
                dispatch('update', {
                    libraryPath: 'existing',
                    existingLibraryId: selectedId,
                    libraryName: lib?.name || wizardState.libraryName,
                });
            }
        });
    });

    async function loadLibraries() {
        loading = true;
        error = '';
        try {
            libraries = await getLibraries();
            if (!selectedId && libraries.length > 0) {
                selectedId = libraries[0].id;
            }
            await tick();
        } catch (/** @type {unknown} */ err) {
            error = err instanceof Error ? err.message : 'Failed to load libraries';
        } finally {
            loading = false;
        }
    }
</script>

<div class="space-y-4">
    <h3 class="text-base font-semibold text-gray-900">
        {$_('knowledge.wizard.step0.heading', { default: 'Library' })}
    </h3>
    <p class="text-sm text-gray-600">
        {$_('knowledge.wizard.step0.description', {
            default: 'Pick an existing Library or create a new one. A Knowledge Store is always populated from a Library.'
        })}
    </p>

    <fieldset class="space-y-3">
        <legend class="sr-only">{$_('knowledge.wizard.step0.legend', { default: 'Library path' })}</legend>

        <label class="flex items-start gap-3 p-3 border rounded-md cursor-pointer hover:bg-gray-50 {path === 'new' ? 'border-[#2271b3] bg-blue-50' : 'border-gray-200'}">
            <input type="radio" bind:group={path} value="new" class="mt-1" />
            <div>
                <div class="text-sm font-medium text-gray-900">
                    {$_('knowledge.wizard.createNew', { default: 'Create new' })}
                </div>
                <div class="text-xs text-gray-500">
                    {$_('knowledge.wizard.step0.createNewHint', {
                        default: 'Start a fresh Library and import documents.'
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
                    {$_('knowledge.wizard.step0.useExistingHint', {
                        default: 'Pick a Library you already have and skip ahead to the Knowledge Store steps.'
                    })}
                </div>

                {#if path === 'existing'}
                    <div class="mt-3">
                        {#if loading}
                            <div class="text-sm text-gray-500">
                                {$_('common.loading', { default: 'Loading...' })}
                            </div>
                        {:else if error}
                            <div class="text-sm text-red-600" role="alert">{error}</div>
                        {:else if libraries.length === 0}
                            <div class="text-sm text-gray-500">
                                {$_('knowledge.wizard.step0.noLibraries', {
                                    default: 'No libraries available. Choose "Create new" instead.'
                                })}
                            </div>
                        {:else}
                            <label for="step0-library-select" class="block text-xs font-medium text-gray-700 mb-1">
                                {$_('knowledge.wizard.step0.selectLabel', { default: 'Library' })}
                            </label>
                            <select
                                id="step0-library-select"
                                bind:value={selectedId}
                                class="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                            >
                                {#each libraries as lib (lib.id)}
                                    <option value={lib.id}>{lib.name} ({lib.item_count} items)</option>
                                {/each}
                            </select>
                        {/if}
                    </div>
                {/if}
            </div>
        </label>
    </fieldset>
</div>
