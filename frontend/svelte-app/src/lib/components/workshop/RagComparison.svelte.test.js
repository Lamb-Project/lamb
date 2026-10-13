// src/lib/components/workshop/RagComparison.svelte.test.js
import { describe, test, expect, beforeAll } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import '@testing-library/jest-dom/vitest';
import { waitLocale } from 'svelte-i18n';
import { setupI18n } from '$lib/i18n';
import RagComparison from './RagComparison.svelte';

beforeAll(async () => {
	setupI18n();
	await waitLocale();
});

const history = [
	{
		turn: 1,
		ragMode: 'on',
		question: 'What is a fraction?',
		sources: [{ similarity: 0.9, content: 'A fraction shows equal parts.' }],
		answer: 'A fraction shows equal parts of a whole.'
	},
	{
		turn: 2,
		ragMode: 'off',
		question: 'What is a fraction?',
		sources: [],
		answer: 'I do not have information about that.'
	}
];

describe('RagComparison — the A/B experiment made visible', () => {
	test('R1: prompts the student before anything has been run', () => {
		render(RagComparison, { props: { history: [] } });
		expect(screen.getByText(/Run the same question in both modes/)).toBeInTheDocument();
	});

	test('R2: shows both answers for the same question side by side', () => {
		render(RagComparison, { props: { history } });

		expect(screen.getByText('What is a fraction?')).toBeInTheDocument();
		expect(screen.getByText('A fraction shows equal parts of a whole.')).toBeInTheDocument();
		expect(screen.getByText('I do not have information about that.')).toBeInTheDocument();
		expect(screen.getByTestId('comparison-on')).toBeInTheDocument();
		expect(screen.getByTestId('comparison-off')).toBeInTheDocument();
	});

	test('R3: the inputs column makes the difference explainable', () => {
		render(RagComparison, { props: { history } });

		// The "on" run had one excerpt; the "off" run had the tool removed.
		expect(screen.getByText(/1 excerpt\(s\) were placed in the prompt/))
			.toBeInTheDocument();
		// The "off" run had no retrieval at all — the tool was removed.
		expect(screen.getByText(/retrieval tool was removed/)).toBeInTheDocument();
	});

	test('R4: a mode that has not been run yet is called out', () => {
		render(RagComparison, {
			props: { history: [history[0]] }
		});
		expect(screen.getByText(/Not run in this mode yet/)).toBeInTheDocument();
	});

	test('R5: a question with no matching excerpts says so', () => {
		render(RagComparison, {
			props: {
				history: [
					{ ragMode: 'on', question: 'q', sources: [], answer: 'a' }
				]
			}
		});
		expect(screen.getByText(/No excerpts matched this question/)).toBeInTheDocument();
	});

	test('R6: several questions each get their own comparison', () => {
		render(RagComparison, {
			props: {
				history: [
					{ ragMode: 'on', question: 'q1', sources: [], answer: 'a1' },
					{ ragMode: 'off', question: 'q1', sources: [], answer: 'b1' },
					{ ragMode: 'on', question: 'q2', sources: [], answer: 'a2' }
				]
			}
		});
		expect(screen.getByText('q1')).toBeInTheDocument();
		expect(screen.getByText('q2')).toBeInTheDocument();
	});
});
