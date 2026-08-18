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
import subprocess
import sys
import pathlib
import time

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
PROCESS_GREP_COMMAND = "git grep -E 'harness\\b' -- README.md"
PROCESS_SOURCE_EXPLOIT_COMMAND = (
    "source <(/usr/bin/printf '%s\\n' \"git grep -E "
    "'harness\\\\b' -- README.md; /bin/echo EXECUTED\")"
)
# The process-boundary tuple carries runtime/exit metadata and is not a decision-fixture
# shape.  Export its two unique commands explicitly so the decision-golden generator's
# exact live corpus cannot silently omit the public envelope exercised below.
DECISION_FIXTURES = (
    ("RED PROCESS: public envelope retains the direct grep decision",
     PROCESS_GREP_COMMAND, "deny"),
    ("ASK PROCESS: public envelope retains executable source uncertainty",
     PROCESS_SOURCE_EXPLOIT_COMMAND, "ask"),
)


class EnvelopeError(ValueError):
    """The matched PreToolUse envelope cannot be judged safely."""


def decide(command, _deadline=None):
    """-> (decision, reason). Worst decision wins; reasons accumulate."""
    _deadline = (time.monotonic() + grep_guard.GUARD_BUDGET_SECONDS
                 if _deadline is None else _deadline)
    worst, reasons = "allow", []
    for name, mod in GUARDS:
        try:
            if time.monotonic() >= _deadline:
                result = (
                    "ask", "the Bash guard exhausted its shared internal decision "
                    "budget before every predicate could classify the command")
            else:
                result = mod.decide(command, _deadline=_deadline)
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


def _emitted_decision(stdout):
    """-> (decision, reason) a hook process emitted, or (None, "") when it emitted nothing."""
    if not stdout:
        return None, ""
    try:
        block = (json.loads(stdout) or {}).get("hookSpecificOutput", {})
    except ValueError:
        return "unparseable output", _clipped(stdout, 90)
    return block.get("permissionDecision"), block.get("permissionDecisionReason") or ""


def _clipped(text, limit=150):
    """-> text cut at a word boundary, so a truncated reason does not end mid-word."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return f"{cut or text[:limit]}..."


def _budget_faults(observations, expected, cap):
    """-> why these hook observations failed, one entry per run, or [] when every one held.

    Each budget check below tests four things and used to print only the elapsed time. That
    is unreadable exactly when it matters: the internal decision budget sits BELOW the cap,
    so a loaded host fail-safes mid-parse and the run then finishes EARLY, and the line
    reported a comfortable number beside the word FAIL with no timing problem in sight.
    Diagnosing one occurrence cost a source read and a reproduction. The guard states its own
    reason when it bails, so that sentence is the diagnosis and belongs in the line.

    Entries carry no run index, so identical faults collapse in `_budget_note`: five runs
    failing the same way is one fact, not five.
    """
    faults = []
    for rc, stdout, stderr, elapsed in observations:
        decision, reason = _emitted_decision(stdout)
        if rc != 0:
            faults.append(f"exited {rc}")
        elif stderr:
            faults.append(f"wrote stderr {_clipped(stderr, 90)!r}")
        elif decision != expected:
            faults.append(
                f"decided {decision or 'nothing'} where {expected or 'nothing'} was "
                f"expected" + (f": {_clipped(reason)}" if reason else ""))
        elif elapsed >= cap:
            faults.append(f"exceeded the {cap}s cap")
    return faults


def _budget_note(faults, runs):
    """-> the trailing clause naming what failed, empty when nothing did."""
    if not faults:
        return ""
    distinct = []
    for fault in faults:
        if fault not in distinct:
            distinct.append(fault)
    shown = [f"{faults.count(fault)} of {runs} runs {fault}" for fault in distinct[:2]]
    if len(distinct) > 2:
        shown.append(f"and {len(distinct) - 2} other faults")
    return "; " + "; ".join(shown)


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
    hook_cases = (
        ("command-terminator", "command -- git grep -Ee'harness\\b' -- README.md", "deny"),
        ("builtin-trap-source", "builtin trap 'source \"$FILE\"' EXIT", "ask"),
        ("exec-single-dash-source", "exec - source \"$FILE\"", "ask"),
        ("alias-exec-source",
         "eval 'alias s=\"exec source\"'; eval 's \"$FILE\"'", "ask"),
        ("alias-source-chain",
         "eval 'alias a=b'; eval 'alias b=source'; eval 'a \"$FILE\"'", "ask"),
        ("alias-embedded-source",
         "eval 'alias s=\"source $FILE; /bin/echo done\"'; eval s", "ask"),
        ("invoked-alias-installs-source",
         ("eval 'alias a=\"builtin alias s=source\"'; eval a; "
          "eval 's \"$FILE\"'"), "ask"),
        ("repeat-alias-source",
         "repeat 1 builtin alias s=source; eval 's \"$FILE\"'", "ask"),
        ("function-alias-source",
         "f(){ builtin alias s=source; }; f; eval 's \"$FILE\"'", "ask"),
        ("debug-trap-alias-source",
         "trap 'builtin alias s=source; trap - DEBUG' DEBUG; eval 's \"$FILE\"'",
         "ask"),
        ("alias-command-source",
         "eval 'alias s=\"command source\"'; eval 's \"$FILE\"'", None),
        ("quoted-alias-data", "/bin/echo 'alias s=source; s \"$FILE\"'", None),
        ("repeat-zero-alias-source",
         "repeat 0 builtin alias s=source; eval 's \"$FILE\"'", None),
        ("uncalled-function-alias-source",
         "f(){ builtin alias s=source; }; eval 's \"$FILE\"'", None),
        ("exit-trap-alias-source",
         "trap 'builtin alias s=source' EXIT; eval 's \"$FILE\"'", None),
        ("invoked-alias-removes-source",
         ("eval 'alias a=\"builtin alias s=source; unalias s\"'; eval a; "
          "eval 's \"$FILE\"'"), None),
        ("exec-argv0", "SHA=x; exec -a harmless git show $SHA:src/f.py", "deny"),
        ("env-s-pcre", "env -S \"git grep -Pe'harness\\b' -- README.md\"", None),
        ("mixed-shell-dynamic", "sh -c 'zsh -c \"git show $SHA:src/f.py\"'", "deny"),
        ("dynamic-exec", "$TOOL show $SHA:src/f.py", "ask"),
        ("command-query", "command -v git show $SHA:src/f.py", None),
        ("numeric-ere", "git grep -Em1 'harness\\b' -- README.md", "deny"),
        ("numeric-pcre", "git grep -Pm1 'harness\\b' -- README.md", None),
        ("optional-ere", "git grep --color -E 'harness\\b' -- README.md", "deny"),
        ("optional-pcre", "git grep --color -P 'harness\\b' -- README.md", None),
        ("terminator-ere", "git grep -E -- 'harness\\b' README.md", "deny"),
        ("terminator-pcre", "git grep -P -- 'harness\\b' README.md", None),
        ("digit-run-ere", "git grep -12Ee'harness\\b' -- README.md", "deny"),
        ("digit-run-pcre", "git grep -12Pe'harness\\b' -- README.md", None),
        ("digit-last-pcre", "git grep -E1Pe'harness\\b' -- README.md", None),
        ("digit-last-ere", "git grep -P1Ee'harness\\b' -- README.md", "deny"),
        ("negated-ere", "git grep -E --no-extended-regexp 'harness\\b' -- README.md", None),
        ("unrelated-negation",
         "git grep -E --no-perl-regexp 'harness\\b' -- README.md", None),
        ("engine-after-reset",
         "git grep --no-perl-regexp -E 'harness\\b' -- README.md", "deny"),
        ("abbrev-extended",
         "git grep --extended -e'harness\\b' -- README.md", "deny"),
        ("abbrev-extended-r",
         "git grep --extended-r -e'harness\\b' -- README.md", "deny"),
        ("abbrev-no-extended",
         "git grep -P --no-extended -e'harness\\b' -- README.md", None),
        ("abbrev-last-wins",
         "git grep --no-extended --extended -e'harness\\b' -- README.md", "deny"),
        ("ambiguous-ext",
         "git grep --ext -e'harness\\b' -- README.md", "ask"),
        ("unknown-arch", "arch git grep -E 'harness\\b' -- README.md", "ask"),
        ("unknown-xcrun", "xcrun git grep -E 'harness\\b' -- README.md", "ask"),
        ("arch-dynamic-exec",
         "arch $TOOL grep -E 'harness\\b' -- README.md", "ask"),
        ("time-dynamic-exec",
         "time $TOOL grep -E 'harness\\b' -- README.md", "ask"),
        ("launcher-dynamic-exec",
         "launcher $TOOL grep -E 'harness\\b' -- README.md", "ask"),
        ("eval-ere", "eval \"git grep -E 'harness\\b' -- README.md\"", "deny"),
        ("eval-pcre", "eval \"git grep -P 'harness\\b' -- README.md\"", None),
        ("eval-zsh", "SHA=x; eval 'git show $SHA:src/f.py'", "deny"),
        ("eval-dynamic-source",
         "eval \"git grep -P $PATTERN -- README.md\"", None),
        ("builtin-eval-dynamic-source",
         "builtin eval \"git grep -P $PATTERN -- README.md\"", None),
        ("sh-dynamic-source",
         "sh -c \"git grep -P $PATTERN -- README.md\"", None),
        ("zsh-dynamic-source",
         "zsh -c \"git grep -P $PATTERN -- README.md\"", None),
        ("sh-single-quoted-dynamic",
         "sh -c '$CMD; git grep -P harness -- README.md'", "ask"),
        ("bash-single-quoted-dynamic",
         "bash -c '$CMD; git grep -P harness -- README.md'", "ask"),
        ("zsh-single-quoted-dynamic",
         "zsh -c '$CMD; git grep -P harness -- README.md'", "ask"),
        ("sh-static-pcre",
         "sh -c \"git grep -P 'harness\\b' -- README.md\"", None),
        ("zsh-static-pcre",
         "zsh -c \"git grep -P 'harness\\b' -- README.md\"", None),
        ("bare-echo", "echo git grep -E 'harness\\b' -- README.md", "ask"),
        ("bare-printf", "printf '%s\\n' git grep -E 'harness\\b' -- README.md", "ask"),
        ("function-echo",
         "echo() { command \"$@\"; }; echo git grep -E 'harness\\b' -- README.md",
         "ask"),
        ("alias-echo",
         "alias echo=git; echo grep -E 'harness\\b' -- README.md", "ask"),
        ("function-printf",
         "function printf { git \"$@\"; }; printf grep -E 'harness\\b' -- README.md",
         "ask"),
        ("alias-printf",
         "alias printf=git; printf grep -E 'harness\\b' -- README.md", "ask"),
        ("builtin-echo",
         "echo() { git \"$@\"; }; builtin echo git grep -E 'harness\\b' -- README.md",
         None),
        ("builtin-printf",
         "alias printf=git; builtin printf '%s\\n' git grep -E 'harness\\b' -- README.md",
         None),
        ("command-echo",
         "echo() { git \"$@\"; }; command echo git grep -E 'harness\\b' -- README.md",
         None),
        ("exact-echo",
         "/bin/echo git grep -E 'harness\\b' -- README.md", None),
        ("exact-printf",
         "/usr/bin/printf '%s\\n' git grep -E 'harness\\b' -- README.md", None),
        ("exact-quoted-function-text",
         "/usr/bin/printf '%s\\n' 'printf() { git \"$@\"; }' git grep -E 'harness\\b' -- README.md",
         None),
        ("brace-function",
         "{ echo() { git \"$@\"; }; echo grep -E 'harness\\b' -- README.md; }",
         "ask"),
        ("subshell-function",
         "( echo() { git \"$@\"; }; echo grep -E 'harness\\b' -- README.md )",
         "ask"),
        ("eval-alias",
         "eval 'alias echo=git'\necho grep -E 'harness\\b' -- README.md", "ask"),
        ("arbitrary-echo-path",
         "/tmp/echo git grep -E 'harness\\b' -- README.md", "ask"),
        ("pcre-quote",
         "git grep -E '^\\Qabc\\E$' -- fixture.txt", "deny"),
        ("required-abbrev",
         "git grep --max-de 1 -E 'harness\\b' -- README.md", "deny"),
        ("recursive-alias",
         "git -c alias.a=b -c 'alias.b=grep -E' a 'harness\\b' -- README.md",
         "deny"),
        ("shell-alias",
         "git -c 'alias.x=!git grep -E \"harness\\b\"' x", "ask"),
        ("shell-alias-eval",
         "git -c \"alias.x=!eval 'git grep -E harness\\\\b -- README.md'\" x",
         "ask"),
        ("shell-alias-sh",
         "git -c 'alias.x=!sh -c \"git show $SHA:src/f.py\"' x", "ask"),
        ("quoted-substitution",
         "/bin/echo \"$(git grep -E 'harness\\b' -- README.md)\"", "deny"),
        ("grouped-substitution",
         "/bin/echo \"$( (printf x); git grep -E 'harness\\b' -- README.md)\"",
         "deny"),
        ("case-substitution",
         "/bin/echo \"$(case x in x) git grep -E 'harness\\b' -- README.md;; esac)\"",
         "ask"),
        ("parameter-substitution",
         "/bin/echo ${value:-$(git grep -E 'harness\\b' -- README.md)}", "deny"),
        ("function-declaration",
         "scan() { git grep -E 'harness\\b' -- README.md; }; /bin/echo safe", None),
        ("function-invocation",
         "scan() { git grep -E 'harness\\b' -- README.md; }; scan", "deny"),
        ("negated-function-invocation",
         "scan() { git grep -E 'harness\\b' -- README.md; }; ! scan", "deny"),
        ("subshell-function-declaration",
         "scan() ( git grep -E 'harness\\b' -- README.md ); /bin/echo safe", None),
        ("subshell-function-invocation",
         "scan() ( git grep -E 'harness\\b' -- README.md ); scan", "deny"),
        ("dynamic-function",
         "scan() { git grep -E 'harness\\b' -- README.md; }; $COMMAND", "ask"),
        ("prefixed-function",
         "scan() { git grep -E 'harness\\b' -- README.md; }; time -p scan", "ask"),
        ("function-name-as-data",
         "scan() { git grep -E 'harness\\b' -- README.md; }; /bin/echo scan", None),
        ("temporal-function-first-hazard",
         ("scan(){ git grep -E 'harness\\b' -- README.md; }; scan; "
          "scan(){ /bin/echo safe; }; scan"), "deny"),
        ("temporal-function-later-inert",
         ("scan(){ /bin/echo safe; }; scan; "
          "scan(){ git grep -E 'harness\\b' -- README.md; }; /bin/echo done"), None),
        ("temporal-function-later-invoked",
         ("scan(){ /bin/echo safe; }; scan; "
          "scan(){ git grep -E 'harness\\b' -- README.md; }; scan"), "deny"),
        ("conditional-function-call",
         ("if false; then scan(){ git grep -E 'harness\\b' -- README.md; }; "
          "fi; scan"), "ask"),
        ("conditional-function-inert",
         ("if false; then scan(){ git grep -E 'harness\\b' -- README.md; }; "
          "fi; /bin/echo done"), None),
        ("subshell-hazard-persists",
         ("scan(){ git grep -E 'harness\\b' -- README.md; }; "
          "(scan(){ /bin/echo safe; }); scan"), "deny"),
        ("subshell-hazard-contained",
         ("scan(){ /bin/echo safe; }; "
          "(scan(){ git grep -E 'harness\\b' -- README.md; }); scan"), None),
        ("subshell-local-call",
         ("scan(){ /bin/echo safe; }; "
          "(scan(){ git grep -E 'harness\\b' -- README.md; }; scan)"), "deny"),
        ("and-rhs-prior-hazard",
         ("scan(){ git grep -E 'harness\\b' -- README.md; }; true && "
          "scan(){ /bin/echo safe; }; scan"), "ask"),
        ("and-rhs-prior-safe",
         ("scan(){ /bin/echo safe; }; true && "
          "scan(){ git grep -E 'harness\\b' -- README.md; }; scan"), "ask"),
        ("or-rhs-prior-hazard",
         ("scan(){ git grep -E 'harness\\b' -- README.md; }; false || "
          "scan(){ /bin/echo safe; }; scan"), "ask"),
        ("or-rhs-prior-safe",
         ("scan(){ /bin/echo safe; }; false || "
          "scan(){ git grep -E 'harness\\b' -- README.md; }; scan"), "ask"),
        ("maybe-superseded-safe",
         ("scan(){ git grep -E 'harness\\b' -- README.md; }; false && "
          "scan(){ git grep -E 'harness\\b' -- README.md; }; "
          "scan(){ /bin/echo safe; }; scan"), None),
        ("maybe-superseded-hazard",
         ("scan(){ /bin/echo safe; }; true || scan(){ /bin/echo safe; }; "
          "scan(){ git grep -E 'harness\\b' -- README.md; }; scan"), "deny"),
        ("pipeline-prior-hazard",
         ("scan(){ git grep -E 'harness\\b' -- README.md; }; "
          "scan(){ /bin/echo safe; } | /bin/cat; scan"), "deny"),
        ("pipeline-prior-safe",
         ("scan(){ /bin/echo safe; }; "
          "scan(){ git grep -E 'harness\\b' -- README.md; } | /bin/cat; scan"), None),
        ("brace-pipeline-prior-hazard",
         ("scan(){ git grep -E 'harness\\b' -- README.md; }; { "
          "scan(){ /bin/echo safe; }; /bin/echo component; } | /bin/cat; scan"),
         "deny"),
        ("brace-pipeline-prior-safe",
         ("scan(){ /bin/echo safe; }; { "
          "scan(){ git grep -E 'harness\\b' -- README.md; }; "
          "/bin/echo component; } | /bin/cat; scan"), None),
        ("arithmetic-backtick",
         "/bin/echo \"$(( `git grep -E 'harness\\b' -- README.md` + 1 ))\"", "deny"),
        ("ambient-engine",
         "git grep 'harness\\b' -- README.md", "ask"),
        ("unknown-subcommand", "git project-helper --version", "ask"),
        ("native-subcommand", "git status --short", None),
        ("literal-here-string",
         "/bin/cat <<< \"git grep -E 'harness\\b' -- README.md\"", None),
        ("shell-here-string",
         "sh <<< \"git grep -E 'harness\\b' -- README.md\"", "deny"),
        ("fd0-shell-here-string",
         "sh 0<<< \"git grep -E 'harness\\b' -- README.md\"", "deny"),
        ("shell-here-string-harmless", "sh 0<<< \"/bin/echo safe\"", None),
        ("shell-here-string-dynamic", "sh <<< \"$BODY\"", "ask"),
        ("leading-shell-here-string",
         "<<< \"git grep -E 'harness\\b' -- README.md\" sh", "deny"),
        ("compound-shell-here-string",
         "{ /bin/echo prep; sh; } <<< \"git grep -E 'harness\\b' -- README.md\"",
         "ask"),
        ("subshell-shell-here-string",
         "(sh) <<< \"git grep -E 'harness\\b' -- README.md\"", "deny"),
        ("if-shell-here-string",
         "if true; then sh; fi <<< \"git grep -E 'harness\\b' -- README.md\"",
         "ask"),
        ("function-shell-here-string",
         "run() { sh; }; run <<< \"git grep -E 'harness\\b' -- README.md\"",
         "ask"),
        ("unknown-here-string-consumer", 'runner <<< "/bin/echo safe"', "ask"),
        ("fd3-shell-here-string",
         "sh 3<<< \"git grep -E 'harness\\b' -- README.md\"", None),
        ("shell-pipeline",
         "/usr/bin/printf '%s\\n' \"git grep -E 'harness\\b' -- README.md\" | sh",
         "ask"),
        ("shell-process-input",
         "sh < <(/usr/bin/printf '%s\\n' \"git grep -E 'harness\\b' -- README.md\")",
         "ask"),
        ("spaced-shell-process-input",
         "sh <  <(/usr/bin/printf '%s\\n' \"git grep -E 'harness\\b' -- README.md\")",
         "ask"),
        ("fd0-shell-process-input",
         "sh 0< <(/usr/bin/printf '%s\\n' \"git grep -E 'harness\\b' -- README.md\")",
         "ask"),
        ("fd3-shell-process-input",
         "sh 3< <(/usr/bin/printf '%s\\n' \"git grep -E 'harness\\b' -- README.md\")",
         None),
        ("leading-shell-file-input", '0<"$SCRIPT" sh', "ask"),
        ("inert-shell-file-input", "0</dev/null sh", None),
        ("fd3-shell-file-input", '3<"$DATA" sh', None),
        ("inert-cross-command-input",
         ("/bin/cat <<< \"git grep -E 'harness\\b' -- README.md\"; "
          "sh </dev/null"), None),
        ("obscured-shell-input",
         "sh 2>/dev/null 0<<< \"git grep -E 'harness\\b' -- README.md\"", "deny"),
        ("obscured-exact-shell-input",
         "/bin/sh 2>/dev/null 0<<< \"git grep -E 'harness\\b' -- README.md\"", "deny"),
        ("exact-data-obscured-input",
         "/bin/cat 2>/dev/null 0<<< \"git grep -E 'harness\\b' -- README.md\"", None),
        ("shell-c-pipeline", "/usr/bin/printf x | sh -c cat", None),
        ("shell-script-pipeline", "/usr/bin/printf x | sh script.sh", None),
        ("arithmetic-command-shift", "(( value = 1 << 2 ))", None),
        ("arithmetic-for-shift",
         "for ((i = 1; i << 2; i++)); do /bin/echo \"$i\"; done", None),
        ("native-submodule", "git submodule status", None),
        ("env-exec-path-submodule",
         "GIT_EXEC_PATH=/tmp/untrusted git submodule status", "ask"),
        ("option-exec-path-submodule",
         "git --exec-path=/tmp/untrusted submodule status", "ask"),
        ("env-exec-path-builtin",
         "GIT_EXEC_PATH=/tmp/untrusted git status --short", None),
        ("option-exec-path-builtin",
         "git --exec-path=/tmp/untrusted status --short", None),
        ("fallback-shell-reachability",
         "launcher /bin/sh 0<<< \"git grep -E 'harness\\b' -- README.md\"", "ask"),
        ("backtick-substitution",
         "/bin/echo " + chr(96) + "git grep -E 'harness\\b' -- README.md" + chr(96),
         "deny"),
        ("shell-heredoc",
         "sh <<'EOF'\ngit grep -E 'harness\\b' -- README.md\nEOF\n", "deny"),
        ("data-heredoc",
         "/bin/cat <<'EOF'\ngit grep -E 'harness\\b' -- README.md\nEOF\n", None),
        ("dashed-shell-heredoc",
         "sh <<'END-MARK'\ngit grep -E 'harness\\b' -- README.md\nEND-MARK\n",
         "deny"),
        ("dashed-data-heredoc",
         "/bin/cat <<'END-MARK'\ngit grep -E 'harness\\b' -- README.md\nEND-MARK\n",
         None),
        ("dynamic-heredoc-consumer",
         "cat <<'END-MARK' | $SHELL\ngit grep -E 'harness\\b' -- README.md\nEND-MARK\n",
         "ask"),
        ("alternate-git-status", "/nonexistent/bin/git status --short", None),
        ("alternate-git-pcre",
         "/nonexistent/bin/git grep -P 'harness\\b' -- README.md", None),
        ("alternate-git-ere",
         "/nonexistent/bin/git grep -E 'harness\\b' -- README.md", "deny"),
        ("command-p-authority", "command -p git status --short", None),
        ("builtin-command-p-authority",
         "builtin command -p git status --short", None),
        ("env-clean-authority", "env -i git status --short", None),
        ("env-unset-path-authority", "env --unset=PATH git status --short", None),
        ("sudo-authority", "sudo -i git status --short", None),
        ("nested-env-clean-authority",
         "env -i sh -c 'git status --short'", None),
        ("nested-env-unset-authority",
         "env -u PATH sh -c 'git status --short'", None),
        ("nested-sudo-authority",
         "sudo sh -c 'git status --short'", None),
        ("stdin-env-clean-authority",
         "env -i sh 0<<< 'git status --short'", None),
        ("heredoc-env-clean-authority",
         "env -i sh <<'EOF'\ngit status --short\nEOF\n", None),
        ("shell-alias-env-clean-authority",
         "git -c 'alias.x=!env -i sh -c \"git status --short\"' x", None),
        ("shell-alias-env-eval-authority",
         "git -c 'alias.x=!env -i sh -c \"eval git\\ status\\ --short\"' x",
         None),
        ("shell-alias-env-stdin-authority",
         "git -c 'alias.x=!env -i sh 0<<< \"git status --short\"' x", None),
        ("shell-alias-path-child-authority",
         "git -c 'alias.x=!PATH=/usr/bin; sh -c \"git status --short\"' x",
         None),
        ("shell-alias-path-stdin-authority",
         "git -c 'alias.x=!PATH=/usr/bin; sh 0<<< \"git status --short\"' x",
         None),
        ("prior-path-authority",
         "PATH=/usr/bin; =git grep -P harness -- README.md", "ask"),
        ("prior-path-missing",
         "PATH=/definitely-missing; =git grep -E 'harness\\b' -- README.md",
         "ask"),
        ("same-command-path-control",
         "PATH=/definitely-missing =git grep -P harness -- README.md", None),
        ("prior-path-stdin-authority",
         "PATH=/usr/bin; sh 0<<< 'git status --short'", None),
        ("prior-line-path-heredoc",
         "PATH=/usr/bin\nzsh <<'EOF'\n"
         "=git grep -P 'harness\\b' -- README.md\nEOF\n", "ask"),
        ("prior-line-path-here-string",
         "PATH=/usr/bin\nzsh 0<<< \"=git grep -P 'harness\\b' -- README.md\"",
         "ask"),
        ("future-path-here-string",
         ("zsh 0<<< \"=git grep -P 'harness\\b' -- README.md\"; "
          "PATH=/usr/bin; /bin/echo done"), None),
        ("future-unset-here-string",
         ("zsh 0<<< \"=git grep -P 'harness\\b' -- README.md\"; "
          "unset PATH; /bin/echo done"), None),
        ("prior-line-path-rev-heredoc",
         "PATH=/usr/bin\nzsh <<'EOF'\n"
         "SHA=x; =git show ${SHA}:src/f.py\nEOF\n", "ask"),
        ("prior-line-path-rev-here-string",
         "PATH=/usr/bin\nzsh 0<<< 'SHA=x; =git show ${SHA}:src/f.py'", "ask"),
        ("prior-path-heredoc-expansion",
         "PATH=/usr/bin; cat <<EOF\n"
         "$(=git grep -P 'harness\\b' -- README.md)\nEOF\n", "ask"),
        ("future-path-heredoc-expansion",
         ("cat <<EOF; PATH=/usr/bin; /bin/echo done\n"
          "$(=git grep -P 'harness\\b' -- README.md)\nEOF\n"), None),
        ("quoted-path-heredoc-control",
         "PATH=/usr/bin; cat <<'EOF'\n"
         "$(=git grep -P 'harness\\b' -- README.md)\nEOF\n", None),
        ("command-p-child-equals",
         "command -p zsh -c \"=git grep -E 'harness\\\\b' -- README.md\"",
         "deny"),
        ("command-p-child-pcre",
         "command -p zsh -c \"=git grep -P 'harness\\\\b' -- README.md\"",
         None),
        ("command-p-stdin-equals",
         "command -p zsh 0<<< \"=git grep -E 'harness\\b' -- README.md\"",
         "deny"),
        ("nested-ask-later-deny",
         ("sh -c \"=git grep -E 'harness\\\\b' -- README.md\"; "
          "=git grep -E 'harness\\b' -- README.md"), "deny"),
        ("direct-deny-later-ask",
         ("=git grep -E 'harness\\b' -- README.md; "
          "sh -c \"=git grep -E 'harness\\\\b' -- README.md\""), "deny"),
        ("heredoc-ask-later-deny",
         ("sh <<'EOF'\n=git grep -E 'harness\\b' -- README.md\nEOF\n"
          "git grep -E 'harness\\b' -- README.md"), "deny"),
        ("direct-deny-later-heredoc",
         ("git grep -E 'harness\\b' -- README.md\n"
          "sh <<'EOF'\n=git grep -E 'harness\\b' -- README.md\nEOF\n"), "deny"),
        ("clustered-child-noequals",
         "zsh -foNO_EQUALS -c \"=git grep -E 'harness\\\\b' -- README.md\"",
         "ask"),
        ("clustered-child-command-noequals",
         "zsh -coNO_EQUALS \"=git grep -E 'harness\\\\b' -- README.md\"",
         "ask"),
        ("clustered-child-stdin-noequals",
         "zsh -foNO_EQUALS 0<<< \"=git grep -E 'harness\\b' -- README.md\"",
         "ask"),
        ("clustered-child-heredoc-noequals",
         "zsh -foNO_EQUALS <<'EOF'\n=git grep -E 'harness\\b' -- README.md\nEOF\n",
         "ask"),
        ("post-c-long-option",
         "zsh -c --no-equals \"git grep -E 'harness\\\\b' -- README.md\"",
         "deny"),
        ("post-c-split-option",
         "zsh -c -o NO_EQUALS \"git grep -E 'harness\\\\b' -- README.md\"",
         "deny"),
        ("post-c-attached-option",
         "zsh -c -oNO_EQUALS \"git grep -E 'harness\\\\b' -- README.md\"",
         "deny"),
        ("post-c-long-option-rev",
         "zsh -c --no-equals 'SHA=x; git show $SHA:src/f.py'", "deny"),
        ("post-body-long-option",
         "zsh -c \"=git grep -E 'harness\\\\b' -- README.md\" --no-equals",
         "deny"),
        ("post-body-split-pcre",
         "zsh -c \"=git grep -P 'harness\\\\b' -- README.md\" -o NO_EQUALS",
         None),
        ("post-body-stdin-control",
         ("zsh -fc '/usr/bin/printf command-only' -s 0<<< "
          "\"git grep -E 'harness\\b' -- README.md\""), None),
        ("clustered-separated-stdin-option",
         "zsh -fo NO_EQUALS <<'EOF'\n"
         "git grep -E 'harness\\b' -- README.md\nEOF\n", "deny"),
        ("clustered-separated-stdin-rev",
         "zsh -fo NO_EQUALS <<'EOF'\n"
         "SHA=x; git show $SHA:src/f.py\nEOF\n", "deny"),
        ("here-string-ask-later-deny",
         ("sh 0<<< \"=git grep -E 'harness\\b' -- README.md\"; "
          "zsh 0<<< \"=git grep -E 'harness\\b' -- README.md\""), "deny"),
        ("here-string-deny-later-ask",
         ("zsh 0<<< \"=git grep -E 'harness\\b' -- README.md\"; "
          "sh 0<<< \"=git grep -E 'harness\\b' -- README.md\""), "deny"),
        ("here-string-rev-ask-later-deny",
         ("sh 0<<< 'SHA=x; =git show $SHA:src/f.py'; "
          "zsh 0<<< 'SHA=x; =git show $SHA:src/f.py'"), "deny"),
        ("command-p-child-heredoc-equals",
         "command -p zsh <<'EOF'\n=git grep -E 'harness\\b' -- README.md\nEOF\n",
         "deny"),
        ("command-p-child-rev",
         "command -p zsh -c 'SHA=x; =git show $SHA:src/f.py'", "deny"),
        ("command-p-rev",
         "SHA=x; command -p git show $SHA:src/f.py", "deny"),
        ("env-clean-rev", "SHA=x; env -i git show $SHA:src/f.py", "deny"),
        ("env-unset-rev",
         "SHA=x; env --unset=PATH git show $SHA:src/f.py", "deny"),
        ("sudo-rev", "SHA=x; sudo git show $SHA:src/f.py", "deny"),
        ("noequals-grep",
         "setopt noequals; =git grep -E 'harness\\b' -- README.md", "ask"),
        ("noequals-rev",
         "SHA=x; unsetopt equals; =git show $SHA:src/f.py", "ask"),
        ("function-noequals",
         "f(){ setopt noequals; }; f; =git grep -E 'harness\\b' -- README.md", "ask"),
        ("child-zsh-equals",
         "setopt noequals; zsh -c \"=git grep -E 'harness\\\\b' -- README.md\"",
         "deny"),
        ("set-o-noequals",
         "set -o noequals; =git grep -E 'harness\\b' -- README.md", "ask"),
        ("emulate-sh-noequals",
         "emulate sh; =git grep -E 'harness\\b' -- README.md", "ask"),
        ("child-zsh-option-noequals",
         "zsh -o NO_EQUALS -c \"=git grep -E 'harness\\\\b' -- README.md\"",
         "ask"),
        ("child-zsh-attached-noequals",
         "zsh -oNO_EQUALS -c \"=git grep -E 'harness\\\\b' -- README.md\"",
         "ask"),
        ("child-zsh-long-noequals",
         "zsh --no-equals -c \"=git grep -E 'harness\\\\b' -- README.md\"",
         "ask"),
        ("uncalled-function-equals",
         "f(){ unsetopt equals; }; =git grep -E 'harness\\b' -- README.md", "deny"),
        ("subshell-equals",
         "(unsetopt equals); =git grep -E 'harness\\b' -- README.md", "deny"),
        ("command-substitution-equals",
         "ignored=$(unsetopt equals); =git grep -E 'harness\\b' -- README.md",
         "deny"),
        ("outer-expanded-env-equals",
         "env -i =git grep -E 'harness\\b' -- README.md", "deny"),
        ("outer-expanded-command-equals",
         "command -p =git grep -E 'harness\\b' -- README.md", "deny"),
        ("outer-expanded-env-rev",
         "SHA=x; env -i =git show $SHA:src/f.py", "deny"),
        ("sh-stdin-equals",
         "sh <<< \"=git grep -E 'harness\\b' -- README.md\"", "ask"),
        ("sh-heredoc-equals",
         "sh <<'EOF'\n=git grep -E 'harness\\b' -- README.md\nEOF\n", "ask"),
        ("child-zsh-heredoc-noequals",
         "zsh -o NO_EQUALS <<'EOF'\n=git grep -E 'harness\\b' -- README.md\nEOF\n",
         "ask"),
        ("child-zsh-heredoc-pcre",
         "zsh <<'EOF'\n=git grep -P 'harness\\b' -- README.md\nEOF\n", None),
        ("heredoc-deny-precedence",
         ("sh <<'A'\n=git grep -E 'harness\\b' -- README.md\nA\n"
          "zsh <<'B'\n=git grep -E 'harness\\b' -- README.md\nB\n"), "deny"),
        ("child-zsh-heredoc-default",
         "unsetopt equals; zsh <<'EOF'\n=git grep -E 'harness\\b' -- README.md\nEOF\n",
         "deny"),
        ("source-process",
         "source <(/usr/bin/printf '%s\\n' '/bin/echo safe')", "ask"),
        ("source-variable", 'source "$FILE"', "ask"),
        ("source-producer-deny",
         "source <(git grep -E 'harness\\b' -- README.md)", "deny"),
        ("source-literal", "source ./script.sh", None),
        ("source-data-consumer", "/bin/cat <(printf safe)", None),
        ("ordinary-alias-rev",
         "alias g='SHA=x; git show $SHA:src/f.py'; eval g", "ask"),
        ("ordinary-alias-grep",
         r'''alias q='git grep -E '"'"'harness\b'"'"' -- README.md'; eval q''',
         "ask"),
        ("global-alias-rev",
         ("alias -g X='; git show $SHA:src/f.py'; "
          "eval 'SHA=x; print -r -- BEFORE X'"), "ask"),
        ("suffix-alias-rev",
         "alias -s x='git show'; eval 'SHA=x; file.x $SHA:src/f.py'", "ask"),
        ("prefixed-w-rev", "SHA=x; git show $SHA:gW@/@h", "ask"),
        ("ordinary-alias-status", "alias g='git status --short'; eval g", None),
        ("builtin-alias-bypass",
         ("eval 'alias t=source'; eval 'alias s=\"builtin t\"'; "
          "eval 's \"$FILE\"'"), None),
        ("called-function-alias-rev",
         "f(){ alias g='git show $SHA:src/f.py'; }; f; eval g", "ask"),
        ("called-function-helper-alias-rev",
         ("setalias(){ alias g='git show $SHA:src/f.py'; }; "
          "f(){ setalias; }; f; eval g"), "ask"),
        ("uncalled-function-alias-rev",
         "f(){ alias g='git show $SHA:src/f.py'; }; eval g", None),
        ("exit-trap-alias-rev",
         "trap \"alias g='git show $SHA:src/f.py'\" EXIT; eval g", None),
        ("unused-global-alias-rev",
         "alias -g X='; git show $SHA:src/f.py'; print -r -- BEFORE", None),
        ("redefined-global-alias-rev",
         ("alias -g X='; git show $SHA:src/f.py'; alias X='print safe'; "
          "eval 'print -r -- BEFORE X'"), None),
        ("alias-bare-git-forward",
         "git -c 'alias.x=!git' x show $SHA:src/f.py", "ask"),
        ("alias-shell-cycle", "git -c 'alias.x=!git x' x", "ask"),
        ("git-terminal-query", "git --exec-path $SHA:src/f.py", None),
    )
    # These run through `hook_mode` in this process. Each one used to be a real
    # interpreter spawn: 218 of them cost 63.5 ms each, about 14 s of the suite's
    # runtime, to re-prove the same process boundary 218 times. The boundary itself is
    # proved once per shape by PROCESS_BOUNDARY_SAMPLE below, which does spawn.
    for label, command, want in hook_cases:
        raw = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
        rc, stdout, stderr = run_raw(raw)
        emitted = json.loads(stdout) if stdout else None
        got = ((emitted or {}).get("hookSpecificOutput", {})
               .get("permissionDecision"))
        ok = rc == 0 and not stderr and got == want
        total += 1
        failures += (not ok)
        print(f"  {'PASS' if ok else 'FAIL'} json-stdin         {label:<18} "
              f"want={want!s:<5} got={got!s:<5}")
    # One real spawn per shape the in-process path cannot reach: argv parsing, actual
    # stdin, the exit code the runtime reads, and the stderr channel.
    process_boundary_sample = (
        ("deny", "claude", PROCESS_GREP_COMMAND, 0, "deny", False),
        ("ask", "claude", "git grep 'harness\\b' -- README.md", 0, "ask", False),
        ("allow", "claude", "git status --short", 0, None, False),
        ("codex-deny", "codex", PROCESS_GREP_COMMAND, 0, "deny",
         False),
        ("codex-ask-maps", "codex", "git grep 'harness\\b' -- README.md", 0, "deny",
         False),
        ("codex-allow", "codex", "git status --short", 0, None, False),
        ("ordinary-alias-rev", "claude",
         "alias g='SHA=x; git show $SHA:src/f.py'; eval g", 0, "ask", False),
        ("called-function-alias-rev", "claude",
         "f(){ alias g='git show $SHA:src/f.py'; }; f; eval g",
         0, "ask", False),
        ("prefixed-w-rev", "claude", "SHA=x; git show $SHA:gW@/@h",
         0, "ask", False),
        ("source-ask", "claude",
         "source <(/usr/bin/printf '%s\\n' '/bin/echo safe')", 0, "ask", False),
        ("source-codex-ask", "codex",
         "source <(/usr/bin/printf '%s\\n' '/bin/echo safe')", 0, "deny", False),
        ("source-grep-exploit", "claude", PROCESS_SOURCE_EXPLOIT_COMMAND,
         0, "ask", False),
        ("source-grep-codex", "codex", PROCESS_SOURCE_EXPLOIT_COMMAND,
         0, "deny", False),
        ("source-rev-exploit", "claude",
         ("SHA=HEAD; source <(/usr/bin/printf '%s\\n' "
          "\"git show \\$SHA:src/f.py 2>/dev/null; /bin/echo AFTER\")"),
         0, "ask", False),
        ("source-rev-codex", "codex",
         ("SHA=HEAD; source <(/usr/bin/printf '%s\\n' "
          "\"git show \\$SHA:src/f.py 2>/dev/null; /bin/echo AFTER\")"),
         0, "deny", False),
        ("non-bash-tool", "claude", None, 0, None, False),
        ("broken-envelope", "claude", "", 2, None, True),
    )
    for label, runtime, command, want_rc, want_decision, want_stderr in (
            process_boundary_sample):
        if command is None:
            raw = json.dumps({"tool_name": "Read", "tool_input": {"file_path": "/x"}})
        elif command == "":
            raw = json.dumps({"tool_name": "Bash", "tool_input": {}})
        else:
            raw = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
        argv = [sys.executable, __file__]
        if runtime == "codex":
            argv.extend(("--runtime", "codex"))
        result = subprocess.run(argv, input=raw, capture_output=True, text=True,
                                timeout=15)
        emitted = json.loads(result.stdout) if result.stdout.strip() else None
        got = ((emitted or {}).get("hookSpecificOutput", {})
               .get("permissionDecision"))
        ok = (result.returncode == want_rc and got == want_decision
              and bool(result.stderr.strip()) == want_stderr)
        total += 1
        failures += (not ok)
        print(f"  {'PASS' if ok else 'FAIL'} process-boundary   {label:<18} "
              f"rc={result.returncode} decision={got!s:<5} stderr={bool(result.stderr.strip())}")
    codex_cases = (
        ("source-process",
         "source <(/usr/bin/printf '%s\\n' '/bin/echo safe')"),
        ("ordinary-alias-rev",
         "alias g='SHA=x; git show $SHA:src/f.py'; eval g"),
        ("called-function-alias-rev",
         "f(){ alias g='git show $SHA:src/f.py'; }; f; eval g"),
        ("prefixed-w-rev", "SHA=x; git show $SHA:gW@/@h"),
        ("alias-bare-git-forward",
         "git -c 'alias.x=!git' x show $SHA:src/f.py"),
        ("alternate-git-ere",
         "/nonexistent/bin/git grep -E 'harness\\b' -- README.md"),
        ("pcre-quote", "git grep -E '^\\Qabc\\E$' -- fixture.txt"),
        ("required-abbrev",
         "git grep --max-de 1 -E 'harness\\b' -- README.md"),
        ("recursive-alias",
         "git -c alias.a=b -c 'alias.b=grep -E' a 'harness\\b' -- README.md"),
        ("shell-alias",
         "git -c 'alias.x=!git grep -E \"harness\\b\"' x"),
        ("shell-alias-eval",
         "git -c \"alias.x=!eval 'git grep -E harness\\\\b -- README.md'\" x"),
        ("grouped-substitution",
         "/bin/echo \"$( (printf x); git grep -E 'harness\\b' -- README.md)\""),
        ("case-substitution",
         "/bin/echo \"$(case x in x) git grep -E 'harness\\b' -- README.md;; esac)\""),
        ("parameter-substitution",
         "/bin/echo ${value:-$(git grep -E 'harness\\b' -- README.md)}"),
        ("function-invocation",
         "scan() { git grep -E 'harness\\b' -- README.md; }; scan"),
        ("negated-function-invocation",
         "scan() { git grep -E 'harness\\b' -- README.md; }; ! scan"),
        ("subshell-function-invocation",
         "scan() ( git grep -E 'harness\\b' -- README.md ); scan"),
        ("dynamic-function",
         "scan() { git grep -E 'harness\\b' -- README.md; }; $COMMAND"),
        ("prefixed-function",
         "scan() { git grep -E 'harness\\b' -- README.md; }; time -p scan"),
        ("temporal-function-first-hazard",
         ("scan(){ git grep -E 'harness\\b' -- README.md; }; scan; "
          "scan(){ /bin/echo safe; }; scan")),
        ("temporal-function-later-invoked",
         ("scan(){ /bin/echo safe; }; scan; "
          "scan(){ git grep -E 'harness\\b' -- README.md; }; scan")),
        ("conditional-function-call",
         ("if false; then scan(){ git grep -E 'harness\\b' -- README.md; }; "
          "fi; scan")),
        ("subshell-hazard-persists",
         ("scan(){ git grep -E 'harness\\b' -- README.md; }; "
          "(scan(){ /bin/echo safe; }); scan")),
        ("subshell-local-call",
         ("scan(){ /bin/echo safe; }; "
          "(scan(){ git grep -E 'harness\\b' -- README.md; }; scan)")),
        ("and-rhs-prior-hazard",
         ("scan(){ git grep -E 'harness\\b' -- README.md; }; true && "
          "scan(){ /bin/echo safe; }; scan")),
        ("and-rhs-prior-safe",
         ("scan(){ /bin/echo safe; }; true && "
          "scan(){ git grep -E 'harness\\b' -- README.md; }; scan")),
        ("or-rhs-prior-hazard",
         ("scan(){ git grep -E 'harness\\b' -- README.md; }; false || "
          "scan(){ /bin/echo safe; }; scan")),
        ("or-rhs-prior-safe",
         ("scan(){ /bin/echo safe; }; false || "
          "scan(){ git grep -E 'harness\\b' -- README.md; }; scan")),
        ("maybe-superseded-hazard",
         ("scan(){ /bin/echo safe; }; true || scan(){ /bin/echo safe; }; "
          "scan(){ git grep -E 'harness\\b' -- README.md; }; scan")),
        ("pipeline-prior-hazard",
         ("scan(){ git grep -E 'harness\\b' -- README.md; }; "
          "scan(){ /bin/echo safe; } | /bin/cat; scan")),
        ("brace-pipeline-prior-hazard",
         ("scan(){ git grep -E 'harness\\b' -- README.md; }; { "
          "scan(){ /bin/echo safe; }; /bin/echo component; } | /bin/cat; scan")),
        ("arithmetic-backtick",
         "/bin/echo \"$(( `git grep -E 'harness\\b' -- README.md` + 1 ))\""),
        ("ambient-engine", "git grep 'harness\\b' -- README.md"),
        ("unknown-subcommand", "git project-helper --version"),
        ("shell-here-string",
         "sh <<< \"git grep -E 'harness\\b' -- README.md\""),
        ("fd0-shell-here-string",
         "sh 0<<< \"git grep -E 'harness\\b' -- README.md\""),
        ("shell-here-string-dynamic", "sh <<< \"$BODY\""),
        ("leading-shell-here-string",
         "<<< \"git grep -E 'harness\\b' -- README.md\" sh"),
        ("compound-shell-here-string",
         "{ /bin/echo prep; sh; } <<< \"git grep -E 'harness\\b' -- README.md\""),
        ("subshell-shell-here-string",
         "(sh) <<< \"git grep -E 'harness\\b' -- README.md\""),
        ("if-shell-here-string",
         "if true; then sh; fi <<< \"git grep -E 'harness\\b' -- README.md\""),
        ("function-shell-here-string",
         "run() { sh; }; run <<< \"git grep -E 'harness\\b' -- README.md\""),
        ("unknown-here-string-consumer", 'runner <<< "/bin/echo safe"'),
        ("shell-pipeline",
         "/usr/bin/printf '%s\\n' \"git grep -E 'harness\\b' -- README.md\" | sh"),
        ("shell-process-input",
         "sh < <(/usr/bin/printf '%s\\n' \"git grep -E 'harness\\b' -- README.md\")"),
        ("spaced-shell-process-input",
         "sh <  <(/usr/bin/printf '%s\\n' \"git grep -E 'harness\\b' -- README.md\")"),
        ("fd0-shell-process-input",
         "sh 0< <(/usr/bin/printf '%s\\n' \"git grep -E 'harness\\b' -- README.md\")"),
        ("leading-shell-file-input", '0<"$SCRIPT" sh'),
        ("obscured-shell-input",
         "sh 2>/dev/null 0<<< \"git grep -E 'harness\\b' -- README.md\""),
        ("obscured-exact-shell-input",
         "/bin/sh 2>/dev/null 0<<< \"git grep -E 'harness\\b' -- README.md\""),
        ("env-exec-path-submodule",
         "GIT_EXEC_PATH=/tmp/untrusted git submodule status"),
        ("option-exec-path-submodule",
         "git --exec-path=/tmp/untrusted submodule status"),
        ("fallback-shell-reachability",
         "launcher /bin/sh 0<<< \"git grep -E 'harness\\b' -- README.md\""),
        ("unknown-escape", "git grep -E '^\\Y$' -- fixture.txt"),
        ("shell-heredoc",
         "sh <<'EOF'\ngit grep -E 'harness\\b' -- README.md\nEOF\n"),
        ("dashed-shell-heredoc",
         "sh <<'END-MARK'\ngit grep -E 'harness\\b' -- README.md\nEND-MARK\n"),
        ("dynamic-heredoc-consumer",
         "cat <<'END-MARK' | $SHELL\ngit grep -E 'harness\\b' -- README.md\nEND-MARK\n"),
        ("prior-path-authority",
         "PATH=/usr/bin; =git grep -P harness -- README.md"),
        ("prior-path-missing",
         "PATH=/definitely-missing; =git grep -E 'harness\\b' -- README.md"),
        ("prior-line-path-heredoc",
         "PATH=/usr/bin\nzsh <<'EOF'\n"
         "=git grep -P 'harness\\b' -- README.md\nEOF\n"),
        ("prior-line-path-here-string",
         "PATH=/usr/bin\nzsh 0<<< \"=git grep -P 'harness\\b' -- README.md\""),
        ("prior-line-path-rev-heredoc",
         "PATH=/usr/bin\nzsh <<'EOF'\n"
         "SHA=x; =git show ${SHA}:src/f.py\nEOF\n"),
        ("prior-line-path-rev-here-string",
         "PATH=/usr/bin\nzsh 0<<< 'SHA=x; =git show ${SHA}:src/f.py'"),
        ("prior-path-heredoc-expansion",
         "PATH=/usr/bin; cat <<EOF\n"
         "$(=git grep -P 'harness\\b' -- README.md)\nEOF\n"),
        ("command-p-child-equals",
         "command -p zsh -c \"=git grep -E 'harness\\\\b' -- README.md\""),
        ("command-p-stdin-equals",
         "command -p zsh 0<<< \"=git grep -E 'harness\\b' -- README.md\""),
        ("nested-ask-later-deny",
         ("sh -c \"=git grep -E 'harness\\\\b' -- README.md\"; "
          "=git grep -E 'harness\\b' -- README.md")),
        ("direct-deny-later-ask",
         ("=git grep -E 'harness\\b' -- README.md; "
          "sh -c \"=git grep -E 'harness\\\\b' -- README.md\"")),
        ("heredoc-ask-later-deny",
         ("sh <<'EOF'\n=git grep -E 'harness\\b' -- README.md\nEOF\n"
          "git grep -E 'harness\\b' -- README.md")),
        ("direct-deny-later-heredoc",
         ("git grep -E 'harness\\b' -- README.md\n"
          "sh <<'EOF'\n=git grep -E 'harness\\b' -- README.md\nEOF\n")),
        ("clustered-child-noequals",
         "zsh -foNO_EQUALS -c \"=git grep -E 'harness\\\\b' -- README.md\""),
        ("clustered-child-command-noequals",
         "zsh -coNO_EQUALS \"=git grep -E 'harness\\\\b' -- README.md\""),
        ("clustered-child-stdin-noequals",
         "zsh -foNO_EQUALS 0<<< \"=git grep -E 'harness\\b' -- README.md\""),
        ("clustered-child-heredoc-noequals",
         "zsh -foNO_EQUALS <<'EOF'\n=git grep -E 'harness\\b' -- README.md\nEOF\n"),
        ("post-c-long-option",
         "zsh -c --no-equals \"git grep -E 'harness\\\\b' -- README.md\""),
        ("post-c-split-option",
         "zsh -c -o NO_EQUALS \"git grep -E 'harness\\\\b' -- README.md\""),
        ("post-c-attached-option",
         "zsh -c -oNO_EQUALS \"git grep -E 'harness\\\\b' -- README.md\""),
        ("post-c-long-option-rev",
         "zsh -c --no-equals 'SHA=x; git show $SHA:src/f.py'"),
        ("post-body-long-option",
         "zsh -c \"=git grep -E 'harness\\\\b' -- README.md\" --no-equals"),
        ("clustered-separated-stdin-option",
         "zsh -fo NO_EQUALS <<'EOF'\n"
         "git grep -E 'harness\\b' -- README.md\nEOF\n"),
        ("clustered-separated-stdin-rev",
         "zsh -fo NO_EQUALS <<'EOF'\n"
         "SHA=x; git show $SHA:src/f.py\nEOF\n"),
        ("here-string-ask-later-deny",
         ("sh 0<<< \"=git grep -E 'harness\\b' -- README.md\"; "
          "zsh 0<<< \"=git grep -E 'harness\\b' -- README.md\"")),
        ("here-string-deny-later-ask",
         ("zsh 0<<< \"=git grep -E 'harness\\b' -- README.md\"; "
          "sh 0<<< \"=git grep -E 'harness\\b' -- README.md\"")),
        ("here-string-rev-ask-later-deny",
         ("sh 0<<< 'SHA=x; =git show $SHA:src/f.py'; "
          "zsh 0<<< 'SHA=x; =git show $SHA:src/f.py'")),
        ("command-p-child-heredoc-equals",
         "command -p zsh <<'EOF'\n=git grep -E 'harness\\b' -- README.md\nEOF\n"),
        ("command-p-child-rev",
         "command -p zsh -c 'SHA=x; =git show $SHA:src/f.py'"),
        ("noequals-grep",
         "setopt noequals; =git grep -E 'harness\\b' -- README.md"),
        ("function-noequals",
         "f(){ setopt noequals; }; f; =git grep -E 'harness\\b' -- README.md"),
        ("sh-stdin-equals",
         "sh <<< \"=git grep -E 'harness\\b' -- README.md\""),
        ("sh-heredoc-equals",
         "sh <<'EOF'\n=git grep -E 'harness\\b' -- README.md\nEOF\n"),
        ("child-zsh-option-noequals",
         "zsh -o NO_EQUALS -c \"=git grep -E 'harness\\\\b' -- README.md\""),
        ("child-zsh-attached-noequals",
         "zsh -oNO_EQUALS -c \"=git grep -E 'harness\\\\b' -- README.md\""),
        ("child-zsh-long-noequals",
         "zsh --no-equals -c \"=git grep -E 'harness\\\\b' -- README.md\""),
        ("uncalled-function-equals",
         "f(){ unsetopt equals; }; =git grep -E 'harness\\b' -- README.md"),
        ("subshell-equals",
         "(unsetopt equals); =git grep -E 'harness\\b' -- README.md"),
        ("command-substitution-equals",
         "ignored=$(unsetopt equals); =git grep -E 'harness\\b' -- README.md"),
        ("outer-expanded-env-equals",
         "env -i =git grep -E 'harness\\b' -- README.md"),
        ("outer-expanded-env-rev", "SHA=x; env -i =git show $SHA:src/f.py"),
        ("child-zsh-heredoc-noequals",
         "zsh -o NO_EQUALS <<'EOF'\n=git grep -E 'harness\\b' -- README.md\nEOF\n"),
        ("heredoc-deny-precedence",
         ("sh <<'A'\n=git grep -E 'harness\\b' -- README.md\nA\n"
          "zsh <<'B'\n=git grep -E 'harness\\b' -- README.md\nB\n")),
    )
    for label, command in codex_cases:
        raw = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
        rc, stdout, stderr = run_raw(raw, runtime="codex")
        emitted = json.loads(stdout) if stdout else None
        got = ((emitted or {}).get("hookSpecificOutput", {})
               .get("permissionDecision"))
        ok = rc == 0 and not stderr and got == "deny"
        total += 1
        failures += (not ok)
        print(f"  {'PASS' if ok else 'FAIL'} codex-json        {label:<18} "
              f"want=deny  got={got!s:<5}")
    codex_allow_cases = (
        ("ordinary-alias-status", "alias g='git status --short'; eval g"),
        ("uncalled-function-alias-rev",
         "f(){ alias g='git show $SHA:src/f.py'; }; eval g"),
        ("exit-trap-alias-rev",
         "trap \"alias g='git show $SHA:src/f.py'\" EXIT; eval g"),
        ("builtin-alias-bypass",
         ("eval 'alias t=source'; eval 'alias s=\"builtin t\"'; "
          "eval 's \"$FILE\"'")),
        ("alternate-git-status", "/nonexistent/bin/git status --short"),
        ("command-p-authority", "command -p git status --short"),
        ("env-clean-authority", "env -i git status --short"),
        ("env-unset-path-authority", "env --unset=PATH git status --short"),
        ("heredoc-env-clean-authority",
         "env -i sh <<'EOF'\ngit status --short\nEOF\n"),
        ("nested-env-clean-authority", "env -i sh -c 'git status --short'"),
        ("nested-env-unset-authority", "env -u PATH sh -c 'git status --short'"),
        ("nested-sudo-authority", "sudo sh -c 'git status --short'"),
        ("prior-path-stdin-authority",
         "PATH=/usr/bin; sh 0<<< 'git status --short'"),
        ("shell-alias-env-clean-authority",
         "git -c 'alias.x=!env -i sh -c \"git status --short\"' x"),
        ("shell-alias-env-eval-authority",
         "git -c 'alias.x=!env -i sh -c \"eval git\\ status\\ --short\"' x"),
        ("shell-alias-env-stdin-authority",
         "git -c 'alias.x=!env -i sh 0<<< \"git status --short\"' x"),
        ("shell-alias-path-child-authority",
         "git -c 'alias.x=!PATH=/usr/bin; sh -c \"git status --short\"' x"),
        ("shell-alias-path-stdin-authority",
         "git -c 'alias.x=!PATH=/usr/bin; sh 0<<< \"git status --short\"' x"),
        ("stdin-env-clean-authority", "env -i sh 0<<< 'git status --short'"),
        ("sudo-authority", "sudo -i git status --short"),
        ("future-path-here-string",
         ("zsh 0<<< \"=git grep -P 'harness\\b' -- README.md\"; "
          "PATH=/usr/bin; /bin/echo done")),
        ("future-unset-here-string",
         ("zsh 0<<< \"=git grep -P 'harness\\b' -- README.md\"; "
          "unset PATH; /bin/echo done")),
        ("future-path-heredoc",
         ("cat <<EOF; PATH=/usr/bin; /bin/echo done\n"
          "$(=git grep -P 'harness\\b' -- README.md)\nEOF\n")),
        ("post-body-pcre",
         "zsh -c \"=git grep -P 'harness\\\\b' -- README.md\" -o NO_EQUALS"),
        ("post-body-stdin",
         ("zsh -fc '/usr/bin/printf command-only' -s 0<<< "
          "\"git grep -E 'harness\\b' -- README.md\"")),
    )
    for label, command in codex_allow_cases:
        raw = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
        rc, stdout, stderr = run_raw(raw, runtime="codex")
        ok = rc == 0 and not stderr and not stdout
        total += 1
        failures += (not ok)
        print(f"  {'PASS' if ok else 'FAIL'} codex-json        {label:<18} "
              f"want=allow got={'allow' if not stdout else 'decision':<8}")
    registered_started = time.monotonic()
    registered_decisions = []
    for _attempt in range(5):
        grep_guard._GIT_AUTHORITY_CACHE.clear()
        raw = json.dumps({"tool_name": "Bash", "tool_input": {"command": "git status --short"}})
        rc, stdout, stderr = run_raw(raw)
        registered_decisions.append((rc, stdout, stderr))
    registered_elapsed = time.monotonic() - registered_started
    faults = _budget_faults(
        [(rc, stdout, stderr, 0.0) for rc, stdout, stderr in registered_decisions],
        None, 4.5)
    note = _budget_note(faults, len(registered_decisions))
    over_cap = registered_elapsed >= 4.5
    if over_cap:
        note += "; the five envelopes together exceeded the 4.5s cap"
    ok = not faults and not over_cap
    total += 1
    failures += (not ok)
    print(f"  {'PASS' if ok else 'FAIL'} hook-budget        5 public envelopes in "
          f"{registered_elapsed:.3f}s (cap 4.5s){note}")

    slow_raw = json.dumps({
        "tool_name": "Bash",
        "tool_input": {"command": grep_guard._FUNCTION_PARSE_LIMIT_SOURCE},
    })
    for runtime, expected in (("claude", "ask"), ("codex", "deny")):
        observations = []
        for _attempt in range(5):
            started = time.monotonic()
            argv = [sys.executable, __file__]
            if runtime == "codex":
                argv.extend(("--runtime", "codex"))
            result = subprocess.run(
                argv, input=slow_raw, capture_output=True, text=True, timeout=5)
            elapsed = time.monotonic() - started
            observations.append(
                (result.returncode, result.stdout, result.stderr, elapsed))
        faults = _budget_faults(observations, expected, 4.5)
        ok = not faults
        total += 1
        failures += (not ok)
        print(f"  {'PASS' if ok else 'FAIL'} slow-hook-budget   {runtime:<6} "
              f"5 explicit {expected} decisions; max="
              f"{max(item[3] for item in observations):.3f}s (cap 4.5s)"
              f"{_budget_note(faults, len(observations))}")

    operator_raw = json.dumps({
        "tool_name": "Bash",
        "tool_input": {"command": grep_guard._FUNCTION_OPERATOR_BUDGET_SOURCE},
    })
    for runtime in ("claude", "codex"):
        observations = []
        for _attempt in range(5):
            started = time.monotonic()
            argv = [sys.executable, __file__]
            if runtime == "codex":
                argv.extend(("--runtime", "codex"))
            result = subprocess.run(
                argv, input=operator_raw, capture_output=True, text=True, timeout=5)
            observations.append((
                result.returncode, result.stdout, result.stderr,
                time.monotonic() - started))
        faults = _budget_faults(observations, None, 4.5)
        ok = not faults
        total += 1
        failures += (not ok)
        print(f"  {'PASS' if ok else 'FAIL'} operator-budget    {runtime:<6} "
              f"5 explicit allow decisions; max="
              f"{max(item[3] for item in observations):.3f}s (cap 4.5s)"
              f"{_budget_note(faults, len(observations))}")

    seen_deadlines = []
    class DeadlineGuard:
        @staticmethod
        def decide(_command, _deadline=None):
            seen_deadlines.append(_deadline)
            return "allow", ""
    original_guards = list(GUARDS)
    GUARDS[:] = [("first", DeadlineGuard), ("second", DeadlineGuard)]
    try:
        shared_deadline_ok = decide("/bin/echo safe")[0] == "allow"
    finally:
        GUARDS[:] = original_guards
    shared_deadline_ok = (shared_deadline_ok and len(seen_deadlines) == 2
                          and seen_deadlines[0] is not None
                          and seen_deadlines[0] == seen_deadlines[1])
    total += 1
    failures += (not shared_deadline_ok)
    print(f"  {'PASS' if shared_deadline_ok else 'FAIL'} shared-deadline    "
          "both predicates receive one outer monotonic deadline")

    oversized = "echo " + ("x" * grep_guard.MAX_COMMAND_CHARS)
    got, reason = decide(oversized)
    ok = got == "ask" and "parse limit" in reason
    total += 1
    failures += (not ok)
    print(f"  {'PASS' if ok else 'FAIL'} parse-limit       want=ask   got={got:<5} "
          "oversized source fails closed")
    class BrokenGuard:
        @staticmethod
        def decide(_command, _deadline=None):
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
    # Each guard now maps its own budget/parse-limit CommandParseError to `ask` before it
    # reaches this arm, because reaching it denied a benign 768 KiB `echo`. This proves the
    # backstop is still closed for that exact type if a future call site escapes again.
    class ParseErrorGuard:
        @staticmethod
        def decide(_command, _deadline=None):
            raise grep_guard.CommandParseError("planted escaping parse error")
    GUARDS.append(("planted_parse_error_guard", ParseErrorGuard))
    try:
        got, reason = decide("echo safe")
    finally:
        GUARDS.pop()
    ok = got == "deny" and "predicate failed" in reason
    total += 1
    failures += (not ok)
    print(f"  {'PASS' if ok else 'FAIL'} parse-error-escape want=deny  got={got:<5} "
          "an escaping CommandParseError cannot become allow")
    class ExitingGuard:
        @staticmethod
        def decide(_command, _deadline=None):
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
    print(f"SELFTEST-SUMMARY suite=bash_command_guard checks={total} failures={failures}")
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
