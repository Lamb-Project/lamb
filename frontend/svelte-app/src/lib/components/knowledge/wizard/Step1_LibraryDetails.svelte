<!--
  @component Step1_LibraryDetails
  Library name + description + share toggle. Skipped when an existing
  library was picked in Step 0.

  Emits:
    - update: { libraryName, libraryDescription, libraryIsShared }
    - validity: { valid: boolean }
-->
<script>
    import { createEventDispatcher, tick, untrack } from 'svelte';
    import { _ } from '$lib/i18n';

    /** @type {{ wizardState: any }} */
    let { wizardState } = $props();

    const dispatch = createEventDispatcher();

    let name = $state(wizardState.libraryName || '');
    let description = $state(wizardState.libraryDescription || '');
    let isShared = $state(!!wizardState.libraryIsShared);
    let nameError = $state('');

    $effect(() => {
        // Track only local form state.
        const _n = name; const _d = description; const _s = isShared;
        void _n; void _d; void _s;
        untrack(() => {
            const trimmed = name.trim();
            if (!trimmed) {
                nameError = $_('knowledge.wizard.step1.nameRequired', { default: 'Name is required' });
                dispatch('validity', { valid: false });
                return;
            }
            if (trimmed.length > 100) {
                nameError = $_('knowledge.wizard.step1.nameTooLong', {
                    default: 'Name must be less than 100 characters'
                });
                dispatch('validity', { valid: false });
                return;
            }
            nameError = '';
            dispatch('validity', { valid: true });
            dispatch('update', {
                libraryName: trimmed,
                libraryDescription: description,
                libraryIsShared: isShared
            });
        });
    });

    $effect(() => {
        (async () => {
            await tick();
            document.getElementById('wizard-library-name')?.focus();
        })();
    });
</script>

<div class="space-y-4">
    <h3 class="text-base font-semibold text-gray-900">
        {$_('knowledge.wizard.step1.heading', { default: 'Library details' })}
    </h3>
    <p class="text-sm text-gray-600">
        {$_('knowledge.wizard.step1.description', {
            default: 'Give your Library a name. Defaults are good — feel free to keep them.'
        })}
    </p>

    <div>
        <label for="wizard-library-name" class="block text-sm font-medium text-gray-700">
            {$_('libraries.name', { default: 'Name' })} <span class="text-red-500">*</span>
        </label>
        <input
            type="text"
            id="wizard-library-name"
            bind:value={name}
            class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm px-3 py-2 text-sm focus:ring-[#2271b3] focus:border-[#2271b3] {nameError ? 'border-red-500' : ''}"
        />
        {#if nameError}
            <p class="mt-1 text-sm text-red-600" role="alert">{nameError}</p>
        {/if}
    </div>

    <div>
        <label for="wizard-library-description" class="block text-sm font-medium text-gray-700">
            {$_('libraries.description', { default: 'Description' })}
        </label>
        <textarea
            id="wizard-library-description"
            bind:value={description}
            rows="3"
            class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm px-3 py-2 text-sm focus:ring-[#2271b3] focus:border-[#2271b3]"
            placeholder={$_('libraries.descriptionPlaceholder', { default: 'Optional description' })}
        ></textarea>
    </div>

    <label class="flex items-start gap-3">
        <input type="checkbox" bind:checked={isShared} class="mt-1" />
        <span>
            <span class="block text-sm font-medium text-gray-700">
                {$_('knowledge.wizard.step1.shareLabel', { default: 'Share with my organization' })}
            </span>
            <span class="block text-xs text-gray-500">
                {$_('knowledge.wizard.step1.shareHint', {
                    default: 'You can change this later from the Library detail view.'
                })}
            </span>
        </span>
    </label>
</div>
