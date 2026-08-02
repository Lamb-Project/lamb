#!/usr/bin/env python3
"""Build the base enchilada — a realistic LAMB installation, created through the
product's own surfaces.

Everything here goes through `lamb-cli`, never through direct database writes: a
seed built by injecting rows would prove nothing about the paths real users take,
and it is precisely those paths an upgrade can break.

This covers what `dev` — base camp — can do. Knowledge Stores arrive with the
upgrade under test, so they are deliberately absent; the point of the baseline is
to hold content that already worked *before* the new features exist.

Usage:
    python3 testing/baseline/seed/seed_base.py --server http://localhost:9099 \
        --admin-email admin@owi.com --admin-password admin

Idempotent by tag: every object it creates carries the run tag in its name, so a
second run with the same tag reuses what is already there instead of duplicating.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

SAMPLES = Path(__file__).resolve().parent.parent / "samples"
STATE = Path(__file__).resolve().parent.parent / "checkpoints"


class Cli:
    """Thin wrapper over lamb-cli. Every call is logged so a failed seed can be
    read like a transcript."""

    def __init__(self, server: str, verbose: bool = True):
        self.server = server
        self.verbose = verbose

    def __call__(self, *args: str, json_out: bool = False, check: bool = True):
        cmd = ["lamb", *args]
        if json_out:
            cmd += ["-o", "json"]
        if self.verbose:
            printable = " ".join(a if "password" not in a.lower() else "***" for a in cmd)
            print(f"  $ {printable}")
        p = subprocess.run(cmd, capture_output=True, text=True)
        if check and p.returncode != 0:
            raise SystemExit(f"FAILED: {' '.join(cmd)}\n{p.stderr.strip()}")
        if json_out and p.returncode == 0:
            try:
                return json.loads(p.stdout)
            except json.JSONDecodeError:
                return None
        return p.stdout.strip() if p.returncode == 0 else None

    def login(self, email: str, password: str):
        self("login", "-s", self.server, "-e", email, "-p", password)


def _find(items, name: str):
    """Locate an object by name in a CLI list result, tolerating list/dict shapes."""
    if isinstance(items, dict):
        items = items.get("organizations") or items.get("users") or items.get("data") or []
    for it in items or []:
        if isinstance(it, dict) and it.get("name") == name or it.get("slug") == name:
            return it
    return None


def seed(cli: Cli, tag: str, admin_email: str, admin_password: str) -> dict:
    created: dict = {"tag": tag, "orgs": [], "users": [], "assistants": [], "kbs": [], "libraries": []}
    pw = "Baseline!2026"

    print("\n[1/7] system admin login")
    cli.login(admin_email, admin_password)

    print("\n[2/7] organizations — two, so cross-org isolation is testable")
    for slug in (f"bio-{tag}", f"chem-{tag}"):
        existing = _find(cli("org", "list", json_out=True), slug)
        if existing:
            print(f"  = org {slug} already exists")
        else:
            cli("org", "create", slug, "--slug", slug, "--signup-enabled",
                "--signup-key", f"key-{slug}")
        created["orgs"].append(slug)

    print("\n[3/7] users — org admin, two creators in different orgs, one end user")
    people = [
        (f"orgadmin-{tag}@example.com", "Org Admin", "creator", f"bio-{tag}"),
        (f"creator1-{tag}@example.com", "Creator One", "creator", f"bio-{tag}"),
        (f"creator2-{tag}@example.com", "Creator Two", "creator", f"chem-{tag}"),
        (f"student-{tag}@example.com", "Student One", "end_user", f"bio-{tag}"),
    ]
    for email, name, kind, org in people:
        out = cli("user", "create", email, name, pw, "-t", kind, "--org", org,
                  json_out=True, check=False)
        print(f"  {'+' if out else '='} {email} ({kind}) in {org}")
        created["users"].append({"email": email, "type": kind, "org": org})

    print("\n[4/7] library with uploaded course documents (creator one)")
    cli.login(f"creator1-{tag}@example.com", pw)
    lib = cli("library", "create", f"biolib-{tag}", json_out=True, check=False)
    lib_id = (lib or {}).get("id")
    if lib_id:
        created["libraries"].append(lib_id)
        for f in sorted(SAMPLES.glob("*.md")):
            cli("library", "upload", lib_id, str(f), check=False)
            print(f"  uploaded {f.name}")

    print("\n[5/7] knowledge base with genuinely ingested content")
    kb = cli("kb", "create", f"biokb-{tag}", "-d", "Biology 101 course materials",
             json_out=True, check=False)
    kb_id = (kb or {}).get("id") or (kb or {}).get("kb_id")
    if kb_id:
        created["kbs"].append(str(kb_id))
        for f in sorted(SAMPLES.glob("*.md")):
            cli("kb", "upload", str(kb_id), str(f), check=False)
        cli("kb", "ingest", str(kb_id), check=False)
        print(f"  ingested {len(list(SAMPLES.glob('*.md')))} files into kb {kb_id}")

    print("\n[6/7] assistants — one grounded in the knowledge base, one plain")
    # Configuration flags are required: without them the CLI drops into an
    # interactive wizard and creates nothing when stdin is not a TTY.
    common = ["--connector", "openai", "--llm", "glm-5.2",
              "--prompt-processor", "simple_augment"]
    grounded = cli("assistant", "create", f"biotutor-{tag}",
                   "-d", "Biology 101 tutor grounded in the course notes",
                   "-s", "You tutor Biology 101 using only the course notes provided. "
                         "If the answer is not in them, say so.",
                   *common, "--rag-processor", "simple_rag",
                   *(["--rag-collections", str(kb_id)] if kb_id else []),
                   json_out=True, check=False)
    plain = cli("assistant", "create", f"plaintutor-{tag}",
                "-d", "Tutor with no retrieval",
                "-s", "You are a general study assistant.",
                *common, "--rag-processor", "no_rag",
                json_out=True, check=False)
    for a in (grounded, plain):
        # the create response names it assistant_id, not id
        aid = (a or {}).get("assistant_id") or (a or {}).get("id")
        if aid:
            created["assistants"].append(aid)
    print(f"  created {len(created['assistants'])} assistants")

    print("\n[7/7] sharing — creator one shares with creator two (cross-org boundary)")
    if created["assistants"]:
        cli("assistant", "publish", str(created["assistants"][0]), check=False)
        print(f"  published assistant {created['assistants'][0]} (creates the OWI group)")

    return created


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", default="http://localhost:9099")
    ap.add_argument("--admin-email", required=True)
    ap.add_argument("--admin-password", required=True)
    ap.add_argument("--tag", default="base", help="suffix for every created object")
    args = ap.parse_args()

    cli = Cli(args.server)
    result = seed(cli, args.tag, args.admin_email, args.admin_password)

    STATE.mkdir(parents=True, exist_ok=True)
    manifest = STATE / f"seed-{args.tag}.json"
    manifest.write_text(json.dumps(result, indent=2))
    print(f"\nseed complete — manifest: {manifest}")
    print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in result.items()}, indent=2))


if __name__ == "__main__":
    main()
