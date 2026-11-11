

> **Name.** In the user interface this component is **LAMB LEGATUS**: like a Roman *legatus* acting on behalf of the Senate, it acts on behalf of the teacher, who keeps the agency and the decisions. Code, APIs and this manual keep the internal name AAC.
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

### Assignment submission chart pilot

`moodle chart submissions --course COURSE_ID --tz Europe/Madrid --language es`

This read-only recipe saves an owned aggregate snapshot and exposes a chart card in
LAMB LEGATUS. It uses Moodle's all-groups grading summary, not course enrolment totals.
It checks at most 20 assignments. Team and offline assignments, missing summaries
and inconsistent counts are explicitly excluded, never shown as zero. Outstanding
includes drafts; a passed course deadline does not prove individual lateness because
personal extensions and overrides are not inspected. No student-level records or
grades are retained by this recipe. Reopening preserves the original figures;
running the command again creates a new snapshot. The pilot retains up to 100 charts
per creator. Image and table access require the owning connection and current
instructor access. Languages: `en`, `es`, `ca`, `eu`; timezone defaults to `UTC`.

The terminal equivalent is `lamb moodle chart submissions` with the same options;
it returns the chart handle and aggregate figures as JSON.

### Assistant activity analysis (0.9)

The `inspect-activity` recipe proposes analysis dimensions or a Full audit, checks the learning scenario, reads bounded conversation evidence and saves a dated report under the assistant. Full audit covers all dimensions; coverage still states any sampling, truncation or unavailable source. Reports require full conversation analytics access.

- `lamb analytics analysis-context ASSISTANT_ID --dimensions full --limit 20` reads a bounded sample and retains its evidence receipt. Options: `--start-date`, `--end-date`, `--scenario SCENARIO_ID|none`; dimensions can be comma-separated `participation,patterns,learning,assistant,friction,boundaries`. The maximum sample is 50 conversations. Date-only bounds use UTC, with the whole end day included.
- `lamb analytics reports ASSISTANT_ID` lists saved reports, newest first, across sessions.
- `lamb analytics report ASSISTANT_ID REPORT_ID` reads a saved report and its original context.
- In Auto, include `analysis_id` alongside `title` and `assistant_id` in the plan's `report` object. After the plan's single approval, `lamb report save --content "REPORT" --reviewed '["CHAT_ID"]'` saves it. `lamb plan finish` exposes Show report. The report is immutable; reanalysis starts a new receipt.
- The external CLI also supports `lamb analytics report-save ASSISTANT_ID RECEIPT_ID --file report.json`, where the JSON contains `title`, `content` and `reviewed_chat_ids`.

Receipts retain measured coverage and the scenario snapshot, not duplicated conversation bodies. A declared reviewed subset is recorded separately from the conversations provided. Historical evidence opens through current analytics permissions. Reports do not grade individual students or establish learning gains from activity counts.
