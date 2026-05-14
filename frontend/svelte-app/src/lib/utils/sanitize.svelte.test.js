// Uses the `.svelte.` filename suffix to opt into the jsdom workspace
// (see vite.config.js test workspaces). The DOMPurify-dependent code paths
// in sanitize.js are no-ops outside a browser env, so jsdom is required to
// exercise them.

import { describe, it, expect } from 'vitest';
import { renderMarkdownSafe, renderMarkdownStrict } from './sanitize.js';

describe('renderMarkdownStrict — XSS hardening', () => {
	it('strips <script> tags', () => {
		const html = renderMarkdownStrict('Hello <script>alert(1)</script> world');
		expect(html).not.toContain('<script');
		expect(html).not.toContain('alert(1)');
	});

	it('strips onerror= and other event handler attributes', () => {
		const html = renderMarkdownStrict('<img src="x" onerror="alert(1)">');
		expect(html).not.toContain('onerror');
		expect(html).not.toContain('alert(1)');
	});

	it('strips <iframe>', () => {
		const html = renderMarkdownStrict('<iframe src="https://evil.example"></iframe>');
		expect(html).not.toContain('<iframe');
	});

	it('strips <form>, <button>, <input>, <style>', () => {
		const html = renderMarkdownStrict(
			'<form action="x"><input name="a"><button>go</button></form><style>body{}</style>'
		);
		expect(html).not.toContain('<form');
		expect(html).not.toContain('<input');
		expect(html).not.toContain('<button');
		expect(html).not.toContain('<style');
	});

	it('strips javascript: URIs from links', () => {
		// eslint-disable-next-line no-script-url
		const html = renderMarkdownStrict('[bad](javascript:alert(1))');
		expect(html).not.toContain('javascript:');
	});

	it('adds target="_blank" and rel="noopener noreferrer" to links', () => {
		const html = renderMarkdownStrict('[example](https://example.com)');
		expect(html).toContain('href="https://example.com"');
		expect(html).toContain('target="_blank"');
		expect(html).toContain('rel="noopener noreferrer"');
	});

	it('renders ordinary markdown structure (heading, list, code)', () => {
		const html = renderMarkdownStrict('# Title\n\n- one\n- two\n\n`code`');
		expect(html).toMatch(/<h1[^>]*>Title<\/h1>/);
		expect(html).toContain('<ul');
		expect(html).toContain('<li>one</li>');
		expect(html).toContain('<code>code</code>');
	});
});

describe('renderMarkdownSafe — regression', () => {
	it('still strips <script>', () => {
		const html = renderMarkdownSafe('<script>alert(1)</script>');
		expect(html).not.toContain('<script');
	});

	it('renders headings and links', () => {
		const html = renderMarkdownSafe('# Hello\n\n[a](https://example.com)');
		expect(html).toMatch(/<h1[^>]*>Hello<\/h1>/);
		expect(html).toContain('href="https://example.com"');
	});
});
