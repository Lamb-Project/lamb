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
		expect(screen.getAllByText('Clarity').length).toBeGreaterThanOrEqual(1);
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
	test('D6a: the numbers sit behind a single closed toggle', () => {
		const { container } = render(FormativeFeedback, {
			props: { evaluation: successEvaluation, evaluating: false },
		});

		// The values exist in the DOM (inside <details>) but the section is
		// closed, so nothing numeric is shown until the student asks for it.
		const totals = container.querySelector('[data-testid="score-details"]');
		expect(totals).toBeInTheDocument();
		expect(totals.hasAttribute('open')).toBe(false);

		// Exactly one toggle for the whole evaluation: a per-criterion toggle
		// repeated the same label for every row, which is what made a runaway
		// 20-row evaluation look like a wall of identical links.
		expect(screen.getAllByText('Show the suggested score')).toHaveLength(1);
	});

	test('D6a2: a long criteria list still renders one toggle, not one per row', () => {
		const many = {
			...successEvaluation,
			criteria: Array.from({ length: 12 }, (_, i) => ({
				criterion: `Criterion ${i + 1}`,
				level: 'Beginning',
				score: 1,
				weight: 10,
				feedback: `Feedback ${i + 1}`,
			})),
		};
		render(FormativeFeedback, { props: { evaluation: many, evaluating: false } });

		expect(screen.getAllByText('Show the suggested score')).toHaveLength(1);
		// …and every criterion's feedback is still readable.
		expect(screen.getByText('Feedback 12')).toBeInTheDocument();
	});

	test('D6b: the student can reveal the total and the per-criterion scores', async () => {
		const { container } = render(FormativeFeedback, {
			props: { evaluation: successEvaluation, evaluating: false },
		});
		const details = /** @type {HTMLDetailsElement} */ (
			container.querySelector('[data-testid="score-details"]')
		);
		await fireEvent.click(details.querySelector('summary'));
		// The revealed block reads "Suggested: 9 / 10" (split across nodes)…
		expect(details.textContent).toContain('9');
		expect(details.textContent).toContain('10');
		// …plus each criterion's score and weight.
		expect(details.textContent).toContain('Score: 4');
		expect(details.textContent).toContain('100%');
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

describe('FormativeFeedback — an incomplete evaluation is disclosed', () => {
	test('warns when the recovered feedback was truncated or partial', () => {
		render(FormativeFeedback, {
			props: {
				evaluation: {
					...successEvaluation,
					// A *completed* evaluation whose JSON had to be repaired, or
					// that only covered some of the rubric's criteria.
					error_message:
						"The model's response was cut off before the JSON was complete; " +
						'the fields it did produce are shown.',
				},
				evaluating: false,
			},
		});
		expect(screen.getByTestId('feedback-truncated')).toBeInTheDocument();
		expect(screen.getByText(/may be incomplete/)).toBeInTheDocument();
		// The recovered feedback is still shown — that is the whole point.
		expect(screen.getAllByText('Clarity').length).toBeGreaterThanOrEqual(1);
	});

	test('says nothing extra for a clean evaluation', () => {
		render(FormativeFeedback, {
			props: { evaluation: successEvaluation, evaluating: false },
		});
		expect(screen.queryByTestId('feedback-truncated')).not.toBeInTheDocument();
	});
});
