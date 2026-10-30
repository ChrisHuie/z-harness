#!/usr/bin/env python3
"""Report whether the installed swamp skills are this repository's, and install them.

Run exactly:

    python3 scripts/check_install.py              # report; exit 0 in sync, 1 drift, 2 usage
    python3 scripts/check_install.py --install    # replace the installed skills with this repository's

Three facts are reported, each with the evidence it rests on:

  1. CLI reference stamp: the swamp version in references/cli/index.md against `swamp --version`.
     A mismatch means `swamp update` ran; regenerate with scripts/render_cli_reference.py.
  2. Installed skill identity, for `swamp` and `swamp-getting-started` under ~/.claude/skills:
     this repository's copy (byte-identical), this repository's copy with drift, the upstream
     bundled skill (`swamp update`, `swamp repo init` and `swamp repo upgrade` write it back),
     or missing.
  3. When the upstream skill is installed: whether it differs from assets/upstream/MANIFEST.json,
     meaning Swamp Club changed the bundled guides; run scripts/sync_upstream.py --diff to list.

--install moves an upstream copy to ~/.claude/backups/swamp-skill-upstream-<cli version>/ (never
deleted) and copies this repository's skill directories into place. It writes nothing else.
"""
import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys

MANAGED = ("swamp", "swamp-getting-started")
UPSTREAM_MARKER = "github-pinned: bundled-with-swamp"
HOST_PATH = re.compile(r"(?<![A-Za-z0-9/])/(?:Users|home|Volumes)/[^/\s]+/")


def cli_version():
    try:
        out = subprocess.run(["swamp", "--version"], capture_output=True, text=True)
    except OSError:
        return None
    m = re.search(r"\d{8}\.\d{6}\.\d+\S*", out.stdout + out.stderr)
    return m.group(0) if m else None


def stamp_version(index_md):
    if not os.path.isfile(index_md):
        return None
    m = re.search(r"swamp help --json`, swamp (\S+)\. Do not edit", open(index_md, encoding="utf-8").read())
    return m.group(1) if m else None


def tree_digests(root, sanitize=False):
    out = {}
    for dirpath, dirs, names in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        for name in sorted(names):
            full = os.path.join(dirpath, name)
            if os.path.islink(full) or not os.path.isfile(full):
                continue
            data = open(full, "rb").read()
            if sanitize:
                try:
                    data = HOST_PATH.sub("$HOME/", data.decode("utf-8")).encode("utf-8")
                except UnicodeDecodeError:
                    pass
            out[os.path.relpath(full, root).replace(os.sep, "/")] = hashlib.sha256(data).hexdigest()
    return out


def identity(installed, repo_copy):
    if not os.path.isdir(installed):
        return "missing", {}
    skill_md = os.path.join(installed, "SKILL.md")
    text = open(skill_md, encoding="utf-8").read() if os.path.isfile(skill_md) else ""
    if UPSTREAM_MARKER in text:
        return "upstream", {}
    ours, theirs = tree_digests(repo_copy), tree_digests(installed)
    if ours == theirs:
        return "ours", {}
    diff = {"missing": sorted(set(ours) - set(theirs)), "extra": sorted(set(theirs) - set(ours)),
            "changed": sorted(k for k in set(ours) & set(theirs) if ours[k] != theirs[k])}
    return "ours-drifted", diff


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--install", action="store_true")
    ap.add_argument("--skills-dir", default=os.path.expanduser("~/.claude/skills"))
    ns = ap.parse_args()
    here = os.path.dirname(os.path.abspath(__file__))
    repo_skills = os.path.normpath(os.path.join(here, "..", ".."))
    skills_dir = os.path.normpath(os.path.expanduser(ns.skills_dir))
    problems = []

    cli = cli_version()
    stamp = stamp_version(os.path.join(repo_skills, "swamp", "references", "cli", "index.md"))
    print("swamp CLI: " + str(cli) + "; CLI reference stamp: " + str(stamp))
    if cli is None:
        problems.append("swamp binary not found on PATH")
    elif stamp != cli:
        problems.append("CLI reference stale: run python3 scripts/render_cli_reference.py")

    states = {}
    for name in MANAGED:
        installed = os.path.join(skills_dir, name)
        state, diff = identity(installed, os.path.join(repo_skills, name))
        states[name] = state
        line = name + ": " + state
        if state == "ours-drifted":
            line += " " + str({k: v[:5] for k, v in diff.items() if v})
        print(line)
        if state != "ours":
            problems.append(name + " installed copy is " + state)

    if states.get("swamp") == "upstream":
        import json
        manifest_path = os.path.join(repo_skills, "swamp", "assets", "upstream", "MANIFEST.json")
        if os.path.isfile(manifest_path):
            stored = json.load(open(manifest_path)).get("files", {})
            live = tree_digests(os.path.join(skills_dir, "swamp"), sanitize=True)
            changed = sorted(k for k in set(stored) & set(live) if stored[k]["sha256"] != live[k])
            added = sorted(set(live) - set(stored))
            removed = sorted(set(stored) - set(live))
            print("upstream vs snapshot: " + str(len(changed)) + " changed, " + str(len(added))
                  + " added, " + str(len(removed)) + " removed (python3 scripts/sync_upstream.py --diff for names)")
            if changed or added or removed:
                problems.append("upstream bundled skill changed since the snapshot; review before --install")

    if ns.install:
        backups = os.path.join(os.path.dirname(skills_dir), "backups")
        for name in MANAGED:
            installed = os.path.join(skills_dir, name)
            if states[name] == "upstream":
                os.makedirs(backups, exist_ok=True)
                target = os.path.join(backups, "swamp-skill-upstream-" + str(cli), name)
                if os.path.exists(target):
                    shutil.rmtree(target)
                os.makedirs(os.path.dirname(target), exist_ok=True)
                shutil.move(installed, target)
                print("moved upstream " + name + " to " + target)
            elif os.path.isdir(installed):
                shutil.rmtree(installed)
            shutil.copytree(os.path.join(repo_skills, name), installed, symlinks=False)
            print("installed " + name + " from " + repo_skills)
        recheck = all(identity(os.path.join(skills_dir, n), os.path.join(repo_skills, n))[0] == "ours" for n in MANAGED)
        print("post-install identity: " + ("ours for all managed skills" if recheck else "MISMATCH"))
        return 0 if recheck and (stamp == cli) else 1

    for p in problems:
        print("DRIFT: " + p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
