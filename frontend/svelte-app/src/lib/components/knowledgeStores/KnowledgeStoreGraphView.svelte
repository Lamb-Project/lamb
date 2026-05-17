<!--
  @component KnowledgeStoreGraphView
  Graph RAG / semantic-graph panel for a Knowledge Store.

  Reads the graph snapshot + change log from the KB Server's /graph
  routes (proxied through LAMB) and exposes basic curation actions
  (approve / reject / rename / merge / edit relationship). Mounted as a
  tab on KnowledgeStoreDetail when KG_RAG_ENABLED=true on the KB Server
  and the store itself has graph_enabled=true.

  This is a focused port of the legacy KnowledgeBaseGraphView from the
  feature/kg-rag-llm-pipeline branch — same endpoints, adapted to the
  Knowledge Store API surface and the Svelte 5 runes layout the new
  /libraries page already uses.
-->
<script>
	import { onMount } from 'svelte';
	import {
		getGraphSnapshot,
		renameConcept,
		curateConcept,
		editRelationship,
		curateRelationship,
	} from '$lib/services/graphService';
	import SigmaGraphModal from './SigmaGraphModal.svelte';
	import { _ } from '$lib/i18n';

	/** @type {{ ksId: string, graphEnabled: boolean }} */
	let { ksId, graphEnabled } = $props();

	let loading = $state(false);
	let error = $state('');
	let snapshot = $state(/** @type {any} */ (null));
	let filter = $state({ concept: '', filename: '', document_id: '' });
	let sigmaOpen = $state(false);

	async function loadAll() {
		loading = true;
		error = '';
		try {
			snapshot = await getGraphSnapshot(ksId, {
				...stripEmpty(filter),
				limit: 80,
				include_chunks: 'true',
			});
		} catch (/** @type {*} */ err) {
			error = err?.response?.data?.detail || err?.message || 'Failed to load graph';
		} finally {
			loading = false;
		}
	}

	/** @param {Record<string, any> | null | undefined} obj */
	function stripEmpty(obj) {
		/** @type {Record<string, any>} */
		const out = {};
		for (const [k, v] of Object.entries(obj || {})) {
			if (v != null && String(v).trim() !== '') out[k] = v;
		}
		return out;
	}

	let bulkBusy = $state(false);
	let editingConcept = $state('');
	let editConceptName = $state('');
	let editingEdgeId = $state('');
	let editEdgeRelation = $state('');

	/**
	 * Set a concept's verification_state. Used by per-item toggle and
	 * by the bulk operations.
	 * @param {string} name
	 * @param {'verified'|'unverified'|'rejected'} state
	 */
	async function setConceptState(name, state) {
		try {
			await curateConcept(ksId, name, {
				verification_state: state,
				reason: `Set to ${state} via Knowledge Store UI`,
			});
		} catch (/** @type {*} */ err) {
			error = err?.response?.data?.detail || err?.message || `Failed to ${state}`;
			throw err;
		}
	}

	/**
	 * Set a relationship's verification_state.
	 * @param {{ source: string, target: string, relation: string }} rel
	 * @param {'verified'|'unverified'|'rejected'} state
	 */
	async function setRelationshipState(rel, state) {
		try {
			await curateRelationship(ksId, {
				source_concept: rel.source,
				target_concept: rel.target,
				relation: rel.relation,
				verification_state: state,
				reason: `Set to ${state} via Knowledge Store UI`,
			});
		} catch (/** @type {*} */ err) {
			error = err?.response?.data?.detail || err?.message || `Failed to ${state}`;
			throw err;
		}
	}

	/** @param {any} node */
	async function toggleConceptVerification(node) {
		const name = displayName(node.data?.name || node.label);
		const current = String(node.data?.verification_state || 'unverified');
		const next = current === 'verified' ? 'unverified' : 'verified';
		await setConceptState(name, next);
		await loadAll();
	}

	/** @param {any} edge */
	async function toggleRelationshipVerification(edge) {
		const rel = edgeEndpoints(edge);
		const current = String(edge.data?.verification_state || 'unverified');
		const next = current === 'verified' ? 'unverified' : 'verified';
		await setRelationshipState(rel, next);
		await loadAll();
	}

	/** @param {'verified' | 'rejected'} state */
	async function bulkConcepts(state) {
		if (!snapshot?.nodes?.length) return;
		const reason =
			state === 'verified' ? 'Bulk approval' : 'Bulk rejection';
		if (
			!confirm(
				`${reason} of ALL concepts in this Knowledge Store. Continue?`,
			)
		)
			return;
		bulkBusy = true;
		try {
			const concepts = snapshot.nodes.filter(
				(/** @type {any} */ n) => n.type === 'concept',
			);
			for (const node of concepts) {
				const cur = String(node.data?.verification_state || 'unverified');
				if (cur === state) continue;
				const name = displayName(node.data?.name || node.label);
				try {
					await curateConcept(ksId, name, {
						verification_state: state,
						reason,
					});
				} catch (/** @type {*} */ err) {
					console.warn('Bulk concept curate failed for', name, err);
				}
			}
			await loadAll();
		} finally {
			bulkBusy = false;
		}
	}

	/** @param {'verified' | 'rejected'} state */
	async function bulkRelationships(state) {
		if (!snapshot?.edges?.length) return;
		const reason =
			state === 'verified' ? 'Bulk approval' : 'Bulk rejection';
		if (
			!confirm(
				`${reason} of ALL relationships in this Knowledge Store. Continue?`,
			)
		)
			return;
		bulkBusy = true;
		try {
			const rels = snapshot.edges.filter(
				(/** @type {any} */ e) => e.type === 'RELATES_TO',
			);
			for (const edge of rels) {
				const cur = String(edge.data?.verification_state || 'unverified');
				if (cur === state) continue;
				const rel = edgeEndpoints(edge);
				try {
					await curateRelationship(ksId, {
						source_concept: rel.source,
						target_concept: rel.target,
						relation: rel.relation,
						verification_state: state,
						reason,
					});
				} catch (/** @type {*} */ err) {
					console.warn('Bulk relationship curate failed for', rel, err);
				}
			}
			await loadAll();
		} finally {
			bulkBusy = false;
		}
	}

	/** @param {any} node */
	function startEditConcept(node) {
		editingConcept = displayName(node.data?.name || node.label);
		editConceptName = editingConcept;
	}

	function cancelEditConcept() {
		editingConcept = '';
		editConceptName = '';
	}

	async function commitEditConcept() {
		const oldName = editingConcept;
		const newName = editConceptName.trim();
		if (!oldName || !newName || newName === oldName) {
			cancelEditConcept();
			return;
		}
		try {
			await renameConcept(ksId, oldName, {
				new_name: newName,
				reason: 'Renamed via Knowledge Store UI',
			});
			cancelEditConcept();
			await loadAll();
		} catch (/** @type {*} */ err) {
			error = err?.response?.data?.detail || err?.message || 'Rename failed';
		}
	}

	/** @param {any} edge */
	function startEditEdge(edge) {
		editingEdgeId = edge.id;
		editEdgeRelation = String(edge.data?.relation || edge.label || '');
	}

	function cancelEditEdge() {
		editingEdgeId = '';
		editEdgeRelation = '';
	}

	/** @param {any} edge */
	async function commitEditEdge(edge) {
		const newRelation = editEdgeRelation.trim();
		const { source, target, relation: oldRelation } = edgeEndpoints(edge);
		if (!newRelation || newRelation === oldRelation) {
			cancelEditEdge();
			return;
		}
		try {
			await editRelationship(ksId, {
				source_concept: source,
				target_concept: target,
				relation: oldRelation,
				new_relation: newRelation,
				reason: 'Edited via Knowledge Store UI',
			});
			cancelEditEdge();
			await loadAll();
		} catch (/** @type {*} */ err) {
			error = err?.response?.data?.detail || err?.message || 'Edit failed';
		}
	}

	/**
	 * Strip the ``concept:`` node-ID prefix when no friendlier label is
	 * available. Node IDs in Neo4j are stored as ``concept:<name>`` but
	 * the user-facing surface should show just the entity name.
	 * @param {string | undefined | null} value
	 * @returns {string}
	 */
	function displayName(value) {
		if (!value) return '';
		return String(value).replace(/^concept:/i, '');
	}

	/**
	 * Extract the clean (prefix-less) source and target concept names
	 * from a snapshot edge. The snapshot returns ``edge.data.source`` and
	 * ``edge.data.target`` as canonical names, but we fall back to
	 * stripping the ``concept:`` prefix from the raw ID for robustness.
	 * @param {any} edge
	 */
	function edgeEndpoints(edge) {
		return {
			source: String(edge.data?.source || displayName(edge.source)),
			target: String(edge.data?.target || displayName(edge.target)),
			relation: String(edge.data?.relation || edge.label || ''),
		};
	}

	onMount(() => {
		if (graphEnabled) loadAll();
	});
</script>

<div class="space-y-4">
	{#if !graphEnabled}
		<div class="rounded border border-dashed border-gray-300 bg-gray-50 p-4 text-sm text-gray-700">
			<p class="font-semibold">Graph RAG is not enabled on this Knowledge Store.</p>
			<p class="mt-2">
				Graph RAG is locked at creation time alongside chunking, embedding, and
				vector DB. To use Graph RAG, create a new Knowledge Store with the
				<span class="font-medium">Enable Graph RAG</span> toggle.
			</p>
		</div>
	{/if}

	{#if error}
		<div class="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700">{error}</div>
	{/if}

	{#if graphEnabled}
		<div class="rounded border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
			<span class="font-semibold">Retrieval policy:</span>
			only concepts and relationships you mark as
			<span class="rounded bg-green-100 px-1 py-0.5 font-medium text-green-800">verified</span>
			are used to enhance LLM retrieval. The LLM receives the
			retrieved <span class="font-medium">chunks</span> as context — the graph drives
			<em>which</em> chunks are returned (via question-entity expansion + RRF fusion
			with the vector baseline) but the concept/relation triples themselves are not
			added to the prompt. Approve the items you trust to make them
			contribute to the retrieval.
		</div>
	{/if}
	<div class="flex flex-wrap items-end gap-3 rounded border border-gray-200 bg-white p-3">
		<label class="flex flex-col text-xs text-gray-700">
			Concept
			<input
				class="mt-1 rounded border border-gray-300 px-2 py-1 text-sm"
				bind:value={filter.concept}
				placeholder="concept name fragment"
			/>
		</label>
		<label class="flex flex-col text-xs text-gray-700">
			Filename
			<input
				class="mt-1 rounded border border-gray-300 px-2 py-1 text-sm"
				bind:value={filter.filename}
				placeholder="source filename"
			/>
		</label>
		<label class="flex flex-col text-xs text-gray-700">
			Document ID
			<input
				class="mt-1 rounded border border-gray-300 px-2 py-1 text-sm"
				bind:value={filter.document_id}
				placeholder="graph document id"
			/>
		</label>
		<button
			type="button"
			class="rounded bg-gray-900 px-3 py-1 text-sm font-semibold text-white hover:bg-black disabled:opacity-50"
			onclick={loadAll}
			disabled={loading}
		>
			{loading ? 'Loading…' : 'Refresh'}
		</button>
		<button
			type="button"
			class="ml-auto rounded bg-[#2271b3] px-3 py-1 text-sm font-semibold text-white hover:bg-[#1a5a90] disabled:opacity-50"
			onclick={() => (sigmaOpen = true)}
			disabled={!graphEnabled}
			title={graphEnabled
				? 'Open the full graph in an interactive view'
				: 'Graph RAG is not enabled on this Knowledge Store'}
		>
			View full graph
		</button>
	</div>

	{#if loading}
		<p class="text-sm text-gray-500">Loading graph…</p>
	{:else if snapshot}
		<div class="grid grid-cols-2 gap-3 text-xs text-gray-700 sm:grid-cols-4">
			<div class="rounded border border-gray-200 bg-white p-2">
				<div class="text-gray-500">Concepts</div>
				<div class="text-base font-semibold">{snapshot?.counts?.concepts ?? 0}</div>
			</div>
			<div class="rounded border border-gray-200 bg-white p-2">
				<div class="text-gray-500">Documents</div>
				<div class="text-base font-semibold">{snapshot?.counts?.documents ?? 0}</div>
			</div>
			<div class="rounded border border-gray-200 bg-white p-2">
				<div class="text-gray-500">Chunks</div>
				<div class="text-base font-semibold">{snapshot?.counts?.chunks ?? 0}</div>
			</div>
			<div class="rounded border border-gray-200 bg-white p-2">
				<div class="text-gray-500">Edges</div>
				<div class="text-base font-semibold">{snapshot?.counts?.edges ?? 0}</div>
			</div>
		</div>

		<section class="rounded border border-gray-200 bg-white p-3">
			<div class="mb-2 flex items-center justify-between gap-2">
				<h3 class="text-sm font-semibold text-gray-900">Concepts</h3>
				<div class="flex gap-2">
					<button
						type="button"
						class="rounded border border-green-300 px-2 py-1 text-xs text-green-700 hover:bg-green-50 disabled:opacity-50"
						onclick={() => bulkConcepts('verified')}
						disabled={bulkBusy || !snapshot?.nodes?.length}
					>Approve all</button>
					<button
						type="button"
						class="rounded border border-red-300 px-2 py-1 text-xs text-red-700 hover:bg-red-50 disabled:opacity-50"
						onclick={() => bulkConcepts('rejected')}
						disabled={bulkBusy || !snapshot?.nodes?.length}
					>Reject all</button>
				</div>
			</div>
			{#if !snapshot?.nodes?.length}
				<p class="text-sm text-gray-500">No concept nodes yet.</p>
			{:else}
				<ul class="divide-y divide-gray-100">
					{#each snapshot.nodes.filter((/** @type {any} */ n) => n.type === 'concept') as node (node.id)}
						{@const conceptName = displayName(node.data?.name || node.label)}
						{@const state = String(node.data?.verification_state || 'unverified')}
						{@const isEditing = editingConcept === conceptName}
						<li class="flex items-center justify-between gap-2 py-2 text-sm">
							<div class="flex-1 min-w-0">
								{#if isEditing}
									<input
										type="text"
										class="w-full rounded border border-gray-300 px-2 py-1 text-sm"
										bind:value={editConceptName}
										onkeydown={(e) => {
											if (e.key === 'Enter') commitEditConcept();
											if (e.key === 'Escape') cancelEditConcept();
										}}
										autofocus
									/>
								{:else}
									<div class="font-medium text-gray-900 truncate">{displayName(node.label)}</div>
									<div class="text-xs">
										<span
											class="inline-block rounded-full px-2 py-0.5 text-[10px] font-medium {state === 'verified'
												? 'bg-green-100 text-green-700'
												: state === 'rejected'
													? 'bg-red-100 text-red-700'
													: 'bg-gray-100 text-gray-600'}"
										>{state}</span>
									</div>
								{/if}
							</div>
							<div class="flex gap-2">
								{#if isEditing}
									<button
										type="button"
										class="rounded bg-[#2271b3] px-2 py-1 text-xs text-white hover:bg-[#1a5a90]"
										onclick={commitEditConcept}
									>Save</button>
									<button
										type="button"
										class="rounded border border-gray-300 px-2 py-1 text-xs hover:bg-gray-50"
										onclick={cancelEditConcept}
									>Cancel</button>
								{:else}
									{#if state === 'verified'}
										<button
											type="button"
											class="rounded border border-gray-300 px-2 py-1 text-xs text-gray-700 hover:bg-gray-50"
											onclick={() => toggleConceptVerification(node)}
										>Unverify</button>
									{:else}
										<button
											type="button"
											class="rounded border border-green-300 px-2 py-1 text-xs text-green-700 hover:bg-green-50"
											onclick={() => toggleConceptVerification(node)}
										>Verify</button>
									{/if}
									<button
										type="button"
										class="rounded border border-gray-300 px-2 py-1 text-xs text-gray-700 hover:bg-gray-50"
										onclick={() => startEditConcept(node)}
									>Edit</button>
								{/if}
							</div>
						</li>
					{/each}
				</ul>
			{/if}
		</section>

		<section class="rounded border border-gray-200 bg-white p-3">
			<div class="mb-2 flex items-center justify-between gap-2">
				<h3 class="text-sm font-semibold text-gray-900">Relationships</h3>
				<div class="flex gap-2">
					<button
						type="button"
						class="rounded border border-green-300 px-2 py-1 text-xs text-green-700 hover:bg-green-50 disabled:opacity-50"
						onclick={() => bulkRelationships('verified')}
						disabled={bulkBusy || !snapshot?.edges?.length}
					>Approve all</button>
					<button
						type="button"
						class="rounded border border-red-300 px-2 py-1 text-xs text-red-700 hover:bg-red-50 disabled:opacity-50"
						onclick={() => bulkRelationships('rejected')}
						disabled={bulkBusy || !snapshot?.edges?.length}
					>Reject all</button>
				</div>
			</div>
			{#if !snapshot?.edges?.length}
				<p class="text-sm text-gray-500">No relationships yet.</p>
			{:else}
				<ul class="divide-y divide-gray-100">
					{#each snapshot.edges.filter((/** @type {any} */ e) => e.type === 'RELATES_TO') as edge (edge.id)}
						{@const state = String(edge.data?.verification_state || 'unverified')}
						{@const isEditing = editingEdgeId === edge.id}
						<li class="flex items-center justify-between gap-2 py-2 text-sm">
							<div class="flex-1 min-w-0">
								<div class="truncate">
									<span class="font-medium text-gray-900">{displayName(edge.data?.source_label || edge.source)}</span>
									<span class="mx-2 text-gray-500">→</span>
									<span class="font-medium text-gray-900">{displayName(edge.data?.target_label || edge.target)}</span>
								</div>
								<div class="mt-1 flex items-center gap-2 text-xs">
									{#if isEditing}
										<input
											type="text"
											class="flex-1 rounded border border-gray-300 px-2 py-1 text-xs"
											bind:value={editEdgeRelation}
											onkeydown={(e) => {
												if (e.key === 'Enter') commitEditEdge(edge);
												if (e.key === 'Escape') cancelEditEdge();
											}}
											autofocus
										/>
									{:else}
										<span class="inline-block rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-600">
											{edge.label || edge.data?.relation}
										</span>
										<span
											class="inline-block rounded-full px-2 py-0.5 text-[10px] font-medium {state === 'verified'
												? 'bg-green-100 text-green-700'
												: state === 'rejected'
													? 'bg-red-100 text-red-700'
													: 'bg-gray-100 text-gray-600'}"
										>{state}</span>
									{/if}
								</div>
							</div>
							<div class="flex gap-2">
								{#if isEditing}
									<button
										type="button"
										class="rounded bg-[#2271b3] px-2 py-1 text-xs text-white hover:bg-[#1a5a90]"
										onclick={() => commitEditEdge(edge)}
									>Save</button>
									<button
										type="button"
										class="rounded border border-gray-300 px-2 py-1 text-xs hover:bg-gray-50"
										onclick={cancelEditEdge}
									>Cancel</button>
								{:else}
									{#if state === 'verified'}
										<button
											type="button"
											class="rounded border border-gray-300 px-2 py-1 text-xs text-gray-700 hover:bg-gray-50"
											onclick={() => toggleRelationshipVerification(edge)}
										>Unverify</button>
									{:else}
										<button
											type="button"
											class="rounded border border-green-300 px-2 py-1 text-xs text-green-700 hover:bg-green-50"
											onclick={() => toggleRelationshipVerification(edge)}
										>Verify</button>
									{/if}
									<button
										type="button"
										class="rounded border border-gray-300 px-2 py-1 text-xs text-gray-700 hover:bg-gray-50"
										onclick={() => startEditEdge(edge)}
									>Edit</button>
								{/if}
							</div>
						</li>
					{/each}
				</ul>
			{/if}
		</section>
	{/if}

</div>

<SigmaGraphModal {ksId} open={sigmaOpen} onclose={() => (sigmaOpen = false)} />
