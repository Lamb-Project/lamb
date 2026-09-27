import { describe, test, expect } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/svelte';
import Page from './+page.svelte';

describe('/+page.svelte', () => {
	test('renders the login view for anonymous users', () => {
		render(Page);
		expect(screen.getByRole('heading', { level: 2, name: 'Login' })).toBeInTheDocument();
	});
});
