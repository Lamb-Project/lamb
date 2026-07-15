import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	preprocess: vitePreprocess(),

	kit: {
		adapter: adapter({
			pages: '../../build/m/file-eval',
			assets: '../../build/m/file-eval',
			fallback: 'index.html',
			precompress: false,
			strict: false
		}),
		paths: {
			base: '/m/file-eval',
			relative: false
		},
		appDir: 'app'
	}
};

export default config;
