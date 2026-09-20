// src/lib/components/workshop/FormativeFeedback.svelte.test.js
import { describe, test, expect, beforeAll } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import '@testing-library/jest-dom/vitest';
import { waitLocale } from 'svelte-i18n';
import { setupI18n } from '$lib/i18n';
import FormativeFeedback from './FormativeFeedback.svelte';

beforeAll(async () => {
	setupI18n();
	await waitLocale();
});

const successEvaluation = {
	configured: true,
	status: 'completed',
	criteria: [
		{
			criterion: 'Clarity',
			level: 'Excellent',
			score: 4,
			weight: 100,
			feedback: 'The instruction is clear and focused.',
		},
	],
	total_score: 9,
	max_score: 10,
	overall_feedback: 'Nice grounding with the document.',
};

describe('FormativeFeedback — renders rubric feedback', () => {
	test('F1: renders criteria, scores and overall feedback', () => {
		render(FormativeFeedback, {
			props: { evaluation: successEvaluation, evaluating: false },
		});
		expect(screen.getByText('Clarity')).toBeInTheDocument();
		expect(screen.getByText(/Excellent/)).toBeInTheDocument();
		expect(screen.getByText('The instruction is clear and focused.')).toBeInTheDocument();
		expect(screen.getByText('Nice grounding with the document.')).toBeInTheDocument();
		// Score is framed as a suggestion, never a grade.
		expect(screen.getByText(/not a grade/i)).toBeInTheDocument();
	});

	test('F2: shows the evaluating state', () => {
		render(FormativeFeedback, {
			props: { evaluation: null, evaluating: true },
		});
		expect(screen.getByText(/Generating your feedback/)).toBeInTheDocument();
	});

	test('F3: reports when no rubric is configured', () => {
		render(FormativeFeedback, {
			props: { evaluation: { configured: false }, evaluating: false },
		});
		expect(screen.getByText(/No rubric is configured/)).toBeInTheDocument();
	});

	test('F4: reports a failed evaluation gracefully', () => {
		render(FormativeFeedback, {
			props: {
				evaluation: { configured: true, status: 'failed', error_message: 'boom' },
				evaluating: false,
			},
		});
		expect(screen.getByText(/Feedback could not be generated/)).toBeInTheDocument();
		expect(screen.getByText('boom')).toBeInTheDocument();
	});
});