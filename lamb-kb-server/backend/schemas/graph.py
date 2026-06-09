"""Schemas for KG-RAG graph traceability endpoints."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class GraphChangeEvent(BaseModel):
    event_id: str = Field(..., description="Unique graph change event ID")
    collection_id: str = Field(..., description="Collection ID")
    org_id: str = Field(..., description="Organization or owner scope")
    operation: str = Field(..., description="Graph operation name")
    actor: Optional[str] = Field(None, description="Actor that produced the change")
    timestamp: Optional[str] = Field(None, description="Change timestamp")
    filename: Optional[str] = Field(None, description="Source filename")
    concepts: List[str] = Field(
        default_factory=list, description="Concepts touched by the change"
    )
    payload_json: Optional[str] = Field(
        None, description="Raw JSON payload stored in Neo4j"
    )
    document_id: Optional[str] = Field(None, description="Related graph document ID")
    file_id: Optional[int] = Field(None, description="Related file registry ID")


class GraphChangeDetail(GraphChangeEvent):
    chunk_ids: List[str] = Field(
        default_factory=list, description="Related graph chunk IDs"
    )


class GraphRevertRequest(BaseModel):
    actor: str = Field(
        "graph-traceability-api", description="Actor requesting the revert"
    )
    reason: str = Field("", description="Human-readable reason for the revert")


class GraphRevertResponse(BaseModel):
    reverted: bool = Field(..., description="Whether the revert was applied")
    reason: Optional[str] = Field(None, description="Reason when no revert was applied")
    event_id: Optional[str] = Field(None, description="Requested event ID")
    revert_event_id: Optional[str] = Field(
        None, description="Audit event created for the revert"
    )
    operation: Optional[str] = Field(None, description="Original operation")
    document_id: Optional[str] = Field(None, description="Reverted graph document ID")
    chunk_ids: List[str] = Field(
        default_factory=list, description="Reverted graph chunk IDs"
    )


class GraphNode(BaseModel):
    id: str = Field(..., description="Stable frontend node ID")
    type: str = Field(..., description="Node type, such as concept or chunk")
    label: str = Field(..., description="Human-readable node label")
    data: Dict[str, Any] = Field(default_factory=dict, description="Node metadata")


class GraphEdge(BaseModel):
    id: str = Field(..., description="Stable frontend edge ID")
    type: str = Field(..., description="Graph edge type")
    source: str = Field(..., description="Source node ID")
    target: str = Field(..., description="Target node ID")
    label: Optional[str] = Field(None, description="Human-readable edge label")
    weight: Optional[float] = Field(None, description="Edge weight")
    data: Dict[str, Any] = Field(default_factory=dict, description="Edge metadata")


class GraphSnapshotResponse(BaseModel):
    collection_id: str = Field(..., description="Collection ID")
    nodes: List[GraphNode] = Field(default_factory=list, description="Graph nodes")
    edges: List[GraphEdge] = Field(default_factory=list, description="Graph edges")
    filters: Dict[str, Any] = Field(default_factory=dict, description="Applied filters")
    counts: Dict[str, int] = Field(
        default_factory=dict, description="Graph summary counts"
    )


class GraphManualOperationResponse(BaseModel):
    ok: bool = Field(..., description="Whether the manual graph operation was applied")
    operation: Optional[str] = Field(None, description="Recorded manual operation name")
    event_id: Optional[str] = Field(
        None, description="ChangeEvent ID recorded for the operation"
    )
    reason: Optional[str] = Field(
        None, description="Reason when the operation was not applied"
    )
    details: Dict[str, Any] = Field(
        default_factory=dict, description="Operation-specific details"
    )


class GraphConceptRenameRequest(BaseModel):
    new_name: str = Field(..., description="New concept name")
    actor: str = Field("graph-curation-api", description="Actor requesting the rename")
    reason: str = Field("", description="Human-readable reason for the rename")


class GraphConceptMergeRequest(BaseModel):
    source_names: List[str] = Field(
        ..., description="Concept names to merge into the target"
    )
    target_name: str = Field(..., description="Target concept name")
    actor: str = Field("graph-curation-api", description="Actor requesting the merge")
    reason: str = Field("", description="Human-readable reason for the merge")


class GraphConceptCurationRequest(BaseModel):
    notes: Optional[str] = Field(None, description="Manual curation notes")
    tags: Optional[List[str]] = Field(None, description="Manual curation tags")
    verification_state: Optional[str] = Field(None, description="Verification state")
    actor: str = Field("graph-curation-api", description="Actor requesting the update")
    reason: str = Field("", description="Human-readable reason for the update")


class GraphRelationshipEditRequest(BaseModel):
    source_concept: str = Field(..., description="Source concept name")
    target_concept: str = Field(..., description="Target concept name")
    relation: str = Field(..., description="Current relationship relation value")
    new_relation: Optional[str] = Field(
        None, description="New relationship relation value"
    )
    weight: Optional[float] = Field(None, description="New relationship weight")
    description: Optional[str] = Field(None, description="Relationship description")
    evidence: Optional[str] = Field(None, description="Relationship evidence")
    notes: Optional[str] = Field(None, description="Manual curation notes")
    tags: Optional[List[str]] = Field(None, description="Manual curation tags")
    verification_state: Optional[str] = Field(None, description="Verification state")
    actor: str = Field("graph-curation-api", description="Actor requesting the update")
    reason: str = Field("", description="Human-readable reason for the update")


class GraphRelationshipCurationRequest(BaseModel):
    source_concept: str = Field(..., description="Source concept name")
    target_concept: str = Field(..., description="Target concept name")
    relation: str = Field(..., description="Current relationship relation value")
    notes: Optional[str] = Field(None, description="Manual curation notes")
    tags: Optional[List[str]] = Field(None, description="Manual curation tags")
    verification_state: Optional[str] = Field(None, description="Verification state")
    actor: str = Field("graph-curation-api", description="Actor requesting the update")
    reason: str = Field("", description="Human-readable reason for the update")
