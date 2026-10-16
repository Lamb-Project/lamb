// src/lib/components/workshop/logic/workshopObservations.svelte.js
/**
 * Per-step observation snapshots for the workshop wizard (D2).
 *
 * Before this, the observation panel only had content once the student had
 * already chatted in step 5 — so steps 2, 3 and 4 showed nothing, and the panel
 * could not do its actual job ("look at what your assistant receives *now*").
 *
 * A snapshot is a small, JSON-serializable record:
 *
 *   { step: 2, kind: 'document', data: {...}, at: <epoch ms> }
 *
 * Kinds used by the wizard:
 *   - `document`      step 2: the KB file registry (how the upload was chunked)
 *   - `probe`         step 3: excerpts retrieved for the student's test question
 *   - `tools`         step 4: the tool definitions that will be sent
 *   - `chat_request`  step 5: the observability "request" frame
 *   - `chat_result`   step 5: the observability "result" frame
 *
 * Stored on `form.observations` so the whole set travels with `build_state`
 * (and therefore reaches the formative transcript without another API call).
 */

/** @typedef {{step: number, kind: string, data: any, at: number}} Observation */

/**
 * Append a snapshot, returning the new list (never mutates in place, so Svelte's
 * reactivity sees the change).
 *
 * @param {Array<Observation>} observations
 * @param {number} step
 * @param {string} kind
 * @param {any} data
 * @param {number} [now]
 * @returns {Array<Observation>}
 */
export function recordObservation(observations, step, kind, data, now = Date.now()) {
	return [...(observations || []), { step, kind, data, at: now }];
}

/**
 * Remove every snapshot of the given kinds, returning the new list.
 *
 * Used when the document is removed: its chunking facts and the probe results
 * describe a knowledge base that no longer exists, so keeping them would show
 * the student evidence for something they just deleted.
 *
 * @param {Array<Observation>} observations
 * @param {Array<string>} kinds
 * @returns {Array<Observation>}
 */
export function dropObservations(observations, kinds) {
	return (observations || []).filter((o) => !(o && kinds.includes(o.kind)));
}

/**
 * The most recent snapshot of a kind for a step, or null.
 *
 * @param {Array<Observation>} observations
 * @param {number} step
 * @param {string} [kind]
 * @returns {Observation | null}
 */
export function latestObservation(observations, step, kind = '') {
	const matches = (observations || []).filter(
		(o) => o && o.step === step && (!kind || o.kind === kind)
	);
	return matches.length ? matches[matches.length - 1] : null;
}

/**
 * Every snapshot recorded for a step, in order.
 *
 * @param {Array<Observation>} observations
 * @param {number} step
 * @returns {Array<Observation>}
 */
export function observationsForStep(observations, step) {
	return (observations || []).filter((o) => o && o.step === step);
}

/**
 * Whether a step has anything to show in the panel.
 *
 * @param {Array<Observation>} observations
 * @param {number} step
 * @returns {boolean}
 */
export function hasObservations(observations, step) {
	return observationsForStep(observations, step).length > 0;
}

/**
 * Describe a KB file registry entry in the terms the lesson uses.
 *
 * `document_count` is the number of *chunks* the document became — the
 * deterministic fact the panel shows (decision C16); a probe query would only
 * reveal whichever top-k excerpts happened to rank highest.
 *
 * @param {any} file - a FileRegistryResponse item
 * @returns {{name: string, chunks: number, chunkSize: number | null,
 *            chunkOverlap: number | null, fileSize: number | null, status: string}}
 */
export function describeDocument(file) {
	const params = (file && file.plugin_params) || {};
	return {
		name: (file && (file.original_filename || file.filename)) || 'document',
		chunks: Number(file?.document_count) || 0,
		chunkSize: params.chunk_size ?? null,
		chunkOverlap: params.chunk_overlap ?? null,
		fileSize: typeof file?.file_size === 'number' ? file.file_size : null,
		status: (file && file.status) || 'unknown'
	};
}

/**
 * Human-readable byte size (kept tiny on purpose — no dependency).
 * @param {number | null} bytes
 * @returns {string}
 */
export function formatBytes(bytes) {
	if (bytes === null || bytes === undefined) return '—';
	if (bytes < 1024) return `${bytes} B`;
	if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
	return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

/**
 * Group A/B runs by question so the two modes can be compared side by side.
 *
 * The student is asked to run the *same* question twice (knowledge base on,
 * then off). Matching on the question text is what makes the comparison
 * honest: two different questions would show a difference no matter what the
 * knowledge base did.
 *
 * @param {Array<{turn?: number, ragMode?: string, question?: string,
 *                sources?: Array<any>, answer?: string, ragContext?: string}>} history
 * @returns {Array<{question: string, on: any | null, off: any | null}>}
 */
export function compareRagRuns(history) {
	/** @type {Array<{question: string, on: any | null, off: any | null}>} */
	const pairs = [];

	for (const run of history || []) {
		if (!run) continue;
		const question = (run.question || '').trim();
		if (!question) continue;

		// A linear scan keeps this a plain function over plain data — no
		// reactive Map, and the group counts here are tiny (a lesson's turns).
		let pair = pairs.find((candidate) => candidate.question === question);
		if (!pair) {
			pair = { question, on: null, off: null };
			pairs.push(pair);
		}
		// Keep the most recent run of each mode.
		if (run.ragMode === 'off') pair.off = run;
		else pair.on = run;
	}
	return pairs;
}
