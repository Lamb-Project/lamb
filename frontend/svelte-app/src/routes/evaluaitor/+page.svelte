<script>
	import { onMount, onDestroy } from 'svelte';
	import { goto } from '$app/navigation';
	import { base } from '$app/paths';
	import { page } from '$app/stores';
	import { user } from '$lib/stores/userStore';
	import { _, locale } from '$lib/i18n';
	import RubricsList from '$lib/components/evaluaitor/RubricsList.svelte';
	import RubricForm from '$lib/components/evaluaitor/RubricForm.svelte';
	import RubricAIGenerationModal from '$lib/components/evaluaitor/RubricAIGenerationModal.svelte';

	// Default text for when i18n isn't loaded yet
	let localeLoaded = $state(!!$locale);

	// State Management
	/** @type {'list' | 'create'} */
	let currentView = $state('list');
	let showAIModal = $state(false);

	// URL Handling
	/** @type {Function|null} */
	let unsubscribePage = null;

	// Redirect to login if not authenticated
	$effect(() => {
		if (!$user.isLoggedIn) {
			window.location.href = '/';
		}
	});

	// Handle rubric creation success
	function handleRubricCreated(event) {
		// Add check for event.detail
		if (event.detail && typeof event.detail.rubricId === 'string') {
			const newRubricId = event.detail.rubricId;
			console.log(`Rubric created with ID: ${newRubricId}, navigating to list.`);
			// Navigate back to the list view
			currentView = 'list';
			goto(`${base}/evaluaitor`, { replaceState: true });
		} else {
			console.error('handleRubricCreated received event without expected detail:', event);
		}
	}

	// Handle AI generation modal
	function openAIModal() {
		showAIModal = true;
	}

	function closeAIModal() {
		showAIModal = false;
	}

	function handleAIRubricCreated(event) {
		showAIModal = false;
		// Navigate back to the list view
		if (event.detail && event.detail.rubricId) {
			const newRubricId = event.detail.rubricId;
			console.log(`AI-generated rubric created: ${newRubricId}, navigating to list.`);
			currentView = 'list';
			goto(`${base}/evaluaitor`, { replaceState: true });
		}
	}

	// Lifecycle
	onMount(() => {
		unsubscribePage = page.subscribe((currentPage) => {
			const viewParam = currentPage.url.searchParams.get('view');
			console.log(`[+page.svelte] URL Params: view=${viewParam}`);

			if (viewParam === 'create') {
				if (currentView !== 'create') {
					console.log("URL indicates 'create' view.");
					currentView = 'create';
				}
			} else if (currentView !== 'list') {
				console.log("URL indicates 'list' view.");
				currentView = 'list';
			}
		});
	});

	onDestroy(() => {
		if (unsubscribePage) {
			unsubscribePage();
		}
	});
</script>

<svelte:head>
	<title>Evaluaitor - Educational Rubrics</title>
</svelte:head>

<h1 class="text-brand mb-4 text-3xl font-bold">
	{localeLoaded ? $_('evaluaitor.title', { default: 'Evaluaitor' }) : 'Evaluaitor'}
</h1>

<!-- Tabs/View Navigation -->
<div class="mb-6 border-b border-gray-200">
	<nav class="-mb-px flex items-center space-x-8" aria-label="Tabs">
		<!-- List View Button (Acts like a tab) -->
		<button
			class="rounded-t-md border-b-2 px-1 py-4 text-sm font-medium whitespace-nowrap transition-colors duration-150 {currentView ===
			'list'
				? 'bg-brand border-brand text-white'
				: 'border-transparent text-gray-800 hover:border-gray-400 hover:text-gray-900'}"
			style={currentView === 'list'
				? 'background-color: #2271b3; color: white; border-color: #2271b3;'
				: ''}
			onclick={() => {
				currentView = 'list';
				goto(`${base}/evaluaitor`, { replaceState: true });
			}}
		>
			{localeLoaded ? $_('evaluaitor.myRubricsTab', { default: 'My Rubrics' }) : 'My Rubrics'}
		</button>
		<!-- Create View Button -->
		<button
			class="rounded-t-md border-b-2 px-1 py-4 text-sm font-medium whitespace-nowrap {currentView ===
			'create'
				? 'bg-brand border-brand text-white'
				: 'border-transparent text-gray-800 hover:border-gray-400 hover:text-gray-900'}"
			style={currentView === 'create'
				? 'background-color: #2271b3; color: white; border-color: #2271b3;'
				: ''}
			onclick={() => {
				currentView = 'create';
				goto(`${base}/evaluaitor?view=create`, { replaceState: true });
			}}
		>
			{localeLoaded
				? $_('evaluaitor.createRubricTab', { default: 'Create Rubric' })
				: 'Create Rubric'}
		</button>
	</nav>
</div>

<!-- Conditional Content Rendering -->
{#if currentView === 'list'}
	<div class="mt-6">
		<div class="rounded-lg border border-gray-200 bg-white p-4 shadow">
			<RubricsList
				on:duplicate={(event) => console.log('Duplicate rubric:', event.detail)}
				on:delete={(event) => console.log('Delete rubric:', event.detail)}
				on:export={(event) => console.log('Export rubric:', event.detail)}
				on:toggleVisibility={(event) => console.log('Toggle visibility:', event.detail)}
			/>
		</div>
	</div>
{:else if currentView === 'create'}
	<!-- Rubric Form -->
	<RubricForm on:formSuccess={handleRubricCreated} on:openAIModal={openAIModal} />
{/if}

<!-- AI Generation Modal -->
<RubricAIGenerationModal
	show={showAIModal}
	onclose={closeAIModal}
	onrubricCreated={handleAIRubricCreated}
/>
