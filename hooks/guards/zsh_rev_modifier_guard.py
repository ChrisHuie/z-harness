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
from git_grep_engine_guard import (  # noqa: E402
    CommandParseError, MAX_PREFIX_DEPTH, nested_shell_invocation,
    shadowed_non_forwarding_commands, source_has_git_hazard_hint, split_commands,
    unwrap_command_prefix,
)

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
    r"\$\{(?:\([^}]*\))?"
    r"(?:[A-Za-z_][A-Za-z0-9_]*(?:\[[^\]]+\])?|[0-9]+|[#?*@!$-])"
    r":g?([" + MODS + r"])(?=[}/:0-9])")

# git subcommands that take a `rev:path` / `rev:./path` argument
# How many `<shell> -c` layers this guard will unwrap. Reaching it returns `ask`, never
# `allow`: an input the guard cannot model is not a clean verdict.
NEST_DEPTH_LIMIT = 4

REV_PATH_SUBCOMMANDS = {"show", "diff", "cat-file", "log", "ls-tree", "archive",
                        "checkout", "restore", "grep", "rev-parse", "blame"}

MOD_MEANING = {
    "a": ":a absolute-path", "A": ":A resolved-absolute", "c": ":c command-path",
    "e": ":e extension-only", "h": ":h dirname", "l": ":l lowercase",
    "P": ":P physical-path", "q": ":q quote", "Q": ":Q unquote",
    "r": ":r strip-extension", "s": ":s/old/new/ substitute (usually 'bad substitution')",
    "t": ":t basename", "u": ":u uppercase",
}


def is_rev_path_git(tokens, resolution=None):
    """True when this subcommand's argv is `git [-C x] <rev:path subcommand> ...`.

    The hook sees shell source, not execve(2) argv, so `git`, `/usr/bin/git`, `env git`
    and `nice git` are the same invocation. Comparing argv[0] to the literal "git" made
    every wrapper spelling vanish from this guard while the bare form was denied, so the
    prefix is peeled by the same helper the sibling grep guard uses rather than by a
    second hand-rolled walk that can drift from it.
    """
    resolution = resolution or unwrap_command_prefix(tokens)
    if resolution.errors:
        return False
    words = [t for t, _ in resolution.items]
    j = 0
    if j >= len(words) or os.path.basename(words[j]) != "git":
        return False
    j += 1
    options_with_args = {
        "-C", "-c", "--git-dir", "--work-tree", "--namespace", "--super-prefix",
        "--exec-path", "--config-env", "--attr-source",
    }
    while j < len(words) and words[j].startswith("-"):
        if words[j] in options_with_args:
            j += 2
        else:
            # Global switches such as --no-pager and --no-optional-locks do not
            # change the rev:path semantics of the later subcommand.
            j += 1
    return j < len(words) and words[j] in REV_PATH_SUBCOMMANDS


def _zsh_expansion_hits(tokens):
    hits = []
    for text, quoting in tokens:
        if quoting == "'":
            continue
        if quoting.startswith("mixed:"):
            modes = quoting.split(":", 1)[1]
        else:
            code = {"": "U", "'": "S", '"': "D"}.get(quoting, "U")
            modes = code * len(text)
        for rx in (EXPANSION, EXPANSION_BRACED):
            for match in rx.finditer(text):
                matched_modes = modes[match.start():match.end(1)]
                if (matched_modes and len(set(matched_modes)) == 1
                        and matched_modes[0] != "S"):
                    hits.append((match.group(0), text, match.group(1)))
    return hits


def _deny_hits(hits):
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


def decide(command, _depth=0, _shell="zsh", _shadowed_commands=frozenset()):
    """-> (decision, reason), tracking the shell that expands each source layer."""
    try:
        commands = split_commands(command)
    except CommandParseError as exc:
        return ("ask", f"the Bash command cannot be parsed safely ({exc}); rewrite it "
                "as a direct command before proceeding.")
    shadowed_commands = frozenset(
        set(_shadowed_commands) | set(shadowed_non_forwarding_commands(command))
    )
    for tokens in commands:
        resolution = unwrap_command_prefix(tokens, shadowed_commands)
        if resolution.errors and resolution.hazard_hint:
            return ("ask",
                    "this command may launch Git through a prefix the guard cannot "
                    "resolve (" + "; ".join(resolution.errors) + "), so it cannot prove "
                    "whether a `rev:path` argument survives shell expansion. Run Git "
                    "directly with a literal executable.")
        direct_git = is_rev_path_git(tokens, resolution)
        invocation = nested_shell_invocation(resolution, _shell)
        descendant_git = (invocation is not None
                          and source_has_git_hazard_hint(invocation.command))
        if _shell == "zsh" and (direct_git or descendant_git):
            hits = _zsh_expansion_hits(tokens)
            if hits:
                return _deny_hits(hits)
        if invocation is None:
            continue
        if _depth >= NEST_DEPTH_LIMIT:
            return ("ask",
                    f"nested shell invocations exceed this guard's depth limit of "
                    f"{NEST_DEPTH_LIMIT}, so it cannot prove what the innermost command "
                    "becomes after each shell expands it. Run the inner command directly.")
        if not invocation.command or invocation.dynamic:
            return ("ask", "a shell -c command string is empty or dynamic, so its Git "
                    "arguments cannot be inspected before execution")
        decision, reason = decide(
            invocation.command, _depth + 1, invocation.shell, shadowed_commands)
        if decision != "allow":
            return (decision, reason)
    return ("allow", "")


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
    ("RED  REVIEW: braced array modifier",
     'git show ${revs[1]:t}ests/x.py', "deny"),
    ("RED  REVIEW: braced positional modifier",
     'git show ${1:t}ests/x.py', "deny"),
    ("RED  REVIEW: braced expansion flags before the name",
     'git show ${(U)SHA:t}ests/x.py', "deny"),
    ("RED  REVIEW: g-prefixed substitute modifier",
     'git show ${SHA:gs/a/b/}:src/x.py', "deny"),
    ("RED  REVIEW: git global option does not hide the rev:path subcommand",
     'git --no-pager show $SHA:src/x.py', "deny"),
    ("RED  REVIEW: line continuation before subcommand",
     "git \\" + "\n" + "show $SHA:src/x.py", "deny"),
    ("RED  REVIEW: later single-quoted segment does not protect earlier expansion",
     "git show $SHA:s'rc/x.py'", "deny"),
    ("GREEN braced name, colon outside - the correct form",
     'git show ${MB}:tests/bdd/steps/domain/uc004_delivery.py', "allow"),
    ("GREEN quote begins immediately after colon",
     "git show $SHA:'tests/x.py'", "allow"),
    ("GREEN double quote ends before colon",
     'git show "$SHA":tests/x.py', "allow"),
    ("GREEN escaped colon reaches git literally",
     'git show $SHA\\:tests/x.py', "allow"),
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
    ("GREEN REVIEW: a fully single-quoted rev:path token is literal",
     "git show '$SHA:src/f.py'", "allow"),
    ("GREEN REVIEW: a single-quoted hazardous segment in a mixed token is literal",
     "git show '$SHA:src'/f.py", "allow"),
    ("RED REVIEW: --attr-source consumes its argument before git show",
     "git --attr-source HEAD show $SHA:src/f.py", "deny"),
    # The hook reads shell source, not execve(2) argv. Comparing argv[0] to the literal
    # "git" made every spelling below vanish while the bare form above was denied.
    ("RED WRAPPER: absolute executable path",
     "SHA=x; /usr/bin/git show $SHA:src/f.py", "deny"),
    ("RED WRAPPER: env",
     "SHA=x; env git show $SHA:src/f.py", "deny"),
    ("RED WRAPPER: env with an inline assignment",
     "env GIT_PAGER=cat git show $SHA:src/f.py", "deny"),
    ("RED WRAPPER: nohup",
     "SHA=x; nohup git show $SHA:src/f.py", "deny"),
    ("RED WRAPPER: nice",
     "SHA=x; nice git show $SHA:src/f.py", "deny"),
    ("RED WRAPPER: command",
     "SHA=x; command git show $SHA:src/f.py", "deny"),
    # The mangling happens in the OUTER zsh, before any launcher runs, so the launcher's
    # identity does not change whether the hazard exists -- only whether this guard can
    # still see git. Both guards shared one prefix peeler that modelled neither of these.
    ("RED WRAPPER: sudo",
     "SHA=x; sudo git show $SHA:src/f.py", "deny"),
    ("RED WRAPPER: sudo with a target user",
     "SHA=x; sudo -u root git show $SHA:src/f.py", "deny"),
    ("RED WRAPPER: sudo with an attached long option",
     "SHA=x; sudo --user=root git show $SHA:src/f.py", "deny"),
    ("RED WRAPPER: command -p still executes git",
     "SHA=x; command -p git show $SHA:src/f.py", "deny"),
    ("RED WRAPPER: command -- still executes git",
     "SHA=x; command -- git show $SHA:src/f.py", "deny"),
    ("RED WRAPPER: builtin command -- still executes git",
     "SHA=x; builtin command -- git show $SHA:src/f.py", "deny"),
    ("RED WRAPPER: exec -a consumes argv0 before executing git",
     "SHA=x; exec -a harmless git show $SHA:src/f.py", "deny"),
    ("RED WRAPPER: exec -c still executes git",
     "SHA=x; exec -c git show $SHA:src/f.py", "deny"),
    ("RED WRAPPER: exec -- still executes git",
     "SHA=x; exec -- git show $SHA:src/f.py", "deny"),
    ("GREEN WRAPPER: command -v only prints a path, it does not run git",
     "SHA=x; command -v git show $SHA:src/f.py", "allow"),
    # A launcher whose argv rewriting is not modelled must not read as clean.
    ("RED WRAPPER: env -S double-quoted source expands in the outer zsh",
     "SHA=x; env -S \"git show $SHA:src/f.py\"", "deny"),
    ("GREEN WRAPPER: env -S single-quoted source is passed literally",
     "SHA=x; env -S 'git show $SHA:src/f.py'", "allow"),
    ("ASK WRAPPER: a dynamic executable with Git arguments is unresolved",
     "$TOOL show $SHA:src/f.py", "ask"),
    ("ASK WRAPPER: command-prefix depth fails closed",
     ("command " * (MAX_PREFIX_DEPTH + 1)) + "git show $SHA:src/f.py", "ask"),
    ("ASK WRAPPER: an unclosed Git command is not a clean parse",
     "git show '$SHA:src/f.py", "ask"),
    ("ASK WRAPPER: xargs is unmodelled and conceals git",
     "SHA=x; xargs git show $SHA:src/f.py", "ask"),
    ("ASK WRAPPER: ssh is unmodelled and conceals git",
     "SHA=x; ssh host git show $SHA:src/f.py", "ask"),
    ("ASK WRAPPER: unknown arch prefix with a guarded Git tail fails closed",
     "SHA=x; arch git show $SHA:src/f.py", "ask"),
    ("ASK WRAPPER: unknown xcrun prefix with a guarded Git tail fails closed",
     "SHA=x; xcrun git show $SHA:src/f.py", "ask"),
    ("ASK WRAPPER: unmodelled time options with a guarded Git tail fail closed",
     "SHA=x; time -p git show $SHA:src/f.py", "ask"),
    ("ASK WRAPPER: arch cannot hide a dynamic executable",
     "SHA=x; arch $TOOL show $SHA:src/f.py", "ask"),
    ("ASK WRAPPER: time cannot hide a dynamic executable",
     "SHA=x; time $TOOL show $SHA:src/f.py", "ask"),
    ("ASK WRAPPER: an arbitrary launcher cannot hide a dynamic executable",
     "SHA=x; launcher $TOOL show $SHA:src/f.py", "ask"),
    ("RED WRAPPER: bare time is a modelled shell keyword",
     "SHA=x; time git show $SHA:src/f.py", "deny"),
    ("RED WRAPPER: eval single-quoted body runs in the current zsh",
     "SHA=x; eval 'git show $SHA:src/f.py'", "deny"),
    ("RED WRAPPER: eval double-quoted body expands in the outer zsh",
     "SHA=x; eval \"git show $SHA:src/f.py\"", "deny"),
    ("RED WRAPPER: builtin eval body runs in the current zsh",
     "SHA=x; builtin eval 'git show $SHA:src/f.py'", "deny"),
    ("GREEN WRAPPER: eval of a non-Git body is outside this guard",
     "eval 'printf safe'", "allow"),
    ("ASK WRAPPER: partially dynamic eval source is not static",
     "eval \"git grep -P $PATTERN -- README.md\"", "ask"),
    ("ASK WRAPPER: partially dynamic builtin eval source is not static",
     "builtin eval \"git grep -P $PATTERN -- README.md\"", "ask"),
    ("ASK NESTED: partially dynamic sh -c source is not static",
     "sh -c \"git grep -P $PATTERN -- README.md\"", "ask"),
    ("ASK NESTED: partially dynamic zsh -c source is not static",
     "zsh -c \"git grep -P $PATTERN -- README.md\"", "ask"),
    ("GREEN NESTED: fully static eval source retains PCRE",
     "eval \"git grep -P 'harness\\b' -- README.md\"", "allow"),
    ("GREEN NESTED: fully static sh -c source retains PCRE",
     "sh -c \"git grep -P 'harness\\b' -- README.md\"", "allow"),
    ("GREEN NESTED: fully static zsh -c source retains PCRE",
     "zsh -c \"git grep -P 'harness\\b' -- README.md\"", "allow"),
    ("GREEN WRAPPER: echo is proven not to forward the literal Git tail",
     "SHA=x; echo git show $SHA:src/f.py", "allow"),
    ("GREEN WRAPPER: printf is proven not to forward the literal Git tail",
     "SHA=x; printf '%s\\n' git show $SHA:src/f.py", "allow"),
    ("ASK WRAPPER: a function-shadowed echo may forward literal Git argv",
     "echo() { command \"$@\"; }; SHA=x; echo git show $SHA:src/f.py", "ask"),
    ("ASK WRAPPER: an echo alias may supply Git",
     "alias echo=git; SHA=x; echo show $SHA:src/f.py", "ask"),
    ("ASK WRAPPER: a function-shadowed printf may supply Git",
     "function printf { git \"$@\"; }; SHA=x; printf show $SHA:src/f.py", "ask"),
    ("ASK WRAPPER: a printf alias may supply Git",
     "alias printf=git; SHA=x; printf show $SHA:src/f.py", "ask"),
    ("GREEN WRAPPER: builtin echo bypasses a same-source function",
     "echo() { git \"$@\"; }; SHA=x; builtin echo git show $SHA:src/f.py", "allow"),
    ("GREEN WRAPPER: quoted function text does not shadow printf",
     "printf '%s\\n' 'printf() { git \"$@\"; }' git show HEAD:README.md", "allow"),
    ("ASK WRAPPER: basename alone does not trust an arbitrary echo path",
     "SHA=x; /tmp/echo git show $SHA:src/f.py", "ask"),
    ("GREEN WRAPPER: an unmodelled launcher with no git in it is not this guard's business",
     "xargs ls -la", "allow"),
    # A nested shell mangles at a different moment depending on which shell it is.
    ("RED NESTED: sh -c body in double quotes - the OUTER zsh expands it first",
     'sh -c "SHA=x; git show $SHA:src/f.py"', "deny"),
    ("RED NESTED: zsh -c body in single quotes - the INNER zsh applies the modifier",
     "zsh -c 'SHA=x; git show $SHA:src/f.py'", "deny"),
    ("GREEN NESTED: sh -c body in single quotes - sh has no history modifiers",
     "sh -c 'SHA=x; git show $SHA:src/f.py'", "allow"),
    ("GREEN NESTED: bash -c body in single quotes - same reason",
     "bash -c 'SHA=x; git show $SHA:src/f.py'", "allow"),
    ("ASK NESTED: sh composes a zsh command source from an unresolved expansion",
     "sh -c 'zsh -c \"git show $SHA:src/f.py\"'", "ask"),
    ("RED NESTED: zsh expands a double-quoted body before entering sh",
     "zsh -c 'sh -c \"git show $SHA:src/f.py\"'", "deny"),
    ("ASK NESTED: bash composes a zsh command source from an unresolved expansion",
     "bash -c 'zsh -c \"git show $SHA:src/f.py\"'", "ask"),
    ("ASK NESTED: sh composes a bash command source from an unresolved expansion",
     "sh -c 'bash -c \"git show $SHA:src/f.py\"'", "ask"),
    ("GREEN NESTED: nested shell with no rev:path git inside",
     'sh -c "git status"', "allow"),
]


def _nest(payload, layers):
    """Wrap `payload` in `layers` single-quoted `zsh -c` invocations."""
    for _ in range(layers):
        payload = "zsh -c '" + payload.replace("'", "'\\''") + "'"
    return payload


# The depth bound must fail CLOSED. An earlier draft fell through to the token scan once
# the limit was reached, so the same payload denied at four layers and was ALLOWED at
# five. Generated rather than hand-escaped, because the quoting is the point of the case
# and a typo in it would silently test a different command.
_HAZARD = "SHA=x; git show $SHA:src/f.py"
FIXTURES += [
    (f"RED NESTED: hazard at depth {NEST_DEPTH_LIMIT}, the last modelled layer",
     _nest(_HAZARD, NEST_DEPTH_LIMIT), "deny"),
    (f"ASK NESTED: hazard at depth {NEST_DEPTH_LIMIT + 1} cannot be proven either way",
     _nest(_HAZARD, NEST_DEPTH_LIMIT + 1), "ask"),
    (f"ASK NESTED: a benign command past the limit is also unprovable, not clean",
     _nest("git status", NEST_DEPTH_LIMIT + 1), "ask"),
    ("GREEN NESTED: a benign command at the last modelled depth still allows",
     _nest("git status", NEST_DEPTH_LIMIT), "allow"),
]


def selftest():
    if not FIXTURES:
        print("SCAN SET EMPTY - zero fixtures is an error", file=sys.stderr)
        return 2
    census = {}
    for fixture in FIXTURES:
        census[fixture[2]] = census.get(fixture[2], 0) + 1
    # Every outcome class is counted, so adding one cannot leave this line describing a
    # scan set that no longer exists.
    unclassified = sum(count for outcome, count in census.items()
                       if outcome not in ("deny", "allow", "ask"))
    if unclassified:
        print("UNKNOWN EXPECTED OUTCOME in fixtures - cannot report the scan set",
              file=sys.stderr)
        return 2
    print("scan set: %d fixtures (%s); shell under test = zsh 5.9"
          % (len(FIXTURES),
             ", ".join(f"{count} must-{outcome}"
                       for outcome, count in sorted(census.items()))))
    bad = 0
    for label, cmd, want in FIXTURES:
        got, _ = decide(cmd)
        ok = got == want
        bad += 0 if ok else 1
        print("  %-4s want=%-5s got=%-5s  %s" % ("PASS" if ok else "FAIL", want, got, label))
        if not ok:
            print("        cmd: %s" % cmd)
    print("failures: %d" % bad)
    print("SELFTEST-SUMMARY suite=zsh_rev_modifier_guard checks=%d failures=%d" % (
        len(FIXTURES), bad))
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
