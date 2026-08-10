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
import os
import re
import shlex
import shutil
import string
import subprocess
import sys
import tempfile
from typing import NamedTuple

PCRE_ONLY = re.compile(r"\\[bBdDsSwWAZzhHvVR]|\(\?[:=!<Pi#'-]")
UNRESOLVED = re.compile(r"\$[A-Za-z_{(]|`")

MAX_COMMAND_CHARS = 1024 * 1024
MAX_SUBCOMMANDS = 16384
MAX_TOKENS = 65536
MAX_PREFIX_DEPTH = 8
MAX_ENV_SPLITS = 4


class CommandParseError(ValueError):
    """The Bash source cannot be tokenized within the guard's closed limits."""


class PrefixResolution(NamedTuple):
    """One resolved command boundary shared by both Bash predicates."""

    items: list
    command_env: dict
    errors: tuple
    hazard_hint: bool


class ShellInvocation(NamedTuple):
    shell: str
    command: str
    dynamic: bool


# git grep uses parse-options(3): single-dash short flags cluster, and -e/-f take their
# argument attached to the cluster when anything follows the letter. Matching only the
# separated spellings let `-e'harness\b'` and `-fpatterns.txt` through with the pattern
# never entering `patterns`, so the engine check ran against an empty list and allowed.
#
# Every letter below was measured against git 2.46.1 on this host rather than recalled;
# an earlier draft of this table guessed and was wrong in both directions -- it omitted
# -o, -p and -W, which allowed `git grep -EWe'harness\b'`, and it listed -O as taking no
# argument, which denied a command carrying no pattern hazard at all.
GREP_SHORT_ENGINE = {"E": "E", "F": "F", "G": "G", "P": "P"}
GREP_SHORT_PATTERN_ARG = {"e", "f"}
# These options accept either a separated number or an attached decimal suffix. A decimal
# suffix with no option letter is Git's `-NUM` context shorthand and may follow another
# clustered flag (`-E3`).
GREP_SHORT_VALUE = set("mABC")
GREP_SHORT_NOARG = set("achilnopqrvwzHILW")
GREP_SHORT_OPTIONAL_VALUE = {"O"}
GREP_LONG_ENGINE = {
    "--basic-regexp": "G",
    "--extended-regexp": "E",
    "--fixed-strings": "F",
    "--perl-regexp": "P",
}
GREP_LONG_NEGATED_ENGINE = {
    "--no-basic-regexp", "--no-extended-regexp",
    "--no-fixed-strings", "--no-perl-regexp",
}
# Git accepts a long option's unique prefix, but uniqueness is over the whole command's
# option table rather than this guard's four engine options. In particular `--ext` is
# ambiguous with `--ext-grep`, while `--extended` resolves to `--extended-regexp`.
GREP_LONG_BOOLEAN_OPTIONS = {
    "--cached", "--untracked", "--exclude-standard", "--recurse-submodules",
    "--invert-match", "--ignore-case", "--word-regexp", "--text", "--textconv",
    "--recursive", "--basic-regexp", "--extended-regexp", "--fixed-strings",
    "--perl-regexp", "--line-number", "--column", "--full-name",
    "--files-with-matches", "--name-only", "--files-without-match", "--null",
    "--only-matching", "--count", "--color", "--break", "--heading", "--context",
    "--before-context", "--after-context", "--threads", "--show-function",
    "--function-context", "--quiet", "--all-match", "--open-files-in-pager",
    "--ext-grep", "--max-count",
}
GREP_LONG_OPTION_NAMES = {
    "--no-index", "--index", "--max-depth", "--regexp", "--file", "--and",
    "--or", "--not",
}
GREP_LONG_OPTION_NAMES.update(GREP_LONG_BOOLEAN_OPTIONS)
GREP_LONG_OPTION_NAMES.update(
    "--no-" + option[2:] for option in GREP_LONG_BOOLEAN_OPTIONS
)
GREP_LONG_PATTERN_ARG = {"--regexp": "e", "--file": "f"}
GREP_LONG_REQUIRED_VALUE = {
    "--max-depth", "--threads", "--max-count", "--after-context",
    "--before-context", "--context",
}
# Git's parse-options optional arguments are attached with `=`. A bare optional option
# never consumes the next argv token; treating it as required hid a following `-E`.
GREP_LONG_OPTIONAL_VALUE = {"--color", "--open-files-in-pager"}


def short_option_cluster(text):
    """Parse a single-dash git grep short-option cluster.

    -> (engine letters in order, kind, terminating letter, attached argument), where kind
    is "pattern" for -e/-f, "value" for a numeric option, "optional" for -O, or
    "plain" when the cluster has only no-argument flags and `-NUM` runs. The attached
    argument is populated for `-ePATTERN`, `-m1`, `-A3`, and `-Opager`. Returns None when
    the cluster is invalid or contains a letter this guard does not model.

    Engines are returned in order because git applies last-one-wins: `-EG` greps as BRE
    and is harmless, `-GE` greps as ERE and is the hazard.
    """
    if len(text) < 2 or not text.startswith("-") or text.startswith("--"):
        return None
    engines = []
    index = 1
    while index < len(text):
        char = text[index]
        suffix = text[index + 1:]
        if char in GREP_SHORT_PATTERN_ARG:
            return (engines, "pattern", char, suffix or None)
        if char in GREP_SHORT_VALUE:
            if suffix and not suffix.isdecimal():
                return None
            return (engines, "value", char, suffix or None)
        if char.isdecimal():
            # Git's -NUM context shorthand consumes the maximal digit run, not the
            # cluster remainder. `-12EePATTERN` is -12, -E, -ePATTERN; stopping at the
            # first digits hid both the later engine and the attached pattern.
            index += 1
            while index < len(text) and text[index].isdecimal():
                index += 1
            continue
        if char in GREP_SHORT_OPTIONAL_VALUE:
            return (engines, "optional", char, suffix or None)
        if char in GREP_SHORT_ENGINE:
            engines.append(GREP_SHORT_ENGINE[char])
            index += 1
            continue
        if char in GREP_SHORT_NOARG:
            index += 1
            continue
        return None
    return (engines, "plain", None, None)


def long_engine_option(text):
    """Return (engine, uncertain) for an exact or uniquely abbreviated long option.

    `uncertain` means the token is a prefix of an engine option but Git cannot resolve it
    uniquely. Callers retain that uncertainty until they have inspected the pattern.
    """
    name, separator, _value = text.partition("=")
    candidates = {option for option in GREP_LONG_OPTION_NAMES
                  if option.startswith(name)}
    canonical = name if name in GREP_LONG_OPTION_NAMES else (
        next(iter(candidates)) if len(candidates) == 1 else None
    )
    engine_names = set(GREP_LONG_ENGINE) | GREP_LONG_NEGATED_ENGINE
    engine_candidates = candidates & engine_names
    if separator and (canonical in engine_names or engine_candidates):
        return None, True
    if canonical in GREP_LONG_ENGINE:
        return GREP_LONG_ENGINE[canonical], False
    if canonical in GREP_LONG_NEGATED_ENGINE:
        return "B", False
    return None, bool(engine_candidates)


def split_commands(cmd):
    """Split on UNQUOTED && || ; | newline ( ) and yield token lists.

    Tokens are (text, quoting) where quoting is one of '', "'", '"'.
    Heredoc bodies are dropped: a `<<'EOF' ... EOF` payload is not argv.
    """
    if not isinstance(cmd, str):
        raise CommandParseError("command source is not text")
    if len(cmd) > MAX_COMMAND_CHARS:
        raise CommandParseError(
            f"command source exceeds the {MAX_COMMAND_CHARS}-byte parse limit")
    out, cur = [], []
    tok_parts, tok_mode_parts, tok_modes, q, i = [], [], set(), "", 0
    token_count = 0
    # strip heredoc bodies so python/EOF payloads never reach the tokenizer
    cmd = re.sub(r"<<-?\s*'?\"?([A-Za-z_][A-Za-z0-9_]*)'?\"?\n.*?\n\1\b",
                 " __HEREDOC__ ", cmd, flags=re.S)
    n = len(cmd)

    def append_tok(text, mode=""):
        if text:
            tok_parts.append(text)
            tok_mode_parts.append({"": "U", "'": "S", '"': "D", "escaped": "E"}[mode]
                                  * len(text))
            tok_modes.add(mode)

    def flush_tok():
        nonlocal tok_parts, tok_mode_parts, tok_modes, token_count
        if tok_parts or tok_modes:
            token_count += 1
            if token_count > MAX_TOKENS:
                raise CommandParseError(
                    f"command source exceeds the {MAX_TOKENS}-token parse limit")
            quoting = (next(iter(tok_modes)) if len(tok_modes) == 1
                       else "mixed:" + "".join(tok_mode_parts))
            cur.append(("".join(tok_parts), quoting))
        tok_parts, tok_mode_parts, tok_modes = [], [], set()

    def flush_cmd():
        nonlocal cur
        flush_tok()
        if cur:
            out.append(cur)
            if len(out) > MAX_SUBCOMMANDS:
                raise CommandParseError(
                    f"command source exceeds the {MAX_SUBCOMMANDS}-subcommand parse limit")
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
                append_tok(cmd[i + 1], "escaped")
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
            if depth:
                raise CommandParseError("command source has an unclosed parameter expansion")
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
    if q:
        raise CommandParseError("command source has an unclosed quote")
    flush_cmd()
    return out


CONTROL_KEYWORDS = {"do", "then", "else", "elif", "if", "while", "until", "time",
                    "nocorrect", "noglob"}
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
SHELLS = {"sh", "bash", "zsh", "dash", "ksh"}
GIT_HAZARD_SUBCOMMANDS = {
    "grep", "show", "diff", "cat-file", "log", "ls-tree", "archive", "checkout",
    "restore", "rev-parse", "blame",
}
# A bare name is not an identity: aliases and functions can replace it before execution.
# Only `builtin`/structurally parsed `command` or these exact system paths may carry a
# guarded-looking argv without becoming `ask`; selftest executes every accepted identity.
SHELL_NON_FORWARDING_COMMANDS = {"echo", "printf"}
TRUSTED_EXTERNAL_NON_FORWARDING_COMMANDS = {"/bin/echo", "/usr/bin/printf"}
EXEC_WRAPPERS = {
    # option flags, options consuming the next argv, attached value prefixes,
    # bundled short flags, positional operands before the command
    "nohup": (set(), set(), (), "", 0),
    "timeout": (
        {"--foreground", "--preserve-status", "--verbose"},
        {"-k", "--kill-after", "-s", "--signal"},
        ("--kill-after=", "--signal=", "-k", "-s"),
        "",
        1,
    ),
    "stdbuf": (
        set(),
        {"-i", "-o", "-e", "--input", "--output", "--error"},
        ("--input=", "--output=", "--error=", "-i", "-o", "-e"),
        "",
        0,
    ),
    "setsid": (
        {"-c", "--ctty", "-f", "--fork", "-w", "--wait"},
        set(),
        (),
        "cfw",
        0,
    ),
    "caffeinate": (
        {"-d", "-i", "-m", "-s", "-u"},
        {"-t", "-w"},
        ("-t", "-w"),
        "dimsu",
        0,
    ),
    # Flags read from `sudo --help` on this host rather than recalled. sudo runs the
    # command in the same argv the outer shell already expanded, so a wrapped git is the
    # same invocation and was previously invisible to both guards.
    "sudo": (
        {"-A", "--askpass", "-b", "--background", "-B", "--bell", "-E",
         "--preserve-env", "-H", "--set-home", "-i", "--login", "-K",
         "--remove-timestamp", "-k", "--reset-timestamp", "-n",
         "--non-interactive", "-P", "--preserve-groups", "-S", "--stdin",
         "-s", "--shell"},
        {"-C", "--close-from", "-D", "--chdir", "-g", "--group", "-h", "--host",
         "-p", "--prompt", "-R", "--chroot", "-T", "--command-timeout",
         "-U", "--other-user", "-u", "--user"},
        ("--close-from=", "--chdir=", "--group=", "--host=", "--prompt=",
         "--chroot=", "--command-timeout=", "--other-user=", "--user=",
         "--preserve-env=", "-C", "-D", "-g", "-h", "-p", "-R", "-T", "-U", "-u"),
        "AbBEHiKknPSs",
        0,
    ),
}
WRAPPER_TERMINAL_OPTIONS = {"--help", "--version"}
# Launchers that do run the command that follows but whose argv rewriting this guard does
# not model. Peeling them by guesswork would mis-locate the command, and ignoring them
# returns allow for a wrapped invocation, so they are reported as an unresolved prefix and
# the decision becomes `ask`.
UNMODELLED_EXEC_WRAPPERS = {"xargs", "script", "strace", "dtruss", "ltrace", "watch",
                            "parallel", "flock", "chroot", "unshare", "doas", "runuser",
                            "su", "systemd-run", "ssh"}

def _literal_git_word(word):
    return (os.path.basename(word) == "git"
            or bool(re.search(r"(?:^|\s)(?:/[^\s]*/)?git(?:\s|$)", word)))


def has_literal_guarded_git_tail(tokens):
    """Whether argv visibly contains `git` followed by a guarded subcommand."""
    words = [text for text, _quoting in tokens]
    for index, word in enumerate(words):
        if os.path.basename(word) != "git":
            continue
        if any(os.path.basename(tail) in GIT_HAZARD_SUBCOMMANDS
               for tail in words[index + 1:]):
            return True
    return False


def command_has_git_hazard_hint(tokens):
    """True when unresolved command discovery could conceal a relevant Git invocation."""
    words = [text for text, _quoting in tokens]
    if any(_literal_git_word(word) for word in words):
        return True
    if has_dynamic_guarded_command_tail(tokens):
        return True
    meaningful = [word for word in words
                  if word not in CONTROL_KEYWORDS and not ASSIGNMENT.match(word)]
    if not meaningful or not UNRESOLVED.search(meaningful[0]):
        return False
    return any(os.path.basename(word) in GIT_HAZARD_SUBCOMMANDS
               for word in meaningful[1:])


def source_has_git_hazard_hint(command):
    """Conservative Git-hazard hint for a nested command source string."""
    try:
        commands = split_commands(command)
    except CommandParseError:
        return True
    return any(command_has_git_hazard_hint(tokens) for tokens in commands)


def _token_has_live_unresolved(token):
    """Whether a token has an expansion active in its recorded quoting mode."""
    text, quoting = token
    if quoting == "'" or quoting == "escaped":
        return False
    if quoting.startswith("mixed:"):
        modes = quoting.split(":", 1)[1]
    else:
        modes = {"": "U", "'": "S", '"': "D"}.get(quoting, "E") * len(text)
    return any(any(mode in "UD" for mode in modes[match.start():match.end()])
               for match in UNRESOLVED.finditer(text))


def source_has_live_unresolved(source):
    """Inspect command source as the downstream shell or eval will parse it."""
    try:
        commands = split_commands(source)
    except CommandParseError:
        return True
    return any(_token_has_live_unresolved(token) for tokens in commands
               for token in tokens)


def has_dynamic_guarded_command_tail(tokens):
    """Whether a live expansion may choose an executable before a guarded operation."""
    words = [text for text, _quoting in tokens]
    for index, token in enumerate(tokens):
        if not _token_has_live_unresolved(token):
            continue
        if any(os.path.basename(word) in GIT_HAZARD_SUBCOMMANDS
               for word in words[index + 1:]):
            return True
    return False


def _split_env_string(value):
    if len(value) > MAX_COMMAND_CHARS:
        raise CommandParseError("env -S string exceeds the command parse limit")
    try:
        words = shlex.split(value, posix=True)
    except ValueError as exc:
        raise CommandParseError(f"env -S string cannot be parsed ({exc})") from exc
    if not words:
        raise CommandParseError("env -S string resolves to no arguments")
    if len(words) > MAX_TOKENS:
        raise CommandParseError("env -S string exceeds the token parse limit")
    return [(word, "") for word in words]


def unwrap_command_prefix(tokens):
    """Resolve the executable boundary shared by both guards.

    The result retains uncertainty instead of guessing through a dynamic executable,
    malformed wrapper, or argv-rewriting launcher. Callers combine that uncertainty with
    `hazard_hint` and return `ask` rather than treating an unresolved command as clean.
    """
    original = list(tokens)
    items = list(tokens)
    command_env = dict(os.environ)
    errors = []
    guarded_prefix_hazard = False
    wrapper_depth = 0
    env_splits = 0
    command_bypass_next = False
    while items:
        while items and items[0][0] in CONTROL_KEYWORDS:
            items.pop(0)
        while items and ASSIGNMENT.match(items[0][0]):
            key, value = items.pop(0)[0].split("=", 1)
            command_env[key] = value
        if not items:
            break

        bypasses_shell_identity = command_bypass_next
        command_bypass_next = False
        executable_text = items[0][0]
        if UNRESOLVED.search(executable_text):
            errors.append(f"dynamic executable {executable_text!r} cannot be resolved")
            break
        executable = os.path.basename(executable_text)

        if executable == "builtin":
            wrapper_depth += 1
            items.pop(0)
            if not items:
                break
            if items[0][0] == "--":
                items.pop(0)
                if not items:
                    break
            if items[0][0] in {"command", "exec"}:
                continue
            if items[0][0] == "eval":
                break
            if items[0][0].startswith("-"):
                errors.append(f"unmodelled builtin option {items[0][0]!r}")
            else:
                # `builtin NAME` refuses to run an external command.
                items.clear()
            break

        if executable == "command":
            wrapper_depth += 1
            items.pop(0)
            terminal = False
            while items:
                word = items[0][0]
                if word == "--":
                    items.pop(0)
                    break
                if word == "-p" or re.fullmatch(r"-p+", word):
                    items.pop(0)
                    continue
                if word in {"-v", "-V", "--version"} or (
                        re.fullmatch(r"-[pvV]+", word) and any(c in word for c in "vV")):
                    items.clear()
                    terminal = True
                    break
                if word.startswith("-"):
                    errors.append(f"unmodelled command option {word!r}")
                break
            if terminal or errors:
                break
            command_bypass_next = True
            continue

        if executable == "exec":
            wrapper_depth += 1
            items.pop(0)
            while items:
                word = items[0][0]
                if word == "--":
                    items.pop(0)
                    break
                if word == "-a":
                    items.pop(0)
                    if not items:
                        errors.append("exec -a is missing argv0")
                        break
                    items.pop(0)
                    continue
                if word in {"-c", "-l"} or re.fullmatch(r"-[cl]+", word):
                    items.pop(0)
                    continue
                if word.startswith("-"):
                    errors.append(f"unmodelled exec option {word!r}")
                break
            if errors:
                break
            continue

        if executable == "env":
            wrapper_depth += 1
            items.pop(0)
            while items:
                word = items[0][0]
                if word == "--":
                    items.pop(0)
                    break
                if word in {"-i", "--ignore-environment"}:
                    command_env = {}
                    items.pop(0)
                    continue
                if word in {"-u", "--unset", "-C", "--chdir"}:
                    option = items.pop(0)[0]
                    if not items:
                        errors.append(f"{option} is missing its argument")
                        break
                    value = items.pop(0)[0]
                    if option in {"-u", "--unset"}:
                        command_env.pop(value, None)
                    continue
                if word.startswith("--unset="):
                    command_env.pop(word.split("=", 1)[1], None)
                    items.pop(0)
                    continue
                if word.startswith("--chdir="):
                    items.pop(0)
                    continue
                split_value = None
                if word in {"-S", "--split-string"}:
                    option = items.pop(0)[0]
                    if not items:
                        errors.append(f"env {option} is missing its argument")
                        break
                    split_value = items.pop(0)[0]
                elif word.startswith("--split-string="):
                    split_value = word.split("=", 1)[1]
                    items.pop(0)
                elif word.startswith("-S") and word != "-S":
                    split_value = word[2:]
                    items.pop(0)
                if split_value is not None:
                    env_splits += 1
                    if env_splits > MAX_ENV_SPLITS:
                        errors.append(
                            f"env -S nesting exceeds the limit of {MAX_ENV_SPLITS}")
                        break
                    try:
                        items = _split_env_string(split_value) + items
                    except CommandParseError as exc:
                        errors.append(str(exc))
                        break
                    continue
                if word.startswith("-"):
                    errors.append(f"unmodelled env option {word!r}")
                    break
                if ASSIGNMENT.match(word):
                    key, value = items.pop(0)[0].split("=", 1)
                    command_env[key] = value
                    continue
                break
            if errors:
                break
            continue

        if executable == "nice":
            wrapper_depth += 1
            items.pop(0)
            while items:
                word = items[0][0]
                if word == "--":
                    items.pop(0)
                    break
                if word in {"-n", "--adjustment"}:
                    option = items.pop(0)[0]
                    if not items:
                        errors.append(f"{option} is missing its argument")
                        break
                    items.pop(0)
                    continue
                if word.startswith("--adjustment=") or re.fullmatch(r"-\d+", word):
                    items.pop(0)
                    continue
                if word.startswith("-"):
                    errors.append(f"unmodelled nice option {word!r}")
                break
            if errors:
                break
            continue

        if executable in EXEC_WRAPPERS:
            wrapper_depth += 1
            flags, value_options, attached_prefixes, short_flags, positionals = (
                EXEC_WRAPPERS[executable]
            )
            items.pop(0)
            terminal = False
            while items:
                word = items[0][0]
                if word in WRAPPER_TERMINAL_OPTIONS:
                    # These options print wrapper-owned output and never execute
                    # a following command, so there is no nested Git invocation.
                    items.clear()
                    terminal = True
                    break
                if word == "--":
                    items.pop(0)
                    break
                if word in flags or (short_flags and re.fullmatch(
                        rf"-[{re.escape(short_flags)}]+", word)):
                    items.pop(0)
                    continue
                if word in value_options:
                    option = items.pop(0)[0]
                    if not items:
                        errors.append(f"{executable} {option} is missing its argument")
                        break
                    items.pop(0)
                    continue
                if any(word.startswith(prefix) and word != prefix
                       for prefix in attached_prefixes):
                    items.pop(0)
                    continue
                if word.startswith("-"):
                    errors.append(f"unmodelled {executable} option {word!r}")
                break
            if terminal or errors:
                break
            for _index in range(positionals):
                if not items:
                    errors.append(f"{executable} is missing a required operand before COMMAND")
                    break
                items.pop(0)
            if errors:
                break
            continue

        if executable in UNMODELLED_EXEC_WRAPPERS:
            # Do not guess where the command starts; say so and let the caller ask.
            errors.append(
                f"{executable!r} launches the command that follows, and this guard does "
                f"not model how it rewrites argv")
            break

        if executable == "eval":
            break

        explicit_harmless = (
            executable_text in TRUSTED_EXTERNAL_NON_FORWARDING_COMMANDS
            or (bypasses_shell_identity and executable_text == executable
                and executable in SHELL_NON_FORWARDING_COMMANDS)
        )
        bare_identity_hazard = (
            executable_text == executable
            and executable in SHELL_NON_FORWARDING_COMMANDS
            and (command_has_git_hazard_hint(items)
                 or any(os.path.basename(word) in GIT_HAZARD_SUBCOMMANDS
                        for word, _quoting in items[1:]))
        )
        if (executable != "git" and not explicit_harmless
                and (has_literal_guarded_git_tail(items)
                     or has_dynamic_guarded_command_tail(items)
                     or bare_identity_hazard)):
            errors.append(
                f"command identity {executable_text!r} is not an explicit builtin or "
                "verified external harmless command before a guarded Git operation")
            guarded_prefix_hazard = True
            break

        break
    if wrapper_depth > MAX_PREFIX_DEPTH:
        errors.append(f"more than {MAX_PREFIX_DEPTH} nested command wrappers")
    return PrefixResolution(
        items, command_env, tuple(errors),
        command_has_git_hazard_hint(original) or guarded_prefix_hazard)


def nested_shell_invocation(resolution, current_shell="sh"):
    """Return the resolved shell and its `-c` body, if this command invokes one."""
    if resolution.errors or not resolution.items:
        return None
    shell = os.path.basename(resolution.items[0][0])
    if shell == "eval":
        args = resolution.items[1:]
        if args and args[0][0] == "--":
            args = args[1:]
        return ShellInvocation(
            current_shell,
            " ".join(word for word, _quoting in args),
            source_has_live_unresolved(
                " ".join(word for word, _quoting in args)),
        )
    if shell not in SHELLS:
        return None
    args = resolution.items[1:]
    for index, (word, _quoting) in enumerate(args):
        if word == "--":
            continue
        if word == "-c" or (word.startswith("-") and not word.startswith("--")
                             and "c" in word[1:]):
            command_arg = args[index + 1] if index + 1 < len(args) else ("", "")
            return ShellInvocation(
                shell, command_arg[0], source_has_live_unresolved(command_arg[0]))
    return None

def git_grep_argv(tokens, resolution=None):
    """-> (argv after git grep, config values, unresolved relevant config),
    or None when this subcommand is not a git grep."""
    resolution = resolution or unwrap_command_prefix(tokens)
    items = resolution.items
    command_env = resolution.command_env
    words = [t for t, _ in items]
    if not words:
        return None
    j = 0
    if resolution.errors:
        if resolution.hazard_hint:
            return [], [], list(resolution.errors)
        return None
    if os.path.basename(words[j]) != "git":
        return None
    j += 1
    configs = []
    unresolved_configs = []

    count_text = command_env.get("GIT_CONFIG_COUNT")
    if count_text is not None:
        try:
            count = int(count_text)
            if count < 0:
                raise ValueError
        except ValueError:
            unresolved_configs.append("GIT_CONFIG_COUNT is not a non-negative integer")
            count = 0
        for index in range(count):
            key = command_env.get(f"GIT_CONFIG_KEY_{index}")
            value = command_env.get(f"GIT_CONFIG_VALUE_{index}")
            if key is None or value is None:
                unresolved_configs.append(f"GIT_CONFIG_KEY/VALUE_{index} is incomplete")
            else:
                configs.append(f"{key}={value}")

    def add_config_env(spec):
        key, separator, env_name = spec.partition("=")
        if not separator or not env_name:
            unresolved_configs.append(f"malformed --config-env {spec!r}")
            return
        if env_name in command_env:
            configs.append(f"{key}={command_env[env_name]}")
        elif key.strip().lower() in {"grep.patterntype", "grep.extendedregexp"}:
            unresolved_configs.append(
                f"--config-env for {key} references unavailable {env_name}"
            )

    options_with_args = {
        "-C", "-c", "--git-dir", "--work-tree", "--namespace", "--super-prefix",
        "--exec-path", "--config-env", "--attr-source",
    }
    while j < len(words) and words[j].startswith("-"):
        option = words[j]
        if option == "--":
            j += 1
            break
        if option in options_with_args:
            if j + 1 >= len(words):
                return None
            if option == "-c":
                configs.append(words[j + 1])
            elif option == "--config-env":
                add_config_env(words[j + 1])
            j += 2
            continue
        if option.startswith("--config-env="):
            add_config_env(option.split("=", 1)[1])
            j += 1
            continue
        # Attached long-option values and no-argument global switches such as
        # --no-pager, -P, --literal-pathspecs and --no-optional-locks all leave
        # the following git subcommand in the next argv slot.
        j += 1
    if j >= len(words) or words[j] != "grep":
        return None
    return items[j + 1:], configs, unresolved_configs


CONFIG_ENGINE = {"extended": "E", "ere": "E", "perl": "P", "pcre": "P",
                 "fixed": "F", "basic": "B", "default": "B"}


def git_config_bool_is_false(value):
    """Recognize Git's false spellings; everything else fails closed as true.

    Git accepts non-zero decimal, signed, hexadecimal, octal, and scaled numeric
    booleans.  A four-string true allowlist is therefore unsafe.  We only allow
    the documented false words and numeric zero aliases; invalid spellings are
    conservatively treated as enabling ERE, matching the guard's fail-closed role.
    """
    val = value.strip().lower()
    if val in {"", "false", "no", "off"}:
        return True
    numeric = re.fullmatch(
        r"([+-]?(?:0[xX][0-9a-fA-F]+|0[0-7]*|[0-9]+))(?:[kKmMgG])?", val
    )
    if not numeric:
        return False
    try:
        number = int(numeric.group(1), 0)
    except ValueError:
        number = int(numeric.group(1), 10)
    return number == 0


def decide(command, _shell_depth=0):
    """-> (decision, reason). decision in {allow, deny, ask}."""
    if _shell_depth > 4:
        return ("ask", "nested shell -c depth exceeds the git-grep guard's model; "
                "verify the command or invoke git grep directly with -P.")
    try:
        commands = split_commands(command)
    except CommandParseError as exc:
        return ("ask", f"the Bash command cannot be parsed safely ({exc}); "
                "rewrite it as a direct command before proceeding.")
    for tokens in commands:
        resolution = unwrap_command_prefix(tokens)
        if resolution.errors and resolution.hazard_hint:
            return ("ask", "a possible Git invocation crosses an unresolved command "
                    "prefix (" + "; ".join(resolution.errors) + "); invoke Git directly "
                    "so the pattern engine can be verified.")
        invocation = nested_shell_invocation(resolution)
        if invocation is not None:
            if not invocation.command:
                return ("ask", "a shell -c wrapper is missing its command string")
            if invocation.dynamic:
                return ("ask", "a shell -c command string is dynamic, so the Git grep "
                        "engine cannot be inspected before execution")
            nested_decision, nested_reason = decide(
                invocation.command, _shell_depth + 1)
            if nested_decision != "allow":
                return nested_decision, nested_reason
        got = git_grep_argv(tokens, resolution)
        if got is None:
            continue
        argv, configs, unresolved_configs = got
        if unresolved_configs:
            return ("ask",
                    "git grep has unresolved Git configuration that may select the ERE "
                    "engine: " + "; ".join(unresolved_configs) + ". This guard cannot "
                    "prove the pattern engine, so verify the config or use an explicit -P.")
        engine = None
        engine_src = None
        for cfg in configs:
            key, separator, value = cfg.partition("=")
            key = key.strip().lower()
            val = value.strip().lower()
            if key == "grep.patterntype":
                if not separator:
                    return ("ask", "git grep has grep.patternType with no value; Git may "
                            "fail without diagnostics, so the guard cannot prove an engine. "
                            "Use an explicit value or invoke git grep with -P.")
                if val not in CONFIG_ENGINE:
                    return ("ask", f"git grep has unrecognized grep.patternType={value!r}; "
                            "the guard cannot prove an engine. Use -P explicitly.")
                engine = CONFIG_ENGINE[val]
                engine_src = "config"
            elif key == "grep.extendedregexp":
                if not separator or not git_config_bool_is_false(value):
                    engine = "E"
                    engine_src = "config"
        patterns = []
        pattern_from_file = False
        pattern_declared = False
        uncertain_engine_options = []
        k = 0
        while k < len(argv):
            text, quoting = argv[k]
            if text == "--":
                k += 1
                # With no earlier -e/-f or positional pattern, parse-options assigns the
                # first operand after `--` to PATTERN. Once a pattern is declared, every
                # operand after `--` is a pathspec.
                if not pattern_declared and k < len(argv):
                    patterns.append(argv[k])
                    pattern_declared = True
                break
            long_name = text.partition("=")[0] if text.startswith("--") else ""
            long_engine, uncertain_engine = (
                long_engine_option(text) if long_name else (None, False)
            )
            if long_engine is not None:
                engine = long_engine
                engine_src = "flag"
                k += 1
                continue
            if uncertain_engine:
                uncertain_engine_options.append(text)
                k += 1
                continue
            if long_name in GREP_LONG_PATTERN_ARG:
                letter = GREP_LONG_PATTERN_ARG[long_name]
                attached = text.partition("=")[2] if "=" in text else None
                if attached is None and k + 1 < len(argv):
                    attached, quoting = argv[k + 1]
                    k += 2
                else:
                    k += 1
                pattern_declared = True
                if letter == "f":
                    pattern_from_file = True
                elif attached is not None:
                    patterns.append((attached, quoting))
                continue
            if long_name in GREP_LONG_REQUIRED_VALUE:
                k += 1 if "=" in text else 2
                continue
            if long_name in GREP_LONG_OPTIONAL_VALUE:
                # Only `--option=value` supplies the optional argument. In either form
                # this token is complete, so the next token remains an option or pattern.
                k += 1
                continue
            cluster = short_option_cluster(text)
            if cluster is not None:
                # A modelled single-dash cluster is authoritative: it knows the order of
                # the engine letters, which the -E regex below does not. `-EG` greps as
                # BRE and is harmless; the regex reads any E anywhere and denied it.
                cluster_engines, kind, letter, attached = cluster
                for cluster_engine in cluster_engines:
                    engine = cluster_engine
                    engine_src = "flag"
                if kind == "value":
                    k += 1 if attached is not None else 2
                    continue
                if kind == "optional":
                    k += 1
                    continue
                if kind == "pattern":
                    pattern_declared = True
                    if letter == "f":
                        pattern_from_file = True
                    if attached is not None:
                        # -e'harness\b' / -fpatterns.txt: the argument rides the token.
                        if letter == "e":
                            patterns.append((attached, quoting))
                        k += 1
                        continue
                    if k + 1 < len(argv):
                        if letter == "e":
                            patterns.append(argv[k + 1])
                        k += 2
                        continue
                k += 1
                continue
            if not text.startswith("-") and not pattern_declared:
                patterns.append((text, quoting))
                pattern_declared = True
            k += 1

        if uncertain_engine_options:
            if pattern_from_file:
                return ("ask", "git grep has an ambiguous or invalid long engine option "
                        f"({', '.join(uncertain_engine_options)}) and a pattern file this "
                        "guard cannot inspect; use a complete engine option.")
            if any(UNRESOLVED.search(pattern) or PCRE_ONLY.search(pattern)
                   for pattern, _quoting in patterns):
                return ("ask", "git grep has an ambiguous or invalid long option that may "
                        "select the ERE engine ("
                        + ", ".join(uncertain_engine_options)
                        + "); use the complete option name so the guarded pattern can be "
                        "classified before execution.")
        if engine != "E":
            continue
        engine_desc = "-E" if engine_src == "flag" else "Git grep configuration"
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
    ("RED  LONG ABBREV: --extended uniquely selects extended-regexp",
     """git grep --extended -e'harness\\b' -- README.md""", "deny"),
    ("RED  LONG ABBREV: --extended-r uniquely selects extended-regexp",
     """git grep --extended-r -e'harness\\b' -- README.md""", "deny"),
    ("GREEN LONG ABBREV: --no-extended resets the shared engine",
     """git grep -P --no-extended -e'harness\\b' -- README.md""", "allow"),
    ("RED  LONG ABBREV: a later --extended wins after an abbreviated reset",
     """git grep --no-extended --extended -e'harness\\b' -- README.md""", "deny"),
    ("ASK  LONG ABBREV: --ext is ambiguous with --ext-grep",
     """git grep --ext -e'harness\\b' -- README.md""", "ask"),
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
    ("ASK bare echo identity is not proven even for quoted Git text",
     '''echo "=== git grep -E lacks \\s support ===" ''', "ask"),
    ("GREEN plain grep, not git grep",
     """grep -rnE 'foo\\s+bar' src/""", "allow"),
    ("GREEN -E pattern where the atom is in the PATHSPEC not the pattern",
     """git grep -nE 'TODO' -- 'src/**'""", "allow"),
    ("RED  UNMODELLED 2026-08-02: ERE selected via -c grep.patternType=extended, no -E flag",
     """git -c grep.patternType=extended grep -n 'harness\\b' -- README.md""", "deny"),
    ("RED  REVIEW: git config keys are case-insensitive",
     """git -c Grep.PatternType=EXTENDED grep -n 'harness\\b' -- README.md""", "deny"),
    ("RED  REVIEW: --no-pager does not hide git grep",
     """git --no-pager grep -nE 'harness\\b' -- README.md""", "deny"),
    ("RED  REVIEW: -P as a git global option does not hide git grep",
     """git -P grep -nE 'harness\\b' -- README.md""", "deny"),
    ("RED  REVIEW: pathspec global switch does not hide git grep",
     """git --literal-pathspecs grep -nE 'harness\\b' -- README.md""", "deny"),
    ("RED  REVIEW: no-optional-locks does not hide git grep",
     """git --no-optional-locks grep -nE 'harness\\b' -- README.md""", "deny"),
    ("RED  REVIEW: attached git-dir option does not hide git grep",
     """git --git-dir=/repo/.git grep -nE 'harness\\b' -- README.md""", "deny"),
    ("RED  REVIEW: grep.extendedRegexp=true selects ERE",
     """git -c grep.extendedRegexp=true grep -n 'harness\\b' -- README.md""", "deny"),
    ("RED  REVIEW: grep.extendedRegexp with omitted value means true",
     """git -c grep.extendedRegexp grep -n 'harness\\b' -- README.md""", "deny"),
    ("RED  REVIEW: case-insensitive extendedRegexp key with omitted value",
     """git -c Grep.ExtendedRegexp grep -n 'harness\\b' -- README.md""", "deny"),
    ("RED  REVIEW: GIT_CONFIG_COUNT selects ERE",
     "GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=grep.patternType "
     "GIT_CONFIG_VALUE_0=extended git grep -n 'harness\\b' -- README.md", "deny"),
    ("RED  REVIEW: --config-env resolves an explicit prefix assignment",
     "PT=extended git --config-env=grep.patternType=PT "
     "grep -n 'harness\\b' -- README.md", "deny"),
    ("RED  ROUND 9: separated --config-env resolves an explicit prefix assignment",
     "PT=extended git --config-env grep.patternType=PT "
     "grep -n 'harness\\b' -- README.md", "deny"),
    ("ASK  REVIEW: unresolved relevant --config-env fails closed",
     "git --config-env=grep.patternType=ZHARNESS_UNSET_PATTERN_TYPE "
     "grep -n 'harness\\b' -- README.md", "ask"),
    ("RED  REVIEW: --namespace consumes its separate argument",
     """git --namespace ns grep -nE 'harness\\b' -- README.md""", "deny"),
    ("RED  REVIEW: --attr-source consumes its separate argument",
     """git --attr-source HEAD grep -nE 'harness\\b' -- README.md""", "deny"),
    ("RED  REVIEW: global switch composes with patternType config",
     """git --no-pager -c grep.patternType=extended grep -n 'harness\\b' -- README.md""",
     "deny"),
    ("ASK  UNMODELLED 2026-08-02: -E with a -f pattern file - guard cannot see the patterns",
     """git grep -nE -f pats.txt -- src/""", "ask"),
    # git grep uses parse-options(3), so -e/-f take an attached argument. Matching only
    # the separated spelling allowed every form below while the separated control denied.
    ("RED  ATTACHED: -e argument riding the same token",
     """git grep -E -e'harness\\b' -- README.md""", "deny"),
    ("RED  ATTACHED: same, double-quoted argument",
     '''git grep -E -e"harness\\b" -- README.md''', "deny"),
    ("RED  ATTACHED: engine and -e clustered, argument attached",
     """git grep -Ee'harness\\b' -- README.md""", "deny"),
    ("RED  ATTACHED: no-arg flag before the clustered engine and -e",
     """git grep -nEe'x = \\d' -- README.md""", "deny"),
    ("ASK  ATTACHED: -f pattern file attached to its flag",
     """git grep -nE -fpats.txt -- src/""", "ask"),
    ("GREEN ATTACHED: -P with an attached -e argument is the intended engine",
     """git grep -P -e'harness\\b' -- README.md""", "allow"),
    ("GREEN ATTACHED: -F fixed strings with an attached -e argument",
     """git grep -F -e'harness\\b' -- README.md""", "allow"),
    ("GREEN ATTACHED: no engine flag, attached -e - BRE is fine",
     """git grep -e'harness\\b' -- README.md""", "allow"),
    # Every case below was cross-checked against git 2.46.1 on a two-line fixture where
    # ERE matches the decoy line and PCRE matches the intended one, so "deny" means git
    # was measured returning the wrong line, not that the spelling merely looked risky.
    ("RED  CLUSTER: -W function-context before the attached -e",
     """git grep -EWe'harness\\b' -- README.md""", "deny"),
    ("RED  CLUSTER: -p show-function before the attached -e",
     """git grep -Epe'harness\\b' -- README.md""", "deny"),
    ("RED  CLUSTER: -o only-matching before the attached -e",
     """git grep -Eoe'harness\\b' -- README.md""", "deny"),
    ("RED  CLUSTER: -m takes the NEXT token, so the later -e is still the pattern",
     """git grep -Em 1 -e'harness\\b' -- README.md""", "deny"),
    ("RED  NUMERIC: -m accepts an attached decimal value after the engine",
     """git grep -Em1 'harness\\b' -- README.md""", "deny"),
    ("GREEN NUMERIC: attached -m preserves an explicit PCRE engine",
     """git grep -Pm1 'harness\\b' -- README.md""", "allow"),
    ("RED  NUMERIC: -A accepts an attached decimal value after the engine",
     """git grep -EA3 'harness\\b' -- README.md""", "deny"),
    ("RED  NUMERIC: -B accepts an attached decimal value after the engine",
     """git grep -EB3 'harness\\b' -- README.md""", "deny"),
    ("RED  NUMERIC: -C accepts an attached decimal value after the engine",
     """git grep -EC3 'harness\\b' -- README.md""", "deny"),
    ("RED  NUMERIC: -NUM context shorthand may follow the engine in a cluster",
     """git grep -E3 'harness\\b' -- README.md""", "deny"),
    ("GREEN NUMERIC: attached context preserves an explicit PCRE engine",
     """git grep -PA3 'harness\\b' -- README.md""", "allow"),
    ("RED  NUMERIC: leading -NUM continues into an ERE engine and attached pattern",
     """git grep -1Ee'harness\\b' -- README.md""", "deny"),
    ("RED  NUMERIC: a maximal multi-digit run continues into later flags",
     """git grep -12Ee'harness\\b' -- README.md""", "deny"),
    ("GREEN NUMERIC: leading -NUM continues into a PCRE engine",
     """git grep -1Pe'harness\\b' -- README.md""", "allow"),
    ("GREEN NUMERIC: embedded digits preserve later last-wins PCRE",
     """git grep -E1Pe'harness\\b' -- README.md""", "allow"),
    ("RED  NUMERIC: embedded digits preserve later last-wins ERE",
     """git grep -P1Ee'harness\\b' -- README.md""", "deny"),
    ("RED  OPTIONAL: bare --color does not consume the following engine",
     """git grep --color -E 'harness\\b' -- README.md""", "deny"),
    ("RED  OPTIONAL: --color=value remains one complete option",
     """git grep --color=never -E 'harness\\b' -- README.md""", "deny"),
    ("GREEN OPTIONAL: bare --color preserves an explicit PCRE engine",
     """git grep --color -P 'harness\\b' -- README.md""", "allow"),
    ("RED  OPTIONAL: bare --open-files-in-pager does not consume the engine",
     """git grep --open-files-in-pager -E 'harness\\b' -- README.md""", "deny"),
    ("RED  OPTIONAL: attached pager value does not consume the engine",
     """git grep --open-files-in-pager=cat -E 'harness\\b' -- README.md""", "deny"),
    ("RED  TERMINATOR: first operand after -- is the pattern when none came before",
     """git grep -E -- 'harness\\b' README.md""", "deny"),
    ("GREEN TERMINATOR: -- pattern preserves an explicit PCRE engine",
     """git grep -P -- 'harness\\b' README.md""", "allow"),
    ("GREEN TERMINATOR: after -e, operands following -- are pathspecs",
     """git grep -E -e 'harness' -- 'path\\b'""", "allow"),
    ("RED  ENGINE ORDER: -GE is last-wins ERE",
     """git grep -GE -e 'harness\\b' -- README.md""", "deny"),
    ("GREEN ENGINE ORDER: -EG is last-wins BRE - git returns the intended line",
     """git grep -EG -e 'harness\\b' -- README.md""", "allow"),
    ("GREEN ENGINE ORDER: -EPe is last-wins PCRE",
     """git grep -EPe'harness\\b' -- README.md""", "allow"),
    ("GREEN ENGINE NEGATION: matching --no-extended-regexp resets ERE to default",
     """git grep --extended-regexp --no-extended-regexp 'harness\\b' -- README.md""",
     "allow"),
    ("GREEN ENGINE NEGATION: --no-extended-regexp resets active PCRE to default",
     """git grep --perl-regexp --no-extended-regexp 'harness\\b' -- README.md""",
     "allow"),
    ("GREEN ENGINE NEGATION: --no-perl-regexp resets active ERE to default",
     """git grep --extended-regexp --no-perl-regexp 'harness\\b' -- README.md""",
     "allow"),
    ("GREEN ENGINE NEGATION: matching --no-perl-regexp resets PCRE to default",
     """git grep --perl-regexp --no-perl-regexp 'harness\\b' -- README.md""",
     "allow"),
    ("GREEN ENGINE NEGATION: a reset does not restore an earlier engine",
     """git grep -E --perl-regexp --no-perl-regexp 'harness\\b' -- README.md""",
     "allow"),
    ("GREEN ENGINE NEGATION: every negative option resets the shared active engine",
     """git grep -P --extended-regexp --no-perl-regexp 'harness\\b' -- README.md""",
     "allow"),
    ("GREEN ENGINE NEGATION: --no-basic-regexp resets the shared active engine",
     """git grep -E --no-basic-regexp 'harness\\b' -- README.md""", "allow"),
    ("GREEN ENGINE NEGATION: --no-fixed-strings resets the shared active engine",
     """git grep -E --no-fixed-strings 'harness\\b' -- README.md""", "allow"),
    ("RED  ENGINE NEGATION: a later positive ERE selection wins after reset",
     """git grep --no-perl-regexp --extended-regexp 'harness\\b' -- README.md""",
     "deny"),
    ("GREEN ENGINE NEGATION: a later positive PCRE selection wins after reset",
     """git grep --no-extended-regexp --perl-regexp 'harness\\b' -- README.md""",
     "allow"),
    ("GREEN CLUSTER: -O takes the attached remainder as its optional value",
     """git grep -EOe'harness\\b' -- README.md""", "allow"),
    ("GREEN CLUSTER: a letter this git rejects outright is not the guard's business",
     """git grep -EZe'harness\\b' -- README.md""", "allow"),
    # Prefix peeling is shared with the zsh guard, so a launcher missing from that table
    # hid the same invocation from both.
    ("RED WRAPPER: sudo",
     """sudo git grep -nE 'harness\\b' -- README.md""", "deny"),
    ("RED WRAPPER: sudo with a target user",
     """sudo -u root git grep -nE 'harness\\b' -- README.md""", "deny"),
    ("RED WRAPPER: command -p still executes git",
     """command -p git grep -nE 'harness\\b' -- README.md""", "deny"),
    ("RED WRAPPER: command -- still executes git",
     "command -- git grep -Ee'harness\\b' -- README.md", "deny"),
    ("RED WRAPPER: builtin command -- still executes git",
     "builtin command -- git grep -Ee'harness\\b' -- README.md", "deny"),
    ("RED WRAPPER: exec -a consumes argv0 before executing git",
     "exec -a harmless git grep -Ee'harness\\b' -- README.md", "deny"),
    ("RED WRAPPER: exec -c still executes git",
     "exec -c git grep -Ee'harness\\b' -- README.md", "deny"),
    ("RED WRAPPER: exec -- still executes git",
     "exec -- git grep -Ee'harness\\b' -- README.md", "deny"),
    ("GREEN WRAPPER: command -v only prints a path",
     """command -v git grep -nE 'harness\\b' -- README.md""", "allow"),
    ("GREEN WRAPPER: clustered command -pv only prints a path",
     "command -pv git grep -nE 'harness\\b' -- README.md", "allow"),
    ("GREEN WRAPPER: builtin refuses to execute an external git",
     "builtin git grep -nE 'harness\\b' -- README.md", "allow"),
    ("ASK WRAPPER: xargs is unmodelled and conceals git",
     """xargs git grep -nE 'harness\\b' -- README.md""", "ask"),
    ("ASK WRAPPER: unknown arch prefix with a guarded Git tail fails closed",
     """arch git grep -nE 'harness\\b' -- README.md""", "ask"),
    ("ASK WRAPPER: unknown xcrun prefix with a guarded Git tail fails closed",
     """xcrun git grep -nE 'harness\\b' -- README.md""", "ask"),
    ("ASK WRAPPER: unmodelled time options with a guarded Git tail fail closed",
     """time -p git grep -nE 'harness\\b' -- README.md""", "ask"),
    ("ASK WRAPPER: arch cannot hide a dynamic executable",
     """arch $TOOL grep -nE 'harness\\b' -- README.md""", "ask"),
    ("ASK WRAPPER: time cannot hide a dynamic executable",
     """time $TOOL grep -nE 'harness\\b' -- README.md""", "ask"),
    ("ASK WRAPPER: an arbitrary launcher cannot hide a dynamic executable",
     """launcher $TOOL grep -nE 'harness\\b' -- README.md""", "ask"),
    ("RED WRAPPER: bare time is a modelled shell keyword",
     """time git grep -nE 'harness\\b' -- README.md""", "deny"),
    ("RED WRAPPER: eval body is recursively inspected",
     """eval \"git grep -nE 'harness\\b' -- README.md\"""", "deny"),
    ("RED WRAPPER: builtin eval body is recursively inspected",
     """builtin eval \"git grep -nE 'harness\\b' -- README.md\"""", "deny"),
    ("GREEN WRAPPER: eval preserves an explicit PCRE engine",
     """eval \"git grep -nP 'harness\\b' -- README.md\"""", "allow"),
    ("ASK WRAPPER: partially dynamic eval source is not inspected as static",
     """eval \"git grep -nP $PATTERN -- README.md\"""", "ask"),
    ("ASK WRAPPER: partially dynamic builtin eval source is not static",
     """builtin eval \"git grep -nP $PATTERN -- README.md\"""", "ask"),
    ("ASK WRAPPER: single-quoted eval source is dynamic to eval",
     """eval '$CMD; git grep -nP harness -- README.md'""", "ask"),
    ("ASK WRAPPER: single-quoted builtin eval source is dynamic to eval",
     """builtin eval '$CMD; git grep -nP harness -- README.md'""", "ask"),
    ("ASK NESTED: partially dynamic sh -c source is not static",
     """sh -c \"git grep -nP $PATTERN -- README.md\"""", "ask"),
    ("ASK NESTED: partially dynamic zsh -c source is not static",
     """zsh -c \"git grep -nP $PATTERN -- README.md\"""", "ask"),
    ("ASK NESTED: single-quoted sh -c source expands in sh",
     """sh -c '$CMD; git grep -nP harness -- README.md'""", "ask"),
    ("ASK NESTED: single-quoted bash -c source expands in bash",
     """bash -c '$CMD; git grep -nP harness -- README.md'""", "ask"),
    ("ASK NESTED: single-quoted zsh -c source expands in zsh",
     """zsh -c '$CMD; git grep -nP harness -- README.md'""", "ask"),
    ("GREEN NESTED: fully static sh -c source retains PCRE",
     """sh -c \"git grep -nP 'harness\\b' -- README.md\"""", "allow"),
    ("GREEN NESTED: fully static zsh -c source retains PCRE",
     """zsh -c \"git grep -nP 'harness\\b' -- README.md\"""", "allow"),
    ("GREEN WRAPPER: arch without a guarded Git tail is outside this guard",
     """arch uname -m""", "allow"),
    ("ASK WRAPPER: bare echo identity is not mechanically fixed",
     """echo git grep -nE 'harness\\b' -- README.md""", "ask"),
    ("ASK WRAPPER: bare printf identity is not mechanically fixed",
     """printf '%s\\n' git grep -nE 'harness\\b' -- README.md""", "ask"),
    ("ASK WRAPPER: a function-shadowed echo may forward literal Git argv",
     """echo() { command \"$@\"; }; echo git grep -nE 'harness\\b' -- README.md""",
     "ask"),
    ("ASK WRAPPER: a function-shadowed echo may supply the Git executable",
     """echo() { git \"$@\"; }; echo grep -nE 'harness\\b' -- README.md""", "ask"),
    ("ASK WRAPPER: an alias may supply Git before the guarded subcommand",
     """alias echo=git; echo grep -nE 'harness\\b' -- README.md""", "ask"),
    ("ASK WRAPPER: a shadowed printf may supply Git",
     """function printf { git \"$@\"; }; printf grep -nE 'harness\\b' -- README.md""",
     "ask"),
    ("ASK WRAPPER: a printf alias may supply Git",
     """alias printf=git; printf grep -nE 'harness\\b' -- README.md""", "ask"),
    ("GREEN WRAPPER: builtin echo bypasses a same-source function",
     """echo() { git \"$@\"; }; builtin echo git grep -nE 'harness\\b' -- README.md""",
     "allow"),
    ("GREEN WRAPPER: exact /usr/bin/printf identity is explicit",
     """/usr/bin/printf '%s\\n' 'printf() { git \"$@\"; }' git grep -nE 'harness\\b' -- README.md""",
     "allow"),
    ("GREEN WRAPPER: exact /bin/echo identity is explicit",
     """/bin/echo git grep -nE 'harness\\b' -- README.md""", "allow"),
    ("GREEN WRAPPER: command structurally bypasses an echo function",
     """echo() { git \"$@\"; }; command echo git grep -nE 'harness\\b' -- README.md""",
     "allow"),
    ("GREEN WRAPPER: builtin printf bypasses shell identity mutation",
     """alias printf=git; builtin printf '%s\\n' git grep -nE 'harness\\b' -- README.md""",
     "allow"),
    ("ASK WRAPPER: brace-body function does not make bare echo identity provable",
     """{ echo() { git \"$@\"; }; echo grep -nE 'harness\\b' -- README.md; }""",
     "ask"),
    ("ASK WRAPPER: subshell-body function does not make bare echo identity provable",
     """( echo() { git \"$@\"; }; echo grep -nE 'harness\\b' -- README.md )""",
     "ask"),
    ("ASK WRAPPER: eval-defined alias leaves bare echo identity unresolved",
     "eval 'alias echo=git'\necho grep -nE 'harness\\b' -- README.md", "ask"),
    ("ASK WRAPPER: basename alone does not trust an arbitrary echo path",
     """/tmp/echo git grep -nE 'harness\\b' -- README.md""", "ask"),
    ("GREEN patternType=perl via config - the intended engine",
     """git -c grep.patternType=perl grep 'x\\b' -- src/""", "allow"),
    ("GREEN -P with a -f pattern file",
     """git grep -P -f pats.txt -- src/""", "allow"),
    ("GREEN inside a for/do loop with the BRE engine",
     """for d in a b; do git grep -n 'x\\b' -- $d; done""", "allow"),
    ("RED  ROUND 9: Git numeric boolean 2 selects ERE",
     """git -c grep.extendedRegexp=2 grep -n 'harness\\b' -- README.md""", "deny"),
    ("RED  ROUND 9: Git signed numeric boolean -1 selects ERE",
     """git -c grep.extendedRegexp=-1 grep -n 'harness\\b' -- README.md""", "deny"),
    ("RED  ROUND 9: Git hexadecimal boolean 0x2 selects ERE",
     """git -c grep.extendedRegexp=0x2 grep -n 'harness\\b' -- README.md""", "deny"),
    ("GREEN ROUND 9: Git numeric zero keeps the default BRE engine",
     """git -c grep.extendedRegexp=0x0 grep -n 'harness\\b' -- README.md""", "allow"),
    ("RED  ROUND 9: env wrapper cannot displace git from argv zero",
     """env GIT_PAGER=cat git grep -nE 'harness\\b' -- README.md""", "deny"),
    ("RED  ROUND 9: env-injected Git config remains visible",
     "env GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=grep.patternType "
     "GIT_CONFIG_VALUE_0=extended git grep -n 'harness\\b' -- README.md", "deny"),
    ("RED  ROUND 9: nice wrapper cannot displace git from argv zero",
     """nice -n 5 git grep -nE 'harness\\b' -- README.md""", "deny"),
    ("RED  ROUND 9: shell -c command is recursively inspected",
     """sh -c \"git grep -nE 'harness\\b' -- README.md\"""", "deny"),
    ("RED  ROUND 9: absolute git path is recognized by basename",
     """/usr/bin/git grep -nE 'harness\\b' -- README.md""", "deny"),
    ("ASK  ROUND 9: valueless grep.patternType fails closed",
     """git -c grep.patternType grep -n 'harness\\b' -- README.md""", "ask"),
    ("RED  ROUND 9: env -S command splitting is parsed before git",
     """env -S \"git grep -nE 'harness\\b' -- README.md\"""", "deny"),
    ("RED  ROUND 12: attached env -S command splitting is parsed",
     """env -S\"git grep -nE 'harness\\b' -- README.md\"""", "deny"),
    ("RED  ROUND 12: long env split-string command splitting is parsed",
     """env --split-string=\"git grep -nE 'harness\\b' -- README.md\"""", "deny"),
    ("GREEN ROUND 12: env -S preserves an explicit PCRE engine",
     """env -S \"git grep -nP 'harness\\b' -- README.md\"""", "allow"),
    ("ASK  ROUND 12: a dynamic executable with Git grep arguments is unresolved",
     """$TOOL grep -nE 'harness\\b' -- README.md""", "ask"),
    ("ASK  ROUND 12: command-prefix depth fails closed",
     ("command " * (MAX_PREFIX_DEPTH + 1))
     + "git grep -nE 'harness\\b' -- README.md", "ask"),
    ("ASK  ROUND 12: an unclosed Git command is not a clean parse",
     """git grep -nE 'harness\\b""", "ask"),
    ("RED  ROUND 10: nohup wrapper cannot displace git from argv zero",
     """nohup git -c grep.patternType=extended grep -n 'harness\\b' -- README.md""", "deny"),
    ("RED  ROUND 10: absolute nohup composes with the command shell keyword",
     """command /usr/bin/nohup git grep -nE 'harness\\b' -- README.md""", "deny"),
    ("RED  ROUND 10: timeout duration and options precede the command",
     """timeout --preserve-status -k 2 5 git grep -nE 'harness\\b' -- README.md""",
     "deny"),
    ("RED  ROUND 10: stdbuf attached mode precedes the command",
     """stdbuf -o0 git grep -nE 'harness\\b' -- README.md""", "deny"),
    ("RED  ROUND 10: stdbuf separated long mode precedes the command",
     """stdbuf --output L git grep -nE 'harness\\b' -- README.md""", "deny"),
    ("RED  ROUND 10: setsid bundled flags precede the command",
     """setsid -fw git grep -nE 'harness\\b' -- README.md""", "deny"),
    ("RED  ROUND 11: caffeinate cannot displace git from argv zero",
     """caffeinate git -c grep.patternType=extended grep -n 'harness\\b' -- README.md""", "deny"),
    ("RED  ROUND 11: caffeinate bundled flags precede the command",
     """caffeinate -dimsu git grep -nE 'harness\\b' -- README.md""", "deny"),
    ("RED  ROUND 11: caffeinate -m assertion flag is modelled standalone",
     """caffeinate -m git grep -nE 'harness\\b' -- README.md""", "deny"),
    ("RED  ROUND 11: caffeinate -m is modelled when bundled",
     """caffeinate -dm git grep -nE 'harness\\b' -- README.md""", "deny"),
    ("GREEN ROUND 11: a modelled caffeinate flag preserves an explicit -P engine",
     """caffeinate -m git grep -nP 'harness\\b' -- README.md""", "allow"),
    ("RED  ROUND 11: caffeinate option argument is not mistaken for the command",
     """caffeinate -t 30 git grep -nE 'harness\\b' -- README.md""", "deny"),
    ("GREEN ROUND 11: caffeinate wrapping a non-git command",
     """caffeinate -i ls -la""", "allow"),
    ("RED  ROUND 10: exec wrappers compose rather than masking one another",
     "env FOO=1 nohup nice git -c grep.patternType=extended "
     "grep -n 'harness\\b' -- README.md", "deny"),
    ("RED  ROUND 10: nohup remains visible inside a nested shell",
     """sh -c \"nohup git grep -nE 'harness\\b' -- README.md\"""", "deny"),
    ("GREEN ROUND 10: nohup wrapping a non-git command",
     """nohup ls -la""", "allow"),
    ("GREEN ROUND 10: wrapper help terminates without executing trailing git tokens",
     """timeout --help git grep -nE 'harness\\b' -- README.md""", "allow"),
    ("ASK ROUND 10: a bare command name is not an explicit harmless identity",
     """echo git grep -nE 'harness\\b' -- README.md""", "ask"),
]


def measure_git_short_options():
    """Classify every ASCII letter against the INSTALLED git. -> (accepted, takes_value).

    Probed outside any repository, because git parses its options before it looks for
    `.git`, so the three outcomes separate cleanly and no fixture repo is needed:
    `unknown switch` is a rejected letter, `expects a ... value` / `cannot open` is a
    letter that takes one, and `not a git repository` is a letter that needs none.

    Returns None when git cannot be run at all, which the caller reports as a failure
    rather than a skip: an unmeasured table is not a verified one.
    """
    probe_root = tempfile.mkdtemp(prefix="z-harness-git-optprobe-")
    accepted, takes_value = set(), set()
    try:
        for char in string.ascii_letters:
            try:
                result = subprocess.run(
                    ["git", "grep", f"-{char}", "x"], cwd=probe_root,
                    capture_output=True, text=True, timeout=10,
                )
            except (OSError, subprocess.SubprocessError):
                return None
            stderr = result.stderr or ""
            if "unknown switch" in stderr:
                continue
            accepted.add(char)
            if "expects" in stderr or "requires a value" in stderr or "cannot open" in stderr:
                takes_value.add(char)
    finally:
        shutil.rmtree(probe_root, ignore_errors=True)
    return (accepted, takes_value) if accepted else None


def check_option_table_against_git():
    """-> list of failure strings. Empty means the table matches the installed git."""
    measured = measure_git_short_options()
    if measured is None:
        return ["cannot enforce: the installed git could not be probed, so the "
                "short-option table is unverified"]
    accepted, takes_value = measured
    modelled = (set(GREP_SHORT_ENGINE) | set(GREP_SHORT_PATTERN_ARG)
                | GREP_SHORT_VALUE | GREP_SHORT_NOARG | GREP_SHORT_OPTIONAL_VALUE)
    failures = []
    gap = sorted(accepted - modelled)
    if gap:
        failures.append(
            f"this git accepts short flag(s) {gap} that short_option_cluster does not "
            f"model, so a cluster containing one falls through and its pattern is never "
            f"parsed; add each to the correct set in the same commit")
    stale = sorted(modelled - accepted)
    if stale:
        failures.append(
            f"the table models short flag(s) {stale} that this git rejects; remove them "
            f"so the table describes the tool actually installed")
    # -e and -f are the pattern-carrying flags and are modelled separately by design.
    measured_value = sorted(takes_value - set(GREP_SHORT_PATTERN_ARG))
    if set(measured_value) != GREP_SHORT_VALUE:
        failures.append(
            f"this git takes a value for {measured_value} but the table says "
            f"{sorted(GREP_SHORT_VALUE)}; a mis-typed arity either swallows the pattern "
            f"or leaves it unparsed")
    return failures


def check_option_grammar_against_git():
    """Exercise the valid spellings whose argv grammar is load-bearing here."""
    failures = []
    try:
        with tempfile.TemporaryDirectory(prefix="z-harness-git-grammar-") as repo:
            initialized = subprocess.run(
                ["git", "init", "--quiet"], cwd=repo,
                capture_output=True, text=True, timeout=10,
            )
            if initialized.returncode:
                return ["cannot initialize the temporary Git grammar fixture: "
                        + (initialized.stderr or "no diagnostic").strip()]
            fixture = os.path.join(repo, "fixture.txt")
            with open(fixture, "w", encoding="utf-8") as stream:
                stream.write("harness\nharnessb\n")
            indexed = subprocess.run(
                ["git", "add", "fixture.txt"], cwd=repo,
                capture_output=True, text=True, timeout=10,
            )
            if indexed.returncode:
                return ["cannot index the temporary Git grammar fixture: "
                        + (indexed.stderr or "no diagnostic").strip()]
            cases = (
                ("attached -m", ["-Em1", r"harness\b", "--", "fixture.txt"],
                 "harnessb"),
                ("attached -A", ["-EA3", r"harness\b", "--", "fixture.txt"],
                 "harnessb"),
                ("attached -B", ["-EB3", r"harness\b", "--", "fixture.txt"],
                 "harnessb"),
                ("attached -C", ["-EC3", r"harness\b", "--", "fixture.txt"],
                 "harnessb"),
                ("-NUM shorthand", ["-E3", r"harness\b", "--", "fixture.txt"],
                 "harnessb"),
                ("-NUM before E and e", ["-12Ee" + r"harness\b", "--", "fixture.txt"],
                 "harnessb"),
                ("-NUM between E and P", ["-E1Pe" + r"harness\b", "--", "fixture.txt"],
                 "harness"),
                ("-NUM between P and E", ["-P1Ee" + r"harness\b", "--", "fixture.txt"],
                 "harnessb"),
                ("bare optional --color",
                 ["--color", "--no-color", "-E", r"harness\b", "--", "fixture.txt"],
                 "harnessb"),
                ("-- pattern state", ["-E", "--", r"harness\b", "fixture.txt"],
                 "harnessb"),
                ("matching E negation",
                 ["--extended-regexp", "--no-extended-regexp", r"harness\b", "--",
                  "fixture.txt"], "fixture.txt:harness\n"),
                ("unrelated E negation",
                 ["--perl-regexp", "--no-extended-regexp", r"harness\b", "--",
                  "fixture.txt"], "fixture.txt:harness\n"),
                ("unrelated P negation",
                 ["--extended-regexp", "--no-perl-regexp", r"harness\b", "--",
                  "fixture.txt"], "fixture.txt:harness\n"),
                ("matching P negation",
                 ["--perl-regexp", "--no-perl-regexp", r"harness\b", "--",
                  "fixture.txt"], "fixture.txt:harness\n"),
                ("basic negation resets shared engine",
                 ["--extended-regexp", "--no-basic-regexp", r"harness\b", "--",
                  "fixture.txt"], "fixture.txt:harness\n"),
                ("fixed negation resets shared engine",
                 ["--extended-regexp", "--no-fixed-strings", r"harness\b", "--",
                  "fixture.txt"], "fixture.txt:harness\n"),
                ("positive E after reset",
                 ["--no-perl-regexp", "--extended-regexp", r"harness\b", "--",
                  "fixture.txt"], "fixture.txt:harnessb\n"),
                ("positive P after reset",
                 ["--no-extended-regexp", "--perl-regexp", r"harness\b", "--",
                  "fixture.txt"], "fixture.txt:harness\n"),
                ("unique --extended abbreviation",
                 ["--extended", r"harness\b", "--", "fixture.txt"],
                 "fixture.txt:harnessb\n"),
                ("unique --extended-r abbreviation",
                 ["--extended-r", r"harness\b", "--", "fixture.txt"],
                 "fixture.txt:harnessb\n"),
                ("unique --no-extended abbreviation resets PCRE",
                 ["--perl-regexp", "--no-extended", r"harness\b", "--", "fixture.txt"],
                 "fixture.txt:harness\n"),
                ("later abbreviated extended engine wins",
                 ["--no-extended", "--extended", r"harness\b", "--", "fixture.txt"],
                 "fixture.txt:harnessb\n"),
            )
            for label, args, expected_fragment in cases:
                observed = subprocess.run(
                    ["git", "grep", *args], cwd=repo,
                    capture_output=True, text=True, timeout=10,
                )
                if (observed.returncode != 0
                        or expected_fragment not in observed.stdout):
                    failures.append(
                        f"installed Git did not accept {label} with the measured ERE "
                        f"behavior (rc={observed.returncode}, stdout={observed.stdout!r}, "
                        f"stderr={observed.stderr!r})")
            ambiguous = subprocess.run(
                ["git", "grep", "--ext", r"harness\b", "--", "fixture.txt"], cwd=repo,
                capture_output=True, text=True, timeout=10,
            )
            if (ambiguous.returncode == 0 or "ambiguous option" not in ambiguous.stderr
                    or "--extended-regexp" not in ambiguous.stderr
                    or "--ext-grep" not in ambiguous.stderr):
                failures.append(
                    "installed Git did not reject --ext as the measured ambiguity "
                    f"(rc={ambiguous.returncode}, stdout={ambiguous.stdout!r}, "
                    f"stderr={ambiguous.stderr!r})")
    except (OSError, subprocess.SubprocessError) as exc:
        failures.append(f"installed Git grammar probe failed closed: {exc!r}")
    return failures


def check_shell_boundary_behavior():
    """Exercise downstream expansion and every explicit harmless identity."""
    failures = []
    zsh_probes = (
        (
            "function-shadowed echo",
            'echo() { print -r -- "FORWARDED:$*"; }\n'
            "echo git grep -E pattern\n",
            "FORWARDED:git grep -E pattern\n",
        ),
        (
            "alias-shadowed printf",
            'alias printf="print -r -- FORWARDED"\n'
            "printf git grep -E pattern\n",
            "FORWARDED git grep -E pattern\n",
        ),
        (
            "brace-body function",
            '{ echo() { print -r -- "BRACE:$*"; }; echo grep -E pattern; }\n',
            "BRACE:grep -E pattern\n",
        ),
        (
            "subshell-body function",
            '( echo() { print -r -- "SUBSHELL:$*"; }; echo grep -E pattern )\n',
            "SUBSHELL:grep -E pattern\n",
        ),
        (
            "eval-defined alias",
            'eval \'alias echo="print -r -- EVAL"\'\n'
            "echo grep -E pattern\n",
            "EVAL grep -E pattern\n",
        ),
        (
            "builtin echo bypass",
            'echo() { print -r -- "WRONG:$*"; }\n'
            "builtin echo git grep -E pattern\n",
            "git grep -E pattern\n",
        ),
        (
            "command echo bypass",
            'echo() { print -r -- "WRONG:$*"; }\n'
            "command echo git grep -E pattern\n",
            "git grep -E pattern\n",
        ),
    )
    for label, source, expected in zsh_probes:
        try:
            observed = subprocess.run(
                ["zsh", "-s"], input=source, capture_output=True, text=True, timeout=10,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            failures.append(f"cannot run {label} probe: {exc!r}")
            continue
        if observed.returncode != 0 or observed.stdout != expected:
            failures.append(
                f"installed zsh did not demonstrate {label} forwarding "
                f"(rc={observed.returncode}, stdout={observed.stdout!r}, "
                f"stderr={observed.stderr!r})")
    for shell in ("sh", "bash", "zsh"):
        environment = dict(os.environ)
        environment["CMD"] = "/usr/bin/printf"
        expected = f"DOWNSTREAM-{shell}\n"
        try:
            observed = subprocess.run(
                [shell, "-c", f"$CMD 'DOWNSTREAM-{shell}\\n'"],
                env=environment, capture_output=True, text=True, timeout=10,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            failures.append(f"cannot run downstream {shell} expansion probe: {exc!r}")
            continue
        if observed.returncode != 0 or observed.stdout != expected:
            failures.append(
                f"installed {shell} did not expand the downstream command source "
                f"(rc={observed.returncode}, stdout={observed.stdout!r}, "
                f"stderr={observed.stderr!r})")
    external_probes = (
        (["/bin/echo", "git", "grep", "-E", "pattern"], "git grep -E pattern\n"),
        (["/usr/bin/printf", "%s\\n", "git grep -E pattern"],
         "git grep -E pattern\n"),
    )
    for argv, expected in external_probes:
        try:
            observed = subprocess.run(
                argv, capture_output=True, text=True, timeout=10,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            failures.append(f"cannot run exact external identity {argv[0]}: {exc!r}")
            continue
        if observed.returncode != 0 or observed.stdout != expected:
            failures.append(
                f"exact external identity {argv[0]} did not retain literal argv "
                f"(rc={observed.returncode}, stdout={observed.stdout!r}, "
                f"stderr={observed.stderr!r})")
    return failures


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
    # The fixtures above test the table against itself. This one tests it against the
    # tool, which is the only thing that can catch the table going stale under a git
    # upgrade or on a host whose git differs from the authoring one.
    table_failures = check_option_table_against_git()
    bad += len(table_failures)
    if table_failures:
        for failure in table_failures:
            print("  FAIL short-option table vs installed git: %s" % failure)
    else:
        print("  PASS short-option table matches the installed git")
    grammar_failures = check_option_grammar_against_git()
    bad += len(grammar_failures)
    if grammar_failures:
        for failure in grammar_failures:
            print("  FAIL option grammar vs installed git: %s" % failure)
    else:
        print("  PASS numeric, optional-value, negated-engine, and -- grammar matches installed git")
    boundary_failures = check_shell_boundary_behavior()
    bad += len(boundary_failures)
    if boundary_failures:
        for failure in boundary_failures:
            print("  FAIL shell-boundary behavior probe: %s" % failure)
    else:
        print("  PASS downstream expansion and explicit harmless identities match installed shells")
    checks = len(FIXTURES) + 3
    print("failures: %d" % bad)
    print("SELFTEST-SUMMARY suite=git_grep_engine_guard checks=%d failures=%d" % (
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
