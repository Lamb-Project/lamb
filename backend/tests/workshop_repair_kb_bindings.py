"""One-shot S1 repair — reset workshop assistants' RAG_collections.

Why
---
Before S1 the workshop wizard trusted a client-supplied ``kb_id`` /
``rag_collections``. Whatever a student sent was written to
``assistants.RAG_collections`` and re-read on **every** later turn by both
``simple_rag`` and the ``kb_query`` tool — so a single crafted request could
permanently point an assistant at another student's collection.

S1 closes the write paths and adds a runtime assertion on the retrieval paths.
This script cleans up rows written *before* that fix.

What it does
------------
For every assistant that looks workshop-built (owner on the synthetic student
domain ``@lamb-lti.local``):

* find its workshop session (``lti_workshop_sessions.assistant_id``)
* compare ``RAG_collections`` with the session's ``kb_id``
* rewrite it to the session kb_id (or clear it when the session has no KB)

Assistants that are not workshop-built are never touched.

Usage
-----
Run inside the backend container (it has the DB and the repo bind-mounted):

    docker compose exec backend python tests/workshop_repair_kb_bindings.py
    docker compose exec backend python tests/workshop_repair_kb_bindings.py --apply

Without ``--apply`` the script is a dry run: it only prints what it would do.
"""

import argparse
import os
import sys

# Running this file directly puts tests/ on sys.path, not the backend root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lamb.database_manager import LambDatabaseManager  # noqa: E402
from lamb.lamb_classes import Assistant  # noqa: E402
from lamb.modules.workshop.kb import (  # noqa: E402
    WORKSHOP_STUDENT_EMAIL_DOMAIN,
    _split_collection_ids,
)


def _iter_workshop_assistants(db):
    """Yield every student-domain assistant row (idempotent, read-only)."""
    connection = db.get_connection()
    if not connection:
        raise SystemExit("Could not open the LAMB database.")
    try:
        cursor = connection.cursor()
        cursor.execute(
            f"SELECT id, name, owner, organization_id, RAG_collections "
            f"FROM {db.table_prefix}assistants "
            f"WHERE LOWER(owner) LIKE ?",
            (f"%{WORKSHOP_STUDENT_EMAIL_DOMAIN}",),
        )
        columns = [col[0] for col in cursor.description]
        for row in cursor.fetchall():
            yield dict(zip(columns, row))
    finally:
        connection.close()


def _plan(db):
    """Return the list of (assistant_row, session, target, action) findings."""
    findings = []
    for row in _iter_workshop_assistants(db):
        owner = str(row.get("owner") or "")
        if not owner.lower().endswith(WORKSHOP_STUDENT_EMAIL_DOMAIN):
            continue
        session = db.get_workshop_session_by_assistant(row.get("id"))
        if not session:
            # Student-domain row with no session: not a workshop assistant we
            # can reason about — leave it alone.
            continue

        session_kb = session.get("kb_id")
        target = str(session_kb) if session_kb else ""
        current = [c for c in _split_collection_ids(row.get("RAG_collections"))]

        if current == ([target] if target else []):
            findings.append((row, session, target, "ok"))
        else:
            findings.append((row, session, target, "repair"))
    return findings


def _apply(db, row, target):
    """Rewrite one assistant's RAG_collections (keeps every other field)."""
    existing = db.get_assistant_by_id(row["id"])
    if not existing:
        return False

    updated = Assistant(
        name=existing.name,
        description=existing.description,
        owner=existing.owner,
        api_callback=existing.metadata,
        system_prompt=existing.system_prompt,
        prompt_template=existing.prompt_template,
        organization_id=existing.organization_id,
        pre_retrieval_endpoint="",
        post_retrieval_endpoint="",
        RAG_endpoint="",
        RAG_Top_k=existing.RAG_Top_k or 3,
        RAG_collections=target,
    )
    return bool(db.update_assistant(row["id"], updated))


def main():
    parser = argparse.ArgumentParser(
        description="Reset workshop assistants' RAG_collections to their "
                    "session KB (S1 dirty-data repair).")
    parser.add_argument("--apply", action="store_true",
                        help="write the repairs (default: dry run)")
    args = parser.parse_args()

    db = LambDatabaseManager()
    findings = _plan(db)

    if not findings:
        print("No workshop-built assistants found — nothing to check.")
        return 0

    dirty = [f for f in findings if f[3] == "repair"]
    print(f"Checked {len(findings)} workshop assistant(s); "
          f"{len(dirty)} need repair.")

    for row, session, target, action in findings:
        current = row.get("RAG_collections")
        marker = "OK    " if action == "ok" else "REPAIR"
        print(f"  [{marker}] assistant={row['id']} owner={row['owner']} "
              f"session={session.get('id')} "
              f"RAG_collections={current!r} -> {target!r}")

    if not dirty:
        return 0

    if not args.apply:
        print("\nDry run — re-run with --apply to write these changes.")
        return 0

    repaired = 0
    for row, _session, target, action in dirty:
        if _apply(db, row, target):
            repaired += 1
        else:
            print(f"  !! failed to update assistant {row['id']}")
    print(f"\nRepaired {repaired}/{len(dirty)} assistant(s).")
    return 0 if repaired == len(dirty) else 1


if __name__ == "__main__":
    raise SystemExit(main())