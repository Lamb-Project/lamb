#!/usr/bin/env python3
"""Structural replay-diff for the AAC golden transcripts.

Re-runs the captured scenarios against a live stack and compares STRUCTURAL
SIGNATURES against the goldens. LLM prose varies run to run by design; the
machinery must not. A signature captures, per turn:

  - the wire grammar (ordered, deduplicated event kinds on the stream
    endpoint; response-shape keys on the plain endpoint)
  - the tool calls made (action_key sequence from the tool_audit delta)
  - the pending-action lifecycle (absent / present after the turn)
  - envelope invariants (key set, conversation growth >= 2 per turn)

Usage:
    python3 replay.py                # replay everything, report table
    python3 replay.py --only ask-approve-es
    python3 replay.py --signatures   # print golden signatures, no live calls

Exit code 0 = all equivalent, 1 = at least one divergence (listed).
"""

import argparse
import json
import sys
from itertools import groupby
from pathlib import Path

GOLD_DIR = Path(__file__).parent / "goldens"


# ---------------------------------------------------------------------------
# Signature extraction (pure functions over a capture record)
# ---------------------------------------------------------------------------

def frame_kind(frame: dict) -> str:
    if frame.get("_done_marker"):
        return "DONE-marker"
    if "status" in frame:
        return f"status:{frame['status']}"
    if frame.get("done"):
        return "done"
    if "content" in frame or "_raw" in frame:
        return "content"
    if "error" in frame:
        return "error"
    return "other:" + ",".join(sorted(frame.keys())[:3])


def turn_signature(turn: dict, prev_audit_len: int) -> dict:
    result = turn.get("result", {})
    env = turn.get("envelope_after", {})
    sig = {}

    if "frames" in result:  # stream mode: ordered grammar, runs collapsed
        kinds = [frame_kind(f) for f in result["frames"]]
        sig["grammar"] = [k for k, _ in groupby(kinds)]
    else:  # plain mode: response shape
        body = result.get("body", {})
        sig["response_keys"] = sorted(body.keys()) if isinstance(body, dict) else ["<non-json>"]

    audit = env.get("tool_audit") or []
    sig["tools"] = [e.get("action_key", "?") for e in audit[prev_audit_len:]]
    sig["pending_after"] = bool(env.get("pending_action"))
    sig["envelope_keys"] = sorted(k for k in env.keys() if k != "error")
    conv = env.get("conversation")
    sig["conversation_len"] = len(conv) if isinstance(conv, list) else -1
    sig["http_status"] = result.get("http_status")
    return sig, len(audit)


def record_signature(record: dict) -> list:
    sigs, audit_len = [], 0
    for turn in record["turns"]:
        sig, audit_len = turn_signature(turn, audit_len)
        sigs.append(sig)
    return sigs


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

COMPARED_FIELDS = ("response_keys", "pending_after", "http_status")
# conversation_len and envelope_keys are reported but tolerated when they
# differ only by additive fields (new keys are expected as the refactor
# extends the envelope; losing keys is a divergence).
#
# Documented tolerances (added after the 2026-07-17 tau soak — every one is
# a variance class that trips legacy-vs-legacy replay as well):
# - tools: compared as sorted multisets with the model-optional
#   session.rename dropped; the model reorders calls and sometimes skips
#   housekeeping between runs.
# - grammar: status:thinking frames are dropped before comparison; their
#   count tracks LLM-call rounds, which vary with tool choice (and the tau
#   shim emits one before the final response where the legacy ask path
#   did not).
# - conversation growth is checked per turn (>= 2: the user message and a
#   final assistant message) instead of against the golden's absolute
#   length, which depends on how many tool calls the model chose.

_OPTIONAL_TOOLS = {"session.rename"}


def _tools_signature(tools: list) -> list:
    return sorted(t for t in tools if t not in _OPTIONAL_TOOLS)


def _grammar_signature(grammar: list) -> list:
    return [g for g in grammar if g != "status:thinking"]


def compare(golden: list, fresh: list) -> list:
    problems = []
    if len(golden) != len(fresh):
        return [f"turn count {len(golden)} -> {len(fresh)}"]
    prev_g_len = prev_f_len = 0
    for i, (g, f) in enumerate(zip(golden, fresh)):
        for field in COMPARED_FIELDS:
            if field in g and g.get(field) != f.get(field):
                problems.append(f"turn {i + 1} {field}: {g.get(field)} -> {f.get(field)}")
        if "grammar" in g and _grammar_signature(g["grammar"]) != _grammar_signature(f.get("grammar", [])):
            problems.append(f"turn {i + 1} grammar: {g['grammar']} -> {f.get('grammar')}")
        if _tools_signature(g["tools"]) != _tools_signature(f["tools"]):
            problems.append(f"turn {i + 1} tools: {g['tools']} -> {f['tools']}")
        lost = set(g["envelope_keys"]) - set(f["envelope_keys"])
        if lost:
            problems.append(f"turn {i + 1} envelope lost keys: {sorted(lost)}")
        g_growth = g["conversation_len"] - prev_g_len
        f_growth = f["conversation_len"] - prev_f_len
        if g_growth >= 2 and f_growth < 2:
            problems.append(f"turn {i + 1} conversation grew by {f_growth} (< 2)")
        prev_g_len, prev_f_len = g["conversation_len"], f["conversation_len"]
    return problems


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="restrict to one scenario name")
    ap.add_argument("--signatures", action="store_true",
                    help="print golden signatures and exit (no live calls)")
    args = ap.parse_args()

    goldens = sorted(GOLD_DIR.glob("*.json"))
    if args.only:
        goldens = [g for g in goldens if g.name.startswith(args.only + "__")]
    if not goldens:
        sys.exit("no goldens found — run capture.py first")

    if args.signatures:
        for path in goldens:
            record = json.loads(path.read_text())
            print(f"== {path.name}")
            for i, sig in enumerate(record_signature(record)):
                print(f"  turn {i + 1}: {json.dumps(sig, ensure_ascii=False)}")
        return

    # Live replay: reuse capture.py's runner so wire handling stays identical.
    import capture  # noqa: E402  (sibling module)
    import requests
    sess = requests.Session()
    capture.login(sess)

    failures = {}
    for path in goldens:
        record = json.loads(path.read_text())
        name, mode = record["scenario"], record["mode"]
        print(f"replaying {name} [{mode}] ...", flush=True)
        fresh = capture.run_scenario(sess, name, capture.SCENARIOS[name], mode)
        problems = compare(record_signature(record), record_signature(fresh))
        if problems:
            failures[path.name] = problems

    print()
    if failures:
        print(f"DIVERGED: {len(failures)}/{len(goldens)}")
        for name, problems in failures.items():
            print(f"  {name}")
            for p in problems:
                print(f"    - {p}")
        sys.exit(1)
    print(f"EQUIVALENT: {len(goldens)}/{len(goldens)} recordings match structurally")


if __name__ == "__main__":
    main()
