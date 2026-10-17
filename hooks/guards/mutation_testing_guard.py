#!/usr/bin/env python3
"""mutation_testing_guard — deny running or installing a mutation-testing tool from Bash.

AGENTS.md (Verification mechanics) bans mutation testing in every project and runtime. This
predicate is command-only, so it runs in bash_command_guard's GUARDS list and decides the
same way for every caller on both runtimes; it needs no hook registration of its own.

Each simple command is judged after its env assignments, the wrappers credential_reach_guard
strips (env, command, exec, nohup, time, sudo, nice, timeout, stdbuf, xargs, ...), shell
control keywords (if, then, do, while, until, !, noglob, coproc, ...) and the launchers this
module strips itself (taskset, chronic, flock, builtin, repeat, zsh's `-` and `=cmd`).
Modelled:
  a listed tool at command position: a tool-specific name by any path; a generic name
  (mutate, mutant, infection, gremlins) only bare or under a directory a package manager
  installs executables into;
  a listed tool or package through a package runner (npx, bunx, pnpx, uvx, pipx run, pnpm
  dlx|exec, npm exec|x, yarn dlx|exec|run, bun x|run, bundle exec, poetry run, uv run, uv tool
  run, pdm run, hatch run, pipenv run, composer exec, conda run, pixi run, rye run, mise
  exec, pyenv|rbenv|asdf exec, direnv exec, corepack), with the runner's value-taking options
  skipped and a listed package named by its --with, --from, --package or --spec option;
  a package script, make, just or task target, tox environment or nox session whose name
  holds a mutation word or a tool name, and `npm|pnpm|yarn|bun init|create` of a listed
  initializer;
  `python -m <module>` with interpreter options parsed (`-mMOD` and submodules included),
  and python, node, php, phpdbg, ruby, bun or deno running a tool from an install bin
  directory or one of this harness's former scripts;
  cargo mutants|mutagen, dotnet stryker, mvn|mvnw|mvnd with a PIT goal or profile, gradle
  with a pitest task, sbt stryker, java with a PIT class or jar, dextool mutate, and go
  run|install|get|tool of a listed Go module or tool;
  an install of a listed package through an installer of the ecosystem that publishes it;
  the bodies of `sh|bash|zsh -c`, a here-string fed to a shell, `eval`, `env -S`,
  `alias NAME=VALUE`, watch, su -c, script, nix-shell --run, nix develop|shell -c, ssh,
  find -exec and parallel, judged recursively; command substitutions and heredoc bodies fed
  to a shell arrive through the shared tokenizer.
A command whose command word is a parameter expansion, in a command that names a listed
tool, is asked about rather than allowed; so is source the tokenizer cannot read that names
one.
Not modelled, and printed by --selftest as out of scope: a variant made by arbitrary code;
a tool launched from code an interpreter receives (python -c, node -e, a heredoc to python),
even when that code names the tool; a listed tool copied or linked under another name; an
alias or function defined in an earlier command; a script or target whose name does not
say what it runs; text piped into a shell's stdin; a container image's entrypoint; a tool
missing from these tables.
"""
import os
import pathlib
import re
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import credential_reach_guard as words      # noqa: E402  (_command_word, SHELLS, WRAPPERS)
import git_grep_engine_guard as tokenizer   # noqa: E402  (split_commands, CONTROL_KEYWORDS)

# Tool-specific command names, matched by basename wherever the path points.
SPECIFIC_TOOLS = frozenset({
    "mutmut", "cosmic-ray", "cr-report", "cr-html", "cr-rate", "cr-badge", "cr-xml",
    "mutatest", "mut.py", "mutahunter",                                      # Python
    "stryker",                                                               # JS/TS
    "dotnet-stryker",                                                        # .NET
    "cargo-mutants", "cargo-mutagen",                                        # Rust
    "go-mutesting",                                                          # Go
    "infection.phar",                                                        # PHP
    "mull-runner", "mull-cxx", "mull-reporter", "analyze_mutants",           # C/C++
    "write-mutation-receipt.py", "enumerate_survivors.py",                   # this harness, former
})
# Generic words other software also uses as names, each with the ecosystem that ships the
# tool: matched only bare or under an install bin directory, and through that ecosystem's
# runners.
GENERIC_TOOLS = {"mutate": "python", "mutant": "ruby", "infection": "php", "gremlins": "go"}
VERSIONED_TOOL = re.compile(r"mull-(?:runner|cxx|reporter)-\d+")
# Script names an interpreter runs from anywhere: no other software ships these files.
SPECIFIC_SCRIPTS = frozenset({"mut.py", "infection.phar", "write-mutation-receipt.py",
                              "enumerate_survivors.py"})
ABSOLUTE_BIN_DIRS = frozenset({"/bin", "/usr/bin", "/usr/local/bin", "/opt/homebrew/bin"})
RELATIVE_BIN_DIRS = ("node_modules/.bin", "vendor/bin", ".venv/bin", "venv/bin", "go/bin",
                     ".cargo/bin", ".local/bin")
PYTHON_MODULES = frozenset({"mutmut", "cosmic_ray", "mutatest", "mutpy", "mutahunter"})
# Package names per ecosystem, lowercased, version stripped. `mutant` is the Ruby tool only:
# the npm and PyPI packages of that name are unrelated software.
PACKAGES = {
    "python": frozenset({"mutmut", "cosmic-ray", "cosmic_ray", "mutatest", "mutpy",
                         "mutahunter", "universalmutator"}),
    "js": frozenset({"stryker", "stryker-cli", "create-stryker"}),
    "rust": frozenset({"cargo-mutants", "cargo-mutagen"}),
    "dotnet": frozenset({"dotnet-stryker"}),
    "php": frozenset({"infection/infection"}),
    "ruby": frozenset({"mutant", "mutant-rspec", "mutant-minitest"}),
}
PACKAGE_SCOPES = {"js": ("@stryker-mutator/",)}
GO_MODULE_MARKERS = ("go-mutesting", "go-gremlins/gremlins")
GO_TOOLS = frozenset({"gremlins", "go-mutesting"})
OS_PACKAGE = re.compile(r"mull(?:-\d+)?")
# Words that name the method or a tool inside a script, target, environment or session name.
SCRIPT_WORDS = frozenset({"mutation", "mutate", "mutants", "mutant", "mutmut", "stryker",
                          "pitest", "mutatest", "mutpy", "mutahunter"})
# Every spelling above contains one of these, lowercased; the selftest proves it. A command
# without any of them, after quotes and backslashes are removed, is answered before the
# tokenizer runs.
NEEDLES = ("mut", "stryker", "pitest", "cosmic", "cr-", "infection", "mull", "gremlins",
           "dextool", "survivor")
PIP = re.compile(r"pip\d*(?:\.\d+)*")
PYTHON = re.compile(r"python(?:\d+(?:\.\d+)*)?|py|pypy\d*(?:\.\d+)*")
SCRIPT_SUFFIX = re.compile(r"\.(?:js|cjs|mjs|ts|rb|php|py)$")
MAX_DEPTH = 4
TOOL_WORD = re.compile(
    r"(?<![\w./-])(?:" + "|".join(re.escape(t) for t in sorted(
        SPECIFIC_TOOLS | set(GENERIC_TOOLS), key=len, reverse=True)) + r")(?![\w-])")
REASON = (
    "mutation_testing: {found}. Mutation testing is banned in every project and runtime "
    "(AGENTS.md, Verification mechanics): do not run, install or request mutation tools, "
    "sweeps, scores or survivor lists. Prove the check directly: positive and negative input "
    "fixtures, planted-defect inputs and tampered artifacts fed to the code, exact assertions "
    "on structured results, the head's regression test failing against the parent commit's "
    "code, a differential run of two real versions, input fuzzing, or adversarial review. If "
    "the tool name is only text, the shell still runs it inside backticks, $( ) or an unquoted "
    "heredoc; single-quote it or use <<'EOF'.")
ASK_REASON = ("mutation_testing: {found}, in a command that names a mutation-testing tool; "
              "confirm it does not run one")

# Options that take a value, per command, so the word after them is never read as the
# command or package they run.
GLOBAL_VALUE_OPTIONS = {
    "npm": {"-w", "--workspace", "--prefix", "-C", "--userconfig", "--cache", "--registry"},
    "pnpm": {"-F", "--filter", "-C", "--dir", "--workspace-concurrency", "--reporter"},
    "yarn": {"--cwd"},
    "bun": {"--cwd", "-c", "--config"},
    "poetry": {"-C", "--directory", "-P", "--project"},
    "uv": {"--directory", "--project", "--cache-dir", "--config-file", "--color"},
    "pdm": {"-p", "--project"},
    "hatch": {"-e", "--env", "-p", "--project", "--data-dir", "--cache-dir", "--config"},
    "composer": {"-d", "--working-dir"},
    "pixi": {"--manifest-path"},
    "cargo": {"-Z", "--config", "-C", "--color"},
    "go": {"-C"},
    "conda": set(), "mamba": set(),
}
UV_RUN_VALUES = {"--directory", "--project", "--python", "-p", "--with", "--with-editable",
                 "--with-requirements", "--extra", "--group", "--only-group", "--no-group",
                 "--package", "--env-file", "--index", "--default-index", "--index-url",
                 "--extra-index-url", "--find-links", "-f", "--from", "--cache-dir",
                 "--config-file", "--color", "--python-preference", "--resolution",
                 "--prerelease", "--exclude-newer", "--link-mode", "--index-strategy",
                 "--keyring-provider", "--config-setting", "-C"}
RUNNER_VALUES = {
    "js": {"-p", "--package", "-c", "--call", "-w", "--workspace", "--node-options"},
    "uv": UV_RUN_VALUES,
    "pipx": {"--spec", "--python", "--pip-args", "--index-url"},
    "conda": {"-n", "--name", "-p", "--prefix", "--cwd"},
    "pixi": {"-e", "--environment", "--manifest-path"},
    "bundle": {"--gemfile"},
    "plain": set(),
}
PACKAGE_OPTIONS = {"-p", "--package", "--with", "--with-editable", "--from", "--spec"}
CALL_OPTIONS = {"-c", "--call"}


class BudgetExhausted(Exception):
    """The caller's decision deadline passed before the scan finished."""


def _base(word):
    return os.path.basename(word)


def _deny(text):
    return ("deny", text)


def _package(word):
    """A package argument, lowercased: registry prefix, version, extras and URL parts dropped."""
    word = word.lower().strip()
    for prefix in ("npm:", "jsr:"):
        if word.startswith(prefix):
            word = word[len(prefix):]
    if "://" in word or word.startswith(("git+", "git@")):
        word = word.split("#", 1)[0].rstrip("/").rsplit("/", 1)[-1]
        word = re.sub(r"@[^/]*$", "", word)
        word = re.sub(r"\.git$", "", word)
        word = re.sub(r"(?:\.tar\.gz|\.tgz|\.tar\.bz2|\.zip|\.whl)$", "", word)
        return re.sub(r"-\d[\w.]*(?:-.*)?$", "", word)
    word = re.sub(r"(?<=.)@[^/@]*$", "", word)
    return re.split(r"[=<>!~;\[ ]", word, maxsplit=1)[0]


def _listed_package(word, family):
    package = _package(word)
    if family == "go":
        return any(marker in package for marker in GO_MODULE_MARKERS)
    if family == "os":
        return OS_PACKAGE.fullmatch(package) is not None
    return (package in PACKAGES.get(family, ())
            or package.startswith(PACKAGE_SCOPES.get(family, ())))


def _in_bin_dir(path):
    directory = os.path.normpath(os.path.dirname(path)) if "/" in path else ""
    if not directory:
        return False
    return directory in ABSOLUTE_BIN_DIRS or any(
        directory == suffix or directory.endswith("/" + suffix) for suffix in RELATIVE_BIN_DIRS)


def _specific(name):
    return name in SPECIFIC_TOOLS or VERSIONED_TOOL.fullmatch(name) is not None


def _tool_at_command(word):
    """A listed tool named at command position."""
    name = _base(word).lower()
    if _specific(name):
        return True
    return name in GENERIC_TOOLS and ("/" not in word or _in_bin_dir(word))


def _runner_tool(word, family):
    """A listed tool named as a package runner's target."""
    name = _base(word).lower()
    return _specific(name) or GENERIC_TOOLS.get(name, "-") == family


def _method_words(name):
    return sorted({t for t in re.split(r"[:._/\-\s,]+", name.lower()) if t in SCRIPT_WORDS})


def _skip_options(args, values):
    """-> index of the first operand: options, their values and a `--` skipped."""
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--":
            return i + 1
        if not arg.startswith("-") or arg == "-":
            return i
        i += 2 if arg in values else 1
    return i


def _subcommand(name, args):
    """-> (subcommand, words after it), with the command's global options skipped."""
    i = _skip_options(args, GLOBAL_VALUE_OPTIONS.get(name, set()))
    if name == "cargo":
        while i < len(args) and args[i].startswith("+"):
            i += 1
            i += _skip_options(args[i:], GLOBAL_VALUE_OPTIONS["cargo"])
    return (args[i], args[i + 1:]) if i < len(args) else (None, [])


def _value_after(args, options):
    """The value of the first of `options` (`-o VALUE` or `--opt=VALUE`), or None."""
    for i, arg in enumerate(args):
        if arg in options and i + 1 < len(args):
            return args[i + 1]
        for option in options:
            if option.startswith("--") and arg.startswith(option + "="):
                return arg[len(option) + 1:]
    return None


def _run_target(label, family, args, values, depth, deadline):
    """A package runner: the package or tool it runs, or the command it hands on."""
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--":
            i += 1
            break
        if not arg.startswith("-") or arg == "-":
            break
        option, eq, attached = arg.partition("=")
        value = attached if eq else (args[i + 1] if option in values and i + 1 < len(args)
                                     else None)
        if option in CALL_OPTIONS and option in values and value is not None:
            return _scan(value, depth + 1, deadline)
        if option in PACKAGE_OPTIONS and value is not None and family \
                and _listed_package(value, family):
            return [_deny(f"`{label}` runs with the mutation-testing package `{value}`")]
        i += 1 if eq or option not in values else 2
    if i >= len(args):
        return []
    target = args[i]
    if (family and _listed_package(target, family)) or _runner_tool(target, family):
        return [_deny(f"`{label}` runs the mutation-testing tool `{target}`")]
    return _findings_for(args[i:], depth + 1, deadline)


def _named_script(label, name):
    found = _method_words(name)
    if found:
        return [_deny(f"`{label} {name}` runs a script or target named for mutation testing "
                      f"({', '.join(found)})")]
    return []


def _script_or_bin(label, family, args, depth, deadline):
    """`npm run NAME`, `yarn NAME` and kin: a listed bin, or a script named for the method."""
    if not args:
        return []
    target = args[0]
    if _runner_tool(target, family) or _listed_package(target, family):
        return [_deny(f"`{label}` runs the mutation-testing tool `{target}`")]
    return _named_script(label, target)


def _initializer(label, args):
    """`npm init NAME` runs the package create-NAME."""
    operands = [a for a in args if not a.startswith("-")]
    if not operands:
        return []
    name = _package(operands[0])
    if _listed_package(name, "js") or _listed_package("create-" + name, "js"):
        return [_deny(f"`{label}` runs the mutation-testing initializer `{operands[0]}`")]
    return []


def _installs(label, family, packages):
    listed = [word for word in packages
              if not word.startswith("-") and _listed_package(word, family)]
    if listed:
        return [_deny(f"`{label}` installs the mutation-testing package `{listed[0]}`")]
    return []


def _python_target(args):
    """-> (kind, value, rest) for python's argv: module, script, code, stdin or none."""
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--":
            return ("script", args[i + 1], args[i + 2:]) if i + 1 < len(args) else (None, None, [])
        if arg == "-":
            return "stdin", None, args[i + 1:]
        if arg.startswith("--"):
            i += 2 if arg == "--check-hash-based-pycs" else 1
            continue
        if arg.startswith("-") and len(arg) > 1:
            consumed = 1
            for at, letter in enumerate(arg[1:], 1):
                if letter == "m":
                    if arg[at + 1:]:
                        return "module", arg[at + 1:], args[i + 1:]
                    return ("module", args[i + 1], args[i + 2:]) if i + 1 < len(args) \
                        else (None, None, [])
                if letter == "c":
                    return "code", None, []
                if letter in "XW":
                    consumed = 1 if arg[at + 1:] else 2
                    break
            i += consumed
            continue
        return "script", args[i], args[i + 1:]
    return None, None, []


INTERPRETER_VALUES = {
    "node": {"-r", "--require", "--import", "--loader", "--experimental-loader", "--env-file",
             "-C", "--conditions", "--input-type", "--title"},
    "php": {"-d", "-c", "-z"},
    "phpdbg": {"-c", "-d", "-i", "-O", "-S", "-l", "-z"},
    "ruby": {"-I", "-r", "-C", "-E", "-F"},
    "deno": {"-c", "--config", "--import-map", "--lock", "--cert", "--location", "--seed",
             "-L", "--log-level", "--env-file"},
}
INTERPRETER_CODE = {
    "node": {"-e", "--eval", "-p", "--print"}, "php": {"-r", "-B", "-R", "-E", "-F"},
    "phpdbg": set(), "ruby": {"-e"}, "deno": {"eval"},
}


def _interpreted(name, script):
    """A script an interpreter runs that is a listed tool."""
    if script is None:
        return []
    path = script[len("npm:"):] if script.startswith("npm:") else script
    if script.startswith(("npm:", "jsr:")) and (_listed_package(script, "js")
                                                or _specific(_package(path))):
        return [_deny(f"`{name}` runs the mutation-testing package `{script}`")]
    base = _base(path)
    stem = SCRIPT_SUFFIX.sub("", base).lower()
    if (base in SPECIFIC_SCRIPTS or "node_modules/@stryker-mutator/" in path
            or (_in_bin_dir(path) and (_specific(stem) or stem in GENERIC_TOOLS))):
        return [_deny(f"`{name}` runs the mutation-testing script `{script}`")]
    return []


def _interpreter_findings(name, args):
    """None when `name` is no interpreter; else the findings for the script or module it runs."""
    if PYTHON.fullmatch(name):
        kind, value, rest = _python_target(args)
        if kind == "module":
            if value.split(".")[0] in PYTHON_MODULES:
                return [_deny(f"`python -m {value}` runs a mutation-testing tool")]
            if value == "pip" and rest[:1] == ["install"]:
                return _installs("python -m pip install", "python", rest[1:])
            return []
        return _interpreted(name, value) if kind == "script" else []
    if name in INTERPRETER_VALUES:
        if name == "deno":
            if args[:1] != ["run"]:
                return []
            args = args[1:]
        code = INTERPRETER_CODE[name]
        i = 0
        while i < len(args):
            arg = args[i]
            if arg in code:
                return []
            if arg == "--" or not arg.startswith("-") or arg == "-":
                break
            if name == "php" and arg == "-f" and i + 1 < len(args):
                return _interpreted(name, args[i + 1])
            i += 2 if arg in INTERPRETER_VALUES[name] else 1
        if i < len(args) and args[i] == "--":
            i += 1
        return _interpreted(name, args[i]) if i < len(args) else []
    return None


def _build_tool_findings(name, args):
    """A build or package tool's subcommand, goal or task that runs a mutation tool."""
    lowered = [a.lower() for a in args]
    if name == "cargo":
        verb, _rest = _subcommand("cargo", args)
        if verb in {"mutants", "mutagen"}:
            return [_deny(f"`cargo {verb}` is a mutation-testing tool")]
    elif name == "dotnet":
        verb, rest = _subcommand("dotnet", args)
        if verb == "stryker" or (verb == "tool" and rest[:2] == ["run", "dotnet-stryker"]):
            return [_deny("`dotnet` runs Stryker.NET, a mutation-testing tool")]
    elif name in {"mvn", "mvnw", "mvnd"}:
        profiles = []
        for i, arg in enumerate(lowered):
            if arg in {"-p", "--activate-profiles"} and i + 1 < len(lowered):
                profiles += lowered[i + 1].split(",")
            elif arg.startswith("-p") and len(arg) > 2:
                profiles += arg[2:].split(",")
        if any(a.startswith(("org.pitest:", "pitest:")) for a in lowered) \
                or "pitest" in [p.lstrip("!") for p in profiles]:
            return [_deny(f"`{name}` runs PIT, a mutation-testing tool")]
    elif name == "java":
        if any("org.pitest" in a for a in lowered) or any(
                _base(a).startswith("pitest") and a.endswith(".jar") for a in lowered):
            return [_deny("`java` runs PIT, a mutation-testing tool")]
    elif name in {"gradle", "gradlew"}:
        values = {"-p", "--project-dir", "-x", "--exclude-task", "-b", "--build-file", "-c",
                  "--settings-file", "-g", "--gradle-user-home", "-i", "--init-script",
                  "--console", "--warning-mode", "-d", "--include-build"}
        i = 0
        while i < len(lowered):
            arg = lowered[i]
            if arg.startswith("-"):
                i += 2 if arg in values else 1
                continue
            if arg.rsplit(":", 1)[-1].startswith("pitest"):
                return [_deny(f"`{name}` runs the PIT task, a mutation-testing tool")]
            i += 1
    elif name == "sbt":
        if "stryker" in lowered:
            return [_deny("`sbt stryker` runs Stryker4s, a mutation-testing tool")]
    elif name == "dextool":
        if [a for a in lowered if not a.startswith("-")][:1] == ["mutate"]:
            return [_deny("`dextool mutate` is a mutation-testing tool")]
    elif name == "go":
        verb, rest = _subcommand("go", args)
        if verb in {"run", "install", "get"} and any(
                marker in a for a in rest for marker in GO_MODULE_MARKERS):
            return [_deny(f"`go {verb}` fetches or runs a mutation-testing module")]
        if verb == "tool" and rest and (_base(rest[0]).lower() in GO_TOOLS or any(
                marker in rest[0] for marker in GO_MODULE_MARKERS)):
            return [_deny(f"`go tool {rest[0]}` runs a mutation-testing tool")]
    return []


def _package_manager_findings(name, args, depth, deadline):
    """Installs, runners, scripts and initializers of the package managers."""
    if PIP.fullmatch(name):
        verb, rest = _subcommand(name, args)
        return _installs(f"{name} install", "python", rest) if verb == "install" else []
    if name in {"npx", "bunx", "pnpx"}:
        return _run_target(name, "js", args, RUNNER_VALUES["js"], depth, deadline)
    if name == "uvx":
        return _run_target(name, "python", args, RUNNER_VALUES["uv"], depth, deadline)
    verb, rest = _subcommand(name, args)
    if verb is None:
        return []
    label = f"{name} {verb}"
    if name == "npm":
        if verb in {"install", "i", "add"}:
            return _installs(label, "js", rest)
        if verb in {"exec", "x"}:
            return _run_target(label, "js", rest, RUNNER_VALUES["js"], depth, deadline)
        if verb in {"run", "run-script"}:
            return _script_or_bin(label, "js", rest[_skip_options(rest, set()):], depth, deadline)
        if verb in {"init", "create"}:
            return _initializer(label, rest)
    elif name == "pnpm":
        if verb in {"add", "install", "i"}:
            return _installs(label, "js", rest)
        if verb in {"dlx", "exec"}:
            return _run_target(label, "js", rest, RUNNER_VALUES["js"], depth, deadline)
        if verb == "create":
            return _initializer(label, rest)
        if verb == "run":
            return _script_or_bin(label, "js", rest[_skip_options(rest, set()):], depth, deadline)
        return _script_or_bin(name, "js", [verb] + rest, depth, deadline)
    elif name == "yarn":
        if verb == "add":
            return _installs(label, "js", rest)
        if verb == "global" and rest[:1] == ["add"]:
            return _installs("yarn global add", "js", rest[1:])
        if verb in {"dlx", "exec"}:
            return _run_target(label, "js", rest, RUNNER_VALUES["js"], depth, deadline)
        if verb == "create":
            return _initializer(label, rest)
        if verb == "workspace" and len(rest) > 1:
            return _package_manager_findings("yarn", rest[1:], depth + 1, deadline)
        if verb == "run":
            return _script_or_bin(label, "js", rest[_skip_options(rest, set()):], depth, deadline)
        return _script_or_bin(name, "js", [verb] + rest, depth, deadline)
    elif name == "bun":
        if verb in {"add", "install", "i"}:
            return _installs(label, "js", rest)
        if verb == "x":
            return _run_target(label, "js", rest, RUNNER_VALUES["js"], depth, deadline)
        if verb == "create":
            return _initializer(label, rest)
        if verb == "run":
            target = rest[_skip_options(rest, set()):]
            if target and ("/" in target[0] or SCRIPT_SUFFIX.search(target[0])):
                return _interpreted(name, target[0])
            return _script_or_bin(label, "js", target, depth, deadline)
        if "/" in verb or SCRIPT_SUFFIX.search(verb):
            return _interpreted(name, verb)
    elif name == "uv":
        if verb == "pip" and rest[:1] == ["install"]:
            return _installs("uv pip install", "python", rest[1:])
        if verb == "tool" and rest[:1] == ["install"]:
            return _installs("uv tool install", "python", rest[1:])
        if verb == "tool" and rest[:1] == ["run"]:
            return _run_target("uv tool run", "python", rest[1:], RUNNER_VALUES["uv"], depth,
                               deadline)
        if verb == "add":
            return _installs(label, "python", rest)
        if verb == "run":
            return _run_target(label, "python", rest, RUNNER_VALUES["uv"], depth, deadline)
    elif name == "pipx":
        if verb == "install":
            return _installs(label, "python", rest)
        if verb == "run":
            return _run_target(label, "python", rest, RUNNER_VALUES["pipx"], depth, deadline)
    elif name in {"poetry", "pdm", "rye", "pipenv", "pixi"}:
        if verb in {"add", "install"} and name != "poetry" or (name == "poetry" and verb == "add"):
            return _installs(label, "python", rest)
        if verb == "run":
            values = RUNNER_VALUES.get(name, set())
            start = _skip_options(rest, values)
            return (_run_target(label, "python", rest, values, depth, deadline)
                    or (_named_script(label, rest[start]) if start < len(rest) else []))
    elif name == "hatch":
        if verb == "run":
            start = _skip_options(rest, set())
            return (_run_target(label, "python", rest, set(), depth, deadline)
                    or (_named_script(label, rest[start]) if start < len(rest) else []))
    elif name in {"conda", "mamba"}:
        if verb == "install":
            return _installs(label, "python", rest)
        if verb == "run":
            return _run_target(label, None, rest, RUNNER_VALUES["conda"], depth, deadline)
    elif name == "bundle":
        if verb == "add":
            return _installs(label, "ruby", rest)
        if verb == "exec":
            return _run_target(label, "ruby", rest, RUNNER_VALUES["bundle"], depth, deadline)
    elif name == "gem":
        if verb == "install":
            return _installs(label, "ruby", rest)
    elif name == "composer":
        if verb == "require":
            return _installs(label, "php", rest)
        if verb == "global" and rest[:1] == ["require"]:
            return _installs("composer global require", "php", rest[1:])
        if verb == "exec":
            return _run_target(label, "php", rest, set(), depth, deadline)
        if verb in {"run", "run-script"}:
            return _script_or_bin(label, "php", rest[_skip_options(rest, set()):], depth,
                                  deadline)
        return _named_script(name, verb)
    elif name == "cargo":
        if verb in {"install", "binstall"}:
            return _installs(label, "rust", rest)
    elif name == "go":
        if verb in {"install", "get"}:
            return _installs(label, "go", rest)
    elif name == "dotnet":
        if verb == "tool" and rest[:1] in (["install"], ["update"]):
            return _installs(f"dotnet tool {rest[0]}", "dotnet", rest[1:])
    elif name in {"brew", "apt", "apt-get"}:
        if verb == "install":
            return _installs(label, "os", rest)
    elif name == "mise" and verb in {"exec", "x"}:
        command = rest[rest.index("--") + 1:] if "--" in rest else rest
        return _run_target(label, None, command, set(), depth, deadline)
    elif name in {"pyenv", "rbenv", "asdf"} and verb == "exec":
        return _run_target(label, None, rest, set(), depth, deadline)
    elif name == "direnv" and verb == "exec" and rest:
        return _run_target(label, None, rest[1:], set(), depth, deadline)
    elif name == "corepack" and verb in {"npm", "pnpm", "yarn"}:
        return _package_manager_findings(verb, rest, depth + 1, deadline)
    return []


def _target_runner_findings(name, args):
    """make, just and task targets, tox environments and nox sessions named for the method."""
    if name in {"make", "gmake"}:
        values = {"-C", "--directory", "-f", "--file", "--makefile", "-I", "--include-dir",
                  "-o", "--old-file", "-W", "--what-if", "--assume-new", "-l"}
        names, i = [], 0
        while i < len(args):
            arg = args[i]
            if arg.startswith("-"):
                i += 2 if arg in values else 1
                if arg == "-j" and i < len(args) and args[i].isdigit():
                    i += 1
                continue
            if "=" not in arg:
                names.append(arg)
            i += 1
    elif name == "just":
        start = _skip_options(args, {"-f", "--justfile", "-d", "--working-directory",
                                     "--dotenv-filename", "--dotenv-path", "--shell",
                                     "--shell-arg", "--color"})
        names = args[start:start + 1]
    elif name == "task":
        start = _skip_options(args, {"-d", "--dir", "-t", "--taskfile", "-o", "--output",
                                     "-c", "--color", "--concurrency"})
        rest = args[start:]
        names = [a for a in (rest[:rest.index("--")] if "--" in rest else rest)
                 if "=" not in a and not a.startswith("-")]
    elif name == "tox":
        names = []
        for i, arg in enumerate(args):
            if arg in {"-e", "--env"} and i + 1 < len(args):
                names += args[i + 1].split(",")
            elif arg.startswith("-e") and len(arg) > 2 and not arg.startswith("--"):
                names += arg[2:].lstrip("=").split(",")
            elif arg.startswith("--env="):
                names += arg[len("--env="):].split(",")
    elif name == "nox":
        names, collecting = [], False
        for arg in args:
            if arg in {"-s", "--session", "--sessions", "-e"}:
                collecting = True
                continue
            if arg.startswith("-"):
                collecting = False
                continue
            if collecting:
                names.append(arg)
    else:
        return None
    label = {"tox": "tox -e", "nox": "nox -s"}.get(name, name)
    for target in names:
        found = _named_script(label, target)
        if found:
            return found
    return []


def _launcher_findings(name, args, depth, deadline):
    """watch, su, script, nix-shell, nix, ssh, find and parallel run a command they are given."""
    if name == "watch":
        start = _skip_options(args, {"-n", "--interval", "-q", "--equexit"})
        return _scan(" ".join(args[start:]), depth + 1, deadline) if start < len(args) else []
    if name == "su":
        body = _value_after(args, {"-c", "--command", "--session-command"})
        return _scan(body, depth + 1, deadline) if body is not None else []
    if name == "script":
        body = _value_after(args, {"-c", "--command"})
        if body is not None:
            return _scan(body, depth + 1, deadline)
        start = _skip_options(args, {"-F", "-t", "-T"})
        command = args[start + 1:]
        return _findings_for(command, depth + 1, deadline) if command else []
    if name == "nix-shell":
        body = _value_after(args, {"--run", "--command"})
        return _scan(body, depth + 1, deadline) if body is not None else []
    if name == "nix":
        if args[:1] in (["develop"], ["shell"]):
            for marker in ("-c", "--command"):
                if marker in args:
                    return _findings_for(args[args.index(marker) + 1:], depth + 1, deadline)
        return []
    if name == "ssh":
        i = 0
        while i < len(args) and args[i].startswith("-") and args[i] != "--":
            letters = args[i][1:]
            i += 1
            for at, letter in enumerate(letters):
                if letter in "BbcDEeFIiJLlmOoPpQRSWw":
                    i += 0 if letters[at + 1:] else 1
                    break
        if i < len(args) and args[i] == "--":
            i += 1
        command = args[i + 1:]
        return _scan(" ".join(command), depth + 1, deadline) if command else []
    if name == "find":
        found, i = [], 0
        while i < len(args):
            if args[i] in {"-exec", "-execdir", "-ok", "-okdir"}:
                end = i + 1
                while end < len(args) and args[end] not in {";", "+"}:
                    end += 1
                found.extend(_findings_for(args[i + 1:end], depth + 1, deadline))
                i = end
            i += 1
        return found
    if name == "parallel":
        start = _skip_options(args, {"-j", "--jobs", "-S", "--sshlogin", "-a", "--arg-file",
                                     "--colsep", "-d", "--delimiter", "-I", "--joblog",
                                     "--results", "--tmpdir", "-n", "--max-args", "-N", "-L",
                                     "--max-lines", "--timeout", "--delay", "--retries", "-E",
                                     "--halt", "--memfree", "--load"})
        command = []
        for arg in args[start:]:
            if arg in {":::", "::::", ":::+", "::::+"}:
                break
            command.append(arg)
        if len(command) == 1 and re.search(r"\s", command[0]):
            return _scan(command[0], depth + 1, deadline)
        return _findings_for(command, depth + 1, deadline) if command else []
    return None


def _env_split_string(args):
    """`env -S VALUE` and `env --split-string=VALUE` run VALUE as a command line."""
    i = 0
    while i < len(args) and args[i].startswith("-") and args[i] != "-":
        arg = args[i]
        if arg in {"-S", "--split-string"} and i + 1 < len(args):
            return " ".join(args[i + 1:])
        if arg.startswith("--split-string="):
            return " ".join([arg[len("--split-string="):]] + args[i + 1:])
        if arg.startswith("-S") and len(arg) > 2:
            return " ".join([arg[2:]] + args[i + 1:])
        i += 2 if arg in words.WRAPPERS["env"] else 1
    return None


def _strip(tokens):
    """-> (command words, nested source): keywords, assignments and wrappers removed."""
    rest = list(tokens)
    for _ in range(32):
        before = rest
        # `time` stays for _command_word, which also skips its options.
        while rest and rest[0] in tokenizer.CONTROL_KEYWORDS and rest[0] != "time":
            rest = rest[1:]
        if rest and _base(rest[0]) == "env":
            nested = _env_split_string(rest[1:])
            if nested is not None:
                return [], nested
        _assigns, rest = words._command_word(rest)
        if rest and rest[0] in {"builtin", "chronic", "-"}:
            rest = rest[1:]
        elif rest and rest[0] == "repeat":
            rest = rest[2:]
        elif rest and rest[0] == "taskset":
            start = _skip_options(rest[1:], set())
            rest = rest[1 + start + 1:]
        elif rest and rest[0] == "flock":
            body = _value_after(rest[1:], {"-c", "--command"})
            if body is not None:
                return [], body
            start = _skip_options(rest[1:], {"-w", "--wait", "--timeout", "-E",
                                             "--conflict-exit-code"})
            rest = rest[1 + start + 1:]
        if rest and rest[0].startswith("=") and len(rest[0]) > 1:
            rest = [rest[0][1:]] + rest[1:]            # zsh `=cmd` is a PATH lookup of cmd
        if rest == before:
            break
    return rest, None


def _findings_for(tokens, depth, deadline):
    """Findings for one simple command, as (verdict, text) pairs naming what was found."""
    if depth > MAX_DEPTH:
        return []
    rest, nested = _strip(tokens)
    if nested is not None:
        return _scan(nested, depth + 1, deadline)
    if not rest:
        return []
    word, args = rest[0], rest[1:]
    if "$" in word:
        return [("expand", f"the command word `{word}` is chosen at run time")]
    name = _base(word).lower()
    if name in words.SHELLS:
        for index, arg in enumerate(args):
            if arg.endswith("<<<") and index + 1 < len(args):
                return _scan(args[index + 1], depth + 1, deadline)
            if re.fullmatch(r"-[A-Za-z]*c[A-Za-z]*", arg):
                body = index + 2 if args[index + 1:index + 2] == ["--"] else index + 1
                return _scan(args[body], depth + 1, deadline) if body < len(args) else []
        return []
    if name == "eval":
        return _scan(" ".join(args), depth + 1, deadline) if args else []
    if name == "alias":
        found = []
        for arg in args:
            if "=" in arg and not arg.startswith("-"):
                found.extend(_scan(arg.split("=", 1)[1], depth + 1, deadline))
        return found
    if _tool_at_command(word):
        return [_deny(f"`{name}` is a mutation-testing tool")]
    for step in (_launcher_findings(name, args, depth, deadline),
                 _target_runner_findings(name, args),
                 _interpreter_findings(name, args)):
        if step is not None:
            return step
    return (_package_manager_findings(name, args, depth, deadline)
            or _build_tool_findings(name, args))


def _scan(text, depth=0, deadline=None):
    if depth > MAX_DEPTH:
        return []
    if deadline is not None and time.monotonic() >= deadline:
        raise BudgetExhausted()
    try:
        simples = tokenizer.split_commands(text, _deadline=deadline)
    except Exception:                              # CommandParseError and kin
        if deadline is not None and time.monotonic() >= deadline:
            raise BudgetExhausted()
        match = TOOL_WORD.search(text)
        return [("unreadable", f"`{match.group(0)}` appears in command source the tokenizer "
                               "cannot read")] if match else []
    found = []
    for simple in simples:
        found.extend(_findings_for([word for word, _quoting in simple], depth, deadline))
    return found


def decide(command, _deadline=None):
    """-> (decision, reason). Deny a modelled mutation-testing tool use; ask when unsure."""
    if not isinstance(command, str):
        return "allow", ""
    normalized = re.sub(r"[\\'\"]", "", command.lower())
    if not any(needle in normalized for needle in NEEDLES):
        return "allow", ""
    try:
        found = _scan(command, deadline=_deadline)
    except BudgetExhausted:
        return "ask", ("mutation_testing: the decision budget ran out before this command was "
                       "checked for a mutation-testing tool")
    denied = [text for verdict, text in found if verdict == "deny"]
    if denied:
        return "deny", REASON.format(found="; ".join(dict.fromkeys(denied)))
    unsure = [text for verdict, text in found if verdict == "unreadable"]
    if not unsure and TOOL_WORD.search(command):
        unsure = [text for verdict, text in found if verdict == "expand"]
    if unsure:
        return "ask", ASK_REASON.format(found="; ".join(dict.fromkeys(unsure)))
    return "allow", ""


FIXTURES = [
    # Python
    ("RED  PY: mutmut at command position", "mutmut run", "deny"),
    ("RED  PY: mutmut results lists survivors", "mutmut results", "deny"),
    ("RED  PY: mutmut through uvx", "uvx mutmut run --paths-to-mutate src", "deny"),
    ("RED  PY: mutmut through pipx run", "pipx run mutmut run", "deny"),
    ("RED  PY: python -m mutmut", "python -m mutmut run", "deny"),
    ("RED  PY: versioned python -m cosmic_ray", "python3.12 -m cosmic_ray init cr.toml s.sqlite", "deny"),
    ("RED  PY: cosmic-ray", "cosmic-ray exec cr.toml s.sqlite", "deny"),
    ("RED  PY: cosmic-ray's report command", "cr-report s.sqlite", "deny"),
    ("RED  PY: mutatest", "mutatest -s src", "deny"),
    ("RED  PY: MutPy's mut.py", "mut.py --target calc --unit-test test_calc", "deny"),
    ("RED  PY: mutahunter", "mutahunter run --test-command pytest", "deny"),
    ("RED  PY: pip install mutmut", "pip install mutmut", "deny"),
    ("RED  PY: a versioned pip", "pip3.12 install mutmut", "deny"),
    ("RED  PY: pip install from a VCS URL", "pip install git+https://github.com/boxed/mutmut", "deny"),
    ("RED  PY: python -m pip install a pinned mutmut", "python3 -m pip install --user 'mutmut==2.4.4'", "deny"),
    ("RED  PY: uv add cosmic-ray", "uv add --dev cosmic-ray", "deny"),
    ("RED  PY: uv tool install mutmut", "uv tool install mutmut", "deny"),
    ("RED  PY: uv pip install mutatest", "uv pip install mutatest", "deny"),
    ("RED  PY: poetry add mutatest", "poetry add --group dev mutatest", "deny"),
    ("RED  PY: pipenv install", "pipenv install --dev mutmut", "deny"),
    ("RED  PY: poetry run mutmut", "poetry run mutmut run", "deny"),
    ("RED  PY: python -I -m", "python3 -I -m cosmic_ray init cr.toml s.sqlite", "deny"),
    ("RED  PY: python -X before -m", "python -X dev -m mutmut run", "deny"),
    ("RED  PY: an attached -mMOD", "python -mmutmut run", "deny"),
    ("RED  PY: combined flags ending in m", "python3 -Im mutmut run", "deny"),
    ("RED  PY: a tool submodule", "python3 -m mutmut.__main__ run", "deny"),
    # JavaScript / TypeScript
    ("RED  JS: npx stryker", "npx stryker run", "deny"),
    ("RED  JS: npx a pinned scoped Stryker package", "npx -y @stryker-mutator/core@8.2.6 run", "deny"),
    ("RED  JS: npx --package names a Stryker package", "npx -p @stryker-mutator/core stryker run", "deny"),
    ("RED  JS: npx --call body", "npx -c 'stryker run'", "deny"),
    ("RED  JS: pnpm dlx stryker", "pnpm dlx stryker run", "deny"),
    ("RED  JS: npm exec stryker", "npm exec -- stryker run", "deny"),
    ("RED  JS: bunx stryker", "bunx stryker run", "deny"),
    ("RED  JS: npm install Stryker packages", "npm install --save-dev @stryker-mutator/core @stryker-mutator/jest-runner", "deny"),
    ("RED  JS: yarn add a Stryker checker", "yarn add -D @stryker-mutator/typescript-checker", "deny"),
    ("RED  JS: yarn global add stryker-cli", "yarn global add stryker-cli", "deny"),
    ("RED  JS: node runs the installed stryker bin", "node node_modules/.bin/stryker run", "deny"),
    ("RED  JS: node -r before the script", "node -r ts-node/register node_modules/.bin/stryker run", "deny"),
    ("RED  JS: yarn runs a bin", "yarn stryker run", "deny"),
    ("RED  JS: yarn run of a bin", "yarn run stryker run", "deny"),
    ("RED  JS: yarn exec", "yarn exec stryker run", "deny"),
    ("RED  JS: yarn workspace", "yarn workspace web stryker run", "deny"),
    ("RED  JS: pnpm runs a bin", "pnpm stryker run", "deny"),
    ("RED  JS: bun x", "bun x stryker run", "deny"),
    ("RED  JS: bun run", "bun run stryker", "deny"),
    ("RED  JS: npm run-script", "npm run-script stryker", "deny"),
    ("RED  JS: npm init runs create-stryker", "npm init stryker", "deny"),
    ("RED  JS: a versioned initializer", "npm init stryker@latest", "deny"),
    ("RED  JS: yarn create", "yarn create stryker", "deny"),
    ("RED  JS: pnpm create", "pnpm create stryker", "deny"),
    ("RED  JS: deno runs an npm specifier", "deno run -A npm:stryker-cli run", "deny"),
    # JVM
    ("RED  JVM: maven PIT goal", "mvn org.pitest:pitest-maven:mutationCoverage", "deny"),
    ("RED  JVM: maven wrapper PIT goal", "./mvnw -DwithHistory test-compile org.pitest:pitest-maven:mutationCoverage", "deny"),
    ("RED  JVM: mvnd PIT goal", "mvnd org.pitest:pitest-maven:mutationCoverage", "deny"),
    ("RED  JVM: maven PIT profile", "mvn -P pitest verify", "deny"),
    ("RED  JVM: gradle wrapper pitest task", "./gradlew pitest", "deny"),
    ("RED  JVM: gradle project pitest task", "gradle :app:pitest", "deny"),
    ("RED  JVM: sbt stryker", "sbt stryker", "deny"),
    ("RED  JVM: java runs the PIT report class", "java -cp target/classes org.pitest.mutationtest.commandline.MutationCoverageReport --reportDir r", "deny"),
    ("RED  JVM: java runs the PIT jar", "java -jar pitest-command-line-1.15.0.jar --reportDir r", "deny"),
    # .NET
    ("RED  NET: dotnet stryker", "dotnet stryker", "deny"),
    ("RED  NET: dotnet tool install dotnet-stryker", "dotnet tool install -g dotnet-stryker", "deny"),
    ("RED  NET: dotnet tool run dotnet-stryker", "dotnet tool run dotnet-stryker", "deny"),
    # Rust
    ("RED  RS: cargo mutants", "cargo mutants", "deny"),
    ("RED  RS: cargo with a toolchain before mutants", "cargo +nightly mutants --in-place", "deny"),
    ("RED  RS: cargo -Z before mutants", "cargo -Z unstable-options mutants", "deny"),
    ("RED  RS: cargo install cargo-mutants", "cargo install --locked cargo-mutants", "deny"),
    ("RED  RS: cargo install --git", "cargo install --git https://github.com/sourcefrog/cargo-mutants", "deny"),
    ("RED  RS: cargo mutagen", "cargo mutagen", "deny"),
    # Go
    ("RED  GO: go-mutesting", "go-mutesting ./...", "deny"),
    ("RED  GO: go install go-mutesting", "go install github.com/zimmski/go-mutesting/cmd/go-mutesting@latest", "deny"),
    ("RED  GO: gremlins", "gremlins unleash", "deny"),
    ("RED  GO: go run gremlins", "go run github.com/go-gremlins/gremlins/cmd/gremlins@latest unleash", "deny"),
    ("RED  GO: go tool gremlins", "go tool gremlins unleash", "deny"),
    # PHP
    ("RED  PHP: vendor infection", "vendor/bin/infection --threads=4", "deny"),
    ("RED  PHP: php runs the infection phar", "php infection.phar", "deny"),
    ("RED  PHP: php -d before the script", "php -d memory_limit=-1 vendor/bin/infection", "deny"),
    ("RED  PHP: phpdbg", "phpdbg -qrr vendor/bin/infection --threads=4", "deny"),
    ("RED  PHP: composer require infection", "composer require --dev infection/infection", "deny"),
    # Ruby
    ("RED  RB: bundle exec mutant", "bundle exec mutant run --use rspec 'Foo*'", "deny"),
    ("RED  RB: gem install mutant-rspec", "gem install mutant-rspec", "deny"),
    # C / C++
    ("RED  C: a versioned mull runner", "mull-runner-17 ./tests", "deny"),
    ("RED  C: mull-runner", "mull-runner ./build/tests", "deny"),
    ("RED  C: a versioned mull reporter", "mull-reporter-17 --reporters Elements", "deny"),
    ("RED  C: apt-get install a versioned mull", "apt-get install -y mull-17", "deny"),
    ("RED  C: dextool mutate", "dextool mutate analyze", "deny"),
    ("RED  C: universalmutator's mutate", "mutate src/foo.c", "deny"),
    ("RED  C: pip install universalmutator", "pip install universalmutator", "deny"),
    # this harness's former mutation machinery
    ("RED  HARNESS: the former mutation receipt writer", "python3 tools/write-mutation-receipt.py --shard-index 0 --shard-count 4", "deny"),
    ("RED  HARNESS: the former survivor enumerator", "python3 instruments/enumerate_survivors.py hooks/announced_work_guard.py", "deny"),
    # package runners with their own options
    ("RED  RUNNER: uv run --directory", "uv run --directory src mutmut run", "deny"),
    ("RED  RUNNER: uv run --python", "uv run --python 3.12 mutmut run", "deny"),
    ("RED  RUNNER: uv run --group", "uv run --group dev mutmut run", "deny"),
    ("RED  RUNNER: uv run --with a listed package", "uv run --with mutmut python -m pytest", "deny"),
    ("RED  RUNNER: uvx --from", "uvx --from mutmut mutmut run", "deny"),
    ("RED  RUNNER: poetry global option before run", "poetry -C sub run mutmut run", "deny"),
    ("RED  RUNNER: pnpm --filter before exec", "pnpm --filter web exec stryker run", "deny"),
    ("RED  RUNNER: npm workspace before exec", "npm -w app exec stryker run", "deny"),
    ("RED  RUNNER: conda run -n", "conda run -n dev mutmut run", "deny"),
    ("RED  RUNNER: pixi run", "pixi run mutmut run", "deny"),
    ("RED  RUNNER: rye run", "rye run mutmut run", "deny"),
    ("RED  RUNNER: mise exec --", "mise exec python@3.12 -- mutmut run", "deny"),
    ("RED  RUNNER: pyenv exec", "pyenv exec mutmut run", "deny"),
    ("RED  RUNNER: direnv exec", "direnv exec . mutmut run", "deny"),
    ("RED  RUNNER: corepack pnpm dlx", "corepack pnpm dlx stryker run", "deny"),
    # scripts, targets, environments and sessions named for the method
    ("RED  SCRIPT: npm script", "npm run test:mutation", "deny"),
    ("RED  SCRIPT: pnpm script", "pnpm test:mutation", "deny"),
    ("RED  SCRIPT: make target", "make mutation", "deny"),
    ("RED  SCRIPT: tox environment", "tox -e mutmut", "deny"),
    ("RED  SCRIPT: tox environment list", "tox -e py312,mutation", "deny"),
    ("RED  SCRIPT: nox session", "nox -s mutation", "deny"),
    ("RED  SCRIPT: just recipe", "just mutate", "deny"),
    ("RED  SCRIPT: hatch environment script", "hatch run test:mutmut", "deny"),
    ("RED  SCRIPT: composer script", "composer run-script mutation", "deny"),
    # wrappers, keywords and composition
    ("RED  WRAP: env assignment, timeout and a prior command", "cd repo && FOO=1 timeout 600 mutmut run", "deny"),
    ("RED  WRAP: sudo -u", "sudo -u ci mutmut run", "deny"),
    ("RED  WRAP: an absolute tool path", "/usr/local/bin/mutmut run", "deny"),
    ("RED  WRAP: xargs", "xargs -n1 mutmut run < files.txt", "deny"),
    ("RED  WRAP: env before python -m", "env PYTHONPATH=src python -m mutmut run", "deny"),
    ("RED  WRAP: taskset", "taskset -c 0 mutmut run", "deny"),
    ("RED  WRAP: chronic", "chronic mutmut run", "deny"),
    ("RED  WRAP: zsh repeat and builtin", "repeat 2 builtin command mutmut run", "deny"),
    ("RED  WRAP: zsh equals lookup", "=mutmut run", "deny"),
    ("RED  KEYWORD: if/then body", "if true; then mutmut run; fi", "deny"),
    ("RED  KEYWORD: for/do body", "for i in 1; do cargo mutants; done", "deny"),
    ("RED  KEYWORD: while/do body", "while true; do npx stryker run; break; done", "deny"),
    ("RED  KEYWORD: until condition", "until mutmut run; do sleep 1; done", "deny"),
    ("RED  KEYWORD: a negated command", "! mutmut run", "deny"),
    ("RED  KEYWORD: a negated if condition", "if ! cargo mutants; then echo fail; fi", "deny"),
    ("RED  KEYWORD: time with an option", "time -p mutmut run", "deny"),
    ("RED  KEYWORD: zsh noglob", "noglob mutmut run", "deny"),
    ("RED  KEYWORD: coproc", "coproc mutmut run", "deny"),
    ("RED  LAUNCH: watch", "watch -n 5 mutmut results", "deny"),
    ("RED  LAUNCH: su -c", "su ci -c 'mutmut run'", "deny"),
    ("RED  LAUNCH: script with a command", "script -q /dev/null mutmut run", "deny"),
    ("RED  LAUNCH: find -execdir", "find . -name setup.cfg -execdir mutmut run {} +", "deny"),
    ("RED  LAUNCH: parallel", "parallel mutmut run ::: a b", "deny"),
    ("RED  LAUNCH: flock -c", "flock /tmp/m.lock -c 'mutmut run'", "deny"),
    ("RED  LAUNCH: nix-shell --run", "nix-shell -p python3Packages.mutmut --run 'mutmut run'", "deny"),
    ("RED  LAUNCH: nix develop -c", "nix develop -c mutmut run", "deny"),
    ("RED  LAUNCH: ssh", "ssh ci 'mutmut run'", "deny"),
    ("RED  NEST: bash -lc body", "bash -lc 'mutmut run'", "deny"),
    ("RED  NEST: bash -c -- body", "bash -c -- 'mutmut run'", "deny"),
    ("RED  NEST: zsh -c body through npx", 'zsh -c "npx stryker run"', "deny"),
    ("RED  NEST: a here-string fed to bash", "bash <<< 'mutmut run'", "deny"),
    ("RED  NEST: eval body", "eval 'cargo mutants'", "deny"),
    ("RED  NEST: env -S", "env -S 'mutmut run'", "deny"),
    ("RED  NEST: an alias value", "alias mm=mutmut; mm run", "deny"),
    ("RED  NEST: an alias expanded through eval", "alias mm='npx stryker'; eval 'mm run'", "deny"),
    ("RED  NEST: command substitution", 'echo "$(mutmut results)"', "deny"),
    ("RED  NEST: heredoc fed to bash", "bash <<'EOF'\nmutmut run\nEOF", "deny"),
    ("RED  NEST: second command of a list", "git status && mutmut run", "deny"),
    ("RED  QUOTE: a backslash inside the name", "str\\yker run", "deny"),
    ("RED  QUOTE: empty quotes inside the name", "npx stry''ker run", "deny"),
    ("RED  DATA: backticks inside double quotes run the tool", 'git commit -m "docs: drop `mutmut run` from README"', "deny"),
    ("RED  DATA: an unquoted heredoc runs its substitutions", "cat > docs/x.md <<EOF\nRun `mutmut run` no more\nEOF", "deny"),
    ("ASK  EXPAND: a variable command word in a command naming a tool", "T=mutmut; $T run", "ask"),
    ("ASK  EXPAND: a loop variable as the command word", 'for t in mutmut; do "$t" run; done', "ask"),
    # mentions as data and other senses of the word stay allowed
    ("GREEN DATA: grep for a tool name", "grep -rn mutmut .", "allow"),
    ("GREEN DATA: rg for tool names", "rg -n 'stryker|pitest' docs/", "allow"),
    ("GREEN DATA: echo a tool command", "echo mutmut run", "allow"),
    ("GREEN DATA: printf a tool command", "printf '%s\\n' 'cargo mutants'", "allow"),
    ("GREEN DATA: cat a report", "cat mutation-report.txt", "allow"),
    ("GREEN DATA: git log -S", "git log -S mutmut --oneline", "allow"),
    ("GREEN DATA: git grep", "git grep -n -P 'mutmut|stryker' -- .", "allow"),
    ("GREEN DATA: a commit message", "git commit -m 'remove mutmut and the mutation sweep'", "allow"),
    ("GREEN DATA: git rm the former tools", "git rm tools/write-mutation-receipt.py instruments/enumerate_survivors.py", "allow"),
    ("GREEN DATA: heredoc to cat is data", "cat > notes.md <<'EOF'\nmutmut run\nEOF", "allow"),
    ("GREEN DATA: a quoted heredoc keeps backticks as text", "cat > docs/x.md <<'EOF'\nRun `mutmut run` no more\nEOF", "allow"),
    ("GREEN DATA: a lookup is not a run", "which mutmut; command -v stryker", "allow"),
    ("GREEN DATA: pip show", "pip show mutmut", "allow"),
    ("GREEN DATA: grep counts survivors in a file", "grep -c survivors report.json", "allow"),
    ("GREEN DATA: a grep inside a for loop", 'for f in docs/*.md; do grep -n mutmut "$f"; done', "allow"),
    ("GREEN DATA: a lookup inside an if", "if command -v mutmut; then echo present; fi", "allow"),
    ("GREEN DATA: watch of a grep", "watch -n 5 'grep -c mutmut log.txt'", "allow"),
    ("GREEN DATA: ssh running a grep", "ssh ci 'grep -rn mutmut /srv/docs'", "allow"),
    ("GREEN DATA: an alias naming no tool", "alias ll='ls -la'; ll mutants/", "allow"),
    ("GREEN DATA: a variable command word in a command naming no tool", "T=pytest; $T -k mutation", "allow"),
    ("GREEN DATA: uv run of a script naming a tool as data", "uv run python tools/check.py --name mutmut", "allow"),
    ("GREEN DATA: uv run pytest selecting by keyword", "uv run pytest -k mutant", "allow"),
    ("GREEN DATA: python -m pytest selecting by a tool name", "python3 -I -m pytest -k mutmut", "allow"),
    ("GREEN DATA: yarn why names a tool", "yarn why stryker", "allow"),
    ("GREEN REMOVE: pip uninstall", "pip uninstall -y mutmut", "allow"),
    ("GREEN REMOVE: npm uninstall", "npm uninstall @stryker-mutator/core", "allow"),
    ("GREEN REMOVE: cargo uninstall", "cargo uninstall cargo-mutants", "allow"),
    ("GREEN REMOVE: find -exec of a cache removal", "find . -name '.mutmut-cache' -prune -exec rm -rf {} +", "allow"),
    ("GREEN SENSE: a GraphQL mutation", "gh api graphql -f query='mutation { addStar(input: {starrableId: \"x\"}) { clientMutationId } }'", "allow"),
    ("GREEN SENSE: a GraphQL codegen script", "npm run codegen:mutations", "allow"),
    ("GREEN SENSE: Mutagen file sync", "mutagen sync list", "allow"),
    ("GREEN SENSE: a mutex test target", "make mutex-test", "allow"),
    ("GREEN SENSE: make with a variable named for the method", "make test MUTATION=0", "allow"),
    ("GREEN SENSE: tox ordinary environments", "tox -e py312,lint", "allow"),
    ("GREEN SENSE: pytest on immutable types", "pytest tests/test_mutations.py -k immutable", "allow"),
    ("GREEN SENSE: a container image name", "docker run --rm infection-tracker:latest", "allow"),
    ("GREEN SENSE: this guard's own selftest", "python3 hooks/guards/mutation_testing_guard.py --selftest", "allow"),
    ("GREEN SENSE: ordinary test runners", "mvn test && ./gradlew test && cargo test && dotnet test && go test ./...", "allow"),
    ("GREEN SENSE: npm init without an initializer", "npm init -y", "allow"),
    ("GREEN SENSE: the npm package named mutant", "npm install mutant", "allow"),
    ("GREEN SENSE: the PyPI package named mutant", "pip install mutant", "allow"),
    ("GREEN SENSE: a test class named for PIT config", "mvn test -Dtest=PitestConfigTest", "allow"),
    ("GREEN SENSE: a module named for a PIT report", "mvn test -pl pitest-report-parser", "allow"),
    ("GREEN SENSE: gradle excluding the pitest task", "./gradlew build -x pitest", "allow"),
    ("GREEN SENSE: an sbt command that starts with stryker", "sbt strykerConfig", "allow"),
    ("GREEN SENSE: node runs a project file named for a monkey-test library", "node tests/gremlins.js", "allow"),
    ("GREEN SENSE: node runs a simulation", "node sim/infection.js --days 30", "allow"),
    ("GREEN SENSE: ruby runs a project script", "ruby scripts/mutate.rb", "allow"),
    ("GREEN SENSE: bun runs a project script", "bun scripts/mutate.ts", "allow"),
    ("GREEN SENSE: python runs a project script", "python3 tools/mutate.py fixtures/", "allow"),
    ("GREEN SENSE: a project script named mutate", "./scripts/mutate users.csv", "allow"),
    ("GREEN SENSE: a project bin named infection", "./bin/infection --dry-run", "allow"),
]

# Stated limits, each decided allow today and printed as out of scope.
OUT_OF_SCOPE = [
    ("a variant built by arbitrary Python names no tool",
     "python3 - <<'EOF'\nsrc = open('m.py').read().replace('+= 1', '+= 0')\n"
     "exec(compile(src, 'm.py', 'exec'))\nEOF"),
    ("a tool launched from code an interpreter receives",
     "python3 -c \"import subprocess; subprocess.run(['mutmut', 'run'])\""),
    ("a tool linked under another name",
     "ln -s \"$(command -v mutmut)\" ./mm && ./mm run"),
    ("an alias or function defined in an earlier command", "mm run --paths-to-mutate src"),
    ("a script or target whose name does not say what it runs", "npm run qa -- --mutate src"),
    ("text piped into a shell's stdin", "echo 'mutmut run' | sh"),
    ("a container image's entrypoint", "docker run --rm ghcr.io/stryker-mutator/stryker run"),
    ("an install from a requirements file that lists a tool",
     "pip install -r requirements-dev.txt"),
]


def _graded(command, deadline=None):
    try:
        return decide(command, _deadline=deadline)
    except BaseException as exc:
        return "<error>", f"{type(exc).__name__}: {exc}"


def selftest():
    total = failures = 0

    def check(ok, label):
        nonlocal total, failures
        total += 1
        failures += (not ok)
        print(f"  {'PASS' if ok else 'FAIL'} {label}")

    if not FIXTURES:
        print("  NO FIXTURES — a suite that cannot go red proves nothing")
        return 2
    print(f"scan set: {len(FIXTURES)} fixtures "
          f"({sum(1 for f in FIXTURES if f[2] == 'deny')} must-deny, "
          f"{sum(1 for f in FIXTURES if f[2] == 'ask')} must-ask, "
          f"{sum(1 for f in FIXTURES if f[2] == 'allow')} must-allow), "
          f"{len(OUT_OF_SCOPE)} stated out-of-scope spellings")
    for label, command, want in FIXTURES:
        got, _reason = _graded(command)
        check(got == want, f"want={want:<5} got={got:<5} {label}")
    reasons = [_graded(command)[1] for _label, command, want in FIXTURES if want == "deny"]
    check(bool(reasons) and all(
        "Mutation testing is banned in every project and runtime" in reason
        and "the head's regression test failing against the parent commit's code" in reason
        and "adversarial review" in reason and "single-quote it" in reason
        for reason in reasons),
        f"every deny reason names the ban, the direct-evidence alternatives and the quoting "
        f"fix ({len(reasons)})")
    spellings = (SPECIFIC_TOOLS | set(GENERIC_TOOLS) | PYTHON_MODULES | SCRIPT_WORDS
                 | GO_TOOLS | set(GO_MODULE_MARKERS)
                 | {p for family in PACKAGES.values() for p in family}
                 | {s for scopes in PACKAGE_SCOPES.values() for s in scopes}
                 | {"pitest", "mutants", "mutagen", "dextool", "stryker", "mull-17",
                    "mull-runner-17", "org.pitest"})
    unneedled = sorted(s for s in spellings if not any(n in s.lower() for n in NEEDLES))
    check(not unneedled, f"every modelled spelling carries a prefilter needle "
                         f"({len(spellings)} spellings; missing {unneedled})")
    calls = []
    original_split = tokenizer.split_commands

    def counting_split(text, *args, **kwargs):
        calls.append(text)
        return original_split(text, *args, **kwargs)

    tokenizer.split_commands = counting_split
    try:
        benign = _graded("git status --short && ls -la")
        benign_calls = len(calls)
        needled = _graded("grep -rn mutmut .")
    finally:
        tokenizer.split_commands = original_split
    check(benign == ("allow", "") and benign_calls == 0 and needled[0] == "allow"
          and len(calls) == 1,
          f"a command with no needle is allowed without tokenizing; a needle tokenizes once "
          f"({benign_calls}, {len(calls)})")
    spent = time.monotonic() - 1
    check(_graded("mutmut run", spent)[0] == "ask"
          and _graded("git status", spent) == ("allow", ""),
          "a spent deadline asks for a needled command and still allows one with no needle")
    unreadable_tool = _graded("/bin/echo \"$(case x in x) mutmut run;; esac)\"")
    unreadable_plain = _graded("/bin/echo \"$(case x in x) mutation;; esac)\"")
    check(unreadable_tool[0] == "ask" and "cannot read" in unreadable_tool[1]
          and unreadable_plain == ("allow", ""),
          "unreadable source naming a tool asks; naming none is allowed")
    for label, command in OUT_OF_SCOPE:
        got, _reason = _graded(command)
        check(got == "allow", f"OUT OF SCOPE, decided {got}: {label}")
    print(f"\n  {total} checks, {failures} failures")
    print(f"SELFTEST-SUMMARY suite=mutation_testing_guard checks={total} failures={failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]:
        sys.exit(selftest())
    print(__doc__)
    sys.exit(0)
