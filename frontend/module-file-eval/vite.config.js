import tailwindcss from '@tailwindcss/vite';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [tailwindcss(), sveltekit()],
	optimizeDeps: {
		include: ['svelte', 'svelte-i18n'],
		exclude: ['@sveltejs/kit']
	},
	ssr: {
		noExternal: ['svelte-i18n']
	},
	server: {
		host: '0.0.0.0',
		port: 5174,
		proxy: {
			'/creator': {
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
			}
		}
	}
});
