#!/usr/bin/env python3
"""harness_check — the mechanical gate for this harness's authored surface.

Runs from either clone (repo root auto-detected from this file's location). Checks:

  C1  guard/report/accounting selftests exit 0 and emit a complete terminal receipt
  C2  shared-corpus reference copies are byte-identical across skills, and any
      basename appearing in >=2 skills is either SHARED or explicitly PER_SKILL —
      an unknown multi-skill basename fails loud
  C3  reference resolution, both directions: every references/ path a SKILL.md
      names exists; every file under references/ is named by its SKILL.md,
      literally or via a <param> template family
  C4  every description <= 400 chars (house cap inside the 1024 spec ceiling)
  C5  method-skill bodies <= 5,000 chars after frontmatter; authoring-skill
      bodies <= 500 lines
  C6  stale-claim tripwires: patterns that once shipped false stay at zero in
      live channels (skills/, hooks/, tools/, AGENTS.md, CLAUDE.md)
  C7  anchors: routing-table skills exist; Claude and Codex hook commands resolve;
      [local] original audit paths exist, `timeout` still absent, askq binary
      anchors hold
  C8  reserved context basenames (CLAUDE.md/AGENTS.md/GEMINI.md) exist nowhere
      but the repo root
  C9  Codex package contract: manifest, marketplace, hook config, context bridges,
      and their size budgets are internally consistent
  C10 PR delivery contract: scoped publication authority, state-proof command,
      and the ban on conflating local commits with the GitHub PR remain present

Exit codes: 0 all checks pass · 1 one or more checks failed · 2 usage error or
zero inputs (an empty scan set is an error, never a clean verdict).

  harness_check.py             run every check (local mode)
  harness_check.py --ci        skip [local]-tagged checks (no ~/.claude, no
                               claude binary, no launchd on the runner)
  harness_check.py --selftest  prove each check can go RED on a planted-defect
                               tree, then exit
"""
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile

VERSION = "2.5.0"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

METHOD_SKILLS = ["git-workflow", "pr-review-method", "testing-ci", "agent-dispatch",
                 "outbound-drafts", "system-design", "prebid-adcp"]
AUTHORING_SKILLS = ["craft-prompt", "craft-skill", "craft-context-file", "review-prompt"]
BODY_CHAR_CAP = 5000          # chars after frontmatter — the builders' instrument
BODY_LINE_CAP = 500           # authoring skills (spec cap)
DESC_CAP = 400                # house cap (spec ceiling is 1024)

# C2: basenames shared verbatim across skills. A same-basename file NOT listed in
# either set is a loud failure — decide SHARED vs PER_SKILL and add it here.
SHARED_BASENAMES = {
    "anti-patterns.md", "skill-authoring.md", "description-archetypes.md",
    "untrusted-content.md", "uncertainty.md", "scope-discipline.md",
    "persistence.md", "action-default.md", "context-file.md",
    "claude-code.md", "codex.md",
    "stance-explore.md", "stance-implement.md", "stance-operate.md",
    "stance-plan.md", "stance-review.md",
    "model-claude.md", "model-gemini.md", "model-gpt.md", "model-neutral.md",
}
PER_SKILL_BASENAMES = {"deferred.md"}   # same name, deliberately different content

# C6: each of these shipped false at least once. The live channels stay at zero.
# (This file is excluded from its own sweep.)
STALE_PATTERNS = [
    "NOT INSTALLED",            # guards claimed dormant while live
    "NOT applied",              # applied proposals claiming to be pending
    "not in the live file yet", # delivered rule claiming undelivered
    "all 24 rows",              # catalog count drift
    "description >1024",        # row-16 cap drift
    "72 further rank-A",        # deferred-count drift
    "(like this one)",          # birth-repo deictic
    "ph-mcp-server",            # birth-repo tooling
    "docs/research/",           # birth-repo paths
    "claude-md-lines",          # retired reference
    "ph-lint",                  # linter that never existed here
    "Each push is its own action needing its own confirmation",  # retired consent loop
    "committed to the PR",      # local commit falsely described as published
]

ROUTING_SKILLS = ["git-workflow", "pr-review-method", "testing-ci", "agent-dispatch",
                  "prebid-adcp", "system-design", "outbound-drafts",
                  "craft-prompt", "craft-skill", "craft-context-file", "review-prompt"]

RESERVED_BASENAMES = {"claude.md", "agents.md", "gemini.md"}
CODEX_HOOK_TOP_LEVEL_KEYS = {"description", "hooks"}
CODEX_VALID_HOOK_EVENTS = {
    "PreToolUse", "PermissionRequest", "PostToolUse", "PreCompact", "PostCompact",
    "SessionStart", "SubagentStart", "SubagentStop",
    "UserPromptSubmit", "Stop",
}
CODEX_REQUIRED_PACKAGE_EVENTS = {"SessionStart", "SubagentStart", "PreToolUse"}
CODEX_HOOK_ENTRY_KEYS = {"matcher", "hooks", "enabled", "trusted_hash"}
CODEX_HOOK_HANDLER_KEYS = {
    "type", "command", "commandWindows", "timeout", "async", "statusMessage",
    "additionalContextLimit",
}
REQUIRED_CODEX_HANDLERS = [
    ("SessionStart", "startup|resume|clear|compact", "hooks/codex_session_start.py", ()),
    ("SubagentStart", None, "hooks/codex_session_start.py", ()),
    ("PreToolUse", "^Bash$", "hooks/bash_command_guard.py", ("--runtime", "codex")),
    ("PreToolUse", "^Agent$", "hooks/spawn_preflight_guard.py", ("--runtime", "codex")),
]
DELIVERY_CONTRACT = {
    "AGENTS.md": [
        "A request to create or open a PR authorizes",
        "A request to update, fix, address, or get an",
        '"commit only" or "do not push" overrides that authority.',
        "pr-delivery-state.py --pr <number> --repo <owner/repo>",
    ],
    "skills/git-workflow/SKILL.md": [
        "A local commit is not on a PR.",
        "tools/pr-delivery-state.py --pr <n> --repo <owner/repo>",
    ],
    "skills/git-workflow/references/deferred.md": [
        "## scoped PR publication `[body]`",
        '"update/fix/address this PR" and "get this PR green"',
        "corrective pushes needed until exact-head checks pass",
        "A failed check leaves authority active for in-scope",
    ],
}


def body_chars(path):
    t = open(path, encoding="utf-8").read()
    m = re.match(r"^---\n.*?\n---\n", t, re.S)
    return len(t[m.end():]) if m else len(t)


def description_of(path):
    t = open(path, encoding="utf-8").read()
    m = re.search(r"^description: (.+)$", t, re.M)
    return m.group(1) if m else ""


def description_within_cap(path):
    size = len(description_of(path))
    return 0 < size <= DESC_CAP, size


def method_body_within_cap(path):
    size = body_chars(path)
    return size <= BODY_CHAR_CAP, size


def authoring_body_within_cap(path):
    size = len(open(path, encoding="utf-8").read().splitlines())
    return size <= BODY_LINE_CAP, size


def validate_codex_hook_config(hook_config):
    """Return (handler_count, errors) for the Codex hook runtime schema."""
    errors = []
    handler_count = 0
    if not isinstance(hook_config, dict):
        return 0, ["top-level: expected object"]
    for key in sorted(set(hook_config) - CODEX_HOOK_TOP_LEVEL_KEYS):
        errors.append(f"top-level.{key}: unknown")
    if "description" in hook_config and not isinstance(hook_config["description"], str):
        errors.append("description: expected string")
    hook_events = hook_config.get("hooks", {})
    if not isinstance(hook_events, dict):
        return 0, errors + ["hooks: expected object"]
    event_names = set(hook_events)
    for event in sorted(event_names - CODEX_VALID_HOOK_EVENTS):
        errors.append(f"{event}: unsupported event name")
    missing_events = CODEX_REQUIRED_PACKAGE_EVENTS - event_names
    if missing_events:
        errors.append(f"required events missing: {sorted(missing_events)!r}")
    for event, entries_for_event in hook_events.items():
        if not isinstance(entries_for_event, list):
            errors.append(f"{event}: expected list")
            continue
        for entry_index, entry in enumerate(entries_for_event):
            if not isinstance(entry, dict):
                errors.append(f"{event}[{entry_index}]: expected object")
                continue
            prefix = f"{event}[{entry_index}]"
            for key in sorted(set(entry) - CODEX_HOOK_ENTRY_KEYS):
                errors.append(f"{prefix}.{key}: unknown")
            matcher = entry.get("matcher")
            if matcher is not None:
                if not isinstance(matcher, str):
                    errors.append(f"{prefix}.matcher: expected string")
                else:
                    try:
                        re.compile(matcher)
                    except re.error as exc:
                        errors.append(f"{prefix}.matcher: invalid regex ({exc})")
            if "enabled" in entry and not isinstance(entry["enabled"], bool):
                errors.append(f"{prefix}.enabled: expected boolean")
            if "trusted_hash" in entry and (
                    not isinstance(entry["trusted_hash"], str)
                    or not entry["trusted_hash"].strip()):
                errors.append(f"{prefix}.trusted_hash: expected non-empty string")
            handlers = entry.get("hooks", [])
            if not isinstance(handlers, list):
                errors.append(f"{prefix}.hooks: expected list")
                continue
            if not handlers:
                errors.append(f"{prefix}.hooks: empty")
            for handler_index, handler in enumerate(handlers):
                handler_prefix = f"{prefix}.hooks[{handler_index}]"
                if not isinstance(handler, dict):
                    errors.append(f"{handler_prefix}: expected object")
                    continue
                handler_count += 1
                for key in sorted(set(handler) - CODEX_HOOK_HANDLER_KEYS):
                    errors.append(f"{handler_prefix}.{key}: unknown")
                if handler.get("type") != "command":
                    errors.append(f"{handler_prefix}.type: only command handlers execute")
                if not isinstance(handler.get("command"), str) or not handler["command"].strip():
                    errors.append(f"{handler_prefix}.command: expected non-empty string")
                timeout = handler.get("timeout")
                if not isinstance(timeout, int) or isinstance(timeout, bool) or timeout <= 0:
                    errors.append(f"{handler_prefix}.timeout: expected positive integer")
                if handler.get("async", False) is not False:
                    errors.append(f"{handler_prefix}.async: must be absent or false")
                limit = handler.get("additionalContextLimit")
                if limit is not None and (
                        not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0):
                    errors.append(
                        f"{handler_prefix}.additionalContextLimit: expected positive integer"
                    )
    return handler_count, errors


def package_paths(root):
    """Return (surface, paths, error) for source or installed package contents."""
    if os.path.exists(os.path.join(root, ".git")):
        tracked = subprocess.run(
            ["git", "-C", root, "ls-files"], capture_output=True, text=True,
        )
        if tracked.returncode != 0:
            return "source", [], tracked.stderr.strip() or "git ls-files failed"
        return "source", [line for line in tracked.stdout.splitlines() if line], None
    paths = []
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d != ".git"]
        for filename in files:
            paths.append(os.path.relpath(os.path.join(dirpath, filename), root))
    return "installed", paths, None


HOST_PATH_CONTENT = re.compile(
    rb"(?i)(?<![A-Za-z0-9/])(?:/"
    rb"(?:Users|home|Volumes)/[^/\s]+/|[A-Z]:\\\\Users\\\\)"
)


def forbidden_package_path(path):
    """Return whether a package-relative path encodes publisher or host-local data."""
    parts = path.replace(os.sep, "/").split("/")
    for part in parts:
        lower = part.lower()
        slug = lower.replace("_", "-")
        if lower == "projects" or lower.startswith("harness-audit-"):
            return True
        if (slug.startswith(("-users-", "-home-", "-volumes-", "-private-"))
                or "-users-" in slug or "-home-" in slug or "-volumes-" in slug):
            return True
    return False


def forbidden_package_entries(root):
    """Find publisher-only paths and absolute host paths in package text."""
    surface, paths, error = package_paths(root)
    forbidden_paths = []
    forbidden_contents = []
    for path in paths:
        if forbidden_package_path(path):
            forbidden_paths.append(path)
        try:
            data = open(os.path.join(root, path), "rb").read()
        except OSError:
            continue
        if b"\0" not in data and HOST_PATH_CONTENT.search(data):
            forbidden_contents.append(path)
    return surface, forbidden_paths, forbidden_contents, error


class Run:
    def __init__(self, root, ci):
        self.root, self.ci, self.failures, self.checks = root, ci, [], 0

    def result(self, check, ok, detail):
        self.checks += 1
        print(f"  {'PASS' if ok else 'FAIL'} {check:4s} {detail}")
        if not ok:
            self.failures.append((check, detail))

    # ---- C1 ----------------------------------------------------------------
    def c1_selftests(self, suites=None):
        if suites is None:
            suites = [("bash_command_guard", ["hooks/bash_command_guard.py", "--selftest"]),
                      ("askq_timeout_guard", ["hooks/askq_timeout_guard.py", "--selftest"]),
                      ("harness_report", ["hooks/harness_report.py", "--selftest"]),
                      ("cc-cost", ["tools/cc-cost.py", "--selftest"]),
                      ("codex-cost", ["tools/codex-cost.py", "--selftest"]),
                      ("pr-delivery-state", ["tools/pr-delivery-state.py", "--selftest"]),
                      ("codex_session_start", ["hooks/codex_session_start.py", "--selftest"]),
                      ("spawn_preflight_guard", ["hooks/spawn_preflight_guard.py", "--selftest"])]
        for name, cmd in suites:
            try:
                p = subprocess.run(
                    [sys.executable, os.path.join(self.root, cmd[0])] + cmd[1:],
                    capture_output=True, cwd=self.root, timeout=15,
                )
            except subprocess.TimeoutExpired:
                self.result("C1", False, f"selftest {name}: exceeded 15s")
                continue
            receipts = re.findall(
                rb"^SELFTEST-SUMMARY checks=(\d+) failures=(\d+)$", p.stdout, re.M
            )
            receipt_ok = (len(receipts) == 1 and int(receipts[0][0]) > 0
                          and int(receipts[0][1]) == 0)
            detail = f"selftest {name}: exit {p.returncode}; terminal receipts={len(receipts)}"
            if len(receipts) == 1:
                detail += f" checks={int(receipts[0][0])} failures={int(receipts[0][1])}"
            self.result("C1", p.returncode == 0 and receipt_ok, detail)

    # ---- C2 ----------------------------------------------------------------
    def c2_shared_identity(self):
        import hashlib
        by_base = {}
        skills_dir = os.path.join(self.root, "skills")
        for skill in sorted(os.listdir(skills_dir)):
            refdir = os.path.join(skills_dir, skill, "references")
            if not os.path.isdir(refdir):
                continue
            for f in sorted(os.listdir(refdir)):
                p = os.path.join(refdir, f)
                if os.path.isfile(p):
                    by_base.setdefault(f, []).append(p)
        multi = {b: ps for b, ps in by_base.items() if len(ps) > 1}
        for base, paths in sorted(multi.items()):
            if base in PER_SKILL_BASENAMES:
                continue
            if base not in SHARED_BASENAMES:
                self.result("C2", False,
                            f"{base}: in {len(paths)} skills but in neither SHARED nor "
                            f"PER_SKILL — classify it")
                continue
            hs = {hashlib.md5(open(p, 'rb').read()).hexdigest() for p in paths}
            self.result("C2", len(hs) == 1,
                        f"{base}: {len(paths)} copies "
                        f"{'identical' if len(hs) == 1 else 'DIVERGED'}")
        missing = SHARED_BASENAMES - set(by_base)
        if missing:
            self.result("C2", False, f"SHARED basenames absent from tree: {sorted(missing)}")

    # ---- C3 ----------------------------------------------------------------
    def c3_reference_resolution(self):
        skills_dir = os.path.join(self.root, "skills")
        resolved = 0
        for skill in sorted(os.listdir(skills_dir)):
            body_path = os.path.join(skills_dir, skill, "SKILL.md")
            if not os.path.isfile(body_path):
                continue
            body = open(body_path, encoding="utf-8").read()
            refdir = os.path.join(skills_dir, skill, "references")
            cited = set(re.findall(r"references/([\w<>.\-]+\.(?:md|yaml))", body))
            literal = {c for c in cited if "<" not in c}
            template_res = [re.compile("^" + re.sub(r"<[^>]*>", r"[\\w.\\-]+", re.escape(c)) + "$")
                            for c in cited if "<" in c]
            # direction 1: cited -> exists
            for c in sorted(literal):
                p = os.path.join(refdir, c)
                resolved += 1
                self.result("C3", os.path.isfile(p), f"{skill}: cites references/{c}")
            # direction 2: exists -> cited (literal or template family)
            if os.path.isdir(refdir):
                for f in sorted(os.listdir(refdir)):
                    if not os.path.isfile(os.path.join(refdir, f)):
                        continue
                    ok = f in literal or any(t.match(f) for t in template_res)
                    resolved += 1
                    self.result("C3", ok, f"{skill}: references/{f} "
                                          f"{'reachable' if ok else 'NAMED NOWHERE in SKILL.md'}")
        if resolved == 0:
            self.result("C3", False, "zero authored reference relationships")

    # ---- C4 / C5 -----------------------------------------------------------
    def c4_descriptions(self):
        for skill in METHOD_SKILLS + AUTHORING_SKILLS:
            p = os.path.join(self.root, "skills", skill, "SKILL.md")
            ok, n = description_within_cap(p)
            self.result("C4", ok, f"{skill}: description {n} chars (cap {DESC_CAP})")

    def c5_bodies(self):
        for skill in METHOD_SKILLS:
            ok, n = method_body_within_cap(
                os.path.join(self.root, "skills", skill, "SKILL.md")
            )
            self.result("C5", ok,
                        f"{skill}: body {n} chars (cap {BODY_CHAR_CAP})")
        for skill in AUTHORING_SKILLS:
            p = os.path.join(self.root, "skills", skill, "SKILL.md")
            ok, n = authoring_body_within_cap(p)
            self.result("C5", ok, f"{skill}: {n} lines (cap {BODY_LINE_CAP})")

    # ---- C6 ----------------------------------------------------------------
    def c6_stale_patterns(self):
        me = os.path.abspath(__file__)
        targets = []
        for rel in ("skills", "hooks", "tools", "docs", ".codex-plugin", ".agents"):
            for dirpath, _dirs, files in os.walk(os.path.join(self.root, rel)):
                if "__pycache__" in dirpath:
                    continue
                targets += [os.path.join(dirpath, f) for f in files
                            if not f.endswith((".pyc", ".jsonl"))]
        targets += [os.path.join(self.root, name)
                    for name in ("AGENTS.md", "CLAUDE.md", "README.md")
                    if os.path.isfile(os.path.join(self.root, name))]
        targets = [t for t in targets if os.path.abspath(t) != me]
        if not targets:
            print("  FATAL C6: zero files in scan set")
            self.failures.append(("C6", "zero files"))
            return
        for pat in STALE_PATTERNS:
            hits = [t for t in targets
                    if pat in open(t, encoding="utf-8", errors="replace").read()]
            self.result("C6", not hits,
                        f"tripwire {pat!r}: {len(hits)} hit(s)"
                        + (f" e.g. {os.path.relpath(hits[0], self.root)}" if hits else ""))

    # ---- C7 ----------------------------------------------------------------
    def c7_anchors(self):
        for skill in ROUTING_SKILLS:
            p = os.path.join(self.root, "skills", skill)
            self.result("C7", os.path.isdir(p), f"routing-table skill exists: {skill}")
        st = json.load(open(os.path.join(self.root, "settings.json")))
        for event, entries in st.get("hooks", {}).items():
            for entry in entries:
                for h in entry.get("hooks", []):
                    cmd = h.get("command", "")
                    m = re.search(r"~/[\w./\-]+\.(?:py|sh)", cmd)
                    if not m:
                        continue
                    rel = m.group(0).replace("~/.claude/", "")
                    p = os.path.join(self.root, rel)
                    self.result("C7", os.path.isfile(p), f"settings {event} -> {rel}")
                    self.result("C7", "timeout" in h,
                                f"settings {event} {rel}: timeout set")
        codex_hooks_path = os.path.join(self.root, "hooks", "hooks.json")
        try:
            codex_hooks = json.load(open(codex_hooks_path))
        except Exception as exc:
            self.result("C7", False, f"Codex hooks config parses: {exc}")
            codex_hooks = {}
        inventory = []
        for event, entries in codex_hooks.get("hooks", {}).items():
            for entry in entries:
                for hook in entry.get("hooks", []):
                    command = hook.get("command", "")
                    match = re.search(r"\$\{PLUGIN_ROOT\}/([\w./\-]+\.(?:py|sh))", command)
                    if not match:
                        self.result("C7", False,
                                    f"Codex {event}: command has no PLUGIN_ROOT script anchor")
                        continue
                    rel = match.group(1)
                    try:
                        argv = shlex.split(command)
                    except ValueError:
                        argv = []
                    inventory.append({
                        "event": event,
                        "matcher": entry.get("matcher"),
                        "rel": rel,
                        "argv": argv,
                    })
                    self.result("C7", os.path.isfile(os.path.join(self.root, rel)),
                                f"Codex {event} -> {rel}")
                    self.result("C7", "timeout" in hook,
                                f"Codex {event} {rel}: timeout set")
        for event, matcher, rel, required_args in REQUIRED_CODEX_HANDLERS:
            matches = [item for item in inventory
                       if item["event"] == event and item["matcher"] == matcher
                       and item["rel"] == rel
                       and all(arg in item["argv"] for arg in required_args)]
            self.result("C7", len(matches) == 1,
                        f"required Codex handler {event} matcher={matcher!r} -> {rel} "
                        f"args={list(required_args)!r}: {len(matches)} match(es)")
        if not self.ci:
            fp = os.path.expanduser("~/.claude/harness-audit-20260801/FINDINGS.md")
            self.result("C7", os.path.isfile(fp),
                        "[local] original harness-audit FINDINGS.md exists")
            w = subprocess.run(["which", "timeout"], capture_output=True)
            self.result("C7", w.returncode != 0,
                        "[local] `timeout` still absent (CLAUDE.md authoring host claims it is)")
            v = subprocess.run([sys.executable,
                                os.path.join(self.root, "hooks/askq_timeout_guard.py"),
                                "--verify-harness"], capture_output=True)
            self.result("C7", v.returncode == 0,
                        f"[local] askq --verify-harness: exit {v.returncode}")

    # ---- C8 ----------------------------------------------------------------
    def c8_reserved_basenames(self):
        hits = []
        for dirpath, dirs, files in os.walk(self.root):
            if ".git" in dirpath:
                continue
            for f in files:
                if f.lower() in RESERVED_BASENAMES:
                    p = os.path.join(dirpath, f)
                    if os.path.dirname(os.path.abspath(p)) != os.path.abspath(self.root):
                        hits.append(os.path.relpath(p, self.root))
        self.result("C8", not hits, f"reserved basenames outside root: {hits or 'none'}")

    # ---- C9 ----------------------------------------------------------------
    def c9_codex_package(self):
        manifest_path = os.path.join(self.root, ".codex-plugin", "plugin.json")
        marketplace_path = os.path.join(self.root, ".agents", "plugins", "marketplace.json")
        try:
            manifest = json.load(open(manifest_path))
        except Exception as exc:
            self.result("C9", False, f"plugin manifest parses: {exc}")
            manifest = {}
        plugin_name = manifest.get("name")
        self.result("C9", bool(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*",
                                           str(plugin_name or ""))),
                    f"manifest name is kebab-case: {plugin_name!r}")
        self.result("C9", bool(re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?",
                                           str(manifest.get("version", "")))),
                    f"manifest version is semver: {manifest.get('version')!r}")
        self.result("C9", manifest.get("skills") == "./skills/",
                    "manifest skills path is ./skills/")
        self.result("C9", isinstance(manifest.get("description"), str)
                    and bool(manifest.get("description", "").strip()),
                    "manifest description is a non-empty string")
        author = manifest.get("author")
        self.result("C9", isinstance(author, dict)
                    and isinstance(author.get("name"), str)
                    and bool(author.get("name", "").strip()),
                    "manifest author.name is a non-empty string")
        interface = manifest.get("interface")
        required_interface_strings = {
            "displayName", "shortDescription", "longDescription",
            "developerName", "category", "websiteURL", "brandColor",
        }
        missing_interface = []
        if not isinstance(interface, dict):
            missing_interface.append("interface: expected object")
            interface = {}
        for key in sorted(required_interface_strings):
            if not isinstance(interface.get(key), str) or not interface.get(key, "").strip():
                missing_interface.append(f"interface.{key}: expected non-empty string")
        if not isinstance(interface.get("capabilities"), list) or not all(
                isinstance(item, str) and item for item in interface.get("capabilities", [])):
            missing_interface.append("interface.capabilities: expected string array")
        prompts = interface.get("defaultPrompt")
        if not isinstance(prompts, list) or not 1 <= len(prompts) <= 3 or not all(
                isinstance(item, str) and 0 < len(item) <= 128 for item in prompts or []):
            missing_interface.append("interface.defaultPrompt: expected 1-3 strings <=128 chars")
        self.result("C9", not missing_interface,
                    f"manifest interface contract: {missing_interface or 'complete'}")
        self.result("C9", os.path.isfile(os.path.join(self.root, "hooks", "hooks.json")),
                    "default plugin hook config exists")

        hook_config_path = os.path.join(self.root, "hooks", "hooks.json")
        try:
            hook_config = json.load(open(hook_config_path))
        except Exception as exc:
            self.result("C9", False, f"hook config parses: {exc}")
            hook_config = {}
        handler_count, hook_errors = validate_codex_hook_config(hook_config)
        self.result("C9", handler_count > 0 and not hook_errors,
                    f"Codex hook runtime contract across {handler_count} handler(s): "
                    f"{hook_errors or 'valid'}")

        try:
            marketplace = json.load(open(marketplace_path))
        except Exception as exc:
            self.result("C9", False, f"marketplace parses: {exc}")
            marketplace = {}
        marketplace_plugins = marketplace.get("plugins", []) if isinstance(marketplace, dict) else []
        if not isinstance(marketplace_plugins, list):
            marketplace_plugins = []
        entries = [entry for entry in marketplace_plugins
                   if isinstance(entry, dict) and entry.get("name") == plugin_name]
        self.result("C9", len(entries) == 1,
                    f"marketplace has one {plugin_name!r} entry: {len(entries)}")
        if entries:
            source = entries[0].get("source") or {}
            if not isinstance(source, dict):
                source = {}
            url = source.get("url", "")
            self.result("C9", source.get("source") == "url"
                        and isinstance(url, str)
                        and url.startswith("https://github.com/")
                        and "@" not in url.split("//", 1)[-1]
                        and isinstance(source.get("ref"), str)
                        and bool(source.get("ref", "").strip()),
                        "marketplace uses a credential-free GitHub URL source")
            policy = entries[0].get("policy") or {}
            self.result("C9", isinstance(policy, dict)
                        and policy.get("installation") == "AVAILABLE" and
                        policy.get("authentication") == "ON_INSTALL",
                        "marketplace install/auth policy is explicit")

        surface, forbidden_paths, forbidden_contents, package_error = (
            forbidden_package_entries(self.root)
        )
        findings = forbidden_paths + forbidden_contents
        sample = f" e.g. {findings[:3]!r}" if findings else ""
        self.result("C9", package_error is None and not findings,
                    f"{surface} current-tree package excludes host-bound paths/content: "
                    f"{len(forbidden_paths)} path(s), {len(forbidden_contents)} content hit(s){sample}"
                    + (f"; inventory error: {package_error}" if package_error else ""))

        agents_path = os.path.join(self.root, "AGENTS.md")
        claude_path = os.path.join(self.root, "CLAUDE.md")
        try:
            agents_bytes = open(agents_path, "rb").read()
        except OSError:
            agents_bytes = b""
        try:
            claude_text = open(claude_path, encoding="utf-8").read()
        except OSError:
            claude_text = ""
        self.result("C9", 0 < len(agents_bytes) < 32 * 1024,
                    f"AGENTS.md {len(agents_bytes)} bytes (cap <32768)")
        self.result("C9", claude_text.startswith("@AGENTS.md\n") and
                    len(claude_text.splitlines()) < 200,
                    f"CLAUDE.md bridges AGENTS.md in {len(claude_text.splitlines())} lines")

    # ---- C10 ---------------------------------------------------------------
    def c10_delivery_contract(self):
        for rel, markers in DELIVERY_CONTRACT.items():
            path = os.path.join(self.root, rel)
            try:
                text = open(path, encoding="utf-8").read()
            except OSError:
                text = ""
            missing = [marker for marker in markers if marker not in text]
            self.result("C10", not missing,
                        f"{rel}: delivery contract markers "
                        f"{'present' if not missing else 'missing ' + repr(missing)}")
        tool = os.path.join(self.root, "tools", "pr-delivery-state.py")
        self.result("C10", os.path.isfile(tool),
                    "tools/pr-delivery-state.py exists")

    def run(self):
        print(f"harness_check {VERSION}  root={self.root}  mode={'ci' if self.ci else 'local'}")
        self.c1_selftests()
        self.c2_shared_identity()
        self.c3_reference_resolution()
        self.c4_descriptions()
        self.c5_bodies()
        self.c6_stale_patterns()
        self.c7_anchors()
        self.c8_reserved_basenames()
        self.c9_codex_package()
        self.c10_delivery_contract()
        print(f"\n  {self.checks} checks, {len(self.failures)} failure(s)")
        if self.checks == 0:
            print("  ZERO CHECKS RAN — error, not a clean verdict")
            return 2
        if self.failures:
            for c, d in self.failures:
                print(f"    - {c}: {d}")
            return 1
        return 0


# ---- selftest: every check proves it can go red -------------------------------
def selftest():
    bad = checks = 0

    def expect_red(label, fn):
        nonlocal bad, checks
        checks += 1
        try:
            ok = fn()
        except Exception as e:
            ok = False
            print(f"  FAIL {label}: raised {e!r}")
            bad += 1
            return
        print(f"  {'PASS' if ok else 'FAIL'} {label}")
        bad += (not ok)

    with tempfile.TemporaryDirectory() as td:
        # minimal planted-defect tree
        sk = os.path.join(td, "skills")
        for s, desc in [("alpha", "x" * 500), ("beta", "ok")]:   # alpha desc over cap
            os.makedirs(os.path.join(sk, s, "references"))
            open(os.path.join(sk, s, "SKILL.md"), "w").write(
                f"---\nname: {s}\ndescription: {desc}\n---\n\nRead references/present.md\n"
                + ("z" * 6000 if s == "alpha" else ""))
        # C2 red: shared basename diverges
        open(os.path.join(sk, "alpha/references/anti-patterns.md"), "w").write("v1")
        open(os.path.join(sk, "beta/references/anti-patterns.md"), "w").write("v2")
        # C3 red: cited file absent in alpha; orphan file in beta
        open(os.path.join(sk, "beta/references/present.md"), "w").write("ok")
        open(os.path.join(sk, "beta/references/orphan.md"), "w").write("named nowhere")
        # C6 red: stale pattern planted
        os.makedirs(os.path.join(td, "hooks"))
        open(os.path.join(td, "hooks/stale.md"), "w").write("this guard is NOT INSTALLED")
        # C8 red: nested reserved basename
        os.makedirs(os.path.join(td, "sub"))
        open(os.path.join(td, "CLAUDE.md"), "w").write("root")
        open(os.path.join(td, "AGENTS.md"), "w").write("root")
        open(os.path.join(td, "sub", "claude.md"), "w").write("collision")
        open(os.path.join(td, "settings.json"), "w").write("{}")

        failing_suite = os.path.join(td, "failing-selftest.py")
        open(failing_suite, "w").write("raise SystemExit(1)\n")
        c1_run = Run(td, ci=True)
        c1_run.c1_selftests([("planted-failure", [failing_suite])])
        expect_red("C1 goes red when an aggregated selftest fails",
                   lambda: any(c == "C1" and "exit 1" in d
                               for c, d in c1_run.failures))

        truncated_suite = os.path.join(td, "truncated-selftest.py")
        open(truncated_suite, "w").write("print('PASS first check')\nraise SystemExit(0)\n")
        c1_truncated = Run(td, ci=True)
        c1_truncated.c1_selftests([("planted-truncation", [truncated_suite])])
        expect_red("C1 rejects exit zero without a terminal selftest receipt",
                   lambda: any(c == "C1" and "terminal receipts=0" in d
                               for c, d in c1_truncated.failures))

        duplicate_suite = os.path.join(td, "duplicate-receipt.py")
        open(duplicate_suite, "w").write(
            "print('SELFTEST-SUMMARY checks=1 failures=0')\n"
            "print('SELFTEST-SUMMARY checks=1 failures=0')\n"
        )
        c1_duplicate = Run(td, ci=True)
        c1_duplicate.c1_selftests([("planted-duplicate", [duplicate_suite])])
        expect_red("C1 rejects ambiguous duplicate terminal receipts",
                   lambda: any(c == "C1" and "terminal receipts=2" in d
                               for c, d in c1_duplicate.failures))

        r = Run(td, ci=True)
        r.c2_shared_identity()
        expect_red("C2 goes red on diverged copies",
                   lambda: any(c == "C2" and "DIVERGED" in d for c, d in r.failures))
        r.c3_reference_resolution()
        expect_red("C3 goes red on missing cited file",
                   lambda: any(c == "C3" and "alpha" in d for c, d in r.failures))
        expect_red("C3 goes red on orphan file",
                   lambda: any(c == "C3" and "orphan.md" in d for c, d in r.failures))
        empty_c3 = os.path.join(td, "empty-c3")
        os.makedirs(os.path.join(empty_c3, "skills"))
        c3_empty_run = Run(empty_c3, ci=True)
        c3_empty_run.c3_reference_resolution()
        expect_red("C3 goes red on a zero-reference scan",
                   lambda: any(c == "C3" and "zero authored" in d
                               for c, d in c3_empty_run.failures))
        r2 = Run(td, ci=True)
        r2.checks = 0
        for s in ["alpha"]:
            skill_path = os.path.join(sk, s, "SKILL.md")
            ok, n = description_within_cap(skill_path)
            r2.result("C4", ok, f"{s}: {n}")
            ok, b = method_body_within_cap(skill_path)
            r2.result("C5", ok, f"{s}: {b}")
        expect_red("C4 goes red on 500-char description",
                   lambda: any(c == "C4" for c, d in r2.failures))
        expect_red("C5 goes red on 6,000-char body",
                   lambda: any(c == "C5" for c, d in r2.failures))
        authoring_fixture = os.path.join(td, "authoring-over-line-cap.md")
        open(authoring_fixture, "w").write("\n".join(["line"] * (BODY_LINE_CAP + 1)))
        authoring_run = Run(td, ci=True)
        ok, lines = authoring_body_within_cap(authoring_fixture)
        authoring_run.result("C5", ok, f"authoring: {lines}")
        expect_red("C5 goes red on an authoring skill over the line cap",
                   lambda: any(c == "C5" for c, _d in authoring_run.failures))
        r3 = Run(td, ci=True)
        r3.c6_stale_patterns()
        expect_red("C6 goes red on planted stale pattern",
                   lambda: any(c == "C6" and "NOT INSTALLED" in d for c, d in r3.failures))
        os.makedirs(os.path.join(td, "docs"))
        open(os.path.join(td, "docs", "relocated.md"), "w").write("committed to the PR")
        r3_docs = Run(td, ci=True)
        r3_docs.c6_stale_patterns()
        expect_red("C6 scans docs and goes red on a relocated stale claim",
                   lambda: any(c == "C6" and "committed to the PR" in d
                               for c, d in r3_docs.failures))
        empty_c6 = os.path.join(td, "empty-c6")
        os.makedirs(empty_c6)
        c6_empty_run = Run(empty_c6, ci=True)
        c6_empty_run.c6_stale_patterns()
        expect_red("C6 goes red on a zero-file scan",
                   lambda: any(c == "C6" and d == "zero files"
                               for c, d in c6_empty_run.failures))
        r4 = Run(td, ci=True)
        r4.c8_reserved_basenames()
        expect_red("C8 goes red on nested claude.md",
                   lambda: any(c == "C8" for c, d in r4.failures))
        r5 = Run(td, ci=True)
        r5.c9_codex_package()
        expect_red("C9 goes red on absent plugin package",
                   lambda: any(c == "C9" for c, d in r5.failures))

        open(os.path.join(td, "hooks", "hooks.json"), "w").write(json.dumps({
            "hooks": {"SessionStart": [{"hooks": [{
                "type": "command", "command": "true", "inventedLimit": 1
            }]}]}
        }))
        r6 = Run(td, ci=True)
        r6.c9_codex_package()
        expect_red("C9 goes red on unknown Codex hook handler key",
                   lambda: any(c == "C9" and "inventedLimit" in d for c, d in r6.failures))

        valid = os.path.join(td, "valid-package")
        for rel in (".codex-plugin", ".agents/plugins", "hooks", "skills", "tools"):
            os.makedirs(os.path.join(valid, rel))
        for rel in ("hooks/codex_session_start.py", "hooks/bash_command_guard.py",
                    "hooks/spawn_preflight_guard.py"):
            open(os.path.join(valid, rel), "w").write("# fixture\n")
        open(os.path.join(valid, "AGENTS.md"), "w").write("# policy\n")
        open(os.path.join(valid, "CLAUDE.md"), "w").write("@AGENTS.md\n")
        open(os.path.join(valid, "settings.json"), "w").write("{}")
        manifest = {
            "name": "z-harness", "version": "0.1.0", "description": "fixture",
            "author": {"name": "Chris"}, "skills": "./skills/",
            "interface": {
                "displayName": "z-harness", "shortDescription": "fixture",
                "longDescription": "fixture", "developerName": "Chris",
                "category": "Productivity", "websiteURL": "https://example.com",
                "brandColor": "#10A37F", "capabilities": ["Read"],
                "defaultPrompt": ["Use fixture"],
            },
        }
        marketplace = {
            "name": "z-harness", "plugins": [{
                "name": "z-harness",
                "source": {"source": "url", "url": "https://github.com/a/b.git", "ref": "main"},
                "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
            }],
        }
        hook_fixture = {
            "description": "fixture",
            "hooks": {
                "SessionStart": [{
                    "matcher": "startup|resume|clear|compact",
                    "enabled": True,
                    "trusted_hash": "sha256:fixture",
                    "hooks": [{
                    "type": "command",
                    "command": "python3 \"${PLUGIN_ROOT}/hooks/codex_session_start.py\"",
                    "timeout": 5,
                }]}],
                "SubagentStart": [{"hooks": [{
                    "type": "command",
                    "command": "python3 \"${PLUGIN_ROOT}/hooks/codex_session_start.py\"",
                    "timeout": 5,
                }]}],
                "PreToolUse": [
                    {"matcher": "^Bash$", "hooks": [{
                        "type": "command",
                        "command": "python3 \"${PLUGIN_ROOT}/hooks/bash_command_guard.py\" --runtime codex",
                        "timeout": 5,
                    }]},
                    {"matcher": "^Agent$", "hooks": [{
                        "type": "command",
                        "command": "python3 \"${PLUGIN_ROOT}/hooks/spawn_preflight_guard.py\" --runtime codex",
                        "timeout": 5,
                    }]},
                ],
                "Stop": [{"hooks": [{
                    "type": "command", "command": "true", "timeout": 5,
                }]}],
            },
        }

        def put_json(rel, value):
            open(os.path.join(valid, rel), "w").write(json.dumps(value))

        def c9_after(mutated_hooks=None, mutated_manifest=None, mutated_marketplace=None):
            put_json("hooks/hooks.json", mutated_hooks or hook_fixture)
            put_json(".codex-plugin/plugin.json", mutated_manifest or manifest)
            put_json(".agents/plugins/marketplace.json", mutated_marketplace or marketplace)
            run = Run(valid, ci=True)
            run.c9_codex_package()
            return run

        baseline = c9_after()
        expect_red("C9 valid fixture has no failures", lambda: not baseline.failures)

        bad_top = json.loads(json.dumps(hook_fixture))
        bad_top["version"] = 1
        run = c9_after(mutated_hooks=bad_top)
        expect_red("C9 rejects unknown hooks.json top-level keys",
                   lambda: any("top-level.version" in d for _c, d in run.failures))

        bad_event = json.loads(json.dumps(hook_fixture))
        bad_event["hooks"]["SessionStrt"] = bad_event["hooks"].pop("SessionStart")
        run = c9_after(mutated_hooks=bad_event)
        expect_red("C9 rejects misspelled case-sensitive event names",
                   lambda: any("unsupported event name" in d for _c, d in run.failures))

        unsupported_runtime_event = json.loads(json.dumps(hook_fixture))
        unsupported_runtime_event["hooks"]["SessionEnd"] = [{"hooks": [{
            "type": "command", "command": "true", "timeout": 5,
        }]}]
        run = c9_after(mutated_hooks=unsupported_runtime_event)
        expect_red("C9 rejects SessionEnd absent from the Codex 0.144.4 runtime schema",
                   lambda: any("SessionEnd: unsupported" in d for _c, d in run.failures))

        expect_red("C9 accepts additional runtime-observed hook events",
                   lambda: not c9_after().failures)
        expect_red("C9 accepts runtime-valid enabled and trusted_hash entry keys",
                   lambda: not c9_after().failures)

        for label, key, value, marker in (
            ("non-boolean enabled", "enabled", "yes", ".enabled: expected boolean"),
            ("empty trusted_hash", "trusted_hash", "", ".trusted_hash: expected non-empty"),
        ):
            mutated = json.loads(json.dumps(hook_fixture))
            mutated["hooks"]["SessionStart"][0][key] = value
            run = c9_after(mutated_hooks=mutated)
            expect_red(f"C9 rejects {label}",
                       lambda run=run, marker=marker: any(marker in d
                                                          for _c, d in run.failures))

        bad_matcher = json.loads(json.dumps(hook_fixture))
        bad_matcher["hooks"]["PreToolUse"][0]["matcher"] = "^Bash(["
        run = c9_after(mutated_hooks=bad_matcher)
        expect_red("C9 rejects invalid matcher regexes",
                   lambda: any("invalid regex" in d for _c, d in run.failures))

        for label, key, value, marker in (
            ("non-command handler", "type", "prompt", "only command"),
            ("async handler", "async", True, "must be absent or false"),
            ("string timeout", "timeout", "5", "positive integer"),
        ):
            mutated = json.loads(json.dumps(hook_fixture))
            mutated["hooks"]["PreToolUse"][0]["hooks"][0][key] = value
            run = c9_after(mutated_hooks=mutated)
            expect_red(f"C9 rejects {label}",
                       lambda run=run, marker=marker: any(marker in d for _c, d in run.failures))

        bad_manifest = json.loads(json.dumps(manifest))
        del bad_manifest["interface"]
        run = c9_after(mutated_manifest=bad_manifest)
        expect_red("C9 rejects a manifest without interface metadata",
                   lambda: any("interface contract" in d for _c, d in run.failures))

        bad_marketplace = json.loads(json.dumps(marketplace))
        bad_marketplace["plugins"][0]["source"]["url"] = 123
        run = c9_after(mutated_marketplace=bad_marketplace)
        expect_red("C9 rejects non-string marketplace source fields",
                   lambda: any("credential-free GitHub URL" in d for _c, d in run.failures))

        missing_runtime = json.loads(json.dumps(hook_fixture))
        missing_runtime["hooks"]["PreToolUse"][0]["hooks"][0]["command"] = (
            "python3 \"${PLUGIN_ROOT}/hooks/bash_command_guard.py\""
        )
        put_json("hooks/hooks.json", missing_runtime)
        c7_run = Run(valid, ci=True)
        c7_run.c7_anchors()
        expect_red("C7 rejects a Bash handler without --runtime codex",
                   lambda: any("bash_command_guard.py" in d and "0 match(es)" in d
                               for _c, d in c7_run.failures))

        put_json("hooks/hooks.json", hook_fixture)
        put_json(".codex-plugin/plugin.json", manifest)
        put_json(".agents/plugins/marketplace.json", marketplace)
        os.makedirs(os.path.join(valid, "nested/projects/private/memory"))
        open(os.path.join(valid, "nested/projects/private/memory/MEMORY.md"), "w").write("x")
        run = Run(valid, ci=True)
        run.c9_codex_package()
        expect_red("C9 rejects nested projects/ content in an installed package",
                   lambda: any("current-tree package excludes host-bound" in d
                               for _c, d in run.failures))

        for label, path in (
            ("nested audit directory", "nested/HARNESS-AUDIT-20260801/record.md"),
            ("prefixed private/Users slug",
             "records/-private-tmp-run--Users-quantum-project/record.md"),
            ("underscore home slug", "records/_home_quantum_project/record.md"),
            ("Volumes slug", "records/-Volumes-work-project/record.md"),
        ):
            expect_red(f"C9 path predicate rejects {label}",
                       lambda path=path: forbidden_package_path(path))
        expect_red("C9 path predicate permits ordinary private documentation",
                   lambda: not forbidden_package_path("docs/private-notes.md"))

        portable = os.path.join(valid, "host-config.txt")
        open(portable, "w").write("tool=/" + "Users/alice/.claude/hooks/check.py\n")
        _surface, _paths, contents, _error = forbidden_package_entries(valid)
        expect_red("C9 rejects absolute host paths inside package text",
                   lambda: "host-config.txt" in contents)

        subprocess.run(["git", "init", "--quiet", valid], check=True)
        audit_file = os.path.join(valid, "nested", "harness-audit-20260801", "record.md")
        os.makedirs(os.path.dirname(audit_file), exist_ok=True)
        open(audit_file, "w").write("publisher-only")
        subprocess.run(
            ["git", "-C", valid, "add", "--",
             "nested/harness-audit-20260801/record.md"],
            check=True,
        )
        run = Run(valid, ci=True)
        run.c9_codex_package()
        expect_red("C9 source-tree arm rejects tracked audit content",
                   lambda: any("source current-tree package excludes host-bound" in d
                               and "harness-audit-20260801" in d
                               for _c, d in run.failures))

        r7 = Run(td, ci=True)
        r7.c10_delivery_contract()
        expect_red("C10 goes red on absent PR delivery contract",
                   lambda: any(c == "C10" for c, d in r7.failures))

    print(f"\n  selftest: {bad} failure(s)")
    print(f"SELFTEST-SUMMARY checks={checks} failures={bad}")
    return 1 if bad else 0


def main(argv):
    args = argv[1:]
    if args and args[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if args and args[0] == "--version":
        print(f"harness_check {VERSION}")
        return 0
    if args and args[0] == "--selftest":
        return selftest()
    ci = False
    if args and args[0] == "--ci":
        ci = True
        args = args[1:]
    if args:
        sys.stderr.write(f"unknown argument: {args[0]!r}\nrun --help\n")
        return 2
    return Run(ROOT, ci).run()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
