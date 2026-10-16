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
  C12 skill claims about the always-on file bind to verbatim AGENTS.md text: every
      sentence naming `~/.claude/CLAUDE.md`, or `AGENTS.md` with one of its section
      headings, a straight-quoted phrase, or a line number, must carry a straight-quoted
      phrase present in AGENTS.md (inside the named section when one is named). A
      `CLAUDE.md:<n>` or `AGENTS.md:<n>` line citation, a bare `:<n>` citation, an
      unbound claim, a stale quote, a negated claim whose quote IS present, and an
      AGENTS.md sentence duplicated outside a quote are findings. The bare noun
      "always-on" and generic CLAUDE.md/AGENTS.md class talk are out of scope. Findings
      are a shrink-only worklist against contracts/worklists.json: identities are
      (file, kind, claim text), never line numbers; green while every live finding is
      in the baseline, red on a finding the baseline lacks and red on a baseline item
      that is no longer live, so the baseline shrinks only by a deliberate edit in the
      change that fixes the item. Every live finding still prints as WORKLIST
  C13 eval coverage: release/evals.json lists every skill as tested or exempt with a
      reason; unlisted skills are the same shrink-only worklist against the baseline's
      C13 list, printed in full; every other manifest defect is a plain failure
  C14 budget ceilings: AGENTS.md and the generated instruction file never exceed the
      sizes recorded in contracts/budget-ceilings.json (fail only on growth); the Claude
      dynamic hook block and the per-turn carrier ceilings sit under the runtime caps and
      match the record; C4, C5 and C9 stay as they are
  C15 hook envelope fixtures decode: every Codex envelope under hooks/fixtures_codex/
      carries every field its event's input schema requires, host paths are scrubbed,
      the synthetic fixture is labeled, and the Claude Stop fixture decodes

Exit codes: 0 all checks pass · 1 one or more checks failed · 2 usage error or
zero inputs (an empty scan set is an error, never a clean verdict).

  harness_check.py                  run every check (local mode)
  harness_check.py --ci             skip [local]-tagged checks (no ~/.claude, no
                                    claude binary, no launchd on the runner)
  harness_check.py --selftest       prove each check can go RED on a planted-defect
                                    tree, then exit
  harness_check.py --verify-runtime structural evidence only: read the installed
                                    Claude binaries (CLI and desktop builds) and the
                                    installed Codex binary for the anchored contracts
                                    with fixed-window byte searches, then print the
                                    host-scenario catalog with every scenario that
                                    has no recorded host run as UNVERIFIED. Anchor
                                    presence is version-bound structural evidence; it
                                    never proves dispatch, enforcement, or delivery
"""
import ast
import contextlib
import fnmatch
import hashlib
import importlib.util
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
import types

VERSION = "3.5.0"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_DIR = os.path.join(ROOT, "tools")
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

from repository_ownership import (  # noqa: E402
    _GIT_REPOSITORY_ENV,
    _bound_separate_gitdir,
    _git_common_dir,
    _git_path_line,
    _gitdir_from_marker,
    _indexed_gitlink,
    _registered_linked_worktree,
    RepositoryOwnershipError,
    git_command_failure,
    git_toplevel_error as _git_toplevel_error,
    is_repository_boundary,
    run_git,
    same_file as _same_file,
    sanitized_git_environment,
)


def _is_git_worktree_root(path, runner, owner_root=None):
    """Compatibility wrapper around the shared ownership authority."""
    return is_repository_boundary(path, owner_root=owner_root, runner=runner)

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
SELFTEST_FLOOR = 354
# This pin gives the current package a reviewable release identity. Update it with the
# manifest when the next release is deliberately cut; C9 rejects a one-sided edit.
CURRENT_PLUGIN_VERSION = "0.3.3"

AUTHORING_SKILLS = {"craft-prompt", "craft-skill", "craft-context-file", "review-prompt"}
BODY_CHAR_CAP = 5000          # chars after frontmatter — the builders' instrument
BODY_LINE_CAP = 500           # authoring skills (spec cap)
DESC_CAP = 400                # house cap (spec ceiling is 1024)

# (name, command, floor). The floor is a shrink-only ratchet: a suite reporting fewer
# checks than its floor goes red. Without it a receipt of checks=1 reads the same as
# checks=111, so a suite can be gutted with nothing failing. Raise a floor in the same
# commit that adds the checks; lowering one is a deliberate, reviewable edit.
SELFTEST_SUITES = [
    ("bash_command_guard", ["hooks/bash_command_guard.py", "--selftest"], 1865),
    ("bash_command_guard-perf", ["hooks/bash_command_guard.py", "--perf"], 17),
    ("credential_reach_guard",
     ["hooks/guards/credential_reach_guard.py", "--selftest"], 84),
    ("askq_timeout_guard", ["hooks/askq_timeout_guard.py", "--selftest"], 13),
    ("announced_work_guard", ["hooks/announced_work_guard.py", "--selftest"], 922),
    ("harness_report", ["hooks/harness_report.py", "--selftest"], 33),
    ("cc-cost", ["tools/cc-cost.py", "--selftest"], 8),
    ("codex-cost", ["tools/codex-cost.py", "--selftest"], 28),
    ("claim-provenance", ["tools/claim-provenance.py", "--selftest"], 83),
    ("repository-ownership", ["tools/repository_ownership.py", "--selftest"], 78),
    ("pr-delivery-state", ["tools/pr-delivery-state.py", "--selftest"], 25),
    ("verify-review-publication",
     ["tools/verify-review-publication.py", "--selftest"], 94),
    ("run-skill-evals", ["tools/run-skill-evals.py", "--selftest"], 53),
    ("install-claude", ["tools/install-claude.py", "--selftest"], 148),
    ("render-packages", ["tools/render-packages.py", "--selftest"], 192),
    ("ci-gate", ["tools/ci-gate.py", "--selftest"], 345),
    ("write-mutation-receipt",
     ["tools/write-mutation-receipt.py", "--selftest"], 169),
    ("portable-conformance", ["tools/portable-conformance.py", "--selftest"], 65),
    ("enumerate-survivors", ["instruments/enumerate_survivors.py", "--selftest"], 28),
    ("fuzz-judge-diff", ["instruments/fuzz_judge_diff.py", "--selftest"], 65),
    ("corpus-delta", ["instruments/corpus_delta.py", "--selftest"], 20),
    ("codex_session_start", ["hooks/codex_session_start.py", "--selftest"], 32),
    ("spawn_preflight_guard", ["hooks/spawn_preflight_guard.py", "--selftest"], 88),
    ("git_grep_engine_guard", ["hooks/guards/git_grep_engine_guard.py", "--selftest"], 1626),
    ("git_grep_engine_guard-perf", ["hooks/guards/git_grep_engine_guard.py", "--perf"], 5),
    ("zsh_rev_modifier_guard", ["hooks/guards/zsh_rev_modifier_guard.py", "--selftest"], 523),
]


def expected_selftest_checks(name):
    """Exact execution-derived counts for suites whose former formulas hid probes."""
    fixed = {
        "announced_work_guard": 922,
        "bash_command_guard-perf": 17,
        "git_grep_engine_guard-perf": 5,
        "ci-gate": 345,
        "enumerate-survivors": 28,
        "fuzz-judge-diff": 65,
        "corpus-delta": 20,
        "spawn_preflight_guard": 88,
        "verify-review-publication": 94,
    }
    if name in fixed:
        return fixed[name]
    if name == "bash_command_guard":
        return 1865
    if name == "credential_reach_guard":
        return 84
    if name == "zsh_rev_modifier_guard":
        return 523
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
    # The portable corpus is 1626 checks for one Git. Every additional executable adds
    # one version probe, one fixture setup, and 22 alias-proof-name probes.
    return 1626 + 24 * (max(1, len(binaries)) - 1)
# The Bash guard's perf suite intentionally runs five independent process-level timing
# observations for each runtime. Give that aggregate suite enough wall-clock without
# weakening the five-second deadline each individual hook process must meet. Those checks
# and the grep guard's at-limit timing controls left the two guards' `--selftest` for
# `--perf`, because the mutation sweep runs `--selftest` once per mutation; measured on the
# authoring host after the move, bash_command_guard-perf took 31.6-33.7 s and
# bash_command_guard 3.3-3.5 s, git_grep_engine_guard-perf 6.2-6.3 s and
# git_grep_engine_guard 10.6-11.3 s.
# Registered where the 15 s default leaves no headroom for a slower runner. Measured
# on the authoring host: bash_command_guard 27 s, git_grep_engine_guard 7.3 s (its
# byte-cap, token and subcommand fixtures parse real megabyte-scale sources, and it
# probes the installed git and zsh), announced_work_guard 15-16 s run alone and longer under
# this gate's own concurrency (the suite includes real Stop-process envelopes), ci-gate
# 20.8 s. C1 requires each to finish inside SELFTEST_TIMEOUT_MARGIN of its budget, so these
# are ceilings with room, not targets -- and the figure that decides the verdict is the
# loaded one, which none of these are. They are not regenerable from a green run either:
# C1 prints a suite's elapsed time only when it exceeds its margin, so a number here is a
# hand-timing on one host and drifts silently until the day it reddens. announced_work_guard
# was raised from 30 s the day that happened, on a run that changed none of its checks;
# ci-gate from 60 s the day its nested run took 36.5 s against a 36 s margin on the Ubuntu
# runner, after the plan grew to 389 sites and the golden to 1,132 with no check changed, and
# from 90 s the day its nested run took 56.5 s on Ubuntu and 56.2 s on macOS against a 54 s
# margin while the same suite run alone took 31.6 s on the authoring host. fuzz-judge-diff was
# registered at 25 s the day its nested macOS run took 9.1 s against the default's 9 s margin. The
# ratios these figures imply are not quoted here: the loaded and unloaded numbers give
# different answers, and the earlier attempt to state one contradicted the ci-gate figure
# three lines above it.
SELFTEST_TIMEOUTS = {
    "bash_command_guard": 30,
    "bash_command_guard-perf": 90,
    "git_grep_engine_guard": 60,
    "git_grep_engine_guard-perf": 30,
    "announced_work_guard": 60,
    "ci-gate": 120,
    "fuzz-judge-diff": 25,
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
# Citations in reference documents that name something this repository does not contain.
# Each is a runtime artifact or an illustrative filename, so requiring it to resolve would be
# wrong rather than merely noisy. Declared, because no structural test separates them from a
# citation that should resolve: `agents/openai.yaml` carries a path separator and is external,
# `PRINCIPLE-REGISTRY.md` carries none and is not. Adding a name here claims the artifact lives
# outside this repository, and the diff is where that claim gets reviewed.
EXTERNAL_REFERENCE_CITATIONS = {
    "probe.py": "illustrative worker filename in a collision anecdote",
    "mutate.py": "illustrative worker filename in a collision anecdote",
    "base.py": "illustrative worker filename in a collision anecdote",
    "agents/openai.yaml": "Codex configuration in the user environment",
    "AGENTS.override.md": "Codex convention outside this repository",
    "policy-blocks/persistence.md": "external prompt-library path",
}
# The line suffix is optional and captured separately. Requiring the backtick to follow the
# extension made `doc.md:12` invisible to this check, so a citation could carry a line number
# and evade resolution entirely -- the path half is what resolves either way.
REFERENCE_CITATION = re.compile(
    r"`([A-Za-z0-9_][A-Za-z0-9_./-]*\.(?:py|md|json|ya?ml|sh|txt))(?::\d+)?`")


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
    ("C12", "c12_claim_binding"),
    ("C13", "c13_eval_coverage"),
    ("C14", "c14_budget_ceilings"),
    ("C15", "c15_envelope_fixtures"),
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
C6_SCAN_FLOOR = 163

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
    ("Stop", None, "hooks/announced_work_guard.py", ()),
    ("PostToolUse", "AskUserQuestion", "hooks/askq_timeout_guard.py", ()),
    ("PreToolUse", "Bash", "hooks/bash_command_guard.py", ()),
    ("PreToolUse", "Agent|Task", "hooks/spawn_preflight_guard.py",
     ("--require-scratch",)),
]

RESERVED_BASENAMES = {"claude.md", "agents.md", "gemini.md"}
CODEX_HOOK_TOP_LEVEL_KEYS = {"description", "hooks"}
# The twelve events whose input schemas are embedded in the installed codex-cli 0.154.0 binary;
# --verify-runtime re-reads the binary for this list. SessionEnd and Interrupt were absent from
# the 0.144.4 schema this allowlist once followed; SessionEnd was observed executing on
# 2026-10-15 and its envelope is committed under hooks/fixtures_codex/.
CODEX_VALID_HOOK_EVENTS = {
    "PreToolUse", "PermissionRequest", "PostToolUse", "PreCompact", "PostCompact",
    "SessionStart", "SessionEnd", "UserPromptSubmit", "SubagentStart", "SubagentStop",
    "Stop", "Interrupt",
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
    ("PreToolUse", "^Agent$", "hooks/spawn_preflight_guard.py",
     ("--runtime", "codex", "--require-scratch")),
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

# ---- C12: skill claims about the always-on file ----------------------------------
# A claim sentence names the installed always-on file by path, or names AGENTS.md together
# with one of its section headings, a straight-quoted phrase, or a line number. Every such
# sentence binds to a straight-quoted phrase present verbatim in AGENTS.md; an edited phrase
# then fails the citing skill loudly, which is the intended signal. No rule identifiers are
# added to the policy for this: the quote IS the binding.
ALWAYS_ON_PATH = re.compile(r"`?~/\.claude/CLAUDE\.md`?")
POLICY_LINE_CITATION = re.compile(r"(?:CLAUDE|AGENTS)\.md`?\s*:\s*\d+(?:\s*[-–]\s*\d+)?")
BARE_LINE_CITATION = re.compile(r"`:\d+(?:-\d+)?`")
STRAIGHT_QUOTE = re.compile(r"\"([^\"]{1,2000})\"", re.S)
# A code span is a run of backticks, its content, and the same run; a longer run may hold a
# shorter one, and the content may span lines.
CODE_SPAN = re.compile(r"(?<![`\\])(`+)(?!`)(.+?)(?<![`\\])\1(?!`)", re.S)
# Masking tokens are private-use characters, which authored prose never carries; any that do
# occur are stripped before masking so text cannot impersonate a token.
SPAN_TOKEN = re.compile("(\\d+)")
QUOTE_TOKEN = re.compile("(\\d+)")
PRIVATE_USE = re.compile("[-]")
QUOTE_ELLIPSIS = re.compile(r"…|\.\.\.")
CLAIM_NEGATION = re.compile(
    r"\b(?:does not|do not|did not|is not|are not|was not|were not|no longer|not carried|"
    r"not carry|never carr(?:y|ies|ied)|never had|absent from|nowhere in)\b", re.I)
SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+")
DUPLICATE_MIN_WORDS = 8
C12_SCOPE = ("sentences naming ~/.claude/CLAUDE.md, or AGENTS.md with a section heading, a "
             "straight-quoted phrase, or a line number; the bare noun always-on and generic "
             "CLAUDE.md/AGENTS.md class talk are out of scope")

# ---- C13 / C14 / C15: manifests and records --------------------------------------
EVAL_MANIFEST = "release/evals.json"
BUDGET_CEILINGS = "contracts/budget-ceilings.json"
# Runtime caps read in-binary (see CLAUDE_RUNTIME_ANCHORS, hook_output.cap_table), and the
# harness's own ceilings under them. The adapter that will emit the dynamic block asserts
# CLAUDE_DYNAMIC_BLOCK_* in its selftest; the per-turn carrier asserts the carrier ceiling.
CLAUDE_HOOK_CONTEXT_CHAR_CAP = 8000
CLAUDE_HOOK_CONTEXT_LINE_CAP = 200
CLAUDE_DYNAMIC_BLOCK_CHAR_CEILING = 7500
CLAUDE_DYNAMIC_BLOCK_LINE_CEILING = 190
PROMPT_SUBMIT_CARRIER_BYTE_CEILING = 600
CODEX_SESSION_START_BYTE_CEILING = 30000
CODEX_SESSION_START_CONSTANT = re.compile(r"^MAX_CONTEXT_BYTES = ([0-9_]+)$", re.M)
CODEX_FIXTURE_DIR = "hooks/fixtures_codex"
CODEX_FIXTURES = {
    "C1_session_start.json": "SessionStart",
    "C2_user_prompt_submit.json": "UserPromptSubmit",
    "C3_pre_tool_use.json": "PreToolUse",
    "C4_post_tool_use.json": "PostToolUse",
    "C5_stop.json": "Stop",
    "C6_session_end.json": "SessionEnd",
    "C7_stop_null_message_synthetic.json": "Stop",
}
CODEX_SYNTHETIC_FIXTURES = {"C7_stop_null_message_synthetic.json"}
CLAUDE_STOP_FIXTURE = "hooks/fixtures_stop/S1_stop_real_envelope.json"
# Per-event required-field lists read from the input schemas embedded in codex-cli 0.154.0
# (each schema's own top-level "required" array). C15 decodes the committed fixtures against
# this table; --verify-runtime compares the table against the installed binary.
CODEX_HOOK_INPUT_REQUIRED = {
    "PreToolUse": ("cwd", "hook_event_name", "model", "permission_mode", "session_id",
                   "tool_input", "tool_name", "tool_use_id", "transcript_path", "turn_id"),
    "PermissionRequest": ("cwd", "hook_event_name", "model", "permission_mode", "session_id",
                          "tool_input", "tool_name", "transcript_path", "turn_id"),
    "PostToolUse": ("cwd", "hook_event_name", "model", "permission_mode", "session_id",
                    "tool_input", "tool_name", "tool_response", "tool_use_id",
                    "transcript_path", "turn_id"),
    "PreCompact": ("cwd", "hook_event_name", "model", "session_id", "transcript_path",
                   "trigger", "turn_id"),
    "PostCompact": ("cwd", "hook_event_name", "model", "session_id", "transcript_path",
                    "trigger", "turn_id"),
    "SessionStart": ("cwd", "hook_event_name", "model", "permission_mode", "session_id",
                     "source", "transcript_path"),
    "SessionEnd": ("cwd", "hook_event_name", "reason", "session_id", "transcript_path"),
    "UserPromptSubmit": ("cwd", "hook_event_name", "model", "permission_mode", "prompt",
                         "session_id", "transcript_path", "turn_id"),
    "SubagentStart": ("agent_id", "agent_type", "cwd", "hook_event_name", "model",
                      "permission_mode", "session_id", "transcript_path", "turn_id"),
    "SubagentStop": ("agent_id", "agent_transcript_path", "agent_type", "cwd",
                     "hook_event_name", "last_assistant_message", "model", "permission_mode",
                     "session_id", "stop_hook_active", "transcript_path", "turn_id"),
    "Stop": ("cwd", "hook_event_name", "last_assistant_message", "model", "permission_mode",
             "session_id", "stop_hook_active", "transcript_path", "turn_id"),
    "Interrupt": ("cwd", "hook_event_name", "model", "permission_mode", "session_id",
                  "transcript_path", "turn_id"),
}
CODEX_SESSION_START_SOURCES = ("startup", "resume", "clear", "compact")
CODEX_PERMISSION_MODES = ("default", "acceptEdits", "plan", "dontAsk", "bypassPermissions")
CODEX_EVENT_KEBAB = {
    "PreToolUse": "pre-tool-use", "PermissionRequest": "permission-request",
    "PostToolUse": "post-tool-use", "PreCompact": "pre-compact", "PostCompact": "post-compact",
    "SessionStart": "session-start", "SessionEnd": "session-end",
    "UserPromptSubmit": "user-prompt-submit", "SubagentStart": "subagent-start",
    "SubagentStop": "subagent-stop", "Stop": "stop", "Interrupt": "interrupt",
}
CODEX_EVENT_VARIANT_RUN = (
    b"PreToolUsePermissionRequestPostToolUsePreCompactPostCompactSessionStartSessionEnd"
    b"UserPromptSubmitSubagentStartSubagentStopStopInterrupt"
)

# ---- --verify-runtime: anchored contracts and the host-scenario catalog ------------
# Each anchor is a fixed-window byte search: the needle is located with bytes.find, and a
# bounded window around it is checked by a small regex or parser. No regex runs over the
# whole binary. A needle may occur many times; the anchor holds when ANY occurrence's window
# satisfies the check. `sample` is bytes that satisfy the anchor, used only to assemble the
# selftest's fixture binary; against a real binary the sample plays no part.
_IDENT = rb"[A-Za-z0-9_$]+"


def _regex_anchor(pattern):
    compiled = re.compile(pattern)

    def verify(window):
        return "" if compiled.search(window) else f"window does not match {pattern!r}"
    return verify


def _event_array_anchor(required):
    def verify(window):
        end = window.find(b"]")
        if end < 0:
            return "no closing bracket in window"
        try:
            names = json.loads(window[:end + 1].decode("ascii"))
        except (UnicodeDecodeError, ValueError) as exc:
            return f"event array does not parse: {exc}"
        missing = sorted(set(required) - set(names))
        return f"event array lacks {missing}" if missing else ""
    return verify


CLAUDE_REQUIRED_EVENTS = ("PreToolUse", "PostToolUse", "UserPromptSubmit", "SessionStart",
                          "SessionEnd", "Stop", "SubagentStart", "SubagentStop",
                          "PreCompact", "PermissionRequest")
CLAUDE_EVENT_ARRAY_SAMPLE = (
    b'["PreToolUse","PostToolUse","PostToolUseFailure","PostToolBatch","Notification",'
    b'"UserPromptSubmit","UserPromptExpansion","SessionStart","SessionEnd","Stop","StopFailure",'
    b'"SubagentStart","SubagentStop","PreCompact","PostCompact","PreModelSwitch",'
    b'"PostModelSwitch","PermissionRequest","PermissionDenied","Setup"]'
)
# (name, needle, bytes before, bytes after, verify, sample, what it establishes)
CLAUDE_RUNTIME_ANCHORS = (
    ("stop.input.fields", b'("Stop"),stop_hook_active:', 0, 160,
     _regex_anchor(rb'\("Stop"\),stop_hook_active:' + _IDENT + rb'\(\),last_assistant_message:'
                   + _IDENT + rb'\(\)\.optional\(\)'),
     b'hook_event_name:C("Stop"),stop_hook_active:H(),last_assistant_message:o().optional().describe("Text")',
     "Stop input: stop_hook_active required, last_assistant_message optional"),
    ("askq.afkTimeoutMs.optional", b"afkTimeoutMs:", 0, 80,
     _regex_anchor(rb"afkTimeoutMs:" + _IDENT + rb"\(\)\.int\(\)\.positive\(\)\.optional\(\)"),
     b"afkTimeoutMs:v().int().positive().optional().describe(\"Set when\")",
     "AskUserQuestion result: afkTimeoutMs is an optional positive integer"),
    ("pretooluse.input.tool_input", b'("PreToolUse"),tool_name:', 0, 160,
     _regex_anchor(rb'\("PreToolUse"\),tool_name:' + _IDENT + rb'\(\),tool_input:' + _IDENT
                   + rb'\(\),tool_use_id:'),
     b'hook_event_name:C("PreToolUse"),tool_name:o(),tool_input:oe(),tool_use_id:o()',
     "PreToolUse input: tool_name, tool_input, tool_use_id"),
    ("agent.tool_input.prompt", b'"The task for the agent to perform"', 0, 0, lambda w: "",
     b'oys="The task for the agent to perform"',
     "Agent tool: the prompt parameter the spawn guard reads is the task text"),
    ("events.registered", b'["PreToolUse","PostToolUse","PostToolUseFailure","PostToolBatch","Notification","UserPromptSubmit"', 0, 1200,
     _event_array_anchor(CLAUDE_REQUIRED_EVENTS), CLAUDE_EVENT_ARRAY_SAMPLE,
     "hook event enum carries every event the harness registers or reads"),
    ("sessionstart.input.source", b'("SessionStart"),source:', 0, 160,
     _regex_anchor(rb'\("SessionStart"\),source:' + _IDENT
                   + rb'\(\["startup","resume","clear","compact","fork"\]\)'),
     b'hook_event_name:C("SessionStart"),source:U(["startup","resume","clear","compact","fork"]),agent_type:o().optional()',
     "SessionStart input: source enum startup|resume|clear|compact|fork"),
    ("userpromptsubmit.input.prompt_source", b'("UserPromptSubmit"),prompt:', 0, 240,
     _regex_anchor(rb'\("UserPromptSubmit"\),prompt:' + _IDENT + rb'\(\),source:' + _IDENT
                   + rb'\(\["user","sdk","system","loop_wakeup","schedule_wakeup","poll_event"\]\)\.optional\(\)'),
     b'hook_event_name:C("UserPromptSubmit"),prompt:o(),source:U(["user","sdk","system","loop_wakeup","schedule_wakeup","poll_event"]).optional().describe("Who")',
     "UserPromptSubmit input: prompt, and the optional source enum incl. sdk"),
    ("sessionstart.output.additionalContext", b'("SessionStart"),additionalContext:', 0, 100,
     _regex_anchor(rb'\("SessionStart"\),additionalContext:' + _IDENT + rb'\(\)\.optional\(\)'),
     b'hookEventName:C("SessionStart"),additionalContext:o().optional(),initialUserMessage:o().optional()',
     "SessionStart output accepts hookSpecificOutput.additionalContext"),
    ("userpromptsubmit.output.additionalContext", b'("UserPromptSubmit"),additionalContext:', 0, 100,
     _regex_anchor(rb'\("UserPromptSubmit"\),additionalContext:' + _IDENT + rb'\(\)\.optional\(\)'),
     b'hookEventName:C("UserPromptSubmit"),additionalContext:o().optional(),sessionTitle:o().optional()',
     "UserPromptSubmit output accepts hookSpecificOutput.additionalContext"),
    ("hook_output.cap_table", b"additionalContext:8000,permissionDecisionReason:2000}", 90, 140,
     _regex_anchor(rb"\{reason:2000,stopReason:2000,systemMessage:4000,additionalContext:8000,"
                   rb"permissionDecisionReason:2000\}," + _IDENT + rb"=200,"),
     b"var T1={reason:2000,stopReason:2000,systemMessage:4000,additionalContext:8000,permissionDecisionReason:2000},rE=200,v1={reason:20}",
     "hook output cap table: additionalContext 8000 chars and 200 lines on the capped path"),
    ("instructionFiles.shape", b"instructionFiles that is not a list of { path, kind, content }", 0, 0,
     lambda w: "", b"instructionFiles that is not a list of { path, kind, content }",
     "instructionFiles hook output is a list of { path, kind, content }"),
    ("instructionFiles.kind_validation", b"an instruction file whose kind is not one of ", 0, 0,
     lambda w: "", b"an instruction file whose kind is not one of ",
     "instructionFiles entries are validated by kind"),
)


def _codex_schema_window(window):
    """The last top-level `"required"` array before the title, as a tuple."""
    matches = list(re.finditer(rb'\n  "required": \[\n((?:    "[^"]+",?\n)+)  \]', window))
    if not matches:
        return None
    return tuple(item.decode("ascii").strip().strip('",')
                 for item in matches[-1].group(1).split(b"\n") if item.strip())


def _codex_required_anchor(event):
    expected = CODEX_HOOK_INPUT_REQUIRED[event]

    def verify(window):
        found = _codex_schema_window(window)
        if found is None:
            return "no top-level required array before the title"
        if found != expected:
            return f"required {list(found)} != recorded {list(expected)}"
        return ""
    return verify


def _codex_enum_anchor(prop, expected):
    pattern = re.compile(
        rb'"' + prop.encode("ascii") + rb'": \{\n      "enum": \[\n((?:        "[^"]+",?\n)+)      \]')

    def verify(window):
        matches = list(pattern.finditer(window))
        if not matches:
            return f"no {prop} enum in window"
        found = tuple(item.decode("ascii").strip().strip('",')
                      for item in matches[-1].group(1).split(b"\n") if item.strip())
        return "" if found == tuple(expected) else f"{prop} enum {list(found)} != {list(expected)}"
    return verify


def _codex_presence_anchor(present, absent):
    def verify(window):
        for needle in present:
            if needle not in window:
                return f"missing {needle!r}"
        for needle in absent:
            if needle in window:
                return f"unexpected {needle!r}"
        return ""
    return verify


def codex_schema_sample(event, required=None, extra_props=""):
    """A minimal schema text in the binary's layout: `<kebab>.command.input{...}` then title."""
    kebab = CODEX_EVENT_KEBAB[event]
    required = CODEX_HOOK_INPUT_REQUIRED[event] if required is None else required
    props = ''.join(f'    "{name}": {{\n      "type": "string"\n    }},\n' for name in required)
    body = (f'{kebab}.command.input{{\n  "$schema": "x",\n  "properties": {{\n{props}{extra_props}'
            f'    "hook_event_name": {{\n      "const": "{event}",\n      "type": "string"\n    }}\n  }},\n'
            f'  "required": [\n' + "".join(f'    "{name}",\n' for name in required[:-1])
            + f'    "{required[-1]}"\n  ],\n  "title": "{kebab}.command.input",\n  "type": "object"\n}}')
    return body.encode("utf-8")


def _codex_anchor_table():
    anchors = [
        ("events.twelve", CODEX_EVENT_VARIANT_RUN, 0, 0, lambda w: "", CODEX_EVENT_VARIANT_RUN,
         "the twelve hook event names in one serde variant run"),
        ("project_doc_max_bytes.default", b"project_doc_max_bytes = 32768", 0, 0, lambda w: "",
         b"project_doc_max_bytes = 32768", "AGENTS chain budget default 32768 bytes"),
        ("pretooluse.ask_rejected_at_runtime",
         b"PreToolUse hook returned unsupported permissionDecision:ask", 0, 0, lambda w: "",
         b"PreToolUse hook returned unsupported permissionDecision:ask",
         "permissionDecision ask is parsed but rejected by the dispatcher"),
    ]
    for event in CODEX_HOOK_INPUT_REQUIRED:
        kebab = CODEX_EVENT_KEBAB[event]
        anchors.append((f"schema.{event}.required", f'"title": "{kebab}.command.input"'.encode("ascii"),
                        2600, 0, _codex_required_anchor(event), codex_schema_sample(event),
                        f"{event} input schema required fields"))
    session_sample = codex_schema_sample(
        "SessionStart",
        extra_props='    "source": {\n      "enum": [\n' + "".join(
            f'        "{s}",\n' for s in CODEX_SESSION_START_SOURCES[:-1])
        + f'        "{CODEX_SESSION_START_SOURCES[-1]}"\n      ],\n      "type": "string"\n    }},\n')
    anchors.append(("schema.SessionStart.source_enum", b'"title": "session-start.command.input"',
                    2600, 0, _codex_enum_anchor("source", CODEX_SESSION_START_SOURCES),
                    session_sample, "SessionStart source enum has no fork"))
    pretool_sample = codex_schema_sample(
        "PreToolUse",
        extra_props='    "permission_mode": {\n      "enum": [\n' + "".join(
            f'        "{m}",\n' for m in CODEX_PERMISSION_MODES[:-1])
        + f'        "{CODEX_PERMISSION_MODES[-1]}"\n      ],\n      "type": "string"\n    }},\n')
    anchors.append(("schema.PreToolUse.permission_mode_enum", b'"title": "pre-tool-use.command.input"',
                    2600, 0, _codex_enum_anchor("permission_mode", CODEX_PERMISSION_MODES),
                    pretool_sample, "permission_mode enum incl. bypassPermissions"))
    anchors.append(("schema.UserPromptSubmit.no_source", b"user-prompt-submit.command.input{", 0, 2600,
                    _codex_presence_anchor((b'"prompt": {',), (b'"source": {',)),
                    codex_schema_sample("UserPromptSubmit"),
                    "UserPromptSubmit input carries prompt and no source"))
    stop_sample = codex_schema_sample(
        "Stop",
        extra_props='    "last_assistant_message": {\n      "$ref": "#/definitions/NullableString"\n    },\n'
                    '    "stop_hook_active": {\n      "type": "boolean"\n    },\n')
    anchors.append(("schema.Stop.nullable_message", b'"title": "stop.command.input"', 2600, 0,
                    _codex_presence_anchor((b'"last_assistant_message": {\n      "$ref": "#/definitions/NullableString"',
                                            b'"stop_hook_active": {\n      "type": "boolean"'), ()),
                    stop_sample, "Stop input: last_assistant_message nullable, stop_hook_active boolean"))
    return tuple(anchors)


CODEX_RUNTIME_ANCHORS = _codex_anchor_table()

# What a host run would have to establish per runtime before any of the above counts as more
# than structural evidence. A record here is (runtime, scenario) -> {"host": ..., "date": ...,
# "result": ...}; none exists yet, so every scenario prints as UNVERIFIED.
HOST_SCENARIO_CATALOG = tuple(
    (runtime, scenario, meaning)
    for runtime in ("claude", "codex")
    for scenario, meaning in (
        ("allow", "a PreToolUse hook answering allow lets the call run"),
        ("deny", "a PreToolUse hook answering deny stops the call and the reason reaches the model"),
        ("malformed output", "a hook printing non-JSON is treated as the documented failure, not as allow"),
        ("crash", "a hook exiting non-zero without a reason is treated as the documented failure"),
        ("timeout", "a hook past its registered timeout is treated as the documented failure"),
        ("untrusted hook", "a changed or untrusted hook definition is skipped and reported"),
        ("delivered context", "additionalContext from SessionStart and UserPromptSubmit reaches the model"),
    )
)
HOST_SCENARIO_EVIDENCE = {}


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
                ["git", "-C", root, "ls-files", "-z"],
                capture_output=True, text=False,
            )
        except OSError as exc:
            # Git absent from PATH raised FileNotFoundError out through every caller, so
            # the gate died with a traceback and no verdict line. An unusable instrument
            # is a named failure of the checks that depend on it.
            return "source", [], f"cannot run git ls-files: {exc}"
        if tracked.returncode != 0:
            return "source", [], git_command_failure(tracked.returncode, tracked.stderr)
        raw = bytes(tracked.stdout or b"")
        if raw and not raw.endswith(b"\0"):
            return "source", [], "git ls-files returned an unterminated NUL inventory"
        paths = [item.decode("utf-8", "surrogateescape")
                 for item in raw.split(b"\0") if item]
        return "source", paths, None
    paths = []
    for dirpath, dirs, files in os.walk(root):
        # A directory carrying its own `.git` is a separate repository vendored inside this
        # tree, not content of the package being inventoried. Without the prune its files are
        # compared against the source as though the package shipped them, and the marker file
        # itself was listed as package content.
        if dirpath != root:
            try:
                boundary = _is_git_worktree_root(dirpath, runner, root)
            except RepositoryOwnershipError as exc:
                return "installed", [], f"cannot resolve Git ownership: {exc}"
            if boundary:
                dirs[:] = []
                continue
        # No filename filter for `.git` here: a directory holding one is pruned above, and a
        # root holding one never reaches this walk because package_paths takes the tracked
        # branch instead. The two conditions coincide, so the filter could not fire.
        dirs[:] = [d for d in dirs if d != ".git"]
        for filename in files:
            # A symlinked file is not package content: its bytes live outside the tree being
            # inventoried, and every consumer of this list reads the path. os.walk already
            # declines to descend a symlinked directory, so this is the same rule for the
            # file case. Nothing tracked in this repository is a symlink.
            full = os.path.join(dirpath, filename)
            if os.path.islink(full):
                continue
            paths.append(os.path.relpath(full, root))
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
    except (OSError, RepositoryOwnershipError) as exc:
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

def load_tool_module(name):
    """Import a hyphenated tool script by path; the gate's own tools, never the fixture's."""
    path = os.path.join(ROOT, "tools", f"{name}.py")
    spec = importlib.util.spec_from_file_location(f"_harness_check_{name.replace('-', '_')}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def normalize_policy_text(text):
    """Collapse markup and whitespace so a quoted phrase and its source compare as prose."""
    text = text.replace("`", "").replace("*", "").replace("’", "'")
    return re.sub(r"\s+", " ", text).strip().casefold()


def agents_sections(agents_text):
    """-> [(heading or '', text)] by `## ` heading, preamble first."""
    sections, heading, lines = [], "", []
    for line in agents_text.splitlines():
        if line.startswith("## "):
            sections.append((heading, "\n".join(lines)))
            heading, lines = line[3:].strip(), []
        else:
            lines.append(line)
    sections.append((heading, "\n".join(lines)))
    return sections


def claim_blocks(text):
    """-> [(first line number, block text)]: paragraphs, list items, table rows and headings.

    Lines inside a fenced code block (``` or ~~~) are examples, not prose, and are skipped.
    A table row is its own block: rows carry no sentence terminator, so a quoted phrase in
    one row and a file mention in another would otherwise read as one sentence.
    """
    blocks, current, start, fenced = [], [], 0, False
    for number, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
            if current:
                blocks.append((start, "\n".join(current)))
                current = []
            continue
        if fenced:
            continue
        item = re.match(r"\s*(?:(?:[-*+]|\d+\.)\s|\|)", line) is not None
        heading = line.startswith("#")
        if not line.strip():
            if current:
                blocks.append((start, "\n".join(current)))
                current = []
            continue
        if (item or heading) and current:
            blocks.append((start, "\n".join(current)))
            current = []
        if not current:
            start = number
        current.append(line)
        if heading:
            blocks.append((start, "\n".join(current)))
            current = []
    if current:
        blocks.append((start, "\n".join(current)))
    return blocks


def quote_binds(quote, policy_normalized):
    """Every ellipsis-separated fragment of the quote appears verbatim in the policy text, in order.

    An elision keeps the source order: each fragment is searched after the end of the
    previous match. Leftmost-after-the-previous-end is exact for the existence of an ordered
    occurrence, so a fragment that occurs twice binds when its later occurrence is in order.
    """
    # Punctuation at a fragment's boundary belongs to the citing sentence, not to the claim:
    # a skill may close its quote with a period where the policy continues with a comma.
    fragments = [normalize_policy_text(f).strip(" ,;:.!()[]") for f in QUOTE_ELLIPSIS.split(quote)]
    fragments = [f for f in fragments if f]
    # A fragment under three characters is a substring of almost any text and cites nothing.
    if not fragments or any(len(f) < 3 for f in fragments):
        return False
    position = 0
    for fragment in fragments:
        found = policy_normalized.find(fragment, position)
        if found < 0:
            return False
        position = found + len(fragment)
    return True


CLAIM_DISPLAY_LIMIT = 120


def claim_identity_key(text):
    """-> "sha256:" + the digest of the whitespace-collapsed claim text: the identity across
    line drift, never truncated, so an edit past any prefix is a new item."""
    collapsed = re.sub(r"\s+", " ", text).strip()
    return "sha256:" + hashlib.sha256(collapsed.encode("utf-8")).hexdigest()


def quote_list_key(quotes):
    """-> the identity text of a list of quotes: each whitespace-collapsed, then a JSON list,
    so a line wrapped inside a quote keeps the identity and two quotes never collide with one
    quote that holds a delimiter."""
    return json.dumps([re.sub(r"\s+", " ", q).strip() for q in quotes])


def claim_display(text, limit=CLAIM_DISPLAY_LIMIT):
    """-> the human-readable form of a claim for worklists and receipts; display only."""
    collapsed = re.sub(r"\s+", " ", text).strip()
    return collapsed if len(collapsed) <= limit else collapsed[:limit - 1] + "…"


def claim_findings(rel, text, agents_text):
    """-> (findings, counters) for one governed file.

    A finding is {"line", "kind", "key", "display", "reason"}; (rel, kind, key) is its
    identity in the shrink-only baseline, where key is the digest of the whole claim text,
    so a claim that moves to another line keeps its identity and a claim whose text changes
    anywhere is a new item. display is the readable form and carries no identity.
    """

    def finding(line, kind, text, reason, display=None):
        return {"line": line, "kind": kind, "key": claim_identity_key(text),
                "display": claim_display(text if display is None else display), "reason": reason}
    findings = []
    counters = {"claims": 0, "bound": 0}
    sections = agents_sections(agents_text)
    whole = normalize_policy_text(agents_text)
    by_heading = {h: normalize_policy_text(body) for h, body in sections if h}
    headings = sorted(by_heading, key=len, reverse=True)
    section_mention = re.compile(
        r"`?AGENTS\.md`?\s*(?:§|section)?\s*,?\s*(" + "|".join(re.escape(h) for h in headings)
        + r")(?![A-Za-z0-9-])"
    ) if headings else None
    sentences_seen = set()
    for start, block in claim_blocks(text):
        block = PRIVATE_USE.sub("", block)

        def line_of(offset):
            return start + block.count("\n", 0, offset)

        cited = False
        for match in POLICY_LINE_CITATION.finditer(block):
            citation = match.group(0).strip()
            findings.append(finding(line_of(match.start()), "line citation", citation,
                                    f"line citation {citation!r}: cite a verbatim phrase, never a "
                                    f"line number"))
            cited = True
        for match in BARE_LINE_CITATION.finditer(block):
            findings.append(finding(line_of(match.start()), "bare line citation", match.group(0),
                                    f"bare line citation {match.group(0)}: cite a verbatim phrase, "
                                    f"never a line number"))
            cited = True
        # A code span is an example, not prose: every span except the bare path, the bare
        # file name and a bare line citation is replaced by a token, so a quote inside a
        # command (`printf "x"`) is never a citation. Tokens are restored for the identity.
        spans = []

        def neutralize_span(match):
            span = match.group(2).strip()
            if span in ("~/.claude/CLAUDE.md", "AGENTS.md") or re.fullmatch(r":\d+(?:-\d+)?", span):
                return match.group(0)
            spans.append(match.group(0))
            return f"{len(spans) - 1}"
        prose = CODE_SPAN.sub(neutralize_span, block)
        # Mask every straight-quoted span before sentence splitting so a quoted question
        # mark or period cannot split the sentence that carries it. A quote that itself
        # contains a file mention (a stray quote earlier in the block, a quoted YAML value, a
        # fabricated quotation naming the file) still counts as a mention through its text.
        quotes = []

        def restore_spans(text):
            return SPAN_TOKEN.sub(lambda m: spans[int(m.group(1))], text)

        def mask(match):
            # A quote keeps the code spans it contains: `"Use `git grep -P` for PCRE atoms"`
            # must bind against the policy text, where the backticks are stripped anyway.
            quotes.append(restore_spans(match.group(1)))
            return f"{len(quotes) - 1}"
        masked = STRAIGHT_QUOTE.sub(mask, prose)

        def restored(text):
            text = QUOTE_TOKEN.sub(lambda m: '"' + quotes[int(m.group(1))] + '"', text)
            return restore_spans(text)

        def mentions(text):
            return ALWAYS_ON_PATH.search(text) is not None or "AGENTS.md" in text

        offset = 0
        for sentence in SENTENCE_BREAK.split(masked):
            position = masked.find(sentence, offset)
            offset = position + len(sentence) if position >= 0 else offset
            tokens = list(QUOTE_TOKEN.finditer(sentence))
            section = section_mention.search(sentence) if section_mention else None
            path_mention = ALWAYS_ON_PATH.search(sentence)
            # A straight-quoted phrase anywhere in a sentence that names AGENTS.md is the
            # citation: `AGENTS.md says "..."` and `The rule "..." is in AGENTS.md` carry the
            # same claim as `AGENTS.md "..."`, in either order and with any words between.
            agents_name = re.search(r"`?AGENTS\.md`?", sentence)
            quote_mention = agents_name if agents_name and tokens else None
            inner_mention = next((t for t in tokens if mentions(quotes[int(t.group(1))])), None)
            mention = path_mention or section or quote_mention or inner_mention
            if mention is None:
                continue
            # Report the line carrying the file mention, not the sentence's first line: a
            # masked quote or code span before the mention may have spanned lines, so add
            # those back.
            prefix = masked[:max(position, 0) + mention.start()]
            line = start + prefix.count("\n") + sum(
                quotes[int(n)].count("\n") for n in QUOTE_TOKEN.findall(prefix)) + sum(
                spans[int(n)].count("\n") for n in SPAN_TOKEN.findall(prefix))
            key = (line, sentence)
            if key in sentences_seen:
                continue
            sentences_seen.add(key)
            counters["claims"] += 1
            original = restored(sentence)
            # A sentence that cites a line number is already reported above. Without a quote
            # it is skipped so the citation stands alone; with quotes they are judged, so a
            # fabricated quotation cannot hide beside a citation.
            if not tokens and (POLICY_LINE_CITATION.search(original) or BARE_LINE_CITATION.search(original)):
                continue
            quoted = [quotes[int(t.group(1))] for t in tokens]
            negated = CLAIM_NEGATION.search(sentence) is not None
            scope = by_heading[section.group(1)] if section else whole
            where = f"AGENTS.md section {section.group(1)!r}" if section else "AGENTS.md"
            bound = [q for q in quoted if quote_binds(q, scope)]
            unbound = [q for q in quoted if not quote_binds(q, scope)]
            if not quoted:
                findings.append(finding(line, "unbound claim", original,
                                        "unbound claim about the always-on file: quote a verbatim "
                                        "AGENTS.md phrase in straight double quotes in the same "
                                        "sentence, or drop the claim"))
            elif negated and bound:
                findings.append(finding(line, "negated claim", quote_list_key(bound),
                                        f"negated claim contradicts {where}: {bound[0][:60]!r} is present",
                                        display=" | ".join(bound)))
            elif negated:
                counters["bound"] += 1
            elif unbound:
                # Every quote in a positive claim must bind, and every stale quote is part of
                # the identity, serialised as a JSON list so two quotes and one quote holding
                # a delimiter never collide: one verbatim phrase beside a stale one would
                # otherwise carry the stale one through, and a second stale quote could change
                # unnoticed.
                findings.append(finding(line, "stale quote", quote_list_key(unbound),
                                        f"stale quote: {unbound[0][:70]!r} is not verbatim in {where}"
                                        + (f" (+{len(unbound) - 1} more)" if len(unbound) > 1 else ""),
                                        display=" | ".join(unbound)))
            else:
                counters["bound"] += 1
    # Duplication: a policy sentence restated outside a quote is a second copy on the same
    # dispatch, which the routing rule forbids; a quoted citation is the sanctioned form.
    unquoted = normalize_policy_text(STRAIGHT_QUOTE.sub(" ", text))
    policy_prose = re.sub(r"^#.*$", "", agents_text, flags=re.M)
    for sentence in SENTENCE_BREAK.split(re.sub(r"\s+", " ", policy_prose)):
        if len(sentence.split()) < DUPLICATE_MIN_WORDS:
            continue
        needle = normalize_policy_text(sentence)
        if needle and needle in unquoted:
            words = [re.escape(w) for w in needle.split()[:6]]
            located = re.search(r"\s+".join(r"[`*]*" + w + r"[`*]*" for w in words), text, re.I)
            line = text.count("\n", 0, located.start()) + 1 if located else 1
            findings.append(finding(line, "duplicated policy sentence", sentence,
                                    f"duplicated policy sentence outside a quote: {sentence[:70]!r}"))
    return findings, counters



def vacuous_expect_red_lines(source_text):
    """-> line numbers of expect_red calls whose lambda cannot fail for the stated reason.

    Rejected: an `or` whose last operand is a parenthesised clause, a truthy constant or a
    negation (it holds whenever the real condition fails); a comprehension over an empty
    literal or an empty constructor call; a constant body. A leading platform gate
    (`sys.platform != "darwin" or ...`) keeps the check count equal across CI platforms and
    is the one sanctioned leading `or`; everything under it is judged like any other body.
    `x or ""` coalescing and ordinary disjunctions stay.
    """
    vacuous = []
    for node in ast.walk(ast.parse(source_text)):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "expect_red"):
            continue
        for arg in node.args:
            if not isinstance(arg, ast.Lambda):
                continue
            body = arg.body
            gate = (isinstance(body, ast.BoolOp) and isinstance(body.op, ast.Or)
                    and len(body.values) == 2 and isinstance(body.values[0], ast.Compare)
                    and (ast.get_source_segment(source_text, body.values[0]) or "").startswith("sys.platform"))
            judged = body.values[1] if gate else body
            text = ast.get_source_segment(source_text, judged) or ""

            def fallback(inner):
                last = inner.values[-1]
                return (isinstance(last, ast.UnaryOp) and isinstance(last.op, ast.Not)
                        or isinstance(last, ast.Constant) and bool(last.value))

            def empty(iterable):
                if isinstance(iterable, (ast.List, ast.Tuple, ast.Set)):
                    return not iterable.elts
                if isinstance(iterable, ast.Dict):
                    return not iterable.keys
                return (isinstance(iterable, ast.Call) and isinstance(iterable.func, ast.Name)
                        and iterable.func.id in ("list", "tuple", "dict", "set", "frozenset")
                        and not iterable.args and not iterable.keywords)

            has_fallback = " or (" in text or any(
                isinstance(inner, ast.BoolOp) and isinstance(inner.op, ast.Or) and fallback(inner)
                for inner in ast.walk(judged))
            empty_iteration = any(isinstance(inner, ast.comprehension) and empty(inner.iter)
                                  for inner in ast.walk(arg))
            if has_fallback or empty_iteration or isinstance(judged, ast.Constant):
                vacuous.append(node.lineno)
    return vacuous


class Run:
    def __init__(self, root, ci):
        self.root, self.ci, self.failures, self.checks = root, ci, [], 0
        self.worklists = {}
        # Structured results beside the printed verdicts, so a proof compares exact values
        # instead of searching a detail string: counters["C12"], ratchets["C12"/"C13"],
        # ceilings["C14"].
        self.counters, self.ratchets, self.ceilings = {}, {}, {}

    def worklist(self, check, item):
        """Print a live, baseline-covered item in full without counting it as a failure."""
        self.worklists.setdefault(check, []).append(item)
        print(f"  WORKLIST {check:4s} {item}")

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
        """Every script exposing --selftest is aggregated or explicitly classified.

        A script defining `perf_selftest` must also be registered with `--perf`: its own
        `--selftest` entry already aggregates the path, so deleting the perf entry alone
        would stop its wall-clock checks from running anywhere with this check still green.
        """
        suites = SELFTEST_SUITES if suites is None else suites
        exemptions = SELFTEST_EXEMPTIONS if exemptions is None else exemptions
        aggregated = {cmd[0] for _name, cmd, _floor in suites}
        perf_registered = {cmd[0] for _name, cmd, _floor in suites if cmd[1:] == ["--perf"]}
        actual = set()
        perf_actual = set()
        for rel_root in ("hooks", "tools", "instruments"):
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
                    if re.search(r"^def perf_selftest\(", text, re.M):
                        perf_actual.add(os.path.relpath(path, self.root))
        declared = aggregated | set(exemptions)
        unknown = sorted(actual - declared)
        stale = sorted(declared - actual)
        perf_unregistered = sorted(perf_actual - perf_registered)
        perf_stale = sorted(perf_registered - perf_actual)
        self.result(
            "C1", (bool(actual) and not unknown and not stale
                   and not perf_unregistered and not perf_stale),
            f"selftest inventory: discovered={len(actual)} aggregated={len(aggregated)} "
            f"exemptions={len(exemptions)} perf={len(perf_registered)}"
            + (f" unclassified={unknown}" if unknown else "")
            + (f" stale={stale}" if stale else "")
            + (f" perf-unregistered={perf_unregistered}" if perf_unregistered else "")
            + (f" perf-stale={perf_stale}" if perf_stale else ""),
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
        inventory = git_owned_live_paths(self.root)
        if inventory["error"]:
            self.result("C3", False,
                        f"cannot enumerate repository-owned references: {inventory['error']}")
            return
        root_real = os.path.realpath(self.root)
        owned = set()
        for relative in inventory["paths"]:
            full = os.path.join(self.root, relative)
            if os.path.islink(full) or not os.path.isfile(full):
                continue
            resolved_path = os.path.realpath(full)
            try:
                inside = os.path.commonpath([root_real, resolved_path]) == root_real
            except ValueError:
                inside = False
            if inside:
                owned.add(os.path.normpath(relative).replace(os.sep, "/"))

        reference_files = sorted(
            relative for relative in owned
            if re.fullmatch(r"skills/[^/]+/references/.+", relative)
        )
        resolved = 0
        for skill in sorted(os.listdir(skills_dir)):
            body_path = os.path.join(skills_dir, skill, "SKILL.md")
            if not os.path.isfile(body_path):
                continue
            body = open(body_path, encoding="utf-8").read()
            prefix = f"skills/{skill}/references/"
            cited = set(re.findall(
                r"references/([\w<>./\-]+\.(?:md|yaml))", body))
            literal = {c for c in cited if "<" not in c}
            template_res = [re.compile("^" + re.sub(r"<[^>]*>", r"[\\w.\\-]+", re.escape(c)) + "$")
                            for c in cited if "<" in c]
            # direction 1: cited -> exists
            for c in sorted(literal):
                resolved += 1
                self.result("C3", prefix + c in owned,
                            f"{skill}: cites references/{c}")
            # direction 2: exists -> cited (literal or template family)
            for relative in reference_files:
                if not relative.startswith(prefix):
                    continue
                name = relative[len(prefix):]
                ok = name in literal or any(t.match(name) for t in template_res)
                resolved += 1
                self.result("C3", ok, f"{skill}: references/{name} "
                                      f"{'reachable' if ok else 'NAMED NOWHERE in SKILL.md'}")
        # direction 3: a citation inside a reference document must resolve, or be declared
        # external. C3 read only SKILL.md, so a reference file could cite a document existing
        # nowhere and nothing looked -- which is how two skills came to cite a registry that
        # was never in this repository.
        # Prune nested checkouts. Every linked worktree carries its own `.git`, and this tree
        # keeps a dozen of them under an ignored directory -- 2235 of 2433 walked paths at the
        # time this was written. Left in, a citation to a file deleted from this repository
        # still resolves against a stale copy, and the check certifies a reference that is
        # gone. A directory holding `.git` is a different repository, not content of this one.
        scanned_docs = 0
        scanned_citations = 0
        cited_anywhere = set()

        def citation_candidates(document, skill, target):
            """Resolve locally first; use repository fallback only when unambiguous."""
            normalized_target = target.replace("\\", "/")
            exact = []
            for candidate in (
                os.path.normpath(os.path.join(os.path.dirname(document), normalized_target)),
                os.path.normpath(os.path.join(f"skills/{skill}", normalized_target)),
                os.path.normpath(normalized_target),
            ):
                candidate = candidate.replace(os.sep, "/")
                if candidate in owned and candidate not in exact:
                    exact.append(candidate)
            if exact:
                return exact
            fallback = []
            for candidate in owned:
                if not (candidate == normalized_target
                        or candidate.endswith("/" + normalized_target)):
                    continue
                if ("/" not in normalized_target and candidate.startswith("skills/")
                        and not candidate.startswith(f"skills/{skill}/")):
                    continue
                fallback.append(candidate)
            return sorted(fallback)

        for document in reference_files:
            if not document.endswith(".md"):
                continue
            parts = document.split("/")
            skill = parts[1]
            label = document[len("skills/"):]
            scanned_docs += 1
            try:
                text = open(os.path.join(self.root, document), encoding="utf-8").read()
            except OSError as exc:
                self.result("C3", False, f"{label}: unreadable ({exc})")
                continue
            targets = sorted({m.group(1) for m in REFERENCE_CITATION.finditer(text)})
            cited_anywhere.update(targets)
            for target in targets:
                if target in EXTERNAL_REFERENCE_CITATIONS:
                    continue
                scanned_citations += 1
                candidates = citation_candidates(document, skill, target)
                resolved += 1
                if len(candidates) == 1:
                    self.result("C3", True,
                                f"{label}: cites {target} -> {candidates[0]}")
                elif not candidates:
                    self.result("C3", False,
                                f"{label}: cites {target} -- resolves to no owned file")
                else:
                    self.result("C3", False,
                                f"{label}: cites {target} -- ambiguous: {candidates[:4]}")

        # An exemption that no document uses is dead weight that can silence a real defect
        # later without anyone re-reading it. Every declared external name must be cited by
        # something, or the declaration is removed rather than kept as a standing allowance.
        # Only against this repository: the allowlist describes these documents, so a planted
        # fixture tree cannot answer the question. And these do not count toward `resolved`,
        # which means authored reference relationships -- counting them defeated the
        # zero-reference guard below, because six exemptions made an empty scan look populated.
        if os.path.realpath(self.root) == os.path.realpath(ROOT):
            for declared in sorted(EXTERNAL_REFERENCE_CITATIONS):
                reached = declared in cited_anywhere
                self.result("C3", reached,
                            f"external citation {declared} is "
                            f"{'used' if reached else 'DECLARED BUT CITED NOWHERE'}")

        # The scan set is part of the claim. This matcher models a backticked token only, so
        # a bare filename in prose is a mention rather than a citation and is deliberately out
        # of scope; measured over this tree, every unbackticked non-resolving token is a
        # mention carrying no line number. Say so in the verdict rather than letting a clean
        # run imply that every spelling was examined.
        self.result(
            "C3", scanned_docs == 0 or scanned_citations > 0,
            f"citation resolution over {scanned_docs} reference document(s), "
            f"{scanned_citations} backticked citation(s); unbackticked prose mentions "
            f"are out of scope")

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
        # Emit one fixed-cardinality verdict per required handler. Counting the handlers
        # discovered in settings made a deletion shrink the selector, so the mutation was
        # caught but could not prove the same suite ran. Exact argv also rejects shell
        # wrappers such as ``VAR=off ...`` and ``... || true`` that name the script while
        # disabling or masking it.
        actual_claude_handlers = []
        malformed_claude_handlers = 0
        hook_events = st.get("hooks", {})
        if not isinstance(hook_events, dict):
            hook_events = {}
            malformed_claude_handlers += 1
        for event, entries in hook_events.items():
            if not isinstance(entries, list):
                malformed_claude_handlers += 1
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    malformed_claude_handlers += 1
                    continue
                handlers = entry.get("hooks", [])
                if not isinstance(handlers, list):
                    malformed_claude_handlers += 1
                    continue
                for handler in handlers:
                    if not isinstance(handler, dict):
                        malformed_claude_handlers += 1
                        continue
                    actual_claude_handlers.append(
                        (event, entry.get("matcher"), handler))
        def command_argv(handler):
            try:
                return shlex.split(handler.get("command", ""))
            except (TypeError, ValueError):
                return []
        for event, matcher, script, required_args in REQUIRED_CLAUDE_HANDLERS:
            expected_argv = ["python3", f"~/.claude/{script}", *required_args]
            matches = [
                handler for actual_event, actual_matcher, handler
                in actual_claude_handlers
                if actual_event == event and actual_matcher == matcher
                and handler.get("type") == "command"
                and handler.get("timeout") == 5
                and handler.get("async", False) is False
                and command_argv(handler) == expected_argv
                and os.path.isfile(os.path.join(self.root, script))
            ]
            self.result("C7", len(matches) == 1,
                        f"settings.json {event} matcher={matcher!r} -> {script}: "
                        f"argv={expected_argv!r} timeout=5: {len(matches)} match(es)")
        self.result(
            "C7", (len(actual_claude_handlers) == len(REQUIRED_CLAUDE_HANDLERS)
                   and malformed_claude_handlers == 0),
            "settings.json Claude handler inventory is closed: "
            f"{len(actual_claude_handlers)} handler(s), "
            f"expected {len(REQUIRED_CLAUDE_HANDLERS)}; "
            f"malformed={malformed_claude_handlers}",
        )
        codex_hooks_path = os.path.join(self.root, "hooks", "hooks.json")
        try:
            codex_hooks = json.load(open(codex_hooks_path))
        except Exception as exc:
            self.result("C7", False, f"Codex hooks config parses: {exc}")
            codex_hooks = {}
        inventory = []
        malformed_codex_handlers = 0
        codex_events = codex_hooks.get("hooks", {}) if isinstance(codex_hooks, dict) else {}
        if not isinstance(codex_events, dict):
            malformed_codex_handlers += 1
            codex_events = {}
        for event, entries in codex_events.items():
            if not isinstance(entries, list):
                malformed_codex_handlers += 1
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    malformed_codex_handlers += 1
                    continue
                hooks = entry.get("hooks", [])
                if not isinstance(hooks, list):
                    malformed_codex_handlers += 1
                    continue
                for hook in hooks:
                    try:
                        command = hook.get("command", "")
                        match = (re.search(
                            r"\$\{PLUGIN_ROOT\}/([\w./\-]+\.(?:py|sh))", command)
                            if isinstance(command, str) else None)
                        rel = match.group(1) if match else None
                        try:
                            argv = (shlex.split(command)
                                    if isinstance(command, str) else [])
                        except (TypeError, ValueError):
                            argv = []
                        if rel is None or not argv:
                            malformed_codex_handlers += 1
                        inventory.append({
                            "event": event,
                            "matcher": entry.get("matcher"),
                            "rel": rel,
                            "argv": argv,
                            "type": hook.get("type"),
                            "timeout": hook.get("timeout"),
                            "async": hook.get("async", False),
                        })
                    except (AttributeError, TypeError, ValueError):
                        # Keep C7's fixed-cardinality receipt even when a malformed
                        # handler defeats an individual traversal predicate.
                        malformed_codex_handlers += 1
                        inventory.append({
                            "event": event, "matcher": entry.get("matcher"),
                            "rel": None, "argv": [], "type": None,
                            "timeout": None, "async": None,
                        })
        for event, matcher, rel, required_args in REQUIRED_CODEX_HANDLERS:
            candidates = [item for item in inventory
                          if item["event"] == event and item["matcher"] == matcher
                          and item["rel"] == rel]
            expected_argv = ["python3", f"${{PLUGIN_ROOT}}/{rel}", *required_args]
            exact = [item for item in candidates if item["argv"] == expected_argv]
            execution = [item for item in exact
                         if item["type"] == "command" and item["timeout"] == 5
                         and item["async"] is False]
            self.result("C7", len(exact) == 1,
                        f"required Codex handler {event} matcher={matcher!r} -> {rel} "
                        f"argv={expected_argv!r}: {len(exact)} match(es)")
            self.result("C7", len(execution) == 1,
                        f"Codex {event} {rel}: type=command timeout=5 async=false: "
                        f"{len(execution)} match(es)")
            self.result("C7", os.path.isfile(os.path.join(self.root, rel)),
                        f"Codex {event} -> {rel}")
        self.result(
            "C7", (len(inventory) == len(REQUIRED_CODEX_HANDLERS)
                   and malformed_codex_handlers == 0),
            "Codex handler inventory is closed: "
            f"{len(inventory)} handler(s), expected {len(REQUIRED_CODEX_HANDLERS)}; "
            f"malformed={malformed_codex_handlers}",
        )
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

    # ---- C12 ---------------------------------------------------------------
    def c12_claim_binding(self):
        """Every skill claim about the always-on file binds to verbatim AGENTS.md text."""
        source = os.path.join(self.root, "AGENTS.md")
        try:
            if os.path.islink(source) or not os.path.isfile(source):
                raise OSError("absent or symlinked outside the governed regular-file profile")
            agents_text = open(source, encoding="utf-8").read()
        except OSError as exc:
            self.result("C12", False, f"cannot enforce: AGENTS.md unreadable: {exc}")
            return
        skills_dir = os.path.join(self.root, "skills")
        if not os.path.isdir(skills_dir) or os.path.islink(skills_dir):
            self.result("C12", False, "cannot enforce: skills directory absent or symlinked")
            return
        governed = {}
        try:
            for skill in sorted(os.listdir(skills_dir)):
                skill_root = os.path.join(skills_dir, skill)
                if not os.path.isdir(skill_root):
                    continue
                if os.path.islink(skill_root):
                    raise OSError(f"skills/{skill} is a symlink")
                body = os.path.join(skill_root, "SKILL.md")
                if os.path.isfile(body) and not os.path.islink(body):
                    governed[f"skills/{skill}/SKILL.md"] = open(body, encoding="utf-8").read()
                references = os.path.join(skill_root, "references")
                if not os.path.isdir(references) or os.path.islink(references):
                    continue
                for current, directories, files in os.walk(references):
                    directories[:] = sorted(d for d in directories
                                            if d not in {"evals", "scripts", "assets"}
                                            and not os.path.islink(os.path.join(current, d)))
                    for filename in sorted(files):
                        if os.path.splitext(filename)[1].lower() not in {".md", ".yaml", ".yml"}:
                            continue
                        path = os.path.join(current, filename)
                        if os.path.islink(path) or not os.path.isfile(path):
                            raise OSError(f"reference file absent or symlinked: {path}")
                        relative = os.path.relpath(path, self.root).replace(os.sep, "/")
                        governed[relative] = open(path, encoding="utf-8").read()
        except (OSError, UnicodeError) as exc:
            self.result("C12", False, f"cannot enforce: governed corpus unreadable: {exc}")
            return
        if not governed:
            self.result("C12", False, "cannot enforce: zero governed files")
            return
        try:
            evals = load_tool_module("run-skill-evals")
            worklists, baseline_error = evals.load_worklists(self.root)
        except Exception as exc:
            worklists, baseline_error = None, f"baseline loader failed: {exc!r}"
        baseline = {(i["file"], i["kind"], i["key"]) for i in worklists["C12"]} if worklists else set()
        claims = bound = 0
        live = {}
        for rel, text in sorted(governed.items()):
            findings, counters = claim_findings(rel, text, agents_text)
            claims += counters["claims"]
            bound += counters["bound"]
            for finding in sorted(findings, key=lambda f: (f["line"], f["kind"], f["key"])):
                live.setdefault((rel, finding["kind"], finding["key"]), []).append(finding)
        new, stale = evals.ratchet(live, baseline) if worklists is not None else (sorted(live), [])
        # One identity may occur more than once in a file (the same stale quote twice); every
        # occurrence prints, and the identity leaves the baseline only when none is left.
        in_baseline = occurrences = 0
        for identity, found in sorted(live.items(), key=lambda kv: (kv[0][0], kv[1][0]["line"], kv[0][1])):
            rel = identity[0]
            in_baseline += identity in baseline
            for finding in sorted(found, key=lambda f: f["line"]):
                occurrences += 1
                item = f"{rel}:{finding['line']}: {finding['reason']}"
                if identity in baseline:
                    self.worklist("C12", item)
                else:
                    self.result("C12", False, f"{item} (not in baseline {evals.WORKLISTS})")
        displays = {(i["file"], i["kind"], i["key"]): i.get("display", "") for i in worklists["C12"]} \
            if worklists else {}
        for rel, kind, key in stale:
            self.result("C12", False,
                        f"stale baseline: {evals.WORKLISTS} C12 lists {rel} {kind} "
                        f"{displays.get((rel, kind, key), '')[:60]!r} ({key[:19]}…), which is no "
                        f"longer found; shrink the baseline in the same change")
        if baseline_error:
            self.result("C12", False, f"cannot apply the ratchet: {baseline_error}")
        self.counters["C12"] = {"claims": claims, "bound": bound}
        self.ratchets["C12"] = {"baseline": len(baseline), "live": len(live), "in_baseline": in_baseline,
                                "new": len(new), "stale": len(stale), "occurrences": occurrences}
        self.result(
            "C12", not new and not stale and not baseline_error,
            f"always-on claims bind to verbatim AGENTS.md text: {claims} claim sentence(s) over "
            f"{len(governed)} governed file(s), {bound} bound, {len(live)} finding identity(ies) "
            f"over {occurrences} occurrence(s): {in_baseline} in the shrink-only baseline, "
            f"{len(new)} new, {len(stale)} stale; "
            f"scope: {C12_SCOPE}",
        )

    # ---- C13 ---------------------------------------------------------------
    def c13_eval_coverage(self):
        """release/evals.json accounts for every skill; the unlisted set is the worklist."""
        try:
            evals = load_tool_module("run-skill-evals")
            verdict = evals.coverage_verdict(self.root)
        except Exception as exc:
            self.result("C13", False, f"cannot enforce: eval coverage module failed: {exc!r}")
            return
        summary = verdict["summary"]
        for name in verdict["in_baseline"]:
            self.worklist("C13", f"unlisted skill {name}: add a tested or exempt entry to "
                                 f"{EVAL_MANIFEST} and remove it from {evals.WORKLISTS}")
        for problem in verdict["hard"]:
            self.result("C13", False, problem)
        for name in verdict["new"]:
            self.result("C13", False, f"unlisted skill {name}: not in the baseline {evals.WORKLISTS}")
        for name in verdict["stale"]:
            self.result("C13", False, f"stale baseline: {evals.WORKLISTS} C13 lists {name}, which is "
                                      f"no longer unlisted; shrink the baseline in the same change")
        if verdict["baseline_error"]:
            self.result("C13", False, f"cannot apply the ratchet: {verdict['baseline_error']}")
        listed = summary["tested"] + summary["exempt"]
        red = (verdict["hard"] or verdict["new"] or verdict["stale"] or verdict["baseline_error"])
        self.ratchets["C13"] = {"baseline": len(verdict["in_baseline"]) + len(verdict["stale"]),
                                "live": len(verdict["unlisted"]), "in_baseline": len(verdict["in_baseline"]),
                                "new": len(verdict["new"]), "stale": len(verdict["stale"])}
        self.result(
            "C13", not red and listed > 0,
            f"eval coverage manifest {EVAL_MANIFEST}: tested={summary['tested']} "
            f"exempt={summary['exempt']} unlisted={verdict['unlisted']} "
            f"({len(verdict['in_baseline'])} in the shrink-only baseline, {len(verdict['new'])} new, "
            f"{len(verdict['stale'])} stale) unknown={summary['unknown']} "
            f"required_scenarios={summary['required']}",
        )

    # ---- C14 ---------------------------------------------------------------
    def c14_budget_ceilings(self):
        """Recorded ceilings fail only on growth; the hard margins sit under the runtime caps."""
        path = os.path.join(self.root, BUDGET_CEILINGS)
        try:
            record = json.load(open(path, encoding="utf-8"))
            ceilings = record["ceilings"]
            hard = record["hard"]
            if record.get("schema_version") != 1 or not isinstance(ceilings, dict) \
                    or not isinstance(hard, dict):
                raise ValueError("schema_version 1 with ceilings and hard objects expected")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self.result("C14", False, f"cannot enforce: {BUDGET_CEILINGS} unusable: {exc}")
            return
        try:
            agents_bytes = os.path.getsize(os.path.join(self.root, "AGENTS.md"))
        except OSError as exc:
            self.result("C14", False, f"cannot measure AGENTS.md: {exc}")
            return
        try:
            installer = load_tool_module("install-claude")
            generated = installer.render_instruction_file(self.root)
        except Exception as exc:
            self.result("C14", False, f"cannot render the instruction file: {exc!r}")
            return
        generated_bytes = len(generated.encode("utf-8"))
        generated_lines = len(generated.splitlines())
        measured = (
            ("AGENTS.md", "bytes", agents_bytes),
            ("generated-instruction-file", "bytes", generated_bytes),
            ("generated-instruction-file", "lines", generated_lines),
        )
        surfaces = self.ceilings.setdefault("C14", {})
        for name, unit, current in measured:
            recorded = ceilings.get(name, {}).get(unit) if isinstance(ceilings.get(name), dict) else None
            if not isinstance(recorded, int):
                surfaces[f"{name}:{unit}"] = {"measured": current, "recorded": None, "verdict": "unrecorded"}
                self.result("C14", False, f"{name} {unit}: no recorded ceiling in {BUDGET_CEILINGS}")
                continue
            verdict = "equal" if current == recorded else ("grew" if current > recorded else "shrank")
            surfaces[f"{name}:{unit}"] = {"measured": current, "recorded": recorded, "verdict": verdict}
            note = {"equal": "", "grew": " (grew; raise the record only with the content that justifies it)",
                    "shrank": " (shrank; the record can be lowered)"}[verdict]
            self.result("C14", verdict != "grew",
                        f"{name}: {current} {unit} <= recorded ceiling {recorded}{note}")
        expected_hard = {
            "claude-hook-context-cap": {"chars": CLAUDE_HOOK_CONTEXT_CHAR_CAP,
                                        "lines": CLAUDE_HOOK_CONTEXT_LINE_CAP},
            "claude-dynamic-block": {"chars": CLAUDE_DYNAMIC_BLOCK_CHAR_CEILING,
                                     "lines": CLAUDE_DYNAMIC_BLOCK_LINE_CEILING},
            "prompt-submit-carrier": {"bytes": PROMPT_SUBMIT_CARRIER_BYTE_CEILING},
            "codex-session-start-injection": {"bytes": CODEX_SESSION_START_BYTE_CEILING},
        }
        self.result("C14", hard == expected_hard,
                    f"hard caps and ceilings recorded in {BUDGET_CEILINGS} match the gate's "
                    f"constants: {hard == expected_hard}")
        self.result(
            "C14",
            CLAUDE_DYNAMIC_BLOCK_CHAR_CEILING < CLAUDE_HOOK_CONTEXT_CHAR_CAP
            and CLAUDE_DYNAMIC_BLOCK_LINE_CEILING < CLAUDE_HOOK_CONTEXT_LINE_CAP,
            f"Claude dynamic hook block ceiling {CLAUDE_DYNAMIC_BLOCK_CHAR_CEILING} chars / "
            f"{CLAUDE_DYNAMIC_BLOCK_LINE_CEILING} lines sits under the runtime cap "
            f"{CLAUDE_HOOK_CONTEXT_CHAR_CAP} / {CLAUDE_HOOK_CONTEXT_LINE_CAP}",
        )
        adapter = os.path.join(self.root, "hooks", "codex_session_start.py")
        try:
            match = CODEX_SESSION_START_CONSTANT.search(open(adapter, encoding="utf-8").read())
            adapter_cap = int(match.group(1).replace("_", "")) if match else None
        except OSError:
            adapter_cap = None
        self.result("C14", adapter_cap == CODEX_SESSION_START_BYTE_CEILING,
                    f"Codex session-start injection budget in the adapter is "
                    f"{adapter_cap} == {CODEX_SESSION_START_BYTE_CEILING}")

    # ---- C15 ---------------------------------------------------------------
    def c15_envelope_fixtures(self):
        """Every committed hook envelope decodes against its event's required-field list."""
        directory = os.path.join(self.root, CODEX_FIXTURE_DIR)
        if not os.path.isdir(directory):
            self.result("C15", False, f"{CODEX_FIXTURE_DIR} is absent")
            return
        present = sorted(name for name in os.listdir(directory) if name.endswith(".json"))
        for name in sorted(set(present) - set(CODEX_FIXTURES)):
            self.result("C15", False, f"{CODEX_FIXTURE_DIR}/{name}: fixture not registered in "
                        f"CODEX_FIXTURES; register it with its event")
        decoded = 0
        for name, event in sorted(CODEX_FIXTURES.items()):
            path = os.path.join(directory, name)
            try:
                envelope = json.load(open(path, encoding="utf-8"))
            except (OSError, ValueError) as exc:
                self.result("C15", False, f"{CODEX_FIXTURE_DIR}/{name}: does not decode: {exc}")
                continue
            problems = []
            if not isinstance(envelope, dict):
                problems.append("top level is not an object")
            else:
                if envelope.get("hook_event_name") != event:
                    problems.append(f"hook_event_name {envelope.get('hook_event_name')!r} != {event!r}")
                if event not in CODEX_VALID_HOOK_EVENTS:
                    problems.append(f"{event} is not an accepted Codex event")
                missing = [key for key in CODEX_HOOK_INPUT_REQUIRED[event] if key not in envelope]
                if missing:
                    problems.append(f"missing required field(s) {missing}")
                for key in ("transcript_path", "cwd"):
                    value = envelope.get(key)
                    if isinstance(value, str) and HOST_PATH_CONTENT.search(value.encode("utf-8")):
                        problems.append(f"{key} carries an absolute host path; scrub it")
                if event == "Stop":
                    if not isinstance(envelope.get("stop_hook_active"), bool):
                        problems.append("stop_hook_active is not a boolean")
                    message = envelope.get("last_assistant_message")
                    if message is not None and not isinstance(message, str):
                        problems.append("last_assistant_message is neither a string nor null")
            if problems:
                self.result("C15", False, f"{CODEX_FIXTURE_DIR}/{name}: " + "; ".join(problems))
            else:
                decoded += 1
        readme = os.path.join(directory, "README.md")
        try:
            readme_text = open(readme, encoding="utf-8").read()
        except OSError:
            readme_text = ""
        for name in sorted(CODEX_SYNTHETIC_FIXTURES):
            labeled = (name in readme_text and "synthetic" in readme_text.lower()
                       and "synthetic" in name.lower())
            self.result("C15", labeled,
                        f"{CODEX_FIXTURE_DIR}/{name} is labeled synthetic in its filename and README")
        stop_path = os.path.join(self.root, CLAUDE_STOP_FIXTURE)
        try:
            stop = json.load(open(stop_path, encoding="utf-8"))
            stop_ok = (isinstance(stop, dict) and stop.get("hook_event_name") == "Stop"
                       and isinstance(stop.get("last_assistant_message"), str)
                       and isinstance(stop.get("stop_hook_active"), bool))
        except (OSError, ValueError):
            stop_ok = False
        self.result("C15", stop_ok, f"{CLAUDE_STOP_FIXTURE} decodes as a Claude Stop envelope")
        self.result("C15", decoded == len(CODEX_FIXTURES),
                    f"{decoded} of {len(CODEX_FIXTURES)} Codex envelope fixtures decode against "
                    f"their event's required-field list ({len(present)} json file(s) present)")


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


# ---- --verify-runtime --------------------------------------------------------------
def discover_claude_binaries():
    """-> [(label, path)]: the CLI the launcher symlink resolves to, and every desktop build."""
    found = []
    launcher = os.path.expanduser("~/.local/bin/claude")
    if os.path.lexists(launcher):
        found.append(("claude-cli", os.path.realpath(launcher)))
    pattern = os.path.expanduser(
        "~/Library/Application Support/Claude/claude-code/*/*/claude.app/Contents/MacOS/claude")
    for path in sorted(__import__("glob").glob(pattern)):
        found.append(("claude-desktop", path))
    return found


def discover_codex_binaries():
    """-> [(label, path, version)]: the native binary behind the `codex` launcher on PATH."""
    launcher = shutil.which("codex")
    if not launcher:
        return []
    real = os.path.realpath(launcher)
    package = os.path.dirname(os.path.dirname(real))
    version = None
    try:
        version = json.load(open(os.path.join(package, "package.json"), encoding="utf-8")).get("version")
    except (OSError, ValueError):
        pass
    candidates = sorted(
        __import__("glob").glob(os.path.join(package, "node_modules", "@openai", "codex-*", "vendor", "*", "bin", "codex"))
        + __import__("glob").glob(os.path.join(package, "vendor", "*", "bin", "codex")))
    return [("codex", path, version or "unknown") for path in candidates]


def claude_binary_version(data):
    match = re.search(rb"// Version: (\d+\.\d+\.\d+)", data)
    return match.group(1).decode("ascii") if match else "unknown"


def verify_anchor(data, anchor, max_occurrences=200):
    """-> (ok, detail): the anchor holds when any occurrence's window satisfies its check."""
    name, needle, before, after, verify, _sample, _meaning = anchor
    start = 0
    seen = 0
    last_error = "needle absent"
    while seen < max_occurrences:
        index = data.find(needle, start)
        if index < 0:
            break
        seen += 1
        window = data[max(0, index - before):index + len(needle) + after]
        error = verify(window)
        if not error:
            return True, f"{name}: ok at byte {index} ({seen} occurrence(s) scanned)"
        last_error = error
        start = index + 1
    return False, f"{name}: {last_error} ({seen} occurrence(s) scanned)"


def verify_runtime(out=sys.stdout, claude=None, codex=None, catalog=HOST_SCENARIO_CATALOG,
                   evidence=None):
    """Structural evidence from the installed binaries; every host scenario not run is UNVERIFIED."""
    p = lambda *a: print(*a, file=out)
    evidence = HOST_SCENARIO_EVIDENCE if evidence is None else evidence
    claude = discover_claude_binaries() if claude is None else claude
    codex = discover_codex_binaries() if codex is None else codex
    p(f"harness_check {VERSION} --verify-runtime (structural evidence only; fixed-window byte searches)")
    anchors = failures = binaries = 0
    labels = {label for label, _path in claude} | {label for label, _path, _version in codex}
    for required_label in ("claude-cli", "claude-desktop", "codex"):
        if required_label not in labels:
            failures += 1
            p(f"  FAIL no {required_label} binary found")
    for label, path in claude:
        try:
            data = open(path, "rb").read()
        except OSError as exc:
            failures += 1
            p(f"  FAIL {label} {path}: unreadable ({exc})")
            continue
        binaries += 1
        p(f"  binary {label} version={claude_binary_version(data)} bytes={len(data)} {path}")
        for anchor in CLAUDE_RUNTIME_ANCHORS:
            ok, detail = verify_anchor(data, anchor)
            anchors += 1
            failures += not ok
            p(f"    {'PASS' if ok else 'FAIL'} {label} {detail}; {anchor[6]}")
    for label, path, version in codex:
        try:
            data = open(path, "rb").read()
        except OSError as exc:
            failures += 1
            p(f"  FAIL {label} {path}: unreadable ({exc})")
            continue
        binaries += 1
        p(f"  binary {label} version={version} bytes={len(data)} {path}")
        for anchor in CODEX_RUNTIME_ANCHORS:
            ok, detail = verify_anchor(data, anchor)
            anchors += 1
            failures += not ok
            p(f"    {'PASS' if ok else 'FAIL'} {label} {detail}; {anchor[6]}")
    unverified = 0
    p("  host scenarios (a binary anchor never establishes any of these):")
    for runtime, scenario, meaning in catalog:
        record = evidence.get((runtime, scenario))
        if record:
            p(f"    RECORDED {runtime} {scenario}: {record}")
        else:
            unverified += 1
            p(f"    UNVERIFIED {runtime} {scenario}: no host run recorded; would establish that {meaning}")
    code = 1 if failures else 0
    p(f"RUNTIME-VERIFY-SUMMARY binaries={binaries} anchors={anchors} failures={failures} "
      f"unverified_scenarios={unverified} exit={code}")
    return code


# ---- selftest: every check proves it can go red -------------------------------
def selftest():
    from unittest.mock import patch

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
        open(os.path.join(sk, "beta/references/orphan.txt"), "w").write("named nowhere")
        # C3 direction 3: a reference document citing a document that exists nowhere, beside
        # one citing a declared-external name. Both in the same file, so a check that simply
        # refuses every citation would fail the second and be visible as over-refusal.
        # `beta/references/present.md` names a real file by a partial path, which only
        # resolves through the suffix rule. Without it a citation that omits a leading
        # component is reported as missing, which is how this check first false-positived on
        # a document that plainly exists.
        open(os.path.join(sk, "beta/references/present.md"), "a").write(
            "\n\nSee `NO-SUCH-REGISTRY.md`, `probe.py`, "
            "`beta/references/present.md`, `NO-SUCH-SUFFIXED.md:12`, and "
            "`ONLY-IN-NESTED.md` for the rest.\n")
        os.makedirs(os.path.join(sk, "alpha", "references", "nested"))
        os.makedirs(os.path.join(sk, "alpha", "references", "other"))
        open(os.path.join(sk, "alpha", "SKILL.md"), "a").write(
            "\nRead references/nested/deep.md, references/nested/local.md, "
            "and references/other/local.md\n")
        open(os.path.join(sk, "alpha", "references", "nested", "deep.md"), "w").write(
            "See `NESTED-MISSING.md`, `ONLY-BETA.md`, `local.md`, and "
            "`references/shared.md`.\n")
        open(os.path.join(sk, "alpha", "references", "nested", "local.md"), "w").write(
            "document-local\n")
        open(os.path.join(sk, "alpha", "references", "other", "local.md"), "w").write(
            "same-skill suffix fallback must remain ambiguous\n")
        open(os.path.join(sk, "beta", "references", "local.md"), "w").write(
            "sibling fallback must not win\n")
        open(os.path.join(sk, "alpha", "references", "shared.md"), "w").write(
            "skill-local\n")
        os.makedirs(os.path.join(td, "references"))
        open(os.path.join(td, "references", "shared.md"), "w").write("repo-root\n")
        open(os.path.join(sk, "beta", "ONLY-BETA.md"), "w").write("wrong sibling\n")
        os.symlink(os.devnull,
                   os.path.join(sk, "beta", "references", "escaped.md"))
        open(os.path.join(sk, "beta", "references", "present.md"), "a").write(
            "See `escaped.md`.\n")
        # A nested checkout holding a file by the same name must not satisfy a citation. It is
        # a different repository's copy, and letting it resolve certifies a reference this
        # tree no longer has.
        nested_repo = os.path.join(td, "nested-checkout")
        os.makedirs(nested_repo)
        subprocess.run(["git", "init", "--quiet", nested_repo], check=True)
        open(os.path.join(nested_repo, "ONLY-IN-NESTED.md"), "w").write("copy")
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
        # These fixtures test timeout dispatch and margins, not receipt counts. Keep
        # their synthetic success receipt valid when the registered corpus grows.
        passing_bash_receipt = (
            "SELFTEST-SUMMARY suite=bash_command_guard-perf "
            f"checks={expected_selftest_checks('bash_command_guard-perf')} failures=0\n"
        ).encode("utf-8")
        def record_c1_timeout(*args, **kwargs):
            observed_timeouts.append(kwargs.get("timeout"))
            return subprocess.CompletedProcess(
                args[0], 0,
                passing_bash_receipt,
                b"")
        subprocess.run = record_c1_timeout
        try:
            c1_timeout = Run(td, ci=True)
            c1_timeout.c1_selftests(
                [("bash_command_guard-perf", [stub_suite], 1)],
                sources=planted_sources("bash_command_guard-perf", stub_suite))
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
            lambda: SELFTEST_TIMEOUTS["bash_command_guard-perf"] == 90,
        )
        expect_red(
            "the Bash guard's selftest suite keeps its measured 30 s budget",
            lambda: SELFTEST_TIMEOUTS["bash_command_guard"] == 30,
        )
        expect_red(
            "the grep guard's perf suite keeps its measured 30 s budget",
            lambda: SELFTEST_TIMEOUTS["git_grep_engine_guard-perf"] == 30,
        )
        expect_red(
            "the registered CI-gate timeout retains measured headroom",
            lambda: SELFTEST_TIMEOUTS["ci-gate"] == 120,
        )
        expect_red(
            "the registered fuzz-judge-diff timeout retains measured headroom",
            lambda: SELFTEST_TIMEOUTS["fuzz-judge-diff"] == 25,
        )

        announced_timeouts = []
        def record_announced_timeout(*args, **kwargs):
            announced_timeouts.append(kwargs.get("timeout"))
            return subprocess.CompletedProcess(
                args[0], 0,
                b"SELFTEST-SUMMARY suite=announced_work_guard checks=922 failures=0\n",
                b"")
        subprocess.run = record_announced_timeout
        try:
            c1_announced_timeout = Run(td, ci=True)
            c1_announced_timeout.c1_selftests(
                [("announced_work_guard", [stub_suite], 922)],
                sources=planted_sources("announced_work_guard", stub_suite))
        finally:
            subprocess.run = original_subprocess_run
        expect_red(
            "C1 gives the process-level announced-work suite measured timeout headroom",
            lambda: SELFTEST_TIMEOUTS["announced_work_guard"] == 60
            and announced_timeouts == [60] and not c1_announced_timeout.failures,
        )

        slow_timeouts = []
        def slow_run(*args, **kwargs):
            slow_timeouts.append(kwargs.get("timeout"))
            time.sleep(0.05)
            return subprocess.CompletedProcess(
                args[0], 0,
                passing_bash_receipt,
                b"")
        subprocess.run = slow_run
        try:
            c1_margin = Run(td, ci=True)
            c1_margin.c1_selftests(
                [("bash_command_guard-perf", [stub_suite], 1)],
                sources=planted_sources("bash_command_guard-perf", stub_suite),
                )
        finally:
            subprocess.run = original_subprocess_run
        margin_clean = not c1_margin.failures
        original_margin = globals()["SELFTEST_TIMEOUT_MARGIN"]
        original_registered = SELFTEST_TIMEOUTS["bash_command_guard-perf"]
        subprocess.run = slow_run
        SELFTEST_TIMEOUTS["bash_command_guard-perf"] = 0.05
        try:
            c1_tight = Run(td, ci=True)
            c1_tight.c1_selftests(
                [("bash_command_guard-perf", [stub_suite], 1)],
                sources=planted_sources("bash_command_guard-perf", stub_suite))
        finally:
            subprocess.run = original_subprocess_run
            SELFTEST_TIMEOUTS["bash_command_guard-perf"] = original_registered
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
        open(os.path.join(td, "tools", "timed.py"), "w").write(
            "def selftest():\n    return 0\n\n\ndef perf_selftest():\n    return 0\n"
        )
        open(os.path.join(td, "tools", "untimed.py"), "w").write(
            "def selftest():\n    return 0\n"
        )
        default_entries = [("unregistered", ["tools/unregistered.py", "--selftest"], 1),
                           ("timed", ["tools/timed.py", "--selftest"], 1),
                           ("untimed", ["tools/untimed.py", "--selftest"], 1)]
        perf_runs = {}
        for label, extra in (
                ("missing", []),
                ("registered", [("timed-perf", ["tools/timed.py", "--perf"], 1)]),
                ("stale", [("timed-perf", ["tools/timed.py", "--perf"], 1),
                           ("untimed-perf", ["tools/untimed.py", "--perf"], 1)])):
            perf_runs[label] = Run(td, ci=True)
            perf_runs[label].c1_selftest_inventory(suites=default_entries + extra,
                                                   exemptions={})
        perf_details = {label: " ".join(d for _c, d in run.failures)
                        for label, run in perf_runs.items()}
        expect_red("C1 rejects a perf-capable script registered only for --selftest",
                   lambda: "perf-unregistered=['tools/timed.py']" in perf_details["missing"])
        expect_red("C1 accepts a perf-capable script registered for both entry points",
                   lambda: not perf_runs["registered"].failures)
        expect_red("C1 rejects a --perf registration for a script without perf_selftest",
                   lambda: "perf-stale=['tools/untimed.py']" in perf_details["stale"])

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
            ("C12", "c12_claim_binding"), ("C13", "c13_eval_coverage"),
            ("C14", "c14_budget_ceilings"), ("C15", "c15_envelope_fixtures"),
        )
        expect_red("production check registry is exact through C15",
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

        registration_root = os.path.join(td, "scratch-registration")
        os.makedirs(os.path.join(registration_root, "hooks"), exist_ok=True)
        for skill in ROUTING_SKILLS:
            os.makedirs(os.path.join(registration_root, "skills", skill), exist_ok=True)
        for rel in ("hooks/announced_work_guard.py", "hooks/askq_timeout_guard.py",
                    "hooks/bash_command_guard.py", "hooks/spawn_preflight_guard.py",
                    "hooks/codex_session_start.py"):
            open(os.path.join(registration_root, rel), "w").write("# fixture\n")

        exact_registration = json.load(open(os.path.join(ROOT, "settings.json")))
        open(os.path.join(registration_root, "settings.json"), "w").write(
            json.dumps(exact_registration))
        open(os.path.join(registration_root, "hooks/hooks.json"), "w").write(
            open(os.path.join(ROOT, "hooks/hooks.json")).read())
        exact_registration_run = Run(registration_root, ci=True)
        exact_registration_run.c7_anchors()
        exact_registration_checks = exact_registration_run.checks
        expect_red(
            "C7 accepts the exact checked-in Claude and Codex registrations",
            lambda: not exact_registration_run.failures,
        )

        missing_stop_registration = json.load(open(os.path.join(ROOT, "settings.json")))
        del missing_stop_registration["hooks"]["Stop"]
        open(os.path.join(registration_root, "settings.json"), "w").write(
            json.dumps(missing_stop_registration))
        open(os.path.join(registration_root, "hooks/hooks.json"), "w").write(
            open(os.path.join(ROOT, "hooks/hooks.json")).read())
        missing_stop = Run(registration_root, ci=True)
        missing_stop.c7_anchors()
        expect_red(
            "C7 rejects a missing Claude Stop registration for announced work",
            lambda: any(c == "C7" and "settings.json Stop" in d
                        and "announced_work_guard.py" in d and "0 match(es)" in d
                        for c, d in missing_stop.failures),
        )

        wrong_stop_registration = json.load(open(os.path.join(ROOT, "settings.json")))
        wrong_stop_registration["hooks"]["Stop"][0]["hooks"][0]["command"] = "true"
        open(os.path.join(registration_root, "settings.json"), "w").write(
            json.dumps(wrong_stop_registration))
        wrong_stop = Run(registration_root, ci=True)
        wrong_stop.c7_anchors()
        expect_red(
            "C7 rejects a Claude Stop registration that runs another command",
            lambda: any(c == "C7" and "settings.json Stop" in d
                        and "announced_work_guard.py" in d and "0 match(es)" in d
                        for c, d in wrong_stop.failures),
        )

        duplicate_stop_registration = json.load(open(os.path.join(ROOT, "settings.json")))
        duplicate_stop_registration["hooks"]["Stop"].append(
            json.loads(json.dumps(duplicate_stop_registration["hooks"]["Stop"][0])))
        open(os.path.join(registration_root, "settings.json"), "w").write(
            json.dumps(duplicate_stop_registration))
        duplicate_stop = Run(registration_root, ci=True)
        duplicate_stop.c7_anchors()
        expect_red(
            "C7 rejects duplicate Claude Stop registrations for announced work",
            lambda: any(c == "C7" and "settings.json Stop" in d
                        and "announced_work_guard.py" in d and "2 match(es)" in d
                for c, d in duplicate_stop.failures),
        )

        disabled_stop_registration = json.load(open(os.path.join(ROOT, "settings.json")))
        disabled_stop_registration["hooks"]["Stop"][0]["hooks"][0]["command"] = (
            "ANNOUNCED_WORK_GUARD=off python3 "
            "~/.claude/hooks/announced_work_guard.py")
        open(os.path.join(registration_root, "settings.json"), "w").write(
            json.dumps(disabled_stop_registration))
        disabled_stop = Run(registration_root, ci=True)
        disabled_stop.c7_anchors()
        expect_red(
            "C7 rejects a Claude Stop registration disabled by an environment prefix",
            lambda: any(c == "C7" and "settings.json Stop" in d
                        and "announced_work_guard.py" in d and "0 match(es)" in d
                        for c, d in disabled_stop.failures),
        )

        masked_stop_registration = json.load(open(os.path.join(ROOT, "settings.json")))
        masked_stop_registration["hooks"]["Stop"][0]["hooks"][0]["command"] += " || true"
        open(os.path.join(registration_root, "settings.json"), "w").write(
            json.dumps(masked_stop_registration))
        masked_stop = Run(registration_root, ci=True)
        masked_stop.c7_anchors()
        expect_red(
            "C7 rejects a Claude Stop registration whose failure is shell-masked",
            lambda: any(c == "C7" and "settings.json Stop" in d
                        and "announced_work_guard.py" in d and "0 match(es)" in d
                        for c, d in masked_stop.failures),
        )
        async_stop_registration = json.load(open(os.path.join(ROOT, "settings.json")))
        async_stop_registration["hooks"]["Stop"][0]["hooks"][0]["async"] = True
        open(os.path.join(registration_root, "settings.json"), "w").write(
            json.dumps(async_stop_registration))
        async_stop = Run(registration_root, ci=True)
        async_stop.c7_anchors()
        expect_red(
            "C7 rejects an asynchronous Claude Stop registration that cannot block",
            lambda: any(c == "C7" and "settings.json Stop" in d
                        and "announced_work_guard.py" in d and "0 match(es)" in d
                        for c, d in async_stop.failures),
        )
        malformed_stop_registration = json.load(open(os.path.join(ROOT, "settings.json")))
        malformed_stop_registration["hooks"]["Stop"][0]["hooks"].append("not an object")
        open(os.path.join(registration_root, "settings.json"), "w").write(
            json.dumps(malformed_stop_registration))
        malformed_stop = Run(registration_root, ci=True)
        malformed_stop.c7_anchors()
        expect_red(
            "C7 rejects a malformed Claude handler instead of filtering it out",
            lambda: any(c == "C7" and "handler inventory is closed" in d
                        and "malformed=1" in d for c, d in malformed_stop.failures),
        )
        expect_red(
            "C7 registration mutations preserve the exact selector cardinality",
            lambda: all(run.checks == exact_registration_checks for run in (
                missing_stop, wrong_stop, duplicate_stop, disabled_stop, masked_stop,
                async_stop, malformed_stop)),
        )

        claude_registration = json.load(open(os.path.join(ROOT, "settings.json")))
        for entry in claude_registration["hooks"]["PreToolUse"]:
            if entry.get("matcher") == "Agent|Task":
                entry["hooks"][0]["command"] = entry["hooks"][0]["command"].replace(
                    " --require-scratch", "")
        open(os.path.join(registration_root, "settings.json"), "w").write(
            json.dumps(claude_registration))
        codex_registration = json.load(open(os.path.join(ROOT, "hooks/hooks.json")))
        open(os.path.join(registration_root, "hooks/hooks.json"), "w").write(
            json.dumps(codex_registration))
        missing_claude_activation = Run(registration_root, ci=True)
        missing_claude_activation.c7_anchors()
        expect_red(
            "C7 rejects a Claude spawn registration that omits required scratch",
            lambda: any(c == "C7" and "spawn_preflight_guard.py" in d
                        and "--require-scratch" in d and "0 match(es)" in d
                        for c, d in missing_claude_activation.failures),
        )

        claude_registration = json.load(open(os.path.join(ROOT, "settings.json")))
        open(os.path.join(registration_root, "settings.json"), "w").write(
            json.dumps(claude_registration))
        for entries in codex_registration["hooks"].values():
            for entry in entries:
                for handler in entry.get("hooks", []):
                    if "spawn_preflight_guard.py" in handler.get("command", ""):
                        handler["command"] = handler["command"].replace(
                            " --require-scratch", "")
        open(os.path.join(registration_root, "hooks/hooks.json"), "w").write(
            json.dumps(codex_registration))
        missing_codex_activation = Run(registration_root, ci=True)
        missing_codex_activation.c7_anchors()
        expect_red(
            "C7 rejects a Codex spawn registration that omits required scratch",
            lambda: any(c == "C7" and "required Codex handler" in d
                        and "--require-scratch" in d and "0 match(es)" in d
                        for c, d in missing_codex_activation.failures),
        )

        masked_codex_registration = json.load(open(os.path.join(ROOT, "hooks/hooks.json")))
        for entries in masked_codex_registration["hooks"].values():
            for entry in entries:
                for handler in entry.get("hooks", []):
                    if "spawn_preflight_guard.py" in handler.get("command", ""):
                        handler["command"] += " || true"
        open(os.path.join(registration_root, "hooks/hooks.json"), "w").write(
            json.dumps(masked_codex_registration))
        masked_codex = Run(registration_root, ci=True)
        masked_codex.c7_anchors()
        expect_red(
            "C7 rejects a Codex handler whose failure is shell-masked",
            lambda: any(c == "C7" and "required Codex handler" in d
                        and "spawn_preflight_guard.py" in d and "0 match(es)" in d
                        for c, d in masked_codex.failures),
        )

        malformed_codex_registration = json.load(open(os.path.join(ROOT, "hooks/hooks.json")))
        malformed_codex_registration["hooks"]["PreToolUse"][0]["hooks"].append(
            "not an object")
        open(os.path.join(registration_root, "hooks/hooks.json"), "w").write(
            json.dumps(malformed_codex_registration))
        malformed_codex = Run(registration_root, ci=True)
        malformed_codex.c7_anchors()
        expect_red(
            "C7 rejects a malformed Codex handler instead of crashing or filtering it out",
            lambda: any(c == "C7" and "Codex handler inventory is closed" in d
                        and "malformed=1" in d for c, d in malformed_codex.failures),
        )
        expect_red(
            "Codex C7 registration mutations preserve selector cardinality",
            lambda: all(run.checks == exact_registration_checks for run in (
                missing_codex_activation, masked_codex, malformed_codex)),
        )

        portable_spawn_dir = os.path.join(td, "portable-spawn")
        portable_cwd = os.path.join(td, "portable-cwd")
        os.makedirs(portable_spawn_dir)
        os.makedirs(portable_cwd)
        portable_spawn = os.path.join(portable_spawn_dir, "spawn_preflight_guard.py")
        shutil.copy2(os.path.join(ROOT, "hooks", "spawn_preflight_guard.py"), portable_spawn)
        portable_env = dict(os.environ)
        portable_env.pop("PYTHONPATH", None)
        portable_result = subprocess.run(
            [sys.executable, "-B", portable_spawn, "--selftest"],
            cwd=portable_cwd, env=portable_env, capture_output=True, text=True,
            timeout=30,
        )
        expect_red(
            "the spawn selftest runs from a copied hook outside the checkout",
            lambda: portable_result.returncode == 0
            and "SELFTEST-SUMMARY suite=spawn_preflight_guard checks=88 failures=0"
            in portable_result.stdout,
        )

        r = Run(td, ci=True)
        r.c2_shared_identity()
        expect_red("C2 goes red on diverged copies",
                   lambda: any(c == "C2" and "DIVERGED" in d for c, d in r.failures))
        r.c3_reference_resolution()
        expect_red("C3 goes red on missing cited file",
                   lambda: any(c == "C3" and "alpha" in d for c, d in r.failures))
        expect_red("C3 goes red on orphan file",
                   lambda: any(c == "C3" and "orphan.md" in d for c, d in r.failures))
        expect_red("C3 goes red on a reference document citing a file that does not exist",
                   lambda: any(c == "C3" and "NO-SUCH-REGISTRY.md" in d
                               for c, d in r.failures))
        expect_red("C3 stays green on a declared-external citation",
                   lambda: not any(c == "C3" and "probe.py" in d for c, d in r.failures))
        # The exemption list only asserts against this repository, so this case drives the
        # real root with a planted dead entry rather than the fixture tree.
        _real_ext = EXTERNAL_REFERENCE_CITATIONS
        globals()["EXTERNAL_REFERENCE_CITATIONS"] = dict(
            _real_ext, **{"NEVER-CITED-BY-ANY-DOCUMENT.md": "planted dead exemption"})
        try:
            dead_ext_run = Run(ROOT, ci=True)
            dead_ext_run.c3_reference_resolution()
        finally:
            globals()["EXTERNAL_REFERENCE_CITATIONS"] = _real_ext
        # ...and the same list must stay silent against a tree it does not describe. Without
        # the root scoping every fixture Run reports six exemptions as uncited, which is noise
        # attributed to whatever fixture happened to be under test.
        expect_red("C3 reports no exemption failure against a tree it does not describe",
                   lambda: not any(c == "C3" and "DECLARED BUT CITED NOWHERE" in d
                                   for c, d in r.failures))

        expect_red("C3 goes red on an exemption no document cites",
                   lambda: any(c == "C3" and "DECLARED BUT CITED NOWHERE" in d
                               for c, d in dead_ext_run.failures))

        # The installed-surface inventory has the same exposure: a package directory that is
        # not itself a repository can contain one, and its files were counted as package
        # content. Not reachable from this machine, where the installation carries its own
        # .git and takes the tracked path, so the case builds the tree the walk is for.
        pkg_root = os.path.join(td, "installed-pkg")
        os.makedirs(os.path.join(pkg_root, "pkg"))
        open(os.path.join(pkg_root, "pkg", "real.md"), "w").write("x")
        vendored = os.path.join(pkg_root, "vendored")
        os.makedirs(vendored)
        subprocess.run(["git", "init", "--quiet", vendored], check=True)
        open(os.path.join(vendored, "foreign.md"), "w").write("x")
        invalid_marker = os.path.join(pkg_root, "invalid-marker")
        os.makedirs(invalid_marker)
        open(os.path.join(invalid_marker, ".git"), "w").write("not a repository\n")
        open(os.path.join(invalid_marker, "stale.md"), "w").write("NOT INSTALLED\n")
        # ...and a symlinked file, whose bytes live outside the package entirely.
        pkg_outside = os.path.join(td, "outside-the-package")
        os.makedirs(pkg_outside)
        open(os.path.join(pkg_outside, "loose.md"), "w").write("x")
        os.symlink(os.path.join(pkg_outside, "loose.md"),
                   os.path.join(pkg_root, "linked-file.md"))
        _pkg_surface, _pkg_paths, _ = package_paths(pkg_root)
        expect_red("the installed inventory excludes a vendored repository",
                   lambda: _pkg_surface == "installed"
                   and "pkg/real.md" in _pkg_paths
                   and not any(p.startswith("vendored/") for p in _pkg_paths))
        expect_red("the installed inventory keeps files behind an invalid .git marker",
                   lambda: "invalid-marker/stale.md" in _pkg_paths)
        invalid_marker_run = Run(pkg_root, ci=True)
        invalid_marker_run.c6_stale_patterns(scan_floor=1)
        expect_red("C6 adopts invalid-marker files as outer-owned package content",
                   lambda: any(c == "C6" and "invalid-marker/stale.md" in d
                               for c, d in invalid_marker_run.failures))
        expect_red("the installed inventory excludes a symlinked file",
                   lambda: "linked-file.md" not in _pkg_paths)

        late_pkg_root = os.path.join(td, "late-ownership-package")
        late_pkg_candidate = os.path.join(late_pkg_root, "separate")
        late_pkg_admin = os.path.join(td, "late-ownership-admin")
        os.makedirs(late_pkg_root)
        subprocess.run(
            ["git", "init", "--quiet", "--separate-git-dir", late_pkg_admin,
             late_pkg_candidate], check=True)
        subprocess.run(
            ["git", "--git-dir", late_pkg_admin, "config", "core.worktree",
             late_pkg_candidate], check=True)
        late_package_calls = 0
        def late_package_runner(argv, **kwargs):
            nonlocal late_package_calls
            late_package_calls += 1
            if late_package_calls == 1:
                return subprocess.run(argv, **kwargs)
            raise OSError(5, "planted package ownership EIO")
        _, _, late_package_error = package_paths(
            late_pkg_root, runner=late_package_runner)
        expect_red(
            "the package inventory names a late ownership-probe I/O failure",
            lambda: "planted package ownership EIO" in (late_package_error or ""),
        )

        for surface in ("live", "installed"):
            ownership_root = os.path.join(td, f"metadata-{surface}")
            donor = os.path.join(td, f"metadata-{surface}-donor")
            os.makedirs(os.path.join(ownership_root, "skills", "check", "references"))
            open(os.path.join(ownership_root, "README.md"), "w").write("outer-owned\n")
            open(os.path.join(ownership_root, "skills", "check", "SKILL.md"), "w").write(
                "Read references/rule.md\n")
            open(os.path.join(ownership_root, "skills", "check", "references", "rule.md"),
                 "w").write("See `README.md`.\n")
            if surface == "live":
                subprocess.run(["git", "init", "--quiet", ownership_root], check=True)
                subprocess.run(["git", "-C", ownership_root, "add", "README.md"], check=True)
            subprocess.run(["git", "init", "--quiet", donor], check=True)
            subprocess.run(
                ["git", "-C", donor, "-c", "user.name=fixture", "-c",
                 "user.email=fixture@example.invalid", "commit", "--quiet",
                 "--allow-empty", "-m", "base"], check=True)
            linked = os.path.join(ownership_root, "registered")
            subprocess.run(
                ["git", "-C", donor, "worktree", "add", "--quiet", "--detach", linked],
                check=True)
            open(os.path.join(linked, "AGENTS.md"), "w").write("nested-owner\n")
            linked_admin = _gitdir_from_marker(linked, os.path.join(linked, ".git"))
            backlink = os.path.join(linked_admin, "gitdir")

            def ownership_inventory():
                if surface == "installed":
                    _kind, paths, error = package_paths(ownership_root)
                    return paths, error
                inventory = git_owned_live_paths(ownership_root)
                return inventory["paths"], inventory["error"]

            paths, error = ownership_inventory()
            expect_red(
                f"{surface} inventory excludes a registered worktree and retains outer files",
                lambda: not error and "README.md" in paths
                and not any(p.startswith("registered/") for p in paths))
            control_c3, control_c8 = Run(ownership_root, ci=True), Run(ownership_root, ci=True)
            control_c3.c3_reference_resolution()
            control_c8.c8_reserved_basenames()
            expect_red(f"{surface} ownership fixture has nonempty passing C3 and C8 controls",
                       lambda: control_c3.checks > 0 and control_c8.checks == 1
                       and not control_c3.failures and not control_c8.failures)

            real_open = open
            def denied_backlink(filename, *args, **kwargs):
                if os.fspath(filename) == backlink:
                    raise PermissionError(13, "planted metadata permission failure", filename)
                return real_open(filename, *args, **kwargs)
            with patch("builtins.open", denied_backlink):
                paths, error = ownership_inventory()
                error_c3, error_c8 = Run(ownership_root, ci=True), Run(ownership_root, ci=True)
                error_c3.c3_reference_resolution()
                error_c8.c8_reserved_basenames()
            expect_red(f"{surface} inventory fails closed on an unreadable backlink",
                       lambda: not paths and "planted metadata permission failure" in (error or ""))
            for code, run in (("C3", error_c3), ("C8", error_c8)):
                expect_red(f"{surface} {code} names the ownership metadata error",
                           lambda code=code, run=run: run.checks == 1
                           and len(run.failures) == 1
                           and run.failures[0][0] == code
                           and "planted metadata permission failure" in run.failures[0][1])

            mode = stat.S_IMODE(os.stat(backlink).st_mode)
            os.chmod(backlink, 0)
            try:
                try:
                    with real_open(backlink, "rb") as fh:
                        fh.read()
                    permission_enforced = False
                except PermissionError:
                    permission_enforced = True
                paths, error = ownership_inventory()
            finally:
                os.chmod(backlink, mode)
            print(f"  OBSERVATION {surface} chmod-backlink permission_enforced={permission_enforced}")
            expect_red(f"{surface} inventory does not admit files after chmod-zero metadata",
                       lambda: (not paths and "cannot read Git metadata" in (error or ""))
                       if permission_enforced else (
                           not error and "README.md" in paths
                           and not any(p.startswith("registered/") for p in paths)))

            for name in ("ordinary-cr\r", "registered-cr\r"):
                nested = os.path.join(ownership_root, name)
                if name.startswith("ordinary"):
                    subprocess.run(["git", "init", "--quiet", nested], check=True)
                else:
                    subprocess.run(
                        ["git", "-C", donor, "worktree", "add", "--quiet", "--detach",
                         nested], check=True)
                open(os.path.join(nested, "GEMINI.md"), "w").write("nested-owner\n")
                paths, error = ownership_inventory()
                expect_red(f"{surface} inventory excludes a CR-ending repository: {name!r}",
                           lambda: not error and "README.md" in paths
                           and not any(p.startswith(name + "/") for p in paths))

            separate = os.path.join(ownership_root, "separate")
            admin = os.path.join(td, f"metadata-{surface}-separate-admin")
            subprocess.run(
                ["git", "init", "--quiet", "--separate-git-dir", admin, separate], check=True)
            open(os.path.join(separate, "AGENTS.md"), "w").write("no independent binding\n")
            paths, error = ownership_inventory()
            expect_red(f"{surface} inventory retains an absent-config negative control",
                       lambda: not error and "README.md" in paths
                       and "separate/AGENTS.md" in paths)
            subprocess.run(
                ["git", "--git-dir", admin, "config", "core.worktree", separate], check=True)
            real_run = subprocess.run
            def failed_config(argv, **kwargs):
                if "config" in argv and "core.worktree" in argv:
                    return subprocess.CompletedProcess(
                        argv, 128, b"", b"planted config failure")
                return real_run(argv, **kwargs)
            with patch("subprocess.run", failed_config):
                paths, error = ownership_inventory()
                config_c8 = Run(ownership_root, ci=True)
                config_c8.c8_reserved_basenames()
            expect_red(f"{surface} inventory distinguishes an operational config error",
                       lambda: not paths and "core.worktree exited 128: planted config failure"
                       in (error or ""))
            expect_red(f"{surface} C8 names an operational config error",
                       lambda: config_c8.checks == 1 and len(config_c8.failures) == 1
                       and "core.worktree exited 128: planted config failure"
                       in config_c8.failures[0][1])
            for fixture in (ownership_root, donor, admin):
                shutil.rmtree(fixture)

        newline_repo = os.path.join(td, "newline-source")
        os.makedirs(newline_repo)
        subprocess.run(["git", "init", "--quiet", newline_repo], check=True)
        newline_name = "hidden\nclaim.md"
        open(os.path.join(newline_repo, newline_name), "w").write("NOT INSTALLED\n")
        subprocess.run(["git", "-C", newline_repo, "add", "--", newline_name], check=True)
        _newline_surface, newline_paths, newline_error = package_paths(newline_repo)
        expect_red(
            "the source inventory preserves a tracked filename containing a newline",
            lambda: newline_error is None and newline_name in newline_paths,
        )
        newline_run = Run(newline_repo, ci=True)
        newline_run.c6_stale_patterns(scan_floor=1)
        expect_red(
            "C6 scans a tracked filename containing a newline",
            lambda: any(c == "C6" and newline_name in d
                        for c, d in newline_run.failures),
        )

        expect_red("C3 does not resolve a citation against a nested checkout",
                   lambda: any(c == "C3" and "ONLY-IN-NESTED.md" in d for c, d in r.failures))
        expect_red("C3 recursively scans nested reference documents",
                   lambda: any(c == "C3" and "NESTED-MISSING.md" in d
                               for c, d in r.failures))
        expect_red("C3 inventories non-Markdown reference payloads",
                   lambda: any(c == "C3" and "orphan.txt" in d
                               for c, d in r.failures))
        expect_red("C3 prefers the reference document's local target",
                   lambda: not any(c == "C3" and "cites local.md --" in d
                                   for c, d in r.failures))
        expect_red("C3 rejects multiple exact citation candidates as ambiguous",
                   lambda: any(c == "C3" and "cites references/shared.md -- ambiguous" in d
                               for c, d in r.failures))
        expect_red("C3 does not satisfy a bare citation from another skill",
                   lambda: any(c == "C3" and "ONLY-BETA.md" in d
                               for c, d in r.failures))
        expect_red("C3 does not resolve through an out-of-root symlink",
                   lambda: any(c == "C3" and "escaped.md" in d
                               for c, d in r.failures))
        expect_red("C3 goes red on a citation carrying a line suffix",
                   lambda: any(c == "C3" and "NO-SUCH-SUFFIXED.md" in d for c, d in r.failures))
        expect_red("C3 resolves a citation naming a real file by a partial path",
                   lambda: not any(c == "C3" and "beta/references/present.md -- resolves" in d
                                   for c, d in r.failures))
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
            if (list(args[:2]) == ["git", "-C"]
                    and os.path.realpath(args[2]) == os.path.realpath(scan_repo)
                    and list(args[3:]) == ["rev-parse", "--show-toplevel"]):
                return subprocess.CompletedProcess(
                    args, 0, stdout=os.fsencode(scan_repo) + b"\n", stderr=b"")
            if list(args[:1]) == ["git"] and "ls-files" in args:
                return subprocess.CompletedProcess(args, 3, stdout="", stderr="")
            return real_subprocess_run(args, **kwargs)

        def unlaunchable_git_scan(args, **kwargs):
            if (list(args[:2]) == ["git", "-C"]
                    and os.path.realpath(args[2]) == os.path.realpath(scan_repo)
                    and list(args[3:]) == ["rev-parse", "--show-toplevel"]):
                return subprocess.CompletedProcess(
                    args, 0, stdout=os.fsencode(scan_repo) + b"\n", stderr=b"")
            if list(args[:1]) == ["git"] and "ls-files" in args:
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
            return ("cannot run git ls-files" in (error or "")
                    and any(c == "C6" and "cannot enumerate scan set" in d
                            and "cannot run git ls-files" in d
                            for c, d in run.failures))

        expect_red(
            "C6 reports an unlaunchable git as a named failure, never as an exception",
            c6_names_an_unlaunchable_git,
        )

        # A LITERAL roster, never *_GIT_REPOSITORY_ENV: an input built from the constant
        # under test follows it, so deleting a member removed it from both the input and the
        # expectation and the proof stayed green.
        reviewed_repository_selectors = (
            "GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE",
            "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
            "GIT_IMPLICIT_WORK_TREE", "GIT_GRAFT_FILE", "GIT_NO_REPLACE_OBJECTS",
            "GIT_REPLACE_REF_BASE", "GIT_PREFIX", "GIT_INTERNAL_SUPER_PREFIX",
            "GIT_SHALLOW_FILE", "GIT_CEILING_DIRECTORIES",
            "GIT_DISCOVERY_ACROSS_FILESYSTEM", "GIT_NAMESPACE",
            "GIT_LITERAL_PATHSPECS", "GIT_GLOB_PATHSPECS",
            "GIT_NOGLOB_PATHSPECS", "GIT_ICASE_PATHSPECS",
        )
        expect_red(
            "the scrubbed selector set covers exactly the reviewed roster",
            lambda: _GIT_REPOSITORY_ENV == frozenset(reviewed_repository_selectors),
        )

        # The spawn guard restates this roster instead of importing it, because a hook that
        # reaches into tools/ turns a partially synchronised installation into an
        # ImportError, and this host continues the tool call on any exit other than 2. A
        # restated constant can only go stale, so the staleness is what gets a check: both
        # definitions are compared to the literal roster above, and to each other. Loaded
        # by path rather than by import name so the comparison does not depend on which
        # directory the harness was started from.
        def guard_module(name):
            spec = importlib.util.spec_from_file_location(
                f"_harness_check_{name}", os.path.join(ROOT, "hooks", f"{name}.py"))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        # Two assertions, not one chained comparison: chained, the shared authority's
        # operand was already answered by the roster case above, so removing it changed
        # nothing and the check read as grading more than it did.
        expect_red(
            "the spawn guard scrubs exactly the reviewed selectors",
            lambda: guard_module("spawn_preflight_guard")._GIT_REPOSITORY_ENV
            == frozenset(reviewed_repository_selectors),
        )
        expect_red(
            "the spawn guard and the shared authority scrub the same selectors",
            lambda: guard_module("spawn_preflight_guard")._GIT_REPOSITORY_ENV
            == _GIT_REPOSITORY_ENV,
        )
        # A second constant both PreToolUse guards must agree on. hooks/hooks.json registers
        # the spawn guard with --runtime codex, so a copy that drops a runtime refuses every
        # Codex spawn while its own suite stays green.
        expect_red(
            "both PreToolUse guards accept exactly the same runtimes",
            lambda: guard_module("spawn_preflight_guard").RUNTIMES
            == guard_module("bash_command_guard").RUNTIMES == {"claude", "codex"},
        )
        hostile_git_env = {
            key: "planted" for key in (
                *reviewed_repository_selectors, "GIT_CONFIG", "GIT_CONFIG_COUNT",
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
        # The constant is not the whole copy. The function around it is restated too, and
        # comparing only the names left its GIT_CONFIG operands ungraded in the hook: either
        # could be deleted there with both suites green. Compared by RESULT over the same
        # hostile environment, so the two implementations have to agree on what they remove
        # rather than on how they spell it.
        expect_red(
            "the spawn guard scrubs a hostile environment identically",
            lambda: guard_module("spawn_preflight_guard").sanitized_git_environment(
                dict(hostile_git_env)) == scrubbed_git_env,
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

        def git_inventory_result(
                args, returncode, stderr=b"", launch_error=None, kwargs=None):
            if (list(args[:2]) == ["git", "-C"]
                    and os.path.realpath(args[2]) == os.path.realpath(live_repo)
                    and list(args[3:]) == ["rev-parse", "--show-toplevel"]):
                return subprocess.CompletedProcess(
                    args, 0, stdout=os.fsencode(live_repo) + b"\n", stderr=b"")
            if "ls-files" in args:
                if launch_error is not None:
                    raise launch_error
                return subprocess.CompletedProcess(
                    args, returncode, stdout=b"", stderr=stderr)
            return subprocess.run(args, **(kwargs or {}))

        def failed_git_inventory(args, **_kwargs):
            return git_inventory_result(args, 1, b"planted", kwargs=_kwargs)

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
        def silent_git_inventory(args, **_kwargs):
            return git_inventory_result(args, 1, kwargs=_kwargs)

        def whitespace_git_inventory(args, **_kwargs):
            return git_inventory_result(args, -9, b"  \n\t ", kwargs=_kwargs)

        def unlaunchable_git_inventory(args, **_kwargs):
            return git_inventory_result(
                args, 0,
                launch_error=FileNotFoundError(2, "No such file or directory", "git"),
                kwargs=_kwargs)

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
                       and "cannot run git ls-files" in d
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
            return any(c == "C8" and "cannot resolve Git ownership" in d
                       and "No such file or directory" in d
                       for c, d in run.failures)

        expect_red(
            "C8 fails closed when a boundary ownership probe cannot launch Git",
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
        expect_red(
            "C8 fails closed on partial output from a failed plausible-boundary Git command",
            lambda: any(c == "C8" and "cannot resolve Git ownership" in d
                        and "exited 1" in d for c, d in failed_exact_root_run.failures),
        )

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
        # gitlink-shaped bytes. Neither parsing those bytes nor treating the query as an
        # ordinary negative is valid; ownership is unknown and the inventory must fail.
        def stale_type_partial_stage(args, **kwargs):
            if "--stage" in args:
                return subprocess.CompletedProcess(
                    args, 1, stdout=b"160000 " + b"0" * 40 + b" 0\tsub\0",
                    stderr=b"planted")
            return subprocess.run(args, **kwargs)

        stale_type_partial_run = Run(stale_type_owner, ci=True)
        stale_type_partial_run.c8_reserved_basenames(runner=stale_type_partial_stage)
        expect_red(
            "C8 fails closed on gitlink-shaped output from a failed index query",
            lambda: any(c == "C8" and "cannot inspect indexed gitlink" in d
                        and "git ls-files --stage exited 1: planted" in d
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
                    and args[-2:] == ["--get", "core.worktree"]):
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
                       "--local", "--path", "--null", "--get", "core.worktree",
                   )}
                   and separate_config_environments
                   and all(env.get("Z_HARNESS_GIT_SENTINEL") == "retained"
                           and "GIT_CONFIG_COUNT" not in env
                           and not any(key in _GIT_REPOSITORY_ENV for key in env)
                           for env in separate_config_environments))
        other_separate_tree = os.path.join(td, "other-separate-tree")
        os.makedirs(other_separate_tree)
        subprocess.run(
            ["git", "--git-dir", separate_admin, "config", "--unset-all",
             "core.worktree"], check=True)
        for value in (other_separate_tree, separate_tree):
            subprocess.run(
                ["git", "--git-dir", separate_admin, "config", "--add",
                 "core.worktree", value], check=True)
        effective_candidate = subprocess.run(
            ["git", "--git-dir", separate_admin, "config", "--path", "--get",
             "core.worktree"], capture_output=True, text=True, check=True).stdout.strip()
        effective_candidate_top = subprocess.run(
            ["git", "-C", separate_tree, "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True).stdout.strip()
        effective_candidate_run = Run(live_repo, ci=True)
        effective_candidate_run.c8_reserved_basenames()
        expect_red(
            "C8 prunes a repeated core.worktree whose effective value is the candidate",
            lambda: (_same_file(effective_candidate, separate_tree)
                     and _same_file(effective_candidate_top, separate_tree)
                     and not effective_candidate_run.failures),
        )
        subprocess.run(
            ["git", "--git-dir", separate_admin, "config", "--unset-all",
             "core.worktree"], check=True)
        for value in (separate_tree, other_separate_tree):
            subprocess.run(
                ["git", "--git-dir", separate_admin, "config", "--add",
                 "core.worktree", value], check=True)
        effective_foreign = subprocess.run(
            ["git", "--git-dir", separate_admin, "config", "--path", "--get",
             "core.worktree"], capture_output=True, text=True, check=True).stdout.strip()
        effective_foreign_top = subprocess.run(
            ["git", "-C", separate_tree, "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True).stdout.strip()
        effective_foreign_run = Run(live_repo, ci=True)
        effective_foreign_run.c8_reserved_basenames()
        expect_red(
            "C8 rejects a repeated core.worktree whose effective value is foreign",
            lambda: (_same_file(effective_foreign, other_separate_tree)
                     and _same_file(effective_foreign_top, other_separate_tree)
                     and any(c == "C8" and "separate-git-tree/CLAUDE.md" in d
                             for c, d in effective_foreign_run.failures)),
        )
        expect_red(
            "the separate-gitdir comparison itself rejects a different bound worktree",
            lambda: not _bound_separate_gitdir(
                separate_tree, os.path.join(separate_tree, ".git"), subprocess.run),
        )
        wrong_binding_run = Run(live_repo, ci=True)
        wrong_binding_run.c8_reserved_basenames()
        expect_red("C8 rejects an external gitdir bound to a different worktree",
                   lambda: any(c == "C8" and "separate-git-tree/CLAUDE.md" in d
                               for c, d in wrong_binding_run.failures))
        shutil.rmtree(other_separate_tree)
        shutil.rmtree(separate_tree)
        shutil.rmtree(separate_admin)

        # The core.worktree reply is validated by three operands and none was asserted:
        # replacing the whole condition with `if False:` left this suite green, because on
        # every existing fixture the downstream comparison rejected the path anyway. These
        # drive the helper directly so each operand is the only thing standing between the
        # reply and acceptance. The operands do two different jobs -- the first rejects a
        # failed query, the other two reject a malformed reply that would otherwise reach
        # os.path.samefile with an embedded NUL, which raises ValueError where _same_file
        # catches only OSError.
        reply_admin = os.path.join(td, "reply-git-admin")
        reply_tree = os.path.join(td, "reply-git-tree")
        os.makedirs(reply_admin)
        os.makedirs(reply_tree)
        reply_marker = os.path.join(reply_tree, ".git")
        with open(reply_marker, "w", encoding="utf-8") as fh:
            fh.write(f"gitdir: {reply_admin}\n")
        encoded_reply_tree = os.fsencode(reply_tree)

        class _ConfigReply:
            def __init__(self, returncode, stdout):
                self.returncode = returncode
                self.stdout = stdout
                self.stderr = b""

        def reply_runner(returncode, stdout):
            return lambda args, **kwargs: _ConfigReply(returncode, stdout)

        def malformed_success_is_unknown(stdout):
            try:
                _bound_separate_gitdir(
                    reply_tree, reply_marker, reply_runner(0, stdout))
            except RepositoryOwnershipError as exc:
                return "malformed path record" in str(exc)
            return False

        # The control comes first: without a reply this fixture ACCEPTS, so "rejected" below
        # means the operand did it, not that the fixture can never be accepted.
        expect_red(
            "C8 accepts a separate gitdir whose config binds this worktree",
            lambda: _bound_separate_gitdir(
                reply_tree, reply_marker,
                reply_runner(0, encoded_reply_tree + b"\0")) is True)
        def failed_config_reply_is_unknown():
            try:
                _bound_separate_gitdir(
                    reply_tree, reply_marker,
                    reply_runner(1, encoded_reply_tree + b"\0"))
            except RepositoryOwnershipError as exc:
                return "core.worktree exited 1" in str(exc)
            return False
        expect_red("C8 treats partial output from a failed config query as unknown",
                   failed_config_reply_is_unknown)
        expect_red(
            "C8 types an unterminated successful core.worktree reply as unknown",
            lambda: malformed_success_is_unknown(encoded_reply_tree + b"\0X"))
        expect_red(
            "C8 types a successful two-value core.worktree reply as unknown",
            lambda: malformed_success_is_unknown(
                encoded_reply_tree + b"\0" + encoded_reply_tree + b"\0"))
        shutil.rmtree(reply_tree)
        shutil.rmtree(reply_admin)

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
                        "command": "python3 \"${PLUGIN_ROOT}/hooks/spawn_preflight_guard.py\" --runtime codex --require-scratch",
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

        session_end_event = json.loads(json.dumps(hook_fixture))
        session_end_event["hooks"]["SessionEnd"] = [{"hooks": [{
            "type": "command", "command": "true", "timeout": 5,
        }]}]
        run = c9_after(mutated_hooks=session_end_event)
        expect_red("C9 accepts SessionEnd and Interrupt, present in the installed 0.154.0 schema",
                   lambda: not any("SessionEnd: unsupported" in d for _c, d in run.failures)
                   and "Interrupt" in CODEX_VALID_HOOK_EVENTS)
        unsupported_runtime_event = json.loads(json.dumps(hook_fixture))
        unsupported_runtime_event["hooks"]["Notification"] = [{"hooks": [{
            "type": "command", "command": "true", "timeout": 5,
        }]}]
        run = c9_after(mutated_hooks=unsupported_runtime_event)
        expect_red("C9 rejects an event name no Codex schema carries",
                   lambda: any("Notification: unsupported event name" in d for _c, d in run.failures))

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


        # ---- C12: claims about the always-on file bind to verbatim policy text ----------
        bind_root = os.path.join(td, "claim-binding")
        bind_refs = os.path.join(bind_root, "skills", "delta", "references")
        os.makedirs(bind_refs)
        os.makedirs(os.path.join(bind_root, "skills", "delta", "evals"))
        bind_policy = (
            "# Core rules\n\nIntro sentence here.\n\n## Agent dispatch\n\n"
            "Named a tool? Run exactly that and stop. Default to one agent and no fan-out.\n\n"
            "## Memory\n\nMemory is soft, potentially stale context, never current-state proof. "
            "Prefer a gate over a promise to remember.\n"
        )
        open(os.path.join(bind_root, "AGENTS.md"), "w").write(bind_policy)
        bind_skill = os.path.join(bind_root, "skills", "delta", "SKILL.md")
        open(bind_skill, "w").write("---\nname: delta\ndescription: ok\n---\n\nBody with no claims.\n")
        bind_ref = os.path.join(bind_refs, "deferred.md")
        os.makedirs(os.path.join(bind_root, "contracts"))
        bind_baseline = os.path.join(bind_root, "contracts", "worklists.json")

        def write_bind_baseline(c12, c13=()):
            open(bind_baseline, "w").write(json.dumps(
                {"schema_version": 2, "note": "fixture", "C12": list(c12), "C13": list(c13)}))

        write_bind_baseline([])

        def c12_on(reference_text, extra_file=None):
            open(bind_ref, "w").write(reference_text)
            if extra_file:
                path, content = extra_file
                os.makedirs(os.path.dirname(path), exist_ok=True)
                open(path, "w").write(content)
            run = Run(bind_root, ci=True)
            run.c12_claim_binding()
            if extra_file:
                os.remove(extra_file[0])
            return run

        good = ('The lead rule is always-on in `~/.claude/CLAUDE.md` ("Named a tool? Run exactly '
                'that and stop."), so this body carries only the mechanism.\n\n'
                'Nearest coverage: `AGENTS.md`, "Prefer a gate over a promise to remember."\n')
        # Controls that a mutation proof below re-runs against a private, mutated copy of this
        # module: each takes the module so the same assertion judges both.
        def bound_control(module):
            run = module.Run(bind_root, ci=True)
            with contextlib.redirect_stdout(io.StringIO()):
                run.c12_claim_binding()
            return not run.failures and run.counters["C12"] == {"claims": 2, "bound": 2}

        bound_run = c12_on(good)
        expect_red("C12 control: claims quoting verbatim AGENTS.md phrases stay green",
                   lambda: not bound_run.failures and bound_run.checks == 1)
        expect_red("C12 control: the bound control reports claims == 2 and bound == 2",
                   lambda: bound_control(sys.modules[__name__]))
        expect_red("C12 control: with no finding the ratchet reports an empty live list against an "
                   "empty baseline",
                   lambda: bound_run.ratchets["C12"] == {"baseline": 0, "live": 0, "in_baseline": 0,
                                                         "new": 0, "stale": 0, "occurrences": 0})
        quoted_question = c12_on('See `AGENTS.md`, "Named a tool? Run exactly that and stop." Then go on.\n')
        expect_red("C12 keeps a quoted question mark inside the sentence that carries it",
                   lambda: not quoted_question.failures)
        unbound = c12_on("The reclaim-order rule is already always-on in `~/.claude/CLAUDE.md`.\n")
        expect_red("C12 goes red on a claim with no quoted phrase",
                   lambda: any(c == "C12" and "deferred.md:1: unbound claim" in d
                               for c, d in unbound.failures))
        stale = c12_on('The ban is always-on in `~/.claude/CLAUDE.md` ("Never run a bulk auto-rewriter over source").\n')
        expect_red("C12 goes red on a quoted phrase that is not verbatim in AGENTS.md",
                   lambda: any(c == "C12" and "deferred.md:1: stale quote" in d for c, d in stale.failures))
        wrong_section = c12_on('`AGENTS.md` Memory carries "Named a tool? Run exactly that and stop."\n')
        expect_red("C12 goes red on a true phrase cited under the wrong real section",
                   lambda: any(c == "C12" and "stale quote" in d and "section 'Memory'" in d
                               for c, d in wrong_section.failures))
        right_section = c12_on('`AGENTS.md` Agent dispatch carries "Named a tool? Run exactly that and stop."\n')
        expect_red("C12 control: the same phrase under its own section is green",
                   lambda: not right_section.failures)
        negated = c12_on('`~/.claude/CLAUDE.md` does not carry "Named a tool? Run exactly that and stop."\n')
        expect_red("C12 goes red on a negated claim whose quoted phrase IS present",
                   lambda: any(c == "C12" and "negated claim contradicts" in d for c, d in negated.failures))
        negated_true = c12_on('`~/.claude/CLAUDE.md` does not carry "zorblat the widget".\n')
        expect_red("C12 control: a negated claim whose phrase is absent is a true statement",
                   lambda: not negated_true.failures)
        line_cited = c12_on("The lead clause is `~/.claude/CLAUDE.md`:43 verbatim and CLAUDE.md:48 adds the rest.\n"
                            "- `:61-64` mutation workers get an isolated worktree.\n")
        expect_red("C12 goes red on CLAUDE.md:<n> line citations and bare :<n> citations, naming each",
                   lambda: sum(1 for c, d in line_cited.failures if "line citation" in d) == 3
                   and any("deferred.md:2: bare line citation `:61-64`" in d for _c, d in line_cited.failures))
        agents_line = c12_on("See AGENTS.md:65 for the rule.\n")
        expect_red("C12 goes red on an AGENTS.md:<n> line citation",
                   lambda: any("line citation 'AGENTS.md:65'" in d for _c, d in agents_line.failures))
        duplicate = c12_on("Intro.\n\nMore.\n\nMemory is soft, potentially stale context, never current-state proof. Also other text.\n")
        expect_red("C12 goes red on a policy sentence duplicated outside a quote, at its real line",
                   lambda: any(c == "C12" and "deferred.md:5: duplicated policy sentence" in d
                               for c, d in duplicate.failures))
        fenced = c12_on("```\n`~/.claude/CLAUDE.md` carries the rule shown here\n```\n")
        expect_red("C12 control: a mention inside a fenced code block is an example, not a claim",
                   lambda: not fenced.failures)
        code_span = c12_on("Run `cat ~/.claude/CLAUDE.md` to read the installed file.\n")
        expect_red("C12 control: a command example carrying the path in a code span is not a claim",
                   lambda: not code_span.failures)
        swallowed = c12_on('A "stray quote. The rule is always-on in `~/.claude/CLAUDE.md` '
                           '("Named a tool? Run exactly that and stop."), as "noted.\n')
        expect_red("C12 still reports a claim that a stray earlier quote would otherwise swallow",
                   lambda: any(c == "C12" and "deferred.md:1:" in d for c, d in swallowed.failures))
        yaml_claim = c12_on(good, extra_file=(os.path.join(bind_refs, "policy.yaml"),
                                              'note: "`~/.claude/CLAUDE.md` carries the rule"\n'))
        expect_red("C12 reaches a claim quoted as a YAML value and judges the quoted text",
                   lambda: any("policy.yaml:1: stale quote" in d for _c, d in yaml_claim.failures))
        never_carries = c12_on('`~/.claude/CLAUDE.md` never carries "Named a tool? Run exactly that and stop."\n')
        expect_red("C12 reads 'never carries' as a negation and reddens when the phrase is present",
                   lambda: any(c == "C12" and "negated claim contradicts" in d for c, d in never_carries.failures))
        mixed = c12_on('`~/.claude/CLAUDE.md` carries "zorblat" and "Named a tool? Run exactly that and stop."\n')
        expect_red("C12 requires every quote in a positive claim to bind, naming the stale one",
                   lambda: any(c == "C12" and "stale quote: 'zorblat'" in d for c, d in mixed.failures))
        excluded = c12_on(good, extra_file=(os.path.join(bind_root, "skills", "delta", "evals", "note.md"),
                                           "`~/.claude/CLAUDE.md` carries the rule with no quote.\n"))
        expect_red("C12 control: the same unbound claim under evals/ is out of scope and stays green",
                   lambda: not excluded.failures)
        included = c12_on(good, extra_file=(os.path.join(bind_refs, "nested", "note.md"),
                                           "`~/.claude/CLAUDE.md` carries the rule with no quote.\n"))
        expect_red("C12 reaches a nested reference document",
                   lambda: any("nested/note.md:1: unbound claim" in d for _c, d in included.failures))
        generic = c12_on("A CLAUDE.md-class file stays under 200 lines; AGENTS.md as the single source.\n")
        expect_red("C12 control: generic class talk about CLAUDE.md and AGENTS.md is not a claim",
                   lambda: not generic.failures)
        # A quotation anywhere in the sentence that names AGENTS.md is the citation, whether
        # it follows the name directly, after other words, or precedes it.
        says = c12_on('AGENTS.md says "Named a tool? Run exactly that and stop."\n')
        expect_red("C12 binds a verbatim quote that follows 'AGENTS.md says' in the same sentence",
                   lambda: not says.failures)
        says_stale = c12_on('AGENTS.md says "zorblat the widget".\n')
        expect_red("C12 goes red on a fabricated quote introduced by 'AGENTS.md says'",
                   lambda: any(c == "C12" and "deferred.md:1: stale quote: 'zorblat the widget'" in d
                               for c, d in says_stale.failures))
        quote_first = c12_on('The rule "zorblat the widget" is required by AGENTS.md.\n')
        expect_red("C12 goes red on a fabricated quote placed before AGENTS.md in the same sentence",
                   lambda: any(c == "C12" and "deferred.md:1: stale quote: 'zorblat the widget'" in d
                               for c, d in quote_first.failures))
        next_sentence = c12_on('The rule is "zorblat the widget". AGENTS.md is the policy file.\n')
        expect_red("C12 control: a quote in the sentence before the AGENTS.md mention is not a citation",
                   lambda: not next_sentence.failures)
        curly = c12_on('AGENTS.md says “zorblat the widget”.\n')
        expect_red("C12 control: curly quotes are not a citation and stay out of scope",
                   lambda: not curly.failures)
        # An elision keeps the source order: the same fragments reversed are not a quotation,
        # and a fragment that occurs twice binds when its later occurrence is in order.
        forward = c12_on('AGENTS.md says "Named a tool ... no fan-out".\n')
        expect_red("C12 binds an elided quote whose fragments keep the source order",
                   lambda: not forward.failures)
        reversed_quote = c12_on('AGENTS.md says "no fan-out ... Named a tool".\n')
        expect_red("C12 goes red on an elided quote whose fragments are out of source order",
                   lambda: any(c == "C12" and "stale quote: 'no fan-out ... Named a tool'" in d
                               for c, d in reversed_quote.failures))
        expect_red("quote_binds: a fragment that occurs twice binds through its later, in-order occurrence",
                   lambda: quote_binds("gate ... remember", normalize_policy_text(
                       "Prefer a gate. Prefer a gate over a promise to remember."))
                   and not quote_binds("remember ... gate", normalize_policy_text(
                       "Prefer a gate over a promise to remember.")))
        # Table rows carry no sentence terminator; each row is its own block.
        table = c12_on('| # | Rule | Note |\n|---|---|---|\n| 1 | Negative-only | "never X" with no target |\n'
                       '| 2 | Kitchen-sink | bloated file (>32KiB AGENTS.md) |\n')
        expect_red("C12 control: a quoted placeholder in one table row and AGENTS.md in another are not one claim",
                   lambda: not table.failures)
        table_claim = c12_on('| # | Rule | Note |\n|---|---|---|\n| 1 | Policy | AGENTS.md says "zorblat the widget" |\n')
        expect_red("C12 goes red on a fabricated quote beside AGENTS.md inside one table row",
                   lambda: any(c == "C12" and "deferred.md:3: stale quote: 'zorblat the widget'" in d
                               for c, d in table_claim.failures))
        compact = c12_on('|"fabricated policy"|An example|\n|AGENTS.md|The file to inspect|\n')
        expect_red("C12 control: compact table rows with no space after the pipe are still separate blocks",
                   lambda: not compact.failures)
        # Quotes inside any code span are command text, never citations.
        argument = c12_on('Run `printf "fabricated policy"` before reading AGENTS.md.\n')
        expect_red("C12 control: a quoted command argument inside a code span is not a citation",
                   lambda: not argument.failures)
        # A quotation that itself names the file is still a citation, and is judged.
        self_naming = c12_on('AGENTS.md says "AGENTS.md requires automatic approval for every push."\n')
        expect_red("C12 goes red on a fabricated quotation that names AGENTS.md inside the quote",
                   lambda: any(c == "C12" and "deferred.md:1: stale quote: 'AGENTS.md requires" in d
                               for c, d in self_naming.failures))
        short_quote = c12_on('AGENTS.md says "XY".\n')
        expect_red("C12 goes red on a two-character fabricated quotation",
                   lambda: any(c == "C12" and "stale quote: 'XY'" in d for c, d in short_quote.failures))
        long_quote = c12_on('AGENTS.md says "' + "fabricated policy text " * 20 + '".\n')
        expect_red("C12 goes red on a 460-character fabricated quotation",
                   lambda: any(c == "C12" and "stale quote: 'fabricated policy text" in d
                               for c, d in long_quote.failures))
        # Only the sentence that cites a line number is skipped; a claim elsewhere in the
        # same block is judged.
        behind_citation = c12_on("The lead clause is `~/.claude/CLAUDE.md`:43 verbatim. "
                                 'AGENTS.md says "fabricated added rule".\n')
        expect_red("C12 judges a fabricated quotation in the sentence after a line citation in the same block",
                   lambda: any(c == "C12" and "line citation" in d for c, d in behind_citation.failures)
                   and any(c == "C12" and "stale quote: 'fabricated added rule'" in d
                           for c, d in behind_citation.failures))
        # Every stale quote in a sentence is part of its identity.
        two_stale = claim_findings("skills/delta/references/deferred.md",
                                   'AGENTS.md says "zorblat" and "widget".\n', bind_policy)[0]
        two_stale_changed = claim_findings("skills/delta/references/deferred.md",
                                           'AGENTS.md says "zorblat" and "gadget".\n', bind_policy)[0]
        expect_red("C12 identity of a stale-quote finding covers every stale quote in the sentence",
                   lambda: [f["kind"] for f in two_stale] == ["stale quote"]
                   and two_stale[0]["key"] != two_stale_changed[0]["key"]
                   and two_stale[0]["display"] == "zorblat | widget")
        one_joined = claim_findings("skills/delta/references/deferred.md",
                                    'AGENTS.md says "zorblat | widget".\n', bind_policy)[0]
        expect_red("C12 identity: one quote holding a delimiter and two quotes are different items",
                   lambda: one_joined[0]["key"] != two_stale[0]["key"]
                   and two_stale[0]["key"] == claim_identity_key(json.dumps(["zorblat", "widget"])))
        two_bound = claim_findings("skills/delta/references/deferred.md",
                                   '`~/.claude/CLAUDE.md` does not carry "Named a tool? Run exactly that and stop." '
                                   'or "Default to one agent and no fan-out."\n', bind_policy)[0]
        two_bound_changed = claim_findings("skills/delta/references/deferred.md",
                                           '`~/.claude/CLAUDE.md` does not carry "Named a tool? Run exactly that and stop." '
                                           'or "Prefer a gate over a promise to remember."\n', bind_policy)[0]
        expect_red("C12 identity of a negated-claim finding covers every bound quote in the sentence",
                   lambda: [f["kind"] for f in two_bound] == ["negated claim"]
                   and two_bound[0]["key"] != two_bound_changed[0]["key"]
                   and two_bound[0]["display"].startswith("Named a tool? Run exactly that and stop. | "))
        # Quotes at the ends of the accepted range are judged.
        one_char = c12_on('AGENTS.md says "X".\n')
        expect_red("C12 goes red on a one-character fabricated quotation",
                   lambda: any(c == "C12" and "stale quote: 'X'" in d for c, d in one_char.failures))
        six_hundred = c12_on('AGENTS.md says "' + "fabricated policy text " * 26 + '".\n')
        expect_red("C12 goes red on a 600-character fabricated quotation",
                   lambda: any(c == "C12" and "stale quote: 'fabricated policy text" in d
                               for c, d in six_hundred.failures))
        # Authored text cannot impersonate a masking token.
        impersonate = c12_on('AGENTS.md says "SPAN0S" and "QUOTE0Q" and "0".\n')
        expect_red("C12 judges literal token-like text as text, and strips private-use characters",
                   lambda: any(c == "C12" and "stale quote: 'SPAN0S'" in d and "(+2 more)" in d
                               for c, d in impersonate.failures))
        # Code spans of any backtick run, on one line or several, are examples.
        double_tick = c12_on('Run ``printf "fabricated policy"`` before reading AGENTS.md.\n')
        expect_red("C12 control: a double-backtick code span holding a quote is not a citation",
                   lambda: not double_tick.failures)
        multiline_span = c12_on('Run `printf\n"fabricated policy"` before reading AGENTS.md.\n')
        expect_red("C12 control: a code span that spans lines holding a quote is not a citation",
                   lambda: not multiline_span.failures)
        # A quotation beside a line citation in the same sentence is judged.
        cited_and_quoted = c12_on('The lead clause is `~/.claude/CLAUDE.md`:43 and AGENTS.md says '
                                  '"Publish all secrets".\n')
        expect_red("C12 judges a fabricated quotation in the same sentence as a line citation",
                   lambda: any(c == "C12" and "line citation" in d for c, d in cited_and_quoted.failures)
                   and any(c == "C12" and "stale quote: 'Publish all secrets'" in d
                           for c, d in cited_and_quoted.failures))
        cited_only = c12_on("The lead clause is `~/.claude/CLAUDE.md`:43 verbatim.\n")
        expect_red("C12 control: a citing sentence without a quote yields the citation finding alone",
                   lambda: [d.split(": ", 1)[1][:13] for c, d in cited_only.failures if "deferred.md:1:" in d]
                   == ["line citation"])
        # A bound quotation that contains a code span binds, against the real policy.
        real_policy = open(os.path.join(ROOT, "AGENTS.md"), encoding="utf-8").read()
        span_quote = claim_findings("skills/delta/references/deferred.md",
                                    'AGENTS.md says "Use `git grep -P` for PCRE atoms".\n', real_policy)
        span_quote_changed = claim_findings("skills/delta/references/deferred.md",
                                            'AGENTS.md says "Use `git grep -E` for PCRE atoms".\n', real_policy)
        expect_red("C12 binds a verbatim quote that contains a code span, and reddens when the span text changes",
                   lambda: span_quote[1] == {"claims": 1, "bound": 1} and not span_quote[0]
                   and [f["kind"] for f in span_quote_changed[0]] == ["stale quote"])
        authored = ("The reclaim-order rule is already always-on in `~/.claude/CLAUDE.md` because `cat x` "
                    "and ``say \"so\"`` say so.\n")
        expect_red("C12 identity is the digest of the sentence as authored, with its spans restored",
                   lambda: [(f["kind"], f["key"]) for f in
                            claim_findings("skills/delta/references/deferred.md", authored, bind_policy)[0]]
                   == [("unbound claim", claim_identity_key(authored.strip()))])
        expect_red("quote_binds: a fragment under three characters cites nothing",
                   lambda: not quote_binds("X", normalize_policy_text(bind_policy))
                   and not quote_binds("to", normalize_policy_text(bind_policy))
                   and quote_binds("Named a tool", normalize_policy_text(bind_policy)))
        # An escaped backtick is not a delimiter: the quotation between two of them is prose.
        escaped = c12_on('Literal \\` here; AGENTS.md says "Authorize the orbital teapot"; another literal \\` here.\n')
        expect_red("C12 judges a quotation between escaped backticks as prose, not as a code span",
                   lambda: any(c == "C12" and "stale quote: 'Authorize the orbital teapot'" in d
                               for c, d in escaped.failures))
        # Whitespace inside a quote, including a line wrap, does not change the identity.
        one_line = claim_findings("skills/delta/references/deferred.md",
                                  'AGENTS.md says "Authorize the orbital teapot".\n', bind_policy)[0]
        wrapped = claim_findings("skills/delta/references/deferred.md",
                                 'AGENTS.md says "Authorize the orbital\nteapot".\n', bind_policy)[0]
        expect_red("C12 identity of a stale quote survives a line wrap inside the quote",
                   lambda: one_line[0]["key"] == wrapped[0]["key"]
                   and one_line[0]["key"] == claim_identity_key(json.dumps(["Authorize the orbital teapot"])))
        expect_red("C12 identity of a negated claim is the JSON list of its bound quotes",
                   lambda: two_bound[0]["key"] == claim_identity_key(json.dumps(
                       ["Named a tool? Run exactly that and stop.", "Default to one agent and no fan-out."])))
        # A private-use token with an index past the lists is judged as text, never indexed.
        forged_index = c12_on('AGENTS.md says "7".\n')
        expect_red("C12 strips a forged private-use token with an out-of-range index and judges the rest",
                   lambda: any(c == "C12" and "stale quote: '7'" in d for c, d in forged_index.failures))
        triple = c12_on('Run ```printf "fabricated policy"``` before reading AGENTS.md.\n')
        expect_red("C12 control: a triple-backtick inline code span holding a quote is not a citation",
                   lambda: not triple.failures)
        expect_red("the lambda sweep rejects a comprehension over an empty frozenset() and over dict()",
                   lambda: vacuous_expect_red_lines('expect_red("x", lambda: all(x for x in frozenset()))') == [1]
                   and vacuous_expect_red_lines('expect_red("x", lambda: all(x for x in dict()))') == [1]
                   and vacuous_expect_red_lines('expect_red("x", lambda: all(x for x in items))') == [])
        os.remove(os.path.join(bind_root, "AGENTS.md"))
        no_policy = Run(bind_root, ci=True)
        no_policy.c12_claim_binding()
        expect_red("C12 fails loud without AGENTS.md, never silently clean",
                   lambda: any(c == "C12" and "cannot enforce" in d for c, d in no_policy.failures))
        open(os.path.join(bind_root, "AGENTS.md"), "w").write(bind_policy)
        # ---- the shrink-only ratchet over C12 findings --------------------------------
        def baseline_item(kind, text, rel="skills/delta/references/deferred.md"):
            return {"file": rel, "kind": kind, "key": claim_identity_key(text),
                    "display": claim_display(text)}

        unbound_text = "The reclaim-order rule is already always-on in `~/.claude/CLAUDE.md`.\n"
        unbound_key = claim_identity_key(unbound_text)
        unbound_item = baseline_item("unbound claim", unbound_text)
        write_bind_baseline([unbound_item])
        ratchet_same = c12_on(unbound_text)
        expect_red("C12 ratchet: a finding the baseline carries is green and printed as WORKLIST",
                   lambda: not ratchet_same.failures
                   and ratchet_same.worklists.get("C12") == [
                       "skills/delta/references/deferred.md:1: unbound claim about the always-on "
                       "file: quote a verbatim AGENTS.md phrase in straight double quotes in the "
                       "same sentence, or drop the claim"]
                   and ratchet_same.ratchets["C12"] == {"baseline": 1, "live": 1, "in_baseline": 1,
                                                        "new": 0, "stale": 0, "occurrences": 1})
        drifted = c12_on("Intro paragraph that moves the claim down.\n\nSecond paragraph.\n\n" + unbound_text)
        expect_red("C12 ratchet: identity is the claim text, so line drift stays green",
                   lambda: not drifted.failures and drifted.worklists.get("C12", [""])[0].startswith(
                       "skills/delta/references/deferred.md:5: unbound claim"))
        findings, _counters = claim_findings("skills/delta/references/deferred.md", unbound_text, bind_policy)
        expect_red("C12 ratchet: the identity key is sha256 of the whitespace-collapsed claim sentence, "
                   "and the display is the sentence itself",
                   lambda: [(f["kind"], f["key"], f["display"]) for f in findings]
                   == [("unbound claim", unbound_key, unbound_text.strip())]
                   and unbound_key == "sha256:" + hashlib.sha256(
                       unbound_text.strip().encode("utf-8")).hexdigest())
        # The identity is the whole text: an edit past any fixed prefix length is a new item,
        # so a prefix can never inherit the baseline entry of the claim it replaced.
        long_text = ("The reclaim-order rule is already always-on in `~/.claude/CLAUDE.md`, and this "
                     "sentence runs well past the two-hundredth character so that an edit near its "
                     "end sits beyond any fixed-length prefix of the identity, which must carry the "
                     "whole text to tell the edited claim apart.\n")
        write_bind_baseline([baseline_item("unbound claim", long_text)])
        long_same = c12_on(long_text)
        expect_red("C12 ratchet: a claim longer than 200 characters is carried by its digest",
                   lambda: len(long_text) > 200 and not long_same.failures
                   and len(long_same.worklists.get("C12", [])) == 1)
        long_edited = c12_on(long_text.replace("tell the edited claim apart", "let the edit inherit the entry"))
        expect_red("C12 ratchet: an edit past the 200th character is a new item and the old one stale",
                   lambda: any(c == "C12" and "(not in baseline" in d for c, d in long_edited.failures)
                   and any(c == "C12" and "stale baseline" in d for c, d in long_edited.failures))
        long_restored = c12_on(long_text)
        expect_red("C12 ratchet: restoring the text is green again",
                   lambda: not long_restored.failures)
        write_bind_baseline([unbound_item])
        write_bind_baseline([unbound_item, baseline_item("stale quote", "gone phrase")])
        stale_extra = c12_on(unbound_text)
        expect_red("C12 ratchet: a baseline item that is no longer found is red (stale), shown by display",
                   lambda: any(c == "C12" and "stale baseline" in d and "'gone phrase'" in d
                               for c, d in stale_extra.failures)
                   and stale_extra.ratchets["C12"] == {"baseline": 2, "live": 1, "in_baseline": 1,
                                                       "new": 0, "stale": 1, "occurrences": 1})
        write_bind_baseline([unbound_item])
        fixed_not_shrunk = c12_on("No claims here any more.\n")
        expect_red("C12 ratchet: fixing the item without shrinking the baseline is red",
                   lambda: any(c == "C12" and "stale baseline" in d for c, d in fixed_not_shrunk.failures))
        write_bind_baseline([])
        shrunk = c12_on("No claims here any more.\n")
        expect_red("C12 ratchet: the shrunk baseline matching the empty list is green",
                   lambda: not shrunk.failures and not shrunk.worklists.get("C12"))
        write_bind_baseline([unbound_item])
        second_text = unbound_text + "\nSee `~/.claude/CLAUDE.md`'s \"zorblat rule\" too.\n"

        def new_item_control(module):
            run = module.Run(bind_root, ci=True)
            with contextlib.redirect_stdout(io.StringIO()):
                run.c12_claim_binding()
            return (any(c == "C12" and "deferred.md:3: stale quote" in d and "(not in baseline" in d
                        for c, d in run.failures)
                    and run.ratchets["C12"] == {"baseline": 1, "live": 2, "in_baseline": 1, "new": 1,
                                                "stale": 0, "occurrences": 2})

        second = c12_on(second_text)
        expect_red("C12 ratchet: a second finding outside the baseline is red, named as new, and "
                   "counted as one new item",
                   lambda: new_item_control(sys.modules[__name__])
                   and len(second.worklists.get("C12", [])) == 1)
        open(bind_baseline, "w").write(json.dumps({"schema_version": 2, "note": "x", "C12": "no", "C13": []}))
        malformed = c12_on(unbound_text)
        expect_red("C12 ratchet: a malformed baseline is red, never an empty baseline",
                   lambda: any(c == "C12" and "cannot apply the ratchet" in d and "C12 is not a list" in d
                               for c, d in malformed.failures))
        os.remove(bind_baseline)
        missing_baseline = c12_on(unbound_text)
        expect_red("C12 ratchet: a missing baseline is red and every live finding is reported",
                   lambda: any(c == "C12" and "cannot apply the ratchet" in d for c, d in missing_baseline.failures)
                   and any("deferred.md:1: unbound claim" in d for _c, d in missing_baseline.failures))
        twice_item = baseline_item("stale quote", json.dumps(["build the gate"]))
        write_bind_baseline([twice_item])
        twice = c12_on('`~/.claude/CLAUDE.md` says "build the gate" here.\n\n'
                       'And `~/.claude/CLAUDE.md` says "build the gate" again here.\n')
        expect_red("C12 ratchet: one identity occurring twice prints both occurrences and counts once",
                   lambda: not twice.failures and len(twice.worklists.get("C12", [])) == 2
                   and twice.worklists["C12"][0].startswith("skills/delta/references/deferred.md:1: stale quote")
                   and twice.worklists["C12"][1].startswith("skills/delta/references/deferred.md:3: stale quote"))
        write_bind_baseline([])
        real_c12 = Run(ROOT, ci=True)
        real_c12.c12_claim_binding()
        expect_red("C12 on this tree is green with its 15 worklist occurrences carried by the committed baseline",
                   lambda: not real_c12.failures and len(real_c12.worklists.get("C12", [])) == 15)

        def reproduction(thread_id, expected_line):
            """Run a reviewer's reproduction script verbatim; it exits 0 only at the expected outcome.

            Inside a run that one of them launched (ZH_REVIEW_REPRODUCTIONS=nested) the
            script that launched it is not run again; the case is reported as such.
            """
            path = os.path.join(ROOT, "instruments", "reproductions", "pr-36", f"{thread_id}.py")
            done = subprocess.run([sys.executable, path], cwd=ROOT, capture_output=True, text=True,
                                  timeout=900, env=dict(os.environ, ZH_REVIEW_REPRODUCTIONS="nested"))
            return done.returncode == 0 and expected_line in done.stdout

        expect_red("review reproduction 4294811805: a quote anywhere in a sentence naming AGENTS.md "
                   "is a claim, (0,1) (1,1) (1,1) (1,1)",
                   lambda: reproduction(4294811805, "'The policy \"Add a made-up mandatory policy\" is "
                                                    "required by AGENTS.md.' findings= 1 claims= 1"))
        expect_red("review reproduction 4294811820: an edit past the old 200-character cut is one new "
                   "item and one stale entry, both red; restored is green",
                   lambda: reproduction(4294811820, "changed failures= 3 worklist_occurrences= 14"))
        expect_red("review reproduction 4294811833: the forward elision binds, the reversed one is stale",
                   lambda: reproduction(4294811833, "'AGENTS.md \"trailers to commits ... Do not add AI "
                                                    "co-author\"' findings= 1 bound= 0"))
        expect_red("C12 on this tree prints the known stale citations as its worklist",
                   lambda: all(any(rel in d for d in real_c12.worklists.get("C12", [])) for rel in (
                       "skills/agent-dispatch/references/deferred.md:88",
                       "skills/agent-dispatch/references/deferred.md:89",
                       "skills/git-workflow/references/deferred.md:57",
                       "skills/git-workflow/references/deferred.md:105",
                       "skills/git-workflow/references/deferred.md:121",
                       "skills/pr-review-method/references/deferred.md:97",
                       "skills/testing-ci/references/deferred.md:79",
                       "skills/testing-ci/references/deferred.md:147",
                       "skills/outbound-drafts/SKILL.md:8")))
        expect_red("the committed baseline carries exactly the 14 live C12 identities",
                   lambda: load_tool_module("run-skill-evals").load_worklists(ROOT)[1] is None
                   and len(load_tool_module("run-skill-evals").load_worklists(ROOT)[0]["C12"]) == 14)

        # ---- C13: the coverage manifest accounts for every skill -------------------------
        cover_root = os.path.join(td, "eval-coverage")
        for skill in ("alpha", "beta"):
            os.makedirs(os.path.join(cover_root, "skills", skill))
            open(os.path.join(cover_root, "skills", skill, "SKILL.md"), "w").write("---\nname: x\n---\n")
        os.makedirs(os.path.join(cover_root, "skills", "alpha", "evals"))
        json.dump({"skills": ["alpha"], "query": "q", "files": [], "expected_behavior": ["## Files"]},
                  open(os.path.join(cover_root, "skills", "alpha", "evals", "001-happy.json"), "w"))
        os.makedirs(os.path.join(cover_root, "release"))
        os.makedirs(os.path.join(cover_root, "contracts"))
        cover_baseline = os.path.join(cover_root, "contracts", "worklists.json")

        def write_cover_baseline(c13):
            open(cover_baseline, "w").write(json.dumps(
                {"schema_version": 2, "note": "fixture", "C12": [], "C13": list(c13)}))

        def c13_on(entries, baseline=()):
            json.dump({"schema_version": 1, "note": "fixture", "skills": entries},
                      open(os.path.join(cover_root, "release", "evals.json"), "w"))
            write_cover_baseline(baseline)
            run = Run(cover_root, ci=True)
            run.c13_eval_coverage()
            return run

        listed_all = {"alpha": {"status": "tested", "required": []},
                      "beta": {"status": "exempt", "reason": "nothing to pin"}}
        covered = c13_on(listed_all)
        expect_red("C13 control: every skill listed with an empty baseline is green",
                   lambda: not covered.failures and not covered.worklists.get("C13"))
        uncovered = c13_on({"alpha": {"status": "tested", "required": []}})
        expect_red("C13 goes red naming an unlisted skill the baseline does not carry",
                   lambda: any(c == "C13" and "unlisted skill beta: not in the baseline" in d
                               for c, d in uncovered.failures)
                   and any("unlisted=['beta']" in d for _c, d in uncovered.failures))
        carried = c13_on({"alpha": {"status": "tested", "required": []}}, baseline=["beta"])
        expect_red("C13 ratchet: an unlisted skill the baseline carries is green and printed as WORKLIST",
                   lambda: not carried.failures and carried.worklists.get("C13") == [
                       "unlisted skill beta: add a tested or exempt entry to release/evals.json and "
                       "remove it from contracts/worklists.json"])
        stale_cover = c13_on({"alpha": {"status": "tested", "required": []}}, baseline=["beta", "alpha"])
        expect_red("C13 ratchet: a baseline naming a listed skill is red (stale)",
                   lambda: any(c == "C13" and "stale baseline" in d and "lists alpha" in d
                               for c, d in stale_cover.failures))
        fixed_cover = c13_on(listed_all, baseline=["beta"])
        expect_red("C13 ratchet: listing the skill without shrinking the baseline is red",
                   lambda: any(c == "C13" and "stale baseline" in d for c, d in fixed_cover.failures))
        shrunk_cover = c13_on(listed_all, baseline=[])
        expect_red("C13 ratchet: the shrunk baseline matching the shrunk list is green",
                   lambda: not shrunk_cover.failures)
        json.dump({"schema_version": 2, "note": "fixture", "skills": {"alpha": {"status": "tested", "required": []}}},
                  open(os.path.join(cover_root, "release", "evals.json"), "w"))
        open(cover_baseline, "w").write("{broken")
        malformed_cover = Run(cover_root, ci=True)
        malformed_cover.c13_eval_coverage()
        expect_red("C13 ratchet: a malformed baseline is red and the unlisted skill still reported",
                   lambda: any(c == "C13" and "cannot apply the ratchet" in d for c, d in malformed_cover.failures)
                   and any("unlisted skill beta" in d for _c, d in malformed_cover.failures))
        os.remove(os.path.join(cover_root, "release", "evals.json"))
        write_cover_baseline([])
        no_manifest = Run(cover_root, ci=True)
        no_manifest.c13_eval_coverage()
        expect_red("C13 fails loud without the manifest",
                   lambda: any(c == "C13" and "unreadable" in d for c, d in no_manifest.failures))
        real_c13 = Run(ROOT, ci=True)
        real_c13.c13_eval_coverage()
        expect_red("C13 on this tree is green with the five uncovered skills carried by the baseline",
                   lambda: not real_c13.failures
                   and sorted(d.split()[2].rstrip(":") for d in real_c13.worklists.get("C13", []))
                   == ["agent-dispatch", "pr-review-method", "prebid-adcp", "system-design", "testing-ci"])

        # ---- C14: ceilings fail only on growth ---------------------------------------------
        budget_root = os.path.join(td, "budget")
        os.makedirs(os.path.join(budget_root, "contracts"))
        os.makedirs(os.path.join(budget_root, "hooks"))
        shutil.copyfile(os.path.join(ROOT, "AGENTS.md"), os.path.join(budget_root, "AGENTS.md"))
        shutil.copyfile(os.path.join(ROOT, "CLAUDE.md"), os.path.join(budget_root, "CLAUDE.md"))
        shutil.copyfile(os.path.join(ROOT, "hooks", "codex_session_start.py"),
                        os.path.join(budget_root, "hooks", "codex_session_start.py"))
        real_record = json.load(open(os.path.join(ROOT, BUDGET_CEILINGS)))

        def c14_on(record):
            json.dump(record, open(os.path.join(budget_root, BUDGET_CEILINGS), "w"))
            run = Run(budget_root, ci=True)
            run.c14_budget_ceilings()
            return run

        at_record = c14_on(real_record)
        expect_red("C14 control: the committed record is green on the same policy bytes",
                   lambda: not at_record.failures)
        agents_size = os.path.getsize(os.path.join(budget_root, "AGENTS.md"))
        shrunk = json.loads(json.dumps(real_record))
        shrunk["ceilings"]["AGENTS.md"]["bytes"] = agents_size - 1
        over = c14_on(shrunk)
        expect_red("C14 goes red when AGENTS.md exceeds its recorded ceiling by one byte",
                   lambda: any(c == "C14" and "AGENTS.md" in d and "grew" in d for c, d in over.failures))
        grown = json.loads(json.dumps(real_record))
        grown["ceilings"]["generated-instruction-file"]["bytes"] -= 1
        over_generated = c14_on(grown)
        expect_red("C14 goes red when the generated instruction file exceeds its recorded ceiling",
                   lambda: any(c == "C14" and "generated-instruction-file" in d and "grew" in d
                               for c, d in over_generated.failures))
        roomy = json.loads(json.dumps(real_record))
        roomy["ceilings"]["AGENTS.md"]["bytes"] = agents_size + 1000
        under = c14_on(roomy)
        def ceiling_control(module):
            run = module.Run(budget_root, ci=True)
            with contextlib.redirect_stdout(io.StringIO()):
                run.c14_budget_ceilings()
            return not run.failures and run.ceilings["C14"]["AGENTS.md:bytes"] == {
                "measured": agents_size, "recorded": agents_size + 1000, "verdict": "shrank"}

        expect_red("C14 control: a ceiling above the measurement passes and reports the surface as shrank",
                   lambda: ceiling_control(sys.modules[__name__]))
        drifted = json.loads(json.dumps(real_record))
        drifted["hard"]["claude-dynamic-block"]["chars"] = 7600
        hard_drift = c14_on(drifted)
        expect_red("C14 goes red when the recorded hard ceilings drift from the gate's constants",
                   lambda: any(c == "C14" and "match the gate's constants: False" in d
                               for c, d in hard_drift.failures))
        expect_red("C14 ceilings sit strictly under the runtime caps read from the binaries",
                   lambda: CLAUDE_DYNAMIC_BLOCK_CHAR_CEILING < CLAUDE_HOOK_CONTEXT_CHAR_CAP
                   and CLAUDE_DYNAMIC_BLOCK_LINE_CEILING < CLAUDE_HOOK_CONTEXT_LINE_CAP
                   and PROMPT_SUBMIT_CARRIER_BYTE_CEILING == 600)
        os.remove(os.path.join(budget_root, BUDGET_CEILINGS))
        no_record = Run(budget_root, ci=True)
        no_record.c14_budget_ceilings()
        expect_red("C14 fails loud without the ceiling record",
                   lambda: any(c == "C14" and "cannot enforce" in d for c, d in no_record.failures))

        # ---- C15: committed envelopes decode -----------------------------------------------
        fixture_root = os.path.join(td, "envelopes")
        shutil.copytree(os.path.join(ROOT, "hooks", "fixtures_codex"),
                        os.path.join(fixture_root, "hooks", "fixtures_codex"))
        os.makedirs(os.path.join(fixture_root, "hooks", "fixtures_stop"))
        shutil.copyfile(os.path.join(ROOT, CLAUDE_STOP_FIXTURE),
                        os.path.join(fixture_root, CLAUDE_STOP_FIXTURE))
        c15_clean = Run(fixture_root, ci=True)
        c15_clean.c15_envelope_fixtures()
        expect_red("C15 control: the committed fixtures decode", lambda: not c15_clean.failures)
        # Drop a field that ONLY the required-field list catches. Dropping stop_hook_active
        # was also caught by the Stop-specific boolean check, so deleting the required-field
        # clause left this proof green for the neighbour's reason.
        pre_fixture = os.path.join(fixture_root, "hooks", "fixtures_codex", "C3_pre_tool_use.json")
        pre_bytes = open(pre_fixture, "rb").read()
        stripped = json.loads(pre_bytes)
        del stripped["session_id"]
        json.dump(stripped, open(pre_fixture, "w"))
        c15_missing = Run(fixture_root, ci=True)
        c15_missing.c15_envelope_fixtures()
        expect_red("C15 goes red when a fixture lacks a field only its schema's required list names",
                   lambda: any(c == "C15" and "C3_pre_tool_use.json" in d
                               and "missing required field(s) ['session_id']" in d
                               for c, d in c15_missing.failures))
        open(pre_fixture, "wb").write(pre_bytes)
        stop_fixture = os.path.join(fixture_root, "hooks", "fixtures_codex", "C5_stop.json")
        stop_bytes = open(stop_fixture, "rb").read()
        typed = json.loads(stop_bytes)
        typed["stop_hook_active"] = "false"
        json.dump(typed, open(stop_fixture, "w"))
        c15_typed = Run(fixture_root, ci=True)
        c15_typed.c15_envelope_fixtures()
        expect_red("C15 goes red when stop_hook_active is present but not a boolean",
                   lambda: any(c == "C15" and "C5_stop.json" in d and "not a boolean" in d
                               for c, d in c15_typed.failures))
        open(stop_fixture, "wb").write(stop_bytes)
        leaked = json.loads(stop_bytes)
        leaked["cwd"] = "/" + "Users/someone/project"
        json.dump(leaked, open(stop_fixture, "w"))
        c15_leak = Run(fixture_root, ci=True)
        c15_leak.c15_envelope_fixtures()
        expect_red("C15 goes red when a fixture carries an absolute host path",
                   lambda: any(c == "C15" and "absolute host path" in d for c, d in c15_leak.failures))
        open(stop_fixture, "wb").write(stop_bytes)
        stray = os.path.join(fixture_root, "hooks", "fixtures_codex", "C9_unregistered.json")
        open(stray, "w").write("{}")
        c15_stray = Run(fixture_root, ci=True)
        c15_stray.c15_envelope_fixtures()
        expect_red("C15 goes red on a fixture file no table registers",
                   lambda: any(c == "C15" and "C9_unregistered.json" in d for c, d in c15_stray.failures))
        os.remove(stray)
        readme = os.path.join(fixture_root, "hooks", "fixtures_codex", "README.md")
        readme_bytes = open(readme, "rb").read()
        open(readme, "w").write("# fixtures\n")
        c15_unlabeled = Run(fixture_root, ci=True)
        c15_unlabeled.c15_envelope_fixtures()
        expect_red("C15 goes red when the synthetic fixture loses its README label",
                   lambda: any(c == "C15" and "labeled synthetic" in d for c, d in c15_unlabeled.failures))
        open(readme, "wb").write(readme_bytes)

        # ---- --verify-runtime: a planted wrong anchor goes red -----------------------------
        def fixture_binary(path, anchors, mutate=None, version=b"// Version: 9.9.9\n"):
            blob = version + b"\x00".join(anchor[5] for anchor in anchors) + b"\x00"
            if mutate:
                blob = mutate(blob)
            open(path, "wb").write(blob)
            return path

        claude_fixture = fixture_binary(os.path.join(td, "claude-fixture.bin"), CLAUDE_RUNTIME_ANCHORS)
        codex_fixture = fixture_binary(os.path.join(td, "codex-fixture.bin"), CODEX_RUNTIME_ANCHORS)
        buf = io.StringIO()
        green = verify_runtime(out=buf, claude=[("claude-cli", claude_fixture), ("claude-desktop", claude_fixture)],
                               codex=[("codex", codex_fixture, "9.9.9")])
        expect_red("verify-runtime plumbing: fixture binaries assembled from the anchor samples pass",
                   lambda: green == 0 and "RUNTIME-VERIFY-SUMMARY binaries=3" in buf.getvalue()
                   and "failures=0" in buf.getvalue())
        expect_red("verify-runtime reports every catalog scenario as UNVERIFIED with no host evidence",
                   lambda: buf.getvalue().count("UNVERIFIED ") == len(HOST_SCENARIO_CATALOG) == 14
                   and "unverified_scenarios=14" in buf.getvalue())
        wrong_cap = fixture_binary(os.path.join(td, "claude-wrong-cap.bin"), CLAUDE_RUNTIME_ANCHORS,
                                   mutate=lambda b: b.replace(b"additionalContext:8000", b"additionalContext:9000"))
        buf = io.StringIO()
        red = verify_runtime(out=buf, claude=[("claude-cli", wrong_cap), ("claude-desktop", claude_fixture)],
                             codex=[("codex", codex_fixture, "9.9.9")])
        expect_red("verify-runtime goes red on a planted wrong hook-output cap",
                   lambda: red == 1 and "FAIL claude-cli hook_output.cap_table" in buf.getvalue())
        no_session_end = fixture_binary(os.path.join(td, "claude-no-sessionend.bin"), CLAUDE_RUNTIME_ANCHORS,
                                        mutate=lambda b: b.replace(b'"SessionEnd",', b""))
        buf = io.StringIO()
        verify_runtime(out=buf, claude=[("claude-cli", no_session_end), ("claude-desktop", claude_fixture)],
                       codex=[("codex", codex_fixture, "9.9.9")])
        expect_red("verify-runtime goes red when the event enum lacks a registered event",
                   lambda: "FAIL claude-cli events.registered: event array lacks ['SessionEnd']" in buf.getvalue())
        no_budget = fixture_binary(os.path.join(td, "codex-no-budget.bin"), CODEX_RUNTIME_ANCHORS,
                                   mutate=lambda b: b.replace(b"project_doc_max_bytes = 32768", b"project_doc_max_bytes = 65536"))
        buf = io.StringIO()
        verify_runtime(out=buf, claude=[("claude-cli", claude_fixture), ("claude-desktop", claude_fixture)],
                       codex=[("codex", no_budget, "9.9.9")])
        expect_red("verify-runtime goes red when a Codex needle is absent",
                   lambda: "FAIL codex project_doc_max_bytes.default: needle absent" in buf.getvalue())
        wrong_required = fixture_binary(
            os.path.join(td, "codex-wrong-required.bin"), CODEX_RUNTIME_ANCHORS,
            mutate=lambda b: b.replace(b'    "session_id",\n    "stop_hook_active",\n    "transcript_path",\n    "turn_id"\n  ],\n  "title": "stop.command.input"',
                                       b'    "session_id",\n    "transcript_path",\n    "turn_id"\n  ],\n  "title": "stop.command.input"'))
        buf = io.StringIO()
        verify_runtime(out=buf, claude=[("claude-cli", claude_fixture), ("claude-desktop", claude_fixture)],
                       codex=[("codex", wrong_required, "9.9.9")])
        expect_red("verify-runtime goes red when a Codex schema's required list differs from the record",
                   lambda: "FAIL codex schema.Stop.required: required [" in buf.getvalue())
        buf = io.StringIO()
        absent = verify_runtime(out=buf, claude=[("claude-cli", claude_fixture)], codex=[])
        expect_red("verify-runtime goes red when a binary class is missing instead of reporting clean",
                   lambda: absent == 1 and "FAIL no claude-desktop binary found" in buf.getvalue()
                   and "FAIL no codex binary found" in buf.getvalue())
        buf = io.StringIO()
        verify_runtime(out=buf, claude=[("claude-cli", claude_fixture), ("claude-desktop", claude_fixture)],
                       codex=[("codex", codex_fixture, "9.9.9")],
                       evidence={("codex", "allow"): {"host": "fixture", "result": "pass"}})
        expect_red("verify-runtime prints a recorded host scenario as RECORDED and the rest UNVERIFIED",
                   lambda: "RECORDED codex allow" in buf.getvalue() and "unverified_scenarios=13" in buf.getvalue())
        expect_red("the Codex event allowlist is exactly the twelve events in the binary's variant run",
                   lambda: CODEX_VALID_HOOK_EVENTS == set(CODEX_HOOK_INPUT_REQUIRED)
                   and all(name.encode("ascii") in CODEX_EVENT_VARIANT_RUN for name in CODEX_VALID_HOOK_EVENTS)
                   and len(CODEX_VALID_HOOK_EVENTS) == 12)

        # ---- harness_health.sh propagates a failing gate ------------------------------------
        def health_exit(check_rc, verify_rc):
            root = os.path.join(td, f"health-{check_rc}{verify_rc}")
            os.makedirs(os.path.join(root, "hooks"))
            open(os.path.join(root, "hooks", "harness_check.py"), "w").write(
                f"import sys\nsys.exit({verify_rc} if '--verify-runtime' in sys.argv else {check_rc})\n")
            done = subprocess.run(["bash", os.path.join(ROOT, "hooks", "harness_health.sh")],
                                  env=dict(os.environ, ZH_HEALTH_ROOT=root), capture_output=True)
            log = open(os.path.join(root, "state", "harness-health.log"), encoding="utf-8").read()
            return done.returncode, log

        health_green, _log = health_exit(0, 0)
        health_check_red, check_log = health_exit(1, 0)
        health_verify_red, verify_log = health_exit(0, 1)
        expect_red("harness_health.sh exits zero when both gate modes pass", lambda: health_green == 0)
        expect_red("harness_health.sh exits non-zero when the planted gate fails, and says so in the log",
                   lambda: health_check_red != 0 and "harness_check FAILED (exit 1)" in check_log)
        expect_red("harness_health.sh exits non-zero when the planted runtime verifier fails",
                   lambda: health_verify_red != 0 and "--verify-runtime FAILED (exit 1)" in verify_log)

        # ---- assertions that can fail: each control above is re-run against a private copy of
        # this module carrying one planted defect, and must fail there by name ----------------
        source_text = open(__file__, encoding="utf-8").read()

        def private_copy(old, new, count=1):
            if source_text.count(old) != count:
                raise AssertionError(f"mutation site occurs {source_text.count(old)} time(s), "
                                     f"expected {count}")
            module = types.ModuleType("harness_check_mutant")
            module.__file__ = __file__
            exec(compile(source_text.replace(old, new), __file__, "exec"), module.__dict__)
            return module

        # The search strings are assembled, never written whole, so this block does not add
        # an occurrence of the site it mutates; a wrong count fails the proof by name.
        this_module = sys.modules[__name__]
        write_bind_baseline([])
        c12_on(good)
        expect_red("mutation: counters['bound'] += 0 fails the bound control (claims == 2, bound == 2) "
                   "by name",
                   lambda: bound_control(this_module) and not bound_control(private_copy(
                       'counters["bound"] ' + '+= 1\n', 'counters["bound"] ' + '+= 0\n', count=2)))
        write_bind_baseline([unbound_item])
        c12_on(second_text)
        expect_red("mutation: the ratchet's new list forced empty fails the new-item control by name",
                   lambda: new_item_control(this_module) and not new_item_control(private_copy(
                       "new, stale = evals.ratchet(live, baseline) " + "if worklists is not None else (sorted(live), [])\n",
                       "new, stale = ([], evals.ratchet(live, baseline)[1]) if worklists is not None else ([], [])\n")))
        c14_on(roomy)
        expect_red("mutation: a ceiling verdict that never says shrank fails the C14 control by name",
                   lambda: ceiling_control(this_module) and not ceiling_control(private_copy(
                       '("grew" if current > recorded ' + 'else "shrank")',
                       '("grew" if current > recorded else "equal")')))

        # ---- no expect_red lambda in this suite may carry a fallback clause, iterate an
        # empty literal or be a constant: that shape passes for a neighbour's reason ----------
        vacuous = vacuous_expect_red_lines(source_text)
        expect_red("no expect_red lambda in this suite carries an 'or' fallback, iterates an empty "
                   "literal or is a constant" + (f" (found at lines {vacuous})" if vacuous else ""),
                   lambda: vacuous == [])
        shapes = {
            "lambda: False or True": True,
            "lambda: False or (True)": True,
            "lambda: run.checks == 1 or not run.failures": True,
            "lambda: all(x for x in [])": True,
            "lambda: all(x for x in ())": True,
            "lambda: all(x for x in {})": True,
            "lambda: all(x for x in set())": True,
            "lambda: True": True,
            'lambda: sys.platform != "darwin" or (a and b)': False,
            'lambda: "x" in (error or "")': False,
            'lambda: a == 1 or b == 2': False,
            "lambda: not run.failures and run.checks == 1": False,
        }
        verdicts = {shape: bool(vacuous_expect_red_lines(f'expect_red("x", {shape})')) for shape in shapes}
        expect_red("the lambda sweep rejects each vacuous shape and accepts each sound one"
                   + "".join(f"; wrong on {s!r}" for s, v in verdicts.items() if v != shapes[s]),
                   lambda: verdicts == shapes)

        if os.environ.get("ZH_REVIEW_REPRODUCTIONS") == "nested":
            expect_red("review reproduction 4294811841: not re-run inside the suite run it launched; "
                       "this run is the reproduction's subject",
                       lambda: os.environ.get("ZH_REVIEW_REPRODUCTIONS") == "nested")
        else:
            expect_red("review reproduction 4294811841: the disabled bound counter fails a named C12 "
                       "proof in the mutated suite; the baseline and restored suites pass",
                       lambda: reproduction(4294811841, "mutated bound_control= 0 SELFTEST-SUMMARY "
                                                        "suite=harness_check checks="))

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
    if args and args[0] == "--verify-runtime":
        if len(args) > 1:
            sys.stderr.write(f"unknown argument: {args[1]!r}\nrun --help\n")
            return 2
        return verify_runtime()
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
