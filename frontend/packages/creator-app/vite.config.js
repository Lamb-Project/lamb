import tailwindcss from '@tailwindcss/vite';
import { svelteTesting } from '@testing-library/svelte/vite';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [tailwindcss(), sveltekit()],
	// Ensure Svelte and related packages are properly pre-bundled to avoid
	// "lifecycle_outside_component" errors from duplicate Svelte instances
	optimizeDeps: {
		include: ['svelte', 'svelte-i18n', 'flowbite-svelte', 'flowbite-svelte-icons'],
		exclude: ['@sveltejs/kit']
	},
	ssr: {
		noExternal: ['svelte-i18n']
	},
	// Dev server proxy for API routes during local development
	// Allow overriding the proxy target via environment variable so the
	// containerized frontend can proxy to the backend service name (backend:9099)
	server: {
		host: '0.0.0.0',
		proxy: {
			'/creator': {
				// Use PROXY_TARGET if set (e.g. http://backend:9099 inside docker),
				// otherwise default to localhost for host-based dev runs.
				target: 'http://backend:9099',
				changeOrigin: true,
				secure: false,
				rewrite: (path) => path
			},
			'/lamb': {
				target: 'http://backend:9099',
				changeOrigin: true,
				secure: false,
				rewrite: (path) => path
			},
			'/static': {
				target: 'http://backend:9099',
				changeOrigin: true,
				secure: false,
				rewrite: (path) => path
			}
		}
	},
	test: {
		workspace: [
			{
				extends: './vite.config.js',
				plugins: [svelteTesting()],
				test: {
					name: 'client',
					environment: 'jsdom',
					clearMocks: true,
					include: ['src/**/*.svelte.{test,spec}.{js,ts}'],
					exclude: ['src/lib/server/**'],
					setupFiles: ['./vitest-setup-client.js']
				}
			},
			{
				extends: './vite.config.js',
				test: {
					name: 'server',
					environment: 'node',
					include: ['src/**/*.{test,spec}.{js,ts}'],
					exclude: ['src/**/*.svelte.{test,spec}.{js,ts}']
				}
			}
		]
	}
});
