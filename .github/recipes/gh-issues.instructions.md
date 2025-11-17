---
description: GitHub issue management best practices using GitHub CLI
---

# GitHub Issue Management

## Key Rule: Always use `--body-file` with GitHub CLI

When creating or updating GitHub issues, use `--body-file` instead of `--body` to prevent bash from interpreting special characters (backticks, file paths, URLs).

IMPORTANT: NEVER use heredoc syntax (<<EOF ... EOF) for issue bodies or generating the file content, as it can lead to too-long lines in bash and cause issues.

Again, ALWAYS create temporary markdown files without resorting to heredoc syntax.

## Workflow:

1. Create temporary markdown file with issue content
2. Use `gh issue create --body-file filename.md`
3. Add labels with `gh issue edit <number> --add-label "label1,label2"`
4. Clean up temporary file

## Available labels:

`enhancement`, `bug`, `documentation`, `technical-debt`, `good-first-issue`, `help-wanted`, `question`, `discussion`, `invalid`, `wontfix`, `duplicate`
