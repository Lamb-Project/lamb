#!/usr/bin/env python3
"""Assert that a seeded world still works.

This is the point of the baseline. Run it before an upgrade to establish that
the content is healthy, and again afterwards to find out whether the upgrade
broke anything that used to work. The failures that matter are not "a column is
missing" — the migration harness catches those — but "the teacher's assistant
from last term no longer answers", "the student can no longer reach it", "the
knowledge base retrieves nothing".

Assertions are structural, never textual: that retrieval returns the expected
document, not that a model produced particular words. Generated text is not
stable and asserting on it produces a suite that cries wolf.

Usage:
    python3 testing/baseline/verify/test_baseline.py --tag b2
    (exit code 0 = the world is intact)
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys

LAMB_DB = "/opt/lamb/lamb_v4.db"
OWI_DB = "/opt/lamb/open-webui/backend/data/webui.db"
PASSWORD = "Baseline!2026"

def _db_in_container(db_path: str, sql: str):
    """Run a query INSIDE the backend container.

    The databases live on the macOS host and reach the containers through a
    Docker bind mount. SQLite coordinates concurrent access with POSIX advisory
    locks, and those locks are not reliably shared across that boundary — a host
    process and a containerised process holding the same file open are two
    writers who cannot see each other's locks, which is how pages get corrupted.
    So every direct query goes through the container: one side of the boundary,
    one view of the locks.
    """
    import json as _json
    import subprocess as _sp
    code = (
        "import sqlite3,json;"
        f"con=sqlite3.connect({db_path!r});"
        f"print(json.dumps([list(r) for r in con.execute({sql!r})]))"
    )
    p = _sp.run(["docker", "exec", "lamb-backend", "python", "-c", code],
                capture_output=True, text=True)
    if p.returncode != 0:
        return [["ERROR", (p.stderr or "").strip()[:120]]]
    try:
        return _json.loads(p.stdout.strip().splitlines()[-1])
    except Exception as e:
        return [["ERROR", f"unparseable: {e}"]]


results: list[tuple[bool, str, str]] = []


def check(name: str, condition: bool, detail: str = "") -> bool:
    results.append((condition, name, detail))
    print(f"  {'PASS' if condition else 'FAIL'}  {name}" + (f" — {detail}" if detail else ""))
    return condition


def cli(*args, server="http://localhost:9099", json_out=True):
    cmd = ["lamb", *args] + (["-o", "json"] if json_out else [])
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        return None
    if not json_out:
        return p.stdout.strip()
    try:
        return json.loads(p.stdout)
    except json.JSONDecodeError:
        return None


def login(email: str, password: str = PASSWORD, server="http://localhost:9099") -> bool:
    p = subprocess.run(["lamb", "login", "-s", server, "-e", email, "-p", password],
                       capture_output=True, text=True)
    return p.returncode == 0


def db(path: str, sql: str, *params):
    """Query a database through the container — never from the host. See
    _db_in_container for why that distinction is not cosmetic."""
    for i, val in enumerate(params):
        sql = sql.replace("?", repr(val), 1)
    return _db_in_container(path, sql)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="b2", help="the seed tag to verify")
    ap.add_argument("--server", default="http://localhost:9099")
    a = ap.parse_args()
    tag = a.tag

    print(f"\nverifying the seeded world (tag: {tag})\n")

    print("authentication — the credentials that worked before must still work")
    creator1 = f"creator1-{tag}@example.com"
    creator2 = f"creator2-{tag}@example.com"
    check("creator one can log in", login(creator1))
    who = cli("whoami")
    check("whoami reports the right identity", bool(who) and who.get("email") == creator1,
          (who or {}).get("email", "no response"))

    print("\nassistants — configuration survives, not merely the row")
    assistants = cli("assistant", "list") or []
    names = [x.get("name", "") for x in assistants]
    grounded = next((x for x in assistants if "biotutor" in x.get("name", "")), None)
    plain = next((x for x in assistants if "plaintutor" in x.get("name", "")), None)
    check("the grounded assistant exists", grounded is not None, ", ".join(names[:4]))
    check("the plain assistant exists", plain is not None)
    if grounded:
        cfg = cli("assistant", "get", str(grounded["id"])) or {}
        meta = cfg.get("metadata") or cfg.get("api_callback") or ""
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except json.JSONDecodeError:
                meta = {}
        check("its retrieval processor is still configured",
              "rag" in json.dumps(meta).lower(), json.dumps(meta)[:80])
        check("its system prompt survived", bool(cfg.get("system_prompt")),
              (cfg.get("system_prompt") or "")[:60])

    print("\nknowledge base — the vectors and the rows still agree")
    kbs = cli("kb", "list") or []
    kbs = kbs if isinstance(kbs, list) else kbs.get("knowledge_bases", [])
    kb = next((k for k in kbs if "biokb" in str(k.get("name", ""))), None)
    check("the knowledge base exists", kb is not None)
    if kb:
        hits = cli("kb", "query", str(kb["id"]), "What happens in the Calvin cycle?") or []
        check("retrieval returns results", len(hits) > 0, f"{len(hits)} hits")
        # Structural, not textual: the right *document* must come back. Which
        # words the model would generate from it is not this suite's business.
        top = (hits[0].get("data", "") if hits else "")
        check("the top hit is the photosynthesis document",
              "Photosynthesis" in top or "Calvin cycle" in top, top[:60].replace("\n", " "))

    print("\nlibrary — uploaded content is still readable")
    libs = cli("library", "list") or []
    libs = libs if isinstance(libs, list) else libs.get("libraries", [])
    lib = next((l for l in libs if f"biolib-{tag}" in str(l.get("name", ""))), None)
    check("the library exists", lib is not None)
    if lib:
        items = cli("library", "items", str(lib["id"])) or []
        items = items if isinstance(items, list) else items.get("items", [])
        check("its uploaded documents are listed", len(items) >= 3, f"{len(items)} items")

    print("\npublication and Open WebUI — the seam a student depends on")
    pub = db(LAMB_DB,
             "SELECT assistant_id, group_id, oauth_consumer_name FROM LAMB_assistant_publish "
             "WHERE assistant_name LIKE ?", f"%biotutor{tag}%")
    check("the assistant is still published", len(pub) > 0 and pub[0][0] != "ERROR",
          str(pub[0]) if pub else "no publication row")
    if pub and pub[0][0] != "ERROR":
        group_id = pub[0][1]
        owi_group = db(OWI_DB, 'SELECT id, name FROM "group" WHERE id = ? OR name = ?',
                       group_id, group_id)
        check("its Open WebUI group still exists", len(owi_group) > 0 and owi_group[0][0] != "ERROR",
              str(owi_group[0]) if owi_group else "group missing")

    print("\nLTI identities — students who launched last term")
    lti_users = db(LAMB_DB, "SELECT COUNT(*) FROM LAMB_lti_users")
    check("LTI user records survive", lti_users[0][0] != "ERROR" and lti_users[0][0] > 0,
          f"{lti_users[0][0]} users")
    owi_users = db(OWI_DB, 'SELECT COUNT(*) FROM "user"')
    check("Open WebUI accounts survive", owi_users[0][0] != "ERROR" and owi_users[0][0] > 0,
          f"{owi_users[0][0]} users")

    print("\nisolation — the boundary between organizations holds")
    if login(creator2):
        other = cli("assistant", "list") or []
        leaked = [x for x in other if "biotutor" in x.get("name", "")]
        check("creator two cannot see creator one's assistant", not leaked,
              f"{len(leaked)} leaked" if leaked else "none visible")
    else:
        check("creator two can log in", False, "login failed")

    failed = [r for r in results if not r[0]]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    if failed:
        print("\nfailures:")
        for _, name, detail in failed:
            print(f"  - {name}" + (f" ({detail})" if detail else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
