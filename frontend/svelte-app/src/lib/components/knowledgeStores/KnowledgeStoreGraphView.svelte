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
		listGraphChanges,
		migrateToGraph,
		renameConcept,
		mergeConcepts,
		curateConcept,
		editRelationship,
		curateRelationship,
	} from '$lib/services/graphService';
	import {
		changeOperationLabel,
		changeMetaLine,
		changeDetail,
	} from '$lib/utils/graphCuration';
	import { _ } from '$lib/i18n';

	/** @type {{ ksId: string, graphEnabled: boolean }} */
	let { ksId, graphEnabled } = $props();

	let loading = $state(false);
	let error = $state('');
	let success = $state('');
	let snapshot = $state(/** @type {any} */ (null));
	let changes = $state(/** @type {any[]} */ ([]));
	let filter = $state({ concept: '', filename: '', document_id: '' });
	let migrating = $state(false);
	let migrateApiKey = $state('');

	// Curation modals
	let curationTarget = $state(/** @type {any} */ (null));

	async function loadAll() {
		loading = true;
		error = '';
		try {
			const [snap, hist] = await Promise.all([
				getGraphSnapshot(ksId, {
					...stripEmpty(filter),
					limit: 80,
					include_chunks: 'true',
				}),
				listGraphChanges(ksId, { ...stripEmpty(filter), limit: 25 }),
			]);
			snapshot = snap;
			changes = Array.isArray(hist) ? hist : [];
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

	async function onMigrate() {
		migrating = true;
		error = '';
		try {
			const body = migrateApiKey ? { openai_api_key: migrateApiKey } : {};
			const result = await migrateToGraph(ksId, body);
			success = `Migrated: ${result.chunks_seen ?? result.chunks ?? 0} chunks processed`;
			await loadAll();
		} catch (/** @type {*} */ err) {
			error =
				err?.response?.data?.detail || err?.message || 'Migration failed';
		} finally {
			migrating = false;
		}
	}

	/** @param {string} name */
	async function approveConcept(name) {
		try {
			await curateConcept(ksId, name, {
				verification_state: 'verified',
				reason: 'Approved via Knowledge Store UI',
			});
			await loadAll();
		} catch (/** @type {*} */ err) {
			error = err?.response?.data?.detail || err?.message || 'Approval failed';
		}
	}

	/** @param {string} name */
	async function rejectConcept(name) {
		try {
			await curateConcept(ksId, name, {
				verification_state: 'rejected',
				reason: 'Rejected via Knowledge Store UI',
			});
			await loadAll();
		} catch (/** @type {*} */ err) {
			error =
				err?.response?.data?.detail || err?.message || 'Rejection failed';
		}
	}

	/** @param {{ source: string, target: string, relation: string }} rel */
	async function approveRelationship(rel) {
		try {
			await curateRelationship(ksId, {
				source_concept: rel.source,
				target_concept: rel.target,
				relation: rel.relation,
				verification_state: 'verified',
				reason: 'Approved via Knowledge Store UI',
			});
			await loadAll();
		} catch (/** @type {*} */ err) {
			error = err?.response?.data?.detail || err?.message || 'Approval failed';
		}
	}

	/** @param {{ source: string, target: string, relation: string }} rel */
	async function rejectRelationship(rel) {
		try {
			await editRelationship(ksId, {
				source_concept: rel.source,
				target_concept: rel.target,
				relation: rel.relation,
				verification_state: 'rejected',
				reason: 'Rejected via Knowledge Store UI',
			});
			await loadAll();
		} catch (/** @type {*} */ err) {
			error =
				err?.response?.data?.detail || err?.message || 'Rejection failed';
		}
	}

	onMount(() => {
		if (graphEnabled) loadAll();
	});
</script>

<div class="space-y-4">
	{#if !graphEnabled}
		<div class="rounded border border-dashed border-amber-300 bg-amber-50 p-4 text-sm text-amber-900">
			<p class="font-semibold">Graph RAG is not enabled on this Knowledge Store.</p>
			<p class="mt-2">
				Run the migration below to extract concepts and relationships from
				existing chunks. This calls the LLM extractor and writes results to
				Neo4j; vector retrieval keeps working either way.
			</p>
			<div class="mt-3 flex flex-wrap items-center gap-2">
				<input
					type="password"
					class="rounded border border-amber-300 bg-white px-2 py-1 text-sm"
					placeholder="OpenAI API key (optional — falls back to org/server config)"
					bind:value={migrateApiKey}
				/>
				<button
					type="button"
					class="rounded bg-amber-600 px-3 py-1 text-sm font-semibold text-white hover:bg-amber-700 disabled:opacity-50"
					onclick={onMigrate}
					disabled={migrating}
				>
					{migrating ? 'Migrating…' : 'Migrate to Graph RAG'}
				</button>
			</div>
		</div>
	{/if}

	{#if error}
		<div class="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700">{error}</div>
	{/if}
	{#if success}
		<div class="rounded border border-green-300 bg-green-50 p-3 text-sm text-green-700">{success}</div>
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
			<h3 class="mb-2 text-sm font-semibold text-gray-900">Concepts</h3>
			{#if !snapshot?.nodes?.length}
				<p class="text-sm text-gray-500">No concept nodes yet.</p>
			{:else}
				<ul class="divide-y divide-gray-100">
					{#each snapshot.nodes.filter((/** @type {any} */ n) => n.type === 'concept') as node (node.id)}
						<li class="flex items-center justify-between gap-2 py-2 text-sm">
							<div>
								<div class="font-medium text-gray-900">{node.label}</div>
								<div class="text-xs text-gray-500">{node.data?.verification_state || 'unverified'}</div>
							</div>
							<div class="flex gap-2">
								<button
									type="button"
									class="rounded border border-green-300 px-2 py-1 text-xs text-green-700 hover:bg-green-50"
									onclick={() => approveConcept(node.data?.name || node.label)}
								>Approve</button>
								<button
									type="button"
									class="rounded border border-red-300 px-2 py-1 text-xs text-red-700 hover:bg-red-50"
									onclick={() => rejectConcept(node.data?.name || node.label)}
								>Reject</button>
							</div>
						</li>
					{/each}
				</ul>
			{/if}
		</section>

		<section class="rounded border border-gray-200 bg-white p-3">
			<h3 class="mb-2 text-sm font-semibold text-gray-900">Relationships</h3>
			{#if !snapshot?.edges?.length}
				<p class="text-sm text-gray-500">No relationships yet.</p>
			{:else}
				<ul class="divide-y divide-gray-100">
					{#each snapshot.edges.filter((/** @type {any} */ e) => e.type === 'RELATES_TO') as edge (edge.id)}
						<li class="flex items-center justify-between gap-2 py-2 text-sm">
							<div>
								<span class="font-medium text-gray-900">{edge.data?.source_label || edge.source}</span>
								<span class="mx-2 text-gray-500">→</span>
								<span class="font-medium text-gray-900">{edge.data?.target_label || edge.target}</span>
								<span class="ml-2 inline-block rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-600">
									{edge.label || edge.data?.relation}
								</span>
							</div>
							<div class="flex gap-2">
								<button
									type="button"
									class="rounded border border-green-300 px-2 py-1 text-xs text-green-700 hover:bg-green-50"
									onclick={() =>
										approveRelationship({
											source: edge.data?.source_name || edge.source,
											target: edge.data?.target_name || edge.target,
											relation: edge.data?.relation || edge.label,
										})}
								>Approve</button>
								<button
									type="button"
									class="rounded border border-red-300 px-2 py-1 text-xs text-red-700 hover:bg-red-50"
									onclick={() =>
										rejectRelationship({
											source: edge.data?.source_name || edge.source,
											target: edge.data?.target_name || edge.target,
											relation: edge.data?.relation || edge.label,
										})}
								>Reject</button>
							</div>
						</li>
					{/each}
				</ul>
			{/if}
		</section>
	{/if}

	<section class="rounded border border-gray-200 bg-white p-3">
		<h3 class="mb-2 text-sm font-semibold text-gray-900">Recent changes</h3>
		{#if !changes.length}
			<p class="text-sm text-gray-500">No change events yet.</p>
		{:else}
			<ul class="divide-y divide-gray-100 text-sm">
				{#each changes as change (change.event_id)}
					<li class="py-2">
						<div class="font-medium text-gray-900">{changeOperationLabel(change)}</div>
						<div class="text-xs text-gray-500">{changeMetaLine(change)}</div>
						<div class="text-xs text-gray-600">{changeDetail(change)}</div>
					</li>
				{/each}
			</ul>
		{/if}
	</section>
</div>
