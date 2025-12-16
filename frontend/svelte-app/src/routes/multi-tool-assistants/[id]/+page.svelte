<script>
	import { _ } from '$lib/i18n';
	import { page } from '$app/stores';
	import { getAssistantById } from '$lib/services/assistantService';
	import { parseMultiToolMetadata } from '$lib/services/multiToolAssistantService';
	import MultiToolAssistantView from '$lib/components/multi-tool-assistants/MultiToolAssistantView.svelte';
	import MultiToolAssistantForm from '$lib/components/multi-tool-assistants/MultiToolAssistantForm.svelte';
	import { goto } from '$app/navigation';
	import { base } from '$app/paths';

	// Get assistant ID from URL
	let assistantId = $derived($page.params.id);

	// Page state
	let assistant = $state(null);
	let loading = $state(true);
	let error = $state(null);
	let editMode = $state(false);

	// Load assistant data
	async function loadAssistant() {
		try {
			loading = true;
			error = null;

			const data = await getAssistantById(assistantId);
			const metadata = parseMultiToolMetadata(data);

			// Check if this is actually a multi-tool assistant
			if (metadata.assistant_type !== 'multi_tool') {
				// Redirect to regular assistant view
				goto(`${base}/assistants/${assistantId}`);
				return;
			}

			assistant = data;
		} catch (err) {
			console.error('Error loading assistant:', err);
			error = err.message || 'Failed to load assistant';
		} finally {
			loading = false;
		}
	}

	// Load assistant on mount and when ID changes
	$effect(() => {
		if (assistantId) {
			loadAssistant();
		}
	});

	// Handle view actions
	function handleEdit() {
		editMode = true;
	}

	function handleSuccess() {
		editMode = false;
		loadAssistant(); // Reload data
	}

	function handleCancel() {
		editMode = false;
	}

	function handleDelete(event) {
		const { assistant } = event.detail;
		// Navigate back to assistants list
		goto(`${base}/assistants`);
	}

	function handleDuplicate(event) {
		// TODO: Implement duplicate functionality
		console.log('Duplicate assistant:', event.detail.assistant);
	}

	function handleShare(event) {
		// TODO: Implement share functionality
		console.log('Share assistant:', event.detail.assistant);
	}

	function handlePublish(event) {
		// TODO: Implement publish functionality
		console.log('Publish assistant:', event.detail.assistant);
		loadAssistant(); // Reload to show updated status
	}

	function handleUnpublish(event) {
		// TODO: Implement unpublish functionality
		console.log('Unpublish assistant:', event.detail.assistant);
		loadAssistant(); // Reload to show updated status
	}

	function handleTest(event) {
		// TODO: Implement test functionality
		console.log('Test assistant:', event.detail.assistant);
	}
</script>

<div class="assistant-page">
	{#if loading}
		<div class="loading-state">
			<div class="spinner"></div>
			<p>{_("Loading assistant...")}</p>
		</div>
	{:else if error}
		<div class="error-state">
			<h2>{_("Error Loading Assistant")}</h2>
			<p>{error}</p>
			<button onclick={loadAssistant} class="retry-btn">
				{_("Try Again")}
			</button>
		</div>
	{:else if assistant}
		<div class="page-header">
			<div class="breadcrumb">
				<a href={`${base}/assistants`}>{_("Assistants")}</a>
				<span class="separator">›</span>
				<a href={`${base}/multi-tool-assistants`}>{_("Multi-Tool")}</a>
				<span class="separator">›</span>
				<span>{assistant.name}</span>
			</div>
		</div>

		{#if editMode}
			<div class="edit-container">
				<div class="edit-header">
					<h1>{_("Edit Multi-Tool Assistant")}</h1>
					<button class="cancel-btn" onclick={handleCancel}>
						{_("Cancel")}
					</button>
				</div>
				<MultiToolAssistantForm
					{assistant}
					startInEdit={true}
					on:success={handleSuccess}
				/>
			</div>
		{:else}
			<MultiToolAssistantView
				{assistant}
				on:edit={handleEdit}
				on:delete={handleDelete}
				on:duplicate={handleDuplicate}
				on:share={handleShare}
				on:publish={handlePublish}
				on:unpublish={handleUnpublish}
				on:test={handleTest}
			/>
		{/if}
	{:else}
		<div class="not-found-state">
			<h2>{_("Assistant Not Found")}</h2>
			<p>{_("The requested multi-tool assistant could not be found.")}</p>
			<a href={`${base}/assistants`} class="back-link">
				{_("Back to Assistants")}
			</a>
		</div>
	{/if}
</div>

<style>
	.assistant-page {
		min-height: 100vh;
	}

	.page-header {
		padding: 1rem 2rem;
		border-bottom: 1px solid #e9ecef;
		background: white;
	}

	.breadcrumb {
		font-size: 0.9rem;
		color: #6c757d;
		margin-bottom: 0.5rem;
	}

	.breadcrumb a {
		color: #0d6efd;
		text-decoration: none;
	}

	.breadcrumb a:hover {
		text-decoration: underline;
	}

	.separator {
		margin: 0 0.5rem;
	}

	.loading-state, .error-state, .not-found-state {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		min-height: 50vh;
		text-align: center;
		padding: 2rem;
	}

	.spinner {
		width: 40px;
		height: 40px;
		border: 4px solid #f3f3f3;
		border-top: 4px solid #0d6efd;
		border-radius: 50%;
		animation: spin 1s linear infinite;
		margin-bottom: 1rem;
	}

	@keyframes spin {
		0% { transform: rotate(0deg); }
		100% { transform: rotate(360deg); }
	}

	.error-state h2, .not-found-state h2 {
		color: #dc3545;
		margin: 0 0 1rem 0;
	}

	.retry-btn, .back-link {
		background: #0d6efd;
		color: white;
		border: none;
		padding: 0.75rem 1.5rem;
		border-radius: 6px;
		text-decoration: none;
		cursor: pointer;
		font-size: 1rem;
		transition: background-color 0.2s ease;
	}

	.retry-btn:hover, .back-link:hover {
		background: #0b5ed7;
		text-decoration: none;
		color: white;
	}

	.edit-container {
		padding: 2rem;
	}

	.edit-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 2rem;
		padding-bottom: 1rem;
		border-bottom: 2px solid #e9ecef;
	}

	.edit-header h1 {
		margin: 0;
		color: #212529;
		font-size: 2rem;
	}

	.cancel-btn {
		background: #6c757d;
		color: white;
		border: none;
		padding: 0.5rem 1rem;
		border-radius: 4px;
		cursor: pointer;
		font-size: 0.9rem;
		transition: background-color 0.2s ease;
	}

	.cancel-btn:hover {
		background: #5a6268;
	}

	@media (max-width: 768px) {
		.page-header {
			padding: 1rem;
		}

		.edit-container {
			padding: 1rem;
		}

		.edit-header {
			flex-direction: column;
			align-items: stretch;
			gap: 1rem;
		}

		.edit-header h1 {
			font-size: 1.5rem;
		}
	}
</style>