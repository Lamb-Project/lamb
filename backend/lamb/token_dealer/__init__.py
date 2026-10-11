"""token-dealer: LAMB as the control plane of student LLM access (#533).

LAMB issues per-student keys for an LTI "LLM access" activity, configures an external
LiteLLM-class proxy (the data plane), opens and closes access on a timetable, and reads
usage back. No token traffic passes through LAMB.

Modules: units (tokens <-> proxy budget units), schedule (timetables), settings (organization
config), store (activities, keys, sync state in LAMB's database), ledger (usage aggregates in a
separate database), proxy_client (proxy admin API), service (configure, issue, rotate, revoke),
worker (the reconcile and ingestion loops, run as its own process).
"""
