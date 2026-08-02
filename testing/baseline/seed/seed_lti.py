#!/usr/bin/env python3
"""Seed the LTI half of the baseline: activities and the students who reached them.

LTI activities have no create endpoint — they come into existence when a launch
arrives from the LMS, which is how the product genuinely works. So this performs
real OAuth-signed launches rather than inserting rows, reusing the signing code
already in `testing/lti_test.py`.

This is the content most likely to break across an upgrade and least likely to be
noticed: a student who launched an assistant last term has an LTI user record, an
Open WebUI account, and membership in the assistant's group. Three tables, two
databases, and an identity mapping between them.

Usage:
    python3 testing/baseline/seed/seed_lti.py --consumer-key 366_biotutorb2 \
        --secret "$LTI_SECRET" --tag b2
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lti_test import build_lti_params, launch_student, launch_unified  # noqa: E402

LAMB_DB = "/opt/lamb/lamb_v4.db"
OWI_DB = "/opt/lamb/open-webui/backend/data/webui.db"


def _count(db: str, sql: str) -> int:
    con = sqlite3.connect(db)
    try:
        return con.execute(sql).fetchone()[0]
    except sqlite3.Error:
        return -1
    finally:
        con.close()


def snapshot() -> dict:
    return {
        "lti_users": _count(LAMB_DB, "SELECT COUNT(*) FROM LAMB_lti_users"),
        "lti_activities": _count(LAMB_DB, "SELECT COUNT(*) FROM LAMB_lti_activities"),
        "owi_users": _count(OWI_DB, 'SELECT COUNT(*) FROM "user"'),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:9099")
    ap.add_argument("--consumer-key", required=True,
                    help="the published assistant's oauth_consumer_name (legacy flow)")
    ap.add_argument("--unified-key", default="lamb",
                    help="global LTI consumer key (unified flow) — the two flows "
                         "validate against different keys")
    ap.add_argument("--secret", required=True)
    ap.add_argument("--tag", default="base")
    ap.add_argument("--course", default="BIO101")
    args = ap.parse_args()

    before = snapshot()
    print(f"before: {before}")

    # An instructor launch first: in the unified flow this is what brings the
    # activity into being, and a student arriving at a course with no activity
    # is a different code path entirely.
    # NOTE: an instructor launching a resource_link that has no activity yet is
    # sent to a setup page to choose an assistant — a browser step. So this
    # seeds the identities headlessly; the activity itself is created by the
    # Playwright half of the seed. Both flows are exercised because they
    # validate against *different* consumer keys, and an upgrade could break
    # either one alone.
    print("\n[1/3] instructor launch (reaches the activity setup page)")
    launch_unified(
        args.base_url, args.unified_key, args.secret,
        user_id=f"instructor-{args.tag}", role="instructor",
        resource_link_id=f"link-{args.course}-{args.tag}",
        context_id=args.course, context_title=f"Biology 101 ({args.course})",
        display_name="Course Instructor", email=f"instructor-{args.tag}@example.com",
        username=f"instructor-{args.tag}",
    )

    print("\n[2/3] two student launches through the unified flow, plus the legacy flow")
    for n in (1, 2):
        launch_unified(
            args.base_url, args.unified_key, args.secret,
            user_id=f"student{n}-{args.tag}", role="learner",
            resource_link_id=f"link-{args.course}-{args.tag}",
            context_id=args.course, context_title=f"Biology 101 ({args.course})",
            display_name=f"Student {n}", email=f"student{n}-{args.tag}@example.com",
            username=f"student{n}-{args.tag}",
        )
    # The legacy student endpoint is still reachable in the wild, so a baseline
    # that only exercises the unified flow would not notice it breaking.
    # NOTE (Marc, 2026-08-02): the legacy LTI activity path is to be discontinued
    # soon. Keep seeding it until it is actually gone — a baseline exists to prove
    # that what used to work still does, and the day it is removed the assertion
    # that it stopped working is the point. See issue #467 for the instructor
    # workflow that replaces it.
    launch_student(args.base_url, args.consumer_key, args.secret,
                   user_id=f"legacy-{args.tag}", username=f"legacy-{args.tag}")

    print("\n[3/3] repeat launch by the first student (must resolve to the same account)")
    launch_unified(
        args.base_url, args.unified_key, args.secret,
        user_id=f"student1-{args.tag}", role="learner",
        resource_link_id=f"link-{args.course}-{args.tag}",
        context_id=args.course, context_title=f"Biology 101 ({args.course})",
        display_name="Student 1", email=f"student1-{args.tag}@example.com",
        username=f"student1-{args.tag}",
    )

    after = snapshot()
    print(f"\nafter: {after}")
    delta = {k: after[k] - before[k] for k in before}
    print(f"delta: {delta}")
    if delta["lti_users"] > 3:
        print("WARNING: more LTI users than students launched — the repeat launch "
              "may have created a duplicate instead of resolving to the same account")


if __name__ == "__main__":
    main()
