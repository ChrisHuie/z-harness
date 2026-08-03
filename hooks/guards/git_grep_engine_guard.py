#!/usr/bin/env python3
"""H1 - PreToolUse(Bash) guard: `git grep -E` with a PCRE-only atom.

LIVE on every Bash call via bash_command_guard.py (settings.json -> PreToolUse) — do NOT
register this file separately; a second registration double-spawns on every Bash call.
Standalone registration, only if bash_command_guard.py is ever removed:

  "PreToolUse": [{ "matcher": "Bash",
    "hooks": [{ "type": "command",
                "command": "python3 ~/.claude/hooks/git_grep_engine_guard.py",
                "timeout": 5 }] }]

`if:` filters are prefix rules; 268/271 recorded cases are `cd X && git grep ...`,
which a `Bash(git grep *)` prefix rule would NOT match. Matcher must stay bare "Bash".

MEASURED FACT the guard encodes (git 2.46.1, macOS, this host):
    git grep -E 'x = \\d'     -> rc=1, ZERO hits   (\\d is literal 'd')
    git grep -E 'a\\s\\s='     -> rc=1, ZERO hits
    git grep -E 'foo\\b'      -> matches literal 'foob', i.e. the WRONG line
    git grep    'x = \\d'     -> rc=0, correct     (BRE/no flag is FINE - do not flag it)
    git grep -P 'x = \\d'     -> rc=0, correct

Also modeled (2026-08-02, both verified breaking on this host):
    git -c grep.patternType=extended grep 'x\\b'  -> ERE with no -E flag: DENY on a
                                                    visible PCRE atom, same mechanism
    git grep -E -f <file>                        -> pattern invisible to argv: ASK,
                                                    naming the form as out of scope

Exit codes:  0 = decision emitted on stdout (allow/deny/ask)
             2 = usage error / unknown flag / zero inputs in --selftest
"""
import json
import re
import sys

PCRE_ONLY = re.compile(r"\\[bBdDsSwWAZzhHvVR]|\(\?[:=!<Pi#'-]")
ENGINE_P = re.compile(r"^--perl-regexp$|^-[a-zA-Z]*P[a-zA-Z]*$")
ENGINE_F = re.compile(r"^--fixed-strings$|^-[a-zA-Z]*F[a-zA-Z]*$")
# short flags that consume the NEXT argv element
TAKES_ARG = {"-e", "-f", "--max-depth", "--threads", "-m", "--max-count",
             "--open-files-in-pager", "--color", "-A", "-B", "-C", "--context",
             "--after-context", "--before-context", "-C"}
UNRESOLVED = re.compile(r"\$[A-Za-z_{(]|`")


def split_commands(cmd):
    """Split on UNQUOTED && || ; | newline ( ) and yield token lists.

    Tokens are (text, quoting) where quoting is one of '', "'", '"'.
    Heredoc bodies are dropped: a `<<'EOF' ... EOF` payload is not argv.
    """
    out, cur, tok_parts, tok_modes, q, i = [], [], [], set(), "", 0
    # strip heredoc bodies so python/EOF payloads never reach the tokenizer
    cmd = re.sub(r"<<-?\s*'?\"?([A-Za-z_][A-Za-z0-9_]*)'?\"?\n.*?\n\1\b",
                 " __HEREDOC__ ", cmd, flags=re.S)
    n = len(cmd)

    def append_tok(text, mode=""):
        if text:
            tok_parts.append(text)
            tok_modes.add(mode)

    def flush_tok():
        nonlocal tok_parts, tok_modes
        if tok_parts or tok_modes:
            quoting = next(iter(tok_modes)) if len(tok_modes) == 1 else "mixed"
            cur.append(("".join(tok_parts), quoting))
        tok_parts, tok_modes = [], set()

    def flush_cmd():
        nonlocal cur
        flush_tok()
        if cur:
            out.append(cur)
        cur = []

    while i < n:
        c = cmd[i]
        if q:
            if c == q:
                q = ""
            elif c == "\\" and q == '"' and i + 1 < n:
                # POSIX double-quote rules: a backslash is only special before
                # $ ` " \ and newline. Before anything else (\s, \b, \d) BOTH
                # characters survive - which is exactly why the atom reaches git.
                nxt = cmd[i + 1]
                if nxt in '$`"\\\n':
                    append_tok(nxt, q)
                else:
                    append_tok(c + nxt, q)
                i += 2
                continue
            else:
                append_tok(c, q)
            i += 1
            continue
        if c in ("'", '"'):
            q = c
            tok_modes.add(c)
            i += 1
            continue
        if c == "\\" and i + 1 < n:
            if cmd[i + 1] != "\n":
                append_tok(cmd[i + 1])
            i += 2
            continue
        if c == "{" and tok_parts and tok_parts[-1].endswith("$"):
            # ${...} parameter expansion stays inside its token — the zsh guard
            # scans for braced modifiers; a shredded ${r:t} would be invisible
            depth = 1
            append_tok(c)
            i += 1
            while i < n and depth:
                ch = cmd[i]
                append_tok(ch)
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                i += 1
            continue
        if cmd.startswith("&&", i) or cmd.startswith("||", i):
            flush_cmd()
            i += 2
            continue
        if c in ";|\n&(){}":
            flush_cmd()
            i += 1
            continue
        if c.isspace():
            flush_tok()
            i += 1
            continue
        append_tok(c)
        i += 1
    flush_cmd()
    return out


SHELL_KEYWORDS = {"do", "then", "else", "elif", "if", "while", "until", "time",
                  "exec", "command", "builtin", "nocorrect", "noglob"}


def strip_shell_keywords(words):
    """Drop leading shell keywords so `do git ...` still gates on git."""
    k = 0
    while k < len(words) and words[k] in SHELL_KEYWORDS:
        k += 1
    return words[k:]


def git_grep_argv(tokens):
    """-> (argv slice after `git [-C path|-c cfg] grep`, list of -c config values),
    or None when this subcommand is not a git grep."""
    words = [t for t, _ in tokens]
    k0 = 0
    while k0 < len(words) and words[k0] in SHELL_KEYWORDS:
        k0 += 1
    words = words[k0:]
    if not words:
        return None
    j = 0
    # allow leading env assignments  FOO=bar git grep ...
    while j < len(words) and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[j]):
        j += 1
    if j >= len(words) or words[j] != "git":
        return None
    j += 1
    configs = []
    while j < len(words) and words[j] in ("-C", "-c", "--git-dir", "--work-tree"):
        if words[j] == "-c" and j + 1 < len(words):
            configs.append(words[j + 1])
        j += 2
    if j >= len(words) or words[j] != "grep":
        return None
    return tokens[k0 + j + 1:], configs


CONFIG_ENGINE = {"extended": "E", "ere": "E", "perl": "P", "pcre": "P",
                 "fixed": "F", "basic": "B"}


def decide(command):
    """-> (decision, reason). decision in {allow, deny, ask}."""
    for tokens in split_commands(command):
        got = git_grep_argv(tokens)
        if got is None:
            continue
        argv, configs = got
        engine = None
        engine_src = None
        for cfg in configs:
            key, separator, value = cfg.partition("=")
            if separator and key.lower() == "grep.patterntype":
                val = value.strip().lower()
                if val in CONFIG_ENGINE:
                    engine = CONFIG_ENGINE[val]
                    engine_src = "config"
        patterns = []
        pattern_from_file = False
        k = 0
        while k < len(argv):
            text, quoting = argv[k]
            if text == "--":
                k += 1
                # first thing after -- is a pathspec, pattern must already be set
                break
            if ENGINE_P.match(text):
                engine = "P"
                engine_src = "flag"
            elif ENGINE_F.match(text):
                engine = "F"
                engine_src = "flag"
            elif text in ("--extended-regexp",) or re.match(r"^-[a-zA-Z]*E[a-zA-Z]*$", text):
                engine = "E"
                engine_src = "flag"
            elif text in ("-e", "-f"):
                if text == "-f":
                    pattern_from_file = True
                if k + 1 < len(argv):
                    if text == "-e":
                        patterns.append(argv[k + 1])
                    k += 2
                    continue
            elif text.startswith("-"):
                if text in TAKES_ARG:
                    k += 2
                    continue
            elif not patterns:
                patterns.append((text, quoting))
            k += 1

        if engine != "E":
            continue
        engine_desc = "-E" if engine_src == "flag" else "the grep.patternType config"
        if not patterns:
            if pattern_from_file:
                return ("ask",
                        "git grep with the ERE engine (%s) and a -f PATTERN FILE: this "
                        "guard reads argv only and CANNOT see the file's patterns, so a "
                        "PCRE atom (\\b \\d \\s \\w) in it silently mismatches under ERE. "
                        "Out of scope for this guard - verify the file's patterns by hand "
                        "or use -P." % engine_desc)
            continue
        unresolved = None
        bad_atoms = set()
        for pattern, _pattern_q in patterns:
            if UNRESOLVED.search(pattern):
                unresolved = unresolved or pattern
                continue
            bad_atoms.update(PCRE_ONLY.findall(pattern))
        if bad_atoms:
            return ("deny",
                    "git grep with the ERE engine (selected by " + engine_desc + ") "
                    "cannot interpret %s. Verified on this host (git 2.46.1): "
                    "`git grep -E 'x = \\d'` returns ZERO hits and exit 1; `git grep -E 'foo\\b'` "
                    "matches literal 'foob' - the WRONG line. An empty result here is evidence "
                    "about the instrument, not about the repo. Re-run with -P "
                    "(NOT by dropping the flag - BRE also works, but -P is the intended engine)."
                    % ", ".join(sorted(bad_atoms)))
        if unresolved is not None:
            return ("ask",
                    "git grep -E with a shell-expanded pattern (%s): this guard reads argv "
                    "only and CANNOT see the final pattern, so the -E/\\b breakage is "
                    "UNCHECKED here. Out of scope for this guard - verify by hand or use -P."
                    % unresolved[:60])
    return ("allow", "")


FIXTURES = [
    # (label, command, expected)
    ("RED  designed: bare -E with \\s",
     """cd /repo && git grep -nE "media_buy_status\\s*=" -- src/""", "deny"),
    ("RED  designed: bundled short flags -cnE with \\s",
     """git grep -cnE "^\\s*logger\\.[a-z]+\\(" f741c8ddf -- src/services/x.py""", "deny"),
    ("RED  designed: long flag --extended-regexp with \\b",
     """git grep -n --extended-regexp 'def _names\\b' -- tests/""", "deny"),
    ("RED  designed: -E with \\w and a rev argument",
     """git grep -nE "class \\w+Submitted" 271d6bbb -- src/core/schemas/""", "deny"),
    ("RED  designed: git -C <path> grep -E",
     """git -C /repo grep -nE '\\bstatus=' -- src/""", "deny"),
    ("RED  UNMODELLED: pattern supplied via -e AFTER other flags",
     """git grep -n -E --heading -e 'error_code\\s*=' -- src/""", "deny"),
    ("RED  REVIEW: every -e pattern is inspected, not only the first",
     """git grep -E -e 'safe_[a-z]+' -e 'unsafe\\b' -- src/""", "deny"),
    ("RED  UNMODELLED: env-assignment prefix + -E, pattern single-quoted",
     """GIT_PAGER=cat git grep -E '^\\s+assert ' HEAD -- src/admin/""", "deny"),
    ("ASK  UNMODELLED: pattern is a shell variable - guard cannot see it",
     """sym=foo; git grep -nE "def $sym\\b" -- src/""", "ask"),
    ("GREEN -P is correct",
     """cd /repo && git grep -nP "media_buy_status\\s*=" -- src/""", "allow"),
    ("GREEN no engine flag (BRE) - VERIFIED working on this host",
     """git grep -n 'get_packages\\b' -- src/""", "allow"),
    ("GREEN -E with only POSIX-ERE metachars",
     """git grep -nE '^(def|class) [A-Za-z_]+\\(' -- src/""", "allow"),
    ("GREEN -F fixed strings",
     """git grep -nF 'a\\sb' -- src/""", "allow"),
    ("GREEN the string 'git grep -E ... \\s' inside an echo, not an invocation",
     '''echo "=== git grep -E lacks \\s support ===" ''', "allow"),
    ("GREEN plain grep, not git grep",
     """grep -rnE 'foo\\s+bar' src/""", "allow"),
    ("GREEN -E pattern where the atom is in the PATHSPEC not the pattern",
     """git grep -nE 'TODO' -- 'src/**'""", "allow"),
    ("RED  UNMODELLED 2026-08-02: ERE selected via -c grep.patternType=extended, no -E flag",
     """git -c grep.patternType=extended grep -n 'harness\\b' -- README.md""", "deny"),
    ("RED  REVIEW: git config keys are case-insensitive",
     """git -c Grep.PatternType=EXTENDED grep -n 'harness\\b' -- README.md""", "deny"),
    ("ASK  UNMODELLED 2026-08-02: -E with a -f pattern file - guard cannot see the patterns",
     """git grep -nE -f pats.txt -- src/""", "ask"),
    ("GREEN patternType=perl via config - the intended engine",
     """git -c grep.patternType=perl grep 'x\\b' -- src/""", "allow"),
    ("GREEN -P with a -f pattern file",
     """git grep -P -f pats.txt -- src/""", "allow"),
    ("GREEN inside a for/do loop with the BRE engine",
     """for d in a b; do git grep -n 'x\\b' -- $d; done""", "allow"),
]


def selftest():
    if not FIXTURES:
        print("SCAN SET EMPTY - zero fixtures is an error, not a clean verdict",
              file=sys.stderr)
        return 2
    print("scan set: %d fixtures (%d must-deny, %d must-ask, %d must-allow)" % (
        len(FIXTURES),
        sum(1 for f in FIXTURES if f[2] == "deny"),
        sum(1 for f in FIXTURES if f[2] == "ask"),
        sum(1 for f in FIXTURES if f[2] == "allow")))
    bad = 0
    for label, cmd, want in FIXTURES:
        got, reason = decide(cmd)
        ok = got == want
        bad += 0 if ok else 1
        print("  %-4s want=%-5s got=%-5s  %s" % ("PASS" if ok else "FAIL", want, got, label))
        if not ok:
            print("        cmd: %s" % cmd)
    print("failures: %d" % bad)
    return 0 if bad == 0 else 1


def main():
    args = sys.argv[1:]
    if args:
        if args[0] in ("-h", "--help"):
            print(__doc__)
            return 0
        if args[0] == "--selftest":
            return selftest()
        if args[0] == "--check":
            if len(args) < 2:
                print("--check needs a command string", file=sys.stderr)
                return 2
            d, r = decide(args[1])
            print(json.dumps({"decision": d, "reason": r}, indent=1))
            return 0 if d == "allow" else 1
        print("unknown flag: %s (try --help)" % args[0], file=sys.stderr)
        return 2
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:
        print("hook input was not JSON: %s" % exc, file=sys.stderr)
        return 2
    if payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    decision, reason = decide(command)
    if decision == "allow":
        return 0
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": decision,
        "permissionDecisionReason": reason}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
