<!--
  @component CreateKnowledgeWizard
  Top-level shell for the unified Library + Knowledge Store creation wizard.

  State machine:
    Step 0: Library path (existing/new)
    Step 1: Library details                (skipped if existing library)
    Step 2: Library import config           (skipped if existing library)
    Step 3: Library content (optional)      (skipped if existing library; otherwise skippable)
    Step 4: Knowledge Store path
    Step 5: KS details                      (skipped if existing KS)
    Step 6: KS config (locked at create)    (skipped if existing KS)
    Step 7: Pick items to ingest (optional)
    Step 8: Review & create
    Step 9: Done

  All DB-writing actions live in Step 8 — Steps 1-7 only collect state.
  Step 3 holds File objects in memory until Step 8 actually creates the
  library and uploads them. This keeps the wizard fully reversible until
  the user clicks "Create".

  Bind via `bind:isOpen`. Emits 'done' when the user finishes.
-->
<script>
	import { createEventDispatcher } from 'svelte';
	import { _ } from '$lib/i18n';

	import Step0 from './wizard/Step0_LibraryPath.svelte';
	import Step1 from './wizard/Step1_LibraryDetails.svelte';
	import Step2 from './wizard/Step2_LibraryConfig.svelte';
	import Step3 from './wizard/Step3_LibraryContent.svelte';
	import Step4 from './wizard/Step4_KSPath.svelte';
	import Step5 from './wizard/Step5_KSDetails.svelte';
	import Step6 from './wizard/Step6_KSConfig.svelte';
	import Step7 from './wizard/Step7_PickItems.svelte';
	import Step8 from './wizard/Step8_ReviewCreate.svelte';
	import Step9 from './wizard/Step9_Done.svelte';

	const dispatch = createEventDispatcher();

	/** @type {{ onclose?: () => void }} */
	let { onclose = () => {} } = $props();

	/**
	 * @typedef {Object} WizardState
	 * @property {'existing'|'new'} libraryPath
	 * @property {string} existingLibraryId
	 * @property {string} libraryName
	 * @property {string} libraryDescription
	 * @property {boolean} libraryIsShared
	 * @property {{ pluginName: string, params: Object }} libraryImportConfig
	 * @property {File[]} pendingFiles
	 * @property {Array<{ id: string, title: string }>} uploadedItems
	 * @property {'existing'|'new'} ksPath
	 * @property {string} existingKsId
	 * @property {string} ksName
	 * @property {string} ksDescription
	 * @property {boolean} ksIsShared
	 * @property {{ chunking_strategy: string, chunking_params: Object, embedding_vendor: string, embedding_model: string, embedding_endpoint: string, vector_db_backend: string }} ksConfig
	 * @property {string[]} selectedItemIds
	 * @property {{ libraryId: string, libraryName: string, ksId: string, ksName: string }} createdRefs
	 */

	function todayLabel() {
		const d = new Date();
		return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
	}

	/** @type {WizardState} */
	const initialState = {
		libraryPath: 'new',
		existingLibraryId: '',
		libraryName: '',
		libraryDescription: '',
		libraryIsShared: false,
		libraryImportConfig: { pluginName: 'simple_import', params: {} },
		pendingFiles: [],
		uploadedItems: [],
		ksPath: 'new',
		existingKsId: '',
		ksName: '',
		ksDescription: '',
		ksIsShared: false,
		ksConfig: {
			chunking_strategy: '',
			chunking_params: {},
			embedding_vendor: '',
			embedding_model: '',
			embedding_endpoint: '',
			vector_db_backend: ''
		},
		selectedItemIds: [],
		createdRefs: { libraryId: '', libraryName: '', ksId: '', ksName: '' }
	};

	let currentStep = $state(0);
	let wizardState = $state(structuredClone(initialState));

	// Apply auto-suggested defaults at mount (component is mounted only
	// when the parent decides to open it via {#if wizardOpen}).
	if (!wizardState.libraryName) {
		wizardState.libraryName = `My Library ${todayLabel()}`;
	}
	if (!wizardState.ksName) {
		wizardState.ksName = `My Knowledge Store ${todayLabel()}`;
	}

	/**
	 * Total displayed steps (10).
	 */
	const TOTAL_STEPS = 10;

	/**
	 * Determine whether a given step number should be skipped given current state.
	 * @param {number} step
	 * @returns {boolean}
	 */
	function isStepSkipped(step) {
		if ((step === 1 || step === 2 || step === 3) && wizardState.libraryPath === 'existing') {
			return true;
		}
		if ((step === 5 || step === 6) && wizardState.ksPath === 'existing') {
			return true;
		}
		return false;
	}

	/**
	 * Compute next step index (skipping irrelevant steps).
	 * @param {number} from
	 * @returns {number}
	 */
	function nextStep(from) {
		let s = from + 1;
		while (s < TOTAL_STEPS && isStepSkipped(s)) {
			s += 1;
		}
		return Math.min(s, TOTAL_STEPS - 1);
	}

	/**
	 * Compute previous step index (skipping irrelevant steps).
	 * @param {number} from
	 * @returns {number}
	 */
	function prevStep(from) {
		let s = from - 1;
		while (s > 0 && isStepSkipped(s)) {
			s -= 1;
		}
		return Math.max(s, 0);
	}

	let canAdvance = $state(true);

	function handleStepValidity(event) {
		canAdvance = !!event.detail?.valid;
	}

	function handleStateUpdate(event) {
		const patch = event.detail || {};
		// Skip no-op updates so that an effect inside a step component that
		// dispatches the same value on every run doesn't loop forever via
		// wizardState mutation -> step prop change -> step effect re-run.
		// Compares by JSON for object/array values to handle freshly-built
		// patch objects whose contents are unchanged.
		let changed = false;
		for (const key of Object.keys(patch)) {
			const a = wizardState[key];
			const b = patch[key];
			if (a === b) continue;
			if (typeof a === 'object' && typeof b === 'object' && a !== null && b !== null) {
				try {
					if (JSON.stringify(a) === JSON.stringify(b)) continue;
				} catch {
					/* fallthrough */
				}
			}
			changed = true;
			break;
		}
		if (!changed) return;
		wizardState = { ...wizardState, ...patch };
	}

	function goNext() {
		if (currentStep === TOTAL_STEPS - 1) {
			close();
			return;
		}
		currentStep = nextStep(currentStep);
		canAdvance = true;
	}

	function goBack() {
		if (currentStep === 0) return;
		currentStep = prevStep(currentStep);
		canAdvance = true;
	}

	function goSkip() {
		// Step 3 and Step 7 are skippable.
		if (currentStep === 3 || currentStep === 7) {
			currentStep = nextStep(currentStep);
			canAdvance = true;
		}
	}

	function handleCreated(event) {
		const refs = event.detail || {};
		wizardState.createdRefs = {
			libraryId: refs.libraryId || wizardState.createdRefs.libraryId,
			libraryName: refs.libraryName || wizardState.createdRefs.libraryName,
			ksId: refs.ksId || wizardState.createdRefs.ksId,
			ksName: refs.ksName || wizardState.createdRefs.ksName
		};
		currentStep = 9;
	}

	function handleDone(event) {
		dispatch('done', event.detail || wizardState.createdRefs);
		close();
	}

	function handleCreateAnother() {
		wizardState = structuredClone(initialState);
		wizardState.libraryName = `My Library ${todayLabel()}`;
		wizardState.ksName = `My Knowledge Store ${todayLabel()}`;
		currentStep = 0;
		canAdvance = true;
	}

	function close() {
		onclose();
		dispatch('close');
	}

	function handleBackdropClick() {
		close();
	}

	function stopPropagation(event) {
		event.stopPropagation();
	}

	const stepTitles = [
		$_('knowledge.wizard.step0.title', { default: 'Choose Library' }),
		$_('knowledge.wizard.step1.title', { default: 'Library Details' }),
		$_('knowledge.wizard.step2.title', { default: 'Library Import Config' }),
		$_('knowledge.wizard.step3.title', { default: 'Initial Content' }),
		$_('knowledge.wizard.step4.title', { default: 'Choose Knowledge Store' }),
		$_('knowledge.wizard.step5.title', { default: 'Knowledge Store Details' }),
		$_('knowledge.wizard.step6.title', { default: 'Knowledge Store Configuration' }),
		$_('knowledge.wizard.step7.title', { default: 'Pick Items' }),
		$_('knowledge.wizard.step8.title', { default: 'Review & Create' }),
		$_('knowledge.wizard.step9.title', { default: 'Done' })
	];

	let stepLabel = $derived(stepTitles[currentStep] || '');
	let visibleStepNumber = $derived.by(() => {
		let n = 0;
		for (let i = 0; i <= currentStep; i += 1) {
			if (!isStepSkipped(i)) n += 1;
		}
		return n;
	});
	let visibleStepTotal = $derived.by(() => {
		let n = 0;
		for (let i = 0; i < TOTAL_STEPS; i += 1) {
			if (!isStepSkipped(i)) n += 1;
		}
		return n;
	});

	let isLastInteractiveStep = $derived(currentStep === 8);
	let isDoneStep = $derived(currentStep === 9);
	let isSkippableStep = $derived(currentStep === 3 || currentStep === 7);
</script>

<!-- Esc handling moved to parent — see /libraries/+page.svelte. -->

<div
	class="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
	role="dialog"
	aria-modal="true"
	aria-labelledby="create-knowledge-wizard-title"
	onclick={handleBackdropClick}
>
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="mx-4 flex max-h-[92vh] w-full max-w-3xl flex-col rounded-lg bg-white shadow-xl"
		onclick={stopPropagation}
	>
		<header class="border-b border-gray-200 px-6 py-4">
			<div class="flex items-center justify-between">
				<h2 id="create-knowledge-wizard-title" class="text-lg font-semibold text-gray-900">
					{$_('knowledge.wizard.title', { default: 'Create Knowledge' })}
				</h2>
				<button
					type="button"
					onclick={close}
					class="px-2 text-xl leading-none text-gray-400 hover:text-gray-600"
					aria-label={$_('common.close', { default: 'Close' })}
				>
					&times;
				</button>
			</div>
			<div class="mt-2 flex items-center gap-3 text-sm text-gray-600" aria-live="polite">
				<span class="font-medium text-[#2271b3]">
					{$_('knowledge.wizard.stepProgress', {
						default: 'Step {n} of {total}',
						values: { n: visibleStepNumber, total: visibleStepTotal }
					})}
				</span>
				<span class="text-gray-300">|</span>
				<span>{stepLabel}</span>
			</div>
			<div class="mt-2 h-1 w-full overflow-hidden rounded-full bg-gray-100" aria-hidden="true">
				<div
					class="h-full bg-[#2271b3] transition-all"
					style="width: {(visibleStepNumber / visibleStepTotal) * 100}%"
				></div>
			</div>
		</header>

		<div class="flex-1 overflow-y-auto px-6 py-5">
			{#if currentStep === 0}
				<Step0 {wizardState} on:update={handleStateUpdate} on:validity={handleStepValidity} />
			{:else if currentStep === 1}
				<Step1 {wizardState} on:update={handleStateUpdate} on:validity={handleStepValidity} />
			{:else if currentStep === 2}
				<Step2 {wizardState} on:update={handleStateUpdate} on:validity={handleStepValidity} />
			{:else if currentStep === 3}
				<Step3 {wizardState} on:update={handleStateUpdate} on:validity={handleStepValidity} />
			{:else if currentStep === 4}
				<Step4 {wizardState} on:update={handleStateUpdate} on:validity={handleStepValidity} />
			{:else if currentStep === 5}
				<Step5 {wizardState} on:update={handleStateUpdate} on:validity={handleStepValidity} />
			{:else if currentStep === 6}
				<Step6 {wizardState} on:update={handleStateUpdate} on:validity={handleStepValidity} />
			{:else if currentStep === 7}
				<Step7 {wizardState} on:update={handleStateUpdate} on:validity={handleStepValidity} />
			{:else if currentStep === 8}
				<Step8
					{wizardState}
					on:update={handleStateUpdate}
					on:validity={handleStepValidity}
					on:created={handleCreated}
				/>
			{:else if currentStep === 9}
				<Step9 {wizardState} on:done={handleDone} on:createAnother={handleCreateAnother} />
			{/if}
		</div>

		<footer class="flex items-center justify-between gap-2 border-t border-gray-200 px-6 py-4">
			<button
				type="button"
				onclick={goBack}
				disabled={currentStep === 0 || isDoneStep}
				class="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
			>
				{$_('knowledge.wizard.back', { default: 'Back' })}
			</button>

			<div class="flex items-center gap-2">
				{#if isSkippableStep}
					<button
						type="button"
						onclick={goSkip}
						class="px-4 py-2 text-sm font-medium text-[#2271b3] hover:underline"
					>
						{$_('knowledge.wizard.skip', { default: 'Skip' })}
					</button>
				{/if}

				{#if !isLastInteractiveStep && !isDoneStep}
					<button
						type="button"
						onclick={goNext}
						disabled={!canAdvance}
						class="rounded-md bg-[#2271b3] px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-[#195a91] disabled:opacity-50"
					>
						{$_('knowledge.wizard.next', { default: 'Next' })}
					</button>
				{/if}

				{#if isDoneStep}
					<button
						type="button"
						onclick={close}
						class="rounded-md bg-[#2271b3] px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-[#195a91]"
					>
						{$_('common.close', { default: 'Close' })}
					</button>
				{/if}
			</div>
		</footer>
	</div>
</div>
