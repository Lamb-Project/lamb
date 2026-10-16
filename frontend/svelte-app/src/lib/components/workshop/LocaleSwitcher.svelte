<script>
	// src/lib/components/workshop/LocaleSwitcher.svelte
	// Four-language switch for the student workshop shell (decision C19).
	//
	// Removing the Creator navigation also removed the only language control a
	// student had. Without it the locale chain (LMS locale → saved choice →
	// browser) can land on a language the teacher did not intend, with no way
	// to correct it in class. This writes the same `localStorage.lang` key the
	// Creator app uses, so an explicit choice sticks.
	//
	// Language names stay in their own language on purpose: a student looking
	// for their language should recognise it, not have to read it translated.

	import { _ } from '$lib/i18n';
	import { locale } from '$lib/i18n';
	import { chooseWorkshopLocale, matchLocale } from '$lib/workshop/workshopLocale.js';

	/** @type {{ compact?: boolean }} */
	let { compact = false } = $props();

	/** @type {Record<string, string>} */
	const LANGUAGE_NAMES = {
		en: 'English',
		es: 'Español',
		ca: 'Català',
		eu: 'Euskara'
	};

	/** @type {string[]} */
	const LANGUAGES = ['en', 'es', 'ca', 'eu'];

	/** @param {Event} e */
	function handleChange(e) {
		const value = /** @type {HTMLSelectElement} */ (e.target).value;
		chooseWorkshopLocale(value);
	}

	const current = $derived(matchLocale($locale) || 'en');
	// Padding note: `@tailwindcss/forms` draws the dropdown chevron as a
	// background image and reserves room for it with `padding-right`. A `px-*`
	// utility overrides that, so the chevron lands on top of the language name.
	// Keep the sides separate (`pl-*` / `pr-*`) and never set `px-*` here.
</script>

<div class="flex items-center gap-1.5">
	<span class="text-xs text-gray-500" aria-hidden="true">🌐</span>
	<label class="sr-only" for="ws-locale">
		{$_('workshop.languageLabel', { default: 'Language' })}
	</label>
	<select
		id="ws-locale"
		data-testid="workshop-locale-switcher"
		class="text-xs border rounded py-1 bg-white text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500
			{compact ? 'pl-1 pr-6' : 'pl-1.5 pr-7'}"
		value={current}
		onchange={handleChange}
	>
		{#each LANGUAGES as code (code)}
			<option value={code}>{LANGUAGE_NAMES[code] || code}</option>
		{/each}
	</select>
</div>
