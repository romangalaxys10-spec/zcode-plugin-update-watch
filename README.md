# Plugin Update Watch

Update your ZCode plugins without breaking the ones that work: diff first,
upgrade under a backup ref, roll back with one named checkout.

## Why

Plugin updates can change skill instructions, add hooks, or break a manifest.
A blind `git pull` across a dozen local plugins is how agents get stuck on a
broken version with no record of what they were running before. This plugin
makes the upgrade transactional: audit, diff, upgrade under a backup ref,
validate, and roll back if anything fails.

## How it works

1. AUDIT: `scripts/update_check.py` walks the plugin roots, fetches upstream
   for every git clone, and reports current vs origin commit, new commit
   count, and version delta. Exit 10 when updates exist.
2. DIFF: commit range, files touched, manifest version bump, and changelog
   entries are shown before anything is applied.
3. UPGRADE: a backup branch and tag are created at the current ref first,
   then a `--ff-only` pull (or archive re-download into a temp dir). Manifest
   validation runs after; any failure triggers the rollback.
4. ROLLBACK: checkout the pre-upgrade ref. `git reset` is never used, the
   script never pushes, and no force-pull happens anywhere.

| Step | Safe by construction |
|---|---|
| Audit | fetch-only; read-only view of deltas |
| Upgrade | backup ref before the pull; ff-only |
| Rollback | checkout of a named ref, not a reset |

## Install

**Option A: self-installable marketplace** (recommended)

1. Download or clone this repo anywhere.
2. In ZCode: Plugin Marketplace -> Add -> Add Plugin Marketplace.
3. Paste the folder path.
4. Install `plugin-update-watch`.

**Option B: manual copy**

Copy this directory into your workspace `plugins/` folder
(Example: `~/.zcode/workspace/default/plugins/plugin-update-watch/`) and
restart ZCode.

## Try it

```
/plugin-update-watch ~/.zcode/workspace/default/plugins
```

Expected result: one line per installed plugin (commit, new count, version
delta), and the exit-10 marker when at least one plugin is behind origin.

## Requirements

- Python 3 (stdlib only).
- `git` on PATH for the audit and upgrade steps.
- Plugin dirs that are git clones with an `origin` remote; local copies
  without a `.git` are listed as `local (no remote)` and cannot be diffed
  against an upstream.

---

<p align="center">
  <a href="https://z.ai/subscribe?ic=R0K78RJKNW"><img alt="z.ai coding plans - 10% OFF coupon" src="https://img.shields.io/badge/z.ai%20coding%20plans-10%25%20OFF%20coupon-blueviolet" /></a>
  <a href="https://zcode.z.ai/invite/ALWM9JUA"><img alt="Try ZCode free" src="https://img.shields.io/badge/Try%20ZCode-free%20invite-0969da" /></a>
</p>

## License

MIT
