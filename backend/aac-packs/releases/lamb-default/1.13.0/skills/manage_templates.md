---
id: manage-templates
name: Manage Prompt Templates
description: Create, inspect, edit, duplicate, share and export prompt templates
required_context: []
optional_context: [language]
---

Use `lamb template list` or `lamb template list-shared`, then `lamb template get ID` to read the actual fields before proposing changes.

Create: `lamb template create NAME --description TEXT --system-prompt TEXT --prompt-template TEXT`. Add `--shared` only if the user requested organization sharing. Edit: `lamb template update ID` with only requested fields. Duplicate: `lamb template duplicate ID --new-name NAME`. Share/unshare: `lamb template share ID --enable` or `--disable`. Delete: `lamb template delete ID` only for an explicit deletion request, never as an edit workaround. These writes need approval of the exact proposed command. Read the resulting template back and report actual IDs/fields before claiming success.

Use `lamb template export ID [ID ...]` for inline JSON; no file flags in frontend liteshell. Export is a read even though the endpoint uses POST. Do not write a local file or invent a download path. Ownership and organization checks apply; stop on forbidden/not-found results. Template inspection or explanation never implies approval to change it.
