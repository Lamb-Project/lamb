"""Unit tests for ``schemas.graph`` — the KG-RAG traceability/curation models.

These are pure Pydantic models, but they were previously never imported by
any test, leaving the whole module uncovered. We instantiate every model in
both its minimal (required-only) and fully-populated forms, and assert the
documented defaults so a future field rename or default change is caught.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from schemas.graph import (
    GraphChangeDetail,
    GraphChangeEvent,
    GraphConceptCurationRequest,
    GraphConceptMergeRequest,
    GraphConceptRenameRequest,
    GraphEdge,
    GraphManualOperationResponse,
    GraphNode,
    GraphRelationshipCurationRequest,
    GraphRelationshipEditRequest,
    GraphRevertRequest,
    GraphRevertResponse,
    GraphSnapshotResponse,
)


def test_graph_change_event_minimal_defaults():
    ev = GraphChangeEvent(
        event_id="e1",
        collection_id="c1",
        org_id="org1",
        operation="add_document",
    )
    assert ev.actor is None
    assert ev.concepts == []
    assert ev.payload_json is None
    assert ev.file_id is None


def test_graph_change_event_full_payload():
    ev = GraphChangeEvent(
        event_id="e1",
        collection_id="c1",
        org_id="org1",
        operation="add_document",
        actor="user@example.com",
        timestamp="2026-06-20T00:00:00Z",
        filename="doc.pdf",
        concepts=["alpha", "beta"],
        payload_json='{"k": "v"}',
        document_id="d1",
        file_id=42,
    )
    assert ev.concepts == ["alpha", "beta"]
    assert ev.file_id == 42


def test_graph_change_event_requires_core_fields():
    with pytest.raises(ValidationError):
        GraphChangeEvent(event_id="e1")  # missing collection_id/org_id/operation


def test_graph_change_detail_extends_event_with_chunk_ids():
    detail = GraphChangeDetail(
        event_id="e1",
        collection_id="c1",
        org_id="org1",
        operation="add_document",
        chunk_ids=["chunk-1", "chunk-2"],
    )
    # Inherited fields plus the new list.
    assert detail.operation == "add_document"
    assert detail.chunk_ids == ["chunk-1", "chunk-2"]
    # Default still applies for the chunk list.
    assert GraphChangeDetail(
        event_id="e2", collection_id="c1", org_id="org1", operation="op"
    ).chunk_ids == []


def test_graph_revert_request_defaults():
    req = GraphRevertRequest()
    assert req.actor == "graph-traceability-api"
    assert req.reason == ""
    custom = GraphRevertRequest(actor="me", reason="mistake")
    assert custom.actor == "me"


def test_graph_revert_response():
    resp = GraphRevertResponse(reverted=True)
    assert resp.reverted is True
    assert resp.chunk_ids == []
    full = GraphRevertResponse(
        reverted=False,
        reason="not found",
        event_id="e1",
        revert_event_id="r1",
        operation="add_document",
        document_id="d1",
        chunk_ids=["c1"],
    )
    assert full.reason == "not found"
    assert full.chunk_ids == ["c1"]


def test_graph_node_and_edge():
    node = GraphNode(id="n1", type="concept", label="Alpha")
    assert node.data == {}
    edge = GraphEdge(id="e1", type="related_to", source="n1", target="n2")
    assert edge.label is None
    assert edge.weight is None
    assert edge.data == {}
    weighted = GraphEdge(
        id="e2",
        type="related_to",
        source="n1",
        target="n2",
        label="relates",
        weight=0.75,
        data={"evidence": "x"},
    )
    assert weighted.weight == 0.75


def test_graph_snapshot_response_defaults():
    snap = GraphSnapshotResponse(collection_id="c1")
    assert snap.nodes == []
    assert snap.edges == []
    assert snap.filters == {}
    assert snap.counts == {}
    populated = GraphSnapshotResponse(
        collection_id="c1",
        nodes=[GraphNode(id="n1", type="concept", label="A")],
        edges=[GraphEdge(id="e1", type="rel", source="n1", target="n1")],
        filters={"verification_state": "verified"},
        counts={"nodes": 1, "edges": 1},
    )
    assert populated.counts["nodes"] == 1


def test_graph_manual_operation_response():
    resp = GraphManualOperationResponse(ok=True)
    assert resp.operation is None
    assert resp.details == {}
    resp2 = GraphManualOperationResponse(
        ok=False, operation="rename", event_id="e1", reason="blocked", details={"x": 1}
    )
    assert resp2.details == {"x": 1}


def test_concept_rename_and_merge_requests():
    rename = GraphConceptRenameRequest(new_name="Beta")
    assert rename.actor == "graph-curation-api"
    assert rename.reason == ""

    merge = GraphConceptMergeRequest(
        source_names=["a", "b"], target_name="c"
    )
    assert merge.source_names == ["a", "b"]
    assert merge.actor == "graph-curation-api"

    with pytest.raises(ValidationError):
        GraphConceptMergeRequest(target_name="c")  # missing source_names


def test_concept_curation_request_defaults():
    req = GraphConceptCurationRequest()
    assert req.notes is None
    assert req.tags is None
    assert req.verification_state is None
    assert req.actor == "graph-curation-api"
    full = GraphConceptCurationRequest(
        notes="n", tags=["t1"], verification_state="verified", reason="cleanup"
    )
    assert full.tags == ["t1"]


def test_relationship_edit_request():
    req = GraphRelationshipEditRequest(
        source_concept="a", target_concept="b", relation="related_to"
    )
    assert req.new_relation is None
    assert req.weight is None
    assert req.actor == "graph-curation-api"
    full = GraphRelationshipEditRequest(
        source_concept="a",
        target_concept="b",
        relation="related_to",
        new_relation="depends_on",
        weight=0.5,
        description="d",
        evidence="e",
        notes="n",
        tags=["t"],
        verification_state="verified",
    )
    assert full.new_relation == "depends_on"
    assert full.weight == 0.5

    with pytest.raises(ValidationError):
        GraphRelationshipEditRequest(source_concept="a")  # missing target/relation


def test_relationship_curation_request():
    req = GraphRelationshipCurationRequest(
        source_concept="a", target_concept="b", relation="related_to"
    )
    assert req.notes is None
    assert req.actor == "graph-curation-api"
    assert req.reason == ""
