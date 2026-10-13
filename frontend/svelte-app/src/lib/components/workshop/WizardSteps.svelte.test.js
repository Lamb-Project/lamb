// src/lib/components/workshop/WizardSteps.svelte.test.js
/**
 * The wizard is reached straight from the LMS, with no Creator session, so
 * every student-visible string must come from the locale bundles. These tests
 * switch the app locale and assert the rendered wizard follows — a hardcoded
 * English string would fail here.
 *
 * (Named `*.svelte.test.js` so the vitest workspace runs it in the jsdom
 * "client" project; that is the convention every other component test uses.)
 */
import { describe, test, expect, beforeAll, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import '@testing-library/jest-dom/vitest';
import { waitLocale, locale } from 'svelte-i18n';
import { setupI18n } from '$lib/i18n';
import { createWorkshopFormState } from './logic/workshopFormState.svelte.js';
import WizardSteps from './WizardSteps.svelte';

beforeAll(async () => {
	setupI18n();
	await waitLocale();
});

beforeEach(async () => {
	await useLocale('en');
});

/**
 * Switch locale and wait for the bundle to load *and* the store to flip.
 *
 * svelte-i18n's `locale.set` is asynchronous while the target dictionary still
 * has a queued loader, so a bare `locale.set('es')` leaves the store on the
 * previous locale.
 * @param {string} lang
 */
async function useLocale(lang) {
	await locale.set(lang);
	await new Promise((resolve) => setTimeout(resolve, 0));
}

/** @param {number} step */
function formAt(step) {
	const store = createWorkshopFormState({ currentStep: step });
	store.form.currentStep = step;
	return store.form;
}

describe('WizardSteps — localization', () => {
	test('I1: step 1 text is English by default', () => {
		render(WizardSteps, { props: { form: formAt(1) } });
		expect(screen.getByText(/System prompt for your assistant/)).toBeInTheDocument();
	});

	test('I2: the same step renders Spanish when the locale is es', async () => {
		await useLocale('es');
		render(WizardSteps, { props: { form: formAt(1) } });
		expect(screen.getByText(/Prompt de sistema de tu asistente/)).toBeInTheDocument();
		expect(screen.queryByText(/System prompt for your assistant/)).not.toBeInTheDocument();
	});

	test('I3: Catalan and Basque render too', async () => {
		await useLocale('ca');
		const { unmount } = render(WizardSteps, { props: { form: formAt(1) } });
		expect(screen.getByText(/Prompt de sistema del teu assistent/)).toBeInTheDocument();
		unmount();

		await useLocale('eu');
		render(WizardSteps, { props: { form: formAt(1) } });
		expect(screen.getByText(/sistema-prompta/)).toBeInTheDocument();
	});

	test('I4: navigation labels are localized', async () => {
		await useLocale('es');
		render(WizardSteps, { props: { form: formAt(2), nextDisabled: false } });
		expect(screen.getByRole('button', { name: /Siguiente/ })).toBeInTheDocument();
		expect(screen.getByRole('button', { name: /Atrás/ })).toBeInTheDocument();
	});

	test('I5: step 4 names the tools in the active language', async () => {
		await useLocale('eu');
		render(WizardSteps, { props: { form: formAt(4) } });
		expect(screen.getByText(/Kalkulagailua/)).toBeInTheDocument();
	});

	test('I6: step 5 shows the three reflection questions in the active language', async () => {
		await useLocale('es');
		render(WizardSteps, { props: { form: formAt(5) } });
		expect(screen.getByTestId('reflection-q1')).toBeInTheDocument();
		expect(screen.getByText(/Qué le pediste a tu asistente/)).toBeInTheDocument();
	});
});

describe('WizardSteps — D2/D3/D5 affordances', () => {
	test('step 4 previews the exact tools JSON that will be sent', () => {
		const form = formAt(4);
		form.selectedTools = ['calculator', 'kb_query'];
		render(WizardSteps, { props: { form } });

		expect(screen.getByText(/Tools that will be sent to the model/)).toBeInTheDocument();
		expect(screen.getByText(/"calculator"/)).toBeInTheDocument();
		expect(screen.getByText(/"kb_query"/)).toBeInTheDocument();
	});

	test('step 4 explains an empty tool list instead of showing nothing', () => {
		const form = formAt(4);
		form.selectedTools = [];
		render(WizardSteps, { props: { form } });
		expect(screen.getByText(/No tools selected/)).toBeInTheDocument();
	});

	test('step 5 exposes the knowledge-base on/off switch', () => {
		const form = formAt(5);
		render(WizardSteps, { props: { form } });

		const on = screen.getByTestId('rag-mode-on');
		const off = screen.getByTestId('rag-mode-off');
		expect(on).toBeInTheDocument();
		expect(off).toBeInTheDocument();
		// Defaults to on (the wizard's normal behaviour).
		expect(form.ragMode).toBe('on');
		expect(on).toHaveAttribute('aria-pressed', 'true');
	});

	test('step 3 no longer renders its own result list (shared panel instead)', () => {
		const form = formAt(3);
		form.kbVerificationResult = {
			results: [{ similarity: 0.9, data: 'inline-excerpt-should-not-render' }]
		};
		render(WizardSteps, { props: { form } });
		expect(screen.queryByText(/inline-excerpt-should-not-render/)).not.toBeInTheDocument();
	});

	test('step 5 keeps a legacy free-text reflection visible', () => {
		const form = formAt(5);
		form.reflection = 'my older reflection';
		render(WizardSteps, { props: { form } });
		expect(screen.getByText(/Your earlier reflection is kept/)).toBeInTheDocument();
		expect(screen.getByDisplayValue('my older reflection')).toBeInTheDocument();
	});
});