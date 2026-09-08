#!/usr/bin/env python3
"""Document cache impact test: measures request latency with/without document RAG cache.

Reads X-Doc-RAG-Time-Ms and X-Doc-RAG-Cache headers from responses to measure
the document fetch time separately from total request time.

Usage:
    python cache_test_simulation.py --label no_cache    # run with cache disabled in backend
    python cache_test_simulation.py --label with_cache  # run with cache enabled in backend

The cache toggle is controlled via DOCUMENT_RAG_CACHE_ENABLED in backend/.env,
requiring a backend container recreate between runs.
"""

import argparse
import asyncio
import json
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path

import aiohttp
from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).parent
load_dotenv(SCRIPT_DIR / ".env")

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:9099").rstrip("/")
CREATOR_EMAIL = os.getenv("CREATOR_EMAIL")
CREATOR_PASSWORD = os.getenv("CREATOR_PASSWORD")
ASSISTANT_ID = os.getenv("ASSISTANT_ID")

NUM_STUDENTS = int(os.getenv("SIM_NUM_STUDENTS", "20"))
DURATION_MINUTES = int(os.getenv("SIM_DURATION_MINUTES", "15"))
INTERVAL_MIN_S = float(os.getenv("SIM_INTERVAL_MIN_S", "25"))
INTERVAL_MAX_S = float(os.getenv("SIM_INTERVAL_MAX_S", "75"))

QUESTIONS_FILE = SCRIPT_DIR / "questions" / "kv_cache_pool.txt"


def load_questions():
    if not QUESTIONS_FILE.exists():
        print(f"ERROR: Questions file not found: {QUESTIONS_FILE}")
        sys.exit(1)
    questions = [line.strip() for line in QUESTIONS_FILE.read_text().splitlines() if line.strip()]
    if not questions:
        print("ERROR: No questions in pool")
        sys.exit(1)
    return questions


async def login(session: aiohttp.ClientSession) -> str:
    form_data = aiohttp.FormData()
    form_data.add_field("email", CREATOR_EMAIL)
    form_data.add_field("password", CREATOR_PASSWORD)
    async with session.post(f"{API_BASE_URL}/creator/login", data=form_data) as resp:
        if resp.status != 200:
            text = await resp.text()
            print(f"Login failed: {resp.status} - {text}")
            sys.exit(1)
        result = await resp.json()
        if not result.get("success"):
            print(f"Login failed: {result.get('error')}")
            sys.exit(1)
        return result["data"]["token"]


async def send_chat(
    session: aiohttp.ClientSession, token: str, question: str,
    student_id: int, request_num: int, max_retries: int = 3,
) -> dict:
    payload = {
        "messages": [{"role": "user", "content": question}],
        "stream": False,
        "persist_chat": False,
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    for attempt in range(max_retries + 1):
        start_time = time.time()
        async with session.post(
            f"{API_BASE_URL}/creator/assistant/{ASSISTANT_ID}/chat/completions",
            json=payload, headers=headers,
        ) as resp:
            elapsed = time.time() - start_time
            status = resp.status

            if status == 429 and attempt < max_retries:
                backoff = min(2 ** attempt * 5, 60)
                print(f"  [student {student_id}] 429 — retry {attempt+1}/{max_retries} in {backoff}s")
                await asyncio.sleep(backoff)
                continue

            doc_rag_time_ms = resp.headers.get("X-Doc-RAG-Time-Ms")
            doc_rag_cache = resp.headers.get("X-Doc-RAG-Cache", "unknown")

            if status == 200:
                data = await resp.json()
                usage = data.get("usage", {})
                return {
                    "student_id": student_id,
                    "request_num": request_num,
                    "question": question,
                    "status": status,
                    "total_time_ms": round(elapsed * 1000, 1),
                    "doc_rag_time_ms": float(doc_rag_time_ms) if doc_rag_time_ms else None,
                    "doc_rag_cache": doc_rag_cache,
                    "timestamp": datetime.now().isoformat(),
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                }
            else:
                text = await resp.text()
                return {
                    "student_id": student_id,
                    "request_num": request_num,
                    "question": question,
                    "status": status,
                    "total_time_ms": round(elapsed * 1000, 1),
                    "doc_rag_time_ms": float(doc_rag_time_ms) if doc_rag_time_ms else None,
                    "doc_rag_cache": doc_rag_cache,
                    "timestamp": datetime.now().isoformat(),
                    "error": text[:200],
                }

    return {
        "student_id": student_id, "request_num": request_num, "question": question,
        "status": 429, "total_time_ms": 0, "doc_rag_time_ms": None,
        "doc_rag_cache": "unknown", "timestamp": datetime.now().isoformat(),
        "error": "Rate limit exceeded after retries",
    }


async def student_loop(
    student_id, session, token, questions, duration_s, results, results_lock,
):
    start = time.time()
    request_num = 0
    while time.time() - start < duration_s:
        question = random.choice(questions)
        request_num += 1
        result = await send_chat(session, token, question, student_id, request_num)
        async with results_lock:
            results.append(result)
        interval = random.uniform(INTERVAL_MIN_S, INTERVAL_MAX_S)
        await asyncio.sleep(interval)


async def run_simulation(run_label: str):
    print(f"\n=== DOCUMENT CACHE TEST: {run_label} ===")
    print(f"Students: {NUM_STUDENTS}, Duration: {DURATION_MINUTES} min")
    print(f"Interval: {INTERVAL_MIN_S}-{INTERVAL_MAX_S}s\n")

    async with aiohttp.ClientSession() as session:
        token = await login(session)
        print(f"Logged in as {CREATOR_EMAIL}")

        questions = load_questions()
        print(f"Loaded {len(questions)} questions")

        # Smoke test: verify headers are present before full run (1 request is enough)
        print("Smoke test: verifying X-Doc-RAG-* headers...")
        r = await send_chat(session, token, questions[0], 0, 0)
        if r.get("doc_rag_time_ms") is None or r.get("doc_rag_cache") == "unknown":
            print("ERROR: Headers missing in smoke request")
            print("       Verify that the assistant has document_rag: single_file_rag configured")
            print("       and that the backend has been recreated with DOCUMENT_RAG_CACHE_ENABLED set")
            sys.exit(1)
        print(f"Smoke test PASSED: doc_rag_time_ms={r['doc_rag_time_ms']}, cache={r['doc_rag_cache']}\n")

        results = []
        results_lock = asyncio.Lock()
        duration_s = DURATION_MINUTES * 60

        tasks = [
            student_loop(sid, session, token, questions, duration_s, results, results_lock)
            for sid in range(NUM_STUDENTS)
        ]

        print(f"Starting {NUM_STUDENTS} students...")
        start_time = time.time()

        async def report_progress():
            while time.time() - start_time < duration_s:
                await asyncio.sleep(30)
                elapsed = time.time() - start_time
                print(f"  [{elapsed/60:.1f}/{DURATION_MINUTES} min] {len(results)} requests")

        await asyncio.gather(*tasks, report_progress())

        elapsed_total = time.time() - start_time
        print(f"\nComplete in {elapsed_total/60:.1f} min, {len(results)} requests")

        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_dir = SCRIPT_DIR / "results" / f"{run_label}_{run_id}"
        results_dir.mkdir(parents=True, exist_ok=True)

        results_file = results_dir / "requests.jsonl"
        with open(results_file, "w") as f:
            for r in results:
                f.write(json.dumps(r) + "\n")

        successful = [r for r in results if r.get("status") == 200]
        failed = [r for r in results if r.get("status") != 200]
        doc_times = [r["doc_rag_time_ms"] for r in successful if r.get("doc_rag_time_ms") is not None]
        total_times = [r["total_time_ms"] for r in successful]
        cache_hits = sum(1 for r in successful if r.get("doc_rag_cache") == "hit")
        cache_misses = sum(1 for r in successful if r.get("doc_rag_cache") == "miss")

        summary = {
            "run_label": run_label,
            "run_id": run_id,
            "timestamp": datetime.now().isoformat(),
            "num_students": NUM_STUDENTS,
            "duration_minutes": DURATION_MINUTES,
            "total_requests": len(results),
            "successful_requests": len(successful),
            "failed_requests": len(failed),
            "error_rate": round(len(failed) / len(results) * 100, 2) if results else 0,
            "total_time_ms": {
                "min": round(min(total_times), 1) if total_times else 0,
                "max": round(max(total_times), 1) if total_times else 0,
                "mean": round(sum(total_times) / len(total_times), 1) if total_times else 0,
                "median": round(sorted(total_times)[len(total_times)//2], 1) if total_times else 0,
            },
            "doc_rag_time_ms": {
                "min": round(min(doc_times), 2) if doc_times else 0,
                "max": round(max(doc_times), 2) if doc_times else 0,
                "mean": round(sum(doc_times) / len(doc_times), 2) if doc_times else 0,
                "median": round(sorted(doc_times)[len(doc_times)//2], 2) if doc_times else 0,
            },
            "cache_hits": cache_hits,
            "cache_misses": cache_misses,
            "cache_hit_rate": round(cache_hits / (cache_hits + cache_misses) * 100, 1) if (cache_hits + cache_misses) > 0 else 0,
        }

        summary_file = results_dir / "summary.json"
        with open(summary_file, "w") as f:
            json.dump(summary, f, indent=2)

        print(f"\n=== SUMMARY ({run_label}) ===")
        print(f"Requests: {len(successful)} OK, {len(failed)} failed ({summary['error_rate']}%)")
        print(f"Total time:  mean={summary['total_time_ms']['mean']}ms, median={summary['total_time_ms']['median']}ms")
        print(f"Doc RAG time: mean={summary['doc_rag_time_ms']['mean']}ms, median={summary['doc_rag_time_ms']['median']}ms")
        print(f"Cache: {cache_hits} hits, {cache_misses} misses ({summary['cache_hit_rate']}% hit rate)")
        print(f"\nResults: {results_dir}")


def main():
    parser = argparse.ArgumentParser(description="Document Cache Impact Test")
    parser.add_argument("--label", required=True, help="Run label: 'no_cache' or 'with_cache'")
    args = parser.parse_args()

    if not all([CREATOR_EMAIL, CREATOR_PASSWORD, ASSISTANT_ID]):
        print("ERROR: Missing CREATOR_EMAIL, CREATOR_PASSWORD, or ASSISTANT_ID")
        sys.exit(1)

    asyncio.run(run_simulation(args.label))


if __name__ == "__main__":
    main()
