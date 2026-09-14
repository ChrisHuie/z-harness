#!/usr/bin/env python3
"""Build the exact guard-decision corpus and deliberately update reviewed verdicts.

The golden is a review snapshot, not an oracle generated silently from production. A
normal run refuses every corpus, metadata, or verdict change. Pass
``--accept-decision-changes`` only after reviewing the reported differences.
``tools/ci-gate.py`` independently requires the exact schema, metadata, corpus, and live
guard verdicts on every run.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "contracts/goldens/guard-decisions.json"
RETAINED = ROOT / "contracts/goldens/retained-guard-commands.json"
SOURCES = (
    "hooks/guards/git_grep_engine_guard.py",
    "hooks/guards/zsh_rev_modifier_guard.py",
    "hooks/bash_command_guard.py",
)
SCHEMA_VERSION = 1
GENERATED_BY = "tools/write-decision-golden.py --accept-decision-changes"
NOTE = "reviewed guard decisions over the generator's exact fixture corpus"
CORPUS_DESCRIPTION = (
    "every eligible literal command in the fixed base and current working tree, plus "
    "every eligible imported fixture and explicitly retained historical command"
)
MAX_GOLDEN_COMMAND_CHARS = 2000
BASE = "654be2a25b90eb7f8e194722c2a908cf97588c2c"
OUTCOMES = {"allow", "ask", "deny"}
TOP_LEVEL_KEYS = (
    "schema_version", "generated_by", "note", "corpus", "exclusions", "decisions",
)
EXCLUSION_KEYS = ("max_command_chars", "oversized", "computed_at_import")
RETAINED_KEYS = ("schema_version", "note", "commands")
RETAINED_SCHEMA_VERSION = 1
RETAINED_NOTE = (
    "reviewed decision commands retained after their originating fixtures left the "
    "current source; append-only unless a deliberate retirement changes the independent "
    "gate contract"
)


def _load_json_strict(path: Path):
    def unique_object(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f"duplicate JSON object key {key!r}")
            value[key] = item
        return value

    return json.loads(
        path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)


def _record_literal_fixtures(source: str, commands: set[str], oversized: dict[str, dict],
                             computed: set[str]) -> None:
    """Collect fixture-shaped tuples from one source blob."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return
    for node in ast.walk(tree):
        if not isinstance(node, ast.Tuple) or len(node.elts) != 3:
            continue
        try:
            label, command, expected = [ast.literal_eval(element) for element in node.elts]
        except Exception:
            if (isinstance(node.elts[0], ast.Constant)
                    and isinstance(node.elts[0].value, str)
                    and isinstance(node.elts[1], (ast.Name, ast.BinOp, ast.JoinedStr))):
                computed.add(node.elts[0].value)
            continue
        if not (isinstance(label, str) and isinstance(command, str)
                and (expected is None
                     or (isinstance(expected, str) and expected in OUTCOMES))
                and len(command) > 2):
            continue
        if len(command) > MAX_GOLDEN_COMMAND_CHARS:
            digest = hashlib.sha256(command.encode()).hexdigest()
            oversized[digest] = {"sha256": digest, "length": len(command)}
        else:
            commands.add(command)


def base_and_worktree_fixture_commands() -> tuple[set[str], dict[str, dict], set[str]]:
    """Collect literal fixtures without depending on the feature branch topology."""
    commands: set[str] = set()
    oversized: dict[str, dict] = {}
    computed: set[str] = set()
    for path in SOURCES:
        blob = subprocess.run(
            ["git", "-C", str(ROOT), "show", f"{BASE}:{path}"],
            capture_output=True, text=True)
        if blob.returncode == 0:
            _record_literal_fixtures(blob.stdout, commands, oversized, computed)
    for path in SOURCES:
        source = ROOT / path
        if source.is_file():
            _record_literal_fixtures(
                source.read_text(encoding="utf-8"), commands, oversized, computed)
    return commands, oversized, computed


def retained_commands() -> tuple[str, ...]:
    """Load the closed, topology-independent historical command manifest."""
    data = _load_json_strict(RETAINED)
    if not isinstance(data, dict) or tuple(data) != RETAINED_KEYS:
        raise ValueError("retained command manifest has an unexpected schema")
    if data.get("schema_version") != RETAINED_SCHEMA_VERSION:
        raise ValueError("retained command manifest schema version differs")
    if data.get("note") != RETAINED_NOTE:
        raise ValueError("retained command manifest note differs")
    commands = data.get("commands")
    if (not isinstance(commands, list) or not commands
            or any(not isinstance(command, str) or len(command) <= 2
                   or len(command) > MAX_GOLDEN_COMMAND_CHARS
                   for command in commands)
            or len(commands) != len(set(commands))):
        raise ValueError("retained command manifest is empty, duplicated, or invalid")
    return tuple(commands)


def imported_fixture_commands() -> tuple[set[str], dict[str, dict], dict[str, set[str]]]:
    """Resolve computed Git/zsh fixture commands and detect conflicting expectations."""
    for path in (ROOT / "hooks", ROOT / "hooks" / "guards"):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    import git_grep_engine_guard
    import zsh_rev_modifier_guard
    import bash_command_guard

    commands: set[str] = set()
    oversized: dict[str, dict] = {}
    expected: dict[str, set[str]] = {}
    registries = (
        git_grep_engine_guard.FIXTURES,
        zsh_rev_modifier_guard.FIXTURES,
        bash_command_guard.DECISION_FIXTURES,
    )
    for fixtures in registries:
        for _label, command, outcome in fixtures:
            if not isinstance(command, str) or len(command) <= 2:
                continue
            if len(command) > MAX_GOLDEN_COMMAND_CHARS:
                digest = hashlib.sha256(command.encode()).hexdigest()
                oversized[digest] = {"sha256": digest, "length": len(command)}
                continue
            commands.add(command)
            if outcome in OUTCOMES:
                expected.setdefault(command, set()).add(outcome)
    conflicts = {command: outcomes for command, outcomes in expected.items()
                 if len(outcomes) != 1}
    return commands, oversized, conflicts


def corpus_snapshot() -> dict:
    """Return the exact corpus and exclusion metadata consumed by writer and gate."""
    commands, oversized, computed = base_and_worktree_fixture_commands()
    imported, imported_oversized, conflicts = imported_fixture_commands()
    if conflicts:
        shown = "; ".join(
            f"{command[:60]!r}: {sorted(outcomes)}"
            for command, outcomes in sorted(conflicts.items())[:6])
        raise ValueError(f"live fixtures disagree on expected decisions ({shown})")
    commands.update(imported)
    commands.update(retained_commands())
    oversized.update(imported_oversized)
    if not commands:
        raise ValueError("no fixture commands found; an empty corpus is not valid")
    return {
        "commands": tuple(sorted(commands)),
        "exclusions": {
            "max_command_chars": MAX_GOLDEN_COMMAND_CHARS,
            "oversized": [oversized[digest] for digest in sorted(oversized)],
            "computed_at_import": sorted(computed),
        },
    }


def payload_for(snapshot: dict, decisions: dict[str, str]) -> dict:
    """Build a payload after its decision map has passed deliberate-update policy."""
    commands = snapshot["commands"]
    if set(decisions) != set(commands):
        raise ValueError("decision keys do not exactly equal the generated corpus")
    invalid = sorted((command, outcome) for command, outcome in decisions.items()
                     if outcome not in OUTCOMES)
    if invalid:
        raise ValueError(f"invalid decisions: {invalid[:4]}")
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": GENERATED_BY,
        "note": NOTE,
        "corpus": CORPUS_DESCRIPTION,
        "exclusions": snapshot["exclusions"],
        "decisions": {command: decisions[command] for command in commands},
    }


def _change_summary(recorded: dict, payload: dict) -> list[str]:
    """Describe every review-relevant payload change without trusting old schema."""
    if not isinstance(recorded, dict) or not recorded:
        return ["no valid recorded payload exists"]
    changes: list[str] = []
    before = recorded.get("decisions") if isinstance(recorded, dict) else None
    before = before if isinstance(before, dict) else {}
    after = payload["decisions"]
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    reversed_decisions = sorted(
        (command, before[command], after[command])
        for command in set(before) & set(after)
        if before[command] != after[command]
    )
    if added:
        changes.append(f"{len(added)} added corpus command(s): {added[:4]}")
    if removed:
        changes.append(f"{len(removed)} removed corpus command(s): {removed[:4]}")
    if reversed_decisions:
        changes.append(
            f"{len(reversed_decisions)} reversed decision(s): "
            f"{reversed_decisions[:4]}")
    for field in TOP_LEVEL_KEYS:
        if field != "decisions" and recorded.get(field) != payload[field]:
            changes.append(f"metadata field {field!r} changed")
    extra = sorted(set(recorded) - set(TOP_LEVEL_KEYS))
    if extra:
        changes.append(f"removed unexpected top-level field(s): {extra}")
    return changes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--accept-decision-changes", action="store_true")
    args = parser.parse_args(argv)
    for path in (ROOT / "hooks", ROOT / "hooks" / "guards"):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    import bash_command_guard

    try:
        snapshot = corpus_snapshot()
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        print(f"cannot build decision corpus: {exc}", file=sys.stderr)
        return 2
    observed = {command: bash_command_guard.decide(command)[0]
                for command in snapshot["commands"]}
    recorded = {}
    if GOLDEN.is_file():
        try:
            parsed = _load_json_strict(GOLDEN)
            if isinstance(parsed, dict) and isinstance(parsed.get("decisions"), dict):
                recorded = parsed["decisions"]
        except (OSError, ValueError):
            recorded = {}
    payload = payload_for(snapshot, observed)
    changes = _change_summary(parsed if 'parsed' in locals() else {}, payload)
    if changes and not args.accept_decision_changes:
        for change in changes[:20]:
            print(f"REFUSED {change}", file=sys.stderr)
        print(
            "refusing to rewrite the recorded golden; review every reported corpus, "
            "decision, and metadata change, then "
            "rerun with --accept-decision-changes",
            file=sys.stderr)
        return 2
    GOLDEN.write_text(json.dumps(payload, indent=1, sort_keys=False) + "\n",
                      encoding="utf-8")
    counts = {value: sum(1 for outcome in observed.values() if outcome == value)
              for value in sorted(OUTCOMES)}
    exclusions = snapshot["exclusions"]
    print(
        f"wrote {GOLDEN.relative_to(ROOT)}: {len(observed)} commands ({counts}); "
        f"excluded {len(exclusions['oversized'])} oversized command(s) and "
        f"{len(exclusions['computed_at_import'])} computed fixture(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
