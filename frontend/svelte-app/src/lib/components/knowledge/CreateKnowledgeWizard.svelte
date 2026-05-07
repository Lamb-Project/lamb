<!--
  @component CreateKnowledgeWizard
  Top-level shell for the unified Library + Knowledge Store creation wizard.

  5-step state machine:
    Step 1: Library setup (StepLibrarySetup)        — always shown
    Step 2: Library content (StepLibraryContent)    — skipped if libraryPath === 'existing'
    Step 3: KS setup (StepKSSetup)                  — always shown
    Step 4: KS content (StepKSContent)              — skippable
    Step 5: Review & create (StepReviewCreate)      — always shown
    Step 6: Done (StepDone)                         — post-create success; not counted in progress

  All DB-writing actions live in Step 5 — Steps 1-4 only collect state.
  Draft persistence: saves to sessionStorage on every state change, restored
  only on explicit user click of "Resume".

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
	import ConfirmationModal from '$lib/components/modals/ConfirmationModal.svelte';

	import StepLibrarySetup from './wizard/StepLibrarySetup.svelte';
	import StepLibraryContent from './wizard/StepLibraryContent.svelte';
	import StepKSSetup from './wizard/StepKSSetup.svelte';
	import StepKSContent from './wizard/StepKSContent.svelte';
	import StepReviewCreate from './wizard/Step8_ReviewCreate.svelte';
	import StepDone from './wizard/Step9_Done.svelte';

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
		libraryImportConfig: { pluginName: 'simple_import', params: {} },
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
		createdRefs: { libraryId: '', libraryName: '', ksId: '', ksName: '' }
	};

	// ── Step indices (internal, 1-based for display) ────────────────────────
	// Internal step numbers: 1=LibrarySetup, 2=LibraryContent, 3=KSSetup,
	//                        4=KSContent, 5=ReviewCreate, 6=Done
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
	let showCancelConfirm = $state(false);
	// Bumped whenever wizardState is replaced wholesale (e.g. resumeDraft).
	// Step components re-mount on bump so their locally-cached form fields
	// pick up the new values.
	let wizardStateVersion = $state(0);

	onMount(() => {
		const draft = getDraft(userId, DRAFT_KIND);
		if (draft) {
			// Existing draft: show banner, don't apply initialState (draft wins).
			draftBannerVisible = true;
			draftSavedAt = draft.savedAt || '';
		} else if (initialState && typeof initialState === 'object') {
			// No draft: shallow-merge caller-supplied initial state into defaults.
			wizardState = { ...wizardState, ...initialState };
		}
	});

	// Auto-save on any state change (debounced inside saveDraft).
	// Skip the very first run: that one fires synchronously on mount with
	// the freshly-cloned defaults, and saving then would stomp any existing
	// sessionStorage draft with defaults BEFORE onMount has had a chance
	// to surface the resume banner. Every later run reflects something the
	// user (or resumeDraft) actually changed, so it's free to save.
	let initialSaveSkipped = false;
	$effect(() => {
		const _snap = JSON.stringify(wizardState);
		void _snap;
		if (!initialSaveSkipped) {
			initialSaveSkipped = true;
			return;
		}
		saveDraft(userId, DRAFT_KIND, wizardState);
	});

	function resumeDraft() {
		const draft = getDraft(userId, DRAFT_KIND);
		if (!draft?.state) return;
		// File objects cannot be stored in sessionStorage; pendingFiles will be [].
		wizardState = {
			...structuredClone(defaultWizardState),
			...draft.state,
			pendingFiles: []
		};
		// Force the active step component to re-mount so its locally-cached
		// $state form fields re-initialise from the resumed wizardState.
		wizardStateVersion += 1;
		draftBannerVisible = false;
	}

	function discardDraft() {
		clearDraft(userId, DRAFT_KIND);
		draftBannerVisible = false;
	}

	// ── Step skip logic ──────────────────────────────────────────────────────
	/**
	 * @param {number} step
	 * @returns {boolean}
	 */
	function isStepSkipped(step) {
		if (step === STEP_LIBRARY_CONTENT && wizardState.libraryPath === 'existing') {
			return true;
		}
		if (step === STEP_KS_CONTENT) {
			// Skip only when there is genuinely nothing to pick: new library with
			// no queued content. (Existing-library + zero accessible items is also
			// a candidate, but StepKSContent already shows an empty-state hint —
			// no need to skip a step that is informationally useful.)
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

	// ── Visible step number for progress ────────────────────────────────────
	// totalVisibleSteps is derived so skipping Step 4 reduces the count.
	let totalVisibleSteps = $derived.by(() => {
		let n = 0;
		for (let i = STEP_LIBRARY_SETUP; i <= STEP_REVIEW; i++) {
			if (!isStepSkipped(i)) n++;
		}
		return n;
	});

	let visibleStepNumber = $derived.by(() => {
		if (currentStep > STEP_REVIEW) return totalVisibleSteps;
		let n = 0;
		for (let i = STEP_LIBRARY_SETUP; i <= currentStep; i++) {
			if (!isStepSkipped(i) && i <= STEP_REVIEW) n++;
		}
		return n;
	});

	// ── Step titles ──────────────────────────────────────────────────────────
	/** @type {Record<number, () => string>} */
	const stepTitles = {
		[STEP_LIBRARY_SETUP]: () =>
			$_('knowledge.wizard.libraryStep.title', { default: 'Library Setup' }),
		[STEP_LIBRARY_CONTENT]: () =>
			$_('knowledge.wizard.libraryContent.title', { default: 'Library Content' }),
		[STEP_KS_SETUP]: () =>
			$_('knowledge.wizard.ksStep.title', { default: 'Knowledge Store Setup' }),
		[STEP_KS_CONTENT]: () =>
			$_('knowledge.wizard.step7.title', { default: 'Pick Items to Ingest' }),
		[STEP_REVIEW]: () => $_('knowledge.wizard.step8.title', { default: 'Review & Create' }),
		[STEP_DONE]: () => $_('knowledge.wizard.step9.title', { default: 'Done' })
	};
	let stepLabel = $derived((stepTitles[currentStep] || (() => ''))());

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
		// Skipping Step 4 (KS content) means "ingest nothing into the
		// Knowledge Store right now — the library will still receive every
		// queued item, the user can ingest them later from the KS detail
		// page". So we clear the selection before advancing. Clicking Next
		// instead keeps whatever the user picked.
		if (currentStep === STEP_KS_CONTENT) {
			wizardState.selectedItemIds = [];
			currentStep = nextStep(currentStep);
			canAdvance = true;
			return;
		}
		// Step 2 (library content) was previously skippable too; keep this
		// branch as a safety net even though isSkippableStep no longer
		// surfaces the Skip button there.
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

	function handleCancelClick() {
		// Show save-as-draft prompt.
		showCancelConfirm = true;
	}

	function handleCancelSave() {
		// Already saved by the reactive effect; just close.
		showCancelConfirm = false;
		close();
	}

	function handleCancelDiscard() {
		showCancelConfirm = false;
		clearDraft(userId, DRAFT_KIND);
		close();
	}

	function handleBackdropClick() {
		// Outside-click: save silently (draft already persisted by reactive effect).
		close();
	}

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

	let isLastInteractiveStep = $derived(currentStep === STEP_REVIEW);
	let isDoneStep = $derived(currentStep === STEP_DONE);
	// Only Step 4 (KS content picker) keeps an explicit Skip button — the
	// optionality of Step 2 (Library content) is now spelled out by the inline
	// hint card inside StepLibraryContent, and the Next button works fine
	// with an empty queue, so a separate Skip would be redundant noise.
	let isSkippableStep = $derived(currentStep === STEP_KS_CONTENT);

	// Bind to the Review step so the wizard footer can host a Create button
	// that aligns with Back/Skip instead of getting pushed below the
	// dialog's scroll area inside Step 5's content.
	/** @type {{ submit: () => void } | null} */
	let reviewStepRef = $state(null);
	let reviewSubmitting = $state(false);
</script>

<!-- Esc handling moved to parent — see /libraries/+page.svelte. -->

<!-- Cancel / Save-as-draft modal -->
<ConfirmationModal
	bind:isOpen={showCancelConfirm}
	variant="info"
	title={$_('knowledge.wizard.draft.savePrompt.title', { default: 'Save as draft?' })}
	message={$_('knowledge.wizard.draft.savePrompt.body', {
		default: 'Your progress will be saved until you log out or close the tab.'
	})}
	confirmText={$_('knowledge.wizard.draft.savePrompt.save', { default: 'Save draft' })}
	cancelText={$_('knowledge.wizard.draft.discard', { default: 'Discard' })}
	onconfirm={handleCancelSave}
	oncancel={handleCancelDiscard}
/>

<div
	class="fixed inset-0 z-50 flex items-start justify-center bg-black/50 pt-8 sm:pt-12"
	role="dialog"
	aria-modal="true"
	aria-labelledby="create-knowledge-wizard-title"
	tabindex="-1"
	onclick={handleBackdropClick}
	onkeydown={handleKeydown}
>
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="mx-4 flex max-h-[92vh] w-full max-w-3xl flex-col rounded-lg bg-white shadow-xl"
		onclick={stopPropagation}
	>
		<header class="border-b border-gray-200 px-6 py-4">
			<!-- Draft banner -->
			{#if draftBannerVisible}
				<div
					class="mb-3 flex items-center justify-between gap-2 rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-800"
					role="status"
				>
					<span>
						{$_('knowledge.wizard.draft.banner', {
							default: 'You have an unfinished draft from {time}.',
							values: { time: formatDraftAge(draftSavedAt) }
						})}
					</span>
					<div class="flex items-center gap-2">
						<button
							type="button"
							onclick={resumeDraft}
							class="font-medium underline hover:no-underline"
						>
							{$_('knowledge.wizard.draft.resume', { default: 'Resume' })}
						</button>
						<button type="button" onclick={discardDraft} class="text-blue-600 hover:text-blue-800">
							{$_('knowledge.wizard.draft.discard', { default: 'Discard' })}
						</button>
					</div>
				</div>
			{/if}

			<div class="flex items-center justify-between">
				<h2 id="create-knowledge-wizard-title" class="text-lg font-semibold text-gray-900">
					{$_('knowledge.wizard.title', { default: 'Create Knowledge' })}
				</h2>
				<button
					type="button"
					onclick={handleCancelClick}
					class="px-2 text-xl leading-none text-gray-400 hover:text-gray-600"
					aria-label={$_('common.close', { default: 'Close' })}
				>
					&times;
				</button>
			</div>
			{#if !isDoneStep}
				<div class="mt-2 flex items-center gap-3 text-sm text-gray-600" aria-live="polite">
					<span class="font-medium text-[#2271b3]">
						{$_('knowledge.wizard.stepProgress', {
							default: 'Step {n} of {total}',
							values: { n: visibleStepNumber, total: totalVisibleSteps }
						})}
					</span>
					<span class="text-gray-300">|</span>
					<span>{stepLabel}</span>
				</div>
				<div class="mt-2 h-1 w-full overflow-hidden rounded-full bg-gray-100" aria-hidden="true">
					<div
						class="h-full bg-[#2271b3] transition-all"
						style="width: {(visibleStepNumber / totalVisibleSteps) * 100}%"
					></div>
				</div>
			{/if}
		</header>

		<div class="min-h-[480px] flex-1 overflow-y-auto px-6 py-5">
			<!-- Step components seed their local form fields from wizardState
			     on mount only. When resumeDraft swaps wizardState wholesale,
			     bump wizardStateVersion to force the active step to re-mount
			     so it picks up the resumed values. -->
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
				<StepKSSetup {wizardState} on:update={handleStateUpdate} on:validity={handleStepValidity} />
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
				/>
			{:else if currentStep === STEP_DONE}
				<StepDone {wizardState} on:done={handleDone} on:createAnother={handleCreateAnother} />
			{/if}
			{/key}
		</div>

		<footer class="flex items-center justify-between gap-2 border-t border-gray-200 px-6 py-4">
			<button
				type="button"
				onclick={goBack}
				disabled={currentStep === STEP_LIBRARY_SETUP || isDoneStep}
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

				{#if isLastInteractiveStep && !isDoneStep}
					<button
						type="button"
						onclick={() => reviewStepRef?.submit()}
						disabled={reviewSubmitting}
						class="inline-flex items-center gap-2 rounded-md bg-[#2271b3] px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-[#195a91] disabled:cursor-not-allowed disabled:opacity-50"
					>
						{#if reviewSubmitting}
							<svg class="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
								<circle
									class="opacity-25"
									cx="12"
									cy="12"
									r="10"
									stroke="currentColor"
									stroke-width="4"
								/>
								<path
									class="opacity-75"
									fill="currentColor"
									d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
								/>
							</svg>
						{/if}
						{reviewSubmitting
							? $_('knowledge.wizard.creating', { default: 'Creating...' })
							: $_('knowledge.wizard.step8.submit', { default: 'Create' })}
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
