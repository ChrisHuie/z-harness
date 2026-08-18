#!/usr/bin/env python3
"""harness_check — the mechanical gate for this harness's authored surface.

Runs from either clone (repo root auto-detected from this file's location). Checks:

  C1  guard/report/accounting selftests exit 0, emit a complete terminal receipt,
      and report at least as many checks as the floor recorded for that suite
  C2  shared-corpus reference copies are byte-identical across skills, and any
      basename appearing in >=2 skills is either SHARED or explicitly PER_SKILL —
      an unknown multi-skill basename fails loud
  C3  reference resolution, both directions: every references/ path a SKILL.md
      names exists; every file under references/ is named by its SKILL.md,
      literally or via a <param> template family
  C4  every description <= 400 chars (house cap inside the 1024 spec ceiling)
  C5  method-skill bodies <= 5,000 chars after frontmatter; authoring-skill
      bodies <= 500 lines
  C6  stale-claim tripwires: patterns that once shipped false stay at zero across
      every tracked file except the declared SCAN_EXCLUSIONS
  C7  anchors: routing-table skills exist; Claude and Codex hook commands resolve;
      [local] original audit paths exist, `timeout` still absent, askq binary
      anchors hold
  C8  reserved context basenames (CLAUDE.md/AGENTS.md/GEMINI.md) exist nowhere
      but the repo root, .git excluded as a path component (not a substring)
  C9  Codex package contract: manifest, marketplace, hook config, context bridges,
      and their size budgets are internally consistent
  C10 PR delivery contract: scoped publication authority, state-proof command,
      and the ban on conflating local commits with the GitHub PR remain present
  C11 claim-vocabulary coherence: the phrases AGENTS.md bans outright appear
      nowhere in the instruction corpus it governs

Exit codes: 0 all checks pass · 1 one or more checks failed · 2 usage error or
zero inputs (an empty scan set is an error, never a clean verdict).

  harness_check.py             run every check (local mode)
  harness_check.py --ci        skip [local]-tagged checks (no ~/.claude, no
                               claude binary, no launchd on the runner)
  harness_check.py --selftest  prove each check can go RED on a planted-defect
                               tree, then exit
"""
import fnmatch
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile

VERSION = "3.1.0"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# C11 anchor. AGENTS.md bans self-assessment carrying no technical sense and keeps words
# like `clean` and `verified` usable, because the corpus needs them for a tree or a head.
# That split holds only while the banned side stays absent from the files telling an agent
# what to emit, and one canonical file mandating a phrase another one bans is invisible to
# every per-file check. Terms are read from AGENTS.md rather than restated here, so the
# prose and the gate cannot drift apart.
BANNED_VOCAB_ANCHOR = "banned outright:"
# Floor on how many phrases the anchor sentence must yield. Without it, only zero was an
# error, so a meaning-preserving reword that split the sentence halved the ban list in
# silence. Lower it only in the commit that retires a phrase.
BANNED_VOCAB_FLOOR = 5
# A floor on cardinality does not floor content: swapping one phrase for an invented word
# keeps the count at five while retiring a real term, and the verdict line is byte-identical.
# These phrases must appear in whatever the anchor yields. Prose may add to the ban list; it
# cannot silently drop one of these, and removing one deliberately means editing here too,
# where it is reviewed.
REQUIRED_BANNED_TERMS = frozenset(
    {"looks good", "should work", "solid", "perfect", "all set"}
)
C11_SCOPE_DECLARATION = (
    "C11 claim-vocabulary scope: AGENTS.md, CLAUDE.md, every skills/*/SKILL.md, "
    "and .md/.yaml/.yml files under skills/*/references/."
)
C11_EXCLUSION_DECLARATION = (
    "C11 excludes evals/, scripts/, assets/, and other source files; it proves "
    "vocabulary coherence only, not factual grounding or output behavior."
)
C11_MATCH_DECLARATION = (
    "C11 is source-lexical: it matches ASCII-case-insensitive phrases separated by "
    "ASCII spaces/tabs or one physical line break; inline markup and paraphrases "
    "are out of scope."
)

# The aggregated suites carry per-suite floors; this is the same ratchet for the meta-suite
# that proves each check can go red. It cannot live in SELFTEST_SUITES without recursing, so
# the count is asserted at the end of its own run. Raise it in the commit that adds proofs.
SELFTEST_FLOOR = 72

AUTHORING_SKILLS = {"craft-prompt", "craft-skill", "craft-context-file", "review-prompt"}
BODY_CHAR_CAP = 5000          # chars after frontmatter — the builders' instrument
BODY_LINE_CAP = 500           # authoring skills (spec cap)
DESC_CAP = 400                # house cap (spec ceiling is 1024)

# (name, command, floor). The floor is a shrink-only ratchet: a suite reporting fewer
# checks than its floor goes red. Without it a receipt of checks=1 reads the same as
# checks=111, so a suite can be gutted with nothing failing. Raise a floor in the same
# commit that adds the checks; lowering one is a deliberate, reviewable edit.
SELFTEST_SUITES = [
    ("bash_command_guard", ["hooks/bash_command_guard.py", "--selftest"], 111),
    ("askq_timeout_guard", ["hooks/askq_timeout_guard.py", "--selftest"], 13),
    ("harness_report", ["hooks/harness_report.py", "--selftest"], 12),
    ("cc-cost", ["tools/cc-cost.py", "--selftest"], 8),
    ("codex-cost", ["tools/codex-cost.py", "--selftest"], 28),
    ("claim-provenance", ["tools/claim-provenance.py", "--selftest"], 42),
    ("pr-delivery-state", ["tools/pr-delivery-state.py", "--selftest"], 8),
    ("run-skill-evals", ["tools/run-skill-evals.py", "--selftest"], 3),
    ("render-packages", ["tools/render-packages.py", "--selftest"], 192),
    ("ci-gate", ["tools/ci-gate.py", "--selftest"], 17),
    ("portable-conformance", ["tools/portable-conformance.py", "--selftest"], 63),
    ("codex_session_start", ["hooks/codex_session_start.py", "--selftest"], 32),
    ("spawn_preflight_guard", ["hooks/spawn_preflight_guard.py", "--selftest"], 16),
    ("announced_work_guard", ["hooks/announced_work_guard.py", "--selftest"], 72),
    ("git_grep_engine_guard", ["hooks/guards/git_grep_engine_guard.py", "--selftest"], 66),
    ("zsh_rev_modifier_guard", ["hooks/guards/zsh_rev_modifier_guard.py", "--selftest"], 31),
]
# The only non-aggregated selftest is this recursive meta-suite itself.
SELFTEST_EXEMPTIONS = {
    "hooks/harness_check.py": "recursive meta-suite",
}
PRODUCTION_CHECKS = (
    ("C1", "c1_selftests"),
    ("C1", "c1_selftest_inventory"),
    ("C2", "c2_shared_identity"),
    ("C3", "c3_reference_resolution"),
    ("C4", "c4_descriptions"),
    ("C5", "c5_bodies"),
    ("C6", "c6_stale_patterns"),
    ("C7", "c7_anchors"),
    ("C8", "c8_reserved_basenames"),
    ("C9", "c9_codex_package"),
    ("C10", "c10_delivery_contract"),
    ("C11", "c11_claim_vocabulary"),
)

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
    "contain no `targetLevel`", # artifacts carry the claims block; denied in two docs
    "no validation status",     # same denial, README wording
]

# C1: source digest per aggregated suite. A receipt's check count is self-reported, so a
# stub can satisfy any floor; binding the source is what makes a receipt evidence.
SUITE_SOURCE_GOLDEN = "contracts/goldens/suite-sources.json"


def suite_source_golden(root=None):
    """Recorded source digest per aggregated suite. Absence is a failure, not a skip.

    Tolerating an absent file made the binding removable by deleting one file that no
    check required, which fully restored the stub attack this exists to stop and produced
    a receipt byte-identical to a pristine run. A guard that any single deletion disables
    is not a guard, so a missing or malformed golden yields an empty mapping and every
    registered suite then reports its digest as unrecorded.
    """
    path = os.path.join(root or ROOT, SUITE_SOURCE_GOLDEN)
    if not os.path.isfile(path):
        return {}
    try:
        value = json.load(open(path, encoding="utf-8")).get("suites")
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


# C6/C8 scan set: everything tracked EXCEPT these. Written down rather than implied by a
# directory list, so a surface added later is scanned by default and an omission is a
# reviewable line instead of a forgotten tuple entry.
# Printing the resolved set size is not a floor on it: adding one filename to
# SCAN_EXCLUSIONS removed a file from the sweep and the verdict stayed green with a
# smaller number nobody compares. Lower this only in the commit that removes the files.
C6_SCAN_FLOOR = 162

SCAN_EXCLUSIONS = (
    "hooks/harness_check.py",   # this file names every tripwire; it cannot sweep itself
    "*.pyc",                    # build output
    "*.jsonl",                  # recorded transcript fixtures, not authored prose
    "**/__pycache__/**",
)

ROUTING_SKILLS = ["git-workflow", "pr-review-method", "testing-ci", "agent-dispatch",
                  "ground-claims", "prebid-adcp", "system-design", "outbound-drafts",
                  "craft-prompt", "craft-skill", "craft-context-file", "review-prompt"]

# Which guard must be registered on which Claude event, mirroring REQUIRED_CODEX_HANDLERS.
# Asserting a handler COUNT and a set of event keys was satisfiable by two handlers running
# `true`: the events existed, the count matched, and all three guards were unregistered --
# the same end state as the deleted hooks block it was written to catch. Bind the script to
# the event instead.
REQUIRED_CLAUDE_HANDLERS = [
    ("PostToolUse", "AskUserQuestion", "hooks/askq_timeout_guard.py"),
    ("PreToolUse", "Bash", "hooks/bash_command_guard.py"),
    ("PreToolUse", "Agent|Task", "hooks/spawn_preflight_guard.py"),
    ("Stop", None, "hooks/announced_work_guard.py"),
]

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


def skill_names(root):
    skills_dir = os.path.join(root, "skills")
    if not os.path.isdir(skills_dir):
        return []
    return sorted(
        name for name in os.listdir(skills_dir)
        if os.path.isfile(os.path.join(skills_dir, name, "SKILL.md"))
    )


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
        if lower == "projects" or slug.startswith("harness-audit-"):
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
    def c1_selftests(self, suites=None, sources=None):
        """Aggregate every suite, and bind what produced each receipt.

        A receipt's check count is self-reported. An eight-line stub printing
        `SELFTEST-SUMMARY suite=<name> checks=<floor> failures=0` satisfied the floor and
        took the whole gate green, including for the tool that proves PR delivery state.
        The floor only ever defended against a suite that reported honestly, so the source
        of each suite is pinned: a suite cannot be replaced by something that merely
        claims to have run.
        """
        if suites is None:
            suites = SELFTEST_SUITES
        if sources is None:
            sources = suite_source_golden()
        for name, cmd, floor in suites:
            # README calls these positive floors. A floor of zero accepted a receipt of
            # checks=0, so the word was doing no work.
            if floor < 1:
                self.result("C1", False,
                            f"selftest {name}: floor {floor} is not positive")
                continue
            if sources is None:
                sources = {}
            if True:
                expected = sources.get(name)
                path = os.path.join(self.root, cmd[0])
                actual = (
                    hashlib.sha256(open(path, "rb").read()).hexdigest()
                    if os.path.isfile(path) else None
                )
                if expected is None:
                    self.result("C1", False,
                                f"selftest {name}: no source digest recorded in "
                                f"{os.path.basename(SUITE_SOURCE_GOLDEN)}")
                    continue
                if actual != expected:
                    self.result("C1", False,
                                f"selftest {name}: {cmd[0]} does not match its recorded "
                                f"source digest; if the tool changed on purpose, update "
                                f"its entry in {os.path.basename(SUITE_SOURCE_GOLDEN)} in "
                                f"the same commit and review that diff")
                    continue
            try:
                p = subprocess.run(
                    [sys.executable, os.path.join(self.root, cmd[0])] + cmd[1:],
                    capture_output=True, cwd=self.root, timeout=15,
                )
            except subprocess.TimeoutExpired:
                self.result("C1", False, f"selftest {name}: exceeded 15s")
                continue
            receipts = re.findall(
                rb"^SELFTEST-SUMMARY suite=([a-z0-9_-]+) checks=(\d+) failures=(\d+)$",
                p.stdout,
                re.M,
            )
            final_line = p.stdout.rstrip().splitlines()[-1] if p.stdout.rstrip() else b""
            receipt_ok = (
                len(receipts) == 1
                and receipts[0][0].decode("ascii") == name
                and int(receipts[0][1]) >= floor
                and int(receipts[0][2]) == 0
                and final_line == (
                    b"SELFTEST-SUMMARY suite=" + receipts[0][0]
                    + b" checks=" + receipts[0][1]
                    + b" failures=" + receipts[0][2]
                )
            )
            detail = f"selftest {name}: exit {p.returncode}; terminal receipts={len(receipts)}"
            if len(receipts) == 1:
                detail += (f" suite={receipts[0][0].decode('ascii')} "
                           f"checks={int(receipts[0][1])} floor={floor} "
                           f"failures={int(receipts[0][2])} "
                           f"final={final_line.startswith(b'SELFTEST-SUMMARY ')}")
                if int(receipts[0][1]) < floor:
                    detail += " below-floor"
            self.result("C1", p.returncode == 0 and receipt_ok, detail)

    def c1_selftest_inventory(self, suites=None, exemptions=None):
        """Every script exposing --selftest is aggregated or explicitly classified."""
        suites = SELFTEST_SUITES if suites is None else suites
        exemptions = SELFTEST_EXEMPTIONS if exemptions is None else exemptions
        aggregated = {cmd[0] for _name, cmd, _floor in suites}
        actual = set()
        for rel_root in ("hooks", "tools"):
            base = os.path.join(self.root, rel_root)
            if not os.path.isdir(base):
                continue
            for dirpath, _dirs, files in os.walk(base):
                for filename in files:
                    if not filename.endswith(".py"):
                        continue
                    path = os.path.join(dirpath, filename)
                    text = open(path, encoding="utf-8", errors="replace").read()
                    if (re.search(r"^def selftest\(", text, re.M)
                            or re.search(r"['\"]--selftest['\"]", text)):
                        actual.add(os.path.relpath(path, self.root))
        declared = aggregated | set(exemptions)
        unknown = sorted(actual - declared)
        stale = sorted(declared - actual)
        self.result(
            "C1", bool(actual) and not unknown and not stale,
            f"selftest inventory: discovered={len(actual)} aggregated={len(aggregated)} "
            f"exemptions={len(exemptions)}"
            + (f" unclassified={unknown}" if unknown else "")
            + (f" stale={stale}" if stale else ""),
        )

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
        names = skill_names(self.root)
        if not names:
            self.result("C4", False, "zero skills discovered")
            return
        for skill in names:
            p = os.path.join(self.root, "skills", skill, "SKILL.md")
            ok, n = description_within_cap(p)
            self.result("C4", ok, f"{skill}: description {n} chars (cap {DESC_CAP})")

    def c5_bodies(self):
        names = skill_names(self.root)
        if not names:
            self.result("C5", False, "zero skills discovered")
            return
        for skill in names:
            p = os.path.join(self.root, "skills", skill, "SKILL.md")
            if skill in AUTHORING_SKILLS:
                ok, n = authoring_body_within_cap(p)
                self.result("C5", ok, f"{skill}: {n} lines (cap {BODY_LINE_CAP})")
            else:
                ok, n = method_body_within_cap(p)
                self.result("C5", ok,
                            f"{skill}: body {n} chars (cap {BODY_CHAR_CAP})")

    # ---- C6 ----------------------------------------------------------------
    def c6_stale_patterns(self, scan_floor=None):
        """Tripwires over the whole shipped surface, not a remembered directory list.

        The scan set is every tracked file minus SCAN_EXCLUSIONS. A hardcoded directory
        tuple silently omitted settings.json, statusline.sh, .gitignore, and the whole of
        .github/, so a false claim could live in a shipped file the guard never opened.
        Deriving the set means a new directory is covered by default and an omission has
        to be written down.
        """
        me = os.path.abspath(__file__)
        surface, paths, error = package_paths(self.root)
        if error:
            self.result("C6", False, f"cannot enumerate scan set: {error}")
            return
        targets, excluded = [], 0
        for rel in paths:
            if any(fnmatch.fnmatch(rel, pattern) for pattern in SCAN_EXCLUSIONS):
                excluded += 1
                continue
            absolute = os.path.join(self.root, rel)
            if not os.path.isfile(absolute):
                continue
            targets.append(absolute)
        # The floor is a parameter so planted-defect fixture trees, which hold a handful of
        # files, can assert the tripwire logic instead of tripping a floor sized for the
        # real repository. Production callers take the default.
        floor = C6_SCAN_FLOOR if scan_floor is None else scan_floor
        if len(targets) < floor:
            print(f"  FATAL C6: {len(targets)} files in scan set, floor is {floor}")
            self.failures.append(
                ("C6", f"scan set shrank to {len(targets)}, floor {floor}")
            )
            return
        for pat in STALE_PATTERNS:
            hits = [t for t in targets
                    if pat in open(t, encoding="utf-8", errors="replace").read()]
            self.result("C6", not hits,
                        f"tripwire {pat!r}: {len(hits)} hit(s) over {len(targets)} "
                        f"{surface} files ({excluded} excluded)"
                        + (f" e.g. {os.path.relpath(hits[0], self.root)}" if hits else ""))

    # ---- C7 ----------------------------------------------------------------
    def c7_anchors(self):
        for skill in ROUTING_SKILLS:
            p = os.path.join(self.root, "skills", skill)
            self.result("C7", os.path.isdir(p), f"routing-table skill exists: {skill}")
        st = json.load(open(os.path.join(self.root, "settings.json")))
        # Deleting the hooks block unregistered every Claude guard and produced zero checks
        # and zero failures -- a silent pass over an empty scan set, which this file's own
        # exit-code contract calls an error. The Codex side is bound by
        # REQUIRED_CODEX_HANDLERS; this is its Claude counterpart.
        for event, matcher, script in REQUIRED_CLAUDE_HANDLERS:
            matches = [
                h for entry in st.get("hooks", {}).get(event, [])
                if entry.get("matcher") == matcher
                for h in entry.get("hooks", [])
                if script in h.get("command", "")
            ]
            self.result("C7", len(matches) == 1,
                        f"settings.json {event} matcher={matcher!r} -> {script}: "
                        f"{len(matches)} match(es)")
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
        """A reserved context basename anywhere but the repo root is auto-loaded instructions.

        The exclusion is the `.git` directory itself, matched as a path component. A
        substring test also excluded `.github/`, where a planted CLAUDE.md passed while the
        identical bytes under docs/ failed — so the one directory a reviewer is least
        likely to read was the one place the guard could not see.
        """
        hits, scanned = [], 0
        for dirpath, dirs, files in os.walk(self.root):
            dirs[:] = [d for d in dirs if d != ".git"]
            for f in files:
                scanned += 1
                if f.lower() in RESERVED_BASENAMES:
                    p = os.path.join(dirpath, f)
                    if os.path.dirname(os.path.abspath(p)) != os.path.abspath(self.root):
                        hits.append(os.path.relpath(p, self.root))
        if not scanned:
            self.result("C8", False, "zero files in scan set")
            return
        self.result("C8", not hits,
                    f"reserved basenames outside root over {scanned} files: {hits or 'none'}")

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

    # ---- C11 ---------------------------------------------------------------
    def c11_claim_vocabulary(self):
        """Corpus-level: no phrase AGENTS.md bans outright survives in the files it governs.

        Loads the whole instruction corpus in one pass, because a contradiction between two
        canonical files is invisible to any check that judges one file at a time. Fails loud
        when its own anchor is missing rather than reporting a clean sweep over nothing.
        """
        source = os.path.join(self.root, "AGENTS.md")
        try:
            if os.path.islink(source) or not os.path.isfile(source):
                raise OSError("absent or symlinked outside the governed regular-file profile")
            agents_text = open(source, encoding="utf-8").read()
        except OSError as exc:
            self.result("C11", False, f"cannot enforce: AGENTS.md unreadable: {exc}")
            return
        missing_declarations = [
            declaration for declaration in (
                C11_SCOPE_DECLARATION, C11_EXCLUSION_DECLARATION,
                C11_MATCH_DECLARATION,
            )
            if declaration not in agents_text
        ]
        if missing_declarations:
            self.result(
                "C11", False,
                f"cannot enforce: missing scope declaration(s) {missing_declarations!r}",
            )
            return
        sentences = list(re.finditer(
            re.escape(BANNED_VOCAB_ANCHOR) + r"([^.]*)\.", agents_text
        ))
        if len(sentences) != 1:
            self.result("C11", False,
                        f"cannot enforce: expected one {BANNED_VOCAB_ANCHOR!r} "
                        f"anchor in AGENTS.md, found {len(sentences)}")
            return
        sentence = sentences[0]
        term_matches = list(re.finditer(r"\*([^*\n]+)\*", sentence.group(1)))
        terms = [match.group(1).strip() for match in term_matches]
        normalized_terms = [term.casefold() for term in terms]
        if (
            not terms
            or len(normalized_terms) != len(set(normalized_terms))
            or any(re.fullmatch(r"[A-Za-z]+(?: [A-Za-z]+)*", term) is None
                   for term in terms)
        ):
            self.result(
                "C11", False,
                "cannot enforce: anchor phrases must be non-empty, unique ASCII word phrases",
            )
            return
        # The sentence regex stops at the first period, and only zero terms was an error.
        # Rewriting the anchor into two sentences -- meaning preserved, one extra period --
        # silently halved the list from five phrases to two, and three banned phrases then
        # sat in a governed file with the whole gate green. This is the same shrink the
        # suite floors exist to catch, so the term count carries its own floor.
        missing_required = sorted(
            REQUIRED_BANNED_TERMS - {term.casefold() for term in terms}
        )
        if missing_required:
            self.result(
                "C11", False,
                f"cannot enforce: anchor no longer bans {missing_required}; retiring a "
                f"phrase means removing it from REQUIRED_BANNED_TERMS in the same commit",
            )
            return
        if len(terms) < BANNED_VOCAB_FLOOR:
            self.result(
                "C11", False,
                f"cannot enforce: anchor lists {len(terms)} phrase(s), floor is "
                f"{BANNED_VOCAB_FLOOR}; if a phrase was retired, lower the floor in the "
                f"same commit so the reduction is reviewed",
            )
            return
        # Exempt only the emphasized declaration tokens. Removing the whole sentence would
        # hide an additional use of a banned phrase later in that same sentence.
        governed_agents = list(agents_text)
        for match in term_matches:
            start = sentence.start(1) + match.start()
            end = sentence.start(1) + match.end()
            governed_agents[start:end] = " " * (end - start)
        governed = {"AGENTS.md": "".join(governed_agents)}
        claude_path = os.path.join(self.root, "CLAUDE.md")
        try:
            if os.path.islink(claude_path):
                raise OSError("symlink is outside the governed regular-file profile")
            governed["CLAUDE.md"] = open(claude_path, encoding="utf-8").read()
        except (OSError, UnicodeError) as exc:
            self.result("C11", False, f"cannot enforce: CLAUDE.md unreadable: {exc}")
            return
        skills_dir = os.path.join(self.root, "skills")
        if not os.path.isdir(skills_dir) or os.path.islink(skills_dir):
            self.result("C11", False, "cannot enforce: skills directory absent or symlinked")
            return
        skill_manifests = 0
        reference_files = 0
        try:
            for skill in sorted(os.listdir(skills_dir)):
                skill_root = os.path.join(skills_dir, skill)
                if not os.path.isdir(skill_root):
                    continue
                if os.path.islink(skill_root):
                    raise OSError(f"skills/{skill} is a symlink")
                body = os.path.join(skill_root, "SKILL.md")
                if not os.path.isfile(body) or os.path.islink(body):
                    raise OSError(f"skills/{skill}/SKILL.md absent or symlinked")
                governed[f"skills/{skill}/SKILL.md"] = open(
                    body, encoding="utf-8"
                ).read()
                skill_manifests += 1
                references = os.path.join(skill_root, "references")
                if not os.path.exists(references):
                    continue
                if not os.path.isdir(references) or os.path.islink(references):
                    raise OSError(f"skills/{skill}/references absent or symlinked")
                for current, directories, files in os.walk(references):
                    directories[:] = sorted(
                        directory for directory in directories
                        if directory not in {"evals", "scripts", "assets"}
                    )
                    for directory in directories:
                        if os.path.islink(os.path.join(current, directory)):
                            raise OSError(
                                f"reference directory symlink: "
                                f"{os.path.relpath(os.path.join(current, directory), self.root)}"
                            )
                    for filename in sorted(files):
                        if os.path.splitext(filename)[1].lower() not in {
                            ".md", ".yaml", ".yml",
                        }:
                            continue
                        path = os.path.join(current, filename)
                        relative = os.path.relpath(path, self.root).replace(os.sep, "/")
                        if os.path.islink(path) or not os.path.isfile(path):
                            raise OSError(f"reference file absent or symlinked: {relative}")
                        governed[relative] = open(path, encoding="utf-8").read()
                        reference_files += 1
        except (OSError, UnicodeError) as exc:
            self.result("C11", False, f"cannot enforce: governed corpus unreadable: {exc}")
            return
        if skill_manifests == 0:
            self.result("C11", False, "cannot enforce: zero skill manifests in scan set")
            return
        hits = []
        for term in terms:
            gap = r"(?:[ \t]+|[ \t]*\r?\n[ \t]*)"
            phrase = gap.join(re.escape(word) for word in term.split(" "))
            pattern = re.compile(
                r"(?<![A-Za-z0-9_])" + phrase + r"(?![A-Za-z0-9_])",
                re.I | re.ASCII,
            )
            for rel, text in sorted(governed.items()):
                if pattern.search(text):
                    hits.append(f"{rel}:{term!r}")
        self.result(
            "C11", not hits,
            f"claim vocabulary: {len(terms)} banned phrase(s) absent from "
            f"{len(governed)} governed file(s) "
            f"[{skill_manifests} SKILL.md, {reference_files} reference md/yaml; "
            f"evals/scripts/assets and other sources excluded; source lexical, ASCII "
            f"case, spaces/tabs or one line break; inline markup/paraphrases "
            f"excluded; vocabulary only]"
            + (f" — present: {hits}" if hits else ""),
        )

    def run(self):
        print(f"harness_check {VERSION}  root={self.root}  mode={'ci' if self.ci else 'local'}")
        for _check_id, method_name in PRODUCTION_CHECKS:
            getattr(self, method_name)()
        print(f"\n  {self.checks} checks, {len(self.failures)} failure(s)")
        if self.checks == 0:
            print("  ZERO CHECKS RAN — error, not a clean verdict")
            code = 2
        elif self.failures:
            for c, d in self.failures:
                print(f"    - {c}: {d}")
            code = 1
        else:
            code = 0
        print(
            f"HARNESS-SUMMARY mode={'ci' if self.ci else 'local'} "
            f"checks={self.checks} failures={len(self.failures)} exit={code}"
        )
        return code


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

        def planted_sources(name, path):
            """Digest a synthetic suite so the source binding applies to it too."""
            return {name: hashlib.sha256(open(path, "rb").read()).hexdigest()}

        failing_suite = os.path.join(td, "failing-selftest.py")
        open(failing_suite, "w").write("raise SystemExit(1)\n")
        c1_run = Run(td, ci=True)
        c1_run.c1_selftests([("planted-failure", [failing_suite], 1)], sources=planted_sources("planted-failure", failing_suite))
        expect_red("C1 goes red when an aggregated selftest fails",
                   lambda: any(c == "C1" and "exit 1" in d
                               for c, d in c1_run.failures))

        truncated_suite = os.path.join(td, "truncated-selftest.py")
        open(truncated_suite, "w").write("print('PASS first check')\nraise SystemExit(0)\n")
        c1_truncated = Run(td, ci=True)
        c1_truncated.c1_selftests([("planted-truncation", [truncated_suite], 1)], sources=planted_sources("planted-truncation", truncated_suite))
        expect_red("C1 rejects exit zero without a terminal selftest receipt",
                   lambda: any(c == "C1" and "terminal receipts=0" in d
                               for c, d in c1_truncated.failures))

        duplicate_suite = os.path.join(td, "duplicate-receipt.py")
        open(duplicate_suite, "w").write(
            "print('SELFTEST-SUMMARY suite=planted-duplicate checks=1 failures=0')\n"
            "print('SELFTEST-SUMMARY suite=planted-duplicate checks=1 failures=0')\n"
        )
        c1_duplicate = Run(td, ci=True)
        c1_duplicate.c1_selftests([("planted-duplicate", [duplicate_suite], 1)], sources=planted_sources("planted-duplicate", duplicate_suite))
        expect_red("C1 rejects ambiguous duplicate terminal receipts",
                   lambda: any(c == "C1" and "terminal receipts=2" in d
                               for c, d in c1_duplicate.failures))

        shrunk_suite = os.path.join(td, "shrunk-selftest.py")
        open(shrunk_suite, "w").write(
            "print('SELFTEST-SUMMARY suite=planted-shrink checks=1 failures=0')\n"
        )
        c1_shrunk = Run(td, ci=True)
        c1_shrunk.c1_selftests([("planted-shrink", [shrunk_suite], 5)], sources=planted_sources("planted-shrink", shrunk_suite))
        expect_red("C1 goes red when a suite reports fewer checks than its floor",
                   lambda: any(c == "C1" and "below-floor" in d
                               for c, d in c1_shrunk.failures))
        c1_at_floor = Run(td, ci=True)
        at_floor_suite = os.path.join(td, "at-floor-selftest.py")
        open(at_floor_suite, "w").write(
            "print('SELFTEST-SUMMARY suite=planted-at-floor checks=1 failures=0')\n"
        )
        c1_at_floor.c1_selftests([("planted-at-floor", [at_floor_suite], 1)], sources=planted_sources("planted-at-floor", at_floor_suite))
        # The stub that motivated this: an honest-looking receipt over no work. It clears
        # the floor, so only the source binding can reject it.
        stub_suite = os.path.join(td, "stub-selftest.py")
        open(stub_suite, "w").write(
            "print('SELFTEST-SUMMARY suite=planted-stub checks=99 failures=0')\n"
        )
        c1_zero_floor = Run(td, ci=True)
        c1_zero_floor.c1_selftests([("planted-zero-floor", [at_floor_suite], 0)],
                                   sources=planted_sources("planted-zero-floor", at_floor_suite))
        expect_red("C1 rejects a floor of zero, which accepted a suite reporting no checks",
                   lambda: any(c == "C1" and "not positive" in d
                               for c, d in c1_zero_floor.failures))
        expect_red("every registered suite floor is positive",
                   lambda: all(floor >= 1 for _n, _c, floor in SELFTEST_SUITES))

        # Tolerating an absent golden made the binding removable by deleting one file.
        c1_no_golden = Run(td, ci=True)
        c1_no_golden.c1_selftests([("planted-stub", [at_floor_suite], 1)],
                                  sources=suite_source_golden(td))
        expect_red("C1 treats an absent suite golden as unrecorded, never as permission",
                   lambda: any(c == "C1" and "no source digest recorded" in d
                               for c, d in c1_no_golden.failures))

        c1_stub = Run(td, ci=True)
        c1_stub.c1_selftests([("planted-stub", [stub_suite], 8)],
                             sources={"planted-stub": "0" * 64})
        expect_red("C1 rejects a suite whose source does not match its recorded digest",
                   lambda: any(c == "C1" and "recorded source digest" in d
                               for c, d in c1_stub.failures))
        c1_registered = Run(td, ci=True)
        c1_registered.c1_selftests([("planted-stub", [stub_suite], 8)],
                                   sources={"other": "0" * 64})
        expect_red("C1 rejects a suite absent from a present source golden",
                   lambda: any(c == "C1" and "no source digest recorded" in d
                               for c, d in c1_registered.failures))
        c1_bound = Run(td, ci=True)
        c1_bound.c1_selftests([("planted-stub", [stub_suite], 8)],
                              sources=planted_sources("planted-stub", stub_suite))
        expect_red("C1 source-binding control: a matching digest still runs the suite",
                   lambda: not any("recorded source digest" in d
                                   for _c, d in c1_bound.failures))
        expect_red("C1 floor control: the same suite exactly at its floor stays green",
                   lambda: not c1_at_floor.failures)

        os.makedirs(os.path.join(td, "tools"))
        open(os.path.join(td, "tools", "unregistered.py"), "w").write(
            "def selftest():\n    return 0\n"
        )
        c1_inventory = Run(td, ci=True)
        c1_inventory.c1_selftest_inventory(suites=[], exemptions={})
        expect_red("C1 rejects an unclassified selftest-capable script",
                   lambda: any(c == "C1" and "unclassified" in d
                               for c, d in c1_inventory.failures))

        vocab_root = os.path.join(td, "vocab")
        skill_root = os.path.join(vocab_root, "skills", "gamma")
        reference_root = os.path.join(skill_root, "references", "nested")
        for relative in (reference_root, os.path.join(skill_root, "evals"),
                         os.path.join(skill_root, "scripts"),
                         os.path.join(skill_root, "assets")):
            os.makedirs(relative)
        anchor = ("Self-assessment carrying no technical sense is banned outright: "
                  "*looks good*, *should work*, *solid*, *perfect*, *all set*. "
                  "Clean and verified stay usable.\n")
        agents_contract = (
            anchor + C11_SCOPE_DECLARATION + "\n" + C11_EXCLUSION_DECLARATION + "\n"
            + C11_MATCH_DECLARATION + "\n"
        )
        open(os.path.join(vocab_root, "AGENTS.md"), "w").write(agents_contract)
        open(os.path.join(vocab_root, "CLAUDE.md"), "w").write("@AGENTS.md\n")
        skill_manifest = os.path.join(skill_root, "SKILL.md")
        safe_skill = (
            "---\nname: gamma\ndescription: ok\n---\n\nThe tree is clean, the head is "
            "verified, and the scoped deliverable is ready and done.\n"
        )
        open(skill_manifest, "w").write(safe_skill)
        near_miss = os.path.join(reference_root, "near-miss.md")
        open(near_miss, "w").write(
            "solidarity perfectly all setter\n"
            "This looks **good**.\n"
            "This process looks\n\nGood evidence remains necessary.\n"
            "Unicode near-miss: ſolid.\n"
            "Unicode separator near-miss: looks\u00a0good.\n"
        )
        for relative in ("evals/case.md", "scripts/case.yaml", "assets/case.yml"):
            open(os.path.join(skill_root, relative), "w").write("looks good\n")
        c11_clean = Run(vocab_root, ci=True)
        c11_clean.c11_claim_vocabulary()
        expect_red(
            "C11 control: declared lexical near-misses and excluded trees stay green",
            lambda: not c11_clean.failures,
        )

        nested_yaml = os.path.join(reference_root, "policy.yaml")
        open(nested_yaml, "w").write("message: SHOULD WORK\n")
        c11_reference_hit = Run(vocab_root, ci=True)
        c11_reference_hit.c11_claim_vocabulary()
        expect_red(
            "C11 discovers a nested YAML reference and matches phrases case-insensitively",
            lambda: any(c == "C11" and "should work" in d and "policy.yaml" in d
                        for c, d in c11_reference_hit.failures),
        )
        open(nested_yaml, "w").write("message: evidence required\n")

        open(nested_yaml, "w").write("message: looks\n  good\n")
        c11_soft_wrap = Run(vocab_root, ci=True)
        c11_soft_wrap.c11_claim_vocabulary()
        expect_red(
            "C11 matches a multiword banned phrase across Markdown-style whitespace",
            lambda: any(c == "C11" and "looks good" in d and "policy.yaml" in d
                        for c, d in c11_soft_wrap.failures),
        )
        open(nested_yaml, "w").write("message: evidence required\n")

        open(skill_manifest, "w").write(safe_skill + "\nThis looks good to me.\n")
        c11_skill_hit = Run(vocab_root, ci=True)
        c11_skill_hit.c11_claim_vocabulary()
        expect_red(
            "C11 goes red when a skill manifest uses an exact banned phrase",
            lambda: any(c == "C11" and "looks good" in d
                        for c, d in c11_skill_hit.failures),
        )
        open(skill_manifest, "w").write(safe_skill)

        os.remove(os.path.join(vocab_root, "CLAUDE.md"))
        c11_missing_root = Run(vocab_root, ci=True)
        c11_missing_root.c11_claim_vocabulary()
        expect_red(
            "C11 fails loud when a required root file disappears",
            lambda: any(c == "C11" and "CLAUDE.md unreadable" in d
                        for c, d in c11_missing_root.failures),
        )
        open(os.path.join(vocab_root, "CLAUDE.md"), "w").write("@AGENTS.md\n")

        agents_fixture = os.path.join(vocab_root, "AGENTS.md")
        external_agents = os.path.join(td, "external-AGENTS.md")
        open(external_agents, "w").write(agents_contract)
        os.remove(agents_fixture)
        os.symlink(external_agents, agents_fixture)
        c11_symlinked_agents = Run(vocab_root, ci=True)
        c11_symlinked_agents.c11_claim_vocabulary()
        expect_red(
            "C11 fails loud when AGENTS.md escapes the repo through a symlink",
            lambda: any(c == "C11" and "AGENTS.md unreadable" in d and "symlinked" in d
                        for c, d in c11_symlinked_agents.failures),
        )
        os.unlink(agents_fixture)
        open(agents_fixture, "w").write(agents_contract)

        open(os.path.join(vocab_root, "AGENTS.md"), "w").write(
            anchor + C11_EXCLUSION_DECLARATION + "\n" + C11_MATCH_DECLARATION + "\n"
        )
        c11_scope = Run(vocab_root, ci=True)
        c11_scope.c11_claim_vocabulary()
        expect_red(
            "C11 fails loud when its governed-scope declaration is missing",
            lambda: any(c == "C11" and "missing scope declaration" in d
                        for c, d in c11_scope.failures),
        )

        open(os.path.join(vocab_root, "AGENTS.md"), "w").write(
            anchor + C11_SCOPE_DECLARATION + "\n" + C11_EXCLUSION_DECLARATION + "\n"
        )
        c11_match_scope = Run(vocab_root, ci=True)
        c11_match_scope.c11_claim_vocabulary()
        expect_red(
            "C11 fails loud when its lexical matcher declaration is missing",
            lambda: any(c == "C11" and "missing scope declaration" in d
                        and "source-lexical" in d for c, d in c11_match_scope.failures),
        )

        open(os.path.join(vocab_root, "AGENTS.md"), "w").write(
            C11_SCOPE_DECLARATION + "\n" + C11_EXCLUSION_DECLARATION + "\n"
            + C11_MATCH_DECLARATION + "\n"
        )
        c11_anchor = Run(vocab_root, ci=True)
        c11_anchor.c11_claim_vocabulary()
        expect_red("C11 fails loud when its own anchor is missing, never silently clean",
                   lambda: any(c == "C11" and "cannot enforce" in d
                               for c, d in c11_anchor.failures))
        open(os.path.join(vocab_root, "AGENTS.md"), "w").write(agents_contract)

        # Splitting the anchor into two sentences preserves the meaning and halves the
        # list, because the sentence regex stops at the first period. This is the attack
        # that put three banned phrases in a governed file with the gate fully green.
        shrunk_contract = re.sub(
            re.escape(BANNED_VOCAB_ANCHOR) + r"([^.]*)\.",
            lambda m: (BANNED_VOCAB_ANCHOR
                       + m.group(1).split(",")[0] + ". Also banned outright are"
                       + ",".join(m.group(1).split(",")[1:]) + "."),
            agents_contract,
            count=1,
        )
        open(os.path.join(vocab_root, "AGENTS.md"), "w").write(shrunk_contract)
        c11_shrunk = Run(vocab_root, ci=True)
        c11_shrunk.c11_claim_vocabulary()
        swapped_contract = agents_contract.replace("*perfect*", "*zorblat*", 1)
        open(os.path.join(vocab_root, "AGENTS.md"), "w").write(swapped_contract)
        c11_swapped = Run(vocab_root, ci=True)
        c11_swapped.c11_claim_vocabulary()
        expect_red(
            "C11 floors content, not only cardinality: a swapped phrase is caught",
            lambda: any(c == "C11" and "no longer bans" in d
                        for c, d in c11_swapped.failures),
        )
        open(os.path.join(vocab_root, "AGENTS.md"), "w").write(agents_contract)

        # Either floor may catch this: the content floor names the dropped phrases, the
        # cardinality floor names the count. Asserting one message made the proof fail when
        # the other fired first, which says nothing about whether the reword was refused.
        expect_red(
            "C11 fails loud when a reworded anchor silently shrinks the ban list",
            lambda: any(
                c == "C11" and "cannot enforce" in d
                and ("floor is" in d or "no longer bans" in d)
                for c, d in c11_shrunk.failures
            ),
        )
        open(os.path.join(vocab_root, "AGENTS.md"), "w").write(agents_contract)

        open(os.path.join(vocab_root, "AGENTS.md"), "w").write(
            agents_contract.replace(
                "*all set*.", "*all set*; nevertheless, say looks good.", 1
            )
        )
        c11_same_sentence = Run(vocab_root, ci=True)
        c11_same_sentence.c11_claim_vocabulary()
        expect_red(
            "C11 scans non-declaration text inside the banned-list sentence",
            lambda: any(c == "C11" and "looks good" in d
                        for c, d in c11_same_sentence.failures),
        )
        open(os.path.join(vocab_root, "AGENTS.md"), "w").write(agents_contract)

        callsite = Run(td, ci=True)
        called = []
        expected_registry = (
            ("C1", "c1_selftests"), ("C1", "c1_selftest_inventory"),
            ("C2", "c2_shared_identity"), ("C3", "c3_reference_resolution"),
            ("C4", "c4_descriptions"), ("C5", "c5_bodies"),
            ("C6", "c6_stale_patterns"), ("C7", "c7_anchors"),
            ("C8", "c8_reserved_basenames"), ("C9", "c9_codex_package"),
            ("C10", "c10_delivery_contract"), ("C11", "c11_claim_vocabulary"),
        )
        expect_red("production check registry is exact through C11",
                   lambda: PRODUCTION_CHECKS == expected_registry)
        method_names = [method_name for _check_id, method_name in expected_registry]
        for method_name in method_names:
            setattr(callsite, method_name, lambda name=method_name: called.append(name))
        callsite.run()
        expect_red("Run.run invokes the exact production check registry",
                   lambda: called == method_names)

        open(nested_yaml, "w").write("message: all set\n")
        production_c11 = Run(vocab_root, ci=True)
        for _check_id, method_name in PRODUCTION_CHECKS:
            if method_name != "c11_claim_vocabulary":
                setattr(production_c11, method_name, lambda: None)
        production_code = production_c11.run()
        expect_red(
            "Run.run reaches C11 and rejects a planted reference defect",
            lambda: production_code == 1
            and any(c == "C11" and "all set" in d
                    for c, d in production_c11.failures),
        )
        open(nested_yaml, "w").write("message: evidence required\n")

        hooks_stripped = os.path.join(td, "no-hooks")
        os.makedirs(hooks_stripped, exist_ok=True)
        open(os.path.join(hooks_stripped, "settings.json"), "w").write('{"hooks": {}}')
        for rel in ROUTING_SKILLS:
            os.makedirs(os.path.join(hooks_stripped, "skills", rel), exist_ok=True)
        c7_nohooks = Run(hooks_stripped, ci=True)
        try:
            c7_nohooks.c7_anchors()
        except Exception:
            pass
        decoy_root = os.path.join(td, "decoy-hooks")
        os.makedirs(decoy_root, exist_ok=True)
        open(os.path.join(decoy_root, "settings.json"), "w").write(json.dumps({"hooks": {
            "PreToolUse": [{"matcher": "Bash", "hooks": [
                {"type": "command", "command": "true", "timeout": 5}]}],
            "PostToolUse": [{"matcher": "AskUserQuestion", "hooks": [
                {"type": "command", "command": "true", "timeout": 5}]}],
        }}))
        for skill in ROUTING_SKILLS:
            os.makedirs(os.path.join(decoy_root, "skills", skill), exist_ok=True)
        c7_decoy = Run(decoy_root, ci=True)
        try:
            c7_decoy.c7_anchors()
        except Exception:
            pass
        expect_red(
            "C7 rejects handlers registered on the right events that run the wrong thing",
            lambda: sum(1 for c, d in c7_decoy.failures
                        if c == "C7" and d.startswith("settings.json ")
                        and "0 match(es)" in d) == len(REQUIRED_CLAUDE_HANDLERS),
        )
        expect_red("C7 goes red when settings.json registers no Claude guard",
                   lambda: any(c == "C7" and "0 match(es)" in d
                               for c, d in c7_nohooks.failures))

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
        r2.c4_descriptions()
        r2.c5_bodies()
        expect_red("C4 discovers a new skill and rejects its 500-char description",
                   lambda: any(c == "C4" and "alpha" in d for c, d in r2.failures))
        expect_red("C5 discovers a new skill and rejects its 6,000-char body",
                   lambda: any(c == "C5" and "alpha" in d for c, d in r2.failures))
        authoring_fixture = os.path.join(td, "authoring-over-line-cap.md")
        open(authoring_fixture, "w").write("\n".join(["line"] * (BODY_LINE_CAP + 1)))
        authoring_run = Run(td, ci=True)
        ok, lines = authoring_body_within_cap(authoring_fixture)
        authoring_run.result("C5", ok, f"authoring: {lines}")
        expect_red("C5 goes red on an authoring skill over the line cap",
                   lambda: any(c == "C5" for c, _d in authoring_run.failures))
        r3 = Run(td, ci=True)
        r3.c6_stale_patterns(scan_floor=1)
        expect_red("C6 goes red on planted stale pattern",
                   lambda: any(c == "C6" and "NOT INSTALLED" in d for c, d in r3.failures))
        os.makedirs(os.path.join(td, "docs"))
        open(os.path.join(td, "docs", "relocated.md"), "w").write("committed to the PR")
        r3_docs = Run(td, ci=True)
        r3_docs.c6_stale_patterns(scan_floor=1)
        expect_red("C6 scans docs and goes red on a relocated stale claim",
                   lambda: any(c == "C6" and "committed to the PR" in d
                               for c, d in r3_docs.failures))
        empty_c6 = os.path.join(td, "empty-c6")
        os.makedirs(empty_c6)
        c6_empty_run = Run(empty_c6, ci=True)
        c6_empty_run.c6_stale_patterns(scan_floor=1)
        expect_red("C6 goes red on a zero-file scan",
                   lambda: any(c == "C6" and "scan set shrank to 0" in d
                               for c, d in c6_empty_run.failures))
        c6_shrunk = Run(td, ci=True)
        c6_shrunk.c6_stale_patterns(scan_floor=99)
        expect_red("C6 goes red when its scan set shrinks below its floor",
                   lambda: any(c == "C6" and "floor 99" in d
                               for c, d in c6_shrunk.failures))
        # The scan set used to be a hardcoded directory tuple, so a stale claim in a
        # tracked root file was invisible. Prove the derived set reaches one.
        open(os.path.join(td, "statusline.sh"), "w").write("#!/bin/sh\n# ph-lint\n")
        r3_root = Run(td, ci=True)
        r3_root.c6_stale_patterns(scan_floor=1)
        expect_red("C6 reaches a tracked root file outside any scanned directory",
                   lambda: any(c == "C6" and "ph-lint" in d for c, d in r3_root.failures))
        os.remove(os.path.join(td, "statusline.sh"))

        r4 = Run(td, ci=True)
        r4.c8_reserved_basenames()
        expect_red("C8 goes red on nested claude.md",
                   lambda: any(c == "C8" for c, d in r4.failures))
        # `.git` was matched as a substring, which also excluded `.github/` — the one
        # directory whose CLAUDE.md a runtime would auto-load and a reviewer least expects.
        os.makedirs(os.path.join(td, ".github", "workflows"), exist_ok=True)
        open(os.path.join(td, ".github", "CLAUDE.md"), "w").write("planted")
        r4_github = Run(td, ci=True)
        r4_github.c8_reserved_basenames()
        expect_red("C8 sees .github/, which a .git substring filter excluded",
                   lambda: any(c == "C8" and ".github/CLAUDE.md" in d
                               for c, d in r4_github.failures))
        os.remove(os.path.join(td, ".github", "CLAUDE.md"))
        c8_empty = os.path.join(td, "empty-c8")
        os.makedirs(c8_empty, exist_ok=True)
        c8_empty_run = Run(c8_empty, ci=True)
        c8_empty_run.c8_reserved_basenames()
        expect_red("C8 goes red on a zero-file scan",
                   lambda: any(c == "C8" and "zero files" in d
                               for c, d in c8_empty_run.failures))
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
            ("underscore audit directory", "nested/harness_audit-20260801/record.md"),
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

    # +1 for this assertion's own increment, so SELFTEST_FLOOR is the number the receipt
    # prints. Comparing the pre-increment count made the floor one less than the reported
    # total, which reads as a wrong floor every time either number is updated.
    observed = checks + 1
    expect_red(
        f"meta-suite runs at least its recorded floor of {SELFTEST_FLOOR} proofs "
        f"(receipt will report {observed})",
        lambda: observed >= SELFTEST_FLOOR,
    )

    print(f"\n  selftest: {bad} failure(s)")
    print(f"SELFTEST-SUMMARY suite=harness_check checks={checks} failures={bad}")
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
