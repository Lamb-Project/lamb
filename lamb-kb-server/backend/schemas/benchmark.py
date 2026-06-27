"""Schemas for KG-RAG benchmark evaluation."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class BenchmarkQuestion(BaseModel):
    id: str = Field(..., description="Stable question ID")
    question: str = Field(..., description="Question text to retrieve against")
    expected_answer: Optional[str] = Field("", description="Reference answer")
    relevant_files: List[str] = Field(
        default_factory=list, description="Relevant source filenames"
    )
    expected_concepts: List[str] = Field(
        default_factory=list, description="Expected graph concepts"
    )
    kind: str = Field("custom", description="Question category")
    answerable: bool = Field(True, description="Whether the answer is present")


class BenchmarkDatasetSummary(BaseModel):
    id: str
    name: str
    description: str
    expected_behavior: str = Field(
        ..., description="Expected KG-RAG behavior for this dataset"
    )
    recommended_top_k: int
    recommended_graph_depth: int
    question_count: int


class BenchmarkDataset(BenchmarkDatasetSummary):
    questions: List[BenchmarkQuestion]


class BenchmarkMetrics(BaseModel):
    precision_at_k: float = 0.0
    recall_at_k: float = 0.0
    mrr: float = 0.0
    avg_vector_ms: float = 0.0
    avg_graph_ms: float = 0.0
    avg_total_ms: float = 0.0


class BenchmarkQueryScore(BaseModel):
    precision_at_k: float = 0.0
    recall_at_k: float = 0.0
    mrr: float = 0.0
    vector_ms: float = 0.0
    graph_ms: float = 0.0
    total_ms: float = 0.0
    retrieved_files: List[str] = Field(default_factory=list)


class BenchmarkQueryResult(BaseModel):
    question_id: str
    question: str
    kind: str
    relevant_files: List[str]
    expected_concepts: List[str] = Field(default_factory=list)
    baseline: BenchmarkQueryScore
    kg_rag: BenchmarkQueryScore


class BenchmarkComparison(BaseModel):
    delta_precision_at_k: float = 0.0
    delta_recall_at_k: float = 0.0
    delta_mrr: float = 0.0
    graph_overhead_ms: float = 0.0
    expected_behavior: str


class EmbeddingCredentialsBody(BaseModel):
    """Embedded request-scoped embedding credentials.

    Mirrors :class:`schemas.content.EmbeddingCredentials` but lives on the
    benchmark request models so the LAMB proxy can send a single flat body
    instead of having to wrap fields under ``request`` (which FastAPI
    requires when multiple ``Body`` parameters coexist on one route).
    """

    api_key: str = Field(default="", description="Vendor API key.")
    api_endpoint: str = Field(
        default="", description="Optional API base URL override."
    )


class BenchmarkRunRequest(BaseModel):
    """Body for a single benchmark run.

    Extra fields are allowed so callers can pass plugin-specific
    tuning knobs (``rrf_k``, ``graph_weight``, ``graph_limit_factor``)
    without requiring a schema change. ``BenchmarkService.run``
    forwards any recognised extra field to the KG-RAG plugin via
    ``plugin_params``.
    """

    model_config = ConfigDict(extra="allow")

    dataset_id: Optional[str] = Field(
        "educational", description="Built-in dataset ID to use when questions are omitted"
    )
    questions: Optional[List[BenchmarkQuestion]] = Field(
        None, description="Custom benchmark questions"
    )
    top_k: Optional[int] = Field(None, ge=1, le=50)
    graph_depth: Optional[int] = Field(None, ge=1, le=4)
    threshold: float = Field(0.0, ge=0.0, le=1.0)
    embedding_credentials: EmbeddingCredentialsBody = Field(
        default_factory=EmbeddingCredentialsBody,
        description=(
            "Per-request embedding credentials. LAMB resolves these from "
            "``setups.default.providers.{vendor}.api_key``; the field is "
            "optional so direct callers can omit it."
        ),
    )


class BenchmarkRunResponse(BaseModel):
    collection_id: str
    dataset_id: str
    dataset_name: str
    top_k: int
    graph_depth: int
    baseline: BenchmarkMetrics
    kg_rag: BenchmarkMetrics
    comparison: BenchmarkComparison
    results: List[BenchmarkQueryResult]


class BenchmarkRunAllRequest(BaseModel):
    dataset_ids: List[str] = Field(
        default_factory=lambda: ["educational", "control", "paper", "extreme"]
    )
    threshold: float = Field(0.0, ge=0.0, le=1.0)
    embedding_credentials: EmbeddingCredentialsBody = Field(
        default_factory=EmbeddingCredentialsBody,
        description="Per-request embedding credentials (same semantics as BenchmarkRunRequest).",
    )


class BenchmarkRunAllResponse(BaseModel):
    collection_id: str
    runs: List[BenchmarkRunResponse]
    summary: Dict[str, Any] = Field(default_factory=dict)
