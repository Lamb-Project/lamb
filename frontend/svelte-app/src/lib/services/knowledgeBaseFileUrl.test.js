import { describe, it, expect } from 'vitest';
import { knowledgeBaseFileUrl } from './knowledgeBaseFileUrl';

describe('legacy KB static URL joining', () => {
    it('repairs the Heavy file link without altering its target', () => {
        expect(knowledgeBaseFileUrl('http://localhost:19090//static/1/monday_test/file.md')).toBe('http://localhost:19090/static/1/monday_test/file.md');
    });
    it('preserves reverse-proxy prefixes and encoded filenames, queries and fragments', () => {
        expect(knowledgeBaseFileUrl('https://example.test/kb//static/1/file%20name.md?next=a//b#section')).toBe('https://example.test/kb/static/1/file%20name.md?next=a//b#section');
    });
    it('leaves working links and unrelated paths unchanged', () => {
        for (const value of ['https://example.test/kb/static/f.md', 'https://example.test/a//b', '/static/a.md', undefined, 'not a URL']) {
            expect(knowledgeBaseFileUrl(value)).toBe(value);
        }
    });
});
