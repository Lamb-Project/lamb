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
import { render, screen, fireEvent } from '@testing-library/svelte';
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

describe('WizardSteps — step 2 document upload', () => {
	const notes = () => new File(['# notes'], 'notes.md', { type: 'text/markdown' });

	/** @param {Record<string, any>} [extra] */
	function renderStep2(extra = {}) {
		/** @type {File[]} */
		const uploaded = [];
		const { container } = render(WizardSteps, {
			props: { form: formAt(2), onUploadDocument: (/** @type {File} */ f) => uploaded.push(f), ...extra }
		});
		const zone = /** @type {HTMLElement} */ (container.querySelector('.border-dashed'));
		const input = /** @type {HTMLInputElement} */ (container.querySelector('input[type=file]'));
		return { uploaded, zone, input };
	}

	test('choosing a file starts the upload', async () => {
		const { uploaded, input } = renderStep2();
		await fireEvent.change(input, { target: { files: [notes()] } });
		expect(uploaded.map((f) => f.name)).toEqual(['notes.md']);
	});

	test('the input is reset so the same file can be chosen again after a failure', async () => {
		const { input } = renderStep2();
		// jsdom's file input has no selection state of its own; emulate the
		// browser's "C:\fakepath\…" value so a missing reset is observable.
		let value = 'C:\\fakepath\\notes.md';
		Object.defineProperty(input, 'value', {
			get: () => value,
			set: (v) => { value = v; },
			configurable: true
		});
		Object.defineProperty(input, 'files', { value: [notes()], configurable: true });
		await fireEvent.change(input);
		// A retained value would stop the browser from firing `change` on re-selection.
		expect(value).toBe('');
	});

	test('dropping a file on the zone starts the upload', async () => {
		const { uploaded, zone } = renderStep2();
		await fireEvent.drop(zone, { dataTransfer: { files: [notes()] } });
		expect(uploaded.map((f) => f.name)).toEqual(['notes.md']);
	});

	test('dragover is cancelled (otherwise the browser opens the file) and highlights the zone', async () => {
		const { zone } = renderStep2();
		const notCancelled = await fireEvent.dragOver(zone, { dataTransfer: { files: [] } });
		expect(notCancelled).toBe(false);
		expect(zone.className).toContain('border-blue-500');
		await fireEvent.dragLeave(zone);
		expect(zone.className).not.toContain('border-blue-500');
	});

	test('a drop while an upload is running is ignored', async () => {
		const { uploaded, zone } = renderStep2({ uploading: true });
		await fireEvent.drop(zone, { dataTransfer: { files: [notes()] } });
		expect(uploaded).toEqual([]);
	});

	test('Remove hands over to the page, which deletes the document server-side', async () => {
		let removed = 0;
		const form = formAt(2);
		form.attachedFilePath = 'file-1';
		form.attachedFileMeta = { name: 'notes.md', path: 'file-1' };
		form.documentStatus = 'completed';
		render(WizardSteps, { props: { form, onRemoveDocument: () => (removed += 1) } });

		await fireEvent.click(screen.getByRole('button', { name: 'Remove' }));

		expect(removed).toBe(1);
		// The page clears the state only once the server confirmed.
		expect(form.attachedFileMeta).not.toBeNull();
	});

	test('Remove is disabled while a removal is in flight', () => {
		const form = formAt(2);
		form.attachedFileMeta = { name: 'notes.md', path: 'file-1' };
		render(WizardSteps, { props: { form, onRemoveDocument: () => {}, removing: true } });
		expect(screen.getByRole('button', { name: 'Remove' })).toBeDisabled();
	});

	test('without a handler Remove still clears the local state', async () => {
		const form = formAt(2);
		form.attachedFilePath = 'file-1';
		form.attachedFileMeta = { name: 'notes.md', path: 'file-1' };
		form.documentStatus = 'completed';
		render(WizardSteps, { props: { form } });

		await fireEvent.click(screen.getByRole('button', { name: 'Remove' }));

		expect(form.attachedFileMeta).toBeNull();
		expect(form.documentStatus).toBe('');
	});

	test('step 3 points at the excerpts, not at how the document was split', () => {
		render(WizardSteps, { props: { form: formAt(3) } });
		expect(screen.getByText(/the excerpts and how similar they are/)).toBeInTheDocument();
		expect(screen.queryByText(/how it was split/)).not.toBeInTheDocument();
	});

	test('the drop hint is localized', async () => {
		await useLocale('es');
		renderStep2();
		expect(screen.getByText(/arrastrar y soltar/)).toBeInTheDocument();
	});
});
