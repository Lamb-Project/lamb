#!/usr/bin/env python3
"""Golden-transcript capture for the AAC agent (Phase 0b of the AAC refactoring).

Drives scripted scenarios through BOTH message endpoints of a live LAMB dev
stack and records everything an equivalence check needs: the raw wire frames,
the final texts, and the session envelope after every turn.

The captures are the regression oracle for the loop migration: after the loop
swap (Phase 3), replay.py re-runs the same scenarios and compares STRUCTURAL
signatures (event grammar, tool calls, pending-action lifecycle) — prose is
allowed to vary, the machinery is not.

Usage:
    python3 capture.py                 # full capture, all scenarios x both modes
    python3 capture.py --only no-tool-greeting --mode stream
    LAMB_BASE=http://localhost:9099 python3 capture.py

Requires a running LAMB dev stack and the goldens user (see README.md).
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE = "http://localhost:9099"
USER = {"email": "aac-goldens@test.local", "password": "goldens-2026-capture"}
OUT_DIR = Path(__file__).parent / "goldens"
TURN_TIMEOUT = 180  # LLM + tool rounds can be slow on a dev stack

# ---------------------------------------------------------------------------
# Scenarios. Phrasing aims to make the agent's tool choice near-deterministic;
# prose in replies will still vary run to run — replay.py compares structure,
# not wording. Multi-turn scenarios exercise the ask-flow state machine and
# session persistence across separate HTTP requests.
# ---------------------------------------------------------------------------
SCENARIOS = {
    "no-tool-greeting": {
        "notes": "No-tool-call path. THE divergence-bug witness: on legacy code the "
                 "plain endpoint returns the first LLM response, the stream endpoint "
                 "discards it and makes a second streamed call.",
        "turns": ["Hello! In one short sentence, what can you help me with?"],
    },
    "multi-tool-list": {
        "notes": "Auto-policy tool round (assistant.list).",
        "turns": ["Please list my assistants and tell me exactly how many I have."],
    },
    "ask-approve-es": {
        "notes": "Ask-flow, approve path, Spanish (classifier is multilingual).",
        "turns": [
            "Crea un asistente llamado 'Golden Test ES' con el system prompt "
            "'Eres un asistente de prueba.' Hazlo ahora, por favor.",
            "sí",
        ],
    },
    "ask-reject-ca": {
        "notes": "Ask-flow, reject path, Catalan.",
        "turns": [
            "Crea un assistent anomenat 'Golden Test CA' amb el system prompt "
            "'Ets un assistent de prova.' Fes-ho ara, si us plau.",
            "no",
        ],
    },
    "ask-ambiguous": {
        "notes": "Ask-flow, ambiguous reply: pending action must survive the turn.",
        "turns": [
            "Create an assistant called 'Golden Ambiguous' with the system prompt "
            "'You are a test.' Do it now please.",
            "By the way, can you also read documentation topics?",
        ],
    },
    "skill-load-mid": {
        "notes": "Mid-session skill.load (prompt swap through the tool-result path).",
        "turns": [
            "Please run exactly this command: lamb skill load create-assistant",
            "In one line: what is the first step the active skill tells you to take?",
        ],
    },
    "continuation-memory": {
        "notes": "Session persistence across separate HTTP requests.",
        "turns": [
            "Remember this number: 4242. Just confirm you have it.",
            "What number did I ask you to remember? Answer with the number only.",
        ],
    },
}


def login(sess: requests.Session) -> str:
    r = sess.post(f"{BASE}/creator/login", data=USER, timeout=30)
    r.raise_for_status()
    body = r.json()
    token = body.get("token") or body.get("access_token") or (
        body.get("data", {}).get("token") if isinstance(body.get("data"), dict) else None)
    if not token:
        sys.exit(f"login gave no token: {json.dumps(body)[:200]}")
    sess.headers["Authorization"] = f"Bearer {token}"
    return token


def create_session(sess: requests.Session, label: str) -> str:
    r = sess.post(f"{BASE}/creator/aac/sessions", json={}, timeout=30)
    r.raise_for_status()
    sid = r.json()["id"]
    sess.put(f"{BASE}/creator/aac/sessions/{sid}/title",
             json={"title": f"golden:{label}"}, timeout=30)
    return sid


def envelope(sess: requests.Session, sid: str) -> dict:
    r = sess.get(f"{BASE}/creator/aac/sessions/{sid}", timeout=30)
    r.raise_for_status()
    return r.json()


def send_plain(sess: requests.Session, sid: str, message: str) -> dict:
    t0 = time.time()
    r = sess.post(f"{BASE}/creator/aac/sessions/{sid}/message",
                  json={"message": message}, timeout=TURN_TIMEOUT)
    return {"http_status": r.status_code,
            "elapsed_s": round(time.time() - t0, 2),
            "body": r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text[:2000]}


def send_stream(sess: requests.Session, sid: str, message: str) -> dict:
    """Capture every SSE frame verbatim (parsed JSON where possible)."""
    t0 = time.time()
    frames = []
    with sess.post(f"{BASE}/creator/aac/sessions/{sid}/message/stream",
                   json={"message": message}, timeout=TURN_TIMEOUT, stream=True) as r:
        status = r.status_code
        for raw in r.iter_lines(decode_unicode=True):
            if not raw or not raw.startswith("data: "):
                continue
            payload = raw[len("data: "):]
            if payload == "[DONE]":
                frames.append({"_done_marker": True})
                continue
            try:
                frames.append(json.loads(payload))
            except json.JSONDecodeError:
                frames.append({"_raw": payload})
    return {"http_status": status,
            "elapsed_s": round(time.time() - t0, 2),
            "frames": frames}


def run_scenario(sess: requests.Session, name: str, spec: dict, mode: str) -> dict:
    label = f"{name}__{mode}"
    sid = create_session(sess, label)
    record = {
        "scenario": name,
        "mode": mode,
        "notes": spec["notes"],
        "session_id": sid,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "base": BASE,
        "turns": [],
    }
    for i, message in enumerate(spec["turns"]):
        print(f"  [{label}] turn {i + 1}/{len(spec['turns'])} ...", flush=True)
        turn = {"user": message}
        try:
            turn["result"] = send_plain(sess, sid, message) if mode == "plain" \
                else send_stream(sess, sid, message)
        except Exception as exc:  # capture errors as data, keep going
            turn["result"] = {"error": repr(exc)}
        try:
            turn["envelope_after"] = envelope(sess, sid)
        except Exception as exc:
            turn["envelope_after"] = {"error": repr(exc)}
        record["turns"].append(turn)
    return record


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="run a single scenario by name")
    ap.add_argument("--mode", choices=["plain", "stream"], help="run a single mode")
    args = ap.parse_args()

    todo = {args.only: SCENARIOS[args.only]} if args.only else SCENARIOS
    modes = [args.mode] if args.mode else ["plain", "stream"]

    OUT_DIR.mkdir(exist_ok=True)
    sess = requests.Session()
    login(sess)
    print(f"capturing {len(todo)} scenario(s) x {modes} against {BASE}", flush=True)

    for name, spec in todo.items():
        for mode in modes:
            record = run_scenario(sess, name, spec, mode)
            out = OUT_DIR / f"{name}__{mode}.json"
            out.write_text(json.dumps(record, indent=1, ensure_ascii=False))
            print(f"  wrote {out.name}", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
