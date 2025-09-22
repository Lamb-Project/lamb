<script>
	import { onMount, onDestroy } from 'svelte';
	import { get } from 'svelte/store';
	import { goto } from '$app/navigation';
	import PublishModal from './PublishModal.svelte'; // Restore PublishModal import
	import { createEventDispatcher } from 'svelte'; // Import createEventDispatcher
	import { publishModalOpen, selectedAssistant } from '$lib/stores/assistantPublish'; // Restore store imports
	import { user } from '$lib/stores/userStore';
	import {
		getAssistants,
		deleteAssistant,
		downloadAssistant,
		unpublishAssistant
	} from '$lib/services/assistantService';
	import { base } from '$app/paths';
	import { browser } from '$app/environment';
	import { _, locale } from '$lib/i18n'; // Import i18n

	// Default text for when i18n isn't loaded yet
	let localeLoaded = $state(!!get(locale)); // Initialize based on current store value
	const dispatch = createEventDispatcher(); // Create dispatcher instance

	// Assistants data from global store
	/** @type {Array<any>} */
	let assistants = $state([]); // Local state for the current page's assistants
	let loading = $state(true);
	/** @type {string | null} */
	let error = $state(null);

	// Pagination
	let ITEMS_PER_PAGE = $state(5); // Use $state for binding
	let currentPage = $state(1);
	let totalItems = $state(0);
	let totalPages = $derived(Math.ceil(totalItems / ITEMS_PER_PAGE));

	// API Key (you should get this from your auth store or environment)
	// let apiKey = ''; // Restore if needed, seems unused currently

	// --- Lifecycle and Data Loading ---
	let localeUnsubscribe = () => {};
	let userUnsubscribe = () => {}; // Ensure declaration is here
	// Removed assistantsStore unsubscribe variable

	onMount(() => {
		localeUnsubscribe = locale.subscribe((value) => {
			if (value) {
				localeLoaded = true;
			}
		});

		if (browser) {
			userUnsubscribe = user.subscribe((userData) => {
				if (userData.isLoggedIn) {
					// Simplified logic: load if logged in and list is empty
					if (assistants.length === 0 && !loading) {
						console.log('User logged in, loading initial assistants...');
						loadPaginatedAssistants(1, ITEMS_PER_PAGE);
					}
				} else {
					console.log('User logged out, clearing assistants.');
					assistants = [];
					totalItems = 0;
					currentPage = 1;
					error = null;
					loading = false;
				}
			});

			const initialUserData = $user;
			if (initialUserData.isLoggedIn) {
				console.log('User already logged in on mount, loading initial assistants...');
				loadPaginatedAssistants(currentPage, ITEMS_PER_PAGE);
			}

			// apiKey = localStorage.getItem('apiKey') || '';

			// Restore event listener for publish event
			// const handleAssistantPublished = () => {
			//     console.log('Assistant published event received, reloading list.');
			//     loadPaginatedAssistants(currentPage, ITEMS_PER_PAGE);
			// };
			// Note: Svelte component events don't use window.addEventListener
			// The event is handled directly on the component tag: <PublishModal on:assistantPublished={...} />
		}

		return () => {
			localeUnsubscribe();
			if (userUnsubscribe) userUnsubscribe();
		};
	});

	// --- Refresh State ---
	let isRefreshing = $state(false);

	// Function to load assistants for a specific page
	/**
	 * @param {number} page
	 * @param {number} limit
	 */
	async function loadPaginatedAssistants(page, limit) {
		loading = true;
		error = null;
		try {
			const offset = (page - 1) * limit;
			console.log(`Calling getAssistants with limit=${limit}, offset=${offset}`);
			const response = await getAssistants(limit, offset);
			console.log('Received data from getAssistants:', response);

			assistants = response.assistants;
			totalItems = response.total_count;
			currentPage = page; // Ensure currentPage state is updated
		} catch (err) {
			console.error('Error loading assistants:', err);
			error = err instanceof Error ? err.message : 'Failed to load assistants';
			assistants = [];
			totalItems = 0;
		} finally {
			loading = false;
		}
		await new Promise((resolve) => setTimeout(resolve, 500));
		loading = false;
	}

	// --- Refresh Function ---
	async function handleRefresh() {
		if (isRefreshing) return; // Prevent multiple refreshes
		console.log('Manual refresh triggered...');
		isRefreshing = true;
		await loadPaginatedAssistants(currentPage, ITEMS_PER_PAGE); // Reload current page
		isRefreshing = false;
	}

	// --- Action Handlers ---

	/** @param {{ detail: { id: number } }} event */
	/**
	 * Handle view button click
	 * @param {number} id - The ID of the assistant to view
	 */
	function handleView(id) {
		console.log(`View assistant (navigate to detail view): ${id}`);
		// Navigate to the detail view without edit mode
		const targetUrl = `${base}/assistants?view=detail&id=${id}`;
		console.log('[AssistantsList] Navigating to view:', targetUrl);
		goto(targetUrl);
	}

	/**
	 * Handle edit button click
	 * @param {number} id - The ID of the assistant to edit
	 */
	function handleEdit(id) {
		console.log(`Edit assistant (navigate to detail view in edit mode): ${id}`);
		// Navigate to the detail view and add startInEdit=true query param
		const targetUrl = `${base}/assistants?view=detail&id=${id}&startInEdit=true`;
		console.log('[AssistantsList] Navigating to edit:', targetUrl);
		goto(targetUrl);
	}

	/** @param {{ detail: { id: number } }} event */
	function handleClone(event) {
		const id = Number(event.detail.id);
		console.log('Clone assistant (not implemented):', id);
		alert(
			localeLoaded
				? $_('assistants.actions.cloneNotImplemented', {
						default: 'Clone functionality not yet implemented.'
					})
				: 'Clone functionality not yet implemented.'
		);
	}

	/** @param {{ detail: { assistantId: number; groupId: string | null | undefined; ownerEmail: string } }} event */
	async function handleUnpublish(event) {
		const assistantId = Number(event.detail.assistantId);
		const { groupId, ownerEmail } = event.detail;
		if (!groupId || !ownerEmail) {
			alert(
				localeLoaded
					? $_('assistants.unpublishErrorMissingData')
					: 'Cannot unpublish: Missing group ID or owner email.'
			);
			return;
		}
		const assistantToUnpublish = assistants.find((a) => a.id === assistantId);
		const confirmMessage = localeLoaded
			? $_('assistants.unpublishConfirm', {
					values: { name: assistantToUnpublish?.name || assistantId }
				})
			: `Are you sure you want to unpublish assistant ${assistantId}?`;
		if (confirm(confirmMessage)) {
			try {
				await unpublishAssistant(assistantId.toString(), groupId, ownerEmail);
				await loadPaginatedAssistants(currentPage, ITEMS_PER_PAGE);
				alert(
					localeLoaded ? $_('assistants.unpublishSuccess') : 'Assistant unpublished successfully!'
				);
			} catch (err) {
				console.error('Error unpublishing assistant:', err);
				const errorMsg = err instanceof Error ? err.message : 'Failed to unpublish assistant';
				error = errorMsg;
				alert(
					localeLoaded
						? $_('assistants.unpublishError', { values: { error: errorMsg } })
						: `Error: ${errorMsg}`
				);
			}
		}
	}

	// --- Pagination Navigation (Define functions) ---

	function goToPreviousPage() {
		if (currentPage > 1) {
			loadPaginatedAssistants(currentPage - 1, ITEMS_PER_PAGE);
		}
	}

	function goToNextPage() {
		if (currentPage < totalPages) {
			loadPaginatedAssistants(currentPage + 1, ITEMS_PER_PAGE);
		}
	}

	// --- Helper Functions ---
	/** @param {string | undefined | null} jsonString */
	function parseMetadata(jsonString) {
		if (!jsonString) return {};
		try {
			return JSON.parse(jsonString);
		} catch (e) {
			console.error('Error parsing metadata:', e, jsonString);
			return {};
		}
	}

	// --- SVG Icons (Ensure definitions are present) ---
	const IconView = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M2.036 12.322a1.012 1.012 0 0 1 0-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178Z" /><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" /></svg>`;
	const IconEdit = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0 1 15.75 21H5.25A2.25 2.25 0 0 1 3 18.75V8.25A2.25 2.25 0 0 1 5.25 6H10" /></svg>`;
	const IconClone = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 17.25v3.375c0 .621-.504 1.125-1.125 1.125h-9.75c-.621 0-1.125-.504-1.125-1.125V7.875c0-.621.504-1.125 1.125-1.125H6.75a9.06 9.06 0 0 1 1.5.124m7.5 10.376h3.375c.621 0 1.125-.504 1.125-1.125V11.25c0-4.46-3.243-8.161-7.5-8.876a9.06 9.06 0 0 0-1.5-.124H9.375c-.621 0-1.125.504-1.125 1.125v3.5m7.5 10.375H9.375a1.125 1.125 0 0 1-1.125-1.125v-9.25m12 6.625v-1.875a3.375 3.375 0 0 0-3.375-3.375h-1.5a1.125 1.125 0 0 1-1.125-1.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H9.75" /></svg>`;
	const IconDelete = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0" /></svg>`;
	const IconRefresh = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99" /></svg>`;
	const IconExport = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3" /></svg>`;
	const IconUnpublish = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 17.25v3.375c0 .621-.504 1.125-1.125 1.125h-9.75c-.621 0-1.125-.504-1.125-1.125V7.875c0-.621.504-1.125 1.125-1.125H6.75a9.06 9.06 0 0 1 1.5.124m7.5 10.376h3.375c.621 0 1.125-.504 1.125-1.125V11.25c0-4.46-3.243-8.161-7.5-8.876a9.06 9.06 0 0 0-1.5-.124H9.375c-.621 0-1.125.504-1.125 1.125v3.5m7.5 10.375H9.375a1.125 1.125 0 0 1-1.125-1.125v-9.25m12 6.625v-1.875a3.375 3.375 0 0 0-3.375-3.375h-1.5a1.125 1.125 0 0 1-1.125-1.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H9.75" /></svg>`;
</script>

<!-- Container for the list -->
<div class="container mx-auto px-4 py-8">
	{#if loading}
		<p class="py-4 text-center text-gray-500">
			{localeLoaded
				? $_('assistants.loading', { default: 'Loading assistants...' })
				: 'Loading assistants...'}
		</p>
	{:else if error}
		<div
			class="relative rounded border border-red-400 bg-red-100 px-4 py-3 text-red-700"
			role="alert"
		>
			<strong class="font-bold">{localeLoaded ? $_('assistants.errorTitle') : 'Error:'}</strong>
			<span class="block sm:inline">{error}</span>
		</div>
	{:else if assistants.length === 0 && totalItems === 0}
		<p class="py-4 text-center text-gray-500">
			{localeLoaded
				? $_('assistants.noAssistants', { default: 'No assistants found.' })
				: 'No assistants found.'}
		</p>
	{:else}
		<!-- Responsive Table Wrapper -->
		<div class="mb-6 overflow-x-auto border border-gray-200 shadow-md sm:rounded-lg">
			<table class="min-w-full divide-y divide-gray-200">
				<thead class="bg-gray-50">
					<tr>
						<th
							scope="col"
							class="text-brand px-6 py-3 text-left text-xs font-medium tracking-wider uppercase"
						>
							{localeLoaded
								? $_('assistants.table.name', { default: 'Assistant Name' })
								: 'Assistant Name'}
						</th>
						<th
							scope="col"
							class="text-brand px-6 py-3 text-left text-xs font-medium tracking-wider uppercase"
						>
							{localeLoaded
								? $_('assistants.table.description', { default: 'Description' })
								: 'Description'}
						</th>
						<th
							scope="col"
							class="text-brand px-6 py-3 text-left text-xs font-medium tracking-wider uppercase"
						>
							{localeLoaded ? $_('assistants.table.actions', { default: 'Actions' }) : 'Actions'}
						</th>
					</tr>
				</thead>
				<tbody class="divide-y divide-gray-200 bg-white">
					{#each assistants as assistant (assistant.id)}
						<!-- Main row with name, description, actions -->
						<tr class="hover:bg-gray-50">
							<!-- Assistant Name -->
							<td class="px-6 py-4 align-top whitespace-normal">
								<button
									onclick={() => handleView(assistant.id)}
									class="text-brand text-left text-sm font-medium break-words hover:underline"
								>
									{assistant.name || '-'}
								</button>
								<!-- Status badge -->
								<div class="mt-1">
									{#if assistant.published}
										<span
											class="inline-flex rounded-full bg-green-100 px-2 py-0.5 text-xs leading-5 font-semibold text-green-800"
											>{localeLoaded
												? $_('assistants.status.published', { default: 'Published' })
												: 'Published'}</span
										>
									{:else}
										<span
											class="inline-flex rounded-full bg-yellow-100 px-2 py-0.5 text-xs leading-5 font-semibold text-yellow-800"
											>{localeLoaded
												? $_('assistants.status.unpublished', { default: 'Unpublished' })
												: 'Unpublished'}</span
										>
									{/if}
								</div>
							</td>

							<!-- Description with max width -->
							<td class="px-6 py-4 align-top">
								<div class="max-w-md text-sm break-words text-gray-500">
									{assistant.description ||
										(localeLoaded
											? $_('assistants.noDescription', { default: 'No description provided' })
											: 'No description provided')}
								</div>
							</td>

							<!-- Actions -->
							<td class="px-6 py-4 align-top text-sm font-medium whitespace-nowrap">
								<div class="flex items-center space-x-1 sm:space-x-2">
									<!-- View Button -->
									<button
										onclick={() => handleView(assistant.id)}
										title={localeLoaded
											? $_('assistants.actions.view', { default: 'View' })
											: 'View'}
										class="rounded p-1 text-green-600 transition-colors duration-150 hover:bg-green-100 hover:text-green-900"
									>
										{@html IconView}
									</button>
									<!-- Duplicate Button -->
									<button
										onclick={() =>
											dispatch('duplicate', { id: assistant.id, name: assistant.name })}
										title={localeLoaded
											? $_('assistants.actions.duplicate', { default: 'Duplicate' })
											: 'Duplicate'}
										class="rounded p-1 text-blue-600 transition-colors duration-150 hover:bg-blue-100 hover:text-blue-900"
									>
										{@html IconClone}
									</button>
									<!-- Export Button -->
									<button
										onclick={() => dispatch('export', { id: assistant.id })}
										title={localeLoaded
											? $_('assistants.actions.export', { default: 'Export JSON' })
											: 'Export JSON'}
										class="rounded p-1 text-green-600 transition-colors duration-150 hover:bg-green-100 hover:text-green-900"
									>
										{@html IconExport}
									</button>
									<!-- Publish/Unpublish Button -->
									{#if assistant.published}
										<button
											onclick={() =>
												handleUnpublish({
													detail: {
														assistantId: assistant.id,
														groupId: assistant.group_id,
														ownerEmail: assistant.owner
													}
												})}
											title={localeLoaded
												? $_('assistants.actions.unpublish', { default: 'Unpublish' })
												: 'Unpublish'}
											class="rounded p-1 text-yellow-600 transition-colors duration-150 hover:bg-yellow-100 hover:text-yellow-900"
										>
											{@html IconUnpublish}
										</button>
									{:else}
										<!-- Delete Button (Only show if not published) -->
										<button
											onclick={() =>
												dispatch('delete', {
													id: assistant.id,
													name: assistant.name,
													published: assistant.published
												})}
											title={localeLoaded
												? $_('assistants.actions.delete', { default: 'Delete' })
												: 'Delete'}
											class="rounded p-1 text-red-600 transition-colors duration-150 hover:bg-red-100 hover:text-red-900"
										>
											{@html IconDelete}
										</button>
									{/if}
								</div>
								<div class="mt-2 text-xs text-gray-400">ID: {assistant.id}</div>
							</td>
						</tr>

						<!-- Configuration rows -->
						{#if assistant.metadata}
							{@const callback = parseMetadata(assistant.metadata)}
							<!-- Single configuration row with all details -->
							<tr class="border-b border-gray-200 bg-gray-50">
								<td colspan="2" class="px-6 py-2 text-sm">
									<div class="flex flex-wrap items-center">
										<span class="text-brand mr-1 font-medium"
											>{localeLoaded
												? $_('assistants.table.promptProcessor', { default: 'Prompt Processor' })
												: 'Prompt Processor'}:</span
										>
										<span class="mr-3"
											>{callback.prompt_processor ||
												(localeLoaded
													? $_('assistants.notSet', { default: 'Not set' })
													: 'Not set')}</span
										>

										<span class="text-brand mr-1 font-medium"
											>{localeLoaded
												? $_('assistants.table.connector', { default: 'Connector' })
												: 'Connector'}:</span
										>
										<span class="mr-3"
											>{callback.connector ||
												(localeLoaded
													? $_('assistants.notSet', { default: 'Not set' })
													: 'Not set')}</span
										>

										<span class="text-brand mr-1 font-medium"
											>{localeLoaded
												? $_('assistants.table.llm', { default: 'LLM' })
												: 'LLM'}:</span
										>
										<span class="mr-3"
											>{callback.llm ||
												(localeLoaded
													? $_('assistants.notSet', { default: 'Not set' })
													: 'Not set')}</span
										>

										<span class="text-brand mr-1 font-medium"
											>{localeLoaded
												? $_('assistants.table.ragProcessor', { default: 'RAG Processor' })
												: 'RAG Processor'}:</span
										>
										<span
											>{callback.rag_processor ||
												(localeLoaded
													? $_('assistants.notSet', { default: 'Not set' })
													: 'Not set')}</span
										>
									</div>
								</td>
								<td class="px-6 py-2"></td>
								<!-- Empty cell to maintain table structure -->
							</tr>

							<!-- Conditional row for simple_rag details -->
							{#if callback.rag_processor === 'simple_rag'}
								<tr class="border-b border-gray-200 bg-gray-50">
									<td colspan="2" class="px-6 py-2 text-sm">
										<div class="flex flex-wrap">
											<div class="mr-6 mb-1">
												<span class="text-brand font-medium"
													>{localeLoaded
														? $_('assistants.table.ragTopK', { default: 'RAG Top K' })
														: 'RAG Top K'}:</span
												>
												<span class="ml-1"
													>{assistant.RAG_Top_k ??
														(localeLoaded
															? $_('assistants.notSet', { default: 'Not set' })
															: 'Not set')}</span
												>
											</div>
											<div>
												<span class="text-brand font-medium"
													>{localeLoaded
														? $_('assistants.table.ragCollections', { default: 'RAG Collections' })
														: 'RAG Collections'}:</span
												>
												<span class="ml-1 truncate" title={assistant.RAG_collections || ''}
													>{assistant.RAG_collections ||
														(localeLoaded
															? $_('assistants.notSet', { default: 'Not set' })
															: 'Not set')}</span
												>
											</div>
										</div>
									</td>
									<td class="px-6 py-2"></td>
									<!-- Empty cell to maintain table structure -->
								</tr>
							{/if}
						{:else}
							<!-- Placeholder row for when no metadata is available -->
							<tr class="border-b border-gray-200 bg-gray-50">
								<td colspan="2" class="px-6 py-2 text-sm text-gray-500">
									<span class="text-brand font-medium"
										>{localeLoaded
											? $_('assistants.table.config', { default: 'Configuration' })
											: 'Configuration'}:</span
									>
									<span class="ml-1"
										>{localeLoaded
											? $_('assistants.notSet', { default: 'Not available' })
											: 'Not available'}</span
									>
								</td>
								<td class="px-6 py-2"></td>
								<!-- Empty cell to maintain table structure -->
							</tr>
						{/if}
					{/each}
				</tbody>
			</table>
		</div>

		<!-- Pagination Controls -->
		{#if totalPages > 1}
			<!-- Centered container for all pagination elements -->
			<div class="mt-4 flex items-center justify-center space-x-4 text-sm text-gray-700">
				<!-- Refresh Button -->
				<button
					onclick={handleRefresh}
					disabled={loading || isRefreshing}
					title={localeLoaded ? $_('common.refresh', { default: 'Refresh' }) : 'Refresh'}
					class="rounded-md border border-gray-300 bg-white p-1.5 font-medium hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
				>
					<span class:animate-spin={isRefreshing}>
						{@html IconRefresh}
					</span>
				</button>

				<!-- Previous Button -->
				<button
					onclick={goToPreviousPage}
					disabled={currentPage === 1 || loading}
					class="rounded-md border border-gray-300 bg-white px-3 py-1 font-medium hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
				>
					{localeLoaded ? $_('pagination.previousShort', { default: '<' }) : '<'}
				</button>

				<!-- Page Info & Results Count -->
				<span>
					{localeLoaded ? $_('pagination.page', { default: 'Page' }) : 'Page'}
					{currentPage}
					{localeLoaded ? $_('pagination.of', { default: 'of' }) : 'of'}
					{totalPages}
					<span class="mx-2">|</span>
					{localeLoaded ? $_('pagination.resultsSimple', { default: 'Results' }) : 'Results'}
					<span class="text-brand font-medium">{(currentPage - 1) * ITEMS_PER_PAGE + 1}</span>
					{localeLoaded ? $_('pagination.to', { default: 'to' }) : 'to'}
					<span class="text-brand font-medium"
						>{Math.min(currentPage * ITEMS_PER_PAGE, totalItems)}</span
					>
					{localeLoaded ? $_('pagination.of', { default: 'of' }) : 'of'}
					<span class="text-brand font-medium">{totalItems}</span>
				</span>

				<!-- Next Button -->
				<button
					onclick={goToNextPage}
					disabled={currentPage === totalPages || loading}
					class="rounded-md border border-gray-300 bg-white px-3 py-1 font-medium hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
				>
					{localeLoaded ? $_('pagination.nextShort', { default: '>' }) : '>'}
				</button>
			</div>
		{/if}
	{/if}
</div>

<!-- Publish Modal -->
{#if $publishModalOpen}
	<!-- <PublishModal on:assistantPublished={handleAssistantPublished} /> -->
{/if}
