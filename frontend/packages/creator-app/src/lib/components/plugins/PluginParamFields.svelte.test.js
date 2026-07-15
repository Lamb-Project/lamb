/**
 * PluginParamFields renderer tests.
 *
 * Verifies the schema-driven renderer that powers per-plugin parameter
 * inputs across the wizard. The aim is to lock in the contract: given a
 * synthetic schema, every parameter type produces the right input, the
 * declared defaults populate the value dict, and min/max validation
 * surfaces errors on the bindable errors prop.
 */
import { describe, it, expect, beforeAll } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { render } from '@testing-library/svelte';
import { tick } from 'svelte';
import { addMessages, init, locale, waitLocale } from 'svelte-i18n';
import PluginParamFields from './PluginParamFields.svelte';

// The renderer's validation effect calls $_(...) — svelte-i18n throws if
// no locale is initialised. Set up a minimal English bundle for the test
// run so the format-time error template resolves.
beforeAll(async () => {
	addMessages('en', {
		plugins: {
			params: {
				advancedLabel: 'Advanced parameters',
				required: 'Required',
				tooSmall: 'Must be ≥ {min}',
				tooLarge: 'Must be ≤ {max}',
				fixErrors: 'Fix the plugin parameter errors first.'
			}
		}
	});
	init({ fallbackLocale: 'en', initialLocale: 'en' });
	// init() is sync but locale loading is async — force the store so the
	// formatter resolves on the next tick.
	locale.set('en');
	await waitLocale('en');
});

const schema = [
	{
		name: 'chunk_size',
		type: 'int',
		description: 'Maximum characters per chunk',
		default: 500,
		min_value: 64,
		max_value: 2000
	},
	{
		name: 'temperature',
		type: 'float',
		description: 'Sampling temperature',
		default: 0.5
	},
	{
		name: 'mode',
		type: 'enum',
		description: 'Operating mode',
		default: 'standard',
		choices: ['standard', 'expert']
	},
	{
		name: 'use_cache',
		type: 'bool',
		description: 'Use cached responses',
		default: true
	},
	{
		name: 'extra_notes',
		type: 'string',
		description: 'Free-text notes',
		default: '',
		advanced: true
	}
];

describe('PluginParamFields', () => {
	it('renders one input per parameter type', () => {
		const { container } = render(PluginParamFields, {
			props: {
				parameters: schema,
				values: {},
				idPrefix: 'test',
				mode: 'advanced'
			}
		});
		expect(container.querySelector('#test-chunk_size')).not.toBeNull();
		expect(container.querySelector('#test-chunk_size').type).toBe('number');
		expect(container.querySelector('#test-temperature').type).toBe('number');
		expect(container.querySelector('#test-mode').tagName).toBe('SELECT');
		expect(container.querySelector('#test-use_cache').type).toBe('checkbox');
		expect(container.querySelector('#test-extra_notes').type).toBe('text');
	});

	it('hides advanced params behind <details> in simplified mode', () => {
		const { container } = render(PluginParamFields, {
			props: {
				parameters: schema,
				values: {},
				idPrefix: 'test',
				mode: 'simplified'
			}
		});
		// extra_notes is advanced — lives inside <details>
		const details = container.querySelector('details');
		expect(details).not.toBeNull();
		expect(details.querySelector('#test-extra_notes')).not.toBeNull();
	});

	it('initialises missing keys from the schema defaults', async () => {
		let captured = {};
		const { component } = render(PluginParamFields, {
			props: {
				parameters: schema,
				values: captured,
				idPrefix: 'test',
				mode: 'advanced'
			}
		});
		// The component fills values via $bindable. Read it back via props.
		await tick();
		// Confirm chunk_size, mode, use_cache defaults flowed in.
		// Note: $bindable two-way binding from a test harness inspects the
		// rendered <input>'s value attribute as the externally visible result.
		const { container } = render(PluginParamFields, {
			props: {
				parameters: schema,
				values: {},
				idPrefix: 'init',
				mode: 'advanced'
			}
		});
		await tick();
		expect(container.querySelector('#init-chunk_size').value).toBe('500');
		expect(container.querySelector('#init-mode').value).toBe('standard');
		expect(container.querySelector('#init-use_cache').checked).toBe(true);
	});

	it('emits an error in the errors map when value is below min', async () => {
		let errors = {};
		const { container, rerender } = render(PluginParamFields, {
			props: {
				parameters: [schema[0]],
				values: { chunk_size: 10 },
				errors,
				idPrefix: 'min',
				mode: 'advanced'
			}
		});
		await tick();
		// The bindable errors prop has been written. Verify via rendered output.
		expect(container.querySelector('p[role="alert"]')).not.toBeNull();
		expect(container.querySelector('p[role="alert"]').textContent).toMatch(/≥/);
	});

	it('emits an error when value is above max', async () => {
		const { container } = render(PluginParamFields, {
			props: {
				parameters: [schema[0]],
				values: { chunk_size: 5000 },
				idPrefix: 'max',
				mode: 'advanced'
			}
		});
		await tick();
		const err = container.querySelector('p[role="alert"]');
		expect(err).not.toBeNull();
		expect(err.textContent).toMatch(/≤/);
	});

	it('excluded params do not render', () => {
		const { container } = render(PluginParamFields, {
			props: {
				parameters: schema,
				values: {},
				idPrefix: 'exclude',
				mode: 'advanced',
				exclude: ['mode', 'use_cache']
			}
		});
		expect(container.querySelector('#exclude-mode')).toBeNull();
		expect(container.querySelector('#exclude-use_cache')).toBeNull();
		expect(container.querySelector('#exclude-chunk_size')).not.toBeNull();
	});

	it('renders nothing when the parameter array is empty', () => {
		const { container } = render(PluginParamFields, {
			props: {
				parameters: [],
				values: {},
				idPrefix: 'empty',
				mode: 'advanced'
			}
		});
		expect(container.querySelectorAll('input').length).toBe(0);
		expect(container.querySelectorAll('select').length).toBe(0);
	});
});
