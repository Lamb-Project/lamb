"""AI Workshop — one-shot Lean MVP smoke test (manual).

Drives the *entire* MVP loop against the running stack in one go:

    seed → step1 instructions → step2 upload document → step3 KB retrieval
         → step4 tools → step5 chat + observability → reflection/submit
         → formative evaluation → teacher dashboard

Run inside the backend container (the container has httpx, the DB and the
KB server on the compose network):

    docker compose exec backend python tests/mvp_smoke.py
    docker compose exec backend python tests/mvp_smoke.py --require-llm
    docker compose exec backend python tests/mvp_smoke.py --cleanup
    docker compose exec backend python tests/mvp_smoke.py --base http://localhost:9099

Notes
-----
* It seeds its own workshop activity + student + session and mints a
  ``workshop_student`` token, so no Moodle / OWI / browser is needed.
* The document upload and KB query hit the *real* KB server.
* The chat and formative-feedback steps need an LLM configured for the org
  (small-fast model for feedback; a chat model for the assistant). When no
  model is reachable those two steps report WARN instead of FAIL unless you
  pass ``--require-llm``.
* Safe to re-run: every run creates a new activity; the rubric is reused by
  title. Pass ``--cleanup`` to delete the activity afterwards.
"""

import argparse
import json
import os
import sys
import time
from datetime import timedelta

# Running this file directly puts the tests/ folder on sys.path, not the
# backend root. Add the backend root so `import lamb` resolves.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx  # noqa: E402

from lamb import auth as lamb_auth  # noqa: E402
from lamb.database_manager import LambDatabaseManager  # noqa: E402
from lamb.evaluaitor.rubric_database import RubricDatabaseManager  # noqa: E402

RUBRIC_TITLE = "AI Workshop MVP smoke rubric"
DOC_NAME = "fractions-notes.md"
DOC_CONTENT = (
    b"# Fractions - study notes\n\n"
    b"## What a fraction is\n"
    b"A fraction shows equal parts of a whole. In 3/4 the bottom number (4) is\n"
    b"the denominator and the top number (3) is the numerator.\n\n"
    b"## Simplifying\n"
    b"Divide the numerator and denominator by their greatest common divisor\n"
    b"(GCD). Example: 6/8, GCD is 2, so 6/8 = 3/4.\n\n"
    b"## Adding fractions\n"
    b"With different denominators, find a common denominator first:\n"
    b"1/2 + 1/3 -> 3/6 + 2/6 = 5/6.\n"
)

REFLECTION = (
    "I learned that my assistant only knows what I give it. Grounding answers "
    "in the attached notes made them specific, and the calculator only ran when "
    "the question contained an arithmetic expression."
)


# ──────────────────────────────────────────────────────────────────────────
# Reporting
# ──────────────────────────────────────────────────────────────────────────
class Report:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warned = 0

    def check(self, label, cond, detail="", warn=False):
        if cond:
            status = "PASS"
            self.passed += 1
        elif warn:
            status = "WARN"
            self.warned += 1
        else:
            status = "FAIL"
            self.failed += 1
        suffix = f" :: {detail}" if detail else ""
        print(f"  [{status}] {label}{suffix}")
        return bool(cond)

    def section(self, title):
        print(f"\n=== {title} ===")


# ──────────────────────────────────────────────────────────────────────────
# Seed
# ──────────────────────────────────────────────────────────────────────────
def _first_org_id(db):
    conn = db.get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id FROM {db.table_prefix}organizations ORDER BY id LIMIT 1")
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def _resolve_owner(db):
    """Return (owner_email, organization_id) for a real creator user."""
    conn = db.get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"""
            SELECT u.user_email, u.organization_id
            FROM {db.table_prefix}Creator_users u
            LEFT JOIN {db.table_prefix}organizations o
                   ON u.organization_id = o.id
            WHERE u.user_email IS NOT NULL
              AND u.organization_id IS NOT NULL
            ORDER BY COALESCE(o.is_system, 0) DESC,
                     CASE WHEN u.user_type = 'creator' THEN 0 ELSE 1 END,
                     u.id
            LIMIT 1
        """)
        row = cur.fetchone()
        if row:
            return row[0], row[1]
    finally:
        conn.close()
    return None, _first_org_id(db)


def _build_rubric_data():
    def levels(prefix):
        return [
            {"id": f"{prefix}-l1", "score": 1, "label": "Beginning",
             "description": "Minimal or missing evidence."},
            {"id": f"{prefix}-l2", "score": 2, "label": "Developing",
             "description": "Partial but inconsistent evidence."},
            {"id": f"{prefix}-l3", "score": 3, "label": "Proficient",
             "description": "Clear and mostly complete evidence."},
            {"id": f"{prefix}-l4", "score": 4, "label": "Exemplary",
             "description": "Precise, thoughtful and complete."},
        ]

    return {
        "rubricId": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "title": RUBRIC_TITLE,
        "description": "Formative rubric for a student-built maths assistant.",
        "metadata": {
            "subject": "Mathematics", "gradeLevel": "6-8",
            "createdAt": "2026-01-01T00:00:00",
            "modifiedAt": "2026-01-01T00:00:00",
        },
        "criteria": [
            {"id": "c-instructions", "name": "Instruction clarity",
             "description": "The system prompt states role, tone and method.",
             "weight": 30, "levels": levels("c1")},
            {"id": "c-grounding", "name": "Use of the document / knowledge base",
             "description": "Answers are grounded in the attached document.",
             "weight": 40, "levels": levels("c2")},
            {"id": "c-tools", "name": "Tool awareness",
             "description": "The student understands when tools are triggered.",
             "weight": 30, "levels": levels("c3")},
        ],
        "scoringType": "points",
        "maxScore": 12,
    }


def _get_or_create_rubric(db, rubric_db, org_id, owner_email):
    conn = db.get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            f"SELECT rubric_id FROM {db.table_prefix}rubrics "
            f"WHERE title = ? AND owner_email = ? LIMIT 1",
            (RUBRIC_TITLE, owner_email))
        row = cur.fetchone()
    finally:
        conn.close()
    if row:
        return row[0]
    created = rubric_db.create_rubric(
        rubric_data=_build_rubric_data(),
        owner_email=owner_email,
        organization_id=org_id,
        is_public=True,
    )
    return created["rubric_id"]


def seed(db, rubric_db, report):
    """Create activity + student + session + tokens. Returns a context dict."""
    report.section("seed")
    owner_email, org_id = _resolve_owner(db)
    if not owner_email:
        report.check("creator user exists for KB ownership", False,
                     "no Creator_users row found; KB wiring will degrade")
        owner_email = "mvp-smoke-teacher@lamb-lti.local"
    else:
        report.check("creator user resolved", True, f"{owner_email} (org {org_id})")

    rubric_id = _get_or_create_rubric(db, rubric_db, org_id, owner_email)

    resource_link = f"mvp-smoke-{int(time.time())}"
    activity_id = db.create_lti_activity(
        resource_link_id=resource_link,
        organization_id=org_id,
        owi_group_id="",
        owi_group_name="",
        configured_by_email=owner_email,
        configured_by_name="MVP Smoke Teacher",
        context_title="MVP Smoke Test",
        activity_name="MVP Smoke Workshop",
        activity_type="workshop",
        rubric_id=rubric_id,
    )
    report.check("workshop activity created", bool(activity_id),
                 f"id={activity_id} type=workshop rubric={rubric_id}")

    email = "mvp-smoke-student@lamb-lti.local"
    activity_user_id = db.create_lti_activity_user(
        activity_id=activity_id,
        user_email=email,
        user_name="mvp",
        user_display_name="MVP Smoke Student",
        lms_user_id="LMS-MVP-SMOKE",
        owi_user_id="owi-mvp-smoke",
    )
    session = db.get_or_create_workshop_session(
        activity_id=activity_id,
        activity_user_id=activity_user_id,
        owi_user_id="owi-mvp-smoke",
    )
    session_id = session["id"]

    principal = {
        "type": "workshop_student",
        "scope": "workshop_student",
        "activity_id": activity_id,
        "activity_user_id": activity_user_id,
        "owi_user_id": "owi-mvp-smoke",
        "email": email,
        "organization_id": org_id,
        "session_id": session_id,
    }
    student_token = lamb_auth.create_token(
        principal, expires_delta=timedelta(seconds=7200))

    dashboard_token = lamb_auth.create_token(
        {
            "type": "dashboard",
            "scope": "lti_unified",
            "resource_link_id": resource_link,
            "lms_user_id": "LMS-MVP-TEACHER",
            "lms_email": owner_email,
            "username": "teacher",
            "display_name": "MVP Smoke Teacher",
            "is_owner": True,
        },
        expires_delta=timedelta(seconds=7200),
    )

    return {
        "org_id": org_id,
        "owner_email": owner_email,
        "rubric_id": rubric_id,
        "activity_id": activity_id,
        "resource_link": resource_link,
        "email": email,
        "activity_user_id": activity_user_id,
        "session_id": session_id,
        "student_token": student_token,
        "dashboard_token": dashboard_token,
    }


# ──────────────────────────────────────────────────────────────────────────
# Student flow
# ──────────────────────────────────────────────────────────────────────────
def _hdr(token):
    return {"token": token}


def _fail_detail(resp):
    return f"HTTP {resp.status_code}: {resp.text[:200]}"


def run_student_flow(client, api, ctx, report, require_llm):
    sid = ctx["session_id"]
    token = ctx["student_token"]

    # 1. Restore session (reload path)
    report.section("1. session restore")
    r = client.get(f"{api}/workshop/sessions/{sid}", headers=_hdr(token))
    report.check("GET /sessions/{id}", r.status_code == 200, _fail_detail(r) if r.status_code != 200 else "")
    assistant_id = None
    if r.status_code == 200:
        body = r.json()
        report.check("restore returns session_id", body.get("session_id") == sid)

    # Auth boundary: a junk token must be rejected
    bad = client.get(f"{api}/workshop/sessions/{sid}", headers=_hdr("garbage"))
    report.check("junk token rejected (401)", bad.status_code == 401,
                 f"HTTP {bad.status_code}")

    # 2. Step 1 — create assistant with instructions
    report.section("2. step 1: create assistant (instructions)")
    r = client.post(
        f"{api}/workshop/sessions/{sid}/assistant",
        headers=_hdr(token),
        json={
            "name": "MVP Smoke Assistant",
            "system_prompt": "You are a friendly maths tutor. Explain fractions "
                             "step by step and ground every answer in the "
                             "attached notes. Use the calculator for arithmetic.",
            "prompt_template": "{user_input}\n\nContext:\n{context}",
            "api_callback": json.dumps({
                "prompt_processor": "simple_augment",
                "connector": os.getenv("SMOKE_CONNECTOR", "ollama"),
                "llm": os.getenv("SMOKE_LLM", "qwen3.5:9b"),
            }),
            "rag_top_k": 3,
            "rag_collections": "",
        },
    )
    report.check("POST /assistant", r.status_code == 200, _fail_detail(r) if r.status_code != 200 else "")
    if r.status_code == 200:
        assistant_id = r.json().get("assistant_id")
    report.check("assistant_id returned", bool(assistant_id))

    # 3. Step 2 — upload document (real KB ingest)
    report.section("3. step 2: upload document (real KB)")
    kb_id = None
    job_id = None
    if assistant_id:
        r = client.post(
            f"{api}/workshop/sessions/{sid}/assistant/{assistant_id}/doc",
            headers=_hdr(token),
            files={"file": (DOC_NAME, DOC_CONTENT, "text/markdown")},
        )
        report.check("POST /doc (multipart)", r.status_code == 200,
                     _fail_detail(r) if r.status_code != 200 else "")
        if r.status_code == 200:
            body = r.json()
            kb_id = body.get("kb_id")
            job_id = body.get("file_registry_id")
            report.check("session KB created", bool(kb_id), f"kb_id={kb_id}")
            report.check("ingestion job queued", bool(job_id), f"job_id={job_id}")

        # 4. Poll ingestion
        report.section("4. document ingestion status")
        status = None
        if job_id and kb_id:
            deadline = time.time() + 90
            while time.time() < deadline:
                r = client.get(
                    f"{api}/workshop/sessions/{sid}/doc/status",
                    headers=_hdr(token),
                    params={"job_id": job_id},
                )
                if r.status_code != 200:
                    status = "error"
                    break
                status = (r.json() or {}).get("status")
                if status in ("completed", "failed"):
                    break
                time.sleep(3)
            report.check("ingestion completed", status == "completed",
                         f"final status={status}",
                         warn=(status in (None, "processing", "error")))

    # 5. Step 3 — connect KB + probe retrieval
    report.section("5. step 3: KB probe retrieval")
    if assistant_id:
        r = client.post(
            f"{api}/workshop/sessions/{sid}/assistant/{assistant_id}/kb",
            headers=_hdr(token),
            json={"query": "How do I simplify 6/8?", "top_k": 3},
        )
        report.check("POST /kb probe", r.status_code == 200,
                     _fail_detail(r) if r.status_code != 200 else "")
        if r.status_code == 200:
            body = r.json()
            results = body.get("results") or []
            report.check("probe returned hits", len(results) > 0,
                         f"count={body.get('count')}",
                         warn=True)
            if results:
                first = results[0]
                has_sim = first.get("similarity") is not None
                has_text = bool(first.get("data") or first.get("text"))
                report.check("hits carry similarity + text", has_sim and has_text,
                             f"similarity={first.get('similarity')}")

    # 6. Step 5 — chat with tools + observability
    report.section("6. step 5: chat + observability + tool")
    obs = None
    tool_events = []
    chat_ok = False
    chat_err = ""
    if assistant_id:
        try:
            obs, tool_events, reply, done = _stream_chat(
                client, api, sid, assistant_id, token,
                tools=[{"type": "function", "function": {"name": "calculator"}}],
                message="What is (3+5)*2? Use the calculator.",
            )
            chat_ok = obs is not None
            report.check("observability frame received", obs is not None,
                         "no frame" if obs is None else "")
            if obs:
                data = obs.get("data", {})
                report.check("obs: system_instructions present",
                             bool(data.get("system_instructions")))
                report.check("obs: user_input present", bool(data.get("user_input")))
                report.check("obs: final_llm_messages present",
                             isinstance(data.get("final_llm_messages"), list)
                             and len(data.get("final_llm_messages")) > 0)
                sources = data.get("retrieved_sources") or []
                report.check("obs: retrieved_sources non-empty", len(sources) > 0,
                             f"count={len(sources)} (needs RAG + model)",
                             warn=True)
        except Exception as e:  # noqa: BLE001
            chat_err = str(e)
        if not chat_ok:
            report.check("chat produced observability", False,
                         chat_err or "no observability frame",
                         warn=not require_llm)
        report.check("tool_event emitted (calculator fired)", len(tool_events) > 0,
                     f"events={len(tool_events)} (model-dependent)", warn=True)

    # 7. Reflection + submit
    report.section("7. reflection + submit")
    saved_chat = json.dumps([
        {"role": "user", "content": "What is (3+5)*2?"},
        {"role": "assistant", "content": "16, after doing the bracket first."},
    ])
    # Mirror what the frontend sends: the full per-step build state, which the
    # formative transcript and teacher dashboard read back.
    build_state = json.dumps({
        "currentStep": 5,
        "instructions": "You are a friendly maths tutor. Explain fractions "
                        "step by step and use the calculator for arithmetic.",
        "attachedFileMeta": {"name": DOC_NAME, "path": job_id or "file"},
        "attachedFilePath": job_id or "file",
        "documentStatus": "completed",
        "selectedKbId": kb_id or "",
        "kbCollection": kb_id or "",
        "selectedTools": ["calculator"],
        "reflection": REFLECTION,
    })
    r = client.post(
        f"{api}/workshop/sessions/{sid}/submit",
        headers=_hdr(token),
        json={
            "saved_chat": saved_chat,
            "reflection": REFLECTION,
            "build_state": build_state,
        },
    )
    report.check("POST /submit", r.status_code == 200, _fail_detail(r) if r.status_code != 200 else "")
    r = client.get(f"{api}/workshop/sessions/{sid}", headers=_hdr(token))
    if r.status_code == 200:
        body = r.json()
        report.check("reflection persisted", body.get("reflection") == REFLECTION)
        report.check("status = submitted", body.get("status") == "submitted",
                     f"status={body.get('status')}")

    # 8. Formative evaluation
    report.section("8. formative evaluation (rubric -> LLM)")
    r = client.post(
        f"{api}/workshop/sessions/{sid}/evaluate",
        headers=_hdr(token),
        json={},
    )
    report.check("POST /evaluate", r.status_code == 200,
                 _fail_detail(r) if r.status_code != 200 else "")
    if r.status_code == 200:
        body = r.json()
        report.check("configured = true", body.get("configured") is True)
        status = body.get("status")
        report.check("evaluation completed", status == "completed",
                     f"status={status} error={body.get('error_message')} "
                     f"(LLM-dependent)", warn=not require_llm)
        if status == "completed":
            report.check("criteria returned", len(body.get("criteria") or []) > 0)

    # 9. Evaluation restore
    report.section("9. evaluation restore (reload path)")
    r = client.get(f"{api}/workshop/sessions/{sid}/evaluation", headers=_hdr(token))
    report.check("GET /evaluation", r.status_code == 200,
                 _fail_detail(r) if r.status_code != 200 else "")
    if r.status_code == 200:
        body = r.json()
        report.check("evaluation readable after reload",
                     body.get("configured") is True and body.get("evaluation") is not None,
                     f"configured={body.get('configured')}", warn=True)

    return assistant_id


def _stream_chat(client, api, sid, assistant_id, token, tools, message):
    """POST the workshop chat SSE endpoint and collect frames."""
    body = {
        "messages": [{"role": "user", "content": message}],
        "stream": True,
        "observability": True,
        "tools": tools,
        "tool_choice": "auto",
    }
    obs = None
    tool_events = []
    reply = ""
    done = False
    with client.stream(
        "POST",
        f"{api}/workshop/sessions/{sid}/assistant/{assistant_id}/chat",
        headers=_hdr(token),
        json=body,
        timeout=180.0,
    ) as resp:
        if resp.status_code != 200:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.read()[:200]}")
        for line in resp.iter_lines():
            if not line or not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                done = True
                continue
            try:
                evt = json.loads(payload)
            except (json.JSONDecodeError, TypeError):
                continue
            etype = evt.get("type")
            if etype == "observability":
                obs = evt
            elif etype == "tool_event":
                tool_events.append(evt.get("data"))
            elif "choices" in evt:
                delta = (evt.get("choices") or [{}])[0].get("delta") or {}
                reply += delta.get("content") or ""
    return obs, tool_events, reply, done


# ──────────────────────────────────────────────────────────────────────────
# Teacher flow
# ──────────────────────────────────────────────────────────────────────────
def run_teacher_flow(client, api, ctx, report):
    report.section("10. teacher dashboard")
    token = ctx["dashboard_token"]
    rl = ctx["resource_link"]
    sid = ctx["session_id"]
    q = {"resource_link_id": rl, "token": token}

    r = client.get(f"{api}/lti/workshop/dashboard/stats", params=q)
    report.check("GET /workshop/dashboard/stats", r.status_code == 200,
                 _fail_detail(r) if r.status_code != 200 else "")
    if r.status_code == 200:
        body = r.json()
        report.check("stats: total_students >= 1",
                     (body.get("total_students") or 0) >= 1,
                     f"total={body.get('total_students')}")
        report.check("stats: submitted >= 1",
                     (body.get("submitted") or 0) >= 1,
                     f"submitted={body.get('submitted')}")

    r = client.get(f"{api}/lti/workshop/dashboard/students", params=q)
    report.check("GET /workshop/dashboard/students", r.status_code == 200,
                 _fail_detail(r) if r.status_code != 200 else "")
    if r.status_code == 200:
        students = (r.json() or {}).get("students") or []
        mine = [s for s in students if s.get("session_id") == sid]
        report.check("student appears with session", bool(mine))
        if mine:
            report.check("student status = submitted",
                         mine[0].get("session_status") == "submitted",
                         f"status={mine[0].get('session_status')}")

    r = client.get(f"{api}/lti/workshop/dashboard/sessions/{sid}", params=q)
    report.check("GET /workshop/dashboard/sessions/{id}", r.status_code == 200,
                 _fail_detail(r) if r.status_code != 200 else "")
    if r.status_code == 200:
        body = r.json()
        report.check("session detail has build_state", bool(body.get("build_state")),
                     "submit persisted the wizard decisions")
        report.check("session detail has transcript", bool(body.get("transcript")))
        report.check("transcript includes build decisions",
                     "=== BUILD DECISIONS ===" in (body.get("transcript") or ""))

    # Token boundary
    bad = client.get(f"{api}/lti/workshop/dashboard/stats",
                     params={"resource_link_id": rl, "token": "garbage"})
    report.check("dashboard junk token rejected (403)", bad.status_code == 403,
                 f"HTTP {bad.status_code}")


# ──────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────
def _cleanup(db, ctx):
    conn = db.get_connection()
    try:
        with conn:
            conn.execute(
                f"DELETE FROM {db.table_prefix}lti_activities "
                f"WHERE resource_link_id = ?", (ctx["resource_link"],))
        print(f"\n  [cleanup] deleted activity {ctx['activity_id']} "
              f"(cascade: sessions/users/evaluations)")
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="AI Workshop MVP smoke test")
    parser.add_argument("--base", default=os.getenv("LAMB_SMOKE_BASE",
                        "http://localhost:9099"),
                        help="Backend base URL (default http://localhost:9099)")
    parser.add_argument("--require-llm", action="store_true",
                        help="Treat LLM-dependent steps (chat, feedback) as FAIL "
                             "when no model is reachable")
    parser.add_argument("--cleanup", action="store_true",
                        help="Delete the seeded activity when done")
    args = parser.parse_args()

    api = args.base.rstrip("/") + "/lamb/v1"
    report = Report()

    print("=" * 64)
    print(" AI WORKSHOP — LEAN MVP SMOKE TEST")
    print(f" backend: {args.base}   require-llm: {args.require_llm}")
    print("=" * 64)

    db = LambDatabaseManager()
    rubric_db = RubricDatabaseManager()

    ctx = seed(db, rubric_db, report)

    with httpx.Client(timeout=120.0) as client:
        run_student_flow(client, api, ctx, report, args.require_llm)
        run_teacher_flow(client, api, ctx, report)

    total = report.passed + report.failed + report.warned
    print("\n" + "=" * 64)
    print(f" RESULT: {report.passed} passed, {report.failed} failed, "
          f"{report.warned} warnings  ({total} checks)")
    print("=" * 64)
    print(f" Student wizard : {args.base}/m/workshop/{ctx['activity_id']}"
          f"?token={ctx['student_token']}")
    print(f" Teacher board  : {args.base}/lamb/v1/lti/workshop/dashboard"
          f"?resource_link_id={ctx['resource_link']}"
          f"&token={ctx['dashboard_token']}")

    if args.cleanup:
        _cleanup(db, ctx)

    return 1 if report.failed else 0


if __name__ == "__main__":
    sys.exit(main())
