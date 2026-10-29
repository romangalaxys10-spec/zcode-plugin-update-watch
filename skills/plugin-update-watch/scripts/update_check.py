#!/usr/bin/env python3
"""update_check.py: report upstream deltas for installed ZCode plugins.

Stdlib only (os, subprocess, json, argparse, pathlib). For every git repo
under the given roots (a repo counts when its plugin dir contains
.zcode-plugin/plugin.json and a .git directory), this script:

  - records the current commit and branch,
  - fetches origin for that branch (fetch only: this script never pushes,
    never pulls, never force-pulls, never resets),
  - counts new commits on origin that HEAD does not have,
  - reads the version from .zcode-plugin/plugin.json (fallback
    marketplace.json) on both sides and reports the delta,
  - lists plugin dirs without a .git as "local (no remote)".

Exit codes:
  0  = scan completed, no updates available
  10 = scan completed, at least one update available
  2  = no valid roots / no plugin dirs found

Usage:
  python3 update_check.py <root> [more roots...]
  python3 update_check.py ~/plugins --json
  python3 update_check.py ~/plugins --no-fetch   # use last-fetched origin refs
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

MANIFEST = Path(".zcode-plugin") / "plugin.json"
MARKETPLACE = Path("marketplace.json")
PRUNE = {"node_modules", "dist", "build", "__pycache__", "venv", ".venv",
         ".tox", "out", "target", ".idea", ".vscode"}
MAX_SCAN_DEPTH = 8


def run_git(repo, *args, timeout=120):
    """Run a git command in repo; return (rc, combined output text)."""
    try:
        p = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "git command timed out"
    except FileNotFoundError:
        return 127, "git not found on PATH"


def read_local_version(plugin_dir: Path):
    """Version from the on-disk manifest: plugin.json, then marketplace.json."""
    for p in (plugin_dir / MANIFEST, plugin_dir / MARKETPLACE):
        if p.is_file():
            try:
                data = json.loads(p.read_text(encoding="utf-8", errors="replace"))
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict) and "version" in data:
                return str(data["version"]), p.name
    return None, None


def read_ref_version(plugin_dir: Path, ref: str):
    """Version of the manifest as it exists on a git ref (git show ref:path)."""
    for rel in (str(MANIFEST), str(MARKETPLACE)):
        rc, out = run_git(plugin_dir, "show", f"{ref}:{rel}")
        if rc != 0:
            continue
        try:
            data = json.loads(out)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and "version" in data:
            return str(data["version"]), rel
    return None, None


def find_plugin_dirs(root: Path):
    """Yield dirs under root that contain .zcode-plugin/plugin.json."""
    base_depth = len(root.parts)
    for dirpath, dirnames, _ in os.walk(root):
        p = Path(dirpath)
        rel_depth = len(p.parts) - base_depth
        if rel_depth >= MAX_SCAN_DEPTH:
            dirnames[:] = []
        else:
            dirnames[:] = [d for d in dirnames if d not in PRUNE
                           and not d.startswith(".")]
        if (p / MANIFEST).is_file():
            yield p


def check_repo(plugin_dir: Path, do_fetch: bool):
    """Build the report row for one plugin dir."""
    row = {
        "plugin": plugin_dir.name,
        "path": str(plugin_dir),
        "is_git": (plugin_dir / ".git").exists(),
    }
    version, source = read_local_version(plugin_dir)
    row["version"] = version
    row["version_source"] = source

    if not row["is_git"]:
        row["status"] = "local (no remote)"
        row["new_commits"] = None
        row["version_delta"] = None
        return row

    rc, out = run_git(plugin_dir, "rev-parse", "HEAD")
    if rc != 0:
        row["status"] = f"git error: {out.strip()[:120]}"
        row["new_commits"] = None
        row["version_delta"] = None
        return row
    row["commit"] = out.strip()[:12]

    rc, out = run_git(plugin_dir, "symbolic-ref", "--short", "HEAD")
    branch = out.strip() if rc == 0 else None
    row["branch"] = branch or "HEAD (detached)"

    if not do_fetch:
        row["status"] = "skipped fetch (--no-fetch; showing local refs only)"
        row["new_commits"] = None
        row["version_delta"] = None
        return row

    rc, out = run_git(plugin_dir, "remote")
    remotes = out.split()
    if "origin" not in remotes:
        row["status"] = "git, no origin remote"
        row["new_commits"] = None
        row["version_delta"] = None
        return row

    upstream = f"origin/{branch}" if branch else None
    if not branch or branch == "HEAD":
        rc2, out2 = run_git(plugin_dir, "symbolic-ref", "--short", "origin/HEAD")
        if rc2 == 0:
            upstream = out2.strip()
    if not upstream:
        row["status"] = "origin remote exists but default branch unknown"
        row["new_commits"] = 0
        row["version_delta"] = None
        return row

    rc, out = run_git(plugin_dir, "fetch", "--quiet", "origin")
    if rc != 0:
        row["status"] = f"fetch failed: {out.strip()[:120]}"
        row["new_commits"] = None
        row["version_delta"] = None
        return row

    rc, out = run_git(plugin_dir, "rev-list", "--count", f"HEAD..{upstream}")
    new_commits = int(out.strip()) if rc == 0 and out.strip().isdigit() else None
    if new_commits is None:
        row["status"] = f"cannot count new commits on {upstream}: {out.strip()[:100]}"
        row["new_commits"] = None
        row["version_delta"] = None
        return row

    remote_v, _ = read_ref_version(plugin_dir, upstream)
    if new_commits == 0:
        row["status"] = "up to date"
        row["version_delta"] = None
    else:
        delta = f"{version} -> {remote_v}" if remote_v else f"{new_commits} commits"
        if version == remote_v:
            delta = f"{version} (no version bump, {new_commits} commits)"
        row["status"] = f"update available ({new_commits} new commits)"
        row["version_delta"] = delta
    row["new_commits"] = new_commits
    row["upstream"] = upstream
    return row


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Check installed ZCode plugins for upstream git updates.")
    ap.add_argument("roots", nargs="+",
                   help="directories to scan for installed plugins")
    ap.add_argument("--json", action="store_true",
                    help="print machine-readable JSON instead of text")
    ap.add_argument("--no-fetch", action="store_true",
                    help="skip git fetch; count against last-fetched origin refs")
    args = ap.parse_args(argv)

    existing = [Path(r).expanduser() for r in args.roots]
    existing = [p for p in existing if p.exists()]
    if not existing:
        print("error: none of the given roots exist", file=sys.stderr)
        return 2

    rows = []
    for root in existing:
        for plugin_dir in find_plugin_dirs(root):
            rows.append(check_repo(plugin_dir, do_fetch=not args.no_fetch))
    rows.sort(key=lambda r: r["plugin"].lower())

    if not rows:
        print("error: no plugin directories found under "
              f"{', '.join(str(r) for r in existing)}", file=sys.stderr)
        return 2

    updates = [r for r in rows if r.get("new_commits") and r["new_commits"] > 0]

    if args.json:
        print(json.dumps({"rows": rows, "updates_available": len(updates)},
                         indent=2))
    else:
        for r in rows:
            extra = ""
            if r.get("commit"):
                extra = f" @ {r['commit']} ({r.get('branch', 'HEAD')})"
            if r["is_git"] and r.get("new_commits", 0) > 0:
                extra += f"  +{r['new_commits']} new on {r.get('upstream', 'origin')}"
                if r.get("version_delta"):
                    extra += f"  [{r['version_delta']}]"
            elif not r["is_git"] or r.get("new_commits") is None:
                extra += f"  ({r.get('status', 'unknown')})"
            print(f"{r['plugin']}{extra}")
        print()
        print(f"{len(rows)} plugins scanned, {len(updates)} with updates.")
        if updates:
            print("exit 10: updates available. Run the DIFF step of the "
                  "plugin-update-watch skill before upgrading.")

    return 10 if updates else 0


if __name__ == "__main__":
    sys.exit(main())
