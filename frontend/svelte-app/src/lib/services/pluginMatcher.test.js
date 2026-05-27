import { describe, it, expect } from 'vitest';
import { matchPluginsForFile, fileExtension } from './pluginMatcher.js';

const PLUGINS = [
	{ name: 'simple_import', file_extensions: ['txt', 'md', 'html', 'htm'] },
	{ name: 'markitdown_import', file_extensions: ['pdf', 'docx', 'doc'] },
	{ name: 'markitdown_plus_import', file_extensions: ['pdf', 'docx', 'doc'] },
	{ name: 'url_import', file_extensions: [] },
	{ name: 'youtube_transcript_import', file_extensions: [] }
];

describe('fileExtension', () => {
	it('returns the lowercase extension', () => {
		expect(fileExtension('report.PDF')).toBe('pdf');
	});

	it('returns empty for no extension', () => {
		expect(fileExtension('README')).toBe('');
	});

	it('returns empty for trailing dot', () => {
		expect(fileExtension('weird.')).toBe('');
	});

	it('returns empty for empty / non-string input', () => {
		expect(fileExtension('')).toBe('');
		// @ts-expect-error intentional bad input
		expect(fileExtension(undefined)).toBe('');
	});

	it('uses the last dot for multi-dot names', () => {
		expect(fileExtension('archive.tar.gz')).toBe('gz');
	});
});

describe('matchPluginsForFile', () => {
	it('returns the single matching plugin for plain-text', () => {
		const matches = matchPluginsForFile({ name: 'notes.md' }, PLUGINS);
		expect(matches).toHaveLength(1);
		expect(matches[0].name).toBe('simple_import');
	});

	it('returns both Markitdown variants for PDFs (multi-match)', () => {
		const matches = matchPluginsForFile({ name: 'paper.pdf' }, PLUGINS);
		expect(matches.map((p) => p.name).sort()).toEqual(
			['markitdown_import', 'markitdown_plus_import'].sort()
		);
	});

	it('matches case-insensitively', () => {
		const matches = matchPluginsForFile({ name: 'paper.PDF' }, PLUGINS);
		expect(matches.map((p) => p.name).sort()).toEqual(
			['markitdown_import', 'markitdown_plus_import'].sort()
		);
	});

	it('tolerates leading dots in declared extensions', () => {
		const plugins = [{ name: 'p', file_extensions: ['.txt'] }];
		expect(matchPluginsForFile({ name: 'a.txt' }, plugins)).toHaveLength(1);
	});

	it('returns no matches for an unknown extension', () => {
		const matches = matchPluginsForFile({ name: 'image.xyz' }, PLUGINS);
		expect(matches).toEqual([]);
	});

	it('returns no matches when the file has no extension', () => {
		const matches = matchPluginsForFile({ name: 'README' }, PLUGINS);
		expect(matches).toEqual([]);
	});

	it('accepts a plain filename string', () => {
		const matches = matchPluginsForFile('notes.txt', PLUGINS);
		expect(matches).toHaveLength(1);
		expect(matches[0].name).toBe('simple_import');
	});

	it('returns empty when plugins list is missing or empty', () => {
		expect(matchPluginsForFile({ name: 'a.pdf' }, [])).toEqual([]);
		// @ts-expect-error intentional bad input
		expect(matchPluginsForFile({ name: 'a.pdf' }, null)).toEqual([]);
	});

	it('excludes plugins with no declared extensions (URL / YouTube)', () => {
		// An ".html" file matches simple_import but not url_import.
		const matches = matchPluginsForFile({ name: 'page.html' }, PLUGINS);
		expect(matches.map((p) => p.name)).toEqual(['simple_import']);
	});
});
