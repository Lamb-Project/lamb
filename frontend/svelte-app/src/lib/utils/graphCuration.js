const GENERIC_CURATION_REASON = 'Educator graph curation';
const INTERNAL_ACTORS = new Set(['graph-curation-api', 'graph-traceability-api']);

/** @typedef {Record<string, any>} GraphData */
/** @typedef {{ id: string, type: string, label: string, data: GraphData }} GraphNode */
/** @typedef {{ id: string, type: string, source: string, target: string, label?: string, weight?: number, data: GraphData }} GraphEdge */
/** @typedef {{ event_id?: string, operation?: string, actor?: string, timestamp?: string, filename?: string, document_id?: string, concepts?: string[], payload_json?: string | null }} GraphChange */

/** @param {GraphChange | null | undefined} change @returns {GraphData} */
export function changePayload(change) {
	try {
		const payload = JSON.parse(change?.payload_json || '{}');
		return payload && typeof payload === 'object' ? payload : {};
	} catch {
		return {};
	}
}

/** @param {GraphChange} change */
export function changeOperationLabel(change) {
	const payload = changePayload(change);
	const operation = change?.operation || '';
	if (operation === 'automatic_ingestion') return 'Created by ingestion';
	if (operation === 'revert_change') {
		if (payload.reverted_operation === 'manual_expunge_relationship')
			return 'Relationship restored';
		if (payload.reverted_operation === 'manual_expunge_concept') return 'Concept restored';
		return 'Change reverted';
	}
	if (operation === 'manual_edit_relationship') return 'Relationship updated';
	if (operation === 'manual_curate_relationship') return 'Relationship status updated';
	if (operation === 'manual_expunge_relationship') return 'Relationship expunged';
	if (operation === 'manual_curate_concept') return 'Concept status updated';
	if (operation === 'manual_expunge_concept') return 'Concept expunged';
	if (operation === 'manual_rename_concept') return 'Concept renamed';
	if (operation === 'manual_merge_concepts') return 'Concepts merged';
	return operation || 'Graph change';
}

/** @param {GraphChange} change */
export function changeDetail(change) {
	const payload = changePayload(change);
	const operation = change?.operation || '';
	const parts = [];
	if (operation === 'revert_change') {
		if (payload.reverted_operation === 'manual_expunge_relationship')
			parts.push('Restored relationship as approved');
		else if (payload.reverted_operation === 'manual_expunge_concept')
			parts.push('Restored concept as approved');
		else parts.push('Reverted previous graph change');
		if (payload.reason && !isGenericReason(payload.reason)) parts.push(String(payload.reason));
		return parts.join(' | ');
	}
	if (payload.reason && !isGenericReason(payload.reason)) parts.push(String(payload.reason));
	const transition = verificationTransition(payload);
	if (transition) parts.push(transition);
	if (operation === 'manual_edit_relationship' && payload.source && payload.target) {
		parts.push(
			`${payload.source} / ${payload.relation || payload.new_relation || 'related_to'} / ${payload.target}`
		);
		if (payload.new_relation && payload.relation && payload.new_relation !== payload.relation) {
			parts.push(`Relation ${payload.relation} -> ${payload.new_relation}`);
		}
	}
	if (Array.isArray(payload.removed_chunk_mentions)) {
		parts.push(`${payload.removed_chunk_mentions.length} mention links removed`);
	}
	if (Array.isArray(payload.removed_relationships)) {
		parts.push(`${payload.removed_relationships.length} relationships removed`);
	}
	return parts.join(' | ');
}

/** @param {unknown} value */
export function isGenericReason(value) {
	return String(value || '').trim() === GENERIC_CURATION_REASON;
}

/** @param {GraphData} payload */
export function verificationTransition(payload) {
	if (
		!Object.prototype.hasOwnProperty.call(payload || {}, 'verification_state') ||
		!payload?.verification_state
	)
		return '';
	const oldState = String(payload.old_verification_state || 'unverified');
	const newState = String(payload.verification_state || 'unverified');
	if (oldState === newState) return '';
	return `${stateLabel(oldState)} -> ${stateLabel(newState)}`;
}

/** @param {GraphChange} change */
export function changeMetaLine(change) {
	const parts = [];
	const source = change?.filename || change?.document_id || '';
	const actor = String(change?.actor || '').trim();
	if (source) parts.push(source);
	if (actor && !INTERNAL_ACTORS.has(actor)) parts.push(actorLabel(actor));
	return parts.join(' / ');
}

/** @param {string} actor */
export function actorLabel(actor) {
	if (actor === 'lamb-ingestion-pipeline') return 'Ingestion pipeline';
	return actor;
}

/** @param {unknown} value */
export function stateLabel(value) {
	const state = String(value || 'unverified');
	if (state === 'unverified') return 'Unreviewed';
	if (state === 'needs_review') return 'Needs review';
	if (state === 'verified') return 'Approved';
	if (state === 'rejected') return 'Expunged';
	return state;
}

/** @param {unknown} value */
export function stateRank(value) {
	const state = String(value || 'unverified');
	if (state === 'needs_review') return 0;
	if (state === 'unverified') return 1;
	if (state === 'rejected') return 2;
	if (state === 'verified') return 3;
	return 4;
}

/** @param {unknown} value */
export function stateClass(value) {
	const state = String(value || 'unverified');
	if (state === 'verified') return 'bg-emerald-50 text-emerald-700 ring-emerald-200';
	if (state === 'rejected') return 'bg-red-50 text-red-700 ring-red-200';
	if (state === 'needs_review') return 'bg-amber-50 text-amber-800 ring-amber-200';
	return 'bg-slate-50 text-slate-700 ring-slate-200';
}

/**
 * @param {GraphChange[]} sourceChanges
 * @param {GraphEdge[]} activeEdges
 * @returns {GraphEdge[]}
 */
export function buildExpungedRelationships(sourceChanges, activeEdges) {
	const activeKeys = new Set(
		(activeEdges || []).map((edge) =>
			relationshipIdentityKey(edge.data?.source, edge.data?.target, edge.data?.relation)
		)
	);
	const seen = new Set();
	const rows = [];
	for (const change of sourceChanges || []) {
		const payload = changePayload(change);
		const candidates = [];
		if (change.operation === 'manual_expunge_relationship') {
			candidates.push({
				source: payload.source,
				target: payload.target,
				relation: payload.relation || payload.new_relation || 'related_to',
				weight: payload.old_weight,
				description: payload.old_description,
				evidence: payload.old_evidence,
				chunk_id: payload.old_chunk_id,
				notes: payload.old_notes,
				tags: payload.old_tags
			});
		}
		if (
			change.operation === 'manual_expunge_concept' &&
			Array.isArray(payload.removed_relationships)
		) {
			candidates.push(
				...payload.removed_relationships.map((relationship) => ({
					...relationship,
					expunged_by_concept: payload.concept
				}))
			);
		}
		for (const [index, relationship] of candidates.entries()) {
			const source = String(relationship.source || '').trim();
			const target = String(relationship.target || '').trim();
			const relation = String(relationship.relation || 'related_to').trim() || 'related_to';
			const key = relationshipIdentityKey(source, target, relation);
			if (!source || !target || activeKeys.has(key) || seen.has(key)) continue;
			seen.add(key);
			rows.push({
				id: `expunged-relationship-${change.event_id || key}${change.operation === 'manual_expunge_concept' ? `-${index}` : ''}`,
				type: 'RELATES_TO',
				source: `concept:${source}`,
				target: `concept:${target}`,
				label: relation,
				weight: valueOrUndefined(relationship.weight),
				data: {
					source,
					target,
					source_label: source,
					target_label: target,
					relation,
					description: relationship.description || '',
					evidence: relationship.evidence || '',
					chunk_id: relationship.chunk_id || '',
					notes: relationship.notes || '',
					tags: Array.isArray(relationship.tags) ? relationship.tags : [],
					verification_state: 'rejected',
					expunged: true,
					expunge_event_id: change.event_id,
					expunged_at: change.timestamp,
					expunged_by_concept: relationship.expunged_by_concept || ''
				}
			});
		}
	}
	return rows;
}

/**
 * @param {GraphChange[]} sourceChanges
 * @param {GraphNode[]} activeNodes
 * @returns {GraphNode[]}
 */
export function buildExpungedConcepts(sourceChanges, activeNodes) {
	const activeNames = new Set((activeNodes || []).map((node) => String(node.data?.name || '')));
	const seen = new Set();
	const rows = [];
	for (const change of sourceChanges || []) {
		if (change.operation !== 'manual_expunge_concept') continue;
		const payload = changePayload(change);
		const concept = String(payload.concept || change.concepts?.[0] || '').trim();
		if (!concept || activeNames.has(concept) || seen.has(concept)) continue;
		seen.add(concept);
		const removedMentions = Array.isArray(payload.removed_chunk_mentions)
			? payload.removed_chunk_mentions
			: [];
		const removedRelationships = Array.isArray(payload.removed_relationships)
			? payload.removed_relationships
			: [];
		rows.push({
			id: `expunged-concept-${change.event_id || concept}`,
			type: 'concept',
			label: concept,
			data: {
				name: concept,
				entity_type: 'concept',
				chunk_count: removedMentions.length,
				relationship_count: removedRelationships.length,
				notes: payload.old_notes || '',
				tags: Array.isArray(payload.old_tags) ? payload.old_tags : [],
				verification_state: 'rejected',
				expunged: true,
				expunge_event_id: change.event_id,
				expunged_at: change.timestamp
			}
		});
	}
	return rows;
}

export function relationshipIdentityKey(source, target, relation) {
	return [source, target, relation]
		.map((value) =>
			String(value || '')
				.trim()
				.toLowerCase()
		)
		.join('|');
}

export function valueOrUndefined(value) {
	return value === undefined || value === null || value === '' ? undefined : value;
}
