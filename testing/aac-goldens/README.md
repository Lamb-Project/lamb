# AAC golden transcripts — regression oracle for the loop migration

Phase 0b of the AAC refactoring (tau loop migration). These recordings pin the
**current** behavior of the AAC agent — both message endpoints, the ask-flow
state machine, mid-session skill loading, and session persistence — so every
later phase can prove it changed the machinery without changing the contract.

## Contents

| File | What |
|---|---|
| `capture.py` | Drives the scripted scenarios against a live stack and records raw wire frames, final texts, and the session envelope after every turn. |
| `replay.py` | Re-runs the scenarios live and diffs **structural signatures** against the goldens (event grammar, tool calls, pending-action lifecycle, envelope invariants). Prose may vary; structure may not. `--signatures` prints the golden signatures offline. |
| `goldens/*.json` | One recording per scenario x endpoint. Committed on purpose: they are the oracle. |

## Scenarios

| Name | Exercises |
|---|---|
| `no-tool-greeting` | The no-tool-call path. **Divergence-bug witness:** on the legacy loop the plain endpoint returns the first LLM response while the stream endpoint discards it and pays for a second streamed call (`loop.py:465` vs `:566-576`). |
| `multi-tool-list` | An auto-policy tool round (`assistant.list`). |
| `ask-approve-es` | Ask-flow approve, Spanish — the write action executes only after confirmation. |
| `ask-reject-ca` | Ask-flow reject, Catalan — the pending action is discarded. |
| `ask-ambiguous` | Ask-flow with an unrelated reply — the pending action must survive the turn. |
| `skill-load-mid` | Mid-session `skill.load` (prompt swap through the tool-result path). |
| `continuation-memory` | Session persistence across separate HTTP requests. |

## Running

Needs the dev stack up (`docker compose start` in the repo root) and the
goldens user present (`aac-goldens@test.local` — create once via
`POST /creator/signup`; credentials at the top of `capture.py`).

```bash
python3 capture.py                     # re-record everything (spends LLM tokens)
python3 replay.py                      # replay + structural diff, exit 1 on divergence
python3 replay.py --signatures         # inspect golden signatures, no live calls
```

Capture and replay both make **real LLM calls** through the org's configured
provider and create sessions (titled `golden:<scenario>__<mode>`) plus, in the
approve scenario, a real assistant named "Golden Test ES" under the goldens
user. That is deliberate: fixtures live in the dev database, not in mocks.

## What "equivalent" means (and what it does not)

`replay.py` compares per-turn: the SSE event grammar (order of frame kinds,
runs collapsed) or the plain-response key set, the sequence of tool
`action_key`s executed, whether a pending action exists after the turn, the
HTTP status, and envelope invariants (no lost keys, conversation never
shrinks). It does NOT compare prose, timings, token counts, or model choice.
New envelope keys and new frame kinds ADDED by the refactor are tolerated by
design; anything lost or reordered fails.

Expected evolution: when Phase 4 replaces the legacy status-dict frames with
the versioned event protocol, the stream grammar WILL change — at that point
the goldens are re-recorded behind the new protocol flag and the old
recordings stay in git history as the legacy-contract record.
