# LAMB 0.7 deployment release notes

Release readiness remains subject to the Linux validation gate in #482.

## LAMB LEGATUS

The assistant that works beside you in LAMB (creating and improving assistants, knowledge bases, rubrics, tests, and Moodle work) is called **LAMB LEGATUS**. In Rome a *legatus* acted on behalf of the Senate on diplomatic missions: it carried out the Senate's decisions, it did not make them. LAMB LEGATUS works the same way. It proposes, explains and carries out what the teacher asks or approves; the teacher keeps the agency and the decisions. That is why it is not called an agent. Internally the component is still the AAC (`aac` in code, APIs and settings).

## Deployment notes

- **Upgrade from 0.6 requires data migration.** Follow the [canonical upgrade guide](installation/migrating-to-lamb-next.md), including stopped backups, the verified copy script, application checks and rollback rehearsal. Persistent stores move to named volumes, including KB files, Library Manager data and backend uploads.
- **Storage paths are pinned in base Compose.** Development keeps source mounts and hot reload, with persistent stores on the same named volumes. Legacy `.env` data paths cannot redirect LAMB or Open WebUI databases back into source mounts.
- **LAMB LEGATUS requires a configured organisation default model.** An organisation without a configured default receives HTTP 503 instead of silently using `gpt-4o-mini`. In organisation administration, configure and save an enabled provider and its global default model, then retry. Check that provider's credentials/connectivity if it remains unavailable.
- **`gpt-5-mini` is the configuration example**, not an automatic migration of existing organisation settings. Existing saved models and secrets must be preserved.
- **Rollback restores the old code, configuration, images and original data.** It does not contain writes made after starting 0.7. Retain the new volumes separately; do not overwrite the old database with them.

Before publication, record clean-install and real-0.6 upgrade results on Linux, preservation of all stores, stack restart, a RAG query, rollback and development-overlay storage verification with a legacy `backend/.env` present. Copy-script tests alone do not meet this gate.
