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

Why the switch is the settings file and not a directory rename: a directory cannot be renamed
over an existing non-empty directory, so a two-rename swap leaves a window with no hook script
at the registered path. Each version keeps its own tree and the registered commands point at
it; rollback is the same replace pointing back.

Why read-merge-replace-verify: the desktop app writes settings.json itself (app-managed keys),
so the file is read immediately before writing, only receipt-owned entries are replaced in that
content, the write is an atomic replace guarded by a stat comparison (a concurrent change
between the read and the replace discards the merge and retries), and the result is re-read; a
mismatch after the write is a failed activation, never an assumed success.

Ownership is by exact identity: an entry is owned when its (event, matcher, type, command,
timeout) tuple is listed in a receipt. User-added hooks, even ones stored under
$HOME/.claude/hooks/, `permissions.defaultMode`, and every other key are never touched.
A hand-made install (no receipt) is reported by --check, not adopted.

The generated instruction file is the shared policy (AGENTS.md) followed by the Claude adapter
section of CLAUDE.md, with the adapter's `~/.claude/hooks/` and `~/.claude/tools/` paths
templated to the active tree. --render prints it with placeholder tree and commit so its size
is stable for the budget ceiling; the installer renders it with the real values.

  install-claude.py --render [--source DIR] [--tree PATH] [--commit SHA]
  install-claude.py --stage [--home DIR] [--source DIR] [--version-id ID] [--allow-dirty]
  install-claude.py --activate ID [--home DIR]
  install-claude.py --check [--home DIR] [--source DIR]
  install-claude.py --selftest

Nothing here touches $HOME unless --stage or --activate names it; --check and --render only read.
Exit codes: 0 ok · 1 drift, failed stage or activation, or selftest failure · 2 usage error.
"""
import compileall
import contextlib
import copy
import datetime
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

VERSION = "1.0.0"
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
RECEIPT_SCHEMA_VERSION = 1
# A flag token is an option or a bare word; a shell operator such as `||` or `;` is not a
# flag, so a wrapped or masked command never matches and is refused as unowned.
OWNED_COMMAND = re.compile(
    r"^python3 ~/\.claude/hooks/([A-Za-z0-9_./-]+\.py)((?: --?[A-Za-z0-9][A-Za-z0-9_-]*)*)$")
HANDLER_IDENTITY_KEYS = ("type", "command", "timeout")


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


def handler_identity(handler):
    return tuple(handler.get(key) for key in HANDLER_IDENTITY_KEYS)


def merge_hooks(settings, remove, add):
    """-> a deep copy of `settings` with `remove` identities dropped and `add` handlers present.

    `remove` is a set of (type, command, timeout) identities; `add` is the owned list. Entries
    left with no handlers are dropped; a new handler joins the entry with the same matcher or
    opens one. Nothing outside the hooks block is read or written.
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
                if not (isinstance(handler, dict) and handler_identity(handler) in remove)
            ]
            if entry["hooks"]:
                kept_entries.append(entry)
        if kept_entries:
            hooks[event] = kept_entries
        else:
            del hooks[event]
    for owned in add:
        handler = {key: owned[key] for key in HANDLER_IDENTITY_KEYS}
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


# ---- activate ------------------------------------------------------------------
def _settings_state(path):
    try:
        st = os.stat(path)
    except FileNotFoundError:
        return None
    return (st.st_ino, st.st_size, st.st_mtime_ns)


def activate(home, version_id, fault=None, between_read_and_replace=None, after_replace=None,
             attempts=5):
    """Switch $HOME/.claude/settings.json to the tree's owned hooks in one atomic replace.

    `fault="before-replace"` abandons the activation after the merged file is written beside
    settings.json and before the replace, which is the window an interrupted upgrade leaves;
    the previous tree must stay active. `between_read_and_replace` and `after_replace` are
    selftest seams for a concurrent writer and for a post-write mismatch.
    """
    tree = tree_path(home, version_id)
    receipt_path = os.path.join(tree, RECEIPT_NAME)
    try:
        receipt = load_json(receipt_path)
    except (OSError, ValueError) as exc:
        raise InstallError(f"no usable receipt at {receipt_path}: {exc}")
    owned = receipt.get("owned_hooks")
    if not isinstance(owned, list) or not owned:
        raise InstallError("receipt owns no hook entries")
    previous = {}
    previous_path = active_receipt_path(home)
    if os.path.isfile(previous_path):
        try:
            previous = load_json(previous_path)
        except (OSError, ValueError) as exc:
            raise InstallError(f"active receipt unreadable: {exc}")
    remove = {handler_identity(h) for h in previous.get("owned_hooks", []) if isinstance(h, dict)}
    remove |= {handler_identity(h) for h in owned}
    settings_path = os.path.join(claude_home(home), "settings.json")
    os.makedirs(os.path.dirname(settings_path), exist_ok=True)
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
                if event == h["event"] and matcher == h["matcher"]
                and handler_identity(handler) == handler_identity(h)]
        if len(hits) != 1:
            problems.append(f"{h['event']} {h['command']!r}: {len(hits)} match(es), expected 1")
    stale = remove - {handler_identity(h) for h in owned}
    for event, _matcher, handler in found:
        if handler_identity(handler) in stale:
            problems.append(f"{event} {handler.get('command')!r}: previous owned entry still present")
    if problems:
        raise InstallError("post-write verification failed: " + "; ".join(problems))
    with open(os.path.join(tree, "CLAUDE.generated.md"), "rb") as fh:
        atomic_write(os.path.join(claude_home(home), "CLAUDE.md"), fh.read())
    active = dict(receipt)
    active["activated_at"] = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")
    atomic_write(previous_path, (json.dumps(active, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    return active


# ---- check ---------------------------------------------------------------------
def harness_scripts(source_root):
    names = set()
    hooks_dir = os.path.join(source_root, "hooks")
    if os.path.isdir(hooks_dir):
        names = {name for name in os.listdir(hooks_dir) if name.endswith(".py")}
    return names


def check(home, source_root, out=sys.stdout):
    """-> 0 when the active install matches its receipt and the generator; 1 on any drift."""
    p = lambda *a: print(*a, file=out)
    drift = []
    settings_path = os.path.join(claude_home(home), "settings.json")
    installed_md = os.path.join(claude_home(home), "CLAUDE.md")
    try:
        settings = load_json(settings_path)
    except (OSError, ValueError):
        settings = {}
    scripts = harness_scripts(source_root)
    receipt_path = active_receipt_path(home)
    if not os.path.isfile(receipt_path):
        p(f"  no install receipt at {receipt_path}: hand-made install, nothing is owned")
        sha, _dirty = source_commit(source_root)
        expected = render_instruction_file(source_root, tree="~/.claude", commit=sha or TEMPLATE_COMMIT)
        try:
            actual = read_text(installed_md)
        except OSError:
            actual = None
        if actual is None:
            p("  CLAUDE.md: absent")
        else:
            differing = sum(1 for a, b in zip(actual.splitlines(), expected.splitlines()) if a != b)
            differing += abs(len(actual.splitlines()) - len(expected.splitlines()))
            p(f"  CLAUDE.md: {'equals' if actual == expected else 'differs from'} the generator's "
              f"output for the legacy ~/.claude layout ({differing} differing line(s))")
        for event, _matcher, handler in registered_handlers(settings):
            command = handler.get("command", "")
            if any(f"/hooks/{name}" in command for name in scripts):
                p(f"  unowned harness handler: {event} {command!r}")
        drift.append("no receipt")
        p(f"INSTALL-CHECK-SUMMARY receipt=absent drift={len(drift)} exit=1")
        return 1
    receipt = load_json(receipt_path)
    tree = expand_display(home, receipt["tree"])
    p(f"  active tree {receipt['tree']} version={receipt['version']} "
      f"source_commit={receipt.get('source_commit')}")
    for relative, record in sorted(receipt.get("files", {}).items()):
        full = os.path.join(tree, relative)
        if not os.path.isfile(full):
            drift.append(f"missing {relative}")
        elif sha256_file(full) != record["sha256"]:
            drift.append(f"changed {relative}")
    generated = os.path.join(tree, "CLAUDE.generated.md")
    try:
        tree_copy = read_text(generated)
        installed = read_text(installed_md)
    except OSError as exc:
        tree_copy, installed = None, None
        drift.append(f"instruction file unreadable: {exc}")
    if tree_copy is not None and installed != tree_copy:
        drift.append("CLAUDE.md differs from the active tree's generated copy")
    expected = render_instruction_file(source_root, tree=receipt["tree"],
                                       commit=receipt.get("source_commit") or TEMPLATE_COMMIT)
    if tree_copy is not None and expected != tree_copy:
        drift.append("generator output from the current source differs from the active tree; "
                     "the source moved since this tree was staged")
    found = registered_handlers(settings)
    for h in receipt.get("owned_hooks", []):
        hits = [1 for event, matcher, handler in found
                if event == h["event"] and matcher == h["matcher"]
                and handler_identity(handler) == handler_identity(h)]
        if len(hits) != 1:
            drift.append(f"owned hook {h['event']} {h['command']!r}: {len(hits)} match(es)")
    owned_identities = {handler_identity(h) for h in receipt.get("owned_hooks", [])}
    for event, _matcher, handler in found:
        command = handler.get("command", "")
        if handler_identity(handler) not in owned_identities and any(
                f"/hooks/{name}" in command for name in scripts):
            p(f"  unowned harness handler: {event} {command!r}")
    for item in drift:
        p(f"  DRIFT {item}")
    code = 1 if drift else 0
    p(f"INSTALL-CHECK-SUMMARY receipt=present files={len(receipt.get('files', {}))} "
      f"drift={len(drift)} exit={code}")
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
    flags = {"--allow-dirty": False}
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
            active = activate(options["--home"], positional[0])
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
