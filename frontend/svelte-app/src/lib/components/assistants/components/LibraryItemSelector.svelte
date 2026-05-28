<script>
	import { _ } from '$lib/i18n';

	let {
		libraries = [],
		items = [],
		selectedLibraryId = $bindable(''),
		selectedItemId = $bindable(''),
		loadingLibraries = false,
		loadingItems = false,
		libraryError = '',
		itemsError = '',
		formState
	} = $props();

	let readyItems = $derived(items.filter((item) => item.status === 'ready'));

	function handleLibraryChange(event) {
		selectedLibraryId = event.target.value;
		selectedItemId = '';
	}

	function handleItemChange(event) {
		selectedItemId = event.target.value;
	}
</script>

<div>
	<h4 class="block text-sm font-medium text-gray-700 mb-1">
		{$_('assistants.form.singleFile.label', { default: 'Select Document' })}
	</h4>

	<div class="mb-3">
		<label for="library-selector" class="block text-sm text-gray-700 mb-1">
			{$_('assistants.form.singleFile.libraryLabel', { default: 'Library' })}
		</label>
		{#if loadingLibraries}
			<p class="text-sm text-gray-500">
				{$_('assistants.form.singleFile.loadingLibraries', { default: 'Loading libraries...' })}
			</p>
		{:else if libraryError}
			<p class="text-sm text-red-600">{libraryError}</p>
		{:else if libraries.length === 0}
			<p class="text-sm text-gray-500">
				{$_('assistants.form.singleFile.noLibraries', { default: 'No libraries available.' })}
				<a href="/libraries" class="text-brand hover:underline ml-1">
					{$_('assistants.form.singleFile.manageLibraries', { default: 'Manage libraries' })}
				</a>
			</p>
		{:else}
			<select
				id="library-selector"
				name="library-selector"
				aria-label={$_('assistants.form.singleFile.libraryLabel', { default: 'Library' })}
				value={selectedLibraryId}
				onchange={handleLibraryChange}
				class="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-brand focus:border-brand sm:text-sm bg-white text-gray-900"
			>
				<option value="">
					{$_('assistants.form.singleFile.selectLibrary', { default: '-- Select a library --' })}
				</option>
				{#each libraries as lib (lib.id)}
					<option value={lib.id}>{lib.name}</option>
				{/each}
			</select>
		{/if}
	</div>

	{#if selectedLibraryId}
		<div class="mb-3">
			<label for="item-selector" class="block text-sm text-gray-700 mb-1">
				{$_('assistants.form.singleFile.itemLabel', { default: 'Document' })}
			</label>
			{#if loadingItems}
				<p class="text-sm text-gray-500">
					{$_('assistants.form.singleFile.loadingItems', { default: 'Loading documents...' })}
				</p>
			{:else if itemsError}
				<p class="text-sm text-red-600">{itemsError}</p>
			{:else if readyItems.length === 0}
				<p class="text-sm text-gray-500">
					{$_('assistants.form.singleFile.noReadyItems', {
						default: 'No ready documents in this library.'
					})}
				</p>
			{:else}
				<select
					id="item-selector"
					name="item-selector"
					aria-label={$_('assistants.form.singleFile.itemLabel', { default: 'Document' })}
					value={selectedItemId}
					onchange={handleItemChange}
					class="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-brand focus:border-brand sm:text-sm bg-white text-gray-900"
				>
					<option value="">
						{$_('assistants.form.singleFile.selectItem', { default: '-- Select a document --' })}
					</option>
					{#each readyItems as item (item.id)}
						<option value={item.id}>{item.title || item.original_filename}</option>
					{/each}
				</select>
			{/if}
		</div>
	{/if}

	{#if !selectedItemId && formState === 'edit'}
		<p class="mt-1 text-xs text-red-500">
			{$_('assistants.form.singleFile.required', { default: 'Please select a document' })}
		</p>
	{/if}

	<p class="mt-2 text-xs text-gray-500">
		<a href="/libraries" class="text-brand hover:underline">
			{$_('assistants.form.singleFile.manageLibraries', { default: 'Manage libraries' })}
		</a>
	</p>
</div>
