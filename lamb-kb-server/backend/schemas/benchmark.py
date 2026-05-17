"""Schemas for KG-RAG benchmark evaluation."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


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


class BenchmarkRunRequest(BaseModel):
    dataset_id: Optional[str] = Field(
        "educational", description="Built-in dataset ID to use when questions are omitted"
    )
    questions: Optional[List[BenchmarkQuestion]] = Field(
        None, description="Custom benchmark questions"
    )
    top_k: Optional[int] = Field(None, ge=1, le=50)
    graph_depth: Optional[int] = Field(None, ge=1, le=4)
    threshold: float = Field(0.0, ge=0.0, le=1.0)


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


class BenchmarkRunAllResponse(BaseModel):
    collection_id: str
    runs: List[BenchmarkRunResponse]
    summary: Dict[str, Any] = Field(default_factory=dict)
