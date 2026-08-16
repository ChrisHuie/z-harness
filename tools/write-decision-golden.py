#!/usr/bin/env python3
"""Regenerate contracts/goldens/guard-decisions.json from the guards as they stand.

The goldens this repository already had pin source bytes and ratchet check counts.
Neither notices a DECISION reversal: 43 fixture expectations were rewritten on one branch
while every suite stayed green, because the fixture and the code it grades move together.
This file is the third thing -- one line per command, so a verdict that changes shows up
as `command: deny -> ask` in a diff instead of inside a relabelled fixture.

Run this deliberately, then review the diff. `tools/ci-gate.py` verifies it on every run.
"""
from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "contracts/goldens/guard-decisions.json"
SOURCES = (
    "hooks/guards/git_grep_engine_guard.py",
    "hooks/guards/zsh_rev_modifier_guard.py",
    "hooks/bash_command_guard.py",
)
# Commands longer than this are parser-limit constructions -- a megabyte of `x`, 65,537
# tokens -- whose bytes carry no review value. They stay in the suites; the count of what
# was left out is recorded here so the corpus never silently shrinks.
MAX_GOLDEN_COMMAND_CHARS = 2000
BASE = "654be2a25b90eb7f8e194722c2a908cf97588c2c"


def branch_fixture_commands():
    """Every command any commit on this branch ever fixtured, in first-seen order."""
    revisions = subprocess.run(
        ["git", "-C", str(ROOT), "rev-list", f"{BASE}..HEAD"],
        capture_output=True, text=True, check=True).stdout.split() + [BASE]
    seen, commands, oversized = set(), [], 0
    computed = set()
    for revision in revisions:
        for path in SOURCES:
            blob = subprocess.run(["git", "-C", str(ROOT), "show", f"{revision}:{path}"],
                                  capture_output=True, text=True)
            if blob.returncode:
                continue
            try:
                tree = ast.parse(blob.stdout)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Tuple) or len(node.elts) != 3:
                    continue
                try:
                    values = [ast.literal_eval(element) for element in node.elts]
                except Exception:
                    # A fixture whose command is built at import time -- the megabyte
                    # byte-cap source, the token and subcommand overflow sources -- is a
                    # name here, not a literal. Those stay in the suites; count them so
                    # the corpus cannot shrink without saying so.
                    if (len(node.elts) == 3
                            and isinstance(node.elts[0], ast.Constant)
                            and isinstance(node.elts[0].value, str)
                            and isinstance(node.elts[1], ast.Name)):
                        computed.add(node.elts[0].value)
                    continue
                label, command, expected = values
                if not (isinstance(label, str) and isinstance(command, str)):
                    continue
                if expected not in ("allow", "deny", "ask", None) or len(command) <= 2:
                    continue
                if command in seen:
                    continue
                seen.add(command)
                if len(command) > MAX_GOLDEN_COMMAND_CHARS:
                    oversized += 1
                    continue
                commands.append(command)
    return commands, oversized, len(computed)


def live_fixture_commands():
    """Every command the guards fixture RIGHT NOW, read from the imported modules.

    The AST sweep below sees literals only, so an f-string fixture -- the whole
    `_UNTRUSTED_GIT` group -- was invisible to it and the golden did not cover the
    alternate-Git verdicts at all. Importing resolves those.
    """
    import git_grep_engine_guard
    import zsh_rev_modifier_guard
    commands, oversized = [], 0
    for module in (git_grep_engine_guard, zsh_rev_modifier_guard):
        for _label, command, _expected in getattr(module, "FIXTURES", ()):
            if not isinstance(command, str) or len(command) <= 2:
                continue
            if len(command) > MAX_GOLDEN_COMMAND_CHARS:
                oversized += 1
                continue
            commands.append(command)
    return commands, oversized


def main() -> int:
    sys.path.insert(0, str(ROOT / "hooks"))
    sys.path.insert(0, str(ROOT / "hooks" / "guards"))
    import bash_command_guard  # noqa: E402

    commands, oversized, computed = branch_fixture_commands()
    live, live_oversized = live_fixture_commands()
    oversized += live_oversized
    seen = set(commands)
    for command in live:
        if command not in seen:
            seen.add(command)
            commands.append(command)
    if not commands:
        print("no fixture commands found; refusing to write an empty golden",
              file=sys.stderr)
        return 2
    decisions = {command: bash_command_guard.decide(command)[0]
                 for command in sorted(commands)}
    payload = {
        "note": __doc__.strip().splitlines()[2].strip(),
        "corpus": ("every command the guards fixture now, plus every command any\n"
                   "commit on this branch or its base ever fixtured as a literal"),
        "excluded_over_chars": MAX_GOLDEN_COMMAND_CHARS,
        "excluded_oversized": oversized,
        "excluded_computed_at_import": computed,
        "decisions": decisions,
    }
    GOLDEN.write_text(json.dumps(payload, indent=1, sort_keys=False) + "\n",
                      encoding="utf-8")
    counts = {value: sum(1 for d in decisions.values() if d == value)
              for value in ("allow", "ask", "deny")}
    print(f"wrote {GOLDEN.relative_to(ROOT)}: {len(decisions)} commands "
          f"({counts}); excluded {oversized} over {MAX_GOLDEN_COMMAND_CHARS} chars and "
          f"{computed} built at import time")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
