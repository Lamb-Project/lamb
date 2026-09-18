
### Personal learning scenarios

Use `lamb learning-scenario list|get|create|update|duplicate|remove|default|selected|select` for persistent teaching context, distinct from test cases. Load the `manage-learning-scenarios` skill before mutations. Inputs are inline text, never local filesystem paths. Read before editing, show changed fields, use the current `--revision`, request confirmation, and read back before reporting success. Discussion does not authorize saving.

`frontend-manage open learning-scenarios` opens the manager; `frontend-manage open learning-scenario SCENARIO_UUID --tab edit` opens an owned document. Wait for acknowledgement. Do not change the active session through `learning-scenario select` during a turn: that endpoint deliberately requires an idle session. New-conversation selection is available in the frontend picker; CLI users can use `lamb aac start --scenario ID|default|none`.

## Assistant test cases

A learning scenario describes creator context. A test case stores an assistant input and expected behaviour; a test run records its execution. Use `lamb test cases ASSISTANT_ID`, `lamb test case-detail CASE_ID ASSISTANT_ID`, `lamb test delete-case CASE_ID ASSISTANT_ID`, and `lamb test run ASSISTANT_ID --case CASE_ID`. Create and update remain `lamb test add` and `lamb test update`. The old `scenarios`, `scenario-detail`, `delete-scenario` commands and `--scenario` option remain compatibility aliases. Existing saved IDs, API paths and JSON fields are unchanged.

### Bind an existing owned file

`lamb assistant create NAME --rag-processor single_file_rag --file-reference REFERENCE`
and `lamb assistant update ID --file-reference REFERENCE` bind an existing upload
owned by the current creator. For example, use the reference returned by a confirmed
Moodle single-file import. The server validates ownership before saving the assistant.
This option does not read local files or upload anything. Local file selection still
belongs in the frontend. LiteShell continues to reject `--file-path`; the standalone
CLI retains that spelling as a compatibility alias for `--file-reference`.
