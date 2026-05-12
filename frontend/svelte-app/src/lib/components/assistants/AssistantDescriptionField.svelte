<!-- src/lib/components/assistants/AssistantDescriptionField.svelte -->
<script>
	import { _ } from '$lib/i18n';
	import { getAuthToken } from './assistantFormUtils.svelte.js';

	let {
		value = $bindable(''),
		/** @type {{ name: string, system_prompt: string, prompt_template: string, connector: string, llm: string, rag_processor: string }} */
		generationContext = {},
		onchange
	} = $props();

	let generatingDescription = $state(false);

	async function handleGenerateDescription() {
		if (!generationContext.name?.trim()) {
			alert(
				$_('assistants.form.description.nameRequired', {
					default: 'Please provide an assistant name first'
				})
			);
			return;
		}
		const token = getAuthToken();
		if (!token) {
			alert(
				$_('assistants.form.description.authError', {
					default: 'Authentication error. Please try logging in again.'
				})
			);
			return;
		}
		generatingDescription = true;
		try {
			const lambServerUrl = window.LAMB_CONFIG?.api?.lambServer;
			if (!lambServerUrl) {
				throw new Error('LAMB server URL not configured in window.LAMB_CONFIG.api.lambServer');
			}
			const controller = new AbortController();
			const timeoutId = setTimeout(() => controller.abort(), 15000);
			const apiUrl = `${lambServerUrl.replace(/\/$/, '')}/creator/assistant/generate_assistant_description`;
			const response = await fetch(apiUrl, {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					Authorization: `Bearer ${token}`
				},
				body: JSON.stringify({
					name: generationContext.name,
					instructions: generationContext.system_prompt || '',
					prompt_template: generationContext.prompt_template || '',
					connector: generationContext.connector || '',
					llm: generationContext.llm || '',
					rag_processor: generationContext.rag_processor || ''
				}),
				signal: controller.signal
			});
			clearTimeout(timeoutId);
			if (!response.ok) {
				const errorText = await response.text();
				if (response.status === 403 || response.status === 401) {
					throw new Error(
						`Authentication error (${response.status}): Please try logging in again.`
					);
				}
				throw new Error(`API error: ${response.status} - ${errorText || 'Unknown error'}`);
			}
			const data = await response.json();
			if (data.description) {
				let processedDescription = data.description.trim().replace(/^["']|["']$/g, '');
				if (processedDescription.length > 500) {
					processedDescription = processedDescription.substring(0, 497) + '...';
				}
				value = processedDescription;
			} else {
				throw new Error(data.error || 'Failed to generate description');
			}
		} catch (err) {
			let descriptionError;
			if (err instanceof Error && err.name === 'AbortError') {
				descriptionError = $_('assistants.form.description.timeout', {
					default: 'Request timed out. Please try again.'
				});
			} else {
				descriptionError =
					err instanceof Error
						? err.message
						: $_('assistants.form.description.error', {
								default: 'Failed to generate description'
							});
			}
			alert(descriptionError);
		} finally {
			generatingDescription = false;
		}
	}
</script>

<div>
	<label for="assistant-description" class="block text-sm font-medium text-gray-700">
		{$_('assistants.form.description.label', { default: 'Description' })}
	</label>
	<div class="mt-1 flex rounded-md shadow-sm">
		<textarea
			id="assistant-description"
			name="description"
			bind:value
			oninput={onchange}
			rows="3"
			disabled={false}
			class="flex-1 block w-full px-3 py-2 border border-gray-300 rounded-l-md focus:outline-none focus:ring-brand focus:border-brand sm:text-sm bg-white text-gray-900"
			placeholder={$_('assistants.form.description.placeholder', {
				default: 'A brief summary of the assistant'
			})}
		></textarea>
		<button
			type="button"
			onclick={handleGenerateDescription}
			disabled={generatingDescription}
			class="relative -ml-px inline-flex items-center space-x-2 rounded-r-md border border-gray-300 bg-gray-50 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand disabled:opacity-50 disabled:cursor-not-allowed"
		>
			<span
				>{generatingDescription
					? $_('assistants.form.description.generating', { default: 'Generating...' })
					: $_('assistants.form.description.generateButton', { default: 'Generate' })}</span
			>
		</button>
	</div>
	<p class="mt-1 text-xs text-gray-500">
		{$_('assistants.form.description.help', {
			default: 'Click Generate after filling in name and prompts.'
		})}
	</p>
</div>
