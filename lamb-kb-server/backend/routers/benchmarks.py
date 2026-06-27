"""Benchmark endpoints for vector RAG versus KG-RAG evaluation."""

from __future__ import annotations

from database.connection import get_session
from dependencies import verify_token
from fastapi import APIRouter, Depends
from schemas.benchmark import (
    BenchmarkDataset,
    BenchmarkDatasetSummary,
    BenchmarkRunAllRequest,
    BenchmarkRunAllResponse,
    BenchmarkRunRequest,
    BenchmarkRunResponse,
)
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
    body: BenchmarkRunRequest,
    db: Session = Depends(get_session),
) -> BenchmarkRunResponse:
    """Run one benchmark dataset.

    Single body parameter so FastAPI doesn't force the LAMB proxy to wrap
    fields under ``request``. Embedded ``embedding_credentials`` carry the
    per-request key for the baseline vector pass.
    """
    creds = body.embedding_credentials
    return BenchmarkService.run(
        db=db,
        collection_id=collection_id,
        request=body,
        embedding_credentials={
            "api_key": creds.api_key,
            "api_endpoint": creds.api_endpoint,
        },
    )


@router.post(
    "/collections/{collection_id}/run-all",
    response_model=BenchmarkRunAllResponse,
    summary="Run all selected benchmark datasets against a collection",
)
async def run_all_collection_benchmarks(
    collection_id: str,
    body: BenchmarkRunAllRequest,
    db: Session = Depends(get_session),
) -> BenchmarkRunAllResponse:
    creds = body.embedding_credentials
    return BenchmarkService.run_all(
        db=db,
        collection_id=collection_id,
        dataset_ids=body.dataset_ids,
        threshold=body.threshold,
        embedding_credentials={
            "api_key": creds.api_key,
            "api_endpoint": creds.api_endpoint,
        },
    )
