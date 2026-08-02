# Upgrade baseline harness

Testing that a migration applies proves the schema changed. It does not prove
that a teacher's assistant from last term still answers, that a student can
still reach it, or that the knowledge base still retrieves anything. Those are
the failures that matter when upgrading a live instance, and they are invisible
to schema tests.

This harness builds a realistic installation, captures it, and lets you replay
an upgrade against it as often as you like.

## The cycle

```bash
# 1. Build a world (once per baseline)
python3 testing/baseline/seed/seed_base.py \
    --admin-email admin@owi.com --admin-password <pw> --tag b2
python3 testing/baseline/seed/seed_lti.py \
    --consumer-key <published-assistant-consumer-name> --secret "$LTI_SECRET" --tag b2

# 2. Check it is healthy
python3 testing/baseline/verify/test_baseline.py --tag b2

# 3. Capture it (stack must be stopped — see the warning below)
docker stop lamb-backend lamb-openwebui-1 lamb-frontend-1 lamb-kb-1 \
    lamb-library-manager-1 lamb-kb-server-1
python3 testing/baseline/bundle.py save base-enchilada

# 4. Test an upgrade against it, any time, as often as you like
python3 testing/baseline/upgrade_test.py \
    --checkpoint base-enchilada --to <branch-or-tag> --tag b2
```

Step 4 restores the checkpoint, verifies the world *before* the upgrade (a
baseline that was already broken would otherwise convict the upgrade of damage
it did not do), moves the code, brings the stack up so migrations run, verifies
the same content again, and puts your branch back where it was.

## The pieces

| File | What it does |
|---|---|
| `seed/seed_base.py` | Builds the world through `lamb-cli` — organizations, users, a library with uploads, a knowledge base with genuinely ingested content, assistants, a published assistant. Never by writing database rows: a seed built by injection proves nothing about the paths users take, and those paths are what upgrades break. |
| `seed/seed_lti.py` | LTI identities via real OAuth-signed launches. Activities have no create endpoint — they come into being from a launch, which is how the product works. |
| `verify/test_baseline.py` | Sixteen checks over authentication, assistant configuration, retrieval, library content, publication and its Open WebUI group, LTI identities, and cross-organization isolation. |
| `bundle.py` | Save and restore a complete installation state, with integrity checks at both ends. |
| `upgrade_test.py` | The cycle above, in one command. |
| `samples/` | Synthetic course documents to ingest. In git, so the seed is reproducible. |
| `checkpoints/` | Captured state. Gitignored — rebuildable, and large. |

## Two rules that are not fussiness

**Never open the databases from the host while the stack is running.** They live
on the host and reach the containers through a bind mount. SQLite coordinates
concurrent access with POSIX advisory locks, and those are not reliably shared
across that boundary — a host process and a containerised process are two
writers who cannot see each other's locks. That corrupted a table here on
2026-08-02: the database read fine and reported "disk image is malformed" on one
table only. Use the API, `lamb-cli`, or `docker exec`. The tools do.

**A checkpoint is not a file.** It is the LAMB database, Open WebUI's database
with its uploads and vector store, the knowledge-base vector store, the Library
Manager's data and content, and user files under `static`. Missing one produces
a baseline that is wrong in ways the tests above it cannot see. `bundle.py`
handles all of them and refuses to save or restore a database that fails
SQLite's integrity check.

## What the assertions do and do not claim

Structural, never textual. The suite asserts that retrieval returns the expected
*document* — not that a model produced particular words. Generated text is not
stable, and a suite that asserts on it cries wolf until nobody reads it.

## Related

`testing/migrations/` builds a database at a chosen schema version and upgrades
a copy, reporting the schema delta. That answers "did the migration apply"; this
answers "does the content still work".
