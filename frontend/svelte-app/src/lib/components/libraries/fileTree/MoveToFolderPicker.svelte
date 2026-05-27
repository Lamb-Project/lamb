<!--
  @component MoveToFolderPicker
  Secondary modal showing a folders-only tree for the "Move to..." flow.
  Receives the already-loaded tree via prop to avoid a refetch.
-->
<script>
	import { _, locale } from '$lib/i18n';
	import { Modal, Button } from '$lib/components/ui';
	import { Folder } from 'lucide-svelte';

	let {
		isOpen = $bindable(false),
		/** @type {import('./treeOps.js').TreeNode} */
		tree,
		/** Keys being moved; used to gray out illegal destinations. */
		moveCandidateKeys = /** @type {string[]} */ ([]),
		/** Optional set of folder keys that are disabled (descendants of dragged folders). */
		disabledKeys = /** @type {Set<string>} */ (new Set()),
		onpicked = (/** @type {string|null} */ _f) => {},
		oncancel = () => {}
	} = $props();

	let localeLoaded = $derived(!!$locale);

	/** Render a folder row recursively. */
	function isDisabled(/** @type {import('./treeOps.js').TreeNode} */ node) {
		return moveCandidateKeys.includes(node.key) || disabledKeys.has(node.key);
	}

	function close() {
		oncancel();
		isOpen = false;
	}

	function pick(/** @type {string|null} */ folderId) {
		onpicked(folderId);
		isOpen = false;
	}
</script>

<Modal
	open={isOpen}
	onclose={close}
	size="sm"
	title={localeLoaded
		? $_('libraries.fileTree.moveToPicker.title', { default: 'Move to folder' })
		: 'Move to folder'}
	closeAriaLabel={$_('common.close', { default: 'Close' })}
>
	<div class="max-h-[60vh] flex-1 overflow-y-auto">
		<!-- Root option -->
			<button
				type="button"
				class="hover:bg-brand-subtle flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm"
				onclick={() => pick(null)}
			>
				<Folder size={16} class="text-brand" aria-hidden="true" />
				<span class="text-text italic">
					{localeLoaded
						? $_('libraries.fileTree.moveToPicker.rootOption', { default: 'Library root' })
						: 'Library root'}
				</span>
			</button>

			{#snippet folder(node, depth)}
				{#if node.kind === 'folder'}
					<button
						type="button"
						class="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm
							{isDisabled(node)
								? 'text-text-disabled cursor-not-allowed'
								: 'text-text hover:bg-brand-subtle'}"
						style="padding-left: {depth * 1.25 + 0.5}rem;"
						disabled={isDisabled(node)}
						onclick={() => pick(node.id)}
					>
						<Folder
							size={16}
							class="shrink-0 {isDisabled(node) ? 'text-text-disabled' : 'text-brand'}"
							aria-hidden="true"
						/>
						<span class="min-w-0 flex-1 truncate">{node.name}</span>
					</button>
					{#each node.children.filter((c) => c.kind === 'folder') as child (child.key)}
						{@render folder(child, depth + 1)}
					{/each}
				{/if}
			{/snippet}

		{#each tree.children.filter((c) => c.kind === 'folder') as topFolder (topFolder.key)}
			{@render folder(topFolder, 0)}
		{/each}
	</div>

	{#snippet footer({ close: closeFn })}
		<Button variant="secondary" onclick={closeFn}>
			{localeLoaded ? $_('common.cancel', { default: 'Cancel' }) : 'Cancel'}
		</Button>
	{/snippet}
</Modal>
