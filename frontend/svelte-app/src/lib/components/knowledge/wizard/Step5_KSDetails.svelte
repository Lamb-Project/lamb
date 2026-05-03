<!--
  @component Step5_KSDetails
  KS name + description + share toggle. Skipped when an existing KS was
  picked in Step 4.

  Emits:
    - update: { ksName, ksDescription, ksIsShared }
    - validity: { valid: boolean }
-->
<script>
    import { createEventDispatcher, tick } from 'svelte';
    import { _ } from '$lib/i18n';

    /** @type {{ wizardState: any }} */
    let { wizardState } = $props();

    const dispatch = createEventDispatcher();

    let name = $state(wizardState.ksName || '');
    let description = $state(wizardState.ksDescription || '');
    let isShared = $state(!!wizardState.ksIsShared);
    let nameError = $state('');

    $effect(() => {
        const trimmed = name.trim();
        if (!trimmed) {
            nameError = $_('knowledge.wizard.step5.nameRequired', { default: 'Name is required' });
            dispatch('validity', { valid: false });
            return;
        }
        if (trimmed.length > 100) {
            nameError = $_('knowledge.wizard.step5.nameTooLong', {
                default: 'Name must be less than 100 characters'
            });
            dispatch('validity', { valid: false });
            return;
        }
        nameError = '';
        dispatch('validity', { valid: true });
        dispatch('update', {
            ksName: trimmed,
            ksDescription: description,
            ksIsShared: isShared
        });
    });

    $effect(() => {
        (async () => {
            await tick();
            document.getElementById('wizard-ks-name')?.focus();
        })();
    });
</script>

<div class="space-y-4">
    <h3 class="text-base font-semibold text-gray-900">
        {$_('knowledge.wizard.step5.heading', { default: 'Knowledge Store details' })}
    </h3>
    <p class="text-sm text-gray-600">
        {$_('knowledge.wizard.step5.description', {
            default: 'Give your Knowledge Store a name. Defaults are good — feel free to keep them.'
        })}
    </p>

    <div>
        <label for="wizard-ks-name" class="block text-sm font-medium text-gray-700">
            {$_('libraries.name', { default: 'Name' })} <span class="text-red-500">*</span>
        </label>
        <input
            type="text"
            id="wizard-ks-name"
            bind:value={name}
            class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm px-3 py-2 text-sm focus:ring-[#2271b3] focus:border-[#2271b3] {nameError ? 'border-red-500' : ''}"
        />
        {#if nameError}
            <p class="mt-1 text-sm text-red-600" role="alert">{nameError}</p>
        {/if}
    </div>

    <div>
        <label for="wizard-ks-description" class="block text-sm font-medium text-gray-700">
            {$_('libraries.description', { default: 'Description' })}
        </label>
        <textarea
            id="wizard-ks-description"
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
                {$_('knowledge.wizard.step5.shareLabel', { default: 'Share with my organization' })}
            </span>
            <span class="block text-xs text-gray-500">
                {$_('knowledge.wizard.step5.shareHint', {
                    default: 'You can change this later from the Knowledge Store detail view.'
                })}
            </span>
        </span>
    </label>
</div>
