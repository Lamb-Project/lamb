import { describe, test, expect } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/svelte';
import Page from './+page.svelte';

describe('/+page.svelte', () => {
	test('should mount page shell', () => {
		render(Page);
		// h1 only renders for authenticated users; assert the always-rendered
		// LAMB brand heading mounts.
		expect(screen.getByRole('heading', { level: 2, name: /LAMB/i })).toBeInTheDocument();
	});
});
