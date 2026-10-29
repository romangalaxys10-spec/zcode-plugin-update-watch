---
name: plugin-update-watch
description: Use when the user wants to check whether installed ZCode plugins/skills have upstream updates, see what changed before updating, upgrade safely, or roll back an upgrade. Covers git-cloned and local-source installs in the workspace plugins dir and the installed cache.
---

# Plugin Update Watch

Update installed ZCode plugins and skills without breaking the ones that
work. Every upgrade is reversible: a backup tag or branch is created first,
and `git reset` is never used to roll back. The script and the workflow
never push and never force-pull.

## Inputs

- Optional roots to scan. Default roots (scan all that exist):
  - `~/.zcode/workspace/default/plugins/` (local source installs)
  - `~/.zcode/cli/plugins/cache/` (installed cache)
- Optional scope: a single plugin slug (example: `roast-my-app`).

## Workflow

### 1. AUDIT

1. Enumerate installed plugins. A plugin is any subdirectory of a root that
   contains `.zcode-plugin/plugin.json`. Cache dirs live under
   `<provider>/<name>/<version>/`.
2. For git-cloned ones (a `.git` inside the plugin dir), run:

   ```
   python3 scripts/update_check.py <root...>
   ```

   It prints, per repo: current commit, `origin/<branch>` commit, new commit
   count, and the version delta parsed from
   `.zcode-plugin/plugin.json` or `marketplace.json` (local vs remote, where
   a remote version is available). It exits 0 with no updates and 10 when at
   least one update exists. Human-readable output goes to stdout; add
   `--json` for the machine view.
3. For non-git local sources there is no upstream to fetch; list them as
   `local (no remote)` so the user knows which ones cannot be checked.
4. Honest limits: a plugin installed via the marketplace copy (Option B,
   manual copy) has no `.git`, so the audit reports what it sees on disk and
   cannot diff it against anything. Say so instead of guessing.

### 2. DIFF (before applying anything)

For every repo with updates available, in the local clone:

```
git -C <plugin-dir> fetch --no-tags --quiet origin
git -C <plugin-dir> log --oneline HEAD..origin/<branch>
git -C <plugin-dir> diff --stat HEAD..origin/<branch>
```

Summarize per plugin:
- commit/tag delta (old SHA -> new SHA, N new commits),
- files touched (from `diff --stat`),
- version bumps: diff the `version` field of `.zcode-plugin/plugin.json` and
  `marketplace.json` between HEAD and the upstream ref (read both sides from
  the local clone: `git show HEAD:.zcode-plugin/plugin.json` vs
  `git show origin/<branch>:.zcode-plugin/plugin.json`),
- changelog entries added: `git diff HEAD..origin/<branch> -- CHANGELOG.md`
  (first ~20 lines).

If a plugin adds or removes a `hooks` entry in `plugin.json`, flag it: hook
changes are the only plugin updates that can change agent behavior on every
command.

### 3. UPGRADE

For each plugin the user approves:

1. Record the current ref: `PRE=$(git -C <dir> rev-parse HEAD)`.
2. Create the backup point (branch and tag, cheap and never lost):

   ```
   git -C <dir> branch backup/pre-upgrade-$(date +%Y%m%d%H%M%S) $PRE
   git -C <dir> tag update-watch/pre-$PRE $(git -C <dir> rev-parse $PRE^{commit})
   ```

3. Apply the update:
   - git source: `git -C <dir> fetch origin && git -C <dir> pull --ff-only origin <branch>`.
     `--ff-only` guarantees a plain fast-forward; if the local clone has
     diverged (local commits), STOP and report: do not merge, do not
     force-pull, ask the user.
   - non-git source with a remote archive: download the new version into a
     temp dir, then replace the source dir contents (rename old dir aside
     first, keep it as `<slug>.old-<timestamp>` until validation passes).
4. Validate the new state before declaring success:
   - `.zcode-plugin/plugin.json` parses as JSON and has `name` + `version`.
   - every skill listed has a `SKILL.md` with frontmatter `name` and
     `description`.
   - every referenced `commands/*.md` exists; every `scripts/*.py` compiles
     (`python3 -m py_compile`).
5. Any validation failure: roll back immediately (step 4 of the ROLLBACK
   section) and report which check failed and what the diff showed.

### 4. ROLLBACK

On demand, or automatically after a failed upgrade:

```
git -C <dir> checkout -q <PRE-ref-or-backup-tag>
```

- Use the backup tag created in step 2 (`update-watch/pre-*`), or for
  non-git sources move the `<slug>.old-<timestamp>` dir back over the
  current one.
- `git reset --hard` is FORBIDDEN in this workflow: it destroys refs you
  cannot name. Checkout of a named pre-upgrade ref is the only sanctioned
  restore. (If a user explicitly asks for a hard reset on their own repo,
  that is their call and outside this skill.)
- After rollback, re-run `update_check.py` and confirm the version matches
  the pre-upgrade one.

## Invariants

- Never `git push`, never force-push, never `git pull --force`, never
  `git reset` on the user's work.
- Every upgrade first creates a named backup ref; an upgrade without a
  backup ref does not happen.
- The agent reports the validation results honestly: a plugin whose
  manifest validation is skipped (no skills, no commands) gets said to be
  "version bump only", not "verified working".

## Script

`scripts/update_check.py` (Python 3 stdlib): for each git repo under the
given roots, report current commit vs origin, new commit count, and version
delta. Exit codes: 0 = no updates, 10 = at least one update available,
2 = no roots found / bad arguments.

```
python3 scripts/update_check.py ~/.zcode/workspace/default/plugins
python3 scripts/update_check.py <root1> <root2> --json
```
