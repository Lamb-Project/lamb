"""Test scenarios and evaluation API router.

Mounted at /creator/assistant/{assistant_id}/tests/
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from lamb.auth_context import AuthContext, get_auth_context
from lamb.services.test_service import TestService
from lamb.logging_config import get_logger

logger = get_logger(__name__, component="TEST")

router = APIRouter(tags=["Tests"])


# ------------------------------------------------------------------
# Scenarios
# ------------------------------------------------------------------

@router.post("/assistant/{assistant_id}/tests/scenarios")
async def create_scenario(
    assistant_id: int,
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
):
    """Create a test scenario for an assistant."""
    auth.require_assistant_access(assistant_id, level="owner")
    body = await request.json()

    title = body.get("title", "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="Title is required")

    messages = body.get("messages", [])
    if not messages:
        # Shorthand: single message string
        message = body.get("message", "").strip()
        if message:
            messages = [{"role": "user", "content": message}]
        else:
            raise HTTPException(status_code=400, detail="Messages or message is required")

    svc = TestService()
    result = svc.create_scenario(
        assistant_id=assistant_id,
        title=title,
        messages=messages,
        created_by=auth.user["email"],
        description=body.get("description", ""),
        scenario_type=body.get("scenario_type", "single_turn"),
        expected_behavior=body.get("expected_behavior", ""),
        tags=body.get("tags"),
    )
    return result


@router.get("/assistant/{assistant_id}/tests/scenarios")
async def list_scenarios(
    assistant_id: int,
    auth: AuthContext = Depends(get_auth_context),
):
    """List test scenarios for an assistant."""
    auth.require_assistant_access(assistant_id)
    svc = TestService()
    return svc.list_scenarios(assistant_id)


@router.get("/assistant/{assistant_id}/tests/scenarios/{scenario_id}")
async def get_scenario(
    assistant_id: int,
    scenario_id: str,
    auth: AuthContext = Depends(get_auth_context),
):
    """Get a test scenario."""
    auth.require_assistant_access(assistant_id)
    svc = TestService()
    scenario = svc.get_scenario(scenario_id)
    if not scenario or scenario["assistant_id"] != assistant_id:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return scenario


@router.put("/assistant/{assistant_id}/tests/scenarios/{scenario_id}")
async def update_scenario(
    assistant_id: int,
    scenario_id: str,
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
):
    """Update a test scenario."""
    auth.require_assistant_access(assistant_id, level="owner")
    body = await request.json()
    svc = TestService()
    if not svc.update_scenario(scenario_id, body):
        raise HTTPException(status_code=404, detail="Scenario not found")
    return {"success": True}


@router.delete("/assistant/{assistant_id}/tests/scenarios/{scenario_id}")
async def delete_scenario(
    assistant_id: int,
    scenario_id: str,
    auth: AuthContext = Depends(get_auth_context),
):
    """Delete a test scenario."""
    auth.require_assistant_access(assistant_id, level="owner")
    svc = TestService()
    if not svc.delete_scenario(scenario_id):
        raise HTTPException(status_code=404, detail="Scenario not found")
    return {"success": True}


# ------------------------------------------------------------------
# Test runs
# ------------------------------------------------------------------

@router.post("/assistant/{assistant_id}/tests/run")
async def run_tests(
    assistant_id: int,
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
):
    """Run test scenarios for an assistant.

    Body (optional):
        {"scenario_id": "uuid"}  — run a specific scenario
        {}                       — run all scenarios
    """
    auth.require_assistant_access(assistant_id, level="owner")
    body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}

    svc = TestService()
    scenario_id = body.get("scenario_id")

    if scenario_id:
        scenario = svc.get_scenario(scenario_id)
        if not scenario or scenario["assistant_id"] != assistant_id:
            raise HTTPException(status_code=404, detail="Scenario not found")
        result = await svc.run_scenario(
            assistant_id=assistant_id,
            scenario_id=scenario_id,
            messages=scenario["messages"],
            user_email=auth.user["email"],
        )
        return result
    else:
        results = await svc.run_all_scenarios(assistant_id, auth.user["email"])
        return {"runs": results, "count": len(results)}


@router.get("/assistant/{assistant_id}/tests/runs")
async def list_runs(
    assistant_id: int,
    limit: int = 50,
    auth: AuthContext = Depends(get_auth_context),
):
    """List test runs for an assistant."""
    auth.require_assistant_access(assistant_id)
    svc = TestService()
    return svc.list_runs(assistant_id, limit=limit)


@router.get("/assistant/{assistant_id}/tests/runs/{run_id}")
async def get_run(
    assistant_id: int,
    run_id: str,
    auth: AuthContext = Depends(get_auth_context),
):
    """Get full test run details (input + output + snapshot)."""
    auth.require_assistant_access(assistant_id)
    svc = TestService()
    run = svc.get_run(run_id)
    if not run or run["assistant_id"] != assistant_id:
        raise HTTPException(status_code=404, detail="Test run not found")
    return run


# ------------------------------------------------------------------
# Evaluations
# ------------------------------------------------------------------

@router.post("/assistant/{assistant_id}/tests/runs/{run_id}/evaluate")
async def evaluate_run(
    assistant_id: int,
    run_id: str,
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
):
    """Submit an evaluation for a test run.

    Body: {"verdict": "good|bad|mixed", "notes": "optional text"}
    """
    auth.require_assistant_access(assistant_id, level="owner")
    body = await request.json()

    verdict = body.get("verdict", "").strip().lower()
    if verdict not in ("good", "bad", "mixed"):
        raise HTTPException(status_code=400, detail="Verdict must be 'good', 'bad', or 'mixed'")

    svc = TestService()
    run = svc.get_run(run_id)
    if not run or run["assistant_id"] != assistant_id:
        raise HTTPException(status_code=404, detail="Test run not found")

    result = svc.create_evaluation(
        test_run_id=run_id,
        evaluator="user",
        verdict=verdict,
        notes=body.get("notes", ""),
        dimensions=body.get("dimensions"),
    )
    return result


@router.get("/assistant/{assistant_id}/tests/evaluations")
async def list_evaluations(
    assistant_id: int,
    auth: AuthContext = Depends(get_auth_context),
):
    """List all evaluations for an assistant's test runs."""
    auth.require_assistant_access(assistant_id)
    svc = TestService()
    return svc.list_evaluations(assistant_id)
