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
      [local] original audit paths and askq anchors hold, and every repository-owned
      Claude-installed skill payload matches its complete reviewed source tree
  C8  reserved context basenames (CLAUDE.md/AGENTS.md/GEMINI.md) exist nowhere but
      the repo root across tracked and authored-untracked files; nested Git ownership
      boundaries are pruned and `.git` is matched as a component, not a substring
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
import io
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import time

VERSION = "3.2.0"
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
SELFTEST_FLOOR = 160
# This pin gives the current package a reviewable release identity. Update it with the
# manifest when the next release is deliberately cut; C9 rejects a one-sided edit.
CURRENT_PLUGIN_VERSION = "0.3.1"

AUTHORING_SKILLS = {"craft-prompt", "craft-skill", "craft-context-file", "review-prompt"}
BODY_CHAR_CAP = 5000          # chars after frontmatter — the builders' instrument
BODY_LINE_CAP = 500           # authoring skills (spec cap)
DESC_CAP = 400                # house cap (spec ceiling is 1024)

# (name, command, floor). The floor is a shrink-only ratchet: a suite reporting fewer
# checks than its floor goes red. Without it a receipt of checks=1 reads the same as
# checks=111, so a suite can be gutted with nothing failing. Raise a floor in the same
# commit that adds the checks; lowering one is a deliberate, reviewable edit.
SELFTEST_SUITES = [
    ("bash_command_guard", ["hooks/bash_command_guard.py", "--selftest"], 1366),
    ("askq_timeout_guard", ["hooks/askq_timeout_guard.py", "--selftest"], 13),
    ("harness_report", ["hooks/harness_report.py", "--selftest"], 12),
    ("cc-cost", ["tools/cc-cost.py", "--selftest"], 8),
    ("codex-cost", ["tools/codex-cost.py", "--selftest"], 28),
    ("claim-provenance", ["tools/claim-provenance.py", "--selftest"], 42),
    ("pr-delivery-state", ["tools/pr-delivery-state.py", "--selftest"], 8),
    ("verify-review-publication",
     ["tools/verify-review-publication.py", "--selftest"], 57),
    ("run-skill-evals", ["tools/run-skill-evals.py", "--selftest"], 3),
    ("render-packages", ["tools/render-packages.py", "--selftest"], 192),
    ("ci-gate", ["tools/ci-gate.py", "--selftest"], 247),
    ("write-mutation-receipt",
     ["tools/write-mutation-receipt.py", "--selftest"], 59),
    ("portable-conformance", ["tools/portable-conformance.py", "--selftest"], 65),
    ("codex_session_start", ["hooks/codex_session_start.py", "--selftest"], 32),
    ("spawn_preflight_guard", ["hooks/spawn_preflight_guard.py", "--selftest"], 16),
    ("git_grep_engine_guard", ["hooks/guards/git_grep_engine_guard.py", "--selftest"], 1149),
    ("zsh_rev_modifier_guard", ["hooks/guards/zsh_rev_modifier_guard.py", "--selftest"], 487),
]


def expected_selftest_checks(name):
    """Exact execution-derived counts for suites whose former formulas hid probes."""
    if name == "bash_command_guard":
        return 1366
    if name == "zsh_rev_modifier_guard":
        return 487
    if name != "git_grep_engine_guard":
        return None
    binaries, seen = [], set()
    for directory in (os.environ.get("PATH") or "").split(os.pathsep):
        if not directory:
            continue
        resolved = shutil.which("git", path=directory)
        if not resolved:
            continue
        real = os.path.realpath(resolved)
        if real not in seen:
            seen.add(real)
            binaries.append(real)
    # The portable corpus is 1149 checks for one Git. Every additional executable adds
    # one version probe, one fixture setup, and 22 alias-proof-name probes.
    return 1149 + 24 * (max(1, len(binaries)) - 1)
# The public Bash-guard selftest intentionally runs five independent process-level timing
# observations for each runtime. Give that aggregate suite enough wall-clock without
# weakening the five-second deadline each individual hook process must meet.
# Registered where the 15 s default leaves no headroom for a slower runner. Measured
# on the authoring host: bash_command_guard 27 s, git_grep_engine_guard 7.3 s (its
# byte-cap, token and subcommand fixtures parse real megabyte-scale sources, and it
# probes the installed git and zsh), ci-gate 20.8 s. C1 requires each to finish inside
# SELFTEST_TIMEOUT_MARGIN of its budget, so these are ceilings with room, not targets.
SELFTEST_TIMEOUTS = {
    "bash_command_guard": 90,
    "git_grep_engine_guard": 60,
    "ci-gate": 60,
}
DEFAULT_SELFTEST_TIMEOUT = 15
# A suite may use this much of its registered timeout before C1 says so. Without it the
# timeout was a number nothing checked: setting the Bash suite's to 15 -- below its
# measured runtime -- left the whole harness selftest green, because the only assertion
# re-derived the expected value from this table.
SELFTEST_TIMEOUT_MARGIN = 0.6
# Non-aggregated, and why. The discovery above matches any file carrying the STRING
# "--selftest", which cannot tell a script that exposes one from a script that invokes
# one. The remaining entry is the recursive case; anything else that lands in this dict
# is a suite dodging aggregation. Invoking other suites is not by itself grounds for an
# exemption, and the mutation generator held one on that reasoning while its own kill
# scoring went unmeasured: an under-generating plan moves plan_sha256, which the gate
# recomputes, but a mis-scored kill leaves every shard agreeing and the re-measurement
# reproducing the same verdict. It is aggregated above over that scoring.
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


def child_faults(stdout, limit=2):
    """-> the failing child's own FAIL lines, so a red suite says WHICH check failed.

    This layer keeps a suite's receipt and drops its stdout, so `failures=1` reached the
    record with nothing naming the check behind it. A suite that improves its own failure
    text gains nothing in CI while that text is captured here and never printed: one
    occurrence read as `failures=1` in the log while the guard's explanation sat in a
    buffer nobody emitted, and attributing it cost a source read and a reproduction.

    Cut at a word boundary. A slice cut a child's reason at "internal decision " and dropped
    `budget`, the one word naming the cause, and this is the copy CI records -- the suite's
    own line does not survive to the log at all.
    """
    def clip(text, limit=220):
        text = " ".join(text.split())
        if len(text) <= limit:
            return text
        cut = text[:limit].rsplit(" ", 1)[0]
        return f"{cut or text[:limit]}..."

    lines = [line.decode("utf-8", "replace").strip()
             for line in stdout.splitlines()
             if line.strip().startswith(b"FAIL")]
    if not lines:
        return ""
    shown = "; ".join(clip(line) for line in lines[:limit])
    more = f"; and {len(lines) - limit} more" if len(lines) > limit else ""
    return f"; child reported: {shown}{more}"


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


def git_command_failure(returncode, stderr, command="git ls-files"):
    """Describe a nonzero Git exit, naming the code even when the child said nothing.

    The exit status is the failure signal; the child's stderr is only the detail. Reading
    the signal off `stderr.strip()` instead made every silent nonzero exit — `1` with an
    empty stream, or a negative code from a signal — indistinguishable from success at the
    call site, which then skipped its failure handling and worked on an inventory it never
    got. Naming the code keeps a broken instrument legible when it produced no text.
    """
    if isinstance(stderr, (bytes, bytearray)):
        detail = bytes(stderr).decode("utf-8", "replace").strip()
    else:
        detail = (stderr or "").strip()
    if detail:
        return f"{command} exited {returncode}: {detail}"
    return f"{command} exited {returncode} with no diagnostic on stderr"


_GIT_REPOSITORY_ENV = frozenset({
    "GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_IMPLICIT_WORK_TREE", "GIT_GRAFT_FILE", "GIT_NO_REPLACE_OBJECTS",
    "GIT_REPLACE_REF_BASE", "GIT_PREFIX", "GIT_INTERNAL_SUPER_PREFIX",
    "GIT_SHALLOW_FILE",
    "GIT_CEILING_DIRECTORIES", "GIT_DISCOVERY_ACROSS_FILESYSTEM",
    "GIT_NAMESPACE",
})


def sanitized_git_environment(source=None):
    """Remove ambient repository/config selectors from one Git subprocess."""
    env = dict(os.environ if source is None else source)
    for key in tuple(env):
        if (key in _GIT_REPOSITORY_ENV or key == "GIT_CONFIG"
                or key.startswith("GIT_CONFIG_")):
            del env[key]
    return env


def run_git(runner, argv, **kwargs):
    """Run Git without allowing ambient state to substitute another repository."""
    kwargs["env"] = sanitized_git_environment(kwargs.get("env"))
    return runner(argv, **kwargs)


def _same_file(left, right):
    """Return whether two path spellings identify the same filesystem object."""
    try:
        return os.path.samefile(left, right)
    except OSError:
        return False


def _git_toplevel_error(root, runner):
    """Return why Git did not resolve exactly the repository root it was given."""
    try:
        done = run_git(
            runner, ["git", "-C", root, "rev-parse", "--show-toplevel"],
            capture_output=True, text=False)
    except OSError as exc:
        return f"cannot run git rev-parse --show-toplevel: {exc}"
    if done.returncode != 0:
        return git_command_failure(
            done.returncode, done.stderr, "git rev-parse --show-toplevel")
    raw = bytes(done.stdout)
    if not raw.endswith(b"\n") or b"\0" in raw:
        return "git rev-parse --show-toplevel returned a malformed path"
    value = raw[:-1]
    if value.endswith(b"\r"):
        value = value[:-1]
    reported = os.fsdecode(value)
    if not _same_file(reported, root):
        return (
            "git rev-parse --show-toplevel resolved "
            f"{reported!r}, expected {os.path.realpath(root)!r}"
        )
    return ""


def package_paths(root, runner=None):
    """Return (surface, paths, error) for source or installed package contents."""
    runner = subprocess.run if runner is None else runner
    if os.path.exists(os.path.join(root, ".git")):
        problem = _git_toplevel_error(root, runner)
        if problem:
            return "source", [], problem
        try:
            tracked = run_git(
                runner,
                ["git", "-C", root, "ls-files"], capture_output=True, text=True,
            )
        except OSError as exc:
            # Git absent from PATH raised FileNotFoundError out through every caller, so
            # the gate died with a traceback and no verdict line. An unusable instrument
            # is a named failure of the checks that depend on it.
            return "source", [], f"cannot run git ls-files: {exc}"
        if tracked.returncode != 0:
            return "source", [], git_command_failure(tracked.returncode, tracked.stderr)
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


def skill_payload_manifest(root, required_names=None):
    """Return the full regular-file payload owned by repository skill directories."""
    errors = []
    if not os.path.isdir(root) or os.path.islink(root):
        return (), {}, [f"skill root is absent, symlinked, or not a directory: {root}"]
    if required_names is None:
        entries = list(os.scandir(root))
        errors.extend(
            f"source skill entry is symlinked: {entry.name}"
            for entry in entries if entry.is_symlink()
        )
        names = tuple(sorted(
            entry.name for entry in entries
            if entry.is_dir(follow_symlinks=False)
        ))
    else:
        names = tuple(sorted(required_names))
    if not names:
        return names, {}, ["zero source-owned skill directories"]
    manifest = {}
    for name in names:
        skill_root = os.path.join(root, name)
        if os.path.islink(skill_root) or not os.path.isdir(skill_root):
            errors.append(f"{name}: skill directory is absent, symlinked, or not a directory")
            continue
        skill_md = os.path.join(skill_root, "SKILL.md")
        if os.path.islink(skill_md) or not os.path.isfile(skill_md):
            errors.append(f"{name}: SKILL.md is absent, symlinked, or not a regular file")
        for dirpath, dirs, files in os.walk(skill_root, followlinks=False):
            retained = []
            for directory in sorted(dirs):
                path = os.path.join(dirpath, directory)
                if os.path.islink(path):
                    errors.append(
                        f"{name}: directory symlink {os.path.relpath(path, skill_root)}")
                else:
                    retained.append(directory)
            dirs[:] = retained
            for filename in sorted(files):
                path = os.path.join(dirpath, filename)
                relative = os.path.relpath(path, skill_root).replace(os.sep, "/")
                if os.path.islink(path) or not os.path.isfile(path):
                    errors.append(f"{name}: non-regular payload {relative}")
                    continue
                try:
                    data = open(path, "rb").read()
                    mode = os.stat(path, follow_symlinks=False).st_mode
                except OSError as exc:
                    errors.append(f"{name}: cannot read {relative}: {exc}")
                    continue
                manifest[f"{name}/{relative}"] = (
                    len(data), hashlib.sha256(data).hexdigest(),
                    bool(mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)),
                )
    return names, manifest, errors


def installed_skill_payload_error(source_root, installed_root):
    """Return why the live installed payload differs from the repository-owned skills."""
    names, source, errors = skill_payload_manifest(source_root)
    _installed_names, installed, installed_errors = skill_payload_manifest(
        installed_root, required_names=names)
    errors.extend(installed_errors)
    missing = sorted(set(source) - set(installed))
    extra = sorted(set(installed) - set(source))
    drifted = sorted(
        path for path in set(source) & set(installed)
        if source[path] != installed[path]
    )
    if missing:
        errors.append(f"missing payload: {missing}")
    if extra:
        errors.append(f"stale payload: {extra}")
    if drifted:
        errors.append(f"drifted payload: {drifted}")
    return "; ".join(errors)


def _git_path_line(path, prefix=b""):
    """Read one Git metadata path, removing only its final line terminator."""
    try:
        raw = open(path, "rb").read()
    except OSError:
        return None
    if not raw.startswith(prefix):
        return None
    value = raw[len(prefix):]
    if not value.endswith(b"\n") or b"\0" in value:
        return None
    value = value[:-1]
    if value.endswith(b"\r"):
        value = value[:-1]
    return os.fsdecode(value)


def _gitdir_from_marker(path, marker):
    if os.path.isdir(marker):
        return os.path.realpath(marker)
    if not os.path.isfile(marker):
        return None
    pointer = _git_path_line(marker, b"gitdir: ")
    if pointer is None:
        return None
    return os.path.realpath(
        pointer if os.path.isabs(pointer) else os.path.join(path, pointer))


def _git_common_dir(admin):
    pointer = _git_path_line(os.path.join(admin, "commondir"))
    if pointer is None:
        return admin
    return os.path.realpath(
        pointer if os.path.isabs(pointer) else os.path.join(admin, pointer))


def _indexed_gitlink(path, owner_root, runner):
    if owner_root is None:
        return False
    relative = os.path.relpath(path, owner_root).replace(os.sep, "/")
    if relative == ".." or relative.startswith("../"):
        return False
    staged = run_git(
        runner,
        ["git", "-C", owner_root, "ls-files", "--stage", "-z", "--", relative],
        capture_output=True, text=False)
    if staged.returncode != 0:
        return False
    for record in bytes(staged.stdout).split(b"\0"):
        metadata, separator, recorded_path = record.partition(b"\t")
        if (separator and metadata.startswith(b"160000 ")
                and recorded_path.decode("utf-8", "surrogateescape") == relative):
            return True
    return False


def _registered_linked_worktree(path, marker):
    """Prove a linked worktree from Git's reciprocal registration metadata."""
    admin = _gitdir_from_marker(path, marker)
    if admin is None:
        return False
    common_pointer = _git_path_line(os.path.join(admin, "commondir"))
    if common_pointer is None:
        return False
    common = _git_common_dir(admin)
    if not _same_file(os.path.dirname(admin), os.path.join(common, "worktrees")):
        return False
    backlink = _git_path_line(os.path.join(admin, "gitdir"))
    if backlink is None:
        return False
    backlink = os.path.realpath(
        backlink if os.path.isabs(backlink) else os.path.join(admin, backlink))
    return _same_file(backlink, marker)


def _bound_separate_gitdir(path, marker, runner):
    """Accept an external gitdir only when its own config binds this worktree."""
    admin = _gitdir_from_marker(path, marker)
    if admin is None or not os.path.isdir(admin):
        return False
    # A linked-worktree admin is owned by its reciprocal registration. It cannot
    # become an independent separate gitdir merely because another marker points at it.
    if (os.path.lexists(os.path.join(admin, "commondir"))
            or os.path.lexists(os.path.join(admin, "gitdir"))):
        return False
    configured = run_git(
        runner,
        ["git", "--git-dir", admin, "config", "--local", "--path", "--null",
         "--get-all", "core.worktree"], capture_output=True, text=False)
    raw = bytes(configured.stdout)
    if configured.returncode != 0 or not raw.endswith(b"\0") or raw.count(b"\0") != 1:
        return False
    worktree = os.fsdecode(raw[:-1])
    if not os.path.isabs(worktree):
        worktree = os.path.join(admin, worktree)
    return _same_file(worktree, path)


def _is_git_worktree_root(path, runner, owner_root=None):
    marker = os.path.join(path, ".git")
    if not os.path.lexists(marker) or os.path.islink(marker):
        return False
    if _git_toplevel_error(path, runner):
        return False
    if os.path.isdir(marker):
        return True
    if not os.path.isfile(marker):
        return False
    return (_indexed_gitlink(path, owner_root, runner)
            or _registered_linked_worktree(path, marker)
            or _bound_separate_gitdir(path, marker, runner))


def _below_nested_git_boundary(root, relative, runner):
    parts = relative.replace(os.sep, "/").split("/")[:-1]
    current = root
    for part in parts:
        current = os.path.join(current, part)
        if _is_git_worktree_root(current, runner, root):
            return True
    return False


def _walk_owned_files(root, start, runner):
    """Walk one owned directory, pruning only registered nested Git worktrees."""
    retained, pruned = [], 0
    for dirpath, dirs, files in os.walk(start, followlinks=False):
        kept = []
        for directory in sorted(dirs):
            path = os.path.join(dirpath, directory)
            relative = os.path.relpath(path, root)
            if directory == ".git":
                continue
            if os.path.islink(path):
                retained.append(relative)
            elif _is_git_worktree_root(path, runner, root):
                pruned += 1
            else:
                kept.append(directory)
        dirs[:] = kept
        for filename in sorted(files):
            path = os.path.join(dirpath, filename)
            if os.path.isfile(path) or os.path.islink(path):
                retained.append(os.path.relpath(path, root))
    return retained, pruned


def _expand_git_inventory_group(root, relatives, runner):
    """Expand Git-collapsed directories unless a registered worktree owns them."""
    retained, pruned = [], 0
    for relative in dict.fromkeys(relatives):
        path = os.path.join(root, relative)
        if _below_nested_git_boundary(root, relative, runner):
            pruned += 1
            continue
        if os.path.isdir(path) and not os.path.islink(path):
            if _is_git_worktree_root(path, runner, root):
                pruned += 1
                continue
            walked, nested_pruned = _walk_owned_files(root, path, runner)
            retained.extend(walked)
            pruned += nested_pruned
        elif os.path.isfile(path) or os.path.islink(path):
            retained.append(relative)
    return list(dict.fromkeys(retained)), pruned


def _outer_indexed_live_paths(root, relatives, runner):
    """Retain indexed files; validate or walk indexed directory entries."""
    retained, pruned = [], 0
    for relative in dict.fromkeys(relatives):
        path = os.path.join(root, relative)
        if os.path.isfile(path) or os.path.islink(path):
            retained.append(relative)
        elif os.path.isdir(path):
            if _is_git_worktree_root(path, runner, root):
                pruned += 1
            else:
                walked, nested_pruned = _walk_owned_files(root, path, runner)
                retained.extend(walked)
                pruned += nested_pruned
    return list(dict.fromkeys(retained)), pruned


def _git_inventory_failure(error, surface="git"):
    """A named, fail-closed inventory. C8 prints this rather than raising through Run."""
    return {
        "surface": surface,
        "tracked": 0,
        "untracked": 0,
        "ignored_context": 0,
        "pruned": 0,
        "paths": (),
        "error": error,
    }


def git_owned_live_paths(root, runner=None):
    """Inventory committed and authored-untracked files, pruning nested Git ownership.

    Every way this inventory can fail leaves by the `error` key. Two ways used to leave by
    raising instead, which cost the caller its whole verdict: the gate exited on a
    traceback with no summary line, so a broken instrument and a real violation looked
    nothing alike and neither was named.
    """
    runner = subprocess.run if runner is None else runner
    if os.path.lexists(os.path.join(root, ".git")):
        problem = _git_toplevel_error(root, runner)
        if problem:
            return _git_inventory_failure(problem)
    groups = []
    failed = False
    failure = ""
    queries = (
        ("--cached",),
        ("--others", "--exclude-standard"),
        ("--others", "--ignored", "--exclude-standard", "--",
         ":(icase,glob)**/agents.md", ":(icase,glob)**/claude.md",
         ":(icase,glob)**/gemini.md"),
    )
    for args in queries:
        try:
            done = run_git(
                runner,
                ["git", "-C", root, "ls-files", "-z", *args],
                capture_output=True, text=False)
        except OSError as exc:
            # A `git` that cannot be launched cannot enumerate anything, and the
            # filesystem fallback below needs the same binary to find ownership
            # boundaries. Say so and stop, rather than raising or walking blind.
            return _git_inventory_failure(f"cannot run git ls-files: {exc}")
        if done.returncode != 0:
            # The exit status decides, not the presence of stderr text. Deriving the
            # decision from a stripped stderr read a silent nonzero exit as success,
            # left `groups` empty, and died indexing it.
            groups = []
            failed = True
            failure = git_command_failure(done.returncode, done.stderr)
            break
        groups.append([
            item.decode("utf-8", "surrogateescape")
            for item in bytes(done.stdout).split(b"\0") if item
        ])
    surface = "git"
    if failed and os.path.lexists(os.path.join(root, ".git")):
        return _git_inventory_failure(failure)
    try:
        if failed:
            surface = "filesystem"
            walked, pruned = _walk_owned_files(root, root, runner)
            groups = [walked, [], []]
        else:
            pruned = 0
        expanded = []
        for index, group in enumerate(groups):
            if surface == "git" and index == 0:
                paths, group_pruned = _outer_indexed_live_paths(root, group, runner)
                expanded.append(paths)
                pruned += group_pruned
                continue
            paths, group_pruned = _expand_git_inventory_group(root, group, runner)
            expanded.append(paths)
            pruned += group_pruned
    except OSError as exc:
        # Ownership resolution shells out to `git` per candidate boundary, so the binary
        # can still go away after enumeration succeeded.
        return _git_inventory_failure(f"cannot resolve Git ownership: {exc}", surface)
    groups = expanded
    retained = list(dict.fromkeys(groups[0] + groups[1] + groups[2]))
    return {
        "surface": surface,
        "tracked": len(groups[0]),
        "untracked": len(groups[1]),
        "ignored_context": len(groups[2]),
        "pruned": pruned,
        "paths": tuple(retained),
        "error": "",
    }


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
        of each suite is pinned. Under the reviewed workflow and authentic runners, an
        isolated suite replacement cannot merely claim to have run. A coordinated edit to
        the workflow, runners, and authored digest registry remains a reviewer or external
        required-workflow trust boundary rather than an in-repo self-attestation.
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
                timeout = SELFTEST_TIMEOUTS.get(name, DEFAULT_SELFTEST_TIMEOUT)
                started = time.monotonic()
                p = subprocess.run(
                    [sys.executable, os.path.join(self.root, cmd[0])] + cmd[1:],
                    capture_output=True, cwd=self.root, timeout=timeout,
                )
                elapsed = time.monotonic() - started
            except subprocess.TimeoutExpired:
                self.result("C1", False,
                            f"selftest {name}: exceeded {timeout}s")
                continue
            # A registered timeout is a claim about the suite, and nothing checked it
            # against the suite. Requiring the margin on the host that actually runs it
            # is the non-circular form: a suite that grows into its budget reddens here
            # instead of timing out on the first slower runner.
            if elapsed > timeout * SELFTEST_TIMEOUT_MARGIN:
                self.result("C1", False,
                            f"selftest {name}: took {elapsed:.1f}s of its registered "
                            f"{timeout}s, past the {SELFTEST_TIMEOUT_MARGIN:.0%} margin; "
                            f"make the suite faster or raise the timeout deliberately")
                continue
            receipts = re.findall(
                rb"^SELFTEST-SUMMARY suite=([a-z0-9_-]+) checks=(\d+) failures=(\d+)$",
                p.stdout,
                re.M,
            )
            final_line = p.stdout.rstrip().splitlines()[-1] if p.stdout.rstrip() else b""
            exact_checks = expected_selftest_checks(name)
            count_ok = (
                int(receipts[0][1]) == exact_checks
                if len(receipts) == 1 and exact_checks is not None
                else len(receipts) == 1 and int(receipts[0][1]) >= floor
            )
            receipt_ok = (
                len(receipts) == 1
                and receipts[0][0].decode("ascii") == name
                and count_ok
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
                           f"exact={exact_checks if exact_checks is not None else 'n/a'} "
                           f"failures={int(receipts[0][2])} "
                           f"final={final_line.startswith(b'SELFTEST-SUMMARY ')}")
                if int(receipts[0][1]) < floor:
                    detail += " below-floor"
                elif exact_checks is not None and int(receipts[0][1]) != exact_checks:
                    detail += " wrong-exact-count"
            passed = p.returncode == 0 and receipt_ok
            if not passed:
                detail += child_faults(p.stdout)
            self.result("C1", passed, detail)

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
    def c7_claude_installed_skill_payload(self, source_root=None, installed_root=None):
        source_root = source_root or os.path.join(self.root, "skills")
        installed_root = installed_root or os.path.expanduser("~/.claude/skills")
        problem = installed_skill_payload_error(source_root, installed_root)
        self.result(
            "C7", not problem,
            "[local] complete Claude-installed skill payload under ~/.claude/skills "
            "matches reviewed source"
            + (f": {problem}" if problem else ""),
        )

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
            # The repository owns every payload file below its skill directories, while
            # unrelated top-level installed skills remain outside this comparison. Missing
            # roots, manifests, references, evals, scripts, stale files, symlinks, byte
            # drift, and executable-bit drift all fail. CI proves the helper's red arms;
            # only local mode claims to inspect the live installation.
            self.c7_claude_installed_skill_payload()

    # ---- C8 ----------------------------------------------------------------
    def c8_reserved_basenames(self, runner=None):
        """A reserved context basename anywhere but the repo root is auto-loaded instructions.

        The exclusion is the `.git` directory itself, matched as a path component. A
        substring test also excluded `.github/`, where a planted CLAUDE.md passed while the
        identical bytes under docs/ failed — so the one directory a reviewer is least
        likely to read was the one place the guard could not see.
        """
        inventory = git_owned_live_paths(self.root, runner=runner)
        if inventory["error"]:
            self.result("C8", False,
                        f"cannot enumerate Git-owned scan set: {inventory['error']}")
            return
        hits = []
        for name in inventory["paths"]:
            if os.path.basename(name).lower() in RESERVED_BASENAMES:
                if os.path.dirname(name):
                    hits.append(name)
        scanned = len(inventory["paths"])
        if not scanned:
            self.result("C8", False, "zero files in scan set")
            return
        self.result("C8", not hits,
                    f"reserved basenames outside root over {scanned} "
                    f"{inventory['surface']} files "
                    f"(tracked={inventory['tracked']} untracked={inventory['untracked']} "
                    f"ignored-context={inventory['ignored_context']} "
                    f"nested-boundary-pruned={inventory['pruned']}): {hits or 'none'}")

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
        self.result("C9", manifest.get("version") == CURRENT_PLUGIN_VERSION,
                    f"manifest version is the reviewed release: "
                    f"{manifest.get('version')!r} == {CURRENT_PLUGIN_VERSION!r}")
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

    # A suite reports `failures=1` and this layer kept only that. The child's own FAIL line
    # is the diagnosis and was being dropped, so improving a suite's failure text bought
    # nothing where it is read.
    expect_red(
        "a failing child's own FAIL line reaches the C1 detail",
        lambda: (
            "operator-budget" in child_faults(
                b"  PASS unrelated\n"
                b"  FAIL operator-budget claude decided ask; budget exhausted\n"
                b"SELFTEST-SUMMARY suite=x checks=1 failures=1\n")
            and child_faults(
                b"  PASS all good\nSELFTEST-SUMMARY suite=x checks=1 failures=0\n") == ""
            and "and 1 more" in child_faults(
                b"  FAIL one\n  FAIL two\n  FAIL three\n", limit=2)
        ),
    )
    # The cut lands on a whole word or the one word naming the cause is what gets dropped.
    expect_red(
        "a surfaced child line is cut at a word boundary, never mid-word",
        lambda: (
            lambda body: body.endswith("...") and body[:-3].rstrip().endswith("alpha")
        )(child_faults(b"  FAIL " + b"alpha " * 80 + b"budget\n")
          .split("child reported: ", 1)[1]),
    )

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

        observed_timeouts = []
        original_subprocess_run = subprocess.run
        def record_c1_timeout(*args, **kwargs):
            observed_timeouts.append(kwargs.get("timeout"))
            return subprocess.CompletedProcess(
                args[0], 0,
                b"SELFTEST-SUMMARY suite=bash_command_guard checks=1366 failures=0\n",
                b"")
        subprocess.run = record_c1_timeout
        try:
            c1_timeout = Run(td, ci=True)
            c1_timeout.c1_selftests(
                [("bash_command_guard", [stub_suite], 1)],
                sources=planted_sources("bash_command_guard", stub_suite))
        finally:
            subprocess.run = original_subprocess_run
        # 90 is a literal here on purpose. Reading it back out of SELFTEST_TIMEOUTS
        # re-derived the expected value from the table under test: setting the Bash
        # suite's timeout to 15 -- below its measured runtime -- left this green.
        expect_red(
            "C1 gives the process-level Bash timing suite its registered aggregate timeout",
            lambda: observed_timeouts == [90] and not c1_timeout.failures,
        )
        expect_red(
            "the registered Bash timeout is still the one this check asserts",
            lambda: SELFTEST_TIMEOUTS["bash_command_guard"] == 90,
        )
        expect_red(
            "the registered CI-gate timeout retains measured headroom",
            lambda: SELFTEST_TIMEOUTS["ci-gate"] == 60,
        )

        slow_timeouts = []
        def slow_run(*args, **kwargs):
            slow_timeouts.append(kwargs.get("timeout"))
            time.sleep(0.05)
            return subprocess.CompletedProcess(
                args[0], 0,
                b"SELFTEST-SUMMARY suite=bash_command_guard checks=1366 failures=0\n",
                b"")
        subprocess.run = slow_run
        try:
            c1_margin = Run(td, ci=True)
            c1_margin.c1_selftests(
                [("bash_command_guard", [stub_suite], 1)],
                sources=planted_sources("bash_command_guard", stub_suite),
                )
        finally:
            subprocess.run = original_subprocess_run
        margin_clean = not c1_margin.failures
        original_margin = globals()["SELFTEST_TIMEOUT_MARGIN"]
        original_registered = SELFTEST_TIMEOUTS["bash_command_guard"]
        subprocess.run = slow_run
        SELFTEST_TIMEOUTS["bash_command_guard"] = 0.05
        try:
            c1_tight = Run(td, ci=True)
            c1_tight.c1_selftests(
                [("bash_command_guard", [stub_suite], 1)],
                sources=planted_sources("bash_command_guard", stub_suite))
        finally:
            subprocess.run = original_subprocess_run
            SELFTEST_TIMEOUTS["bash_command_guard"] = original_registered
            globals()["SELFTEST_TIMEOUT_MARGIN"] = original_margin
        expect_red(
            "C1 reddens when a suite grows into its registered timeout",
            lambda: margin_clean and bool(c1_tight.failures)
            and any("margin" in detail for _check, detail in c1_tight.failures),
        )

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

        # C6 and C9 both enumerate through package_paths. `git ls-files` failing there is a
        # broken instrument, and the check has to say which one: an empty stderr is no
        # evidence of success, and a `git` that will not launch raised straight through the
        # check rather than being reported by it.
        scan_repo = os.path.join(td, "scan-set-repo")
        os.makedirs(scan_repo)
        open(os.path.join(scan_repo, ".git"), "w").write("gitdir: elsewhere\n")
        open(os.path.join(scan_repo, "README.md"), "w").write("root\n")
        real_subprocess_run = subprocess.run

        def with_patched_run(replacement, call):
            subprocess.run = replacement
            try:
                return call()
            finally:
                subprocess.run = real_subprocess_run

        def silent_git_scan(args, **kwargs):
            if list(args[:1]) == ["git"]:
                return subprocess.CompletedProcess(args, 3, stdout="", stderr="")
            return real_subprocess_run(args, **kwargs)

        def unlaunchable_git_scan(args, **kwargs):
            if list(args[:1]) == ["git"]:
                raise FileNotFoundError(2, "No such file or directory", "git")
            return real_subprocess_run(args, **kwargs)

        def c6_names_a_silent_git_exit():
            def probe():
                _surface, paths, error = package_paths(scan_repo)
                run = Run(scan_repo, ci=True)
                run.c6_stale_patterns(scan_floor=1)
                return paths, error, run
            paths, error, run = with_patched_run(silent_git_scan, probe)
            return (paths == [] and "exited 3" in (error or "")
                    and any(c == "C6" and "cannot enumerate scan set" in d
                            and "exited 3" in d for c, d in run.failures))

        expect_red(
            "C6 names a silent nonzero git ls-files exit, never an unexplained scan set",
            c6_names_a_silent_git_exit,
        )

        def c6_names_an_unlaunchable_git():
            def probe():
                _surface, _paths, error = package_paths(scan_repo)
                run = Run(scan_repo, ci=True)
                run.c6_stale_patterns(scan_floor=1)
                return error, run
            error, run = with_patched_run(unlaunchable_git_scan, probe)
            return ("cannot run git rev-parse --show-toplevel" in (error or "")
                    and any(c == "C6" and "cannot enumerate scan set" in d
                            and "cannot run git rev-parse --show-toplevel" in d
                            for c, d in run.failures))

        expect_red(
            "C6 reports an unlaunchable git as a named failure, never as an exception",
            c6_names_an_unlaunchable_git,
        )

        hostile_git_env = {
            key: "planted" for key in (
                *_GIT_REPOSITORY_ENV, "GIT_CONFIG", "GIT_CONFIG_COUNT",
                "GIT_CONFIG_KEY_0", "GIT_CONFIG_VALUE_0", "GIT_CONFIG_PARAMETERS",
                "GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM", "GIT_CONFIG_NOSYSTEM",
            )
        }
        hostile_git_env.update(PATH="retained", Z_HARNESS_SENTINEL="retained",
                               GIT_AUTHOR_NAME="retained")
        scrubbed_git_env = sanitized_git_environment(hostile_git_env)
        expect_red(
            "Git subprocesses discard repository and config selectors but retain benign env",
            lambda: (set(hostile_git_env) - set(scrubbed_git_env)
                     == set(hostile_git_env) - {
                         "PATH", "Z_HARNESS_SENTINEL", "GIT_AUTHOR_NAME"}
            and scrubbed_git_env == {
                "PATH": "retained", "Z_HARNESS_SENTINEL": "retained",
                "GIT_AUTHOR_NAME": "retained"}),
        )

        # C7 owns every file below each repository skill directory in Claude's installed
        # skill root. That root may contain unrelated top-level skills, but no reviewed file
        # may disappear, drift, or gain a stale installed sibling without making the local
        # comparison red.
        skill_fixture = os.path.join(td, "skill-payload")
        source_skills = os.path.join(skill_fixture, "source")
        installed_skills = os.path.join(skill_fixture, "installed")

        def reset_skill_payload():
            shutil.rmtree(skill_fixture, ignore_errors=True)
            for root in (source_skills, installed_skills):
                os.makedirs(os.path.join(root, "alpha", "references"))
                open(os.path.join(root, "alpha", "SKILL.md"), "w").write("# alpha\n")
                open(os.path.join(root, "alpha", "references", "rule.md"), "w").write(
                    "rule\n")

        reset_skill_payload()
        expect_red("C7 full-payload control accepts an exact installed skill tree",
                   lambda: installed_skill_payload_error(
                       source_skills, installed_skills) == "")
        empty_source = os.path.join(skill_fixture, "empty-source")
        os.makedirs(empty_source)
        expect_red("C7 rejects zero source-owned skill directories",
                   lambda: "zero source-owned" in installed_skill_payload_error(
                       empty_source, installed_skills))
        expect_red("C7 rejects an absent installed skill root",
                   lambda: "skill root is absent" in installed_skill_payload_error(
                       source_skills, os.path.join(skill_fixture, "absent")))

        reset_skill_payload()
        os.symlink("alpha", os.path.join(source_skills, "source-alias"))
        expect_red("C7 rejects a symlinked source skill entry",
                   lambda: "source skill entry is symlinked" in
                   installed_skill_payload_error(source_skills, installed_skills))
        reset_skill_payload()
        os.remove(os.path.join(source_skills, "alpha", "SKILL.md"))
        expect_red("C7 rejects a source skill without SKILL.md",
                   lambda: "alpha: SKILL.md is absent" in installed_skill_payload_error(
                       source_skills, installed_skills))
        reset_skill_payload()
        os.remove(os.path.join(installed_skills, "alpha", "SKILL.md"))
        expect_red("C7 rejects an installed skill without SKILL.md",
                   lambda: "alpha: SKILL.md is absent" in installed_skill_payload_error(
                       source_skills, installed_skills))
        reset_skill_payload()
        os.remove(os.path.join(installed_skills, "alpha", "references", "rule.md"))
        expect_red("C7 rejects a missing installed support file",
                   lambda: "missing payload" in installed_skill_payload_error(
                       source_skills, installed_skills))
        reset_skill_payload()
        open(os.path.join(installed_skills, "alpha", "stale.md"), "w").write("stale\n")
        expect_red("C7 rejects a stale file inside a managed installed skill",
                   lambda: "stale payload" in installed_skill_payload_error(
                       source_skills, installed_skills))
        reset_skill_payload()
        open(os.path.join(installed_skills, "alpha", "references", "rule.md"), "w").write(
            "different\n")
        expect_red("C7 rejects support-file byte drift",
                   lambda: "drifted payload" in installed_skill_payload_error(
                       source_skills, installed_skills))
        reset_skill_payload()
        os.chmod(os.path.join(installed_skills, "alpha", "SKILL.md"), 0o755)
        expect_red("C7 rejects executable-class drift",
                   lambda: "drifted payload" in installed_skill_payload_error(
                       source_skills, installed_skills))
        reset_skill_payload()
        os.makedirs(os.path.join(installed_skills, "unmanaged"))
        open(os.path.join(installed_skills, "unmanaged", "SKILL.md"), "w").write(
            "# unmanaged\n")
        expect_red("C7 ignores unrelated top-level installed skills",
                   lambda: installed_skill_payload_error(
                       source_skills, installed_skills) == "")
        reset_skill_payload()
        os.symlink("rule.md", os.path.join(
            installed_skills, "alpha", "references", "alias.md"))
        expect_red("C7 rejects symlinked payload",
                   lambda: "non-regular payload" in installed_skill_payload_error(
                       source_skills, installed_skills))
        reset_skill_payload()
        os.remove(os.path.join(installed_skills, "alpha", "references", "rule.md"))
        c7_payload_run = Run(td, ci=False)
        c7_payload_run.c7_claude_installed_skill_payload(source_skills, installed_skills)
        expect_red("C7 production call adopts the full-payload failure",
                   lambda: any(c == "C7" and "missing payload" in d
                               for c, d in c7_payload_run.failures))

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

        live_repo = os.path.join(td, "live-context-repo")
        os.makedirs(live_repo)
        subprocess.run(["git", "init", "--quiet", live_repo], check=True)
        open(os.path.join(live_repo, "README.md"), "w").write("root\n")
        subprocess.run(["git", "-C", live_repo, "add", "README.md"], check=True)
        subprocess.run(
            ["git", "-C", live_repo, "-c", "user.name=fixture", "-c",
             "user.email=fixture@example.invalid", "commit", "--quiet", "-m", "fixture"],
            check=True)
        os.makedirs(os.path.join(live_repo, "docs"))
        open(os.path.join(live_repo, "docs", "AGENTS.md"), "w").write("untracked\n")
        live_run = Run(live_repo, ci=True)
        live_run.c8_reserved_basenames()
        expect_red("C8 Git mode catches an authored untracked nested context file",
                   lambda: any(c == "C8" and "docs/AGENTS.md" in d
                               for c, d in live_run.failures))

        decoy_repo = os.path.join(td, "ambient-git-decoy")
        os.makedirs(decoy_repo)
        subprocess.run(["git", "init", "--quiet", decoy_repo], check=True)
        open(os.path.join(decoy_repo, "README.md"), "w").write("decoy\n")
        subprocess.run(["git", "-C", decoy_repo, "add", "README.md"], check=True)
        stale_path = os.path.join(live_repo, "stale.md")
        open(stale_path, "w").write("NOT INSTALLED\n")
        subprocess.run(["git", "-C", live_repo, "add", "stale.md"], check=True)

        def with_ambient_git_decoy(call):
            keys = ("GIT_DIR", "GIT_WORK_TREE", "GIT_CONFIG_COUNT",
                    "GIT_CONFIG_KEY_0", "GIT_CONFIG_VALUE_0")
            previous = {key: os.environ.get(key) for key in keys}
            os.environ.update({
                "GIT_DIR": os.path.join(decoy_repo, ".git"),
                "GIT_WORK_TREE": decoy_repo,
                "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": "core.worktree",
                "GIT_CONFIG_VALUE_0": decoy_repo,
            })
            try:
                return call()
            finally:
                for key, value in previous.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value

        contaminated_c8 = with_ambient_git_decoy(
            lambda: Run(live_repo, ci=True))
        with_ambient_git_decoy(contaminated_c8.c8_reserved_basenames)
        expect_red(
            "C8 inspects its explicit root despite ambient Git repository substitution",
            lambda: (any(c == "C8" and "docs/AGENTS.md" in d
                         for c, d in live_run.failures)
                     and any(c == "C8" and "docs/AGENTS.md" in d
                             for c, d in contaminated_c8.failures)),
        )
        control_c6 = Run(live_repo, ci=True)
        control_c6.c6_stale_patterns(scan_floor=1)
        contaminated_c6 = Run(live_repo, ci=True)
        with_ambient_git_decoy(
            lambda: contaminated_c6.c6_stale_patterns(scan_floor=1))
        expect_red(
            "C6 inspects its explicit root despite ambient Git repository substitution",
            lambda: (any(c == "C6" and "NOT INSTALLED" in d
                         for c, d in control_c6.failures)
                     and any(c == "C6" and "NOT INSTALLED" in d
                             for c, d in contaminated_c6.failures)),
        )

        def wrong_toplevel(args, **kwargs):
            if (list(args[:2]) == ["git", "-C"]
                    and os.path.realpath(args[2]) == os.path.realpath(live_repo)
                    and list(args[3:]) == ["rev-parse", "--show-toplevel"]):
                return subprocess.CompletedProcess(
                    args, 0, stdout=os.fsencode(decoy_repo) + b"\n", stderr=b"")
            return subprocess.run(args, **kwargs)

        wrong_root_inventory = git_owned_live_paths(live_repo, runner=wrong_toplevel)
        expect_red(
            "C8 rejects an inventory whose successful Git probe names another root",
            lambda: (not wrong_root_inventory["paths"]
                     and "resolved" in wrong_root_inventory["error"]
                     and os.path.realpath(live_repo) in wrong_root_inventory["error"]),
        )
        wrong_root_surface, wrong_root_paths, wrong_root_error = package_paths(
            live_repo, runner=wrong_toplevel)
        expect_red(
            "C6 rejects package enumeration whose successful Git probe names another root",
            lambda: (wrong_root_surface == "source" and not wrong_root_paths
                     and "resolved" in wrong_root_error
                     and os.path.realpath(live_repo) in wrong_root_error),
        )

        def missing_toplevel(args, **kwargs):
            if (list(args[:2]) == ["git", "-C"]
                    and os.path.realpath(args[2]) == os.path.realpath(live_repo)
                    and list(args[3:]) == ["rev-parse", "--show-toplevel"]):
                return subprocess.CompletedProcess(
                    args, 0, stdout=os.fsencode(
                        os.path.join(td, "missing-repository-root")) + b"\n",
                    stderr=b"")
            return subprocess.run(args, **kwargs)

        expect_red(
            "C8 treats an unstatable reported top level as a mismatch, never authority",
            lambda: "resolved" in _git_toplevel_error(live_repo, missing_toplevel),
        )

        def unterminated_toplevel(args, **kwargs):
            if (list(args[:2]) == ["git", "-C"]
                    and os.path.realpath(args[2]) == os.path.realpath(live_repo)
                    and list(args[3:]) == ["rev-parse", "--show-toplevel"]):
                return subprocess.CompletedProcess(
                    args, 0, stdout=os.fsencode(live_repo) + b"x", stderr=b"")
            return subprocess.run(args, **kwargs)

        def nul_toplevel(args, **kwargs):
            if (list(args[:2]) == ["git", "-C"]
                    and os.path.realpath(args[2]) == os.path.realpath(live_repo)
                    and list(args[3:]) == ["rev-parse", "--show-toplevel"]):
                return subprocess.CompletedProcess(
                    args, 0, stdout=os.fsencode(live_repo) + b"\0junk\n", stderr=b"")
            return subprocess.run(args, **kwargs)

        expect_red(
            "C8 rejects an unterminated top-level path whose final byte masks as a terminator",
            lambda: "malformed path" in _git_toplevel_error(
                live_repo, unterminated_toplevel),
        )
        expect_red(
            "C8 rejects an embedded NUL in the reported top-level path",
            lambda: "malformed path" in _git_toplevel_error(live_repo, nul_toplevel),
        )

        case_alias = os.path.join(
            os.path.dirname(live_repo), os.path.basename(live_repo).swapcase())
        case_alias_supported = (
            sys.platform != "darwin"
            or (os.path.isdir(case_alias) and os.path.samefile(case_alias, live_repo))
        )
        expect_red(
            "C8 case-alias fixture names the same directory on case-insensitive macOS",
            lambda: case_alias_supported,
        )
        case_alias_surface = case_alias_paths = case_alias_error = None
        case_alias_inventory = None
        if sys.platform == "darwin" and case_alias_supported:
            case_alias_surface, case_alias_paths, case_alias_error = package_paths(case_alias)
            case_alias_inventory = git_owned_live_paths(case_alias)
        expect_red(
            "C6 and C8 accept filesystem-identical root spellings on macOS",
            lambda: (sys.platform != "darwin"
                     or (case_alias_supported
                         and _git_toplevel_error(case_alias, subprocess.run) == ""
                         and case_alias_surface == "source"
                         and not case_alias_error and bool(case_alias_paths)
                         and not case_alias_inventory["error"]
                         and bool(case_alias_inventory["paths"]))),
        )

        def failed_git_inventory(_args, **_kwargs):
            return subprocess.CompletedProcess(_args, 1, stdout=b"", stderr=b"planted")

        failed_inventory_run = Run(live_repo, ci=True)
        failed_inventory_run.c8_reserved_basenames(runner=failed_git_inventory)
        expect_red("C8 fails closed when Git-owned scan enumeration fails",
                   lambda: any(c == "C8" and "cannot enumerate" in d
                               for c, d in failed_inventory_run.failures))

        # stderr carries the detail; the exit status carries the verdict. A nonzero exit
        # over an empty or whitespace-only stream took neither failure branch, so the
        # inventory stayed empty, indexing it ended the process on a traceback, and no
        # HARNESS-SUMMARY line was printed at all -- a broken instrument reading as
        # neither a pass nor a named failure.
        def silent_git_inventory(_args, **_kwargs):
            return subprocess.CompletedProcess(_args, 1, stdout=b"", stderr=b"")

        def whitespace_git_inventory(_args, **_kwargs):
            return subprocess.CompletedProcess(_args, -9, stdout=b"", stderr=b"  \n\t ")

        def unlaunchable_git_inventory(_args, **_kwargs):
            raise FileNotFoundError(2, "No such file or directory", "git")

        def c8_names_a_silent_git_exit():
            run = Run(live_repo, ci=True)
            run.c8_reserved_basenames(runner=silent_git_inventory)
            return any(c == "C8" and "cannot enumerate" in d and "exited 1" in d
                       for c, d in run.failures)

        expect_red(
            "C8 names a silent nonzero git ls-files exit instead of indexing an empty "
            "inventory",
            c8_names_a_silent_git_exit,
        )

        def c8_reads_whitespace_stderr_as_failure():
            run = Run(live_repo, ci=True)
            run.c8_reserved_basenames(runner=whitespace_git_inventory)
            return any(c == "C8" and "cannot enumerate" in d and "exited -9" in d
                       for c, d in run.failures)

        expect_red(
            "C8 reads whitespace-only git stderr as failure, never as a clean inventory",
            c8_reads_whitespace_stderr_as_failure,
        )

        def c8_names_an_unlaunchable_git():
            run = Run(live_repo, ci=True)
            run.c8_reserved_basenames(runner=unlaunchable_git_inventory)
            return any(c == "C8" and "cannot enumerate" in d
                       and "cannot run git rev-parse --show-toplevel" in d
                       for c, d in run.failures)

        expect_red(
            "C8 names an unlaunchable git binary instead of propagating OSError",
            c8_names_an_unlaunchable_git,
        )

        # Failing closed on the exit status may not cost the check its non-Git surface: a
        # silent failure outside a worktree still has to reach the filesystem fallback.
        def c8_keeps_its_filesystem_fallback_on_a_silent_failure():
            fallback = os.path.join(td, "silent-failure-fallback")
            os.makedirs(os.path.join(fallback, "sub"), exist_ok=True)
            open(os.path.join(fallback, "README.md"), "w").write("root\n")
            open(os.path.join(fallback, "sub", "CLAUDE.md"), "w").write("nested\n")
            run = Run(fallback, ci=True)
            run.c8_reserved_basenames(runner=silent_git_inventory)
            return any(c == "C8" and "sub/CLAUDE.md" in d and "filesystem files" in d
                       for c, d in run.failures)

        expect_red(
            "C8 still reaches its filesystem fallback when a silent git failure has no .git",
            c8_keeps_its_filesystem_fallback_on_a_silent_failure,
        )

        # The point of a named failure is the verdict line. Driving Run.run through the
        # broken instrument has to end in a HARNESS-SUMMARY receipt, not a traceback.
        def harness_summary_survives_a_broken_git_inventory():
            summary_run = Run(live_repo, ci=True)
            for _check_id, method_name in PRODUCTION_CHECKS:
                if method_name != "c8_reserved_basenames":
                    setattr(summary_run, method_name, lambda: None)
            summary_run.c8_reserved_basenames = (
                lambda: Run.c8_reserved_basenames(
                    summary_run, runner=silent_git_inventory))
            buffer = io.StringIO()
            original_stdout = sys.stdout
            sys.stdout = buffer
            try:
                code = summary_run.run()
            finally:
                sys.stdout = original_stdout
            return (code == 1
                    and "HARNESS-SUMMARY mode=ci checks=1 failures=1 exit=1"
                    in buffer.getvalue()
                    and any(c == "C8" and "exited 1" in d
                            for c, d in summary_run.failures))

        expect_red(
            "Run.run still prints HARNESS-SUMMARY when the Git inventory instrument fails",
            harness_summary_survives_a_broken_git_inventory,
        )

        os.remove(os.path.join(live_repo, "docs", "AGENTS.md"))
        nested_repo = os.path.join(live_repo, "nested-repo")
        os.makedirs(nested_repo)
        subprocess.run(["git", "init", "--quiet", nested_repo], check=True)
        open(os.path.join(nested_repo, "CLAUDE.md"), "w").write("other owner\n")
        nested_run = Run(live_repo, ci=True)
        nested_run.c8_reserved_basenames()
        expect_red("C8 prunes a nested repository boundary",
                   lambda: not nested_run.failures)

        # Ownership resolution shells out once per candidate boundary, so the binary can
        # still become unusable after enumeration already succeeded. The control above
        # proves this fixture reaches that call at all.
        def git_lost_during_resolution(args, **kwargs):
            if (list(args[:2]) == ["git", "-C"]
                    and os.path.realpath(args[2]) == os.path.realpath(nested_repo)
                    and list(args[3:5]) == ["rev-parse", "--show-toplevel"]):
                raise FileNotFoundError(2, "No such file or directory", "git")
            return subprocess.run(args, **kwargs)

        def c8_names_a_git_lost_while_resolving_ownership():
            run = Run(live_repo, ci=True)
            run.c8_reserved_basenames(runner=git_lost_during_resolution)
            return any(c == "C8" and "nested-repo/CLAUDE.md" in d
                       for c, d in run.failures)

        expect_red(
            "C8 retains a candidate whose ownership probe cannot launch Git",
            c8_names_a_git_lost_while_resolving_ownership,
        )

        def failed_exact_root(args, **kwargs):
            if (args[:2] == ["git", "-C"]
                    and os.path.realpath(args[2]) == os.path.realpath(nested_repo)
                    and args[3:] == ["rev-parse", "--show-toplevel"]):
                return subprocess.CompletedProcess(
                    args, 1, stdout=os.fsencode(nested_repo) + b"\n", stderr=b"planted")
            return subprocess.run(args, **kwargs)

        failed_exact_root_run = Run(live_repo, ci=True)
        failed_exact_root_run.c8_reserved_basenames(runner=failed_exact_root)
        expect_red("C8 rejects partial exact-root output from a failed Git command",
                   lambda: any(c == "C8" and "nested-repo/CLAUDE.md" in d
                               for c, d in failed_exact_root_run.failures))

        indexed_then_nested = os.path.join(live_repo, "indexed-then-nested")
        os.makedirs(indexed_then_nested)
        indexed_context = os.path.join(indexed_then_nested, "AGENTS.md")
        open(indexed_context, "w").write("outer owner\n")
        subprocess.run(
            ["git", "-C", live_repo, "add", "indexed-then-nested/AGENTS.md"],
            check=True)
        subprocess.run(["git", "init", "--quiet", indexed_then_nested], check=True)
        indexed_then_nested_run = Run(live_repo, ci=True)
        indexed_then_nested_run.c8_reserved_basenames()
        expect_red("C8 retains a live file still owned by the outer Git index",
                   lambda: any(c == "C8" and "indexed-then-nested/AGENTS.md" in d
                               for c, d in indexed_then_nested_run.failures))
        subprocess.run(
            ["git", "-C", live_repo, "rm", "--cached", "--quiet", "--force",
             "indexed-then-nested/AGENTS.md"], check=True)
        shutil.rmtree(indexed_then_nested)

        # The clause above decides an INDEXED path. A separate clause decides the untracked
        # ones by walking their parent components, and nothing reached it: Git does not
        # descend into a nested repository, so `--others` normally lists nothing below one
        # and that walk could be made inert with the whole suite green. Index a file inside
        # the directory first and Git does descend, so an untracked context file beside it
        # arrives in the inventory and only the parent-component walk keeps the nested
        # repository's own file out of the owner's scan set.
        below_boundary_owner = os.path.join(td, "below-boundary-owner")
        os.makedirs(os.path.join(below_boundary_owner, "nested"))
        subprocess.run(["git", "init", "--quiet", below_boundary_owner], check=True)
        open(os.path.join(below_boundary_owner, "README.md"), "w").write("root\n")
        open(os.path.join(below_boundary_owner, "nested", "keep.md"), "w").write(
            "outer owner\n")
        subprocess.run(
            ["git", "-C", below_boundary_owner, "add", "README.md", "nested/keep.md"],
            check=True)
        subprocess.run(
            ["git", "-C", below_boundary_owner, "-c", "user.name=fixture", "-c",
             "user.email=fixture@example.invalid", "commit", "--quiet", "-m", "fixture"],
            check=True)
        subprocess.run(
            ["git", "init", "--quiet", os.path.join(below_boundary_owner, "nested")],
            check=True)
        open(os.path.join(below_boundary_owner, "nested", "AGENTS.md"), "w").write(
            "other owner\n")
        below_boundary_others = subprocess.run(
            ["git", "-C", below_boundary_owner, "ls-files", "--others",
             "--exclude-standard", "-z"], capture_output=True).stdout
        below_boundary_run = Run(below_boundary_owner, ci=True)
        below_boundary_run.c8_reserved_basenames()
        # Without this the proof below passes over an empty inventory: if Git ever stops
        # descending here, nothing reaches the parent-component walk at all, and "pruned"
        # and "never enumerated" produce the same green.
        expect_red(
            "C8 below-boundary fixture really does enumerate the file below the boundary",
            lambda: b"nested/AGENTS.md" in below_boundary_others.split(b"\0"),
        )
        expect_red(
            "C8 prunes an untracked file below a boundary Git still descended into",
            lambda: not below_boundary_run.failures,
        )
        shutil.rmtree(below_boundary_owner)

        fake_boundary = os.path.join(live_repo, "fake-boundary")
        os.makedirs(fake_boundary)
        open(os.path.join(fake_boundary, ".git"), "w").write("not a repository\n")
        open(os.path.join(fake_boundary, "AGENTS.md"), "w").write("still owned here\n")
        fake_boundary_run = Run(live_repo, ci=True)
        fake_boundary_run.c8_reserved_basenames()
        expect_red("C8 does not let a fake .git marker prune authored context",
                   lambda: any(c == "C8" and "fake-boundary/AGENTS.md" in d
                               for c, d in fake_boundary_run.failures))
        shutil.rmtree(fake_boundary)

        invalid_directory = os.path.join(live_repo, "invalid-git-directory")
        os.makedirs(os.path.join(invalid_directory, ".git"))
        open(os.path.join(invalid_directory, "AGENTS.md"), "w").write(
            "still owned here\n")
        invalid_directory_run = Run(live_repo, ci=True)
        invalid_directory_run.c8_reserved_basenames()
        expect_red("C8 does not fall through an invalid .git directory to its owner",
                   lambda: any(c == "C8" and "invalid-git-directory/AGENTS.md" in d
                               for c, d in invalid_directory_run.failures))
        shutil.rmtree(invalid_directory)

        redirected_directory = os.path.join(live_repo, "redirected-git-directory")
        os.makedirs(redirected_directory)
        subprocess.run(
            ["git", "init", "--quiet", "--bare",
             os.path.join(redirected_directory, ".git")], check=True)
        subprocess.run(
            ["git", "--git-dir", os.path.join(redirected_directory, ".git"),
             "config", "core.bare", "false"], check=True)
        subprocess.run(
            ["git", "--git-dir", os.path.join(redirected_directory, ".git"),
             "config", "core.worktree", live_repo], check=True)
        open(os.path.join(redirected_directory, "GEMINI.md"), "w").write(
            "still owned here\n")
        redirected_directory_run = Run(live_repo, ci=True)
        redirected_directory_run.c8_reserved_basenames()
        expect_red("C8 rejects a nested gitdir whose worktree is the owner repository",
                   lambda: any(c == "C8" and "redirected-git-directory/GEMINI.md" in d
                               for c, d in redirected_directory_run.failures))
        shutil.rmtree(redirected_directory)

        forged_boundary = os.path.join(live_repo, "forged-boundary")
        os.makedirs(forged_boundary)
        open(os.path.join(forged_boundary, ".git"), "w").write("gitdir: ../.git\n")
        open(os.path.join(forged_boundary, "AGENTS.md"), "w").write("still owned here\n")
        forged_boundary_run = Run(live_repo, ci=True)
        forged_boundary_run.c8_reserved_basenames()
        expect_red("C8 rejects an unregistered .git pointer into the outer repository",
                   lambda: any(c == "C8" and "forged-boundary/AGENTS.md" in d
                               for c, d in forged_boundary_run.failures))
        shutil.rmtree(forged_boundary)

        linked = os.path.join(live_repo, "linked-worktree")
        subprocess.run(
            ["git", "-C", live_repo, "worktree", "add", "--quiet", "--detach",
             linked, "HEAD"], check=True)
        open(os.path.join(linked, "GEMINI.md"), "w").write("other owner\n")
        linked_run = Run(live_repo, ci=True)
        linked_run.c8_reserved_basenames()
        expect_red("C8 prunes a registered nested worktree boundary",
                   lambda: not linked_run.failures)
        linked_case_alias_run = Run(case_alias, ci=True)
        linked_case_alias_run.c8_reserved_basenames()
        expect_red(
            "C8 prunes registered linked worktrees through a case-alias owner root",
            lambda: sys.platform != "darwin" or not linked_case_alias_run.failures,
        )

        worktree_list_calls = []
        def no_worktree_list(args, **kwargs):
            if args[-4:] == ["worktree", "list", "--porcelain", "-z"]:
                worktree_list_calls.append(tuple(args))
                return subprocess.CompletedProcess(
                    args, 129, stdout=b"", stderr=b"error: unknown switch `z'\n")
            return subprocess.run(args, **kwargs)
        linked_portable_run = Run(live_repo, ci=True)
        linked_portable_run.c8_reserved_basenames(runner=no_worktree_list)
        expect_red("C8 linked-worktree proof does not require worktree-list -z support",
                   lambda: not linked_portable_run.failures and not worktree_list_calls)
        os.remove(os.path.join(linked, "GEMINI.md"))

        linked_trailing = os.path.join(live_repo, "linked-trailing ")
        subprocess.run(
            ["git", "-C", live_repo, "worktree", "add", "--quiet", "--detach",
             linked_trailing, "HEAD"], check=True)
        open(os.path.join(linked_trailing, "AGENTS.md"), "w").write("other owner\n")
        linked_trailing_run = Run(live_repo, ci=True)
        linked_trailing_run.c8_reserved_basenames()
        expect_red("C8 preserves trailing spaces in registered-worktree paths",
                   lambda: not linked_trailing_run.failures)
        os.remove(os.path.join(linked_trailing, "AGENTS.md"))

        linked_newline = os.path.join(live_repo, "linked-newline\n")
        subprocess.run(
            ["git", "-C", live_repo, "worktree", "add", "--quiet", "--detach",
             linked_newline, "HEAD"], check=True)
        open(os.path.join(linked_newline, "GEMINI.md"), "w").write("other owner\n")
        linked_newline_run = Run(live_repo, ci=True)
        linked_newline_run.c8_reserved_basenames()
        expect_red("C8 preserves trailing newlines in registered-worktree paths",
                   lambda: not linked_newline_run.failures)
        os.remove(os.path.join(linked_newline, "GEMINI.md"))

        linked_marker = os.path.join(linked, ".git")
        linked_admin = _gitdir_from_marker(linked, linked_marker)
        linked_common = os.path.join(linked_admin, "commondir")
        linked_common_bytes = open(linked_common, "rb").read()
        alias_common_supported = sys.platform != "darwin"
        if sys.platform == "darwin" and case_alias_supported:
            open(linked_common, "wb").write(
                os.fsencode(os.path.join(case_alias, ".git")) + b"\n")
            linked_git_probe = subprocess.run(
                ["git", "-C", linked, "rev-parse", "--show-toplevel"],
                capture_output=True)
            alias_common_run = Run(case_alias, ci=True)
            alias_common_run.c8_reserved_basenames()
            alias_common_supported = (
                linked_git_probe.returncode == 0
                and _registered_linked_worktree(linked, linked_marker)
                and not alias_common_run.failures)
            open(linked_common, "wb").write(linked_common_bytes)
        expect_red(
            "C8 accepts an absolute case-alias common-dir for a registered worktree",
            lambda: alias_common_supported,
        )
        linked_backlink = os.path.join(linked_admin, "gitdir")
        linked_backlink_bytes = open(linked_backlink, "rb").read()
        os.remove(linked_backlink)
        open(os.path.join(linked, "AGENTS.md"), "w").write("still owned here\n")
        missing_backlink_run = Run(live_repo, ci=True)
        missing_backlink_run.c8_reserved_basenames()
        expect_red("C8 rejects linked metadata without its reciprocal backlink",
                   lambda: any(c == "C8" and "linked-worktree/AGENTS.md" in d
                               for c, d in missing_backlink_run.failures))
        open(linked_backlink, "wb").write(linked_backlink_bytes)
        os.remove(os.path.join(linked, "AGENTS.md"))

        linked_metadata = (
            linked_marker,
            os.path.join(linked_admin, "commondir"),
            linked_backlink,
        )
        linked_metadata_bytes = {
            path: open(path, "rb").read() for path in linked_metadata
        }
        for path, data in linked_metadata_bytes.items():
            open(path, "wb").write(data[:-1] + b"\r\n")
        open(os.path.join(linked, "AGENTS.md"), "w").write("other owner\n")
        crlf_linked_run = Run(live_repo, ci=True)
        crlf_linked_run.c8_reserved_basenames()
        expect_red("C8 accepts Git-valid CRLF linked-worktree metadata",
                   lambda: not crlf_linked_run.failures)
        for path, data in linked_metadata_bytes.items():
            open(path, "wb").write(data)
        os.remove(os.path.join(linked, "AGENTS.md"))

        foreign_repo = os.path.join(td, "foreign-linked-owner")
        subprocess.run(["git", "init", "--quiet", foreign_repo], check=True)
        subprocess.run(
            ["git", "-C", foreign_repo, "-c", "user.name=fixture", "-c",
             "user.email=fixture@example.invalid", "commit", "--quiet",
             "--allow-empty", "-m", "fixture"], check=True)
        foreign_linked = os.path.join(td, "foreign-linked-worktree")
        subprocess.run(
            ["git", "-C", foreign_repo, "worktree", "add", "--quiet", "--detach",
             foreign_linked, "HEAD"], check=True)
        foreign_admin = _gitdir_from_marker(
            foreign_linked, os.path.join(foreign_linked, ".git"))
        borrowed_admin = os.path.join(live_repo, "borrowed-linked-admin")
        os.makedirs(borrowed_admin)
        open(os.path.join(borrowed_admin, ".git"), "wb").write(
            b"gitdir: " + os.fsencode(foreign_admin) + b"\n")
        open(os.path.join(borrowed_admin, "AGENTS.md"), "w").write(
            "still owned here\n")
        borrowed_admin_run = Run(live_repo, ci=True)
        borrowed_admin_run.c8_reserved_basenames()
        expect_red("C8 rejects a pointer borrowing another worktree's registered admin",
                   lambda: any(c == "C8" and "borrowed-linked-admin/AGENTS.md" in d
                               for c, d in borrowed_admin_run.failures))
        shutil.rmtree(borrowed_admin)
        subprocess.run(
            ["git", "-C", foreign_repo, "worktree", "remove", "--force",
             foreign_linked], check=True)
        shutil.rmtree(foreign_repo)

        # The rejection above holds because that admin has no `core.worktree` binding at
        # all, so the query below it fails and the reciprocal-registration clause guarding
        # it is never the reason. Bind one and they separate. `--local` on a linked
        # worktree's admin resolves to the repository's COMMON config, so the binding is
        # written there -- in the FOREIGN repository, leaving the owner's own worktree
        # resolution untouched -- and the borrowing directory then answers every question
        # an independently bound separate gitdir would. Only the clause that says a linked
        # admin is owned by its registration keeps it from pruning the tree.
        bound_foreign_repo = os.path.join(td, "bound-linked-owner")
        subprocess.run(["git", "init", "--quiet", bound_foreign_repo], check=True)
        subprocess.run(
            ["git", "-C", bound_foreign_repo, "-c", "user.name=fixture", "-c",
             "user.email=fixture@example.invalid", "commit", "--quiet",
             "--allow-empty", "-m", "fixture"], check=True)
        bound_foreign_linked = os.path.join(td, "bound-linked-worktree")
        subprocess.run(
            ["git", "-C", bound_foreign_repo, "worktree", "add", "--quiet", "--detach",
             bound_foreign_linked, "HEAD"], check=True)
        bound_foreign_admin = _gitdir_from_marker(
            bound_foreign_linked, os.path.join(bound_foreign_linked, ".git"))
        bound_borrowed = os.path.join(live_repo, "borrowed-bound-linked-admin")
        os.makedirs(bound_borrowed)
        open(os.path.join(bound_borrowed, ".git"), "wb").write(
            b"gitdir: " + os.fsencode(bound_foreign_admin) + b"\n")
        open(os.path.join(bound_borrowed, "AGENTS.md"), "w").write(
            "still owned here\n")
        subprocess.run(
            ["git", "-C", bound_foreign_repo, "config", "core.worktree",
             bound_borrowed], check=True)
        bound_borrowed_binding = subprocess.run(
            ["git", "--git-dir", bound_foreign_admin, "config", "--local", "--path",
             "--null", "--get-all", "core.worktree"], capture_output=True)
        bound_borrowed_run = Run(live_repo, ci=True)
        bound_borrowed_run.c8_reserved_basenames()
        # The binding has to actually be visible through that admin, or the rejection
        # below is the absent-binding rejection already proved above wearing a new name.
        expect_red(
            "C8 bound-linked fixture really does answer the separate-gitdir query",
            lambda: bound_borrowed_binding.returncode == 0
            and os.path.realpath(os.fsdecode(
                bytes(bound_borrowed_binding.stdout).rstrip(b"\0")))
            == os.path.realpath(bound_borrowed)
            and os.path.lexists(os.path.join(bound_foreign_admin, "commondir")),
        )
        expect_red(
            "C8 keeps a registered linked admin owned by its registration, not by a "
            "core.worktree binding",
            lambda: any(c == "C8" and "borrowed-bound-linked-admin/AGENTS.md" in d
                        for c, d in bound_borrowed_run.failures),
        )
        shutil.rmtree(bound_borrowed)
        subprocess.run(
            ["git", "-C", bound_foreign_repo, "worktree", "remove", "--force",
             bound_foreign_linked], check=True)
        shutil.rmtree(bound_foreign_repo)

        sibling_repo = os.path.join(live_repo, "sibling-ordinary-repository")
        subprocess.run(["git", "init", "--quiet", sibling_repo], check=True)
        borrowed_ordinary = os.path.join(live_repo, "borrowed-ordinary-admin")
        os.makedirs(borrowed_ordinary)
        open(os.path.join(borrowed_ordinary, ".git"), "wb").write(
            b"gitdir: " + os.fsencode(os.path.join(sibling_repo, ".git")) + b"\n")
        open(os.path.join(borrowed_ordinary, "AGENTS.md"), "w").write(
            "still owned here\n")
        borrowed_ordinary_run = Run(live_repo, ci=True)
        borrowed_ordinary_run.c8_reserved_basenames()
        expect_red("C8 rejects a pointer borrowing an ordinary repository's admin",
                   lambda: any(c == "C8" and "borrowed-ordinary-admin/AGENTS.md" in d
                               for c, d in borrowed_ordinary_run.failures))
        shutil.rmtree(borrowed_ordinary)
        shutil.rmtree(sibling_repo)

        # `borrowed-ordinary-admin` above carries the same `.git`-file-into-an-ordinary-
        # repository shape, but nothing records that directory in the owner's index, so
        # `ls-files --stage` returns no record at all and the index-mode comparison behind
        # it is never reached. Two conjuncts guard that comparison and each needs its own
        # tree, because a tree that reaches one leaves the other unasserted.
        #
        # First: a stale index TYPE. The owner recorded `sub` as a regular file and the
        # working tree now holds a directory there, so the pathspec yields a `100644`
        # record AT the queried path. Only the recorded mode separates that from a
        # submodule, and reading any mode as a gitlink prunes the directory whole.
        stale_type_owner = os.path.join(td, "stale-index-type-owner")
        stale_type_sibling = os.path.join(td, "stale-index-type-sibling")
        os.makedirs(stale_type_owner)
        for repository in (stale_type_owner, stale_type_sibling):
            subprocess.run(["git", "init", "--quiet", repository], check=True)
        open(os.path.join(stale_type_owner, "README.md"), "w").write("root\n")
        open(os.path.join(stale_type_owner, "sub"), "w").write("a regular file\n")
        subprocess.run(
            ["git", "-C", stale_type_owner, "add", "README.md", "sub"], check=True)
        subprocess.run(
            ["git", "-C", stale_type_owner, "-c", "user.name=fixture", "-c",
             "user.email=fixture@example.invalid", "commit", "--quiet", "-m", "fixture"],
            check=True)
        os.remove(os.path.join(stale_type_owner, "sub"))
        os.makedirs(os.path.join(stale_type_owner, "sub"))
        open(os.path.join(stale_type_owner, "sub", "CLAUDE.md"), "w").write(
            "still owned here\n")
        open(os.path.join(stale_type_owner, "sub", ".git"), "wb").write(
            b"gitdir: " + os.fsencode(os.path.join(stale_type_sibling, ".git")) + b"\n")
        stale_type_staged = subprocess.run(
            ["git", "-C", stale_type_owner, "ls-files", "--stage", "-z", "--", "sub"],
            capture_output=True).stdout
        stale_type_run = Run(stale_type_owner, ci=True)
        stale_type_run.c8_reserved_basenames()
        # Without this the proof above can degrade into agreement: a Git that stopped
        # producing the record, or a pathspec that stopped matching, leaves an empty
        # inventory that no mode comparison ever reads and the tree looks discriminating
        # while asserting nothing.
        expect_red(
            "C8 stale-index-type fixture records that path as a regular file, not a "
            "gitlink",
            lambda: stale_type_staged.startswith(b"100644 ")
            and stale_type_staged.rstrip(b"\0").endswith(b"\tsub"),
        )
        expect_red(
            "C8 reads a stale index type as a regular file, not a submodule boundary",
            lambda: any(c == "C8" and "sub/CLAUDE.md" in d
                        for c, d in stale_type_run.failures),
        )

        # The exit status decides here too. A failed index query can still have written
        # gitlink-shaped bytes, and parsing them prunes the directory on the word of a
        # command that reported it had failed.
        def stale_type_partial_stage(args, **kwargs):
            if "--stage" in args:
                return subprocess.CompletedProcess(
                    args, 1, stdout=b"160000 " + b"0" * 40 + b" 0\tsub\0",
                    stderr=b"planted")
            return subprocess.run(args, **kwargs)

        stale_type_partial_run = Run(stale_type_owner, ci=True)
        stale_type_partial_run.c8_reserved_basenames(runner=stale_type_partial_stage)
        expect_red(
            "C8 rejects gitlink-shaped output from a failed index query",
            lambda: any(c == "C8" and "sub/CLAUDE.md" in d
                        for c, d in stale_type_partial_run.failures),
        )
        shutil.rmtree(stale_type_owner)
        shutil.rmtree(stale_type_sibling)

        # Second: a gitlink recorded BENEATH the queried directory. The pathspec now
        # yields a genuine `160000` record, so the mode comparison passes and only the
        # recorded-path comparison is left. An owner holding one submodule under a
        # directory does not make that directory somebody else's worktree.
        gitlink_beneath_owner = os.path.join(td, "gitlink-beneath-owner")
        gitlink_beneath_sibling = os.path.join(td, "gitlink-beneath-sibling")
        os.makedirs(gitlink_beneath_owner)
        for repository in (gitlink_beneath_owner, gitlink_beneath_sibling):
            subprocess.run(["git", "init", "--quiet", repository], check=True)
        open(os.path.join(gitlink_beneath_owner, "README.md"), "w").write("root\n")
        subprocess.run(
            ["git", "-C", gitlink_beneath_owner, "add", "README.md"], check=True)
        subprocess.run(
            ["git", "-C", gitlink_beneath_owner, "-c", "user.name=fixture", "-c",
             "user.email=fixture@example.invalid", "commit", "--quiet", "-m", "fixture"],
            check=True)
        beneath_commit = subprocess.run(
            ["git", "-C", gitlink_beneath_owner, "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True).stdout.strip()
        subprocess.run(
            ["git", "-C", gitlink_beneath_owner, "update-index", "--add", "--cacheinfo",
             f"160000,{beneath_commit},sub/inner"], check=True)
        os.makedirs(os.path.join(gitlink_beneath_owner, "sub"))
        open(os.path.join(gitlink_beneath_owner, "sub", "AGENTS.md"), "w").write(
            "still owned here\n")
        open(os.path.join(gitlink_beneath_owner, "sub", ".git"), "wb").write(
            b"gitdir: " + os.fsencode(
                os.path.join(gitlink_beneath_sibling, ".git")) + b"\n")
        beneath_staged = subprocess.run(
            ["git", "-C", gitlink_beneath_owner, "ls-files", "--stage", "-z",
             "--", "sub"], capture_output=True).stdout
        gitlink_beneath_run = Run(gitlink_beneath_owner, ci=True)
        gitlink_beneath_run.c8_reserved_basenames()
        expect_red(
            "C8 gitlink-beneath fixture yields a real gitlink record under that pathspec",
            lambda: beneath_staged.startswith(b"160000 ")
            and beneath_staged.rstrip(b"\0").endswith(b"\tsub/inner"),
        )
        expect_red(
            "C8 requires the gitlink record to be the queried path, not one beneath it",
            lambda: any(c == "C8" and "sub/AGENTS.md" in d
                        for c, d in gitlink_beneath_run.failures),
        )
        shutil.rmtree(gitlink_beneath_owner)
        shutil.rmtree(gitlink_beneath_sibling)

        standalone_owner_admin = os.path.join(td, "standalone-owner-admin")
        standalone_owner_tree = os.path.join(td, "standalone-owner-tree")
        subprocess.run(
            ["git", "init", "--quiet", "--separate-git-dir",
             standalone_owner_admin, standalone_owner_tree], check=True)
        borrowed_standalone = os.path.join(live_repo, "borrowed-standalone-admin")
        os.makedirs(borrowed_standalone)
        open(os.path.join(borrowed_standalone, ".git"), "wb").write(
            b"gitdir: " + os.fsencode(standalone_owner_admin) + b"\n")
        open(os.path.join(borrowed_standalone, "CLAUDE.md"), "w").write(
            "still owned here\n")
        borrowed_standalone_run = Run(live_repo, ci=True)
        borrowed_standalone_run.c8_reserved_basenames()
        expect_red("C8 rejects a pointer borrowing an unbound standalone gitdir",
                   lambda: any(c == "C8" and "borrowed-standalone-admin/CLAUDE.md" in d
                               for c, d in borrowed_standalone_run.failures))
        shutil.rmtree(borrowed_standalone)
        shutil.rmtree(standalone_owner_tree)
        shutil.rmtree(standalone_owner_admin)

        separate_admin = os.path.join(td, "separate-git-admin")
        separate_tree = os.path.join(live_repo, "separate-git-tree")
        subprocess.run(
            ["git", "init", "--quiet", "--separate-git-dir", separate_admin,
             separate_tree], check=True)
        open(os.path.join(separate_tree, "CLAUDE.md"), "w").write("other owner\n")
        unbound_separate_run = Run(live_repo, ci=True)
        unbound_separate_run.c8_reserved_basenames()
        expect_red("C8 rejects an external gitdir with no candidate binding",
                   lambda: any(c == "C8" and "separate-git-tree/CLAUDE.md" in d
                               for c, d in unbound_separate_run.failures))
        subprocess.run(
            ["git", "--git-dir", separate_admin, "config", "core.worktree",
             separate_tree], check=True)
        separate_config_queries = []
        separate_config_environments = []
        def record_separate_config(args, **kwargs):
            separate_config_environments.append(dict(kwargs.get("env", {})))
            if (args[:3] == ["git", "--git-dir", os.path.realpath(separate_admin)]
                    and args[-2:] == ["--get-all", "core.worktree"]):
                separate_config_queries.append(args)
            return subprocess.run(args, **kwargs)
        bound_separate_run = Run(live_repo, ci=True)
        prior_sentinel = os.environ.get("Z_HARNESS_GIT_SENTINEL")
        prior_config_count = os.environ.get("GIT_CONFIG_COUNT")
        os.environ["Z_HARNESS_GIT_SENTINEL"] = "retained"
        os.environ["GIT_CONFIG_COUNT"] = "1"
        try:
            bound_separate_run.c8_reserved_basenames(runner=record_separate_config)
        finally:
            if prior_sentinel is None:
                os.environ.pop("Z_HARNESS_GIT_SENTINEL", None)
            else:
                os.environ["Z_HARNESS_GIT_SENTINEL"] = prior_sentinel
            if prior_config_count is None:
                os.environ.pop("GIT_CONFIG_COUNT", None)
            else:
                os.environ["GIT_CONFIG_COUNT"] = prior_config_count
        expect_red("C8 prunes an external gitdir explicitly bound to its worktree",
                   lambda: not bound_separate_run.failures)
        bound_separate_alias_run = Run(case_alias, ci=True)
        bound_separate_alias_run.c8_reserved_basenames()
        expect_red(
            "C8 prunes bound separate gitdirs through a case-alias owner root",
            lambda: sys.platform != "darwin" or not bound_separate_alias_run.failures,
        )
        expect_red("C8 reads only the local admin-owned core.worktree binding",
                   lambda: {tuple(args) for args in separate_config_queries} == {(
                       "git", "--git-dir", os.path.realpath(separate_admin), "config",
                       "--local", "--path", "--null", "--get-all", "core.worktree",
                   )}
                   and separate_config_environments
                   and all(env.get("Z_HARNESS_GIT_SENTINEL") == "retained"
                           and "GIT_CONFIG_COUNT" not in env
                           and not any(key in _GIT_REPOSITORY_ENV for key in env)
                           for env in separate_config_environments))
        other_separate_tree = os.path.join(td, "other-separate-tree")
        os.makedirs(other_separate_tree)
        subprocess.run(
            ["git", "--git-dir", separate_admin, "config", "core.worktree",
             other_separate_tree], check=True)
        wrong_binding_run = Run(live_repo, ci=True)
        wrong_binding_run.c8_reserved_basenames()
        expect_red("C8 rejects an external gitdir bound to a different worktree",
                   lambda: any(c == "C8" and "separate-git-tree/CLAUDE.md" in d
                               for c, d in wrong_binding_run.failures))
        shutil.rmtree(other_separate_tree)
        shutil.rmtree(separate_tree)
        shutil.rmtree(separate_admin)

        symlink_admin = os.path.join(td, "symlink-git-admin")
        symlink_tree = os.path.join(live_repo, "symlink-git-marker")
        subprocess.run(
            ["git", "init", "--quiet", "--separate-git-dir", symlink_admin,
             symlink_tree], check=True)
        subprocess.run(
            ["git", "--git-dir", symlink_admin, "config", "core.worktree",
             symlink_tree], check=True)
        os.remove(os.path.join(symlink_tree, ".git"))
        os.symlink(symlink_admin, os.path.join(symlink_tree, ".git"))
        open(os.path.join(symlink_tree, "GEMINI.md"), "w").write(
            "still owned here\n")
        symlink_marker_run = Run(live_repo, ci=True)
        symlink_marker_run.c8_reserved_basenames()
        expect_red("C8 rejects a symlinked .git marker even when Git accepts it",
                   lambda: any(c == "C8" and "symlink-git-marker/GEMINI.md" in d
                               for c, d in symlink_marker_run.failures))
        shutil.rmtree(symlink_tree)
        shutil.rmtree(symlink_admin)

        wrong_parent_tree = os.path.join(live_repo, "wrong-admin-parent")
        subprocess.run(
            ["git", "-C", live_repo, "worktree", "add", "--quiet", "--detach",
             wrong_parent_tree, "HEAD"], check=True)
        wrong_parent_marker = os.path.join(wrong_parent_tree, ".git")
        wrong_parent_admin = _gitdir_from_marker(
            wrong_parent_tree, wrong_parent_marker)
        relocated_admin = os.path.join(live_repo, ".git", "relocated-admin")
        shutil.move(wrong_parent_admin, relocated_admin)
        open(wrong_parent_marker, "wb").write(
            b"gitdir: " + os.fsencode(relocated_admin) + b"\n")
        open(os.path.join(relocated_admin, "commondir"), "wb").write(b"..\n")
        open(os.path.join(wrong_parent_tree, "AGENTS.md"), "w").write(
            "still owned here\n")
        wrong_parent_run = Run(live_repo, ci=True)
        wrong_parent_run.c8_reserved_basenames()
        expect_red("C8 rejects linked metadata outside the common worktrees directory",
                   lambda: any(c == "C8" and "wrong-admin-parent/AGENTS.md" in d
                               for c, d in wrong_parent_run.failures))
        shutil.rmtree(wrong_parent_tree)
        shutil.rmtree(relocated_admin)

        stale_backlink_tree = os.path.join(live_repo, "stale-backlink")
        subprocess.run(
            ["git", "-C", live_repo, "worktree", "add", "--quiet", "--detach",
             stale_backlink_tree, "HEAD"], check=True)
        stale_backlink_marker = os.path.join(stale_backlink_tree, ".git")
        stale_backlink_admin = _gitdir_from_marker(
            stale_backlink_tree, stale_backlink_marker)
        open(os.path.join(stale_backlink_admin, "gitdir"), "wb").write(
            os.fsencode(os.path.join(live_repo, "missing", ".git")) + b"\n")
        open(os.path.join(stale_backlink_tree, "CLAUDE.md"), "w").write(
            "still owned here\n")
        stale_backlink_run = Run(live_repo, ci=True)
        stale_backlink_run.c8_reserved_basenames()
        expect_red("C8 rejects linked metadata whose reciprocal backlink is stale",
                   lambda: any(c == "C8" and "stale-backlink/CLAUDE.md" in d
                               for c, d in stale_backlink_run.failures))
        shutil.rmtree(stale_backlink_tree)
        shutil.rmtree(stale_backlink_admin)

        unterminated_tree = os.path.join(live_repo, "unterminated-marker")
        subprocess.run(
            ["git", "-C", live_repo, "worktree", "add", "--quiet", "--detach",
             unterminated_tree, "HEAD"], check=True)
        unterminated_marker = os.path.join(unterminated_tree, ".git")
        unterminated_admin = _gitdir_from_marker(unterminated_tree, unterminated_marker)
        marker_bytes = open(unterminated_marker, "rb").read()
        open(unterminated_marker, "wb").write(marker_bytes[:-1])
        open(os.path.join(unterminated_tree, "GEMINI.md"), "w").write(
            "still owned here\n")
        unterminated_run = Run(live_repo, ci=True)
        unterminated_run.c8_reserved_basenames()
        expect_red("C8 rejects Git metadata without its required final terminator",
                   lambda: any(c == "C8" and "unterminated-marker/GEMINI.md" in d
                               for c, d in unterminated_run.failures))
        shutil.rmtree(unterminated_tree)
        shutil.rmtree(unterminated_admin)

        # Truncating the terminator above also destroys the path, so the requirement and
        # the unconditional final-byte strip that follows it agree and neither is isolated:
        # dropping the requirement still leaves a directory that does not exist. Give the
        # marker one byte of slack -- a trailing separator, still unterminated -- and they
        # disagree. Git accepts the marker either way, so only the requirement stands
        # between the strip and a valid admin directory to prune the tree with.
        slack_tree = os.path.join(live_repo, "unterminated-slack-marker")
        subprocess.run(
            ["git", "-C", live_repo, "worktree", "add", "--quiet", "--detach",
             slack_tree, "HEAD"], check=True)
        slack_marker = os.path.join(slack_tree, ".git")
        slack_admin = _gitdir_from_marker(slack_tree, slack_marker)
        open(slack_marker, "wb").write(b"gitdir: " + os.fsencode(slack_admin) + b"/")
        open(os.path.join(slack_tree, "CLAUDE.md"), "w").write("still owned here\n")
        slack_prefix = subprocess.run(
            ["git", "-C", slack_tree, "rev-parse", "--show-prefix"],
            capture_output=True)
        slack_run = Run(live_repo, ci=True)
        slack_run.c8_reserved_basenames()
        # The rejection has to be this file's doing. If Git itself refused the marker, the
        # exact-root gate would reject the tree first and the requirement below would be
        # asserted by a fixture that never reaches it.
        expect_red(
            "C8 unterminated-slack fixture is a marker Git itself still accepts",
            lambda: slack_prefix.returncode == 0
            and bytes(slack_prefix.stdout) in (b"\n", b"\r\n")
            and os.path.isdir(slack_admin)
            and open(slack_marker, "rb").read()[:-1].endswith(os.fsencode(slack_admin)),
        )
        expect_red(
            "C8 requires the final terminator even when the last byte is strippable slack",
            lambda: any(c == "C8" and "unterminated-slack-marker/CLAUDE.md" in d
                        for c, d in slack_run.failures),
        )
        shutil.rmtree(slack_tree)
        shutil.rmtree(slack_admin)

        # Same condition, other operand. A marker carrying an embedded NUL is one Git
        # itself accepts -- it stops at the newline -- so nothing upstream rejects the
        # tree, and the NUL never reaches a path call only because this clause drops it
        # first. Without the clause the byte reaches `realpath`, which raises ValueError
        # rather than returning; the inventory catches OSError only, so the gate would
        # end on a traceback with no verdict line instead of naming a failure.
        nul_tree = os.path.join(live_repo, "nul-bearing-marker")
        subprocess.run(
            ["git", "-C", live_repo, "worktree", "add", "--quiet", "--detach",
             nul_tree, "HEAD"], check=True)
        nul_marker = os.path.join(nul_tree, ".git")
        nul_admin = _gitdir_from_marker(nul_tree, nul_marker)
        open(nul_marker, "wb").write(
            b"gitdir: " + os.fsencode(nul_admin) + b"\0junk\n")
        open(os.path.join(nul_tree, "AGENTS.md"), "w").write("still owned here\n")
        nul_prefix = subprocess.run(
            ["git", "-C", nul_tree, "rev-parse", "--show-prefix"], capture_output=True)
        # The scan runs inside the proof on purpose. Dropping the clause makes this tree
        # raise out of the inventory, and a raise at fixture-construction time takes the
        # whole meta-suite down before it can print a receipt -- the missing-receipt arm,
        # which says only that something broke. Inside, the same raise is caught and
        # attributed to the proof whose subject it is.
        def c8_drops_a_nul_bearing_marker():
            run = Run(live_repo, ci=True)
            run.c8_reserved_basenames()
            return any(c == "C8" and "nul-bearing-marker/AGENTS.md" in d
                       for c, d in run.failures)

        expect_red(
            "C8 nul-bearing fixture is a marker Git itself still accepts",
            lambda: nul_prefix.returncode == 0
            and bytes(nul_prefix.stdout) in (b"\n", b"\r\n")
            and b"\0" in open(nul_marker, "rb").read(),
        )
        expect_red(
            "C8 drops a NUL-bearing marker instead of carrying the byte into a path call",
            c8_drops_a_nul_bearing_marker,
        )
        shutil.rmtree(nul_tree)
        shutil.rmtree(nul_admin)

        submodule_source = os.path.join(td, "submodule-source")
        subprocess.run(["git", "init", "--quiet", submodule_source], check=True)
        subprocess.run(
            ["git", "-C", submodule_source, "-c", "user.name=fixture", "-c",
             "user.email=fixture@example.invalid", "commit", "--quiet", "--allow-empty",
             "-m", "fixture"], check=True)
        submodule = os.path.join(live_repo, "nested-submodule")
        subprocess.run(
            ["git", "-C", live_repo, "-c", "protocol.file.allow=always", "submodule",
             "add", "--quiet", submodule_source, "nested-submodule"], check=True)
        submodule_marker = os.path.join(submodule, ".git")
        submodule_admin = _gitdir_from_marker(submodule, submodule_marker)
        subprocess.run(
            ["git", "--git-dir", submodule_admin, "config", "--unset", "core.worktree"],
            check=True)
        open(os.path.join(submodule, "AGENTS.md"), "w").write("other owner\n")
        submodule_run = Run(live_repo, ci=True)
        submodule_run.c8_reserved_basenames()
        expect_red("C8 prunes an indexed nested submodule boundary",
                   lambda: not submodule_run.failures)

        submodule_marker_bytes = open(submodule_marker, "rb").read()
        os.remove(submodule_marker)
        broken_submodule_run = Run(live_repo, ci=True)
        broken_submodule_run.c8_reserved_basenames()
        expect_red("C8 walks an indexed submodule whose live Git boundary is missing",
                   lambda: any(c == "C8" and "nested-submodule/AGENTS.md" in d
                               for c, d in broken_submodule_run.failures))
        open(submodule_marker, "wb").write(submodule_marker_bytes)

        ignored = os.path.join(live_repo, "ignored")
        os.makedirs(ignored)
        open(os.path.join(live_repo, ".gitignore"), "w").write("ignored/\n")
        open(os.path.join(ignored, "AGENTS.md"), "w").write("ignored but live\n")
        ignored_run = Run(live_repo, ci=True)
        ignored_run.c8_reserved_basenames()
        expect_red("C8 separately reaches an ignored reserved context basename",
                   lambda: any(c == "C8" and "ignored/AGENTS.md" in d
                               for c, d in ignored_run.failures))

        fallback_root = os.path.join(td, "fallback-live-context")
        os.makedirs(fallback_root)
        open(os.path.join(fallback_root, "README.md"), "w").write("root\n")
        fallback_fake = os.path.join(fallback_root, "invalid-marker")
        os.makedirs(fallback_fake)
        open(os.path.join(fallback_fake, ".git"), "w").write("not a repository\n")
        open(os.path.join(fallback_fake, "AGENTS.md"), "w").write("still owned here\n")
        fallback_fake_run = Run(fallback_root, ci=True)
        fallback_fake_run.c8_reserved_basenames()
        expect_red("C8 filesystem fallback does not trust a fake .git marker",
                   lambda: any(c == "C8" and "invalid-marker/AGENTS.md" in d
                               for c, d in fallback_fake_run.failures))

        shutil.rmtree(fallback_fake)
        fallback_nested = os.path.join(fallback_root, "nested-repository")
        subprocess.run(["git", "init", "--quiet", fallback_nested], check=True)
        open(os.path.join(fallback_nested, "CLAUDE.md"), "w").write("other owner\n")
        fallback_nested_run = Run(fallback_root, ci=True)
        fallback_nested_run.c8_reserved_basenames()
        expect_red("C8 filesystem fallback prunes a real nested repository",
                   lambda: not fallback_nested_run.failures)

        fallback_separate_admin = os.path.join(td, "fallback-separate-admin")
        fallback_separate_tree = os.path.join(
            fallback_root, "separate-git-repository")
        subprocess.run(
            ["git", "init", "--quiet", "--separate-git-dir",
             fallback_separate_admin, fallback_separate_tree], check=True)
        open(os.path.join(fallback_separate_tree, "GEMINI.md"), "w").write(
            "other owner\n")
        fallback_unbound_run = Run(fallback_root, ci=True)
        fallback_unbound_run.c8_reserved_basenames()
        expect_red("C8 filesystem fallback rejects an unbound external gitdir",
                   lambda: any(c == "C8" and "separate-git-repository/GEMINI.md" in d
                               for c, d in fallback_unbound_run.failures))
        subprocess.run(
            ["git", "--git-dir", fallback_separate_admin, "config", "core.worktree",
             fallback_separate_tree], check=True)
        fallback_bound_run = Run(fallback_root, ci=True)
        fallback_bound_run.c8_reserved_basenames()
        expect_red("C8 filesystem fallback prunes an explicitly bound external gitdir",
                   lambda: not fallback_bound_run.failures)

        os.makedirs(os.path.join(live_repo, ".github"))
        open(os.path.join(live_repo, ".github", "CLAUDE.md"), "w").write("visible\n")
        github_live_run = Run(live_repo, ci=True)
        github_live_run.c8_reserved_basenames()
        expect_red("C8 Git mode keeps .github visible",
                   lambda: any(c == "C8" and ".github/CLAUDE.md" in d
                               for c, d in github_live_run.failures))
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
            "name": "z-harness", "version": CURRENT_PLUGIN_VERSION,
            "description": "fixture",
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

        stale_release = json.loads(json.dumps(manifest))
        stale_release["version"] = "0.3.0"
        stale_release_run = c9_after(mutated_manifest=stale_release)
        expect_red(
            "C9 rejects a manifest that keeps the predecessor release identity",
            lambda: any("reviewed release" in detail
                        for _check, detail in stale_release_run.failures),
        )

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
