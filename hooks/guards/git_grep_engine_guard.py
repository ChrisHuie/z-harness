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

OUT OF SCOPE, named so `allow` is not read as a clean verdict over an unmodelled edge:
a NON-SHELL interpreter that reaches git through its own runtime. `python3 -c`, `perl -e`,
`ruby -e`, `node -e` and `awk 'BEGIN{system(...)}'` bodies are not classified, so a guarded
`git grep -E` inside one is allowed. Shell sources -- `sh -c`, `eval`, substitutions,
heredocs, here-strings, process substitution, interpreter stdin -- ARE classified. Modelling
Python or awk semantics is a different guard, not a widening of this one.

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
import time
from typing import NamedTuple

# A live PCRE escape has an odd-length backslash run. A regular expression that only
# looks behind one character cannot apply that rule symmetrically to both the known
# atoms and the controls. Keep the locally grounded alphabet explicit, scan every run,
# and classify an unknown live alphabetic escape as uncertain rather than safe.
PCRE_ESCAPE_LETTERS = frozenset("bBdDsSwWAZzhHvVRQEXNK")
UNRESOLVED = re.compile(r"\$[A-Za-z_{(]|`")

MAX_COMMAND_CHARS = 1024 * 1024
MAX_SUBCOMMANDS = 16384
MAX_TOKENS = 65536
MAX_PREFIX_DEPTH = 8
MAX_ENV_SPLITS = 4
MAX_ALIAS_DEPTH = 8
MAX_SOURCE_DEPTH = 16
MAX_FUNCTION_DECLARATIONS = 512
REGISTERED_HOOK_TIMEOUT_SECONDS = 5
GUARD_BUDGET_SECONDS = 4.0
GIT_PROBE_TIMEOUT_SECONDS = 0.75
ZSH_EQUALS_ON = "on"
ZSH_EQUALS_OFF = "off"
ZSH_EQUALS_UNKNOWN = "unknown"


def hook_timeout_contract(settings_data=None, codex_data=None, *, root=None, budget=None):
    """Return an error when the two registered Bash hooks do not bound this guard."""
    root = (os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            if root is None else root)
    if settings_data is None:
        settings_data = json.load(open(os.path.join(root, "settings.json"), encoding="utf-8"))
    if codex_data is None:
        codex_data = json.load(open(
            os.path.join(root, "hooks", "hooks.json"), encoding="utf-8"))
    claude = [
        hook.get("timeout")
        for entry in settings_data.get("hooks", {}).get("PreToolUse", [])
        if entry.get("matcher") == "Bash"
        for hook in entry.get("hooks", [])
        if "bash_command_guard.py" in hook.get("command", "")
    ]
    codex = [
        hook.get("timeout")
        for entry in codex_data.get("hooks", {}).get("PreToolUse", [])
        if entry.get("matcher") == "^Bash$"
        for hook in entry.get("hooks", [])
        if ("bash_command_guard.py" in hook.get("command", "")
            and "--runtime codex" in hook.get("command", ""))
    ]
    if claude != [REGISTERED_HOOK_TIMEOUT_SECONDS]:
        return f"Claude Bash hook timeouts are {claude!r}, expected [5]"
    if codex != [REGISTERED_HOOK_TIMEOUT_SECONDS]:
        return f"Codex Bash hook timeouts are {codex!r}, expected [5]"
    internal = GUARD_BUDGET_SECONDS if budget is None else budget
    if internal > REGISTERED_HOOK_TIMEOUT_SECONDS - 1.0:
        return (f"internal budget {internal} does not leave the required one-second "
                f"margin inside timeout {REGISTERED_HOOK_TIMEOUT_SECONDS}")
    return ""


class CommandParseError(ValueError):
    """The Bash source cannot be tokenized within the guard's closed limits."""


def _check_decision_budget(deadline):
    if deadline is not None and time.monotonic() >= deadline:
        raise CommandParseError(
            "the guard's internal decision budget was exhausted while parsing")


class GitAuthorityError(RuntimeError):
    """The executing trusted Git could not supply its command authority inventory."""


class PrefixResolution(NamedTuple):
    """One resolved command boundary shared by both Bash predicates."""

    items: list
    command_env: dict
    errors: tuple
    hazard_hint: bool
    lookup_authority_uncertain: bool
    descendant_lookup_authority_uncertain: bool


class ShellInvocation(NamedTuple):
    shell: str
    command: str
    dynamic: bool
    command_env: dict
    lookup_authority_uncertain: bool


class PatternScan(NamedTuple):
    atoms: tuple
    uncertain: tuple


class LongOptionResolution(NamedTuple):
    canonical: str
    value: str
    has_value: bool
    ambiguous: tuple
    unknown: bool


class FunctionDeclaration(NamedTuple):
    start: int
    end: int
    name: str
    body: str
    scope_start: int
    scope_end: int
    conditional: bool
    maybe: bool
    pipeline_start: int
    pipeline_end: int


class GitAuthority(NamedTuple):
    executable: str
    exec_path: str
    builtins: frozenset
    main: frozenset


class HereStringSource(NamedTuple):
    prefix: str
    line: str
    redirect_start: int
    word_end: int
    descriptor: int
    body: str
    dynamic: bool


class FileInputSource(NamedTuple):
    line: str
    redirect_start: int
    word_end: int
    descriptor: int
    path: str
    dynamic: bool


class StdinConsumer(NamedTuple):
    reads_stdin: bool
    unresolved: bool
    shell: str


class StdinProvenance(NamedTuple):
    decision: str
    reason: str


class HeredocFinding(NamedTuple):
    shell: str
    header: str
    body: str
    prefix: str
    header_offset: int


class HeredocExpansionFinding(NamedTuple):
    source: str
    prefix: str
    header: str
    header_offset: int


class ZshArgvState(NamedTuple):
    equals_state: str
    command_index: object
    reads_stdin: bool


def scan_pcre_constructs(pattern):
    """Return live PCRE-only constructs and unmodelled alphabetic escapes.

    Punctuation escapes such as ``\\(`` are portable equality controls. Any live
    ``(?`` group opener is PCRE grammar here, including forms introduced after this
    guard was authored. Alphabetic escapes outside the grounded set fail closed.
    """
    atoms = set()
    uncertain = set()
    index = 0
    in_class = False
    class_has_member = False
    while index < len(pattern):
        if (not in_class and pattern[index] == "("
                and index + 1 < len(pattern) and pattern[index + 1] == "?"):
            atoms.add("(?")
            index += 2
            continue
        if pattern[index] == "[" and not in_class:
            in_class = True
            class_has_member = False
            index += 1
            continue
        if (in_class and pattern[index] == "[" and index + 1 < len(pattern)
                and pattern[index + 1] in ":.="):
            marker = pattern[index + 1]
            end = pattern.find(marker + "]", index + 2)
            if end < 0:
                uncertain.add("[" + marker)
                break
            class_has_member = True
            index = end + 2
            continue
        if pattern[index] == "]" and in_class:
            if class_has_member:
                in_class = False
            else:
                class_has_member = True
            index += 1
            continue
        if pattern[index] != "\\":
            if in_class and not (pattern[index] == "^" and not class_has_member):
                class_has_member = True
            index += 1
            continue
        start = index
        while index < len(pattern) and pattern[index] == "\\":
            index += 1
        run = index - start
        if run % 2 == 0 or index >= len(pattern):
            continue
        escaped = pattern[index]
        if in_class:
            class_has_member = True
        if escaped.isalpha():
            atom = "\\" + escaped
            if escaped in PCRE_ESCAPE_LETTERS:
                atoms.add(atom)
            else:
                uncertain.add(atom)
        index += 1
    return PatternScan(tuple(sorted(atoms)), tuple(sorted(uncertain)))


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
    "--no-index", "--index", "--max-depth", "--and",
    "--or", "--not",
}
GREP_LONG_OPTION_NAMES.update(GREP_LONG_BOOLEAN_OPTIONS)
GREP_LONG_OPTION_NAMES.update(
    "--no-" + option[2:] for option in GREP_LONG_BOOLEAN_OPTIONS
)
# Git 2.46.1 exposes pattern arguments only as short -e/-f. Inventing long aliases
# changes abbreviation uniqueness and can make an invalid command look executable.
GREP_LONG_PATTERN_ARG = {}
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


def canonical_long_option(text):
    """Resolve Git's exact or unique long-option prefix before interpreting arity."""
    name, separator, value = text.partition("=")
    if not name.startswith("--") or name == "--":
        return LongOptionResolution(None, value, bool(separator), (), True)
    candidates = tuple(sorted(option for option in GREP_LONG_OPTION_NAMES
                              if option.startswith(name)))
    canonical = name if name in GREP_LONG_OPTION_NAMES else (
        candidates[0] if len(candidates) == 1 else None
    )
    return LongOptionResolution(
        canonical, value, bool(separator), candidates if len(candidates) > 1 else (),
        canonical is None and not candidates,
    )


def _has_unmodelled_case_pattern(body):
    return bool(re.search(
        r"(?ms)(?:^|[;&|()\n])\s*case(?:[ \t\n]|$).*?\bin(?:[ \t\n]|$)",
        body,
    ))


def _command_substitution(cmd, start):
    """Return (body, next-index) for a live ``$(...)`` command substitution."""
    depth = 1
    quote = ""
    index = start + 2
    body_start = index
    while index < len(cmd):
        char = cmd[index]
        if quote:
            if char == "\\" and quote == '"' and index + 1 < len(cmd):
                index += 2
                continue
            if char == quote:
                quote = ""
            index += 1
            continue
        if char in ("'", '"'):
            quote = char
            index += 1
            continue
        if char == "\\" and index + 1 < len(cmd):
            index += 2
            continue
        if cmd.startswith("$((", index):
            depth += 2
            index += 3
            continue
        if cmd.startswith("$(", index):
            depth += 1
            index += 2
            continue
        if char == "(":
            depth += 1
            index += 1
            continue
        if char == ")":
            candidate = cmd[body_start:index]
            if _has_unmodelled_case_pattern(candidate):
                raise CommandParseError(
                    "command substitution contains unmodelled case-pattern closers")
            depth -= 1
            if depth == 0:
                return cmd[body_start:index], index + 1
        index += 1
    raise CommandParseError("command source has an unclosed command substitution")


def _arithmetic_expansion(cmd, start, _depth=0):
    """Return (body, next-index, nested-command-sources) for ``$((...))``."""
    if _depth > MAX_SOURCE_DEPTH:
        raise CommandParseError(
            f"arithmetic source nesting exceeds depth {MAX_SOURCE_DEPTH}")
    depth = 2
    quote = ""
    index = start + 3
    body_start = index
    nested_sources = []
    while index < len(cmd):
        char = cmd[index]
        if quote:
            if quote == '"' and cmd.startswith("$(", index):
                if cmd.startswith("$((", index):
                    _body, index, sources = _arithmetic_expansion(cmd, index, _depth + 1)
                    nested_sources.extend(sources)
                else:
                    source, index = _command_substitution(cmd, index)
                    nested_sources.append(source)
                continue
            if quote == '"' and char == "`":
                source, index = _backtick_substitution(cmd, index)
                nested_sources.append(source)
                continue
            if char == "\\" and quote == '"' and index + 1 < len(cmd):
                index += 2
                continue
            if char == quote:
                quote = ""
            index += 1
            continue
        if char in ("'", '"'):
            quote = char
            index += 1
            continue
        if char == "\\" and index + 1 < len(cmd):
            index += 2
            continue
        if cmd.startswith("$((", index):
            _body, index, sources = _arithmetic_expansion(cmd, index, _depth + 1)
            nested_sources.extend(sources)
            continue
        if cmd.startswith("$(", index):
            source, index = _command_substitution(cmd, index)
            nested_sources.append(source)
            continue
        if char == "`":
            source, index = _backtick_substitution(cmd, index)
            nested_sources.append(source)
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return (cmd[body_start:index - 1], index + 1,
                        tuple(nested_sources))
        index += 1
    raise CommandParseError("command source has an unclosed arithmetic expansion")


def _parameter_expansion(cmd, start, _depth=0):
    """Return (text, next-index, executable-sources) for one ``${...}``."""
    if _depth > MAX_SOURCE_DEPTH:
        raise CommandParseError(
            f"parameter source nesting exceeds depth {MAX_SOURCE_DEPTH}")
    depth = 1
    quote = ""
    index = start + 2
    sources = []
    while index < len(cmd):
        char = cmd[index]
        if quote:
            if quote == '"' and cmd.startswith("$(", index):
                if cmd.startswith("$((", index):
                    _body, index, nested = _arithmetic_expansion(cmd, index, _depth + 1)
                    sources.extend(nested)
                else:
                    source, index = _command_substitution(cmd, index)
                    sources.append(source)
                continue
            if quote == '"' and char == "`":
                source, index = _backtick_substitution(cmd, index)
                sources.append(source)
                continue
            if char == "\\" and quote == '"' and index + 1 < len(cmd):
                index += 2
                continue
            if char == quote:
                quote = ""
            index += 1
            continue
        if char in ("'", '"'):
            quote = char
            index += 1
            continue
        if char == "\\" and index + 1 < len(cmd):
            index += 2
            continue
        if cmd.startswith("$(", index):
            if cmd.startswith("$((", index):
                _body, index, nested = _arithmetic_expansion(cmd, index, _depth + 1)
                sources.extend(nested)
            else:
                source, index = _command_substitution(cmd, index)
                sources.append(source)
            continue
        if char == "`":
            source, index = _backtick_substitution(cmd, index)
            sources.append(source)
            continue
        if cmd.startswith("${", index):
            _text, index, nested = _parameter_expansion(cmd, index, _depth + 1)
            sources.extend(nested)
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return cmd[start:index + 1], index + 1, tuple(sources)
        index += 1
    raise CommandParseError("command source has an unclosed parameter expansion")


def _backtick_substitution(cmd, start):
    """Return (body, next-index) for a live backtick command substitution."""
    index = start + 1
    body = []
    while index < len(cmd):
        char = cmd[index]
        if char == "\\" and index + 1 < len(cmd):
            body.append(cmd[index:index + 2])
            index += 2
            continue
        if char == "`":
            return "".join(body), index + 1
        body.append(char)
        index += 1
    raise CommandParseError("command source has an unclosed backtick substitution")


def _zsh_argv_state(words, default=ZSH_EQUALS_ON):
    """Parse zsh options once for EQUALS state, ``-c`` body, and stdin use."""
    state = default
    command_mode = False
    explicit_stdin = False
    operands = []
    index = 1
    while index < len(words):
        word = words[index]
        if word == "--":
            operands.extend(range(index + 1, len(words)))
            break
        normalized = re.sub(r"[-_]", "", word.lower())
        if word.startswith("--"):
            if normalized == "equals":
                state = ZSH_EQUALS_ON
            elif normalized == "noequals":
                state = ZSH_EQUALS_OFF
            elif "equal" in normalized:
                state = ZSH_EQUALS_UNKNOWN
            index += 1
            continue
        cluster = (re.fullmatch(r"([+-])([^+-].*)", word)
                   if not word.startswith(("--", "++")) else None)
        if cluster:
            sign, letters = cluster.groups()
            option_index = letters.find("o")
            flag_letters = letters if option_index < 0 else letters[:option_index]
            command_mode = command_mode or "c" in flag_letters
            explicit_stdin = explicit_stdin or "s" in flag_letters
            if option_index >= 0:
                attached = letters[option_index + 1:]
                if attached:
                    option_word = attached
                elif index + 1 < len(words):
                    option_word = words[index + 1]
                    index += 1
                else:
                    return ZshArgvState(ZSH_EQUALS_UNKNOWN, None, True)
                option = re.sub(r"[-_]", "", option_word.lower())
                if option == "equals":
                    state = ZSH_EQUALS_ON if sign == "-" else ZSH_EQUALS_OFF
                elif option == "noequals":
                    state = ZSH_EQUALS_OFF if sign == "-" else ZSH_EQUALS_ON
                elif "equal" in option:
                    state = ZSH_EQUALS_UNKNOWN
            index += 1
            continue
        # Zsh stops parsing startup options at the first operand.  In ``-c``
        # mode that operand is the command string; otherwise it is the script
        # path.  Everything after it is positional argv, even when it looks
        # like another option.
        operands.append(index)
        break
    command_index = operands[0] if command_mode and operands else None
    reads_stdin = explicit_stdin or (not command_mode and not operands)
    return ZshArgvState(state, command_index, reads_stdin)


def _shell_reads_stdin(words):
    """Whether a directly named shell consumes commands from standard input."""
    if not words or os.path.basename(words[0]) not in SHELLS:
        return False
    if os.path.basename(words[0]) == "zsh":
        return _zsh_argv_state(words).reads_stdin
    operands = []
    explicit_stdin = False
    options_with_values = {"-o", "+o", "-O", "+O", "--rcfile", "--init-file"}
    index = 1
    while index < len(words):
        word = words[index]
        if word == "--":
            operands.extend(words[index + 1:])
            break
        if word in options_with_values:
            if index + 1 >= len(words):
                return True
            index += 2
            continue
        if word.startswith("--"):
            index += 1
            continue
        if word.startswith(("-", "+")):
            if "c" in word[1:]:
                return False
            explicit_stdin = explicit_stdin or "s" in word[1:]
            index += 1
            continue
        operands.append(word)
        index += 1
    return explicit_stdin or not operands


def _header_stdin_shell(header, suffix="", deadline=None):
    """Return the named stdin-reading shell, empty for data, or None if uncertain."""
    try:
        header_commands = split_commands(header, _deadline=deadline)
    except CommandParseError:
        return None
    if not header_commands:
        return ""
    header_resolution = unwrap_command_prefix(header_commands[-1])
    if header_resolution.errors:
        return None
    words = [word for word, _quoting in header_resolution.items]
    if _shell_reads_stdin(words):
        return os.path.basename(words[0])
    # A literal pipeline into a shell also executes the heredoc bytes. This recognizes
    # the direct bounded form; arbitrary filters and compound redirections remain outside
    # the tokenizer contract and therefore must not be described as comprehensively parsed.
    if suffix:
        try:
            downstream_commands = split_commands(suffix, _deadline=deadline)
        except CommandParseError:
            return None
        if downstream_commands:
            downstream_resolution = unwrap_command_prefix(downstream_commands[-1])
            if downstream_resolution.errors:
                return None
            candidate = [word for word, _quoting in downstream_resolution.items]
            if _shell_reads_stdin(candidate):
                return os.path.basename(candidate[0])
    return ""


def _header_executes_shell(header, suffix="", deadline=None):
    """Whether a heredoc feeds a named shell; None means the consumer is uncertain."""
    shell = _header_stdin_shell(header, suffix, deadline)
    return None if shell is None else bool(shell)


def _leading_equals_hazard(source, subcommands=None, deadline=None):
    """Whether source visibly executes guarded `=git` syntax."""
    subcommands = GIT_HAZARD_SUBCOMMANDS if subcommands is None else subcommands
    try:
        commands = split_commands(source, _deadline=deadline)
    except CommandParseError:
        return True
    for tokens in commands:
        meaningful = [token for token in tokens
                      if token[0] not in CONTROL_KEYWORDS
                      and not ASSIGNMENT.match(token[0])]
        if (meaningful and _equals_expansion_is_live(*meaningful[0])
                and any(os.path.basename(word) in subcommands
                        for word, _quoting in meaningful[1:])):
            return True
    return False


def _heredoc_expansion_sources(body):
    """Return command substitutions expanded by an unquoted heredoc delimiter."""
    sources = []
    index = 0
    while index < len(body):
        if body[index] == "\\" and index + 1 < len(body):
            index += 2
            continue
        if body.startswith("$(", index):
            source, index = _command_substitution(body, index)
            sources.append(source)
            continue
        if body[index] == "`":
            source, index = _backtick_substitution(body, index)
            sources.append(source)
            continue
        index += 1
    return tuple(sources)


def _find_heredoc_operator(line):
    """Return (offset, strip-tabs) for one live heredoc operator in a header."""
    # A line with no `<<` can only produce one other outcome here, the unclosed-quote
    # raise, so a line with no quote characters either has nothing to find. Two C-level
    # substring tests replace a per-character walk that probed four prefixes per byte:
    # this function alone cost 1.23 s over three calls on a 600 KiB single-token line.
    if "<<" not in line and '"' not in line and "'" not in line:
        return None
    quote = ""
    index = 0
    arithmetic_depth = 0
    while index < len(line):
        char = line[index]
        if quote:
            if char == "\\" and quote == '"' and index + 1 < len(line):
                index += 2
                continue
            if char == quote:
                quote = ""
            index += 1
            continue
        if char in ("'", '"'):
            quote = char
            index += 1
            continue
        if char == "\\" and index + 1 < len(line):
            index += 2
            continue
        if char == "#" and (index == 0 or line[index - 1].isspace()):
            return None
        if line.startswith("$((", index):
            arithmetic_depth += 2
            index += 3
            continue
        if line.startswith("((", index):
            arithmetic_depth += 2
            index += 2
            continue
        if arithmetic_depth and char == "(":
            arithmetic_depth += 1
            index += 1
            continue
        if arithmetic_depth and char == ")":
            arithmetic_depth -= 1
            index += 1
            continue
        if line.startswith("<<<", index):
            index += 3
            continue
        if line.startswith("<<", index):
            if arithmetic_depth:
                index += 2
                continue
            return index, line.startswith("<<-", index)
        index += 1
    if quote:
        raise CommandParseError("heredoc header has an unclosed quote")
    return None


def _parse_heredoc_delimiter_word(line, start):
    """Quote-remove one literal shell word used as a heredoc delimiter."""
    output = []
    quoted = False
    consumed = False
    index = start
    while index < len(line):
        char = line[index]
        if char.isspace() or char in ";|&()<>":
            break
        consumed = True
        if char == "\\":
            if index + 1 >= len(line):
                raise CommandParseError("heredoc delimiter ends with a backslash")
            quoted = True
            output.append(line[index + 1])
            index += 2
            continue
        if char == "'":
            end = line.find("'", index + 1)
            if end < 0:
                raise CommandParseError("heredoc delimiter has an unclosed single quote")
            quoted = True
            output.append(line[index + 1:end])
            index = end + 1
            continue
        if char == '"':
            quoted = True
            index += 1
            while index < len(line) and line[index] != '"':
                if line[index] == "\\" and index + 1 < len(line):
                    next_char = line[index + 1]
                    if next_char in '$`"\\':
                        output.append(next_char)
                    else:
                        output.append("\\" + next_char)
                    index += 2
                    continue
                output.append(line[index])
                index += 1
            if index >= len(line):
                raise CommandParseError("heredoc delimiter has an unclosed double quote")
            index += 1
            continue
        if char in "`$":
            raise CommandParseError(
                "dynamic-looking heredoc delimiters are outside the literal word model")
        output.append(char)
        index += 1
    if not consumed:
        raise CommandParseError("heredoc operator has no delimiter word")
    return "".join(output), quoted, index


def extract_heredoc_sources(cmd, deadline=None, equals_findings=None,
                            equals_subcommands=None, shell_findings=None,
                            expansion_findings=None,
                            classify_non_direct_shell_bodies=False):
    """Remove heredoc payloads from argv text and return executable shell bodies."""
    _check_decision_budget(deadline)
    bodies = []
    cleaned = []
    cursor = 0
    while cursor < len(cmd):
        _check_decision_budget(deadline)
        header_end = cmd.find("\n", cursor)
        if header_end < 0:
            header_end = len(cmd)
        header_line = cmd[cursor:header_end]
        first_operator = _find_heredoc_operator(header_line)
        if first_operator is None:
            cleaned.append(cmd[cursor:header_end])
            if header_end < len(cmd):
                cleaned.append("\n")
                cursor = header_end + 1
                continue
            cursor = header_end
            break
        redirects = []
        search = 0
        while True:
            _check_decision_budget(deadline)
            found = _find_heredoc_operator(header_line[search:])
            if found is None:
                break
            relative_offset, strip_tabs = found
            offset = search + relative_offset
            redirect_start = offset
            candidate_start = offset
            while candidate_start > 0 and header_line[candidate_start - 1].isdigit():
                candidate_start -= 1
            if (candidate_start < offset
                    and (candidate_start == 0
                         or not (header_line[candidate_start - 1].isalnum()
                                 or header_line[candidate_start - 1] == "_"))):
                redirect_start = candidate_start
            descriptor = header_line[redirect_start:offset]
            feeds_stdin = not descriptor or int(descriptor) == 0
            word_start = offset + (3 if strip_tabs else 2)
            while word_start < len(header_line) and header_line[word_start] in " \t":
                word_start += 1
            delimiter, quoted, word_end = _parse_heredoc_delimiter_word(
                header_line, word_start)
            if not delimiter:
                raise CommandParseError("empty heredoc delimiters are outside the model")
            redirects.append((redirect_start, word_end, delimiter, quoted,
                              strip_tabs, feeds_stdin))
            search = word_end
        if header_end >= len(cmd):
            raise CommandParseError("heredoc header has no payload line")
        header_parts = []
        clean_redirect_offsets = {}
        clean_length = 0
        part_start = 0
        for redirect_start, word_end, *_rest in redirects:
            part = header_line[part_start:redirect_start]
            header_parts.append(part)
            clean_length += len(part)
            clean_redirect_offsets[redirect_start] = clean_length
            header_parts.append(" ")
            clean_length += 1
            part_start = word_end
        final_part = header_line[part_start:]
        header_parts.append(final_part)
        clean_header = "".join(header_parts)
        stdin_shell = _header_stdin_shell(clean_header, deadline=deadline)
        executes_shell = None if stdin_shell is None else bool(stdin_shell)
        single_shell_body = (
            executes_shell is True
            and sum(1 for redirect in redirects if redirect[-1]) == 1
            and (classify_non_direct_shell_bodies
                 or _direct_heredoc_header(header_line, deadline)))
        body_start = header_end + 1
        for _start, _end, delimiter, quoted, strip_tabs, feeds_stdin in redirects:
            scan = body_start
            body_end = None
            terminator_end = None
            while scan <= len(cmd):
                _check_decision_budget(deadline)
                line_end = cmd.find("\n", scan)
                if line_end < 0:
                    line_end = len(cmd)
                line = cmd[scan:line_end]
                candidate = line.lstrip("\t") if strip_tabs else line
                if candidate == delimiter:
                    body_end = scan
                    terminator_end = line_end + (1 if line_end < len(cmd) else 0)
                    break
                if line_end >= len(cmd):
                    break
                scan = line_end + 1
            if body_end is None:
                raise CommandParseError(
                    f"heredoc delimiter {delimiter!r} has no exact terminator")
            body = cmd[body_start:body_end]
            equals_hazard = (feeds_stdin and stdin_shell
                             and _leading_equals_hazard(
                                 body, equals_subcommands, deadline))
            if equals_hazard and equals_findings is not None:
                equals_findings.append(HeredocFinding(
                    stdin_shell, clean_header, body, cmd[:cursor],
                    clean_redirect_offsets[_start]))
            elif equals_hazard and stdin_shell != "zsh":
                raise CommandParseError(
                    f"{stdin_shell} heredoc contains guarded leading-equals command "
                    "syntax whose executable identity is unresolved outside zsh")
            if (feeds_stdin and executes_shell is None
                    and source_has_git_hazard_hint(body)):
                raise CommandParseError(
                    "heredoc has guarded source and an unresolved stdin consumer")
            if feeds_stdin and executes_shell is True:
                bodies.append(body)
                if shell_findings is not None and single_shell_body:
                    shell_findings.append(HeredocFinding(
                        stdin_shell, clean_header, body, cmd[:cursor],
                        clean_redirect_offsets[_start]))
            if not quoted:
                expansion_sources = _heredoc_expansion_sources(body)
                bodies.extend(expansion_sources)
                if (expansion_findings is not None
                        and not (feeds_stdin and executes_shell is True)):
                    expansion_findings.extend(
                        HeredocExpansionFinding(
                            source, cmd[:cursor], clean_header,
                            clean_redirect_offsets[_start])
                        for source in expansion_sources)
            body_start = terminator_end
        cleaned.append(clean_header + "\n")
        cursor = body_start
    return "".join(cleaned), tuple(bodies)


def command_without_heredoc_payloads(command, deadline=None):
    """Return headers and ordinary commands without reclassifying payload bytes."""
    cleaned, _bodies = extract_heredoc_sources(
        command, deadline, [], (), [], [])
    return cleaned


def _function_scope_pairs(cmd, records, deadline=None):
    """Return ordinary subshell/command-source pairs outside declaration bodies."""
    # No parenthesis means no pair and no arithmetic depth; no quote means the trailing
    # unclosed-quote raise cannot fire either. Both closers are required in the test
    # because a bare `)` is itself the unmatched-subshell error.
    if not any(char in cmd for char in "()'\""):
        return ()
    by_start = {record.start: record for record in records}
    pairs = []
    stack = []
    quote = ""
    arithmetic_depth = 0
    index = 0
    while index < len(cmd):
        if index % 256 == 0:
            _check_decision_budget(deadline)
        if index in by_start:
            index = by_start[index].end
            continue
        char = cmd[index]
        if quote:
            if char == "\\" and quote == '"' and index + 1 < len(cmd):
                index += 2
                continue
            if char == quote:
                quote = ""
            index += 1
            continue
        if char in ("'", '"'):
            quote = char
            index += 1
            continue
        if char == "\\" and index + 1 < len(cmd):
            index += 2
            continue
        if char == "#" and (index == 0 or cmd[index - 1].isspace()):
            newline = cmd.find("\n", index + 1)
            index = len(cmd) if newline < 0 else newline + 1
            continue
        if not arithmetic_depth and cmd.startswith("$((", index):
            arithmetic_depth = 2
            index += 3
            continue
        if not arithmetic_depth and cmd.startswith("((", index):
            arithmetic_depth = 2
            index += 2
            continue
        if arithmetic_depth:
            if char == "(":
                arithmetic_depth += 1
            elif char == ")":
                arithmetic_depth -= 1
            index += 1
            continue
        if char == "(":
            stack.append(index)
        elif char == ")":
            if not stack:
                raise CommandParseError("function scope has an unmatched closing subshell")
            pairs.append((stack.pop(), index))
        index += 1
    if quote or arithmetic_depth or stack:
        raise CommandParseError("function scope has an unclosed quote, arithmetic, or subshell")
    return tuple(sorted(pairs))


def _conditional_function_intervals(cmd, records, deadline=None):
    masked = list(cmd)
    for record in records:
        masked[record.start:record.end] = " " * (record.end - record.start)
    quote = ""
    index = 0
    while index < len(masked):
        if index % 256 == 0:
            _check_decision_budget(deadline)
        char = masked[index]
        if quote:
            masked[index] = " "
            if char == "\\" and quote == '"' and index + 1 < len(masked):
                masked[index + 1] = " "
                index += 2
                continue
            if char == quote:
                quote = ""
            index += 1
            continue
        if char in ("'", '"'):
            masked[index] = " "
            quote = char
            index += 1
            continue
        if char == "\\" and index + 1 < len(masked):
            masked[index:index + 2] = "  "
            index += 2
            continue
        if char == "#" and (index == 0 or masked[index - 1].isspace()):
            newline = cmd.find("\n", index + 1)
            end = len(masked) if newline < 0 else newline
            masked[index:end] = " " * (end - index)
            index = end
            continue
        index += 1
    source = "".join(masked)
    token = re.compile(
        r"(?m)(?:^|[;&|(){}\n])[ \t]*(if|while|until|for|case|fi|done|esac)\b")
    openers = {"if": "fi", "while": "done", "until": "done",
               "for": "done", "case": "esac"}
    stack = []
    intervals = []
    for match in token.finditer(source):
        _check_decision_budget(deadline)
        word = match.group(1)
        position = match.start(1)
        if word in openers:
            stack.append((word, position))
            continue
        for candidate in range(len(stack) - 1, -1, -1):
            opener, start = stack[candidate]
            if openers[opener] == word:
                stack.pop(candidate)
                intervals.append((start, match.end(1)))
                break
    intervals.extend((start, len(cmd)) for _opener, start in stack)
    return tuple(intervals)


def _function_list_operators(cmd, records, deadline=None):
    """Return live list/pipeline operators with their lexical subshell scope."""
    by_start = {record.start: record for record in records}
    operators = []
    record_braces = {}
    brace_stack = []
    scope_stack = []
    quote = ""
    arithmetic_depth = 0
    index = 0
    while index < len(cmd):
        if index % 256 == 0:
            _check_decision_budget(deadline)
        if index in by_start:
            record_braces[index] = tuple(brace_stack)
            index = by_start[index].end
            continue
        char = cmd[index]
        if quote:
            if char == "\\" and quote == '"' and index + 1 < len(cmd):
                index += 2
                continue
            if char == quote:
                quote = ""
            index += 1
            continue
        if char in ("'", '"'):
            quote = char
            index += 1
            continue
        if char == "\\" and index + 1 < len(cmd):
            index += 2
            continue
        if char == "#" and (index == 0 or cmd[index - 1].isspace()):
            newline = cmd.find("\n", index + 1)
            index = len(cmd) if newline < 0 else newline
            continue
        if not arithmetic_depth and cmd.startswith("$((", index):
            arithmetic_depth = 2
            index += 3
            continue
        if not arithmetic_depth and cmd.startswith("((", index):
            arithmetic_depth = 2
            index += 2
            continue
        if arithmetic_depth:
            if char == "(":
                arithmetic_depth += 1
            elif char == ")":
                arithmetic_depth -= 1
            index += 1
            continue
        if char == "(":
            scope_stack.append(index)
            index += 1
            continue
        if char == ")":
            if scope_stack:
                scope_stack.pop()
            index += 1
            continue
        if char == "{":
            brace_stack.append(index)
            index += 1
            continue
        if char == "}":
            if brace_stack:
                brace_stack.pop()
            index += 1
            continue
        operator = None
        width = 1
        if cmd.startswith("&&", index):
            operator, width = "&&", 2
        elif cmd.startswith("||", index):
            operator, width = "||", 2
        elif char == "|":
            operator, width = "|", 2 if cmd.startswith("|&", index) else 1
        elif char in ";\n":
            operator = ";"
        elif char == "&":
            operator = ";"
        if operator is None:
            index += 1
            continue
        scope_start = scope_stack[-1] if scope_stack else -1
        operators.append((index, width, operator, scope_start,
                          tuple(brace_stack)))
        index += width
    return tuple(operators), record_braces


def annotate_function_declarations(cmd, records, deadline=None):
    """Attach lexical subshell scope and conditional reachability to declarations."""
    _check_decision_budget(deadline)
    pairs = _function_scope_pairs(cmd, records, deadline)
    intervals = _conditional_function_intervals(cmd, records, deadline)
    operators, record_braces = _function_list_operators(cmd, records, deadline)
    annotated = []
    for record in records:
        _check_decision_budget(deadline)
        containers = []
        for pair_index, pair in enumerate(pairs):
            if pair_index % 256 == 0:
                _check_decision_budget(deadline)
            if pair[0] < record.start < pair[1]:
                containers.append(pair)
        scope_start, scope_end = (-1, len(cmd))
        if containers:
            scope_start, scope_end = min(
                containers, key=lambda pair: pair[1] - pair[0])
        conditional = any(start < record.start < end for start, end in intervals)
        brace_path = record_braces.get(record.start, ())
        contexts = [brace_path[:depth]
                    for depth in range(len(brace_path) + 1)]
        maybe = False
        pipeline_candidates = []
        for context in contexts:
            _check_decision_budget(deadline)
            same_context = []
            for operator_index, operator in enumerate(operators):
                if operator_index % 256 == 0:
                    _check_decision_budget(deadline)
                if operator[3] == scope_start and operator[4] == context:
                    same_context.append(operator)
            previous = [operator for operator in same_context
                        if operator[0] < record.start]
            following = [operator for operator in same_context
                         if operator[0] >= record.end]
            prior = max(previous, default=None, key=lambda operator: operator[0])
            next_operator = min(
                following, default=None, key=lambda operator: operator[0])
            maybe = maybe or (prior is not None
                              and prior[2] in {"&&", "||"})
            if next_operator is not None and next_operator[2] == "|":
                component_start = (scope_start + 1 if prior is None
                                   else prior[0] + prior[1])
                pipeline_candidates.append((component_start, next_operator[0]))
        pipeline_start, pipeline_end = (-1, -1)
        if pipeline_candidates:
            pipeline_start, pipeline_end = min(
                pipeline_candidates, key=lambda candidate: candidate[1] - candidate[0])
        annotated.append(FunctionDeclaration(
            record.start, record.end, record.name, record.body,
            scope_start, scope_end, conditional, maybe,
            pipeline_start, pipeline_end,
        ))
    return tuple(annotated)


def function_declaration_records(cmd, deadline=None):
    """Return live function declarations with temporal reachability and scope."""
    _check_decision_budget(deadline)
    if "()" not in cmd and "function " not in cmd:
        return ()
    pattern = re.compile(
        r"(?ms)(?:(?:function[ \t]+)([A-Za-z_][A-Za-z0-9_]*)(?:\s*\(\s*\))?"
        r"|([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*\))\s*([({])")
    live = [True] * len(cmd)
    quote = ""
    index = 0
    while index < len(cmd):
        if index % 256 == 0:
            _check_decision_budget(deadline)
        char = cmd[index]
        if quote:
            live[index] = False
            if char == "\\" and quote == '"' and index + 1 < len(cmd):
                live[index + 1] = False
                index += 2
                continue
            if char == quote:
                quote = ""
            index += 1
            continue
        if char in ("'", '"'):
            live[index] = False
            quote = char
        elif char == "\\" and index + 1 < len(cmd):
            live[index + 1] = False
            index += 1
        index += 1
    records = []
    cursor = 0
    for match in pattern.finditer(cmd):
        _check_decision_budget(deadline)
        if match.start() < cursor:
            continue
        if not live[match.start()]:
            continue
        opener = match.group(3)
        closer = "}" if opener == "{" else ")"
        depth, quote, index = 1, "", match.end()
        while index < len(cmd) and depth:
            if index % 256 == 0:
                _check_decision_budget(deadline)
            char = cmd[index]
            if quote:
                if char == "\\" and quote == '"':
                    index += 2
                    continue
                if char == quote:
                    quote = ""
            elif char in ("'", '"'):
                quote = char
            elif char == "\\":
                index += 2
                continue
            elif char == "#" and (index == match.end() or cmd[index - 1].isspace()):
                newline = cmd.find("\n", index + 1)
                index = len(cmd) if newline < 0 else newline + 1
                continue
            elif char == opener:
                depth += 1
            elif char == closer:
                depth -= 1
            index += 1
        if depth:
            raise CommandParseError("function declaration has an unclosed body")
        if len(records) >= MAX_FUNCTION_DECLARATIONS:
            raise CommandParseError(
                f"command source exceeds the {MAX_FUNCTION_DECLARATIONS}-function parse limit")
        records.append(FunctionDeclaration(
            match.start(), index, match.group(1) or match.group(2),
            cmd[match.end():index - 1], -1, len(cmd), False, False, -1, -1,
        ))
        cursor = index
    return annotate_function_declarations(cmd, tuple(records), deadline)


def _invoked_function_bodies(source, declarations, uncertain=(), deadline=None):
    _check_decision_budget(deadline)
    if not declarations and not uncertain:
        return ()
    if source_has_dynamic_command_word(source, deadline):
        raise CommandParseError(
            "a dynamic command word may invoke a declared function")
    invoked = []
    for tokens in split_commands(source, _deadline=deadline):
        words = [text for text, _quoting in tokens
                 if text not in CONTROL_KEYWORDS and not ASSIGNMENT.match(text)]
        if words and words[0] in uncertain:
            raise CommandParseError(
                f"function {words[0]!r} is conditionally defined at this call site")
        if words and words[0] in declarations:
            invoked.append(declarations[words[0]])
            continue
        if (words and words[0] not in {"builtin", "command"}
                and words[0] not in TRUSTED_EXTERNAL_NON_FORWARDING_COMMANDS
                and any(name in words[1:] for name in set(declarations) | set(uncertain))):
            raise CommandParseError(
                "a declared function appears behind an unmodelled invocation prefix")
    return tuple(invoked)


def _extract_function_region(cmd, records, start, end, scope_start,
                             inherited, inherited_uncertain,
                             pipeline_scope=None, deadline=None):
    _check_decision_budget(deadline)
    declarations = dict(inherited)
    uncertain = set(inherited_uncertain)
    direct_records = [record for record in records
                      if record.scope_start == scope_start
                      and start <= record.start < end
                      and ((pipeline_scope is None and record.pipeline_start < 0)
                           or (pipeline_scope is not None
                               and (record.pipeline_start, record.pipeline_end)
                               == pipeline_scope))]
    pipeline_children = sorted({(record.pipeline_start, record.pipeline_end)
                                for record in records
                                if start <= record.start < end
                                and record.scope_start == scope_start
                                and record.pipeline_start >= 0
                                and (record.pipeline_start, record.pipeline_end)
                                != pipeline_scope})
    child_scopes = sorted({(record.scope_start, record.scope_end)
                           for record in records
                           if start <= record.start < end
                           and record.scope_start != scope_start})
    direct_children = []
    for child in child_scopes:
        if not any(other[0] < child[0] and child[1] < other[1]
                   for other in child_scopes):
            direct_children.append(child)
    events = [(record.start, "record", record) for record in direct_records]
    events.extend((child_start, "pipeline", (child_start, child_end))
                  for child_start, child_end in pipeline_children)
    events.extend((child_start, "scope", (child_start, child_end))
                  for child_start, child_end in direct_children)
    events.sort(key=lambda event: event[0])
    cleaned = []
    invoked = []
    cursor = start
    for position, kind, item in events:
        _check_decision_budget(deadline)
        if position < cursor:
            continue
        segment = cmd[cursor:position]
        cleaned.append(segment)
        invoked.extend(_invoked_function_bodies(
            segment, declarations, uncertain, deadline))
        if kind == "record":
            record = item
            if record.conditional or record.maybe:
                uncertain.add(record.name)
            else:
                declarations[record.name] = record.body
                uncertain.discard(record.name)
            cursor = record.end
            continue
        child_start, child_end = item
        if kind == "pipeline":
            child_cleaned, child_invoked = _extract_function_region(
                cmd, records, child_start, child_end, scope_start,
                declarations, uncertain, (child_start, child_end), deadline,
            )
            cleaned.append(child_cleaned)
            invoked.extend(child_invoked)
            cursor = child_end
            continue
        child_cleaned, child_invoked = _extract_function_region(
            cmd, records, child_start + 1, child_end, child_start,
            declarations, uncertain, None, deadline,
        )
        cleaned.extend((cmd[child_start:child_start + 1], child_cleaned,
                        cmd[child_end:child_end + 1]))
        invoked.extend(child_invoked)
        cursor = child_end + 1
    tail = cmd[cursor:end]
    cleaned.append(tail)
    invoked.extend(_invoked_function_bodies(tail, declarations, uncertain, deadline))
    return "".join(cleaned), tuple(invoked)


def extract_function_invocations(cmd, deadline=None):
    """Follow calls against definitions live at that point and in that shell scope."""
    _check_decision_budget(deadline)
    records = function_declaration_records(cmd, deadline)
    if not records:
        return cmd, ()
    return _extract_function_region(
        cmd, records, 0, len(cmd), -1, {}, set(), None, deadline)


def split_commands(cmd, _parse_depth=0, _deadline=None):
    """Split on UNQUOTED && || ; | newline ( ) and yield token lists.

    Tokens are (text, quoting) where quoting is one of '', "'", '"'.
    Command substitutions are recursively inspected even inside double quotes. Heredoc
    bodies are inspected only when stdin is executed by a named shell interpreter.
    """
    _check_decision_budget(_deadline)
    if not isinstance(cmd, str):
        raise CommandParseError("command source is not text")
    if _parse_depth > MAX_SOURCE_DEPTH:
        raise CommandParseError(
            f"executable source nesting exceeds depth {MAX_SOURCE_DEPTH}")
    if len(cmd) > MAX_COMMAND_CHARS:
        raise CommandParseError(
            f"command source exceeds the {MAX_COMMAND_CHARS}-byte parse limit")
    cmd, function_sources = extract_function_invocations(cmd, _deadline)
    cmd, heredoc_sources = extract_heredoc_sources(cmd, _deadline)
    out, cur, embedded = [], [], []
    tok_parts, tok_mode_parts, tok_modes, q, i = [], [], set(), "", 0
    token_count = 0
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
        if i % 256 == 0:
            _check_decision_budget(_deadline)
        c = cmd[i]
        if q:
            if q == '"' and cmd.startswith("${", i):
                text, i, sources = _parameter_expansion(cmd, i)
                for source in sources:
                    embedded.extend(split_commands(source, _parse_depth + 1, _deadline))
                append_tok(text, q)
                continue
            if q == '"' and cmd.startswith("$((", i):
                _body, i, sources = _arithmetic_expansion(cmd, i)
                for source in sources:
                    embedded.extend(split_commands(source, _parse_depth + 1, _deadline))
                append_tok("$((__ARITH__))", q)
                continue
            if q == '"' and cmd.startswith("$(", i):
                body, i = _command_substitution(cmd, i)
                embedded.extend(split_commands(body, _parse_depth + 1, _deadline))
                append_tok("$(__COMMAND__)", q)
                continue
            if q == '"' and c == "`":
                body, i = _backtick_substitution(cmd, i)
                embedded.extend(split_commands(body, _parse_depth + 1, _deadline))
                append_tok("`__COMMAND__`", q)
                continue
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
        if cmd.startswith("$((", i):
            _body, i, sources = _arithmetic_expansion(cmd, i)
            for source in sources:
                embedded.extend(split_commands(source, _parse_depth + 1, _deadline))
            append_tok("$((__ARITH__))")
            continue
        if cmd.startswith("$(", i):
            body, i = _command_substitution(cmd, i)
            embedded.extend(split_commands(body, _parse_depth + 1, _deadline))
            append_tok("$(__COMMAND__)")
            continue
        if cmd.startswith("${", i):
            text, i, sources = _parameter_expansion(cmd, i)
            for source in sources:
                embedded.extend(split_commands(source, _parse_depth + 1, _deadline))
            append_tok(text)
            continue
        if c == "`":
            body, i = _backtick_substitution(cmd, i)
            embedded.extend(split_commands(body, _parse_depth + 1, _deadline))
            append_tok("`__COMMAND__`")
            continue
        if c == "\\" and i + 1 < n:
            if cmd[i + 1] != "\n":
                append_tok(cmd[i + 1], "escaped")
            i += 2
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
    for source in heredoc_sources:
        embedded.extend(split_commands(source, _parse_depth + 1, _deadline))
    for source in function_sources:
        embedded.extend(split_commands(source, _parse_depth + 1, _deadline))
    out.extend(embedded)
    if len(out) > MAX_SUBCOMMANDS:
        raise CommandParseError(
            f"command source exceeds the {MAX_SUBCOMMANDS}-subcommand parse limit")
    return out


CONTROL_KEYWORDS = {"!", "do", "then", "else", "elif", "if", "while", "until", "time",
                    "nocorrect", "noglob"}
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
SHELLS = {"sh", "bash", "zsh", "dash", "ksh"}
GIT_HAZARD_SUBCOMMANDS = {
    "grep", "show", "diff", "cat-file", "log", "ls-tree", "archive", "checkout",
    "restore", "rev-parse", "blame", "shortlog", "rev-list",
}
# Query the resolved Git's non-helper command inventory once per guard process. Names
# outside that executing binary's inventory can be supplied by ambient alias/config or
# git-NAME helpers, neither of which argv inspection can authorize.
_GIT_AUTHORITY_CACHE = {}


def _remaining_probe_timeout(deadline, clock):
    remaining = deadline - clock()
    if remaining <= 0:
        raise GitAuthorityError("the guard's internal Git-discovery budget was exhausted")
    return min(GIT_PROBE_TIMEOUT_SECONDS, remaining)


def trusted_git_authority(executable="git", deadline=None, *, runner=None, clock=None):
    """Bind command authority to the one Git selected by the inherited PATH.

    A different executable is never probed and never inherits inventories or config from
    the PATH-selected Git. Discovery calls share the hook's monotonic deadline; any timeout,
    subprocess failure, or incomplete inventory is uncertainty rather than permission.
    """
    runner = subprocess.run if runner is None else runner
    clock = time.monotonic if clock is None else clock
    deadline = clock() + GUARD_BUDGET_SECONDS if deadline is None else deadline
    trusted = shutil.which("git")
    candidate = (shutil.which(executable) if os.sep not in executable else executable)
    if not trusted or not candidate:
        raise GitAuthorityError("the Git executable cannot be resolved")
    trusted = os.path.realpath(trusted)
    candidate = os.path.realpath(candidate)
    if candidate != trusted:
        raise GitAuthorityError(
            "the command selects a Git executable other than the PATH-trusted Git")
    if trusted not in _GIT_AUTHORITY_CACHE:
        try:
            exec_path_result = runner(
                [trusted, "--exec-path"], capture_output=True, text=True,
                timeout=_remaining_probe_timeout(deadline, clock),
            )
            builtins_result = runner(
                [trusted, "--list-cmds=builtins"], capture_output=True,
                text=True, timeout=_remaining_probe_timeout(deadline, clock),
            )
            main_result = runner(
                [trusted, "--list-cmds=main,nohelpers"], capture_output=True,
                text=True, timeout=_remaining_probe_timeout(deadline, clock),
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise GitAuthorityError(
                f"trusted Git command discovery failed: {exc!r}") from exc
        exec_path = exec_path_result.stdout.strip()
        builtins = frozenset(builtins_result.stdout.split())
        main = frozenset(main_result.stdout.split())
        if (exec_path_result.returncode or builtins_result.returncode
                or main_result.returncode or not exec_path or not builtins or not main
                or not {"grep", "status"} <= builtins
                or "submodule" in builtins or "submodule" not in main):
            raise GitAuthorityError("trusted Git command discovery failed or drifted")
        _GIT_AUTHORITY_CACHE[trusted] = GitAuthority(
            trusted, os.path.realpath(exec_path), builtins, main,
        )
    return _GIT_AUTHORITY_CACHE[trusted]


def authorize_git_subcommand(subcommand, authority, effective_exec_path):
    if subcommand in authority.builtins:
        # git-config(1): aliases that hide existing Git commands are ignored. This holds
        # only because `trusted_git_authority` already proved the executable identity.
        return None
    if subcommand in authority.main:
        if os.path.realpath(effective_exec_path) != authority.exec_path:
            return (f"Git subcommand {subcommand!r} is not builtin and the effective "
                    "GIT_EXEC_PATH differs from the trusted Git exec path")
        return None
    return (f"Git subcommand {subcommand!r} is not a proven native command and may "
            "be supplied by ambient alias/config")
# A bare name is not an identity: aliases and functions can replace it before execution.
# Only `builtin`/structurally parsed `command` or these exact system paths may carry a
# guarded-looking argv without becoming `ask`; selftest executes every accepted identity.
SHELL_NON_FORWARDING_COMMANDS = {"echo", "printf"}
TRUSTED_EXTERNAL_NON_FORWARDING_COMMANDS = {
    "/bin/cat", "/bin/echo", "/usr/bin/printf",
}
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


def _equals_expanded(word):
    """Resolve zsh's `=name` command form, which bash does not have.

    The Bash tool's shell is zsh on this host, and zsh expands a leading `=` on a command
    word to that name's PATH resolution before execution, so `=git` IS git. Comparing the
    raw word to `git` read `=git grep -E` and `=git show $SHA:src/f.py` as unrelated
    commands and allowed both, while the sibling zsh-only forms `noglob` and `nocorrect`
    were already modelled beside it.

    Measured on zsh 5.9: `=git` runs git; `==git` reports `=git not found`; `"=git"`,
    `'=git'` and `setopt noequals` all leave it literal. Quoting is gated by
    `_equals_expansion_is_live`; the option state is applied by `unwrap_command_prefix`.
    """
    return word[1:] if len(word) > 1 and word[0] == "=" and word[1] != "=" else word


def _equals_expansion_is_live(text, quoting):
    """Whether a leading `=` is syntactically live; shell and option state are separate."""
    if not (len(text) > 1 and text[0] == "=" and text[1] != "="):
        return False
    if quoting.startswith("mixed:"):
        return quoting.split(":", 1)[1][:1] == "U"
    return quoting == ""


# One PATH walk per (name, PATH) per guard process. A live `=name` may repeat across an
# argv, and each miss stats every PATH entry: 20,000 repeats cost 36.9 s and 60,000 did not
# finish inside a 90 s bound, both under MAX_TOKENS.
_EQUALS_LOOKUP_CACHE = {}


def _resolve_outer_zsh_equals(tokens, shell, equals_state, command_env,
                              lookup_authority_uncertain):
    """Resolve live ``=name`` words before command wrappers change the environment.

    zsh performs filename generation for every live word in the outer command before
    ``env``, ``command -p``, or ``sudo`` executes. Preserve that absolute identity so a
    later wrapper cannot incorrectly turn a known ERE/PCRE decision into lookup doubt.
    A child shell receives its own environment and lookup uncertainty through
    ``ShellInvocation`` and therefore does not borrow the parent's resolution.
    """
    prepared = list(tokens)
    if shell != "zsh" or equals_state != ZSH_EQUALS_ON:
        return prepared
    if lookup_authority_uncertain:
        return prepared
    search_path = command_env.get("PATH")
    for index, (text, quoting) in enumerate(prepared):
        if not _equals_expansion_is_live(text, quoting):
            continue
        name = _equals_expanded(text)
        key = (name, search_path)
        if key not in _EQUALS_LOOKUP_CACHE:
            resolved = shutil.which(name, path=search_path)
            _EQUALS_LOOKUP_CACHE[key] = (
                os.path.realpath(resolved) if resolved else None)
        resolved = _EQUALS_LOOKUP_CACHE[key]
        if resolved:
            prepared[index] = (resolved, quoting)
    return prepared


def _zsh_equals_option_action(tokens):
    """Return the definite EQUALS state established by one straight-line command.

    Only the three literal forms grounded against zsh are authority. A setter in a
    conditional/list context, a dynamic command, eval, or sourced code can change the
    calling shell but is not interpreted here, so it returns ``unknown``.
    """
    if not tokens:
        return None
    has_control = any(text in CONTROL_KEYWORDS for text, _quoting in tokens)
    words = [text for text, _quoting in tokens if text not in CONTROL_KEYWORDS
             and not ASSIGNMENT.match(text)]
    if not words:
        return None
    executable = words[0]
    if executable in {"eval", "source", "."} or UNRESOLVED.search(executable):
        return ZSH_EQUALS_UNKNOWN
    if executable == "set":
        if words == ["set", "-o", "equals"]:
            return ZSH_EQUALS_ON
        if words in (["set", "-o", "noequals"], ["set", "+o", "equals"]):
            return ZSH_EQUALS_OFF
        if words == ["set", "+o", "noequals"]:
            return ZSH_EQUALS_ON
        if any("equals" in word.lower() or UNRESOLVED.search(word)
               for word in words[1:]):
            return ZSH_EQUALS_UNKNOWN
        return None
    if executable == "emulate":
        modes = [word.lower() for word in words[1:] if not word.startswith("-")]
        if len(modes) == 1 and modes[0] == "zsh":
            return ZSH_EQUALS_ON
        if len(modes) == 1 and modes[0] in {"sh", "ksh", "bash"}:
            return ZSH_EQUALS_OFF
        return ZSH_EQUALS_UNKNOWN
    if executable not in {"setopt", "unsetopt"}:
        return None
    if has_control:
        return ZSH_EQUALS_UNKNOWN
    if words == ["setopt", "equals"]:
        return ZSH_EQUALS_ON
    if words == ["setopt", "noequals"] or words == ["unsetopt", "equals"]:
        return ZSH_EQUALS_OFF
    # A different literal option command is harmless unless it mentions this option.
    # Dynamic or compound option spellings are not proof of either state.
    if any("equals" in word.lower() or UNRESOLVED.search(word) for word in words[1:]):
        return ZSH_EQUALS_UNKNOWN
    return None


def _zsh_option_skeleton(source, deadline=None):
    """Blank quoted bytes while preserving source offsets for option-state events."""
    # With no quote and no backslash there is nothing to blank, so the skeleton is the
    # source. This runs twice per decision over the whole command.
    if not any(char in source for char in "'\"\\"):
        return source
    live = []
    quote = ""
    index = 0
    while index < len(source):
        if index % 256 == 0:
            _check_decision_budget(deadline)
        char = source[index]
        if quote:
            if char == "\\" and quote == '"' and index + 1 < len(source):
                live.extend("  ")
                index += 2
                continue
            live.append(" ")
            if char == quote:
                quote = ""
            index += 1
            continue
        if char in ("'", '"'):
            quote = char
            live.append(" ")
            index += 1
            continue
        if char == "\\" and index + 1 < len(source):
            live.extend("  ")
            index += 2
            continue
        live.append(char)
        index += 1
    return "".join(live)


def zsh_equals_states(source, commands, initial=ZSH_EQUALS_ON, deadline=None):
    """State before each parsed command, preserving only proven straight-line changes.

    ``split_commands`` intentionally flattens several compound forms. If an EQUALS setter
    appears beside live control/scope syntax, the state is therefore uncertain rather than
    pretending the option mutation is unconditional or leaks out of a child scope.
    Nested literal shell bodies are parsed by their recursive ``decide`` call and are
    quoted here, so they do not contaminate this source's state.
    """
    _check_decision_budget(deadline)
    state = initial
    states = []
    records = function_declaration_records(source, deadline)
    lexical_source = _zsh_option_skeleton(source, deadline)
    state_source = list(lexical_source)
    excluded = []
    for record in records:
        state_source[record.start:record.end] = " " * (record.end - record.start)
        excluded.append((record.start, record.end))
    for start, end in _function_scope_pairs(source, records, deadline):
        state_source[start:end + 1] = " " * (end + 1 - start)
        excluded.append((start, end + 1))
    _cleaned, invoked_sources = extract_function_invocations(source, deadline)
    invoked_setter = any(
        re.search(r"\b(?:setopt|unsetopt|emulate)\b|\bset\s+[+-]o\b", body)
        for body in invoked_sources
    )
    skeleton = "".join(state_source)
    complex_setter = invoked_setter or (
        re.search(r"\b(?:setopt|unsetopt|emulate)\b|\bset\s+[+-]o\b",
                  skeleton) is not None
        and (re.search(r"&&|\|\||[(){}|]", skeleton) is not None
             or re.search(r"\b(?:if|then|elif|else|fi|while|until|for|case|function)\b",
                          skeleton) is not None)
    )
    if complex_setter:
        state = ZSH_EQUALS_UNKNOWN
    used_action_positions = set()
    for tokens in commands:
        states.append(state)
        action = _zsh_equals_option_action(tokens)
        if action is not None:
            action_words = [re.escape(text) for text, _quoting in tokens
                            if text not in CONTROL_KEYWORDS
                            and not ASSIGNMENT.match(text)]
            pattern = r"(?<![A-Za-z0-9_])" + r"\s+".join(action_words)
            positions = [match.start() for match in re.finditer(
                pattern, lexical_source) if match.start() not in used_action_positions]
            position = positions[0] if positions else None
            if position is not None:
                used_action_positions.add(position)
            inside_excluded_scope = (position is not None and any(
                start <= position < end for start, end in excluded))
            if inside_excluded_scope:
                continue
            state = (ZSH_EQUALS_UNKNOWN
                     if complex_setter or position is None else action)
    return tuple(states)


def _path_environment_action(tokens):
    """Return one proven shell-persistent PATH action, or ``None``."""
    words = [word for word, _quoting in tokens]
    while words and words[0] in CONTROL_KEYWORDS:
        words = words[1:]
    if words and all(ASSIGNMENT.match(word) for word in words):
        updates = {}
        for word in words:
            key, value = word.split("=", 1)
            if key == "PATH":
                updates[key] = value
        return (updates, ()) if updates else None
    if words and words[0] == "export":
        tail = words[1:]
        while tail and tail[0] in {"-x", "--"}:
            tail = tail[1:]
        if tail and all(ASSIGNMENT.match(word) for word in tail):
            updates = {}
            for word in tail:
                key, value = word.split("=", 1)
                if key == "PATH":
                    updates[key] = value
            return (updates, ()) if updates else None
    if words and words[0] == "unset":
        tail = words[1:]
        while tail and tail[0] in {"-v", "--"}:
            tail = tail[1:]
        if tail == ["PATH"]:
            return ({}, ("PATH",))
    return None


def command_environment_states(
        source, commands, initial_env=None, initial_lookup_uncertain=False,
        deadline=None):
    """Return the environment and lookup authority before each parsed command.

    Only assignment-only, ``export PATH=...``, and ``unset PATH`` statements at the
    current shell scope advance definite state. Conditional or otherwise unmodelled PATH
    mutation becomes uncertainty; function bodies and subshells cannot silently rewrite
    their parent's lookup state.
    """
    current_env = dict(os.environ if initial_env is None else initial_env)
    current_lookup = bool(initial_lookup_uncertain)
    states = []
    records = function_declaration_records(source, deadline)
    lexical_source = _zsh_option_skeleton(source, deadline)
    excluded = [(record.start, record.end) for record in records]
    for start, end in _function_scope_pairs(source, records, deadline):
        excluded.append((start, end + 1))
    conditional = _conditional_function_intervals(source, records, deadline)
    invoked_path_mutation = any(
        re.search(r"(?:^|[;\s])(?:PATH=|export\s+PATH=|unset\s+(?:-v\s+)?PATH\b)",
                  body)
        for body in extract_function_invocations(source, deadline)[1]
    )
    dynamic_path_mutation = invoked_path_mutation or bool(re.search(
        r"(?:^|[;\s])(?:source|\.)\s+|\beval\b[^;\n]*\bPATH\b", lexical_source))
    operators, _record_braces = _function_list_operators(source, records, deadline)
    used_positions = set()
    for tokens in commands:
        _check_decision_budget(deadline)
        states.append((dict(current_env), current_lookup))
        action = _path_environment_action(tokens)
        if action is None:
            continue
        words = [re.escape(word) for word, _quoting in tokens]
        pattern = r"(?<![A-Za-z0-9_])" + r"\s+".join(words)
        positions = [match.start() for match in re.finditer(pattern, lexical_source)
                     if match.start() not in used_positions]
        position = positions[0] if positions else None
        if position is not None:
            used_positions.add(position)
        if position is not None and any(start <= position < end
                                        for start, end in excluded):
            continue
        maybe = (position is None or dynamic_path_mutation
                 or (position is not None and any(
                     start < position < end for start, end in conditional))
                 or (position is not None and any(
                     operator[0] < position and operator[2] in {"&&", "||", "|"}
                     for operator in operators)))
        if maybe:
            current_lookup = True
            continue
        updates, removals = action
        current_env.update(updates)
        for name in removals:
            current_env.pop(name, None)
        current_lookup = True
    return tuple(states)


def zsh_invocation_equals_state(words, default=ZSH_EQUALS_ON):
    """Resolve literal zsh startup option spellings that alter EQUALS."""
    if not words or os.path.basename(words[0]) != "zsh":
        return ZSH_EQUALS_OFF
    return _zsh_argv_state(words, default).equals_state


_ENV_OCCURRENCE_MARKER = "__ZHAR_ENV_OCCURRENCE__"


def _marked_occurrence_command_index(source, deadline=None):
    """Return the command containing the exact occurrence marker."""
    commands = split_commands(source, _deadline=deadline)
    matches = []
    for index, tokens in enumerate(commands):
        if not any(word == _ENV_OCCURRENCE_MARKER
                   for word, _quoting in tokens):
            continue
        # A redirect following a closed subshell, ``(sh) <<< ...``, belongs to
        # that preceding command even though inserting a word at the redirect
        # offset makes the marker a standalone lexical command.
        marker_only = all(word == _ENV_OCCURRENCE_MARKER
                          for word, _quoting in tokens)
        matches.append(index - 1 if marker_only and index > 0 else index)
    if len(matches) != 1:
        raise CommandParseError("source occurrence does not map to one command")
    return matches[0]


def _occurrence_command_index(source, offset, deadline=None):
    """Return the command containing one exact source offset."""
    marked = (source[:offset] + " " + _ENV_OCCURRENCE_MARKER + " "
              + source[offset:])
    return _marked_occurrence_command_index(marked, deadline)


def _command_at_occurrence(source, offset, deadline=None):
    """Return the token record containing one exact source offset."""
    marked = (source[:offset] + " " + _ENV_OCCURRENCE_MARKER + " "
              + source[offset:])
    commands = split_commands(marked, _deadline=deadline)
    index = _occurrence_command_index(source, offset, deadline)
    return [token for token in commands[index]
            if token[0] != _ENV_OCCURRENCE_MARKER]


def _occurrence_environment(
        prefix, fragment, occurrence_offset, command_env=None,
        lookup_authority_uncertain=False, deadline=None):
    """Return authority state before one exact occurrence, including prior lines."""
    joined = prefix
    if joined and fragment and not joined.endswith(("\n", ";")):
        joined += "\n"
    fragment_start = len(joined)
    joined += fragment
    marked_joined = (joined[:fragment_start + occurrence_offset] + " "
                     + _ENV_OCCURRENCE_MARKER + " "
                     + joined[fragment_start + occurrence_offset:])
    marked_cleaned = command_without_heredoc_payloads(marked_joined, deadline)
    target_index = _marked_occurrence_command_index(marked_cleaned, deadline)
    cleaned = command_without_heredoc_payloads(joined, deadline)
    commands = split_commands(cleaned, _deadline=deadline)
    if not commands:
        return (dict(os.environ if command_env is None else command_env),
                bool(lookup_authority_uncertain))
    states = command_environment_states(
        cleaned, commands, command_env, lookup_authority_uncertain, deadline)
    if target_index >= len(states):
        raise CommandParseError("source occurrence command has no environment state")
    return states[target_index]


def _heredoc_occurrence_environment(
        finding, command_env=None, lookup_authority_uncertain=False,
        deadline=None):
    """Bind an executable heredoc header to its preceding command state."""
    return _occurrence_environment(
        finding.prefix, finding.header, finding.header_offset, command_env,
        lookup_authority_uncertain, deadline)


def _heredoc_expansion_environment(
        finding, command_env=None, lookup_authority_uncertain=False,
        deadline=None):
    """Bind an unquoted heredoc expansion to its preceding command state."""
    return _occurrence_environment(
        finding.prefix, finding.header, finding.header_offset, command_env,
        lookup_authority_uncertain, deadline)


def _here_string_occurrence_environment(
        source, fragment, command_env=None, lookup_authority_uncertain=False,
        deadline=None):
    """Bind a here-string source to state established on prior physical lines."""
    return _occurrence_environment(
        source.prefix, fragment, source.redirect_start, command_env,
        lookup_authority_uncertain, deadline)


def _literal_git_word(word):
    word = _equals_expanded(word)
    return (os.path.basename(word) == "git"
            or bool(re.search(r"(?:^|\s)(?:/[^\s]*/)?=?git(?:\s|$)", word)))


def _guarded_subcommand_after(words):
    """index -> whether a guarded subcommand occupies a LATER index.

    One backward pass, so the two tail predicates below are linear in the token count.
    Rescanning the tail per candidate word was quadratic: `echo git git ...` with 20,000
    `git` words -- 60 KiB, well inside MAX_COMMAND_CHARS -- spent 32 s in
    `os.path.basename` alone, and `unwrap_command_prefix` never consults the deadline, so
    nothing stopped it inside a hook registered with a five-second timeout.
    """
    later = [False] * (len(words) + 1)
    for index in range(len(words) - 1, -1, -1):
        later[index] = (later[index + 1]
                        or os.path.basename(words[index]) in GIT_HAZARD_SUBCOMMANDS)
    return later


def has_literal_guarded_git_tail(tokens):
    """Whether argv visibly contains `git` followed by a guarded subcommand."""
    words = [text for text, _quoting in tokens]
    guarded_after = _guarded_subcommand_after(words)
    for index, word in enumerate(words):
        if os.path.basename(_equals_expanded(word)) != "git":
            continue
        if guarded_after[index + 1]:
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


def source_has_git_hazard_hint(command, deadline=None):
    """Conservative Git-hazard hint for a nested command source string."""
    try:
        commands = split_commands(command, _deadline=deadline)
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


def source_has_live_unresolved(source, deadline=None):
    """Inspect command source as the downstream shell or eval will parse it."""
    try:
        commands = split_commands(source, _deadline=deadline)
    except CommandParseError:
        return True
    return any(_token_has_live_unresolved(token) for tokens in commands
               for token in tokens)


def source_has_dynamic_command_word(source, deadline=None):
    """Whether the EXECUTABLE of any subcommand in this source is itself an expansion.

    `sh -c "$CMD"` is genuinely unknowable and must stay a question. `sh -c 'git show
    $SHA:x'` names its command and expands only an argument, so it can be judged on what
    is written. Treating both as "dynamic" questioned ordinary commands whose only sin was
    containing a `$`.
    """
    try:
        commands = split_commands(source, _deadline=deadline)
    except CommandParseError:
        return True
    for tokens in commands:
        words = [token for token in tokens if token[0] not in CONTROL_KEYWORDS
                 and not ASSIGNMENT.match(token[0])]
        if words and _token_has_live_unresolved(words[0]):
            return True
    return False


def has_dynamic_guarded_command_tail(tokens):
    """Whether a live expansion may choose an executable before a guarded operation."""
    words = [text for text, _quoting in tokens]
    guarded_after = _guarded_subcommand_after(words)
    for index, token in enumerate(tokens):
        if not _token_has_live_unresolved(token):
            continue
        if guarded_after[index + 1]:
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


GIT_LOOKUP_AUTHORITY_ERROR = (
    "Git executable lookup or configuration authority changes across a wrapper, so "
    "the PATH-trusted Git inventory cannot be transferred"
)
ZSH_EQUALS_LOOKUP_AUTHORITY_ERROR = (
    "zsh EQUALS executable lookup could not be resolved from the effective shell "
    "environment"
)


def changed_git_lookup_authority_error(executable, lookup_authority_uncertain):
    """Reject Git authority transfer across wrappers that change executable lookup."""
    if (os.path.basename(executable) == "git" and os.sep not in executable
            and lookup_authority_uncertain):
        return GIT_LOOKUP_AUTHORITY_ERROR
    return ""


def only_changed_git_lookup_authority_error(resolution):
    """True when prefix parsing resolved Git but could not transfer its authority."""
    return (bool(resolution.errors)
            and all(error == GIT_LOOKUP_AUTHORITY_ERROR
                    for error in resolution.errors))


def only_changed_zsh_equals_lookup_authority_error(resolution):
    """True when a live =name is known but its changed PATH authority is not."""
    return (bool(resolution.errors)
            and all(error == ZSH_EQUALS_LOOKUP_AUTHORITY_ERROR
                    for error in resolution.errors))


def unwrap_command_prefix(tokens, shell="zsh", equals_state=ZSH_EQUALS_ON,
                          command_env=None, lookup_authority_uncertain=False):
    """Resolve the executable boundary shared by both guards.

    The result retains uncertainty instead of guessing through a dynamic executable,
    malformed wrapper, or argv-rewriting launcher. Callers combine that uncertainty with
    `hazard_hint` and return `ask` rather than treating an unresolved command as clean.
    """
    original = list(tokens)
    command_env = dict(os.environ if command_env is None else command_env)
    items = _resolve_outer_zsh_equals(
        tokens, shell, equals_state, command_env, lookup_authority_uncertain)
    errors = []
    guarded_prefix_hazard = False
    wrapper_depth = 0
    env_splits = 0
    command_bypass_next = False
    lookup_authority_uncertain = bool(lookup_authority_uncertain)
    descendant_lookup_authority_uncertain = lookup_authority_uncertain
    while items:
        while items and items[0][0] in CONTROL_KEYWORDS:
            items.pop(0)
        while items and ASSIGNMENT.match(items[0][0]):
            key, value = items.pop(0)[0].split("=", 1)
            command_env[key] = value
            if key == "PATH":
                lookup_authority_uncertain = True
                descendant_lookup_authority_uncertain = True
        if not items:
            break

        bypasses_shell_identity = command_bypass_next
        command_bypass_next = False
        executable_text = items[0][0]
        if _equals_expansion_is_live(*items[0]) and shell == "zsh":
            # Write the resolved name back so every downstream reader -- this loop, the
            # grep guard's argv walk and the zsh guard's rev:path gate -- sees the command
            # zsh will actually run rather than the `=` form. Quoting suppresses the
            # expansion, so a quoted `=git` keeps its literal name and falls to the
            # generic identity check below like any other unproven command word.
            if equals_state == ZSH_EQUALS_ON:
                errors.append(ZSH_EQUALS_LOOKUP_AUTHORITY_ERROR)
                break
            else:
                errors.append(
                    "zsh EQUALS expansion is disabled" if equals_state == ZSH_EQUALS_OFF
                    else "zsh EQUALS expansion state is uncertain")
                break
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
                    # `command -p` changes how this one executable is located. It does
                    # not rewrite the environment inherited by a launched shell, so a
                    # child must not borrow this launcher's lookup uncertainty.
                    lookup_authority_uncertain = True
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
                    lookup_authority_uncertain = True
                    descendant_lookup_authority_uncertain = True
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
                        if value == "PATH":
                            lookup_authority_uncertain = True
                            descendant_lookup_authority_uncertain = True
                    continue
                if word.startswith("--unset="):
                    unset_name = word.split("=", 1)[1]
                    command_env.pop(unset_name, None)
                    if unset_name == "PATH":
                        lookup_authority_uncertain = True
                        descendant_lookup_authority_uncertain = True
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
                    if key == "PATH":
                        lookup_authority_uncertain = True
                        descendant_lookup_authority_uncertain = True
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
            if executable == "sudo":
                lookup_authority_uncertain = True
                descendant_lookup_authority_uncertain = True
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

        if executable == "eval":
            break

        lookup_error = changed_git_lookup_authority_error(
            executable_text, lookup_authority_uncertain)
        if lookup_error:
            errors.append(lookup_error)
            guarded_prefix_hazard = True
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
        # This is also the arm that answers for a launcher whose argv rewriting is not
        # modelled -- xargs, ssh, flock, su and the rest. It deliberately fires on a
        # GUARDED tail rather than on the launcher's name: asking on the name alone
        # questioned `git diff --name-only | xargs git add`, and `add` is a subcommand
        # neither guard reasons about. A separate name-keyed arm above this one decided
        # nothing these three predicates did not already decide, so it was removed rather
        # than left as a list that reads like coverage.
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
        command_has_git_hazard_hint(original) or guarded_prefix_hazard,
        lookup_authority_uncertain, descendant_lookup_authority_uncertain)


def _descendant_lookup_authority(resolution):
    """Select lookup uncertainty inherited inside a launched shell."""
    return resolution.descendant_lookup_authority_uncertain


def nested_shell_invocation(resolution, current_shell="sh", deadline=None):
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
                " ".join(word for word, _quoting in args), deadline),
            dict(resolution.command_env),
            _descendant_lookup_authority(resolution),
        )
    if shell not in SHELLS:
        return None
    args = resolution.items[1:]
    if shell == "zsh":
        words = [word for word, _quoting in resolution.items]
        state = _zsh_argv_state(words)
        if state.command_index is None:
            return None
        command_arg = resolution.items[state.command_index]
        return ShellInvocation(
            shell, command_arg[0],
            source_has_live_unresolved(command_arg[0], deadline),
            dict(resolution.command_env),
            _descendant_lookup_authority(resolution))
    for index, (word, _quoting) in enumerate(args):
        if word == "--":
            continue
        if word == "-c" or (word.startswith("-") and not word.startswith("--")
                             and "c" in word[1:]):
            command_arg = args[index + 1] if index + 1 < len(args) else ("", "")
            return ShellInvocation(
                shell, command_arg[0],
                source_has_live_unresolved(command_arg[0], deadline),
                dict(resolution.command_env),
                _descendant_lookup_authority(resolution))
    return None


def nested_shell_equals_state(resolution, invocation, inherited=ZSH_EQUALS_ON):
    """Return EQUALS state for an eval body or a newly launched shell."""
    if invocation.shell != "zsh":
        return ZSH_EQUALS_OFF
    executable = (os.path.basename(resolution.items[0][0])
                  if resolution.items else "")
    if executable == "eval":
        return inherited
    words = [word for word, _quoting in resolution.items]
    return zsh_invocation_equals_state(words)


def _strongest_decision(decisions):
    """Return the highest-severity decision without making source order authority."""
    rank = {"allow": 0, "ask": 1, "deny": 2}
    worst = max(rank[decision] for decision, _reason in decisions)
    selected = [(decision, reason) for decision, reason in decisions
                if rank[decision] == worst]
    return selected[0][0], "\n\n".join(reason for _decision, reason in selected)


def _reduce_stdin_provenance(findings):
    """Reduce every stdin-source decision so an earlier question cannot mask denial."""
    decision, reason = _strongest_decision(
        [(finding.decision, finding.reason) for finding in findings])
    return StdinProvenance(decision, reason)


def heredoc_equals_decision(
        command, deadline=None, subcommands=None, classifier=None,
        current_shell="zsh", inherited_equals_state=ZSH_EQUALS_ON,
        command_env=None, lookup_authority_uncertain=False,
        classify_non_direct_shell_bodies=False):
    """Recursively classify direct shell heredocs with deny precedence."""
    equals_findings = []
    shell_findings = []
    expansion_findings = []
    try:
        extract_heredoc_sources(
            command, deadline, equals_findings, subcommands, shell_findings,
            expansion_findings, classify_non_direct_shell_bodies)
    except CommandParseError:
        return None
    findings = shell_findings + [finding for finding in equals_findings
                                 if finding not in shell_findings]
    decisions = []
    for finding in findings:
        _check_decision_budget(deadline)
        resolved_env = dict(command_env or os.environ)
        resolved_lookup = lookup_authority_uncertain
        try:
            occurrence_env, occurrence_lookup = _heredoc_occurrence_environment(
                finding, command_env, lookup_authority_uncertain, deadline)
            header_command = _command_at_occurrence(
                finding.header, finding.header_offset, deadline)
            resolution = unwrap_command_prefix(
                header_command, current_shell, inherited_equals_state,
                occurrence_env, occurrence_lookup)
            resolved_env = resolution.command_env
            resolved_lookup = _descendant_lookup_authority(resolution)
            words = [word for word, _quoting in resolution.items]
            state = (zsh_invocation_equals_state(words)
                     if finding.shell == "zsh" else ZSH_EQUALS_OFF)
        except (CommandParseError, IndexError):
            state = ZSH_EQUALS_UNKNOWN
        if classifier is None:
            decision = ("deny" if finding.shell == "zsh" and state == ZSH_EQUALS_ON
                        else "ask")
            reason = ("a zsh heredoc executes guarded `=git` syntax while its EQUALS "
                      "option is enabled" if decision == "deny"
                      else f"a {finding.shell} heredoc contains guarded `=git` syntax but its "
                      "executable identity is not proven")
        else:
            decision, reason = classifier(
                finding.body, finding.shell, state, deadline,
                resolved_env, resolved_lookup)
        if decision != "allow":
            decisions.append((decision, reason))
    if classifier is not None:
        for finding in expansion_findings:
            _check_decision_budget(deadline)
            try:
                resolved_env, resolved_lookup = _heredoc_expansion_environment(
                    finding, command_env, lookup_authority_uncertain, deadline)
            except CommandParseError:
                resolved_env = dict(command_env or os.environ)
                resolved_lookup = True
            decision, reason = classifier(
                finding.source, current_shell, inherited_equals_state, deadline,
                resolved_env, resolved_lookup)
            if decision != "allow":
                decisions.append((decision, reason))
    if not decisions:
        return None
    return _strongest_decision(decisions)

def _alias_table(configs):
    aliases = {}
    for config in configs:
        key, separator, value = config.partition("=")
        normalized = key.strip().lower()
        if separator and normalized.startswith("alias.") and len(normalized) > 6:
            aliases[normalized[6:]] = value
    return aliases


def _git_config_parameter_items(parameters):
    """Parse Git's quoted GIT_CONFIG_PARAMETERS transport or return one error."""
    if not parameters:
        return [], None
    entry = re.compile(
        r"'((?:[^']|'\\'')*)'(?:='((?:[^']|'\\'')*)')?")
    configs = []
    cursor = 0
    for match in entry.finditer(parameters):
        if parameters[cursor:match.start()].strip():
            return [], "GIT_CONFIG_PARAMETERS contains unmodelled quoting"
        key = match.group(1).replace("'\\''", "'")
        quoted_value = (match.group(2) or "").replace("'\\''", "'")
        if match.group(2) is not None:
            configs.append(f"{key}={quoted_value}")
        elif "=" in key:
            configs.append(key)
        else:
            return [], f"GIT_CONFIG_PARAMETERS entry {key!r} has no value"
        cursor = match.end()
    if parameters[cursor:].strip() or not configs:
        return [], "GIT_CONFIG_PARAMETERS contains unmodelled quoting"
    return configs, None


ALIAS_HARMLESS = "harmless"
ALIAS_GUARDED = "guarded"
ALIAS_UNCERTAIN = "uncertain"


def _alias_guard_state(
        name, aliases, seen=(), depth=0, deadline=None, command_env=None,
        lookup_authority_uncertain=False):
    """Classify a standard alias chain without collapsing uncertainty into safety."""
    lowered = name.lower()
    if lowered in GIT_HAZARD_SUBCOMMANDS:
        return ALIAS_GUARDED
    if lowered in seen:
        return ALIAS_UNCERTAIN
    if lowered not in aliases:
        return ALIAS_HARMLESS
    if depth >= MAX_ALIAS_DEPTH:
        return ALIAS_UNCERTAIN
    body = aliases[lowered]
    if body.startswith("!"):
        return _shell_alias_guard_state(
            body[1:], aliases, seen + (lowered,), depth + 1,
            deadline=deadline, command_env=command_env,
            lookup_authority_uncertain=lookup_authority_uncertain)
    try:
        words = shlex.split(body, posix=True)
    except ValueError:
        return ALIAS_UNCERTAIN
    local_aliases = dict(aliases)
    index = 0
    while index < len(words) and words[index] == "-c":
        if index + 1 >= len(words):
            return ALIAS_UNCERTAIN
        key, separator, value = words[index + 1].partition("=")
        normalized = key.strip().lower()
        if separator and normalized.startswith("alias.") and len(normalized) > 6:
            local_aliases[normalized[6:]] = value
        index += 2
    if index >= len(words) or words[index].startswith("-"):
        return ALIAS_UNCERTAIN
    return _alias_guard_state(
        words[index], local_aliases, seen + (lowered,), depth + 1, deadline,
        command_env, lookup_authority_uncertain)


def _shell_alias_git_state(resolution, aliases, seen, depth, deadline=None):
    """Classify one literal Git invocation reached from shell alias source."""
    words = [word for word, _quoting in resolution.items]
    if not words or os.path.basename(words[0]) != "git":
        return ALIAS_HARMLESS
    index = 1
    local_aliases = dict(aliases)
    parameter_configs, parameter_error = _git_config_parameter_items(
        resolution.command_env.get("GIT_CONFIG_PARAMETERS"))
    if parameter_error:
        return ALIAS_UNCERTAIN
    local_aliases.update(_alias_table(parameter_configs))
    if any(resolution.command_env.get(name)
           for name in ("GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM")):
        return ALIAS_UNCERTAIN
    count_text = resolution.command_env.get("GIT_CONFIG_COUNT")
    if count_text is not None:
        try:
            count = int(count_text)
            if count < 0:
                raise ValueError
        except ValueError:
            return ALIAS_UNCERTAIN
        for config_index in range(count):
            key = resolution.command_env.get(f"GIT_CONFIG_KEY_{config_index}")
            value = resolution.command_env.get(f"GIT_CONFIG_VALUE_{config_index}")
            if key is None or value is None:
                return ALIAS_UNCERTAIN
            normalized = key.strip().lower()
            if normalized.startswith("alias.") and len(normalized) > 6:
                local_aliases[normalized[6:]] = value
    options_with_values = {
        "-C", "-c", "--git-dir", "--work-tree", "--namespace",
        "--super-prefix", "--exec-path", "--config-env", "--attr-source",
    }
    while index < len(words) and words[index].startswith("-"):
        if words[index] == "--":
            index += 1
            break
        option = words[index]
        if option.startswith("--config-env="):
            configured_key = option.split("=", 1)[1].partition("=")[0].strip().lower()
            if configured_key.startswith("alias."):
                return ALIAS_UNCERTAIN
        if option == "--config-env":
            if index + 1 >= len(words):
                return ALIAS_UNCERTAIN
            configured_key = words[index + 1].partition("=")[0].strip().lower()
            if configured_key.startswith("alias."):
                return ALIAS_UNCERTAIN
        if option == "-c":
            if index + 1 >= len(words):
                return ALIAS_UNCERTAIN
            key, separator, value = words[index + 1].partition("=")
            normalized = key.strip().lower()
            if normalized.startswith("alias."):
                if not separator or len(normalized) <= 6:
                    return ALIAS_UNCERTAIN
                local_aliases[normalized[6:]] = value
        if option in options_with_values:
            if index + 1 >= len(words):
                return ALIAS_UNCERTAIN
            index += 2
        else:
            index += 1
    if index >= len(words):
        return ALIAS_HARMLESS
    return _alias_guard_state(
        words[index], local_aliases, seen, depth + 1, deadline,
        resolution.command_env,
        resolution.descendant_lookup_authority_uncertain)


def _alias_authority_context(command_env, lookup_authority_uncertain):
    """Copy authority state at each shell-alias parser re-entry."""
    return dict(command_env), bool(lookup_authority_uncertain)


def _alias_command_environment_states(
        source, commands, command_env, lookup_authority_uncertain, deadline):
    """Bind alias commands to the same straight-line PATH state as public source."""
    return command_environment_states(
        source, commands, command_env, lookup_authority_uncertain, deadline)


def _shell_alias_guard_state(source, aliases, seen=(), depth=0,
                             current_shell="sh", deadline=None, command_env=None,
                             lookup_authority_uncertain=False):
    """Tri-state literal shell alias traversal shared with top-level shell parsing."""
    if depth > MAX_ALIAS_DEPTH:
        return ALIAS_UNCERTAIN
    if not isinstance(source, str) or not source:
        return ALIAS_UNCERTAIN
    alias_env = dict(os.environ if command_env is None else command_env)

    def classify_heredoc(body, shell, state, inner_deadline, env, lookup):
        nested_env, nested_lookup = _alias_authority_context(env, lookup)
        nested = _shell_alias_guard_state(
            body, aliases, seen, depth + 1, shell, inner_deadline,
            nested_env, nested_lookup)
        return (("allow", "") if nested == ALIAS_HARMLESS
                else ("ask", "shell alias heredoc is guarded or unresolved"))

    heredoc = heredoc_equals_decision(
        source, deadline, classifier=classify_heredoc,
        current_shell=current_shell,
        inherited_equals_state=(ZSH_EQUALS_ON if current_shell == "zsh"
                                else ZSH_EQUALS_OFF),
        command_env=alias_env,
        lookup_authority_uncertain=lookup_authority_uncertain)
    if heredoc is not None:
        return ALIAS_UNCERTAIN
    for here_source in live_here_string_sources(source):
        if here_source.descriptor != 0:
            continue
        direct = direct_here_string_invocation(
            here_source, current_shell,
            ZSH_EQUALS_ON if current_shell == "zsh" else ZSH_EQUALS_OFF,
            alias_env, lookup_authority_uncertain, deadline)
        if not direct:
            continue
        resolution, invocation = direct
        if here_source.dynamic:
            return ALIAS_UNCERTAIN
        nested_env, nested_lookup = _alias_authority_context(
            invocation.command_env, invocation.lookup_authority_uncertain)
        nested = _shell_alias_guard_state(
            here_source.body, aliases, seen, depth + 1, invocation.shell,
            deadline, nested_env, nested_lookup)
        if nested != ALIAS_HARMLESS:
            return nested
    try:
        commands = split_commands(source, _deadline=deadline)
    except CommandParseError:
        return ALIAS_UNCERTAIN
    environments = _alias_command_environment_states(
        source, commands, alias_env, lookup_authority_uncertain, deadline)
    state = ALIAS_HARMLESS
    for tokens, (nested_command_env, nested_lookup) in zip(
            commands, environments):
        resolution = unwrap_command_prefix(
            tokens, current_shell,
            ZSH_EQUALS_ON if current_shell == "zsh" else ZSH_EQUALS_OFF,
            nested_command_env, nested_lookup)
        if resolution.errors:
            return ALIAS_UNCERTAIN
        invocation = nested_shell_invocation(
            resolution, current_shell, deadline)
        if invocation is not None:
            if not invocation.command:
                return ALIAS_UNCERTAIN
            nested_env, nested_lookup = _alias_authority_context(
                invocation.command_env, invocation.lookup_authority_uncertain)
            nested_state = _shell_alias_guard_state(
                invocation.command, aliases, seen, depth + 1, invocation.shell,
                deadline, nested_env, nested_lookup)
            if nested_state != ALIAS_HARMLESS:
                return nested_state
            if (invocation.dynamic
                    or source_has_dynamic_command_word(
                        invocation.command, deadline)):
                return ALIAS_UNCERTAIN
            continue
        command_state = _shell_alias_git_state(
            resolution, aliases, seen, depth, deadline)
        if command_state != ALIAS_HARMLESS:
            return command_state
        state = command_state
    return state


def resolve_git_alias(
        subcommand, tail, aliases, authority, effective_exec_path, deadline=None,
        command_env=None, lookup_authority_uncertain=False):
    """Resolve standard Git aliases with bounded recursive closure.

    Return ``(subcommand, argv, error, derived-config)``. A harmless shell alias has no subcommand;
    a shell alias which contains or reaches a guarded Git operation returns an error so
    the public runtime asks (Claude) or denies (Codex) rather than executing unseen text.
    """
    current = subcommand.lower()
    argv = list(tail)
    seen = []
    derived_configs = []
    for _depth in range(MAX_ALIAS_DEPTH + 1):
        if current not in aliases:
            authority_error = authorize_git_subcommand(
                current, authority, effective_exec_path)
            if authority_error is None:
                return current, argv, None, derived_configs
            return None, [], authority_error, derived_configs
        if current in seen:
            return (None, [], "Git alias cycle: " + " -> ".join(seen + [current]),
                    derived_configs)
        seen.append(current)
        body = aliases[current]
        if body.startswith("!"):
            shell_state = _shell_alias_guard_state(
                body[1:], aliases, tuple(seen), deadline=deadline,
                command_env=command_env,
                lookup_authority_uncertain=lookup_authority_uncertain)
            if shell_state != ALIAS_HARMLESS:
                detail = ("contains or reaches a guarded Git operation"
                          if shell_state == ALIAS_GUARDED
                          else "has dynamic, malformed, cyclic, or unmodelled source")
                error = f"shell alias {current!r} {detail}"
                return None, [], error, derived_configs
            return None, [], None, derived_configs
        try:
            words = shlex.split(body, posix=True)
        except ValueError as exc:
            return None, [], f"malformed Git alias {current!r}: {exc}", derived_configs
        if not words:
            return None, [], f"empty Git alias {current!r}", derived_configs
        index = 0
        while index < len(words) and words[index] == "-c":
            if index + 1 >= len(words):
                return (None, [], f"Git alias {current!r} ends after -c",
                        derived_configs)
            config = words[index + 1]
            derived_configs.append(config)
            key, separator, value = config.partition("=")
            normalized = key.strip().lower()
            if separator and normalized.startswith("alias.") and len(normalized) > 6:
                aliases[normalized[6:]] = value
            index += 2
        if index >= len(words):
            return (None, [], f"Git alias {current!r} has no subcommand after config",
                    derived_configs)
        if words[index].startswith("-"):
            return (None, [],
                    f"Git alias {current!r} begins with an unmodelled global option "
                    f"{words[index]!r}", derived_configs)
        current = words[index].lower()
        argv = [(word, "") for word in words[index + 1:]] + argv
    return (None, [], f"Git alias expansion exceeds depth {MAX_ALIAS_DEPTH}",
            derived_configs)


def git_grep_argv(tokens, resolution=None, deadline=None):
    """Return guarded pattern argv, Git config, and unresolved invocation state.

    None means the resolved Git subcommand is outside grep/log/shortlog/rev-list
    pattern handling. This is a bounded argv model, not a general Git dispatcher.
    """
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
    if (os.sep not in words[j]
            and command_env.get("PATH", os.environ.get("PATH")) != os.environ.get("PATH")):
        return [], [], ["PATH changes which Git executable would run"]
    authority = trusted_git_authority(words[j], deadline=deadline)
    effective_exec_path = command_env.get("GIT_EXEC_PATH", authority.exec_path)
    j += 1
    configs = []
    unresolved_configs = []
    unresolved_aliases = set()

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

    # GIT_CONFIG_PARAMETERS is the transport `-c` itself uses, so a guard that models
    # `-c` and not this one models half a channel. Measured on git 2.46.1: both
    # `'grep.patternType=extended'` and `'grep.patternType'='extended'` select ERE.
    parameter_configs, parameter_error = _git_config_parameter_items(
        command_env.get("GIT_CONFIG_PARAMETERS"))
    configs.extend(parameter_configs)
    if parameter_error:
        unresolved_configs.append(parameter_error)

    # These name a file whose contents this guard cannot read from argv. The engine is
    # therefore unproven rather than known-safe, which is what `ask` is for.
    for file_channel in ("GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM"):
        if command_env.get(file_channel):
            unresolved_configs.append(
                f"{file_channel} points at a config file this guard cannot read, and it "
                f"may set grep.patternType")

    def add_config_env(spec):
        key, separator, env_name = spec.partition("=")
        if not separator or not env_name:
            unresolved_configs.append(f"malformed --config-env {spec!r}")
            return
        if env_name in command_env:
            configs.append(f"{key}={command_env[env_name]}")
        elif (key.strip().lower() in {"grep.patterntype", "grep.extendedregexp"}
              or key.strip().lower().startswith("alias.")):
            unresolved_configs.append(
                f"--config-env for {key} references unavailable {env_name}"
            )
            if key.strip().lower().startswith("alias."):
                unresolved_aliases.add(key.strip().lower()[6:])

    options_with_args = {
        "-C", "-c", "--git-dir", "--work-tree", "--namespace", "--super-prefix",
        "--config-env", "--attr-source",
    }
    while j < len(words) and words[j].startswith("-"):
        option = words[j]
        if option == "--":
            j += 1
            break
        if option == "--exec-path":
            return None
        if option.startswith("--exec-path="):
            effective_exec_path = option.split("=", 1)[1]
            j += 1
            continue
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
    if j >= len(words):
        return None
    subcommand, rest, alias_error, alias_configs = resolve_git_alias(
        words[j], items[j + 1:], _alias_table(configs), authority,
        effective_exec_path, deadline, command_env,
        resolution.descendant_lookup_authority_uncertain)
    configs.extend(alias_configs)
    if alias_error:
        unresolved_configs.append(alias_error)
        return [], configs, unresolved_configs
    if subcommand is None:
        return None
    if subcommand in unresolved_aliases:
        return [], configs, unresolved_configs
    if subcommand == "grep":
        return rest, configs, unresolved_configs
    # `git log --grep=<pattern>` runs the pattern through the same engine selection as
    # `git grep`: measured on git 2.46.1, `-E --grep='foo\b'` returns the commit whose
    # subject contains `foob` while `-P` returns the intended one. The pattern rides an
    # option rather than sitting in argv, so it is lifted out here.
    if subcommand in GIT_LOG_GREP_SUBCOMMANDS:
        lifted = []
        k = 0
        while k < len(rest):
            text, quoting = rest[k]
            name, separator, value = text.partition("=")
            if name in GIT_LOG_PATTERN_OPTIONS:
                if separator:
                    lifted.append((value, quoting))
                    k += 1
                    continue
                if k + 1 < len(rest):
                    lifted.append(rest[k + 1])
                    k += 2
                    continue
            lifted.append((text, quoting))
            k += 1
        if any(name in GIT_LOG_PATTERN_OPTIONS
               for text, _q in rest
               for name in (text.partition("=")[0],)):
            return lifted, configs, unresolved_configs
    return None


# Subcommands whose --grep/--author/--committer patterns go through the same engine
# selection as `git grep`. Verified on git 2.46.1: `git log -E --grep='foo\b'` returns
# the commit whose subject contains `foob`, `-P` returns the intended one.
GIT_LOG_GREP_SUBCOMMANDS = {"log", "shortlog", "rev-list"}
GIT_LOG_PATTERN_OPTIONS = {"--grep", "--author", "--committer"}

CONFIG_ENGINE = {"extended": "E", "ere": "E", "perl": "P", "pcre": "P",
                 "fixed": "F", "basic": "B", "default": "B"}
AMBIENT_ENGINE_REQUIRES_EXPLICIT = True


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


def _live_shell_operator_positions(line, operator):
    positions = []
    quote = ""
    index = 0
    while index < len(line):
        char = line[index]
        if quote:
            if char == "\\" and quote == '"' and index + 1 < len(line):
                index += 2
                continue
            if char == quote:
                quote = ""
            index += 1
            continue
        if char in ("'", '"'):
            quote = char
            index += 1
            continue
        if char == "\\" and index + 1 < len(line):
            index += 2
            continue
        if line.startswith(operator, index):
            positions.append(index)
            index += len(operator)
            continue
        index += 1
    return positions


def _live_interpreter_input_redirects(line):
    """Return live here-string/process-input redirects with their effective fd."""
    redirects = []
    quote = ""
    index = 0
    while index < len(line):
        char = line[index]
        if quote:
            if char == "\\" and quote == '"' and index + 1 < len(line):
                index += 2
                continue
            if char == quote:
                quote = ""
            index += 1
            continue
        if char in ("'", '"'):
            quote = char
            index += 1
            continue
        if char == "\\" and index + 1 < len(line):
            index += 2
            continue
        kind = None
        end = index
        if line.startswith("<<<", index):
            kind = "here-string"
            end = index + 3
        elif char == "<":
            candidate = index + 1
            while candidate < len(line) and line[candidate] in " \t":
                candidate += 1
            if candidate > index + 1 and line.startswith("<(", candidate):
                kind = "process substitution"
                end = candidate + 2
        if kind is None:
            index += 1
            continue
        descriptor_start = index
        while descriptor_start > 0 and line[descriptor_start - 1].isdigit():
            descriptor_start -= 1
        descriptor = line[descriptor_start:index]
        if (descriptor and descriptor_start > 0
                and (line[descriptor_start - 1].isalnum()
                     or line[descriptor_start - 1] == "_")):
            descriptor_start = index
            descriptor = ""
        redirects.append((kind, descriptor_start, int(descriptor or "0")))
        index = end
    return tuple(redirects)


def _parse_shell_input_word(line, start):
    output = []
    quote = ""
    dynamic = False
    consumed = False
    index = start
    while index < len(line) and line[index] in " \t":
        index += 1
    while index < len(line):
        char = line[index]
        if quote:
            if char == quote:
                quote = ""
                consumed = True
                index += 1
                continue
            if quote == '"' and char == "\\" and index + 1 < len(line):
                next_char = line[index + 1]
                if next_char in '$`"\\':
                    output.append(next_char)
                else:
                    output.append("\\" + next_char)
                index += 2
                consumed = True
                continue
            if quote == '"' and char in "$`":
                dynamic = True
            output.append(char)
            consumed = True
            index += 1
            continue
        if char.isspace() or char in ";|&<>":
            break
        if char in ("'", '"'):
            quote = char
            consumed = True
            index += 1
            continue
        if char == "\\":
            if index + 1 >= len(line):
                raise CommandParseError("shell input word ends with a backslash")
            output.append(line[index + 1])
            consumed = True
            index += 2
            continue
        if char in "$`":
            dynamic = True
        if char in "(){}":
            dynamic = True
        output.append(char)
        consumed = True
        index += 1
    if quote:
        raise CommandParseError("shell input word has an unclosed quote")
    if not consumed:
        raise CommandParseError("shell input operator has no source word")
    return "".join(output), dynamic, index


def live_here_string_sources(command):
    # Every source this returns, and every parse error it can raise, begins at a `<<<`.
    if "<<<" not in command:
        return ()
    sources = []
    offset = 0
    for raw_line in command.splitlines(keepends=True):
        line = raw_line[:-1] if raw_line.endswith("\n") else raw_line
        if line.endswith("\r"):
            line = line[:-1]
        prefix = command[:offset]
        quote = ""
        index = 0
        while index < len(line):
            char = line[index]
            if quote:
                if char == "\\" and quote == '"' and index + 1 < len(line):
                    index += 2
                    continue
                if char == quote:
                    quote = ""
                index += 1
                continue
            if char in ("'", '"'):
                quote = char
                index += 1
                continue
            if char == "\\" and index + 1 < len(line):
                index += 2
                continue
            if not line.startswith("<<<", index):
                index += 1
                continue
            redirect_start = index
            while redirect_start > 0 and line[redirect_start - 1].isdigit():
                redirect_start -= 1
            descriptor_text = line[redirect_start:index]
            if (descriptor_text and redirect_start > 0
                    and (line[redirect_start - 1].isalnum()
                         or line[redirect_start - 1] == "_")):
                redirect_start = index
                descriptor_text = ""
            body, dynamic, word_end = _parse_shell_input_word(line, index + 3)
            sources.append(HereStringSource(
                prefix, line, redirect_start, word_end,
                int(descriptor_text or "0"), body, dynamic,
            ))
            index = word_end
        offset += len(raw_line)
    return tuple(sources)


def live_file_input_sources(command):
    """Return live plain file-input redirects without confusing shell arithmetic."""
    # Same shape: no `<` means no redirect to find and no input word to fail parsing.
    if "<" not in command:
        return ()
    sources = []
    for line in command.splitlines():
        quote = ""
        index = 0
        arithmetic_depth = 0
        while index < len(line):
            char = line[index]
            if quote:
                if char == "\\" and quote == '"' and index + 1 < len(line):
                    index += 2
                    continue
                if char == quote:
                    quote = ""
                index += 1
                continue
            if char in ("'", '"'):
                quote = char
                index += 1
                continue
            if char == "\\" and index + 1 < len(line):
                index += 2
                continue
            if line.startswith("$((", index):
                arithmetic_depth += 2
                index += 3
                continue
            if line.startswith("((", index):
                arithmetic_depth += 2
                index += 2
                continue
            if arithmetic_depth and char == "(":
                arithmetic_depth += 1
                index += 1
                continue
            if arithmetic_depth and char == ")":
                arithmetic_depth -= 1
                index += 1
                continue
            if char != "<" or arithmetic_depth:
                index += 1
                continue
            if line.startswith("<<<", index):
                index += 3
                continue
            if line.startswith(("<<", "<&", "<>", "<("), index):
                index += 2
                continue
            word_start = index + 1
            while word_start < len(line) and line[word_start] in " \t":
                word_start += 1
            if line.startswith("<(", word_start):
                index = word_start + 2
                continue
            redirect_start = index
            while redirect_start > 0 and line[redirect_start - 1].isdigit():
                redirect_start -= 1
            descriptor_text = line[redirect_start:index]
            if (descriptor_text and redirect_start > 0
                    and (line[redirect_start - 1].isalnum()
                         or line[redirect_start - 1] == "_")):
                descriptor_text = ""
            path, dynamic, word_end = _parse_shell_input_word(line, index + 1)
            sources.append(FileInputSource(
                line, redirect_start, word_end, int(descriptor_text or "0"),
                path, dynamic,
            ))
            index = word_end
    return tuple(sources)


_REDIRECTION_TOKEN = re.compile(
    r"^(?:[0-9]+)?(?P<operator><<<|<<-|<<|<>|<&|>&|>>|>|<)(?P<tail>.*)$")


def _without_redirection_tokens(tokens):
    cleaned = []
    index = 0
    while index < len(tokens):
        text, quoting = tokens[index]
        match = _REDIRECTION_TOKEN.match(text)
        if match is not None and quoting.startswith("mixed:"):
            modes = quoting.split(":", 1)[1]
            if any(mode != "U" for mode in modes[:match.start("tail")]):
                match = None
        elif match is not None and quoting not in {"", "escaped"}:
            match = None
        if match is None:
            cleaned.append(tokens[index])
            index += 1
            continue
        if not match.group("tail") and index + 1 < len(tokens):
            index += 2
        else:
            index += 1
    return cleaned


def reachable_stdin_shells(commands):
    """Return stdin-reading state for every executable shell in the parsed graph."""
    states = []
    for tokens in commands:
        resolution = unwrap_command_prefix(_without_redirection_tokens(tokens))
        if resolution.errors or not resolution.items:
            continue
        words = [word for word, _quoting in resolution.items]
        if os.path.basename(words[0]) in SHELLS:
            states.append(_shell_reads_stdin(words))
    return tuple(states)


def _marked_stdin_command(line, redirect_start, word_end, deadline=None):
    """Return the one command record owning an input-source marker."""
    marker = "__ZHAR_STDIN_SOURCE__"
    if marker in line:
        return None
    marked = line[:redirect_start] + " " + marker + " " + line[word_end:]
    try:
        marked_commands = split_commands(marked, _deadline=deadline)
    except CommandParseError:
        return None
    matches = []
    for index, tokens in enumerate(marked_commands):
        if any(text == marker for text, _quoting in tokens):
            matches.append((index, tokens))
    if len(matches) != 1:
        return None
    index, tokens = matches[0]
    return index, [token for token in tokens if token[0] != marker]


def associated_stdin_consumer(
        line, redirect_start, word_end, deadline=None):
    """Resolve one input source to its command record without cross-command joins."""
    marked = _marked_stdin_command(line, redirect_start, word_end, deadline)
    if marked is None:
        return StdinConsumer(False, True, "")
    _index, stripped = marked
    resolution = unwrap_command_prefix(_without_redirection_tokens(stripped))
    if resolution.errors or not resolution.items:
        return StdinConsumer(False, True, "")
    words = [word for word, _quoting in resolution.items]
    executable = words[0]
    if executable in TRUSTED_EXTERNAL_NON_FORWARDING_COMMANDS:
        return StdinConsumer(False, False, "")
    if os.path.basename(executable) in SHELLS:
        return StdinConsumer(_shell_reads_stdin(words), False,
                             os.path.basename(executable))
    return StdinConsumer(False, True, "")


def direct_here_string_invocation(
        source, current_shell="zsh", equals_state=ZSH_EQUALS_ON,
        command_env=None, lookup_authority_uncertain=False, deadline=None):
    """Bind a direct shell here-string to the wrapper authority that launches it."""
    marked = _marked_stdin_command(
        source.line, source.redirect_start, source.word_end, deadline)
    if marked is None:
        return None
    command_index, marked_tokens = marked
    if (not marked_tokens and command_index > 0
            and re.fullmatch(
                r"\s*\(\s*(?:/[^\s()]+/)?(?:sh|bash|zsh|dash|ksh)\s*\)\s*",
                source.line[:source.redirect_start])):
        command_index -= 1
    clean_line = (source.line[:source.redirect_start] + " "
                  + source.line[source.word_end:])
    try:
        occurrence_env, occurrence_lookup = _here_string_occurrence_environment(
            source, clean_line, command_env, lookup_authority_uncertain,
            deadline)
        commands = split_commands(clean_line, _deadline=deadline)
        if command_index >= len(commands):
            return None
        resolution = unwrap_command_prefix(
            commands[command_index], current_shell, equals_state,
            occurrence_env, occurrence_lookup)
    except (CommandParseError, IndexError):
        return None
    if resolution.errors or not resolution.items:
        return None
    words = [word for word, _quoting in resolution.items]
    shell = os.path.basename(words[0])
    if shell not in SHELLS or not _shell_reads_stdin(words):
        return None
    invocation = ShellInvocation(
        shell, source.body, source.dynamic, dict(resolution.command_env),
        _descendant_lookup_authority(resolution))
    return resolution, invocation


def _direct_heredoc_header(line, deadline=None):
    redirects = []
    search = 0
    while True:
        found = _find_heredoc_operator(line[search:])
        if found is None:
            break
        offset, strip_tabs = found
        operator = search + offset
        redirect_start = operator
        while redirect_start > 0 and line[redirect_start - 1].isdigit():
            redirect_start -= 1
        descriptor_text = line[redirect_start:operator]
        if (descriptor_text and redirect_start > 0
                and (line[redirect_start - 1].isalnum()
                     or line[redirect_start - 1] == "_")):
            redirect_start = operator
            descriptor_text = ""
        word_start = operator + (3 if strip_tabs else 2)
        while word_start < len(line) and line[word_start] in " \t":
            word_start += 1
        _delimiter, _quoted, word_end = _parse_heredoc_delimiter_word(
            line, word_start)
        redirects.append((redirect_start, word_end, int(descriptor_text or "0")))
        search = word_end
    stdin_redirects = [redirect for redirect in redirects if redirect[2] == 0]
    if len(stdin_redirects) != 1:
        return False
    parts = []
    cursor = 0
    for start, end, _descriptor in redirects:
        parts.extend((line[cursor:start], " "))
        cursor = end
    parts.append(line[cursor:])
    try:
        commands = split_commands("".join(parts), _deadline=deadline)
    except CommandParseError:
        return False
    return len(commands) == 1 and reachable_stdin_shells(commands) == (True,)


def classify_direct_here_string(source, shell_depth, deadline, resolution,
                                invocation, inherited_equals_state):
    if source.dynamic:
        return StdinProvenance(
            "ask", "a directly associated shell here-string has a dynamic source")
    decision, reason = decide(
        source.body, shell_depth + 1, deadline, invocation.shell,
        nested_shell_equals_state(
            resolution, invocation, inherited_equals_state),
        invocation.command_env, invocation.lookup_authority_uncertain)
    if decision == "allow":
        return None
    return StdinProvenance(
        decision, "a directly associated shell here-string recursively classified as "
        + decision + " (" + reason + ")")


def interpreter_stdin_provenance(
        command, commands, shell_depth, deadline, current_shell="zsh",
        equals_state=ZSH_EQUALS_ON, command_env=None,
        lookup_authority_uncertain=False):
    """Classify stdin source reachability over all parsed command/function records."""
    findings = []
    for source in live_here_string_sources(command):
        if source.descriptor != 0:
            continue
        clean_line = (source.line[:source.redirect_start] + " "
                      + source.line[source.word_end:])
        try:
            source_env, source_lookup = _here_string_occurrence_environment(
                source, clean_line, command_env, lookup_authority_uncertain,
                deadline)
        except CommandParseError:
            source_env = dict(command_env or os.environ)
            source_lookup = True
        direct = direct_here_string_invocation(
            source, current_shell, equals_state, command_env,
            lookup_authority_uncertain, deadline)
        if direct:
            resolution, invocation = direct
            classified = classify_direct_here_string(
                source, shell_depth, deadline, resolution, invocation,
                equals_state)
            if classified is not None:
                findings.append(classified)
            continue
        consumer = associated_stdin_consumer(
            source.line, source.redirect_start, source.word_end, deadline)
        if not consumer.reads_stdin and not consumer.unresolved:
            continue
        if consumer.reads_stdin and not consumer.unresolved:
            classified = classify_direct_here_string(
                source, shell_depth, deadline,
                PrefixResolution(
                    [(consumer.shell, "")], dict(source_env), (),
                    False, source_lookup, source_lookup),
                ShellInvocation(
                    consumer.shell, source.body, source.dynamic,
                    dict(source_env), source_lookup),
                equals_state)
            if classified is not None:
                findings.append(classified)
            continue
        if source.dynamic:
            nested_decision, nested_reason = decide(
                source.body, shell_depth + 1, deadline, current_shell,
                equals_state, source_env, source_lookup)
            if nested_decision != "allow":
                findings.append(StdinProvenance(
                    nested_decision,
                    "a here-string expansion recursively classified as "
                    + nested_decision + " (" + nested_reason + ")",
                ))
        guarded_body = _raw_has_guarded_evidence(source.body)
        if (consumer.unresolved and guarded_body
                and _has_simple_unproven_shell_input(source.line, deadline)):
            continue
        if consumer.unresolved:
            findings.append(StdinProvenance(
                "ask", "a here-string consumer edge could not be resolved to a "
                "proven data consumer or interpreter"))
            continue
        if source.dynamic or guarded_body:
            association = "unresolved" if consumer.unresolved else "executable"
            findings.append(StdinProvenance(
                "ask", f"a guarded or dynamic here-string has an {association} "
                "interpreter edge through a compound, subshell, or function"))
    for source in live_file_input_sources(command):
        if source.descriptor != 0:
            continue
        consumer = associated_stdin_consumer(
            source.line, source.redirect_start, source.word_end, deadline)
        if not consumer.reads_stdin and not consumer.unresolved:
            continue
        if source.path == "/dev/null":
            continue
        if source.dynamic or _raw_has_guarded_evidence(source.path):
            detail = "dynamic" if source.dynamic else "guarded"
        else:
            detail = "uninspected"
        findings.append(StdinProvenance(
            "ask", f"a {detail} file-input source can reach an executable interpreter; "
            "use an explicit script operand or a directly classified source"))
    guarded_or_dynamic = _raw_has_guarded_evidence(command) or bool(UNRESOLVED.search(command))
    if not guarded_or_dynamic:
        if not findings:
            return None
        return _reduce_stdin_provenance(findings)
    has_pipeline = False
    for line in command.splitlines():
        for position in _live_shell_operator_positions(line, "|"):
            try:
                downstream = split_commands(
                    line[position + 1:], _deadline=deadline)
            except CommandParseError:
                has_pipeline = True
                break
            if downstream:
                resolution = unwrap_command_prefix(downstream[0])
                words = [word for word, _quoting in resolution.items]
                if resolution.errors or _shell_reads_stdin(words):
                    has_pipeline = True
                    break
        if has_pipeline:
            break
    has_process_input = False
    for line in command.splitlines():
        for kind, prefix, descriptor in _live_interpreter_input_redirects(line):
            if kind != "process substitution" or descriptor != 0:
                continue
            executes = _header_executes_shell(line[:prefix], deadline=deadline)
            if executes is not False:
                has_process_input = True
                break
        if has_process_input:
            break
    heredoc_headers = [line for line in command.splitlines()
                       if _find_heredoc_operator(line) is not None]
    has_unproven_heredoc = any(
        not _direct_heredoc_header(line, deadline)
        and _header_executes_shell(
            line[:_find_heredoc_operator(line)[0]], deadline=deadline) is not False
        for line in heredoc_headers)
    if has_pipeline or has_process_input or has_unproven_heredoc:
        findings.append(StdinProvenance(
            "ask", "guarded or dynamic stdin source syntax can reach an executable "
            "interpreter but no single direct source association was proven"))
    if not findings:
        return None
    return _reduce_stdin_provenance(findings)


def _raw_has_guarded_evidence(command):
    words = re.findall(r"[A-Za-z0-9_./$:{}+-]+", command)
    has_git = any(os.path.basename(word) == "git" for word in words)
    has_guarded_subcommand = any(
        os.path.basename(word) in GIT_HAZARD_SUBCOMMANDS for word in words)
    has_rev_expansion = bool(re.search(
        r"\$(?:[A-Za-z_][A-Za-z0-9_]*|[0-9?*@$!#-]|\{[^\n}]+\}):[A-Za-z]",
        command,
    ))
    return (has_git and has_guarded_subcommand) or has_rev_expansion


def _has_simple_unproven_shell_input(line, deadline=None):
    stdin_sources = [source for source in live_here_string_sources(line)
                     if source.descriptor == 0]
    if stdin_sources:
        consumers = [associated_stdin_consumer(
            source.line, source.redirect_start, source.word_end, deadline)
            for source in stdin_sources]
        if all(not consumer.unresolved and not consumer.reads_stdin
               for consumer in consumers):
            return False
    for _kind, prefix_end, descriptor in _live_interpreter_input_redirects(line):
        prefix = line[:prefix_end]
        if (descriptor == 0
                and _header_executes_shell(prefix, deadline=deadline) is False
                and not any(_live_shell_operator_positions(line, operator)
                            for operator in (";", "|", "&", "{", "}", "(", ")"))
                and re.search(
                    r"(?:^|[;&|() \t])(?:[^;&|() \t]*/)?"
                    r"(?:sh|bash|zsh|dash|ksh)(?:$|[ \t])",
                    prefix,
                )):
            return True
    return False


def conservative_allow_uncertainty(command, deadline=None):
    """Catch guarded execution syntax left unresolved by the detailed parser.

    This fallback deliberately prefers a question over treating guarded-looking text as
    inert when shell-input association is obscured. Exact non-forwarding binaries are the
    bounded exception; callers using an aliasable data-consumer name may be questioned.

    Its escalation is scoped to SHELL-input association. Guarded text riding a non-shell
    interpreter body -- `python3 -c`, `perl -e`, `awk 'BEGIN{system(...)}'` -- reaches this
    function with guarded evidence and leaves it allowed, which is the module docstring's
    named out-of-scope edge rather than an oversight here.
    """
    if not _raw_has_guarded_evidence(command):
        return None
    try:
        commands = split_commands(command, _deadline=deadline)
    except CommandParseError:
        return "guarded execution syntax could not be classified"
    if commands:
        exact_inert = True
        for tokens in commands:
            resolution = unwrap_command_prefix(tokens)
            if (resolution.errors or not resolution.items
                    or resolution.items[0][0]
                    not in TRUSTED_EXTERNAL_NON_FORWARDING_COMMANDS):
                exact_inert = False
                break
        if exact_inert:
            return None
    if any(_has_simple_unproven_shell_input(line, deadline)
           for line in command.splitlines()):
        return "shell-input association remains unproven after detailed parsing"
    return None


# Every site that can raise CommandParseError while classifying is a place the guard could
# not finish reading the source: the closed parse limits, and the wall-clock decision
# budget. That is the unresolved-source row of the decision contract, which is `ask`. Two
# call sites were already wrapped and the rest were not, so an exhausted budget inside
# zsh_equals_states escaped to bash_command_guard's `except BaseException` arm and denied a
# benign command. Catching it here keeps the findings already proven, so an exhausted budget
# cannot mask a deny either.
BUDGET_EXHAUSTED_REASON = (
    "the Bash guard could not finish classifying this command within its internal "
    "decision budget (%s); rerun it as a smaller direct command."
)


def decide(command, _shell_depth=0, _deadline=None, _shell="zsh",
           _equals_state=ZSH_EQUALS_ON, _command_env=None,
           _lookup_authority_uncertain=False):
    """-> (decision, reason). decision in {allow, deny, ask}."""
    _deadline = (time.monotonic() + GUARD_BUDGET_SECONDS
                 if _deadline is None else _deadline)
    if time.monotonic() >= _deadline:
        return ("ask", "the Bash guard exhausted its internal decision budget before "
                "the command could be classified; retry with a simpler direct command.")
    if _shell_depth > 4:
        return ("ask", "nested shell -c depth exceeds the git-grep guard's model; "
                "verify the command or invoke git grep directly with -P.")
    decisions = []
    try:
        _classify(command, decisions, _shell_depth, _deadline, _shell, _equals_state,
                  _command_env, _lookup_authority_uncertain)
    except CommandParseError as exc:
        decisions.append(("ask", BUDGET_EXHAUSTED_REASON % exc))
    return _strongest_decision(decisions) if decisions else ("allow", "")


def _classify(command, decisions, _shell_depth, _deadline, _shell, _equals_state,
              _command_env, _lookup_authority_uncertain):
    """Append every non-allow finding for one command source to `decisions`."""
    equals_heredoc = heredoc_equals_decision(
        command, _deadline,
        classifier=lambda body, shell, state, deadline, env, lookup: decide(
            body, _shell_depth + 1, deadline, shell, state, env, lookup),
        current_shell=_shell, inherited_equals_state=_equals_state,
        command_env=_command_env,
        lookup_authority_uncertain=_lookup_authority_uncertain)
    if equals_heredoc is not None:
        decisions.append(equals_heredoc)
    try:
        scan_command = command_without_heredoc_payloads(command, _deadline)
        commands = split_commands(scan_command, _deadline=_deadline)
    except CommandParseError as exc:
        decisions.append((
            "ask", f"the Bash command cannot be parsed safely ({exc}); "
            "rewrite it as a direct command before proceeding."))
        return
    try:
        stdin_provenance = interpreter_stdin_provenance(
            command, commands, _shell_depth, _deadline, _shell, _equals_state,
            _command_env, _lookup_authority_uncertain)
    except CommandParseError as exc:
        decisions.append((
            "ask", f"interpreter stdin provenance cannot be parsed safely ({exc}); "
            "rewrite it as one direct source before proceeding."))
        return
    if stdin_provenance is not None:
        decisions.append((stdin_provenance.decision, stdin_provenance.reason))
    equals_states = zsh_equals_states(
        scan_command, commands,
        _equals_state if _shell == "zsh" else ZSH_EQUALS_OFF, _deadline)
    environment_states = command_environment_states(
        scan_command, commands, _command_env, _lookup_authority_uncertain,
        _deadline)
    for tokens, equals_state, (command_env, lookup_uncertain) in zip(
            commands, equals_states, environment_states):
        resolution = unwrap_command_prefix(
            tokens, _shell, equals_state, command_env, lookup_uncertain)
        if resolution.errors and resolution.hazard_hint:
            decisions.append((
                "ask", "a possible Git invocation crosses an unresolved command "
                "prefix (" + "; ".join(resolution.errors) + "); invoke Git directly "
                "so the pattern engine can be verified."))
            continue
        invocation = nested_shell_invocation(resolution, _shell, _deadline)
        if invocation is not None:
            # Inspect the body first. Returning `ask` on `dynamic` before recursing meant
            # a nested body carrying a live ERE hazard was downgraded to a question, and
            # a body with no Git in it at all -- `sh -c 'echo $PATH'` -- was questioned
            # too, purely for containing a `$`.
            if invocation.command:
                nested_equals_state = nested_shell_equals_state(
                    resolution, invocation, equals_state)
                nested_decision, nested_reason = decide(
                    invocation.command, _shell_depth + 1, _deadline,
                    invocation.shell, nested_equals_state,
                    invocation.command_env,
                    invocation.lookup_authority_uncertain)
                if nested_decision != "allow":
                    decisions.append((nested_decision, nested_reason))
            # Uncertainty about the body only matters once Git is actually in it.
            # An unknown EXECUTABLE is the honest question: the body could be anything,
            # including a git grep. An unknown ARGUMENT to a named command is not -- that
            # is judged on what is written.
            if (not invocation.command
                    or source_has_dynamic_command_word(invocation.command, _deadline)):
                decisions.append((
                    "ask", "a shell -c command string is empty, or chooses its "
                    "executable from an expansion, so the Git grep engine cannot be "
                    "inspected before execution"))
        try:
            got = git_grep_argv(tokens, resolution, _deadline)
        except GitAuthorityError as exc:
            # Not proof of the guarded hazard, so not `deny`: this is the unresolved-
            # executable row of the decision contract, which is `ask`.
            decisions.append((
                "ask", "the Git behind this command cannot be identified ("
                + str(exc) + "), so neither its command inventory nor its regex "
                "engine can be proved; confirm the binary or invoke Git directly "
                "with an explicit -P engine."))
            continue
        if got is None:
            continue
        argv, configs, unresolved_configs = got
        if unresolved_configs:
            decisions.append((
                "ask", "the Git pattern invocation has unresolved configuration or alias "
                "state: " + "; ".join(unresolved_configs) + ". This guard cannot "
                "prove the command and regex engine, so use a direct invocation with "
                "an explicit -P engine."))
            continue
        engine = None
        engine_src = None
        invalid_config = False
        for cfg in configs:
            key, separator, value = cfg.partition("=")
            key = key.strip().lower()
            val = value.strip().lower()
            if key == "grep.patterntype":
                if not separator:
                    decisions.append((
                        "ask", "git grep has grep.patternType with no value; Git may "
                        "fail without diagnostics, so the guard cannot prove an engine. "
                        "Use an explicit value or invoke git grep with -P."))
                    invalid_config = True
                    break
                if val not in CONFIG_ENGINE:
                    decisions.append((
                        "ask", f"git grep has unrecognized grep.patternType={value!r}; "
                        "the guard cannot prove an engine. Use -P explicitly."))
                    invalid_config = True
                    break
                engine = CONFIG_ENGINE[val]
                engine_src = "config"
            elif key == "grep.extendedregexp":
                if separator and git_config_bool_is_false(value):
                    engine = "B"
                    engine_src = "config"
                else:
                    engine = "E"
                    engine_src = "config"
        if invalid_config:
            continue
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
            long_option = canonical_long_option(text) if text.startswith("--") else None
            long_name = long_option.canonical if long_option is not None else ""
            engine_names = set(GREP_LONG_ENGINE) | GREP_LONG_NEGATED_ENGINE
            if long_option is not None and long_option.ambiguous:
                uncertain_engine_options.append(text)
                k += 1
                continue
            if long_name in engine_names and long_option.has_value:
                uncertain_engine_options.append(text)
                k += 1
                continue
            if long_name in GREP_LONG_ENGINE:
                engine = GREP_LONG_ENGINE[long_name]
                engine_src = "flag"
                k += 1
                continue
            if long_name in GREP_LONG_NEGATED_ENGINE:
                engine = "B"
                engine_src = "flag"
                k += 1
                continue
            if long_name in GREP_LONG_PATTERN_ARG:
                letter = GREP_LONG_PATTERN_ARG[long_name]
                attached = long_option.value if long_option.has_value else None
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
                k += 1 if long_option.has_value else 2
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
            decisions.append((
                "ask", "git grep has an ambiguous or invalid long option ("
                + ", ".join(uncertain_engine_options)
                + "); use the complete option name so its arity and regex-engine "
                "effect can be classified before execution."))
            continue
        if engine not in {None, "E"}:
            continue
        if engine is None and AMBIENT_ENGINE_REQUIRES_EXPLICIT and pattern_from_file:
            decisions.append((
                "ask", "git grep has no command-resolved regex engine and reads a "
                "pattern file that argv inspection cannot classify. Ambient Git "
                "configuration may select ERE; use an explicit -P/-E/-G/-F engine."))
            continue
        engine_desc = "-E" if engine_src == "flag" else "Git grep configuration"
        if not patterns:
            if pattern_from_file:
                decisions.append((
                    "ask",
                    "git grep with the ERE engine (%s) and a -f PATTERN FILE: this "
                    "guard reads argv only and CANNOT see the file's patterns, so a "
                    "live PCRE-only construct may silently mismatch under ERE. "
                    "Out of scope for this guard - verify the file's patterns by hand "
                    "or use -P." % engine_desc))
            continue
        unresolved = None
        bad_atoms = set()
        uncertain_atoms = set()
        for pattern, _pattern_q in patterns:
            if UNRESOLVED.search(pattern):
                unresolved = unresolved or pattern
                continue
            scan = scan_pcre_constructs(pattern)
            bad_atoms.update(scan.atoms)
            uncertain_atoms.update(scan.uncertain)
        if engine is None and AMBIENT_ENGINE_REQUIRES_EXPLICIT:
            if bad_atoms or uncertain_atoms or unresolved is not None:
                constructs = sorted(bad_atoms | uncertain_atoms)
                detail = (", ".join(constructs) if constructs
                          else f"dynamic pattern {unresolved!r}")
                decisions.append((
                    "ask", "git grep has no command-resolved regex engine while its "
                    f"pattern contains {detail}. Mutable ambient Git configuration "
                    "may change the effective engine; choose -P/-E/-G/-F explicitly."))
            continue
        if engine is None:
            continue
        if bad_atoms:
            decisions.append((
                "deny",
                "git grep with the ERE engine (selected by " + engine_desc + ") "
                "cannot interpret %s with the intended PCRE grammar. Installed-Git "
                "selftests distinguish these live constructs from escaped-literal controls. "
                "An empty or different result is evidence about the selected regex engine, "
                "not about the repository. Re-run with -P."
                % ", ".join(sorted(bad_atoms))))
            continue
        if uncertain_atoms:
            decisions.append((
                "ask",
                "git grep with the ERE engine contains unmodelled live regex "
                "construct(s) %s. The guard cannot prove those constructs have the same "
                "meaning under ERE and PCRE; use -P or replace them with grounded portable "
                "syntax." % ", ".join(sorted(uncertain_atoms))))
            continue
        if unresolved is not None:
            decisions.append((
                "ask",
                "git grep -E with a shell-expanded pattern (%s): this guard reads argv "
                "only and CANNOT see the final pattern, so regex-engine compatibility is "
                "UNCHECKED here. Out of scope for this guard - verify by hand or use -P."
                % unresolved[:60]))
    fallback_uncertainty = conservative_allow_uncertainty(command, _deadline)
    if fallback_uncertainty:
        decisions.append((
            "ask", fallback_uncertainty + "; guarded-looking text is allowed through "
            "complex input syntax only when the operation resolves to an exact trusted "
            "data-consumer path. Otherwise rewrite it as one directly classified source."))


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
    ("ASK ambient config may change the implicit engine",
     """git grep -n 'get_packages\\b' -- src/""", "ask"),
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
    ("ASK ATTACHED: no command-resolved engine for a PCRE-like pattern",
     """git grep -e'harness\\b' -- README.md""", "ask"),
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
    ("ASK WRAPPER: sudo changes Git execution authority",
     """sudo git grep -nE 'harness\\b' -- README.md""", "ask"),
    ("ASK WRAPPER: sudo user selection changes Git execution authority",
     """sudo -u root git grep -nE 'harness\\b' -- README.md""", "ask"),
    ("ASK WRAPPER: command -p uses a different executable search path",
     """command -p git grep -nE 'harness\\b' -- README.md""", "ask"),
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
    ("GREEN WRAPPER: dynamic pattern under -P, the safe engine, has no hazard",
"""eval \"git grep -nP $PATTERN -- README.md\"""", "allow"),
    ("GREEN WRAPPER: same under builtin eval",
"""builtin eval \"git grep -nP $PATTERN -- README.md\"""", "allow"),
    ("ASK WRAPPER: single-quoted eval source is dynamic to eval",
     """eval '$CMD; git grep -nP harness -- README.md'""", "ask"),
    ("ASK WRAPPER: single-quoted builtin eval source is dynamic to eval",
     """builtin eval '$CMD; git grep -nP harness -- README.md'""", "ask"),
    ("GREEN NESTED: dynamic pattern under -P is already the remedy",
"""sh -c \"git grep -nP $PATTERN -- README.md\"""", "allow"),
    ("GREEN NESTED: dynamic pattern under -P is already the remedy",
"""zsh -c \"git grep -nP $PATTERN -- README.md\"""", "allow"),
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
    ("GREEN WRAPPER: builtin bypass does not invoke the declared function",
     """echo() { git \"$@\"; }; builtin echo git grep -nE 'harness\\b' -- README.md""",
     "allow"),
    ("GREEN WRAPPER: exact /usr/bin/printf identity is explicit",
     """/usr/bin/printf '%s\\n' 'printf() { git \"$@\"; }' git grep -nE 'harness\\b' -- README.md""",
     "allow"),
    ("GREEN WRAPPER: exact /bin/echo identity is explicit",
     """/bin/echo git grep -nE 'harness\\b' -- README.md""", "allow"),
    ("GREEN WRAPPER: command bypass does not invoke the declared function",
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
    ("ASK inside a loop still has ambient engine uncertainty",
     """for d in a b; do git grep -n 'x\\b' -- $d; done""", "ask"),
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
    ("ASK  ROUND 9: a different absolute Git path fails authority discovery closed",
     """/nonexistent/bin/git grep -nE 'harness\\b' -- README.md""", "ask"),
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
     """echo git log -E --grep='harness\\b'""", "ask"),
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


def check_option_grammar_against_git(argv_mutator=None):
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
                stream.write("harness\nharnessb\nharnessx\n")
            engine_order_fixture = os.path.join(repo, "engine-order.txt")
            with open(engine_order_fixture, "w", encoding="utf-8") as stream:
                stream.write("zz\n")
            indexed = subprocess.run(
                ["git", "add", "fixture.txt", "engine-order.txt"], cwd=repo,
                capture_output=True, text=True, timeout=10,
            )
            if indexed.returncode:
                return ["cannot index the temporary Git grammar fixture: "
                        + (indexed.stderr or "no diagnostic").strip()]
            # `\b` is not a portable engine oracle: Git's regex backend treats it as a
            # word boundary under ERE on some Linux builds and as a literal `b` on this
            # macOS build. These patterns instead select syntax specific to the expected
            # final engine. The exact matched line proves which grammar ran without
            # assuming one platform's extension behavior.
            bre_pattern = r"\(harness\)"
            ere_pattern = r"harness{1}b"
            cases = (
                ("attached -m", ["-Em1", ere_pattern, "--", "fixture.txt"],
                 "fixture.txt:harnessb\n"),
                ("attached -A", ["-EA3", ere_pattern, "--", "fixture.txt"],
                 "fixture.txt:harnessb\n"),
                ("attached -B", ["-EB3", ere_pattern, "--", "fixture.txt"],
                 "fixture.txt:harnessb\n"),
                ("attached -C", ["-EC3", ere_pattern, "--", "fixture.txt"],
                 "fixture.txt:harnessb\n"),
                ("-NUM shorthand", ["-E3", ere_pattern, "--", "fixture.txt"],
                 "fixture.txt:harnessb\n"),
                ("-NUM before E and e", ["-12Ee" + ere_pattern, "--", "fixture.txt"],
                 "fixture.txt:harnessb\n"),
                ("bare optional --color",
                 ["--color", "--no-color", "-E", ere_pattern, "--", "fixture.txt"],
                 "fixture.txt:harnessb\n"),
                ("-- pattern state", ["-E", "--", ere_pattern, "fixture.txt"],
                 "fixture.txt:harnessb\n"),
                ("matching E negation",
                 ["--extended-regexp", "--no-extended-regexp", bre_pattern, "--",
                  "fixture.txt"], "fixture.txt:harness\n"),
                ("unrelated E negation",
                 ["--perl-regexp", "--no-extended-regexp", bre_pattern, "--",
                  "fixture.txt"], "fixture.txt:harness\n"),
                ("unrelated P negation",
                 ["--extended-regexp", "--no-perl-regexp", bre_pattern, "--",
                  "fixture.txt"], "fixture.txt:harness\n"),
                ("matching P negation",
                 ["--perl-regexp", "--no-perl-regexp", bre_pattern, "--",
                  "fixture.txt"], "fixture.txt:harness\n"),
                ("basic negation resets shared engine",
                 ["--extended-regexp", "--no-basic-regexp", bre_pattern, "--",
                  "fixture.txt"], "fixture.txt:harness\n"),
                ("fixed negation resets shared engine",
                 ["--extended-regexp", "--no-fixed-strings", bre_pattern, "--",
                  "fixture.txt"], "fixture.txt:harness\n"),
                ("unique --extended abbreviation",
                 ["--extended", ere_pattern, "--", "fixture.txt"],
                 "fixture.txt:harnessb\n"),
                ("unique --extended-r abbreviation",
                 ["--extended-r", ere_pattern, "--", "fixture.txt"],
                 "fixture.txt:harnessb\n"),
                ("unique --no-extended abbreviation resets PCRE",
                 ["--perl-regexp", "--no-extended", bre_pattern, "--", "fixture.txt"],
                 "fixture.txt:harness\n"),
                ("unique --max-de abbreviation",
                 ["--max-de", "1", "-E", ere_pattern, "--", "fixture.txt"],
                 "fixture.txt:harnessb\n"),
                ("attached unique --max-de abbreviation",
                 ["--max-de=1", "-E", ere_pattern, "--", "fixture.txt"],
                 "fixture.txt:harnessb\n"),
                ("unique --thr abbreviation",
                 ["--thr", "1", "-E", ere_pattern, "--", "fixture.txt"],
                 "fixture.txt:harnessb\n"),
                ("attached unique --thr abbreviation",
                 ["--thr=1", "-E", ere_pattern, "--", "fixture.txt"],
                 "fixture.txt:harnessb\n"),
                ("unique --max-c abbreviation",
                 ["--max-c", "1", "-E", ere_pattern, "--", "fixture.txt"],
                 "fixture.txt:harnessb\n"),
                ("attached unique --max-c abbreviation",
                 ["--max-c=1", "-E", ere_pattern, "--", "fixture.txt"],
                 "fixture.txt:harnessb\n"),
                ("unique --after-c abbreviation",
                 ["--after-c", "1", "-E", ere_pattern, "--", "fixture.txt"],
                 "fixture.txt:harnessb\n"),
                ("attached unique --after-c abbreviation",
                 ["--after-c=1", "-E", ere_pattern, "--", "fixture.txt"],
                 "fixture.txt:harnessb\n"),
                ("unique --before-c abbreviation",
                 ["--before-c", "1", "-E", ere_pattern, "--", "fixture.txt"],
                 "fixture.txt:harnessb\n"),
                ("attached unique --before-c abbreviation",
                 ["--before-c=1", "-E", ere_pattern, "--", "fixture.txt"],
                 "fixture.txt:harnessb\n"),
                ("unique --conte abbreviation",
                 ["--conte", "1", "-E", ere_pattern, "--", "fixture.txt"],
                 "fixture.txt:harnessb\n"),
                ("attached unique --conte abbreviation",
                 ["--conte=1", "-E", ere_pattern, "--", "fixture.txt"],
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

            # POSIX ERE chooses the leftmost-longest alternative (`zz`), while PCRE
            # chooses the first alternative twice (`z`, `z`). With --only-matching and
            # a one-line fixture, exact stdout distinguishes the final E and P engines;
            # a pattern accepted identically by both cannot make these controls green.
            order_pattern = r"z|zz"
            exact_engine_cases = (
                ("-NUM between E and P",
                 ["--only-matching", "-E1Pe" + order_pattern, "--", "engine-order.txt"],
                 "engine-order.txt:z\nengine-order.txt:z\n"),
                ("-NUM between P and E",
                 ["--only-matching", "-P1Ee" + order_pattern, "--", "engine-order.txt"],
                 "engine-order.txt:zz\n"),
                ("positive E after reset",
                 ["--only-matching", "--no-perl-regexp", "--extended-regexp",
                  order_pattern, "--", "engine-order.txt"],
                 "engine-order.txt:zz\n"),
                ("positive P after reset",
                 ["--only-matching", "--no-extended-regexp", "--perl-regexp",
                  order_pattern, "--", "engine-order.txt"],
                 "engine-order.txt:z\nengine-order.txt:z\n"),
                ("later abbreviated extended engine wins",
                 ["--only-matching", "--no-extended", "--extended", order_pattern,
                  "--", "engine-order.txt"],
                 "engine-order.txt:zz\n"),
            )
            for label, args, expected_stdout in exact_engine_cases:
                command = ["git", "grep", *args]
                if argv_mutator is not None:
                    command = argv_mutator(label, command)
                observed = subprocess.run(
                    command, cwd=repo, capture_output=True, text=True, timeout=10,
                )
                if observed.returncode != 0 or observed.stdout != expected_stdout:
                    failures.append(
                        f"installed Git did not preserve exact final-engine order for "
                        f"{label} (rc={observed.returncode}, "
                        f"stdout={observed.stdout!r}, expected={expected_stdout!r}, "
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
            ambiguous_value = subprocess.run(
                ["git", "grep", "--max", "1", "-E", ere_pattern, "--", "fixture.txt"],
                cwd=repo, capture_output=True, text=True, timeout=10,
            )
            if (ambiguous_value.returncode == 0
                    or "ambiguous option" not in ambiguous_value.stderr
                    or "--max-count" not in ambiguous_value.stderr
                    or "--max-depth" not in ambiguous_value.stderr):
                failures.append(
                    "installed Git did not reject --max as the measured ambiguity "
                    f"(rc={ambiguous_value.returncode}, stdout={ambiguous_value.stdout!r}, "
                    f"stderr={ambiguous_value.stderr!r})")
    except (OSError, subprocess.SubprocessError) as exc:
        failures.append(f"installed Git grammar probe failed closed: {exc!r}")
    return failures


def check_pcre_constructs_against_git():
    """Ground each modeled PCRE construct and the escaped-group equality control."""
    failures = []
    try:
        with tempfile.TemporaryDirectory(prefix="z-harness-pcre-atoms-") as repo:
            initialized = subprocess.run(
                ["git", "init", "--quiet"], cwd=repo,
                capture_output=True, text=True, timeout=10,
            )
            if initialized.returncode:
                return ["cannot initialize PCRE construct fixture: "
                        + (initialized.stderr or "no diagnostic").strip()]
            contents = {
                "quote.txt": "abc\nQabcE\n",
                "cluster.txt": "a\nX\nN\n",
                "reset.txt": "ab\naKb\n",
                "group.txt": "abc\n(?:abc)\n(\n?\n",
                "bracket.txt": "a\n(\n?\n)\na(?)\n1\n",
            }
            for name, content in contents.items():
                with open(os.path.join(repo, name), "w", encoding="utf-8") as stream:
                    stream.write(content)
            added = subprocess.run(
                ["git", "add", *contents], cwd=repo,
                capture_output=True, text=True, timeout=10,
            )
            if added.returncode:
                return ["cannot index PCRE construct fixture: "
                        + (added.stderr or "no diagnostic").strip()]
            cases = (
                (r"^\Qabc\E$", "quote.txt", "quote.txt:QabcE\n", "quote.txt:abc\n"),
                (r"^\X$", "cluster.txt", "cluster.txt:X\n",
                 "cluster.txt:a\ncluster.txt:X\ncluster.txt:N\n"),
                (r"^\N$", "cluster.txt", "cluster.txt:N\n",
                 "cluster.txt:a\ncluster.txt:X\ncluster.txt:N\n"),
                (r"^a\Kb$", "reset.txt", "reset.txt:aKb\n", "reset.txt:b\n"),
            )
            for pattern, path, ere_stdout, pcre_stdout in cases:
                scan = scan_pcre_constructs(pattern)
                if not scan.atoms or scan.uncertain:
                    failures.append(
                        f"scanner did not classify grounded construct {pattern!r}: {scan!r}")
                for engine, expected in (("-E", ere_stdout), ("-P", pcre_stdout)):
                    observed = subprocess.run(
                        ["git", "grep", "--only-matching", engine, pattern, "--", path],
                        cwd=repo, capture_output=True, text=True, timeout=10,
                    )
                    if observed.returncode != 0 or observed.stdout != expected:
                        failures.append(
                            f"installed Git did not ground {pattern!r} under {engine} "
                            f"(rc={observed.returncode}, stdout={observed.stdout!r}, "
                            f"expected={expected!r}, stderr={observed.stderr!r})")
            group_cases = (
                (r"^(?:abc)$", "-E", 128, ""),
                (r"^(?:abc)$", "-P", 0, "group.txt:abc\n"),
                (r"^\(\?:abc\)$", "-E", 0, "group.txt:(?:abc)\n"),
                (r"^\(\?:abc\)$", "-P", 0, "group.txt:(?:abc)\n"),
                (r"^[()?]$", "-E", 0, "group.txt:(\ngroup.txt:?\n"),
                (r"^[()?]$", "-P", 0, "group.txt:(\ngroup.txt:?\n"),
            )
            for pattern, engine, expected_rc, expected_stdout in group_cases:
                observed = subprocess.run(
                    ["git", "grep", engine, pattern, "--", "group.txt"], cwd=repo,
                    capture_output=True, text=True, timeout=10,
                )
                if observed.returncode != expected_rc or observed.stdout != expected_stdout:
                    failures.append(
                        f"installed Git did not preserve group control {pattern!r} under "
                        f"{engine} (rc={observed.returncode}, stdout={observed.stdout!r}, "
                        f"expected_rc={expected_rc}, expected={expected_stdout!r}, "
                        f"stderr={observed.stderr!r})")
            escaped = scan_pcre_constructs(r"^\(\?:abc\)$")
            if escaped.atoms or escaped.uncertain:
                failures.append(
                    f"escaped-group equality control was classified as live: {escaped!r}")
            bracketed = scan_pcre_constructs(r"^[()?]$")
            if bracketed.atoms or bracketed.uncertain:
                failures.append(
                    f"bracket-class equality control was classified as live: {bracketed!r}")
            posix_bracket_pattern = r"^[[:alpha:](?)]+$"
            expected_posix_stdout = (
                "bracket.txt:a\nbracket.txt:(\nbracket.txt:?\n"
                "bracket.txt:)\nbracket.txt:a(?)\n"
            )
            observed_outputs = []
            for engine in ("-E", "-P"):
                observed = subprocess.run(
                    ["git", "grep", engine, posix_bracket_pattern, "--", "bracket.txt"],
                    cwd=repo, capture_output=True, text=True, timeout=10,
                )
                observed_outputs.append(observed.stdout)
                if (observed.returncode != 0
                        or observed.stdout != expected_posix_stdout):
                    failures.append(
                        f"installed Git did not preserve POSIX bracket nesting under "
                        f"{engine} (rc={observed.returncode}, stdout={observed.stdout!r}, "
                        f"expected={expected_posix_stdout!r}, stderr={observed.stderr!r})")
            if len(observed_outputs) == 2 and observed_outputs[0] != observed_outputs[1]:
                failures.append(
                    "installed Git ERE/PCRE POSIX bracket controls are not byte-equal")
            for pattern in (
                    posix_bracket_pattern, r"^[[.a.](?)]$", r"^[[=a=](?)]$"):
                scan = scan_pcre_constructs(pattern)
                if scan.atoms or scan.uncertain:
                    failures.append(
                        f"POSIX bracket element closed its outer class early for "
                        f"{pattern!r}: {scan!r}")
            outside = scan_pcre_constructs(r"^[[:alpha:]](?:abc)$")
            if "(?" not in outside.atoms or outside.uncertain:
                failures.append(
                    f"group opener after a POSIX bracket class was not live: {outside!r}")
    except (OSError, subprocess.SubprocessError) as exc:
        failures.append(f"installed Git PCRE construct probe failed closed: {exc!r}")
    return failures


def check_aliases_against_git():
    """Ground quoted standard aliases, recursive expansion, and cycle failure."""
    failures = []
    try:
        with tempfile.TemporaryDirectory(prefix="z-harness-git-alias-") as repo:
            initialized = subprocess.run(
                ["git", "init", "--quiet"], cwd=repo,
                capture_output=True, text=True, timeout=10,
            )
            if initialized.returncode:
                return ["cannot initialize Git alias fixture: "
                        + (initialized.stderr or "no diagnostic").strip()]
            with open(os.path.join(repo, "fixture.txt"), "w", encoding="utf-8") as stream:
                stream.write("harness\nharnessb\n")
            subprocess.run(
                ["git", "add", "fixture.txt"], cwd=repo,
                capture_output=True, text=True, timeout=10, check=True,
            )
            expected = "fixture.txt:harness\nfixture.txt:harnessb\n"
            cases = (
                ("quoted arguments",
                 ["-c", "alias.gg=grep -e 'harness'", "gg", "--", "fixture.txt"],
                 expected),
                ("recursive chain",
                 ["-c", "alias.a=b", "-c", "alias.b=grep -e harness", "a", "--",
                  "fixture.txt"], expected),
                ("leading -c configuration",
                 ["-c", "alias.gg=-c grep.patternType=extended grep", "gg",
                  "harness{1}b", "--", "fixture.txt"],
                 "fixture.txt:harnessb\n"),
            )
            for label, args, case_expected in cases:
                observed = subprocess.run(
                    ["git", *args], cwd=repo,
                    capture_output=True, text=True, timeout=10,
                )
                if observed.returncode != 0 or observed.stdout != case_expected:
                    failures.append(
                        f"installed Git did not preserve {label} alias behavior "
                        f"(rc={observed.returncode}, stdout={observed.stdout!r}, "
                        f"expected={case_expected!r}, stderr={observed.stderr!r})")
            local_config = subprocess.run(
                ["git", "config", "alias.ambient", "status --short"], cwd=repo,
                capture_output=True, text=True, timeout=10,
            )
            local_alias = subprocess.run(
                ["git", "ambient"], cwd=repo,
                capture_output=True, text=True, timeout=10,
            )
            global_path = os.path.join(repo, "global-config")
            global_config = subprocess.run(
                ["git", "config", "--file", global_path, "alias.external", "status --short"],
                cwd=repo, capture_output=True, text=True, timeout=10,
            )
            global_env = dict(os.environ, GIT_CONFIG_GLOBAL=global_path,
                              GIT_CONFIG_NOSYSTEM="1")
            global_alias = subprocess.run(
                ["git", "external"], cwd=repo, env=global_env,
                capture_output=True, text=True, timeout=10,
            )
            if (local_config.returncode or local_alias.returncode
                    or global_config.returncode or global_alias.returncode):
                failures.append("installed Git did not expose local/global ambient aliases")
            if decide("git ambient")[0] != "ask" or decide("git external")[0] != "ask":
                failures.append("unknown ambient aliases were not classified as uncertain")
            authority = trusted_git_authority()
            if ("submodule" in authority.builtins
                    or "submodule" not in authority.main):
                failures.append("trusted Git inventory misclassified standard submodule")
            if (decide("git submodule status")[0] != "allow"
                    or decide(shlex.quote(authority.executable)
                              + " status --short")[0] != "allow"):
                failures.append("trusted Git native/absolute controls were not allowed")
            alternate_exec = os.path.join(repo, "alternate-exec")
            os.mkdir(alternate_exec)
            env_override = subprocess.run(
                ["git", "submodule", "status"], cwd=repo,
                env=dict(os.environ, GIT_EXEC_PATH=alternate_exec),
                capture_output=True, text=True, timeout=10,
            )
            option_override = subprocess.run(
                ["git", f"--exec-path={alternate_exec}", "submodule", "status"],
                cwd=repo, capture_output=True, text=True, timeout=10,
            )
            builtin_override = subprocess.run(
                ["git", "status", "--short"], cwd=repo,
                env=dict(os.environ, GIT_EXEC_PATH=alternate_exec),
                capture_output=True, text=True, timeout=10,
            )
            if (env_override.returncode == 0 or option_override.returncode == 0
                    or builtin_override.returncode != 0):
                failures.append(
                    "installed Git did not distinguish exec-path external commands "
                    "from builtins")
            if (decide(f"GIT_EXEC_PATH={shlex.quote(alternate_exec)} "
                       "git submodule status")[0] != "ask"
                    or decide(f"git --exec-path={shlex.quote(alternate_exec)} "
                              "submodule status")[0] != "ask"
                    or decide(f"GIT_EXEC_PATH={shlex.quote(alternate_exec)} "
                              "git status --short")[0] != "allow"):
                failures.append("exec-path authority controls disagreed with installed Git")
            cycle = subprocess.run(
                ["git", "-c", "alias.a=b", "-c", "alias.b=a", "a"], cwd=repo,
                capture_output=True, text=True, timeout=10,
            )
            if cycle.returncode == 0 or "alias loop detected" not in cycle.stderr:
                failures.append(
                    "installed Git did not reject the recursive alias cycle "
                    f"(rc={cycle.returncode}, stdout={cycle.stdout!r}, "
                    f"stderr={cycle.stderr!r})")
    except (OSError, subprocess.SubprocessError) as exc:
        failures.append(f"installed Git alias probe failed closed: {exc!r}")
    return failures


def check_shell_boundary_behavior():
    """Exercise downstream expansion and every explicit harmless identity.

    Return (failures, executed, skipped). Only probes requiring an unavailable zsh are
    skipped; sh, bash, and exact-path probes remain mandatory on every host.
    """
    failures = []
    executed = skipped = 0
    has_zsh = shutil.which("zsh") is not None
    resolved_git = shutil.which("git")
    if has_zsh and resolved_git is None:
        failures.append("installed zsh boundary probes cannot resolve Git")
        has_zsh = False

    # `_equals_expanded`'s doubled-equals condition models a real zsh refusal that the
    # DECISION surface cannot observe: `os.path.basename` already reduces a doubled-equals
    # absolute Git path
    # to `git`, and `==git` reaches no guarded arm either way. Deleting the condition
    # therefore reddens nothing downstream, which is the shape of a dead defensive clause.
    # Bind it to the installed zsh directly instead, so it is covered rather than assumed.
    if has_zsh:
        for word, expanded, runs_git in (
            ("=git", "git", True),
            ("=" + resolved_git, resolved_git, True),
            ("==git", "==git", False),
            ("==" + resolved_git, "==" + resolved_git, False),
        ):
            probe = subprocess.run(
                ["zsh", "-c", f"{word} --version"], capture_output=True, timeout=10)
            zsh_ran_git = probe.returncode == 0 and b"git version" in probe.stdout
            executed += 1
            if _equals_expanded(word) != expanded or zsh_ran_git != runs_git:
                failures.append(
                    f"equals-expansion model disagrees with this zsh for {word!r}: "
                    f"helper gave {_equals_expanded(word)!r}, zsh ran git={zsh_ran_git}")
        with tempfile.TemporaryDirectory(prefix="z-harness-equals-") as command_dir:
            literal_git = os.path.join(command_dir, "=git")
            with open(literal_git, "w", encoding="utf-8") as handle:
                handle.write("#!/bin/sh\nprintf 'literal-equals\\n'\n")
            os.chmod(literal_git, 0o700)
            expanded_git = os.path.join(command_dir, "git")
            with open(expanded_git, "w", encoding="utf-8") as handle:
                handle.write("#!/bin/sh\nprintf 'expanded-git\\n'\n")
            os.chmod(expanded_git, 0o700)
            for option_command in (
                    "setopt noequals", "unsetopt equals", "set -o noequals",
                    "set +o equals", "emulate sh"):
                probe = subprocess.run(
                    ["zsh", "-fc",
                     f'PATH="$1:$PATH"; {option_command}; =git probe',
                     "zsh", command_dir],
                    capture_output=True, text=True, timeout=10,
                )
                executed += 1
                if probe.returncode != 0 or probe.stdout != "literal-equals\n":
                    failures.append(
                        f"installed zsh did not leave =git literal after "
                        f"{option_command!r} (rc={probe.returncode}, "
                        f"stdout={probe.stdout!r}, stderr={probe.stderr!r})")
            for restore_command in (
                    "setopt equals", "set +o noequals", "emulate zsh"):
                probe = subprocess.run(
                    ["zsh", "-fc",
                     f"setopt noequals; {restore_command}; =git --version"],
                    capture_output=True, text=True, timeout=10,
                )
                executed += 1
                if probe.returncode != 0 or "git version" not in probe.stdout:
                    failures.append(
                        "installed zsh did not restore =git expansion after literal "
                        f"{restore_command!r} (rc={probe.returncode}, "
                        f"stdout={probe.stdout!r}, stderr={probe.stderr!r})")
            for option_args in (
                    ("-o", "NO_EQUALS"), ("+o", "EQUALS"),
                    ("-oNO_EQUALS",), ("+oEQUALS",),
                    ("-foNO_EQUALS",), ("+foEQUALS",),
                    ("--no-equals",)):
                probe = subprocess.run(
                    ["zsh", *option_args, "-fc", 'PATH="$1:$PATH"; =git probe',
                     "zsh", command_dir],
                    capture_output=True, text=True, timeout=10,
                )
                executed += 1
                if probe.returncode != 0 or probe.stdout != "literal-equals\n":
                    failures.append(
                        "installed zsh child option did not leave =git literal for "
                        f"{option_args!r} (rc={probe.returncode}, "
                        f"stdout={probe.stdout!r}, stderr={probe.stderr!r})")
            for option_arg in ("-coNO_EQUALS", "+coEQUALS"):
                probe = subprocess.run(
                    ["zsh", option_arg, 'PATH="$1:$PATH"; =git probe',
                     "zsh", command_dir],
                    capture_output=True, text=True, timeout=10,
                )
                executed += 1
                if probe.returncode != 0 or probe.stdout != "literal-equals\n":
                    failures.append(
                        "installed zsh clustered -c option did not leave =git literal "
                        f"for {option_arg!r} (rc={probe.returncode}, "
                        f"stdout={probe.stdout!r}, stderr={probe.stderr!r})")
            for option_args in (
                    ("--no-equals",), ("-o", "NO_EQUALS"),
                    ("-oNO_EQUALS",)):
                probe = subprocess.run(
                    ["zsh", "-c", *option_args,
                     'PATH="$1:$PATH"; =git probe', "zsh", command_dir],
                    capture_output=True, text=True, timeout=10,
                )
                executed += 1
                if probe.returncode != 0 or probe.stdout != "literal-equals\n":
                    failures.append(
                        "installed zsh did not parse a startup option after -c "
                        f"for {option_args!r} (rc={probe.returncode}, "
                        f"stdout={probe.stdout!r}, stderr={probe.stderr!r})")
            for option_args in (
                    ("--no-equals",), ("-o", "NO_EQUALS"),
                    ("-oNO_EQUALS",)):
                probe = subprocess.run(
                    ["zsh", "-c", '[[ -o equals ]] && print on || print off',
                     *option_args],
                    capture_output=True, text=True, timeout=10,
                )
                executed += 1
                if probe.returncode != 0 or probe.stdout != "on\n":
                    failures.append(
                        "installed zsh treated a positional post-command option as "
                        f"startup state for {option_args!r} (rc={probe.returncode}, "
                        f"stdout={probe.stdout!r}, stderr={probe.stderr!r})")
            clustered_stdin = subprocess.run(
                ["zsh", "-fo", "NO_EQUALS"],
                input=f'PATH="{command_dir}:$PATH"; =git probe\n',
                capture_output=True, text=True, timeout=10,
            )
            executed += 1
            if (clustered_stdin.returncode != 0
                    or clustered_stdin.stdout != "literal-equals\n"):
                failures.append(
                    "installed zsh did not consume a separated option value from "
                    "clustered -fo before reading stdin "
                    f"(rc={clustered_stdin.returncode}, "
                    f"stdout={clustered_stdin.stdout!r}, "
                    f"stderr={clustered_stdin.stderr!r})")
            for scoped_setter in (
                    "f(){ unsetopt equals; }; ",
                    "(unsetopt equals); ",
                    "ignored=$(unsetopt equals); "):
                probe = subprocess.run(
                    ["zsh", "-fc", scoped_setter + "=git --version"],
                    capture_output=True, text=True, timeout=10,
                )
                executed += 1
                if probe.returncode != 0 or "git version" not in probe.stdout:
                    failures.append(
                        "installed zsh leaked a scope-local EQUALS option change "
                        f"from {scoped_setter!r} (rc={probe.returncode}, "
                        f"stdout={probe.stdout!r}, stderr={probe.stderr!r})")
            for wrapper in ("env -i", "command -p"):
                probe = subprocess.run(
                    ["zsh", "-fc", f"{wrapper} =git --version"],
                    capture_output=True, text=True, timeout=10,
                )
                executed += 1
                if probe.returncode != 0 or "git version" not in probe.stdout:
                    failures.append(
                        "installed zsh did not expand =git before wrapper execution "
                        f"for {wrapper!r} (rc={probe.returncode}, "
                        f"stdout={probe.stdout!r}, stderr={probe.stderr!r})")
            prior_path = subprocess.run(
                ["zsh", "-fc", 'PATH="$1"; =git probe', "zsh", command_dir],
                capture_output=True, text=True, timeout=10,
            )
            executed += 1
            if prior_path.returncode != 0 or prior_path.stdout != "expanded-git\n":
                failures.append(
                    "installed zsh did not apply a prior PATH assignment to a later "
                    f"=git expansion (rc={prior_path.returncode}, "
                    f"stdout={prior_path.stdout!r}, stderr={prior_path.stderr!r})")
            command_p_child = subprocess.run(
                ["zsh", "-fc",
                 'PATH="$1"; command -p zsh -fc \'=git probe\'',
                 "zsh", command_dir],
                capture_output=True, text=True, timeout=10,
            )
            executed += 1
            if (command_p_child.returncode != 0
                    or command_p_child.stdout != "expanded-git\n"):
                failures.append(
                    "installed zsh command -p launcher did not preserve the child PATH "
                    f"and default EQUALS state (rc={command_p_child.returncode}, "
                    f"stdout={command_p_child.stdout!r}, "
                    f"stderr={command_p_child.stderr!r})")
    else:
        skipped += 1
    for text, quoting, live in (
        ("=git", "", True), ("=git", "'", False), ("=git", '"', False),
        ("=git", "mixed:UUUU", True), ("=git", "mixed:SUUU", False),
        ("==git", "", False), ("git", "", False),
    ):
        executed += 1
        if _equals_expansion_is_live(text, quoting) != live:
            failures.append(
                f"equals-expansion liveness for {text!r} quoted {quoting!r} is not {live}")
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
        if not has_zsh:
            skipped += 1
            continue
        executed += 1
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
        if shell == "zsh" and not has_zsh:
            skipped += 1
            continue
        executed += 1
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
        (["/bin/cat"], "git grep -E pattern\n"),
        (["/bin/echo", "git", "grep", "-E", "pattern"], "git grep -E pattern\n"),
        (["/usr/bin/printf", "%s\\n", "git grep -E pattern"],
         "git grep -E pattern\n"),
    )
    for argv, expected in external_probes:
        executed += 1
        try:
            observed = subprocess.run(
                argv, input=("git grep -E pattern\n" if argv == ["/bin/cat"] else None),
                capture_output=True, text=True, timeout=10,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            failures.append(f"cannot run exact external identity {argv[0]}: {exc!r}")
            continue
        if observed.returncode != 0 or observed.stdout != expected:
            failures.append(
                f"exact external identity {argv[0]} did not retain literal argv "
                f"(rc={observed.returncode}, stdout={observed.stdout!r}, "
                f"stderr={observed.stderr!r})")
    return failures, executed, skipped


# Backslash counting. A PCRE atom exists only when its backslash is unescaped, so an even
# run of backslashes is a literal and carries no engine hazard: measured on git 2.46.1,
# `git grep -E '\\b'` and `-P` and `-F` and the default all return the identical line.
# Denying it blocked this repository's own audit of which patterns use \b.
FIXTURES += [
    ("GREEN LITERAL: even backslashes are a literal, same result under every engine",
     r"""git grep -nE '\\b' -- hooks/""", "allow"),
    ("GREEN LITERAL: literal \\d likewise",
     r"""git grep -nE '\\d' -- tools/""", "allow"),
    ("GREEN LITERAL: four backslashes are still an escaped pair",
     r"""git grep -nE 'a\\\\b' -- .""", "allow"),
    ("RED LITERAL: an odd run leaves a live atom",
     r"""git grep -nE 'a\\\b' -- .""", "deny"),
    ("RED LITERAL: the bare atom is unaffected by the counting",
     r"""git grep -nE 'harness\b' -- README.md""", "deny"),
]

# Git config through the environment. `-c` and `--config-env` were modelled and
# GIT_CONFIG_PARAMETERS was not, although it is the transport `-c` itself uses; measured
# on git 2.46.1, every RED line below returns the decoy line while the guard allowed it.
FIXTURES += [
    ("RED ENV: GIT_CONFIG_PARAMETERS selects ERE",
     r"""GIT_CONFIG_PARAMETERS="'grep.patternType=extended'" git grep -n 'harness\b' -- README.md""",
     "deny"),
    ("RED ENV: the key='value' spelling selects it too",
     r"""GIT_CONFIG_PARAMETERS="'grep.patternType'='extended'" git grep -n 'harness\b' -- README.md""",
     "deny"),
    ("RED ENV: same through an env wrapper",
     r"""env GIT_CONFIG_PARAMETERS="'grep.patternType=extended'" git grep -n 'harness\b' -- README.md""",
     "deny"),
    ("ASK ENV: GIT_CONFIG_GLOBAL names a file this guard cannot read",
     r"""GIT_CONFIG_GLOBAL=/tmp/gc.ini git grep -n 'harness\b' -- README.md""", "ask"),
    ("ASK ENV: GIT_CONFIG_SYSTEM likewise",
     r"""GIT_CONFIG_SYSTEM=/tmp/gc.ini git grep -n 'harness\b' -- README.md""", "ask"),
    ("ASK ENV: unrelated config does not resolve the pattern engine",
     r"""GIT_CONFIG_PARAMETERS="'core.bare=false'" git grep -n 'harness\b' -- README.md""",
     "ask"),
    ("GREEN ENV: patternType=perl is the safe engine",
     r"""GIT_CONFIG_PARAMETERS="'grep.patternType=perl'" git grep -n 'harness\b' -- README.md""",
     "allow"),
]

# Unmodelled launchers. This arm asked on the launcher's NAME, so ordinary pipelines were
# questioned although the subcommand after them is one neither guard reasons about. The
# generic identity path already required a guarded subcommand, which is why `arch git
# status` was allowed while `xargs git add` was not.
FIXTURES += [
    ("GREEN LAUNCHER: xargs feeding git add, not a guarded subcommand",
     "git diff --name-only | xargs git add", "allow"),
    ("GREEN LAUNCHER: xargs feeding git branch -d",
     "git branch --merged | grep -v main | xargs git branch -d", "allow"),
    ("GREEN LAUNCHER: ssh running git status", "ssh host git status", "allow"),
    ("GREEN LAUNCHER: watch running git status", "watch -n 10 git status", "allow"),
    ("ASK LAUNCHER: xargs ahead of a guarded subcommand", "xargs git show", "ask"),
    ("ASK LAUNCHER: ssh ahead of a guarded subcommand",
     "ssh host git log --oneline", "ask"),
    ("ASK LAUNCHER: xargs ahead of git grep", "xargs git grep -E 'x'", "ask"),
]

# A machine can carry more than one real Git. The command inventory, aliases, system
# configuration, and helper path of the PATH-selected Git are not authority for another
# executable. The path is nonexistent so it cannot equal the trusted Git on any host and
# the test never executes it.
_UNTRUSTED_GIT = "/nonexistent/bin/git"
FIXTURES += [
    ("ASK  AUTHORITY: an alternate Git builtin has no transferred authority",
     f"{_UNTRUSTED_GIT} status --short", "ask"),
    ("ASK  AUTHORITY: an alternate Git staging command has no transferred authority",
     f"{_UNTRUSTED_GIT} add -A", "ask"),
    ("ASK  AUTHORITY: an alternate Git PCRE command is still a different authority",
     f"{_UNTRUSTED_GIT} grep -P 'harness\\b' -- README.md", "ask"),
    ("ASK  AUTHORITY: an alternate Git ERE command is not inspected speculatively",
     f"{_UNTRUSTED_GIT} grep -E 'harness\\b' -- README.md", "ask"),
    ("ASK  AUTHORITY: an alternate Git non-builtin has no transferred authority",
     f"{_UNTRUSTED_GIT} submodule status", "ask"),
    ("ASK  AUTHORITY: an alternate Git unknown command has no transferred authority",
     f"{_UNTRUSTED_GIT} project-helper --version", "ask"),
    ("ASK AUTHORITY: command -p cannot transfer PATH-selected Git authority",
     "command -p git status --short", "ask"),
    ("ASK AUTHORITY: builtin command -p has the same alternate search path",
     "builtin command -p git status --short", "ask"),
    ("ASK AUTHORITY: env -i removes executable-search authority",
     "env -i git status --short", "ask"),
    ("ASK AUTHORITY: long env ignore-environment removes executable-search authority",
     "env --ignore-environment git status --short", "ask"),
    ("ASK AUTHORITY: env -u PATH removes executable-search authority",
     "env -u PATH git status --short", "ask"),
    ("ASK AUTHORITY: env --unset PATH removes executable-search authority",
     "env --unset=PATH git status --short", "ask"),
    ("ASK AUTHORITY: sudo changes identity and executable-search authority",
     "sudo -i git status --short", "ask"),
    ("ASK AUTHORITY: env-clean authority persists into a shell -c body",
     "env -i sh -c 'git status --short'", "ask"),
    ("ASK AUTHORITY: env-unset authority persists into a shell -c body",
     "env -u PATH sh -c 'git status --short'", "ask"),
    ("ASK AUTHORITY: sudo authority persists into a shell -c body",
     "sudo sh -c 'git status --short'", "ask"),
    ("ASK AUTHORITY: env-clean uncertainty survives an explicit PCRE spelling",
     "env -i sh -c \"git grep -P 'harness\\b' -- README.md\"", "ask"),
    ("ASK AUTHORITY: env-clean authority persists into a shell here-string",
     "env -i sh 0<<< 'git status --short'", "ask"),
    ("ASK AUTHORITY: env-clean authority persists into a shell heredoc",
     "env -i sh <<'EOF'\ngit status --short\nEOF\n", "ask"),
    ("GREEN AUTHORITY: an environment-cleared harmless shell body stays harmless",
     "env -i sh -c '/bin/echo safe'", "allow"),
]

# zsh resolves `=name` through PATH before execution; bash has no such form. The Bash
# tool's shell is zsh on this host, so these are the same invocations as their bare forms.
FIXTURES += [
    ("RED  EQUALS: zsh =git reaches the ERE hazard",
     "=git grep -E 'harness\\b' -- README.md", "deny"),
    ("GREEN EQUALS: zsh =git with a PCRE engine is correct",
     "=git grep -P 'harness\\b' -- README.md", "allow"),
    ("GREEN EQUALS: zsh =git running a builtin carries no guarded hazard",
     "=git status --short", "allow"),
    ("ASK EQUALS: setopt noequals leaves =git as an unresolved literal executable",
     "setopt noequals; =git grep -E 'harness\\b' -- README.md", "ask"),
    ("ASK EQUALS: unsetopt equals also disables the expansion",
     "unsetopt equals; =git grep -E 'harness\\b' -- README.md", "ask"),
    ("ASK EQUALS: set -o noequals disables the expansion",
     "set -o noequals; =git grep -E 'harness\\b' -- README.md", "ask"),
    ("ASK EQUALS: set +o equals disables the expansion",
     "set +o equals; =git grep -E 'harness\\b' -- README.md", "ask"),
    ("ASK EQUALS: emulate sh disables zsh executable expansion",
     "emulate sh; =git grep -E 'harness\\b' -- README.md", "ask"),
    ("RED EQUALS: a later literal setopt equals restores the expansion",
     "setopt noequals; setopt equals; =git grep -E 'harness\\b' -- README.md", "deny"),
    ("RED EQUALS: emulate zsh restores the native option set",
     "setopt noequals; emulate zsh; =git grep -E 'harness\\b' -- README.md", "deny"),
    ("ASK EQUALS: a conditional option mutation is not unconditional authority",
     "if true; then setopt equals; fi; =git grep -E 'harness\\b' -- README.md", "ask"),
    ("ASK EQUALS: a called function option mutation is not flattened after its caller",
     "f(){ setopt noequals; }; f; =git grep -E 'harness\\b' -- README.md", "ask"),
    ("ASK EQUALS: a nested zsh tracks its own noequals state",
     "zsh -c \"setopt noequals; =git grep -E 'harness\\\\b' -- README.md\"", "ask"),
    ("ASK EQUALS: zsh -o NO_EQUALS changes the child startup state",
     "zsh -o NO_EQUALS -c \"=git grep -E 'harness\\\\b' -- README.md\"", "ask"),
    ("ASK EQUALS: zsh +o EQUALS changes the child startup state",
     "zsh +o EQUALS -c \"=git grep -E 'harness\\\\b' -- README.md\"", "ask"),
    ("ASK EQUALS: attached -oNO_EQUALS changes the child startup state",
     "zsh -oNO_EQUALS -c \"=git grep -E 'harness\\\\b' -- README.md\"", "ask"),
    ("ASK EQUALS: attached +oEQUALS changes the child startup state",
     "zsh +oEQUALS -c \"=git grep -E 'harness\\\\b' -- README.md\"", "ask"),
    ("ASK EQUALS: long --no-equals changes the child startup state",
     "zsh --no-equals -c \"=git grep -E 'harness\\\\b' -- README.md\"", "ask"),
    ("ASK EQUALS: eval inherits an uncertain option mutation in the current zsh",
     "eval 'setopt noequals'; =git grep -E 'harness\\b' -- README.md", "ask"),
    ("ASK EQUALS: sourced code can change the option outside the visible command",
     "source \"$OPTIONS_FILE\"; =git grep -E 'harness\\b' -- README.md", "ask"),
    ("RED EQUALS: a child zsh starts with its own default after an outer noequals",
     "setopt noequals; zsh -c \"=git grep -E 'harness\\\\b' -- README.md\"", "deny"),
    ("RED EQUALS: an uncalled function cannot alter the parent option state",
     "f(){ unsetopt equals; }; =git grep -E 'harness\\b' -- README.md", "deny"),
    ("GREEN EQUALS: the uncalled-function control preserves an explicit PCRE engine",
     "f(){ unsetopt equals; }; =git grep -P 'harness\\b' -- README.md", "allow"),
    ("RED EQUALS: a subshell option change cannot escape to the parent",
     "(unsetopt equals); =git grep -E 'harness\\b' -- README.md", "deny"),
    ("GREEN EQUALS: the subshell control preserves an explicit PCRE engine",
     "(unsetopt equals); =git grep -P 'harness\\b' -- README.md", "allow"),
    ("RED EQUALS: a command-substitution option change cannot escape",
     "ignored=$(unsetopt equals); =git grep -E 'harness\\b' -- README.md", "deny"),
    ("RED EQUALS: env cannot change an outer pre-expanded executable identity",
     "env -i =git grep -E 'harness\\b' -- README.md", "deny"),
    ("GREEN EQUALS: outer pre-expansion preserves PCRE through env",
     "env -i =git grep -P 'harness\\b' -- README.md", "allow"),
    ("RED EQUALS: command -p cannot change an outer pre-expanded identity",
     "command -p =git grep -E 'harness\\b' -- README.md", "deny"),
    ("RED EQUALS: sudo cannot change an outer pre-expanded identity",
     "sudo =git grep -E 'harness\\b' -- README.md", "deny"),
    ("ASK  EQUALS: a wrapped =git behind an unmodelled launcher is unresolved",
     "xargs =git show", "ask"),
    ("ASK EQUALS: a path-qualified alternate Git has no transferred authority",
     "=/nonexistent/bin/git grep -E 'harness\\b' -- README.md", "ask"),
    ("GREEN EQUALS: zsh reports `=git not found` for a doubled equals",
     "==git grep -E 'harness\\b' -- README.md", "allow"),
    # zsh refuses a doubled-equals absolute Git path the same way, but
    # `os.path.basename` reads the last
    # path component of the raw word as `git` before any `=` handling runs, so this
    # denies a command that cannot execute. Same safe-direction over-approximation as the
    # nested non-zsh body, pinned here so it is a recorded decision and not a surprise.
    ("ASK EQUALS: a doubled equals alternate Git remains unresolved",
     "==/nonexistent/bin/git grep -E 'harness\\b' -- README.md", "ask"),
    ("ASK  EQUALS: quoting suppresses the expansion, leaving an unproven identity",
     "'=git' grep -E 'harness\\b' -- README.md", "ask"),
    ("ASK  EQUALS: double quoting suppresses it the same way",
     '"=git" grep -E \'harness\\b\' -- README.md', "ask"),
    ("ASK EQUALS: bash does not expand =git and its literal executable is unresolved",
     "bash -c \"=git grep -E 'harness\\b' -- README.md\"", "ask"),
    ("ASK EQUALS: a sh here-string retains the downstream shell identity",
     "sh <<< \"=git grep -E 'harness\\b' -- README.md\"", "ask"),
    ("ASK EQUALS: zsh -o NO_EQUALS applies to a here-string body",
     "zsh -o NO_EQUALS <<< \"=git grep -E 'harness\\b' -- README.md\"", "ask"),
    ("ASK EQUALS: zsh +o EQUALS applies to a here-string body",
     "zsh +o EQUALS <<< \"=git grep -E 'harness\\b' -- README.md\"", "ask"),
    ("ASK EQUALS: attached -oNO_EQUALS applies to a here-string body",
     "zsh -oNO_EQUALS <<< \"=git grep -E 'harness\\b' -- README.md\"", "ask"),
    ("ASK EQUALS: a sh heredoc retains the downstream shell identity",
     "sh <<'EOF'\n=git grep -E 'harness\\b' -- README.md\nEOF\n", "ask"),
    ("ASK EQUALS: zsh -o NO_EQUALS applies to a heredoc body",
     "zsh -o NO_EQUALS <<'EOF'\n=git grep -E 'harness\\b' -- README.md\nEOF\n", "ask"),
    ("ASK EQUALS: zsh +o EQUALS applies to a heredoc body",
     "zsh +o EQUALS <<'EOF'\n=git grep -E 'harness\\b' -- README.md\nEOF\n", "ask"),
    ("ASK EQUALS: attached -oNO_EQUALS applies to a heredoc body",
     "zsh -oNO_EQUALS <<'EOF'\n=git grep -E 'harness\\b' -- README.md\nEOF\n", "ask"),
    ("RED EQUALS: child zsh heredoc starts from its own default",
     "unsetopt equals; zsh <<'EOF'\n=git grep -E 'harness\\b' -- README.md\nEOF\n", "deny"),
    ("GREEN EQUALS: a child zsh heredoc preserves explicit PCRE",
     "zsh <<'EOF'\n=git grep -P 'harness\\b' -- README.md\nEOF\n", "allow"),
    ("RED EQUALS: a later zsh heredoc deny outranks an earlier sh question",
     ("sh <<'A'\n=git grep -E 'harness\\b' -- README.md\nA\n"
      "zsh <<'B'\n=git grep -E 'harness\\b' -- README.md\nB\n"), "deny"),
    ("RED EQUALS: heredoc deny precedence is independent of source order",
     ("zsh <<'A'\n=git grep -E 'harness\\b' -- README.md\nA\n"
      "sh <<'B'\n=git grep -E 'harness\\b' -- README.md\nB\n"), "deny"),
]

# A legal source one byte under the declared cap, as a cost control expressed as a
# decision: exhausting the internal budget returns `ask`, so this stays `allow` only while
# a maximum-size command can still be classified inside the budget on the host running it.
# It reddens where the declared limit stops being reachable, which is what makes the limit
# a claim rather than a number. Margin measured on the authoring host after this commit's
# work: 2.3 s against a 4.0 s budget, from 4.05 s and a denial before it.
_BYTE_LIMIT_SOURCE = "/bin/echo " + "x" * (MAX_COMMAND_CHARS - 11)
_FUNCTION_PARSE_LIMIT_SOURCE = (
    "f(){ git status --short; }; f;" * (MAX_FUNCTION_DECLARATIONS + 1))
_FUNCTION_OPERATOR_BUDGET_SOURCE = (
    "f(){ /bin/echo safe; }; f;" + "( : );" * 16000)
FIXTURES += [
    ("GREEN LIMIT: a legal source at the byte cap is classified inside the budget",
     _BYTE_LIMIT_SOURCE, "allow"),
    ("ASK LIMIT: too many function declarations cannot consume the hook timeout",
     _FUNCTION_PARSE_LIMIT_SOURCE, "ask"),
    ("GREEN LIMIT: operator-heavy source remains inside the public hook budget",
     _FUNCTION_OPERATOR_BUDGET_SOURCE, "allow"),
]

# Authority and decision composition across command/alias boundaries. These cases bind
# state to the command that actually consumes it instead of letting one parser re-entry
# borrow the ambient process or letting an earlier question mask a later denial.
FIXTURES += [
    ("ASK ALIAS AUTHORITY: env-clean state survives shell-alias -c traversal",
     "git -c 'alias.x=!env -i sh -c \"git status --short\"' x", "ask"),
    ("ASK ALIAS AUTHORITY: env-clean state survives shell-alias eval traversal",
     "git -c 'alias.x=!env -i sh -c \"eval git\\ status\\ --short\"' x", "ask"),
    ("ASK ALIAS AUTHORITY: env-clean state survives shell-alias here-string traversal",
     "git -c 'alias.x=!env -i sh 0<<< \"git status --short\"' x", "ask"),
    ("ASK ALIAS AUTHORITY: prior PATH survives shell-alias -c traversal",
     "git -c 'alias.x=!PATH=/usr/bin; sh -c \"git status --short\"' x", "ask"),
    ("ASK ALIAS AUTHORITY: prior PATH survives shell-alias here-string traversal",
     "git -c 'alias.x=!PATH=/usr/bin; sh 0<<< \"git status --short\"' x", "ask"),
    ("ASK PATH STATE: an earlier PATH selects an alternate Git",
     "PATH=/usr/bin; =git grep -P harness -- README.md", "ask"),
    ("ASK PATH STATE: an unavailable earlier PATH cannot inherit ambient Git",
     "PATH=/definitely-missing; =git grep -E 'harness\\b' -- README.md", "ask"),
    ("GREEN PATH STATE: same-command PATH does not precede outer EQUALS expansion",
     "PATH=/definitely-missing =git grep -P harness -- README.md", "allow"),
    ("ASK PATH STATE: conditional mutation is not straight-line authority",
     "if true; then PATH=/usr/bin; fi; =git grep -P harness -- README.md", "ask"),
    ("ASK PATH STATE: prior PATH reaches a directly associated shell here-string",
     "PATH=/usr/bin; sh 0<<< 'git status --short'", "ask"),
    ("ASK PATH STATE: prior-line PATH reaches a child zsh heredoc",
     "PATH=/usr/bin\nzsh <<'EOF'\n=git grep -P 'harness\\b' -- README.md\nEOF\n",
     "ask"),
    ("ASK PATH STATE: prior-line PATH reaches a child zsh here-string",
     "PATH=/usr/bin\nzsh 0<<< \"=git grep -P 'harness\\b' -- README.md\"",
     "ask"),
    ("GREEN PATH STATE: later same-line PATH cannot alter an earlier here-string",
     ("zsh 0<<< \"=git grep -P 'harness\\b' -- README.md\"; "
      "PATH=/usr/bin; /bin/echo done"), "allow"),
    ("GREEN PATH STATE: later same-line unset cannot alter an earlier here-string",
     ("zsh 0<<< \"=git grep -P 'harness\\b' -- README.md\"; "
      "unset PATH; /bin/echo done"), "allow"),
    ("ASK PATH STATE: prior PATH reaches an unquoted heredoc expansion",
     "PATH=/usr/bin; cat <<EOF\n$(=git grep -P 'harness\\b' -- README.md)\nEOF\n",
     "ask"),
    ("GREEN PATH STATE: later header PATH cannot alter an earlier heredoc expansion",
     ("cat <<EOF; PATH=/usr/bin; /bin/echo done\n"
      "$(=git grep -P 'harness\\b' -- README.md)\nEOF\n"), "allow"),
    ("GREEN PATH STATE: a quoted data heredoc does not expand its body",
     "PATH=/usr/bin; cat <<'EOF'\n$(=git grep -P 'harness\\b' -- README.md)\nEOF\n",
     "allow"),
    ("RED COMMAND-P: launcher lookup does not taint child zsh EQUALS state",
     "command -p zsh -c \"=git grep -E 'harness\\\\b' -- README.md\"", "deny"),
    ("GREEN COMMAND-P: child zsh preserves an explicit PCRE engine",
     "command -p zsh -c \"=git grep -P 'harness\\\\b' -- README.md\"", "allow"),
    ("RED COMMAND-P: child zsh here-string keeps inherited PATH authority",
     "command -p zsh 0<<< \"=git grep -E 'harness\\b' -- README.md\"", "deny"),
    ("RED COMMAND-P: child zsh heredoc keeps inherited PATH authority",
     "command -p zsh <<'EOF'\n=git grep -E 'harness\\b' -- README.md\nEOF\n", "deny"),
    ("RED PRECEDENCE: a nested question cannot mask a later direct denial",
     ("sh -c \"=git grep -E 'harness\\\\b' -- README.md\"; "
      "=git grep -E 'harness\\b' -- README.md"), "deny"),
    ("RED PRECEDENCE: direct denial remains strongest in the reverse order",
     ("=git grep -E 'harness\\b' -- README.md; "
      "sh -c \"=git grep -E 'harness\\\\b' -- README.md\""), "deny"),
    ("RED PRECEDENCE: a heredoc question cannot mask a later ordinary denial",
     ("sh <<'EOF'\n=git grep -E 'harness\\b' -- README.md\nEOF\n"
      "git grep -E 'harness\\b' -- README.md"), "deny"),
    ("RED PRECEDENCE: an ordinary denial outranks a later heredoc question",
     ("git grep -E 'harness\\b' -- README.md\n"
      "sh <<'EOF'\n=git grep -E 'harness\\b' -- README.md\nEOF\n"), "deny"),
    ("ASK EQUALS: clustered -fo consumes attached NO_EQUALS",
     "zsh -foNO_EQUALS -c \"=git grep -E 'harness\\\\b' -- README.md\"", "ask"),
    ("ASK EQUALS: clustered +fo consumes attached EQUALS",
     "zsh +foEQUALS -c \"=git grep -E 'harness\\\\b' -- README.md\"", "ask"),
    ("ASK EQUALS: -co processes EQUALS state before the command body",
     "zsh -coNO_EQUALS \"=git grep -E 'harness\\\\b' -- README.md\"", "ask"),
    ("ASK EQUALS: clustered -fo applies to a here-string body",
     "zsh -foNO_EQUALS 0<<< \"=git grep -E 'harness\\b' -- README.md\"", "ask"),
    ("ASK EQUALS: clustered -fo applies to a heredoc body",
     "zsh -foNO_EQUALS <<'EOF'\n=git grep -E 'harness\\b' -- README.md\nEOF\n",
     "ask"),
    ("RED ZSH ARGV: a long option after -c does not hide the command body",
     "zsh -c --no-equals \"git grep -E 'harness\\\\b' -- README.md\"",
     "deny"),
    ("RED ZSH ARGV: a split option after -c does not hide the command body",
     "zsh -c -o NO_EQUALS \"git grep -E 'harness\\\\b' -- README.md\"",
     "deny"),
    ("RED ZSH ARGV: an attached option after -c does not hide the command body",
     "zsh -c -oNO_EQUALS \"git grep -E 'harness\\\\b' -- README.md\"",
     "deny"),
    ("RED ZSH ARGV: a post-body long option is positional, not startup state",
     "zsh -c \"=git grep -E 'harness\\\\b' -- README.md\" --no-equals",
     "deny"),
    ("GREEN ZSH ARGV: post-body split options do not change a PCRE command",
     "zsh -c \"=git grep -P 'harness\\\\b' -- README.md\" -o NO_EQUALS",
     "allow"),
    ("GREEN ZSH ARGV: post-body -s does not make zsh read a here-string",
     ("zsh -fc '/usr/bin/printf command-only' -s 0<<< "
      "\"git grep -E 'harness\\b' -- README.md\""), "allow"),
    ("RED ZSH ARGV: clustered -fo consumes its separated option before stdin",
     "zsh -fo NO_EQUALS <<'EOF'\n"
     "git grep -E 'harness\\b' -- README.md\nEOF\n", "deny"),
    ("RED PRECEDENCE: a later zsh here-string deny outranks a sh question",
     ("sh 0<<< \"=git grep -E 'harness\\b' -- README.md\"; "
      "zsh 0<<< \"=git grep -E 'harness\\b' -- README.md\""), "deny"),
    ("RED PRECEDENCE: here-string deny precedence is source-order independent",
     ("zsh 0<<< \"=git grep -E 'harness\\b' -- README.md\"; "
      "sh 0<<< \"=git grep -E 'harness\\b' -- README.md\""), "deny"),
]

# Same hazard, reached through a different subcommand. Verified on git 2.46.1 against a
# repo whose subjects are "fix foob handling" and "fix foo bar handling": `-E` returns the
# foob commit, `-P` the intended one. --author behaves identically (authors foob / foo bar).
# Aliases reach it too: the alias body was already parsed into `configs` and ignored.
FIXTURES += [
    ("RED LOG: -E --grep= returns the wrong commit",
     r"""git log -E --grep='foo\b'""", "deny"),
    ("RED LOG: separated --grep value",
     r"""git log -E --grep 'foo\b'""", "deny"),
    ("RED LOG: long engine spelling",
     r"""git log --extended-regexp --grep='foo\b'""", "deny"),
    ("RED LOG: shortlog shares the engine",
     r"""git shortlog -E --grep='foo\b'""", "deny"),
    ("RED LOG: --author shares the engine too",
     r"""git log -E --author='foo\b'""", "deny"),
    ("GREEN LOG: -P is the intended engine",
     r"""git log -P --grep='foo\b'""", "allow"),
    ("ASK LOG: ambient config may change an implicit pattern engine",
     r"""git log --grep='foo\b'""", "ask"),
    ("GREEN LOG: an ordinary log is not this guard's business",
     "git log --grep=fix --oneline", "allow"),
    ("RED ALIAS: an alias body carrying -E",
     r"""git -c alias.gg='grep -nE' gg 'harness\b'""", "deny"),
    ("GREEN ALIAS: an alias body carrying -P",
     r"""git -c alias.gg='grep -nP' gg 'harness\b'""", "allow"),
    ("GREEN ALIAS: an alias to a subcommand with no engine",
     "git -c alias.st='status --short' st", "allow"),
]

# Construct scanner, long-option arity, alias closure, and executable-source boundaries.
FIXTURES += [
    ("RED PCRE: live quote pair is not POSIX ERE",
     r"""git grep -E '^\Qabc\E$' -- fixture.txt""", "deny"),
    ("RED PCRE: live grapheme escape is not POSIX ERE",
     r"""git grep -E '^\X$' -- fixture.txt""", "deny"),
    ("RED PCRE: live non-newline escape is not POSIX ERE",
     r"""git grep -E '^\N$' -- fixture.txt""", "deny"),
    ("RED PCRE: live match-reset escape is not POSIX ERE",
     r"""git grep -E '^a\Kb$' -- fixture.txt""", "deny"),
    ("RED PCRE: live group opener is not POSIX ERE",
     r"""git grep -E '^(?:abc)$' -- fixture.txt""", "deny"),
    ("GREEN PCRE: escaped group punctuation is literal under both engines",
     r"""git grep -E '^\(\?:abc\)$' -- fixture.txt""", "allow"),
    ("GREEN PCRE: group-like text inside a bracket class is literal",
     r"""git grep -E '^[()?]$' -- fixture.txt""", "allow"),
    ("GREEN PCRE: POSIX character class keeps group-like text inside the outer class",
     r"""git grep -E '^[[:alpha:](?)]+$' -- fixture.txt""", "allow"),
    ("GREEN PCRE: POSIX collating element keeps the outer bracket class open",
     r"""git grep -E '^[[.a.](?)]$' -- fixture.txt""", "allow"),
    ("GREEN PCRE: POSIX equivalence element keeps the outer bracket class open",
     r"""git grep -E '^[[=a=](?)]$' -- fixture.txt""", "allow"),
    ("RED PCRE: group opener after a completed POSIX bracket class stays live",
     r"""git grep -E '^[[:alpha:]](?:abc)$' -- fixture.txt""", "deny"),
    ("RED PCRE: an even backslash run leaves the following group opener live",
     r"""git grep -E '^\\(?:abc)$' -- fixture.txt""", "deny"),
    ("ASK PCRE: unknown live alphabetic escape fails closed",
     r"""git grep -E '^\Y$' -- fixture.txt""", "ask"),
    ("RED LONG: --max-de consumes its separate value",
     r"""git grep --max-de 1 -E 'harness\b' -- README.md""", "deny"),
    ("RED LONG: --thr consumes its separate value",
     r"""git grep --thr 1 -E 'harness\b' -- README.md""", "deny"),
    ("RED LONG: --max-c consumes its separate value",
     r"""git grep --max-c 1 -E 'harness\b' -- README.md""", "deny"),
    ("RED LONG: --after-c consumes its separate value",
     r"""git grep --after-c 1 -E 'harness\b' -- README.md""", "deny"),
    ("RED LONG: --before-c consumes its separate value",
     r"""git grep --before-c 1 -E 'harness\b' -- README.md""", "deny"),
    ("RED LONG: --conte consumes its separate value",
     r"""git grep --conte 1 -E 'harness\b' -- README.md""", "deny"),
    ("RED LONG: attached unique required-value abbreviation",
     r"""git grep --max-de=1 -E 'harness\b' -- README.md""", "deny"),
    ("ASK LONG: --max is ambiguous across required-value options",
     r"""git grep --max 1 -E 'harness\b' -- README.md""", "ask"),
    ("RED ALIAS: quoted standard alias arguments survive parsing",
     r'''git -c "alias.gg=grep -E -e 'harness\b'" gg -- README.md''', "deny"),
    ("RED ALIAS: recursive standard alias reaches grep",
     r"""git -c alias.a=b -c 'alias.b=grep -E' a 'harness\b' -- README.md""", "deny"),
    ("RED ALIAS: resolved config-env carries a standard alias",
     r"""BODY='grep -E' git --config-env=alias.gg=BODY gg 'harness\b' -- README.md""",
     "deny"),
    ("ASK ALIAS: unresolved config-env alias cannot become allow",
     r"""git --config-env=alias.gg=MISSING gg 'harness\b' -- README.md""", "ask"),
    ("RED ALIAS: standard alias may prepend Git -c configuration",
     r"""git -c 'alias.gg=-c grep.patternType=extended grep' gg 'harness\b' -- README.md""",
     "deny"),
    ("RED ALIAS: standard alias may define and reach another alias",
     r'''git -c "alias.x=-c alias.y='grep -E' y" x 'harness\b' -- README.md''',
     "deny"),
    ("RED ALIAS: alias reaches log pattern parsing",
     r"""git -c 'alias.ll=log -E' ll --grep='harness\b'""", "deny"),
    ("RED ALIAS: alias reaches shortlog pattern parsing",
     r"""git -c 'alias.sl=shortlog -E' sl --grep='harness\b'""", "deny"),
    ("RED ALIAS: alias reaches rev-list pattern parsing",
     r"""git -c 'alias.rl=rev-list -E' rl --grep='harness\b' HEAD""", "deny"),
    ("ASK ALIAS: recursive cycle cannot become allow",
     r"""git -c alias.a=b -c alias.b=a a 'harness\b'""", "ask"),
    ("ASK ALIAS: malformed quoted alias cannot become allow",
     r'''git -c "alias.bad=grep -E 'unterminated" bad 'harness\b' ''', "ask"),
    ("ASK ALIAS: shell alias containing guarded Git is not executed speculatively",
     r'''git -c 'alias.x=!git grep -E "harness\b"' x''', "ask"),
    ("ASK ALIAS: shell alias reaching a standard guarded alias fails closed",
     r'''git -c 'alias.x=!git y' -c 'alias.y=grep -E' x 'harness\b' ''', "ask"),
    ("ASK ALIAS: shell alias defines then reaches a guarded alias",
     r'''git -c 'alias.x=!git -c alias.y=grep y -E "harness\b"' x''', "ask"),
    ("ASK ALIAS: shell alias reaching an alias cycle fails closed",
     r'''git -c 'alias.x=!git a' -c alias.a=b -c alias.b=a x''', "ask"),
    ("ASK ALIAS: shell alias reaches standard alias with inline config",
     r'''git -c 'alias.s=!git x' -c "alias.x=-c alias.y=grep y" s''', "ask"),
    ("ASK ALIAS: shell alias reaches env-count alias configuration",
     (r"git -c 'alias.s=!GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=alias.y "
      r"GIT_CONFIG_VALUE_0=grep git y' s"),
     "ask"),
    ("ASK ALIAS: shell alias reaches GIT_CONFIG_PARAMETERS alias configuration",
     (r'''git -c "alias.s=!GIT_CONFIG_PARAMETERS=\"'alias.y=grep -E'\" '''
      r'''git y 'harness\b' -- README.md" s'''),
     "ask"),
    ("GREEN ALIAS: harmless GIT_CONFIG_PARAMETERS alias remains outside the guard",
     r'''git -c "alias.s=!GIT_CONFIG_PARAMETERS=\"'alias.y=status --short'\" git y" s''',
     "allow"),
    ("ASK ALIAS: shell alias with external alias config-env fails closed",
     r'''git -c 'alias.s=!git --config-env=alias.y=BODY y' s''', "ask"),
    ("GREEN ALIAS: harmless shell alias is outside the guard",
     r'''git -c 'alias.x=!printf harmless' x''', "allow"),
    ("ASK ALIAS: literal eval reaches an ERE Git hazard",
     r'''git -c "alias.x=!eval 'git grep -E harness\\b -- README.md'" x''', "ask"),
    ("GREEN ALIAS: literal eval of a harmless command remains outside the guard",
     r'''git -c "alias.x=!eval 'printf harmless'" x''', "allow"),
    ("ASK ALIAS: sh -c reaches a rev-path Git hazard",
     r'''git -c 'alias.x=!sh -c "git show $SHA:src/f.py"' x''', "ask"),
    ("ASK ALIAS: bash -c reaches an ERE Git hazard",
     r'''git -c 'alias.x=!bash -c "git grep -E harness\b -- README.md"' x''', "ask"),
    ("ASK ALIAS: zsh -c reaches a rev-path Git hazard",
     r'''git -c 'alias.x=!zsh -c "git show $SHA:src/f.py"' x''', "ask"),
    ("GREEN ALIAS: literal shell -c harmless body remains outside the guard",
     r'''git -c 'alias.x=!sh -c "printf harmless"' x''', "allow"),
    ("ASK ALIAS: dynamic shell -c source cannot become harmless",
     r'''git -c 'alias.x=!sh -c "$CMD"' x''', "ask"),
    ("ASK ALIAS: malformed nested shell source cannot become harmless",
     r'''git -c 'alias.x=!sh -c "unterminated' x''', "ask"),
    ("RED TOKEN: double-quoted command substitution is recursively inspected",
     r'''/bin/echo "$(git grep -E 'harness\b' -- README.md)"''', "deny"),
    ("RED TOKEN: ordinary subshell parentheses stay inside command substitution",
     r'''/bin/echo "$( (printf x); git grep -E 'harness\b' -- README.md)"''', "deny"),
    ("RED TOKEN: command substitution inside arithmetic remains executable",
     r'''/bin/echo "$(( $(git grep -E 'harness\b' -- README.md) + 1 ))"''', "deny"),
    ("GREEN TOKEN: balanced literal arithmetic is not command source",
     r'''/bin/echo "$(( (1 + 2) * 3 ))"''', "allow"),
    ("ASK TOKEN: case pattern closers are outside the command-substitution model",
     r'''/bin/echo "$(case x in x) git grep -E 'harness\b' -- README.md;; esac)"''',
     "ask"),
    ("RED TOKEN: backtick substitution is recursively inspected",
     r'''/bin/echo `git grep -E 'harness\b' -- README.md`''', "deny"),
    ("GREEN TOKEN: single-quoted command text is not executed",
     r'''/bin/echo '$(git grep -E "harness\b" -- README.md)' ''', "allow"),
    ("RED TOKEN: parameter default source is recursively inspected",
     r'''/bin/echo ${value:-$(git grep -E 'harness\b' -- README.md)}''', "deny"),
    ("RED TOKEN: quoted parameter assignment source is recursively inspected",
     r'''/bin/echo "${value:="$(git grep -E 'harness\b' -- README.md)"}"''', "deny"),
    ("RED TOKEN: parameter backtick source is recursively inspected",
     r'''/bin/echo ${value:-`git grep -E 'harness\b' -- README.md`}''', "deny"),
    ("ASK TOKEN: malformed parameter source fails closed",
     r'''/bin/echo ${value:-$(git grep -E 'harness\b' -- README.md)''', "ask"),
    ("GREEN FUNCTION: declaration does not execute its body",
     r'''scan() { git grep -E 'harness\b' -- README.md; }; /bin/echo safe''', "allow"),
    ("RED FUNCTION: direct invocation executes the declared body",
     r'''scan() { git grep -E 'harness\b' -- README.md; }; scan''', "deny"),
    ("RED FUNCTION: negated invocation still executes the declared body",
     r'''scan() { git grep -E 'harness\b' -- README.md; }; ! scan''', "deny"),
    ("GREEN FUNCTION: subshell-body declaration does not execute",
     r'''scan() ( git grep -E 'harness\b' -- README.md ); /bin/echo safe''', "allow"),
    ("RED FUNCTION: subshell-body invocation executes the declared body",
     r'''scan() ( git grep -E 'harness\b' -- README.md ); scan''', "deny"),
    ("GREEN FUNCTION: function-keyword declaration does not execute",
     r'''function scan { git grep -E 'harness\b' -- README.md; }; /bin/echo safe''',
     "allow"),
    ("RED FUNCTION: function-keyword invocation executes the body",
     r'''function scan { git grep -E 'harness\b' -- README.md; }; scan''', "deny"),
    ("RED FUNCTION: control-keyword invocation executes the body",
     r'''scan() { git grep -E 'harness\b' -- README.md; }; if scan; then :; fi''',
     "deny"),
    ("ASK FUNCTION: dynamic command may invoke the declared function",
     r'''scan() { git grep -E 'harness\b' -- README.md; }; $COMMAND''', "ask"),
    ("ASK FUNCTION: an unmodelled prefix may invoke the declared function",
     r'''scan() { git grep -E 'harness\b' -- README.md; }; time -p scan''', "ask"),
    ("GREEN FUNCTION: exact data-consumer argument is not an invocation",
     r'''scan() { git grep -E 'harness\b' -- README.md; }; /bin/echo scan''', "allow"),
    ("RED FUNCTION: a call uses the definition active before redefinition",
     (r'''scan(){ git grep -E 'harness\b' -- README.md; }; scan; '''
      r'''scan(){ /bin/echo safe; }; scan'''), "deny"),
    ("GREEN FUNCTION: a later hazardous redefinition is inert until invoked",
     (r'''scan(){ /bin/echo safe; }; scan; '''
      r'''scan(){ git grep -E 'harness\b' -- README.md; }; /bin/echo done'''), "allow"),
    ("RED FUNCTION: invocation after redefinition uses the new body",
     (r'''scan(){ /bin/echo safe; }; scan; '''
      r'''scan(){ git grep -E 'harness\b' -- README.md; }; scan'''), "deny"),
    ("ASK FUNCTION: a false conditional definition is not globally active",
     (r'''if false; then scan(){ git grep -E 'harness\b' -- README.md; }; fi; '''
      r'''scan'''), "ask"),
    ("GREEN FUNCTION: an uncalled conditional definition remains inert",
     (r'''if false; then scan(){ git grep -E 'harness\b' -- README.md; }; fi; '''
      r'''/bin/echo done'''), "allow"),
    ("RED FUNCTION: a subshell redefinition cannot replace an outer hazard",
     (r'''scan(){ git grep -E 'harness\b' -- README.md; }; '''
      r'''(scan(){ /bin/echo safe; }); scan'''), "deny"),
    ("GREEN FUNCTION: a hazardous subshell redefinition does not escape",
     (r'''scan(){ /bin/echo safe; }; '''
      r'''(scan(){ git grep -E 'harness\b' -- README.md; }); scan'''), "allow"),
    ("RED FUNCTION: a subshell call uses its local redefinition",
     (r'''scan(){ /bin/echo safe; }; '''
      r'''(scan(){ git grep -E 'harness\b' -- README.md; }; scan)'''), "deny"),
    ("ASK FUNCTION: an AND-RHS safe definition may leave an outer hazard",
     (r'''scan(){ git grep -E 'harness\b' -- README.md; }; true && '''
      r'''scan(){ /bin/echo safe; }; scan'''), "ask"),
    ("ASK FUNCTION: an AND-RHS hazard may replace an outer safe definition",
     (r'''scan(){ /bin/echo safe; }; true && '''
      r'''scan(){ git grep -E 'harness\b' -- README.md; }; scan'''), "ask"),
    ("ASK FUNCTION: an OR-RHS safe definition may leave an outer hazard",
     (r'''scan(){ git grep -E 'harness\b' -- README.md; }; false || '''
      r'''scan(){ /bin/echo safe; }; scan'''), "ask"),
    ("ASK FUNCTION: an OR-RHS hazard may replace an outer safe definition",
     (r'''scan(){ /bin/echo safe; }; false || '''
      r'''scan(){ git grep -E 'harness\b' -- README.md; }; scan'''), "ask"),
    ("GREEN FUNCTION: an unconditional definition supersedes a maybe binding",
     (r'''scan(){ git grep -E 'harness\b' -- README.md; }; false && '''
      r'''scan(){ git grep -E 'harness\b' -- README.md; }; '''
      r'''scan(){ /bin/echo safe; }; scan'''), "allow"),
    ("RED FUNCTION: an unconditional hazard supersedes a maybe binding",
     (r'''scan(){ /bin/echo safe; }; true || '''
      r'''scan(){ /bin/echo safe; }; '''
      r'''scan(){ git grep -E 'harness\b' -- README.md; }; scan'''), "deny"),
    ("RED FUNCTION: a non-final pipeline definition cannot replace an outer hazard",
     (r'''scan(){ git grep -E 'harness\b' -- README.md; }; '''
      r'''scan(){ /bin/echo safe; } | /bin/cat; scan'''), "deny"),
    ("GREEN FUNCTION: a non-final pipeline hazard does not escape its component",
     (r'''scan(){ /bin/echo safe; }; '''
      r'''scan(){ git grep -E 'harness\b' -- README.md; } | /bin/cat; scan'''),
     "allow"),
    ("RED FUNCTION: a brace pipeline component cannot replace an outer hazard",
     (r'''scan(){ git grep -E 'harness\b' -- README.md; }; { '''
      r'''scan(){ /bin/echo safe; }; /bin/echo component; } | /bin/cat; scan'''),
     "deny"),
    ("GREEN FUNCTION: a brace pipeline hazard remains component-local",
     (r'''scan(){ /bin/echo safe; }; { '''
      r'''scan(){ git grep -E 'harness\b' -- README.md; }; '''
      r'''/bin/echo component; } | /bin/cat; scan'''), "allow"),
    ("RED TOKEN: quoted arithmetic dollar source is recursively inspected",
     r'''/bin/echo "$(( "$(git grep -E 'harness\b' -- README.md)" + 1 ))"''', "deny"),
    ("RED TOKEN: arithmetic backtick source is recursively inspected",
     r'''/bin/echo "$(( `git grep -E 'harness\b' -- README.md` + 1 ))"''', "deny"),
    ("GREEN TOKEN: arithmetic left shift is not a heredoc",
     r'''/bin/echo "$(( 1 << 2 ))"''', "allow"),
    ("GREEN TOKEN: arithmetic-command left shift is not a heredoc",
     r'''(( value = 1 << 2 ))''', "allow"),
    ("GREEN TOKEN: arithmetic for-clause left shift is not a heredoc",
     r'''for ((i = 1; i << 2; i++)); do /bin/echo "$i"; done''', "allow"),
    ("GREEN TOKEN: literal here-string text is not a heredoc body",
     r'''/bin/cat <<< "git grep -E 'harness\b' -- README.md"''', "allow"),
    ("RED TOKEN: command substitution in a here-string still executes",
     r'''cat <<< "$(git grep -E 'harness\b' -- README.md)"''', "deny"),
    ("RED TOKEN: direct shell here-string body is recursively classified",
     r'''sh <<< "git grep -E 'harness\b' -- README.md"''', "deny"),
    ("RED TOKEN: fd-zero direct here-string has the same recursive source",
     r'''sh 0<<< "git grep -E 'harness\b' -- README.md"''', "deny"),
    ("GREEN TOKEN: harmless static direct shell here-string is classified",
     r'''sh 0<<< "/bin/echo safe"''', "allow"),
    ("ASK TOKEN: a dynamic direct shell here-string cannot be inspected",
     r'''sh <<< "$BODY"''', "ask"),
    ("RED TOKEN: a leading here-string still binds to the shell command",
     r'''<<< "git grep -E 'harness\b' -- README.md" sh''', "deny"),
    ("ASK TOKEN: a brace compound carries stdin to a later interpreter",
     r'''{ /bin/echo prep; sh; } <<< "git grep -E 'harness\b' -- README.md"''',
     "ask"),
    ("RED TOKEN: a single-shell subshell retains direct recursive classification",
     r'''(sh) <<< "git grep -E 'harness\b' -- README.md"''', "deny"),
    ("ASK TOKEN: an if branch can carry stdin to a later interpreter",
     r'''if true; then sh; fi <<< "git grep -E 'harness\b' -- README.md"''', "ask"),
    ("ASK TOKEN: an invoked function edge can carry stdin to its interpreter",
     r'''run() { sh; }; run <<< "git grep -E 'harness\b' -- README.md"''', "ask"),
    ("ASK TOKEN: an unknown here-string consumer edge stays unresolved",
     r'''runner <<< "/bin/echo safe"''', "ask"),
    ("GREEN TOKEN: non-stdin here-string does not supply interpreter source",
     r'''sh 3<<< "git grep -E 'harness\b' -- README.md"''', "allow"),
    ("ASK TOKEN: pipeline into a shell interpreter has unproven source association",
     r'''/usr/bin/printf '%s\n' "git grep -E 'harness\b' -- README.md" | sh''', "ask"),
    ("ASK TOKEN: process substitution into a shell interpreter is unproven",
     r'''sh < <(/usr/bin/printf '%s\n' "git grep -E 'harness\b' -- README.md")''', "ask"),
    ("ASK TOKEN: whitespace variants do not hide process-substitution input",
     r'''sh <  <(/usr/bin/printf '%s\n' "git grep -E 'harness\b' -- README.md")''', "ask"),
    ("ASK TOKEN: fd-zero process-substitution input supplies interpreter source",
     r'''sh 0< <(/usr/bin/printf '%s\n' "git grep -E 'harness\b' -- README.md")''', "ask"),
    ("GREEN TOKEN: fd-three process-substitution input is not shell stdin",
     r'''sh 3< <(/usr/bin/printf '%s\n' "git grep -E 'harness\b' -- README.md")''', "allow"),
    ("ASK TOKEN: a leading dynamic file redirect supplies interpreter source",
     r'''0<"$SCRIPT" sh''', "ask"),
    ("GREEN TOKEN: /dev/null is an exact inert shell-input source",
     r'''0</dev/null sh''', "allow"),
    ("GREEN TOKEN: fd-three file input is not shell stdin",
     r'''3<"$DATA" sh''', "allow"),
    ("GREEN TOKEN: an inert data edge does not join an unrelated shell",
     (r'''/bin/cat <<< "git grep -E 'harness\b' -- README.md"; '''
      r'''sh </dev/null'''), "allow"),
    ("RED TOKEN: other redirections do not obscure direct here-string recursion",
     r'''sh 2>/dev/null 0<<< "git grep -E 'harness\b' -- README.md"''', "deny"),
    ("RED TOKEN: an exact shell path retains direct here-string recursion",
     r'''/bin/sh 2>/dev/null 0<<< "git grep -E 'harness\b' -- README.md"''', "deny"),
    ("GREEN TOKEN: fallback admits an exact data consumer with literal input",
     r'''/bin/cat 2>/dev/null 0<<< "git grep -E 'harness\b' -- README.md"''', "allow"),
    ("ASK TOKEN: unproven launcher reachability stays behind the fallback",
     r'''launcher /bin/sh 0<<< "git grep -E 'harness\b' -- README.md"''', "ask"),
    ("GREEN TOKEN: shell -c does not read pipeline source as commands",
     r'''/usr/bin/printf x | sh -c cat''', "allow"),
    ("GREEN TOKEN: shell script operand does not read stdin as commands",
     r'''/usr/bin/printf x | sh script.sh''', "allow"),
    ("GREEN GIT: a proven native subcommand is not an ambient alias",
     "git status --short", "allow"),
    ("GREEN GIT: standard submodule uses the trusted default exec path",
     "git submodule status", "allow"),
    ("ASK GIT: GIT_EXEC_PATH cannot authorize an external main command",
     "GIT_EXEC_PATH=/tmp/untrusted git submodule status", "ask"),
    ("ASK GIT: --exec-path cannot authorize an external main command",
     "git --exec-path=/tmp/untrusted submodule status", "ask"),
    ("GREEN GIT: a builtin remains bound to the trusted Git under env override",
     "GIT_EXEC_PATH=/tmp/untrusted git status --short", "allow"),
    ("GREEN GIT: a builtin remains bound to the trusted Git under option override",
     "git --exec-path=/tmp/untrusted status --short", "allow"),
    ("ASK GIT: an unknown subcommand may be an ambient alias",
     "git project-helper --version", "ask"),
    ("ASK GIT: a command-local PATH may select a different Git executable",
     "PATH=/tmp git status --short", "ask"),
    ("RED HEREDOC: a shell interpreter executes its stdin body",
     "sh <<'EOF'\ngit grep -E 'harness\\b' -- README.md\nEOF\n", "deny"),
    ("RED HEREDOC: explicit shell -s reads stdin despite positional arguments",
     "sh -s script-name <<'EOF'\ngit grep -E 'harness\\b' -- README.md\nEOF\n", "deny"),
    ("RED HEREDOC: a long shell option containing c is not short -c",
     "bash --norc <<'EOF'\ngit grep -E 'harness\\b' -- README.md\nEOF\n", "deny"),
    ("RED HEREDOC: env options cannot hide a shell reading stdin",
     "env -u UNUSED sh <<'EOF'\ngit grep -E 'harness\\b' -- README.md\nEOF\n", "deny"),
    ("RED HEREDOC: shell option arguments do not become script operands",
     "bash --rcfile /dev/null <<'EOF'\ngit grep -E 'harness\\b' -- README.md\nEOF\n",
     "deny"),
    ("GREEN HEREDOC: a data consumer does not execute its stdin body",
     "/bin/cat <<'EOF'\ngit grep -E 'harness\\b' -- README.md\nEOF\n", "allow"),
    ("GREEN HEREDOC: shell -c executes its argument, not heredoc stdin",
     "sh -c cat <<'EOF'\ngit grep -E 'harness\\b' -- README.md\nEOF\n", "allow"),
    ("ASK HEREDOC: pipeline association is not a direct classified heredoc",
     "cat <<'EOF' | sh\ngit grep -E 'harness\\b' -- README.md\nEOF\n", "ask"),
    ("RED HEREDOC: unquoted data heredoc expands command substitution",
     "cat <<EOF\n$(git grep -E 'harness\\b' -- README.md)\nEOF\n", "deny"),
    ("GREEN HEREDOC: unquoted literal Git text is still data",
     "/bin/cat <<EOF\ngit grep -E 'harness\\b' -- README.md\nEOF\n", "allow"),
    ("GREEN HEREDOC: quoted dashed delimiter feeds a data consumer",
     "/bin/cat <<'END-MARK'\ngit grep -E 'harness\\b' -- README.md\nEND-MARK\n",
     "allow"),
    ("RED HEREDOC: quoted dashed delimiter feeds executable shell stdin",
     "sh <<'END-MARK'\ngit grep -E 'harness\\b' -- README.md\nEND-MARK\n",
     "deny"),
    ("RED HEREDOC: unquoted dashed delimiter expands a command substitution",
     "cat <<END-MARK\n$(git grep -E 'harness\\b' -- README.md)\nEND-MARK\n",
     "deny"),
    ("GREEN HEREDOC: mixed quoted delimiter segments are quote-removed",
     "/bin/cat <<E'ND-'MARK\ngit grep -E 'harness\\b' -- README.md\nEND-MARK\n",
     "allow"),
    ("ASK HEREDOC: dynamic-looking delimiter syntax is outside the literal model",
     "cat <<$(printf EOF)\nx\nEOF\n", "ask"),
    ("ASK HEREDOC: dynamic downstream consumer may execute stdin",
     "cat <<'END-MARK' | $SHELL\ngit grep -E 'harness\\b' -- README.md\nEND-MARK\n",
     "ask"),
    ("GREEN HEREDOC: non-stdin descriptor remains data",
     "/bin/cat 3<<'EOF'\ngit grep -E 'harness\\b' -- README.md\nEOF\n", "allow"),
    ("RED HEREDOC: descriptor zero feeds executable shell stdin",
     "sh 0<<'EOF'\ngit grep -E 'harness\\b' -- README.md\nEOF\n", "deny"),
    ("GREEN HEREDOC: multiple quoted data redirects remain data",
     ("/bin/cat <<'A' <<'B'\ngit grep -E 'harness\\b' -- README.md\nA\n"
      "literal\nB\n"), "allow"),
    ("ASK HEREDOC: executable shell has multiple possible stdin redirects",
     ("sh <<'A' <<'B'\nliteral\nA\n"
      "git grep -E 'harness\\b' -- README.md\nB\n"), "ask"),
    ("RED HEREDOC: every unquoted data body expands, not only the winning redirect",
     ("cat <<A <<'B'\n$(git grep -E 'harness\\b' -- README.md)\nA\n"
      "literal\nB\n"), "deny"),
]

# Keep the depth boundary generated from the same constant the resolver enforces.
FIXTURES.append((
    "ASK ALIAS: expansion beyond the bounded closure cannot become allow",
    "git " + " ".join(f"-c alias.a{index}=a{index + 1}"
                       for index in range(MAX_ALIAS_DEPTH + 1))
    + " -c 'alias.a9=grep -E' a0 'harness\\b' -- README.md",
    "ask",
))
FIXTURES.append((
    "ASK TOKEN: executable-source nesting beyond the bound fails closed",
    '/bin/echo "' + ("$(" * (MAX_SOURCE_DEPTH + 2)) + "echo x"
    + (")" * (MAX_SOURCE_DEPTH + 2)) + '"',
    "ask",
))


def fixture_pair_duplicates(fixtures):
    """Return repeated public command/expected pairs; labels do not make cases distinct."""
    seen = set()
    duplicates = []
    for _label, command, expected in fixtures:
        pair = (command, expected)
        if pair in seen:
            duplicates.append(pair)
        seen.add(pair)
    return duplicates

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
    duplicates = fixture_pair_duplicates(FIXTURES)
    uniqueness_ok = bool(FIXTURES) and not duplicates
    bad += 0 if uniqueness_ok else 1
    print("  %s fixture command/expected pairs are non-empty and unique" % (
        "PASS" if uniqueness_ok else "FAIL"))
    if duplicates:
        print("        duplicate pairs: %r" % duplicates)
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
    construct_failures = check_pcre_constructs_against_git()
    bad += len(construct_failures)
    if construct_failures:
        for failure in construct_failures:
            print("  FAIL PCRE construct vs installed git: %s" % failure)
    else:
        print("  PASS PCRE constructs and escaped-group control match installed git")
    alias_failures = check_aliases_against_git()
    bad += len(alias_failures)
    if alias_failures:
        for failure in alias_failures:
            print("  FAIL alias behavior vs installed git: %s" % failure)
    else:
        print("  PASS quoted, recursive, and cyclic aliases match installed git")
    def retain_pcre_engine(label, command):
        if label != "-NUM between P and E":
            return command
        return [word.replace("-P1Ee", "-P1Pe") for word in command]
    retained_pcre_failures = check_option_grammar_against_git(retain_pcre_engine)
    retained_pcre_red = any(
        "exact final-engine order for -NUM between P and E" in failure
        for failure in retained_pcre_failures
    )
    bad += 0 if retained_pcre_red else 1
    print("  %s final-engine oracle rejects an incorrectly retained PCRE engine" % (
        "PASS" if retained_pcre_red else "FAIL"))
    boundary_failures, boundary_checks, boundary_skips = check_shell_boundary_behavior()
    bad += len(boundary_failures)
    if boundary_failures:
        for failure in boundary_failures:
            print("  FAIL shell-boundary behavior probe: %s" % failure)
    else:
        print("  PASS downstream expansion and explicit harmless identities match installed shells")
    print("SHELL-BOUNDARY-SUMMARY checks=%d skips=%d failures=%d" % (
        boundary_checks, boundary_skips, len(boundary_failures)))

    # Prove the absence branch is narrow: removing the availability check or broadening
    # it to skip sh/bash/exact-path probes changes these counts and turns this selftest red.
    original_which = shutil.which
    shutil.which = lambda name: None if name == "zsh" else original_which(name)
    try:
        absent_failures, absent_checks, absent_skips = check_shell_boundary_behavior()
    finally:
        shutil.which = original_which
    absence_ok = not absent_failures and absent_checks == 12 and absent_skips == 9
    bad += 0 if absence_ok else 1
    print("  %s absent zsh skips only 9 zsh probe groups; 12 portable probes still execute" % (
        "PASS" if absence_ok else "FAIL"))

    # Mutate each production call site, not its helper in isolation. Every representative
    # command must lose its protected outcome when the mechanism is bypassed.
    original_scanner = scan_pcre_constructs
    globals()["scan_pcre_constructs"] = lambda _pattern: PatternScan((), ())
    try:
        scanner_red = decide(r"""git grep -E '^\Qabc\E$' -- fixture.txt""")[0] != "deny"
    finally:
        globals()["scan_pcre_constructs"] = original_scanner
    bad += 0 if scanner_red else 1
    print("  %s scanner callsite mutation loses the PCRE-construct deny" % (
        "PASS" if scanner_red else "FAIL"))

    def premature_posix_close(pattern):
        scan = original_scanner(pattern)
        if "[[:" in pattern and "(?" in pattern:
            return PatternScan(tuple(sorted(set(scan.atoms) | {"(?"})), scan.uncertain)
        return scan
    globals()["scan_pcre_constructs"] = premature_posix_close
    try:
        posix_bracket_red = decide(
            r"""git grep -E '^[[:alpha:](?)]+$' -- fixture.txt"""
        )[0] != "allow"
    finally:
        globals()["scan_pcre_constructs"] = original_scanner
    bad += 0 if posix_bracket_red else 1
    print("  %s scanner callsite mutation exposes premature POSIX bracket closure" % (
        "PASS" if posix_bracket_red else "FAIL"))

    original_long = canonical_long_option
    def exact_long_only(text):
        name = text.partition("=")[0]
        if name not in GREP_LONG_OPTION_NAMES:
            value = text.partition("=")[2]
            return LongOptionResolution(None, value, "=" in text, (), True)
        return original_long(text)
    globals()["canonical_long_option"] = exact_long_only
    try:
        long_red = decide(
            r"""git grep --max-de 1 -E 'harness\b' -- README.md""")[0] != "deny"
    finally:
        globals()["canonical_long_option"] = original_long
    bad += 0 if long_red else 1
    print("  %s long-option callsite mutation loses required-value abbreviation deny" % (
        "PASS" if long_red else "FAIL"))

    original_alias = resolve_git_alias
    globals()["resolve_git_alias"] = (
        lambda subcommand, tail, _aliases, _authority, _exec_path, _deadline=None,
        _command_env=None, _lookup_authority_uncertain=False:
        (subcommand.lower(), list(tail), None, [])
    )
    try:
        alias_red = decide(
            r"""git -c alias.a=b -c 'alias.b=grep -E' a 'harness\b' -- README.md"""
        )[0] != "deny"
    finally:
        globals()["resolve_git_alias"] = original_alias
    bad += 0 if alias_red else 1
    print("  %s alias-resolution callsite mutation loses recursive alias deny" % (
        "PASS" if alias_red else "FAIL"))

    original_nested_shell = nested_shell_invocation
    def ignore_alias_eval(resolution, current_shell="sh", deadline=None):
        if resolution.items and os.path.basename(resolution.items[0][0]) == "eval":
            return None
        return original_nested_shell(resolution, current_shell, deadline)
    globals()["nested_shell_invocation"] = ignore_alias_eval
    try:
        alias_eval_red = decide(
            r'''git -c "alias.x=!eval 'git grep -E harness\\b -- README.md'" x'''
        )[0] != "ask"
    finally:
        globals()["nested_shell_invocation"] = original_nested_shell
    bad += 0 if alias_eval_red else 1
    print("  %s shell-alias eval traversal mutation loses uncertain outcome" % (
        "PASS" if alias_eval_red else "FAIL"))

    def ignore_alias_shell_c(resolution, current_shell="sh", deadline=None):
        if (resolution.items
                and os.path.basename(resolution.items[0][0]) in SHELLS):
            return None
        return original_nested_shell(resolution, current_shell, deadline)
    globals()["nested_shell_invocation"] = ignore_alias_shell_c
    try:
        alias_shell_red = decide(
            r'''git -c 'alias.x=!sh -c "git show $SHA:src/f.py"' x'''
        )[0] != "ask"
    finally:
        globals()["nested_shell_invocation"] = original_nested_shell
    bad += 0 if alias_shell_red else 1
    print("  %s shell-alias -c traversal mutation loses uncertain outcome" % (
        "PASS" if alias_shell_red else "FAIL"))

    original_parameter_items = _git_config_parameter_items
    globals()["_git_config_parameter_items"] = lambda _parameters: ([], None)
    try:
        alias_parameter_red = decide(
            r'''git -c "alias.s=!GIT_CONFIG_PARAMETERS=\"'alias.y=grep -E'\" '''
            r'''git y 'harness\b' -- README.md" s'''
        )[0] != "ask"
    finally:
        globals()["_git_config_parameter_items"] = original_parameter_items
    bad += 0 if alias_parameter_red else 1
    print("  %s shell-alias config-parameter mutation loses uncertain outcome" % (
        "PASS" if alias_parameter_red else "FAIL"))

    original_dollar = _command_substitution
    def drop_dollar_body(source, start):
        _body, end = original_dollar(source, start)
        return "", end
    globals()["_command_substitution"] = drop_dollar_body
    try:
        dollar_red = decide(
            r'''/bin/echo "$(git grep -E 'harness\b' -- README.md)"'''
        )[0] != "deny"
    finally:
        globals()["_command_substitution"] = original_dollar
    bad += 0 if dollar_red else 1
    print("  %s dollar-substitution callsite mutation loses nested deny" % (
        "PASS" if dollar_red else "FAIL"))

    def close_at_first_parenthesis(source, start):
        end = source.find(")", start + 2)
        if end < 0:
            return original_dollar(source, start)
        return source[start + 2:end], end + 1
    globals()["_command_substitution"] = close_at_first_parenthesis
    try:
        grouped_red = decide(
            r'''/bin/echo "$( (printf x); git grep -E 'harness\b' -- README.md)"'''
        )[0] != "deny"
    finally:
        globals()["_command_substitution"] = original_dollar
    bad += 0 if grouped_red else 1
    print("  %s parenthesis-balancing mutation loses grouped substitution deny" % (
        "PASS" if grouped_red else "FAIL"))

    original_case = _has_unmodelled_case_pattern
    globals()["_has_unmodelled_case_pattern"] = lambda _body: False
    try:
        case_red = decide(
            r'''/bin/echo "$(case x in x) git grep -E 'harness\b' -- README.md;; esac)"'''
        )[0] != "ask"
    finally:
        globals()["_has_unmodelled_case_pattern"] = original_case
    bad += 0 if case_red else 1
    print("  %s case-closer mutation loses fail-closed substitution outcome" % (
        "PASS" if case_red else "FAIL"))

    original_arithmetic = _arithmetic_expansion
    def drop_arithmetic_sources(source, start):
        body, end, _sources = original_arithmetic(source, start)
        return body, end, ()
    globals()["_arithmetic_expansion"] = drop_arithmetic_sources
    try:
        arithmetic_red = decide(
            r'''/bin/echo "$(( $(git grep -E 'harness\b' -- README.md) + 1 ))"'''
        )[0] != "deny"
    finally:
        globals()["_arithmetic_expansion"] = original_arithmetic
    bad += 0 if arithmetic_red else 1
    print("  %s arithmetic-source mutation loses nested substitution deny" % (
        "PASS" if arithmetic_red else "FAIL"))

    original_parameter = _parameter_expansion
    def drop_parameter_sources(source, start):
        text, end, _sources = original_parameter(source, start)
        return text, end, ()
    globals()["_parameter_expansion"] = drop_parameter_sources
    try:
        parameter_red = decide(
            r'''/bin/echo ${value:-$(git grep -E 'harness\b' -- README.md)}'''
        )[0] != "deny"
    finally:
        globals()["_parameter_expansion"] = original_parameter
    bad += 0 if parameter_red else 1
    print("  %s parameter-expansion callsite mutation loses nested deny" % (
        "PASS" if parameter_red else "FAIL"))

    globals()["_arithmetic_expansion"] = drop_arithmetic_sources
    try:
        quoted_arithmetic_red = decide(
            r'''/bin/echo "$(( "$(git grep -E 'harness\b' -- README.md)" + 1 ))"'''
        )[0] != "deny"
        backtick_arithmetic_red = decide(
            r'''/bin/echo "$(( `git grep -E 'harness\b' -- README.md` + 1 ))"'''
        )[0] != "deny"
    finally:
        globals()["_arithmetic_expansion"] = original_arithmetic
    bad += 0 if quoted_arithmetic_red else 1
    bad += 0 if backtick_arithmetic_red else 1
    print("  %s quoted-arithmetic dollar mutation loses nested deny" % (
        "PASS" if quoted_arithmetic_red else "FAIL"))
    print("  %s arithmetic-backtick mutation loses nested deny" % (
        "PASS" if backtick_arithmetic_red else "FAIL"))

    original_authorize = authorize_git_subcommand
    def admit_unknown(subcommand, authority, effective_exec_path):
        if subcommand == "project-helper":
            return None
        return original_authorize(subcommand, authority, effective_exec_path)
    globals()["authorize_git_subcommand"] = admit_unknown
    try:
        unknown_subcommand_red = decide("git project-helper --version")[0] != "ask"
    finally:
        globals()["authorize_git_subcommand"] = original_authorize
    bad += 0 if unknown_subcommand_red else 1
    print("  %s native-command classification mutation loses unknown-alias ask" % (
        "PASS" if unknown_subcommand_red else "FAIL"))

    original_discovery = trusted_git_authority
    globals()["trusted_git_authority"] = lambda _executable="git", deadline=None: (
        _ for _ in ()).throw(GitAuthorityError("planted discovery failure"))
    try:
        discovery_red = decide("git status --short")[0] == "ask"
    finally:
        globals()["trusted_git_authority"] = original_discovery
    bad += 0 if discovery_red else 1
    print("  %s trusted-Git discovery failure asks instead of allowing" % (
        "PASS" if discovery_red else "FAIL"))

    trusted_authority = original_discovery()
    globals()["trusted_git_authority"] = lambda _executable="git", deadline=None: GitAuthority(
        trusted_authority.executable, trusted_authority.exec_path,
        trusted_authority.builtins, trusted_authority.main - {"submodule"},
    )
    try:
        drift_red = decide("git submodule status")[0] != "allow"
    finally:
        globals()["trusted_git_authority"] = original_discovery
    bad += 0 if drift_red else 1
    print("  %s trusted-Git inventory drift loses standard submodule allow" % (
        "PASS" if drift_red else "FAIL"))

    # An alternate executable must fail before any subprocess is attempted. Querying the
    # candidate in order to decide whether to trust it would execute attacker-selected code.
    candidate_calls = []
    try:
        original_discovery(
            "/nonexistent/bin/git",
            runner=lambda *args, **kwargs: candidate_calls.append((args, kwargs)),
        )
        alternate_preprobe_ok = False
    except GitAuthorityError:
        alternate_preprobe_ok = not candidate_calls
    bad += 0 if alternate_preprobe_ok else 1
    print("  %s alternate Git is rejected before candidate execution" % (
        "PASS" if alternate_preprobe_ok else "FAIL"))

    globals()["trusted_git_authority"] = (
        lambda _executable="git", deadline=None: trusted_authority
    )
    try:
        alternate_callsite_red = decide(
            "/nonexistent/bin/git status --short")[0] != "ask"
    finally:
        globals()["trusted_git_authority"] = original_discovery
    bad += 0 if alternate_callsite_red else 1
    print("  %s alternate-Git authority callsite mutation loses fail-closed ask" % (
        "PASS" if alternate_callsite_red else "FAIL"))

    original_lookup_authority = changed_git_lookup_authority_error
    globals()["changed_git_lookup_authority_error"] = (
        lambda _executable, _uncertain: "")
    try:
        lookup_authority_red = all(decide(source)[0] != "ask" for source in (
            "command -p git status --short",
            "builtin command -p git status --short",
            "env -i git status --short",
            "env --ignore-environment git status --short",
            "env -u PATH git status --short",
            "env --unset=PATH git status --short",
            "sudo -i git status --short",
        ))
    finally:
        globals()["changed_git_lookup_authority_error"] = original_lookup_authority
    bad += 0 if lookup_authority_red else 1
    print("  %s wrapper lookup-authority mutation transfers PATH Git authority" % (
        "PASS" if lookup_authority_red else "FAIL"))

    original_nested_invocation = nested_shell_invocation
    def drop_nested_authority(resolution, current_shell="sh", deadline=None):
        invocation = original_nested_invocation(resolution, current_shell, deadline)
        if invocation is None:
            return None
        return invocation._replace(
            command_env=dict(os.environ), lookup_authority_uncertain=False)
    globals()["nested_shell_invocation"] = drop_nested_authority
    try:
        nested_authority_red = all(decide(source)[0] != "ask" for source in (
            "env -i sh -c 'git status --short'",
            "env -u PATH sh -c 'git status --short'",
            "sudo sh -c 'git status --short'",
        ))
    finally:
        globals()["nested_shell_invocation"] = original_nested_invocation
    bad += 0 if nested_authority_red else 1
    print("  %s nested-shell mutation drops wrapper lookup authority" % (
        "PASS" if nested_authority_red else "FAIL"))

    original_direct_invocation = direct_here_string_invocation
    def drop_here_string_authority(
            source, current_shell="zsh", equals_state=ZSH_EQUALS_ON,
            command_env=None, lookup_authority_uncertain=False, deadline=None):
        direct = original_direct_invocation(
            source, current_shell, equals_state, command_env,
            lookup_authority_uncertain, deadline)
        if direct is None:
            return None
        resolution, invocation = direct
        return (resolution._replace(
                    command_env=dict(os.environ),
                    lookup_authority_uncertain=False),
                invocation._replace(
                    command_env=dict(os.environ),
                    lookup_authority_uncertain=False))
    globals()["direct_here_string_invocation"] = drop_here_string_authority
    try:
        here_authority_red = all(decide(source)[0] != "ask" for source in (
            "env -i sh 0<<< 'git status --short'",
            "PATH=/usr/bin; sh 0<<< 'git status --short'",
        ))
    finally:
        globals()["direct_here_string_invocation"] = original_direct_invocation
    bad += 0 if here_authority_red else 1
    print("  %s here-string mutation drops wrapper lookup authority" % (
        "PASS" if here_authority_red else "FAIL"))

    original_heredoc_decision = heredoc_equals_decision
    def drop_heredoc_authority(
            source, deadline=None, subcommands=None, classifier=None,
            **context):
        stripped = (None if classifier is None else
                    lambda body, shell, state, inner_deadline, _env, _lookup:
                    classifier(body, shell, state, inner_deadline,
                               dict(os.environ), False))
        return original_heredoc_decision(
            source, deadline, subcommands, stripped, **context)
    globals()["heredoc_equals_decision"] = drop_heredoc_authority
    try:
        heredoc_authority_red = decide(
            "env -i sh <<'EOF'\ngit status --short\nEOF\n")[0] != "ask"
    finally:
        globals()["heredoc_equals_decision"] = original_heredoc_decision
    bad += 0 if heredoc_authority_red else 1
    print("  %s heredoc mutation drops wrapper lookup authority" % (
        "PASS" if heredoc_authority_red else "FAIL"))

    original_alias_context = _alias_authority_context
    globals()["_alias_authority_context"] = (
        lambda _env, _lookup: (dict(os.environ), False))
    try:
        alias_authority_red = all(decide(source)[0] != "ask" for source in (
            "git -c 'alias.x=!env -i sh -c \"git status --short\"' x",
            "git -c 'alias.x=!env -i sh -c \"eval git\\ status\\ --short\"' x",
            "git -c 'alias.x=!env -i sh 0<<< \"git status --short\"' x",
        ))
    finally:
        globals()["_alias_authority_context"] = original_alias_context
    bad += 0 if alias_authority_red else 1
    print("  %s shell-alias re-entry mutation drops lookup authority" % (
        "PASS" if alias_authority_red else "FAIL"))

    original_alias_environments = _alias_command_environment_states
    globals()["_alias_command_environment_states"] = (
        lambda _source, commands, command_env,
        lookup_authority_uncertain, _deadline: tuple(
            (dict(command_env), bool(lookup_authority_uncertain))
            for _command in commands))
    try:
        alias_path_red = decide(
            "git -c 'alias.x=!PATH=/usr/bin; sh -c \"git status --short\"' x"
        )[0] != "ask"
    finally:
        globals()["_alias_command_environment_states"] = original_alias_environments
    bad += 0 if alias_path_red else 1
    print("  %s shell-alias PATH-state callsite mutation transfers ambient authority" % (
        "PASS" if alias_path_red else "FAIL"))

    original_environment_states = command_environment_states
    globals()["command_environment_states"] = (
        lambda _source, commands, initial_env=None,
        initial_lookup_uncertain=False, deadline=None: tuple(
            (dict(os.environ if initial_env is None else initial_env),
             bool(initial_lookup_uncertain)) for _command in commands))
    try:
        path_state_red = all(decide(source)[0] != "ask" for source in (
            "PATH=/usr/bin; =git grep -P harness -- README.md",
            "PATH=/definitely-missing; =git grep -E 'harness\\b' -- README.md",
            "PATH=/usr/bin; sh 0<<< 'git status --short'",
            "git -c 'alias.x=!PATH=/usr/bin; sh 0<<< \"git status --short\"' x",
        ))
    finally:
        globals()["command_environment_states"] = original_environment_states
    bad += 0 if path_state_red else 1
    print("  %s straight-line PATH-state mutation transfers ambient Git authority" % (
        "PASS" if path_state_red else "FAIL"))

    original_descendant_lookup = _descendant_lookup_authority
    globals()["_descendant_lookup_authority"] = (
        lambda resolution: resolution.lookup_authority_uncertain)
    try:
        command_p_child_red = all(decide(source)[0] != expected for source, expected in (
            ("command -p zsh -c \"=git grep -E 'harness\\\\b' -- README.md\"",
             "deny"),
            ("command -p zsh -c \"=git grep -P 'harness\\\\b' -- README.md\"",
             "allow"),
            ("command -p zsh 0<<< \"=git grep -E 'harness\\b' -- README.md\"",
             "deny"),
        ))
    finally:
        globals()["_descendant_lookup_authority"] = original_descendant_lookup
    bad += 0 if command_p_child_red else 1
    print("  %s command-p descendant mutation transfers launcher uncertainty" % (
        "PASS" if command_p_child_red else "FAIL"))

    # All three discovery calls share one monotonic budget. A slow first probe reduces the
    # next timeout; it cannot reset a fresh allowance for each subprocess.
    _GIT_AUTHORITY_CACHE.clear()
    ticks = [0.0]
    observed_timeouts = []
    def budget_runner(argv, **kwargs):
        observed_timeouts.append(kwargs["timeout"])
        ticks[0] += 0.3
        if argv[-1] == "--exec-path":
            stdout = "/tmp/trusted-git-core\n"
        elif argv[-1] == "--list-cmds=builtins":
            stdout = "grep status\n"
        else:
            stdout = "grep status submodule\n"
        return subprocess.CompletedProcess(argv, 0, stdout, "")
    try:
        budget_authority = original_discovery(
            "git", deadline=1.0, runner=budget_runner, clock=lambda: ticks[0])
        shared_budget_ok = (
            budget_authority.builtins == frozenset({"grep", "status"})
            and observed_timeouts == [0.75, 0.7, 0.4]
        )
    finally:
        _GIT_AUTHORITY_CACHE.clear()
    bad += 0 if shared_budget_ok else 1
    print("  %s Git discovery subprocesses consume one shared deadline" % (
        "PASS" if shared_budget_ok else "FAIL"))

    _GIT_AUTHORITY_CACHE.clear()
    ticks = [0.0]
    calls = [0]
    def exhausted_runner(argv, **kwargs):
        calls[0] += 1
        ticks[0] = 2.0
        return subprocess.CompletedProcess(argv, 0, "/tmp/trusted-git-core\n", "")
    try:
        original_discovery(
            "git", deadline=1.0, runner=exhausted_runner, clock=lambda: ticks[0])
        exhausted_ok = False
    except GitAuthorityError:
        exhausted_ok = calls[0] == 1
    finally:
        _GIT_AUTHORITY_CACHE.clear()
    bad += 0 if exhausted_ok else 1
    print("  %s exhausted shared deadline stops before the next Git probe" % (
        "PASS" if exhausted_ok else "FAIL"))

    _GIT_AUTHORITY_CACHE.clear()
    timeout_calls = []
    def timeout_runner(argv, **kwargs):
        timeout_calls.append((tuple(argv), kwargs["timeout"]))
        raise subprocess.TimeoutExpired(argv, kwargs["timeout"])
    try:
        original_discovery("git", runner=timeout_runner)
        subprocess_timeout_ok = False
    except GitAuthorityError:
        subprocess_timeout_ok = (
            len(timeout_calls) == 1
            and timeout_calls[0][0][-1] == "--exec-path"
            and 0 < timeout_calls[0][1] <= GIT_PROBE_TIMEOUT_SECONDS
        )
    finally:
        _GIT_AUTHORITY_CACHE.clear()
    bad += 0 if subprocess_timeout_ok else 1
    print("  %s Git discovery timeout asks before a second probe" % (
        "PASS" if subprocess_timeout_ok else "FAIL"))

    original_remaining_timeout = _remaining_probe_timeout
    globals()["_remaining_probe_timeout"] = lambda _deadline, _clock: 0.75
    _GIT_AUTHORITY_CACHE.clear()
    ticks = [0.0]
    def reset_budget_runner(argv, **kwargs):
        ticks[0] += 2.0
        if argv[-1] == "--exec-path":
            stdout = "/tmp/trusted-git-core\n"
        elif argv[-1] == "--list-cmds=builtins":
            stdout = "grep status\n"
        else:
            stdout = "grep status submodule\n"
        return subprocess.CompletedProcess(argv, 0, stdout, "")
    try:
        try:
            original_discovery(
                "git", deadline=1.0, runner=reset_budget_runner,
                clock=lambda: ticks[0])
            per_call_deadline_red = True
        except GitAuthorityError:
            per_call_deadline_red = False
    finally:
        globals()["_remaining_probe_timeout"] = original_remaining_timeout
        _GIT_AUTHORITY_CACHE.clear()
    bad += 0 if per_call_deadline_red else 1
    print("  %s independent-per-call deadline mutation bypasses the shared budget" % (
        "PASS" if per_call_deadline_red else "FAIL"))

    timeout_contract_ok = hook_timeout_contract() == ""
    planted_settings = json.load(open(os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "settings.json"), encoding="utf-8"))
    planted_settings["hooks"]["PreToolUse"][0]["hooks"][0]["timeout"] = 4
    timeout_contract_red = bool(hook_timeout_contract(settings_data=planted_settings))
    budget_contract_red = bool(hook_timeout_contract(budget=4.01))
    for label, ok in (
        ("registered Claude/Codex timeout contract matches", timeout_contract_ok),
        ("registered timeout mutation turns the contract red", timeout_contract_red),
        ("internal budget margin mutation turns the contract red", budget_contract_red),
    ):
        bad += 0 if ok else 1
        print("  %s %s" % ("PASS" if ok else "FAIL", label))

    original_parse_limit = MAX_FUNCTION_DECLARATIONS
    globals()["MAX_FUNCTION_DECLARATIONS"] = original_parse_limit + 1
    try:
        parse_limit_red = decide(_FUNCTION_PARSE_LIMIT_SOURCE)[0] != "ask"
    finally:
        globals()["MAX_FUNCTION_DECLARATIONS"] = original_parse_limit
    bad += 0 if parse_limit_red else 1
    print("  %s function-declaration limit mutation loses bounded-parse ask" % (
        "PASS" if parse_limit_red else "FAIL"))

    original_budget_check = _check_decision_budget
    globals()["_check_decision_budget"] = lambda _deadline: None
    try:
        try:
            split_commands("/bin/echo safe", _deadline=time.monotonic() - 1.0)
            parser_budget_red = True
        except CommandParseError:
            parser_budget_red = False
    finally:
        globals()["_check_decision_budget"] = original_budget_check
    bad += 0 if parser_budget_red else 1
    print("  %s parser-deadline checkpoint mutation accepts an expired budget" % (
        "PASS" if parser_budget_red else "FAIL"))

    # Cost, counted rather than timed, so the check means the same thing on every host and
    # fails fast when it fails. Rescanning the tail per candidate word was quadratic:
    # `echo git git ...` with 20,000 words cost 32 s in one hook process, and 60,000 `=git`
    # words did not finish inside 90 s, both under MAX_TOKENS and both inside a hook
    # registered with a five-second timeout. Four times the tokens must cost about four
    # times the work, not sixteen.
    original_basename = os.path.basename
    basename_counts = []
    for word_count in (1000, 4000):
        counted = [0]

        def counting_basename(path, _counted=counted, _original=original_basename):
            _counted[0] += 1
            return _original(path)

        os.path.basename = counting_basename
        try:
            repeated = [("git", "")] * word_count
            has_literal_guarded_git_tail(repeated)
            has_dynamic_guarded_command_tail(repeated)
        finally:
            os.path.basename = original_basename
        basename_counts.append(counted[0])
    tail_linear_ok = (basename_counts[0] > 0
                      and basename_counts[1] < basename_counts[0] * 8)
    bad += 0 if tail_linear_ok else 1
    print("  %s guarded-tail predicates stay linear (%d -> %d basename reads for 4x "
          "tokens)" % ("PASS" if tail_linear_ok else "FAIL", *basename_counts))

    original_which = shutil.which
    which_names = []

    def counting_which(*args, **kwargs):
        which_names.append(args[0] if args else kwargs.get("cmd"))
        return original_which(*args, **kwargs)

    _EQUALS_LOOKUP_CACHE.clear()
    shutil.which = counting_which
    try:
        unwrap_command_prefix([("=git", "")] * 500 + [("show", "")])
    finally:
        shutil.which = original_which
        _EQUALS_LOOKUP_CACHE.clear()
    equals_cache_ok = len(which_names) == 1
    bad += 0 if equals_cache_ok else 1
    print("  %s a repeated live `=name` costs one PATH walk, not one per word (%d)" % (
        "PASS" if equals_cache_ok else "FAIL", len(which_names)))

    # The arm above proves the checkpoint is REMOVABLE; nothing proved it fires. Replacing
    # `_check_decision_budget`'s body with `return None` left this suite, the sibling
    # guard's and the merged Bash suite all green, which is why the two defects below
    # shipped. These three drive the real checkpoint instead.
    try:
        split_commands("/bin/echo safe", _deadline=time.monotonic() - 1.0)
        parser_budget_live = False
    except CommandParseError:
        parser_budget_live = True
    bad += 0 if parser_budget_live else 1
    print("  %s an expired budget raises from the live parser checkpoint" % (
        "PASS" if parser_budget_live else "FAIL"))

    class _ExpiringClock:
        """A monotonic stand-in that jumps past the deadline after N readings."""

        def __init__(self, readings_before_expiry):
            self.readings_before_expiry = readings_before_expiry
            self.readings = 0

        def monotonic(self):
            self.readings += 1
            return 1000.0 + (
                0.0 if self.readings <= self.readings_before_expiry else 100.0)

    def _decide_with_expiry(command, readings_before_expiry):
        """-> (decision, reason, expiry-actually-fired). An escape is the defect."""
        clock = _ExpiringClock(readings_before_expiry)
        real_time = globals()["time"]
        globals()["time"] = clock
        try:
            decision, reason = decide(command, _deadline=1001.0)
        except BaseException as exc:
            decision, reason = "escaped:" + type(exc).__name__, repr(exc)
        finally:
            globals()["time"] = real_time
        return decision, reason, clock.readings > readings_before_expiry

    # Calibrated against the run itself rather than a literal, so a later refactor that
    # changes how many clock readings a decision takes cannot make these vacuous.
    benign_readings = _decide_with_expiry("/bin/echo safe", 10 ** 9)
    full_benign = _ExpiringClock(10 ** 9)
    real_time_module = globals()["time"]
    globals()["time"] = full_benign
    try:
        decide("/bin/echo safe", _deadline=1001.0)
    finally:
        globals()["time"] = real_time_module
    benign_total = full_benign.readings
    budget_results = [
        _decide_with_expiry("/bin/echo safe", max(1, benign_total * share // 5))
        for share in (1, 2, 3, 4)
    ]
    budget_ask_ok = (benign_total > 4 and benign_readings[0] == "allow"
                     and all(decision == "ask" and fired
                             for decision, _reason, fired in budget_results))
    bad += 0 if budget_ask_ok else 1
    print("  %s budget exhaustion during classification is ask, never deny or escape "
          "(%d readings; %s)" % (
              "PASS" if budget_ask_ok else "FAIL", benign_total,
              ", ".join(result[0] for result in budget_results)))

    hazard_source = "git grep -E 'harness\\b' -- README.md; /bin/echo x"
    full_hazard = _ExpiringClock(10 ** 9)
    globals()["time"] = full_hazard
    try:
        decide(hazard_source, _deadline=1001.0)
    finally:
        globals()["time"] = real_time_module
    deny_kept_ok = any(
        decision == "deny" and fired
        for decision, _reason, fired in (
            _decide_with_expiry(hazard_source, readings)
            for readings in range(1, full_hazard.readings)))
    bad += 0 if deny_kept_ok else 1
    print("  %s an exhausted budget after a proven hazard still denies" % (
        "PASS" if deny_kept_ok else "FAIL"))

    original_split_commands = split_commands
    observed_parser_deadlines = []
    def record_parser_deadline(source, _parse_depth=0, _deadline=None):
        observed_parser_deadlines.append(_deadline)
        return original_split_commands(source, _parse_depth, _deadline)
    globals()["split_commands"] = record_parser_deadline
    try:
        parser_deadline_callsite = True
        for parser_source in (
                "zsh <<'EOF'\n/bin/echo safe\nEOF\n",
                "git -c 'alias.x=!sh -c \"/bin/echo safe\"' x",
        ):
            observed_parser_deadlines.clear()
            parser_deadline_callsite = (
                parser_deadline_callsite
                and decide(parser_source)[0] == "allow"
                and len(observed_parser_deadlines) >= 2
                and observed_parser_deadlines[0] is not None
                and len(set(observed_parser_deadlines)) == 1
            )
    finally:
        globals()["split_commands"] = original_split_commands
    bad += 0 if parser_deadline_callsite else 1
    print("  %s top-level parser receives the shared decision deadline" % (
        "PASS" if parser_deadline_callsite else "FAIL"))

    original_function_operators = _function_list_operators
    observed_operator_deadlines = []
    def record_function_operator_deadline(source, records, deadline=None):
        observed_operator_deadlines.append(deadline)
        return original_function_operators(source, records, deadline)
    globals()["_function_list_operators"] = record_function_operator_deadline
    try:
        function_operator_deadline = (
            decide("f(){ /bin/echo safe; }; f; ( : );")[0] == "allow"
            and bool(observed_operator_deadlines)
            and all(item is not None for item in observed_operator_deadlines)
            and len(set(observed_operator_deadlines)) == 1)
    finally:
        globals()["_function_list_operators"] = original_function_operators
    bad += 0 if function_operator_deadline else 1
    print("  %s function operator scan receives the shared decision deadline" % (
        "PASS" if function_operator_deadline else "FAIL"))

    original_equals_states = zsh_equals_states
    globals()["zsh_equals_states"] = (
        lambda _source, commands, initial=ZSH_EQUALS_ON, deadline=None:
        tuple(ZSH_EQUALS_ON for _command in commands)
    )
    try:
        equals_transition_red = decide(
            "setopt noequals; =git grep -E 'harness\\b' -- README.md"
        )[0] != "ask"
        equals_conditional_red = decide(
            "if true; then setopt equals; fi; "
            "=git grep -E 'harness\\b' -- README.md"
        )[0] != "ask"
        equals_function_red = decide(
            "f(){ setopt noequals; }; f; "
            "=git grep -E 'harness\\b' -- README.md"
        )[0] != "ask"
    finally:
        globals()["zsh_equals_states"] = original_equals_states
    bad += 0 if equals_transition_red else 1
    bad += 0 if equals_conditional_red else 1
    bad += 0 if equals_function_red else 1
    print("  %s EQUALS-state callsite mutation loses noequals uncertainty" % (
        "PASS" if equals_transition_red else "FAIL"))
    print("  %s EQUALS-state callsite mutation loses conditional uncertainty" % (
        "PASS" if equals_conditional_red else "FAIL"))
    print("  %s EQUALS-state callsite mutation loses function uncertainty" % (
        "PASS" if equals_function_red else "FAIL"))

    original_nested_equals = nested_shell_equals_state
    globals()["nested_shell_equals_state"] = (
        lambda _resolution, invocation, _inherited=ZSH_EQUALS_ON:
        ZSH_EQUALS_ON if invocation.shell == "zsh" else ZSH_EQUALS_OFF)
    try:
        nested_option_red = all(decide(source)[0] != "ask" for source in (
            "zsh -o NO_EQUALS -c \"=git grep -E 'harness\\\\b' -- README.md\"",
            "zsh +o EQUALS -c \"=git grep -E 'harness\\\\b' -- README.md\"",
            "zsh -oNO_EQUALS -c \"=git grep -E 'harness\\\\b' -- README.md\"",
            "zsh +oEQUALS -c \"=git grep -E 'harness\\\\b' -- README.md\"",
            "zsh --no-equals -c \"=git grep -E 'harness\\\\b' -- README.md\"",
            "zsh -foNO_EQUALS -c \"=git grep -E 'harness\\\\b' -- README.md\"",
            "zsh +foEQUALS -c \"=git grep -E 'harness\\\\b' -- README.md\"",
            "zsh -coNO_EQUALS \"=git grep -E 'harness\\\\b' -- README.md\"",
        ))
    finally:
        globals()["nested_shell_equals_state"] = original_nested_equals
    bad += 0 if nested_option_red else 1
    print("  %s nested-zsh option-state mutation loses startup uncertainty" % (
        "PASS" if nested_option_red else "FAIL"))

    original_nested_invocation = nested_shell_invocation
    def immediate_post_c_body(resolution, current_shell="sh", deadline=None):
        if (resolution.items
                and os.path.basename(resolution.items[0][0]) == "zsh"):
            args = resolution.items[1:]
            for index, (word, _quoting) in enumerate(args):
                if (word == "-c"
                        or (word.startswith("-") and not word.startswith("--")
                            and "c" in word[1:])):
                    command_arg = (args[index + 1]
                                   if index + 1 < len(args) else ("", ""))
                    return ShellInvocation(
                        "zsh", command_arg[0],
                        source_has_live_unresolved(command_arg[0], deadline),
                        dict(resolution.command_env),
                        _descendant_lookup_authority(resolution))
            return None
        return original_nested_invocation(resolution, current_shell, deadline)
    globals()["nested_shell_invocation"] = immediate_post_c_body
    try:
        post_c_argv_red = all(decide(source)[0] != "deny" for source in (
            "zsh -c --no-equals \"git grep -E 'harness\\\\b' -- README.md\"",
            "zsh -c -o NO_EQUALS \"git grep -E 'harness\\\\b' -- README.md\"",
            "zsh -c -oNO_EQUALS \"git grep -E 'harness\\\\b' -- README.md\"",
        ))
    finally:
        globals()["nested_shell_invocation"] = original_nested_invocation
    bad += 0 if post_c_argv_red else 1
    print("  %s nested-zsh argv callsite mutation loses post-c command bodies" % (
        "PASS" if post_c_argv_red else "FAIL"))

    original_zsh_argv_state = _zsh_argv_state
    def scan_post_operand_options(words, default=ZSH_EQUALS_ON):
        parsed = original_zsh_argv_state(words, default)
        if parsed.command_index is None:
            return parsed
        tail = original_zsh_argv_state(
            [words[0], *words[parsed.command_index + 1:]], parsed.equals_state)
        return ZshArgvState(
            tail.equals_state, parsed.command_index,
            parsed.reads_stdin or tail.reads_stdin)
    globals()["_zsh_argv_state"] = scan_post_operand_options
    try:
        post_operand_red = all(decide(source)[0] != expected
                               for source, expected in (
            ("zsh -c \"=git grep -E 'harness\\\\b' -- README.md\" "
             "--no-equals", "deny"),
            ("zsh -c \"=git grep -P 'harness\\\\b' -- README.md\" "
             "-o NO_EQUALS", "allow"),
            (("zsh -fc '/usr/bin/printf command-only' -s 0<<< "
              "\"git grep -E 'harness\\b' -- README.md\""), "allow"),
        ))
    finally:
        globals()["_zsh_argv_state"] = original_zsh_argv_state
    bad += 0 if post_operand_red else 1
    print("  %s zsh-argv boundary mutation parses positional args as options" % (
        "PASS" if post_operand_red else "FAIL"))

    original_direct_invocation = direct_here_string_invocation
    def force_direct_equals_on(source, current_shell="zsh",
                               equals_state=ZSH_EQUALS_ON, command_env=None,
                               lookup_authority_uncertain=False, deadline=None):
        direct = original_direct_invocation(
            source, current_shell, equals_state, command_env,
            lookup_authority_uncertain, deadline)
        if not direct:
            return None
        resolution, invocation = direct
        return resolution._replace(items=[("zsh", "")]), invocation
    globals()["direct_here_string_invocation"] = force_direct_equals_on
    try:
        here_option_red = all(decide(source)[0] != "ask" for source in (
            "zsh -o NO_EQUALS <<< \"=git grep -E 'harness\\b' -- README.md\"",
            "zsh -foNO_EQUALS 0<<< \"=git grep -E 'harness\\b' -- README.md\"",
        ))
    finally:
        globals()["direct_here_string_invocation"] = original_direct_invocation
    bad += 0 if here_option_red else 1
    print("  %s here-string zsh option-state mutation loses startup uncertainty" % (
        "PASS" if here_option_red else "FAIL"))

    original_heredoc_equals = heredoc_equals_decision
    globals()["heredoc_equals_decision"] = (
        lambda _source, _deadline=None, _subcommands=None, classifier=None,
        **_context: None)
    try:
        heredoc_default_red = all(decide(source)[0] != expected
                                  for source, expected in (
            ("unsetopt equals; zsh <<'EOF'\n"
             "=git grep -E 'harness\\b' -- README.md\nEOF\n", "deny"),
            ("zsh -foNO_EQUALS <<'EOF'\n"
             "=git grep -E 'harness\\b' -- README.md\nEOF\n", "ask"),
        ))
    finally:
        globals()["heredoc_equals_decision"] = original_heredoc_equals
    bad += 0 if heredoc_default_red else 1
    print("  %s heredoc child-state mutation inherits the outer EQUALS option" % (
        "PASS" if heredoc_default_red else "FAIL"))

    original_shell_reads_stdin = _shell_reads_stdin
    def drop_clustered_zsh_option_value(words):
        if (len(words) >= 3 and os.path.basename(words[0]) == "zsh"
                and words[1] in {"-fo", "+fo"}):
            return False
        return original_shell_reads_stdin(words)
    globals()["_shell_reads_stdin"] = drop_clustered_zsh_option_value
    try:
        clustered_stdin_red = decide(
            "zsh -fo NO_EQUALS <<'EOF'\n"
            "git grep -E 'harness\\b' -- README.md\nEOF\n")[0] != "deny"
    finally:
        globals()["_shell_reads_stdin"] = original_shell_reads_stdin
    bad += 0 if clustered_stdin_red else 1
    print("  %s zsh-stdin argv callsite mutation loses clustered option value" % (
        "PASS" if clustered_stdin_red else "FAIL"))

    original_scope_pairs = _function_scope_pairs
    globals()["_function_scope_pairs"] = (
        lambda _source, _records, deadline=None: ())
    try:
        scope_equals_red = decide(
            "(unsetopt equals); =git grep -E 'harness\\b' -- README.md"
        )[0] != "deny"
    finally:
        globals()["_function_scope_pairs"] = original_scope_pairs
    bad += 0 if scope_equals_red else 1
    print("  %s EQUALS scope mutation leaks a subshell option change" % (
        "PASS" if scope_equals_red else "FAIL"))

    original_outer_equals = _resolve_outer_zsh_equals
    globals()["_resolve_outer_zsh_equals"] = (
        lambda tokens, _shell, _state, _env, _lookup: list(tokens))
    try:
        outer_equals_red = (
            decide("env -i =git grep -E 'harness\\b' -- README.md")[0]
            != "deny"
            and decide("env -i =git grep -P 'harness\\b' -- README.md")[0]
            != "allow")
    finally:
        globals()["_resolve_outer_zsh_equals"] = original_outer_equals
    bad += 0 if outer_equals_red else 1
    print("  %s outer EQUALS pre-resolution mutation transfers wrapper authority" % (
        "PASS" if outer_equals_red else "FAIL"))

    original_strongest = _strongest_decision
    globals()["_strongest_decision"] = (
        lambda decisions: min(
            decisions, key=lambda item: {"allow": 0, "ask": 1, "deny": 2}[item[0]]))
    try:
        precedence_red = all(decide(source)[0] != "deny" for source in (
            "sh <<'A'\n=git grep -E 'harness\\b' -- README.md\nA\n"
            "zsh <<'B'\n=git grep -E 'harness\\b' -- README.md\nB\n",
            "zsh <<'A'\n=git grep -E 'harness\\b' -- README.md\nA\n"
            "sh <<'B'\n=git grep -E 'harness\\b' -- README.md\nB\n",
            ("sh -c \"=git grep -E 'harness\\\\b' -- README.md\"; "
             "=git grep -E 'harness\\b' -- README.md"),
            ("=git grep -E 'harness\\b' -- README.md; "
             "sh -c \"=git grep -E 'harness\\\\b' -- README.md\""),
            ("sh <<'EOF'\n=git grep -E 'harness\\b' -- README.md\nEOF\n"
             "git grep -E 'harness\\b' -- README.md"),
            ("git grep -E 'harness\\b' -- README.md\n"
             "sh <<'EOF'\n=git grep -E 'harness\\b' -- README.md\nEOF\n"),
        ))
    finally:
        globals()["_strongest_decision"] = original_strongest
    bad += 0 if precedence_red else 1
    print("  %s decision-reducer mutation lets a question mask a deny" % (
        "PASS" if precedence_red else "FAIL"))

    original_stdin_reducer = _reduce_stdin_provenance
    globals()["_reduce_stdin_provenance"] = lambda findings: findings[0]
    try:
        here_string_precedence_red = decide(
            "sh 0<<< \"=git grep -E 'harness\\b' -- README.md\"; "
            "zsh 0<<< \"=git grep -E 'harness\\b' -- README.md\""
        )[0] != "deny"
    finally:
        globals()["_reduce_stdin_provenance"] = original_stdin_reducer
    bad += 0 if here_string_precedence_red else 1
    print("  %s stdin-reducer mutation lets a here-string question mask a deny" % (
        "PASS" if here_string_precedence_red else "FAIL"))

    ambient_occurrence = lambda _finding, command_env=None, \
        lookup_authority_uncertain=False, deadline=None: (
            dict(os.environ if command_env is None else command_env),
            bool(lookup_authority_uncertain))
    original_heredoc_occurrence = _heredoc_occurrence_environment
    globals()["_heredoc_occurrence_environment"] = ambient_occurrence
    try:
        heredoc_occurrence_red = decide(
            "PATH=/usr/bin\nzsh <<'EOF'\n"
            "=git grep -P 'harness\\b' -- README.md\nEOF\n")[0] != "ask"
    finally:
        globals()["_heredoc_occurrence_environment"] = original_heredoc_occurrence
    bad += 0 if heredoc_occurrence_red else 1
    print("  %s heredoc-occurrence mutation drops prior-line PATH authority" % (
        "PASS" if heredoc_occurrence_red else "FAIL"))

    original_expansion_occurrence = _heredoc_expansion_environment
    globals()["_heredoc_expansion_environment"] = ambient_occurrence
    try:
        expansion_occurrence_red = decide(
            "PATH=/usr/bin; cat <<EOF\n"
            "$(=git grep -P 'harness\\b' -- README.md)\nEOF\n")[0] != "ask"
    finally:
        globals()["_heredoc_expansion_environment"] = original_expansion_occurrence
    bad += 0 if expansion_occurrence_red else 1
    print("  %s heredoc-expansion mutation drops prior PATH authority" % (
        "PASS" if expansion_occurrence_red else "FAIL"))

    original_here_occurrence = _here_string_occurrence_environment
    globals()["_here_string_occurrence_environment"] = (
        lambda _source, _fragment, command_env=None,
        lookup_authority_uncertain=False, deadline=None: (
            dict(os.environ if command_env is None else command_env),
            bool(lookup_authority_uncertain)))
    try:
        here_occurrence_red = decide(
            "PATH=/usr/bin\nzsh 0<<< \"=git grep -P 'harness\\b' -- README.md\""
        )[0] != "ask"
    finally:
        globals()["_here_string_occurrence_environment"] = original_here_occurrence
    bad += 0 if here_occurrence_red else 1
    print("  %s here-string occurrence mutation drops prior-line PATH authority" % (
        "PASS" if here_occurrence_red else "FAIL"))

    original_occurrence_index = _marked_occurrence_command_index
    def choose_last_occurrence(source, deadline=None):
        commands = split_commands(source, _deadline=deadline)
        if not commands:
            raise CommandParseError("mutated occurrence source has no command")
        return len(commands) - 1
    globals()["_marked_occurrence_command_index"] = choose_last_occurrence
    try:
        future_occurrence_red = all(decide(source)[0] != "allow" for source in (
            ("zsh 0<<< \"=git grep -P 'harness\\b' -- README.md\"; "
             "PATH=/usr/bin; /bin/echo done"),
            ("zsh 0<<< \"=git grep -P 'harness\\b' -- README.md\"; "
             "unset PATH; /bin/echo done"),
            ("cat <<EOF; PATH=/usr/bin; /bin/echo done\n"
             "$(=git grep -P 'harness\\b' -- README.md)\nEOF\n"),
        ))
    finally:
        globals()["_marked_occurrence_command_index"] = original_occurrence_index
    bad += 0 if future_occurrence_red else 1
    print("  %s occurrence-index mutation lets future PATH state flow backward" % (
        "PASS" if future_occurrence_red else "FAIL"))

    original_ordinary_source = command_without_heredoc_payloads
    globals()["command_without_heredoc_payloads"] = (
        lambda source, deadline=None: "" if "<<'EOF'" in source
        else original_ordinary_source(source, deadline))
    try:
        heredoc_composition_red = all(decide(source)[0] != "deny" for source in (
            ("sh <<'EOF'\n=git grep -E 'harness\\b' -- README.md\nEOF\n"
             "git grep -E 'harness\\b' -- README.md"),
            ("git grep -E 'harness\\b' -- README.md\n"
             "sh <<'EOF'\n=git grep -E 'harness\\b' -- README.md\nEOF\n"),
        ))
    finally:
        globals()["command_without_heredoc_payloads"] = original_ordinary_source
    bad += 0 if heredoc_composition_red else 1
    print("  %s heredoc-composition mutation skips ordinary-command denial" % (
        "PASS" if heredoc_composition_red else "FAIL"))

    globals()["authorize_git_subcommand"] = (
        lambda subcommand, authority, effective_exec_path:
        None if subcommand == "submodule"
        else original_authorize(subcommand, authority, effective_exec_path)
    )
    try:
        env_exec_red = decide(
            "GIT_EXEC_PATH=/tmp/untrusted git submodule status")[0] != "ask"
        option_exec_red = decide(
            "git --exec-path=/tmp/untrusted submodule status")[0] != "ask"
    finally:
        globals()["authorize_git_subcommand"] = original_authorize
    bad += 0 if env_exec_red else 1
    bad += 0 if option_exec_red else 1
    print("  %s GIT_EXEC_PATH authority mutation loses external-command ask" % (
        "PASS" if env_exec_red else "FAIL"))
    print("  %s --exec-path authority mutation loses external-command ask" % (
        "PASS" if option_exec_red else "FAIL"))

    globals()["AMBIENT_ENGINE_REQUIRES_EXPLICIT"] = False
    try:
        ambient_engine_red = decide(
            r"git grep 'harness\b' -- README.md")[0] != "ask"
    finally:
        globals()["AMBIENT_ENGINE_REQUIRES_EXPLICIT"] = True
    bad += 0 if ambient_engine_red else 1
    print("  %s implicit-engine classification mutation loses ambient-config ask" % (
        "PASS" if ambient_engine_red else "FAIL"))

    original_functions = extract_function_invocations
    globals()["extract_function_invocations"] = (
        lambda source, deadline=None: (source, ()))
    try:
        declaration_red = all(decide(source)[0] != "allow" for source in (
            r'''scan() { git grep -E 'harness\b' -- README.md; }; /bin/echo safe''',
            r'''scan() ( git grep -E 'harness\b' -- README.md ); /bin/echo safe''',
            r'''scan() { git grep -E 'harness\b' -- README.md; }; /bin/echo scan''',
        ))
        declaration_red = declaration_red and decide(
            r'''scan() { git grep -E 'harness\b' -- README.md; }; time -p scan'''
        )[0] != "ask"
    finally:
        globals()["extract_function_invocations"] = original_functions
    bad += 0 if declaration_red else 1
    print("  %s declaration-time execution mutation loses harmless declaration control" % (
        "PASS" if declaration_red else "FAIL"))

    def drop_function_invocations(source, deadline=None):
        cleaned, _sources = original_functions(source, deadline)
        return cleaned, ()
    globals()["extract_function_invocations"] = drop_function_invocations
    try:
        invocation_red = all(decide(source)[0] != "deny" for source in (
            r'''scan() { git grep -E 'harness\b' -- README.md; }; scan''',
            r'''scan() { git grep -E 'harness\b' -- README.md; }; ! scan''',
            r'''scan() ( git grep -E 'harness\b' -- README.md ); scan''',
        ))
    finally:
        globals()["extract_function_invocations"] = original_functions
    bad += 0 if invocation_red else 1
    print("  %s disabled function-invocation traversal loses nested deny" % (
        "PASS" if invocation_red else "FAIL"))

    original_function_records = function_declaration_records
    def collapse_function_versions(source, deadline=None):
        records = original_function_records(source, deadline)
        last_body = {record.name: record.body for record in records}
        return tuple(FunctionDeclaration(
            record.start, record.end, record.name, last_body[record.name],
            record.scope_start, record.scope_end, record.conditional,
            record.maybe, record.pipeline_start, record.pipeline_end,
        ) for record in records)
    globals()["function_declaration_records"] = collapse_function_versions
    try:
        collapse_red = decide(
            r'''scan(){ git grep -E 'harness\b' -- README.md; }; scan; '''
            r'''scan(){ /bin/echo safe; }; scan''')[0] != "deny"
        collapse_red = collapse_red and decide(
            r'''scan(){ /bin/echo safe; }; scan; '''
            r'''scan(){ git grep -E 'harness\b' -- README.md; }; /bin/echo done'''
        )[0] != "allow"
    finally:
        globals()["function_declaration_records"] = original_function_records
    bad += 0 if collapse_red else 1
    print("  %s global-definition collapse mutation loses temporal function outcomes" % (
        "PASS" if collapse_red else "FAIL"))

    original_annotation = annotate_function_declarations
    def ignore_conditional_reachability(source, records, deadline=None):
        return tuple(record._replace(conditional=False)
                     for record in original_annotation(source, records, deadline))
    globals()["annotate_function_declarations"] = ignore_conditional_reachability
    try:
        conditional_red = decide(
            r'''if false; then scan(){ git grep -E 'harness\b' -- README.md; }; '''
            r'''fi; scan''')[0] != "ask"
    finally:
        globals()["annotate_function_declarations"] = original_annotation
    bad += 0 if conditional_red else 1
    print("  %s conditional-reachability mutation loses uncertain call outcome" % (
        "PASS" if conditional_red else "FAIL"))

    def globalize_function_scope(source, records, deadline=None):
        return tuple(record._replace(scope_start=-1, scope_end=len(source))
                     for record in original_annotation(source, records, deadline))
    globals()["annotate_function_declarations"] = globalize_function_scope
    try:
        scope_red = decide(
            r'''scan(){ git grep -E 'harness\b' -- README.md; }; '''
            r'''(scan(){ /bin/echo safe; }); scan''')[0] != "deny"
        scope_red = scope_red and decide(
            r'''scan(){ /bin/echo safe; }; '''
            r'''(scan(){ git grep -E 'harness\b' -- README.md; }); scan'''
        )[0] != "allow"
    finally:
        globals()["annotate_function_declarations"] = original_annotation
    bad += 0 if scope_red else 1
    print("  %s subshell-scope mutation loses both outer-definition controls" % (
        "PASS" if scope_red else "FAIL"))

    def globalize_maybe_definitions(source, records, deadline=None):
        return tuple(record._replace(maybe=False)
                     for record in original_annotation(source, records, deadline))
    globals()["annotate_function_declarations"] = globalize_maybe_definitions
    try:
        maybe_red = all(decide(source)[0] != "ask" for source in (
            r'''scan(){ git grep -E 'harness\b' -- README.md; }; true && '''
            r'''scan(){ /bin/echo safe; }; scan''',
            r'''scan(){ /bin/echo safe; }; true && '''
            r'''scan(){ git grep -E 'harness\b' -- README.md; }; scan''',
            r'''scan(){ git grep -E 'harness\b' -- README.md; }; false || '''
            r'''scan(){ /bin/echo safe; }; scan''',
            r'''scan(){ /bin/echo safe; }; false || '''
            r'''scan(){ git grep -E 'harness\b' -- README.md; }; scan''',
        ))
    finally:
        globals()["annotate_function_declarations"] = original_annotation
    bad += 0 if maybe_red else 1
    print("  %s short-circuit-state mutation loses all maybe-definition asks" % (
        "PASS" if maybe_red else "FAIL"))

    def globalize_pipeline_definitions(source, records, deadline=None):
        return tuple(record._replace(pipeline_start=-1, pipeline_end=-1)
                     for record in original_annotation(source, records, deadline))
    globals()["annotate_function_declarations"] = globalize_pipeline_definitions
    try:
        pipeline_scope_red = decide(
            r'''scan(){ git grep -E 'harness\b' -- README.md; }; '''
            r'''{ scan(){ /bin/echo safe; }; /bin/echo component; } '''
            r'''| /bin/cat; scan''')[0] != "deny"
        pipeline_scope_red = pipeline_scope_red and decide(
            r'''scan(){ /bin/echo safe; }; '''
            r'''{ scan(){ git grep -E 'harness\b' -- README.md; }; '''
            r'''/bin/echo component; } | /bin/cat; scan'''
        )[0] != "allow"
    finally:
        globals()["annotate_function_declarations"] = original_annotation
    bad += 0 if pipeline_scope_red else 1
    print("  %s pipeline-child mutation loses both outer-definition controls" % (
        "PASS" if pipeline_scope_red else "FAIL"))

    original_marked_stdin = _marked_stdin_command
    globals()["_marked_stdin_command"] = (
        lambda _line, _start, _end, _deadline=None: None)
    try:
        leading_stdin_red = decide(
            r'''(sh) <<< "git grep -E 'harness\b' -- README.md"''')[0] != "deny"
    finally:
        globals()["_marked_stdin_command"] = original_marked_stdin
    bad += 0 if leading_stdin_red else 1
    print("  %s grouped-shell association mutation loses recursive deny" % (
        "PASS" if leading_stdin_red else "FAIL"))

    original_association = associated_stdin_consumer
    globals()["associated_stdin_consumer"] = (
        lambda _line, _start, _end, _deadline=None:
        StdinConsumer(False, False, ""))
    try:
        compound_stdin_red = decide(
            r'''{ /bin/echo prep; sh; } <<< "git grep -E 'harness\b' -- README.md"'''
        )[0] != "ask"
    finally:
        globals()["associated_stdin_consumer"] = original_association
    bad += 0 if compound_stdin_red else 1
    print("  %s command-graph reachability mutation loses compound stdin ask" % (
        "PASS" if compound_stdin_red else "FAIL"))

    original_file_inputs = live_file_input_sources
    globals()["live_file_input_sources"] = lambda _source: ()
    try:
        file_input_red = decide(r'''0<"$SCRIPT" sh''')[0] != "ask"
    finally:
        globals()["live_file_input_sources"] = original_file_inputs
    bad += 0 if file_input_red else 1
    print("  %s fd-zero file-input callsite mutation loses dynamic-source ask" % (
        "PASS" if file_input_red else "FAIL"))

    globals()["associated_stdin_consumer"] = (
        lambda _line, _start, _end, _deadline=None:
        StdinConsumer(True, False, "sh"))
    try:
        cartesian_red = decide(
            r'''/bin/cat <<< "git grep -E 'harness\b' -- README.md"; '''
            r'''sh </dev/null''')[0] != "allow"
    finally:
        globals()["associated_stdin_consumer"] = original_association
    bad += 0 if cartesian_red else 1
    print("  %s global-source association mutation loses inert cross-command allow" % (
        "PASS" if cartesian_red else "FAIL"))

    original_here_classifier = classify_direct_here_string
    globals()["classify_direct_here_string"] = (
        lambda _source, _depth, _deadline, _resolution, _invocation,
        _equals_state: StdinProvenance(
            "ask", "planted unconditional ask"))
    try:
        unconditional_here_red = decide(
            r'''sh 0<<< "/bin/echo safe"''')[0] != "allow"
    finally:
        globals()["classify_direct_here_string"] = original_here_classifier
    bad += 0 if unconditional_here_red else 1
    print("  %s unconditional here-string mutation loses harmless static allow" % (
        "PASS" if unconditional_here_red else "FAIL"))

    globals()["classify_direct_here_string"] = (
        lambda _source, _depth, _deadline, _resolution, _invocation,
        _equals_state: None)
    try:
        here_recursion_red = decide(
            r'''sh <<< "git grep -E 'harness\b' -- README.md"''')[0] != "deny"
    finally:
        globals()["classify_direct_here_string"] = original_here_classifier
    bad += 0 if here_recursion_red else 1
    print("  %s here-string recursion mutation loses guarded nested deny" % (
        "PASS" if here_recursion_red else "FAIL"))

    original_direct_invocation = direct_here_string_invocation
    def force_direct_zsh(source, current_shell="zsh",
                         equals_state=ZSH_EQUALS_ON, command_env=None,
                         lookup_authority_uncertain=False, deadline=None):
        direct = original_direct_invocation(
            source, current_shell, equals_state, command_env,
            lookup_authority_uncertain, deadline)
        if not direct:
            return None
        resolution, invocation = direct
        return (resolution._replace(items=[("zsh", "")]),
                invocation._replace(shell="zsh"))
    globals()["direct_here_string_invocation"] = force_direct_zsh
    try:
        here_shell_red = decide(
            r'''sh <<< "=git grep -E 'harness\b' -- README.md"''')[0] != "ask"
    finally:
        globals()["direct_here_string_invocation"] = original_direct_invocation
    bad += 0 if here_shell_red else 1
    print("  %s here-string shell-identity mutation misclassifies sh EQUALS syntax" % (
        "PASS" if here_shell_red else "FAIL"))

    original_heredoc_decision = heredoc_equals_decision
    def force_zsh_heredoc_identity(
            source, deadline=None, subcommands=None, classifier=None,
            **context):
        forced = (None if classifier is None else
                  lambda body, _shell, state, inner_deadline, env, lookup:
                  classifier(body, "zsh", ZSH_EQUALS_ON, inner_deadline,
                             env, lookup))
        return original_heredoc_decision(
            source, deadline, subcommands, forced, **context)
    globals()["heredoc_equals_decision"] = force_zsh_heredoc_identity
    try:
        heredoc_shell_red = decide(
            "sh <<'EOF'\n=git grep -E 'harness\\b' -- README.md\nEOF\n"
        )[0] != "ask"
    finally:
        globals()["heredoc_equals_decision"] = original_heredoc_decision
    bad += 0 if heredoc_shell_red else 1
    print("  %s heredoc shell-identity mutation misclassifies sh EQUALS syntax" % (
        "PASS" if heredoc_shell_red else "FAIL"))

    original_find_heredoc = _find_heredoc_operator
    def confuse_redirection_context(line):
        if "<<<" in line:
            return line.index("<<<"), False
        if "<<" in line:
            return line.index("<<"), False
        return original_find_heredoc(line)
    globals()["_find_heredoc_operator"] = confuse_redirection_context
    try:
        here_string_red = decide(
            r'''/bin/cat <<< "git grep -E 'harness\b' -- README.md"''')[0] != "allow"
        shift_red = all(decide(source)[0] != "allow" for source in (
            r'''/bin/echo "$(( 1 << 2 ))"''',
            r'''(( value = 1 << 2 ))''',
            r'''for ((i = 1; i << 2; i++)); do /bin/echo "$i"; done''',
        ))
    finally:
        globals()["_find_heredoc_operator"] = original_find_heredoc
    bad += 0 if here_string_red and shift_red else 1
    print("  %s redirection-context mutation misclassifies here-string and shift" % (
        "PASS" if here_string_red and shift_red else "FAIL"))

    original_backtick = _backtick_substitution
    def drop_backtick_body(source, start):
        _body, end = original_backtick(source, start)
        return "", end
    globals()["_backtick_substitution"] = drop_backtick_body
    try:
        backtick_command = "/bin/echo " + chr(96) + (
            "git grep -E 'harness\\b' -- README.md") + chr(96)
        backtick_red = decide(backtick_command)[0] != "deny"
    finally:
        globals()["_backtick_substitution"] = original_backtick
    bad += 0 if backtick_red else 1
    print("  %s backtick callsite mutation loses nested deny" % (
        "PASS" if backtick_red else "FAIL"))

    original_heredoc = extract_heredoc_sources
    def drop_heredoc_body(source, deadline=None, equals_findings=None,
                          equals_subcommands=None, shell_findings=None,
                          expansion_findings=None,
                          classify_non_direct_shell_bodies=False):
        cleaned, _bodies = original_heredoc(
            source, deadline, equals_findings, equals_subcommands, None)
        return cleaned, ()
    globals()["extract_heredoc_sources"] = drop_heredoc_body
    try:
        heredoc_red = decide(
            "sh <<'EOF'\ngit grep -E 'harness\\b' -- README.md\nEOF\n"
        )[0] != "deny"
    finally:
        globals()["extract_heredoc_sources"] = original_heredoc
    bad += 0 if heredoc_red else 1
    print("  %s executable-heredoc callsite mutation loses nested deny" % (
        "PASS" if heredoc_red else "FAIL"))

    def keep_winning_heredoc_only(source, deadline=None, equals_findings=None,
                                  equals_subcommands=None, shell_findings=None,
                                  expansion_findings=None,
                                  classify_non_direct_shell_bodies=False):
        expansion_start = (len(expansion_findings)
                           if expansion_findings is not None else 0)
        cleaned, bodies = original_heredoc(
            source, deadline, equals_findings, equals_subcommands,
            shell_findings, expansion_findings,
            classify_non_direct_shell_bodies)
        if "<<A <<'B'" in source:
            if expansion_findings is not None:
                del expansion_findings[expansion_start:]
            return cleaned, ()
        return cleaned, bodies
    globals()["extract_heredoc_sources"] = keep_winning_heredoc_only
    try:
        winner_red = decide(
            "cat <<A <<'B'\n$(git grep -E 'harness\\b' -- README.md)\nA\n"
            "literal\nB\n"
        )[0] != "deny"
    finally:
        globals()["extract_heredoc_sources"] = original_heredoc
    bad += 0 if winner_red else 1
    print("  %s winner-only heredoc mutation loses nonwinning-body expansion deny" % (
        "PASS" if winner_red else "FAIL"))

    original_header_shell = _header_stdin_shell
    globals()["_header_stdin_shell"] = (
        lambda _header, _suffix="", deadline=None: "")
    try:
        heredoc_path_red = decide(
            "sh 0<<'EOF'\ngit grep -E 'harness\\b' -- README.md\nEOF\n"
        )[0] != "deny"
    finally:
        globals()["_header_stdin_shell"] = original_header_shell
    bad += 0 if heredoc_path_red else 1
    print("  %s heredoc execution-header mutation loses descriptor-zero deny" % (
        "PASS" if heredoc_path_red else "FAIL"))

    original_fallback = conservative_allow_uncertainty
    globals()["conservative_allow_uncertainty"] = (
        lambda _source, _deadline=None: None)
    try:
        fallback_red = decide(
            r'''launcher /bin/sh 0<<< "git grep -E 'harness\b' -- README.md"'''
        )[0] != "ask"
    finally:
        globals()["conservative_allow_uncertainty"] = original_fallback
    bad += 0 if fallback_red else 1
    print("  %s conservative allow-fallback mutation loses obscured-input ask" % (
        "PASS" if fallback_red else "FAIL"))

    original_delimiter = _parse_heredoc_delimiter_word
    def identifier_delimiter_only(line, start):
        delimiter, quoted, end = original_delimiter(line, start)
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", delimiter):
            raise CommandParseError("legacy identifier-only heredoc delimiter")
        return delimiter, quoted, end
    globals()["_parse_heredoc_delimiter_word"] = identifier_delimiter_only
    try:
        dashed_heredoc_red = decide(
            "sh <<'END-MARK'\ngit grep -E 'harness\\b' -- README.md\nEND-MARK\n"
        )[0] != "deny"
    finally:
        globals()["_parse_heredoc_delimiter_word"] = original_delimiter
    bad += 0 if dashed_heredoc_red else 1
    print("  %s identifier-only heredoc mutation loses dashed-delimiter deny" % (
        "PASS" if dashed_heredoc_red else "FAIL"))

    checks = len(FIXTURES) + 74
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
