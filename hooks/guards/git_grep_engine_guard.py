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


class CommandParseError(ValueError):
    """The Bash source cannot be tokenized within the guard's closed limits."""


class GitAuthorityError(RuntimeError):
    """The executing trusted Git could not supply its command authority inventory."""


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
    # False when the command names a Git other than the one PATH resolves. The inventories
    # still come from the trusted Git -- the named binary is never executed to enumerate
    # its own -- so only builtins may be classified from them while this is False.
    candidate_trusted: bool = True


class HereStringSource(NamedTuple):
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


class StdinProvenance(NamedTuple):
    decision: str
    reason: str


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


def _shell_reads_stdin(words):
    """Whether a directly named shell consumes commands from standard input."""
    if not words or os.path.basename(words[0]) not in SHELLS:
        return False
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


def _header_executes_shell(header, suffix=""):
    """Whether a heredoc feeds a named shell; None means the consumer is uncertain."""
    try:
        header_commands = split_commands(header)
    except CommandParseError:
        return None
    if not header_commands:
        return False
    header_resolution = unwrap_command_prefix(header_commands[-1])
    if header_resolution.errors:
        return None
    words = [word for word, _quoting in header_resolution.items]
    if _shell_reads_stdin(words):
        return True
    # A literal pipeline into a shell also executes the heredoc bytes. This recognizes
    # the direct bounded form; arbitrary filters and compound redirections remain outside
    # the tokenizer contract and therefore must not be described as comprehensively parsed.
    if suffix:
        try:
            downstream_commands = split_commands(suffix)
        except CommandParseError:
            return None
        if downstream_commands:
            downstream_resolution = unwrap_command_prefix(downstream_commands[-1])
            if downstream_resolution.errors:
                return None
            candidate = [word for word, _quoting in downstream_resolution.items]
            return _shell_reads_stdin(candidate)
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


def extract_heredoc_sources(cmd):
    """Remove heredoc payloads from argv text and return executable shell bodies."""
    bodies = []
    cleaned = []
    cursor = 0
    while cursor < len(cmd):
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
        part_start = 0
        for redirect_start, word_end, *_rest in redirects:
            header_parts.append(header_line[part_start:redirect_start])
            header_parts.append(" ")
            part_start = word_end
        header_parts.append(header_line[part_start:])
        clean_header = "".join(header_parts)
        executes_shell = _header_executes_shell(clean_header)
        body_start = header_end + 1
        for _start, _end, delimiter, quoted, strip_tabs, feeds_stdin in redirects:
            scan = body_start
            body_end = None
            terminator_end = None
            while scan <= len(cmd):
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
            if (feeds_stdin and executes_shell is None
                    and source_has_git_hazard_hint(body)):
                raise CommandParseError(
                    "heredoc has guarded source and an unresolved stdin consumer")
            if feeds_stdin and executes_shell is True:
                bodies.append(body)
            if not quoted:
                bodies.extend(_heredoc_expansion_sources(body))
            body_start = terminator_end
        cleaned.append(clean_header + "\n")
        cursor = body_start
    return "".join(cleaned), tuple(bodies)


def _function_scope_pairs(cmd, records):
    """Return ordinary subshell/command-source pairs outside declaration bodies."""
    by_start = {record.start: record for record in records}
    pairs = []
    stack = []
    quote = ""
    arithmetic_depth = 0
    index = 0
    while index < len(cmd):
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


def _conditional_function_intervals(cmd, records):
    masked = list(cmd)
    for record in records:
        masked[record.start:record.end] = " " * (record.end - record.start)
    quote = ""
    index = 0
    while index < len(masked):
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


def _function_list_operators(cmd, records, pairs):
    """Return live list/pipeline operators with their lexical subshell scope."""
    by_start = {record.start: record for record in records}
    operators = []
    record_braces = {}
    brace_stack = []
    quote = ""
    arithmetic_depth = 0
    index = 0
    while index < len(cmd):
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
        containers = [pair for pair in pairs if pair[0] < index < pair[1]]
        scope_start = (-1 if not containers else min(
            containers, key=lambda pair: pair[1] - pair[0])[0])
        operators.append((index, width, operator, scope_start,
                          tuple(brace_stack)))
        index += width
    return tuple(operators), record_braces


def annotate_function_declarations(cmd, records):
    """Attach lexical subshell scope and conditional reachability to declarations."""
    pairs = _function_scope_pairs(cmd, records)
    intervals = _conditional_function_intervals(cmd, records)
    operators, record_braces = _function_list_operators(cmd, records, pairs)
    annotated = []
    for record in records:
        containers = [pair for pair in pairs
                      if pair[0] < record.start < pair[1]]
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
            same_context = [operator for operator in operators
                            if operator[3] == scope_start
                            and operator[4] == context]
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


def function_declaration_records(cmd):
    """Return live function declarations with temporal reachability and scope."""
    if "()" not in cmd and "function " not in cmd:
        return ()
    pattern = re.compile(
        r"(?ms)(?:(?:function[ \t]+)([A-Za-z_][A-Za-z0-9_]*)(?:\s*\(\s*\))?"
        r"|([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*\))\s*([({])")
    live = [True] * len(cmd)
    quote = ""
    index = 0
    while index < len(cmd):
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
        if match.start() < cursor:
            continue
        if not live[match.start()]:
            continue
        opener = match.group(3)
        closer = "}" if opener == "{" else ")"
        depth, quote, index = 1, "", match.end()
        while index < len(cmd) and depth:
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
        records.append(FunctionDeclaration(
            match.start(), index, match.group(1) or match.group(2),
            cmd[match.end():index - 1], -1, len(cmd), False, False, -1, -1,
        ))
        cursor = index
    return annotate_function_declarations(cmd, tuple(records))


def _invoked_function_bodies(source, declarations, uncertain=()):
    if not declarations and not uncertain:
        return ()
    if source_has_dynamic_command_word(source):
        raise CommandParseError(
            "a dynamic command word may invoke a declared function")
    invoked = []
    for tokens in split_commands(source):
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
                             pipeline_scope=None):
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
        if position < cursor:
            continue
        segment = cmd[cursor:position]
        cleaned.append(segment)
        invoked.extend(_invoked_function_bodies(
            segment, declarations, uncertain))
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
                declarations, uncertain, (child_start, child_end),
            )
            cleaned.append(child_cleaned)
            invoked.extend(child_invoked)
            cursor = child_end
            continue
        child_cleaned, child_invoked = _extract_function_region(
            cmd, records, child_start + 1, child_end, child_start,
            declarations, uncertain, None,
        )
        cleaned.extend((cmd[child_start:child_start + 1], child_cleaned,
                        cmd[child_end:child_end + 1]))
        invoked.extend(child_invoked)
        cursor = child_end + 1
    tail = cmd[cursor:end]
    cleaned.append(tail)
    invoked.extend(_invoked_function_bodies(tail, declarations, uncertain))
    return "".join(cleaned), tuple(invoked)


def extract_function_invocations(cmd):
    """Follow calls against definitions live at that point and in that shell scope."""
    records = function_declaration_records(cmd)
    if not records:
        return cmd, ()
    return _extract_function_region(
        cmd, records, 0, len(cmd), -1, {}, set(), None)


def split_commands(cmd, _parse_depth=0):
    """Split on UNQUOTED && || ; | newline ( ) and yield token lists.

    Tokens are (text, quoting) where quoting is one of '', "'", '"'.
    Command substitutions are recursively inspected even inside double quotes. Heredoc
    bodies are inspected only when stdin is executed by a named shell interpreter.
    """
    if not isinstance(cmd, str):
        raise CommandParseError("command source is not text")
    if _parse_depth > MAX_SOURCE_DEPTH:
        raise CommandParseError(
            f"executable source nesting exceeds depth {MAX_SOURCE_DEPTH}")
    if len(cmd) > MAX_COMMAND_CHARS:
        raise CommandParseError(
            f"command source exceeds the {MAX_COMMAND_CHARS}-byte parse limit")
    cmd, function_sources = extract_function_invocations(cmd)
    cmd, heredoc_sources = extract_heredoc_sources(cmd)
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
        c = cmd[i]
        if q:
            if q == '"' and cmd.startswith("${", i):
                text, i, sources = _parameter_expansion(cmd, i)
                for source in sources:
                    embedded.extend(split_commands(source, _parse_depth + 1))
                append_tok(text, q)
                continue
            if q == '"' and cmd.startswith("$((", i):
                _body, i, sources = _arithmetic_expansion(cmd, i)
                for source in sources:
                    embedded.extend(split_commands(source, _parse_depth + 1))
                append_tok("$((__ARITH__))", q)
                continue
            if q == '"' and cmd.startswith("$(", i):
                body, i = _command_substitution(cmd, i)
                embedded.extend(split_commands(body, _parse_depth + 1))
                append_tok("$(__COMMAND__)", q)
                continue
            if q == '"' and c == "`":
                body, i = _backtick_substitution(cmd, i)
                embedded.extend(split_commands(body, _parse_depth + 1))
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
                embedded.extend(split_commands(source, _parse_depth + 1))
            append_tok("$((__ARITH__))")
            continue
        if cmd.startswith("$(", i):
            body, i = _command_substitution(cmd, i)
            embedded.extend(split_commands(body, _parse_depth + 1))
            append_tok("$(__COMMAND__)")
            continue
        if cmd.startswith("${", i):
            text, i, sources = _parameter_expansion(cmd, i)
            for source in sources:
                embedded.extend(split_commands(source, _parse_depth + 1))
            append_tok(text)
            continue
        if c == "`":
            body, i = _backtick_substitution(cmd, i)
            embedded.extend(split_commands(body, _parse_depth + 1))
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
        embedded.extend(split_commands(source, _parse_depth + 1))
    for source in function_sources:
        embedded.extend(split_commands(source, _parse_depth + 1))
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


def trusted_git_authority(executable="git"):
    """Bind builtin/main command inventories to one resolved Git and exec path.

    A command naming a Git other than the one PATH resolves is uncertainty, not a hazard.
    Stock macOS carries two real Git binaries -- Homebrew's and Apple's /usr/bin/git --
    and refusing the second denied `/usr/bin/git status`, which carries neither guarded
    hazard. The named binary is still never executed to read its inventories, because the
    command chose that path; the authority is returned with `candidate_trusted=False`
    instead and `authorize_git_subcommand` narrows to builtins.
    """
    trusted = shutil.which("git")
    candidate = (shutil.which(executable) if os.sep not in executable else executable)
    if not trusted or not candidate:
        raise GitAuthorityError("the Git executable cannot be resolved")
    trusted = os.path.realpath(trusted)
    candidate = os.path.realpath(candidate)
    if trusted not in _GIT_AUTHORITY_CACHE:
        try:
            exec_path_result = subprocess.run(
                [trusted, "--exec-path"], capture_output=True, text=True, timeout=10,
            )
            builtins_result = subprocess.run(
                [trusted, "--list-cmds=builtins"], capture_output=True,
                text=True, timeout=10,
            )
            main_result = subprocess.run(
                [trusted, "--list-cmds=main,nohelpers"], capture_output=True,
                text=True, timeout=10,
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
    authority = _GIT_AUTHORITY_CACHE[trusted]
    if candidate != trusted:
        return authority._replace(candidate_trusted=False)
    return authority


def authorize_git_subcommand(subcommand, authority, effective_exec_path):
    if subcommand in authority.builtins:
        # git-config(1): "aliases that hide existing Git commands are ignored". A builtin
        # name therefore cannot be redirected by ambient alias/config in any Git on this
        # machine, which is what lets an untrusted candidate be classified from the
        # trusted Git's inventory. A Git too old or too new to carry the command as a
        # builtin is outside that inference.
        return None
    if not authority.candidate_trusted:
        return (f"Git subcommand {subcommand!r} is not a builtin of the trusted Git and "
                f"the command names a different Git executable, whose helper set and exec "
                f"path cannot be enumerated without executing it")
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
    """
    return word[1:] if len(word) > 1 and word[0] == "=" and word[1] != "=" else word


def _literal_git_word(word):
    word = _equals_expanded(word)
    return (os.path.basename(word) == "git"
            or bool(re.search(r"(?:^|\s)(?:/[^\s]*/)?=?git(?:\s|$)", word)))


def has_literal_guarded_git_tail(tokens):
    """Whether argv visibly contains `git` followed by a guarded subcommand."""
    words = [text for text, _quoting in tokens]
    for index, word in enumerate(words):
        if os.path.basename(_equals_expanded(word)) != "git":
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


def source_has_dynamic_command_word(source):
    """Whether the EXECUTABLE of any subcommand in this source is itself an expansion.

    `sh -c "$CMD"` is genuinely unknowable and must stay a question. `sh -c 'git show
    $SHA:x'` names its command and expands only an argument, so it can be judged on what
    is written. Treating both as "dynamic" questioned ordinary commands whose only sin was
    containing a `$`.
    """
    try:
        commands = split_commands(source)
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
        executable_text = _equals_expanded(items[0][0])
        if executable_text != items[0][0]:
            # Write the resolved name back so every downstream reader -- this loop, the
            # grep guard's argv walk and the zsh guard's rev:path gate -- sees the command
            # zsh will actually run rather than the `=` form.
            items[0] = (executable_text, items[0][1])
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


def _alias_guard_state(name, aliases, seen=(), depth=0):
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
            body[1:], aliases, seen + (lowered,), depth + 1)
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
        words[index], local_aliases, seen + (lowered,), depth + 1)


def _shell_alias_git_state(resolution, aliases, seen, depth):
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
    return _alias_guard_state(words[index], local_aliases, seen, depth + 1)


def _shell_alias_guard_state(source, aliases, seen=(), depth=0,
                             current_shell="sh"):
    """Tri-state literal shell alias traversal shared with top-level shell parsing."""
    if depth > MAX_ALIAS_DEPTH:
        return ALIAS_UNCERTAIN
    if not isinstance(source, str) or not source:
        return ALIAS_UNCERTAIN
    try:
        commands = split_commands(source)
    except CommandParseError:
        return ALIAS_UNCERTAIN
    state = ALIAS_HARMLESS
    for tokens in commands:
        resolution = unwrap_command_prefix(tokens)
        if resolution.errors:
            return ALIAS_UNCERTAIN
        invocation = nested_shell_invocation(resolution, current_shell)
        if invocation is not None:
            if not invocation.command:
                return ALIAS_UNCERTAIN
            nested_state = _shell_alias_guard_state(
                invocation.command, aliases, seen, depth + 1, invocation.shell)
            if nested_state != ALIAS_HARMLESS:
                return nested_state
            if invocation.dynamic or source_has_dynamic_command_word(invocation.command):
                return ALIAS_UNCERTAIN
            continue
        command_state = _shell_alias_git_state(resolution, aliases, seen, depth)
        if command_state != ALIAS_HARMLESS:
            return command_state
        state = command_state
    return state


def resolve_git_alias(subcommand, tail, aliases, authority, effective_exec_path):
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
            shell_state = _shell_alias_guard_state(body[1:], aliases, tuple(seen))
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


def git_grep_argv(tokens, resolution=None):
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
    authority = trusted_git_authority(words[j])
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
        effective_exec_path)
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
    sources = []
    for line in command.splitlines():
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
                line, redirect_start, word_end, int(descriptor_text or "0"),
                body, dynamic,
            ))
            index = word_end
    return tuple(sources)


def live_file_input_sources(command):
    """Return live plain file-input redirects without confusing shell arithmetic."""
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


def associated_stdin_consumer(line, redirect_start, word_end, commands):
    """Resolve one input source to its command record without cross-command joins."""
    marker = "__ZHAR_STDIN_SOURCE__"
    if marker in line:
        return StdinConsumer(False, True)
    marked = line[:redirect_start] + " " + marker + " " + line[word_end:]
    try:
        marked_commands = split_commands(marked)
    except CommandParseError:
        return StdinConsumer(False, True)
    matches = []
    for tokens in marked_commands:
        if any(text == marker for text, _quoting in tokens):
            matches.append(tokens)
    if len(matches) != 1:
        return StdinConsumer(False, True)
    stripped = [token for token in matches[0] if token[0] != marker]
    resolution = unwrap_command_prefix(_without_redirection_tokens(stripped))
    if resolution.errors or not resolution.items:
        return StdinConsumer(False, True)
    words = [word for word, _quoting in resolution.items]
    executable = words[0]
    if executable in TRUSTED_EXTERNAL_NON_FORWARDING_COMMANDS:
        return StdinConsumer(False, False)
    if os.path.basename(executable) in SHELLS:
        return StdinConsumer(_shell_reads_stdin(words), False)
    return StdinConsumer(False, True)


def _direct_here_string_shell(source):
    clean_line = (source.line[:source.redirect_start] + " "
                  + source.line[source.word_end:])
    try:
        commands = split_commands(clean_line)
    except CommandParseError:
        return False
    executable_commands = []
    for tokens in commands:
        stripped = _without_redirection_tokens(tokens)
        if stripped:
            executable_commands.append(stripped)
    if len(executable_commands) != 1:
        return False
    resolution = unwrap_command_prefix(executable_commands[0])
    if resolution.errors or not resolution.items:
        return False
    words = [word for word, _quoting in resolution.items]
    return bool(os.path.basename(words[0]) in SHELLS and _shell_reads_stdin(words))


def _direct_heredoc_header(line):
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
        commands = split_commands("".join(parts))
    except CommandParseError:
        return False
    return reachable_stdin_shells(commands) == (True,)


def classify_direct_here_string(source, shell_depth):
    if source.dynamic:
        return StdinProvenance(
            "ask", "a directly associated shell here-string has a dynamic source")
    decision, reason = decide(source.body, shell_depth + 1)
    if decision == "allow":
        return None
    return StdinProvenance(
        decision, "a directly associated shell here-string recursively classified as "
        + decision + " (" + reason + ")")


def interpreter_stdin_provenance(command, commands, shell_depth):
    """Classify stdin source reachability over all parsed command/function records."""
    for source in live_here_string_sources(command):
        if source.descriptor != 0:
            continue
        if _direct_here_string_shell(source):
            classified = classify_direct_here_string(source, shell_depth)
            if classified is not None:
                return classified
            continue
        consumer = associated_stdin_consumer(
            source.line, source.redirect_start, source.word_end, commands)
        if not consumer.reads_stdin and not consumer.unresolved:
            continue
        if consumer.reads_stdin and not consumer.unresolved:
            classified = classify_direct_here_string(source, shell_depth)
            if classified is not None:
                return classified
            continue
        if source.dynamic:
            nested_decision, nested_reason = decide(source.body, shell_depth + 1)
            if nested_decision != "allow":
                return StdinProvenance(
                    nested_decision,
                    "a here-string expansion recursively classified as "
                    + nested_decision + " (" + nested_reason + ")",
                )
        guarded_body = _raw_has_guarded_evidence(source.body)
        if (consumer.unresolved and guarded_body
                and _has_simple_unproven_shell_input(source.line)):
            continue
        if consumer.unresolved:
            return StdinProvenance(
                "ask", "a here-string consumer edge could not be resolved to a "
                "proven data consumer or interpreter")
        if source.dynamic or guarded_body:
            association = "unresolved" if consumer.unresolved else "executable"
            return StdinProvenance(
                "ask", f"a guarded or dynamic here-string has an {association} "
                "interpreter edge through a compound, subshell, or function")
    for source in live_file_input_sources(command):
        if source.descriptor != 0:
            continue
        consumer = associated_stdin_consumer(
            source.line, source.redirect_start, source.word_end, commands)
        if not consumer.reads_stdin and not consumer.unresolved:
            continue
        if source.path == "/dev/null":
            continue
        if source.dynamic or _raw_has_guarded_evidence(source.path):
            detail = "dynamic" if source.dynamic else "guarded"
        else:
            detail = "uninspected"
        return StdinProvenance(
            "ask", f"a {detail} file-input source can reach an executable interpreter; "
            "use an explicit script operand or a directly classified source")
    guarded_or_dynamic = _raw_has_guarded_evidence(command) or bool(UNRESOLVED.search(command))
    if not guarded_or_dynamic:
        return None
    has_pipeline = False
    for line in command.splitlines():
        for position in _live_shell_operator_positions(line, "|"):
            try:
                downstream = split_commands(line[position + 1:])
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
            executes = _header_executes_shell(line[:prefix])
            if executes is not False:
                has_process_input = True
                break
        if has_process_input:
            break
    heredoc_headers = [line for line in command.splitlines()
                       if _find_heredoc_operator(line) is not None]
    has_unproven_heredoc = any(
        not _direct_heredoc_header(line)
        and _header_executes_shell(line[:_find_heredoc_operator(line)[0]]) is not False
        for line in heredoc_headers)
    if has_pipeline or has_process_input or has_unproven_heredoc:
        return StdinProvenance(
            "ask", "guarded or dynamic stdin source syntax can reach an executable "
            "interpreter but no single direct source association was proven")
    return None


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


def _has_simple_unproven_shell_input(line):
    for _kind, prefix_end, descriptor in _live_interpreter_input_redirects(line):
        prefix = line[:prefix_end]
        if (descriptor == 0 and _header_executes_shell(prefix) is False
                and not any(_live_shell_operator_positions(line, operator)
                            for operator in (";", "|", "&", "{", "}", "(", ")"))
                and re.search(
                    r"(?:^|[;&|() \t])(?:[^;&|() \t]*/)?"
                    r"(?:sh|bash|zsh|dash|ksh)(?:$|[ \t])",
                    prefix,
                )):
            return True
    return False


def conservative_allow_uncertainty(command):
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
        commands = split_commands(command)
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
    if any(_has_simple_unproven_shell_input(line) for line in command.splitlines()):
        return "shell-input association remains unproven after detailed parsing"
    return None


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
    try:
        stdin_provenance = interpreter_stdin_provenance(
            command, commands, _shell_depth)
    except CommandParseError as exc:
        return ("ask", f"interpreter stdin provenance cannot be parsed safely ({exc}); "
                "rewrite it as one direct source before proceeding.")
    if stdin_provenance is not None:
        return stdin_provenance.decision, stdin_provenance.reason
    for tokens in commands:
        resolution = unwrap_command_prefix(tokens)
        if resolution.errors and resolution.hazard_hint:
            return ("ask", "a possible Git invocation crosses an unresolved command "
                    "prefix (" + "; ".join(resolution.errors) + "); invoke Git directly "
                    "so the pattern engine can be verified.")
        invocation = nested_shell_invocation(resolution)
        if invocation is not None:
            # Inspect the body first. Returning `ask` on `dynamic` before recursing meant
            # a nested body carrying a live ERE hazard was downgraded to a question, and
            # a body with no Git in it at all -- `sh -c 'echo $PATH'` -- was questioned
            # too, purely for containing a `$`.
            if invocation.command:
                nested_decision, nested_reason = decide(
                    invocation.command, _shell_depth + 1)
                if nested_decision != "allow":
                    return nested_decision, nested_reason
            # Uncertainty about the body only matters once Git is actually in it.
            # An unknown EXECUTABLE is the honest question: the body could be anything,
            # including a git grep. An unknown ARGUMENT to a named command is not -- that
            # is judged on what is written.
            if (not invocation.command
                    or source_has_dynamic_command_word(invocation.command)):
                return ("ask", "a shell -c command string is empty, or chooses its "
                        "executable from an expansion, so the Git grep engine cannot be "
                        "inspected before execution")
        try:
            got = git_grep_argv(tokens, resolution)
        except GitAuthorityError as exc:
            # Not proof of the guarded hazard, so not `deny`: this is the unresolved-
            # executable row of the decision contract, which is `ask`.
            return ("ask", "the Git behind this command cannot be identified ("
                    + str(exc) + "), so neither its command inventory nor its regex "
                    "engine can be proved; confirm the binary or invoke Git directly "
                    "with an explicit -P engine.")
        if got is None:
            continue
        argv, configs, unresolved_configs = got
        if unresolved_configs:
            return ("ask",
                    "the Git pattern invocation has unresolved configuration or alias "
                    "state: " + "; ".join(unresolved_configs) + ". This guard cannot "
                    "prove the command and regex engine, so use a direct invocation with "
                    "an explicit -P engine.")
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
                if separator and git_config_bool_is_false(value):
                    engine = "B"
                    engine_src = "config"
                else:
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
            return ("ask", "git grep has an ambiguous or invalid long option ("
                    + ", ".join(uncertain_engine_options)
                    + "); use the complete option name so its arity and regex-engine "
                    "effect can be classified before execution.")
        if engine not in {None, "E"}:
            continue
        if engine is None and AMBIENT_ENGINE_REQUIRES_EXPLICIT and pattern_from_file:
            return ("ask", "git grep has no command-resolved regex engine and reads a "
                    "pattern file that argv inspection cannot classify. Ambient Git "
                    "configuration may select ERE; use an explicit -P/-E/-G/-F engine.")
        engine_desc = "-E" if engine_src == "flag" else "Git grep configuration"
        if not patterns:
            if pattern_from_file:
                return ("ask",
                        "git grep with the ERE engine (%s) and a -f PATTERN FILE: this "
                        "guard reads argv only and CANNOT see the file's patterns, so a "
                        "live PCRE-only construct may silently mismatch under ERE. "
                        "Out of scope for this guard - verify the file's patterns by hand "
                        "or use -P." % engine_desc)
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
                return ("ask", "git grep has no command-resolved regex engine while its "
                        f"pattern contains {detail}. Mutable ambient Git configuration "
                        "may change the effective engine; choose -P/-E/-G/-F explicitly.")
            continue
        if engine is None:
            continue
        if bad_atoms:
            return ("deny",
                    "git grep with the ERE engine (selected by " + engine_desc + ") "
                    "cannot interpret %s with the intended PCRE grammar. Installed-Git "
                    "selftests distinguish these live constructs from escaped-literal controls. "
                    "An empty or different result is evidence about the selected regex engine, "
                    "not about the repository. Re-run with -P."
                    % ", ".join(sorted(bad_atoms)))
        if uncertain_atoms:
            return ("ask",
                    "git grep with the ERE engine contains unmodelled live regex "
                    "construct(s) %s. The guard cannot prove those constructs have the same "
                    "meaning under ERE and PCRE; use -P or replace them with grounded portable "
                    "syntax." % ", ".join(sorted(uncertain_atoms)))
        if unresolved is not None:
            return ("ask",
                    "git grep -E with a shell-expanded pattern (%s): this guard reads argv "
                    "only and CANNOT see the final pattern, so regex-engine compatibility is "
                    "UNCHECKED here. Out of scope for this guard - verify by hand or use -P."
                    % unresolved[:60])
    fallback_uncertainty = conservative_allow_uncertainty(command)
    if fallback_uncertainty:
        return ("ask", fallback_uncertainty + "; guarded-looking text is allowed through "
                "complex input syntax only when the operation resolves to an exact trusted "
                "data-consumer path. Otherwise rewrite it as one directly classified source.")
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
    ("RED  ROUND 9: a different absolute Git path fails authority discovery closed",
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

# A machine can carry more than one real Git -- Homebrew's and Apple's /usr/bin/git are
# both present on stock macOS. Naming the one PATH does not resolve is uncertainty about
# WHICH binary runs, never proof of the guarded hazard, so it may not reach `deny`. The
# path below is absolute and nonexistent so it is never the trusted Git on any host, which
# keeps this group's contribution to `checks` the same everywhere.
_UNTRUSTED_GIT = "/nonexistent/bin/git"
FIXTURES += [
    ("GREEN AUTHORITY: an untrusted Git running a builtin is not the guarded hazard",
     f"{_UNTRUSTED_GIT} status --short", "allow"),
    ("GREEN AUTHORITY: an untrusted Git staging files is not the guarded hazard",
     f"{_UNTRUSTED_GIT} add -A", "allow"),
    ("GREEN AUTHORITY: an untrusted Git with a PCRE engine stays allowed",
     f"{_UNTRUSTED_GIT} grep -P 'harness\\b' -- README.md", "allow"),
    ("RED  AUTHORITY: an untrusted Git does not launder the ERE hazard",
     f"{_UNTRUSTED_GIT} grep -E 'harness\\b' -- README.md", "deny"),
    ("ASK  AUTHORITY: a non-builtin subcommand on an untrusted Git is unresolved",
     f"{_UNTRUSTED_GIT} submodule status", "ask"),
    ("ASK  AUTHORITY: an unknown subcommand on an untrusted Git is unresolved",
     f"{_UNTRUSTED_GIT} project-helper --version", "ask"),
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
    ("ASK  EQUALS: a wrapped =git behind an unmodelled launcher is unresolved",
     "xargs =git show", "ask"),
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
    absence_ok = not absent_failures and absent_checks == 5 and absent_skips == 8
    bad += 0 if absence_ok else 1
    print("  %s absent zsh skips only 8 zsh probes; 5 portable probes still execute" % (
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
        lambda subcommand, tail, _aliases, _authority, _exec_path:
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
    def ignore_alias_eval(resolution, current_shell="sh"):
        if resolution.items and os.path.basename(resolution.items[0][0]) == "eval":
            return None
        return original_nested_shell(resolution, current_shell)
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

    def ignore_alias_shell_c(resolution, current_shell="sh"):
        if (resolution.items
                and os.path.basename(resolution.items[0][0]) in SHELLS):
            return None
        return original_nested_shell(resolution, current_shell)
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
    globals()["trusted_git_authority"] = lambda _executable="git": (_ for _ in ()).throw(
        GitAuthorityError("planted discovery failure"))
    try:
        discovery_red = decide("git status --short")[0] == "ask"
    finally:
        globals()["trusted_git_authority"] = original_discovery
    bad += 0 if discovery_red else 1
    print("  %s trusted-Git discovery failure asks instead of allowing" % (
        "PASS" if discovery_red else "FAIL"))

    trusted_authority = original_discovery()
    globals()["trusted_git_authority"] = lambda _executable="git": GitAuthority(
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
    globals()["extract_function_invocations"] = lambda source: (source, ())
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

    def drop_function_invocations(source):
        cleaned, _sources = original_functions(source)
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
    def collapse_function_versions(source):
        records = original_function_records(source)
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
    def ignore_conditional_reachability(source, records):
        return tuple(record._replace(conditional=False)
                     for record in original_annotation(source, records))
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

    def globalize_function_scope(source, records):
        return tuple(record._replace(scope_start=-1, scope_end=len(source))
                     for record in original_annotation(source, records))
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

    def globalize_maybe_definitions(source, records):
        return tuple(record._replace(maybe=False)
                     for record in original_annotation(source, records))
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

    def globalize_pipeline_definitions(source, records):
        return tuple(record._replace(pipeline_start=-1, pipeline_end=-1)
                     for record in original_annotation(source, records))
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

    original_direct_here = _direct_here_string_shell
    globals()["_direct_here_string_shell"] = lambda _source: False
    try:
        leading_stdin_red = decide(
            r'''(sh) <<< "git grep -E 'harness\b' -- README.md"''')[0] != "deny"
    finally:
        globals()["_direct_here_string_shell"] = original_direct_here
    bad += 0 if leading_stdin_red else 1
    print("  %s grouped-shell association mutation loses recursive deny" % (
        "PASS" if leading_stdin_red else "FAIL"))

    original_association = associated_stdin_consumer
    globals()["associated_stdin_consumer"] = (
        lambda _line, _start, _end, _commands: StdinConsumer(False, False))
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
        lambda _line, _start, _end, parsed:
        StdinConsumer(any(reachable_stdin_shells(parsed)), False))
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
        lambda _source, _depth: StdinProvenance("ask", "planted unconditional ask"))
    try:
        unconditional_here_red = decide(
            r'''sh 0<<< "/bin/echo safe"''')[0] != "allow"
    finally:
        globals()["classify_direct_here_string"] = original_here_classifier
    bad += 0 if unconditional_here_red else 1
    print("  %s unconditional here-string mutation loses harmless static allow" % (
        "PASS" if unconditional_here_red else "FAIL"))

    globals()["classify_direct_here_string"] = lambda _source, _depth: None
    try:
        here_recursion_red = decide(
            r'''sh <<< "git grep -E 'harness\b' -- README.md"''')[0] != "deny"
    finally:
        globals()["classify_direct_here_string"] = original_here_classifier
    bad += 0 if here_recursion_red else 1
    print("  %s here-string recursion mutation loses guarded nested deny" % (
        "PASS" if here_recursion_red else "FAIL"))

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
    def drop_heredoc_body(source):
        cleaned, _bodies = original_heredoc(source)
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

    def keep_winning_heredoc_only(source):
        cleaned, bodies = original_heredoc(source)
        if "<<A <<'B'" in source:
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

    original_header_executes = _header_executes_shell
    globals()["_header_executes_shell"] = lambda _header, _suffix="": False
    try:
        heredoc_path_red = decide(
            "sh 0<<'EOF'\ngit grep -E 'harness\\b' -- README.md\nEOF\n"
        )[0] != "deny"
    finally:
        globals()["_header_executes_shell"] = original_header_executes
    bad += 0 if heredoc_path_red else 1
    print("  %s heredoc execution-header mutation loses descriptor-zero deny" % (
        "PASS" if heredoc_path_red else "FAIL"))

    original_fallback = conservative_allow_uncertainty
    globals()["conservative_allow_uncertainty"] = lambda _source: None
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

    checks = len(FIXTURES) + 48
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
