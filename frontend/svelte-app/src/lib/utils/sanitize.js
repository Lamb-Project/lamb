/**
 * Markdown rendering with HTML sanitization.
 *
 * Wrap any `{@html …}` site that renders user/LLM/CMS-controlled markdown
 * with `renderMarkdownSafe()` so a stored XSS payload (e.g. `<script>`,
 * `<img onerror=…>`, `<iframe>`) cannot execute in another user's browser.
 *
 * DOMPurify is browser-only. The build is statically pre-rendered (adapter-static)
 * so SSR doesn't touch user content — but if a caller runs this in an SSR
 * context, fall back to returning the raw marked output rather than crashing.
 * (#353, M2)
 */

import { marked } from 'marked';
import DOMPurify from 'dompurify';
import { browser } from '$app/environment';

/**
 * Parse markdown to HTML and sanitize the result.
 * Use this anywhere you would otherwise write `{@html marked(text)}`.
 *
 * @param {string} text - Markdown source
 * @param {object} [options]
 * @param {boolean} [options.breaks=true] - Convert single newlines to <br>
 * @param {boolean} [options.gfm=true] - Enable GitHub-flavoured markdown
 * @returns {string} Sanitized HTML
 */
export function renderMarkdownSafe(text, options = {}) {
	if (!text) return '';
	const { breaks = true, gfm = true } = options;
	const html = String(marked.parse(text, { breaks, gfm }));
	if (!browser) return html;
	return DOMPurify.sanitize(html, {
		// Strip event handlers and javascript: URIs by default. Allow common
		// safe tags + class/id attrs so Tailwind prose styles still apply.
		USE_PROFILES: { html: true }
	});
}

/**
 * Sanitize a pre-built HTML string (no markdown parsing).
 * Use for HTML returned from a backend or third-party that you must render.
 *
 * @param {string} html
 * @returns {string}
 */
export function sanitizeHtml(html) {
	if (!html) return '';
	if (!browser) return html;
	return DOMPurify.sanitize(html, { USE_PROFILES: { html: true } });
}
