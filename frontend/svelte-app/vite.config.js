import tailwindcss from '@tailwindcss/vite';
import { svelteTesting } from '@testing-library/svelte/vite';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [tailwindcss(), sveltekit()],
	// Dev server proxy for API routes during local development
	// Allow overriding the proxy target via environment variable so the
	// containerized frontend can proxy to the backend service name (backend:9099)
	server: {
		proxy: {
			'/creator': {
				// Use PROXY_TARGET if set (e.g. http://backend:9099 inside docker),
				// otherwise default to localhost for host-based dev runs.
				target: process.env.PROXY_TARGET || 'http://localhost:9099',
				changeOrigin: true,
				secure: false
			},
			'/lamb': {
				target: process.env.PROXY_TARGET || 'http://localhost:9099',
				changeOrigin: true,
				secure: false
			},
			'/static': {
				target: process.env.PROXY_TARGET || 'http://localhost:9099',
				changeOrigin: true,
				secure: false
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
