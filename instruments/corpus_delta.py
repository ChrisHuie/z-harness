#!/usr/bin/env python3
"""corpus_delta — price a Bash-guard change on the real command corpus.

Every other instrument in this package asks whether a hazard gets through. This one asks
the other question: what does a guard change do to ordinary commands. It extracts every
distinct Bash tool command from local transcripts, decides each one with the guard at a
base checkout and at a head checkout, and reports the verdict matrix, the moved verdicts
by direction, and the head's reasons for every command the base allowed and the head did
not. The measurement that motivated it: a head that answered `ask` on 23.6% of commands
main allowed, with every fixture, sweep and fuzz green.

Only aggregates leave this process. Transcripts are private; no command text is printed.

    python3 instruments/corpus_delta.py --base <checkout> --head <checkout>
        [--transcripts GLOB] [--top N]
    python3 instruments/corpus_delta.py --selftest

A base or head is any checkout holding hooks/bash_command_guard.py and hooks/guards/.
An empty corpus is an error (exit 2), never a clean delta.
"""
from __future__ import annotations

import argparse
import collections
import glob
import importlib.util
import json
import os
import re
import sys
import tempfile

VERSION = "1.0"
RECEIPT = "CORPUS-DELTA-SUMMARY"
DEFAULT_TRANSCRIPTS = "~/.claude/projects/*/*.jsonl"
GUARD_MODULES = ("bash_command_guard", "git_grep_engine_guard", "zsh_rev_modifier_guard")


def load_guard(root: str):
    """Import one checkout's Bash guard in isolation from any other loaded checkout."""
    for name in GUARD_MODULES:
        sys.modules.pop(name, None)
    saved = list(sys.path)
    sys.path[:0] = [os.path.join(root, "hooks"), os.path.join(root, "hooks", "guards")]
    try:
        path = os.path.join(root, "hooks", "bash_command_guard.py")
        spec = importlib.util.spec_from_file_location("bash_command_guard", path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules["bash_command_guard"] = module
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = saved
    if not callable(getattr(module, "decide", None)):
        raise RuntimeError(f"{root} guard exposes no decide()")
    return module


def transcript_commands(pattern: str) -> tuple[list[str], int, int]:
    """Return (distinct commands in first-seen order, occurrences, files read)."""
    files = sorted(glob.glob(os.path.expanduser(pattern)))
    seen: dict[str, int] = collections.OrderedDict()
    for path in files:
        try:
            with open(path, encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    if '"Bash"' not in line:
                        continue
                    try:
                        record = json.loads(line)
                    except ValueError:
                        continue
                    message = record.get("message") if isinstance(record, dict) else None
                    content = message.get("content") if isinstance(message, dict) else None
                    if not isinstance(content, list):
                        continue
                    for block in content:
                        if (isinstance(block, dict) and block.get("type") == "tool_use"
                                and block.get("name") == "Bash"):
                            command = (block.get("input") or {}).get("command")
                            if isinstance(command, str) and command.strip():
                                seen[command] = seen.get(command, 0) + 1
        except OSError:
            continue
    return list(seen), sum(seen.values()), len(files)


def reason_key(reason: str) -> str:
    """The head's first sentence with its parenthetical detail removed, for grouping."""
    first = reason.split("\n", 1)[0]
    return re.sub(r"\s*\(.*", "", first).strip()[:96]


def decide(module, command: str) -> tuple[str, str]:
    try:
        verdict, reason = module.decide(command)
    except BaseException as exc:  # a crashing guard is a finding, not a skip
        return f"raised:{type(exc).__name__}", str(exc)
    return verdict, reason or ""


def delta(base, head, commands: list[str]) -> dict:
    matrix: collections.Counter = collections.Counter()
    moved: collections.Counter = collections.Counter()
    reasons: collections.Counter = collections.Counter()
    raised = 0
    for command in commands:
        base_verdict, _ = decide(base, command)
        head_verdict, head_reason = decide(head, command)
        matrix[(base_verdict, head_verdict)] += 1
        if base_verdict != head_verdict:
            moved[(base_verdict, head_verdict)] += 1
        if head_verdict.startswith("raised:") or base_verdict.startswith("raised:"):
            raised += 1
        if base_verdict == "allow" and head_verdict != "allow":
            reasons[(head_verdict, reason_key(head_reason))] += 1
    base_allowed = sum(n for (b, _h), n in matrix.items() if b == "allow")
    newly_not_allowed = sum(n for (b, h), n in matrix.items() if b == "allow" and h != "allow")
    return {
        "commands": len(commands),
        "matrix": matrix,
        "moved": moved,
        "reasons": reasons,
        "raised": raised,
        "base_allowed": base_allowed,
        "newly_not_allowed": newly_not_allowed,
    }


def render(result: dict, files: int, occurrences: int, top: int) -> str:
    lines = [
        f"corpus: {result['commands']} distinct commands, {occurrences} occurrences, "
        f"{files} transcript files",
        "base x head (distinct commands):",
    ]
    for (b, h), n in sorted(result["matrix"].items()):
        lines.append(f"  {b:<6} -> {h:<6} {n}")
    lines.append("moved:")
    for (b, h), n in sorted(result["moved"].items(), key=lambda item: -item[1]):
        lines.append(f"  {b:<6} -> {h:<6} {n}")
    if not result["moved"]:
        lines.append("  (none)")
    base_allowed = result["base_allowed"]
    share = (100.0 * result["newly_not_allowed"] / base_allowed) if base_allowed else 0.0
    lines.append(
        f"base-allowed commands the head does not allow: {result['newly_not_allowed']} "
        f"of {base_allowed} ({share:.1f}%)")
    lines.append(f"head reasons for those (top {top}):")
    for (verdict, key), n in result["reasons"].most_common(top):
        lines.append(f"  {n:6d}  {verdict:<5} {key}")
    if not result["reasons"]:
        lines.append("  (none)")
    lines.append(
        f"{RECEIPT} version={VERSION} commands={result['commands']} "
        f"moved={sum(result['moved'].values())} "
        f"newly_not_allowed={result['newly_not_allowed']} raised={result['raised']}")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--base")
    parser.add_argument("--head")
    parser.add_argument("--transcripts", default=DEFAULT_TRANSCRIPTS)
    parser.add_argument("--top", type=int, default=12)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv[1:])
    if args.selftest:
        return selftest()
    if not args.base or not args.head:
        parser.error("--base and --head are required")
    commands, occurrences, files = transcript_commands(args.transcripts)
    if not commands:
        print(f"{RECEIPT} version={VERSION} commands=0 problem=empty-corpus", file=sys.stderr)
        return 2
    try:
        base = load_guard(args.base)
        head = load_guard(args.head)
    except (RuntimeError, OSError, ImportError, SyntaxError) as exc:
        print(f"{RECEIPT} version={VERSION} problem=cannot-load-guard ({exc})", file=sys.stderr)
        return 2
    print(render(delta(base, head, commands), files, occurrences, args.top))
    return 0


# ---------------------------------------------------------------------------------------
STUB_GUARD = '''
import os
MODE = os.environ.get("CORPUS_DELTA_STUB", "allow")
def decide(command):
    if MODE == "ask-on-hash" and "#" in command:
        return "ask", "this command may launch Git through a prefix the guard cannot resolve (executable '#')"
    if MODE == "raise" and "boom" in command:
        raise ValueError("planted")
    if "git grep -E" in command:
        return "deny", "git grep with the ERE engine"
    return "allow", ""
'''


def _stub_root(directory: str, mode: str) -> str:
    root = os.path.join(directory, mode)
    os.makedirs(os.path.join(root, "hooks", "guards"))
    with open(os.path.join(root, "hooks", "bash_command_guard.py"), "w", encoding="utf-8") as f:
        f.write(STUB_GUARD)
    return root


def selftest() -> int:
    checks = failures = 0

    def check(name: str, condition: bool) -> None:
        nonlocal checks, failures
        checks += 1
        failures += not condition
        print(f"  {'PASS' if condition else 'FAIL'} {name}")

    with tempfile.TemporaryDirectory(prefix="corpus-delta-") as raw:
        transcripts = os.path.join(raw, "projects", "p1")
        os.makedirs(transcripts)
        secret = "ls /very/private/path && echo it-is-private"
        rows = [
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Bash", "input": {"command": secret}}]}},
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Bash", "input": {"command": "# note\\nls"}}]}},
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Bash", "input": {"command": secret}}]}},
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Read", "input": {"file_path": "/x"}}]}},
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Bash", "input": {"command": "   "}}]}},
            {"type": "assistant", "message": {"content": "not a list"}},
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Bash",
                 "input": {"command": "git grep -E 'x' -- README.md"}}]}},
        ]
        with open(os.path.join(transcripts, "s.jsonl"), "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row) + "\n")
            f.write('{"malformed": \n')
            f.write('"Bash" appears in a line that is not JSON\n')
        pattern = os.path.join(raw, "projects", "*", "*.jsonl")
        commands, occurrences, files = transcript_commands(pattern)
        check("distinct commands are extracted once each from Bash tool_use blocks only",
              commands == [secret, "# note\\nls", "git grep -E 'x' -- README.md"])
        check("occurrences count repeats and files are counted",
              occurrences == 4 and files == 1)
        check("an empty corpus is an error, not a clean delta",
              transcript_commands(os.path.join(raw, "nothing", "*.jsonl"))[0] == [])

        base_root = _stub_root(raw, "allow")
        head_root = _stub_root(raw, "ask-on-hash")
        os.environ["CORPUS_DELTA_STUB"] = "allow"
        base = load_guard(base_root)
        os.environ["CORPUS_DELTA_STUB"] = "ask-on-hash"
        head = load_guard(head_root)
        check("each checkout's guard is loaded in isolation",
              base.MODE == "allow" and head.MODE == "ask-on-hash" and base is not head)
        result = delta(base, head, commands)
        check("the verdict matrix counts every command exactly once",
              sum(result["matrix"].values()) == len(commands)
              and result["matrix"][("allow", "allow")] == 1
              and result["matrix"][("allow", "ask")] == 1
              and result["matrix"][("deny", "deny")] == 1)
        check("moved verdicts are keyed by direction",
              dict(result["moved"]) == {("allow", "ask"): 1})
        check("newly-not-allowed is measured against the base-allowed set",
              result["base_allowed"] == 2 and result["newly_not_allowed"] == 1)
        check("head reasons are grouped without their parenthetical detail",
              list(result["reasons"]) == [
                  ("ask", "this command may launch Git through a prefix the guard cannot resolve")])
        report = render(result, files, occurrences, 5)
        check("the report carries only aggregates: no command text leaves the process",
              secret not in report and "/very/private" not in report
              and "# note" not in report and RECEIPT in report)
        check("the receipt names the moved and newly-not-allowed counts",
              "moved=1" in report and "newly_not_allowed=1" in report and "raised=0" in report)

        os.environ["CORPUS_DELTA_STUB"] = "raise"
        raising = load_guard(_stub_root(raw, "raise"))
        result_raise = delta(base, raising, commands + ["boom"])
        check("a guard that raises is counted as a finding, not skipped",
              result_raise["raised"] == 1
              and result_raise["matrix"][("allow", "raised:ValueError")] == 1)
        os.environ.pop("CORPUS_DELTA_STUB", None)

        check("reason keys survive an empty reason", reason_key("") == "")
        check("main refuses an empty corpus with exit 2",
              main(["corpus_delta.py", "--base", base_root, "--head", head_root,
                    "--transcripts", os.path.join(raw, "nothing", "*.jsonl")]) == 2)
        check("main refuses a checkout without a guard with exit 2",
              main(["corpus_delta.py", "--base", raw, "--head", head_root,
                    "--transcripts", pattern]) == 2)

    print(f"\n  {checks} checks, {failures} failure(s)")
    print(f"SELFTEST-SUMMARY suite=corpus-delta checks={checks} failures={failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
