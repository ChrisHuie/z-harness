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
    out, cur = [], []
    tok_parts, tok_mode_parts, tok_modes, q, i = [], [], set(), "", 0
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
        nonlocal tok_parts, tok_mode_parts, tok_modes
        if tok_parts or tok_modes:
            quoting = (next(iter(tok_modes)) if len(tok_modes) == 1
                       else "mixed:" + "".join(tok_mode_parts))
            cur.append(("".join(tok_parts), quoting))
        tok_parts, tok_mode_parts, tok_modes = [], [], set()

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
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
SHELLS = {"sh", "bash", "zsh", "dash", "ksh"}
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
}
WRAPPER_TERMINAL_OPTIONS = {"--help", "--version"}


def strip_shell_keywords(words):
    """Drop leading shell keywords so `do git ...` still gates on git."""
    k = 0
    while k < len(words) and words[k] in SHELL_KEYWORDS:
        k += 1
    return words[k:]


def unwrap_command_prefix(tokens):
    """Peel common launch wrappers and return (argv tokens, environment, errors).

    The hook sees shell source, not execve(2) argv.  `env`, `nice`, absolute
    executable paths, and `sh -c` are therefore part of the security boundary:
    treating only literal argv[0] == "git" makes the same Git invocation vanish.
    """
    items = list(tokens)
    command_env = dict(os.environ)
    errors = []
    wrapper_depth = 0
    while items:
        while items and items[0][0] in SHELL_KEYWORDS:
            items.pop(0)
        while items and ASSIGNMENT.match(items[0][0]):
            key, value = items.pop(0)[0].split("=", 1)
            command_env[key] = value
        if not items:
            break

        executable = os.path.basename(items[0][0])
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

        break
    if wrapper_depth > 8:
        errors.append("more than eight nested command wrappers")
    return items, command_env, errors


def nested_shell_command(tokens):
    """Return the command string passed to a common shell's -c, if present."""
    items, _command_env, errors = unwrap_command_prefix(tokens)
    if errors or not items or os.path.basename(items[0][0]) not in SHELLS:
        return None
    args = items[1:]
    for index, (word, _quoting) in enumerate(args):
        if word == "--":
            continue
        if word == "-c" or (word.startswith("-") and not word.startswith("--")
                             and "c" in word[1:]):
            return args[index + 1][0] if index + 1 < len(args) else ""
    return None


def git_grep_argv(tokens):
    """-> (argv after git grep, config values, unresolved relevant config),
    or None when this subcommand is not a git grep."""
    items, command_env, prefix_errors = unwrap_command_prefix(tokens)
    words = [t for t, _ in items]
    if not words:
        return None
    j = 0
    if prefix_errors:
        concealed_git = any(
            os.path.basename(word) == "git"
            or re.search(r"(?:^|\s)(?:/[^\s]*/)?git(?:\s|$)", word)
            for word in words
        )
        if concealed_git:
            return [], [], prefix_errors
    if os.path.basename(words[j]) != "git":
        return None
    j += 1
    configs = []
    unresolved_configs = list(prefix_errors)

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
    for tokens in split_commands(command):
        nested = nested_shell_command(tokens)
        if nested is not None:
            if not nested:
                return ("ask", "a shell -c wrapper is missing its command string")
            nested_decision, nested_reason = decide(nested, _shell_depth + 1)
            if nested_decision != "allow":
                return nested_decision, nested_reason
        got = git_grep_argv(tokens)
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
    ("ASK  ROUND 9: unmodelled env command splitting cannot hide git",
     """env -S \"git grep -nE 'harness\\b' -- README.md\"""", "ask"),
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
    ("GREEN ROUND 10: an arbitrary non-wrapper is not treated as command forwarding",
     """echo git grep -nE 'harness\\b' -- README.md""", "allow"),
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
