
### Personal learning scenarios

Use `lamb learning-scenario list|get|create|update|duplicate|remove|default|selected|select` for persistent teaching context, distinct from test scenarios. Load the `manage-learning-scenarios` skill before mutations. Inputs are inline text, never local filesystem paths. Read before editing, show changed fields, use the current `--revision`, request confirmation, and read back before reporting success. Discussion does not authorize saving.

`frontend-manage open learning-scenarios` opens the manager; `frontend-manage open learning-scenario SCENARIO_UUID --tab edit` opens an owned document. Wait for acknowledgement. Do not change the active session through `learning-scenario select` during a turn: that endpoint deliberately requires an idle session. New-conversation selection is available in the frontend picker; CLI users can use `lamb aac start --scenario ID|default|none`.
