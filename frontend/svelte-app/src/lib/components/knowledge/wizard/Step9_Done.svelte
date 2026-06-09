<!--
  @component Step9_Done
  Success summary with quick links.

  Phase C consistency contract:
    * Success check uses `<CheckCircle2>` from the canonical icon set
      inside a `bg-success-subtle` circle.
    * CTAs are differentiated: primary "Open Knowledge Store" (Database
      iconLeft), secondary "Open Library" (BookOpen iconLeft), ghost
      "Create another" (Plus iconLeft).
    * On mount: `toast.success("Knowledge Store created.")` — guarded
      by a `mounted` flag so re-renders don't spam the toast stack.

  Emits:
    - done: { ksId, libraryId, target }     parent closes the wizard and may navigate
    - createAnother: ()                     parent resets state and returns to Step 1
-->
<script>
	import { createEventDispatcher, onMount } from 'svelte';
	import { _ } from '$lib/i18n';
	import { toast } from '$lib/stores/toast.js';
	import { Button } from '$lib/components/ui';
	import { CheckCircle2, Database, BookOpen, Plus } from '$lib/components/ui/icons.js';

	/** @type {{ wizardState: any }} */
	let { wizardState } = $props();

	const dispatch = createEventDispatcher();

	let mounted = $state(false);

	onMount(() => {
		if (mounted) return;
		mounted = true;
		toast.success(
			$_('knowledge.wizard.step9.toast', {
				default: 'Knowledge Store created.'
			})
		);
	});

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
	<div class="bg-success-subtle mx-auto flex h-14 w-14 items-center justify-center rounded-full">
		<CheckCircle2 class="text-success h-8 w-8" aria-hidden="true" />
	</div>

	<h3 class="type-section-title">
		{$_('knowledge.wizard.step9.heading', { default: "You're all set" })}
	</h3>

	<p class="type-body-muted">
		{$_('knowledge.wizard.step9.description', {
			default:
				'Your Library and Knowledge Store are ready. Ingestion runs in the background — items will become queryable as they finish.'
		})}
	</p>

	<div class="border-border bg-surface-muted space-y-1 rounded-md border p-3 text-left text-sm">
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
			<Button variant="primary" iconLeftComponent={Database} onclick={openKS}>
				{$_('knowledge.wizard.step9.openKS', { default: 'Open Knowledge Store' })}
			</Button>
		{/if}
		{#if wizardState.createdRefs?.libraryId}
			<Button variant="secondary" iconLeftComponent={BookOpen} onclick={openLibrary}>
				{$_('knowledge.wizard.step9.openLibrary', { default: 'Open Library' })}
			</Button>
		{/if}
		<Button variant="ghost" iconLeftComponent={Plus} onclick={createAnother}>
			{$_('knowledge.wizard.step9.createAnother', { default: 'Create another' })}
		</Button>
	</div>
</div>
