#!/usr/bin/env python3
r"""H4 - PreToolUse(Bash) guard: unbraced `$VAR:<zsh modifier>` in a git rev:path.

LIVE on every Bash call via bash_command_guard.py (settings.json -> PreToolUse) — do NOT
register this file separately; a second registration double-spawns on every Bash call.
Standalone registration, only if bash_command_guard.py is ever removed:

  "PreToolUse": [{ "matcher": "Bash",
    "hooks": [{ "type": "command",
                "command": "python3 ~/.claude/hooks/zsh_rev_modifier_guard.py",
                "timeout": 5 }] }]

Matcher must stay bare "Bash": 85 of the 86 recorded cases begin with `cd`,
a `for` loop or a variable assignment, so a `Bash(git show *)` prefix rule
misses them.

MEASURED on this host (zsh 5.9, which IS the Bash tool's shell - `ps -o comm= -p $$`
returns /bin/zsh). zsh applies history modifiers to an UNBRACED expansion:

    r=/a/b/c.py
    $r:tests/x      -> c.pyests/x        (:t = tail)      <- WRONG OBJECT, silent
    $sha:src/f.py   -> zsh: bad substitution (:s = subst)  <- whole command dies
    $t:run-demo.sh  -> HEADun-demo.sh    (:r = root)
    "$r:tests/x"    -> c.pyests/x        DOUBLE QUOTES DO NOT PROTECT
    ${r}:tests/x    -> /a/b/c.py:tests/x SAFE - braces are the only fix
    $(cmd):src/x    -> abc:src/x         SAFE - command substitution is not affected

Dangerous modifier letters, enumerated empirically a-zA-Z on this zsh:
    a A c e h l P q Q r s t u
Everything else after the colon is inert.

Affected expansion forms (all verified mangled): $NAME  $1  $#  $?  $NAME[sub]

Exit codes:  0 = decision emitted on stdout
             2 = usage error / unknown flag / zero inputs in --selftest
"""
import json
import re
import sys

MODS = "aAcehlPqQrstu"
# unbraced parameter expansions, INCLUDING positionals and specials. $( is excluded.
EXPANSION = re.compile(
    r"\$(?:"
    r"[A-Za-z_][A-Za-z0-9_]*(?:\[[^\]]*\])?"   # $name  $name[1]
    r"|[0-9]+"                                  # $1 $2
    r"|[#?*@!$-]"                               # $# $? $* $@ $! $$ $-
    r")"
    r":([" + MODS + r"])")

# git subcommands that take a `rev:path` / `rev:./path` argument
GIT_REV_PATH = re.compile(
    r"\bgit\b(?:\s+(?:-C|-c|--git-dir|--work-tree)\s+\S+)*\s+"
    r"(show|diff|cat-file|log|ls-tree|archive|checkout|restore|grep|rev-parse|blame)\b")

MOD_MEANING = {
    "a": ":a absolute-path", "A": ":A resolved-absolute", "c": ":c command-path",
    "e": ":e extension-only", "h": ":h dirname", "l": ":l lowercase",
    "P": ":P physical-path", "q": ":q quote", "Q": ":Q unquote",
    "r": ":r strip-extension", "s": ":s/old/new/ substitute (usually 'bad substitution')",
    "t": ":t basename", "u": ":u uppercase",
}


def decide(command):
    """-> (decision, reason)."""
    if not GIT_REV_PATH.search(command):
        return ("allow", "")
    hits = []
    for m in EXPANSION.finditer(command):
        # the whole rev:path argument, for the message
        start = command.rfind(" ", 0, m.start()) + 1
        end = m.end()
        while end < len(command) and not command[end].isspace() and command[end] not in "\"'|;&)":
            end += 1
        hits.append((m.group(0), command[start:end], m.group(1)))
    if not hits:
        return ("allow", "")
    tok, arg, mod = hits[0]
    braced = re.sub(r"^\$([A-Za-z_][A-Za-z0-9_]*)", r"${\1}", tok.split(":")[0]) + ":" + tok.split(":", 1)[1]
    return ("deny",
            "zsh eats `%s` as the %s history modifier - the Bash tool's shell IS zsh on this "
            "host. `%s` does not reach git as written; it becomes a mangled ref "
            "(e.g. `$SHA:src/core/tools/creatives/listing.py` was observed arriving as "
            "`dc185feb4eatives/listing.py`, `fatal: ambiguous argument`). Double quotes do NOT "
            "protect. Brace it: `%s...`. If the command has `2>/dev/null` the fatal is "
            "swallowed and the empty output reads as 'the file/symbol is absent' - "
            "that is the failure this blocks. (%d occurrence(s) in this command.)"
            % (tok, MOD_MEANING.get(mod, mod), arg[:80], braced, len(hits)))


FIXTURES = [
    ("RED  designed: $MB:tests/... (:t basename)",
     'cd /repo && MB=$(git merge-base origin/main HEAD) && git show $MB:tests/bdd/x.py', "deny"),
    ("RED  designed: $SHA:src/... (:s substitute -> bad substitution)",
     'SHA=dc185feb4; git show $SHA:src/core/tools/creatives/listing.py', "deny"),
    ("RED  designed: DOUBLE-QUOTED - quotes do not protect",
     'git show "$rev:src/a2a_server/adcp_a2a_server.py" > /tmp/p.py 2>/dev/null', "deny"),
    ("RED  designed: git cat-file -e $t:run-demo.sh (:r strip-ext)",
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
    ("GREEN braced - the correct form",
     'git show ${MB}:tests/bdd/steps/domain/uc004_delivery.py', "allow"),
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
