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
 * @property {{q1?: string, q2?: string, q3?: string}} [reflectionAnswers]
 * @property {'on' | 'off'} [ragMode]
 * @property {Array<{turn: number, ragMode: string, sources: Array<any>, answer: string, question: string}>} [obsHistory]
 * @property {Array<{step: number, kind: string, data: any, at?: number}>} [observations]
 * @property {Array<{role: string, content: string}>} [chatMessages]
 * @property {number | null} [assistantId]
 * @property {string} [assistantName]
 * @property {Object<string, boolean>} [stepValid]
 */

/**
 * Reflection questions, in order. Kept here (not only in the component) so the
 * composed `reflection` string and the transcript agree with the UI.
 */
export const REFLECTION_QUESTIONS = [
	{ key: 'q1', heading: 'What did you ask your assistant to do, and why?' },
	{ key: 'q2', heading: 'What did the assistant actually receive?' },
	{ key: 'q3', heading: 'What would you change in your design after testing it?' }
];

/**
 * Compose the free-text `reflection` field from the three structured answers.
 *
 * `dashboard.avg_reflection_length` and `evaluation.build_transcript` keep
 * working unchanged: the composed string is what they read. Answers left blank
 * are skipped, so a half-filled form never produces empty headings.
 *
 * @param {{q1?: string, q2?: string, q3?: string}} [answers]
 * @returns {string}
 */
export function composeReflection(answers = {}) {
	const parts = [];
	for (const question of REFLECTION_QUESTIONS) {
		const answer = (answers?.[question.key] || '').trim();
		if (!answer) continue;
		parts.push(`### ${question.heading}\n${answer}`);
	}
	return parts.join('\n\n');
}

/**
 * A form store seeded from persisted build state.
 *
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
		// `reflection` stays the free-text field the backend/transcript read; the
		// three structured answers are the UI, and compose into it on submit
		// (legacy rows keep their original text — D5).
		reflection: initial.reflection ?? '',
		/** @type {{q1: string, q2: string, q3: string}} */
		reflectionAnswers: {
			q1: initial.reflectionAnswers?.q1 ?? '',
			q2: initial.reflectionAnswers?.q2 ?? '',
			q3: initial.reflectionAnswers?.q3 ?? '',
		},
		/** @type {'on' | 'off'} */
		ragMode: initial.ragMode === 'off' ? 'off' : 'on',
		/** @type {Array<{turn: number, ragMode: string, sources: Array<any>, answer: string, question: string}>} */
		obsHistory: initial.obsHistory ?? [],
		/** @type {Array<{step: number, kind: string, data: any, at?: number}>} */
		observations: initial.observations ?? [],
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
		 * Compose the structured reflection answers into the persisted
		 * `reflection` string, keeping any legacy text that predates the
		 * three questions.
		 * @returns {string}
		 */
		composeReflection() {
			const composed = composeReflection(form.reflectionAnswers);
			if (composed) return composed;
			return form.reflection || '';
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
				reflectionAnswers: form.reflectionAnswers,
				ragMode: form.ragMode,
				obsHistory: form.obsHistory,
				observations: form.observations,
				chatMessages: form.chatMessages,
				assistantId: form.assistantId,
				assistantName: form.assistantName,
			}));
		},
	};
}