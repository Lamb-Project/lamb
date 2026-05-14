import '@testing-library/jest-dom/vitest';
import { vi } from 'vitest';

// Node.js 22+ exposes a native (unconfigured) localStorage global that is
// undefined, which prevents jsdom from shadowing it. Polyfill it so stores
// that access localStorage at module-init time don't throw.
if (typeof localStorage === 'undefined' || localStorage === null) {
	const store = {};
	globalThis.localStorage = {
		getItem: (key) => store[key] ?? null,
		setItem: (key, value) => {
			store[key] = String(value);
		},
		removeItem: (key) => {
			delete store[key];
		},
		clear: () => {
			for (const k of Object.keys(store)) delete store[k];
		},
		get length() {
			return Object.keys(store).length;
		},
		key: (i) => Object.keys(store)[i] ?? null
	};
}

// required for svelte5 + jsdom as jsdom does not support matchMedia
Object.defineProperty(window, 'matchMedia', {
	writable: true,
	enumerable: true,
	value: vi.fn().mockImplementation((query) => ({
		matches: false,
		media: query,
		onchange: null,
		addEventListener: vi.fn(),
		removeEventListener: vi.fn(),
		dispatchEvent: vi.fn()
	}))
});

// add more mocks here if you need them
