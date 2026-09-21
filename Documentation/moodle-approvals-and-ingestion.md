# Moodle approvals and ingestion settings

Implemented on `feature/moodle-connector-487`, engine 0.7.7 and AAC pack 1.8.0.

## Approval presentation

The Moodle connection page includes a personal **Advanced mode** setting beside the QR connection controls. Basic mode is the default. Both modes show the proposed change and the exact values needed to review it. Advanced mode also displays the executable command. The setting applies to all the user's LAMB AGENT conversations, from the next approval message; it never grants additional permissions. It survives disconnects and applies across browsers.

For each pending action, the application asks the organization's **Small Fast Model** to explain the proposed change in one short sentence. This is the model configured under organization model settings, separate from the AAC driver and its translation utility model. OpenAI-compatible and Ollama configurations are supported. If absent, unsupported, unavailable or too slow, the deterministic review remains usable. There is no fallback to another provider. Configure the Small Fast Model if generated explanations are wanted.

The call receives bounded proposed action values, not the conversation or retrieved documents. It has no tools, cannot change the queued command and cannot authorize execution. Its explanation supplements the exact review. Import source, destination, excluded files, conversion warnings and chunking remain visible; grade proposals retain the submission and proposed values. Action details may reach a hosted small/fast provider, as disclosed on the Moodle page.

Explanations use the session's effective response language. They are cached with the pending action, including failures, so repeated approval discussions do not repeat the call. Changing the presentation setting does not rewrite prior conversation messages or the pinned system prompt. The auxiliary request has a 30-second overall limit. Provider errors never become approval errors.

Read-only Moodle commands are automatically authorized by the registered command contract. The AAC recipes explicitly tell the model to execute the reads needed for a user request without asking permission. Course and owner checks still apply. Unknown commands are refused. Importing into LAMB is a write even when Moodle access is read-only, so it retains one application confirmation.

## Ingestion choices

Both LiteShell and `lamb moodle` accept these options on `import file`, `import page`, `import book`, `import folder` and `import refresh`:

| Option | New import default | Meaning |
|---|---|---|
| `--chunk-size` | 1000 | Positive chunk size |
| `--chunk-overlap` | 100 | Nonnegative overlap, smaller than chunk size |
| `--splitter-type` | `RecursiveCharacterTextSplitter` | Also supports `CharacterTextSplitter` and `TokenTextSplitter` |

The character splitters use characters. TokenTextSplitter uses its own tokenizer's tokens, not a measurement of the assistant model's context window. The defaults preserve the existing Moodle import behavior; they are not a claim that every ingestion plugin has the same defaults. Converter selection remains automatic according to the supported file type. These options do not enable arbitrary plugins or unsupported formats.

For example, in AAC LiteShell:

```text
moodle import folder FOLDER_REF --to kb KB_ID --chunk-size 2000 --chunk-overlap 200
moodle import refresh IMPORT_ID --chunk-size 3000
```

The terminal CLI uses `lamb moodle ...` and requires its owned `--session SESSION_ID`; the confirmation request also carries `--confirm REVIEW_ID` returned by the review endpoint.

The chosen settings are part of the exact approval, each file's receipt and the ingestion job. Folder settings apply to every included file. Changing options invalidates an existing approval. `finish` resumes the approved settings, without starting duplicate imports. Refresh reuses the original receipt's settings for omitted options, including a partial override such as changing only chunk size. Pre-option receipts retain the previous 1000/100 behavior. Single-file grounding keeps the full document and rejects chunking options.

The AAC must use an explicit user request rather than silently substitute defaults, and inspect job parameters before claiming what was applied. An ingestion job completing does not itself prove useful retrieval; query the KB for that.

## LAMB 1.0 follow-through

The library-based replacement must preserve user-selectable ingestion parameters across UI, CLI and AAC, with defaults only when omitted. Store effective plugin/chunking choices in library ingestion provenance; show them in approval and status; retain them on re-ingestion unless explicitly overridden. This is an acceptance requirement for the future library migration, not an implementation on the parked alpha branch.
