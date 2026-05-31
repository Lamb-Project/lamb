<!--
  @component FileTreeNode
  Recursive tree row. Renders one node (folder or item) and recurses
  into its children when the folder is expanded. Drag and drop, inline
  rename, ARIA treeitem semantics.
-->
<script>
	import { SvelteSet } from 'svelte/reactivity';
	import { _, locale } from '$lib/i18n';
	import { highlightMatch } from './treeOps.js';
	import { Folder, FileText, Youtube, Link, ChevronRight } from 'lucide-svelte';

	let {
		node,
		depth = 0,
		selectedIds = new SvelteSet(),
		expandedKeys = new SvelteSet(),
		focusedNodeKey = '',
		renamingNodeKey = '',
		highlightTerm = '',
		visibleKeys = /** @type {Set<string>|null} */ (null),
		dragOverKey = '',
		invalidDropKey = '',
		isReadOnly = false,
		/** Parent folder id that's currently in "create child folder" mode. ``undefined`` = no active create. */
		creatingFolderUnder = /** @type {string|null|undefined} */ (undefined),
		newFolderName = $bindable(''),
		ontoggle = (/** @type {string} */ _k) => {},
		onselect = (/** @type {string} */ _k, /** @type {{ ctrl: boolean, shift: boolean }} */ _m) => {},
		oncontextmenu = (/** @type {string} */ _k, /** @type {number} */ _x, /** @type {number} */ _y) => {},
		ondragstart = (/** @type {string} */ _k, /** @type {DragEvent} */ _e) => {},
		ondragover = (/** @type {string} */ _k, /** @type {DragEvent} */ _e) => {},
		ondragleave = (/** @type {string} */ _k) => {},
		ondrop = (/** @type {string} */ _k, /** @type {DragEvent} */ _e) => {},
		oncommitrename = (/** @type {string} */ _k, /** @type {string} */ _name) => {},
		oncancelrename = () => {},
		oncommitcreate = () => {},
		oncancelcreate = () => {}
	} = $props();

	let localeLoaded = $derived(!!$locale);
	let isExpanded = $derived(expandedKeys.has(node.key));
	let isSelected = $derived(selectedIds.has(node.key));
	let isFocused = $derived(focusedNodeKey === node.key);
	let isRenaming = $derived(renamingNodeKey === node.key);
	let isFolder = $derived(node.kind === 'folder');
	let isVisible = $derived(!visibleKeys || visibleKeys.has(node.key));
	let isDragOver = $derived(dragOverKey === node.key && isFolder);
	let isInvalidDrop = $derived(invalidDropKey === node.key);

	let renameValue = $state('');
	$effect(() => {
		if (isRenaming) renameValue = node.name;
	});

	let chunks = $derived(highlightMatch(node.name, highlightTerm));

	/** Pick a small icon glyph by item source_type (file / url / youtube). */
	let sourceKind = $derived(
		!isFolder && node.raw ? String(node.raw.source_type || 'file').toLowerCase() : ''
	);
	let hasFailedImport = $derived(
		!isFolder && node.raw && node.raw.status === 'failed'
	);

	function handleClick(/** @type {MouseEvent} */ e) {
		e.stopPropagation();
		onselect(node.key, { ctrl: e.ctrlKey || e.metaKey, shift: e.shiftKey });
	}

	function handleChevronClick(/** @type {MouseEvent} */ e) {
		e.stopPropagation();
		if (isFolder) ontoggle(node.key);
	}

	function handleDoubleClick(/** @type {MouseEvent} */ e) {
		e.stopPropagation();
		if (isReadOnly) return;
		// Folder dblclick = expand toggle; item dblclick = open preview (already happens via single select)
		if (isFolder) ontoggle(node.key);
	}

	function handleContext(/** @type {MouseEvent} */ e) {
		e.preventDefault();
		e.stopPropagation();
		oncontextmenu(node.key, e.clientX, e.clientY);
	}

	function commitRename() {
		const trimmed = renameValue.trim();
		if (!trimmed || trimmed === node.name) {
			oncancelrename();
			return;
		}
		oncommitrename(node.key, trimmed);
	}

	function handleRenameKey(/** @type {KeyboardEvent} */ e) {
		if (e.key === 'Enter') {
			e.preventDefault();
			commitRename();
		} else if (e.key === 'Escape') {
			e.preventDefault();
			oncancelrename();
		}
	}
</script>

{#if isVisible}
	<div
		role="treeitem"
		aria-level={depth + 1}
		aria-expanded={isFolder ? isExpanded : undefined}
		aria-selected={isSelected}
		tabindex={isFocused ? 0 : -1}
		draggable={!isReadOnly && !isRenaming}
		class="group relative flex cursor-pointer items-center gap-1.5 rounded-md px-2 py-1.5 text-sm transition-all
			{isSelected
				? 'bg-brand-subtle text-brand ring-brand/30 shadow-card ring-1'
				: 'text-text hover:bg-surface-sunken'}
			{isFocused ? 'outline-brand outline outline-2' : ''}
			{isDragOver ? 'bg-brand-subtle ring-brand ring-2' : ''}
			{isInvalidDrop ? 'opacity-40' : ''}"
		style="padding-left: {depth * 1.25 + 0.5}rem;"
		onclick={handleClick}
		ondblclick={handleDoubleClick}
		oncontextmenu={handleContext}
		ondragstart={(e) => !isReadOnly && ondragstart(node.key, e)}
		ondragover={(e) => isFolder && ondragover(node.key, e)}
		ondragleave={() => isFolder && ondragleave(node.key)}
		ondrop={(e) => isFolder && ondrop(node.key, e)}
	>
		<!-- Chevron (folders only) -->
		{#if isFolder}
			<button
				type="button"
				class="text-text-subtle hover:text-text flex h-4 w-4 shrink-0 items-center justify-center"
				onclick={handleChevronClick}
				tabindex="-1"
				aria-label={isExpanded
					? localeLoaded
						? $_('libraries.fileTree.collapseFolder', { default: 'Collapse' })
						: 'Collapse'
					: localeLoaded
						? $_('libraries.fileTree.expandFolder', { default: 'Expand' })
						: 'Expand'}
			>
				<ChevronRight
					size={12}
					class="motion-safe:duration-150 transition-transform {isExpanded ? 'rotate-90' : ''}"
					aria-hidden="true"
				/>
			</button>
		{:else}
			<span class="inline-block h-4 w-4 shrink-0"></span>
		{/if}

		<!-- Icon -->
		{#if isFolder}
			<Folder
				size={16}
				class="shrink-0 {isSelected ? 'text-brand' : 'text-amber-500'}"
				aria-hidden="true"
			/>
		{:else if sourceKind === 'youtube'}
			<Youtube size={16} class="text-danger shrink-0" aria-hidden="true" />
		{:else if sourceKind === 'url'}
			<Link size={16} class="shrink-0 text-emerald-500" aria-hidden="true" />
		{:else}
			<FileText
				size={16}
				class="shrink-0 {isSelected ? 'text-brand' : 'text-text-subtle'}"
				aria-hidden="true"
			/>
		{/if}

		<!-- Name (or inline-rename input) -->
		{#if isRenaming}
			<input
				type="text"
				bind:value={renameValue}
				onkeydown={handleRenameKey}
				onblur={commitRename}
				onclick={(e) => e.stopPropagation()}
				class="border-brand focus:ring-brand flex-1 rounded border px-1 py-0.5 text-sm focus:ring-1 focus:outline-none"
				autofocus
			/>
		{:else}
			<span class="flex min-w-0 flex-1 items-center gap-1.5 truncate">
				<span class="truncate">
					{#each chunks as chunk, i (i)}
						{#if chunk.match}
							<mark class="rounded bg-yellow-200 px-0.5">{chunk.text}</mark>
						{:else}{chunk.text}{/if}
					{/each}
				</span>
				{#if isFolder && node.descendantItemCount > 0}
					<span
						class="rounded-pill bg-surface-sunken text-text-muted ml-auto inline-flex shrink-0 items-center px-1.5 py-0.5 text-[10px] leading-none font-medium
						{isSelected ? 'bg-brand-subtle text-brand' : ''}"
					>
						{node.descendantItemCount}
					</span>
				{/if}
				{#if hasFailedImport}
					<span
						class="rounded-pill bg-danger-subtle text-danger-text ml-auto inline-flex shrink-0 items-center px-1.5 py-0.5 text-[10px] leading-none font-medium"
						title="Import failed"
					>
						!
					</span>
				{/if}
			</span>
		{/if}
	</div>

	<!-- Recurse into children if expanded -->
	{#if isFolder && isExpanded}
		<div role="group">
			<!-- Inline "create subfolder" input as first child when this folder is the target -->
			{#if creatingFolderUnder === node.id && !isReadOnly}
				<div
					class="flex items-center gap-2 py-1"
					style="padding-left: {(depth + 1) * 1.25 + 0.5}rem;"
				>
					<span class="inline-block h-4 w-4 shrink-0"></span>
					<Folder size={16} class="text-brand shrink-0" aria-hidden="true" />
					<input
						type="text"
						data-create-folder-input="true"
						bind:value={newFolderName}
						onkeydown={(e) => {
							if (e.key === 'Enter') {
								e.preventDefault();
								oncommitcreate();
							} else if (e.key === 'Escape') {
								e.preventDefault();
								oncancelcreate();
							}
						}}
						onclick={(e) => e.stopPropagation()}
						placeholder="New folder name"
						class="border-brand shadow-card focus:ring-brand flex-1 rounded border px-2 py-1 text-sm focus:ring-1 focus:outline-none"
						autofocus
					/>
				</div>
			{/if}
			{#each node.children as child (child.key)}
				<svelte:self
					node={child}
					depth={depth + 1}
					{selectedIds}
					{expandedKeys}
					{focusedNodeKey}
					{renamingNodeKey}
					{highlightTerm}
					{visibleKeys}
					{dragOverKey}
					{invalidDropKey}
					{isReadOnly}
					{creatingFolderUnder}
					bind:newFolderName
					{ontoggle}
					{onselect}
					{oncontextmenu}
					{ondragstart}
					{ondragover}
					{ondragleave}
					{ondrop}
					{oncommitrename}
					{oncancelrename}
					{oncommitcreate}
					{oncancelcreate}
				/>
			{/each}
		</div>
	{/if}
{/if}
