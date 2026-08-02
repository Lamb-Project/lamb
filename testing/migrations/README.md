# Migration checkpoints

Testing a migration by re-running it on a database that already applied it proves
almost nothing — the guards make it a no-op. The case that matters is a database
that has **never seen** the new migrations: a deployment sitting at an older
version, being upgraded. That is what breaks, and that is what this builds.

```bash
python3 testing/migrations/checkpoint.py build 25     # a fresh database at v25
python3 testing/migrations/checkpoint.py upgrade 25   # copy it, migrate to LATEST, report
python3 testing/migrations/checkpoint.py list
```

`build` creates the base schema the way a new install does, then applies migrations
up to the version you name — giving a reusable baseline of a deployment at that
version. `upgrade` **copies** the checkpoint before migrating, so the baseline is
never consumed and the same upgrade can be run as many times as you like.

`upgrade` reports what the migration chain actually produced — new tables, new
columns per table — rather than only that it finished. It fails if the final
version disagrees with `LATEST_VERSION`, and warns about versions that were never
applied on that database (a gap, which on the current high-water-mark runner can
never be filled afterwards).

Checkpoints are build artifacts, not source: they live in `checkpoints/` and are
gitignored. Rebuild them from code whenever you need them.
