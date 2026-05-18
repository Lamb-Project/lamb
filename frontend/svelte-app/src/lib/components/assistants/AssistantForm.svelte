<!-- src/lib/components/assistants/AssistantForm.svelte -->
<script>
	import { _ } from '$lib/i18n';
	import { assistantConfigStore } from '$lib/stores/assistantConfigStore';
	import { tick } from 'svelte';
	import { get } from 'svelte/store';
	import { createAssistant, updateAssistant } from '$lib/services/assistantService';
	import { extractModelsFromConnectorData, selectModel } from './assistantFormUtils.svelte.js';
	import { isKbBasedRag, isSingleFileRag, isRubricRag } from '$lib/utils/ragProcessorHelpers.js';
	import { validateImportedAssistant } from './importAssistantValidator.js';
	import { createAssistantFormState, resetFormFieldsToDefaults, populateFormFields, revertToInitial, clearRagDependentState, handleFieldChange } from './assistantFormState.svelte.js';
	import { fetchKnowledgeBases, fetchRubricsList, fetchUserFiles } from './assistantFormFetchers.js';
	import AssistantFormHeader from './AssistantFormHeader.svelte';
	import AssistantNameField from './AssistantNameField.svelte';
	import AssistantDescriptionField from './AssistantDescriptionField.svelte';
	import AssistantPromptFields from './AssistantPromptFields.svelte';
	import RubricSelector from './RubricSelector.svelte';
	import ConfigurationPanel from './ConfigurationPanel.svelte';
	import FormActions from './FormActions.svelte';

	// Track mount status so async fetches that resolve after the user
	// navigates away don't write state to a destroyed component. (#352, M13)
	let isMounted = true;
	$effect(() => {
		return () => { isMounted = false; };
	});

	// --- Props ---
	// Use $props for Svelte 5 runes mode
	let {
		assistant = null,
		onFormSuccess = /** @type {(e: { assistantId: number }) => void} */ (() => {}),
		onCancel = /** @type {() => void} */ (() => {})
	} = $props();

	// --- Reactive form state (extracted to hook) ---
	const form = createAssistantFormState();

	// --- Derived values (component-level, depend on store) ---
	let availableModels = $derived.by(() => {
		const data = $assistantConfigStore?.systemCapabilities?.connectors?.[form.selectedConnector];
		return extractModelsFromConnectorData(data);
	});

	// --- Reactive UI Logic ---
	const showRubricSelector = $derived(isRubricRag(form.selectedRagProcessor));

	// --- Fetcher wrappers (bind state + isMounted guard) ---
	async function doFetchKnowledgeBases() {
		if (!isMounted) return;
		await fetchKnowledgeBases(form);
	}

	async function doFetchUserFiles(force = false) {
		if (!isMounted) return;
		await fetchUserFiles(form, { force, assistant });
	}

	async function doFetchRubricsList() {
		if (!isMounted) return;
		await fetchRubricsList(form);
	}

	// --- Store Integration and Initialization ---
	$effect(() => {
		const assistantIdChanged = assistant?.id !== form.initialAssistantData?.id;
		const assistantNullStatusChanged = (assistant === null && form.initialAssistantData !== null) || (assistant !== null && form.initialAssistantData === null);

		// Check if the assistant data content has changed (not just ID)
		const assistantDataChanged = assistant && form.initialAssistantData &&
			(assistant.system_prompt !== form.initialAssistantData.system_prompt ||
				assistant.prompt_template !== form.initialAssistantData.prompt_template ||
				assistant.name !== form.initialAssistantData.name ||
				assistant.description !== form.initialAssistantData.description);

		if (assistantIdChanged || assistantNullStatusChanged || assistantDataChanged) {
			if (assistant) {
				form.initialAssistantData = { ...assistant };
				form.formState = 'edit';
				form.previousAssistantId = assistant.id;
				// Reset dirty state when loading a different assistant
				form.formDirty = false;

				populateFormFields(form, assistant, () => availableModels);
				form.formError = '';
				form.successMessage = '';
			} else {
				form.formState = 'create';
				form.initialAssistantData = null;
				form.previousAssistantId = null;
				form.formDirty = false;
				if (form.configInitialized) {
					resetFormFieldsToDefaults(form, () => availableModels);
				}
			}
		} else {
			// FIX: Prevent unnecessary repopulation that causes field resets
			// Svelte 5's reactivity can cause prop reference changes even when data hasn't changed
			// Only repopulate basic text fields, NOT the configuration dropdowns
			// Configuration dropdowns (connector, llm, rag processor, etc.) should only be
			// populated on initial load or explicit assistant change (handled above)
			if (assistant && !form.formDirty) {
				// The only case where we'd repopulate is on actual ID change (handled above)
			} else if (assistant && form.formDirty) {
				// User has edits, don't overwrite
			}
		}
	});

	// Trigger config load if not yet loaded
	$effect(() => {
		if (!form.configInitialized && !$assistantConfigStore.loading && !$assistantConfigStore.systemCapabilities) {
			assistantConfigStore.loadConfig();
		}
	});

	// React to config becoming available
	$effect(() => {
		const state = $assistantConfigStore;
		if (!state.loading && state.systemCapabilities && state.configDefaults && !form.configInitialized) {
			const capabilities = state.systemCapabilities;

			form.promptProcessors = capabilities.prompt_processors || [];
			form.connectorsList = Object.keys(capabilities.connectors || {});
			form.ragProcessors = capabilities.rag_processors || [];

			form.configInitialized = true;

			if (form.formState === 'create') {
				resetFormFieldsToDefaults(form, () => availableModels);
			} else {
				populateFormFields(form, form.initialAssistantData, () => availableModels);
			}
		}
	});

	// FIX FOR ISSUE #96: Effect to apply pending KB selections when list becomes available
	$effect(() => {
		// Apply pending selections AFTER fetch completes (not just when arrays have items)
		// This handles cases where user has no KBs or KBs were deleted
		if (form.pendingKBSelections !== null && form.kbFetchAttempted && !form.loadingKnowledgeBases) {
			form.selectedKnowledgeBases = form.pendingKBSelections;
			form.pendingKBSelections = null; // Clear pending state
		}
	});

	// Effect to fetch KBs/Files when RAG processor changes
	$effect(() => {
		if ((isKbBasedRag(form.selectedRagProcessor)) && form.configInitialized) {
			// Trigger fetch only if we land on simple_rag, context_aware_rag, or hierarchical_rag and haven't attempted the fetch yet
			if (!form.kbFetchAttempted && !form.loadingKnowledgeBases) { // Check attempted flag, ignore error here
				doFetchKnowledgeBases();
			} else {
				// Already attempted or loading
			}
		} else if (isSingleFileRag(form.selectedRagProcessor) && form.configInitialized) {
			// Fetch files when switching to single_file_rag
			if (!form.filesFetchAttempted && !form.loadingFiles) {
				doFetchUserFiles();
			}
		} else if (isRubricRag(form.selectedRagProcessor) && form.configInitialized) {
			if (!form.rubricsFetchAttempted && !form.loadingRubrics) {
				tick().then(doFetchRubricsList);
			}
		} else {
			// Clear KB state AND reset attempted flag if RAG processor changes away
			clearRagDependentState(form);
		}
	});

	// --- Mode Switching Functions ---
	function switchToViewMode() {
		// Revert fields to initial state
		revertToInitial(form, () => availableModels);
		onCancel();
	}

	// --- Event Handlers ---

	/**
	 * @typedef {import('$lib/services/knowledgeBaseService').KnowledgeBase} KnowledgeBase
	 */

	/**
	 * @typedef {Object} AssistantResponse - Defines the structure of an assistant object from API
	 * @property {number} id
	 * @property {string} name
	 * @property {string} [description]
	 * // Add other expected fields from the createAssistant/updateAssistant response if known
	 */

	/**
	 * Handles form submission (Create or Update).
	 * @param {Event} event - The form submission event.
	 */
	async function handleSubmit(event) {
		event.preventDefault();
		form.formError = '';
		form.successMessage = '';
		form.formLoading = true;

		if (!form.name?.trim()) {
			form.formError = 'Assistant Name is required.';
			form.formLoading = false;
			return;
		}

		// Validate rubric selection if rubric_rag is selected
		if (isRubricRag(form.selectedRagProcessor) && !form.selectedRubricId) {
			form.formError = 'Please select a rubric when using Rubric RAG.';
			form.formLoading = false;
			return;
		}

		// In non-advanced mode, ensure defaults are used
		if (form.formState === 'create' && !form.isAdvancedMode) {
			const defaults = get(assistantConfigStore).configDefaults?.config || {};
			form.selectedPromptProcessor = defaults.prompt_processor || (form.promptProcessors.length > 0 ? form.promptProcessors[0] : '');
			form.selectedConnector = defaults.connector || (form.connectorsList.length > 0 ? form.connectorsList[0] : '');
			await tick();
			// Reset LLM if needed with the new models list
			if (!availableModels.includes(form.selectedLlm)) {
				form.selectedLlm = defaults.llm || (availableModels.length > 0 ? availableModels[0] : '');
			}
		}

		// Construct the data for the metadata field
		/** @type {Record<string, any>} */
		const metadataObj = {
			prompt_processor: form.selectedPromptProcessor,
			connector: form.selectedConnector,
			llm: form.selectedLlm,
			rag_processor: form.selectedRagProcessor,
			file_path: isSingleFileRag(form.selectedRagProcessor) ? form.selectedFilePath : '',
			capabilities: {
				vision: form.visionEnabled,
				image_generation: form.imageGenerationEnabled
			}
		};

		// Add rubric fields if rubric_rag is selected
		if (isRubricRag(form.selectedRagProcessor)) {
			metadataObj.rubric_id = form.selectedRubricId;
			metadataObj.rubric_format = form.rubricFormat;
		}

		// Construct payload according to the expected API structure
		const assistantDataPayload = {
			name: form.name.trim(),
			description: form.description,
			system_prompt: form.system_prompt,
			prompt_template: form.prompt_template,
			RAG_Top_k: Number(form.RAG_Top_k) || 3,
			RAG_collections: (isKbBasedRag(form.selectedRagProcessor)) ? form.selectedKnowledgeBases.join(',') : '',
			// Add metadata with the stringified JSON
			metadata: JSON.stringify(metadataObj),
			pre_retrieval_endpoint: '',
			post_retrieval_endpoint: '',
			RAG_endpoint: ''
		};

		try {
			if (form.formState === 'edit' && form.initialAssistantData?.id) { // Check formState and ID from initial data
				await updateAssistant(form.initialAssistantData.id.toString(), assistantDataPayload); // Ensure ID is string
				form.successMessage = 'Assistant updated successfully!';
				// Reset dirty state after successful save
				form.formDirty = false;

				// and stay in edit mode. The parent page handles list refresh via the event.
				// Preserve the original metadata structure (object) instead of using the payload's stringified version
				form.initialAssistantData = {
					...form.initialAssistantData,
					...assistantDataPayload,
					metadata: metadataObj // Use the parsed metadata object, not the stringified version
				};
				populateFormFields(form, form.initialAssistantData, () => availableModels); // Update form with potentially modified response data
				onFormSuccess({ assistantId: form.initialAssistantData.id });
			} else if (form.formState === 'create') {
				// Handle create case here
				const createResponse = await createAssistant(assistantDataPayload);
				if (!createResponse?.assistant_id) {
					throw new Error('Create assistant response did not include an assistant_id.');
				}
				form.successMessage = 'Assistant created successfully!';
				// Reset dirty state after successful create
				form.formDirty = false;

				onFormSuccess({ assistantId: createResponse.assistant_id });
			} else {
				throw new Error('Invalid form state for submission.');
			}
		} catch (error) {
			console.error(`Error ${form.formState === 'edit' ? 'updating' : 'creating'} assistant:`, error);
			form.formError = error instanceof Error ? error.message : `Failed to ${form.formState === 'edit' ? 'update' : 'create'} assistant`;
			form.successMessage = ''; // Clear success on error
		} finally {
			form.formLoading = false;
		}
	}

	// --- Import Functionality ---

	/**
	 * Handles file selection for import.
	 * @param {Event} event
	 */
	function handleFileSelect(event) {
		const inputElement = /** @type {HTMLInputElement} */ (event.target);
		const files = inputElement.files;
		form.importError = ''; // Clear previous import errors
		let validationLog = ['Starting validation...'];

		if (files && files.length > 0) {
			const file = files[0];

			if (file.type !== 'application/json' && !file.name.toLowerCase().endsWith('.json')) {
				form.importError = $_('assistants.form.import.invalidFile', { default: 'Invalid file type. Please select a .json file.' });
				console.error(form.importError);
				inputElement.value = ''; // Clear the input
				return;
			}

			const reader = new FileReader();

			reader.onload = async (e) => {
				const content = e.target?.result;
				if (typeof content === 'string') {

					const storeState = get(assistantConfigStore);
					const capabilities = storeState.systemCapabilities;
					const { parsedData, callbackData, validationLog, hasErrors } = validateImportedAssistant(
						content, capabilities, extractModelsFromConnectorData
					);

					// --- Validation Summary ---

					if (!hasErrors && parsedData && callbackData) {
						try {
							validationLog.push('ℹ️ Populating form fields...');

							// Populate basic fields
							form.name = parsedData.name || ''; // Keep original name for now, user can change
							form.description = parsedData.description || '';
							form.system_prompt = parsedData.system_prompt || '';
							form.prompt_template = parsedData.prompt_template || '';
							form.RAG_Top_k = parsedData.RAG_Top_k ?? 3;

							// Populate selections from metadata
							form.selectedPromptProcessor = callbackData.prompt_processor || (form.promptProcessors.length > 0 ? form.promptProcessors[0] : '');
							form.selectedConnector = callbackData.connector || (form.connectorsList.length > 0 ? form.connectorsList[0] : '');
							form.selectedRagProcessor = callbackData.rag_processor || (form.ragProcessors.length > 0 ? form.ragProcessors[0] : '');

							// Set LLM based on connector
							form.selectedLlm = selectModel(callbackData.llm, availableModels);
							if (callbackData.llm && !availableModels.includes(callbackData.llm)) {
								validationLog.push(`⚠️ Imported LLM '${callbackData.llm}' not available for connector '${form.selectedConnector}'. Defaulting to '${form.selectedLlm}'.`);
							}

						// Populate RAG specific fields
						// FIX FOR ISSUE #96: Apply Load-Then-Select pattern for imports too
						if (isKbBasedRag(form.selectedRagProcessor)) {
							form.selectedFilePath = ''; // Clear file path if switching to simple RAG, context_aware_rag, or hierarchical_rag
							// Fetch KBs BEFORE setting selections
							if (!form.kbFetchAttempted) {
								await doFetchKnowledgeBases(); // ✅ WAIT for KBs to load
							}
							// NOW set selections when KB list is ready
							form.selectedKnowledgeBases = parsedData.RAG_collections?.split(',').filter(Boolean) || [];
						} else if (isSingleFileRag(form.selectedRagProcessor)) {
							form.selectedKnowledgeBases = []; // Clear KBs if switching to single file RAG
							// Fetch files BEFORE setting selection
							if (!form.filesFetchAttempted) {
								await doFetchUserFiles(); // ✅ WAIT for files to load
							}
							// NOW set selection when file list is ready
							form.selectedFilePath = callbackData.file_path || '';
						} else { // No RAG
							form.selectedKnowledgeBases = [];
							form.selectedFilePath = '';
						}
							validationLog.push('✅ Form fields populated successfully.');
							form.importError = ''; // Clear any previous error
							// Show success message briefly
							form.successMessage = $_('assistants.form.import.success', { default: 'Assistant data imported successfully! Please review and save.' });
							setTimeout(() => { form.successMessage = ''; }, 5000); // Clear success after 5 seconds
						} catch (populationError) {
							validationLog.push(`❌ Error populating form: ${populationError instanceof Error ? populationError.message : 'Unknown population error'}`);
							form.importError = $_('assistants.form.import.populationError', { default: 'Error populating form from imported data. Check console.' });
						}
					} else {
						form.importError = $_('assistants.form.import.validationFailed', { default: 'Import validation failed. Form not populated. Check console for details.' });
					}
				} else {
					console.error('Failed to read file content as string.');
					form.importError = $_('assistants.form.import.readError', { default: 'Could not read file content.' });
					validationLog.push(`❌ ${form.importError}`);
				}
			};

			reader.onerror = (e) => {
				console.error('Error reading file:', e);
				form.importError = $_('assistants.form.import.fileReadError', { default: 'Error reading the selected file.' });
				validationLog.push(`❌ ${form.importError}`);
			};

			reader.readAsText(file);
		}

		// Clear the file input value so the same file can be selected again
		inputElement.value = '';
	}

</script>

	<div class="p-4 md:p-6 border rounded-md shadow-sm bg-white">

	<AssistantFormHeader
		formState={form.formState}
		assistantId={form.initialAssistantData?.id}
		importError={form.importError}
		onImportFile={handleFileSelect}
	/>

	{#if $assistantConfigStore.loading && !form.configInitialized}
		<p class="text-center text-gray-600 py-10">{$_('assistants.loadingConfig', { default: 'Loading configuration...' })}</p>
	{:else if $assistantConfigStore.error}
		<p class="text-center text-red-600 py-10">{$_('assistants.errorConfig', { default: 'Error loading configuration:' })} {$assistantConfigStore.error}</p>
	{:else if !form.configInitialized}
		<p class="text-center text-gray-600 py-10">{$_('assistants.initializingForm', { default: 'Initializing form...' })}</p>
	{:else}
		<!-- Form starts here -->
		<form
			onsubmit={handleSubmit}
			class="space-y-6"
			id="assistant-form-main"
		>
			<div class="flex flex-col md:flex-row md:space-x-6">
				<!-- Left Column: Main Fields -->
				<div class="md:w-2/3 space-y-6">
					<AssistantNameField bind:value={form.name} formState={form.formState} oninput={() => handleFieldChange(form)} />

					<AssistantDescriptionField
						bind:value={form.description}
						generationContext={{
							name: form.name,
							system_prompt: form.system_prompt,
							prompt_template: form.prompt_template,
							connector: form.selectedConnector,
							llm: form.selectedLlm,
							rag_processor: form.selectedRagProcessor
						}}
						oninput={() => handleFieldChange(form)}
					/>

				<AssistantPromptFields
					bind:systemPrompt={form.system_prompt}
					bind:promptTemplate={form.prompt_template}
					ragPlaceholders={form.ragPlaceholders}
					selectedPromptProcessor={form.selectedPromptProcessor}
					formState={form.formState}
					oninput={() => handleFieldChange(form)}
					onTemplateApplied={() => {
						form.formDirty = true;
					}}
				/>

				{#if showRubricSelector}
					<RubricSelector
						rubrics={form.accessibleRubrics}
						loading={form.loadingRubrics}
						error={form.rubricError}
						bind:selectedRubricId={form.selectedRubricId}
						bind:rubricFormat={form.rubricFormat}
					/>
				{/if}
			</div>

			<!-- Right Column: Configuration -->
			<div class="md:w-1/3">
				<ConfigurationPanel
					formState={form.formState}
					{availableModels}
					bind:isAdvancedMode={form.isAdvancedMode}
					promptProcessors={form.promptProcessors}
					connectorsList={form.connectorsList}
					ragProcessors={form.ragProcessors}
					bind:selectedPromptProcessor={form.selectedPromptProcessor}
					bind:selectedConnector={form.selectedConnector}
					bind:selectedLlm={form.selectedLlm}
					bind:selectedRagProcessor={form.selectedRagProcessor}
					bind:visionEnabled={form.visionEnabled}
					bind:imageGenerationEnabled={form.imageGenerationEnabled}
					bind:RAG_Top_k={form.RAG_Top_k}
					ownedKnowledgeBases={form.ownedKnowledgeBases}
					sharedKnowledgeBases={form.sharedKnowledgeBases}
					bind:selectedKnowledgeBases={form.selectedKnowledgeBases}
					loadingKnowledgeBases={form.loadingKnowledgeBases}
					knowledgeBaseError={form.knowledgeBaseError}
					userFiles={form.userFiles}
					bind:selectedFilePath={form.selectedFilePath}
					loadingFiles={form.loadingFiles}
					fileError={form.fileError}
					onFilesChanged={() => doFetchUserFiles(true)}
					onchange={() => handleFieldChange(form)}
				/>
			</div>
			</div>

			<FormActions
				formState={form.formState}
				formLoading={form.formLoading}
				formError={form.formError}
				successMessage={form.successMessage}
				oncancel={switchToViewMode}
			/>

		</form>
	{/if}


</div>
