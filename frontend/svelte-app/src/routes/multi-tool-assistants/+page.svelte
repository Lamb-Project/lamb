<script>
	import { _ } from '$lib/i18n';
	import { browser } from '$app/environment';
	import MultiToolAssistantForm from '$lib/components/multi-tool-assistants/MultiToolAssistantForm.svelte';
	import { goto } from '$app/navigation';
	import { base } from '$app/paths';

	// Page state
	let showCreateForm = $state(false);
</script>

<div class="multi-tool-assistants-page">
	<div class="page-header">
		<div class="header-content">
			<h1>{$_("Multi-Tool Assistants")}</h1>
			<p class="page-description">
				{$_("Create and manage assistants that can use multiple tools to gather context before responding.")}
			</p>
		</div>

		<div class="header-actions">
			<button
				class="create-btn"
				onclick={() => showCreateForm = true}
			>
				➕ {$_("Create Multi-Tool Assistant")}
			</button>
		</div>
	</div>

	{#if showCreateForm}
		<div
			class="modal-overlay"
			onclick={() => showCreateForm = false}
			onkeydown={(e) => { if (e.key === 'Escape') showCreateForm = false; }}
			role="dialog"
			aria-modal="true"
			aria-labelledby="modal-title"
			tabindex="-1"
		>
		<div class="modal-content" role="document" onclick={(e) => e.stopPropagation()}>
			<div class="modal-header">
				<h2>{$_("Create Multi-Tool Assistant")}</h2>
				<button class="close-btn" onclick={() => showCreateForm = false}>×</button>
			</div>
				<div class="modal-body">
					<MultiToolAssistantForm
						on:success={() => {
							showCreateForm = false;
							goto(`${base}/assistants`);
						}}
					/>
				</div>
			</div>
		</div>
	{:else}
		<div class="empty-state">
			<div class="empty-icon">🔧</div>
			<h2>{$_("No Multi-Tool Assistants Yet")}</h2>
			<p>{$_("Create your first multi-tool assistant to get started.")}</p>
			<button
				class="create-btn primary"
				onclick={() => showCreateForm = true}
			>
				➕ {$_("Create Your First Assistant")}
			</button>
		</div>
	{/if}
</div>

<style>
	.multi-tool-assistants-page {
		max-width: 1200px;
		margin: 0 auto;
		padding: 2rem;
	}

	.page-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		margin-bottom: 2rem;
		padding-bottom: 1.5rem;
		border-bottom: 2px solid #e9ecef;
	}

	.header-content h1 {
		margin: 0 0 0.5rem 0;
		color: #212529;
		font-size: 2.5rem;
	}

	.page-description {
		color: #6c757d;
		margin: 0;
		font-size: 1.1rem;
		line-height: 1.5;
		max-width: 600px;
	}

	.header-actions {
		flex-shrink: 0;
	}

	.create-btn {
		background: #0d6efd;
		color: white;
		border: none;
		padding: 0.75rem 1.5rem;
		border-radius: 6px;
		font-size: 1rem;
		font-weight: 500;
		cursor: pointer;
		transition: background-color 0.2s ease;
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.create-btn:hover {
		background: #0b5ed7;
	}

	.create-btn.primary {
		background: #198754;
	}

	.create-btn.primary:hover {
		background: #157347;
	}

	.empty-state {
		text-align: center;
		padding: 4rem 2rem;
		background: #f8f9fa;
		border: 2px dashed #dee2e6;
		border-radius: 12px;
		margin-top: 2rem;
	}

	.empty-icon {
		font-size: 4rem;
		margin-bottom: 1rem;
		opacity: 0.5;
	}

	.empty-state h2 {
		color: #495057;
		margin: 0 0 1rem 0;
		font-size: 1.5rem;
	}

	.empty-state p {
		color: #6c757d;
		margin: 0 0 2rem 0;
		font-size: 1.1rem;
	}

	.modal-overlay {
		position: fixed;
		top: 0;
		left: 0;
		width: 100%;
		height: 100%;
		background: rgba(0, 0, 0, 0.5);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 1000;
		padding: 1rem;
	}

	.modal-content {
		background: white;
		border-radius: 8px;
		box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
		max-width: 1000px;
		width: 100%;
		max-height: 90vh;
		overflow: hidden;
		display: flex;
		flex-direction: column;
	}

	.modal-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 1.5rem;
		border-bottom: 1px solid #e9ecef;
		background: #f8f9fa;
	}

	.modal-header h2 {
		margin: 0;
		color: #212529;
		font-size: 1.5rem;
	}

	.close-btn {
		background: none;
		border: none;
		font-size: 1.5rem;
		cursor: pointer;
		color: #6c757d;
		padding: 0.25rem;
		border-radius: 4px;
		transition: all 0.2s ease;
	}

	.close-btn:hover {
		background: #e9ecef;
		color: #495057;
	}

	.modal-body {
		padding: 0;
		overflow-y: auto;
		flex: 1;
	}

	@media (max-width: 768px) {
		.multi-tool-assistants-page {
			padding: 1rem;
		}

		.page-header {
			flex-direction: column;
			align-items: stretch;
			gap: 1rem;
		}

		.header-content h1 {
			font-size: 2rem;
		}

		.modal-content {
			max-height: 95vh;
		}

		.modal-header {
			padding: 1rem;
		}

		.modal-header h2 {
			font-size: 1.25rem;
		}
	}
</style>