<!--
  @component SigmaGraphModal
  Full-screen Sigma.js visualization of a Knowledge Store's graph.

  Renders concept + document + chunk nodes with all edges (RELATES_TO,
  MENTIONS, DOCUMENT_MENTIONS, CONTAINS). Initial positions are seeded
  by node type so ForceAtlas2 converges to a readable shape quickly.
  Hovering or clicking a node highlights its 1-hop neighborhood and
  dims the rest via Sigma's node/edge reducers.

  Mirrors the explorer behaviour from the legacy
  KnowledgeBaseGraphView.svelte but as a full-screen modal scoped to
  the new Knowledge Store surface.
-->
<script>
	import { onMount, onDestroy, tick } from 'svelte';
	import { getGraphSnapshot } from '$lib/services/graphService';

	/** @type {{ ksId: string, open: boolean, onclose: () => void }} */
	let { ksId, open, onclose } = $props();

	let container = $state(/** @type {HTMLDivElement | null} */ (null));
	let renderer = /** @type {any} */ (null);
	let graphInstance = /** @type {any} */ (null);
	let nodeLookup = /** @type {Map<string, any>} */ (new Map());
	let edgeLookup = /** @type {Map<string, any>} */ (new Map());
	let neighborIndex = /** @type {Map<string, Set<string>>} */ (new Map());

	let loading = $state(false);
	let error = $state('');
	let stats = $state({ nodes: 0, edges: 0, relatesEdges: 0 });
	let search = $state('');
	let selectedNodeId = $state('');
	let selectedNodeAttrs = $state(/** @type {any} */ (null));
	let hoveredNodeId = $state('');

	const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5));
	const HIGHLIGHT_COLOR = '#1d4ed8';
	const DIM_COLOR = '#e2e8f0';

	function colorForNode(/** @type {any} */ node) {
		if (node.type === 'document') return '#4f46e5';
		if (node.type === 'chunk') return '#f59e0b';
		const state = String(node.data?.verification_state || '').toLowerCase();
		if (state === 'verified') return '#22c55e';
		if (state === 'rejected') return '#dc2626';
		if (state === 'needs_review') return '#d97706';
		return '#2271b3';
	}

	function sizeForNode(/** @type {any} */ node) {
		if (node.type === 'document') return 8;
		if (node.type === 'chunk') return 5.5;
		const chunks = Math.max(1, Number(node.data?.chunk_count || 1));
		return Math.min(13, 7 + Math.log2(chunks));
	}

	function labelForNode(/** @type {any} */ node) {
		const raw = String(node.label || node.id).replace(/^[a-z]+:/i, '');
		const cap = node.type === 'chunk' ? 22 : 38;
		return raw.length > cap ? raw.slice(0, cap - 1) + '…' : raw;
	}

	function colorForEdge(/** @type {any} */ edge) {
		const t = String(edge.type || '').toUpperCase();
		if (t === 'RELATES_TO') return '#475569';
		if (t === 'CONTAINS') return '#94a3b8';
		if (t === 'DOCUMENT_MENTIONS') return '#7c3aed';
		if (t === 'MENTIONS') return '#d97706';
		return '#cbd5e1';
	}

	function sizeForEdge(/** @type {any} */ edge) {
		const t = String(edge.type || '').toUpperCase();
		if (t === 'RELATES_TO') return 1.6;
		if (t === 'CONTAINS') return 0.9;
		return 0.7;
	}

	function labelForEdge(/** @type {any} */ edge) {
		if (String(edge.type).toUpperCase() !== 'RELATES_TO') return '';
		return String(edge.data?.relation || edge.label || '').slice(0, 26);
	}

	// Phyllotaxis (golden-angle) spiral seed for concept-only graphs.
	// Spreads nodes evenly across the plane so ForceAtlas2 doesn't have
	// to untangle a degenerate starting configuration.
	function initialPositions(/** @type {any[]} */ nodes) {
		const positions = /** @type {Map<string, {x: number, y: number}>} */ (new Map());
		const ordered = [...nodes].sort((a, b) =>
			String(a.label || a.id).localeCompare(String(b.label || b.id)),
		);
		ordered.forEach((n, i) => {
			const distance = Math.sqrt(i + 1) * 2.2;
			const angle = i * GOLDEN_ANGLE;
			positions.set(String(n.id), {
				x: Math.cos(angle) * distance,
				y: Math.sin(angle) * distance,
			});
		});
		return positions;
	}

	function jitter(/** @type {string} */ value, /** @type {number} */ salt) {
		const text = `${value}:${salt}`;
		let hash = 0;
		for (let i = 0; i < text.length; i++) hash = (hash * 31 + text.charCodeAt(i)) >>> 0;
		return (hash % 1000) / 1000 - 0.5;
	}

	function normalizePositions(/** @type {any} */ graph) {
		let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
		graph.forEachNode((/** @type {string} */ _, /** @type {any} */ a) => {
			minX = Math.min(minX, a.x); maxX = Math.max(maxX, a.x);
			minY = Math.min(minY, a.y); maxY = Math.max(maxY, a.y);
		});
		if (![minX, maxX, minY, maxY].every(Number.isFinite)) return;
		const cx = (minX + maxX) / 2;
		const cy = (minY + maxY) / 2;
		const scale = Math.max(maxX - minX, maxY - minY, 1);
		graph.forEachNode((/** @type {string} */ n, /** @type {any} */ a) => {
			graph.mergeNodeAttributes(n, {
				x: ((a.x - cx) / scale) * 0.9 + 0.5,
				y: ((a.y - cy) / scale) * 0.9 + 0.5,
			});
		});
	}

	function buildNeighborIndex(/** @type {any[]} */ edges) {
		const index = /** @type {Map<string, Set<string>>} */ (new Map());
		for (const e of edges) {
			const s = String(e.source), t = String(e.target);
			if (!index.has(s)) index.set(s, new Set());
			if (!index.has(t)) index.set(t, new Set());
			index.get(s).add(t);
			index.get(t).add(s);
		}
		return index;
	}

	async function loadGraph() {
		loading = true;
		error = '';
		try {
			const [graphologyMod, sigmaMod, layoutMod] = await Promise.all([
				import('graphology'),
				import('sigma'),
				import('graphology-layout-forceatlas2'),
			]);
			const MultiDirectedGraph =
				graphologyMod.MultiDirectedGraph || graphologyMod.default;
			const Sigma = sigmaMod.default;
			const forceAtlas2 = layoutMod.default || layoutMod;

			const snap = await getGraphSnapshot(ksId, {
				limit: 5000,
				include_chunks: 'false',
			});
			// Concepts + RELATES_TO only. Documents and chunks are
			// available in the underlying graph but cluttered the view;
			// the Files tab is the right surface for inspecting them.
			const nodes = (snap?.nodes || []).filter(
				(/** @type {any} */ n) => n.type === 'concept',
			);
			const conceptIds = new Set(nodes.map((/** @type {any} */ n) => String(n.id)));
			const edges = (snap?.edges || []).filter(
				(/** @type {any} */ e) =>
					String(e.type).toUpperCase() === 'RELATES_TO' &&
					conceptIds.has(String(e.source)) &&
					conceptIds.has(String(e.target)),
			);

			nodeLookup = new Map(nodes.map((/** @type {any} */ n) => [String(n.id), n]));
			edgeLookup = new Map();
			neighborIndex = buildNeighborIndex(edges);

			const g = new MultiDirectedGraph();
			const positions = initialPositions(nodes);
			for (const n of nodes) {
				const id = String(n.id);
				const pos = positions.get(id) || { x: 0, y: 0 };
				g.addNode(id, {
					label: labelForNode(n),
					x: pos.x,
					y: pos.y,
					size: sizeForNode(n),
					color: colorForNode(n),
					nodeType: n.type,
					forceLabel: n.type === 'concept',
					zIndex: n.type === 'concept' ? 3 : n.type === 'document' ? 2 : 1,
				});
			}
			const seen = new Set();
			let relatesCount = 0;
			for (const e of edges) {
				const s = String(e.source), t = String(e.target);
				if (!g.hasNode(s) || !g.hasNode(t)) continue;
				const key = String(e.id || `${s}->${t}->${e.type}`);
				if (seen.has(key)) continue;
				seen.add(key);
				edgeLookup.set(key, e);
				if (String(e.type).toUpperCase() === 'RELATES_TO') relatesCount++;
				try {
					g.addDirectedEdgeWithKey(key, s, t, {
						label: labelForEdge(e),
						size: sizeForEdge(e),
						color: colorForEdge(e),
						edgeType: e.type,
						zIndex: String(e.type).toUpperCase() === 'RELATES_TO' ? 2 : 1,
					});
				} catch {
					// Duplicate edge key — skip silently.
				}
			}

			// Tuned ForceAtlas2: barnes-hut for large graphs, scaled
			// gravity / slowDown to keep the layout readable without
			// being too tight.
			if (g.order > 1) {
				const inferred =
					typeof forceAtlas2.inferSettings === 'function'
						? forceAtlas2.inferSettings(g)
						: {};
				forceAtlas2.assign(g, {
					iterations: 260,
					settings: {
						...inferred,
						barnesHutOptimize: g.order > 80,
						scalingRatio: 22,
						gravity: 0.7,
						slowDown: 8,
						strongGravityMode: false,
					},
				});
				normalizePositions(g);
			}

			stats = { nodes: g.order, edges: g.size, relatesEdges: relatesCount };

			if (renderer) renderer.kill();
			if (!container) return;
			renderer = new Sigma(g, container, {
				allowInvalidContainer: true,
				zIndex: true,
				renderEdgeLabels: true,
				enableEdgeClickEvents: true,
				enableEdgeHoverEvents: true,
				labelDensity: 0.45,
				labelGridCellSize: 96,
				labelRenderedSizeThreshold: 9,
				labelFont: 'Inter, ui-sans-serif, system-ui, sans-serif',
				labelSize: 12,
				labelWeight: '600',
				edgeLabelSize: 10,
				edgeLabelWeight: '600',
				defaultEdgeColor: '#94a3b8',
				defaultNodeColor: '#2271b3',
				minCameraRatio: 0.05,
				maxCameraRatio: 10,
			});
			graphInstance = g;
			attachEvents();
			applyReducers();
		} catch (/** @type {*} */ err) {
			console.error(err);
			error = err?.response?.data?.detail || err?.message || 'Failed to load graph';
		} finally {
			loading = false;
		}
	}

	function attachEvents() {
		if (!renderer) return;
		renderer.on('enterNode', ({ node }) => {
			hoveredNodeId = String(node);
			applyReducers();
		});
		renderer.on('leaveNode', () => {
			hoveredNodeId = '';
			applyReducers();
		});
		renderer.on('clickNode', ({ node }) => {
			selectedNodeId = String(node);
			selectedNodeAttrs = nodeLookup.get(selectedNodeId) || null;
			applyReducers();
		});
		renderer.on('clickStage', () => {
			selectedNodeId = '';
			selectedNodeAttrs = null;
			applyReducers();
		});
	}

	// Highlight focused-node + 1-hop neighbors, dim the rest. Called on
	// hover, click, and after the initial render.
	function applyReducers() {
		if (!renderer) return;
		const focusId = hoveredNodeId || selectedNodeId || '';
		const focus = focusId ? new Set([focusId, ...(neighborIndex.get(focusId) || [])]) : null;

		renderer.setSetting(
			'nodeReducer',
			(/** @type {string} */ key, /** @type {any} */ data) => {
				if (!focus) return data;
				if (focus.has(key)) {
					return {
						...data,
						color: key === focusId ? HIGHLIGHT_COLOR : data.color,
						size: key === focusId ? data.size + 2.5 : data.size + 0.5,
						zIndex: 10,
						forceLabel: true,
					};
				}
				return { ...data, color: DIM_COLOR, label: '', zIndex: 0 };
			},
		);

		renderer.setSetting(
			'edgeReducer',
			(/** @type {string} */ key, /** @type {any} */ data) => {
				if (!focus) return data;
				const edge = edgeLookup.get(key);
				if (!edge) return data;
				const s = String(edge.source), t = String(edge.target);
				const touchesFocus = focus.has(s) && focus.has(t);
				if (touchesFocus) {
					return { ...data, color: HIGHLIGHT_COLOR, size: data.size + 1.5, zIndex: 9 };
				}
				return { ...data, color: '#f1f5f9', size: Math.max(0.3, data.size * 0.5), label: '' };
			},
		);
		renderer.refresh();
	}

	function findAndCenter() {
		if (!renderer || !graphInstance || !search.trim()) return;
		const needle = search.trim().toLowerCase();
		let match = '';
		graphInstance.forEachNode((/** @type {string} */ key, /** @type {any} */ a) => {
			if (match) return;
			if (String(a.label || '').toLowerCase().includes(needle)) match = key;
		});
		if (!match) return;
		const attrs = graphInstance.getNodeAttributes(match);
		renderer.getCamera().animate({ x: attrs.x, y: attrs.y, ratio: 0.2 }, { duration: 500 });
		selectedNodeId = match;
		selectedNodeAttrs = nodeLookup.get(match) || null;
		applyReducers();
	}

	function handleKey(/** @type {KeyboardEvent} */ e) {
		if (!open) return;
		if (e.key === 'Escape') onclose();
		if (e.key === 'Enter' && document.activeElement?.id === 'sigma-search') {
			findAndCenter();
		}
	}

	$effect(() => {
		if (open && container && !renderer && !loading) {
			void loadGraph();
		}
	});

	onMount(() => {
		window.addEventListener('keydown', handleKey);
	});

	onDestroy(() => {
		window.removeEventListener('keydown', handleKey);
		if (renderer) renderer.kill();
		renderer = null;
		graphInstance = null;
	});
</script>

{#if open}
	<div class="fixed inset-0 z-50 flex flex-col bg-white" role="dialog" aria-modal="true">
		<header class="flex flex-wrap items-center gap-3 border-b border-gray-200 px-4 py-2">
			<h2 class="text-base font-semibold text-gray-900">Knowledge Graph</h2>
			<div class="text-xs text-gray-500">
				{stats.nodes} concepts · {stats.edges} relationships
			</div>
			<div class="ml-auto flex items-center gap-2">
				<input
					id="sigma-search"
					type="text"
					bind:value={search}
					placeholder="Find a concept (Enter to center)"
					class="rounded border border-gray-300 px-2 py-1 text-sm"
				/>
				<button
					type="button"
					class="rounded bg-[#2271b3] px-3 py-1 text-sm text-white hover:bg-[#1a5a90]"
					onclick={findAndCenter}
				>Find</button>
				<button
					type="button"
					class="rounded border border-gray-300 px-3 py-1 text-sm hover:bg-gray-100"
					onclick={onclose}
				>Close</button>
			</div>
		</header>

		{#if loading}
			<div class="flex flex-1 items-center justify-center text-sm text-gray-500">
				Loading graph (this may take a moment for large knowledge stores)…
			</div>
		{:else if error}
			<div class="flex flex-1 items-center justify-center text-sm text-red-600">
				{error}
			</div>
		{/if}

		<div bind:this={container} class="relative flex-1 w-full" style="background: #f8fafc">
			<!-- Legend (bottom-left, overlaid on canvas). -->
			<div class="absolute bottom-4 left-4 rounded-md border border-gray-300 bg-white/95 p-3 text-xs shadow-md">
				<div class="mb-1 font-semibold text-gray-700">Legend</div>
				<div class="flex flex-col gap-1">
					<div class="flex items-center gap-2">
						<span class="inline-block h-3 w-3 rounded-full" style="background:#22c55e"></span>
						Approved
					</div>
					<div class="flex items-center gap-2">
						<span class="inline-block h-3 w-3 rounded-full" style="background:#2271b3"></span>
						Unverified
					</div>
					<div class="flex items-center gap-2">
						<span class="inline-block h-3 w-3 rounded-full" style="background:#dc2626"></span>
						Rejected
					</div>
					<div class="mt-2 flex items-center gap-2">
						<span class="inline-block h-[2px] w-6" style="background:#475569"></span>
						RELATES_TO edge
					</div>
				</div>
			</div>

			{#if selectedNodeAttrs}
				<div class="absolute right-4 bottom-4 max-w-sm rounded-md border border-gray-300 bg-white p-3 text-sm shadow-md">
					<div class="font-semibold text-gray-900">
						{(selectedNodeAttrs.label || selectedNodeAttrs.id || '').replace(/^[a-z]+:/i, '')}
					</div>
					<div class="text-xs text-gray-500">type: {selectedNodeAttrs.type}</div>
					{#if selectedNodeAttrs.data?.entity_type}
						<div class="text-xs text-gray-500">entity: {selectedNodeAttrs.data.entity_type}</div>
					{/if}
					{#if selectedNodeAttrs.data?.verification_state}
						<div class="text-xs text-gray-500">verification: {selectedNodeAttrs.data.verification_state}</div>
					{/if}
					{#if selectedNodeAttrs.data?.filename}
						<div class="text-xs text-gray-500 truncate">filename: {selectedNodeAttrs.data.filename}</div>
					{/if}
					{#if selectedNodeAttrs.data?.chunk_count}
						<div class="text-xs text-gray-500">{selectedNodeAttrs.data.chunk_count} chunks</div>
					{/if}
				</div>
			{/if}
		</div>
	</div>
{/if}
