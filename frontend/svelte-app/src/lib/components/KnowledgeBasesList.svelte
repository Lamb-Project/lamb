<script>
	import { onMount } from 'svelte';
	import { getKnowledgeBases } from '$lib/services/knowledgeBaseService';
	import { _ } from '$lib/i18n';
	import { user } from '$lib/stores/userStore';
	import { base } from '$app/paths';
	import CreateKnowledgeBaseModal from '$lib/components/modals/CreateKnowledgeBaseModal.svelte';
	import { createEventDispatcher } from 'svelte';

	/**
	 * @typedef {Object} KnowledgeBase
	 * @property {string} id
	 * @property {string} name
	 * @property {string} [description]
	 * @property {string} owner
	 * @property {number} created_at
	 * @property {Object} [metadata]
	 * @property {string} [metadata.access_control]
	 */

	// State management
	/** @type {KnowledgeBase[]} */
	let knowledgeBases = $state([]);
	let loading = $state(true);
	let error = $state('');
	let serverOffline = $state(false);
	let successMessage = $state('');

	// Pagination (for future implementation)
	let currentPage = $state(1);
	let totalPages = $state(1);

	// Component references
	/** @type {CreateKnowledgeBaseModal} */
	let createModal;

	// Event dispatcher to communicate with parent
	const dispatch = createEventDispatcher();

	// Load knowledge bases on component mount
	onMount(async () => {
		await loadKnowledgeBases();
	});

	// Function to load knowledge bases from API
	async function loadKnowledgeBases() {
		// Reset states
		loading = true;
		error = '';
		serverOffline = false;

		try {
			// Check if user is logged in
			if (!$user.isLoggedIn) {
				error = 'You must be logged in to view knowledge bases.';
				loading = false;
				return;
			}

			// Fetch knowledge bases
			const data = await getKnowledgeBases();
			knowledgeBases = data || [];
			console.log('Knowledge bases loaded:', knowledgeBases.length);
		} catch (/** @type {unknown} */ err) {
			console.error('Error loading knowledge bases:', err);
			error = err instanceof Error ? err.message : 'Failed to load knowledge bases';

			// Check if server is offline based on error message
			if (err instanceof Error && err.message.includes('server offline')) {
				serverOffline = true;
			}
		} finally {
			loading = false;
		}
	}

	/**
	 * Format timestamp to readable date
	 * @param {number} timestamp - Unix timestamp in seconds
	 * @returns {string} Formatted date string
	 */
	function formatDate(timestamp) {
		if (!timestamp) return 'N/A';
		const date = new Date(timestamp * 1000);
		return date.toLocaleDateString('en-US', {
			year: 'numeric',
			month: 'short',
			day: 'numeric'
		});
	}

	// Show the create modal
	function showCreateModal() {
		createModal.open();
	}

	/**
	 * Navigate to knowledge base detail view by dispatching an event to parent
	 * @param {string} id - Knowledge base ID
	 */
	function viewKnowledgeBase(id) {
		dispatch('view', { id });
	}

	/**
	 * Handle successful knowledge base creation event
	 * @param {CustomEvent<{id: string, name: string, message?: string}>} event - The creation event
	 */
	function handleKnowledgeBaseCreated(event) {
		const { id, name, message } = event.detail;

		// Show success message
		successMessage =
			message ||
			$_('knowledgeBases.createSuccess', {
				values: { name },
				default: `Knowledge base "${name}" created successfully!`
			});

		// Hide message after 5 seconds
		setTimeout(() => {
			successMessage = '';
		}, 5000);

		// Refresh the list
		loadKnowledgeBases();
	}
</script>

<div class="overflow-hidden bg-white shadow sm:rounded-md">
	<div class="border-b border-gray-200 p-4 sm:flex sm:items-center sm:justify-between">
		<h3 class="text-lg leading-6 font-medium text-gray-900">
			{$_('knowledgeBases.list.title', { default: 'Knowledge Bases' })}
		</h3>
		<div class="mt-3 sm:mt-0 sm:ml-4">
			<button
				onclick={showCreateModal}
				class="inline-flex items-center rounded-md border border-transparent bg-[#2271b3] px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-[#195a91] focus:ring-2 focus:ring-[#2271b3] focus:ring-offset-2 focus:outline-none"
				style="background-color: #2271b3;"
			>
				{$_('knowledgeBases.list.createButton', { default: 'Create Knowledge Base' })}
			</button>
		</div>
	</div>

	{#if successMessage}
		<div class="border-b border-green-100 bg-green-50 p-4">
			<div class="text-sm text-green-700">
				{successMessage}
			</div>
		</div>
	{/if}

	{#if loading}
		<div class="p-6 text-center">
			<div class="animate-pulse text-gray-500">
				{$_('knowledgeBases.list.loading', { default: 'Loading knowledge bases...' })}
			</div>
		</div>
	{:else if error}
		<div class="p-6 text-center">
			<div class="text-red-500">
				{#if serverOffline}
					<div>
						<p class="mb-2 font-bold">
							{$_('knowledgeBases.list.serverOffline', {
								default: 'Knowledge Base Server Offline'
							})}
						</p>
						<p>
							{$_('knowledgeBases.list.tryAgainLater', {
								default: 'Please try again later or contact an administrator.'
							})}
						</p>
					</div>
				{:else}
					{error}
				{/if}
			</div>
			<button
				onclick={() => loadKnowledgeBases()}
				class="mt-4 inline-flex items-center rounded-md border border-transparent bg-[#2271b3] px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-[#195a91] focus:ring-2 focus:ring-[#2271b3] focus:ring-offset-2 focus:outline-none"
				style="background-color: #2271b3;"
			>
				{$_('knowledgeBases.list.retry', { default: 'Retry' })}
			</button>
		</div>
	{:else if knowledgeBases.length === 0}
		<div class="p-6 text-center">
			<div class="text-gray-500">
				{$_('knowledgeBases.list.empty', { default: 'No knowledge bases found.' })}
			</div>
		</div>
	{:else}
		<div class="overflow-x-auto">
			<table class="min-w-full divide-y divide-gray-200">
				<thead class="bg-gray-50">
					<tr>
						<th
							scope="col"
							class="px-6 py-3 text-left text-xs font-medium tracking-wider text-gray-500 uppercase"
						>
							{$_('knowledgeBases.list.nameColumn', { default: 'Name' })}
						</th>
						<th
							scope="col"
							class="px-6 py-3 text-left text-xs font-medium tracking-wider text-gray-500 uppercase"
						>
							{$_('knowledgeBases.list.descriptionColumn', { default: 'Description' })}
						</th>
						<th
							scope="col"
							class="px-6 py-3 text-left text-xs font-medium tracking-wider text-gray-500 uppercase"
						>
							{$_('knowledgeBases.list.createdColumn', { default: 'Created' })}
						</th>
						<th
							scope="col"
							class="px-6 py-3 text-left text-xs font-medium tracking-wider text-gray-500 uppercase"
						>
							{$_('knowledgeBases.list.accessColumn', { default: 'Access' })}
						</th>
						<th
							scope="col"
							class="px-6 py-3 text-right text-xs font-medium tracking-wider text-gray-500 uppercase"
						>
							{$_('knowledgeBases.list.actionsColumn', { default: 'Actions' })}
						</th>
					</tr>
				</thead>
				<tbody class="divide-y divide-gray-200 bg-white">
					{#each knowledgeBases as kb (kb.id)}
						<tr>
							<td class="px-6 py-4 whitespace-nowrap">
								<div class="text-sm font-medium text-gray-900">
									<button
										type="button"
										onclick={() => viewKnowledgeBase(kb.id)}
										class="cursor-pointer border-0 bg-transparent p-0 text-left font-medium text-[#2271b3] hover:text-[#195a91] hover:underline"
										style="color: #2271b3;"
									>
										{kb.name}
									</button>
								</div>
								<div class="text-sm text-gray-500">{kb.id}</div>
							</td>
							<td class="px-6 py-4 whitespace-normal">
								<div class="text-sm text-gray-900">{kb.description || '-'}</div>
							</td>
							<td class="px-6 py-4 whitespace-nowrap">
								<div class="text-sm text-gray-900">{formatDate(kb.created_at)}</div>
							</td>
							<td class="px-6 py-4 whitespace-nowrap">
								<span
									class="inline-flex rounded-full px-2 text-xs leading-5 font-semibold {kb.metadata
										?.access_control === 'private'
										? 'bg-yellow-100 text-yellow-800'
										: 'bg-green-100 text-green-800'}"
								>
									{kb.metadata?.access_control || 'public'}
								</span>
							</td>
							<td class="px-6 py-4 text-right text-sm font-medium whitespace-nowrap">
								<button
									onclick={() => viewKnowledgeBase(kb.id)}
									class="mr-2 text-[#2271b3] hover:text-[#195a91]"
									style="color: #2271b3;"
								>
									{$_('knowledgeBases.list.viewButton', { default: 'View' })}
								</button>
								<button
									type="button"
									onclick={() => viewKnowledgeBase(kb.id)}
									class="mr-2 text-[#2271b3] hover:text-[#195a91]"
									style="color: #2271b3;"
								>
									{$_('knowledgeBases.list.editButton', { default: 'Edit' })}
								</button>
								<button class="text-red-600 hover:text-red-900">
									{$_('knowledgeBases.list.deleteButton', { default: 'Delete' })}
								</button>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}

	<!-- Create Knowledge Base Modal -->
	<CreateKnowledgeBaseModal bind:this={createModal} on:created={handleKnowledgeBaseCreated} />
</div>
