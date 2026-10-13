// src/lib/components/workshop/logic/workshopObservations.test.js
import { describe, test, expect } from 'vitest';
import {
	compareRagRuns,
	describeDocument,
	formatBytes,
	hasObservations,
	latestObservation,
	observationsForStep,
	recordObservation
} from './workshopObservations.svelte.js';

describe('recordObservation / lookups', () => {
	test('appends without mutating the input list', () => {
		const before = [];
		const after = recordObservation(before, 2, 'document', { files: [] }, 111);

		expect(before).toHaveLength(0);
		expect(after).toHaveLength(1);
		expect(after[0]).toEqual({
			step: 2, kind: 'document', data: { files: [] }, at: 111
		});
	});

	test('latest returns the most recent entry for a step+kind', () => {
		let obs = recordObservation([], 5, 'chat_result', { n: 1 });
		obs = recordObservation(obs, 5, 'chat_result', { n: 2 });
		expect(latestObservation(obs, 5, 'chat_result').data.n).toBe(2);
	});

	test('latest without a kind matches any kind for the step', () => {
		let obs = recordObservation([], 5, 'chat_request', { n: 1 });
		obs = recordObservation(obs, 5, 'chat_result', { n: 2 });
		expect(latestObservation(obs, 5).data.n).toBe(2);
	});

	test('latest returns null when the step has no snapshot', () => {
		expect(latestObservation([], 3, 'probe')).toBeNull();
		expect(latestObservation(undefined, 3)).toBeNull();
	});

	test('observationsForStep / hasObservations filter by step', () => {
		let obs = recordObservation([], 2, 'document', {});
		obs = recordObservation(obs, 3, 'probe', {});
		expect(observationsForStep(obs, 3)).toHaveLength(1);
		expect(hasObservations(obs, 2)).toBe(true);
		expect(hasObservations(obs, 4)).toBe(false);
	});

	test('tolerates null/garbage entries', () => {
		expect(observationsForStep([null, { step: 2 }], 2)).toHaveLength(1);
		expect(hasObservations([null], 2)).toBe(false);
	});
});

describe('describeDocument — the deterministic chunking facts', () => {
	test('reads the KB file registry fields', () => {
		const described = describeDocument({
			original_filename: 'notes.md',
			document_count: 12,
			file_size: 4096,
			status: 'completed',
			plugin_params: { chunk_size: 1000, chunk_overlap: 200 }
		});
		expect(described).toEqual({
			name: 'notes.md',
			chunks: 12,
			chunkSize: 1000,
			chunkOverlap: 200,
			fileSize: 4096,
			status: 'completed'
		});
	});

	test('survives a registry entry with no plugin params', () => {
		const described = describeDocument({ filename: 'a.txt' });
		expect(described.name).toBe('a.txt');
		expect(described.chunks).toBe(0);
		expect(described.chunkSize).toBeNull();
		expect(described.status).toBe('unknown');
	});

	test('handles a missing entry entirely', () => {
		expect(describeDocument(undefined).name).toBe('document');
	});
});

describe('formatBytes', () => {
	test('formats each magnitude', () => {
		expect(formatBytes(512)).toBe('512 B');
		expect(formatBytes(2048)).toBe('2.0 KB');
		expect(formatBytes(3 * 1024 * 1024)).toBe('3.00 MB');
		expect(formatBytes(null)).toBe('—');
	});
});

describe('compareRagRuns — pairing the A/B turns by question', () => {
	test('pairs an on-run and an off-run of the same question', () => {
		const pairs = compareRagRuns([
			{ ragMode: 'on', question: 'What is a fraction?', sources: [{}, {}], answer: 'A' },
			{ ragMode: 'off', question: 'What is a fraction?', sources: [], answer: 'B' }
		]);

		expect(pairs).toHaveLength(1);
		expect(pairs[0].question).toBe('What is a fraction?');
		expect(pairs[0].on.answer).toBe('A');
		expect(pairs[0].off.answer).toBe('B');
	});

	test('keeps different questions apart', () => {
		const pairs = compareRagRuns([
			{ ragMode: 'on', question: 'q1' },
			{ ragMode: 'on', question: 'q2' }
		]);
		expect(pairs.map((p) => p.question)).toEqual(['q1', 'q2']);
	});

	test('a question run in one mode only leaves the other side empty', () => {
		const pairs = compareRagRuns([{ ragMode: 'on', question: 'q1' }]);
		expect(pairs[0].on).not.toBeNull();
		expect(pairs[0].off).toBeNull();
	});

	test('re-running a mode replaces the previous attempt', () => {
		const pairs = compareRagRuns([
			{ ragMode: 'on', question: 'q1', answer: 'first' },
			{ ragMode: 'on', question: 'q1', answer: 'second' }
		]);
		expect(pairs).toHaveLength(1);
		expect(pairs[0].on.answer).toBe('second');
	});

	test('ignores entries without a question or that are null', () => {
		expect(compareRagRuns([null, { ragMode: 'on', question: '  ' }])).toEqual([]);
		expect(compareRagRuns(undefined)).toEqual([]);
	});
});
