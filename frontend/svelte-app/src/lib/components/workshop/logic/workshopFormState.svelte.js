// src/lib/components/workshop/logic/workshopFormState.svelte.js
/**
 * Reactive state hook for Workshop 5-step build wizard.
 *
 * Encapsulates the four build steps' state + the reflection step, so it can
 * be unit-tested in isolation (vitest) and persisted per-step.
 *
 * Usage (Svelte 5 runes, `.svelte.js` module):
 *   const form = createWorkshopFormState(initialBuildState);
 *   form.instructions;      // reactive read
 *   form.instructions = x;  // reactive write
 *   form.isStepComplete(1); // enables the Next button
 *   form.serialize();       // build_state payload persisted to the backend
 */

/**
 * @typedef {Object} WorkshopBuildState
 * @property {number} [currentStep]
 * @property {string} [instructions]
 * @property {string} [attachedFilePath]
 * @property {{name: string, path: string} | null} [attachedFileMeta]
 * @property {string} [documentStatus]
 * @property {string} [selectedKbId]
 * @property {string} [kbCollection]
 * @property {string} [kbQuery]
 * @property {any} [kbVerificationResult]
 * @property {string[]} [selectedTools]
 * @property {boolean} [sandboxEnabled]
 * @property {string} [reflection]
 * @property {Array<{role: string, content: string}>} [chatMessages]
 * @property {number | null} [assistantId]
 * @property {string} [assistantName]
 * @property {Object<string, boolean>} [stepValid]
 */

/**
 * @param {WorkshopBuildState} [initial] - persisted build_state from the backend.
 */
export function createWorkshopFormState(initial = {}) {
	let form = $state({
		// --- Step ownership ---
		currentStep: initial.currentStep ?? 1, // 1-5

		// --- Step 1: Instructions ---
		instructions: initial.instructions ?? '',

		// --- Step 2: Attach document ---
		attachedFilePath: initial.attachedFilePath ?? '',
		/** @type {{name: string, path: string} | null} */
		attachedFileMeta: initial.attachedFileMeta ?? null,
		documentStatus: initial.documentStatus ?? '',

		// --- Step 3: Connect KB ---
		selectedKbId: initial.selectedKbId ?? '',
		kbCollection: initial.kbCollection ?? '',
		kbQuery: initial.kbQuery ?? '',
		/** @type {any | null} */
		kbVerificationResult: initial.kbVerificationResult ?? null,

		// --- Step 4: Add tool ---
		/** @type {string[]} */
		selectedTools: initial.selectedTools ?? ['calculator'],
		sandboxEnabled: initial.sandboxEnabled ?? false,

		// --- Step 5: Test chat + reflection ---
		reflection: initial.reflection ?? '',
		/** @type {Array<{role: string, content: string}>} */
		chatMessages: initial.chatMessages ?? [],

		// --- assistant identity (built by submit) ---
		assistantId: initial.assistantId ?? null,
		assistantName: initial.assistantName ?? '',

		// --- UI state ---
		/** @type {Object<string, boolean>} */
		stepValid: initial.stepValid ?? {},
		submitting: false,
		error: '',
	});

	return {
		form,
		/** @param {number} step */
		goToStep(step) {
			if (step >= 1 && step <= 5) form.currentStep = step;
		},
		nextStep() {
			if (form.currentStep < 5) form.currentStep++;
		},
		prevStep() {
			if (form.currentStep > 1) form.currentStep--;
		},
		/**
		 * Determine if a step is complete (used to enable Next button).
		 * @param {number} step
		 * @returns {boolean}
		 */
		isStepComplete(step) {
			switch (step) {
				case 1: return !!form.instructions.trim();
				case 2: return !!form.attachedFilePath && form.documentStatus === 'completed';
				case 3: return !!form.selectedKbId;
				case 4: return form.selectedTools.length > 0;
				case 5: return false; // always actionable
				default: return false;
			}
		},
		/**
		 * Serialize the current build state (for persistence / submit).
		 * @returns {Object}
		 */
		serialize() {
			// Deep copy so the persisted payload is independent of the live store.
			return JSON.parse(JSON.stringify({
				currentStep: form.currentStep,
				instructions: form.instructions,
				attachedFilePath: form.attachedFilePath,
				attachedFileMeta: form.attachedFileMeta,
				documentStatus: form.documentStatus,
				selectedKbId: form.selectedKbId,
				kbCollection: form.kbCollection,
				kbQuery: form.kbQuery,
				kbVerificationResult: form.kbVerificationResult,
				selectedTools: form.selectedTools,
				sandboxEnabled: form.sandboxEnabled,
				reflection: form.reflection,
				chatMessages: form.chatMessages,
				assistantId: form.assistantId,
				assistantName: form.assistantName,
			}));
		},
	};
}