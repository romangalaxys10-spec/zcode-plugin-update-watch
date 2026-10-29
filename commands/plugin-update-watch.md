---
description: Audit, diff, upgrade, and roll back installed ZCode plugins and skills with backup refs and manifest validation.
allowed-tools: Read, Bash, Write
argument-hint: [root dir to scan] [plugin slug]
---
Invoke the `plugin-update-watch` skill with this input: **$ARGUMENTS**

- No arguments: AUDIT all default roots (workspace plugins dir, installed
  cache) with `scripts/update_check.py`, then report which plugins have
  updates.
- With a root or slug: scope the audit to it, then walk AUDIT -> DIFF ->
  UPGRADE -> ROLLBACK in order. Never skip DIFF before UPGRADE, and never
  upgrade without creating the backup ref first.
