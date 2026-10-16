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
import types

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
    if not isinstance(marker.get("started_at"), str) or not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", marker["started_at"]):
        problems.append("started_at must be a UTC timestamp like 2026-01-01T00:00:00Z")
    return problems


# ---- stage ---------------------------------------------------------------------
def tree_file_digests(tree):
    digests = {}
    for dirpath, dirs, files in os.walk(tree):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        for name in sorted(files):
            if name == RECEIPT_NAME or name.endswith(".pyc"):
                continue
            full = os.path.join(dirpath, name)
            relative = os.path.relpath(full, tree).replace(os.sep, "/")
            digests[relative] = {"sha256": sha256_file(full), "bytes": os.path.getsize(full)}
    return digests


def stage(source_root, home, version_id=None, allow_dirty=False, now=None):
    """Stage one complete tree under $HOME/.claude/harness/<version>; -> the receipt."""
    sha, dirty = source_commit(source_root)
    if version_id is None:
        version_id, sha, dirty = derive_version_id(source_root, allow_dirty)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9+._-]*", version_id):
        raise InstallError(f"version id {version_id!r} is not a safe directory name")
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


def script_operand(comm, args):
    """-> the script an interpreter process executes: the first non-flag argument after
    the executable, which ps reports in `comm` so a path with spaces is removed whole."""
    rest = args[len(comm):] if args.startswith(comm) else args.split(" ", 1)[1] if " " in args else ""
    for token in rest.split():
        if not token.startswith("-"):
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
        for relative, record in sorted(active.get("files", {}).items()):
            full = os.path.join(tree, relative)
            if not os.path.isfile(full):
                state["drift"].append(f"missing {relative}")
            elif sha256_file(full) != record["sha256"]:
                state["drift"].append(f"changed {relative}")
        try:
            tree_copy = read_text(os.path.join(tree, "CLAUDE.generated.md"))
        except OSError as exc:
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
    the active receipt; write the pending marker; read-merge-replace settings.json under the
    stat guard with retries; verify the written file; install CLAUDE.md; write the active
    receipt; clear the marker. A stop anywhere after the marker is written leaves it in
    place, --check names the stage, and the next --activate of any version completes a
    consistent switch because the removal set covers every version.

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
    with open(os.path.join(tree, "CLAUDE.generated.md"), "rb") as fh:
        atomic_write(os.path.join(claude_home(home), "CLAUDE.md"), fh.read())
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

    def private_copy(old, new):
        """-> a private copy of this module with one planted defect, executed in memory."""
        source_text = read_text(__file__)
        if source_text.count(old) != 1:
            raise AssertionError(f"mutation site occurs {source_text.count(old)} time(s)")
        module = types.ModuleType("install_claude_mutant")
        module.__file__ = __file__
        exec(compile(source_text.replace(old, new), __file__, "exec"), module.__dict__)
        return module

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
        no_marker = private_copy('            atomic_write(marker_path, (json.dumps(marker, indent=2, sort_keys=True) + "\\n").encode("utf-8"))\n', "")
        no_marker_home = os.path.join(td, "no-marker-home")
        os.makedirs(os.path.join(no_marker_home, ".claude"))
        json.dump(user_settings, open(os.path.join(no_marker_home, ".claude", "settings.json"), "w"))
        no_marker.stage(source, no_marker_home, version_id="v1")
        no_marker.stage(source, no_marker_home, version_id="v2")
        no_marker.activate(no_marker_home, "v1", processes=lambda: [])
        try:
            no_marker.activate(no_marker_home, "v2", after_replace=stop, processes=lambda: [])
        except Stopped:
            pass
        chk("mutation: without the marker write, a post-replace stop leaves no marker, the state the "
            "stage-naming proofs reject",
            not os.path.exists(no_marker.pending_marker_path(no_marker_home)))

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

        chk("review reproduction 4294811755: a switch killed after its settings replace rolls back "
            "to exactly v1's entries",
            reproduction(4294811755, "hooks= {'v1': 4, 'v2': 0}"))

        # --- mutation proof on a private copy of this module: with the removal set built from
        # the active receipt only, the post-switch stop leaves both versions wired, the state
        # the rollback proof above rejects
        mutant = private_copy('    for staged in state["trees"].values():\n'
                              '        remove |= _owned_set(staged)\n', "")
        mutant_home = os.path.join(td, "mutant-home")
        os.makedirs(os.path.join(mutant_home, ".claude"))
        json.dump(user_settings, open(os.path.join(mutant_home, ".claude", "settings.json"), "w"))
        mutant.stage(source, mutant_home, version_id="v1")
        mutant.stage(source, mutant_home, version_id="v2")
        mutant.activate(mutant_home, "v1", processes=lambda: [])
        try:
            mutant.activate(mutant_home, "v2", after_replace=stop, processes=lambda: [])
        except Stopped:
            pass
        mutant.activate(mutant_home, "v1", processes=lambda: [])
        chk("mutation: removal from the active receipt only leaves both versions wired after a "
            "post-switch stop, which the rollback proof rejects",
            wired(mutant_home) == {"v1": 2, "v2": 2})

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
