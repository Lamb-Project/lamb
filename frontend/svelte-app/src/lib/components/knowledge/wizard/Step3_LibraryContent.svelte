<!--
  @component Step3_LibraryContent
  Optional. Multi-file picker. Files are NOT uploaded here — they're
  collected as in-memory File objects so that the wizard remains fully
  reversible until Step 8 ("Create"). Step 8 does the actual library
  creation, file upload, and status polling.

  This step is always considered valid (skippable).

  Emits:
    - update: { pendingFiles }
    - validity: { valid: boolean }
-->
<script>
    import { createEventDispatcher } from 'svelte';
    import { _ } from '$lib/i18n';

    /** @type {{ wizardState: any }} */
    let { wizardState } = $props();

    const dispatch = createEventDispatcher();

    let files = $state(/** @type {File[]} */ (wizardState.pendingFiles || []));

    $effect(() => {
        dispatch('validity', { valid: true });
        dispatch('update', { pendingFiles: files });
    });

    /** @param {Event} event */
    function handleFileChange(event) {
        const target = /** @type {HTMLInputElement} */ (event.target);
        if (!target.files) return;
        const incoming = Array.from(target.files);
        files = [...files, ...incoming];
        target.value = '';
    }

    /** @param {number} idx */
    function removeFile(idx) {
        files = files.filter((_, i) => i !== idx);
    }

    /** @param {number} bytes */
    function formatSize(bytes) {
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    }
</script>

<div class="space-y-4">
    <h3 class="text-base font-semibold text-gray-900">
        {$_('knowledge.wizard.step3.heading', { default: 'Initial content' })}
    </h3>
    <p class="text-sm text-gray-600">
        {$_('knowledge.wizard.step3.description', {
            default: 'Optionally add files to your new Library now. You can also skip this and add content later.'
        })}
    </p>

    <div>
        <label for="wizard-library-files" class="block text-sm font-medium text-gray-700">
            {$_('knowledge.wizard.step3.pickLabel', { default: 'Pick files' })}
        </label>
        <input
            type="file"
            id="wizard-library-files"
            multiple
            onchange={handleFileChange}
            class="mt-1 block w-full text-sm text-gray-700 file:mr-3 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-medium file:bg-[#2271b3] file:text-white hover:file:bg-[#195a91]"
        />
    </div>

    {#if files.length > 0}
        <div class="border border-gray-200 rounded-md divide-y">
            {#each files as f, idx (idx + '-' + f.name)}
                <div class="flex items-center gap-3 px-3 py-2">
                    <div class="flex-1 min-w-0">
                        <div class="text-sm font-medium text-gray-900 truncate">{f.name}</div>
                        <div class="text-xs text-gray-400">{formatSize(f.size)}</div>
                    </div>
                    <button
                        type="button"
                        onclick={() => removeFile(idx)}
                        class="text-xs text-red-600 hover:underline"
                    >
                        {$_('common.remove', { default: 'Remove' })}
                    </button>
                </div>
            {/each}
        </div>
        <p class="text-xs text-gray-500">
            {$_('knowledge.wizard.step3.uploadNote', {
                default: 'Files will be uploaded when you click "Create" in the Review step.'
            })}
        </p>
    {:else}
        <p class="text-sm text-gray-500">
            {$_('knowledge.wizard.step3.emptyHint', {
                default: 'No files selected. You can skip this step.'
            })}
        </p>
    {/if}
</div>
