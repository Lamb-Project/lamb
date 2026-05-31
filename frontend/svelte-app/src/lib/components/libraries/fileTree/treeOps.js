/**
 * Pure helpers for the library file tree.
 *
 * The backend ships flat lists of folders + items. ``buildTree`` assembles
 * a nested tree the renderer can walk. Other helpers handle filtering,
 * flattening for keyboard navigation, drop-target validation, and the
 * upload-target resolution rule.
 *
 * @module treeOps
 */

/**
 * @typedef {Object} TreeNode
 * @property {string} key             - 'folder:<id>' | 'item:<id>' | 'folder:__root__'
 * @property {string} id              - raw id ('__root__' for the synthetic root)
 * @property {'folder'|'item'|'root'} kind
 * @property {string} name            - folder name or item title
 * @property {string|null} parentId
 * @property {TreeNode[]} children    - folders first, then items, both alphabetical
 * @property {Object} [raw]           - raw payload from the API (items only)
 * @property {number} descendantItemCount
 */

const ROOT_KEY = 'folder:__root__';
const COLLATOR = new Intl.Collator(undefined, { sensitivity: 'base' });

/** Lower-case + strip diacritics so filtering works for Catalan/Basque names. */
function normalize(s) {
	return String(s || '')
		.normalize('NFD')
		.replace(/\p{Diacritic}/gu, '')
		.toLowerCase();
}

/**
 * Build a nested ``TreeNode`` from the flat tree response.
 *
 * @param {{ folders: Array<object>, items: Array<object> }} payload
 * @returns {TreeNode} The synthetic root node.
 */
export function buildTree(payload) {
	const folders = Array.isArray(payload?.folders) ? payload.folders : [];
	const items = Array.isArray(payload?.items) ? payload.items : [];

	/** @type {Map<string|null, TreeNode[]>} */
	const folderChildren = new Map();
	/** @type {Map<string|null, TreeNode[]>} */
	const itemChildren = new Map();

	for (const f of folders) {
		const node = /** @type {TreeNode} */ ({
			key: `folder:${f.id}`,
			id: f.id,
			kind: 'folder',
			name: f.name || '',
			parentId: f.parent_folder_id ?? null,
			children: [],
			descendantItemCount: 0
		});
		const arr = folderChildren.get(node.parentId) || [];
		arr.push(node);
		folderChildren.set(node.parentId, arr);
	}

	for (const i of items) {
		const node = /** @type {TreeNode} */ ({
			key: `item:${i.id}`,
			id: i.id,
			kind: 'item',
			name: i.title || i.original_filename || i.id,
			parentId: i.folder_id ?? null,
			children: [],
			raw: i,
			descendantItemCount: 0
		});
		const arr = itemChildren.get(node.parentId) || [];
		arr.push(node);
		itemChildren.set(node.parentId, arr);
	}

	// Sort: folders alphabetical first, then items alphabetical.
	for (const arr of folderChildren.values()) {
		arr.sort((a, b) => COLLATOR.compare(a.name, b.name));
	}
	for (const arr of itemChildren.values()) {
		arr.sort((a, b) => COLLATOR.compare(a.name, b.name));
	}

	/** @param {string|null} parentId */
	const assemble = (parentId) => {
		const fc = folderChildren.get(parentId) || [];
		const ic = itemChildren.get(parentId) || [];
		for (const f of fc) f.children = assemble(f.id);
		return [...fc, ...ic];
	};

	const root = /** @type {TreeNode} */ ({
		key: ROOT_KEY,
		id: '__root__',
		kind: 'root',
		name: '',
		parentId: null,
		children: assemble(null),
		descendantItemCount: 0
	});

	// Compute descendantItemCount in one bottom-up walk.
	const computeCount = (/** @type {TreeNode} */ node) => {
		if (node.kind === 'item') {
			node.descendantItemCount = 1;
			return 1;
		}
		let sum = 0;
		for (const c of node.children) sum += computeCount(c);
		node.descendantItemCount = sum;
		return sum;
	};
	computeCount(root);

	return root;
}

/**
 * Filter the tree by a name query.
 *
 * Returns a set of node keys that should remain visible (matching nodes
 * AND their ancestor chain) plus a set of folder keys to auto-expand so
 * matches are revealed. Empty query returns ``null`` so callers can skip
 * the filter pass entirely.
 *
 * @param {TreeNode} root
 * @param {string} query
 * @returns {{ visible: Set<string>, autoExpand: Set<string> } | null}
 */
export function filterTree(root, query) {
	const q = normalize(query).trim();
	if (!q) return null;

	const visible = new Set();
	const autoExpand = new Set();

	/** @param {TreeNode} node @param {string[]} ancestors */
	const walk = (node, ancestors) => {
		const matches = node.kind !== 'root' && normalize(node.name).includes(q);
		let hasMatch = matches;
		for (const c of node.children) {
			if (walk(c, [...ancestors, node.key])) hasMatch = true;
		}
		if (hasMatch) {
			visible.add(node.key);
			for (const a of ancestors) {
				visible.add(a);
				if (a.startsWith('folder:')) autoExpand.add(a);
			}
		}
		return hasMatch;
	};
	walk(root, []);

	return { visible, autoExpand };
}

/**
 * Return the tree flattened to the linear order the user sees (folders
 * expanded into their children). Used for keyboard navigation and Shift+
 * click range selection.
 *
 * @param {TreeNode} root
 * @param {Set<string>} expandedKeys
 * @param {Set<string>|null} visibleKeys  if non-null, only keys in this set are included
 * @returns {TreeNode[]}
 */
export function flatten(root, expandedKeys, visibleKeys) {
	/** @type {TreeNode[]} */
	const out = [];
	/** @param {TreeNode} node */
	const walk = (node) => {
		if (node.kind !== 'root') {
			if (visibleKeys && !visibleKeys.has(node.key)) return;
			out.push(node);
		}
		if (node.kind === 'root' || (node.kind === 'folder' && expandedKeys.has(node.key))) {
			for (const c of node.children) walk(c);
		}
	};
	walk(root);
	return out;
}

/**
 * Return true if ``candidateKey`` lives in the subtree rooted at
 * ``ancestorKey``.
 *
 * @param {TreeNode} root
 * @param {string} ancestorKey  must be a folder key
 * @param {string} candidateKey
 */
export function isDescendant(root, ancestorKey, candidateKey) {
	/** @param {TreeNode} node */
	const find = (node) => {
		if (node.key === ancestorKey) return node;
		for (const c of node.children) {
			const r = find(c);
			if (r) return r;
		}
		return null;
	};
	const sub = find(root);
	if (!sub) return false;
	/** @param {TreeNode} node */
	const has = (node) => {
		if (node.key === candidateKey) return true;
		return node.children.some(has);
	};
	return sub.children.some(has);
}

/**
 * Validate that ``draggedKeys`` can be dropped onto ``targetKey``.
 *
 * @param {string} targetKey  folder key or the synthetic root key
 * @param {string[]} draggedKeys
 * @param {TreeNode} root
 */
export function isValidDropTarget(targetKey, draggedKeys, root) {
	if (!targetKey.startsWith('folder:')) return false; // root key starts with 'folder:__root__'
	if (draggedKeys.length === 0) return false;
	if (draggedKeys.includes(targetKey)) return false;
	for (const k of draggedKeys) {
		if (k.startsWith('folder:') && k !== ROOT_KEY) {
			if (isDescendant(root, k, targetKey)) return false;
		}
	}
	return true;
}

/**
 * Compute the folder id new uploads should land under, given the current
 * selection. Rules:
 *
 *  - exactly one folder selected → that folder
 *  - exactly one item selected → its parent (or root)
 *  - else → root (null)
 *
 * @param {Set<string>} selectedIds  set of node keys
 * @param {TreeNode} root
 * @returns {string|null}
 */
export function resolveUploadFolderId(selectedIds, root) {
	if (!selectedIds || selectedIds.size !== 1) return null;
	const [only] = selectedIds;
	if (only === ROOT_KEY) return null;
	if (only.startsWith('folder:')) return only.slice('folder:'.length);
	if (only.startsWith('item:')) {
		// Find the item and return its parent
		/** @param {TreeNode} node */
		const find = (node) => {
			if (node.key === only) return node;
			for (const c of node.children) {
				const r = find(c);
				if (r) return r;
			}
			return null;
		};
		const item = find(root);
		return item ? item.parentId : null;
	}
	return null;
}

/**
 * Split a selection set into item ids and folder ids.
 *
 * @param {Iterable<string>} selectedKeys
 */
export function splitSelection(selectedKeys) {
	const itemIds = [];
	const folderIds = [];
	for (const k of selectedKeys) {
		if (k.startsWith('item:')) itemIds.push(k.slice('item:'.length));
		else if (k.startsWith('folder:') && k !== ROOT_KEY) folderIds.push(k.slice('folder:'.length));
	}
	return { itemIds, folderIds };
}

/**
 * Highlight matching substrings as ``<mark>`` chunks without touching innerHTML.
 *
 * @param {string} text
 * @param {string} term  raw search term (case + diacritics insensitive match)
 * @returns {Array<{ text: string, match: boolean }>}
 */
export function highlightMatch(text, term) {
	if (!term) return [{ text, match: false }];
	const normName = normalize(text);
	const normTerm = normalize(term).trim();
	if (!normTerm) return [{ text, match: false }];
	const chunks = [];
	let cursor = 0;
	let idx = normName.indexOf(normTerm, cursor);
	while (idx !== -1) {
		if (idx > cursor) chunks.push({ text: text.slice(cursor, idx), match: false });
		chunks.push({ text: text.slice(idx, idx + normTerm.length), match: true });
		cursor = idx + normTerm.length;
		idx = normName.indexOf(normTerm, cursor);
	}
	if (cursor < text.length) chunks.push({ text: text.slice(cursor), match: false });
	return chunks;
}

/**
 * Find a node in the tree by key.
 *
 * @param {TreeNode} root
 * @param {string} key
 * @returns {TreeNode|null}
 */
export function findNode(root, key) {
	if (root.key === key) return root;
	for (const c of root.children) {
		const r = findNode(c, key);
		if (r) return r;
	}
	return null;
}

/**
 * Return the ancestor chain (excluding the root) for ``key``, root-first.
 *
 * @param {TreeNode} root
 * @param {string} key
 * @returns {TreeNode[]}
 */
export function ancestorsOf(root, key) {
	/**
	 * @param {TreeNode} node
	 * @param {TreeNode[]} acc
	 * @returns {TreeNode[]|null}
	 */
	const walk = (node, acc) => {
		if (node.key === key) return acc;
		for (const c of node.children) {
			const r = walk(c, [...acc, node]);
			if (r) return r;
		}
		return null;
	};
	const chain = walk(root, []);
	return (chain || []).filter((n) => n.kind !== 'root');
}

export { ROOT_KEY };
