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

	// Status filters (client-side, applied to already-loaded snapshot)
	let conceptStatusFilter = $state('all');
	let relStatusFilter = $state('all');

	// Pagination
	const PAGE_SIZE = 20;
	let conceptPage = $state(1);
	let relPage = $state(1);

	// --- Derived lists ---

	let allConcepts = $derived(
		(snapshot?.nodes || []).filter((/** @type {any} */ n) => n.type === 'concept'),
	);
	let allRels = $derived(
		(snapshot?.edges || []).filter((/** @type {any} */ e) => e.type === 'RELATES_TO'),
	);

	let filteredConcepts = $derived(
		conceptStatusFilter === 'all'
			? allConcepts
			: allConcepts.filter(
					(/** @type {any} */ n) =>
						(n.data?.verification_state || 'unverified') === conceptStatusFilter,
				),
	);
	let filteredRels = $derived(
		relStatusFilter === 'all'
			? allRels
			: allRels.filter(
					(/** @type {any} */ e) =>
						(e.data?.verification_state || 'unverified') === relStatusFilter,
				),
	);

	let conceptTotalPages = $derived(Math.max(1, Math.ceil(filteredConcepts.length / PAGE_SIZE)));
	let relTotalPages = $derived(Math.max(1, Math.ceil(filteredRels.length / PAGE_SIZE)));

	let pagedConcepts = $derived(
		filteredConcepts.slice((conceptPage - 1) * PAGE_SIZE, conceptPage * PAGE_SIZE),
	);
	let pagedRels = $derived(
		filteredRels.slice((relPage - 1) * PAGE_SIZE, relPage * PAGE_SIZE),
	);

	// --- Stats ---

	let conceptVerifiedCount = $derived(
		allConcepts.filter(
			(/** @type {any} */ n) => (n.data?.verification_state || 'unverified') === 'verified',
		).length,
	);
	let relVerifiedCount = $derived(
		allRels.filter(
			(/** @type {any} */ e) => (e.data?.verification_state || 'unverified') === 'verified',
		).length,
	);

	/** @param {number} num @param {number} den */
	function pct(num, den) {
		if (!den) return '—';
		return Math.round((num / den) * 100) + '%';
	}

	// Reset pages to 1 when filter or snapshot changes
	$effect(() => {
		// eslint-disable-next-line no-unused-expressions
		conceptStatusFilter;
		conceptPage = 1;
	});
	$effect(() => {
		// eslint-disable-next-line no-unused-expressions
		relStatusFilter;
		relPage = 1;
	});
	$effect(() => {
		// eslint-disable-next-line no-unused-expressions
		snapshot;
		conceptPage = 1;
		relPage = 1;
	});

	async function loadAll() {
		loading = true;
		error = '';
		try {
			snapshot = await getGraphSnapshot(ksId, {
				...stripEmpty(filter),
				limit: 200,
				include_chunks: 'true',
			});
		} catch (/** @type {*} */ err) {
			error =
				err?.response?.data?.detail || err?.message || $_('knowledgeStores.graph.errorLoad');
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
				reason: $_('knowledgeStores.graph.reasonSetState', { values: { state } }),
			});
		} catch (/** @type {*} */ err) {
			error =
				err?.response?.data?.detail ||
				err?.message ||
				$_('knowledgeStores.graph.errorSetState', { values: { state } });
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
				reason: $_('knowledgeStores.graph.reasonSetState', { values: { state } }),
			});
		} catch (/** @type {*} */ err) {
			error =
				err?.response?.data?.detail ||
				err?.message ||
				$_('knowledgeStores.graph.errorSetState', { values: { state } });
			throw err;
		}
	}

	/** @param {any} node */
	async function toggleConceptVerification(node) {
		const name = displayName(node.data?.name || node.label);
		const current = String(node.data?.verification_state || 'unverified');
		const next = current === 'verified' ? 'unverified' : 'verified';
		await setConceptState(name, next);
		// Mutate in place — avoids a full re-fetch and the resulting flicker.
		// $state deep-proxy picks up the change immediately.
		node.data.verification_state = next;
	}

	/** @param {any} edge */
	async function toggleRelationshipVerification(edge) {
		const rel = edgeEndpoints(edge);
		const current = String(edge.data?.verification_state || 'unverified');
		const next = current === 'verified' ? 'unverified' : 'verified';
		await setRelationshipState(rel, next);
		edge.data.verification_state = next;
	}

	/** @param {'verified' | 'rejected'} state */
	async function bulkConcepts(state) {
		if (!snapshot?.nodes?.length) return;
		const reason =
			state === 'verified'
				? $_('knowledgeStores.graph.bulkApproval')
				: $_('knowledgeStores.graph.bulkRejection');
		if (!confirm($_('knowledgeStores.graph.confirmBulkConcepts', { values: { reason } }))) return;
		bulkBusy = true;
		try {
			const concepts = snapshot.nodes.filter((/** @type {any} */ n) => n.type === 'concept');
			for (const node of concepts) {
				const cur = String(node.data?.verification_state || 'unverified');
				if (cur === state) continue;
				const name = displayName(node.data?.name || node.label);
				try {
					await curateConcept(ksId, name, { verification_state: state, reason });
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
			state === 'verified'
				? $_('knowledgeStores.graph.bulkApproval')
				: $_('knowledgeStores.graph.bulkRejection');
		if (!confirm($_('knowledgeStores.graph.confirmBulkRelationships', { values: { reason } })))
			return;
		bulkBusy = true;
		try {
			const rels = snapshot.edges.filter((/** @type {any} */ e) => e.type === 'RELATES_TO');
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
				reason: $_('knowledgeStores.graph.reasonRename'),
			});
			cancelEditConcept();
			await loadAll();
		} catch (/** @type {*} */ err) {
			error =
				err?.response?.data?.detail || err?.message || $_('knowledgeStores.graph.errorRename');
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
				reason: $_('knowledgeStores.graph.reasonEdit'),
			});
			cancelEditEdge();
			await loadAll();
		} catch (/** @type {*} */ err) {
			error = err?.response?.data?.detail || err?.message || $_('knowledgeStores.graph.errorEdit');
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
			<p class="font-semibold">{$_('knowledgeStores.graph.notEnabledTitle')}</p>
			<p class="mt-2">{@html $_('knowledgeStores.graph.notEnabledBody')}</p>
		</div>
	{/if}

	{#if error}
		<div class="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700">{error}</div>
	{/if}

	{#if graphEnabled}
		<div class="rounded border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
			{@html $_('knowledgeStores.graph.retrievalPolicyHtml')}
		</div>
	{/if}

	<div class="flex flex-wrap items-end gap-3 rounded border border-gray-200 bg-white p-3">
		<label class="flex flex-col text-xs text-gray-700">
			{$_('knowledgeStores.graph.conceptLabel')}
			<input
				class="mt-1 rounded border border-gray-300 px-2 py-1 text-sm"
				bind:value={filter.concept}
				placeholder={$_('knowledgeStores.graph.conceptPlaceholder')}
			/>
		</label>
		<label class="flex flex-col text-xs text-gray-700">
			{$_('knowledgeStores.graph.filenameLabel')}
			<input
				class="mt-1 rounded border border-gray-300 px-2 py-1 text-sm"
				bind:value={filter.filename}
				placeholder={$_('knowledgeStores.graph.filenamePlaceholder')}
			/>
		</label>
		<label class="flex flex-col text-xs text-gray-700">
			{$_('knowledgeStores.graph.documentIdLabel')}
			<input
				class="mt-1 rounded border border-gray-300 px-2 py-1 text-sm"
				bind:value={filter.document_id}
				placeholder={$_('knowledgeStores.graph.documentIdPlaceholder')}
			/>
		</label>
		<button
			type="button"
			class="rounded bg-gray-900 px-3 py-1 text-sm font-semibold text-white hover:bg-black disabled:opacity-50"
			onclick={loadAll}
			disabled={loading}
		>
			{loading ? $_('knowledgeStores.graph.loading') : $_('knowledgeStores.graph.refresh')}
		</button>
		<button
			type="button"
			class="ml-auto rounded bg-[#2271b3] px-3 py-1 text-sm font-semibold text-white hover:bg-[#1a5a90] disabled:opacity-50"
			onclick={() => (sigmaOpen = true)}
			disabled={!graphEnabled}
			title={graphEnabled
				? $_('knowledgeStores.graph.viewFullGraphTitle')
				: $_('knowledgeStores.graph.notEnabledTitleShort')}
		>
			{$_('knowledgeStores.graph.viewFullGraph')}
		</button>
	</div>

	{#if loading}
		<p class="text-sm text-gray-500">{$_('knowledgeStores.graph.loadingGraph')}</p>
	{:else if snapshot}
		<!-- Stats -->
		<div class="grid grid-cols-2 gap-3 text-xs text-gray-700 sm:grid-cols-4">
			<div class="rounded border border-gray-200 bg-white p-2">
				<div class="text-gray-500">{$_('knowledgeStores.graph.concepts')}</div>
				<div class="text-base font-semibold">{snapshot?.counts?.concepts ?? 0}</div>
				<div class="mt-0.5 text-[11px] text-green-700">
					{$_('knowledgeStores.graph.verifiedCount', {
						values: {
							count: conceptVerifiedCount,
							pct: pct(conceptVerifiedCount, allConcepts.length),
						},
					})}
				</div>
			</div>
			<div class="rounded border border-gray-200 bg-white p-2">
				<div class="text-gray-500">{$_('knowledgeStores.graph.documents')}</div>
				<div class="text-base font-semibold">{snapshot?.counts?.documents ?? 0}</div>
			</div>
			<div class="rounded border border-gray-200 bg-white p-2">
				<div class="text-gray-500">{$_('knowledgeStores.graph.chunks')}</div>
				<div class="text-base font-semibold">{snapshot?.counts?.chunks ?? 0}</div>
			</div>
			<div class="rounded border border-gray-200 bg-white p-2">
				<div class="text-gray-500">{$_('knowledgeStores.graph.edges')}</div>
				<div class="text-base font-semibold">{snapshot?.counts?.edges ?? 0}</div>
				<div class="mt-0.5 text-[11px] text-green-700">
					{$_('knowledgeStores.graph.verifiedCount', {
						values: { count: relVerifiedCount, pct: pct(relVerifiedCount, allRels.length) },
					})}
				</div>
			</div>
		</div>

		<!-- Concepts section -->
		<section class="rounded border border-gray-200 bg-white p-3">
			<div class="mb-2 flex flex-wrap items-center justify-between gap-2">
				<div class="flex items-center gap-2">
					<h3 class="text-sm font-semibold text-gray-900">{$_('knowledgeStores.graph.concepts')}</h3>
					<span class="text-xs text-gray-400"
						>{$_('knowledgeStores.graph.verifiedRatio', {
							values: { count: conceptVerifiedCount, total: allConcepts.length },
						})}</span
					>
				</div>
				<div class="flex flex-wrap items-center gap-2">
					<select
						class="rounded border border-gray-300 bg-white px-2 py-1 text-xs text-gray-700"
						bind:value={conceptStatusFilter}
					>
						<option value="all">{$_('knowledgeStores.graph.filterAll')}</option>
						<option value="unverified">{$_('knowledgeStores.graph.filterUnverified')}</option>
						<option value="verified">{$_('knowledgeStores.graph.filterVerified')}</option>
						<option value="rejected">{$_('knowledgeStores.graph.filterRejected')}</option>
					</select>
					<button
						type="button"
						class="rounded border border-green-300 px-2 py-1 text-xs text-green-700 hover:bg-green-50 disabled:opacity-50"
						onclick={() => bulkConcepts('verified')}
						disabled={bulkBusy || !snapshot?.nodes?.length}
					>{$_('knowledgeStores.graph.approveAll')}</button>
					<button
						type="button"
						class="rounded border border-red-300 px-2 py-1 text-xs text-red-700 hover:bg-red-50 disabled:opacity-50"
						onclick={() => bulkConcepts('rejected')}
						disabled={bulkBusy || !snapshot?.nodes?.length}
					>{$_('knowledgeStores.graph.rejectAll')}</button>
				</div>
			</div>

			{#if !allConcepts.length}
				<p class="text-sm text-gray-500">{$_('knowledgeStores.graph.noConcepts')}</p>
			{:else if !filteredConcepts.length}
				<p class="text-sm text-gray-500">{$_('knowledgeStores.graph.noConceptsFilter')}</p>
			{:else}
				<ul class="divide-y divide-gray-100">
					{#each pagedConcepts as node (node.id)}
						{@const conceptName = displayName(node.data?.name || node.label)}
						{@const state = String(node.data?.verification_state || 'unverified')}
						{@const isEditing = editingConcept === conceptName}
						<li class="flex items-center justify-between gap-2 py-2 text-sm">
							<div class="min-w-0 flex-1">
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
									<div class="truncate font-medium text-gray-900">{displayName(node.label)}</div>
									<div class="text-xs">
										<span
											class="inline-block rounded-full px-2 py-0.5 text-[10px] font-medium {state === 'verified'
												? 'bg-green-100 text-green-700'
												: state === 'rejected'
													? 'bg-red-100 text-red-700'
													: 'bg-gray-100 text-gray-600'}"
										>{$_('knowledgeStores.graph.state.' + state)}</span>
									</div>
								{/if}
							</div>
							<div class="flex gap-2">
								{#if isEditing}
									<button
										type="button"
										class="rounded bg-[#2271b3] px-2 py-1 text-xs text-white hover:bg-[#1a5a90]"
										onclick={commitEditConcept}
									>{$_('knowledgeStores.graph.save')}</button>
									<button
										type="button"
										class="rounded border border-gray-300 px-2 py-1 text-xs hover:bg-gray-50"
										onclick={cancelEditConcept}
									>{$_('knowledgeStores.graph.cancel')}</button>
								{:else}
									{#if state === 'verified'}
										<button
											type="button"
											class="rounded border border-gray-300 px-2 py-1 text-xs text-gray-700 hover:bg-gray-50"
											onclick={() => toggleConceptVerification(node)}
										>{$_('knowledgeStores.graph.unverify')}</button>
									{:else}
										<button
											type="button"
											class="rounded border border-green-300 px-2 py-1 text-xs text-green-700 hover:bg-green-50"
											onclick={() => toggleConceptVerification(node)}
										>{$_('knowledgeStores.graph.verify')}</button>
									{/if}
									<button
										type="button"
										class="rounded border border-gray-300 px-2 py-1 text-xs text-gray-700 hover:bg-gray-50"
										onclick={() => startEditConcept(node)}
									>{$_('knowledgeStores.graph.edit')}</button>
								{/if}
							</div>
						</li>
					{/each}
				</ul>

				{#if conceptTotalPages > 1}
					<div class="mt-3 flex items-center justify-between border-t border-gray-100 pt-2 text-xs text-gray-600">
						<button
							type="button"
							class="rounded border border-gray-300 px-2 py-1 hover:bg-gray-50 disabled:opacity-40"
							onclick={() => conceptPage--}
							disabled={conceptPage <= 1}
						>{$_('knowledgeStores.graph.prev')}</button>
						<span
							>{$_('knowledgeStores.graph.pageInfo', {
								values: {
									page: conceptPage,
									total: conceptTotalPages,
									items: filteredConcepts.length,
								},
							})}</span
						>
						<button
							type="button"
							class="rounded border border-gray-300 px-2 py-1 hover:bg-gray-50 disabled:opacity-40"
							onclick={() => conceptPage++}
							disabled={conceptPage >= conceptTotalPages}
						>{$_('knowledgeStores.graph.next')}</button>
					</div>
				{/if}
			{/if}
		</section>

		<!-- Relationships section -->
		<section class="rounded border border-gray-200 bg-white p-3">
			<div class="mb-2 flex flex-wrap items-center justify-between gap-2">
				<div class="flex items-center gap-2">
					<h3 class="text-sm font-semibold text-gray-900">
						{$_('knowledgeStores.graph.relationships')}
					</h3>
					<span class="text-xs text-gray-400"
						>{$_('knowledgeStores.graph.verifiedRatio', {
							values: { count: relVerifiedCount, total: allRels.length },
						})}</span
					>
				</div>
				<div class="flex flex-wrap items-center gap-2">
					<select
						class="rounded border border-gray-300 bg-white px-2 py-1 text-xs text-gray-700"
						bind:value={relStatusFilter}
					>
						<option value="all">{$_('knowledgeStores.graph.filterAll')}</option>
						<option value="unverified">{$_('knowledgeStores.graph.filterUnverified')}</option>
						<option value="verified">{$_('knowledgeStores.graph.filterVerified')}</option>
						<option value="rejected">{$_('knowledgeStores.graph.filterRejected')}</option>
					</select>
					<button
						type="button"
						class="rounded border border-green-300 px-2 py-1 text-xs text-green-700 hover:bg-green-50 disabled:opacity-50"
						onclick={() => bulkRelationships('verified')}
						disabled={bulkBusy || !snapshot?.edges?.length}
					>{$_('knowledgeStores.graph.approveAll')}</button>
					<button
						type="button"
						class="rounded border border-red-300 px-2 py-1 text-xs text-red-700 hover:bg-red-50 disabled:opacity-50"
						onclick={() => bulkRelationships('rejected')}
						disabled={bulkBusy || !snapshot?.edges?.length}
					>{$_('knowledgeStores.graph.rejectAll')}</button>
				</div>
			</div>

			{#if !allRels.length}
				<p class="text-sm text-gray-500">{$_('knowledgeStores.graph.noRelationships')}</p>
			{:else if !filteredRels.length}
				<p class="text-sm text-gray-500">{$_('knowledgeStores.graph.noRelationshipsFilter')}</p>
			{:else}
				<ul class="divide-y divide-gray-100">
					{#each pagedRels as edge (edge.id)}
						{@const state = String(edge.data?.verification_state || 'unverified')}
						{@const isEditing = editingEdgeId === edge.id}
						<li class="flex items-center justify-between gap-2 py-2 text-sm">
							<div class="min-w-0 flex-1">
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
										>{$_('knowledgeStores.graph.state.' + state)}</span>
									{/if}
								</div>
							</div>
							<div class="flex gap-2">
								{#if isEditing}
									<button
										type="button"
										class="rounded bg-[#2271b3] px-2 py-1 text-xs text-white hover:bg-[#1a5a90]"
										onclick={() => commitEditEdge(edge)}
									>{$_('knowledgeStores.graph.save')}</button>
									<button
										type="button"
										class="rounded border border-gray-300 px-2 py-1 text-xs hover:bg-gray-50"
										onclick={cancelEditEdge}
									>{$_('knowledgeStores.graph.cancel')}</button>
								{:else}
									{#if state === 'verified'}
										<button
											type="button"
											class="rounded border border-gray-300 px-2 py-1 text-xs text-gray-700 hover:bg-gray-50"
											onclick={() => toggleRelationshipVerification(edge)}
										>{$_('knowledgeStores.graph.unverify')}</button>
									{:else}
										<button
											type="button"
											class="rounded border border-green-300 px-2 py-1 text-xs text-green-700 hover:bg-green-50"
											onclick={() => toggleRelationshipVerification(edge)}
										>{$_('knowledgeStores.graph.verify')}</button>
									{/if}
									<button
										type="button"
										class="rounded border border-gray-300 px-2 py-1 text-xs text-gray-700 hover:bg-gray-50"
										onclick={() => startEditEdge(edge)}
									>{$_('knowledgeStores.graph.edit')}</button>
								{/if}
							</div>
						</li>
					{/each}
				</ul>

				{#if relTotalPages > 1}
					<div class="mt-3 flex items-center justify-between border-t border-gray-100 pt-2 text-xs text-gray-600">
						<button
							type="button"
							class="rounded border border-gray-300 px-2 py-1 hover:bg-gray-50 disabled:opacity-40"
							onclick={() => relPage--}
							disabled={relPage <= 1}
						>{$_('knowledgeStores.graph.prev')}</button>
						<span
							>{$_('knowledgeStores.graph.pageInfo', {
								values: { page: relPage, total: relTotalPages, items: filteredRels.length },
							})}</span
						>
						<button
							type="button"
							class="rounded border border-gray-300 px-2 py-1 hover:bg-gray-50 disabled:opacity-40"
							onclick={() => relPage++}
							disabled={relPage >= relTotalPages}
						>{$_('knowledgeStores.graph.next')}</button>
					</div>
				{/if}
			{/if}
		</section>
	{/if}
</div>

<SigmaGraphModal {ksId} open={sigmaOpen} onclose={() => (sigmaOpen = false)} />
