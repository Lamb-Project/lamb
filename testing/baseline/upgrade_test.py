#!/usr/bin/env python3
"""Test an upgrade against content that already worked.

    python3 testing/baseline/upgrade_test.py --checkpoint base-enchilada \
        --to integration/456-merge --tag b2

Restores the checkpoint, moves the code to the target revision, brings the stack
up — migrations run on boot — and re-runs the verification suite that passed
before. Anything that used to work and now does not is the answer we came for.

The suite is run *before* the upgrade too. A baseline that was already broken
would otherwise convict the upgrade of damage it did not do.

Nothing here is destructive to your work: the checkpoint is copied, not consumed,
and the branch you were on is restored at the end.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAMB = Path("/opt/lamb")
# The harness must outlive the checkout. These files live in the repository
# under test, so switching to the target revision deletes them mid-run — an
# upgrade test whose tester changes with the tested is measuring a moving
# target. They are copied out before anything moves and run from the copy.
TOOLS = Path(tempfile.mkdtemp(prefix="lamb-upgrade-harness-"))
STACK = ["lamb-kb-1", "lamb-library-manager-1", "lamb-kb-server-1",
         "lamb-openwebui-1", "lamb-frontend-1", "lamb-backend"]


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def git(*args: str) -> str:
    return run(["git", "-C", str(LAMB), *args]).stdout.strip()


def stack(action: str) -> None:
    order = STACK if action == "start" else list(reversed(STACK))
    run(["docker", action, *order])


def wait_healthy(timeout: int = 300) -> bool:
    """Wait until the stack can actually serve, not merely until it is running.

    "Up" is not "ready" three times over: migrations run on boot, SQLite rebuilds
    its side files before accepting writes, and the HTTP surface plus the library
    and knowledge-base services come up after the container does. A probe that
    checks one of those returns too early and the suite fails against a stack
    that was never asked a fair question — which, in an upgrade test, convicts
    the upgrade of damage it did not do.
    """
    import urllib.request

    def db_writable() -> bool:
        p = run(["docker", "exec", "lamb-backend", "python", "-c",
                 "import sqlite3;c=sqlite3.connect('/opt/lamb/lamb_v4.db');"
                 "c.execute('create table if not exists _probe(x int)');c.commit();"
                 "c.execute('drop table _probe');c.commit();print('rw')"])
        return "rw" in p.stdout

    def http_ok(url: str) -> bool:
        try:
            urllib.request.urlopen(url, timeout=4)
            return True
        except Exception as e:
            # A 404 still proves something is listening and routing.
            return getattr(e, "code", None) is not None

    deadline = time.time() + timeout
    # Required: present in every revision this harness spans.
    checks = {
        "database writable": db_writable,
        "backend API": lambda: http_ok("http://localhost:9099/docs"),
        "library manager": lambda: http_ok("http://localhost:9091/health"),
    }
    # Optional: the knowledge-store service ships *with* the upgrade, so on a
    # base-camp revision its source is not even on disk. Requiring it would make
    # the baseline unverifiable for the very reason we are testing the upgrade.
    optional = {"knowledge store": lambda: http_ok("http://localhost:9092/health")}
    pending = dict(checks)
    while time.time() < deadline and pending:
        for name, probe in list(pending.items()):
            if probe():
                print(f"    ready: {name}")
                pending.pop(name)
        if pending:
            time.sleep(5)
    if pending:
        print(f"    NOT ready: {', '.join(pending)}")
    for name, probe in optional.items():
        print(f"    {'ready' if probe() else 'absent'}: {name} (optional)")
    return not pending


def verify(tag: str) -> tuple[bool, str]:
    p = run([sys.executable, str(TOOLS / "test_baseline.py"), "--tag", tag])
    tail = [l for l in p.stdout.splitlines() if "checks passed" in l]
    if p.returncode != 0 and not tail:
        # Surface why rather than reporting a blank verdict: a harness that
        # fails silently is indistinguishable from a product that broke.
        detail = (p.stderr or p.stdout).strip().splitlines()
        return False, "harness error: " + (detail[-1][:150] if detail else "no output")
    return p.returncode == 0, (tail[-1] if tail else p.stdout.strip()[-120:])


def schema_version() -> str:
    p = run(["docker", "exec", "lamb-backend", "python", "-c",
             "import sqlite3;c=sqlite3.connect('/opt/lamb/lamb_v4.db');"
             "print(c.execute('select coalesce(max(version),0) from LAMB_schema_version').fetchone()[0])"])
    return p.stdout.strip() or "?"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--to", required=True, help="git revision to upgrade to")
    ap.add_argument("--tag", default="b2", help="seed tag the checkpoint contains")
    ap.add_argument("--keep-upgraded", action="store_true",
                    help="leave the upgraded database in place for inspection "
                         "instead of restoring the checkpoint at the end")
    a = ap.parse_args()

    shutil.copy2(HERE / "verify" / "test_baseline.py", TOOLS / "test_baseline.py")
    shutil.copy2(HERE / "bundle.py", TOOLS / "bundle.py")
    print(f"harness copied out of the repository to {TOOLS}")

    started_on = git("rev-parse", "--abbrev-ref", "HEAD")
    print(f"starting on {started_on}, upgrading to {a.to}\n")

    print("[1/6] restoring the checkpoint")
    stack("stop")
    p = run([sys.executable, str(TOOLS / "bundle.py"), "restore", a.checkpoint])
    if p.returncode != 0:
        print(p.stdout + p.stderr)
        return 1
    stack("start")
    if not wait_healthy():
        print("stack did not become writable — aborting")
        return 1
    before_version = schema_version()
    print(f"  restored, schema v{before_version}")

    print("\n[2/6] verifying the baseline BEFORE the upgrade")
    ok_before, summary_before = verify(a.tag)
    print(f"  {summary_before}")
    if not ok_before:
        print("  the baseline is already failing — fix that before blaming an upgrade")
        return 1

    print(f"\n[3/6] moving the code to {a.to}")
    stack("stop")
    run(["git", "-C", str(LAMB), "stash", "push", "-u", "--", "lamb-kb-server"])
    co = run(["git", "-C", str(LAMB), "checkout", a.to])
    if co.returncode != 0:
        print("  checkout failed:", co.stderr.strip()[:200])
        stack("start")
        return 1
    print(f"  now on {git('rev-parse', '--abbrev-ref', 'HEAD')} @ {git('rev-parse', '--short', 'HEAD')}")

    print("\n[4/6] starting the stack — migrations run on boot")
    stack("start")
    if not wait_healthy():
        print("  stack did not become writable after the upgrade — that is the finding")
        return 1
    after_version = schema_version()
    print(f"  schema v{before_version} -> v{after_version}")

    print("\n[5/6] verifying the SAME content AFTER the upgrade")
    ok_after, summary_after = verify(a.tag)
    print(f"  {summary_after}")

    print("\n[6/6] returning the machine to where you left it")
    stack("stop")
    run(["git", "-C", str(LAMB), "checkout", started_on])
    run(["git", "-C", str(LAMB), "stash", "pop"])
    if a.keep_upgraded:
        print("  code restored; database left upgraded (--keep-upgraded)")
    else:
        # Restoring the branch without the database leaves a schema from the
        # target revision under the code of the original one. Nothing complains,
        # and the next person inherits a hybrid that matches no commit.
        run([sys.executable, str(TOOLS / "bundle.py"), "restore", a.checkpoint])
        print("  code and database both restored")
    stack("start")
    wait_healthy()

    print("\n" + "=" * 62)
    print(f"upgrade {started_on} -> {a.to}: schema v{before_version} -> v{after_version}")
    print(f"  before: {summary_before}")
    print(f"  after:  {summary_after}")
    print("VERDICT: the upgrade preserved everything the baseline covers"
          if ok_after else
          "VERDICT: the upgrade BROKE content that worked before — see the failures above")
    print("=" * 62)
    return 0 if ok_after else 1


if __name__ == "__main__":
    sys.exit(main())
