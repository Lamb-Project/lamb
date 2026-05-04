<!--
  @component Step9_Done
  Success summary with quick links.

  Emits:
    - done: { ksId, libraryId }     (parent closes the wizard and may navigate)
    - createAnother: ()             (parent resets state and returns to Step 0)
-->
<script>
	import { createEventDispatcher } from 'svelte';
	import { _ } from '$lib/i18n';

	/** @type {{ wizardState: any }} */
	let { wizardState } = $props();

	const dispatch = createEventDispatcher();

	function openKS() {
		dispatch('done', {
			ksId: wizardState.createdRefs?.ksId,
			libraryId: wizardState.createdRefs?.libraryId,
			target: 'ks'
		});
	}

	function openLibrary() {
		dispatch('done', {
			ksId: wizardState.createdRefs?.ksId,
			libraryId: wizardState.createdRefs?.libraryId,
			target: 'library'
		});
	}

	function createAnother() {
		dispatch('createAnother');
	}
</script>

<div class="space-y-4 text-center">
	<div class="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-green-100">
		<svg
			class="h-6 w-6 text-green-600"
			fill="none"
			stroke="currentColor"
			viewBox="0 0 24 24"
			aria-hidden="true"
		>
			<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
		</svg>
	</div>

	<h3 class="text-lg font-semibold text-gray-900">
		{$_('knowledge.wizard.step9.heading', { default: "You're all set" })}
	</h3>

	<p class="text-sm text-gray-600">
		{$_('knowledge.wizard.step9.description', {
			default:
				'Your Library and Knowledge Store are ready. Ingestion runs in the background — items will become queryable as they finish.'
		})}
	</p>

	<div class="space-y-1 rounded-md border border-gray-200 bg-gray-50 p-3 text-left text-sm">
		{#if wizardState.createdRefs?.libraryName}
			<div>
				<span class="font-medium"
					>{$_('knowledge.wizard.step8.libraryHeading', { default: 'Library' })}:</span
				>
				<span class="ml-1">{wizardState.createdRefs.libraryName}</span>
			</div>
		{/if}
		{#if wizardState.createdRefs?.ksName}
			<div>
				<span class="font-medium"
					>{$_('knowledge.wizard.step8.ksHeading', { default: 'Knowledge Store' })}:</span
				>
				<span class="ml-1">{wizardState.createdRefs.ksName}</span>
			</div>
		{/if}
	</div>

	<div class="flex flex-wrap justify-center gap-2 pt-2">
		{#if wizardState.createdRefs?.ksId}
			<button
				type="button"
				onclick={openKS}
				class="rounded-md bg-[#2271b3] px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-[#195a91]"
			>
				{$_('knowledge.wizard.step9.openKS', { default: 'Open Knowledge Store' })}
			</button>
		{/if}
		{#if wizardState.createdRefs?.libraryId}
			<button
				type="button"
				onclick={openLibrary}
				class="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
			>
				{$_('knowledge.wizard.step9.openLibrary', { default: 'Open Library' })}
			</button>
		{/if}
		<button
			type="button"
			onclick={createAnother}
			class="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
		>
			{$_('knowledge.wizard.step9.createAnother', { default: 'Create another' })}
		</button>
	</div>
</div>
