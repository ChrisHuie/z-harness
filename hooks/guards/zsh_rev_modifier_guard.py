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
Plus four flag letters that are inert alone but consume the base modifier after them:
    g f w F
so `$SHA:guards/g.py` -> DC185FEB4ards/g.py (`:gu`), and `frontend/` `functions/`
`flake.nix` `gradle/` `generated/` `graphql/` `web/` `wait/` all mangle the same way,
while `:go` `:gz` `:gitignore` `:foo` `:world` reach git untouched.

Uppercase `:W` takes a delimiter and is NOT modelled: `:Watch.py` and `:World/x` mangle,
`:Wa` and `:Warehouse/a.py` do not. A rev:path whose next segment starts with a capital W
is outside this guard.

Everything else after the colon is inert. The sets are re-derived from the installed zsh
by `--selftest`; they were hand-listed once and four letters were missing.

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
import shutil
import string
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from git_grep_engine_guard import (  # noqa: E402
    CommandParseError, MAX_PREFIX_DEPTH, nested_shell_invocation,
    fixture_pair_duplicates,
    source_has_dynamic_command_word, source_has_git_hazard_hint,
    split_commands, unwrap_command_prefix,
)

MODS = "aAcehlPqQrstu"
# Flag letters that carry no meaning alone but consume the base modifier that follows.
# Enumerated a-zA-Z against zsh 5.9 by asking whether `$v:<letters>rest` differs from the
# literal concatenation, which is the hazard's own shape. Omitting them read `$SHA:guards/`
# `$SHA:frontend/` `$SHA:flake.nix` `$SHA:gradle/` as inert while zsh mangled every one --
# `guards/` is a directory in this repository. They are a separate class rather than more
# MODS letters because alone they are harmless: `:go` `:gz` `:gitignore` `:foo` `:world`
# all reach git untouched, so folding them into MODS would deny correct commands.
MOD_PREFIXES = "gfwF"
# Uppercase `:W` is deliberately absent from both sets. It takes a delimiter, so what it
# consumes depends on the rest of the token: `:Watch.py` and `:World/x` mangle while
# `:Wa` and `:Warehouse/a.py` reach git intact. Neither "always" nor "only before a base
# modifier" describes it, and guessing would either miss a mangle or deny a correct path.
MOD_UNMODELLED = "W"
# unbraced parameter expansions, INCLUDING positionals and specials. $( is excluded.
EXPANSION = re.compile(
    r"\$(?:"
    r"[A-Za-z_][A-Za-z0-9_]*(?:\[[^\]]*\])?"   # $name  $name[1]
    r"|[0-9]+"                                  # $1 $2
    r"|[#?*@!$-]"                               # $# $? $* $@ $! $$ $-
    r")"
    r":[" + MOD_PREFIXES + r"]*([" + MODS + r"])")
# braced WITH the modifier inside: ${name:t} — mangles identically ("brace it" done
# wrong). POSIX forms ${name:-x} ${name:+x} ${name:=x} ${name:?x} ${name:0:2} do not
# collide: -, +, =, ?, digits are not modifier letters.
EXPANSION_BRACED = re.compile(
    r"\$\{(?:\([^}]*\))?"
    r"(?:[A-Za-z_][A-Za-z0-9_]*(?:\[[^\]]+\])?|[0-9]+|[#?*@!$-])"
    r":[" + MOD_PREFIXES + r"]*([" + MODS + r"])(?=\}[A-Za-z0-9]|[/:0-9])")
# The guard's own advice, applied one word too wide. Its deny text says "Brace the NAME
# only"; bracing the whole rev:path instead puts a path where zsh expects a modifier list,
# and zsh refuses the whole command -- `${SHA:tests/x.py}` is `unrecognized modifier`,
# `${SHA:src/f.py}` is `bad substitution`. A modifier letter followed by another letter
# inside the braces is that shape and nothing else: every POSIX form (`:-` `:=` `:?` `:+`
# `:0:2`) and every real modifier use (`:t}` `:s/a/b/`) was checked and none collide.
EXPANSION_BRACED_INVALID = re.compile(
    r"\$\{(?:[A-Za-z_][A-Za-z0-9_]*(?:\[[^\]]+\])?|[0-9]+|[#?*@!$-])"
    r":[" + MOD_PREFIXES + r"]*([" + MODS + r"])[A-Za-z]")

# git subcommands that take a `rev:path` / `rev:./path` argument
# How many `<shell> -c` layers this guard will unwrap. Reaching it returns `ask`, never
# `allow`: an input the guard cannot model is not a clean verdict.
NEST_DEPTH_LIMIT = 4

# Subcommands whose documented argument grammar contains a `X:Y` form, so a mangled colon
# expression silently changes which object is addressed. The refspec consumers were
# missing, which mattered most on `push`: it is the one that WRITES, and
# `$BRANCH:refs/heads/main` with BRANCH=feature/my-work.v2 was observed reaching git as
# `feature/my-workefs/heads/main` -- a different destination ref, no error.
REV_PATH_SUBCOMMANDS = {"show", "diff", "cat-file", "log", "ls-tree", "archive",
                        "checkout", "restore", "grep", "rev-parse", "blame",
                        # refspec `src:dst`
                        "push", "fetch", "pull",
                        # rev:path, same grammar as `diff`
                        "difftool"}

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
        for rx in (EXPANSION, EXPANSION_BRACED, EXPANSION_BRACED_INVALID):
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


def decide(command, _depth=0, _shell="zsh"):
    """-> (decision, reason), tracking the shell that expands each source layer."""
    try:
        commands = split_commands(command)
    except CommandParseError as exc:
        return ("ask", f"the Bash command cannot be parsed safely ({exc}); rewrite it "
                "as a direct command before proceeding.")
    for tokens in commands:
        resolution = unwrap_command_prefix(tokens)
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
        # Recurse BEFORE falling back to uncertainty. This short-circuited on `dynamic`
        # first, which cost enforcement in one direction and precision in the other:
        # `zsh -c 'SHA=x; git show $SHA:src/f.py'` is a proven hazard -- the inner zsh
        # applies `:s` whatever SHA holds -- and returned `ask` instead of `deny`, while
        # `sh -c 'echo $PATH'`, which contains no Git at all, also returned `ask`.
        if invocation.command:
            decision, reason = decide(invocation.command, _depth + 1, invocation.shell)
            if decision != "allow":
                return (decision, reason)
        # Only then does an uninspectable body matter, and only when Git is actually in
        # it. `descendant_git` is the same predicate the deny above is gated on.
        # sh, bash, dash and ksh apply no history modifier whatever the value expands
        # to, so an unresolved argument in their body is not this guard's hazard.
        if (not invocation.command
                or source_has_dynamic_command_word(invocation.command)):
            return ("ask", "a shell -c command string is empty or dynamic, so its Git "
                    "arguments cannot be inspected before execution")
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
    ("RED WRAPPER: eval body mangles - zsh reports `(eval):1: bad substitution`",
"SHA=x; eval 'git show $SHA:src/f.py'", "deny"),
    ("RED WRAPPER: eval double-quoted body expands in the outer zsh",
     "SHA=x; eval \"git show $SHA:src/f.py\"", "deny"),
    ("RED WRAPPER: builtin eval body mangles the same way",
"SHA=x; builtin eval 'git show $SHA:src/f.py'", "deny"),
    ("GREEN WRAPPER: eval of a non-Git body is outside this guard",
     "eval 'printf safe'", "allow"),
    ("GREEN WRAPPER: dynamic pattern under -P, the safe engine, has no hazard",
"eval \"git grep -P $PATTERN -- README.md\"", "allow"),
    ("GREEN WRAPPER: same under builtin eval",
"builtin eval \"git grep -P $PATTERN -- README.md\"", "allow"),
    ("ASK WRAPPER: single-quoted eval source is dynamic to eval",
     "eval '$CMD; git grep -P harness -- README.md'", "ask"),
    ("ASK WRAPPER: single-quoted builtin eval source is dynamic to eval",
     "builtin eval '$CMD; git grep -P harness -- README.md'", "ask"),
    ("GREEN NESTED: dynamic pattern under -P is already the remedy",
"sh -c \"git grep -P $PATTERN -- README.md\"", "allow"),
    ("GREEN NESTED: dynamic pattern under -P is already the remedy",
"zsh -c \"git grep -P $PATTERN -- README.md\"", "allow"),
    ("ASK NESTED: single-quoted sh -c source expands in sh",
     "sh -c '$CMD; git grep -P harness -- README.md'", "ask"),
    ("ASK NESTED: single-quoted bash -c source expands in bash",
     "bash -c '$CMD; git grep -P harness -- README.md'", "ask"),
    ("ASK NESTED: single-quoted zsh -c source expands in zsh",
     "zsh -c '$CMD; git grep -P harness -- README.md'", "ask"),
    ("GREEN NESTED: fully static eval source retains PCRE",
     "eval \"git grep -P 'harness\\b' -- README.md\"", "allow"),
    ("GREEN NESTED: fully static sh -c source retains PCRE",
     "sh -c \"git grep -P 'harness\\b' -- README.md\"", "allow"),
    ("GREEN NESTED: fully static zsh -c source retains PCRE",
     "zsh -c \"git grep -P 'harness\\b' -- README.md\"", "allow"),
    ("ASK WRAPPER: bare echo identity is not mechanically fixed",
     "SHA=x; echo git show $SHA:src/f.py", "ask"),
    ("ASK WRAPPER: bare printf identity is not mechanically fixed",
     "SHA=x; printf '%s\\n' git show $SHA:src/f.py", "ask"),
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
    ("GREEN WRAPPER: exact /usr/bin/printf identity is explicit",
     "/usr/bin/printf '%s\\n' 'printf() { git \"$@\"; }' git show HEAD:README.md",
     "allow"),
    ("GREEN WRAPPER: exact /bin/echo identity is explicit",
     "/bin/echo git show HEAD:README.md", "allow"),
    ("GREEN WRAPPER: command structurally bypasses an echo function",
     "echo() { git \"$@\"; }; command echo git show HEAD:README.md", "allow"),
    ("GREEN WRAPPER: builtin printf bypasses shell identity mutation",
     "alias printf=git; builtin printf '%s\\n' git show HEAD:README.md", "allow"),
    ("ASK WRAPPER: brace-body function leaves bare echo identity unresolved",
     "{ echo() { git \"$@\"; }; echo show HEAD:README.md; }", "ask"),
    ("ASK WRAPPER: subshell-body function leaves bare echo identity unresolved",
     "( echo() { git \"$@\"; }; echo show HEAD:README.md )", "ask"),
    ("ASK WRAPPER: eval-defined alias leaves bare echo identity unresolved",
     "eval 'alias echo=git'\necho show HEAD:README.md", "ask"),
    ("ASK WRAPPER: basename alone does not trust an arbitrary echo path",
     "SHA=x; /tmp/echo git show $SHA:src/f.py", "ask"),
    ("GREEN WRAPPER: an unmodelled launcher with no git in it is not this guard's business",
     "xargs ls -la", "allow"),
    # A nested shell mangles at a different moment depending on which shell it is.
    ("RED NESTED: sh -c body in double quotes - the OUTER zsh expands it first",
     'sh -c "SHA=x; git show $SHA:src/f.py"', "deny"),
    ("RED NESTED: inner zsh applies the modifier - `zsh:1: bad substitution`",
"zsh -c 'SHA=x; git show $SHA:src/f.py'", "deny"),
    ("GREEN NESTED: sh expands it, and sh has no history modifiers",
"sh -c 'SHA=x; git show $SHA:src/f.py'", "allow"),
    ("GREEN NESTED: bash expands it, and bash has no history modifiers",
"bash -c 'SHA=x; git show $SHA:src/f.py'", "allow"),
    ("RED NESTED: sh composes a zsh body - renders `git show :src/f.py`",
"sh -c 'zsh -c \"git show $SHA:src/f.py\"'", "deny"),
    ("RED NESTED: outer zsh mangles before sh ever runs",
"zsh -c 'sh -c \"git show $SHA:src/f.py\"'", "deny"),
    ("RED NESTED: bash composes a zsh body - renders `git show :src/f.py`",
"bash -c 'zsh -c \"git show $SHA:src/f.py\"'", "deny"),
    ("GREEN NESTED: neither sh nor bash applies a modifier",
"sh -c 'bash -c \"git show $SHA:src/f.py\"'", "allow"),
    ("GREEN NESTED: nested shell with no rev:path git inside",
     'sh -c "git status"', "allow"),
]


# Prefix-flag modifiers. Every RED path below was observed mangling under zsh 5.9 and
# every GREEN one reaching git intact; the guard and the shell were compared on all of
# them. `guards/` is a directory in this repository, so this was reachable from ordinary
# work, not only from a crafted string.
FIXTURES += [
    ("RED PREFIX: :gu via guards/ - a directory in this repo",
     "SHA=x; git show $SHA:guards/g.py", "deny"),
    ("RED PREFIX: :fr via frontend/", "SHA=x; git show $SHA:frontend/a.js", "deny"),
    ("RED PREFIX: :fu via functions/", "SHA=x; git show $SHA:functions/f.js", "deny"),
    ("RED PREFIX: :fl via flake.nix", "SHA=x; git show $SHA:flake.nix", "deny"),
    ("RED PREFIX: :gr via gradle/", "SHA=x; git show $SHA:gradle/b", "deny"),
    ("RED PREFIX: :ge via generated/", "SHA=x; git show $SHA:generated/x.ts", "deny"),
    ("RED PREFIX: :we via web/", "SHA=x; git show $SHA:web/x.ts", "deny"),
    ("RED PREFIX: :wa via wait/", "SHA=x; git show $SHA:wait/x", "deny"),
    ("RED PREFIX: braced form carries the prefix too",
     "SHA=x; git show ${SHA:fr}ontend/a.js", "deny"),
    # The flag letters are harmless alone. Folding them into MODS would deny these.
    ("GREEN PREFIX: :go is inert", "SHA=x; git show $SHA:go/main.go", "allow"),
    ("GREEN PREFIX: :gz is inert", "SHA=x; git show $SHA:gz/x", "allow"),
    ("GREEN PREFIX: :gi is inert", "SHA=x; git show $SHA:gitignore", "allow"),
    ("GREEN PREFIX: :fo is inert", "SHA=x; git show $SHA:foo/bar", "allow"),
    ("GREEN PREFIX: :wo is inert", "SHA=x; git show $SHA:world/x", "allow"),
    ("GREEN PREFIX: ordinary path is untouched",
     "SHA=x; git show $SHA:README.md", "allow"),
]


# Refspec and rev:path consumers. Each RED line was observed mangling under zsh 5.9; the
# push cases matter most because push WRITES, so a mangled refspec names a different
# destination ref and git reports no error.
FIXTURES += [
    ("RED REFSPEC: push destination silently rewritten",
     "B=feature/my-work.v2; git push origin $B:refs/heads/main", "deny"),
    ("RED REFSPEC: push tag refspec via :t",
     "T=v1.0; git push origin $T:tags/rel", "deny"),
    ("RED REFSPEC: fetch refspec", "R=origin.v2; git fetch $R:refs/remotes/x", "deny"),
    ("RED REFSPEC: pull refspec", "R=origin.v2; git pull $R:refs/remotes/x", "deny"),
    ("RED REVPATH: difftool takes rev:path like diff",
     "A=HEAD.v2; git difftool $A:src/f.py", "deny"),
    ("GREEN REFSPEC: a push with no expansion is untouched",
     "git push origin HEAD:refs/heads/main", "allow"),
    ("GREEN REFSPEC: braced NAME only is the safe spelling",
     "B=x; git push origin ${B}:refs/heads/main", "allow"),
    ("GREEN REFSPEC: an ordinary push is not this guard's business",
     "git push origin HEAD", "allow"),
]


# Deliberate modifiers versus a brace that closed one character early. Both spell
# `${name:mod}`, so the discriminator is what follows the closing brace: a letter or digit
# means the path continues into text the modifier already ate, which is the mistyped
# rev:path. A separator or end-of-token means the author asked for the modifier and got
# it. Flagging both denied `git show HEAD:${f:t}`, which zsh renders `HEAD:c.py` exactly
# as intended, and the deny text proposed a rewrite that produces a different string.
FIXTURES += [
    ("GREEN BRACE: deliberate :t, brace closes before the token ends",
     "f=/a/b/c.py; git show HEAD:${f:t}", "allow"),
    ("GREEN BRACE: deliberate :h in a -C argument",
     "repo=/x/y/z; git -C ${repo:h} log --oneline -5", "allow"),
    ("GREEN BRACE: deliberate :t as a pathspec",
     "f=/a/b/c.py; git log --oneline -- ${f:t}", "allow"),
    ("GREEN BRACE: separator after the brace is still deliberate",
     "f=/a/b/c.py; git show HEAD:${f:t}/x", "allow"),
    ("RED BRACE: closes one char early, path continues into the eaten text",
     "r=/a/b/c.py; git show ${r:t}ests/x", "deny"),
    ("RED BRACE: same shape with a prefix flag",
     "SHA=x; git show ${SHA:gu}ards/g.py", "deny"),
]


# Nested bodies with no Git in them. These returned `ask` purely for containing a `$`,
# which on Codex maps to a hard deny. The command word is what decides: an unknown
# executable is a real question, an unknown argument to a named command is not.
FIXTURES += [
    ("GREEN NESTED: sh -c with no Git at all", "sh -c 'echo $PATH'", "allow"),
    ("GREEN NESTED: bash -c with no Git at all", "bash -c 'echo $HOME'", "allow"),
    ("GREEN NESTED: sh -c listing a directory", "sh -c 'ls -la $DIR'", "allow"),
    ("GREEN NESTED: a literal Git command with no expansion", "sh -c 'git status'", "allow"),
    ("ASK NESTED: the executable itself comes from an expansion",
     'sh -c "$CMD"', "ask"),
    ("ASK NESTED: an empty -c body", 'sh -c ""', "ask"),
]


# The guard's own remedy applied one word too wide. zsh refuses these outright, so the
# command dies rather than addressing the wrong object -- and with `2>/dev/null` that
# death reads as "the file is absent", which is the failure this guard exists to stop.
FIXTURES += [
    ("RED BRACEWIDE: whole rev:path braced - zsh says unrecognized modifier",
     "git show ${SHA:tests/x.py}", "deny"),
    ("RED BRACEWIDE: whole rev:path braced - zsh says bad substitution",
     "git show ${SHA:src/f.py}", "deny"),
    ("RED BRACEWIDE: same with an archive path", "git show ${SHA:archive/x}", "deny"),
    ("GREEN BRACEWIDE: the advice done right, NAME only",
     "git show ${SHA}:tests/x.py", "allow"),
    ("GREEN BRACEWIDE: POSIX default form is not a modifier",
     "git show ${VAR:-default}", "allow"),
    ("GREEN BRACEWIDE: POSIX substring form is not a modifier",
     "git show HEAD:${VAR:0:2}", "allow"),
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
    (f"RED NESTED: the hazard is still provable at depth {NEST_DEPTH_LIMIT}",
     _nest(_HAZARD, NEST_DEPTH_LIMIT), "deny"),
    (f"ASK NESTED: hazard at depth {NEST_DEPTH_LIMIT + 1} cannot be proven either way",
     _nest(_HAZARD, NEST_DEPTH_LIMIT + 1), "ask"),
    (f"ASK NESTED: a benign command past the limit is also unprovable, not clean",
     _nest("git status", NEST_DEPTH_LIMIT + 1), "ask"),
    ("GREEN NESTED: a benign command at the last modelled depth still allows",
     _nest("git status", NEST_DEPTH_LIMIT), "allow"),
]


def check_modifier_sets_against_zsh():
    """Bind MODS and MOD_PREFIXES to what the installed zsh actually consumes.

    Return (failures, executed, skipped). The letters were originally hand-listed and were
    wrong: five that zsh consumes were missing. Enumerating a-zA-Z here is the only check
    that can catch the next such drift, because every other case in this file tests the
    tables against themselves.

    Probe shape is the hazard's own: `$v:<letters>rest` differing from the literal
    concatenation means zsh ate the colon expression. Skipped, counted, where zsh is
    absent -- the claim is about zsh, so on a host without it the claim is inapplicable
    rather than unproven.
    """
    # One probe GROUP either way. A conditionally-sized contribution made `checks` vary
    # by host, so the shrink-only floor read a zsh-less runner as a gutted suite; the
    # skip is reported in the printed line instead, where it is visible without moving
    # the number the floor compares against.
    if shutil.which("zsh") is None:
        return [], 0, 1

    def consumed(suffix):
        probe = subprocess.run(
            ["zsh", "-c", f'v=/a/b/c.py; print -r -- "$v:{suffix}"'],
            capture_output=True, timeout=10,
        )
        if probe.returncode != 0:
            return True
        expected = f"/a/b/c.py:{suffix}".encode("ascii")
        return probe.stdout.rstrip(b"\n") != expected

    failures = []
    modelled = set(MODS) | set(MOD_PREFIXES) | set(MOD_UNMODELLED)
    for char in string.ascii_letters:
        # A base modifier consumes on its own; a prefix letter only ahead of one.
        alone = consumed(char + "rest")
        if alone and char not in modelled:
            failures.append(
                f"zsh consumes `:{char}` but neither MODS nor MOD_PREFIXES models it, so "
                f"a rev:path whose next segment starts with {char!r} reaches git mangled")
        if not alone and char in MODS:
            failures.append(
                f"MODS claims `:{char}` is a modifier but this zsh leaves it literal, so "
                f"a correct rev:path starting with {char!r} is denied")
    for prefix in MOD_PREFIXES:
        if consumed(prefix + "o-x"):
            failures.append(
                f"MOD_PREFIXES treats `:{prefix}` as harmless alone, but this zsh consumed "
                f"`:{prefix}o-x`; it belongs in MODS instead")
        if not consumed(prefix + MODS[0] + "-x"):
            failures.append(
                f"MOD_PREFIXES expects `:{prefix}` to consume ahead of a base modifier, "
                f"but this zsh left `:{prefix}{MODS[0]}-x` literal")
    return failures, 1, 0


FIXTURES += [
    ("RED TOKEN: double-quoted substitution preserves zsh rev hazard",
     '/bin/echo "$(git show $SHA:src/f.py)"', "deny"),
    ("RED TOKEN: grouped substitution preserves later zsh rev hazard",
     '/bin/echo "$( (printf x); git show $SHA:src/f.py)"', "deny"),
    ("ASK TOKEN: case pattern closer is outside the shared tokenizer model",
     '/bin/echo "$(case x in x) git show $SHA:src/f.py;; esac)"', "ask"),
    ("RED TOKEN: backtick substitution preserves zsh rev hazard",
     "/bin/echo `git show $SHA:src/f.py`", "deny"),
    ("RED HEREDOC: zsh executes its stdin body",
     "zsh <<'EOF'\ngit show $SHA:src/f.py\nEOF\n", "deny"),
    ("RED HEREDOC: zsh -o option value still reads stdin",
     "zsh -o SH_WORD_SPLIT <<'EOF'\ngit show $SHA:src/f.py\nEOF\n", "deny"),
    ("GREEN HEREDOC: a data consumer does not execute zsh-looking stdin",
     "cat <<'EOF'\ngit show $SHA:src/f.py\nEOF\n", "allow"),
    ("GREEN HEREDOC: zsh -c does not execute its heredoc stdin",
     "zsh -c cat <<'EOF'\ngit show $SHA:src/f.py\nEOF\n", "allow"),
    ("RED HEREDOC: a literal pipeline feeds heredoc bytes to zsh",
     "cat <<'EOF' | zsh\ngit show $SHA:src/f.py\nEOF\n", "deny"),
    ("RED HEREDOC: unquoted data heredoc expands nested zsh hazard",
     "cat <<EOF\n$(git show $SHA:src/f.py)\nEOF\n", "deny"),
    ("GREEN HEREDOC: unquoted literal rev-looking text remains data",
     "cat <<EOF\ngit show $SHA:src/f.py\nEOF\n", "allow"),
    ("RED HEREDOC: quoted dashed delimiter feeds zsh stdin",
     "zsh <<'END-MARK'\ngit show $SHA:src/f.py\nEND-MARK\n", "deny"),
    ("GREEN HEREDOC: quoted dashed delimiter feeds a data consumer",
     "cat <<'END-MARK'\ngit show $SHA:src/f.py\nEND-MARK\n", "allow"),
    ("RED HEREDOC: unquoted dashed data delimiter expands a rev hazard",
     "cat <<END-MARK\n$(git show $SHA:src/f.py)\nEND-MARK\n", "deny"),
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
    duplicates = fixture_pair_duplicates(FIXTURES)
    uniqueness_ok = bool(FIXTURES) and not duplicates
    bad += 0 if uniqueness_ok else 1
    print("  %-4s fixture command/expected pairs are non-empty and unique"
          % ("PASS" if uniqueness_ok else "FAIL"))
    if duplicates:
        print("        duplicate pairs: %r" % duplicates)
    modifier_failures, modifier_checks, modifier_skips = check_modifier_sets_against_zsh()
    bad += len(modifier_failures)
    for failure in modifier_failures:
        print("  FAIL modifier set vs installed zsh: %s" % failure)
    if modifier_skips:
        print("  SKIP modifier set vs installed zsh: no zsh on this host; "
              "the letters are unverified here")
    elif not modifier_failures:
        print("  PASS MODS and MOD_PREFIXES match the installed zsh "
              "(%d letters, %d prefixes probed)" % (len(string.ascii_letters),
                                                    len(MOD_PREFIXES)))
    # Exercise the skip path itself, so "zsh absent" cannot drift into a silent pass and
    # cannot change the number the floor compares against.
    original_which = shutil.which
    shutil.which = lambda name: None if name == "zsh" else original_which(name)
    try:
        absent_failures, absent_executed, absent_skipped = (
            check_modifier_sets_against_zsh())
    finally:
        shutil.which = original_which
    absent_ok = (not absent_failures and absent_executed == 0 and absent_skipped == 1)
    bad += 0 if absent_ok else 1
    print("  %-4s a zsh-less host skips the probe and reports the same check count"
          % ("PASS" if absent_ok else "FAIL"))

    # Some modifier spellings make zsh emit arbitrary bytes. Drive that through the
    # production subprocess call site: decoding as UTF-8 used to crash before the suite
    # receipt, and whether it crashed depended on set iteration order. The fake models
    # the declared tables, then returns invalid UTF-8 for one extra consumed letter so
    # the probe must report a deterministic semantic mismatch rather than skip or crash.
    original_run = subprocess.run
    original_which = shutil.which
    byte_probe_calls = []
    def byte_probe(args, **kwargs):
        byte_probe_calls.append((args, kwargs))
        suffix = args[2].split('$v:', 1)[1].rsplit('"', 1)[0]
        consumed = (
            suffix[0] in MODS + MOD_UNMODELLED
            or (suffix[0] in MOD_PREFIXES
                and len(suffix) > 1 and suffix[1] in MODS)
        )
        if suffix == "xrest":
            stdout = b"/a/b/c.py:\xf8rest\n"
        elif consumed:
            stdout = b"consumed\n"
        else:
            stdout = f"/a/b/c.py:{suffix}\n".encode("ascii")
        return subprocess.CompletedProcess(args, 0, stdout=stdout, stderr=b"")
    shutil.which = lambda name: "/fake/zsh" if name == "zsh" else original_which(name)
    subprocess.run = byte_probe
    try:
        byte_failures, byte_executed, byte_skipped = check_modifier_sets_against_zsh()
    finally:
        subprocess.run = original_run
        shutil.which = original_which
    byte_probe_ok = (
        byte_executed == 1
        and byte_skipped == 0
        and len(byte_failures) == 1
        and "starts with 'x'" in byte_failures[0]
        and len(byte_probe_calls) == len(string.ascii_letters) + 2 * len(MOD_PREFIXES)
        and all(
            kwargs == {"capture_output": True, "timeout": 10}
            for _args, kwargs in byte_probe_calls
        )
    )
    bad += 0 if byte_probe_ok else 1
    print("  %-4s modifier probe handles non-UTF-8 bytes through its production call site"
          % ("PASS" if byte_probe_ok else "FAIL"))

    checks = len(FIXTURES) + 4
    print("failures: %d" % bad)
    print("SELFTEST-SUMMARY suite=zsh_rev_modifier_guard checks=%d failures=%d" % (
        checks, bad))
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
