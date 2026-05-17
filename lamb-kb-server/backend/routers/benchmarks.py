"""Benchmark endpoints for vector RAG versus KG-RAG evaluation."""

from __future__ import annotations

from database.connection import get_session
from dependencies import verify_token
from fastapi import APIRouter, Body, Depends
from schemas.benchmark import (
    BenchmarkDataset,
    BenchmarkDatasetSummary,
    BenchmarkRunAllRequest,
    BenchmarkRunAllResponse,
    BenchmarkRunRequest,
    BenchmarkRunResponse,
)
from schemas.content import EmbeddingCredentials
from services.benchmark import BenchmarkService
from sqlalchemy.orm import Session

router = APIRouter(
    prefix="/benchmarks",
    tags=["Benchmarks"],
    dependencies=[Depends(verify_token)],
)


@router.get(
    "/datasets",
    response_model=list[BenchmarkDatasetSummary],
    summary="List built-in benchmark datasets",
)
async def list_benchmark_datasets() -> list[BenchmarkDatasetSummary]:
    return BenchmarkService.list_datasets()


@router.get(
    "/datasets/{dataset_id}",
    response_model=BenchmarkDataset,
    summary="Get a built-in benchmark dataset",
)
async def get_benchmark_dataset(dataset_id: str) -> BenchmarkDataset:
    return BenchmarkService.get_dataset(dataset_id)


@router.post(
    "/collections/{collection_id}/run",
    response_model=BenchmarkRunResponse,
    summary="Run a benchmark dataset against a collection",
)
async def run_collection_benchmark(
    collection_id: str,
    request: BenchmarkRunRequest,
    embedding_credentials: EmbeddingCredentials = Body(
        default_factory=EmbeddingCredentials,
        embed=True,
    ),
    db: Session = Depends(get_session),
) -> BenchmarkRunResponse:
    return BenchmarkService.run(
        db=db,
        collection_id=collection_id,
        request=request,
        embedding_credentials={
            "api_key": embedding_credentials.api_key,
            "api_endpoint": embedding_credentials.api_endpoint,
        },
    )


@router.post(
    "/collections/{collection_id}/run-all",
    response_model=BenchmarkRunAllResponse,
    summary="Run all selected benchmark datasets against a collection",
)
async def run_all_collection_benchmarks(
    collection_id: str,
    request: BenchmarkRunAllRequest,
    embedding_credentials: EmbeddingCredentials = Body(
        default_factory=EmbeddingCredentials,
        embed=True,
    ),
    db: Session = Depends(get_session),
) -> BenchmarkRunAllResponse:
    return BenchmarkService.run_all(
        db=db,
        collection_id=collection_id,
        dataset_ids=request.dataset_ids,
        threshold=request.threshold,
        embedding_credentials={
            "api_key": embedding_credentials.api_key,
            "api_endpoint": embedding_credentials.api_endpoint,
        },
    )
