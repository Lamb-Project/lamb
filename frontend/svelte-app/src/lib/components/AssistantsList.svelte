<script>
	import { onMount, onDestroy } from 'svelte';
	import { get } from 'svelte/store';
	import { goto } from '$app/navigation';
	import { createEventDispatcher } from 'svelte';
	import { user } from '$lib/stores/userStore';
	import {
		getAssistants,
		getSharedAssistants,
		deleteAssistant,
		downloadAssistant
	} from '$lib/services/assistantService';
	import { base } from '$app/paths';
	import { browser } from '$app/environment';
	import { _, locale } from '$lib/i18n';

	// Import new components and utilities
	import Pagination from './common/Pagination.svelte';
	import FilterBar from './common/FilterBar.svelte';
	import ConfirmationModal from './modals/ConfirmationModal.svelte';
	import { processListData } from '$lib/utils/listHelpers';
	import { formatDateForTable } from '$lib/utils/dateHelpers';
	import { getAssistantMetadataObject } from '$lib/utils/assistantData';

	// State for the delete confirmation modal
	let showDeleteModal = $state(false);
	/** @type {{ id: number|null, name: string, published: boolean }} */
	let deleteTarget = $state({ id: null, name: '', published: false });
	let isDeleting = $state(false);
	// Handler to open the delete confirmation modal
	function handleDelete(assistant) {
		deleteTarget = {
			id: assistant.id,
			name: assistant.name ?? '',
			published: !!assistant.published
		};
		showDeleteModal = true;
	}

	// Handler to confirm deletion from the modal
	async function handleDeleteConfirm() {
		if (!deleteTarget.id || isDeleting) return;
		isDeleting = true;
		try {
			await deleteAssistant(deleteTarget.id);
			await loadAllAssistants(); // Refresh the list automatically
			showDeleteModal = false;
			deleteTarget = { id: null, name: '', published: false };
		} catch (err) {
			console.error('Error deleting assistant:', err);
			// Optional: show error to user
		} finally {
			isDeleting = false;
		}
	}

	// Handler to cancel deletion from the modal
	function handleDeleteCancel() {
		if (isDeleting) return;
		showDeleteModal = false;
		deleteTarget = { id: null, name: '', published: false };
	}

	// ✅ CORRECT: Props using $props()
	let { showShared = false } = $props();

	// Default text for when i18n isn't loaded yet
	let localeLoaded = $state(!!get(locale));
	const dispatch = createEventDispatcher();

	// All assistants (fetched once)
	/** @type {Array<any>} */
	let allAssistants = $state([]);

	// Filtered and paginated assistants (for display)
	/** @type {Array<any>} */
	let displayAssistants = $state([]);

	// Loading and error states
	let loading = $state(true);
	/** @type {string | null} */
	let error = $state(null);
	let isRefreshing = $state(false);

	// Filter state
	let searchTerm = $state('');
	let filterStatus = $state(''); // '', 'published', 'unpublished'

	// Sort state
	let sortBy = $state('updated_at');
	let sortOrder = $state('desc');

	// Pagination state
	let currentPage = $state(1);
	let itemsPerPage = $state(10);
	let totalPages = $state(1);
	let totalItems = $state(0);

	// Lifecycle and Data Loading
	let localeUnsubscribe = () => {};
	let userUnsubscribe = () => {};
	// Track mount status so the retry recursion in loadAllAssistants does not
	// resume after the component has been destroyed (e.g. logout, route change
	// mid-retry). Without this, setState fires on a destroyed component. (#352, H8)
	let isMounted = true;

	onMount(() => {
		localeUnsubscribe = locale.subscribe((value) => {
			if (value) {
				localeLoaded = true;
			}
		});

		if (browser) {
			userUnsubscribe = user.subscribe((userData) => {
				if (userData.isLoggedIn) {
					if (allAssistants.length === 0 && !loading) {
						console.log('User logged in, loading assistants...');
						loadAllAssistants();
					}
				} else {
					console.log('User logged out, clearing assistants.');
					allAssistants = [];
					displayAssistants = [];
					totalItems = 0;
					currentPage = 1;
					error = null;
					loading = false;
				}
			});

			const initialUserData = $user;
			if (initialUserData.isLoggedIn) {
				console.log('User already logged in on mount, loading assistants...');
				loadAllAssistants();
			}
		}

		return () => {
			isMounted = false;
			localeUnsubscribe();
			if (userUnsubscribe) userUnsubscribe();
		};
	});

	// Load all assistants (with high limit for client-side processing)
	// retryAttempt tracks whether we've already retried (to avoid infinite loops)
	async function loadAllAssistants(retryAttempt = false) {
		if (!isMounted) return;
		loading = true;
		error = null;
		try {
			console.log(showShared ? 'Fetching shared assistants...' : 'Fetching all assistants...');
			const response = showShared ? await getSharedAssistants() : await getAssistants(100, 0); // Backend max is 100 items
			console.log('Received assistants:', response);

			if (!isMounted) return;
			allAssistants = response.assistants || [];
			applyFiltersAndPagination();
		} catch (err) {
			console.error('Error loading assistants:', err);
			if (!retryAttempt && isMounted) {
				console.log('Will retry loading assistants in 1 second...');
				loading = true;
				await new Promise((resolve) => setTimeout(resolve, 1000));
				if (!isMounted) return; // Don't recurse if unmounted while waiting
				return loadAllAssistants(true);
			}
			if (!isMounted) return;
			error = err instanceof Error ? err.message : String(err);
			allAssistants = [];
			displayAssistants = [];
			totalItems = 0;
		} finally {
			if (isMounted) loading = false;
		}
	}

	// Apply filters, sorting, and pagination
	function applyFiltersAndPagination() {
		const result = processListData(allAssistants, {
			search: searchTerm,
			searchFields: ['name', 'description', 'owner'],
			filters: {
				published: filterStatus === '' ? null : filterStatus === 'published'
			},
			sortBy,
			sortOrder,
			page: currentPage,
			itemsPerPage
		});

		displayAssistants = result.items;
		totalItems = result.filteredCount;
		totalPages = result.totalPages;
		currentPage = result.currentPage; // Use safe page from result
	}

	// Refresh function
	async function handleRefresh() {
		if (isRefreshing) return;
		console.log('Manual refresh triggered...');
		isRefreshing = true;
		await loadAllAssistants();
		isRefreshing = false;
	}

	// --- Filter and Pagination Event Handlers ---

	function handleSearchChange(event) {
		searchTerm = event.detail.value;
		currentPage = 1; // Reset to first page
		applyFiltersAndPagination();
	}

	function handleFilterChange(event) {
		const { key, value } = event.detail;
		if (key === 'status') {
			filterStatus = value;
		}
		currentPage = 1; // Reset to first page
		applyFiltersAndPagination();
	}

	function handleSortChange(event) {
		sortBy = event.detail.sortBy;
		sortOrder = event.detail.sortOrder;
		applyFiltersAndPagination();
	}

	// Handle column header click for sorting
	function handleColumnSort(column) {
		if (sortBy === column) {
			// Toggle order if clicking same column
			sortOrder = sortOrder === 'asc' ? 'desc' : 'asc';
		} else {
			// Set new column with default descending order
			sortBy = column;
			sortOrder = 'desc';
		}
		applyFiltersAndPagination();
	}

	// Handle date column sort - toggles between created_at and updated_at
	function handleDateColumnSort() {
		if (sortBy === 'created_at' || sortBy === 'updated_at') {
			// Toggle between created_at and updated_at
			if (sortBy === 'created_at') {
				sortBy = 'updated_at';
			} else {
				sortBy = 'created_at';
			}
			// Keep the same sort order
		} else {
			// Start with updated_at (default)
			sortBy = 'updated_at';
			sortOrder = 'desc';
		}
		applyFiltersAndPagination();
	}

	function handlePageChange(event) {
		currentPage = event.detail.page;
		applyFiltersAndPagination();
	}

	function handleItemsPerPageChange(event) {
		itemsPerPage = event.detail.itemsPerPage;
		currentPage = 1; // Reset to first page
		applyFiltersAndPagination();
	}

	function handleClearFilters() {
		searchTerm = '';
		filterStatus = '';
		sortBy = 'updated_at';
		sortOrder = 'desc';
		currentPage = 1;
		applyFiltersAndPagination();
	}

	// --- Action Handlers ---

	/**
	 * Handle view button click
	 * @param {number} id - The ID of the assistant to view
	 */
	function handleView(id) {
		console.log(`View assistant (navigate to detail view): ${id}`);
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
		const targetUrl = `${base}/assistants?view=detail&id=${id}&startInEdit=true`;
		console.log('[AssistantsList] Navigating to edit:', targetUrl);
		goto(targetUrl);
	}

	// --- SVG Icons (Ensure definitions are present) ---
	const IconView = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M2.036 12.322a1.012 1.012 0 0 1 0-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178Z" /><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" /></svg>`;
	const IconEdit = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0 1 15.75 21H5.25A2.25 2.25 0 0 1 3 18.75V8.25A2.25 2.25 0 0 1 5.25 6H10" /></svg>`;
	const IconDelete = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0" /></svg>`;
	const IconRefresh = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99" /></svg>`;
	const IconExport = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3" /></svg>`;
</script>

<!-- Container for the list -->
<div class="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
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
	{:else}
		<!-- Filter Bar -->
		<FilterBar
			searchPlaceholder={localeLoaded
				? $_('assistants.searchPlaceholder', {
						default: 'Search assistants by name, description...'
					})
				: 'Search assistants by name, description...'}
			searchValue={searchTerm}
			filters={[
				{
					key: 'status',
					label: localeLoaded ? $_('assistants.filters.status', { default: 'Status' }) : 'Status',
					options: [
						{
							value: 'published',
							label: localeLoaded
								? $_('assistants.status.published', { default: 'Published' })
								: 'Published'
						},
						{
							value: 'unpublished',
							label: localeLoaded
								? $_('assistants.status.unpublished', { default: 'Not Published' })
								: 'Not Published'
						}
					]
				}
			]}
			filterValues={{ status: filterStatus }}
			sortOptions={[
				{
					value: 'name',
					label: localeLoaded ? $_('assistants.sort.name', { default: 'Name' }) : 'Name'
				},
				{
					value: 'updated_at',
					label: localeLoaded
						? $_('assistants.sort.updated', { default: 'Last Modified' })
						: 'Last Modified'
				},
				{
					value: 'created_at',
					label: localeLoaded
						? $_('assistants.sort.created', { default: 'Created Date' })
						: 'Created Date'
				}
			]}
			{sortBy}
			{sortOrder}
			on:searchChange={handleSearchChange}
			on:filterChange={handleFilterChange}
			on:sortChange={handleSortChange}
			on:clearFilters={handleClearFilters}
		/>

		<!-- Results count and refresh button -->
		<div class="mb-4 flex items-center justify-between px-4">
			<div class="text-sm text-gray-600">
				{#if searchTerm || filterStatus}
					{localeLoaded ? $_('assistants.showingFiltered', { default: 'Showing' }) : 'Showing'}
					<span class="font-medium">{totalItems}</span>
					{localeLoaded ? $_('assistants.of', { default: 'of' }) : 'of'}
					<span class="font-medium">{allAssistants.length}</span>
					{localeLoaded ? $_('assistants.items', { default: 'assistants' }) : 'assistants'}
				{:else}
					<span class="font-medium">{totalItems}</span>
					{localeLoaded ? $_('assistants.totalItems', { default: 'assistants' }) : 'assistants'}
				{/if}
			</div>

			<!-- Refresh button -->
			<button
				onclick={handleRefresh}
				disabled={loading || isRefreshing}
				title={localeLoaded ? $_('common.refresh', { default: 'Refresh' }) : 'Refresh'}
				class="focus:ring-brand rounded-md border border-gray-300 bg-white p-2 text-sm font-medium hover:bg-gray-50 focus:ring-2 focus:ring-offset-2 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
			>
				<span class:animate-spin={isRefreshing}>
					{@html IconRefresh}
				</span>
			</button>
		</div>

		{#if displayAssistants.length === 0}
			{#if allAssistants.length === 0}
				<!-- No assistants at all -->
				<div class="rounded-lg border border-gray-200 bg-white py-12 text-center">
					<p class="text-gray-500">
						{localeLoaded
							? $_('assistants.noAssistants', { default: 'No assistants found.' })
							: 'No assistants found.'}
					</p>
				</div>
			{:else}
				<!-- No results match filters -->
				<div class="rounded-lg border border-gray-200 bg-white py-12 text-center">
					<p class="mb-4 text-gray-500">
						{localeLoaded
							? $_('assistants.noMatches', { default: 'No assistants match your filters' })
							: 'No assistants match your filters'}
					</p>
					<button
						onclick={handleClearFilters}
						class="text-brand hover:text-brand-hover focus:ring-brand rounded-md px-3 py-1 hover:underline focus:ring-2 focus:ring-offset-2 focus:outline-none"
					>
						{localeLoaded
							? $_('common.clearFilters', { default: 'Clear filters' })
							: 'Clear filters'}
					</button>
				</div>
			{/if}
		{:else}
			<!-- Responsive Table Wrapper -->
			<div class="mb-6 overflow-x-auto border border-gray-200 shadow-md sm:rounded-lg">
				<table class="min-w-full table-fixed divide-y divide-gray-200">
					<colgroup>
						<col class="w-1/5" />
						<col class="w-2/5" />
						<col class="w-1/5" />
						<col class="w-1/5" />
					</colgroup>
					<thead class="bg-gray-50">
						<tr>
							<th
								scope="col"
								class="text-brand cursor-pointer px-6 py-3 text-left text-xs font-medium tracking-wider uppercase select-none hover:bg-gray-100"
								onclick={() => handleColumnSort('name')}
							>
								<div class="flex items-center gap-1">
									{localeLoaded
										? $_('assistants.table.name', { default: 'Assistant Name' })
										: 'Assistant Name'}
									{#if sortBy === 'name'}
										{#if sortOrder === 'asc'}
											<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
												<path
													stroke-linecap="round"
													stroke-linejoin="round"
													stroke-width="2"
													d="M3 4h13M3 8h9m-9 4h6m4 0l4-4m0 0l4 4m-4-4v12"
												/>
											</svg>
										{:else}
											<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
												<path
													stroke-linecap="round"
													stroke-linejoin="round"
													stroke-width="2"
													d="M3 4h13M3 8h9m-9 4h9m5-4v12m0 0l-4-4m4 4l4-4"
												/>
											</svg>
										{/if}
									{/if}
								</div>
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
								class="text-brand cursor-pointer px-6 py-3 text-left text-xs font-medium tracking-wider whitespace-nowrap uppercase select-none hover:bg-gray-100"
								onclick={handleDateColumnSort}
							>
								<div class="flex items-center gap-1">
									{localeLoaded
										? $_('assistants.table.createdUpdated', { default: 'Created / Updated' })
										: 'Created / Updated'}
									{#if sortBy === 'created_at' || sortBy === 'updated_at'}
										<span class="ml-1 text-xs text-gray-500">
											({sortBy === 'created_at' ? 'Created' : 'Updated'})
										</span>
										{#if sortOrder === 'asc'}
											<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
												<path
													stroke-linecap="round"
													stroke-linejoin="round"
													stroke-width="2"
													d="M3 4h13M3 8h9m-9 4h6m4 0l4-4m0 0l4 4m-4-4v12"
												/>
											</svg>
										{:else}
											<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
												<path
													stroke-linecap="round"
													stroke-linejoin="round"
													stroke-width="2"
													d="M3 4h13M3 8h9m-9 4h9m5-4v12m0 0l-4-4m4 4l4-4"
												/>
											</svg>
										{/if}
									{/if}
								</div>
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
						{#each displayAssistants as assistant (assistant.id)}
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
									<!-- Status badges -->
									<div class="mt-1 flex flex-wrap gap-1">
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
										{#if showShared}
											<span
												class="inline-flex rounded-full bg-blue-100 px-2 py-0.5 text-xs leading-5 font-semibold text-blue-800"
												>{localeLoaded
													? $_('assistants.status.sharedWithYou', { default: 'Shared with you' })
													: 'Shared with you'}</span
											>
										{/if}
										{#if assistant.metadata}
											{@const callback = getAssistantMetadataObject(assistant)}
											{#if callback.capabilities?.vision}
												<span
													class="inline-flex items-center rounded-full bg-purple-100 px-2 py-0.5 text-xs font-medium text-purple-800"
												>
													<svg class="mr-1 h-3 w-3" fill="currentColor" viewBox="0 0 20 20">
														<path
															fill-rule="evenodd"
															d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
															clip-rule="evenodd"
														></path>
													</svg>
													{localeLoaded
														? $_('assistants.table.visionEnabled', { default: 'Vision' })
														: 'Vision'}
												</span>
											{/if}
										{/if}
									</div>
								</td>

								<!-- Description with more space -->
								<td class="px-6 py-4 align-top">
									<div class="text-sm break-words text-gray-500">
										{assistant.description ||
											(localeLoaded
												? $_('assistants.noDescription', { default: 'No description provided' })
												: 'No description provided')}
									</div>
								</td>

								<!-- Created / Updated Dates (combined column) -->
								<td class="px-6 py-4 align-top text-sm text-gray-500">
									<div class="flex flex-col gap-1">
										<div>
											<span class="text-xs font-medium text-gray-400">Created:</span>
											<div class="text-xs">{formatDateForTable(assistant.created_at)}</div>
										</div>
										<div>
											<span class="text-xs font-medium text-gray-400">Updated:</span>
											<div class="text-xs">{formatDateForTable(assistant.updated_at)}</div>
										</div>
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
										<!-- Delete Button (Only show if not published - published assistants must be unpublished from detail view first) -->
										{#if !assistant.published}
											<button
												onclick={() => handleDelete(assistant)}
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
								{@const callback = getAssistantMetadataObject(assistant)}
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
											<span class="mr-3"
												>{callback.rag_processor ||
													(localeLoaded
														? $_('assistants.notSet', { default: 'Not set' })
														: 'Not set')}</span
											>

											{#if callback.capabilities?.vision}
												<span
													class="mr-3 inline-flex items-center rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-800"
												>
													<svg class="mr-1 h-3 w-3" fill="currentColor" viewBox="0 0 20 20">
														<path
															fill-rule="evenodd"
															d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
															clip-rule="evenodd"
														></path>
													</svg>
													{localeLoaded
														? $_('assistants.table.visionEnabled', { default: 'Vision Enabled' })
														: 'Vision Enabled'}
												</span>
											{/if}
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
															? $_('assistants.table.ragCollections', {
																	default: 'RAG Collections'
																})
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
				<Pagination
					{currentPage}
					{totalPages}
					{totalItems}
					{itemsPerPage}
					itemsPerPageOptions={[5, 10, 25, 50, 100]}
					on:pageChange={handlePageChange}
					on:itemsPerPageChange={handleItemsPerPageChange}
				/>
			{/if}
		{/if}
	{/if}
</div>

<!-- Delete Confirmation Modal (rendered once, outside the loop) -->
<ConfirmationModal
	bind:isOpen={showDeleteModal}
	bind:isLoading={isDeleting}
	title={localeLoaded
		? $_('assistants.deleteModal.title', { default: 'Delete Assistant' })
		: 'Delete Assistant'}
	message={localeLoaded
		? $_('assistants.deleteModal.confirmation', {
				values: { name: deleteTarget.name },
				default: `Are you sure you want to delete the assistant "${deleteTarget.name}"? This action cannot be undone.`
			})
		: `Are you sure you want to delete the assistant "${deleteTarget.name}"? This action cannot be undone.`}
	confirmText={localeLoaded
		? $_('assistants.deleteModal.confirmButton', { default: 'Delete' })
		: 'Delete'}
	variant="danger"
	onconfirm={handleDeleteConfirm}
	oncancel={handleDeleteCancel}
/>
