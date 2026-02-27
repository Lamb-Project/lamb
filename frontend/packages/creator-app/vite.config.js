import tailwindcss from '@tailwindcss/vite';
import { svelteTesting } from '@testing-library/svelte/vite';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [tailwindcss(), sveltekit()],
	optimizeDeps: {
		include: [
			'svelte',
			'svelte-i18n',
			'@lamb/ui',
			'flowbite-svelte',
			'flowbite-svelte-icons'
		],
		exclude: ['@sveltejs/kit']
	},
	ssr: {
		noExternal: ['svelte-i18n', '@lamb/ui']
	},
	server: {
		proxy: {
			'/creator': {
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
					include: ['src/**/*.svelte.{test,spec}.{js,ts}']
				}
			}
		]
	}
});
