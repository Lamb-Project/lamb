"""Worker cancellation-branch tests for ``tasks.worker._process_job_sync``.

Covers the two cancellation exits: cancelled-before-pickup and the
cooperative ``JobCancelledError`` raised mid-ingestion.
"""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

import services.ingestion_service as ing
from database.connection import get_session_direct
from database.models import Collection, IngestionJob
from tasks.worker import _process_job_sync


def _seed_collection(session) -> str:
    cid = f"col-wk-{uuid4().hex[:8]}"
    session.add(Collection(
        id=cid, organization_id="org-wk", name=f"wk-{uuid4().hex[:6]}",
        chunking_strategy="simple",
        chunking_params=json.dumps({"chunk_size": 200, "chunk_overlap": 20}),
        embedding_vendor="fake", embedding_model="fake-model",
        vector_db_backend="chromadb", backend_collection_id=cid,
        storage_path="/tmp/wk-does-not-matter",
    ))
    session.commit()
    return cid


def _seed_job(session, collection_id, status) -> str:
    jid = f"job-wk-{uuid4().hex[:8]}"
    session.add(IngestionJob(
        id=jid, collection_id=collection_id, organization_id="org-wk",
        documents_json=json.dumps([{"source_item_id": "s1", "title": "T",
                                    "text": "body", "permalinks": {}, "pages": [],
                                    "extra_metadata": {}}]),
        documents_total=1, status=status,
    ))
    session.commit()
    return jid


def test_process_job_cancelled_before_pickup():
    session = get_session_direct()
    try:
        cid = _seed_collection(session)
        jid = _seed_job(session, cid, status="cancelled")
    finally:
        session.close()

    # Should return early without flipping back to processing.
    _process_job_sync(jid)

    check = get_session_direct()
    try:
        job = check.query(IngestionJob).filter(IngestionJob.id == jid).first()
        assert job.status == "cancelled"
    finally:
        check.close()


def test_process_job_cooperative_cancellation(monkeypatch):
    session = get_session_direct()
    try:
        cid = _seed_collection(session)
        jid = _seed_job(session, cid, status="pending")
    finally:
        session.close()

    # Force the ingestion to raise the cooperative-cancel signal once running.
    def _raise_cancelled(db, job, collection, credentials):
        raise ing.JobCancelledError("cancelled mid-flight")

    monkeypatch.setattr(ing, "execute_ingestion_job", _raise_cancelled)

    _process_job_sync(jid)

    # The worker leaves the row alone on cooperative cancel (does not mark
    # completed/failed). Status stays whatever the canceller left it.
    check = get_session_direct()
    try:
        job = check.query(IngestionJob).filter(IngestionJob.id == jid).first()
        assert job.status != "completed"
    finally:
        check.close()
