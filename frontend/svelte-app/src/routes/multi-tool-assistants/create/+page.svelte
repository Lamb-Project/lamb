<script>
	import { _, locale } from '$lib/i18n';
	import MultiToolAssistantForm from '$lib/components/multi-tool-assistants/MultiToolAssistantForm.svelte';
	import { goto } from '$app/navigation';
	import { base } from '$app/paths';

	// Locale state for i18n
	let localeLoaded = $state(false);
	let localeUnsubscribe = () => {};
	$effect(() => {
		localeUnsubscribe = locale.subscribe(value => {
			localeLoaded = !!value;
		});
		return () => {
			localeUnsubscribe();
		};
	});

	// Handle successful creation
	function handleSuccess() {
		goto(`${base}/assistants`);
	}
</script>

<div class="create-page">
	<div class="page-header">
		<div class="breadcrumb">
			<a href={`${base}/multi-tool-assistants`}>{localeLoaded ? $_('Multi-Tool Assistants') : 'Multi-Tool Assistants'}</a>
			<span class="separator">›</span>
			<span>{localeLoaded ? $_('Create') : 'Create'}</span>
		</div>
		<h1>{localeLoaded ? $_('Create Multi-Tool Assistant') : 'Create Multi-Tool Assistant'}</h1>
		<p class="page-description">
			{localeLoaded ? $_('Configure an assistant that can use multiple tools to gather context before responding.') : 'Configure an assistant that can use multiple tools to gather context before responding.'}
		</p>
	</div>

	<div class="form-container">
		<MultiToolAssistantForm on:success={handleSuccess} />
	</div>
</div>

<style>
	.create-page {
		max-width: 1200px;
		margin: 0 auto;
		padding: 2rem;
	}

	.page-header {
		margin-bottom: 2rem;
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

	.page-header h1 {
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

	.form-container {
		background: white;
		border: 1px solid #dee2e6;
		border-radius: 8px;
		box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
	}

	@media (max-width: 768px) {
		.create-page {
			padding: 1rem;
		}

		.page-header h1 {
			font-size: 2rem;
		}
	}
</style>