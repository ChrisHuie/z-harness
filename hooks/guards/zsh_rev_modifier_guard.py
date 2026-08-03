#!/usr/bin/env python3
r"""H4 - PreToolUse(Bash) guard: `$VAR:<zsh modifier>` in a git rev:path argument.

LIVE on every Bash call via bash_command_guard.py (settings.json -> PreToolUse) — do NOT
register this file separately; a second registration double-spawns on every Bash call.
Standalone registration, only if bash_command_guard.py is ever removed:

  "PreToolUse": [{ "matcher": "Bash",
    "hooks": [{ "type": "command",
                "command": "python3 ~/.claude/hooks/zsh_rev_modifier_guard.py",
                "timeout": 5 }] }]

MEASURED on this host (zsh 5.9, which IS the Bash tool's shell - `ps -o comm= -p $$`
returns /bin/zsh). zsh applies history modifiers to parameter expansions:

    r=/a/b/c.py
    $r:tests/x       -> c.pyests/x        (:t = tail)      <- WRONG OBJECT, silent
    ${r:t}ests/x     -> c.pyests/x        BRACED WITH THE MODIFIER INSIDE mangles the
                                          same way - ${r}:tests is the only safe brace
    $sha:src/f.py    -> zsh: bad substitution (:s = subst)  <- whole command dies
    "$r:tests/x"     -> c.pyests/x        quotes do NOT protect when the colon is
                                          INSIDE them
    "$r":tests/x     -> /a/b/c.py:tests/x SAFE - the colon is outside the quotes
    $r\:tests/x      -> /a/b/c.py:tests/x SAFE - escaped colon
    ${r}:tests/x     -> /a/b/c.py:tests/x SAFE - colon outside the braces
    $(cmd):src/x     -> abc:src/x         SAFE - command substitution is unaffected
    'single quoted'  -> never expands     out of scope by construction

Dangerous modifier letters, enumerated empirically a-zA-Z on this zsh:
    a A c e h l P q Q r s t u
Everything else after the colon is inert.

Affected expansion forms (all verified mangled): $NAME  $1  $#  $?  $NAME[sub]  ${NAME:m}

SCOPE (reworked 2026-08-02): analysis is per-subcommand argv, not raw-string. A
subcommand is gated only when its argv resolves to `git <rev:path subcommand>` (leading
env assignments and shell keywords like `do`/`then` stripped, `git -C x` skipped), and
only unquoted or double-quoted tokens are scanned - a `git show` mentioned inside one
quoted argument no longer flags a `$v:mod` sitting in a different subcommand, and
single-quoted text (which the outer shell never expands) is ignored.

Exit codes:  0 = decision emitted on stdout (or out of scope)
             2 = usage error / unknown flag / zero inputs in --selftest
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from git_grep_engine_guard import split_commands, strip_shell_keywords  # noqa: E402

MODS = "aAcehlPqQrstu"
# unbraced parameter expansions, INCLUDING positionals and specials. $( is excluded.
EXPANSION = re.compile(
    r"\$(?:"
    r"[A-Za-z_][A-Za-z0-9_]*(?:\[[^\]]*\])?"   # $name  $name[1]
    r"|[0-9]+"                                  # $1 $2
    r"|[#?*@!$-]"                               # $# $? $* $@ $! $$ $-
    r")"
    r":([" + MODS + r"])")
# braced WITH the modifier inside: ${name:t} — mangles identically ("brace it" done
# wrong). POSIX forms ${name:-x} ${name:+x} ${name:=x} ${name:?x} ${name:0:2} do not
# collide: -, +, =, ?, digits are not modifier letters.
EXPANSION_BRACED = re.compile(
    r"\$\{[A-Za-z_][A-Za-z0-9_]*:([" + MODS + r"])(?=[}/:0-9])")

# git subcommands that take a `rev:path` / `rev:./path` argument
REV_PATH_SUBCOMMANDS = {"show", "diff", "cat-file", "log", "ls-tree", "archive",
                        "checkout", "restore", "grep", "rev-parse", "blame"}

MOD_MEANING = {
    "a": ":a absolute-path", "A": ":A resolved-absolute", "c": ":c command-path",
    "e": ":e extension-only", "h": ":h dirname", "l": ":l lowercase",
    "P": ":P physical-path", "q": ":q quote", "Q": ":Q unquote",
    "r": ":r strip-extension", "s": ":s/old/new/ substitute (usually 'bad substitution')",
    "t": ":t basename", "u": ":u uppercase",
}


def is_rev_path_git(tokens):
    """True when this subcommand's argv is `git [-C x] <rev:path subcommand> ...`."""
    words = strip_shell_keywords([t for t, _ in tokens])
    j = 0
    while j < len(words) and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[j]):
        j += 1
    if j >= len(words) or words[j] != "git":
        return False
    j += 1
    while j < len(words) and words[j] in ("-C", "-c", "--git-dir", "--work-tree"):
        j += 2
    return j < len(words) and words[j] in REV_PATH_SUBCOMMANDS


def decide(command):
    """-> (decision, reason)."""
    hits = []
    for tokens in split_commands(command):
        if not is_rev_path_git(tokens):
            continue
        for text, quoting in tokens:
            if quoting == "'":          # single-quoted: the outer shell never expands it
                continue
            for rx in (EXPANSION, EXPANSION_BRACED):
                for m in rx.finditer(text):
                    hits.append((m.group(0), text, m.group(1)))
    if not hits:
        return ("allow", "")
    tok, arg, mod = hits[0]
    braced = re.sub(r"^\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?", r"${\1}",
                    tok.split(":")[0]) + ":" + tok.split(":", 1)[1]
    return ("deny",
            "zsh eats `%s` as the %s history modifier - the Bash tool's shell IS zsh on this "
            "host, and it applies modifiers inside `${...:%s}` braces too. `%s` does not reach "
            "git as written; it becomes a mangled ref (e.g. `$SHA:src/core/tools/creatives/"
            "listing.py` was observed arriving as `dc185feb4eatives/listing.py`, `fatal: "
            "ambiguous argument`). Double quotes do NOT protect when the colon is inside them. "
            "Brace the NAME only: `%s...`. If the command has `2>/dev/null` the fatal is "
            "swallowed and the empty output reads as 'the file/symbol is absent' - that is the "
            "failure this blocks. (%d occurrence(s) in this command.)"
            % (tok, MOD_MEANING.get(mod, mod), mod, arg[:80], braced, len(hits)))


FIXTURES = [
    ("RED  designed: $MB:tests/... (:t basename)",
     'cd /repo && MB=$(git merge-base origin/main HEAD) && git show $MB:tests/bdd/x.py', "deny"),
    ("RED  designed: $SHA:src/... (:s substitute -> bad substitution)",
     'SHA=dc185feb4; git show $SHA:src/core/tools/creatives/listing.py', "deny"),
    ("RED  designed: DOUBLE-QUOTED, colon inside - quotes do not protect",
     'git show "$rev:src/a2a_server/adcp_a2a_server.py" > /tmp/p.py 2>/dev/null', "deny"),
    ("RED  designed: git cat-file -e $t:run-demo.sh inside a for/do loop",
     'for t in v0.1.0 v0.2.0; do git cat-file -e $t:run-demo.sh 2>/dev/null; done', "deny"),
    ("RED  designed: $BASE:tests/... inside $( ) capture",
     'n=$(git show $BASE:tests/unit/test_x.py | grep -c Mock)', "deny"),
    ("RED  UNMODELLED: POSITIONAL parameter $1:tests/... "
     "(the guard's first draft only matched $NAME)",
     'f() { git show $1:tests/bdd/conftest.py; }; f abc123', "deny"),
    ("RED  UNMODELLED: ARRAY subscript $revs[1]:src/...",
     'revs=(aaa bbb); git show $revs[1]:src/app.py', "deny"),
    ("RED  UNMODELLED: special parameter $?:tests/...",
     'git rev-parse HEAD; git show $?:tests/x.py', "deny"),
    ("RED  UNMODELLED 2026-08-02: braced WITH modifier inside - ${SHA:t} mangles too",
     'git show ${SHA:t}ests/x.py', "deny"),
    ("GREEN braced name, colon outside - the correct form",
     'git show ${MB}:tests/bdd/steps/domain/uc004_delivery.py', "allow"),
    ("GREEN POSIX default form ${name:-x} is not a modifier",
     'git show ${SHA:-HEAD}:src/app.py', "allow"),
    ("GREEN command substitution is not a parameter expansion",
     'git show $(git merge-base main HEAD):src/core/app.py', "allow"),
    ("GREEN colon followed by a NON-modifier letter (.github, digits, /)",
     'git show $PRHEAD:.github/workflows/ci.yml && git show $B:/abs && git show $C:0x', "allow"),
    ("GREEN literal rev, no expansion",
     'git show v0.1.0:run-demo.sh', "allow"),
    ("GREEN $VAR:<mod> but no git rev-path subcommand in the command",
     'echo "$HOME:tests" && ls $d:tests', "allow"),
    ("GREEN $VAR used as the path half, not the rev half",
     'git show HEAD:$f', "allow"),
    ("GREEN 2026-08-02: cross-subcommand composition - single-quoted advice text plus an "
     "unrelated git show",
     "echo 'brace it: use $r:tests never bare' && git show HEAD:README.md", "allow"),
    ("GREEN 2026-08-02: git rev:path text inside a single-quoted argument to another tool",
     "python3 guard.py --check 'git show $SHA:src/f.py'", "allow"),
]


def selftest():
    if not FIXTURES:
        print("SCAN SET EMPTY - zero fixtures is an error", file=sys.stderr)
        return 2
    print("scan set: %d fixtures (%d must-deny, %d must-allow); shell under test = zsh 5.9"
          % (len(FIXTURES),
             sum(1 for f in FIXTURES if f[2] == "deny"),
             sum(1 for f in FIXTURES if f[2] == "allow")))
    bad = 0
    for label, cmd, want in FIXTURES:
        got, _ = decide(cmd)
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
