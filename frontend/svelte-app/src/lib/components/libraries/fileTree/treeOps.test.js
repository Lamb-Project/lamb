import { describe, it, expect } from 'vitest';
import {
	buildTree,
	filterTree,
	flatten,
	isDescendant,
	isValidDropTarget,
	resolveUploadFolderId,
	splitSelection,
	highlightMatch,
	findNode,
	ancestorsOf,
	ROOT_KEY
} from './treeOps.js';

const FOLDER_F1 = { id: 'f1', name: 'Bravo', parent_folder_id: null };
const FOLDER_F2 = { id: 'f2', name: 'Alpha', parent_folder_id: null };
const FOLDER_F3 = { id: 'f3', name: 'Sub', parent_folder_id: 'f1' };
const FOLDER_F4 = { id: 'f4', name: 'Deep', parent_folder_id: 'f3' };
const ITEM_I1 = { id: 'i1', title: 'paper.pdf', folder_id: null };
const ITEM_I2 = { id: 'i2', title: 'notes.md', folder_id: 'f1' };
const ITEM_I3 = { id: 'i3', title: 'sub-doc.md', folder_id: 'f3' };

const PAYLOAD = {
	folders: [FOLDER_F1, FOLDER_F2, FOLDER_F3, FOLDER_F4],
	items: [ITEM_I1, ITEM_I2, ITEM_I3]
};

describe('buildTree', () => {
	it('places folders before items at each level', () => {
		const root = buildTree(PAYLOAD);
		// Root children: 2 folders (Alpha, Bravo) then 1 item (paper.pdf)
		expect(root.children.length).toBe(3);
		expect(root.children[0].kind).toBe('folder');
		expect(root.children[1].kind).toBe('folder');
		expect(root.children[2].kind).toBe('item');
	});

	it('sorts folders alphabetically (locale-aware)', () => {
		const root = buildTree(PAYLOAD);
		const folderNames = root.children.filter((c) => c.kind === 'folder').map((c) => c.name);
		expect(folderNames).toEqual(['Alpha', 'Bravo']);
	});

	it('nests folders correctly', () => {
		const root = buildTree(PAYLOAD);
		const bravo = root.children.find((c) => c.name === 'Bravo');
		expect(bravo).toBeDefined();
		// Bravo should contain: folder "Sub", then item "notes.md"
		expect(bravo.children.map((c) => c.name)).toEqual(['Sub', 'notes.md']);
		const sub = bravo.children.find((c) => c.kind === 'folder');
		expect(sub.children.map((c) => c.name)).toEqual(['Deep', 'sub-doc.md']);
	});

	it('handles empty payload', () => {
		const root = buildTree({ folders: [], items: [] });
		expect(root.children).toEqual([]);
		expect(root.descendantItemCount).toBe(0);
	});

	it('computes descendantItemCount correctly', () => {
		const root = buildTree(PAYLOAD);
		expect(root.descendantItemCount).toBe(3);
		const bravo = root.children.find((c) => c.name === 'Bravo');
		// Bravo contains notes.md + (Sub > sub-doc.md) = 2
		expect(bravo.descendantItemCount).toBe(2);
	});
});

describe('filterTree', () => {
	it('returns null for empty query', () => {
		const root = buildTree(PAYLOAD);
		expect(filterTree(root, '')).toBeNull();
		expect(filterTree(root, '   ')).toBeNull();
	});

	it('returns matching node + its ancestors', () => {
		const root = buildTree(PAYLOAD);
		const r = filterTree(root, 'sub-doc');
		expect(r).not.toBeNull();
		expect(r.visible.has('item:i3')).toBe(true);
		expect(r.visible.has('folder:f3')).toBe(true); // Sub
		expect(r.visible.has('folder:f1')).toBe(true); // Bravo
		expect(r.autoExpand.has('folder:f3')).toBe(true);
		expect(r.autoExpand.has('folder:f1')).toBe(true);
	});

	it('is diacritics-insensitive', () => {
		const root = buildTree({
			folders: [{ id: 'f', name: 'Català', parent_folder_id: null }],
			items: []
		});
		const r = filterTree(root, 'catala');
		expect(r.visible.has('folder:f')).toBe(true);
	});

	it('excludes non-matching siblings', () => {
		const root = buildTree(PAYLOAD);
		const r = filterTree(root, 'sub-doc');
		// Alpha (f2) and its absence should not appear
		expect(r.visible.has('folder:f2')).toBe(false);
	});
});

describe('flatten', () => {
	it('respects expand state', () => {
		const root = buildTree(PAYLOAD);
		const expanded = new Set(); // collapsed
		const flat = flatten(root, expanded, null);
		// Only top-level children show: Alpha, Bravo, paper.pdf
		expect(flat.map((n) => n.name)).toEqual(['Alpha', 'Bravo', 'paper.pdf']);
	});

	it('reveals children of expanded folders', () => {
		const root = buildTree(PAYLOAD);
		const expanded = new Set(['folder:f1']);
		const flat = flatten(root, expanded, null);
		expect(flat.map((n) => n.name)).toEqual(['Alpha', 'Bravo', 'Sub', 'notes.md', 'paper.pdf']);
	});

	it('honors visibleKeys filter', () => {
		const root = buildTree(PAYLOAD);
		const expanded = new Set(['folder:f1', 'folder:f3']);
		const visible = new Set(['folder:f1', 'folder:f3', 'item:i3']);
		const flat = flatten(root, expanded, visible);
		expect(flat.map((n) => n.name)).toEqual(['Bravo', 'Sub', 'sub-doc.md']);
	});
});

describe('isDescendant', () => {
	const root = buildTree(PAYLOAD);

	it('detects direct child', () => {
		expect(isDescendant(root, 'folder:f1', 'folder:f3')).toBe(true);
	});

	it('detects deep descendant', () => {
		expect(isDescendant(root, 'folder:f1', 'folder:f4')).toBe(true);
	});

	it('rejects unrelated subtree', () => {
		expect(isDescendant(root, 'folder:f2', 'folder:f4')).toBe(false);
	});
});

describe('isValidDropTarget', () => {
	const root = buildTree(PAYLOAD);

	it('allows dropping into a different folder', () => {
		expect(isValidDropTarget('folder:f2', ['item:i2'], root)).toBe(true);
	});

	it('rejects dropping into self', () => {
		expect(isValidDropTarget('folder:f1', ['folder:f1'], root)).toBe(false);
	});

	it('rejects dropping a folder into its descendant', () => {
		expect(isValidDropTarget('folder:f4', ['folder:f1'], root)).toBe(false);
	});

	it('rejects when target is not a folder', () => {
		expect(isValidDropTarget('item:i1', ['item:i2'], root)).toBe(false);
	});

	it('accepts root drop', () => {
		expect(isValidDropTarget(ROOT_KEY, ['item:i2'], root)).toBe(true);
	});
});

describe('resolveUploadFolderId', () => {
	const root = buildTree(PAYLOAD);

	it('returns null when nothing selected', () => {
		expect(resolveUploadFolderId(new Set(), root)).toBeNull();
	});

	it('returns null when multi-select', () => {
		expect(resolveUploadFolderId(new Set(['folder:f1', 'folder:f2']), root)).toBeNull();
	});

	it('returns folder id for a single-folder selection', () => {
		expect(resolveUploadFolderId(new Set(['folder:f1']), root)).toBe('f1');
	});

	it('returns the parent of a selected item', () => {
		// item i2 lives in folder f1
		expect(resolveUploadFolderId(new Set(['item:i2']), root)).toBe('f1');
	});

	it('returns null for a root-level item', () => {
		expect(resolveUploadFolderId(new Set(['item:i1']), root)).toBeNull();
	});
});

describe('splitSelection', () => {
	it('partitions item and folder keys', () => {
		const r = splitSelection(['item:a', 'folder:b', 'item:c']);
		expect(r.itemIds).toEqual(['a', 'c']);
		expect(r.folderIds).toEqual(['b']);
	});

	it('skips the synthetic root key', () => {
		const r = splitSelection([ROOT_KEY, 'item:a']);
		expect(r.folderIds).toEqual([]);
		expect(r.itemIds).toEqual(['a']);
	});
});

describe('highlightMatch', () => {
	it('returns one non-match chunk when no term', () => {
		expect(highlightMatch('hello', '')).toEqual([{ text: 'hello', match: false }]);
	});

	it('splits around a single match', () => {
		const chunks = highlightMatch('biology paper', 'paper');
		expect(chunks).toEqual([
			{ text: 'biology ', match: false },
			{ text: 'paper', match: true }
		]);
	});

	it('splits around multiple matches', () => {
		const chunks = highlightMatch('aba', 'a');
		expect(chunks.map((c) => c.match)).toEqual([true, false, true]);
	});

	it('is diacritics + case insensitive', () => {
		const chunks = highlightMatch('Català notes', 'catala');
		expect(chunks[0]).toEqual({ text: 'Català', match: true });
	});
});

describe('findNode + ancestorsOf', () => {
	const root = buildTree(PAYLOAD);

	it('finds a node by key', () => {
		expect(findNode(root, 'item:i3').name).toBe('sub-doc.md');
	});

	it('returns ancestor chain root-first', () => {
		const chain = ancestorsOf(root, 'item:i3');
		expect(chain.map((n) => n.name)).toEqual(['Bravo', 'Sub']);
	});

	it('returns empty for root-level node', () => {
		const chain = ancestorsOf(root, 'item:i1');
		expect(chain).toEqual([]);
	});
});
