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
verified in-binary at 2.1.220. Codex's installed hook contract accepts `deny` with a
non-empty reason, or no output; `allow` requires `updatedInput`, and `ask` is rejected.
With `--runtime codex`, an `ask` result therefore maps to `deny`. PreToolUse reads stdin
JSON and emits
  {"hookSpecificOutput":{"hookEventName":"PreToolUse",
                         "permissionDecision":"deny|ask|allow",
                         "permissionDecisionReason":"..."}}
`decision:"block"` is deprecated for PreToolUse and is not used.
"""
import json
import sys
import pathlib

VERSION = "1.5.0"
RUNTIMES = {"claude", "codex"}
sys.path.insert(0, str(pathlib.Path(__file__).parent / "guards"))

import zsh_rev_modifier_guard as zsh_guard      # noqa: E402
import git_grep_engine_guard as grep_guard      # noqa: E402

GUARDS = [
    ("zsh_rev_modifier", zsh_guard),
    ("git_grep_engine", grep_guard),
]
RANK = {"allow": 0, "ask": 1, "deny": 2}


class EnvelopeError(ValueError):
    """The matched PreToolUse envelope cannot be judged safely."""


def decide(command):
    """-> (decision, reason). Worst decision wins; reasons accumulate."""
    worst, reasons = "allow", []
    for name, mod in GUARDS:
        try:
            result = mod.decide(command)
            if not isinstance(result, tuple) or len(result) != 2:
                raise TypeError(f"expected (decision, reason), got {result!r}")
            decision, reason = result
            if decision not in RANK:
                raise ValueError(f"unknown decision {decision!r}")
            if not isinstance(reason, str):
                raise TypeError(f"reason is not a string: {reason!r}")
        except BaseException as exc:                   # predicate failure is not an allow
            decision = "deny"
            reason = (
                f"{name}: predicate failed ({exc!r}); z-harness cannot prove this Bash "
                "command safe, so the guard is denying it."
            )
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
    ask_payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": "git grep -nE -f patterns.txt -- src/"},
    }
    output = evaluate_payload(ask_payload, runtime="codex")
    decision = (output or {}).get("hookSpecificOutput", {}).get("permissionDecision")
    reason = (output or {}).get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
    ok = decision == "deny" and "fails closed" in reason
    total += 1
    failures += (not ok)
    print(f"  {'PASS' if ok else 'FAIL'} codex-ask-closed   want=deny  got={decision!s:<5} "
          "unsupported confirmation maps to deny")
    class BrokenGuard:
        @staticmethod
        def decide(_command):
            raise RuntimeError("planted predicate fault")
    GUARDS.append(("planted_broken_guard", BrokenGuard))
    try:
        got, reason = decide("echo safe")
    finally:
        GUARDS.pop()
    ok = got == "deny" and "predicate failed" in reason
    total += 1
    failures += (not ok)
    print(f"  {'PASS' if ok else 'FAIL'} predicate-fault    want=deny  got={got:<5} "
          "a broken sub-guard cannot become allow")
    class ExitingGuard:
        @staticmethod
        def decide(_command):
            raise SystemExit(0)
    GUARDS.append(("planted_exiting_guard", ExitingGuard))
    try:
        try:
            got, reason = decide("echo safe")
        except BaseException as exc:
            got, reason = "propagated", repr(exc)
    finally:
        GUARDS.pop()
    ok = got == "deny" and "predicate failed" in reason
    total += 1
    failures += (not ok)
    print(f"  {'PASS' if ok else 'FAIL'} predicate-exit     want=deny  got={got:<5} "
          "a sub-guard SystemExit cannot become allow")
    for label, raw in (
        ("empty stdin", ""),
        ("malformed JSON", "{"),
        ("non-object payload", "[1, 2, 3]"),
        ("missing tool_name", json.dumps({"tool_input": {"command": "echo x"}})),
        ("non-string tool_name", json.dumps({"tool_name": 7, "tool_input": {}})),
        ("non-object tool_input", json.dumps({"tool_name": "Bash", "tool_input": "x"})),
        ("missing command", json.dumps({"tool_name": "Bash", "tool_input": {}})),
    ):
        rc, _out, err = run_raw(raw, runtime="codex")
        ok = rc == 2 and bool(err.strip())
        total += 1
        failures += (not ok)
        print(f"  {'PASS' if ok else 'FAIL'} envelope-closed    {label}: rc={rc}, stderr={bool(err.strip())}")
    class BrokenReader:
        def read(self):
            raise UnicodeError("planted stdin decode failure")
    raw, read_error = read_hook_input(BrokenReader())
    ok = raw is None and "stdin read failed" in read_error
    total += 1
    failures += (not ok)
    print(f"  {'PASS' if ok else 'FAIL'} stdin-closed       decode failure has a reason")
    import time
    large_command = "echo " + ("x" * (256 * 1024))
    started = time.perf_counter()
    tokenized = grep_guard.split_commands(large_command)
    elapsed = time.perf_counter() - started
    ok = (elapsed < 1.5 and len(tokenized) == 1
          and tokenized[0][1][0] == "x" * (256 * 1024))
    total += 1
    failures += (not ok)
    print(f"  {'PASS' if ok else 'FAIL'} tokenizer-linear   256 KiB in {elapsed:.3f}s (cap 1.5s)")
    print(f"\n  {total} checks, {failures} failures")
    if total == 0:
        print("  ZERO CHECKS RAN — treating as failure")
        return 2
    print(f"SELFTEST-SUMMARY checks={total} failures={failures}")
    return 1 if failures else 0


def run_raw(raw, runtime="claude"):
    """In-process hook run for selftest -> (return code, stdout, stderr)."""
    import io
    out, err = io.StringIO(), io.StringIO()
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = out, err
    try:
        rc = hook_mode(raw, runtime=runtime)
    finally:
        sys.stdout, sys.stderr = old_out, old_err
    return rc, out.getvalue(), err.getvalue()


def hook_mode(raw, runtime="claude"):
    if not raw.strip():
        print("bash_command_guard: empty stdin — no input to judge", file=sys.stderr)
        return 2
    try:
        payload = json.loads(raw)
        output = evaluate_payload(payload, runtime=runtime)
    except EnvelopeError as exc:
        print(f"bash_command_guard: {exc}; refusing to run blind", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"bash_command_guard: internal failure {exc!r}; refusing to run blind",
              file=sys.stderr)
        return 2
    if output is not None:
        print(json.dumps(output))
    return 0


def read_hook_input(stream):
    """Return (text, error); stdin failures must never become a silent allow."""
    try:
        return stream.read(), ""
    except Exception as exc:
        return None, f"bash_command_guard: stdin read failed ({exc!r}); refusing to run blind"


def main():
    args = sys.argv[1:]
    runtime = "claude"
    if len(args) >= 2 and args[0] == "--runtime":
        runtime = args[1]
        args = args[2:]
        if runtime not in RUNTIMES:
            print(f"unknown runtime: {runtime!r}; choose claude or codex", file=sys.stderr)
            return 2
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

    raw, error = read_hook_input(sys.stdin)
    if raw is None:
        print(error, file=sys.stderr)
        return 2
    return hook_mode(raw, runtime=runtime)


def evaluate_payload(payload, runtime="claude"):
    """Return a hook output object for a blocked Bash call, otherwise None."""
    if not isinstance(payload, dict):
        raise EnvelopeError("PreToolUse payload is not an object")
    tool_name = payload.get("tool_name")
    if not isinstance(tool_name, str) or not tool_name:
        raise EnvelopeError("PreToolUse payload has no string tool_name")
    if tool_name != "Bash":
        return None
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        raise EnvelopeError("matched Bash payload has non-object tool_input")
    command = tool_input.get("command")
    if not isinstance(command, str) or not command:
        raise EnvelopeError("matched Bash payload has no non-empty string command")
    decision, reason = decide(command)
    if decision == "allow":
        return None
    if runtime == "codex" and decision == "ask":
        decision = "deny"
        reason += (" Codex PreToolUse cannot request confirmation, so z-harness fails closed; "
                   "inspect the pattern source and retry with an explicit safe command.")
    return {"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": decision,
        "permissionDecisionReason": reason}}


if __name__ == "__main__":
    sys.exit(main())
