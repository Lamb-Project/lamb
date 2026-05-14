// Regression test for #370: when the user changes libraries quickly, a
// stale getItems() response must not overwrite items belonging to the
// currently-selected library. The component uses an incrementing
// sequence number (`loadSeq` + `mySeq`) to discard out-of-order responses.
//
// Rather than render the component (Svelte 5 + jsdom + $effect timing
// makes this brittle), we lock in the source-level contract: the guard
// must remain in place. A future edit that removes it fails this test
// loud and clear with a traceable line number.

import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(join(__dirname, 'StepKSContent.svelte'), 'utf8');

describe('StepKSContent — race-guard contract', () => {
	it('declares a load-sequence counter', () => {
		expect(source).toMatch(/let loadSeq = 0/);
	});

	it('captures the current sequence id before awaiting getItems', () => {
		// `const mySeq = ++loadSeq;` MUST appear in loadItems before the await.
		const fn = source.split('async function loadItems(libraryId)')[1] || '';
		const beforeAwait = fn.split('await getItems(')[0] || '';
		expect(beforeAwait).toMatch(/const mySeq = \+\+loadSeq/);
	});

	it('discards stale responses on the success path', () => {
		expect(source).toMatch(
			/await getItems\([^)]+\);[\s\n]*if \(mySeq !== loadSeq\) return;/
		);
	});

	it('discards stale errors on the failure path', () => {
		expect(source).toMatch(/catch[\s\S]{1,80}if \(mySeq !== loadSeq\) return;/);
	});

	it('only clears loading when this is the latest request', () => {
		expect(source).toMatch(/if \(mySeq === loadSeq\) loading = false;/);
	});
});
