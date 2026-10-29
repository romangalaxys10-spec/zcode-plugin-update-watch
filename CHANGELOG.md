# Changelog

## 0.1.1 - 2026-10-30

- Fix: NoneType guard in the text report path when a repo has no commit info.

## 0.1.0 - 2026-10-29

- Initial release: AUDIT via `update_check.py` (per-repo commit vs origin,
  new commit count, manifest version delta, exit 10 on updates), DIFF step
  that shows files touched and changelog entries before applying, UPGRADE
  under a pre-created backup ref with manifest validation, and ROLLBACK via
  checkout of the pre-upgrade ref. Never pushes, never force-pulls,
  never uses `git reset`.
