# LAMB AGENT knowledge content

Agent-readable documentation lives in [`backend/agent-docs/`](../backend/agent-docs/), with stable topic and section identifiers, locale coverage and image hashes in its manifest. Images are served under `/agent-docs`. Human-facing deployment and CLI manuals remain in `Documentation/`.

Persona, workflow skills, role layers, routing and glossaries live in [`backend/aac-packs/`](../backend/aac-packs/). Organisation administrators select a channel or installed version in LAMB AGENT settings. Existing sessions refresh their instructions once when the selected version changes; pending approvals retain their original pack until resolved.

The default directories can be overridden with `LAMB_AGENT_DOCS_DIR` and `LAMB_AAC_PACKS_DIR`. Mount the whole pack directory, including channel metadata and any releases needed by saved sessions. Content is hash-checked before use.

Validate a content build from the backend environment:

```sh
python -m lamb.aac.pack_build
```

Authoring builds use `--write` to generate glossary UI labels from the frontend locale bundles and refresh content hashes and documentation coverage. They require the frontend source checkout. Published versions are immutable; edit a new version rather than changing a released directory. The `qa-1.1` bank specifies model acceptance separately from deterministic build checks.
