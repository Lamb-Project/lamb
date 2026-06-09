<!-- src/lib/components/assistants/RubricSelector.svelte -->
<script>
	import { _ } from '$lib/i18n';

	let {
		rubrics = [],
		loading = false,
		error = '',
		selectedRubricId = $bindable(''),
		rubricFormat = $bindable('markdown')
	} = $props();

	let rubricSearchQuery = $state('');
	let filteredRubrics = $derived.by(() => {
		if (!rubricSearchQuery.trim()) return rubrics;
		const query = rubricSearchQuery.toLowerCase();
		return rubrics.filter(
			(rubric) =>
				rubric.title.toLowerCase().includes(query) ||
				(rubric.description && rubric.description.toLowerCase().includes(query))
		);
	});
</script>

<div class="mt-6 border-t border-gray-200 pt-6">
	<h4 class="mb-4 text-lg font-medium text-gray-900">
		{$_('assistants.form.rubric.label', { default: 'Select Rubric' })}
	</h4>
	{#if loading}
		<p class="text-sm text-gray-500">
			{$_('assistants.form.rubric.loading', { default: 'Loading rubrics...' })}
		</p>
	{:else if error}
		<p class="text-sm text-red-600">
			{$_('assistants.form.rubric.error', { default: 'Error loading rubrics:' })}
			{error}
		</p>
	{:else if rubrics.length === 0}
		<p class="text-sm text-gray-500">
			{$_('assistants.form.rubric.noneFound', { default: 'No rubrics available.' })}
			<a href="/evaluaitor" class="text-blue-600 hover:underline" target="_blank">
				{$_('assistants.form.rubric.createLink', { default: 'Create a rubric' })} →
			</a>
		</p>
	{:else}
		<div class="mb-4">
			<label for="rubric-search" class="sr-only">
				{$_('assistants.form.rubric.search.label', { default: 'Search rubrics' })}
			</label>
			<input
				type="text"
				id="rubric-search"
				bind:value={rubricSearchQuery}
				placeholder={$_('assistants.form.rubric.search.placeholder', {
					default: 'Search rubrics by title or description...'
				})}
				class="focus:ring-brand focus:border-brand w-full rounded-md border border-gray-300 bg-white px-4 py-2 text-gray-900 shadow-sm sm:text-sm"
			/>
		</div>
		{#if selectedRubricId}
			{@const selectedRubric = rubrics.find((r) => r.rubric_id === selectedRubricId)}
			{#if selectedRubric}
				<div class="mb-4 rounded-md border border-blue-200 bg-blue-50 p-3">
					<div class="flex items-start justify-between">
						<div class="flex-1">
							<div class="flex items-center gap-2">
								<span class="text-sm font-semibold text-blue-900">
									{$_('assistants.form.rubric.selected', { default: 'Selected:' })}
								</span>
								<span class="text-sm font-medium text-blue-800">{selectedRubric.title}</span>
								{#if selectedRubric.is_showcase}
									<span class="text-xs">🌟</span>
								{/if}
							</div>
							{#if selectedRubric.description}
								<p class="mt-1 text-xs text-blue-700">{selectedRubric.description}</p>
							{/if}
						</div>
						<a
							href="/evaluaitor/{selectedRubric.rubric_id}"
							target="_blank"
							rel="noopener noreferrer"
							class="ml-2 text-sm whitespace-nowrap text-blue-600 hover:text-blue-800 hover:underline"
						>
							{$_('assistants.form.rubric.view', { default: 'View' })} →
						</a>
					</div>
				</div>
			{/if}
		{/if}
		<div class="overflow-hidden rounded-md border">
			<div class="max-h-96 overflow-y-auto">
				<table class="min-w-full divide-y divide-gray-200">
					<thead class="sticky top-0 bg-gray-50">
						<tr>
							<th
								scope="col"
								class="w-12 px-3 py-3 text-left text-xs font-medium tracking-wider text-gray-500 uppercase"
								>{$_('assistants.form.rubric.table.select', { default: 'Select' })}</th
							>
							<th
								scope="col"
								class="px-3 py-3 text-left text-xs font-medium tracking-wider text-gray-500 uppercase"
								>{$_('assistants.form.rubric.table.title', { default: 'Title' })}</th
							>
							<th
								scope="col"
								class="px-3 py-3 text-left text-xs font-medium tracking-wider text-gray-500 uppercase"
								>{$_('assistants.form.rubric.table.description', { default: 'Description' })}</th
							>
							<th
								scope="col"
								class="w-24 px-3 py-3 text-left text-xs font-medium tracking-wider text-gray-500 uppercase"
								>{$_('assistants.form.rubric.table.type', { default: 'Type' })}</th
							>
							<th
								scope="col"
								class="w-20 px-3 py-3 text-center text-xs font-medium tracking-wider text-gray-500 uppercase"
								>{$_('assistants.form.rubric.table.actions', { default: 'Actions' })}</th
							>
						</tr>
					</thead>
					<tbody class="divide-y divide-gray-200 bg-white">
						{#if filteredRubrics.length === 0}
							<tr>
								<td colspan="5" class="px-3 py-4 text-center text-sm text-gray-500">
									{$_('assistants.form.rubric.noMatches', {
										default: 'No rubrics match your search.'
									})}
								</td>
							</tr>
						{:else}
							{#each filteredRubrics as rubric (rubric.rubric_id)}
								<tr
									class="hover:bg-gray-50 {selectedRubricId === rubric.rubric_id
										? 'bg-blue-50'
										: ''}"
								>
									<td class="px-3 py-3 text-center whitespace-nowrap">
										<input
											type="radio"
											name="rubric-selector"
											value={rubric.rubric_id}
											bind:group={selectedRubricId}
											class="text-brand focus:ring-brand h-4 w-4"
										/>
									</td>
									<td class="px-3 py-3">
										<div class="flex items-center gap-2">
											<span class="text-sm font-medium text-gray-900">{rubric.title}</span>
											{#if rubric.is_showcase}
												<span class="text-xs" title="Showcase rubric">🌟</span>
											{/if}
										</div>
									</td>
									<td class="px-3 py-3">
										<p class="line-clamp-2 text-sm text-gray-600">{rubric.description || ''}</p>
									</td>
									<td class="px-3 py-3 whitespace-nowrap">
										{#if rubric.is_mine}
											<span
												class="inline-flex items-center rounded bg-green-100 px-2 py-0.5 text-xs font-medium text-green-800"
												>{$_('assistants.form.rubric.mine', { default: 'Mine' })}</span
											>
										{:else}
											<span
												class="inline-flex items-center rounded bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-800"
												>{$_('assistants.form.rubric.public', { default: 'Public' })}</span
											>
										{/if}
									</td>
									<td class="px-3 py-3 text-center whitespace-nowrap">
										<a
											href="/evaluaitor/{rubric.rubric_id}"
											target="_blank"
											rel="noopener noreferrer"
											class="text-sm text-blue-600 hover:text-blue-800 hover:underline"
										>
											{$_('assistants.form.rubric.view', { default: 'View' })} →
										</a>
									</td>
								</tr>
							{/each}
						{/if}
					</tbody>
				</table>
			</div>
		</div>
		{#if !selectedRubricId}
			<p class="mt-2 text-xs text-red-500">
				{$_('assistants.form.rubric.required', { default: 'Please select a rubric' })}
			</p>
		{/if}
		<div class="mt-6 border-t border-gray-200 pt-4">
			<div class="mb-3 block text-sm font-medium text-gray-700">
				{$_('assistants.form.rubric.format.label', { default: 'Rubric Format for LLM' })}
			</div>
			<div class="flex gap-6">
				<label class="flex cursor-pointer items-center">
					<input
						type="radio"
						bind:group={rubricFormat}
						value="markdown"
						class="text-brand focus:ring-brand mr-2 h-4 w-4"
					/>
					<span class="text-sm text-gray-900">
						{$_('assistants.form.rubric.format.markdown', { default: 'Markdown (table format)' })}
					</span>
				</label>
				<label class="flex cursor-pointer items-center">
					<input
						type="radio"
						bind:group={rubricFormat}
						value="json"
						class="text-brand focus:ring-brand mr-2 h-4 w-4"
					/>
					<span class="text-sm text-gray-900">
						{$_('assistants.form.rubric.format.json', { default: 'JSON (structured data)' })}
					</span>
				</label>
			</div>
			<p class="mt-2 text-xs text-gray-500">
				{$_('assistants.form.rubric.format.help', {
					default:
						'Choose the format that works best with your selected LLM. You can test both to see which produces better results.'
				})}
			</p>
		</div>
	{/if}
</div>
