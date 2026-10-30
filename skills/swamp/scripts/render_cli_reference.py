#!/usr/bin/env python3
"""Render references/cli/*.md from the installed swamp CLI's own help schema.

Run exactly:

    python3 scripts/render_cli_reference.py            # write references/cli/
    python3 scripts/render_cli_reference.py --check    # exit 1 when the files on disk are stale

Source of truth is `swamp help --json` (the CLI's canonical schema), plus `swamp help <name>
--json` for each hidden root command named in HIDDEN_ROOTS, which the top-level schema omits.
One Markdown file per command group, plus index.md carrying the schema version, the global
flags, the exit codes and the collapsed common flags. Output is deterministic for a given
schema, so a diff between runs is a CLI change, never noise.
"""
import argparse
import collections
import json
import os
import re
import subprocess
import sys

HIDDEN_ROOTS = ["audit"]
LEGACY_ROOTS = {"model": "behavior"}          # mirrored legacy spellings, summarised not expanded
GROUPS = {
    "access": ["access"],
    "setup": ["auth", "version", "init", "repo", "start", "workspace", "dashboard", "update",
              "config", "completions", "inbox", "quest", "invite", "subscription", "telemetry",
              "source", "issue"],
    "behavior": ["behavior"],
    "data": ["data"],
    "workflow": ["workflow"],
    "vault": ["vault"],
    "report": ["report"],
    "extension": ["extension"],
    "datastore": ["datastore"],
    "serve": ["serve"],
    "worker": ["worker"],
    "operations": ["run", "doctor", "audit", "summarise"],
    "agent": ["agent"],
}
COMMON_FLAG_FLOOR = 8          # a (flags, description) pair on >= this many commands is collapsed


def swamp_help_json(*path):
    cmd = ["swamp", "help", *path, "--json"]
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        sys.exit(f"{' '.join(cmd)} failed (exit {out.returncode}): {out.stderr.strip()[:300]}")
    return json.loads(out.stdout)


def walk(node, path, sink):
    sink.append((path, node))
    for sub in node.get("subcommands", []):
        walk(sub, path + [sub["name"]], sink)


def esc(text):
    return text.replace("|", "\\|").replace("\n", " ").strip()


def render_description(desc):
    desc = (desc or "").strip()
    if not desc:
        return ""
    if "\n" in desc:
        return "```text\n" + desc + "\n```\n"
    return desc + "\n"


def render_command(path, node, common, hidden):
    full = " ".join(path)
    alias = node.get("aliases") or []
    head = "## " + full
    if alias:
        head += " (alias: " + ", ".join(alias) + ")"
    lines = [head, ""]
    if hidden:
        lines.append("Hidden: omitted from `swamp help`; shown by `swamp help " + " ".join(path[1:]) + "`.")
        lines.append("")
    lines.append(render_description(node.get("description")))
    args = node.get("arguments") or []
    if args:
        parts = []
        for a in args:
            label = a["name"] + ("" if a.get("required") else "?")
            if a.get("description"):
                label += " (" + esc(a["description"]) + ")"
            parts.append(label)
        lines.append("Arguments: " + ", ".join(parts) + "  (`?` marks optional)")
        lines.append("")
    rows, collapsed = [], []
    for o in node.get("options") or []:
        key = (o.get("flags"), (o.get("description") or "").strip())
        if key in common:
            collapsed.append(o.get("flags"))
            continue
        value = o.get("value") or ""
        default = o.get("default")
        desc = esc(key[1])
        if default not in (None, "", False):      # a boolean flag's False default carries no information
            desc += " Default: " + esc(str(default)) + "."
        rows.append("| `" + o.get("flags", "") + "` | " + esc(value) + " | " + desc + " |")
    if rows:
        lines += ["| Flag | Value | Description |", "|---|---|---|", *rows, ""]
    if collapsed:
        lines.append("Common flags (see index.md): " + ", ".join("`" + c + "`" for c in collapsed))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "references", "cli"))
    ap.add_argument("--check", action="store_true", help="compare with the files on disk; exit 1 on drift")
    ns = ap.parse_args()
    out_dir = os.path.normpath(ns.out)

    schema = swamp_help_json()
    version = schema["version"]
    root = schema["root"]
    commands = []
    for sub in root.get("subcommands", []):
        walk(sub, ["swamp", sub["name"]], commands)
    hidden_paths = set()
    for name in HIDDEN_ROOTS:
        h = swamp_help_json(name)
        if h.get("version") != version:
            sys.exit(f"schema version mismatch: root {version} vs hidden {name} {h.get('version')}")
        node = h["root"]
        before = len(commands)
        walk(node, ["swamp", name], commands)
        hidden_paths.update(" ".join(p) for p, _ in commands[before:])

    counts = collections.Counter()
    for _, node in commands:
        for o in node.get("options") or []:
            counts[(o.get("flags"), (o.get("description") or "").strip())] += 1
    common = {k for k, n in counts.items() if n >= COMMON_FLAG_FLOOR}

    by_group = collections.defaultdict(list)
    root_to_group = {r: g for g, roots in GROUPS.items() for r in roots}
    legacy = collections.Counter()
    for path, node in commands:
        r = path[1]
        if r in LEGACY_ROOTS:
            legacy[r] += 1
            continue
        by_group[root_to_group.get(r, "other")].append((path, node))

    files = {}
    stamp = ("Generated from `swamp help --json`, swamp " + version + ". Do not edit by hand; "
             "regenerate with `python3 scripts/render_cli_reference.py`.\n\n")
    for group, items in sorted(by_group.items()):
        body = ["# swamp CLI: " + group + "\n", stamp,
                "Root commands in this group: " + ", ".join(sorted({p[1] for p, _ in items})) + ".\n\n"]
        for path, node in items:                       # schema order within each root
            body.append(render_command(path, node, common, " ".join(path) in hidden_paths))
        files[group + ".md"] = "".join(body).rstrip() + "\n"

    idx = ["# swamp CLI: index\n", stamp]
    idx.append("Totals: " + str(len(commands)) + " commands (" + str(len(hidden_paths)) + " hidden), "
               + str(sum(counts.values())) + " flag occurrences. The `swamp model` tree ("
               + str(legacy.get("model", 0)) + " commands) mirrors `swamp behavior` with the legacy "
               "spelling and is not expanded here.\n\n")
    idx.append("## Root help\n\n" + render_description(root.get("description")) + "\n")
    idx.append("## Global flags\n\n| Flag | Value | Description |\n|---|---|---|\n")
    for o in root.get("options") or []:
        idx.append("| `" + o.get("flags", "") + "` | " + esc(o.get("value") or "") + " | " + esc(o.get("description") or "") + " |\n")
    idx.append("\n## Common flags collapsed in the group files\n\n| Flag | On commands | Description |\n|---|---|---|\n")
    for (flags, desc), n in sorted(common and counts.items() or [], key=lambda kv: -kv[1]):
        if (flags, desc) in common:
            idx.append("| `" + flags + "` | " + str(n) + " | " + esc(desc) + " |\n")
    idx.append("\n## Groups\n\n| File | Root commands | Commands |\n|---|---|---|\n")
    for group, items in sorted(by_group.items()):
        idx.append("| " + group + ".md | " + ", ".join(sorted({p[1] for p, _ in items})) + " | " + str(len(items)) + " |\n")
    files["index.md"] = "".join(idx).rstrip() + "\n"

    if ns.check:
        stale = []
        for name, text in files.items():
            p = os.path.join(out_dir, name)
            if not os.path.isfile(p) or open(p, encoding="utf-8").read() != text:
                stale.append(name)
        extra = sorted(set(f for f in os.listdir(out_dir) if f.endswith(".md")) - set(files)) if os.path.isdir(out_dir) else []
        if stale or extra:
            print("stale CLI reference for swamp " + version + ": " + ", ".join(stale + ["extra:" + e for e in extra]))
            return 1
        print("CLI reference current for swamp " + version)
        return 0
    os.makedirs(out_dir, exist_ok=True)
    for name in os.listdir(out_dir):
        if name.endswith(".md") and name not in files:
            os.remove(os.path.join(out_dir, name))
    for name, text in files.items():
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as fh:
            fh.write(text)
    print("wrote " + str(len(files)) + " files to " + out_dir + " for swamp " + version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
