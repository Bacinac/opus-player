import nodeAdapter from '@sveltejs/adapter-node';
import staticAdapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vitest/config';
import { csp } from './src/lib/opus/csp.js';

// the hostname a tunnel publishes this dev server at, when it is opened from
// beyond the LAN; hot reload then comes back over the tunnel's TLS as well
const devHost = process.env.OPUS_DEV_HOST;
const demo = process.env.OPUS_DEMO === '1';

export default defineConfig({
	plugins: [
		sveltekit({
			preprocess: vitePreprocess(),
			adapter: demo
				? staticAdapter({ fallback: 'index.html', precompress: true, strict: true })
				: nodeAdapter(),
			files: demo ? { appTemplate: 'src/app.demo.html' } : {},
			...(demo ? {} : { csp })
		})
	],
	resolve: process.env.VITEST ? { conditions: ['browser'] } : undefined,
	test: {
		include: ['src/**/*.test.ts'],
		environmentOptions: { happyDOM: { url: 'http://tv.test/' } }
	},
	server: {
		host: '0.0.0.0',
		port: 5173,
		allowedHosts: [...(devHost ? [devHost] : []), 'localhost', '.local'],
		proxy: {
			'/api': 'http://backend:8098'
		},
		hmr: devHost ? { host: devHost, clientPort: 443, protocol: 'wss' } : undefined
	}
});
