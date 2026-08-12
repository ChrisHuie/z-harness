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
    hook_cases = (
        ("command-terminator", "command -- git grep -Ee'harness\\b' -- README.md", "deny"),
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
        ("alternate-git-status", "/nonexistent/bin/git status --short", "ask"),
        ("alternate-git-pcre",
         "/nonexistent/bin/git grep -P 'harness\\b' -- README.md", "ask"),
        ("alternate-git-ere",
         "/nonexistent/bin/git grep -E 'harness\\b' -- README.md", "ask"),
    )
    for label, command, want in hook_cases:
        raw = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
        result = subprocess.run(
            [sys.executable, __file__], input=raw, capture_output=True, text=True,
            timeout=5,
        )
        rc, stdout, stderr = result.returncode, result.stdout, result.stderr
        emitted = json.loads(stdout) if stdout else None
        got = ((emitted or {}).get("hookSpecificOutput", {})
               .get("permissionDecision"))
        ok = rc == 0 and not stderr and got == want
        total += 1
        failures += (not ok)
        print(f"  {'PASS' if ok else 'FAIL'} json-stdin         {label:<18} "
              f"want={want!s:<5} got={got!s:<5}")
    codex_cases = (
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
        ("alternate-git-status", "/nonexistent/bin/git status --short"),
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
    registered_started = time.monotonic()
    registered_decisions = []
    for _attempt in range(5):
        grep_guard._GIT_AUTHORITY_CACHE.clear()
        raw = json.dumps({"tool_name": "Bash", "tool_input": {"command": "git status --short"}})
        rc, stdout, stderr = run_raw(raw)
        registered_decisions.append((rc, stdout, stderr))
    registered_elapsed = time.monotonic() - registered_started
    ok = (registered_elapsed < 4.5 and all(
        rc == 0 and not stdout and not stderr
        for rc, stdout, stderr in registered_decisions
    ))
    total += 1
    failures += (not ok)
    print(f"  {'PASS' if ok else 'FAIL'} hook-budget        5 public envelopes in "
          f"{registered_elapsed:.3f}s (cap 4.5s)")
    oversized = "echo " + ("x" * grep_guard.MAX_COMMAND_CHARS)
    got, reason = decide(oversized)
    ok = got == "ask" and "parse limit" in reason
    total += 1
    failures += (not ok)
    print(f"  {'PASS' if ok else 'FAIL'} parse-limit       want=ask   got={got:<5} "
          "oversized source fails closed")
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
