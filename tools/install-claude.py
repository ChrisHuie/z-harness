#!/usr/bin/env python3
"""install-claude — generate the Claude instruction file; stage, activate, and check a versioned install.

Layout. One immutable tree per source version, activated by a settings-file switch:

  $HOME/.claude/harness/<version>/          the staged tree (never edited after staging)
      hooks/  tools/                         copied from the source checkout and byte-compiled
      AGENTS.source.md  CLAUDE.source.md     the policy and adapter the tree was generated from
      CLAUDE.generated.md                    the generated user-level instruction file
      install-receipt.json                   source commit, date, file digests, owned hook
                                             entries, checks run
  $HOME/.claude/settings.json                activation: ONE atomic replace that swaps only the
                                             hook entries a receipt owns; every other key is
                                             carried through byte-for-byte as parsed
  $HOME/.claude/CLAUDE.md                    the generated instruction file, installed after
                                             the settings switch
  $HOME/.claude/state/install-receipt.json   the receipt of the ACTIVE tree
  $HOME/.claude/state/install-pending.json   present only while an activation is in flight:
                                             from, to, the digest of the merged settings
                                             document, started_at

Why the switch is the settings file and not a directory rename: a directory cannot be renamed
over an existing non-empty directory, so a two-rename swap leaves a window with no hook script
at the registered path. Each version keeps its own tree and the registered commands point at
it; rollback is the same replace pointing back.

Why activation is a logged transaction: the switch is three writes (settings.json, CLAUDE.md,
the active receipt), and a process can stop between any two. The pending marker is written
before the settings replace and removed after the receipt write, so --check can name the stage
an interrupted activation reached; the removal set of every activation is the union of the
owned entries of every staged tree's receipt plus the active receipt's, so --activate of any
version from any interrupted state ends with exactly one version's entries registered. One
derivation, installation_state(), feeds both --check and --activate.

Why read-merge-replace-verify: the desktop app writes settings.json itself (app-managed keys),
so the file is read immediately before writing, only receipt-owned entries are replaced in that
content, the write is an atomic replace guarded by a stat comparison, and the result is re-read;
a mismatch after the write is a failed activation, never an assumed success. What the stat
comparison covers: a change to settings.json between the read and the final stat, which is
taken immediately before the rename, discards the merge and retries. What it does not cover: a
write that lands between that final stat and the rename. The rename overwrites it, nothing can
detect it afterwards because the lost content is unknown, and no cooperative lock around
settings.json is documented for the Claude Code runtime. That residual is bounded, not closed:
the final stat sits directly before the rename, and --activate and --check print the Claude Code
processes that could write the file while they run. --require-quiescent turns the report into
a refusal for an operator who has closed every session and wants the window provably empty; it
is opt-in because a precondition that every real run overrides would guarantee nothing.

Ownership is by exact identity: an entry is owned when its (event, matcher, type, command,
timeout) tuple is listed in a receipt; the same command registered under another event or
matcher is a user entry. User-added hooks, even ones stored under $HOME/.claude/hooks/,
`permissions.defaultMode`, and every other key are never touched. A hand-made install (no
receipt) is reported by --check, not adopted.

The generated instruction file is the shared policy (AGENTS.md) followed by the Claude adapter
section of CLAUDE.md, with the adapter's `~/.claude/hooks/` and `~/.claude/tools/` paths
templated to the active tree. --render prints it with placeholder tree and commit so its size
is stable for the budget ceiling; the installer renders it with the real values.

  install-claude.py --render [--source DIR] [--tree PATH] [--commit SHA]
  install-claude.py --stage [--home DIR] [--source DIR] [--version-id ID] [--allow-dirty]
  install-claude.py --activate ID [--home DIR] [--remove-orphans] [--require-quiescent]
  install-claude.py --check [--home DIR] [--source DIR]
  install-claude.py --selftest

Nothing here touches $HOME unless --stage or --activate names it; --check and --render only read.
Exit codes: 0 ok · 1 drift, failed stage or activation, or selftest failure · 2 usage error.
"""
import ast
import compileall
import contextlib
import copy
import datetime
import difflib
import hashlib
import io
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile

VERSION = "1.1.0"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_TREE = "~/.claude/harness/<version>"
TEMPLATE_COMMIT = "<commit>"
ADAPTER_HEADING = "# Claude Code adapter\n"
IMPORT_LINE = "@AGENTS.md\n"
# The repository's adapter opens with a sentence that is true inside the repository and false in
# a generated file where the policy sits inline above it; the generator replaces exactly that
# paragraph with provenance and keeps every other paragraph as authored.
REPLACED_PARAGRAPH_PREFIX = "The shared policy lives in `AGENTS.md`."
PATH_SUBSTITUTIONS = ("~/.claude/hooks/", "~/.claude/tools/")
COPIED_DIRECTORIES = ("hooks", "tools")
COPY_IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", "*events*.jsonl")
RECEIPT_NAME = "install-receipt.json"
# Schema 2 differs from 1 only in what an owned entry's identity means: all five fields,
# never the three handler fields alone. The fields are the same, so both versions load.
RECEIPT_SCHEMA_VERSION = 2
RECEIPT_SCHEMA_VERSIONS = (1, 2)
# A flag token is an option or a bare word; a shell operator such as `||` or `;` is not a
# flag, so a wrapped or masked command never matches and is refused as unowned.
# A script path is plain segments under hooks/: no `.` or `..` segment, no absolute path, so a
# command cannot name a script outside the tree it claims to run from.
SCRIPT_PATH = r"[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*\.py"
FLAGS = r"((?: --?[A-Za-z0-9][A-Za-z0-9_-]*)*)"
OWNED_COMMAND = re.compile(r"^python3 ~/\.claude/hooks/(" + SCRIPT_PATH + r")" + FLAGS + r"$")
# An entry's identity is the whole registration: the same command under another event or
# matcher is a different entry, and a user's.
HANDLER_IDENTITY_KEYS = ("event", "matcher", "type", "command", "timeout")
HANDLER_KEYS = ("type", "command", "timeout")


class InstallError(Exception):
    """A stage, activation, or check that must not be read as success."""


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def atomic_write(path, data, mode=0o644):
    """Write bytes to a temp file beside `path` and replace in one step."""
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".install-claude-", dir=directory)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.remove(tmp)
        raise


# ---- generator -----------------------------------------------------------------
def provenance_paragraph(tree, commit):
    return (
        f"Generated by `tools/install-claude.py` from z-harness `AGENTS.md` and `CLAUDE.md` at "
        f"{commit}. The shared policy above is inlined so this host has one user-level "
        f"instruction file, and the active tree is `{tree}`. Author policy changes in the "
        f"repository's `AGENTS.md` and adapter changes in its `CLAUDE.md`, never here."
    )


def adapter_paragraphs(claude_text):
    """-> the adapter body after the import line and heading, split into paragraphs."""
    if not claude_text.startswith(IMPORT_LINE):
        raise InstallError("CLAUDE.md does not open with the @AGENTS.md import line")
    body = claude_text[len(IMPORT_LINE):].lstrip("\n")
    if not body.startswith(ADAPTER_HEADING):
        raise InstallError("CLAUDE.md adapter section does not open with '# Claude Code adapter'")
    rest = body[len(ADAPTER_HEADING):].lstrip("\n")
    return rest.split("\n\n")


def render_instruction_file(source_root, tree=TEMPLATE_TREE, commit=TEMPLATE_COMMIT):
    """-> the generated user-level instruction file as text."""
    agents = read_text(os.path.join(source_root, "AGENTS.md"))
    claude = read_text(os.path.join(source_root, "CLAUDE.md"))
    if not agents.strip():
        raise InstallError("AGENTS.md is empty")
    paragraphs = adapter_paragraphs(claude)
    provenance = provenance_paragraph(tree, commit)
    replaced = False
    kept = []
    for paragraph in paragraphs:
        if not replaced and paragraph.startswith(REPLACED_PARAGRAPH_PREFIX):
            kept.append(provenance)
            replaced = True
        else:
            kept.append(paragraph)
    if not replaced:
        kept.insert(0, provenance)
    adapter = "\n\n".join(kept)
    for prefix in PATH_SUBSTITUTIONS:
        adapter = adapter.replace(prefix, f"{tree}/{prefix[len('~/.claude/'):]}")
    if not agents.endswith("\n"):
        agents += "\n"
    text = agents + "\n" + ADAPTER_HEADING + "\n" + adapter
    if not text.endswith("\n"):
        text += "\n"
    return text


# ---- ownership -----------------------------------------------------------------
def owned_hook_entries(source_settings, tree):
    """-> the handlers the tree owns, derived from the source settings.json hooks block.

    Every handler in the source must be a `python3 ~/.claude/hooks/<script> [flags]` command;
    anything else is refused rather than silently adopted, because ownership is by exact
    identity and an entry this installer did not derive is not one it may later replace.
    """
    hooks = source_settings.get("hooks")
    if not isinstance(hooks, dict) or not hooks:
        raise InstallError("source settings.json has no hooks block to own")
    owned = []
    for event, entries in hooks.items():
        if not isinstance(entries, list):
            raise InstallError(f"source settings.json hooks.{event} is not a list")
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("hooks"), list):
                raise InstallError(f"source settings.json hooks.{event} entry is malformed")
            for handler in entry["hooks"]:
                command = handler.get("command") if isinstance(handler, dict) else None
                match = OWNED_COMMAND.match(command or "")
                if handler.get("type") != "command" or not match:
                    raise InstallError(
                        f"source settings.json registers a handler this installer does not "
                        f"own: {command!r}")
                script, flags = match.group(1), match.group(2)
                owned.append({
                    "event": event,
                    "matcher": entry.get("matcher"),
                    "type": "command",
                    "command": f"python3 {tree}/hooks/{script}{flags}",
                    "timeout": handler.get("timeout"),
                })
    return owned


def handler_identity(event, matcher, handler):
    """-> (event, matcher, type, command, timeout) for a registered handler."""
    return (event, matcher) + tuple(handler.get(key) for key in HANDLER_KEYS)


def owned_identity(owned):
    """-> the identity of a receipt's owned entry, which carries all five fields itself."""
    return handler_identity(owned.get("event"), owned.get("matcher"), owned)


def merge_hooks(settings, remove, add):
    """-> a deep copy of `settings` with `remove` identities dropped and `add` handlers present.

    `remove` is a set of (event, matcher, type, command, timeout) identities; `add` is the
    owned list. Entries left with no handlers are dropped; a new handler joins the entry with
    the same matcher or opens one. Nothing outside the hooks block is read or written.
    """
    merged = copy.deepcopy(settings)
    hooks = merged.get("hooks")
    if hooks is None:
        hooks = merged["hooks"] = {}
    if not isinstance(hooks, dict):
        raise InstallError("settings.json hooks is not an object")
    for event, entries in list(hooks.items()):
        if not isinstance(entries, list):
            raise InstallError(f"settings.json hooks.{event} is not a list")
        kept_entries = []
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("hooks"), list):
                kept_entries.append(entry)
                continue
            entry["hooks"] = [
                handler for handler in entry["hooks"]
                if not (isinstance(handler, dict)
                        and handler_identity(event, entry.get("matcher"), handler) in remove)
            ]
            if entry["hooks"]:
                kept_entries.append(entry)
        if kept_entries:
            hooks[event] = kept_entries
        else:
            del hooks[event]
    for owned in add:
        handler = {key: owned[key] for key in HANDLER_KEYS}
        entries = hooks.setdefault(owned["event"], [])
        for entry in entries:
            if isinstance(entry, dict) and entry.get("matcher") == owned["matcher"] \
                    and isinstance(entry.get("hooks"), list):
                entry["hooks"].append(handler)
                break
        else:
            entry = {}
            if owned["matcher"] is not None:
                entry["matcher"] = owned["matcher"]
            entry["hooks"] = [handler]
            entries.append(entry)
    return merged


def registered_handlers(settings):
    """-> [(event, matcher, handler)] over a parsed settings file, malformed items skipped."""
    found = []
    hooks = settings.get("hooks") if isinstance(settings, dict) else None
    if not isinstance(hooks, dict):
        return found
    for event, entries in hooks.items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("hooks"), list):
                continue
            for handler in entry["hooks"]:
                if isinstance(handler, dict):
                    found.append((event, entry.get("matcher"), handler))
    return found


# ---- versions and paths ----------------------------------------------------------
def source_commit(source_root):
    """-> (sha, dirty) from git, or (None, None) when the source is not a checkout."""
    try:
        head = subprocess.run(["git", "-C", source_root, "rev-parse", "HEAD"],
                              capture_output=True, text=True)
        status = subprocess.run(["git", "-C", source_root, "status", "--porcelain"],
                                capture_output=True, text=True)
    except OSError:
        return None, None
    if head.returncode != 0 or status.returncode != 0:
        return None, None
    return head.stdout.strip(), bool(status.stdout.strip())


def derive_version_id(source_root, allow_dirty):
    sha, dirty = source_commit(source_root)
    if sha is None:
        raise InstallError("source is not a git checkout; pass --version-id")
    if dirty and not allow_dirty:
        raise InstallError("source checkout is dirty; commit first or pass --allow-dirty")
    manifest = os.path.join(source_root, ".codex-plugin", "plugin.json")
    try:
        plugin_version = json.load(open(manifest, encoding="utf-8")).get("version")
    except (OSError, ValueError):
        plugin_version = None
    if not isinstance(plugin_version, str) or not plugin_version:
        raise InstallError("cannot read the plugin version from .codex-plugin/plugin.json")
    return f"{plugin_version}+{sha[:12]}{'.dirty' if dirty else ''}", sha, dirty


def claude_home(home):
    return os.path.join(home, ".claude")


def tree_display(version_id):
    return f"~/.claude/harness/{version_id}"


def tree_path(home, version_id):
    return os.path.join(claude_home(home), "harness", version_id)


def expand_display(home, display):
    """Resolve a `~/.claude/...` display path against the install home, not $HOME."""
    if display.startswith("~/"):
        return os.path.join(home, display[2:])
    return display


def active_receipt_path(home):
    return os.path.join(claude_home(home), "state", RECEIPT_NAME)


def load_json(path):
    with open(path, "rb") as fh:
        return json.loads(fh.read().decode("utf-8"))


def _int(value):
    return type(value) is int


def _contained(rel):
    """A relative path inside the tree: no absolute or home prefix, no `.` or `..` segment."""
    return (isinstance(rel, str) and rel and not rel.startswith(("/", "~"))
            and all(part not in ("", ".", "..") for part in rel.split("/")))


def receipt_problems(receipt):
    """-> [problem] for a receipt this installer must not trust; [] for a usable one.

    Every field the installer later reads is checked here, so a receipt that loads is one
    whose files can be verified, whose owned entries can be removed and compared, and whose
    owned hook scripts are in the files it accounts for.
    """
    if not isinstance(receipt, dict):
        return ["not an object"]
    version = receipt.get("schema_version")
    if not _int(version) or version not in RECEIPT_SCHEMA_VERSIONS:
        return [f"schema_version {version!r} is not an integer in {RECEIPT_SCHEMA_VERSIONS}"]
    problems = []
    for key in ("version", "tree"):
        if not isinstance(receipt.get(key), str) or not receipt[key].strip():
            problems.append(f"{key} must be a non-empty string")
    if isinstance(receipt.get("version"), str) and not VERSION_ID.fullmatch(receipt["version"]):
        problems.append(f"version {receipt['version']!r} is not a safe version id")
    if isinstance(receipt.get("version"), str) and isinstance(receipt.get("tree"), str) \
            and receipt["tree"] != tree_display(receipt["version"]):
        problems.append(f"tree {receipt['tree']!r} is not the display path of version {receipt['version']!r}")
    files = receipt.get("files")
    if not isinstance(files, dict) or not files:
        problems.append("files must be a non-empty map")
        files = {}
    for rel, rec in files.items():
        if not _contained(rel):
            problems.append(f"files key {rel!r} is not a contained relative path")
        if not (isinstance(rec, dict) and isinstance(rec.get("sha256"), str)
                and re.fullmatch(r"[0-9a-f]{64}", rec["sha256"])):
            problems.append(f"files[{rel!r}] must be an object with a 64-hex sha256")
    owned = receipt.get("owned_hooks")
    if not isinstance(owned, list):
        problems.append("owned_hooks must be a list")
        return problems
    seen = set()
    for index, h in enumerate(owned):
        if not isinstance(h, dict) or not all(key in h for key in HANDLER_IDENTITY_KEYS):
            problems.append(f"owned_hooks[{index}] must carry {', '.join(HANDLER_IDENTITY_KEYS)}")
            continue
        if not isinstance(h["event"], str) or not h["event"]:
            problems.append(f"owned_hooks[{index}] event must be a non-empty string")
        if h["matcher"] is not None and not isinstance(h["matcher"], str):
            problems.append(f"owned_hooks[{index}] matcher must be a string or null")
        if h["type"] != "command":
            problems.append(f"owned_hooks[{index}] type must be \"command\"")
        if h["timeout"] is not None and not _int(h["timeout"]):
            problems.append(f"owned_hooks[{index}] timeout must be an integer or null")
        command = h["command"]
        if not isinstance(command, str) or not command:
            problems.append(f"owned_hooks[{index}] command must be a non-empty string")
            continue
        pointed = HARNESS_COMMAND.match(command)
        if pointed is None:
            problems.append(f"owned_hooks[{index}] command {command!r} is not a harness hook command")
        else:
            if isinstance(receipt.get("version"), str) and pointed.group(1) != receipt["version"]:
                problems.append(f"owned_hooks[{index}] command points into version {pointed.group(1)!r}, "
                                f"not {receipt['version']!r}")
            if f"hooks/{pointed.group(2)}" not in files:
                problems.append(f"owned_hooks[{index}] script hooks/{pointed.group(2)} is not in files")
        if problems and problems[-1].startswith(f"owned_hooks[{index}]"):
            continue
        identity = owned_identity(h)
        if identity in seen:
            problems.append(f"owned_hooks[{index}] repeats {identity!r}")
        seen.add(identity)
    return problems


def load_receipt(path):
    """-> a receipt whose shape this installer can act on; InstallError otherwise."""
    try:
        receipt = load_json(path)
    except (OSError, ValueError) as exc:
        raise InstallError(f"receipt unreadable at {path}: {exc}")
    problems = receipt_problems(receipt)
    if problems:
        raise InstallError(f"receipt at {path}: " + "; ".join(problems))
    return receipt


def marker_problems(marker):
    """-> [problem] for a pending marker this installer must not read as a transaction."""
    if not isinstance(marker, dict):
        return ["not an object"]
    problems = []
    version = marker.get("schema_version")
    if not _int(version) or version != PENDING_SCHEMA_VERSION:
        problems.append(f"schema_version {version!r} is not the integer {PENDING_SCHEMA_VERSION}")
    if not isinstance(marker.get("to"), str) or not VERSION_ID.fullmatch(marker["to"]):
        problems.append("to must be a version id")
    if marker.get("from") is not None and (not isinstance(marker["from"], str)
                                           or not VERSION_ID.fullmatch(marker["from"])):
        problems.append("from must be a version id or null")
    digest = marker.get("merged_sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        problems.append("merged_sha256 must be 64 hex characters")
    started = marker.get("started_at")
    try:
        if not isinstance(started, str):
            raise ValueError("not a string")
        datetime.datetime.strptime(started, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        problems.append("started_at must be a real UTC timestamp like 2026-01-01T00:00:00Z")
    return problems


# The argument of a sys.path mutation is evaluated symbolically, anchored on __file__; these
# calls return their argument's path unchanged.
PATH_IDENTITY_CALLS = frozenset({"str", "Path", "pathlib.Path", "os.fspath", "os.path.abspath",
                                 "os.path.normpath", "os.path.realpath"})
# These, like `.resolve()`, collapse `..` segments where they stand, so a later `.parent` climbs
# from the collapsed path; `.absolute()`, `str`, `Path` and `os.fspath` keep the segments.
PATH_NORMALISING_CALLS = frozenset({"os.path.abspath", "os.path.normpath", "os.path.realpath"})


def path_parent(relative):
    """-> the parent of a tree-relative path as `Path.parent` and `os.path.dirname` give it at
    run time, where every path is absolute: the parent of the tree root is above the tree,
    never the empty string."""
    if relative in ("", "."):
        return ".."
    if set(relative.split("/")) == {".."}:
        return relative + "/.."
    return os.path.dirname(relative) or "."
DYNAMIC_IMPORT_CALLS = ("importlib.import_module", "__import__", "importlib.__import__")
# The interpreter's own sys.path entries (its zip, stdlib, extension and site directories),
# whose number varies by host: one sentinel between the script's directory and appended ones.
INTERPRETER_ENTRIES = "<the interpreter's own entries>"


def sys_path_mutation(node):
    """-> `node` when it is a `sys.path.insert(...)` or `sys.path.append(...)` call, else None."""
    return (node if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr in ("insert", "append") and isinstance(node.func.value, ast.Attribute)
            and node.func.value.attr == "path" and isinstance(node.func.value.value, ast.Name)
            and node.func.value.value.id == "sys" else None)


def path_expression(node, script):
    """-> the tree-relative path `node` denotes for the script at `script`, or None.

    Modelled: `__file__`, string constants, `.parent`, `os.path.dirname(...)`,
    `os.path.join(...)`, `/`, the identity calls (`.absolute()` among them, which keeps `..`),
    and `.resolve()`, `os.path.abspath`, `normpath` and `realpath`, which collapse `..` where
    they stand.
    Anything else is None: the checker refuses what it cannot resolve rather than certify it.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name) and node.id == "__file__":
        return script
    if isinstance(node, ast.Attribute) and node.attr == "parent":
        base = path_expression(node.value, script)
        return None if base is None else path_parent(base)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        left, right = path_expression(node.left, script), path_expression(node.right, script)
        return None if left is None or right is None else os.path.join(left, right)
    if isinstance(node, ast.Call) and not node.keywords:
        callee = ast.unparse(node.func)
        if callee in PATH_IDENTITY_CALLS and len(node.args) == 1:
            inner = path_expression(node.args[0], script)
            return None if inner is None else (os.path.normpath(inner) if callee in PATH_NORMALISING_CALLS else inner)
        if callee == "os.path.dirname" and len(node.args) == 1:
            base = path_expression(node.args[0], script)
            return None if base is None else path_parent(base)
        if callee == "os.path.join" and node.args:
            parts = [path_expression(a, script) for a in node.args]
            return None if any(part is None for part in parts) else os.path.join(*parts)
        if isinstance(node.func, ast.Attribute) and node.func.attr in ("resolve", "absolute") and not node.args:
            inner = path_expression(node.func.value, script)
            return None if inner is None else (os.path.normpath(inner) if node.func.attr == "resolve" else inner)
    return None


def hook_import_problems(tree, receipt):
    """-> [problem] for an owned hook script whose imports the receipt cannot vouch for.

    The receipt vouches for a hook only when every module the interpreter would load for it
    is in the files map, resolved the way `python3 <tree>/hooks/<script>.py` resolves them.
    Each owned script is its own process: the search path is the script's directory, then
    the interpreter's own entries, modelled as one sentinel; a top-level `sys.path.insert(0,
    …)` or `insert(1, …)` (the only indices whose position relative to those entries is
    fixed) or `sys.path.append(…)`, with an argument built from `__file__`, mutates the one
    shared path at the point it executes; an import resolves against the path as it stands
    then, the first directory holding `<name>/__init__.py` or else `<name>.py` wins (the
    interpreter prefers a package to a module of the same name), and a module imported from
    the tree is walked right there, its own mutations and imports included; a name resolves
    once per process, as `sys.modules` does. A dotted import descends the package from the
    file that resolved its first segment; `from mod import name` imports nothing more when a
    top-level statement of `mod` that always runs binds `name`, walks `mod/name.py` when it
    exists, and is reported otherwise; a relative import resolves from the importing file's
    package, which only a module reached as a package member has. An import inside a
    function or compound statement, and an `importlib.import_module` or `__import__` call
    with a constant name, resolve where they stand. Everything inside any other statement (the
    branches and header expressions of a compound statement, a function's defaults, decorators
    and body, a class's bases and body) resolves where that statement stands, speculatively:
    what it imports is checked, but its path mutations and cached modules are not kept.

    Reported: a module that no searched directory holds; a file that wins the search but is
    not in the receipt's files map; a dotted segment the package does not hold, or a segment
    under a plain module; a from-import of a name the module neither binds nor holds as a submodule; a relative import from
    a file that is not in a package; a file on
    the path named like a standard-library module, which shadows it for every interpreter
    that has not already loaded that module (also reported for an appended directory, which
    the interpreter searches after its own entries); a sys.path mutation outside a top-level
    call statement, or with an index other than 0 or 1; an argument the evaluator does not
    model; a target outside the tree; a dynamic import whose name is not a constant; a
    script that does not parse.
    """
    files = receipt.get("files", {})
    stdlib = getattr(sys, "stdlib_module_names", frozenset())
    problems = []
    parsed = {}

    def module_ast(relative):
        if relative not in parsed:
            try:
                parsed[relative] = ast.parse(read_text(os.path.join(tree, relative)))
            except (OSError, SyntaxError, UnicodeDecodeError) as exc:
                problems.append(f"{relative} cannot be parsed: {exc}")
                parsed[relative] = None
        return parsed[relative]

    def import_targets(node):
        """-> [(dotted module name, names imported from it)] for one absolute import statement."""
        if isinstance(node, ast.Import):
            return [(alias.name, ()) for alias in node.names]
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            return [(node.module, tuple(alias.name for alias in node.names))]
        return []

    COMPOUND = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith, ast.Try, ast.Match)
    if hasattr(ast, "TryStar"):
        COMPOUND = COMPOUND + (ast.TryStar,)

    def process(entry):
        path = [os.path.dirname(entry), INTERPRETER_ENTRIES]
        loaded = {}
        walked = set()
        context = []
        executed = {}

        def present(relative):
            return relative in files or os.path.isfile(os.path.join(tree, relative))

        def locate(name):
            # The interpreter loads what is on disk, listed or not; an unlisted file that wins
            # is reported by `vouch`, and `tree_problems` names it as unreceipted.
            for directory in path:
                if directory is INTERPRETER_ENTRIES:
                    continue
                for candidate in (f"{name}/__init__.py", f"{name}.py"):
                    relative = os.path.normpath(os.path.join(directory, candidate))
                    if present(relative):
                        return relative
            return None

        def namespace_directory(name):
            for directory in path:
                if directory is INTERPRETER_ENTRIES:
                    continue
                relative = os.path.normpath(os.path.join(directory, name))
                if os.path.isdir(os.path.join(tree, relative)) or any(f.startswith(relative + "/") for f in files):
                    return relative
            return None

        def vouch(relative, dotted, found):
            if found not in files:
                problems.append(f"{relative} imports {dotted}, which loads {found}, a file the receipt "
                                f"does not list")

        def import_source(module_file, depth, statement):
            """-> (the file `from <module> import …` in `module_file` reads from, the package
            depth it is loaded at), or (None, None); a standard-library source is ("stdlib",
            None). `depth` is the package depth of the load of `module_file` being read; a
            relative import needs it to cover the level."""
            if statement.level == 0:
                top, *rest = statement.module.split(".")
                if top in stdlib:
                    return "stdlib", None
                source = loaded.get(top) or locate(top)
                reached = 1
            else:
                if statement.level > depth:
                    return None, None
                package = os.path.dirname(module_file)
                for _ in range(statement.level - 1):
                    package = os.path.dirname(package)
                source = os.path.normpath(os.path.join(package, "__init__.py"))
                if not present(source):
                    return None, None
                rest = statement.module.split(".") if statement.module else []
                reached = depth - (statement.level - 1)
            for segment in rest:
                if source is None or not source.endswith("/__init__.py"):
                    return None, None
                source = submodule(source, segment)
                reached += 1
            if source is None:
                return None, None
            return source, (reached if source.endswith("/__init__.py") else reached - 1)

        def import_provides(module_file, depth, statement, item, visiting):
            """`from <module> import item` provides `item` only when the source holds it as a
            submodule or binds it itself; two imports that vouch for each other provide
            nothing (the cycle is broken by `visiting`)."""
            source, source_depth = import_source(module_file, depth, statement)
            if source == "stdlib":
                return True
            if source is None or (source, source_depth, item) in visiting:
                return False
            if source.endswith("/__init__.py") and submodule(source, item) is not None:
                return True
            return binds(source, item, source_depth, visiting | {(source, source_depth, item)})

        def binds(module_file, name, depth, visiting=frozenset()):
            """A module binds `name` as an attribute when a top-level statement that always
            runs, and has already run if the module is still initialising, stores, defines or
            imports it, and no top-level `del` removes it. A binding
            inside a function, class or compound statement does not count; nor does an
            annotation without a value, a star import, or a from-import whose source does
            not itself provide the name (so the module's own `from . import name`, under any
            alias, and two self-imports vouching for each other, are no evidence). `depth` is
            the package depth of the load being read: the same file loading as `pkg.mod` and
            as `mod` is two modules, each at its own position."""
            module = module_ast(module_file)
            if module is None:
                return True
            visiting = visiting | {(module_file, depth, name)}
            # A module still initialising has bound only what its statements executed so
            # far bound: an import that reaches back into it sees nothing later. Inside an
            # `import a, b` the aliases already completed are bound; a `from` import binds
            # nothing until the whole statement completes, since a submodule it names loads
            # inside it, before any of its names is stored.
            statements = module.body
            if (module_file, depth) in executed:
                index, aliases = executed[(module_file, depth)]
                statements = list(module.body[:index])
                current = module.body[index] if index < len(module.body) else None
                if aliases and isinstance(current, ast.Import):
                    statements.append(ast.Import(names=current.names[:aliases]))
            def stores(target):
                # The names a target binds: a plain name, or the names inside an unpacking
                # target; a name read inside a subscript or attribute target binds nothing.
                if isinstance(target, ast.Name):
                    return {target.id} if isinstance(target.ctx, (ast.Store, ast.Del)) else set()
                if isinstance(target, (ast.Tuple, ast.List)):
                    return set().union(*(stores(e) for e in target.elts))
                if isinstance(target, ast.Starred):
                    return stores(target.value)
                return set()

            bound = False
            for statement in statements:
                if isinstance(statement, (ast.Assign, ast.AugAssign)):
                    targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                    bound = bound or any(name in stores(target) for target in targets)
                elif isinstance(statement, ast.AnnAssign):
                    # An annotation without a value declares nothing.
                    bound = bound or (statement.value is not None and name in stores(statement.target))
                elif isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    bound = bound or statement.name == name
                elif isinstance(statement, ast.Import):
                    bound = bound or any((a.asname or a.name.split(".")[0]) == name for a in statement.names)
                elif isinstance(statement, ast.ImportFrom):
                    for alias in statement.names:
                        # A star import exports an unknown set and binds nothing here.
                        if alias.name != "*" and (alias.asname or alias.name) == name:
                            bound = bound or import_provides(module_file, depth, statement, alias.name, visiting)
                elif isinstance(statement, (ast.With, ast.AsyncWith)):
                    bound = bound or any(name in stores(item.optional_vars) for item in statement.items
                                         if item.optional_vars is not None)
                elif isinstance(statement, ast.Delete):
                    if any(name in stores(target) for target in statement.targets):
                        return False
            return bound

        def submodule(package_file, segment):
            directory = os.path.dirname(package_file)
            for candidate in (f"{segment}/__init__.py", f"{segment}.py"):
                relative = os.path.normpath(os.path.join(directory, candidate))
                if present(relative):
                    return relative
            return None

        def depth_of(dotted, file):
            """The number of segments of a module's __package__: all of its dotted name for a
            package, one fewer for a plain module."""
            return dotted.count(".") + 1 if file.endswith("/__init__.py") else dotted.count(".")

        def from_name(relative, dotted, current, name):
            """`from <current> import name`: a name the module binds is an attribute and imports
            nothing more; otherwise a submodule of a package is walked; otherwise the
            interpreter raises, so the import is reported."""
            if name == "*" or binds(current, name, depth_of(dotted, current)):
                return
            inner = submodule(current, name) if current.endswith("/__init__.py") else None
            if inner is not None:
                vouch(relative, f"{dotted}.{name}", inner)
                walk(inner, depth_of(f"{dotted}.{name}", inner))
            else:
                problems.append(f"{relative} imports {name} from {dotted}, which {current} neither binds "
                                f"nor holds as a submodule")

        def mutate(relative, call):
            if (call.func.attr == "insert" and len(call.args) == 2
                    and isinstance(call.args[0], ast.Constant) and call.args[0].value in (0, 1)
                    and type(call.args[0].value) is int):
                index, argument = call.args[0].value, call.args[1]
            elif call.func.attr == "append" and len(call.args) == 1:
                index, argument = len(path), call.args[0]
            else:
                problems.append(f"{relative} line {call.lineno}: unsupported sys.path mutation "
                                f"{ast.unparse(call)}")
                return
            anchored = any(isinstance(n, ast.Name) and n.id == "__file__" for n in ast.walk(argument))
            target = path_expression(argument, relative) if anchored else None
            if target is None:
                problems.append(f"{relative} line {call.lineno}: sys.path entry {ast.unparse(argument)} "
                                f"is not a path built from __file__ that the checker resolves")
                return
            target = os.path.normpath(target)
            if os.path.isabs(target) or target == ".." or target.startswith("../"):
                # An absolute entry, or one that leaves the tree (wherever it re-enters), does
                # not survive the relocation of a staged tree.
                problems.append(f"{relative} inserts a sys.path entry outside the tree ({target})")
                return
            path.insert(index, target)

        def unordered(relative, call):
            problems.append(f"{relative} line {call.lineno}: sys.path mutated outside a top-level call "
                            f"statement; the search path cannot be ordered")

        def resolve(relative, dotted, from_names=()):
            name, *segments = dotted.split(".")
            if name in stdlib:
                return
            if name not in loaded:
                found = locate(name)
                if found is None:
                    directory = namespace_directory(name)
                    if directory is not None:
                        problems.append(f"{relative} imports {name}, but {directory}/ holds no __init__.py: a "
                                        f"namespace package the checker does not model")
                    else:
                        problems.append(f"{relative} imports {name}, which is neither standard library nor "
                                        f"in the receipt's files under "
                                        f"{', '.join(d for d in dict.fromkeys(path) if d is not INTERPRETER_ENTRIES)}")
                    return
                loaded[name] = found
                vouch(relative, name, found)
                walk(found, depth_of(name, found))
            current = loaded[name]
            reached = name
            for segment in segments:
                if not current.endswith("/__init__.py"):
                    problems.append(f"{relative} imports {dotted}, but {current} is a module, not a package")
                    return
                current = submodule(current, segment)
                if current is None:
                    problems.append(f"{relative} imports {dotted}, which is not in the receipt's files")
                    return
                reached = f"{reached}.{segment}"
                vouch(relative, dotted, current)
                walk(current, depth_of(reached, current))
            for name in from_names:
                from_name(relative, dotted, current, name)

        def resolve_relative(relative, node):
            """`from .a.b import c` from `relative`: the importing module's package depth (the
            segments of its __package__, carried from the import that reached it, not read
            from the directories around it) must cover the level; a script run by file name or
            a module found by bare name has depth 0."""
            depth = context[-1]
            if not depth:
                problems.append(f"{relative} line {node.lineno}: relative import {ast.unparse(node)} from a "
                                f"module that has no package context")
                return
            if node.level > depth:
                problems.append(f"{relative} line {node.lineno}: relative import {ast.unparse(node)} climbs "
                                f"beyond the top-level package")
                return
            package = os.path.dirname(relative)
            for climb in range(node.level - 1):
                package = os.path.dirname(package)
            current = os.path.normpath(os.path.join(package, "__init__.py"))
            base_depth = depth - (node.level - 1)
            dotted = "." * node.level + (node.module or "")
            reached = base_depth
            for segment in (node.module.split(".") if node.module else []):
                if not current.endswith("/__init__.py"):
                    problems.append(f"{relative} imports {dotted}, but {current} is a module, not a package")
                    return
                current = submodule(current, segment)
                if current is None:
                    problems.append(f"{relative} imports {dotted}, which is not in the receipt's files")
                    return
                reached += 1
                vouch(relative, dotted, current)
                walk(current, reached if current.endswith("/__init__.py") else reached - 1)
            current_depth = reached if current.endswith("/__init__.py") else reached - 1
            for alias in node.names:
                bound = alias.name == "*" or binds(current, alias.name, current_depth)
                inner = None if bound else (submodule(current, alias.name) if current.endswith("/__init__.py") else None)
                if inner is not None:
                    vouch(relative, f"{dotted}.{alias.name}", inner)
                    walk(inner, reached + 1 if inner.endswith("/__init__.py") else reached)
                elif not bound:
                    problems.append(f"{relative} imports {alias.name} from {dotted}, which {current} neither "
                                    f"binds nor holds as a submodule")

        def constant(node):
            return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None

        def resolve_dynamic(relative, call):
            """An `importlib.import_module` or `__import__` call resolves where it stands; a
            shape the checker does not read (a non-constant name, package, fromlist or level)
            is reported."""
            if not (isinstance(call, ast.Call) and ast.unparse(call.func) in DYNAMIC_IMPORT_CALLS):
                return
            positional = list(call.args)
            unresolved = f"{relative} line {call.lineno}: dynamic import {ast.unparse(call)}"
            parameters = (("name", "package") if ast.unparse(call.func) == "importlib.import_module"
                          else ("name", "globals", "locals", "fromlist", "level"))
            keywords = {k.arg: k.value for k in call.keywords}
            # An unpacked argument, an unknown keyword, a keyword that repeats a positional
            # parameter or a positional overflow is a call the interpreter rejects or the
            # checker does not read.
            if (None in keywords or set(keywords) - set(parameters) or len(positional) > len(parameters)
                    or set(parameters[:len(positional)]) & set(keywords)
                    or any(isinstance(a, ast.Starred) for a in positional)):
                problems.append(f"{unresolved} has arguments the checker does not read")
                return
            module_name = constant(positional[0] if positional else keywords.get("name"))
            if module_name is None:
                problems.append(f"{unresolved} names no constant module; the checker cannot resolve it")
                return
            from_names = ()
            if parameters == ("name", "package"):
                package = constant(positional[1] if len(positional) > 1 else keywords.get("package"))
            else:
                package = None
                fromlist = positional[3] if len(positional) > 3 else keywords.get("fromlist")
                level = positional[4] if len(positional) > 4 else keywords.get("level")
                if fromlist is not None:
                    names = [constant(e) for e in getattr(fromlist, "elts", [None])]
                    if not isinstance(fromlist, (ast.List, ast.Tuple)) or any(n is None for n in names):
                        problems.append(f"{unresolved} has a fromlist the checker does not read")
                        return
                    from_names = tuple(names)
                if level is not None and not (isinstance(level, ast.Constant) and level.value == 0):
                    problems.append(f"{unresolved} is relative; the checker cannot resolve it")
                    return
            if module_name.startswith("."):
                if package is None:
                    problems.append(f"{unresolved} is relative without a constant package")
                    return
                depth = len(module_name) - len(module_name.lstrip("."))
                parts = package.split(".")
                if depth > len(parts):
                    problems.append(f"{unresolved} climbs beyond the top-level package")
                    return
                rest = module_name.lstrip(".")
                module_name = ".".join(parts[:len(parts) - (depth - 1)] + ([rest] if rest else []))
            resolve(relative, module_name, from_names)

        def speculative(action):
            """A body that may never run, or runs later, is examined for what it imports, but
            its path mutations, cached modules and walked files are not established as facts:
            a module it reached is walked again when a top-level import reaches it."""
            kept_path, kept_loaded, kept_walked = list(path), dict(loaded), set(walked)
            try:
                action()
            finally:
                path[:] = kept_path
                loaded.clear()
                loaded.update(kept_loaded)
                walked.clear()
                walked.update(kept_walked)

        def run(relative, statements, top_level):
            """Statements in execution order: a mutation counts only as a top-level call
            statement; an import resolves against the path as it stands; everything inside any
            other statement (a compound statement's branches and header expressions, a
            function's defaults, decorators and body, a class's bases and body) resolves where
            the statement stands, speculatively."""
            def progress(index, aliases):
                if top_level:
                    executed[(relative, context[-1])] = (index, aliases)

            for index, statement in enumerate(statements):
                progress(index, 0)
                if isinstance(statement, ast.Expr) and sys_path_mutation(statement.value) is not None:
                    (mutate if top_level else unordered)(relative, statement.value)
                elif isinstance(statement, ast.ImportFrom) and statement.level > 0:
                    resolve_relative(relative, statement)
                elif isinstance(statement, (ast.Import, ast.ImportFrom)):
                    for k, (dotted, from_names) in enumerate(import_targets(statement)):
                        if isinstance(statement, ast.Import):
                            progress(index, k)
                        resolve(relative, dotted, from_names)
                else:
                    scan(relative, statement)

        def scan(relative, node):
            """Every node under `node` in evaluation order: a call's arguments before the call,
            a statement's expressions before its bodies, each body under its own snapshot. A
            lambda body, the operands after the first of a short-circuit, the branches of a
            conditional expression and all of a comprehension but its first iterable run later
            or not at all, so they are scanned speculatively too."""
            if sys_path_mutation(node) is not None:
                unordered(relative, node)
            if isinstance(node, ast.Lambda):
                scan(relative, node.args)
                speculative(lambda: scan(relative, node.body))
                return
            if isinstance(node, ast.BoolOp):
                scan(relative, node.values[0])
                for value in node.values[1:]:
                    speculative(lambda value=value: scan(relative, value))
                return
            if isinstance(node, ast.IfExp):
                scan(relative, node.test)
                for branch in (node.body, node.orelse):
                    speculative(lambda branch=branch: scan(relative, branch))
                return
            if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                # The first iterable is evaluated at once; per iteration come the first
                # target, its filters, each later generator's iterable, target and filters,
                # and last the result expression (a dict's key, then its value).
                scan(relative, node.generators[0].iter)
                later = [node.generators[0].target] + list(node.generators[0].ifs)
                for generator in node.generators[1:]:
                    later += [generator.iter, generator.target] + list(generator.ifs)
                later += [getattr(node, f) for f in ("elt", "key", "value") if hasattr(node, f)]
                speculative(lambda: [scan(relative, part) for part in later])
                return
            bodies = []
            for field, value in ast.iter_fields(node):
                if isinstance(value, list) and value and isinstance(value[0], ast.stmt):
                    bodies.append(value)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, ast.AST):
                            scan(relative, item)
                elif isinstance(value, ast.AST):
                    scan(relative, value)
            if isinstance(node, ast.Call):
                resolve_dynamic(relative, node)
            for body in bodies:
                speculative(lambda body=body: run(relative, body, False))

        def walk(relative, depth):
            """A file is walked once per load context: reached as a package member it carries
            its package's depth, reached by bare name it carries none, and one file can be
            loaded both ways; each load keeps its own execution position while it runs."""
            if (relative, depth) in walked:
                return
            walked.add((relative, depth))
            context.append(depth)
            try:
                module = module_ast(relative)
                if module is not None:
                    executed[(relative, depth)] = (0, 0)
                    try:
                        run(relative, module.body, top_level=True)
                    finally:
                        del executed[(relative, depth)]
            finally:
                context.pop()

        walk(entry, 0)
        # Any file on the final search path named like a standard-library module shadows it
        # for whatever imports it, directly or through another standard-library module, on
        # every interpreter that has not already loaded that module; reported regardless.
        for directory in dict.fromkeys(path):
            if directory is INTERPRETER_ENTRIES:
                continue
            on_disk = os.path.join(tree, directory)
            names = {os.path.basename(f) for f in files
                     if os.path.normpath(os.path.dirname(f) or ".") == os.path.normpath(directory)}
            names |= {os.path.basename(os.path.dirname(f)) for f in files if f.endswith("/__init__.py")
                      and os.path.normpath(os.path.dirname(os.path.dirname(f)) or ".") == os.path.normpath(directory)}
            if os.path.isdir(on_disk):
                names |= set(os.listdir(on_disk))
            for name in sorted(names):
                stem = name[:-3] if name.endswith(".py") else name
                if stem != name or present(os.path.normpath(os.path.join(directory, name, "__init__.py"))):
                    if stem in stdlib:
                        line = (f"{os.path.normpath(os.path.join(directory, name))} on the search path of "
                                f"{entry} shadows the standard-library module {stem}")
                        if line not in problems:
                            problems.append(line)

    for h in receipt.get("owned_hooks", []):
        pointed = HARNESS_COMMAND.match(h.get("command", "")) if isinstance(h.get("command"), str) else None
        if pointed:
            process(f"hooks/{pointed.group(2)}")
    return list(dict.fromkeys(problems))


def tree_problems(tree, receipt):
    """-> (file problems, hook problems) for one staged tree against its receipt.

    File problems are "missing <path>" and "changed <path>" over the receipt's files map in
    path order, then "unreceipted <path>" for every file under the tree the map does not
    list (a file the digests never verify, which a hook's search path may load ahead of a
    listed one); hook problems are those of `hook_import_problems`. --check applies this to
    the active tree and reports each line; --activate applies it to the target at the commit
    fence, before the temp file, the pending marker and the settings replace, so a tree that
    no longer matches what was staged is refused before anything is written.
    """
    recorded = receipt.get("files", {})
    files = []
    for relative, record in sorted(recorded.items()):
        full = os.path.join(tree, relative)
        if not os.path.isfile(full):
            files.append(f"missing {relative}")
        elif sha256_file(full) != record["sha256"]:
            files.append(f"changed {relative}")
    if os.path.isdir(tree):
        files.extend(f"unreceipted {relative}" for relative in sorted(set(tree_files(tree)) - set(recorded)))
    return files, hook_import_problems(tree, receipt)


# ---- stage ---------------------------------------------------------------------
def tree_files(tree):
    """-> every file under the tree that a receipt describes: all but the receipt itself and
    byte-compiled copies, in walk order."""
    found = []
    for dirpath, dirs, files in os.walk(tree):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        for name in sorted(files):
            if name == RECEIPT_NAME or name.endswith(".pyc"):
                continue
            found.append(os.path.relpath(os.path.join(dirpath, name), tree).replace(os.sep, "/"))
    return found


def tree_file_digests(tree):
    digests = {}
    for relative in tree_files(tree):
        full = os.path.join(tree, relative)
        digests[relative] = {"sha256": sha256_file(full), "bytes": os.path.getsize(full)}
    return digests


def stage(source_root, home, version_id=None, allow_dirty=False, now=None):
    """Stage one complete tree under $HOME/.claude/harness/<version>; -> the receipt."""
    sha, dirty = source_commit(source_root)
    if version_id is None:
        version_id, sha, dirty = derive_version_id(source_root, allow_dirty)
    if not VERSION_ID.fullmatch(version_id) or STAGING_MARK in version_id:
        raise InstallError(f"version id {version_id!r} is not a safe directory name "
                           f"({STAGING_MARK!r} is reserved for staging directories)")
    tree = tree_path(home, version_id)
    if os.path.lexists(tree):
        raise InstallError(f"tree already staged: {tree}; a staged tree is immutable")
    display = tree_display(version_id)
    source_settings = load_json(os.path.join(source_root, "settings.json"))
    owned = owned_hook_entries(source_settings, display)
    generated = render_instruction_file(source_root, tree=display, commit=sha or TEMPLATE_COMMIT)
    os.makedirs(os.path.dirname(tree), exist_ok=True)
    staging = f"{tree}.staging-{os.getpid()}"
    if os.path.lexists(staging):
        shutil.rmtree(staging)
    try:
        os.makedirs(staging)
        for directory in COPIED_DIRECTORIES:
            shutil.copytree(os.path.join(source_root, directory),
                            os.path.join(staging, directory), ignore=COPY_IGNORE, symlinks=False)
        shutil.copyfile(os.path.join(source_root, "AGENTS.md"),
                        os.path.join(staging, "AGENTS.source.md"))
        shutil.copyfile(os.path.join(source_root, "CLAUDE.md"),
                        os.path.join(staging, "CLAUDE.source.md"))
        with open(os.path.join(staging, "CLAUDE.generated.md"), "w", encoding="utf-8") as fh:
            fh.write(generated)
        compile_log = io.StringIO()
        with contextlib.redirect_stdout(compile_log):
            compiled = compileall.compile_dir(staging, quiet=1, force=True)
        if not compiled:
            raise InstallError("compileall failed in the staged tree: "
                               + " ".join(compile_log.getvalue().split())[:400])
        receipt = {
            "schema_version": RECEIPT_SCHEMA_VERSION,
            "version": version_id,
            "tree": display,
            "source_commit": sha,
            "source_dirty": dirty,
            "generated_at": (now or datetime.datetime.now(datetime.timezone.utc)).strftime(
                "%Y-%m-%dT%H:%M:%SZ"),
            "files": tree_file_digests(staging),
            "owned_hooks": owned,
            "checks": {"compileall": "ok"},
        }
        with open(os.path.join(staging, RECEIPT_NAME), "w", encoding="utf-8") as fh:
            json.dump(receipt, fh, indent=2, sort_keys=True)
            fh.write("\n")
        os.rename(staging, tree)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return receipt


# ---- installation state ------------------------------------------------------------
PENDING_NAME = "install-pending.json"
PENDING_SCHEMA_VERSION = 1
# Registered commands name a tree in display form. A command points into a tree only when
# it has the shape the installer itself registers (python3, a script under that tree's
# hooks/, flags); a command that merely mentions such a path is a user entry.
HARNESS_TREE_PREFIX = "~/.claude/harness/"
HARNESS_COMMAND = re.compile(
    r"^python3 ~/\.claude/harness/([A-Za-z0-9][A-Za-z0-9+._-]*)/hooks/(" + SCRIPT_PATH + r")" + FLAGS + r"$")
VERSION_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9+._-]*")
STAGING_MARK = ".staging-"
# The Claude Code runtime processes that write $HOME/.claude/settings.json: the desktop
# app's embedded runtime (claude-code/<version>/.../claude.app/Contents/MacOS/claude), the
# CLI binary (claude/versions/<version>, usually run through a `claude` symlink, so the
# executable's basename is what both share), and the npm entry point. The Electron shell
# `Claude`, its `Claude Helper` processes and `disclaimer` are not the runtime.
CLAUDE_CODE_EXECUTABLE = "claude"
CLAUDE_CODE_VERSIONED_PATH = "/claude/versions/"
CLAUDE_CODE_ENTRY_POINT = "@anthropic-ai/claude-code/"
SCRIPT_RUNTIMES = ("node", "nodejs", "bun")
RESIDUAL_SENTENCE = ("a settings.json write by one of them between the installer's final stat and "
                     "its rename would be overwritten and cannot be detected afterwards")


# Interpreter options that take the next token as their operand; `--opt=value` is one token.
OPTIONS_WITH_OPERAND = frozenset({
    "-r", "--require", "--import", "--loader", "--experimental-loader", "-C", "--conditions",
    "--input-type", "--title", "--stack-trace-limit", "--max-old-space-size", "-e", "--eval",
    "-p", "--print"})


def script_operand(comm, args):
    """-> the script an interpreter process executes: the first operand after the executable
    that is neither an option nor the operand of an option that takes one. The executable is
    the comm column, so a path with spaces is removed whole."""
    rest = args[len(comm):] if args.startswith(comm) else args.split(" ", 1)[1] if " " in args else ""
    tokens = rest.split()
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in OPTIONS_WITH_OPERAND:
            index += 2
            continue
        if token.startswith("-"):
            index += 1
            continue
        return token
    return ""


def is_claude_code_process(comm, args):
    """True for the runtime's own executable or an interpreter running its entry point.

    The executable's basename `claude` covers the desktop app's embedded runtime and the
    CLI run through its symlink; the versioned path covers the CLI binary run directly. The
    npm entry point counts only as the script operand of an interpreter, so a `grep` over a
    log that names it, or another script that takes the path as an argument, is not one.
    """
    base = os.path.basename(comm)
    if base == CLAUDE_CODE_EXECUTABLE or CLAUDE_CODE_VERSIONED_PATH in comm:
        return True
    return base in SCRIPT_RUNTIMES and CLAUDE_CODE_ENTRY_POINT in script_operand(comm, args)


def claude_processes(ps_rows=None):
    """-> [(pid, executable)] Claude Code runtime processes, or None when ps cannot be read.

    `ps_rows` is the selftest seam: [(pid, comm, args)]. The real list comes from two ps
    columns read separately, because a path with spaces cannot be split out of one row.
    """
    if ps_rows is None:
        try:
            comm_out = subprocess.run(["ps", "-axo", "pid=,comm="], capture_output=True,
                                      text=True, check=True).stdout
            args_out = subprocess.run(["ps", "-axo", "pid=,args="], capture_output=True,
                                      text=True, check=True).stdout
        except (OSError, subprocess.CalledProcessError):
            return None
        args_by_pid = {}
        for line in args_out.splitlines():
            pid, _sep, args = line.strip().partition(" ")
            if pid.isdigit():
                args_by_pid[int(pid)] = args.strip()
        ps_rows = []
        for line in comm_out.splitlines():
            pid, _sep, comm = line.strip().partition(" ")
            if pid.isdigit():
                ps_rows.append((int(pid), comm.strip(), args_by_pid.get(int(pid), "")))
    found = []
    for pid, comm, args in ps_rows:
        if is_claude_code_process(comm, args):
            found.append((int(pid), comm if os.path.basename(comm) == CLAUDE_CODE_EXECUTABLE
                          or CLAUDE_CODE_VERSIONED_PATH in comm else args))
    return found


def process_report(running):
    """-> the one-sentence residual for a non-empty process list, or '' when it is empty."""
    if not running:
        return ""
    listed = ", ".join(str(pid) for pid, _exe in running[:8])
    return (f"{len(running)} Claude Code process(es) running (pids {listed}): {RESIDUAL_SENTENCE}")


def pending_marker_path(home):
    return os.path.join(claude_home(home), "state", PENDING_NAME)


def harness_version_of(command):
    """-> the tree version a registered command executes a hook from, or None."""
    found = HARNESS_COMMAND.match(command) if isinstance(command, str) else None
    return found.group(1) if found else None


def instruction_file_provenance(text):
    """-> {"tree", "commit"} named by an installed instruction file's provenance paragraph."""
    found = re.search(r"`AGENTS\.md` and `CLAUDE\.md` at (\S+)\. .*?the active tree is `([^`]+)`",
                      text or "", re.S)
    return {"tree": found.group(2), "commit": found.group(1)} if found else None


def _owned_set(receipt):
    return {owned_identity(h) for h in receipt["owned_hooks"]}


def installation_state(home, source_root=None):
    """-> one structured view of the installation; --check and --activate both consume it.

    trees            {version: receipt} for every readable staged receipt
    broken_trees     {version: reason} for a receipt that could not be loaded
    active           the active receipt, or None
    pending          the pending-activation marker, or None
    handlers         every registered handler, classified exactly once: owned (by the tree
                     whose receipt lists its five-tuple identity), orphan (the command points
                     into a harness tree version that has no receipt, so nothing can own or
                     remove it), or foreign (a user entry, including an owned command
                     re-registered under another event or matcher; read for classification
                     only)
    wired_versions   the tree versions that owned handlers point at
    instruction_file the tree and commit named by the installed CLAUDE.md, or None
    verdicts         inconsistencies, each with its repair instruction
    drift            the active tree's file digests and generated-copy comparisons
    """
    state = {"trees": {}, "broken_trees": {}, "active": None, "pending": None, "handlers": [],
             "wired_versions": set(), "instruction_file": None, "verdicts": [], "drift": [],
             "settings_error": None}
    verdicts = state["verdicts"]
    root = os.path.join(claude_home(home), "harness")
    if os.path.isdir(root):
        for name in sorted(os.listdir(root)):
            path = os.path.join(root, name, RECEIPT_NAME)
            if not os.path.isfile(path):
                continue
            # A directory left by an interrupted --stage carries a receipt for a version
            # whose tree does not exist; it is never a staged tree.
            if STAGING_MARK in name or not VERSION_ID.fullmatch(name):
                state["broken_trees"][name] = "not a staged tree: an interrupted staging directory"
                continue
            try:
                receipt = load_receipt(path)
            except InstallError as exc:
                state["broken_trees"][name] = str(exc)
                continue
            if receipt["version"] != name:
                state["broken_trees"][name] = (f"receipt names version {receipt['version']!r} but the "
                                               f"directory is {name!r}")
                continue
            state["trees"][name] = receipt
    active_path = active_receipt_path(home)
    if os.path.isfile(active_path):
        try:
            state["active"] = load_receipt(active_path)
        except InstallError as exc:
            verdicts.append(f"active receipt unreadable: {exc}; run --activate <version> to rewrite it")
    marker_path = pending_marker_path(home)
    if os.path.isfile(marker_path):
        decoded = False
        try:
            pending = load_json(marker_path)
            decoded = True
        except (OSError, ValueError) as exc:
            pending = None
            verdicts.append(f"pending marker unreadable: {exc}; run --activate <version> to replace it")
        if decoded:
            # Whatever decoded is validated, including JSON null: a marker file that is
            # present is never read as absent.
            problems = marker_problems(pending)
            if problems:
                verdicts.append(f"pending marker malformed ({'; '.join(problems)}); run --activate "
                                f"<version> to replace it")
            else:
                state["pending"] = pending
    settings_path = os.path.join(claude_home(home), "settings.json")
    settings = {}
    if os.path.isfile(settings_path):
        try:
            settings = load_json(settings_path)
        except ValueError as exc:
            state["settings_error"] = f"settings.json is not valid JSON: {exc}"
            verdicts.append(state["settings_error"])
    owned_by = {}
    for version, receipt in state["trees"].items():
        for identity in _owned_set(receipt):
            owned_by.setdefault(identity, version)
    for event, matcher, handler in registered_handlers(settings):
        identity = handler_identity(event, matcher, handler)
        pointed = harness_version_of(handler.get("command"))
        if identity in owned_by:
            kind, version = "owned", owned_by[identity]
            state["wired_versions"].add(version)
        elif pointed is not None and pointed not in state["trees"] and pointed not in state["broken_trees"]:
            # The command points into a tree version that has no receipt: nothing can own
            # or remove it. A command into a staged tree under an event or matcher its
            # receipt does not list is a user entry and stays.
            kind, version = "orphan", pointed
        else:
            kind, version = "foreign", None
        state["handlers"].append({"event": event, "matcher": matcher, "handler": handler,
                                  "identity": identity, "kind": kind, "version": version})
    installed_md = os.path.join(claude_home(home), "CLAUDE.md")
    try:
        installed_text = read_text(installed_md)
    except OSError:
        installed_text = None
    state["instruction_file"] = instruction_file_provenance(installed_text)
    active = state["active"]
    active_version = active["version"] if active else None
    wired = state["wired_versions"]
    pending = state["pending"]
    if pending:
        to, frm = pending.get("to"), pending.get("from")
        to_receipt = state["trees"].get(to)
        wired_identities = {h["identity"] for h in state["handlers"] if h["kind"] == "owned"}
        if active_version == to:
            stage = "before the marker was cleared"
        elif state["instruction_file"] and state["instruction_file"]["tree"] == tree_display(to):
            stage = "after the instruction file"
        elif to_receipt and _owned_set(to_receipt) and _owned_set(to_receipt) <= wired_identities:
            stage = "after the switch"
        else:
            stage = "before the switch"
        verdicts.append(f"activation of {to} interrupted {stage}; run --activate {to} to finish"
                        + (f" or --activate {frm} to roll back" if frm else ""))
    if active is not None and wired != {active_version}:
        verdicts.append(f"settings wire {sorted(wired) or 'no tree'} but the active receipt is "
                        f"{active_version}; run --activate {active_version}")
    elif active is None and wired:
        verdicts.append(f"settings wire {sorted(wired)} but no receipt is active; run --activate "
                        f"{sorted(wired)[0]}")
    if active is not None:
        # The active receipt is the staged receipt of its version plus activation fields; a
        # difference means one of them was edited, and the owned entries can no longer be
        # trusted to describe what the tree registered.
        staged_copy = state["trees"].get(active_version)
        if staged_copy is None and active_version not in state["broken_trees"]:
            verdicts.append(f"active receipt names version {active_version}, which is not staged; "
                            f"re-stage it or run --activate <another version>")
        elif staged_copy is not None and any(
                staged_copy.get(key) != active.get(key) for key in ("tree", "files", "owned_hooks")):
            verdicts.append(f"active receipt differs from the staged receipt of {active_version} "
                            f"(tree, files or owned entries); run --activate {active_version}")
    if active is not None:
        named = state["instruction_file"]
        if named is None:
            verdicts.append(f"CLAUDE.md is absent or carries no provenance paragraph; active is "
                            f"{active['tree']}; run --activate {active_version}")
        elif named["tree"] != active["tree"]:
            verdicts.append(f"CLAUDE.md was generated for {named['tree']}, active is "
                            f"{active['tree']}; run --activate {active_version}")
    for h in state["handlers"]:
        if h["kind"] == "orphan":
            verdicts.append(f"orphaned harness handler {h['event']} {h['handler'].get('command')!r}: "
                            f"no staged tree owns it; re-stage that version or run --activate "
                            f"with --remove-orphans")
    for version, reason in state["broken_trees"].items():
        verdicts.append(f"staged tree {version}: {reason}; remove or re-stage it")
    if active is not None:
        counts = {}
        for h in state["handlers"]:
            counts[h["identity"]] = counts.get(h["identity"], 0) + 1
        for h in active["owned_hooks"]:
            hits = counts.get(owned_identity(h), 0)
            if hits != 1:
                verdicts.append(f"owned hook {h['event']} {h['command']!r}: {hits} match(es); "
                                f"run --activate {active_version}")
        tree = expand_display(home, active["tree"])
        drifted, unloadable = tree_problems(tree, active)
        state["drift"].extend(drifted)
        for problem in unloadable:
            verdicts.append(f"owned hook {problem}; re-stage {active_version}")
        try:
            tree_copy = read_text(os.path.join(tree, "CLAUDE.generated.md"))
        except (OSError, UnicodeDecodeError) as exc:
            tree_copy = None
            state["drift"].append(f"instruction file unreadable: {exc}")
        if tree_copy is not None and installed_text != tree_copy:
            state["drift"].append("CLAUDE.md differs from the active tree's generated copy")
        if source_root is not None and tree_copy is not None:
            expected = render_instruction_file(source_root, tree=active["tree"],
                                               commit=active.get("source_commit") or TEMPLATE_COMMIT)
            if expected != tree_copy:
                state["drift"].append("generator output from the current source differs from the "
                                      "active tree; the source moved since this tree was staged")
    return state


# ---- activate ------------------------------------------------------------------
def _settings_state(path):
    try:
        st = os.stat(path)
    except FileNotFoundError:
        return None
    return (st.st_ino, st.st_size, st.st_mtime_ns)


def activate(home, version_id, fault=None, between_read_and_replace=None, after_replace=None,
             attempts=5, remove_orphans=False, log=None, processes=None, require_quiescent=False):
    """Switch $HOME/.claude/settings.json to the tree's owned hooks as a logged transaction.

    In order: report the Claude Code processes that could write settings.json meanwhile
    (refuse when `require_quiescent` and any is running, or the list cannot be read); derive
    the installation state and refuse on an unreadable staged receipt or an orphaned harness
    handler (unless `remove_orphans`); build the removal set from every staged receipt plus
    the active receipt; verify the target tree against its receipt at the fence; write the
    pending marker; read-merge-replace settings.json under the stat guard with retries; verify
    the written file; install CLAUDE.md; write the active receipt; clear the marker. A stop
    anywhere after the marker is written leaves it in place, --check names the stage, and the
    next --activate of any version completes a consistent switch because the removal set
    covers every version.

    `fault` plants a stop: "before-replace" (the merged file is written beside settings.json,
    the replace never happens), "after-marker" (the marker is written, the replace never
    happens), "after-instruction-file", or "after-receipt".
    `between_read_and_replace` and `after_replace` are selftest seams for a concurrent
    writer and for a stop after the replace; `processes` is the seam for the process list.
    `log` receives one line per notable event.
    """
    log = log or (lambda line: None)
    running = claude_processes() if processes is None else processes()
    if running is None:
        if require_quiescent:
            raise InstallError("cannot list processes, so quiescence cannot be confirmed "
                               "(--require-quiescent)")
        log("cannot list processes: whether a Claude Code process could write settings.json "
            "meanwhile is unknown")
    elif running:
        if require_quiescent:
            raise InstallError(f"refusing to activate (--require-quiescent): {process_report(running)}")
        log(process_report(running))
    if STAGING_MARK in version_id or not VERSION_ID.fullmatch(version_id):
        raise InstallError(f"{version_id!r} is not a staged version id")
    tree = tree_path(home, version_id)
    receipt = load_receipt(os.path.join(tree, RECEIPT_NAME))
    if receipt["version"] != version_id:
        raise InstallError(f"receipt under {tree} names version {receipt['version']!r}, not {version_id!r}")
    owned = receipt["owned_hooks"]
    if not owned:
        raise InstallError("receipt owns no hook entries")
    state = installation_state(home)
    if state["broken_trees"]:
        raise InstallError("refusing to activate with unreadable staged receipt(s): "
                           + "; ".join(f"{v}: {why}" for v, why in state["broken_trees"].items()))
    orphans = [h for h in state["handlers"] if h["kind"] == "orphan"]
    if orphans and not remove_orphans:
        raise InstallError("refusing to activate: orphaned harness handler(s) no staged tree owns: "
                           + "; ".join(f"{h['event']} {h['handler'].get('command')!r}" for h in orphans)
                           + "; re-stage that version or pass --remove-orphans")
    active = state["active"]
    active_version = active["version"] if active else None
    target = {owned_identity(h) for h in owned}
    remove = set(target)
    for staged in state["trees"].values():
        remove |= _owned_set(staged)
    if active is not None:
        remove |= _owned_set(active)
    if orphans:
        remove |= {h["identity"] for h in orphans}
        log(f"removing {len(orphans)} orphaned harness handler(s) (--remove-orphans)")
    leftover = sorted({h["version"] for h in state["handlers"]
                       if h["kind"] == "owned" and h["version"] not in (version_id, active_version)})
    pending = state["pending"]
    if pending or leftover:
        log("completing an interrupted switch: "
            + (f"marker from {pending.get('from')} to {pending.get('to')}; " if pending else "")
            + (f"settings wire {leftover} while the active receipt is {active_version or 'absent'}"
               if leftover else "every version's entries are removed before this one's are added"))

    def refuse_unverified_target():
        # Judged on every attempt, before the temp file and before the stat guard reads the
        # settings state, so nothing is written on refusal and a settings write that lands
        # during the check is still seen; a target edited after staging is named.
        drifted, unloadable = tree_problems(tree, receipt)
        if drifted:
            raise InstallError(f"refusing to activate {version_id}: the staged tree does not match "
                               f"its receipt: " + "; ".join(drifted))
        if unloadable:
            raise InstallError("refusing to activate a tree whose hooks cannot load: "
                               + "; ".join(unloadable))

    settings_path = os.path.join(claude_home(home), "settings.json")
    os.makedirs(os.path.dirname(settings_path), exist_ok=True)
    marker_path = pending_marker_path(home)
    for attempt in range(attempts):
        before = _settings_state(settings_path)
        if before is None:
            current = {}
        else:
            try:
                current = load_json(settings_path)
            except ValueError as exc:
                raise InstallError(f"settings.json is not valid JSON: {exc}")
            if not isinstance(current, dict):
                raise InstallError("settings.json top level is not an object")
        merged = merge_hooks(current, remove, owned)
        data = (json.dumps(merged, indent=2) + "\n").encode("utf-8")
        if between_read_and_replace is not None:
            between_read_and_replace(attempt)
        refuse_unverified_target()
        fd, tmp = tempfile.mkstemp(prefix=".settings-", dir=os.path.dirname(settings_path))
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
                fh.flush()
                os.fsync(fh.fileno())
            os.chmod(tmp, 0o644)
            if _settings_state(settings_path) != before:
                os.remove(tmp)
                continue
            if fault == "before-replace":
                os.remove(tmp)
                raise InstallError("planted fault: activation abandoned before the settings replace")
            marker = {
                "schema_version": PENDING_SCHEMA_VERSION,
                "from": active_version,
                "to": version_id,
                "merged_sha256": hashlib.sha256(data).hexdigest(),
                "started_at": datetime.datetime.now(datetime.timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"),
            }
            atomic_write(marker_path, (json.dumps(marker, indent=2, sort_keys=True) + "\n").encode("utf-8"))
            if fault == "after-marker":
                os.remove(tmp)
                raise InstallError("planted fault: stopped after the marker, before the replace")
            os.replace(tmp, settings_path)
        except BaseException:
            with contextlib.suppress(OSError):
                os.remove(tmp)
            raise
        break
    else:
        raise InstallError(f"settings.json changed under every one of {attempts} merge attempts")
    if after_replace is not None:
        after_replace()
    try:
        written = load_json(settings_path)
    except (OSError, ValueError) as exc:
        raise InstallError(f"post-write verification failed: settings.json unreadable: {exc}")
    found = registered_handlers(written)
    problems = []
    for h in owned:
        hits = [1 for event, matcher, handler in found
                if handler_identity(event, matcher, handler) == owned_identity(h)]
        if len(hits) != 1:
            problems.append(f"{h['event']} {h['command']!r}: {len(hits)} match(es), expected 1")
    stale = remove - target
    for event, matcher, handler in found:
        if handler_identity(event, matcher, handler) in stale:
            problems.append(f"{event} {handler.get('command')!r}: removed entry still present")
    if problems:
        raise InstallError("post-write verification failed: " + "; ".join(problems))
    try:
        with open(os.path.join(tree, "CLAUDE.generated.md"), "rb") as fh:
            generated = fh.read()
    except OSError as exc:
        raise InstallError(f"stopped after the switch: the instruction file of {version_id} is "
                           f"unreadable: {exc}; run --activate {version_id} again")
    atomic_write(os.path.join(claude_home(home), "CLAUDE.md"), generated)
    if fault == "after-instruction-file":
        raise InstallError("planted fault: stopped after the instruction file was installed")
    activated = dict(receipt)
    activated["activated_at"] = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")
    atomic_write(active_receipt_path(home),
                 (json.dumps(activated, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    if fault == "after-receipt":
        raise InstallError("planted fault: stopped after the active receipt was written")
    # Every durable write is done; an already-absent marker is not an inconsistency.
    with contextlib.suppress(FileNotFoundError):
        os.remove(marker_path)
    return activated


# ---- check ---------------------------------------------------------------------
def harness_scripts(source_root):
    names = set()
    hooks_dir = os.path.join(source_root, "hooks")
    if os.path.isdir(hooks_dir):
        names = {name for name in os.listdir(hooks_dir) if name.endswith(".py")}
    return names


def check(home, source_root, out=sys.stdout, processes=None):
    """-> 0 when the active install is consistent, matches its receipt and the generator; else 1.

    The residual of the settings-write race is named whenever a Claude Code process is
    running; it is a report, never a verdict, because --check does not write anything.
    """
    p = lambda *a: print(*a, file=out)
    running = claude_processes() if processes is None else processes()
    if running is None:
        p("  processes: cannot list; whether a Claude Code process is running is unknown")
    elif running:
        p(f"  residual: {process_report(running)}")
    state = installation_state(home, source_root)
    scripts = harness_scripts(source_root)
    installed_md = os.path.join(claude_home(home), "CLAUDE.md")
    if state["active"] is None and state["pending"] is None and not state["wired_versions"]:
        p(f"  no install receipt at {active_receipt_path(home)}: hand-made install, nothing is owned")
        sha, _dirty = source_commit(source_root)
        expected = render_instruction_file(source_root, tree="~/.claude", commit=sha or TEMPLATE_COMMIT)
        try:
            actual = read_text(installed_md)
        except OSError:
            actual = None
        if actual is None:
            p("  CLAUDE.md: absent")
        else:
            differing = sum(
                1 for line in difflib.unified_diff(
                    expected.splitlines(), actual.splitlines(), lineterm="", n=0)
                if line[:1] in "+-" and line[:3] not in ("+++", "---"))
            p(f"  CLAUDE.md: {'equals' if actual == expected else 'differs from'} the generator's "
              f"output for the legacy ~/.claude layout ({differing} added or removed line(s))")
        for h in state["handlers"]:
            command = h["handler"].get("command", "")
            if h["kind"] == "orphan" or any(f"/hooks/{name}" in command for name in scripts):
                p(f"  unowned harness handler: {h['event']} {command!r}")
        for verdict in state["verdicts"]:
            p(f"  INCONSISTENT {verdict}")
        p(f"INSTALL-CHECK-SUMMARY receipt=absent files=0 inconsistencies={len(state['verdicts']) + 1} "
          f"drift=0 exit=1")
        return 1
    active = state["active"]
    if active is not None:
        p(f"  active tree {active['tree']} version={active['version']} "
          f"source_commit={active.get('source_commit')}")
    else:
        p("  no active receipt")
    if state["pending"]:
        p(f"  pending marker: from={state['pending'].get('from')} to={state['pending'].get('to')} "
          f"started_at={state['pending'].get('started_at')}")
    for h in state["handlers"]:
        command = h["handler"].get("command", "")
        if h["kind"] == "foreign" and any(f"/hooks/{name}" in command for name in scripts):
            p(f"  unowned harness handler: {h['event']} {command!r}")
    for verdict in state["verdicts"]:
        p(f"  INCONSISTENT {verdict}")
    for item in state["drift"]:
        p(f"  DRIFT {item}")
    code = 1 if state["verdicts"] or state["drift"] else 0
    files = len(active.get("files", {})) if active else 0
    p(f"INSTALL-CHECK-SUMMARY receipt={'present' if active else 'absent'} files={files} "
      f"inconsistencies={len(state['verdicts'])} drift={len(state['drift'])} exit={code}")
    return code


# ---- selftest ------------------------------------------------------------------
def selftest():
    checks = bad = 0

    def chk(label, ok):
        nonlocal checks, bad
        checks += 1
        bad += (not ok)
        print(f"  {'PASS' if ok else 'FAIL'} {label}")

    def raises(call, needle):
        try:
            call()
        except InstallError as exc:
            return needle in str(exc)
        return False

    # Every activation below runs with an empty process list so this host's own sessions
    # cannot change a verdict; the residual proofs pass their own lists to the real function.
    real_activate = globals()["activate"]

    def activate(home, version_id, **seams):
        seams.setdefault("processes", lambda: [])
        return real_activate(home, version_id, **seams)

    def reproduction(thread_id, expected_line):
        """Run a reviewer's reproduction script verbatim; it exits 0 only at the expected outcome."""
        path = os.path.join(ROOT, "instruments", "reproductions", "pr-36", f"{thread_id}.py")
        done = subprocess.run([sys.executable, path], cwd=ROOT, capture_output=True, text=True,
                              timeout=600, env=dict(os.environ, ZH_REVIEW_REPRODUCTIONS="nested"))
        return done.returncode == 0 and expected_line in done.stdout

    # --- the generator against the real repository (read-only)
    rendered = render_instruction_file(ROOT)
    agents = read_text(os.path.join(ROOT, "AGENTS.md"))
    claude = read_text(os.path.join(ROOT, "CLAUDE.md"))
    chk("render opens with the shared policy byte-for-byte", rendered.startswith(agents))
    chk("render carries the adapter heading once after the policy",
        rendered.count(ADAPTER_HEADING) == 1 and rendered.index(ADAPTER_HEADING) >= len(agents))
    chk("render drops the import line", IMPORT_LINE not in rendered[len(agents):])
    chk("render replaces the repository-only opening paragraph with provenance",
        REPLACED_PARAGRAPH_PREFIX not in rendered and TEMPLATE_COMMIT in rendered
        and TEMPLATE_TREE in rendered)
    substitutions = sum(claude.count(prefix) for prefix in PATH_SUBSTITUTIONS)
    chk(f"render templates every ~/.claude/hooks and tools path ({substitutions} in CLAUDE.md)",
        substitutions > 0 and not any(prefix in rendered[len(agents):] for prefix in PATH_SUBSTITUTIONS)
        and rendered.count(TEMPLATE_TREE + "/") == substitutions)
    chk("render is deterministic", render_instruction_file(ROOT) == rendered)
    chk("render with a real tree and commit differs only in the templated values",
        render_instruction_file(ROOT, tree="~/.claude/harness/0.0.0+abc", commit="abc")
        == rendered.replace(TEMPLATE_TREE, "~/.claude/harness/0.0.0+abc").replace(TEMPLATE_COMMIT, "abc"))

    with tempfile.TemporaryDirectory() as td:
        # --- a synthetic source: tiny hooks that answer, the real policy and adapter
        source = os.path.join(td, "source")
        os.makedirs(os.path.join(source, "hooks"))
        os.makedirs(os.path.join(source, "tools"))
        os.makedirs(os.path.join(source, ".codex-plugin"))
        guard = ("import json, sys\n"
                 "payload = json.load(sys.stdin)\n"
                 "print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse', "
                 "'permissionDecision': 'allow', 'answered_by': sys.argv[0]}}))\n")
        open(os.path.join(source, "hooks", "stub_guard.py"), "w").write(guard)
        open(os.path.join(source, "hooks", "stop_guard.py"), "w").write("import sys\nsys.exit(0)\n")
        open(os.path.join(source, "tools", "tool.py"), "w").write("VALUE = 1\n")
        shutil.copyfile(os.path.join(ROOT, "AGENTS.md"), os.path.join(source, "AGENTS.md"))
        shutil.copyfile(os.path.join(ROOT, "CLAUDE.md"), os.path.join(source, "CLAUDE.md"))
        json.dump({"version": "0.0.1"}, open(os.path.join(source, ".codex-plugin", "plugin.json"), "w"))
        source_settings = {
            "model": "fixture",
            "permissions": {"allow": ["Bash(echo:*)"], "defaultMode": "auto"},
            "hooks": {
                "Stop": [{"hooks": [{"type": "command",
                                     "command": "python3 ~/.claude/hooks/stop_guard.py", "timeout": 5}]}],
                "PreToolUse": [{"matcher": "Bash", "hooks": [{
                    "type": "command",
                    "command": "python3 ~/.claude/hooks/stub_guard.py --require-scratch",
                    "timeout": 5}]}],
            },
        }
        json.dump(source_settings, open(os.path.join(source, "settings.json"), "w"), indent=2)

        home = os.path.join(td, "home")
        os.makedirs(os.path.join(home, ".claude"))
        user_settings = {
            "permissions": {"allow": ["Bash(ls:*)"], "defaultMode": "auto"},
            "model": "user-choice",
            "hooks": {"PreToolUse": [{"matcher": "Write", "hooks": [{
                "type": "command", "command": "echo user-hook", "timeout": 3}]}]},
            "autoMode": {"managed": True},
        }
        settings_path = os.path.join(home, ".claude", "settings.json")
        json.dump(user_settings, open(settings_path, "w"), indent=2)

        chk("owned entries are derived from the source settings and point at the tree",
            [h["command"] for h in owned_hook_entries(source_settings, "~/.claude/harness/v1")]
            == ["python3 ~/.claude/harness/v1/hooks/stop_guard.py",
                "python3 ~/.claude/harness/v1/hooks/stub_guard.py --require-scratch"])
        foreign = copy.deepcopy(source_settings)
        foreign["hooks"]["Stop"][0]["hooks"][0]["command"] = "python3 ~/.claude/hooks/x.py || true"
        chk("a source handler the installer cannot own is refused, never adopted",
            raises(lambda: owned_hook_entries(foreign, "~/.claude/harness/v1"), "does not own"))

        # --- stage
        receipt = stage(source, home, version_id="v1")
        tree = tree_path(home, "v1")
        chk("stage creates the versioned tree with hooks, tools, sources, generated file, receipt",
            all(os.path.exists(os.path.join(tree, rel)) for rel in (
                "hooks/stub_guard.py", "tools/tool.py", "AGENTS.source.md", "CLAUDE.source.md",
                "CLAUDE.generated.md", RECEIPT_NAME)))
        chk("stage byte-compiles the tree",
            os.path.isdir(os.path.join(tree, "hooks", "__pycache__")))
        chk("the receipt digests match the staged files",
            all(sha256_file(os.path.join(tree, rel)) == rec["sha256"]
                for rel, rec in receipt["files"].items()) and len(receipt["files"]) == 6)
        chk("the receipt records owned entries, version, tree, and the compileall check",
            receipt["version"] == "v1" and receipt["tree"] == "~/.claude/harness/v1"
            and receipt["checks"] == {"compileall": "ok"} and len(receipt["owned_hooks"]) == 2)
        chk("the receipt is schema 2 and every owned entry carries all five identity fields",
            receipt["schema_version"] == 2 and all(
                all(key in h for key in HANDLER_IDENTITY_KEYS) for h in receipt["owned_hooks"]))
        legacy = dict(receipt, schema_version=1)
        legacy_path = os.path.join(td, "legacy-receipt.json")
        json.dump(legacy, open(legacy_path, "w"))
        chk("a schema 1 receipt still loads: the fields are the same, only identity semantics changed",
            load_receipt(legacy_path)["version"] == "v1")
        json.dump(dict(receipt, schema_version=3), open(legacy_path, "w"))
        chk("a receipt of an unknown schema version is refused, never read as empty",
            raises(lambda: load_receipt(legacy_path), "schema_version 3"))
        json.dump(dict(receipt, owned_hooks=[{"type": "command", "command": "x", "timeout": 1}]),
                  open(legacy_path, "w"))
        chk("a receipt whose owned entry lacks event or matcher is refused",
            raises(lambda: load_receipt(legacy_path), "owned_hooks[0] must carry event, matcher"))
        chk("the generated file in the tree is templated with the tree's own path",
            "~/.claude/harness/v1/hooks/" in read_text(os.path.join(tree, "CLAUDE.generated.md")))
        chk("a staged tree is immutable: staging the same version again is refused",
            raises(lambda: stage(source, home, version_id="v1"), "already staged"))
        broken = os.path.join(td, "broken-source")
        shutil.copytree(source, broken)
        open(os.path.join(broken, "hooks", "bad.py"), "w").write("def (:\n")
        chk("stage refuses a tree that does not byte-compile and leaves no tree behind",
            raises(lambda: stage(broken, home, version_id="v-broken"), "compileall failed")
            and not os.path.lexists(tree_path(home, "v-broken"))
            and not any(name.startswith("v-broken") for name in os.listdir(os.path.dirname(tree))))
        chk("stage refuses an unsafe version id",
            raises(lambda: stage(source, home, version_id="../escape"), "not a safe"))

        # --- activate v1
        active = activate(home, "v1")
        written = load_json(settings_path)
        commands = [h.get("command") for _e, _m, h in registered_handlers(written)]
        chk("activation registers every owned handler exactly once",
            commands.count("python3 ~/.claude/harness/v1/hooks/stop_guard.py") == 1
            and commands.count("python3 ~/.claude/harness/v1/hooks/stub_guard.py --require-scratch") == 1)
        chk("activation carries the user's own hook, permissions, model, and app-managed keys through",
            "echo user-hook" in commands and written["permissions"] == user_settings["permissions"]
            and written["model"] == "user-choice" and written["autoMode"] == {"managed": True})
        chk("activation installs the generated instruction file",
            read_text(os.path.join(home, ".claude", "CLAUDE.md"))
            == read_text(os.path.join(tree, "CLAUDE.generated.md")))
        chk("activation writes the active receipt with an activation time",
            load_json(active_receipt_path(home))["version"] == "v1" and "activated_at" in active)
        env = dict(os.environ, HOME=home)
        argv = shlex.split(commands[commands.index(
            "python3 ~/.claude/harness/v1/hooks/stub_guard.py --require-scratch")])
        argv = [os.path.expanduser(part) if part.startswith("~/") else part for part in argv]
        argv = [part.replace(os.path.expanduser("~"), home, 1) if part.startswith(os.path.expanduser("~")) else part for part in argv]
        answer = subprocess.run([sys.executable] + argv[1:], input=b'{"tool_name":"Bash"}',
                                capture_output=True, env=env)
        chk("the registered command answers from the active tree",
            answer.returncode == 0 and b'"permissionDecision": "allow"' in answer.stdout
            and b"harness/v1/hooks/stub_guard.py" in answer.stdout)
        activate(home, "v1")
        again = [h.get("command") for _e, _m, h in registered_handlers(load_json(settings_path))]
        chk("re-activating the active tree is idempotent", again == commands)

        # --- an activation killed between staging and the settings replace
        open(os.path.join(source, "hooks", "stub_guard.py"), "a").write("# v2\n")
        stage(source, home, version_id="v2")
        before_bytes = open(settings_path, "rb").read()
        chk("a planted fault before the replace is reported as a failed activation",
            raises(lambda: activate(home, "v2", fault="before-replace"), "before the settings replace"))
        after_bytes = open(settings_path, "rb").read()
        chk("after the fault, settings.json is byte-identical: the previous tree stays active",
            after_bytes == before_bytes)
        chk("after the fault, the active receipt and instruction file are still v1's",
            load_json(active_receipt_path(home))["version"] == "v1"
            and read_text(os.path.join(home, ".claude", "CLAUDE.md"))
            == read_text(os.path.join(tree, "CLAUDE.generated.md")))
        chk("after the fault, no stray temporary settings file is left beside settings.json",
            not [n for n in os.listdir(os.path.join(home, ".claude")) if n.startswith(".settings-")])
        answer = subprocess.run([sys.executable] + argv[1:], input=b'{"tool_name":"Bash"}',
                                capture_output=True, env=env)
        chk("after the fault, the previous tree's guard still answers",
            answer.returncode == 0 and b"harness/v1/hooks/stub_guard.py" in answer.stdout)

        # --- the real switch to v2
        activate(home, "v2")
        commands = [h.get("command") for _e, _m, h in registered_handlers(load_json(settings_path))]
        chk("activating v2 replaces v1's owned entries and only those",
            not any("harness/v1/" in c for c in commands)
            and commands.count("python3 ~/.claude/harness/v2/hooks/stop_guard.py") == 1
            and "echo user-hook" in commands)
        chk("the v1 tree is untouched after the switch, so rollback is the same replace back",
            os.path.isfile(os.path.join(tree, "hooks", "stub_guard.py")))
        activate(home, "v1")
        commands = [h.get("command") for _e, _m, h in registered_handlers(load_json(settings_path))]
        chk("rollback to v1 is the same switch pointing back",
            not any("harness/v2/" in c for c in commands)
            and commands.count("python3 ~/.claude/harness/v1/hooks/stub_guard.py --require-scratch") == 1)

        # --- identity carries event and matcher: a user entry that reuses an owned command
        # under another event or matcher is not owned and survives a switch either way
        owned_bash = next(h for h in active["owned_hooks"] if h["matcher"] == "Bash")
        reused = {key: owned_bash[key] for key in HANDLER_KEYS}
        current = load_json(settings_path)
        current["hooks"]["PreToolUse"].append({"matcher": "Bash|Shell", "hooks": [dict(reused)]})
        current["hooks"]["PostToolUse"] = [{"matcher": "Bash", "hooks": [dict(reused)]}]
        atomic_write(settings_path, (json.dumps(current, indent=2) + "\n").encode("utf-8"))
        activate(home, "v2")
        kept = sorted((event, matcher) for event, matcher, h in registered_handlers(load_json(settings_path))
                      if h == reused)
        chk("same event, different matcher: the user entry survives activating v2",
            ("PreToolUse", "Bash|Shell") in kept)
        chk("different event, same matcher: the user entry survives activating v2",
            ("PostToolUse", "Bash") in kept)
        chk("activating v2 removed the owned entry itself and kept nothing else of v1",
            kept == [("PostToolUse", "Bash"), ("PreToolUse", "Bash|Shell")]
            and not any("harness/v1/" in h.get("command", "") for e, m, h in
                        registered_handlers(load_json(settings_path)) if (e, m) == ("PreToolUse", "Bash")))
        activate(home, "v1")
        after = registered_handlers(load_json(settings_path))
        chk("rolling back to v1 keeps both user entries and registers the owned one exactly once",
            sorted((event, matcher) for event, matcher, h in after if h == reused)
            == [("PostToolUse", "Bash"), ("PreToolUse", "Bash"), ("PreToolUse", "Bash|Shell")])
        buf = io.StringIO()
        check(home, source, out=buf)
        chk("--check reports those user entries as unowned, not as drift",
            buf.getvalue().count("unowned harness handler") == 2
            and "INSTALL-CHECK-SUMMARY receipt=present files=6 inconsistencies=0 drift=0 exit=0"
            in buf.getvalue())
        current = load_json(settings_path)
        current["hooks"]["PreToolUse"] = [e for e in current["hooks"]["PreToolUse"]
                                          if e.get("matcher") != "Bash|Shell"]
        del current["hooks"]["PostToolUse"]
        atomic_write(settings_path, (json.dumps(current, indent=2) + "\n").encode("utf-8"))
        chk("review reproduction 4294811762: both user entries that reuse the command are retained",
            reproduction(4294811762, "user entries retained: [('PostToolUse', 'Bash'), "
                                     "('PreToolUse', 'Bash|Shell')]"))

        # --- activation is a logged transaction: a stop at any point after the marker is
        # written leaves --check red with the stage named, and the next --activate of either
        # version restores exactly one version's entries
        def wired(home_dir):
            commands = [h.get("command") for _e, _m, h in registered_handlers(
                load_json(os.path.join(home_dir, ".claude", "settings.json")))]
            return {v: sum(f"/harness/{v}/" in c for c in commands) for v in ("v1", "v2")}

        marker_path = pending_marker_path(home)
        activate(home, "v1")
        chk("a completed activation leaves no pending marker", not os.path.exists(marker_path))

        class Stopped(Exception):
            pass

        def stop():
            raise Stopped()

        for label, seams, expected_stage in (
                ("after the replace", {"after_replace": stop}, "after the switch"),
                ("after the instruction file", {"fault": "after-instruction-file"},
                 "after the instruction file"),
                ("after the receipt", {"fault": "after-receipt"}, "before the marker was cleared")):
            activate(home, "v1")
            try:
                activate(home, "v2", **seams)
            except (Stopped, InstallError):
                pass
            buf = io.StringIO()
            code = check(home, source, out=buf)
            marker = load_json(marker_path) if os.path.isfile(marker_path) else None
            chk(f"stopped {label}: the marker names the switch and --check exits 1 naming the stage "
                f"'{expected_stage}'",
                code == 1 and marker is not None and marker["from"] == "v1" and marker["to"] == "v2"
                and f"activation of v2 interrupted {expected_stage}" in buf.getvalue())
            lines = []
            activate(home, "v1", log=lines.append)
            buf = io.StringIO()
            chk(f"stopped {label}: --activate v1 restores exactly v1's entries, clears the marker, "
                f"and --check is clean",
                wired(home) == {"v1": 2, "v2": 0} and not os.path.exists(marker_path)
                and check(home, source, out=buf) == 0
                and any("completing an interrupted switch" in line for line in lines))
            try:
                activate(home, "v2", **seams)
            except (Stopped, InstallError):
                pass
            activate(home, "v2")
            buf = io.StringIO()
            chk(f"stopped {label}: --activate v2 finishes the switch to exactly v2's entries and "
                f"--check is clean",
                wired(home) == {"v1": 0, "v2": 2} and not os.path.exists(marker_path)
                and check(home, source, out=buf) == 0)
            activate(home, "v1")
        atomic_write(marker_path, json.dumps({"schema_version": 1, "from": "v1", "to": "v2",
                                              "merged_sha256": "0" * 64,
                                              "started_at": "2026-01-01T00:00:00Z"}).encode("utf-8"))
        buf = io.StringIO()
        chk("a marker with no switch behind it reads as interrupted before the switch",
            check(home, source, out=buf) == 1
            and "activation of v2 interrupted before the switch" in buf.getvalue())
        activate(home, "v1")
        chk("--activate clears a stale marker", not os.path.exists(marker_path))
        twice = activate(home, "v1")
        buf = io.StringIO()
        chk("re-activating the active version is idempotent: same entries, no marker, --check clean",
            wired(home) == {"v1": 2, "v2": 0} and twice["version"] == "v1"
            and not os.path.exists(marker_path) and check(home, source, out=buf) == 0)

        # --- an orphaned harness handler: a command into the harness directory that no
        # staged receipt owns is refused, never adopted or silently dropped
        current = load_json(settings_path)
        current["hooks"]["Stop"].append({"hooks": [{
            "type": "command", "command": "python3 ~/.claude/harness/v9/hooks/stop_guard.py",
            "timeout": 5}]})
        atomic_write(settings_path, (json.dumps(current, indent=2) + "\n").encode("utf-8"))
        buf = io.StringIO()
        chk("--check names a handler pointing into a harness tree no receipt owns as orphaned",
            check(home, source, out=buf) == 1 and "INCONSISTENT orphaned harness handler Stop "
            "'python3 ~/.claude/harness/v9/hooks/stop_guard.py'" in buf.getvalue())
        chk("--activate refuses while an orphaned harness handler is registered, naming it",
            raises(lambda: activate(home, "v1"), "orphaned harness handler(s) no staged tree owns: "
                                                "Stop 'python3 ~/.claude/harness/v9/hooks/stop_guard.py'"))
        lines = []
        activate(home, "v1", remove_orphans=True, log=lines.append)
        buf = io.StringIO()
        chk("--activate --remove-orphans removes it, says so, and --check is clean",
            not any("harness/v9/" in h.get("command", "")
                    for _e, _m, h in registered_handlers(load_json(settings_path)))
            and check(home, source, out=buf) == 0
            and any("removing 1 orphaned harness handler" in line for line in lines))

        # --- a staged tree whose receipt cannot be read: its entries could not be removed
        broken_tree = tree_path(home, "v-corrupt")
        os.makedirs(broken_tree)
        open(os.path.join(broken_tree, RECEIPT_NAME), "w").write("{not json")
        buf = io.StringIO()
        chk("--check names a staged tree whose receipt cannot be read",
            check(home, source, out=buf) == 1 and "INCONSISTENT staged tree v-corrupt" in buf.getvalue())
        chk("--activate refuses with an unreadable staged receipt",
            raises(lambda: activate(home, "v1"), "unreadable staged receipt(s): v-corrupt"))
        shutil.rmtree(broken_tree)
        buf = io.StringIO()
        chk("--check is clean again once the broken tree is gone", check(home, source, out=buf) == 0)

        # --- a receipt that loads is one the installer can act on: every field it reads later
        # is checked at load, so a thin or mistyped receipt never produces a verdict it cannot
        # back or a crash in place of one
        good_receipt = load_receipt(os.path.join(tree, RECEIPT_NAME))
        for label, broken, needle in (
                ("no files map", {k: v for k, v in good_receipt.items() if k != "files"},
                 "files must be a non-empty map"),
                ("a file record without a digest", dict(good_receipt, files={"hooks/x.py": {}}),
                 "must be an object with a 64-hex sha256"),
                ("no version", {k: v for k, v in good_receipt.items() if k != "version"},
                 "version must be a non-empty string"),
                ("a boolean schema version", dict(good_receipt, schema_version=True),
                 "schema_version True is not an integer in"),
                ("an owned entry whose timeout is a list", dict(good_receipt, owned_hooks=[
                    dict(good_receipt["owned_hooks"][0], timeout=[])]),
                 "owned_hooks[0] timeout must be an integer or null"),
                ("a repeated owned entry", dict(good_receipt, owned_hooks=good_receipt["owned_hooks"]
                                                 + good_receipt["owned_hooks"][:1]),
                 "owned_hooks[2] repeats"),
                ("an owned entry that is not a command", dict(good_receipt, owned_hooks=[
                    dict(good_receipt["owned_hooks"][0], type="prompt")]),
                 'type must be "command"')):
            json.dump(broken, open(legacy_path, "w"))
            chk(f"a receipt with {label} is refused at load, never acted on",
                raises(lambda: load_receipt(legacy_path), needle))
        thin = dict(good_receipt)
        del thin["files"]
        atomic_write(active_receipt_path(home), (json.dumps(thin, indent=2) + "\n").encode("utf-8"))
        buf = io.StringIO()
        chk("--check with an active receipt that lost its files map is red, not files=0 drift=0",
            check(home, source, out=buf) == 1 and "active receipt unreadable" in buf.getvalue()
            and "files must be a non-empty map" in buf.getvalue())
        activate(home, "v1")

        # --- the active receipt is the staged receipt plus activation fields: an edit to
        # either is an inconsistency, so a hook dropped from both the active receipt and
        # settings is still found through the staged receipt
        edited = load_json(active_receipt_path(home))
        dropped = edited["owned_hooks"].pop(0)
        atomic_write(active_receipt_path(home), (json.dumps(edited, indent=2) + "\n").encode("utf-8"))
        current = load_json(settings_path)
        current["hooks"][dropped["event"]] = [
            entry for entry in current["hooks"][dropped["event"]]
            if not any(h.get("command") == dropped["command"] for h in entry.get("hooks", []))]
        atomic_write(settings_path, (json.dumps(current, indent=2) + "\n").encode("utf-8"))
        buf = io.StringIO()
        chk("--check reconciles the active receipt against the staged receipt of its version",
            check(home, source, out=buf) == 1
            and "active receipt differs from the staged receipt of v1" in buf.getvalue())
        activate(home, "v1")
        buf = io.StringIO()
        chk("--activate restores the dropped entry and the receipt, and --check is clean",
            wired(home) == {"v1": 2, "v2": 0} and check(home, source, out=buf) == 0)
        activate(home, "v2")
        shutil.rmtree(tree_path(home, "v2"))
        buf = io.StringIO()
        chk("--check names an active receipt whose version is no longer staged",
            check(home, source, out=buf) == 1
            and "active receipt names version v2, which is not staged" in buf.getvalue())
        stage(source, home, version_id="v2")
        activate(home, "v1")

        # --- only a command of the installer's own shape points into a tree: a user command
        # that merely prints such a path is a user entry and survives --remove-orphans
        current = load_json(settings_path)
        mention = {"type": "command", "timeout": 5,
                   "command": "printf '%s\\n' '~/.claude/harness/old/hooks/example.py'"}
        current["hooks"]["Stop"].append({"hooks": [dict(mention)]})
        atomic_write(settings_path, (json.dumps(current, indent=2) + "\n").encode("utf-8"))
        state = installation_state(home, source)
        chk("a user command that only mentions a harness path is foreign, not an orphan",
            [h["kind"] for h in state["handlers"] if h["handler"] == mention] == ["foreign"]
            and harness_version_of(mention["command"]) is None
            and harness_version_of("python3 ~/.claude/harness/v9/hooks/stop_guard.py --x") == "v9")
        activate(home, "v1", remove_orphans=True)
        buf = io.StringIO()
        chk("--activate --remove-orphans keeps that user command and --check stays clean",
            any(h == mention for _e, _m, h in registered_handlers(load_json(settings_path)))
            and check(home, source, out=buf) == 0)
        current = load_json(settings_path)
        current["hooks"]["Stop"] = [e for e in current["hooks"]["Stop"]
                                    if not any(h == mention for h in e.get("hooks", []))]
        atomic_write(settings_path, (json.dumps(current, indent=2) + "\n").encode("utf-8"))

        # --- a pending marker is trusted only in its own shape
        for label, bad_marker in (("only a target", {"to": "v2"}),
                                  ("a foreign schema", {"schema_version": 999, "from": 1, "to": "v2",
                                                        "merged_sha256": "x", "started_at": 1}),
                                  ("an empty target", {"schema_version": 1, "from": "v1", "to": "",
                                                       "merged_sha256": "0" * 64,
                                                       "started_at": "2026-01-01T00:00:00Z"})):
            atomic_write(marker_path, json.dumps(bad_marker).encode("utf-8"))
            buf = io.StringIO()
            chk(f"--check names a pending marker with {label} as malformed, never as a transaction",
                check(home, source, out=buf) == 1 and "pending marker malformed" in buf.getvalue()
                and "activation of" not in buf.getvalue())
        activate(home, "v1")
        chk("--activate replaces a malformed marker and leaves none", not os.path.exists(marker_path))

        # --- the marker precedes the replace: a stop between them leaves the marker, the stage
        # 'before the switch', and settings untouched
        before_bytes = open(settings_path, "rb").read()
        chk("a stop after the marker and before the replace is reported as a failed activation",
            raises(lambda: activate(home, "v2", fault="after-marker"), "after the marker"))
        buf = io.StringIO()
        chk("after that stop the marker exists, --check names 'before the switch', and settings.json "
            "is byte-identical",
            os.path.isfile(marker_path) and check(home, source, out=buf) == 1
            and "activation of v2 interrupted before the switch" in buf.getvalue()
            and open(settings_path, "rb").read() == before_bytes)
        activate(home, "v1")

        # --- the default process acquisition reads both ps columns and pairs them by pid, and a
        # quiescent list under the strict flag activates
        from unittest.mock import patch

        class PsResult:
            def __init__(self, stdout):
                self.stdout = stdout

        def fake_ps(argv, **_kw):
            table = {"pid=,comm=": " 101 /x/claude.app/Contents/MacOS/claude\n 102 /usr/bin/python3\n",
                     "pid=,args=": " 101 /x/claude.app/Contents/MacOS/claude --output-format stream-json\n"
                                   " 102 python3 tools/x.py\n"}
            return PsResult(table[argv[2]])

        with patch.object(subprocess, "run", fake_ps):
            live = claude_processes()
        chk("claude_processes reads both ps columns by default and pairs them by pid",
            live == [(101, "/x/claude.app/Contents/MacOS/claude")])
        chk("a grep over a log that names the npm entry point is not a Claude Code process, a "
            "versioned CLI binary is",
            not is_claude_code_process("/usr/bin/grep", "grep @anthropic-ai/claude-code/ /tmp/log")
            and is_claude_code_process("/opt/claude/versions/2.1.301", "claude")
            and is_claude_code_process("/usr/local/bin/node",
                                       "node /usr/local/lib/node_modules/@anthropic-ai/claude-code/cli.js"))
        strict = real_activate(home, "v1", processes=lambda: [], require_quiescent=True)
        chk("--require-quiescent activates when the process list is empty",
            strict["version"] == "v1" and wired(home) == {"v1": 2, "v2": 0})

        # --- each validation branch alone: every fixture is otherwise valid, so the named
        # branch is the only one that can refuse it
        good_receipt = load_receipt(os.path.join(tree, RECEIPT_NAME))
        hook0 = good_receipt["owned_hooks"][0]
        script0 = HARNESS_COMMAND.match(hook0["command"]).group(2)
        for label, broken, needle in (
                ("an empty files map", dict(good_receipt, files={}), "files must be a non-empty map"),
                ("an absolute files key", dict(good_receipt, files=dict(good_receipt["files"], **{
                    "/etc/passwd": {"sha256": "0" * 64}})), "'/etc/passwd' is not a contained relative path"),
                ("a traversing files key", dict(good_receipt, files=dict(good_receipt["files"], **{
                    "hooks/../x.py": {"sha256": "0" * 64}})), "is not a contained relative path"),
                ("an owned script missing from files", dict(good_receipt, files={
                    k: v for k, v in good_receipt["files"].items() if k != f"hooks/{script0}"}),
                 f"script hooks/{script0} is not in files"),
                ("a float schema version", dict(good_receipt, schema_version=2.0),
                 "schema_version 2.0 is not an integer in"),
                ("an empty tree", dict(good_receipt, tree=""), "tree must be a non-empty string"),
                ("a tree that is not the version's display path", dict(good_receipt, tree="~/.claude/harness/v9"),
                 "is not the display path of version"),
                ("a non-hex digest", dict(good_receipt, files=dict(good_receipt["files"], **{
                    f"hooks/{script0}": {"sha256": "zz" * 32}})), "must be an object with a 64-hex sha256"),
                ("a boolean timeout", dict(good_receipt, owned_hooks=[dict(hook0, timeout=True)]
                                           + good_receipt["owned_hooks"][1:]), "timeout must be an integer or null"),
                ("a float timeout", dict(good_receipt, owned_hooks=[dict(hook0, timeout=1.5)]
                                         + good_receipt["owned_hooks"][1:]), "timeout must be an integer or null"),
                ("a numeric matcher", dict(good_receipt, owned_hooks=[dict(hook0, matcher=123)]
                                           + good_receipt["owned_hooks"][1:]), "matcher must be a string or null"),
                ("a command into another version", dict(good_receipt, owned_hooks=[
                    dict(hook0, command=hook0["command"].replace("/v1/", "/v2/"))] + good_receipt["owned_hooks"][1:]),
                 "points into version 'v2', not 'v1'"),
                ("a command that is not a harness hook command", dict(good_receipt, owned_hooks=[
                    dict(hook0, command="python3 ~/.claude/hooks/x.py")] + good_receipt["owned_hooks"][1:]),
                 "is not a harness hook command")):
            json.dump(broken, open(legacy_path, "w"))
            chk(f"a receipt with {label} is refused at load",
                raises(lambda: load_receipt(legacy_path), needle))
        good_marker = {"schema_version": 1, "from": "v1", "to": "v2", "merged_sha256": "0" * 64,
                       "started_at": "2026-01-01T00:00:00Z"}
        chk("marker control: the well-formed marker has no problems", marker_problems(good_marker) == [])
        for label, change, needle in (
                ("a float schema version", {"schema_version": 1.0}, "not the integer 1"),
                ("a numeric from", {"from": 1}, "from must be a version id or null"),
                ("a short digest", {"merged_sha256": "abc"}, "64 hex characters"),
                ("a non-timestamp started_at", {"started_at": "yesterday"}, "UTC timestamp"),
                ("a target that is not a version id", {"to": "../x"}, "to must be a version id")):
            problems = marker_problems(dict(good_marker, **change))
            chk(f"a marker with {label} is refused by that branch alone",
                len(problems) == 1 and needle in problems[0])
        chk("a null marker is not an object", marker_problems(None) == ["not an object"])
        atomic_write(marker_path, b"null\n")
        buf = io.StringIO()
        chk("--check names a marker file holding JSON null as malformed, never as absent",
            check(home, source, out=buf) == 1
            and "pending marker malformed (not an object)" in buf.getvalue())
        activate(home, "v1")
        edited = load_json(active_receipt_path(home))
        edited["files"] = dict(edited["files"], **{f"hooks/{script0}": {"sha256": "0" * 64}})
        atomic_write(active_receipt_path(home), (json.dumps(edited, indent=2) + "\n").encode("utf-8"))
        buf = io.StringIO()
        chk("--check reconciles the files map alone against the staged receipt",
            check(home, source, out=buf) == 1
            and "active receipt differs from the staged receipt of v1" in buf.getvalue())
        activate(home, "v1")

        # --- a directory left by an interrupted --stage is never a staged tree
        leftover = tree_path(home, "v2.staging-1")
        shutil.copytree(tree_path(home, "v2"), leftover)
        buf = io.StringIO()
        chk("--check names an interrupted staging directory and never lists it as a tree",
            check(home, source, out=buf) == 1
            and "staged tree v2.staging-1: not a staged tree: an interrupted staging directory" in buf.getvalue()
            and "v2.staging-1" not in installation_state(home)["trees"])
        chk("--activate refuses an interrupted staging directory by name",
            raises(lambda: activate(home, "v2.staging-1"), "is not a staged version id"))
        shutil.rmtree(leftover)
        renamed = tree_path(home, "v3")
        shutil.copytree(tree_path(home, "v2"), renamed)
        buf = io.StringIO()
        chk("--check names a tree directory whose receipt belongs to another version",
            check(home, source, out=buf) == 1
            and "receipt names version 'v2' but the directory is 'v3'" in buf.getvalue())
        chk("--activate refuses a directory whose receipt names another version",
            raises(lambda: activate(home, "v3"), "names version 'v2', not 'v3'"))
        shutil.rmtree(renamed)
        buf = io.StringIO()
        chk("--check is clean again", check(home, source, out=buf) == 0)

        # --- the command shape cannot reach outside the tree
        chk("a command whose script path traverses out of hooks/ is not a harness hook command",
            harness_version_of("python3 ~/.claude/harness/old/hooks/../../../../user.py") is None
            and harness_version_of("python3 ~/.claude/harness/v1/hooks/guards/x_guard.py --flag") == "v1"
            and OWNED_COMMAND.match("python3 ~/.claude/hooks/../x.py") is None
            and OWNED_COMMAND.match("python3 ~/.claude/hooks/guards/x_guard.py --flag") is not None)
        current = load_json(settings_path)
        traversal = {"type": "command", "timeout": 5,
                     "command": "python3 ~/.claude/harness/old/hooks/../../../../user.py"}
        current["hooks"]["Stop"].append({"hooks": [dict(traversal)]})
        atomic_write(settings_path, (json.dumps(current, indent=2) + "\n").encode("utf-8"))
        activate(home, "v1", remove_orphans=True)
        chk("a traversing user command is foreign and survives --remove-orphans",
            any(h == traversal for _e, _m, h in registered_handlers(load_json(settings_path))))
        current = load_json(settings_path)
        current["hooks"]["Stop"] = [e for e in current["hooks"]["Stop"]
                                    if not any(h == traversal for h in e.get("hooks", []))]
        atomic_write(settings_path, (json.dumps(current, indent=2) + "\n").encode("utf-8"))

        # --- the interpreter's script operand, not any argument, names the entry point
        chk("an interpreter counts only when its script operand is the entry point; a path with "
            "spaces is removed whole; flags before the script are skipped",
            not is_claude_code_process("/usr/local/bin/node",
                                       "node other.js /usr/lib/node_modules/@anthropic-ai/claude-code/cli.js")
            and is_claude_code_process("/opt/Node Runtime/bin/node",
                                       "/opt/Node Runtime/bin/node /usr/lib/node_modules/@anthropic-ai/claude-code/cli.js")
            and is_claude_code_process("/usr/local/bin/node",
                                       "node --inspect /usr/lib/node_modules/@anthropic-ai/claude-code/cli.js")
            and script_operand("/opt/Node Runtime/bin/node", "/opt/Node Runtime/bin/node a.js b.js") == "a.js")

        def fake_ps_node(argv, **_kw):
            table = {"pid=,comm=": " 101 /usr/local/bin/node\n 102 /usr/bin/python3\n",
                     "pid=,args=": " 101 node /usr/lib/node_modules/@anthropic-ai/claude-code/cli.js\n"
                                   " 102 python3 tools/x.py\n"}
            return PsResult(table[argv[2]])

        with patch.object(subprocess, "run", fake_ps_node):
            live = claude_processes()
        chk("the default acquisition reads the arguments column: an interpreter process is found "
            "only through it",
            live == [(101, "node /usr/lib/node_modules/@anthropic-ai/claude-code/cli.js")])
        chk("an interpreter option that takes an operand does not hide the script behind it",
            is_claude_code_process("/usr/local/bin/node",
                                   "node --require bootstrap.cjs /usr/lib/node_modules/@anthropic-ai/claude-code/cli.js")
            and is_claude_code_process("/usr/local/bin/node",
                                       "node -r ./boot.js --no-warnings /usr/lib/node_modules/@anthropic-ai/claude-code/cli.js")
            and not is_claude_code_process("/usr/local/bin/node",
                                           "node --require /usr/lib/node_modules/@anthropic-ai/claude-code/cli.js other.js")
            and script_operand("/usr/local/bin/node", "node --eval x") == "")

        # --- every containment and typing branch alone, with otherwise-valid fixtures
        for label, broken, needle in (
                ("a home-prefixed files key", dict(good_receipt, files=dict(good_receipt["files"], **{
                    "~/outside": {"sha256": "0" * 64}})), "'~/outside' is not a contained relative path"),
                ("a dot segment in a files key", dict(good_receipt, files=dict(good_receipt["files"], **{
                    "hooks/./x.py": {"sha256": "0" * 64}})), "'hooks/./x.py' is not a contained relative path"),
                ("an empty segment in a files key", dict(good_receipt, files=dict(good_receipt["files"], **{
                    "hooks//x.py": {"sha256": "0" * 64}})), "'hooks//x.py' is not a contained relative path"),
                ("a numeric event", dict(good_receipt, owned_hooks=[dict(hook0, event=321)]
                                         + good_receipt["owned_hooks"][1:]), "event must be a non-empty string"),
                ("a short digest", dict(good_receipt, files=dict(good_receipt["files"], **{
                    f"hooks/{script0}": {"sha256": "abc"}})), "must be an object with a 64-hex sha256")):
            json.dump(broken, open(legacy_path, "w"))
            chk(f"a receipt with {label} is refused by that branch alone",
                raises(lambda: load_receipt(legacy_path), needle))
        chk("a marker whose timestamp has the right shape but an impossible date is refused",
            [p for p in marker_problems(dict(good_marker, started_at="2026-19-45T29:78:99Z"))]
            == ["started_at must be a real UTC timestamp like 2026-01-01T00:00:00Z"])

        # --- one version-name contract: a name carrying the staging mark is refused before
        # staging writes anything, so it can never block activation afterwards
        chk("stage refuses a version id carrying the staging mark",
            raises(lambda: stage(source, home, version_id="v3.staging-release"), "reserved for staging")
            and not os.path.lexists(tree_path(home, "v3.staging-release")))

        # --- a hook whose sibling module is missing from the files map cannot load: the
        # receipt vouches for the imports of every owned script, transitively
        dep_source = os.path.join(td, "dep-source")
        shutil.copytree(source, dep_source)
        open(os.path.join(dep_source, "hooks", "helper_lib.py"), "w").write("VALUE = 1\n")
        open(os.path.join(dep_source, "hooks", "dep_guard.py"), "w").write(
            "import os, sys\nsys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))\n"
            "import helper_lib\nsys.exit(0)\n")
        dep_settings = json.load(open(os.path.join(dep_source, "settings.json")))
        dep_settings["hooks"]["Stop"][0]["hooks"].append({
            "type": "command", "command": "python3 ~/.claude/hooks/dep_guard.py", "timeout": 5})
        json.dump(dep_settings, open(os.path.join(dep_source, "settings.json"), "w"), indent=2)
        dep_home = os.path.join(td, "dep-home")
        os.makedirs(os.path.join(dep_home, ".claude"))
        json.dump(user_settings, open(os.path.join(dep_home, ".claude", "settings.json"), "w"))
        dep_receipt = stage(dep_source, dep_home, version_id="v1")
        chk("hook_import_problems is empty for a tree whose imports the receipt covers",
            hook_import_problems(tree_path(dep_home, "v1"), dep_receipt) == [])
        activate(dep_home, "v1")
        buf = io.StringIO()
        chk("--check is clean on the dependent tree", check(dep_home, dep_source, out=buf) == 0)
        dep_tree = tree_path(dep_home, "v1")
        os.remove(os.path.join(dep_tree, "hooks", "helper_lib.py"))
        for receipt_path in (os.path.join(dep_tree, RECEIPT_NAME), active_receipt_path(dep_home)):
            thinned = load_json(receipt_path)
            del thinned["files"]["hooks/helper_lib.py"]
            atomic_write(receipt_path, (json.dumps(thinned, indent=2, sort_keys=True) + "\n").encode("utf-8"))
        buf = io.StringIO()
        chk("--check names a hook whose sibling module is neither standard library nor in the files map",
            check(dep_home, dep_source, out=buf) == 1
            and "owned hook hooks/dep_guard.py imports helper_lib, which is neither standard library nor "
                "in the receipt's files under hooks" in buf.getvalue())
        chk("--activate refuses a tree whose hooks cannot load",
            raises(lambda: activate(dep_home, "v1"), "hooks cannot load: hooks/dep_guard.py imports helper_lib"))

        # --- the module must sit in a directory the hook actually searches: its own
        # directory always, hooks/guards/ and tools/ only when its source inserts them
        def import_check(tree_files, scripts_by_path, fn=None, owned=None):
            """-> hook_import_problems over a throwaway tree: files map plus the named scripts;
            every script directly under hooks/ is an owned hook unless `owned` names them."""
            root = os.path.join(td, "import-tree")
            shutil.rmtree(root, ignore_errors=True)
            for rel, body in scripts_by_path.items():
                os.makedirs(os.path.dirname(os.path.join(root, rel)), exist_ok=True)
                open(os.path.join(root, rel), "w").write(body)
            if owned is None:
                owned = [rel[len("hooks/"):] for rel in scripts_by_path
                         if rel.startswith("hooks/") and "/" not in rel[len("hooks/"):]]
            receipt = {"files": {rel: {"sha256": "0" * 64} for rel in tree_files},
                       "owned_hooks": [{"event": "Stop", "matcher": None, "type": "command",
                                        "command": f"python3 ~/.claude/harness/v1/hooks/{name}",
                                        "timeout": 5} for name in owned]}
            return (fn or hook_import_problems)(root, receipt)

        inserts_guards = "import os, sys\nsys.path.insert(0, os.path.join(os.path.dirname(__file__), \"guards\"))\n"
        inserts_tools = "import os, sys\nsys.path.insert(0, os.path.join(os.path.dirname(__file__), \"..\", \"tools\"))\n"
        chk("a sibling under hooks/guards/ is accepted only when the hook inserts \"guards\" on sys.path",
            import_check(["hooks/a.py", "hooks/guards/lib.py"], {"hooks/a.py": inserts_guards + "import lib\n",
                                                                 "hooks/guards/lib.py": "X = 1\n"}) == []
            and import_check(["hooks/a.py", "hooks/guards/lib.py"], {"hooks/a.py": "import os, sys\nimport lib\n",
                                                                     "hooks/guards/lib.py": "X = 1\n"})
            == ["hooks/a.py imports lib, which is neither standard library nor in the receipt's files under hooks"])
        chk("a module under tools/ is accepted only when the hook inserts \"tools\" on sys.path",
            import_check(["hooks/a.py", "tools/lib.py"], {"hooks/a.py": inserts_tools + "import lib\n",
                                                          "tools/lib.py": "X = 1\n"}) == []
            and import_check(["hooks/a.py", "tools/lib.py"], {"hooks/a.py": inserts_guards + "import lib\n",
                                                              "tools/lib.py": "X = 1\n"})
            == ["hooks/a.py imports lib, which is neither standard library nor in the receipt's files under "
                "hooks/guards, hooks"])
        transitive_root = os.path.join(td, "transitive-tree")
        shutil.rmtree(transitive_root, ignore_errors=True)
        os.makedirs(os.path.join(transitive_root, "hooks"))
        open(os.path.join(transitive_root, "hooks", "a.py"), "w").write("import lib\n")
        open(os.path.join(transitive_root, "hooks", "lib.py"), "w").write("import deeper\n")
        only_a = {"files": {"hooks/a.py": {"sha256": "0" * 64}, "hooks/lib.py": {"sha256": "0" * 64}},
                  "owned_hooks": [{"event": "Stop", "matcher": None, "type": "command",
                                   "command": "python3 ~/.claude/harness/v1/hooks/a.py", "timeout": 5}]}
        chk("imports are followed transitively: only a.py is owned, and lib.py's missing import is named",
            hook_import_problems(transitive_root, only_a)
            == ["hooks/lib.py imports deeper, which is neither standard library nor in the receipt's files under hooks"])
        chk("an insert is resolved onto the script's directory: \"tools\" under hooks/ is not the tree's tools/",
            import_check(["hooks/a.py", "tools/lib.py"], {"hooks/a.py": 'import os, sys\nsys.path.insert(0, os.path.join(os.path.dirname(__file__), "tools"))\nimport lib\n',
                                                          "tools/lib.py": "X = 1\n"})
            == ["hooks/a.py imports lib, which is neither standard library nor in the receipt's files under hooks/tools, hooks"]
            and import_check(["hooks/a.py", "hooks/tools/lib.py"], {"hooks/a.py": 'import os, sys\nsys.path.insert(0, os.path.join(os.path.dirname(__file__), "tools"))\nimport lib\n',
                                                                    "hooks/tools/lib.py": "X = 1\n"}) == [])
        chk("an insert that lands outside the tree is reported",
            import_check(["hooks/a.py"], {"hooks/a.py": 'import os, sys\nsys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "elsewhere"))\n'})
            == ["hooks/a.py inserts a sys.path entry outside the tree (../elsewhere)"])
        chk("only a sys.path.insert or sys.path.append of the right arity authorises a directory: other "
            "receivers and attributes do not, and a two-argument append is reported",
            all(import_check(["hooks/a.py", "tools/lib.py"], {"hooks/a.py": f'import os, sys\n{call}(0, os.path.join(os.path.dirname(__file__), "..", "tools"))\nimport lib\n',
                                                              "tools/lib.py": "X = 1\n"})
                == ["hooks/a.py imports lib, which is neither standard library nor in the receipt's files under hooks"]
                for call in ("other.path.insert", "sys.other.insert"))
            and import_check(["hooks/a.py", "tools/lib.py"], {"hooks/a.py": 'import os, sys\nsys.path.append(0, os.path.join(os.path.dirname(__file__), "..", "tools"))\nimport lib\n',
                                                              "tools/lib.py": "X = 1\n"})
            == ["hooks/a.py line 2: unsupported sys.path mutation sys.path.append(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))",
                "hooks/a.py imports lib, which is neither standard library nor in the receipt's files under hooks"]
            and import_check(["hooks/a.py", "tools/lib.py", "hooks/guards/g.py"], {
                "hooks/a.py": 'import os, sys\nDIRECTORY = "tools"\nsys.path.insert(0, os.path.join(os.path.dirname(__file__), "guards"))\nimport lib\n',
                "tools/lib.py": "X = 1\n", "hooks/guards/g.py": "X = 1\n"})
            == ["hooks/a.py imports lib, which is neither standard library nor in the receipt's files under hooks/guards, hooks"])
        chk("an insert with the wrong arity, or whose directory string sits in the index argument, is reported "
            "as unsupported and authorises nothing",
            import_check(["hooks/a.py", "tools/lib.py"], {"hooks/a.py": 'import os, sys\nsys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"), 99)\nimport lib\n',
                                                          "tools/lib.py": "X = 1\n"})
            == ["hooks/a.py line 2: unsupported sys.path mutation sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'), 99)",
                "hooks/a.py imports lib, which is neither standard library nor in the receipt's files under hooks"]
            and import_check(["hooks/a.py", "tools/lib.py"], {"hooks/a.py": 'import os, sys\nsys.path.insert("../tools", os.path.dirname(__file__))\nimport lib\n',
                                                              "tools/lib.py": "X = 1\n"})
            == ["hooks/a.py line 2: unsupported sys.path mutation sys.path.insert('../tools', os.path.dirname(__file__))",
                "hooks/a.py imports lib, which is neither standard library nor in the receipt's files under hooks"])
        chk("a commented-out sys.path.insert, or a string naming the directory, authorises nothing",
            import_check(["hooks/a.py", "tools/lib.py"], {"hooks/a.py": 'import os, sys\n# sys.path.insert(0, "tools")\nimport lib\n',
                                                          "tools/lib.py": "X = 1\n"})
            == ["hooks/a.py imports lib, which is neither standard library nor in the receipt's files under hooks"]
            and import_check(["hooks/a.py", "tools/lib.py"], {"hooks/a.py": 'import os, sys\nDIRECTORY = "tools"\nimport lib\n',
                                                              "tools/lib.py": "X = 1\n"})
            == ["hooks/a.py imports lib, which is neither standard library nor in the receipt's files under hooks"]
            and import_check(["hooks/a.py", "tools/lib.py"], {"hooks/a.py": 'import os, sys\nsys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))\nimport lib\n',
                                                              "tools/lib.py": "X = 1\n"}) == [])
        chk("a `from x import y` and every alias of one `import a, b` are inspected",
            import_check(["hooks/a.py", "hooks/one.py"], {"hooks/a.py": "from two import X\n",
                                                          "hooks/one.py": "X = 1\n"})
            == ["hooks/a.py imports two, which is neither standard library nor in the receipt's files under hooks"]
            and import_check(["hooks/a.py", "hooks/one.py"], {"hooks/a.py": "import one, three\n",
                                                              "hooks/one.py": "X = 1\n"})
            == ["hooks/a.py imports three, which is neither standard library nor in the receipt's files under hooks"])
        chk("a hook that cannot be parsed is reported, never skipped",
            any(p.startswith("hooks/a.py cannot be parsed")
                for p in import_check(["hooks/a.py"], {"hooks/a.py": "def (:\n"})))

        # --- the resolver follows the interpreter (review thread 4298561313): search order,
        # the inherited path, shadowing of the standard library, unordered mutations
        def differential(scripts_by_path):
            """-> (checker clear, child exit 0) for one tree whose entry is hooks/a.py, the child
            run by a fresh interpreter with an empty PYTHONPATH."""
            root = os.path.join(td, "differential-tree")
            shutil.rmtree(root, ignore_errors=True)
            for rel, body in scripts_by_path.items():
                os.makedirs(os.path.dirname(os.path.join(root, rel)), exist_ok=True)
                open(os.path.join(root, rel), "w").write(body)
            receipt = {"files": {rel: {"sha256": "0" * 64} for rel in scripts_by_path},
                       "owned_hooks": [{"event": "Stop", "matcher": None, "type": "command",
                                        "command": "python3 ~/.claude/harness/v1/hooks/a.py", "timeout": 5}]}
            child = subprocess.run([sys.executable, os.path.join(root, "hooks", "a.py")], cwd=td,
                                   capture_output=True, text=True, timeout=60,
                                   env=dict(os.environ, PYTHONPATH="", PYTHONDONTWRITEBYTECODE="1"))
            return hook_import_problems(root, receipt) == [], child.returncode == 0

        prefix = 'import sys\nfrom pathlib import Path\nsys.path.insert(0, str(Path(__file__).parent / "guards"))\n'
        BOOT_INSERTS_G = 'import sys\nfrom pathlib import Path\nsys.path.insert(0, str(Path(__file__).parent / "g"))\n'
        shapes = {
            "control": ({"hooks/a.py": prefix + "import lib\nprint(lib.VALUE)\n",
                         "hooks/guards/lib.py": "VALUE = 42\n"}, (True, True)),
            "precedence": ({"hooks/a.py": prefix + "import lib\n", "hooks/lib.py": "VALUE = 42\n",
                            "hooks/guards/lib.py": "import missing_review_dependency\n"}, (False, False)),
            "inherited_path": ({"hooks/a.py": prefix + "import lib\n",
                                "hooks/guards/lib.py": "import helper_lib\nVALUE = helper_lib.VALUE\n",
                                "hooks/helper_lib.py": "VALUE = 42\n"}, (True, True)),
            "stdlib_shadow": ({"hooks/a.py": "import json\n",
                               "hooks/json.py": "import missing_review_dependency\n"}, (False, False)),
            "unexecuted_insert": ({"hooks/a.py": 'import sys\nfrom pathlib import Path\nif False:\n'
                                                 '    sys.path.insert(0, str(Path(__file__).parent / "guards"))\n'
                                                 'import lib\n',
                                   "hooks/guards/lib.py": "VALUE = 42\n"}, (False, False)),
            "insert_after_own_dir": ({"hooks/a.py": prefix.replace("insert(0,", "insert(1,") + "import lib\n",
                                      "hooks/lib.py": "VALUE = 42\n",
                                      "hooks/guards/lib.py": "import missing_review_dependency\n"}, (True, True)),
            "append": ({"hooks/a.py": 'import sys\nfrom pathlib import Path\n'
                                      'sys.path.append(str(Path(__file__).parent / "guards"))\nimport lib\n',
                        "hooks/guards/lib.py": "VALUE = 42\n"}, (True, True)),
            "parent_parent": ({"hooks/a.py": 'import sys\nfrom pathlib import Path\n'
                                             'sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))\nimport lib\n',
                               "tools/lib.py": "VALUE = 42\n"}, (True, True)),
            "dirname_abspath": ({"hooks/a.py": 'import os, sys\nsys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))\n'
                                               'import lib\n', "hooks/lib.py": "VALUE = 42\n"}, (True, True)),
            "package": ({"hooks/a.py": "import pkg\nprint(pkg.VALUE)\n",
                         "hooks/pkg/__init__.py": "import sub\nVALUE = sub.VALUE\n",
                         "hooks/sub.py": "VALUE = 42\n"}, (True, True)),
            "unanchored_entry": ({"hooks/a.py": 'import sys\nsys.path.insert(0, "/nonexistent/guards")\nimport lib\n',
                                  "hooks/guards/lib.py": "VALUE = 42\n"}, (False, False)),
            "dotted_submodule": ({"hooks/a.py": "import pkg.sub\nprint(pkg.sub.VALUE)\n", "hooks/pkg/__init__.py": "",
                                  "hooks/pkg/sub.py": "VALUE = 42\n"}, (True, True)),
            "dotted_missing": ({"hooks/a.py": "import pkg.nope\n", "hooks/pkg/__init__.py": ""}, (False, False)),
            "from_package_submodule": ({"hooks/a.py": "from pkg import sub\nprint(sub.VALUE)\n", "hooks/pkg/__init__.py": "",
                                        "hooks/pkg/sub.py": "import missing_review_dependency\nVALUE = 42\n"}, (False, False)),
            "dynamic_constant": ({"hooks/a.py": 'import importlib\nlib = importlib.import_module("lib")\nprint(lib.VALUE)\n',
                                  "hooks/lib.py": "VALUE = 42\n"}, (True, True)),
            "dynamic_missing": ({"hooks/a.py": 'import importlib\nlib = importlib.import_module("nope")\n'}, (False, False)),
            "package_over_module": ({"hooks/a.py": "import lib\nprint(lib.VALUE)\n", "hooks/lib.py": "import missing_review_dependency\n",
                                     "hooks/lib/__init__.py": "VALUE = 42\n"}, (True, True)),
            "append_after_own_dir": ({"hooks/a.py": 'import sys\nfrom pathlib import Path\n'
                                                    'sys.path.append(str(Path(__file__).parent / "guards"))\nimport lib\n',
                                      "hooks/lib.py": "VALUE = 42\n",
                                      "hooks/guards/lib.py": "import missing_review_dependency\n"}, (True, True)),
            "insert_index_2_refused": ({"hooks/a.py": prefix.replace("insert(0,", "insert(2,") + "import lib\n",
                                        "hooks/guards/lib.py": "VALUE = 42\n"}, (False, True)),
            "relative_in_package": ({"hooks/a.py": "import pkg.sub\nprint(pkg.sub.VALUE)\n", "hooks/pkg/__init__.py": "",
                                     "hooks/pkg/sub.py": "from . import helper\nVALUE = helper.VALUE\n",
                                     "hooks/pkg/helper.py": "VALUE = 42\n"}, (True, True)),
            "relative_outside_package": ({"hooks/a.py": "from . import helper\n", "hooks/helper.py": "VALUE = 42\n"}, (False, False)),
            "relative_missing": ({"hooks/a.py": "import pkg.sub\n", "hooks/pkg/__init__.py": "",
                                  "hooks/pkg/sub.py": "from . import nope\n"}, (False, False)),
            "from_attribute_masks_module": ({"hooks/a.py": "from pkg import mod\nprint(mod)\n", "hooks/pkg/__init__.py": "mod = 42\n",
                                             "hooks/pkg/mod.py": "import missing_review_dependency\n"}, (True, True)),
            "main_guard_before_insert": ({"hooks/a.py": 'import sys\nfrom pathlib import Path\nif __name__ == "__main__":\n'
                                                        '    import lib\nsys.path.insert(0, str(Path(__file__).parent / "guards"))\n',
                                          "hooks/guards/lib.py": "VALUE = 42\n"}, (False, False)),
            "function_called_before_insert": ({"hooks/a.py": 'import sys\nfrom pathlib import Path\ndef f():\n    import lib\nf()\n'
                                                             'sys.path.insert(0, str(Path(__file__).parent / "guards"))\n',
                                               "hooks/guards/lib.py": "VALUE = 42\n"}, (False, False)),
            "function_defined_before_insert_called_after": ({"hooks/a.py": 'import sys\nfrom pathlib import Path\ndef f():\n'
                                                                           '    import lib\nsys.path.insert(0, str(Path(__file__).parent / "guards"))\nf()\n',
                                                             "hooks/guards/lib.py": "VALUE = 42\n"}, (False, True)),
            "dynamic_keyword": ({"hooks/a.py": 'import importlib\nlib = importlib.import_module(name="lib")\nprint(lib.VALUE)\n',
                                 "hooks/lib.py": "VALUE = 42\n"}, (True, True)),
            "dunder_plain": ({"hooks/a.py": 'lib = __import__("lib")\nprint(lib.VALUE)\n', "hooks/lib.py": "VALUE = 42\n"}, (True, True)),
            "dunder_fromlist": ({"hooks/a.py": 'pkg = __import__("pkg", fromlist=["mod"])\n', "hooks/pkg/__init__.py": "",
                                 "hooks/pkg/mod.py": "import missing_review_dependency\n"}, (False, False)),
            "stdlib_transitive_shadow": ({"hooks/a.py": "import statistics\n",
                                          "hooks/fractions.py": "import missing_review_dependency\n"}, (False, False)),
            "resolved_parent": ({"hooks/a.py": 'import sys\nfrom pathlib import Path\n'
                                               'sys.path.insert(0, str((Path(__file__).parent / "g" / "..").resolve().parent / "tools"))\n'
                                               'import lib\nprint(lib.VALUE)\n', "tools/lib.py": "VALUE = 42\n"}, (True, True)),
            "path_change_persists": ({"hooks/a.py": "import lib\nimport second\nprint(second.VALUE)\n",
                                      "hooks/lib.py": 'import sys\nfrom pathlib import Path\nsys.path.insert(0, str(Path(__file__).parent / "guards"))\n',
                                      "hooks/guards/second.py": "VALUE = 42\n"}, (True, True)),
            "package_self_import_missing": ({"hooks/a.py": "import pkg\n", "hooks/pkg/__init__.py": "from . import absent\n"}, (False, False)),
            "package_self_import_broken": ({"hooks/a.py": "import pkg\n", "hooks/pkg/__init__.py": "from . import mod\n",
                                            "hooks/pkg/mod.py": "import missing_review_dependency\n"}, (False, False)),
            "default_arg_dynamic": ({"hooks/a.py": 'import importlib\ndef f(x=importlib.import_module("nope")):\n    pass\n'}, (False, False)),
            "with_dynamic": ({"hooks/a.py": 'import importlib\nwith importlib.import_module("nope"):\n    pass\n'}, (False, False)),
            "uncalled_function_inserts": ({"hooks/a.py": "def f():\n    import inserter\nimport second\n",
                                           "hooks/inserter.py": 'import sys\nfrom pathlib import Path\nsys.path.insert(0, str(Path(__file__).parent / "guards"))\n',
                                           "hooks/guards/second.py": "VALUE = 42\n"}, (False, False)),
            "unreachable_import_caches": ({"hooks/a.py": 'import sys\nfrom pathlib import Path\nif False:\n    import lib\n'
                                                         'sys.path.insert(0, str(Path(__file__).parent / "guards"))\nimport lib\n',
                                           "hooks/lib.py": "VALUE = 1\n", "hooks/guards/lib.py": "import missing_review_dependency\n"}, (False, False)),
            "entry_relative_with_init": ({"hooks/a.py": "from . import helper\n", "hooks/__init__.py": "", "hooks/helper.py": "X = 1\n"}, (False, False)),
            "absolute_keeps_dotdot": ({"hooks/a.py": 'import sys\nfrom pathlib import Path\n'
                                                     'sys.path.insert(0, str((Path(__file__).parent / "g" / "..").absolute().parent / "tools"))\n'
                                                     'import lib\nprint(lib.VALUE)\n', "hooks/g/tools/lib.py": "VALUE = 42\n"}, (True, True)),
            "relative_dotted_through_module": ({"hooks/a.py": "import pkg.sub\n", "hooks/pkg/__init__.py": "",
                                                "hooks/pkg/sub.py": "from .mod.child import X\n", "hooks/pkg/mod.py": "X = 1\n",
                                                "hooks/pkg/child.py": "X = 1\n"}, (False, False)),
            "dynamic_relative_beyond_top": ({"hooks/a.py": 'import importlib\nsub = importlib.import_module("..sub", "pkg")\n',
                                             "hooks/pkg/__init__.py": "", "hooks/sub.py": "X = 1\n"}, (False, False)),
            "speculative_walk_then_real": ({"hooks/a.py": "if False:\n    import m\nimport m\nimport dep\nprint(dep.VALUE)\n",
                                            "hooks/m.py": 'import sys\nfrom pathlib import Path\nsys.path.insert(0, str(Path(__file__).parent / "extra"))\n',
                                            "hooks/extra/dep.py": "VALUE = 42\n"}, (True, True)),
            "same_file_two_contexts": ({"hooks/a.py": 'import sys\nfrom pathlib import Path\nimport pkg.sub\n'
                                                      'sys.path.insert(0, str(Path(__file__).parent / "pkg"))\nimport sub\n',
                                        "hooks/pkg/__init__.py": "", "hooks/pkg/sub.py": "from . import helper\n",
                                        "hooks/pkg/helper.py": "X = 1\n"}, (False, False)),
            "class_base_dynamic": ({"hooks/a.py": 'import importlib\nclass C(importlib.import_module("nope").Base):\n    pass\n'}, (False, False)),
            "except_type_dynamic": ({"hooks/a.py": 'import importlib\ntry:\n    raise ValueError\nexcept importlib.import_module("nope").E:\n    pass\n'}, (False, False)),
            "match_guard_dynamic": ({"hooks/a.py": 'import importlib\nx = 1\nmatch x:\n    case 1 if importlib.import_module("nope"):\n        pass\n'}, (False, False)),
            "loop_condition_dynamic": ({"hooks/a.py": 'import importlib\nwhile importlib.import_module("nope"):\n    break\n'}, (False, False)),
            "class_body_import": ({"hooks/a.py": "class C:\n    import nope\n"}, (False, False)),
            "if_header_dynamic": ({"hooks/a.py": 'import importlib\nif importlib.import_module("nope"):\n    pass\n'}, (False, False)),
            "for_header_dynamic": ({"hooks/a.py": 'import importlib\nfor x in importlib.import_module("nope").items:\n    pass\n'}, (False, False)),
            "else_after_false_boot": ({"hooks/a.py": "if False:\n    import boot\nelse:\n    import lib\n", "hooks/boot.py": "BOOT",
                                       "hooks/g/lib.py": "VALUE = 42\n"}, (False, False)),
            "decorator_before_body": ({"hooks/a.py": 'import importlib\n@importlib.import_module("lib").deco\ndef f():\n    import boot\n',
                                       "hooks/boot.py": "BOOT", "hooks/g/lib.py": "deco = lambda f: f\n"}, (False, False)),
            "self_import_alias": ({"hooks/a.py": "import pkg\n", "hooks/pkg/__init__.py": "from . import sub as sub\n",
                                   "hooks/pkg/sub.py": "import missing_review_dependency\n"}, (False, False)),
            "subscript_target_is_a_read": ({"hooks/a.py": "from pkg import len\n", "hooks/pkg/__init__.py": "bag = [0]\nbag[len([])] = 1\n",
                                            "hooks/pkg/len.py": "import missing_review_dependency\n"}, (False, False)),
            "del_subscript_keeps_binding": ({"hooks/a.py": "from pkg import len\n", "hooks/pkg/__init__.py": "len = 5\nbag = {5: 1}\ndel bag[len]\n",
                                             "hooks/pkg/len.py": "import missing_review_dependency\n"}, (True, True)),
            "annotation_only": ({"hooks/a.py": "from pkg import sub\n", "hooks/pkg/__init__.py": "sub: int\n",
                                 "hooks/pkg/sub.py": "import missing_review_dependency\n"}, (False, False)),
            "star_import_binds_nothing": ({"hooks/a.py": "from pkg import sub\n", "hooks/pkg/__init__.py": "from .other import *\n",
                                           "hooks/pkg/other.py": "__all__ = []\n", "hooks/pkg/sub.py": "import missing_review_dependency\n"}, (False, False)),
            "relative_beyond_logical_package": ({"hooks/a.py": "import pkg\n", "hooks/__init__.py": "", "hooks/helper.py": "X = 1\n",
                                                 "hooks/pkg/__init__.py": "from .. import helper\n"}, (False, False)),
            "from_package_relative": ({"hooks/a.py": "from pkg import sub\nprint(sub.VALUE)\n", "hooks/pkg/__init__.py": "",
                                       "hooks/pkg/sub.py": "from . import helper\nVALUE = helper.VALUE\n", "hooks/pkg/helper.py": "VALUE = 42\n"}, (True, True)),
            "dunder_unknown_keyword": ({"hooks/a.py": '__import__("os", nope=True)\n'}, (False, False)),
            "lambda_boot": ({"hooks/a.py": 'f = lambda: __import__("boot")\nimport lib\n', "hooks/boot.py": "BOOT",
                             "hooks/g/lib.py": "VALUE = 42\n"}, (False, False)),
            "shortcircuit_boot": ({"hooks/a.py": 'x = False and __import__("boot")\nimport lib\n', "hooks/boot.py": "BOOT",
                                   "hooks/g/lib.py": "VALUE = 42\n"}, (False, False)),
            "ternary_boot": ({"hooks/a.py": 'x = None if True else __import__("boot")\nimport lib\n', "hooks/boot.py": "BOOT",
                              "hooks/g/lib.py": "VALUE = 42\n"}, (False, False)),
            "empty_comprehension_boot": ({"hooks/a.py": 'x = [__import__("boot") for _ in []]\nimport lib\n', "hooks/boot.py": "BOOT",
                                          "hooks/g/lib.py": "VALUE = 42\n"}, (False, False)),
            "immediate_dynamic_boot": ({"hooks/a.py": 'boot = __import__("boot")\nimport lib\nprint(lib.VALUE)\n', "hooks/boot.py": "BOOT",
                                        "hooks/g/lib.py": "VALUE = 42\n"}, (True, True)),
            "argument_before_call": ({"hooks/a.py": '__import__("boot", __import__("lib").__dict__)\n', "hooks/boot.py": "BOOT",
                                      "hooks/g/lib.py": "VALUE = 42\n"}, (False, False)),
            "argument_before_call_valid": ({"hooks/a.py": '__import__("lib", __import__("boot").__dict__)\n', "hooks/boot.py": "BOOT",
                                            "hooks/g/lib.py": "VALUE = 42\n"}, (True, True)),
            "cross_alias_cycle": ({"hooks/a.py": "from pkg import sub\n", "hooks/pkg/__init__.py": "from . import sub as other\nfrom . import other as sub\n"},
                                  (False, False)),
            "unpacked_keywords": ({"hooks/a.py": '__import__("os", **{"nope": True})\n'}, (False, False)),
            "duplicate_name": ({"hooks/a.py": '__import__("os", name="sys")\n'}, (False, False)),
            "with_header_before_body": ({"hooks/a.py": 'import importlib\nwith importlib.import_module("lib"):\n    import boot\n',
                                         "hooks/boot.py": "BOOT", "hooks/g/lib.py": "__enter__ = lambda: None\n"}, (False, False)),
            "nested_package_relative": ({"hooks/a.py": "import pkg.a.b\n", "hooks/pkg/__init__.py": "", "hooks/pkg/a/__init__.py": "",
                                         "hooks/pkg/a/b.py": "from .. import helper\nfrom ... import helper as h2\n",
                                         "hooks/pkg/helper.py": "X = 1\n"}, (False, False)),
            "nested_package_relative_ok": ({"hooks/a.py": "import pkg.a.b\n", "hooks/pkg/__init__.py": "", "hooks/pkg/a/__init__.py": "",
                                            "hooks/pkg/a/b.py": "from .. import helper\nfrom . import sibling\n",
                                            "hooks/pkg/helper.py": "X = 1\n", "hooks/pkg/a/sibling.py": "X = 1\n"}, (True, True)),
            "relative_reached_module_relative": ({"hooks/a.py": "import pkg\n", "hooks/pkg/__init__.py": "from .a import X\n",
                                                  "hooks/pkg/a.py": "from . import helper\nX = helper.X\n", "hooks/pkg/helper.py": "X = 1\n"}, (True, True)),
            "unpacking_targets_bind": ({"hooks/a.py": "from pkg import b, rest\n", "hooks/pkg/__init__.py": "(a, b) = 1, 2\n*rest, = [3]\n"}, (True, True)),
            "positional_overflow": ({"hooks/a.py": '__import__("os", {}, {}, [], 0, 7)\n'}, (False, False)),
            "later_operand_checked": ({"hooks/a.py": 'x = True and __import__("nope")\n'}, (False, False)),
            "else_branch_checked": ({"hooks/a.py": 'x = 1 if False else __import__("nope")\n'}, (False, False)),
            "test_effect_kept": ({"hooks/a.py": 'x = 1 if __import__("boot") else 2\nimport lib\nprint(lib.VALUE)\n', "hooks/boot.py": "BOOT",
                                  "hooks/g/lib.py": "VALUE = 42\n"}, (True, True)),
            "first_iterable_effect_kept": ({"hooks/a.py": 'x = [i for i in __import__("boot").__dict__]\nimport lib\nprint(lib.VALUE)\n',
                                            "hooks/boot.py": "BOOT", "hooks/g/lib.py": "VALUE = 42\n"}, (True, True)),
            "first_operand_effect_kept": ({"hooks/a.py": 'x = __import__("boot") and 1\nimport lib\nprint(lib.VALUE)\n', "hooks/boot.py": "BOOT",
                                           "hooks/g/lib.py": "VALUE = 42\n"}, (True, True)),
            "lambda_default_effect_kept": ({"hooks/a.py": 'f = lambda x=__import__("boot"): x\nimport lib\nprint(lib.VALUE)\n', "hooks/boot.py": "BOOT",
                                            "hooks/g/lib.py": "VALUE = 42\n"}, (True, True)),
            "lambda_body_checked": ({"hooks/a.py": 'f = lambda: __import__("nope")\nf()\n'}, (False, False)),
            "if_body_checked": ({"hooks/a.py": 'x = __import__("nope") if True else 1\n'}, (False, False)),
            "comp_target_checked": ({"hooks/a.py": 'box = {}\n[0 for box[__import__("nope")] in [1]]\n'}, (False, False)),
            "comp_filter_before_elt": ({"hooks/a.py": '[__import__("boot") for _ in [1] if __import__("lib")]\n', "hooks/boot.py": "BOOT",
                                        "hooks/g/lib.py": "VALUE = 42\n"}, (False, False)),
            "comp_filter_checked": ({"hooks/a.py": '[1 for _ in [1] if __import__("nope")]\n'}, (False, False)),
            "comp_later_generator_checked": ({"hooks/a.py": '[1 for _ in [1] for __ in __import__("nope").items]\n'}, (False, False)),
            "comp_dict_key_checked": ({"hooks/a.py": '{__import__("nope"): 1 for _ in [1]}\n'}, (False, False)),
            "comp_dict_value_checked": ({"hooks/a.py": '{1: __import__("nope") for _ in [1]}\n'}, (False, False)),
            "comp_elt_after_boot_iterable": ({"hooks/a.py": '[__import__("lib") for _ in __import__("boot").__dict__]\n', "hooks/boot.py": "BOOT",
                                              "hooks/g/lib.py": "VALUE = 42\n"}, (True, True)),
            "starred_positional": ({"hooks/a.py": '__import__(*["os"])\n'}, (False, True)),
            "cached_source_binding": ({"hooks/a.py": 'import sys\nfrom pathlib import Path\nimport dep\n'
                                                     'sys.path.insert(0, str(Path(__file__).parent / "shadow"))\nfrom pkg import x\n',
                                       "hooks/dep.py": "x = 1\n", "hooks/shadow/dep.py": "y = 1\n", "hooks/pkg/__init__.py": "from dep import x\n"}, (True, True)),
            "decorator_effect_before_body": ({"hooks/a.py": '@__import__("boot").deco\ndef f():\n    import lib\n', "hooks/boot.py": "BOOT\ndeco = lambda f: f\n",
                                              "hooks/g/lib.py": "VALUE = 42\n"}, (True, True)),
            "subpackage_init_relative": ({"hooks/a.py": "import pkg.a\n", "hooks/pkg/__init__.py": "", "hooks/pkg/helper.py": "X = 1\n",
                                          "hooks/pkg/a/__init__.py": "from .. import helper\n"}, (True, True)),
            "from_import_subpackage_relative": ({"hooks/a.py": "import pkg\n", "hooks/pkg/__init__.py": "from . import sub\nfrom . import mod\n",
                                                 "hooks/pkg/helper.py": "X = 1\n", "hooks/pkg/sub/__init__.py": "from .. import helper\n",
                                                 "hooks/pkg/mod.py": "from . import helper\n"}, (True, True)),
            "helper_climbs_beyond": ({"hooks/a.py": "import pkg.a.b\n", "hooks/pkg/__init__.py": "", "hooks/pkg/a/__init__.py": "",
                                      "hooks/pkg/a/b.py": "from .. import helper\n", "hooks/pkg/helper.py": "from .. import x\n"}, (False, False)),
            "reexport_chains": ({"hooks/a.py": "from pkg import x, m, z\n", "hooks/pkg/__init__.py": "from .mod import x\nfrom . import mod as m\nfrom .deep.inner import z\n",
                                 "hooks/pkg/mod.py": "x = 1\n", "hooks/pkg/deep/__init__.py": "", "hooks/pkg/deep/inner.py": "z = 1\n"}, (True, True)),
            "reexport_absolute": ({"hooks/a.py": "from pkg import x\n", "hooks/pkg/__init__.py": "from mod import x\n", "hooks/mod.py": "x = 1\n"}, (True, True)),
            "reexport_parent_climb": ({"hooks/a.py": "from pkg.a import x\n", "hooks/pkg/__init__.py": "x = 1\n", "hooks/pkg/a/__init__.py": "from .. import x\n"}, (True, True)),
            "cycle_guard_by_name": ({"hooks/a.py": "from pkg import x\n", "hooks/pkg/__init__.py": "z = 1\nfrom .mod import y as x\n",
                                     "hooks/pkg/mod.py": "from . import z as y\n"}, (True, True)),
            "comp_later_target_checked": ({"hooks/a.py": 'box = {}\n[1 for _ in [1] for box[__import__("nope")] in [1]]\n'}, (False, False)),
            "comp_later_filter_checked": ({"hooks/a.py": '[1 for _ in [1] for __ in [1] if __import__("nope")]\n'}, (False, False)),
            "set_comp_elt_checked": ({"hooks/a.py": '{__import__("nope") for _ in [1]}\n'}, (False, False)),
            "generator_consumed_checked": ({"hooks/a.py": 'list(__import__("nope") for _ in [1])\n'}, (False, False)),
            "comp_later_iter_before_elt": ({"hooks/a.py": '[__import__("boot") for _ in [1] for __ in __import__("lib").__dict__]\n',
                                            "hooks/boot.py": "BOOT", "hooks/g/lib.py": "VALUE = 42\n"}, (False, False)),
            "comp_target_before_filter": ({"hooks/a.py": 'box = {}\n[1 for box[__import__("boot").__name__] in [1] if __import__("lib")]\n',
                                           "hooks/boot.py": "BOOT", "hooks/g/lib.py": "VALUE = 42\n"}, (True, True)),
            "dict_key_before_value": ({"hooks/a.py": '{__import__("boot").__name__: __import__("lib") for _ in [1]}\n',
                                       "hooks/boot.py": "BOOT", "hooks/g/lib.py": "VALUE = 42\n"}, (True, True)),
            "dict_value_not_before_key": ({"hooks/a.py": '{__import__("lib").__name__: __import__("boot") for _ in [1]}\n',
                                           "hooks/boot.py": "BOOT", "hooks/g/lib.py": "VALUE = 42\n"}, (False, False)),
            "late_binding_partial": ({"hooks/a.py": "from pkg import x\n", "hooks/pkg/__init__.py": "from . import helper\nfrom dep import x\n",
                                      "hooks/pkg/helper.py": "from pkg import x\n", "hooks/dep.py": "x = 1\n"}, (False, False)),
            "early_binding_partial": ({"hooks/a.py": "from pkg import x\n", "hooks/pkg/__init__.py": "from dep import x\nfrom . import helper\n",
                                       "hooks/pkg/helper.py": "from pkg import x\n", "hooks/dep.py": "x = 1\n"}, (True, True)),
            "late_assignment_partial": ({"hooks/a.py": "import pkg\n", "hooks/pkg/__init__.py": "from . import helper\nx = 1\n",
                                         "hooks/pkg/helper.py": "from pkg import x\n"}, (False, False)),
            "comp_later_filters_checked_twice": ({"hooks/a.py": '[1 for _ in [1] for __ in [1] if True if __import__("nope")]\n'}, (False, False)),
            "comp_later_iter_before_target": ({"hooks/a.py": 'box = {}\n[1 for _ in [1] for box[__import__("lib").__name__] in __import__("boot").__dict__]\n',
                                               "hooks/boot.py": "BOOT", "hooks/g/lib.py": "VALUE = 42\n"}, (True, True)),
            "comp_later_filter_before_target": ({"hooks/a.py": 'box = {}\n[1 for _ in [1] for box[__import__("boot").__name__] in [1] if __import__("lib")]\n',
                                                 "hooks/boot.py": "BOOT", "hooks/g/lib.py": "VALUE = 42\n"}, (True, True)),
            "comp_generators_in_order": ({"hooks/a.py": '[1 for _ in [1] for a in __import__("boot").__dict__ for b in __import__("lib").__dict__]\n',
                                          "hooks/boot.py": "BOOT", "hooks/g/lib.py": "VALUE = 42\n"}, (True, True)),
            "comp_first_filters_in_order": ({"hooks/a.py": '[1 for _ in [1] if __import__("boot") if __import__("lib")]\n',
                                             "hooks/boot.py": "BOOT", "hooks/g/lib.py": "VALUE = 42\n"}, (True, True)),
            "comp_later_filters_in_order": ({"hooks/a.py": '[1 for _ in [1] for __ in [1] if __import__("boot") if __import__("lib")]\n',
                                             "hooks/boot.py": "BOOT", "hooks/g/lib.py": "VALUE = 42\n"}, (True, True)),
            "dual_context_partial": ({"hooks/a.py": "import pkg.mod\n", "hooks/pkg/__init__.py": "",
                                      "hooks/pkg/mod.py": 'import sys\nfrom pathlib import Path\nsys.path.insert(0, str(Path(__file__).parent))\n'
                                                          'import trigger\nx = 1\n',
                                      "hooks/pkg/trigger.py": "import mod\nfrom pkg.mod import x\n"}, (False, False)),
            "alias_completed_visible": ({"hooks/a.py": "import pkg\n", "hooks/pkg/__init__.py": "import dep, helper\n", "hooks/dep.py": "X = 1\n",
                                         "hooks/helper.py": "from pkg import dep\n"}, (True, True)),
            "rhs_circular": ({"hooks/a.py": "import pkg\n", "hooks/pkg/__init__.py": 'x = __import__("helper")\n', "hooks/helper.py": "from pkg import x\n"},
                             (False, False)),
            "class_body_sees_earlier": ({"hooks/a.py": "import pkg\n", "hooks/pkg/__init__.py": "x = 1\nclass C:\n    import helper\n",
                                         "hooks/helper.py": "from pkg import x\n"}, (True, True)),
            "set_comp_iterable_first": ({"hooks/a.py": '{__import__("boot") for _ in __import__("lib").__dict__}\n', "hooks/boot.py": "BOOT",
                                         "hooks/g/lib.py": "VALUE = 42\n"}, (False, False)),
            "dict_comp_iterable_first": ({"hooks/a.py": '{__import__("boot"): 1 for _ in __import__("lib").__dict__}\n', "hooks/boot.py": "BOOT",
                                          "hooks/g/lib.py": "VALUE = 42\n"}, (False, False)),
            "generator_iterable_first": ({"hooks/a.py": 'list(__import__("boot") for _ in __import__("lib").__dict__)\n', "hooks/boot.py": "BOOT",
                                          "hooks/g/lib.py": "VALUE = 42\n"}, (False, False)),
            "outer_name_paused": ({"hooks/a.py": "import pkg.mod\n", "hooks/pkg/__init__.py": "",
                                   "hooks/pkg/mod.py": 'import sys\nfrom pathlib import Path\nsys.path.insert(0, str(Path(__file__).parent))\n'
                                                       'import trigger\nx = 1\nimport probe\n',
                                   "hooks/pkg/trigger.py": "import mod\n", "hooks/pkg/probe.py": "from pkg.mod import x\n"}, (False, False)),
            "inner_name_bound": ({"hooks/a.py": "import pkg.mod\n", "hooks/pkg/__init__.py": "",
                                  "hooks/pkg/mod.py": 'import sys\nfrom pathlib import Path\nsys.path.insert(0, str(Path(__file__).parent))\n'
                                                      'import trigger\nx = 1\nimport probe\n',
                                  "hooks/pkg/trigger.py": "import mod\n", "hooks/pkg/probe.py": "from mod import x\n"}, (True, True)),
            "from_alias_not_yet_bound": ({"hooks/a.py": "import pkg\n", "hooks/pkg/__init__.py": "from dep import x, helper\n",
                                          "hooks/dep/__init__.py": "x = 1\n", "hooks/dep/helper.py": "from pkg import x\n"}, (False, False)),
            "relative_from_alias_not_yet_bound": ({"hooks/a.py": "import pkg\n", "hooks/pkg/__init__.py": "from .sub import x, helper\n",
                                                   "hooks/pkg/sub/__init__.py": "x = 1\n", "hooks/pkg/sub/helper.py": "from pkg import x\n"}, (False, False)),
            "triple_dirname_root_lib": ({"hooks/a.py": 'import os, sys\nsys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))\nimport lib\n',
                                         "lib.py": "X = 1\n"}, (False, False)),
        }
        for name, (files, _) in shapes.items():
            if files.get("hooks/boot.py", "").startswith("BOOT"):
                files["hooks/boot.py"] = BOOT_INSERTS_G + files["hooks/boot.py"][len("BOOT"):].lstrip("\n")
        outcomes = {name: differential(files) for name, (files, _) in shapes.items()}
        chk(f"differential: for {len(shapes)} tree shapes the checker's verdict equals a fresh interpreter's "
            "(clear iff the hook exits 0), except the three shapes the model refuses by design: "
            + ", ".join(f"{n}={v}" for n, v in outcomes.items()),
            outcomes == {name: expected for name, (_, expected) in shapes.items()})
        chk("search order: an insert at 0 is searched before the script's directory, an insert at 1 after it",
            import_check(["hooks/a.py", "hooks/lib.py", "hooks/guards/lib.py"], shapes["precedence"][0])
            == ["hooks/guards/lib.py imports missing_review_dependency, which is neither standard library nor "
                "in the receipt's files under hooks/guards, hooks"]
            and import_check(["hooks/a.py", "hooks/lib.py", "hooks/guards/lib.py"], shapes["insert_after_own_dir"][0]) == [])
        chk("the inherited path: a module under guards/ may import a sibling of the entry script",
            import_check(["hooks/a.py", "hooks/guards/lib.py", "hooks/helper_lib.py"], shapes["inherited_path"][0]) == [])
        chk("a file named like a standard-library module on the search path is reported as shadowing it",
            import_check(["hooks/a.py", "hooks/json.py"], {"hooks/a.py": "import json\n"})
            == ["hooks/json.py on the search path of hooks/a.py shadows the standard-library module json"]
            and import_check(["hooks/a.py"], {"hooks/a.py": "import json\n"}) == [])
        chk("a sys.path mutation inside control flow is reported and authorises nothing",
            import_check(["hooks/a.py", "hooks/guards/lib.py"], shapes["unexecuted_insert"][0])
            == ["hooks/a.py line 4: sys.path mutated outside a top-level call statement; the search path cannot be ordered",
                "hooks/a.py imports lib, which is neither standard library nor in the receipt's files under hooks"])
        chk("an entry not built from __file__, or an expression the evaluator does not model, is reported",
            import_check(["hooks/a.py", "hooks/guards/lib.py"], shapes["unanchored_entry"][0])
            == ["hooks/a.py line 2: sys.path entry '/nonexistent/guards' is not a path built from __file__ that "
                "the checker resolves",
                "hooks/a.py imports lib, which is neither standard library nor in the receipt's files under hooks"]
            and import_check(["hooks/a.py", "hooks/guards/lib.py"], {"hooks/a.py": 'import os, sys\nd = "guards"\n'
                             'sys.path.insert(0, os.path.join(os.path.dirname(__file__), d))\nimport lib\n',
                             "hooks/guards/lib.py": "X = 1\n"})
            == ["hooks/a.py line 3: sys.path entry os.path.join(os.path.dirname(__file__), d) is not a path built "
                "from __file__ that the checker resolves",
                "hooks/a.py imports lib, which is neither standard library nor in the receipt's files under hooks"])
        chk("`.parent.parent`, `.resolve()`, `os.path.abspath` and a package __init__ resolve as the interpreter does",
            import_check(["hooks/a.py", "tools/lib.py"], shapes["parent_parent"][0]) == []
            and import_check(["hooks/a.py", "hooks/guards/lib.py"], {"hooks/a.py": 'import sys\nfrom pathlib import Path\n'
                             'sys.path.insert(0, str(Path(__file__).resolve().parent / "guards"))\nimport lib\n',
                             "hooks/guards/lib.py": "X = 1\n"}) == []
            and import_check(["hooks/a.py", "hooks/lib.py"], shapes["dirname_abspath"][0]) == []
            and import_check(["hooks/a.py", "hooks/pkg/__init__.py", "hooks/sub.py"], shapes["package"][0]) == []
            and import_check(["hooks/a.py", "hooks/pkg/__init__.py"], shapes["package"][0])
            == ["hooks/pkg/__init__.py imports sub, which loads hooks/sub.py, a file the receipt does not list"])
        chk("a dotted import descends the package: a missing segment, or a segment under a plain module, is reported",
            import_check(["hooks/a.py", "hooks/pkg/__init__.py"], shapes["dotted_missing"][0])
            == ["hooks/a.py imports pkg.nope, which is not in the receipt's files"]
            and import_check(["hooks/a.py", "hooks/pkg.py"], {"hooks/a.py": "import pkg.sub\n", "hooks/pkg.py": "X = 1\n"})
            == ["hooks/a.py imports pkg.sub, but hooks/pkg.py is a module, not a package"]
            and import_check(["hooks/a.py", "hooks/pkg/__init__.py", "hooks/pkg/sub.py"], shapes["from_package_submodule"][0])
            == ["hooks/pkg/sub.py imports missing_review_dependency, which is neither standard library nor in the "
                "receipt's files under hooks"])
        chk("a dynamic import with a constant name resolves like a static one; a non-constant name is reported",
            import_check(["hooks/a.py", "hooks/lib.py"], shapes["dynamic_constant"][0]) == []
            and import_check(["hooks/a.py"], shapes["dynamic_missing"][0])
            == ["hooks/a.py imports nope, which is neither standard library nor in the receipt's files under hooks"]
            and import_check(["hooks/a.py"], {"hooks/a.py": 'import importlib\nname = "lib"\nlib = importlib.import_module(name)\n'})
            == ["hooks/a.py line 3: dynamic import importlib.import_module(name) names no constant module; the "
                "checker cannot resolve it"])
        chk("an import inside a function resolves where the function is defined: a sibling made available "
            "only by a later insert is reported, one made available before is not",
            import_check(["hooks/a.py"], {"hooks/a.py": "def call():\n    import missing_dep\ncall()\n"})
            == ["hooks/a.py imports missing_dep, which is neither standard library nor in the receipt's files under hooks"]
            and import_check(["hooks/a.py", "hooks/guards/lib.py"], {"hooks/a.py": "def call():\n    import lib\n" + prefix,
                                                                     "hooks/guards/lib.py": "X = 1\n"})
            == ["hooks/a.py imports lib, which is neither standard library nor in the receipt's files under hooks"]
            and import_check(["hooks/a.py", "hooks/guards/lib.py"], {"hooks/a.py": prefix + "def call():\n    import lib\n",
                                                                     "hooks/guards/lib.py": "X = 1\n"}) == [])
        chk("a top-level import inside a main guard, or a call made before the insert, resolves at its position",
            import_check(["hooks/a.py", "hooks/guards/lib.py"], shapes["main_guard_before_insert"][0])
            == ["hooks/a.py imports lib, which is neither standard library nor in the receipt's files under hooks"]
            and import_check(["hooks/a.py", "hooks/guards/lib.py"], shapes["function_called_before_insert"][0])
            == ["hooks/a.py imports lib, which is neither standard library nor in the receipt's files under hooks"])
        chk("a from-import of a name the package binds imports nothing more, even when a submodule of that name exists",
            import_check(["hooks/a.py", "hooks/pkg/__init__.py", "hooks/pkg/mod.py"], shapes["from_attribute_masks_module"][0],
                         owned=["a.py"]) == [])
        chk("dynamic imports: a keyword name, `__import__` with a constant fromlist, and a relative name under a "
            "constant package resolve; a non-constant fromlist or a relative level is reported",
            import_check(["hooks/a.py", "hooks/lib.py"], shapes["dynamic_keyword"][0]) == []
            and import_check(["hooks/a.py", "hooks/lib.py"], shapes["dunder_plain"][0]) == []
            and import_check(["hooks/a.py", "hooks/pkg/__init__.py", "hooks/pkg/mod.py"], shapes["dunder_fromlist"][0], owned=["a.py"])
            == ["hooks/pkg/mod.py imports missing_review_dependency, which is neither standard library nor in the "
                "receipt's files under hooks"]
            and import_check(["hooks/a.py", "hooks/pkg/__init__.py", "hooks/pkg/sub.py"],
                             {"hooks/a.py": 'import importlib\nsub = importlib.import_module(".sub", "pkg")\n',
                              "hooks/pkg/__init__.py": "", "hooks/pkg/sub.py": "X = 1\n"}, owned=["a.py"]) == []
            and import_check(["hooks/a.py"], {"hooks/a.py": 'names = ["x"]\npkg = __import__("os", fromlist=names)\n'})
            == ['hooks/a.py line 2: dynamic import __import__(\'os\', fromlist=names) has a fromlist the checker does not read']
            and import_check(["hooks/a.py"], {"hooks/a.py": 'pkg = __import__("os", globals(), locals(), [], 1)\n'})
            == ["hooks/a.py line 1: dynamic import __import__('os', globals(), locals(), [], 1) is relative; the checker "
                "cannot resolve it"])
        chk("a tree file named like a standard-library module is reported even when only another standard-library "
            "module would import it",
            import_check(["hooks/a.py", "hooks/fractions.py"], shapes["stdlib_transitive_shadow"][0], owned=["a.py"])
            == ["hooks/fractions.py on the search path of hooks/a.py shadows the standard-library module fractions"])
        chk("`.resolve()` collapses `..` where it stands, so a later `.parent` climbs from the collapsed path",
            import_check(["hooks/a.py", "tools/lib.py"], shapes["resolved_parent"][0]) == [])
        chk("a package's own `from . import name` is no evidence that `name` exists: the submodule is walked, "
            "or its absence reported",
            import_check(["hooks/a.py", "hooks/pkg/__init__.py"], shapes["package_self_import_missing"][0], owned=["a.py"])
            == ["hooks/pkg/__init__.py imports absent from ., which hooks/pkg/__init__.py neither binds nor holds as a submodule"]
            and import_check(["hooks/a.py", "hooks/pkg/__init__.py", "hooks/pkg/mod.py"], shapes["package_self_import_broken"][0],
                             owned=["a.py"])
            == ["hooks/pkg/mod.py imports missing_review_dependency, which is neither standard library nor in the "
                "receipt's files under hooks"])
        chk("a binding counts only from a top-level statement that always runs and is not deleted",
            all(import_check(["hooks/a.py", "hooks/mod.py"], {"hooks/a.py": "from mod import x\n", "hooks/mod.py": body}, owned=["a.py"])
                == ["hooks/a.py imports x from mod, which hooks/mod.py neither binds nor holds as a submodule"]
                for body in ("def f():\n    x = 1\n", "if False:\n    x = 1\n", "x = 1\ndel x\n", "class C:\n    x = 1\n"))
            and import_check(["hooks/a.py", "hooks/mod.py"], {"hooks/a.py": "from mod import x, y\n",
                                                              "hooks/mod.py": "with open(__file__) as x:\n    pass\ny: int = 2\n"},
                             owned=["a.py"]) == [])
        chk("expressions in a function's defaults, a with header and a decorator are resolved where they stand",
            all(import_check(["hooks/a.py"], files)
                == ['hooks/a.py imports nope, which is neither standard library nor in the receipt\'s files under hooks']
                for files in (shapes["default_arg_dynamic"][0], shapes["with_dynamic"][0],
                              {"hooks/a.py": 'import importlib\n@importlib.import_module("nope")\ndef f(): pass\n'})))
        chk("a body that may never run establishes nothing: an insert made by a module it imports, or a module it "
            "caches, does not serve the importer's later imports",
            import_check(["hooks/a.py", "hooks/inserter.py", "hooks/guards/second.py"], shapes["uncalled_function_inserts"][0],
                         owned=["a.py"])
            == ["hooks/a.py imports second, which is neither standard library nor in the receipt's files under hooks"]
            and import_check(["hooks/a.py", "hooks/lib.py", "hooks/guards/lib.py"], shapes["unreachable_import_caches"][0],
                             owned=["a.py"])
            == ["hooks/guards/lib.py imports missing_review_dependency, which is neither standard library nor in the "
                "receipt's files under hooks/guards, hooks"])
        chk("a script run by file name, or a module found by name on the path, has no package context even beside "
            "an __init__.py",
            import_check(["hooks/a.py", "hooks/__init__.py", "hooks/helper.py"], shapes["entry_relative_with_init"][0], owned=["a.py"])
            == ["hooks/a.py line 1: relative import from . import helper from a module that has no package context"]
            and import_check(["hooks/a.py", "hooks/__init__.py", "hooks/lib.py", "hooks/helper.py"],
                             {"hooks/a.py": "import lib\n", "hooks/__init__.py": "", "hooks/lib.py": "from . import helper\n",
                              "hooks/helper.py": "X = 1\n"}, owned=["a.py"])
            == ["hooks/lib.py line 1: relative import from . import helper from a module that has no package context"])
        chk("a relative dotted import does not descend through a plain module",
            import_check(["hooks/a.py", "hooks/pkg/__init__.py", "hooks/pkg/sub.py", "hooks/pkg/mod.py", "hooks/pkg/child.py"],
                         shapes["relative_dotted_through_module"][0], owned=["a.py"])
            == ["hooks/pkg/sub.py imports .mod.child, but hooks/pkg/mod.py is a module, not a package"])
        chk("a relative dynamic import deeper than its package is reported, not read as absolute",
            import_check(["hooks/a.py", "hooks/pkg/__init__.py", "hooks/sub.py"], shapes["dynamic_relative_beyond_top"][0], owned=["a.py"])
            == ["hooks/a.py line 2: dynamic import importlib.import_module('..sub', 'pkg') climbs beyond the top-level package"])
        chk("`.absolute()` keeps `..`, so a later `.parent` climbs from the unnormalised path",
            import_check(["hooks/a.py", "hooks/g/tools/lib.py"], shapes["absolute_keeps_dotdot"][0]) == []
            and import_check(["hooks/a.py", "tools/lib.py"], {"hooks/a.py": shapes["absolute_keeps_dotdot"][0]["hooks/a.py"],
                                                              "tools/lib.py": "VALUE = 42\n"})
            == ["hooks/a.py imports lib, which is neither standard library nor in the receipt's files under hooks/g/tools, hooks"])
        chk("the parent of the tree root is above the tree, so a path that climbs out and re-enters is outside",
            import_check(["hooks/a.py", "tools/lib.py"], {"hooks/a.py": 'import sys\nfrom pathlib import Path\n'
                         'sys.path.insert(0, str(Path(__file__).parent.parent.parent / "tree/tools"))\nimport lib\n',
                         "tools/lib.py": "X = 1\n"})
            == ["hooks/a.py inserts a sys.path entry outside the tree (../tree/tools)",
                "hooks/a.py imports lib, which is neither standard library nor in the receipt's files under hooks"]
            and import_check(["hooks/a.py", "tools/lib.py"], {"hooks/a.py": 'import os, sys\n'
                             'sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "tools"))\nimport lib\n',
                             "tools/lib.py": "X = 1\n"}) == [])
        chk("under a package too, a directory beats a module of the same name; a directory without __init__.py is "
            "reported as a namespace package the checker does not model",
            import_check(["hooks/a.py", "hooks/pkg/__init__.py", "hooks/pkg/sub.py", "hooks/pkg/sub/__init__.py"],
                         {"hooks/a.py": "import pkg.sub\n", "hooks/pkg/__init__.py": "", "hooks/pkg/sub.py": "X = 1\n",
                          "hooks/pkg/sub/__init__.py": "import missing_review_dependency\n"}, owned=["a.py"])
            == ["hooks/pkg/sub/__init__.py imports missing_review_dependency, which is neither standard library nor in "
                "the receipt's files under hooks"]
            and import_check(["hooks/a.py", "hooks/pkg/mod.py"], {"hooks/a.py": "import pkg.mod\n", "hooks/pkg/mod.py": "X = 1\n"},
                             owned=["a.py"])
            == ["hooks/a.py imports pkg, but hooks/pkg/ holds no __init__.py: a namespace package the checker does not model"])
        chk("the normalising os.path calls collapse `..` where they stand; importlib.__import__, a package keyword "
            "and a positional fromlist are read; a builtin name is reported like any other shadow",
            import_check(["hooks/a.py", "tools/lib.py"], {"hooks/a.py": 'import os, sys\nsys.path.insert(0, os.path.join('
                         'os.path.dirname(os.path.normpath(os.path.join(os.path.dirname(__file__), "g", ".."))), "tools"))\nimport lib\n',
                         "tools/lib.py": "X = 1\n"}) == []
            and import_check(["hooks/a.py"], {"hooks/a.py": 'import importlib\nm = importlib.__import__("nope")\n'})
            == ["hooks/a.py imports nope, which is neither standard library nor in the receipt's files under hooks"]
            and import_check(["hooks/a.py", "hooks/pkg/__init__.py", "hooks/pkg/sub.py"],
                             {"hooks/a.py": 'import importlib\nsub = importlib.import_module(".sub", package="pkg")\n',
                              "hooks/pkg/__init__.py": "", "hooks/pkg/sub.py": "X = 1\n"}, owned=["a.py"]) == []
            and import_check(["hooks/a.py", "hooks/pkg/__init__.py", "hooks/pkg/mod.py"],
                             {"hooks/a.py": 'pkg = __import__("pkg", globals(), locals(), ["mod"])\n', "hooks/pkg/__init__.py": "",
                              "hooks/pkg/mod.py": "import missing_review_dependency\n"}, owned=["a.py"])
            == ["hooks/pkg/mod.py imports missing_review_dependency, which is neither standard library nor in the "
                "receipt's files under hooks"]
            and import_check(["hooks/a.py", "hooks/sys.py"], {"hooks/a.py": "import sys\n"}, owned=["a.py"])
            == ["hooks/sys.py on the search path of hooks/a.py shadows the standard-library module sys"])
        chk("a module walked speculatively is walked again by its real import, whose mutations then count",
            import_check(["hooks/a.py", "hooks/m.py", "hooks/extra/dep.py"], shapes["speculative_walk_then_real"][0], owned=["a.py"]) == [])
        chk("one file loaded as a package member and again by bare name is walked in each context, and its relative "
            "import is reported for the bare load",
            import_check(["hooks/a.py", "hooks/pkg/__init__.py", "hooks/pkg/sub.py", "hooks/pkg/helper.py"],
                         shapes["same_file_two_contexts"][0], owned=["a.py"])
            == ["hooks/pkg/sub.py line 1: relative import from . import helper from a module that has no package context"])
        chk("a dynamic import in a class base, an exception type, a match guard or a loop condition, and an import "
            "in a class body, resolve where they stand",
            all(import_check(["hooks/a.py"], shapes[name][0]) == [
                    "hooks/a.py imports nope, which is neither standard library nor in the receipt's files under hooks"]
                for name in ("class_base_dynamic", "except_type_dynamic", "match_guard_dynamic", "loop_condition_dynamic",
                             "class_body_import")))
        chk("a branch establishes nothing for its sibling branch, and a function body nothing for the decorator "
            "that runs before it",
            import_check(["hooks/a.py", "hooks/boot.py", "hooks/g/lib.py"], shapes["else_after_false_boot"][0], owned=["a.py"])
            == ["hooks/a.py imports lib, which is neither standard library nor in the receipt's files under hooks"]
            and import_check(["hooks/a.py", "hooks/boot.py", "hooks/g/lib.py"], shapes["decorator_before_body"][0], owned=["a.py"])
            == ["hooks/a.py imports lib, which is neither standard library nor in the receipt's files under hooks"])
        chk("binding evidence: the identity alias, a subscript target, an annotation without a value and a star "
            "import bind nothing; a deleted subscript keeps the binding its index reads",
            import_check(["hooks/a.py", "hooks/pkg/__init__.py", "hooks/pkg/sub.py"], shapes["self_import_alias"][0], owned=["a.py"])
            == ["hooks/pkg/sub.py imports missing_review_dependency, which is neither standard library nor in the receipt's files under hooks"]
            and import_check(["hooks/a.py", "hooks/pkg/__init__.py", "hooks/pkg/len.py"], shapes["subscript_target_is_a_read"][0], owned=["a.py"])
            == ["hooks/pkg/len.py imports missing_review_dependency, which is neither standard library nor in the receipt's files under hooks"]
            and import_check(["hooks/a.py", "hooks/pkg/__init__.py", "hooks/pkg/len.py"], shapes["del_subscript_keeps_binding"][0], owned=["a.py"]) == []
            and import_check(["hooks/a.py", "hooks/pkg/__init__.py", "hooks/pkg/sub.py"], shapes["annotation_only"][0], owned=["a.py"])
            == ["hooks/pkg/sub.py imports missing_review_dependency, which is neither standard library nor in the receipt's files under hooks"]
            and import_check(["hooks/a.py", "hooks/pkg/__init__.py", "hooks/pkg/other.py", "hooks/pkg/sub.py"],
                             shapes["star_import_binds_nothing"][0], owned=["a.py"])
            == ["hooks/pkg/sub.py imports missing_review_dependency, which is neither standard library nor in the receipt's files under hooks"])
        chk("relative depth comes from the package the import reached, not from the directories around the file; a "
            "submodule reached through `from pkg import sub` keeps its package",
            import_check(["hooks/a.py", "hooks/__init__.py", "hooks/helper.py", "hooks/pkg/__init__.py"],
                         shapes["relative_beyond_logical_package"][0], owned=["a.py"])
            == ["hooks/pkg/__init__.py line 1: relative import from .. import helper climbs beyond the top-level package"]
            and import_check(["hooks/a.py", "hooks/pkg/__init__.py", "hooks/pkg/sub.py", "hooks/pkg/helper.py"],
                             shapes["from_package_relative"][0], owned=["a.py"]) == [])
        chk("an `__import__` call with an argument the checker does not read is reported; a dynamic import in an "
            "if or for header resolves where it stands",
            import_check(["hooks/a.py"], shapes["dunder_unknown_keyword"][0])
            == ["hooks/a.py line 1: dynamic import __import__('os', nope=True) has arguments the checker does not read"]
            and all(import_check(["hooks/a.py"], shapes[n][0])
                    == ["hooks/a.py imports nope, which is neither standard library nor in the receipt's files under hooks"]
                    for n in ("if_header_dynamic", "for_header_dynamic")))
        chk("os.path.abspath and os.path.realpath each collapse `..` where they stand; the parent of a path above "
            "the tree climbs further",
            all(import_check(["hooks/a.py", "tools/lib.py"], {"hooks/a.py": f'import os, sys\nsys.path.insert(0, os.path.join('
                             f'os.path.dirname({call}(os.path.join(os.path.dirname(__file__), "g", ".."))), "tools"))\nimport lib\n',
                             "tools/lib.py": "X = 1\n"}) == [] for call in ("os.path.abspath", "os.path.realpath"))
            and import_check(["hooks/a.py", "x/lib.py"], {"hooks/a.py": 'import sys\nfrom pathlib import Path\n'
                             'sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "x"))\nimport lib\n', "x/lib.py": "X = 1\n"})
            == ["hooks/a.py inserts a sys.path entry outside the tree (../../x)",
                "hooks/a.py imports lib, which is neither standard library nor in the receipt's files under hooks"]
            and import_check(["hooks/a.py"], {"hooks/a.py": "import pkg.mod\n", "hooks/pkg/mod.py": "X = 1\n"}, owned=["a.py"])
            == ["hooks/a.py imports pkg, but hooks/pkg/ holds no __init__.py: a namespace package the checker does not model"])
        chk("a problem met on two walks of one file is reported once",
            import_check(["hooks/a.py", "hooks/pkg/__init__.py", "hooks/pkg/sub.py"],
                         {"hooks/a.py": 'import sys\nfrom pathlib import Path\n'
                                        'sys.path.insert(0, str(Path(__file__).parent / "pkg"))\nimport pkg.sub\nimport sub\n',
                          "hooks/pkg/__init__.py": "", "hooks/pkg/sub.py": "import missing_review_dependency\n"}, owned=["a.py"])
            == ["hooks/pkg/sub.py imports missing_review_dependency, which is neither standard library nor in the receipt's "
                "files under hooks/pkg, hooks"])
        chk("a lambda body, a short-circuit operand, a conditional branch and a comprehension body establish nothing; "
            "a top-level dynamic import does",
            all(import_check(["hooks/a.py", "hooks/boot.py", "hooks/g/lib.py"], shapes[n][0], owned=["a.py"])
                == ["hooks/a.py imports lib, which is neither standard library nor in the receipt's files under hooks"]
                for n in ("lambda_boot", "shortcircuit_boot", "ternary_boot", "empty_comprehension_boot"))
            and import_check(["hooks/a.py", "hooks/boot.py", "hooks/g/lib.py"], shapes["immediate_dynamic_boot"][0], owned=["a.py"]) == [])
        chk("the later operands of a short-circuit and the else branch of a conditional are still checked; the "
            "first operand, a conditional's test, a comprehension's first iterable and a lambda's defaults keep "
            "their effects",
            all(import_check(["hooks/a.py"], shapes[n][0]) == [
                    "hooks/a.py imports nope, which is neither standard library nor in the receipt's files under hooks"]
                for n in ("later_operand_checked", "else_branch_checked"))
            and all(import_check(["hooks/a.py", "hooks/boot.py", "hooks/g/lib.py"], shapes[n][0], owned=["a.py"]) == []
                    for n in ("test_effect_kept", "first_iterable_effect_kept", "first_operand_effect_kept",
                              "lambda_default_effect_kept")))
        chk("comprehension parts resolve in evaluation order: the first target, filters, later generators and a "
            "dict's key and value are checked, and a filter runs before the result expression",
            all(import_check(["hooks/a.py"], shapes[n][0]) == [
                    "hooks/a.py imports nope, which is neither standard library nor in the receipt's files under hooks"]
                for n in ("comp_target_checked", "comp_filter_checked", "comp_later_generator_checked", "comp_dict_key_checked",
                          "comp_dict_value_checked", "lambda_body_checked", "if_body_checked"))
            and import_check(["hooks/a.py", "hooks/boot.py", "hooks/g/lib.py"], shapes["comp_filter_before_elt"][0], owned=["a.py"])
            == ["hooks/a.py imports lib, which is neither standard library nor in the receipt's files under hooks"]
            and import_check(["hooks/a.py", "hooks/boot.py", "hooks/g/lib.py"], shapes["comp_elt_after_boot_iterable"][0], owned=["a.py"]) == [])
        chk("every comprehension part is checked (a later generator's target and filter, a set's element, a consumed "
            "generator) and each runs in order: the target before the filter, a later iterable before the element, a "
            "dict's key before its value",
            all(import_check(["hooks/a.py"], shapes[n][0]) == [
                    "hooks/a.py imports nope, which is neither standard library nor in the receipt's files under hooks"]
                for n in ("comp_later_target_checked", "comp_later_filter_checked", "set_comp_elt_checked", "generator_consumed_checked"))
            and all(import_check(["hooks/a.py", "hooks/boot.py", "hooks/g/lib.py"], shapes[n][0], owned=["a.py"])
                    == ["hooks/a.py imports lib, which is neither standard library nor in the receipt's files under hooks"]
                    for n in ("comp_later_iter_before_elt", "dict_value_not_before_key"))
            and all(import_check(["hooks/a.py", "hooks/boot.py", "hooks/g/lib.py"], shapes[n][0], owned=["a.py"]) == []
                    for n in ("comp_target_before_filter", "dict_key_before_value")))
        chk("a module still initialising binds only what it has executed: an import reaching back into it before "
            "the binding is reported, after it is accepted",
            import_check(["hooks/a.py", "hooks/pkg/__init__.py", "hooks/pkg/helper.py", "hooks/dep.py"], shapes["late_binding_partial"][0], owned=["a.py"])
            == ["hooks/pkg/helper.py imports x from pkg, which hooks/pkg/__init__.py neither binds nor holds as a submodule"]
            and import_check(["hooks/a.py", "hooks/pkg/__init__.py", "hooks/pkg/helper.py", "hooks/dep.py"], shapes["early_binding_partial"][0], owned=["a.py"]) == []
            and import_check(["hooks/a.py", "hooks/pkg/__init__.py", "hooks/pkg/helper.py"], shapes["late_assignment_partial"][0], owned=["a.py"])
            == ["hooks/pkg/helper.py imports x from pkg, which hooks/pkg/__init__.py neither binds nor holds as a submodule"])
        chk("a file loading under two names keeps each load's position; the aliases already completed inside one "
            "`import` statement count; the statement being executed does not; a nested body sees earlier top-level bindings",
            import_check(["hooks/a.py", "hooks/pkg/__init__.py", "hooks/pkg/mod.py", "hooks/pkg/trigger.py"], shapes["dual_context_partial"][0], owned=["a.py"])
            == ["hooks/pkg/trigger.py imports x from pkg.mod, which hooks/pkg/mod.py neither binds nor holds as a submodule"]
            and import_check(["hooks/a.py", "hooks/pkg/__init__.py", "hooks/dep.py", "hooks/helper.py"], shapes["alias_completed_visible"][0], owned=["a.py"]) == []
            and import_check(["hooks/a.py", "hooks/pkg/__init__.py", "hooks/helper.py"], shapes["rhs_circular"][0], owned=["a.py"])
            == ["hooks/helper.py imports x from pkg, which hooks/pkg/__init__.py neither binds nor holds as a submodule"]
            and import_check(["hooks/a.py", "hooks/pkg/__init__.py", "hooks/helper.py"], shapes["class_body_sees_earlier"][0], owned=["a.py"]) == [])
        dual_files = ["hooks/a.py", "hooks/pkg/__init__.py", "hooks/pkg/mod.py", "hooks/pkg/trigger.py", "hooks/pkg/probe.py"]
        chk("an import reads the position of the load it names: the paused `pkg.mod` has not bound x while the complete "
            "`mod` has; a `from` import binds none of its names until the whole statement completes, absolute or relative",
            import_check(dual_files, shapes["outer_name_paused"][0], owned=["a.py"])
            == ["hooks/pkg/probe.py imports x from pkg.mod, which hooks/pkg/mod.py neither binds nor holds as a submodule"]
            and import_check(dual_files, shapes["inner_name_bound"][0], owned=["a.py"]) == []
            and import_check(["hooks/a.py", "hooks/pkg/__init__.py", "hooks/dep/__init__.py", "hooks/dep/helper.py"],
                             shapes["from_alias_not_yet_bound"][0], owned=["a.py"])
            == ["hooks/dep/helper.py imports x from pkg, which hooks/pkg/__init__.py neither binds nor holds as a submodule"]
            and import_check(["hooks/a.py", "hooks/pkg/__init__.py", "hooks/pkg/sub/__init__.py", "hooks/pkg/sub/helper.py"],
                             shapes["relative_from_alias_not_yet_bound"][0], owned=["a.py"])
            == ["hooks/pkg/sub/helper.py imports x from pkg, which hooks/pkg/__init__.py neither binds nor holds as a submodule"])
        chk("set, dict and generator comprehensions evaluate their first iterable before their result expression",
            all(import_check(["hooks/a.py", "hooks/boot.py", "hooks/g/lib.py"], shapes[n][0], owned=["a.py"])
                == ["hooks/a.py imports lib, which is neither standard library nor in the receipt's files under hooks"]
                for n in ("set_comp_iterable_first", "dict_comp_iterable_first", "generator_iterable_first")))
        chk("comprehension order, continued: a second filter is checked; a later target runs after its iterable and "
            "before its filters; generators and filters run in source order with effects kept between them",
            import_check(["hooks/a.py"], shapes["comp_later_filters_checked_twice"][0])
            == ["hooks/a.py imports nope, which is neither standard library nor in the receipt's files under hooks"]
            and all(import_check(["hooks/a.py", "hooks/boot.py", "hooks/g/lib.py"], shapes[n][0], owned=["a.py"]) == []
                    for n in ("comp_later_iter_before_target", "comp_later_filter_before_target", "comp_generators_in_order",
                              "comp_first_filters_in_order", "comp_later_filters_in_order")))
        chk("a starred positional argument is reported; a binding source already loaded is read from the cache, not "
            "the path; a decorator's effect precedes the body it decorates",
            import_check(["hooks/a.py"], shapes["starred_positional"][0])
            == ["hooks/a.py line 1: dynamic import __import__(*['os']) has arguments the checker does not read"]
            and import_check(["hooks/a.py", "hooks/dep.py", "hooks/shadow/dep.py", "hooks/pkg/__init__.py"], shapes["cached_source_binding"][0],
                             owned=["a.py"]) == []
            and import_check(["hooks/a.py", "hooks/boot.py", "hooks/g/lib.py"], shapes["decorator_effect_before_body"][0], owned=["a.py"]) == [])
        chk("package depth: a subpackage's __init__ reaches its parent at level two; submodules reached by from-import "
            "keep their depth; a helper that climbs beyond the top level is reported; re-export chains provide names",
            import_check(["hooks/a.py", "hooks/pkg/__init__.py", "hooks/pkg/helper.py", "hooks/pkg/a/__init__.py"],
                         shapes["subpackage_init_relative"][0], owned=["a.py"]) == []
            and import_check(["hooks/a.py", "hooks/pkg/__init__.py", "hooks/pkg/helper.py", "hooks/pkg/sub/__init__.py", "hooks/pkg/mod.py"],
                             shapes["from_import_subpackage_relative"][0], owned=["a.py"]) == []
            and import_check(["hooks/a.py", "hooks/pkg/__init__.py", "hooks/pkg/a/__init__.py", "hooks/pkg/a/b.py", "hooks/pkg/helper.py"],
                             shapes["helper_climbs_beyond"][0], owned=["a.py"])
            == ["hooks/pkg/helper.py line 1: relative import from .. import x climbs beyond the top-level package"]
            and all(import_check(sorted(shapes[n][0]), shapes[n][0], owned=["a.py"]) == []
                    for n in ("reexport_chains", "reexport_absolute", "reexport_parent_climb", "cycle_guard_by_name"))
            and import_check(["hooks/a.py", "lib.py"], shapes["triple_dirname_root_lib"][0], owned=["a.py"])
            == ["hooks/a.py inserts a sys.path entry outside the tree (..)",
                "hooks/a.py imports lib, which is neither standard library nor in the receipt's files under hooks"])
        chk("a dynamic import's arguments are evaluated before the call, so an inner import runs first",
            import_check(["hooks/a.py", "hooks/boot.py", "hooks/g/lib.py"], shapes["argument_before_call"][0], owned=["a.py"])
            == ["hooks/a.py imports lib, which is neither standard library nor in the receipt's files under hooks"]
            and import_check(["hooks/a.py", "hooks/boot.py", "hooks/g/lib.py"], shapes["argument_before_call_valid"][0], owned=["a.py"]) == [])
        chk("two self-imports vouching for each other under different aliases bind nothing; a with header runs "
            "before its body",
            import_check(["hooks/a.py", "hooks/pkg/__init__.py"], shapes["cross_alias_cycle"][0], owned=["a.py"])
            == ["hooks/pkg/__init__.py imports sub from ., which hooks/pkg/__init__.py neither binds nor holds as a submodule",
                "hooks/pkg/__init__.py imports other from ., which hooks/pkg/__init__.py neither binds nor holds as a submodule",
                "hooks/a.py imports sub from pkg, which hooks/pkg/__init__.py neither binds nor holds as a submodule"]
            and import_check(["hooks/a.py", "hooks/boot.py", "hooks/g/lib.py"], shapes["with_header_before_body"][0], owned=["a.py"])
            == ["hooks/a.py imports lib, which is neither standard library nor in the receipt's files under hooks"])
        chk("an unpacked keyword, a keyword repeating a positional parameter and a positional overflow are reported",
            all(import_check(["hooks/a.py"], shapes[n][0]) == [f"hooks/a.py line 1: dynamic import {call} has arguments the "
                                                               "checker does not read"]
                for n, call in (("unpacked_keywords", "__import__('os', **{'nope': True})"),
                                ("duplicate_name", "__import__('os', name='sys')"),
                                ("positional_overflow", "__import__('os', {}, {}, [], 0, 7)"))))
        chk("package depth follows nested packages: level two from pkg/a/b.py reaches pkg, level three is beyond; "
            "a module reached by a relative import keeps its package; unpacking targets bind",
            import_check(["hooks/a.py", "hooks/pkg/__init__.py", "hooks/pkg/a/__init__.py", "hooks/pkg/a/b.py", "hooks/pkg/helper.py"],
                         shapes["nested_package_relative"][0], owned=["a.py"])
            == ["hooks/pkg/a/b.py line 2: relative import from ... import helper as h2 climbs beyond the top-level package"]
            and import_check(["hooks/a.py", "hooks/pkg/__init__.py", "hooks/pkg/a/__init__.py", "hooks/pkg/a/b.py", "hooks/pkg/helper.py",
                              "hooks/pkg/a/sibling.py"], shapes["nested_package_relative_ok"][0], owned=["a.py"]) == []
            and import_check(["hooks/a.py", "hooks/pkg/__init__.py", "hooks/pkg/a.py", "hooks/pkg/helper.py"],
                             shapes["relative_reached_module_relative"][0], owned=["a.py"]) == []
            and import_check(["hooks/a.py", "hooks/pkg/__init__.py"], shapes["unpacking_targets_bind"][0], owned=["a.py"]) == [])
        chk("a sys.path mutation made by an imported module persists for the importer's later imports",
            import_check(["hooks/a.py", "hooks/lib.py", "hooks/guards/second.py"], shapes["path_change_persists"][0],
                         owned=["a.py"]) == [])
        chk("every identity call and `.absolute()` resolve a path built from __file__",
            all(import_check(["hooks/a.py", "hooks/guards/lib.py"],
                             {"hooks/a.py": f'import os, pathlib, sys\nsys.path.insert(0, {call}(os.path.join(os.path.dirname(__file__), "guards")))\nimport lib\n',
                              "hooks/guards/lib.py": "X = 1\n"}) == []
                for call in sorted(PATH_IDENTITY_CALLS))
            and import_check(["hooks/a.py", "hooks/guards/lib.py"],
                             {"hooks/a.py": 'import pathlib, sys\nsys.path.insert(0, str(pathlib.Path(__file__).absolute().parent / "guards"))\nimport lib\n',
                              "hooks/guards/lib.py": "X = 1\n"}) == [])
        chk("a file on the search path that the receipt does not list is what the interpreter loads, and is reported",
            import_check(["hooks/a.py", "hooks/lib.py"], {"hooks/a.py": prefix + "import lib\n", "hooks/lib.py": "X = 1\n",
                                                          "hooks/guards/lib.py": "import missing_review_dependency\n"})
            == ["hooks/a.py imports lib, which loads hooks/guards/lib.py, a file the receipt does not list",
                "hooks/guards/lib.py imports missing_review_dependency, which is neither standard library nor in the "
                "receipt's files under hooks/guards, hooks"])
        chk("a package directory beats a module file of the same name, as the interpreter's finder does",
            import_check(["hooks/a.py", "hooks/lib.py", "hooks/lib/__init__.py"], shapes["package_over_module"][0],
                         owned=["a.py"]) == [])
        chk("a from-import requires the module to bind the name or hold it as a submodule",
            import_check(["hooks/a.py", "hooks/mod.py"], {"hooks/a.py": "from mod import missing_name\n",
                                                          "hooks/mod.py": "present = 1\ndef f(): pass\n"}, owned=["a.py"])
            == ["hooks/a.py imports missing_name from mod, which hooks/mod.py neither binds nor holds as a submodule"]
            and import_check(["hooks/a.py", "hooks/mod.py"], {"hooks/a.py": "from mod import present, f, imported, aliased\n",
                                                              "hooks/mod.py": "import os as imported\nfrom sys import argv as aliased\n"
                                                                              "present = 1\ndef f(): pass\n"}, owned=["a.py"]) == []
            and import_check(["hooks/a.py", "hooks/pkg/__init__.py", "hooks/pkg/sub.py"],
                             {"hooks/a.py": "from pkg import sub, attr\n", "hooks/pkg/__init__.py": "attr = 1\n",
                              "hooks/pkg/sub.py": "X = 1\n"}, owned=["a.py"]) == [])
        chk("an appended directory is searched after the script's own; an insert index other than 0 or 1 is reported",
            import_check(["hooks/a.py", "hooks/lib.py", "hooks/guards/lib.py"], shapes["append_after_own_dir"][0]) == []
            and import_check(["hooks/a.py", "hooks/guards/lib.py"], shapes["insert_index_2_refused"][0])
            == ["hooks/a.py line 3: unsupported sys.path mutation sys.path.insert(2, str(Path(__file__).parent / 'guards'))",
                "hooks/a.py imports lib, which is neither standard library nor in the receipt's files under hooks"])
        chk("a relative import resolves from the importing file's package; outside a package it is reported",
            import_check(["hooks/a.py", "hooks/pkg/__init__.py", "hooks/pkg/sub.py", "hooks/pkg/helper.py"],
                         shapes["relative_in_package"][0]) == []
            and import_check(["hooks/a.py", "hooks/helper.py"], shapes["relative_outside_package"][0])
            == ["hooks/a.py line 1: relative import from . import helper from a module that has no package context"]
            and import_check(["hooks/a.py", "hooks/pkg/__init__.py", "hooks/pkg/sub.py"], shapes["relative_missing"][0])
            == ["hooks/pkg/sub.py imports nope from ., which hooks/pkg/__init__.py neither binds nor holds as a submodule"])
        chk("the module cache is per owned script: two hooks importing one name from different search paths "
            "each get their own file",
            import_check(["hooks/a.py", "hooks/b.py", "hooks/lib.py", "hooks/guards/lib.py"],
                         {"hooks/a.py": prefix + "import lib\n", "hooks/b.py": "import lib\n",
                          "hooks/lib.py": "import missing_review_dependency\n", "hooks/guards/lib.py": "X = 1\n"},
                         owned=["a.py", "b.py"])
            == ["hooks/lib.py imports missing_review_dependency, which is neither standard library nor in the "
                "receipt's files under hooks"])
        chk("a name resolves once per process: a later import of the same name from another directory is the cached module",
            import_check(["hooks/a.py", "hooks/lib.py", "hooks/guards/lib.py", "hooks/guards/second.py"],
                         {"hooks/a.py": "import lib\n" + prefix + "import second\n", "hooks/lib.py": "X = 1\n",
                          "hooks/guards/lib.py": "import missing_review_dependency\n",
                          "hooks/guards/second.py": "import lib\n"}) == [])
        chk("review reproduction 4298561313: the checker's verdict follows the module Python loads",
            reproduction(4298561313, "precedence preflight_clear, activated, check_exit, hook_exit = "
                                     "(False, False, 1, 1)"))

        moved_home = os.path.join(td, "moved-home")
        shutil.copytree(dep_home, moved_home)
        stage(dep_source, moved_home, version_id="v2")
        activate(moved_home, "v2")
        moved_tree = tree_path(moved_home, "v2")
        os.replace(os.path.join(moved_tree, "hooks", "helper_lib.py"), os.path.join(moved_tree, "tools", "helper_lib.py"))
        for receipt_path in (os.path.join(moved_tree, RECEIPT_NAME), active_receipt_path(moved_home)):
            moved = load_json(receipt_path)
            moved["files"]["tools/helper_lib.py"] = moved["files"].pop("hooks/helper_lib.py")
            atomic_write(receipt_path, (json.dumps(moved, indent=2, sort_keys=True) + "\n").encode("utf-8"))
        buf = io.StringIO()
        chk("--check names a sibling module relocated to a directory the hook does not search",
            check(moved_home, dep_source, out=buf) == 1
            and "hooks/dep_guard.py imports helper_lib" in buf.getvalue())
        operand_options = ["-r", "--require", "--import", "--loader", "--experimental-loader", "-C",
                           "--conditions", "--input-type", "--title", "--stack-trace-limit",
                           "--max-old-space-size", "-e", "--eval", "-p", "--print"]
        chk("each of the fifteen interpreter options that take an operand is skipped with its operand",
            sorted(operand_options) == sorted(OPTIONS_WITH_OPERAND)
            and all(script_operand("/usr/local/bin/node", f"node {option} value /x/@anthropic-ai/claude-code/cli.js")
                    == "/x/@anthropic-ai/claude-code/cli.js" for option in operand_options)
            and script_operand("/usr/local/bin/node", "node --unknown-flag /x/cli.js") == "/x/cli.js")

        chk("review reproduction 4294811755: a switch killed after its settings replace rolls back "
            "to exactly v1's entries",
            reproduction(4294811755, "hooks= {'v1': 4, 'v2': 0}"))

        # --- the interval between the final stat and the rename: reported, bounded, and
        # proven uncovered; refused only on request
        rows = [
            (12, "/Applications/Claude.app/Contents/MacOS/Claude",
             "/Applications/Claude.app/Contents/MacOS/Claude"),
            (13, "/Applications/Claude.app/Contents/Frameworks/Claude Helper.app/Contents/MacOS/Claude Helper",
             "/Applications/Claude.app/Contents/Frameworks/Claude Helper.app/Contents/MacOS/Claude Helper --type=utility"),
            (14, "/Applications/Claude.app/Contents/Helpers/disclaimer",
             "/Applications/Claude.app/Contents/Helpers/disclaimer --pgroup -- /x/claude.app/Contents/MacOS/claude"),
            (15, "/Library/Application Support/Claude/claude-code/2.1.299/4fa9/claude.app/Contents/MacOS/claude",
             "/Library/Application Support/Claude/claude-code/2.1.299/4fa9/claude.app/Contents/MacOS/claude --output-format stream-json"),
            (16, "/opt/claude/versions/2.1.299", "claude --continue"),
            (17, "/usr/local/bin/node", "node /usr/local/lib/node_modules/@anthropic-ai/claude-code/cli.js"),
            (18, "/usr/bin/python3", "python3 tools/install-claude.py --activate v1"),
        ]
        chk("claude_processes names the desktop runtime, the versioned CLI binary, the symlinked CLI and "
            "the npm entry point, and not the Electron shell, its helpers or the disclaimer wrapper",
            [pid for pid, _exe in claude_processes(ps_rows=rows)] == [15, 16, 17]
            and claude_processes(ps_rows=[(16, "/opt/homebrew/bin/claude", "claude")]) == [
                (16, "/opt/homebrew/bin/claude")])
        chk("claude_processes on an empty table is an empty list, not unknown",
            claude_processes(ps_rows=[]) == [])
        chk("claude_processes reads the live table without raising",
            isinstance(claude_processes(), (list, type(None))))
        two = lambda: [(15, "/x/claude.app/Contents/MacOS/claude"), (16, "/y/claude")]
        chk("--require-quiescent refuses while Claude Code processes run, naming their pids",
            raises(lambda: real_activate(home, "v1", processes=two, require_quiescent=True),
                   "refusing to activate (--require-quiescent): 2 Claude Code process(es) running (pids 15, 16)"))
        chk("--require-quiescent refuses when the process table cannot be read",
            raises(lambda: real_activate(home, "v1", processes=lambda: None, require_quiescent=True),
                   "cannot list processes"))
        lines = []
        real_activate(home, "v1", processes=two, log=lines.append)
        chk("without the flag the same list proceeds and prints the residual with the pids",
            wired(home) == {"v1": 2, "v2": 0}
            and any(line.startswith("2 Claude Code process(es) running (pids 15, 16): ")
                    and "between the installer's final stat and its rename" in line for line in lines))
        lines = []
        real_activate(home, "v1", processes=lambda: [], log=lines.append)
        chk("with no process running nothing is reported", not any("process" in line for line in lines))
        buf = io.StringIO()
        chk("--check names the residual when a Claude Code process is running, and stays clean",
            check(home, source, out=buf, processes=two) == 0
            and "residual: 2 Claude Code process(es) running (pids 15, 16)" in buf.getvalue())
        buf = io.StringIO()
        chk("--check says when the process table cannot be read",
            check(home, source, out=buf, processes=lambda: None) == 0
            and "processes: cannot list" in buf.getvalue())
        chk("review reproduction 4294811773 (known residual, not covered): a write landing between "
            "the final stat and the rename is lost; the assertion is the reviewer's, unchanged",
            reproduction(4294811773, "activation= v1 writer_completed= True app_update= None"))

        # --- a concurrent writer between the read and the replace
        seen = []

        def concurrent_write(attempt):
            seen.append(attempt)
            if attempt == 0:
                current = load_json(settings_path)
                current["appManaged"] = "written-by-the-app"
                atomic_write(settings_path, (json.dumps(current, indent=2) + "\n").encode("utf-8"))

        activate(home, "v2", between_read_and_replace=concurrent_write)
        final = load_json(settings_path)
        chk("a concurrent settings write between read and replace forces a re-read and retry",
            seen == [0, 1] and final.get("appManaged") == "written-by-the-app"
            and any("harness/v2/" in h.get("command", "") for _e, _m, h in registered_handlers(final)))
        chk("a writer that never stops is a failed activation, not a clobber",
            raises(lambda: activate(home, "v1", between_read_and_replace=lambda a: atomic_write(
                settings_path, (json.dumps(dict(load_json(settings_path), tick=a), indent=2) + "\n").encode("utf-8")),
                attempts=3), "changed under every one of 3"))

        def corrupt_after_replace():
            current = load_json(settings_path)
            current["hooks"]["Stop"] = []
            atomic_write(settings_path, (json.dumps(current, indent=2) + "\n").encode("utf-8"))

        chk("a post-write mismatch is reported as a failed activation, never assumed",
            raises(lambda: activate(home, "v1", after_replace=corrupt_after_replace),
                   "post-write verification failed"))
        activate(home, "v1")

        # --- check
        buf = io.StringIO()
        chk("--check passes on a freshly activated tree", check(home, source, out=buf) == 0)
        with open(os.path.join(tree, "tools", "tool.py"), "a") as fh:
            fh.write("# drift\n")
        buf = io.StringIO()
        chk("--check names a changed file in the active tree",
            check(home, source, out=buf) == 1 and "DRIFT changed tools/tool.py" in buf.getvalue())
        open(os.path.join(tree, "tools", "tool.py"), "w").write("VALUE = 1\n")
        open(os.path.join(home, ".claude", "CLAUDE.md"), "a").write("hand edit\n")
        buf = io.StringIO()
        chk("--check names an instruction file that differs from the generated copy",
            check(home, source, out=buf) == 1 and "CLAUDE.md differs" in buf.getvalue())
        activate(home, "v1")
        open(os.path.join(source, "CLAUDE.md"), "a").write("\nA new adapter paragraph.\n")
        buf = io.StringIO()
        chk("--check names a source that moved since the tree was staged",
            check(home, source, out=buf) == 1 and "source moved" in buf.getvalue())
        shutil.copyfile(os.path.join(ROOT, "CLAUDE.md"), os.path.join(source, "CLAUDE.md"))
        current = load_json(settings_path)
        current["hooks"]["Stop"] = []
        atomic_write(settings_path, (json.dumps(current, indent=2) + "\n").encode("utf-8"))
        buf = io.StringIO()
        chk("--check names an owned hook missing from settings",
            check(home, source, out=buf) == 1 and "owned hook Stop" in buf.getvalue())
        activate(home, "v1")
        current = load_json(settings_path)
        current["hooks"]["Stop"].append({"hooks": [{"type": "command",
                                                    "command": "python3 ~/.claude/hooks/stop_guard.py",
                                                    "timeout": 5}]})
        atomic_write(settings_path, (json.dumps(current, indent=2) + "\n").encode("utf-8"))
        buf = io.StringIO()
        check(home, source, out=buf)
        chk("--check reports a hand-registered harness handler as unowned instead of adopting it",
            "unowned harness handler: Stop 'python3 ~/.claude/hooks/stop_guard.py'" in buf.getvalue())

        legacy_home = os.path.join(td, "legacy-home")
        os.makedirs(os.path.join(legacy_home, ".claude"))
        json.dump(source_settings, open(os.path.join(legacy_home, ".claude", "settings.json"), "w"))
        open(os.path.join(legacy_home, ".claude", "CLAUDE.md"), "w").write("hand-made\n")
        buf = io.StringIO()
        chk("--check on a hand-made install reports no receipt and the unowned handlers, exit 1",
            check(legacy_home, source, out=buf) == 1 and "hand-made install" in buf.getvalue()
            and "unowned harness handler: Stop" in buf.getvalue()
            and "differs from the generator" in buf.getvalue())

    # --- the target tree is verified at the commit fence (review thread 4298561334): a staged
    # tree edited after staging, or missing its instruction file, is refused before any write;
    # a damaged ACTIVE tree never blocks switching to a healthy target
    with tempfile.TemporaryDirectory() as td:
        source = os.path.join(td, "source")
        os.makedirs(os.path.join(source, "hooks"))
        os.makedirs(os.path.join(source, "tools"))
        for name in ("AGENTS.md", "CLAUDE.md"):
            shutil.copyfile(os.path.join(ROOT, name), os.path.join(source, name))
        open(os.path.join(source, "hooks", "a.py"), "w").write("print('ok')\n")
        json.dump({"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
            {"type": "command", "command": "python3 ~/.claude/hooks/a.py", "timeout": 5}]}]}},
                  open(os.path.join(source, "settings.json"), "w"))
        home = os.path.join(td, "home")
        os.makedirs(os.path.join(home, ".claude"))
        for version in ("v1", "v2"):
            stage(source, home, version_id=version)
        activate(home, "v1")
        settings_path = os.path.join(home, ".claude", "settings.json")
        marker_path = pending_marker_path(home)
        target = tree_path(home, "v2")
        damaged = os.path.join(target, "hooks", "a.py")
        pristine = read_text(damaged)
        generated = os.path.join(target, "CLAUDE.generated.md")
        generated_bytes = open(generated, "rb").read()
        receipt_v2 = load_receipt(os.path.join(target, RECEIPT_NAME))
        chk("tree_problems on a staged tree that matches its receipt reports nothing",
            tree_problems(target, receipt_v2) == ([], []))
        open(damaged, "w").write('raise RuntimeError("damaged staged hook")\n')
        before = open(settings_path, "rb").read()
        chk("tree_problems names a changed file of a staged tree against its receipt",
            tree_problems(target, receipt_v2) == (["changed hooks/a.py"], []))
        chk("--activate refuses a target whose file no longer matches its receipt, naming the file",
            raises(lambda: activate(home, "v2"),
                   "refusing to activate v2: the staged tree does not match its receipt: "
                   "changed hooks/a.py"))
        chk("the refused switch wrote nothing: settings unchanged, no marker, --check 0 on v1",
            open(settings_path, "rb").read() == before and not os.path.exists(marker_path)
            and check(home, source, out=io.StringIO()) == 0)
        open(damaged, "w").write(pristine)

        def damage_on_first_attempt(attempt):
            if attempt == 0:
                open(damaged, "w").write('raise RuntimeError("edited during the switch")\n')
        chk("the target is judged on every attempt: a file edited after the activation began is refused",
            raises(lambda: activate(home, "v2", between_read_and_replace=damage_on_first_attempt),
                   "changed hooks/a.py")
            and open(settings_path, "rb").read() == before and not os.path.exists(marker_path)
            and not [n for n in os.listdir(os.path.dirname(settings_path)) if n.startswith(".settings-")])
        open(damaged, "w").write(pristine)
        original_sha256 = globals()["sha256_file"]
        fired = []

        def sha256_then_write(path):
            # A writer that lands while the target is being hashed, after the attempt read
            # the settings state: the stat guard must still see it.
            if not fired and path.startswith(target):
                fired.append(path)
                current = load_json(settings_path)
                current["writerKey"] = "during validation"
                atomic_write(settings_path, (json.dumps(current, indent=2) + "\n").encode("utf-8"))
            return original_sha256(path)
        globals()["sha256_file"] = sha256_then_write
        try:
            activate(home, "v2")
        finally:
            globals()["sha256_file"] = original_sha256
        chk("a settings write that lands during target validation is seen by the stat guard, retried and kept",
            bool(fired) and load_json(settings_path).get("writerKey") == "during validation"
            and installation_state(home)["active"]["version"] == "v2")
        activate(home, "v1")
        before = open(settings_path, "rb").read()
        planted = os.path.join(target, "hooks", "extra.py")
        open(planted, "w").write("X = 1\n")
        chk("a file under the tree that the receipt does not list is refused as unreceipted",
            tree_problems(target, receipt_v2) == (["unreceipted hooks/extra.py"], [])
            and raises(lambda: activate(home, "v2"), "does not match its receipt: unreceipted hooks/extra.py"))
        os.remove(planted)
        os.remove(generated)
        chk("--activate refuses a target whose instruction file is missing, before any write",
            raises(lambda: activate(home, "v2"), "does not match its receipt: missing CLAUDE.generated.md")
            and open(settings_path, "rb").read() == before and not os.path.exists(marker_path)
            and installation_state(home)["wired_versions"] == {"v1"}
            and installation_state(home)["pending"] is None)
        open(generated, "wb").write(generated_bytes)
        activate(home, "v2")
        chk("the repaired target activates", installation_state(home)["active"]["version"] == "v2")
        open(damaged, "w").write('raise RuntimeError("damaged active hook")\n')
        buf = io.StringIO()
        chk("--check names the damaged active tree's file as DRIFT through the same validator",
            check(home, source, out=buf) == 1 and "DRIFT changed hooks/a.py" in buf.getvalue())
        activate(home, "v1")
        chk("a damaged active tree does not block switching to a healthy target; --check is then 0",
            installation_state(home)["active"]["version"] == "v1" and check(home, source, out=io.StringIO()) == 0)
        open(damaged, "w").write(pristine)
        chk("an instruction file that vanishes after the switch is an InstallError naming the stage",
            raises(lambda: activate(home, "v2", after_replace=lambda: os.remove(generated)),
                   "stopped after the switch"))
        buf = io.StringIO()
        check(home, source, out=buf)
        chk("--check then names the activation interrupted after the switch, marker in place",
            os.path.exists(marker_path) and "activation of v2 interrupted after the switch" in buf.getvalue())
        open(generated, "wb").write(generated_bytes)
        activate(home, "v2")
        chk("the interrupted switch completes once the instruction file is back",
            not os.path.exists(marker_path) and check(home, source, out=io.StringIO()) == 0)
        open(generated, "wb").write(b"\xff\xfe not utf-8\n")
        buf = io.StringIO()
        chk("a generated instruction file that is not UTF-8 is a drift line of the active tree, not a crash, and "
            "does not block switching to a healthy target",
            check(home, source, out=buf) == 1 and "instruction file unreadable" in buf.getvalue()
            and activate(home, "v1")["version"] == "v1")
        open(generated, "wb").write(generated_bytes)
        activate(home, "v2")
        chk("review reproduction 4298561334: a changed or missing target file is refused before any write",
            reproduction(4298561334, "damaged target: activation_exit= 1 check_exit= 0 hook_exit= 1 "
                                     "settings_changed= False"))

    print(f"\n  selftest: {bad} failure(s)")
    print(f"SELFTEST-SUMMARY suite=install-claude checks={checks} failures={bad}")
    return 1 if bad else 0


# ---- main ----------------------------------------------------------------------
def main(argv):
    args = list(argv[1:])
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0 if args else 2
    mode = args.pop(0)
    if mode == "--version":
        print(f"install-claude {VERSION}")
        return 0
    if mode == "--selftest":
        return selftest()
    options = {"--home": os.path.expanduser("~"), "--source": ROOT, "--tree": TEMPLATE_TREE,
               "--commit": TEMPLATE_COMMIT, "--version-id": None}
    flags = {"--allow-dirty": False, "--remove-orphans": False, "--require-quiescent": False}
    positional = []
    while args:
        item = args.pop(0)
        if item in options:
            if not args:
                sys.stderr.write(f"{item} needs a value\n")
                return 2
            options[item] = args.pop(0)
        elif item in flags:
            flags[item] = True
        elif item.startswith("-"):
            sys.stderr.write(f"unknown argument: {item!r}\nrun --help\n")
            return 2
        else:
            positional.append(item)
    try:
        if mode == "--render":
            sys.stdout.write(render_instruction_file(options["--source"], tree=options["--tree"],
                                                     commit=options["--commit"]))
            return 0
        if mode == "--stage":
            receipt = stage(options["--source"], options["--home"],
                            version_id=options["--version-id"], allow_dirty=flags["--allow-dirty"])
            print(f"staged {receipt['tree']} ({len(receipt['files'])} files, "
                  f"{len(receipt['owned_hooks'])} owned hook entries); not active until --activate")
            return 0
        if mode == "--activate":
            if len(positional) != 1:
                sys.stderr.write("--activate takes exactly one version id\n")
                return 2
            active = activate(options["--home"], positional[0],
                              remove_orphans=flags["--remove-orphans"], log=print,
                              require_quiescent=flags["--require-quiescent"])
            print(f"activated {active['tree']} at {active['activated_at']}")
            return 0
        if mode == "--check":
            return check(options["--home"], options["--source"])
    except InstallError as exc:
        print(f"INSTALL-ERROR {exc}")
        return 1
    sys.stderr.write(f"unknown argument: {mode!r}\nrun --help\n")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
