#!/usr/bin/env python3
"""bash_command_guard — one Claude/Codex PreToolUse spawn, two proven predicates.

Merged because each guard costs ~23 ms of cold Python spawn on EVERY Bash call;
two scripts is ~46 ms for no benefit. The predicates are independent and both work
off the same command string, so one process runs both.

Guards, each with its own fixtures and red-proof in guards/:
  zsh_rev_modifier_guard  — unbraced $VAR:<zsh history modifier> in a git rev:path
                            argument. The Bash tool's shell is zsh, which applies
                            :t :s :r etc. to unbraced expansions. DOUBLE QUOTES DO
                            NOT PROTECT. 86 corpus events, 38 of them silent under
                            2>/dev/null where the empty result reads as absence.
  git_grep_engine_guard   — `git grep -E` with a PCRE-only atom (\\b \\d \\s \\w …).
                            POSIX ERE has no such atoms; the pattern silently matches
                            the wrong thing or nothing. 332 corpus events, 19 followed
                            within 3 records by a shipped absence claim.

Precedence: deny > ask > allow. Reasons from every guard that fired are concatenated,
so a command tripping both is told about both.

Both runtimes use the same PreToolUse fields and deny shape. The Claude envelope was
verified in-binary at 2.1.220; the Codex envelope is covered by its hook contract and
the selftest below. PreToolUse reads stdin JSON and emits
  {"hookSpecificOutput":{"hookEventName":"PreToolUse",
                         "permissionDecision":"deny|ask|allow",
                         "permissionDecisionReason":"..."}}
`decision:"block"` is deprecated for PreToolUse and is not used.
"""
import json
import sys
import pathlib

VERSION = "1.1.0"
sys.path.insert(0, str(pathlib.Path(__file__).parent / "guards"))

import zsh_rev_modifier_guard as zsh_guard      # noqa: E402
import git_grep_engine_guard as grep_guard      # noqa: E402

GUARDS = [
    ("zsh_rev_modifier", zsh_guard),
    ("git_grep_engine", grep_guard),
]
RANK = {"allow": 0, "ask": 1, "deny": 2}


def decide(command):
    """-> (decision, reason). Worst decision wins; reasons accumulate."""
    worst, reasons = "allow", []
    for name, mod in GUARDS:
        try:
            decision, reason = mod.decide(command)
        except Exception as exc:                       # a guard must never break Bash
            print(f"{name}: predicate raised {exc!r}; allowing", file=sys.stderr)
            continue
        if RANK[decision] > RANK[worst]:
            worst = decision
        if decision != "allow" and reason:
            reasons.append(reason)
    return worst, "\n\n".join(reasons)


def selftest():
    """Run every sub-guard's own suite. Fails if any fails, or if a suite is empty."""
    total = failures = 0
    for name, mod in GUARDS:
        fixtures = getattr(mod, "FIXTURES", None)
        if not fixtures:
            print(f"  {name}: NO FIXTURES — a suite that cannot go red proves nothing")
            failures += 1
            continue
        for label, cmd, want in fixtures:          # (label, command, expected)
            got, _ = mod.decide(cmd)
            ok = got == want
            total += 1
            failures += (not ok)
            print(f"  {'PASS' if ok else 'FAIL'} {name:<18} want={want:<5} got={got:<5} {label}")
    # the merge itself must be exercised, not just the parts
    both = 'git show $sha:src/x.py && git grep -nE "def \\bfoo"'
    got, reason = decide(both)
    ok = got == "deny" and reason.count("\n\n") >= 1
    total += 1
    failures += (not ok)
    print(f"  {'PASS' if ok else 'FAIL'} merge              want=deny  got={got:<5} "
          f"both predicates fire, both reasons returned")
    payload = {"hook_event_name": "PreToolUse", "model": "gpt-test",
               "tool_name": "Bash", "tool_input": {"command": "git show $sha:tests/x"}}
    output = evaluate_payload(payload)
    ok = (output is not None and
          output["hookSpecificOutput"]["permissionDecision"] == "deny")
    total += 1
    failures += (not ok)
    print(f"  {'PASS' if ok else 'FAIL'} codex-envelope     Bash payload emits deny shape")
    print(f"\n  {total} checks, {failures} failures")
    if total == 0:
        print("  ZERO CHECKS RAN — treating as failure")
        return 2
    return 1 if failures else 0


def main():
    args = sys.argv[1:]
    if args:
        if args[0] in ("-h", "--help"):
            print(__doc__)
            return 0
        if args[0] == "--version":
            print(f"bash_command_guard {VERSION}")
            return 0
        if args[0] == "--selftest":
            return selftest()
        print(f"unknown flag: {args[0]}", file=sys.stderr)
        return 2

    raw = sys.stdin.read()
    if not raw.strip():
        print("bash_command_guard: empty stdin — no input to judge", file=sys.stderr)
        return 2
    try:
        payload = json.loads(raw)
    except Exception as exc:
        print(f"bash_command_guard: stdin is not JSON ({exc}); "
              f"the PreToolUse envelope changed and this guard is running blind",
              file=sys.stderr)
        return 2

    output = evaluate_payload(payload)
    if output is not None:
        print(json.dumps(output))
    return 0


def evaluate_payload(payload):
    """Return a hook output object for a blocked Bash call, otherwise None."""
    if payload.get("tool_name") != "Bash":
        return None
    command = (payload.get("tool_input") or {}).get("command", "")
    if not isinstance(command, str) or not command:
        return None
    decision, reason = decide(command)
    if decision == "allow":
        return None
    return {"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": decision,
        "permissionDecisionReason": reason}}


if __name__ == "__main__":
    sys.exit(main())
