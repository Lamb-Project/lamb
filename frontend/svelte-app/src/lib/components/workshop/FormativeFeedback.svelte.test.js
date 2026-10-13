// src/lib/components/workshop/FormativeFeedback.svelte.test.js
import { describe, test, expect, beforeAll } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/svelte';
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
	test('F1: renders criteria, feedback and the "not a grade" framing', () => {
		render(FormativeFeedback, {
			props: { evaluation: successEvaluation, evaluating: false },
		});
		// The qualitative feedback is visible immediately…
		expect(screen.getByText('Clarity')).toBeInTheDocument();
		expect(screen.getByText('The instruction is clear and focused.')).toBeInTheDocument();
		expect(screen.getByText('Nice grounding with the document.')).toBeInTheDocument();
		// …the numbers are not (D6).
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

// ── D6: the scores are folded away by default ─────────────────────────────

describe('FormativeFeedback — suggested score is opt-in', () => {
	test('D6a: neither the total nor the criterion score is visible up front', () => {
		const { container } = render(FormativeFeedback, {
			props: { evaluation: successEvaluation, evaluating: false },
		});

		// The values exist in the DOM (inside <details>) but the sections are
		// closed, so nothing numeric is shown until the student asks for it.
		const totals = container.querySelector('[data-testid="score-details"]');
		expect(totals).toBeInTheDocument();
		expect(totals.hasAttribute('open')).toBe(false);

		const criterionScore = container.querySelector('[data-testid="criterion-score-0"]');
		expect(criterionScore).toBeInTheDocument();
		expect(criterionScore.hasAttribute('open')).toBe(false);
	});

	test('D6b: the student can reveal the total by opening the section', async () => {
		const { container } = render(FormativeFeedback, {
			props: { evaluation: successEvaluation, evaluating: false },
		});
		const details = /** @type {HTMLDetailsElement} */ (
			container.querySelector('[data-testid="score-details"]')
		);
		await fireEvent.click(details.querySelector('summary'));
		// The revealed block reads "Suggested: 9 / 10" (split across nodes).
		expect(details.textContent).toContain('9');
		expect(details.textContent).toContain('10');
	});

	test('D6c: feedback without a score renders no score section at all', () => {
		render(FormativeFeedback, {
			props: {
				evaluation: {
					configured: true,
					status: 'completed',
					criteria: [{ criterion: 'Clarity', feedback: 'clear' }],
					overall_feedback: 'ok',
				},
				evaluating: false,
			},
		});
		expect(screen.queryByTestId('score-details')).not.toBeInTheDocument();
		expect(screen.getByText('clear')).toBeInTheDocument();
	});
});

describe('FormativeFeedback — a cut-off evaluation is disclosed', () => {
	test('warns when the recovered feedback was truncated', () => {
		render(FormativeFeedback, {
			props: {
				evaluation: {
					...successEvaluation,
					// A *completed* evaluation whose JSON had to be repaired: the
					// feedback is usable, but its last sentence is clipped.
					error_message:
						"The model's response was cut off before the JSON was complete; " +
						'the fields it did produce are shown.',
				},
				evaluating: false,
			},
		});
		expect(screen.getByTestId('feedback-truncated')).toBeInTheDocument();
		expect(screen.getByText(/may end mid-sentence/)).toBeInTheDocument();
		// The recovered feedback is still shown — that is the whole point.
		expect(screen.getByText('Clarity')).toBeInTheDocument();
	});

	test('says nothing extra for a clean evaluation', () => {
		render(FormativeFeedback, {
			props: { evaluation: successEvaluation, evaluating: false },
		});
		expect(screen.queryByTestId('feedback-truncated')).not.toBeInTheDocument();
	});
});
