/**
 * Markdown + LaTeX rendering with HTML sanitization.
 *
 * Combines the unified/remark/rehype pipeline for markdown-to-HTML
 * conversion with KaTeX for LaTeX math rendering, then sanitizes
 * the output with DOMPurify.
 *
 * Use `renderMarkdownWithMath()` anywhere you would previously write
 * `{@html marked(text)}` to also get rendered LaTeX formulas.
 *
 * DOMPurify is browser-only. The build is statically pre-rendered
 * (adapter-static) so SSR doesn't touch user content — but if a
 * caller runs this in an SSR context, fall back to returning the
 * raw unified output rather than crashing.
 */

import { unified } from 'unified';
import remarkParse from 'remark-parse';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import remarkRehype from 'remark-rehype';
import rehypeKatex from 'rehype-katex';
import rehypeStringify from 'rehype-stringify';
import DOMPurify from 'dompurify';
import { browser } from '$app/environment';
import 'katex/dist/katex.min.css';

/**
 * Parse markdown with LaTeX math to sanitized HTML.
 *
 * @param {string} text - Markdown source (may contain $$...$$ and $...$ LaTeX)
 * @returns {string} Sanitized HTML with rendered math
 */
export function renderMarkdownWithMath(text) {
	if (!text) return '';

	const html = String(
		unified()
			.use(remarkParse)
			.use(remarkGfm)
			.use(remarkMath)
			.use(remarkRehype)
			.use(rehypeKatex)
			.use(rehypeStringify)
			.processSync(text)
	);

	if (!browser) return html;
	return DOMPurify.sanitize(html, {
		USE_PROFILES: { html: true },
		ADD_ATTR: ['class', 'style'] // KaTeX uses inline styles and classes for math rendering
	});
}
