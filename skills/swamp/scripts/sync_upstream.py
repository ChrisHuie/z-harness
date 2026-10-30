#!/usr/bin/env python3
"""Vendor the Swamp Club bundled `swamp` skill into assets/upstream/ with host paths neutralised.

Run exactly:

    python3 scripts/sync_upstream.py            # capture from ~/.claude/skills/swamp into assets/upstream/
    python3 scripts/sync_upstream.py --diff     # exit 1 when the installed upstream differs from the snapshot
    python3 scripts/sync_upstream.py --source <dir>

The source must be the upstream skill (its SKILL.md carries `github-pinned: bundled-with-swamp`);
this skill's own installed copy is refused so a snapshot cannot be taken of itself. Every file is
copied byte for byte except for one rewrite: an absolute home directory path (a Users, home or
Volumes prefix followed by an account name) becomes $HOME/, because the repository's package
check refuses host paths.
assets/upstream/MANIFEST.json records the swamp CLI version at capture, the rewrite rule, and the
sha256 of every stored file, so a later --diff can tell a CLI update's changes from local edits.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

UPSTREAM_MARKER = "github-pinned: bundled-with-swamp"
HOST_PATH = re.compile(r"(?<![A-Za-z0-9/])/(?:Users|home|Volumes)/[^/\s]+/")
HOST_PATH_REPLACEMENT = "$HOME/"
MANIFEST = "MANIFEST.json"


def swamp_version():
    out = subprocess.run(["swamp", "--version"], capture_output=True, text=True)
    m = re.search(r"\d{8}\.\d{6}\.\d+\S*", out.stdout + out.stderr)
    return m.group(0) if m else "unknown"


def capture(source):
    files = {}
    for dirpath, dirs, names in os.walk(source):
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d != "__pycache__")
        for name in sorted(names):
            full = os.path.join(dirpath, name)
            if os.path.islink(full) or not os.path.isfile(full):
                continue
            rel = os.path.relpath(full, source).replace(os.sep, "/")
            data = open(full, "rb").read()
            rewrites = 0
            try:
                text = data.decode("utf-8")
                text, rewrites = HOST_PATH.subn(HOST_PATH_REPLACEMENT, text)
                data = text.encode("utf-8")
            except UnicodeDecodeError:
                pass
            files[rel] = (data, rewrites)
    return files


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", default=os.path.expanduser("~/.claude/skills/swamp"))
    ap.add_argument("--diff", action="store_true")
    ns = ap.parse_args()
    here = os.path.dirname(os.path.abspath(__file__))
    dest = os.path.normpath(os.path.join(here, "..", "assets", "upstream"))
    source = os.path.normpath(os.path.expanduser(ns.source))
    skill_md = os.path.join(source, "SKILL.md")
    if not os.path.isfile(skill_md):
        sys.exit("no SKILL.md under " + source + "; nothing to capture (exit 2)") or 2
    if UPSTREAM_MARKER not in open(skill_md, encoding="utf-8").read():
        print("refused: " + skill_md + " is not the upstream bundled skill (marker absent)")
        return 2
    files = capture(source)
    manifest = {
        "source": "~/.claude/skills/swamp" if source == os.path.expanduser("~/.claude/skills/swamp") else "(custom --source)",
        "swampVersion": swamp_version(),
        "rewrite": {"pattern": HOST_PATH.pattern, "replacement": HOST_PATH_REPLACEMENT},
        "files": {rel: {"sha256": hashlib.sha256(d).hexdigest(), "bytes": len(d), "rewrites": n}
                  for rel, (d, n) in sorted(files.items())},
    }
    if ns.diff:
        stored_path = os.path.join(dest, MANIFEST)
        stored = json.load(open(stored_path)) if os.path.isfile(stored_path) else {"files": {}}
        old, new = stored.get("files", {}), manifest["files"]
        added = sorted(set(new) - set(old))
        removed = sorted(set(old) - set(new))
        changed = sorted(k for k in set(old) & set(new) if old[k]["sha256"] != new[k]["sha256"])
        print("snapshot swamp " + str(stored.get("swampVersion")) + " vs installed upstream, CLI swamp " + manifest["swampVersion"])
        for label, items in (("added", added), ("removed", removed), ("changed", changed)):
            print("  " + label + " (" + str(len(items)) + "): " + ", ".join(items[:40]) + (" ..." if len(items) > 40 else ""))
        return 1 if (added or removed or changed) else 0
    if os.path.isdir(dest):
        shutil.rmtree(dest)
    for rel, (data, _) in files.items():
        target = os.path.join(dest, rel)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "wb") as fh:
            fh.write(data)
    with open(os.path.join(dest, MANIFEST), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)
        fh.write("\n")
    rewritten = sum(1 for v in manifest["files"].values() if v["rewrites"])
    print("captured " + str(len(files)) + " files from " + source + " into " + dest
          + " (" + str(rewritten) + " files had host paths rewritten) at swamp " + manifest["swampVersion"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
