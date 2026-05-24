<!--
  @component CreateKnowledgeWizard
  Top-level shell for the unified Library + Knowledge Store creation wizard.

  5-step state machine (Step 6 is the post-create Done screen):
    Step 1: Library setup (StepLibrarySetup)        — always shown
    Step 2: Library content (StepLibraryContent)    — skippable when empty
    Step 3: KS setup (StepKSSetup)                  — always shown
    Step 4: KS content (StepKSContent)              — skippable
    Step 5: Review & create (StepReviewCreate)      — always shown
    Step 6: Done (StepDone)                         — post-create success; not counted in progress

  All DB-writing actions live in Step 5 — Steps 1-4 only collect state.
  Draft persistence: saves to sessionStorage on every state change,
  restored only on explicit user click of "Resume".

  Phase C consistency contract:
    * Wraps the canonical `<Modal size="xl">`.
    * Progress uses the canonical `<Stepper>` primitive (same as
      AddContentToKSModal — guarantees visual identity).
    * Draft banner uses `<Banner variant="info">`.
    * Footer is at most 3 buttons: Back (left, ghost) + optional Skip
      (ghost) + primary (Next / Create / Close). The previous "Go to
      start" / "Go to review" text links are gone — clickable Stepper
      circles replace them.

  Bind via `onclose` prop. Emits 'done' when the user finishes.
-->
<script>
	import { createEventDispatcher, onMount } from 'svelte';
	import { _ } from '$lib/i18n';
	import { user } from '$lib/stores/userStore';
	import {
		saveDraft,
		clearDraft,
		getDraft,
		formatDraftAge
	} from '$lib/stores/wizardDraftStore.svelte.js';
	import { saveFiles, getFiles, clearFiles } from '$lib/stores/wizardFileStore.svelte.js';

	import StepLibrarySetup from './wizard/StepLibrarySetup.svelte';
	import StepLibraryContent from './wizard/StepLibraryContent.svelte';
	import StepKSSetup from './wizard/StepKSSetup.svelte';
	import StepKSContent from './wizard/StepKSContent.svelte';
	import StepReviewCreate from './wizard/Step8_ReviewCreate.svelte';
	import StepDone from './wizard/Step9_Done.svelte';

	import { Stepper, Banner, Button } from '$lib/components/ui';

	const dispatch = createEventDispatcher();

	/** @type {{ onclose?: () => void, initialState?: Record<string, any> | null }} */
	let { onclose = () => {}, initialState = null } = $props();

	/**
	 * @typedef {Object} WizardState
	 * @property {'existing'|'new'} libraryPath
	 * @property {string} existingLibraryId
	 * @property {string} libraryName
	 * @property {string} libraryDescription
	 * @property {boolean} libraryIsShared
	 * @property {{ pluginName: string, params: Object }} libraryImportConfig
	 * @property {File[]} pendingFiles
	 * @property {Array<{ type: 'url'|'youtube', url: string, title?: string, language?: string }>} pendingUrlSources
	 * @property {Array<{ id: string, title: string }>} uploadedItems
	 * @property {'existing'|'new'} ksPath
	 * @property {string} existingKsId
	 * @property {string} ksName
	 * @property {string} ksDescription
	 * @property {boolean} ksIsShared
	 * @property {{ chunking_strategy: string, chunking_params: Object, embedding_vendor: string, embedding_model: string, embedding_endpoint: string, vector_db_backend: string }} ksConfig
	 * @property {string[]} selectedItemIds
	 * @property {boolean} selectionInitialized
	 * @property {{ libraryId: string, libraryName: string, ksId: string, ksName: string }} createdRefs
	 */

	function todayLabel() {
		const d = new Date();
		return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
	}

	/** @type {WizardState} */
	const defaultWizardState = {
		libraryPath: 'new',
		existingLibraryId: '',
		libraryName: '',
		libraryDescription: '',
		libraryIsShared: false,
		libraryImportConfig: { pluginName: '', params: {} },
		pendingFiles: [],
		pendingUrlSources: [],
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
		selectionInitialized: false,
		createdRefs: { libraryId: '', libraryName: '', ksId: '', ksName: '' }
	};

	// ── Step indices (internal, 1-based for display) ────────────────────────
	const STEP_LIBRARY_SETUP = 1;
	const STEP_LIBRARY_CONTENT = 2;
	const STEP_KS_SETUP = 3;
	const STEP_KS_CONTENT = 4;
	const STEP_REVIEW = 5;
	const STEP_DONE = 6;

	let currentStep = $state(STEP_LIBRARY_SETUP);
	let wizardState = $state(structuredClone(defaultWizardState));

	if (!wizardState.libraryName) {
		wizardState.libraryName = `My Library ${todayLabel()}`;
	}
	if (!wizardState.ksName) {
		wizardState.ksName = `My Knowledge Store ${todayLabel()}`;
	}

	// ── Draft persistence ────────────────────────────────────────────────────
	let userId = $derived($user?.data?.id || $user?.email || '_anon');
	const DRAFT_KIND = 'createKnowledge';

	let draftBannerVisible = $state(false);
	let draftSavedAt = $state('');
	let wizardStateVersion = $state(0);

	onMount(() => {
		if (initialState && typeof initialState === 'object') {
			wizardState = { ...wizardState, ...initialState };
		}
		const draft = getDraft(userId, DRAFT_KIND);
		if (draft) {
			draftBannerVisible = true;
			draftSavedAt = draft.savedAt || '';
		}
	});

	let initialSaveSkipped = false;
	$effect(() => {
		const _snap = JSON.stringify(wizardState);
		const _step = currentStep;
		void _snap;
		void _step;
		if (!initialSaveSkipped) {
			initialSaveSkipped = true;
			return;
		}
		if (currentStep === STEP_DONE) return;
		saveDraft(userId, DRAFT_KIND, { ...wizardState, __currentStep: currentStep });
		saveFiles(userId, DRAFT_KIND, wizardState.pendingFiles || []);
	});

	async function resumeDraft() {
		const draft = getDraft(userId, DRAFT_KIND);
		if (!draft?.state) return;
		const { __currentStep, ...savedWizardState } = draft.state;
		const restoredFiles = await getFiles(userId, DRAFT_KIND);
		wizardState = {
			...structuredClone(defaultWizardState),
			...savedWizardState,
			pendingFiles: restoredFiles
		};
		if (
			typeof __currentStep === 'number' &&
			__currentStep >= STEP_LIBRARY_SETUP &&
			__currentStep <= STEP_REVIEW
		) {
			let target = __currentStep;
			while (target < STEP_REVIEW && isStepSkipped(target)) target += 1;
			currentStep = target;
		}
		wizardStateVersion += 1;
		draftBannerVisible = false;
	}

	function discardDraft() {
		clearDraft(userId, DRAFT_KIND);
		clearFiles(userId, DRAFT_KIND);
		draftBannerVisible = false;
		if (initialState && typeof initialState === 'object') {
			wizardState = { ...structuredClone(defaultWizardState), ...initialState };
			if (!wizardState.libraryName) {
				wizardState.libraryName = `My Library ${todayLabel()}`;
			}
			if (!wizardState.ksName) {
				wizardState.ksName = `My Knowledge Store ${todayLabel()}`;
			}
			currentStep = STEP_LIBRARY_SETUP;
			wizardStateVersion += 1;
		}
	}

	// ── Step skip logic ──────────────────────────────────────────────────────
	/**
	 * @param {number} step
	 * @returns {boolean}
	 */
	function isStepSkipped(step) {
		if (step === STEP_KS_CONTENT) {
			if (
				wizardState.libraryPath === 'new' &&
				wizardState.pendingFiles.length === 0 &&
				wizardState.pendingUrlSources.length === 0
			) {
				return true;
			}
		}
		return false;
	}

	/** @param {number} from */
	function nextStep(from) {
		let s = from + 1;
		while (s < STEP_DONE && isStepSkipped(s)) s += 1;
		return Math.min(s, STEP_DONE);
	}

	/** @param {number} from */
	function prevStep(from) {
		let s = from - 1;
		while (s > STEP_LIBRARY_SETUP && isStepSkipped(s)) s -= 1;
		return Math.max(s, STEP_LIBRARY_SETUP);
	}

	// ── Visible steps for the Stepper ────────────────────────────────────────
	/**
	 * @typedef {Object} VisibleStep
	 * @property {number} stepIndex  internal step number (STEP_*)
	 * @property {string} key
	 * @property {string} label
	 */

	let visibleSteps = $derived.by(() => {
		/** @type {VisibleStep[]} */
		const out = [];
		const map = [
			{
				stepIndex: STEP_LIBRARY_SETUP,
				key: 'librarySetup',
				label: $_('knowledge.wizard.libraryStep.title', { default: 'Library Setup' })
			},
			{
				stepIndex: STEP_LIBRARY_CONTENT,
				key: 'libraryContent',
				label: $_('knowledge.wizard.libraryContent.title', { default: 'Library Content' })
			},
			{
				stepIndex: STEP_KS_SETUP,
				key: 'ksSetup',
				label: $_('knowledge.wizard.ksStep.title', { default: 'Knowledge Store Setup' })
			},
			{
				stepIndex: STEP_KS_CONTENT,
				key: 'ksContent',
				label: $_('knowledge.wizard.step7.title', { default: 'Pick Items to Ingest' })
			},
			{
				stepIndex: STEP_REVIEW,
				key: 'review',
				label: $_('knowledge.wizard.step8.title', { default: 'Review & Create' })
			}
		];
		for (const item of map) {
			if (!isStepSkipped(item.stepIndex)) out.push(item);
		}
		return out;
	});

	let visibleStepNumber = $derived.by(() => {
		if (currentStep > STEP_REVIEW) return visibleSteps.length;
		const idx = visibleSteps.findIndex((v) => v.stepIndex === currentStep);
		return idx === -1 ? 1 : idx + 1;
	});

	// Completed Stepper keys: every visible step whose stepIndex < currentStep.
	let completedStepKeys = $derived(
		new Set(visibleSteps.filter((v) => v.stepIndex < currentStep).map((v) => v.key))
	);

	/** @param {string} key */
	function jumpToStep(key) {
		const target = visibleSteps.find((v) => v.key === key);
		if (!target) return;
		// Only allow jumping back to already-completed steps. Stepper guards
		// this too but we double-check.
		if (target.stepIndex >= currentStep) return;
		currentStep = target.stepIndex;
		canAdvance = true;
	}

	// ── Validity / navigation ────────────────────────────────────────────────
	let canAdvance = $state(true);

	/** @param {CustomEvent<{valid:boolean}>} event */
	function handleStepValidity(event) {
		canAdvance = !!event.detail?.valid;
	}

	/** @param {CustomEvent<any>} event */
	function handleStateUpdate(event) {
		const patch = /** @type {Record<string, any>} */ (event.detail || {});
		let changed = false;
		for (const key of Object.keys(patch)) {
			const a = /** @type {Record<string, any>} */ (wizardState)[key];
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
		if (currentStep >= STEP_REVIEW) return;
		currentStep = nextStep(currentStep);
		canAdvance = true;
	}

	function goBack() {
		if (currentStep <= STEP_LIBRARY_SETUP) return;
		currentStep = prevStep(currentStep);
		canAdvance = true;
	}

	function goSkip() {
		if (currentStep === STEP_KS_CONTENT) {
			wizardState.selectedItemIds = [];
			currentStep = nextStep(currentStep);
			canAdvance = true;
			return;
		}
		if (currentStep === STEP_LIBRARY_CONTENT) {
			currentStep = nextStep(currentStep);
			canAdvance = true;
		}
	}

	/** @param {CustomEvent<any>} event */
	function handleCreated(event) {
		const refs = event.detail || {};
		wizardState.createdRefs = {
			libraryId: refs.libraryId || wizardState.createdRefs.libraryId,
			libraryName: refs.libraryName || wizardState.createdRefs.libraryName,
			ksId: refs.ksId || wizardState.createdRefs.ksId,
			ksName: refs.ksName || wizardState.createdRefs.ksName
		};
		clearDraft(userId, DRAFT_KIND);
		clearFiles(userId, DRAFT_KIND);
		currentStep = STEP_DONE;
	}

	/** @param {CustomEvent<any>} event */
	function handleDone(event) {
		dispatch('done', event.detail || wizardState.createdRefs);
		close();
	}

	function handleCreateAnother() {
		wizardState = structuredClone(defaultWizardState);
		wizardState.libraryName = `My Library ${todayLabel()}`;
		wizardState.ksName = `My Knowledge Store ${todayLabel()}`;
		currentStep = STEP_LIBRARY_SETUP;
		canAdvance = true;
		discardDraft();
	}

	function close() {
		onclose();
		dispatch('close');
	}

	let isLastInteractiveStep = $derived(currentStep === STEP_REVIEW);
	let isDoneStep = $derived(currentStep === STEP_DONE);
	let isFirstStep = $derived(currentStep === STEP_LIBRARY_SETUP);
	let isSkippableStep = $derived(currentStep === STEP_KS_CONTENT);

	/** @type {{ submit: () => void } | null} */
	let reviewStepRef = $state(null);
	let reviewSubmitting = $state(false);

	/** @param {KeyboardEvent} event */
	function handleKeydown(event) {
		if (event.key === 'Escape') {
			close();
		}
	}

	/** @param {MouseEvent} event */
	function stopPropagation(event) {
		event.stopPropagation();
	}
</script>

<!-- The wizard is rendered as a full-screen overlay with its own backdrop
     rather than the canonical Modal primitive because the wizard owns its
     header (draft banner + Stepper) and a non-trivial footer. The shell
     still follows the canonical look — white panel, rounded-xl, shadow-modal. -->
<div
	class="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-gray-900/40 p-4 pt-8 backdrop-blur-[1px] sm:pt-12"
	role="dialog"
	aria-modal="true"
	aria-labelledby="create-knowledge-wizard-title"
	tabindex="-1"
	onclick={close}
	onkeydown={handleKeydown}
>
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="bg-surface shadow-modal border-border mx-4 mx-auto flex max-h-[92vh] w-full max-w-full flex-col rounded-xl border md:max-w-3xl"
		onclick={stopPropagation}
	>
		<header class="border-border border-b px-6 py-4">
			<div class="flex items-center justify-between gap-3">
				<h2 id="create-knowledge-wizard-title" class="type-section-title min-w-0 flex-1 truncate">
					{#if wizardState.ksPath === 'existing' && wizardState.existingKsId}
						{$_('knowledge.wizard.titleAddContent', { default: 'Add Content' })}
					{:else}
						{$_('knowledge.wizard.title', { default: 'Create Knowledge' })}
					{/if}
				</h2>
				<button
					type="button"
					onclick={close}
					class="text-text-subtle hover:text-text rounded-md p-1 text-xl leading-none transition-colors"
					aria-label={$_('common.close', { default: 'Close' })}
				>
					&times;
				</button>
			</div>

			<!-- Draft banner -->
			{#if draftBannerVisible}
				<div class="mt-3">
					<Banner
						variant="info"
						description={$_('knowledge.wizard.draft.banner', {
							default: 'You have an unfinished draft from {time}.',
							values: { time: formatDraftAge(draftSavedAt) }
						})}
					>
						{#snippet actions()}
							<div class="flex items-center gap-2">
								<Button variant="primary" size="sm" onclick={resumeDraft}>
									{$_('knowledge.wizard.draft.resume', { default: 'Resume' })}
								</Button>
								<Button variant="ghost" size="sm" onclick={discardDraft}>
									{$_('knowledge.wizard.draft.discard', { default: 'Discard' })}
								</Button>
							</div>
						{/snippet}
					</Banner>
				</div>
			{/if}

			<!-- Stepper (same primitive as AddContentToKSModal) -->
			{#if !isDoneStep}
				<div class="mt-3">
					<Stepper
						steps={visibleSteps.map((v) => ({ key: v.key, label: v.label }))}
						current={visibleStepNumber}
						completed={completedStepKeys}
						onJump={jumpToStep}
						mobileCollapsed
					/>
				</div>
			{/if}
		</header>

		<div class="min-h-[480px] flex-1 overflow-y-auto px-6 py-5">
			{#key wizardStateVersion}
				{#if currentStep === STEP_LIBRARY_SETUP}
					<StepLibrarySetup
						{wizardState}
						on:update={handleStateUpdate}
						on:validity={handleStepValidity}
					/>
				{:else if currentStep === STEP_LIBRARY_CONTENT}
					<StepLibraryContent
						{wizardState}
						on:update={handleStateUpdate}
						on:validity={handleStepValidity}
					/>
				{:else if currentStep === STEP_KS_SETUP}
					<StepKSSetup
						{wizardState}
						on:update={handleStateUpdate}
						on:validity={handleStepValidity}
					/>
				{:else if currentStep === STEP_KS_CONTENT}
					<StepKSContent
						{wizardState}
						on:update={handleStateUpdate}
						on:validity={handleStepValidity}
					/>
				{:else if currentStep === STEP_REVIEW}
					<StepReviewCreate
						bind:this={reviewStepRef}
						bind:submitting={reviewSubmitting}
						{wizardState}
						on:update={handleStateUpdate}
						on:validity={handleStepValidity}
						on:created={handleCreated}
						onJumpToStep={(/** @type {number} */ stepIndex) => {
							if (stepIndex >= STEP_LIBRARY_SETUP && stepIndex < STEP_REVIEW) {
								currentStep = stepIndex;
								canAdvance = true;
							}
						}}
					/>
				{:else if currentStep === STEP_DONE}
					<StepDone {wizardState} on:done={handleDone} on:createAnother={handleCreateAnother} />
				{/if}
			{/key}
		</div>

		<footer
			class="border-border bg-surface-muted flex items-center justify-between gap-2 border-t px-6 py-4"
		>
			<Button variant="ghost" onclick={goBack} disabled={isFirstStep || isDoneStep}>
				{$_('knowledge.wizard.back', { default: 'Back' })}
			</Button>

			<div class="flex items-center gap-2">
				{#if isSkippableStep && !isDoneStep}
					<Button variant="ghost" onclick={goSkip}>
						{$_('knowledge.wizard.skip', { default: 'Skip' })}
					</Button>
				{/if}

				{#if !isLastInteractiveStep && !isDoneStep}
					<Button variant="primary" onclick={goNext} disabled={!canAdvance}>
						{$_('knowledge.wizard.next', { default: 'Next' })}
					</Button>
				{/if}

				{#if isLastInteractiveStep && !isDoneStep}
					<Button
						variant="primary"
						onclick={() => reviewStepRef?.submit()}
						loading={reviewSubmitting}
					>
						{#if reviewSubmitting}
							{wizardState.ksPath === 'existing' && wizardState.existingKsId
								? $_('knowledge.wizard.adding', { default: 'Adding...' })
								: $_('knowledge.wizard.creating', { default: 'Creating...' })}
						{:else if wizardState.ksPath === 'existing' && wizardState.existingKsId}
							{$_('knowledge.wizard.step8.submitAdd', { default: 'Add' })}
						{:else}
							{$_('knowledge.wizard.step8.submit', { default: 'Create' })}
						{/if}
					</Button>
				{/if}

				{#if isDoneStep}
					<Button variant="primary" onclick={close}>
						{$_('common.close', { default: 'Close' })}
					</Button>
				{/if}
			</div>
		</footer>
	</div>
</div>
