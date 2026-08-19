#!/usr/bin/env python3
"""Run the complete offline z-harness gate and validate each terminal receipt."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Callable, List, Optional, Sequence, Tuple


VERSION = "1.0.0"
ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github/workflows/check.yml"
MUTATION_WORKFLOW = ROOT / ".github/workflows/mutation-proof.yml"
WORKFLOW_DIR = ROOT / ".github/workflows"
# The contract pinned one file byte-for-byte and nothing enumerated the directory, so a
# SECOND workflow -- `permissions: write-all`, `pull_request_target`, arbitrary steps --
# ran on every push with the gate reporting the workflow contract satisfied. A CI
# configuration is the set of files, not the one file we happen to name.
EXPECTED_WORKFLOW_FILES = ("check.yml", "mutation-proof.yml")
# Every selftest suite carries a numeric floor; the eval corpus was floored only at zero,
# so cutting 25 scenarios across 7 skills down to a single semantically empty one leaves the
# whole gate green. Lower these in the commit that removes the scenarios.
# Per skill, not a total. The aggregate floors below compare only sums, so deleting an
# entire skill's eval corpus and adding the same number of throwaway files under any other
# skill restored both totals and passed the whole gate. A deletion must not be maskable by
# an addition somewhere else, so each skill's corpus is floored where it lives. Counted from
# disk here rather than read from the child receipt, which reports only totals.
EVAL_SCENARIO_FLOORS = {
    "craft-context-file": 3,
    "craft-prompt": 3,
    "craft-skill": 3,
    "git-workflow": 3,
    "ground-claims": 6,
    "outbound-drafts": 3,
    "review-prompt": 4,
}
EVAL_SCENARIO_FLOOR = 25
EVAL_SKILL_FLOOR = 7

# One floor per suite, read by both the production spec table and the selftest's fake
# runner. Two hand-maintained copies had already drifted -- render-packages was floored at
# 165 here and 178 in harness_check -- and a fake that hardcodes its own number tests the
# literal rather than the contract.
SUITE_FLOORS = {
    "harness_check": 78,
    "render-packages": 192,
    "bash_command_guard": 1366,
    "git_grep_engine_guard": 1149,
    "zsh_rev_modifier_guard": 487,
}
EXPECTED_WORKFLOW = """name: harness-check
on:
  push:
    branches: [main]
  pull_request:

permissions:
  contents: read

jobs:
  check:
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-24.04, macos-15]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
        with:
          persist-credentials: false
          fetch-depth: 0
      - uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97
        with:
          python-version: 3.13.14
      - name: install zsh where the runner image omits it
        if: runner.os == 'Linux'
        timeout-minutes: 10
        run: |
          # A stalled mirror does not fail, it hangs: `update` sat on one InRelease fetch
          # until the step budget killed it, so `|| true` never fired -- that guards against
          # a non-zero exit, not against never exiting. Each refresh is bounded instead, and
          # is advisory because the runner image ships package lists an install can already
          # satisfy. `zsh --version` remains the assertion: an absent interpreter still fails
          # this step, so resilience is not bought with coverage.
          # No backslash continuations here: this file is pinned byte-for-byte inside a
          # Python string literal, where a trailing backslash is a line continuation and
          # would collapse, so the pin could never match the file.
          APT_OPTS="-o Acquire::Retries=2 -o Acquire::http::Timeout=15"
          for attempt in 1 2 3; do
            sudo timeout 120 apt-get update $APT_OPTS || true
            sudo apt-get install -y zsh && break
            echo "apt attempt $attempt did not yield zsh; retrying"
            sleep 10
          done
          zsh --version
      - name: source-bound bootstrap and complete offline gate
        run: |
          python3 hooks/harness_check.py --ci
          python3 tools/ci-gate.py

  portable-conformance:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
        with:
          persist-credentials: false
      - uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97
        with:
          python-version: 3.13.14
      - name: pinned upstream conformance
        run: python3 tools/portable-conformance.py
"""
EXPECTED_MUTATION_WORKFLOW = """name: mutation-proof
# The sweep re-measures every mutation to prove the committed receipt is truthful rather than
# merely self-consistent, which is the one thing the offline gate cannot do: it recomputes
# from the receipt's own contents and can never re-measure. It is the only check that tells a
# real measurement from a fabricated one, so it must reach every head.
#
# It runs on every pull request. What varies is the work, not the coverage: a head that
# changes nothing a sweep would observe inherits the proof its base already carries, and the
# aggregate says so positively rather than being absent. A path filter would instead leave no
# entry at all for such a head, and a job class with no entry is indistinguishable from a
# workflow that failed to run -- absence is not evidence. `tools/write-mutation-receipt.py`
# owns both decisions, so the rule is tested rather than expressed in unreachable YAML.
on:
  pull_request:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read

jobs:
  scope:
    runs-on: ubuntu-24.04
    timeout-minutes: 10
    outputs:
      resweep: ${{ steps.decide.outputs.resweep }}
      base: ${{ steps.decide.outputs.base }}
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
        with:
          persist-credentials: false
          ref: ${{ github.event.pull_request.head.sha || github.sha }}
          fetch-depth: 0
      - uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97
        with:
          python-version: 3.13.14
      - name: decide whether this head can differ from its base in what a sweep observes
        id: decide
        run: |
          BASE='${{ github.event.pull_request.base.sha }}'
          if [ -z "$BASE" ]; then
            echo "resweep=true" >> "$GITHUB_OUTPUT"
            echo "base=" >> "$GITHUB_OUTPUT"
            echo "no pull-request base: sweeping"
          else
            RESWEEP="$(python3 tools/write-mutation-receipt.py --resweep-needed "$BASE")"
            echo "resweep=$RESWEEP" >> "$GITHUB_OUTPUT"
            echo "base=$BASE" >> "$GITHUB_OUTPUT"
            echo "base $BASE resweep=$RESWEEP"
          fi

  mutations:
    needs: scope
    if: needs.scope.outputs.resweep == 'true'
    strategy:
      fail-fast: false
      matrix:
        shard: [0, 1, 2, 3, 4, 5]
    runs-on: ubuntu-24.04
    timeout-minutes: 90
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
        with:
          persist-credentials: false
          ref: ${{ github.event.pull_request.head.sha || github.sha }}
      - uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97
        with:
          python-version: 3.13.14
      - name: install zsh and assert the exact pull-request head
        timeout-minutes: 10
        run: |
          # A stalled mirror does not fail, it hangs: `update` sat on one InRelease fetch
          # until the step budget killed it, so `|| true` never fired -- that guards against
          # a non-zero exit, not against never exiting. Each refresh is bounded instead, and
          # is advisory because the runner image ships package lists an install can already
          # satisfy. `zsh --version` remains the assertion: an absent interpreter still fails
          # this step, so resilience is not bought with coverage.
          # No backslash continuations here: this file is pinned byte-for-byte inside a
          # Python string literal, where a trailing backslash is a line continuation and
          # would collapse, so the pin could never match the file.
          APT_OPTS="-o Acquire::Retries=2 -o Acquire::http::Timeout=15"
          for attempt in 1 2 3; do
            sudo timeout 120 apt-get update $APT_OPTS || true
            sudo apt-get install -y zsh && break
            echo "apt attempt $attempt did not yield zsh; retrying"
            sleep 10
          done
          zsh --version
          git rev-parse HEAD | grep -Fx '${{ github.event.pull_request.head.sha || github.sha }}'
      - name: run mutation shard
        run: >-
          python3 tools/write-mutation-receipt.py
          --shard-index ${{ matrix.shard }}
          --shard-count 6
          --fragment mutation-fragment-${{ matrix.shard }}.json
          --expected-head '${{ github.event.pull_request.head.sha || github.sha }}'
      - uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02
        with:
          name: mutation-fragment-${{ matrix.shard }}
          path: mutation-fragment-${{ matrix.shard }}.json
          if-no-files-found: error
          retention-days: 7

  aggregate:
    if: always()
    needs: [scope, mutations]
    runs-on: ubuntu-24.04
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
        with:
          persist-credentials: false
          ref: ${{ github.event.pull_request.head.sha || github.sha }}
          fetch-depth: 0
      - uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97
        with:
          python-version: 3.13.14
      - name: install zsh and assert the exact pull-request head
        timeout-minutes: 10
        run: |
          # A stalled mirror does not fail, it hangs: `update` sat on one InRelease fetch
          # until the step budget killed it, so `|| true` never fired -- that guards against
          # a non-zero exit, not against never exiting. Each refresh is bounded instead, and
          # is advisory because the runner image ships package lists an install can already
          # satisfy. `zsh --version` remains the assertion: an absent interpreter still fails
          # this step, so resilience is not bought with coverage.
          # No backslash continuations here: this file is pinned byte-for-byte inside a
          # Python string literal, where a trailing backslash is a line continuation and
          # would collapse, so the pin could never match the file.
          APT_OPTS="-o Acquire::Retries=2 -o Acquire::http::Timeout=15"
          for attempt in 1 2 3; do
            sudo timeout 120 apt-get update $APT_OPTS || true
            sudo apt-get install -y zsh && break
            echo "apt attempt $attempt did not yield zsh; retrying"
            sleep 10
          done
          zsh --version
          git rev-parse HEAD | grep -Fx '${{ github.event.pull_request.head.sha || github.sha }}'
      - name: refuse a swept head whose shards did not all succeed
        if: needs.scope.outputs.resweep == 'true' && needs.mutations.result != 'success'
        run: |
          echo "mutations result: ${{ needs.mutations.result }}"
          exit 1
      - uses: actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093
        if: needs.scope.outputs.resweep == 'true'
        with:
          pattern: mutation-fragment-*
          path: mutation-fragments
          merge-multiple: true
      - name: reject incomplete evidence and compare the tracked receipt
        if: needs.scope.outputs.resweep == 'true'
        run: >-
          python3 tools/write-mutation-receipt.py
          --aggregate mutation-fragments/*.json
      - name: assert this head inherits its base's proof
        if: needs.scope.outputs.resweep != 'true'
        run: >-
          python3 tools/write-mutation-receipt.py
          --verify-inherited '${{ needs.scope.outputs.base }}'
"""


@dataclass(frozen=True)
class Result:
    returncode: int
    stdout: str
    stderr: str = ""


@dataclass(frozen=True)
class ReceiptSpec:
    name: str
    pattern: re.Pattern[str]
    validate: Callable[[re.Match[str], int], Optional[str]]


def _success_receipt(match: re.Match[str], returncode: int) -> Optional[str]:
    failures = int(match.group("failures"))
    reported_exit = int(match.group("exit"))
    if failures != 0 or reported_exit != 0 or returncode != 0:
        return (
            f"inconsistent success: process={returncode} reported={reported_exit} "
            f"failures={failures}"
        )
    return None


def expected_selftest_checks(suite: str) -> Optional[int]:
    """Read the exact variable-environment count from the harness registry SSOT."""
    try:
        spec = importlib.util.spec_from_file_location(
            "_ci_gate_harness_counts", ROOT / "hooks/harness_check.py")
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.expected_selftest_checks(suite)
    except Exception:
        return None


def selftest_receipt(suite: str, floor: int) -> ReceiptSpec:
    pattern = re.compile(
        rf"^SELFTEST-SUMMARY suite=(?P<suite>[a-z0-9_-]+) "
        r"checks=(?P<checks>\d+) failures=(?P<failures>\d+)$"
    )

    def validate(match: re.Match[str], returncode: int) -> Optional[str]:
        if match.group("suite") != suite:
            return f"wrong suite id {match.group('suite')!r}, expected {suite!r}"
        checks = int(match.group("checks"))
        failures = int(match.group("failures"))
        exact = expected_selftest_checks(suite)
        if exact is not None and checks != exact:
            return f"checks={checks}, expected exact execution count={exact}"
        if checks < floor:
            return f"checks={checks} below floor={floor}"
        if failures != 0 or returncode != 0:
            return f"inconsistent selftest: process={returncode} failures={failures}"
        return None

    return ReceiptSpec(suite, pattern, validate)


def validate_receipt(result: Result, spec: ReceiptSpec) -> Optional[str]:
    matches = [
        match
        for line in result.stdout.splitlines()
        if (match := spec.pattern.fullmatch(line)) is not None
    ]
    if len(matches) != 1:
        return f"{spec.name}: receipt count={len(matches)}, expected 1"
    final = result.stdout.rstrip().splitlines()
    if not final or final[-1] != matches[0].group(0):
        return f"{spec.name}: receipt is not the final non-empty stdout line"
    return spec.validate(matches[0], result.returncode)


def workflow_error(data: str, mutation_data: Optional[str] = None) -> Optional[str]:
    if mutation_data is None:
        mutation_data = EXPECTED_MUTATION_WORKFLOW
    if data != EXPECTED_WORKFLOW:
        return (
            "workflow differs from the closed contract: two explicit OS targets, Python "
            "3.13.14, full action SHAs, read-only permissions, non-persisted checkout "
            "credentials, a Linux-only zsh install whose own version call proves it "
            "landed, one ci-gate command, and one conformance command"
        )
    if mutation_data != EXPECTED_MUTATION_WORKFLOW:
        return (
            "mutation workflow differs from the closed contract: pull-request-only, "
            "exact head checkout, six deterministic shards, read-only permissions, "
            "immutable actions, artifact aggregation, and tracked-receipt comparison"
        )
    return None


CHILD_TIMEOUT_SECONDS = 120


def run_command(argv: Sequence[str]) -> Result:
    try:
        completed = subprocess.run(
            list(argv),
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=CHILD_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as expired:
        # Uncaught, this left the gate with a traceback and no receipt, which reads as a
        # tooling crash rather than as the child that ran out of time.
        return Result(
            1, "",
            f"child exceeded {CHILD_TIMEOUT_SECONDS}s: {' '.join(argv)}\n"
            f"{(expired.stderr or b'').decode('utf-8', 'replace')[-2000:]}")
    return Result(completed.returncode, completed.stdout, completed.stderr)


def command_specs(render_root: Path) -> List[Tuple[List[str], ReceiptSpec]]:
    python = sys.executable
    return [
        (
            [python, "hooks/harness_check.py", "--ci"],
            ReceiptSpec(
                "harness-ci",
                re.compile(
                    r"^HARNESS-SUMMARY mode=ci checks=(?P<checks>\d+) "
                    r"failures=(?P<failures>\d+) exit=(?P<exit>\d+)$"
                ),
                lambda match, code: (
                    "zero harness checks" if int(match.group("checks")) == 0
                    else _success_receipt(match, code)
                ),
            ),
        ),
        ([python, "hooks/harness_check.py", "--selftest"],
         selftest_receipt("harness_check", SUITE_FLOORS["harness_check"])),
        ([python, "tools/render-packages.py", "--selftest"],
         selftest_receipt("render-packages", SUITE_FLOORS["render-packages"])),
        ([python, "hooks/bash_command_guard.py", "--selftest"],
         selftest_receipt("bash_command_guard", SUITE_FLOORS["bash_command_guard"])),
        ([python, "hooks/guards/git_grep_engine_guard.py", "--selftest"],
         selftest_receipt("git_grep_engine_guard", SUITE_FLOORS["git_grep_engine_guard"])),
        ([python, "hooks/guards/zsh_rev_modifier_guard.py", "--selftest"],
         selftest_receipt("zsh_rev_modifier_guard", SUITE_FLOORS["zsh_rev_modifier_guard"])),
        (
            [python, "tools/run-skill-evals.py", "--validate"],
            ReceiptSpec(
                "eval-validate",
                re.compile(
                    r"^EVAL-VALIDATE-SUMMARY scenarios=(?P<scenarios>\d+) "
                    r"skills=(?P<skills>\d+) failures=(?P<failures>\d+) "
                    r"scope=shape-only exit=(?P<exit>\d+)$"
                ),
                lambda match, code: (
                    f"eval corpus shrank: scenarios={match.group('scenarios')} "
                    f"skills={match.group('skills')}, floors are "
                    f"{EVAL_SCENARIO_FLOOR}/{EVAL_SKILL_FLOOR}"
                    if int(match.group("scenarios")) < EVAL_SCENARIO_FLOOR
                    or int(match.group("skills")) < EVAL_SKILL_FLOOR
                    else _success_receipt(match, code)
                ),
            ),
        ),
        (
            [python, "tools/render-packages.py", "--output", str(render_root)],
            ReceiptSpec(
                "render",
                re.compile(
                    r"^RENDER-SUMMARY action=render targets=(?P<targets>\d+) "
                    r"failures=(?P<failures>\d+) exit=(?P<exit>\d+)$"
                ),
                lambda match, code: (
                    f"target count={match.group('targets')}, expected 5"
                    if int(match.group("targets")) != 5
                    else _success_receipt(match, code)
                ),
            ),
        ),
        (
            [python, "tools/render-packages.py", "--verify", str(render_root)],
            ReceiptSpec(
                "verify",
                re.compile(
                    r"^RENDER-SUMMARY action=verify targets=(?P<targets>\d+) "
                    r"failures=(?P<failures>\d+) exit=(?P<exit>\d+)$"
                ),
                lambda match, code: (
                    f"target count={match.group('targets')}, expected 5"
                    if int(match.group("targets")) != 5
                    else _success_receipt(match, code)
                ),
            ),
        ),
    ]


def floor_registry_error() -> str:
    """Return drift between this gate and the imported harness registry."""
    import importlib.util as _il
    try:
        spec = _il.spec_from_file_location("_ci_gate_harness", ROOT / "hooks/harness_check.py")
        if spec is None or spec.loader is None:
            return "cannot load hooks/harness_check.py for floor comparison"
        harness = _il.module_from_spec(spec)
        spec.loader.exec_module(harness)
        harness_floors = {
            name: floor for name, _command, floor in harness.SELFTEST_SUITES
        }
        harness_floors["harness_check"] = harness.SELFTEST_FLOOR
    except Exception as exc:
        return f"cannot import harness floor registry: {exc!r}"
    drift = {
        suite: (floor, harness_floors.get(suite))
        for suite, floor in SUITE_FLOORS.items()
        if harness_floors.get(suite) != floor
    }
    return f"suite floor registry drift: {drift}" if drift else ""


def hook_budget_error(*, settings_data=None, codex_data=None, budget=None) -> str:
    """Return drift between registered hook timeouts and the guard's inner deadline."""
    try:
        spec = importlib.util.spec_from_file_location(
            "_ci_gate_git_guard", ROOT / "hooks/guards/git_grep_engine_guard.py")
        if spec is None or spec.loader is None:
            return "cannot load git_grep_engine_guard.py for hook-budget comparison"
        guard = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(guard)
        if settings_data is None:
            settings_data = json.loads((ROOT / "settings.json").read_text(encoding="utf-8"))
        if codex_data is None:
            codex_data = json.loads(
                (ROOT / "hooks/hooks.json").read_text(encoding="utf-8"))
        return guard.hook_timeout_contract(
            settings_data=settings_data, codex_data=codex_data, budget=budget)
    except Exception as exc:
        return f"cannot verify hook-budget contract: {exc!r}"


DECISION_GOLDEN = ROOT / "contracts/goldens/guard-decisions.json"
DECISION_WRITER = ROOT / "tools/write-decision-golden.py"
RETAINED_DECISION_COMMANDS = ROOT / "contracts/goldens/retained-guard-commands.json"
SUITE_SOURCE_GOLDEN = ROOT / "contracts/goldens/suite-sources.json"
HARNESS_SOURCE = ROOT / "hooks/harness_check.py"
DECISION_CORPUS_FLOOR = 975
DECISION_WRITER_SHA256 = "8c4180468fc05a88c69fafba3a79f2387f5df2d1aa728def1670f5497a442e9d"
RETAINED_DECISION_SCHEMA_VERSION = 1
RETAINED_DECISION_NOTE = (
    "reviewed decision commands retained after their originating fixtures left the "
    "current source; append-only unless a deliberate retirement changes the independent "
    "gate contract"
)
EXPECTED_RETAINED_DECISION_COMMANDS = (
    "=/usr/bin/git grep -E 'harness\\b' -- README.md",
    "==/usr/bin/git grep -E 'harness\\b' -- README.md",
    "printf '%s\\n' 'printf() { git \"$@\"; }' git grep -E 'harness\\b' -- README.md",
    "printf '%s\\n' 'printf() { git \"$@\"; }' git grep -nE 'harness\\b' -- README.md",
    "printf '%s\\n' 'printf() { git \"$@\"; }' git show HEAD:README.md",
)


def _json_without_duplicate_keys(path: Path):
    """Load JSON while rejecting duplicate object keys hidden by ordinary json.loads."""
    def unique_object(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f"duplicate JSON object key {key!r}")
            value[key] = item
        return value

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)


def decision_writer_source_error(source_bytes=None) -> str:
    """Bind corpus derivation to the independently reviewed writer implementation."""
    try:
        source = DECISION_WRITER.read_bytes() if source_bytes is None else source_bytes
    except OSError as exc:
        return f"cannot read decision writer source: {exc}"
    actual = hashlib.sha256(source).hexdigest()
    if actual != DECISION_WRITER_SHA256:
        return "tools/write-decision-golden.py differs from its reviewed source digest"
    return ""


def retained_decision_commands_error(data=None) -> str:
    """Validate the topology-independent retained corpus against a closed set."""
    try:
        if data is None:
            data = _json_without_duplicate_keys(RETAINED_DECISION_COMMANDS)
    except (OSError, ValueError) as exc:
        return f"cannot read retained decision commands: {exc}"
    if not isinstance(data, dict):
        return "retained decision command manifest is not an object"
    required = {"schema_version", "note", "commands"}
    if set(data) != required:
        return "retained decision command manifest fields differ from the closed schema"
    if data.get("schema_version") != RETAINED_DECISION_SCHEMA_VERSION:
        return "retained decision command schema version differs"
    if data.get("note") != RETAINED_DECISION_NOTE:
        return "retained decision command note differs"
    commands = data.get("commands")
    if not isinstance(commands, list) or tuple(commands) != EXPECTED_RETAINED_DECISION_COMMANDS:
        return "retained decision commands differ from the independent closed inventory"
    return ""


def harness_source_error(golden_data=None, source_bytes=None) -> str:
    """Bind the harness this gate executes to the reviewed source registry.

    ``harness_check.py`` cannot aggregate its own selftest without recursing, so its
    source is absent from that script's C1 loop.  The outer gate executes both its
    production and selftest modes and must bind those receipts independently; otherwise
    a two-receipt stub can erase C2-C11 while preserving every process-level check here.
    """
    try:
        if golden_data is None:
            golden_data = _json_without_duplicate_keys(SUITE_SOURCE_GOLDEN)
        suites = golden_data.get("suites") if isinstance(golden_data, dict) else None
        expected = suites.get("harness_check") if isinstance(suites, dict) else None
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
            return "suite source registry has no valid harness_check digest"
        current = HARNESS_SOURCE.read_bytes() if source_bytes is None else source_bytes
        actual = hashlib.sha256(current).hexdigest()
    except (OSError, ValueError) as exc:
        return f"cannot verify harness_check source: {exc}"
    if actual != expected:
        return "hooks/harness_check.py differs from its reviewed suite source digest"
    return ""


def mutation_generator_source_error(golden_data=None, source_bytes=None) -> str:
    """Bind the mutation generator to the reviewed source registry.

    The three guards carry an authored digest here, so editing one reddens this gate until a
    reviewer updates the registry in the same commit. The tool that MEASURES those guards had
    no such binding: its only digest was ``generator_sha256`` inside the receipt it writes
    itself, so editing the generator and regenerating in one commit moved both together and
    the gate stayed green. A self-attesting measurement instrument is not attested.
    """
    try:
        if golden_data is None:
            golden_data = _json_without_duplicate_keys(SUITE_SOURCE_GOLDEN)
        suites = golden_data.get("suites") if isinstance(golden_data, dict) else None
        expected = suites.get("write-mutation-receipt") if isinstance(suites, dict) else None
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
            return "suite source registry has no valid write-mutation-receipt digest"
        current = ((ROOT / "tools/write-mutation-receipt.py").read_bytes()
                   if source_bytes is None else source_bytes)
        actual = hashlib.sha256(current).hexdigest()
    except (OSError, ValueError) as exc:
        return f"cannot verify write-mutation-receipt source: {exc}"
    if actual != expected:
        return ("tools/write-mutation-receipt.py differs from its reviewed suite source "
                "digest; update its entry in the same commit and review that diff")
    return ""


def decision_golden_error(golden_data=None, decide=None, snapshot=None,
                          contract=None, minimum_commands=None) -> str:
    """Return drift between the recorded guard verdicts and what the guards now return.

    Source digests pin bytes and floors ratchet counts; neither notices a DECISION
    reversal, because a fixture and the code it grades move together. Forty-three fixture
    expectations were rewritten on this branch with every suite green. A verdict change
    now has to appear here too, one reviewable line per command.
    """
    production_contract = snapshot is None or contract is None
    try:
        if golden_data is None:
            golden_data = _json_without_duplicate_keys(DECISION_GOLDEN)
        if production_contract:
            writer_problem = decision_writer_source_error()
            if writer_problem:
                return writer_problem
            retained_problem = retained_decision_commands_error()
            if retained_problem:
                return retained_problem
            writer_spec = importlib.util.spec_from_file_location(
                "_ci_gate_decision_writer", DECISION_WRITER)
            if writer_spec is None or writer_spec.loader is None:
                return "cannot load write-decision-golden.py for corpus comparison"
            writer = importlib.util.module_from_spec(writer_spec)
            writer_spec.loader.exec_module(writer)
            snapshot = writer.corpus_snapshot()
            contract = {
                "schema_version": writer.SCHEMA_VERSION,
                "generated_by": writer.GENERATED_BY,
                "note": writer.NOTE,
                "corpus": writer.CORPUS_DESCRIPTION,
                "top_level_keys": tuple(writer.TOP_LEVEL_KEYS),
                "exclusion_keys": tuple(writer.EXCLUSION_KEYS),
            }
        if minimum_commands is None:
            minimum_commands = DECISION_CORPUS_FLOOR if production_contract else 1
        if decide is None:
            for path in (ROOT / "hooks", ROOT / "hooks" / "guards"):
                if str(path) not in sys.path:
                    sys.path.insert(0, str(path))
            spec = importlib.util.spec_from_file_location(
                "_ci_gate_bash_guard", ROOT / "hooks/bash_command_guard.py")
            if spec is None or spec.loader is None:
                return "cannot load bash_command_guard.py for the decision golden"
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            decide = module.decide
    except Exception as exc:
        return f"cannot verify the decision golden: {exc!r}"

    if not isinstance(golden_data, dict):
        return "the decision golden root is not an object"
    problems = []
    required = set(contract["top_level_keys"])
    actual = set(golden_data)
    if actual != required:
        problems.append(
            f"top-level fields missing={sorted(required - actual)} "
            f"unexpected={sorted(actual - required)}")
    for field in ("schema_version", "generated_by", "note", "corpus"):
        if golden_data.get(field) != contract[field]:
            problems.append(f"{field} does not match the closed generator contract")
    exclusions = golden_data.get("exclusions")
    if not isinstance(exclusions, dict):
        problems.append("exclusions is not an object")
    else:
        expected_exclusion_fields = set(contract["exclusion_keys"])
        actual_exclusion_fields = set(exclusions)
        if actual_exclusion_fields != expected_exclusion_fields:
            problems.append(
                "exclusion fields "
                f"missing={sorted(expected_exclusion_fields - actual_exclusion_fields)} "
                f"unexpected={sorted(actual_exclusion_fields - expected_exclusion_fields)}")
        if exclusions != snapshot["exclusions"]:
            problems.append("recorded exclusions differ from the exact generated corpus")
    recorded = golden_data.get("decisions")
    if not isinstance(recorded, dict) or not recorded:
        problems.append("the decision golden records no commands")
        recorded = {}
    expected_commands = set(snapshot["commands"])
    recorded_commands = set(recorded)
    if len(expected_commands) < minimum_commands:
        problems.append(
            f"generated decision corpus {len(expected_commands)} is below floor "
            f"{minimum_commands}")
    missing_commands = sorted(expected_commands - recorded_commands, key=repr)
    foreign_commands = sorted(recorded_commands - expected_commands, key=repr)
    if missing_commands or foreign_commands:
        problems.append(
            f"decision corpus missing={missing_commands[:4]} "
            f"foreign={foreign_commands[:4]}")
    invalid = sorted(
        (repr(command), repr(outcome)) for command, outcome in recorded.items()
        if not isinstance(command, str)
        or not isinstance(outcome, str)
        or outcome not in {"allow", "ask", "deny"}
    )
    if invalid:
        problems.append(f"invalid decision entries={invalid[:4]}")
    if problems:
        return "decision golden schema/corpus mismatch: " + "; ".join(problems[:8])

    drift = []
    for command in snapshot["commands"]:
        expected = recorded[command]
        try:
            observed = decide(command)[0]
        except BaseException as exc:
            observed = f"raised {type(exc).__name__}"
        if observed != expected:
            drift.append((command, expected, observed))
    if not drift:
        return ""
    shown = "; ".join(f"{command[:60]!r}: {was} -> {now}" for command, was, now in drift[:6])
    return (f"guard decisions drifted from the recorded golden on {len(drift)} of "
            f"{len(recorded)} commands ({shown}"
            f"{'; ...' if len(drift) > 6 else ''}). If the change is intended, run "
            f"tools/write-decision-golden.py in the same commit and review that diff")


MUTATION_RECEIPT = ROOT / "contracts/goldens/mutation-receipt.json"
MUTATION_SUMMARY = ROOT / "contracts/goldens/mutation-summary.md"
MUTATION_SURVIVOR_DEBT_CEILING = 80
MUTATION_PLAN_FLOOR = 322
# Kills scored only because the recorded check count moved, with no assertion failing. A
# guard that increments its counter once per element of the collection under mutation moves
# that count on any removal, so such a kill is decided by loop structure before any probe
# runs and inflates `caught` without evidence. This was 17 of the 22 CROSS_VERSION_ALIAS_PROOF
# elements, thirteen of which moved a real merged verdict from deny to ask while every gate
# stayed green. Fixtures now assert those verdicts, and an arithmetic kill no longer preempts
# the merged suite that sees them, so the count fell from 17 to zero on the authoring host.
# The ceiling is one rather than zero because whether an assertion fires can depend on the
# environment: deleting "W" from MOD_UNMODELLED reddens a probe on a zsh that consumes that
# letter as a modifier and only moves the check count on a zsh that does not, so the CI
# runner observes one such kill where this host observes none. The writer owns the ceiling
# because it evaluates fresh fragments before projecting host-observed fields away; this gate
# reads that same value while validating the tracked authoring receipt.
# Declared additions, pinned here independently of the generator. The element sweep only
# REMOVES members, and removal makes a collection that grants an exemption stricter, so the
# generated sweep cannot express the direction these fail in. Each entry must be caught; a
# survivor is a live fail-open rather than coverage debt. Pinned so an entry cannot be
# dropped without this gate saying so.
# The committed receipt's kill reasons are dropped from the cross-host comparison, because
# whether an assertion fires can differ by environment. Dropped from comparison also means
# unfalsifiable: relabelling every recorded kill as a real assertion and emptying the tally
# passed both this gate and the CI aggregate, which is exactly the overstatement the reason
# field exists to prevent. Pinning the committed set by identity puts it back under review --
# laundering it now requires editing this constant, which a reader sees. This constrains the
# committed artifact only; it does not claim any host observes the same set.
# Empty because the committed receipt was measured on a host whose zsh consumes "W" as a
# modifier, so that mutation reddens a real probe there. A host whose zsh does not will
# observe one arithmetic kill instead, which the ceiling admits; the cross-host comparison
# never sees the difference. This pin constrains the COMMITTED set only, and it ratchets in
# both directions: a regeneration that produces a different set fails until this constant is
# updated, so the set can neither grow unnoticed nor be quietly emptied.
EXPECTED_UNASSERTED_KILLS: set[tuple] = set()
EXPECTED_MUTATION_ADDITIONS = {
    (
        "hooks/guards/git_grep_engine_guard.py", "_GIT_TERMINAL_OPTIONS", "set",
        "--icase-pathspecs", "a non-terminating git global is treated as terminal", (),
    ),
    (
        "hooks/guards/git_grep_engine_guard.py", "_GIT_GLOBAL_OPTIONS_WITH_VALUES", "set",
        "--no-advice", "a valueless git global is treated as value-taking", (),
    ),
    (
        "hooks/guards/git_grep_engine_guard.py", "GREP_SHORT_PATTERN_ARG", "set", "w",
        "a boolean grep short option is treated as taking the pattern", (),
    ),
    (
        "hooks/guards/git_grep_engine_guard.py", "GREP_SHORT_OPTIONAL_VALUE", "set", "w",
        "a boolean grep short option is treated as optionally valued", (),
    ),
}
EXPECTED_MUTATION_COLLECTIONS = {
    ("hooks/bash_command_guard.py", "GUARDS"): 2,
    ("hooks/bash_command_guard.py", "RANK"): 3,
    ("hooks/bash_command_guard.py", "RUNTIMES"): 2,
    ("hooks/guards/git_grep_engine_guard.py", "CONFIG_ENGINE"): 7,
    ("hooks/guards/git_grep_engine_guard.py", "CONTROL_KEYWORDS"): 12,
    ("hooks/guards/git_grep_engine_guard.py", "CROSS_VERSION_ALIAS_PROOF"): 22,
    ("hooks/guards/git_grep_engine_guard.py", "EXEC_WRAPPERS"): 6,
    ("hooks/guards/git_grep_engine_guard.py", "GIT_HAZARD_SUBCOMMANDS"): 17,
    ("hooks/guards/git_grep_engine_guard.py", "GIT_LOG_ENGINE_TOKENS"): 7,
    ("hooks/guards/git_grep_engine_guard.py", "GIT_LOG_GREP_SUBCOMMANDS"): 3,
    ("hooks/guards/git_grep_engine_guard.py", "GIT_LOG_PATTERN_OPTIONS"): 3,
    ("hooks/guards/git_grep_engine_guard.py", "GREP_LONG_BOOLEAN_OPTIONS"): 37,
    ("hooks/guards/git_grep_engine_guard.py", "GREP_LONG_ENGINE"): 4,
    ("hooks/guards/git_grep_engine_guard.py", "GREP_LONG_NEGATED_ENGINE"): 4,
    ("hooks/guards/git_grep_engine_guard.py", "GREP_LONG_OPTIONAL_VALUE"): 2,
    ("hooks/guards/git_grep_engine_guard.py", "GREP_LONG_OPTION_NAMES"): 6,
    ("hooks/guards/git_grep_engine_guard.py", "GREP_LONG_REQUIRED_VALUE"): 6,
    ("hooks/guards/git_grep_engine_guard.py", "GREP_SHORT_ENGINE"): 4,
    ("hooks/guards/git_grep_engine_guard.py", "GREP_SHORT_NOARG"): 17,
    ("hooks/guards/git_grep_engine_guard.py", "GREP_SHORT_OPTIONAL_VALUE"): 1,
    ("hooks/guards/git_grep_engine_guard.py", "GREP_SHORT_PATTERN_ARG"): 2,
    ("hooks/guards/git_grep_engine_guard.py", "GREP_SHORT_VALUE"): 4,
    ("hooks/guards/git_grep_engine_guard.py", "PCRE_ESCAPE_LETTERS"): 21,
    ("hooks/guards/git_grep_engine_guard.py", "REV_PATH_SUBCOMMANDS"): 15,
    ("hooks/guards/git_grep_engine_guard.py", "SHELLS"): 5,
    ("hooks/guards/git_grep_engine_guard.py", "SHELL_NON_FORWARDING_COMMANDS"): 2,
    ("hooks/guards/git_grep_engine_guard.py", "TRUSTED_EXTERNAL_NON_FORWARDING_COMMANDS"): 3,
    ("hooks/guards/git_grep_engine_guard.py", "WRAPPER_TERMINAL_OPTIONS"): 2,
    ("hooks/guards/git_grep_engine_guard.py", "_CLOSED_LIMITS"): 5,
    ("hooks/guards/git_grep_engine_guard.py", "_GIT_GLOBAL_OPTIONS_WITH_VALUES"): 8,
    ("hooks/guards/git_grep_engine_guard.py", "_GIT_TERMINAL_OPTIONS"): 8,
    ("hooks/guards/zsh_rev_modifier_guard.py", "MODS"): 13,
    ("hooks/guards/zsh_rev_modifier_guard.py", "MOD_MEANING"): 13,
    ("hooks/guards/zsh_rev_modifier_guard.py", "MOD_PREFIXES"): 4,
    ("hooks/guards/zsh_rev_modifier_guard.py", "MOD_UNMODELLED"): 1,
}
EXPECTED_MUTATION_SITES = {
    ("hooks/bash_command_guard.py", "merged guard function cache scope dropped"),
    ("hooks/guards/git_grep_engine_guard.py", "alias shadowing failure channel dropped"),
    ("hooks/guards/git_grep_engine_guard.py", "attached exec argv-zero grammar dropped"),
    ("hooks/guards/git_grep_engine_guard.py", "builtin trap wrapper adoption dropped"),
    ("hooks/guards/git_grep_engine_guard.py", "budget wrap deleted"),
    ("hooks/guards/git_grep_engine_guard.py", "candidate authority forced trusted"),
    ("hooks/guards/git_grep_engine_guard.py", "decision-budget checkpoint neutered"),
    ("hooks/guards/git_grep_engine_guard.py", "dynamic source adoption removed"),
    ("hooks/guards/git_grep_engine_guard.py", "dynamic source command identity dropped"),
    ("hooks/guards/git_grep_engine_guard.py", "exec single-dash terminator dropped"),
    ("hooks/guards/git_grep_engine_guard.py", "function record decision cache dropped"),
    ("hooks/guards/git_grep_engine_guard.py", "function record cache cap raised"),
    ("hooks/guards/git_grep_engine_guard.py", "git config count cap dropped"),
    ("hooks/guards/git_grep_engine_guard.py", "git config loop budget dropped"),
    ("hooks/guards/git_grep_engine_guard.py", "git hazard union adoption dropped"),
    ("hooks/guards/git_grep_engine_guard.py", "guarded-tail predicate rescans per word"),
    ("hooks/guards/git_grep_engine_guard.py",
     "invoked alias body state transition dropped"),
    ("hooks/guards/git_grep_engine_guard.py", "native command checked after alias"),
    ("hooks/guards/git_grep_engine_guard.py", "nested source shell identity dropped"),
    ("hooks/guards/git_grep_engine_guard.py", "process substitution loses typed operand"),
    ("hooks/guards/git_grep_engine_guard.py", "shell alias cycle context reset"),
    ("hooks/guards/git_grep_engine_guard.py", "shell alias forwarding dropped"),
    ("hooks/guards/git_grep_engine_guard.py", "source alias invocation dropped"),
    ("hooks/guards/git_grep_engine_guard.py", "source alias wrapper resolution dropped"),
    ("hooks/guards/git_grep_engine_guard.py", "source alias body traversal dropped"),
    ("hooks/guards/git_grep_engine_guard.py",
     "ordinary shell alias Git classification dropped"),
    ("hooks/guards/git_grep_engine_guard.py",
     "executed alias Git traversal dropped"),
    ("hooks/guards/git_grep_engine_guard.py",
     "nonordinary alias mode tracking dropped"),
    ("hooks/guards/git_grep_engine_guard.py",
     "nonordinary alias use detection dropped"),
    ("hooks/guards/git_grep_engine_guard.py",
     "declared helper function alias traversal dropped"),
    ("hooks/guards/git_grep_engine_guard.py",
     "source alias embedded operand classification dropped"),
    ("hooks/guards/git_grep_engine_guard.py",
     "source alias dynamic command detection dropped"),
    ("hooks/guards/git_grep_engine_guard.py",
     "source alias invocation lookup bypass dropped"),
    ("hooks/guards/git_grep_engine_guard.py",
     "source alias state lookup bypass dropped"),
    ("hooks/guards/git_grep_engine_guard.py",
     "same-shell alias mutation wrapper resolution dropped"),
    ("hooks/guards/git_grep_engine_guard.py", "called function alias state dropped"),
    ("hooks/guards/git_grep_engine_guard.py", "TRAPDEBUG function alias state dropped"),
    ("hooks/guards/git_grep_engine_guard.py", "DEBUG trap alias state dropped"),
    ("hooks/guards/git_grep_engine_guard.py", "repeat zero execution boundary dropped"),
    ("hooks/guards/git_grep_engine_guard.py", "source command wrapper omitted"),
    ("hooks/guards/git_grep_engine_guard.py", "source exec wrapper omitted"),
    ("hooks/guards/git_grep_engine_guard.py", "trap action traversal dropped"),
    ("hooks/guards/git_grep_engine_guard.py", "zsh trap function source traversal dropped"),
    ("hooks/guards/zsh_rev_modifier_guard.py", "zsh shared resolver bypassed"),
    ("hooks/guards/zsh_rev_modifier_guard.py", "zsh trap function traversal dropped"),
    ("hooks/guards/zsh_rev_modifier_guard.py", "zsh unmodelled modifier uncertainty dropped"),
    ("hooks/guards/zsh_rev_modifier_guard.py",
     "zsh unmodelled modifier prefix grammar dropped"),
}
EXPECTED_MUTATION_SITE_DIGEST = (
    "4999ddfc67d497d16a8757a5cfc9ff5a49c7486a20e27a1810a88d53d0945626"
)
EXPECTED_MUTATION_EXCLUSIONS = {
    "hooks/guards/git_grep_engine_guard.py::ALIAS_GUARDED":
        "repeated characters identify an enum word, not a membership charset",
    "hooks/guards/git_grep_engine_guard.py::ALIAS_HARMLESS":
        "repeated characters identify an enum word, not a membership charset",
    "hooks/guards/git_grep_engine_guard.py::ALIAS_UNCERTAIN":
        "repeated characters identify an enum word, not a membership charset",
    "hooks/guards/git_grep_engine_guard.py::FIXTURES":
        "fixture corpus; removing a fixture measures the grader",
    "hooks/guards/git_grep_engine_guard.py::GREP_LONG_PATTERN_ARG":
        "empty grammar collection has no element mutation; absence is fixture-pinned",
    "hooks/guards/git_grep_engine_guard.py::ZSH_EQUALS_OFF":
        "repeated characters identify an enum word, not a membership charset",
    "hooks/guards/git_grep_engine_guard.py::ZSH_EQUALS_UNKNOWN":
        "repeated characters identify an enum word, not a membership charset",
    "hooks/guards/git_grep_engine_guard.py::_EQUALS_LOOKUP_CACHE":
        "runtime memoization map, not a guarded membership collection",
    "hooks/guards/git_grep_engine_guard.py::_GIT_AUTHORITY_CACHE":
        "runtime memoization map, not a guarded membership collection",
    "hooks/guards/zsh_rev_modifier_guard.py::FIXTURES":
        "fixture corpus; removing a fixture measures the grader",
    "hooks/guards/zsh_rev_modifier_guard.py::UNRESOLVED_GIT":
        "repeated characters identify an enum word, not a membership charset",
}


def mutation_unasserted_kill_ceiling() -> int:
    """Read the fresh-observation ceiling from the mutation evidence owner."""
    spec = importlib.util.spec_from_file_location(
        "_ci_gate_mutation_ceiling", ROOT / "tools/write-mutation-receipt.py")
    if spec is None or spec.loader is None:
        raise ValueError("cannot load write-mutation-receipt.py for its kill ceiling")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.UNASSERTED_KILL_CEILING


def mutation_site_policy_digest(descriptors) -> str:
    """Hash every semantic site field under a stable, reviewable framing."""
    records = []
    for descriptor in descriptors:
        records.append({
            "module": descriptor["module"],
            "label": descriptor["label"],
            "anchor_sha256": descriptor["anchor_sha256"],
            "replacement_sha256": descriptor["replacement_sha256"],
            "allowed_statuses": list(descriptor["allowed_statuses"]),
        })
    records.sort(key=lambda item: (item["module"], item["label"]))
    framed = json.dumps(
        records, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(framed).hexdigest()


def mutation_policy_error(plan, exclusions, policy) -> str:
    """Validate the plan against a closed inventory independent of its generator."""
    collection_counts = {}
    addition_descriptors = []
    site_identities = []
    site_descriptors = []
    semantic_targets = []
    ids = []
    problems = []
    for descriptor in plan:
        if not isinstance(descriptor, dict):
            return "mutation plan contains a non-object descriptor"
        ids.append(descriptor.get("id"))
        if descriptor.get("kind") == "set-element":
            identity = (descriptor.get("module"), descriptor.get("name"))
            collection_counts[identity] = collection_counts.get(identity, 0) + 1
        elif descriptor.get("kind") == "site":
            module = descriptor.get("module")
            label = descriptor.get("label")
            anchor = descriptor.get("anchor_sha256")
            replacement = descriptor.get("replacement_sha256")
            allowed = descriptor.get("allowed_statuses")
            site_identities.append((module, label))
            if (not isinstance(module, str) or not isinstance(label, str)
                    or not isinstance(anchor, str)
                    or not re.fullmatch(r"[0-9a-f]{64}", anchor)
                    or not isinstance(replacement, str)
                    or not re.fullmatch(r"[0-9a-f]{64}", replacement)
                    or not isinstance(allowed, (list, tuple))
                    or any(not isinstance(status, str) for status in allowed)):
                problems.append(f"site descriptor fields are invalid for {(module, label)}")
                continue
            normalized = {
                "module": module, "label": label,
                "anchor_sha256": anchor,
                "replacement_sha256": replacement,
                "allowed_statuses": tuple(allowed),
            }
            site_descriptors.append(normalized)
            semantic_targets.append((module, anchor, replacement))
        elif descriptor.get("kind") == "set-addition":
            module = descriptor.get("module")
            name = descriptor.get("name")
            collection_kind = descriptor.get("collection_kind")
            element = descriptor.get("element")
            label = descriptor.get("label")
            allowed = descriptor.get("allowed_statuses")
            if (not isinstance(module, str) or not isinstance(name, str)
                    or not isinstance(collection_kind, str)
                    or not isinstance(element, str) or not isinstance(label, str)
                    or not isinstance(allowed, (list, tuple))
                    or any(not isinstance(status, str) for status in allowed)):
                problems.append(
                    f"addition descriptor fields are invalid for {(module, name)}")
                continue
            addition_descriptors.append(
                (module, name, collection_kind, element, label, tuple(allowed)))
        else:
            return f"mutation plan contains unknown kind {descriptor.get('kind')!r}"
    if len(addition_descriptors) != len(set(addition_descriptors)):
        problems.append("addition inventory contains duplicate full descriptors")
    if set(addition_descriptors) != policy["additions"]:
        problems.append(
            f"addition inventory differs: observed={set(addition_descriptors)} "
            f"required={policy['additions']}")
    if collection_counts != policy["collections"]:
        problems.append(
            f"collection inventory differs: observed={collection_counts} "
            f"required={policy['collections']}")
    if len(site_identities) != len(set(site_identities)):
        problems.append("site inventory contains duplicate module/label identities")
    if set(site_identities) != policy["sites"]:
        problems.append(
            f"site inventory differs: observed={set(site_identities)} "
            f"required={policy['sites']}")
    if len(semantic_targets) != len(set(semantic_targets)):
        problems.append("site inventory contains duplicate semantic mutation targets")
    if (len(site_descriptors) == len(site_identities)
            and mutation_site_policy_digest(site_descriptors)
            != policy["site_digest"]):
        problems.append("site descriptor semantics differ from the independent digest")
    if exclusions != policy["exclusions"]:
        problems.append("sweep exclusions differ from the independent closed inventory")
    if len(plan) < policy["floor"]:
        problems.append(
            f"plan cardinality {len(plan)} is below floor {policy['floor']}")
    if len(ids) != len(set(ids)) or any(not isinstance(item, str) for item in ids):
        problems.append("mutation IDs are missing or duplicated")
    return "; ".join(problems)


def mutation_receipt_error(receipt_data=None, plan=None, exclusions=None,
                           contract=None, current_sources=None, ceiling=None,
                           policy=None, unasserted_ceiling=None,
                           unasserted_identities=None) -> str:
    """Validate exact mutation schema, plan coverage, and every derived field."""
    try:
        production_contract = plan is None or exclusions is None or contract is None
        if receipt_data is None:
            receipt_data = _json_without_duplicate_keys(MUTATION_RECEIPT)
        if plan is None or exclusions is None or contract is None:
            spec = importlib.util.spec_from_file_location(
                "_ci_gate_mutation", ROOT / "tools/write-mutation-receipt.py")
            if spec is None or spec.loader is None:
                return "cannot load write-mutation-receipt.py for the mutation receipt"
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            plan, exclusions = module.mutation_plan()
            contract = {
                "schema_version": module.SCHEMA_VERSION,
                # A schema pin, not an attestation: this field is a constant the gate
                # compares, so it can never record which flags actually ran. It previously
                # named --accept-receipt-changes unconditionally, which read as provenance
                # for the one bypass that skips receipt comparison. CI aggregates in verify
                # mode, so a real mode field cannot live here either -- the freshly computed
                # value would never equal the committed one.
                "generated_by": f"{module.GENERATOR} --aggregate",
                "note": module.NOTE,
                "keys": tuple(module.RECEIPT_KEYS),
                "generator_sha256": module.file_sha256(ROOT / module.GENERATOR),
                "guards": tuple(module.GUARDS),
                "plan_sha256": module.digest(plan),
                "kill_reasons": frozenset(module.KILL_REASONS),
                "unasserted_reason": module.UNASSERTED_KILL_REASON,
                "unasserted_ceiling": module.UNASSERTED_KILL_CEILING,
            }
            current_sources = module.source_digests()
        if policy is None and production_contract:
            policy = {
                "collections": EXPECTED_MUTATION_COLLECTIONS,
                "sites": EXPECTED_MUTATION_SITES,
                "site_digest": EXPECTED_MUTATION_SITE_DIGEST,
                "exclusions": EXPECTED_MUTATION_EXCLUSIONS,
                "additions": EXPECTED_MUTATION_ADDITIONS,
                "floor": MUTATION_PLAN_FLOOR,
            }
        if ceiling is None:
            ceiling = MUTATION_SURVIVOR_DEBT_CEILING
        if unasserted_ceiling is None:
            unasserted_ceiling = contract["unasserted_ceiling"]
        if unasserted_identities is None:
            unasserted_identities = EXPECTED_UNASSERTED_KILLS
    except Exception as exc:
        return f"cannot verify the mutation receipt: {exc!r}"
    if not isinstance(receipt_data, dict):
        return "mutation receipt root is not an object"
    problems = []
    if policy is not None:
        policy_problem = mutation_policy_error(plan, exclusions, policy)
        if policy_problem:
            problems.append("closed mutation policy: " + policy_problem)
    expected_fields = set(contract["keys"])
    actual_fields = set(receipt_data)
    if actual_fields != expected_fields:
        problems.append(
            f"top-level fields missing={sorted(expected_fields - actual_fields)} "
            f"unexpected={sorted(actual_fields - expected_fields)}")
    for field in ("schema_version", "generated_by", "note", "generator_sha256",
                  "plan_sha256"):
        expected = contract[field]
        if receipt_data.get(field) != expected:
            problems.append(f"{field} differs from the generator contract")
    if receipt_data.get("source_digests") != current_sources:
        problems.append("source digests do not equal all current guard sources")
    if receipt_data.get("baseline") != {
            relative: "passed" for relative in contract["guards"]}:
        problems.append("baseline does not prove all three guard suites passed")
    if receipt_data.get("sweep_exclusions") != exclusions:
        problems.append("module-qualified sweep exclusions differ from the exact scan")
    plan_by_id = {item["id"]: item for item in plan}
    results = receipt_data.get("results")
    if not isinstance(results, dict) or not results:
        problems.append("results are empty or not an object")
        results = {}
    missing = sorted(set(plan_by_id) - set(results))
    foreign = sorted(set(results) - set(plan_by_id))
    if missing or foreign:
        problems.append(f"result inventory missing={missing[:4]} foreign={foreign[:4]}")
    observed_survivors = []
    addition_survivors = []
    site_survivors = []
    observed_unasserted = []
    unasserted_reason = contract["unasserted_reason"]
    for mutation_id in sorted(set(plan_by_id) & set(results)):
        expected = dict(plan_by_id[mutation_id])
        allowed_statuses = set(expected.pop("allowed_statuses", ()) or ())
        recorded = results[mutation_id]
        if not isinstance(recorded, dict):
            problems.append(f"result {mutation_id} is not an object")
            continue
        outcome = recorded.get("outcome")
        if outcome not in {"caught", "survived"}:
            problems.append(f"result {mutation_id} has invalid outcome {outcome!r}")
            continue
        reason = recorded.get("reason")
        if reason not in contract["kill_reasons"]:
            problems.append(f"result {mutation_id} has invalid reason {reason!r}")
            continue
        # A survived outcome has exactly one truthful reason, and a kill can never carry it.
        # Without this the reason is decorative: a caught result could record "survived" and
        # the unasserted tally below would be whatever the generator chose to report.
        if (outcome == "survived") != (reason == "survived"):
            problems.append(
                f"result {mutation_id} outcome {outcome!r} contradicts reason {reason!r}")
            continue
        # A crash status is only a legitimate kill where the plan declared it tolerable.
        if reason in {"timeout", "invalid-receipt"} and reason not in allowed_statuses:
            problems.append(
                f"result {mutation_id} records status {reason!r} its plan does not allow")
            continue
        expected["outcome"] = outcome
        expected["reason"] = reason
        if recorded != expected:
            problems.append(f"result {mutation_id} fields do not match its planned mutation")
        if outcome == "survived":
            observed_survivors.append(mutation_id)
            if expected["kind"] == "site":
                site_survivors.append(mutation_id)
            elif expected["kind"] == "set-addition":
                addition_survivors.append(mutation_id)
        elif reason == unasserted_reason:
            observed_unasserted.append(mutation_id)
    if receipt_data.get("survivors") != observed_survivors:
        problems.append("survivor IDs are not exactly derived from results")
    if receipt_data.get("unasserted_kills") != observed_unasserted:
        problems.append("unasserted-kill IDs are not exactly derived from results")
    recorded_unasserted = {
        (results[i].get("module"), results[i].get("name"), results[i].get("element"))
        for i in observed_unasserted if isinstance(results.get(i), dict)
    }
    if recorded_unasserted != set(unasserted_identities):
        problems.append(
            f"recorded unasserted kills {sorted(recorded_unasserted)} differ from the "
            f"reviewed set {sorted(unasserted_identities)}")
    if len(observed_unasserted) > unasserted_ceiling:
        problems.append(
            f"unasserted kills {len(observed_unasserted)} exceed ceiling "
            f"{unasserted_ceiling}: these mutations are recorded caught while no assertion "
            f"failed, so the count is not evidence the suites observe them")
    if receipt_data.get("total") != len(plan_by_id):
        problems.append("total is not the exact mutation-plan cardinality")
    if receipt_data.get("caught") != len(plan_by_id) - len(observed_survivors):
        problems.append("caught is not derived from total minus survivors")
    if site_survivors:
        problems.append(f"site mutations survived: {site_survivors[:4]}")
    if addition_survivors:
        problems.append(f"declared additions survived: {addition_survivors[:4]}")
    if len(observed_survivors) > ceiling:
        problems.append(
            f"survivor debt {len(observed_survivors)} exceeds ceiling {ceiling}")
    return ("mutation receipt mismatch: " + "; ".join(problems[:8])) if problems else ""


def mutation_summary_error(receipt_data=None, summary_bytes=None) -> str:
    """Require the canonical summary bytes to be derived from the strict receipt."""
    try:
        if receipt_data is None:
            receipt_data = _json_without_duplicate_keys(MUTATION_RECEIPT)
        receipt_problem = mutation_receipt_error(receipt_data=receipt_data)
        if receipt_problem:
            return "cannot derive mutation summary from an invalid receipt: " + receipt_problem
        spec = importlib.util.spec_from_file_location(
            "_ci_gate_mutation_summary", ROOT / "tools/write-mutation-receipt.py")
        if spec is None or spec.loader is None:
            return "cannot load write-mutation-receipt.py for summary derivation"
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        expected = module.summary_text(receipt_data).encode("utf-8")
        actual = MUTATION_SUMMARY.read_bytes() if summary_bytes is None else summary_bytes
    except Exception as exc:
        return f"cannot verify mutation summary derivation: {exc!r}"
    if actual != expected:
        return "contracts/goldens/mutation-summary.md is not derived from the strict receipt"
    return ""


REVIEW_ROOT = ROOT / "contracts/review"
INCLUDE_OPEN = "<!-- include: "
INCLUDE_CLOSE = "<!-- end include -->"
FENCE_MARKERS = ("```", "~~~")
REQUIRED_REVIEW_INCLUDES = {
    "pr-8/description.md": ("contracts/goldens/mutation-summary.md",),
}
REGISTERED_REVIEW_DOCUMENTS = frozenset({"description.md", "title.txt", "README.md"})
HANDOFF_DOCTRINE = {
    "skills/outbound-drafts/SKILL.md": (
        "Review handoffs are append-only, one exact head per comment.",
        "Never edit, replace, or delete a posted handoff",
    ),
    "skills/pr-review-method/SKILL.md": (
        "A head-specific handoff",
        "it never owns a finding",
    ),
    "skills/pr-review-method/references/deferred.md": (
        "append-only handoff comments, one exact head per comment",
    ),
    "contracts/review/README.md": (
        "Head-specific handoffs are append-only external comments",
        "Do not keep a mutable tracked file as the current handoff",
    ),
}
FORBIDDEN_HANDOFF_DOCTRINE = (
    "one roll-up comment per pr",
    "one roll-up per pull request",
    "one tracking comment edited in place",
    "edited in place across rounds",
    "edited rather than reposted",
)


def include_blocks(lines):
    """(header, close, name) per include block, ignoring blocks inside a code fence.

    The include syntax has to be DOCUMENTED somewhere, and the only place it belongs is
    contracts/review/README.md -- inside a fence, as an example. A scanner blind to fences
    reads that example as a live include and reports the README as drifted from a file the
    example never claimed to copy, so the convention's own documentation cannot satisfy it.

    A block's body is skipped wholesale rather than scanned, so a fence in INCLUDED content
    -- a generated table may carry one -- cannot leave the scanner stuck in a fence and
    silently blind to every later include.
    """
    found, fence, index = [], None, 0
    while index < len(lines):
        stripped = lines[index].lstrip()
        marker = next((m for m in FENCE_MARKERS if stripped.startswith(m)), None)
        if fence is not None:
            fence = None if marker == fence else fence
        elif marker:
            fence = marker
        elif INCLUDE_OPEN in lines[index]:
            head = lines[index].split(INCLUDE_OPEN, 1)[1]
            name = head.split("-->")[0].strip() if "-->" in head else ""
            close = next((j for j in range(index + 1, len(lines))
                          if INCLUDE_CLOSE in lines[j]), None)
            found.append((index, close, name))
            if close is None:
                break
            index = close + 1
            continue
        index += 1
    return found


def review_path_label(path):
    """Repo-relative where that reads better, absolute where relative_to would raise.

    A document outside the repo only appears in this check's own fixtures, but raising
    ValueError while BUILDING a failure message turns a reported problem into a crash.
    """
    try:
        return path.relative_to(ROOT)
    except ValueError:
        return path


def review_include_error(review_root=None, required_inventory=None) -> str:
    """Return any outbound review file whose included block drifted from its source.

    Every number this branch published wrong was retyped into a GitHub comment from a
    failure list, where no gate could see it. Outbound review text lives under
    contracts/review/ so it is inside a gate at all, and a block marked as included must be
    byte-identical to the file it names -- so a generated table cannot go stale in the copy
    a reviewer actually reads.

    A missing directory and an empty one are failures, not clean verdicts: this check
    asserts that outbound text is gated, and it cannot assert that over nothing.
    """
    root = REVIEW_ROOT if review_root is None else Path(review_root)
    enforce_inventory = review_root is None if required_inventory is None else True
    required_inventory = (
        REQUIRED_REVIEW_INCLUDES if required_inventory is None else required_inventory)
    if not root.is_dir():
        return (f"{REVIEW_ROOT.name}/ does not exist, so no outbound review text is gated; "
                "this check asserts nothing without it")
    documents = sorted(root.rglob("*.md"))
    if not documents:
        return (f"no markdown under {root}, so the review-include check scanned nothing, "
                "which is not a clean verdict")
    problems, blocks, observed_inventory = [], 0, {}
    for document in documents:
        try:
            document_bytes = document.read_bytes()
            lines = document_bytes.decode("utf-8").splitlines()
            raw_lines = document_bytes.splitlines(keepends=True)
        except UnicodeDecodeError as exc:
            problems.append(
                f"{review_path_label(document)} is not UTF-8 ({exc})")
            continue
        for header, close, name in include_blocks(lines):
            blocks += 1
            relative_document = str(document.relative_to(root))
            observed_inventory.setdefault(relative_document, []).append(name)
            if close is None:
                problems.append(f"{review_path_label(document)}: unterminated include")
                continue
            if not name:
                problems.append(f"{review_path_label(document)}: include names no file")
                continue
            source = (ROOT / name).resolve()
            try:
                source.relative_to(ROOT.resolve())
            except ValueError:
                problems.append(
                    f"{review_path_label(document)} includes {name}, which is outside "
                    "the repository")
                continue
            if not source.is_file():
                problems.append(f"{review_path_label(document)} includes {name}, "
                                "which does not exist")
                continue
            embedded = b"".join(raw_lines[header + 1:close])
            expected = source.read_bytes()
            if embedded != expected:
                problems.append(
                    f"{review_path_label(document)} has a stale copy of {name}; "
                    "regenerate it before posting")
    if enforce_inventory:
        observed = {document: tuple(sorted(names))
                    for document, names in observed_inventory.items()}
        required = {document: tuple(sorted(names))
                    for document, names in required_inventory.items()}
        if observed != required:
            problems.append(
                f"live include inventory differs: observed={observed} required={required}")
    if problems:
        return (f"outbound review text drifted from its sources "
                f"(scanned {len(documents)} files, {blocks} include blocks under "
                f"{root}): " + "; ".join(problems[:5]))
    return ""


def eval_corpus_distribution_error(counts=None, floors=None) -> str:
    """Require every skill's own eval corpus to hold, not merely the totals."""
    floors = EVAL_SCENARIO_FLOORS if floors is None else floors
    if counts is None:
        counts = {}
        skills_root = ROOT / "skills"
        if skills_root.is_dir():
            for skill in sorted(skills_root.iterdir()):
                found = sorted((skill / "evals").glob("*.json")) if skill.is_dir() else []
                if found:
                    counts[skill.name] = len(found)
    problems = []
    for skill, floor in sorted(floors.items()):
        observed = counts.get(skill, 0)
        if observed < floor:
            problems.append(f"{skill} holds {observed} scenario(s), floor {floor}")
    return ("eval corpus distribution: " + "; ".join(problems[:6])) if problems else ""


def _raises(call, kind) -> bool:
    """True when `call` raises `kind`; a check that swallows it would prove nothing."""
    try:
        call()
    except kind:
        return True
    except Exception:
        return False
    return False


def review_handoff_policy_error(source_texts=None, review_root=None,
                                extra_texts=None) -> str:
    """Require append-only head-specific handoffs and reject the retired mutable artifact."""
    problems = []
    if source_texts is None:
        source_texts = {}
        for relative in HANDOFF_DOCTRINE:
            path = ROOT / relative
            if not path.is_file():
                problems.append(f"missing handoff doctrine source {relative}")
                continue
            source_texts[relative] = path.read_text(encoding="utf-8")
    for relative, required in HANDOFF_DOCTRINE.items():
        text = source_texts.get(relative)
        if text is None:
            problems.append(f"missing handoff doctrine source {relative}")
            continue
        normalized_text = re.sub(r"\s+", " ", text)
        for phrase in required:
            if phrase not in normalized_text:
                problems.append(f"{relative} is missing required handoff rule {phrase!r}")
    # Scan every markdown document, not only the four that carry the rule. The retired
    # spelling is not legitimate anywhere here, and the file that outranks every skill --
    # AGENTS.md -- is not among the four, so a scan limited to them left the one document
    # that could reinstate the rule with the most authority entirely unread.
    scanned = dict(source_texts)
    if extra_texts is None:
        # Tracked files only. A directory walk also reads nested worktrees and any other
        # untracked checkout living inside the tree, which are other branches' bytes and
        # not this commit's claim -- the same mistake that makes C8 red locally and green
        # in CI. `git ls-files` is the scan set the commit is actually accountable for.
        listed = subprocess.run(
            ["git", "-C", str(ROOT), "ls-files", "-z", "--", "*.md"],
            capture_output=True, text=True)
        if listed.returncode != 0:
            problems.append("cannot enumerate tracked markdown for the forbidden-rule scan")
            names = []
        else:
            names = [name for name in listed.stdout.split("\0") if name]
        for name in names:
            if name in scanned:
                continue
            try:
                scanned[name] = (ROOT / name).read_text(encoding="utf-8")
            except OSError:
                continue
    else:
        scanned.update(extra_texts)
    for relative, text in sorted(scanned.items()):
        joined = re.sub(r"\s+", " ", text).casefold()
        for phrase in FORBIDDEN_HANDOFF_DOCTRINE:
            if phrase in joined:
                problems.append(
                    f"retired mutable-handoff rule is present in {relative}: {phrase!r}")
    # An allowlist, not a denylist of one basename. The doctrine forbids keeping a mutable
    # tracked file as the current handoff -- not keeping a file called rollup.md -- and a
    # denylist is escaped by renaming, which is how a tracked handoff.md carrying a
    # hand-typed figure passed every review check.
    root = REVIEW_ROOT if review_root is None else Path(review_root)
    if root.is_dir():
        unregistered = sorted(
            str(review_path_label(path))
            for path in root.rglob("*")
            if path.is_file() and path.name not in REGISTERED_REVIEW_DOCUMENTS
        )
        if unregistered:
            problems.append(
                f"unregistered document in the review tree, which may be a mutable "
                f"handoff: {unregistered[:6]}")
    if not problems:
        return ""
    # Per testing-ci: a guard that models only the spellings it knows must say so where the
    # verdict is read. Required-phrase presence is monotone -- a document can carry the rule
    # and contradict it in the next paragraph -- and the forbidden list is a denylist that
    # a paraphrase walks past. Both arms are tripwires, not proofs.
    return (
        "review handoff policy mismatch: " + "; ".join(problems[:8])
        + " (scope: literal retired spellings across tracked markdown and registered "
        + "document names; a paraphrase or an added contradicting rule is out of scope)")


def gated_environment(which=None, runner=None) -> str:
    """Name the interpreters this run's verdicts were measured against.

    Two probe corpora reduce to skips when zsh is missing -- 105 modifier probes and 46
    zsh-dependent shell-boundary probes -- and both preserve their planned check counts.
    A suite's receipt is therefore byte-identical whether those probes ran or were skipped,
    and only a child's LAST line survives this gate, which drops the printed SKIP. Without
    this line nothing in the record distinguishes the two, so a claim about zsh could go
    unverified on a runner with no zsh and read as proven.

    Reported, never asserted: a host without zsh may still run the gate. What it may not
    do is leave no trace that the zsh-dependent claims were not checked.
    """
    which = shutil.which if which is None else which
    runner = subprocess.run if runner is None else runner
    parts = []
    for name in ("git", "zsh"):
        path = which(name)
        if not path:
            parts.append(f"{name}=absent")
            continue
        try:
            result = runner([path, "--version"], capture_output=True, text=True,
                            timeout=10)
            reported = result.stdout.strip().splitlines()
            version = reported[0] if reported else "unreported"
        except (OSError, subprocess.SubprocessError):
            version = "unreported"
        parts.append(f"{name}={path} ({version})")
    return "CI-GATE-ENV " + " ".join(parts)


def gate(
    runner: Callable[[Sequence[str]], Result] = run_command,
    *,
    emit_child_output: bool = True,
) -> int:
    failures: List[str] = []
    workflow = WORKFLOW.read_text(encoding="utf-8") if WORKFLOW.is_file() else ""
    mutation_workflow = (
        MUTATION_WORKFLOW.read_text(encoding="utf-8")
        if MUTATION_WORKFLOW.is_file() else ""
    )
    problem = workflow_error(workflow, mutation_workflow)
    print(f"  {'FAIL' if problem else 'PASS'} workflow-contract")
    if problem:
        failures.append(problem)
    present = (
        tuple(sorted(p.name for p in WORKFLOW_DIR.iterdir() if p.is_file()))
        if WORKFLOW_DIR.is_dir() else ()
    )
    extra = [name for name in present if name not in EXPECTED_WORKFLOW_FILES]
    missing = [name for name in EXPECTED_WORKFLOW_FILES if name not in present]
    inventory_problem = (
        f"workflow directory inventory: unexpected={extra} missing={missing}"
        if extra or missing else ""
    )
    print(f"  {'FAIL' if inventory_problem else 'PASS'} workflow-inventory "
          f"({len(present)} file(s))")
    if inventory_problem:
        failures.append(inventory_problem)
    floor_problem = floor_registry_error()
    print(f"  {'FAIL' if floor_problem else 'PASS'} floor-registry")
    if floor_problem:
        failures.append(floor_problem)
    harness_source_problem = harness_source_error()
    print(f"  {'FAIL' if harness_source_problem else 'PASS'} harness-source")
    if harness_source_problem:
        failures.append(harness_source_problem)
    # Reported here rather than in the tracked summary: whether an assertion fires can differ
    # between hosts, so this count belongs in the run that observed it, not in a file two
    # hosts compare byte for byte.
    try:
        _receipt = _json_without_duplicate_keys(MUTATION_RECEIPT)
        _unasserted = len(_receipt.get("unasserted_kills") or [])
        _caught = _receipt.get("caught")
        print(f"  INFO mutation-kills caught={_caught} scored-on-count-alone={_unasserted} "
              f"ceiling={mutation_unasserted_kill_ceiling()} "
              f"(recorded in the committed receipt, not measured on this host)")
    except Exception as exc:
        print(f"  INFO mutation-kills unavailable: {exc!r}")
    generator_source_problem = mutation_generator_source_error()
    print(f"  {'FAIL' if generator_source_problem else 'PASS'} mutation-generator-source")
    if generator_source_problem:
        failures.append(generator_source_problem)
    budget_problem = hook_budget_error()
    print(f"  {'FAIL' if budget_problem else 'PASS'} hook-budget")
    if budget_problem:
        failures.append(budget_problem)
    decision_problem = decision_golden_error()
    print(f"  {'FAIL' if decision_problem else 'PASS'} decision-golden")
    if decision_problem:
        failures.append(decision_problem)
    mutation_problem = mutation_receipt_error()
    print(f"  {'FAIL' if mutation_problem else 'PASS'} mutation-receipt")
    if mutation_problem:
        failures.append(mutation_problem)
    summary_problem = mutation_summary_error()
    print(f"  {'FAIL' if summary_problem else 'PASS'} mutation-summary")
    if summary_problem:
        failures.append(summary_problem)
    review_problem = review_include_error()
    print(f"  {'FAIL' if review_problem else 'PASS'} review-includes")
    if review_problem:
        failures.append(review_problem)
    distribution_problem = eval_corpus_distribution_error()
    print(f"  {'FAIL' if distribution_problem else 'PASS'} eval-corpus-distribution")
    if distribution_problem:
        failures.append(distribution_problem)
    handoff_problem = review_handoff_policy_error()
    print(f"  {'FAIL' if handoff_problem else 'PASS'} review-handoff-policy")
    if handoff_problem:
        failures.append(handoff_problem)
    completed = 1
    with tempfile.TemporaryDirectory(prefix="z-harness-ci-gate-") as raw:
        render_root = Path(raw) / "rendered"
        for argv, spec in command_specs(render_root):
            result = runner(argv)
            problem = validate_receipt(result, spec)
            if emit_child_output:
                if problem:
                    if result.stdout:
                        print(result.stdout.rstrip())
                    if result.stderr:
                        print(result.stderr.rstrip(), file=sys.stderr)
                elif result.stdout.rstrip():
                    print(result.stdout.rstrip().splitlines()[-1])
            print(f"  {'FAIL' if problem else 'PASS'} receipt {spec.name}")
            completed += 1
            if problem:
                failures.append(problem)
    code = 1 if failures else 0
    for failure in failures:
        print(f"  - {failure}")
    print(gated_environment())
    print(
        f"CI-GATE-SUMMARY suites={completed} failures={len(failures)} exit={code}"
    )
    return code


def selftest() -> int:
    checks = failures = 0

    def expect(label: str, predicate: bool) -> None:
        nonlocal checks, failures
        checks += 1
        failures += not predicate
        print(f"  {'PASS' if predicate else 'FAIL'} {label}")

    spec = selftest_receipt("probe", 5)
    good = "SELFTEST-SUMMARY suite=probe checks=5 failures=0\n"
    expect("valid terminal receipt clears", validate_receipt(Result(0, good), spec) is None)
    expect("missing receipt fails", validate_receipt(Result(0, "PASS\n"), spec) is not None)
    expect("duplicate receipt fails", validate_receipt(Result(0, good + good), spec) is not None)
    expect("non-terminal receipt fails", validate_receipt(Result(0, good + "tail\n"), spec) is not None)
    expect("wrong suite id fails", validate_receipt(Result(0, good.replace("probe", "other")), spec) is not None)
    expect("below-floor count fails", validate_receipt(Result(0, good.replace("checks=5", "checks=4")), spec) is not None)
    expect("reported failure fails", validate_receipt(Result(0, good.replace("failures=0", "failures=1")), spec) is not None)
    expect("nonzero process with green receipt fails", validate_receipt(Result(1, good), spec) is not None)
    git_exact = expected_selftest_checks("git_grep_engine_guard")
    git_spec = selftest_receipt("git_grep_engine_guard", SUITE_FLOORS["git_grep_engine_guard"])
    git_good = ("SELFTEST-SUMMARY suite=git_grep_engine_guard "
                f"checks={git_exact} failures=0\n")
    expect(
        "execution-derived Git count clears at the exact environment cardinality",
        validate_receipt(Result(0, git_good), git_spec) is None,
    )
    expect(
        "deleting one Git check fails even while the floor still clears",
        validate_receipt(
            Result(0, git_good.replace(f"checks={git_exact}",
                                       f"checks={git_exact - 1}")),
            git_spec,
        ) is not None,
    )
    expect("workflow baseline matches exact contract", workflow_error(EXPECTED_WORKFLOW) is None)
    expect(
        "ordinary full-gate checkout must retain the fixed decision-corpus base",
        workflow_error(EXPECTED_WORKFLOW.replace("          fetch-depth: 0\n", "", 1))
        is not None,
    )
    expect(
        "the decision writer matches its independently reviewed source digest",
        decision_writer_source_error() == "",
    )
    expect(
        "changing the decision writer invalidates its source binding",
        decision_writer_source_error(
            DECISION_WRITER.read_bytes() + b"\n# planted source drift\n") != "",
    )
    retained_probe = _json_without_duplicate_keys(RETAINED_DECISION_COMMANDS)
    expect(
        "the retained decision manifest matches the closed command inventory",
        retained_decision_commands_error(retained_probe) == "",
    )
    expect(
        "a retained decision command cannot disappear self-consistently",
        retained_decision_commands_error(dict(
            retained_probe, commands=retained_probe["commands"][:-1])) != "",
    )
    decision_writer_spec = importlib.util.spec_from_file_location(
        "_ci_gate_topology_probe", DECISION_WRITER)
    decision_writer = importlib.util.module_from_spec(decision_writer_spec)
    decision_writer_spec.loader.exec_module(decision_writer)
    topology_calls = []

    def base_only_runner(argv, **_kwargs):
        topology_calls.append(tuple(argv))
        return subprocess.CompletedProcess(argv, 0, "", "")

    original_decision_runner = decision_writer.subprocess.run
    decision_writer.subprocess.run = base_only_runner
    try:
        decision_writer.base_and_worktree_fixture_commands()
    finally:
        decision_writer.subprocess.run = original_decision_runner
    expect(
        "decision corpus derivation reads the fixed base but never branch HEAD history",
        len(topology_calls) == len(decision_writer.SOURCES)
        and all(call[-2] == "show"
                and call[-1].startswith(decision_writer.BASE + ":")
                for call in topology_calls),
    )
    expect(
        "mutation workflow baseline matches exact contract",
        workflow_error(EXPECTED_WORKFLOW, EXPECTED_MUTATION_WORKFLOW) is None,
    )
    expect(
        "mutation workflow rejects a merge-ref checkout",
        workflow_error(
            EXPECTED_WORKFLOW,
            EXPECTED_MUTATION_WORKFLOW.replace(
                "          ref: ${{ github.event.pull_request.head.sha "
                "|| github.sha }}\n", "", 1),
        ) is not None,
    )
    # The sweep is the only check that can tell a truthful receipt from a self-consistent
    # forgery, so it must reach every head. A `paths:` filter would leave no entry at all for
    # a head it skips, and a job class with no entry cannot be told from a workflow that
    # failed to run. Coverage is therefore unconditional and only the WORK is conditional:
    # these pin that the verdict is always produced, by one arm or the other.
    expect(
        "mutation workflow carries no paths filter that would silence a head",
        "paths:" not in EXPECTED_MUTATION_WORKFLOW,
    )
    expect(
        "mutation aggregate depends on the scope decision and the shards",
        workflow_error(
            EXPECTED_WORKFLOW,
            EXPECTED_MUTATION_WORKFLOW.replace(
                "    needs: [scope, mutations]\n", "    needs: mutations\n", 1),
        ) is not None,
    )
    expect(
        "a swept head whose shards did not all succeed is refused",
        workflow_error(
            EXPECTED_WORKFLOW,
            EXPECTED_MUTATION_WORKFLOW.replace(
                "        if: needs.scope.outputs.resweep == 'true' "
                "&& needs.mutations.result != 'success'\n", "", 1),
        ) is not None,
    )
    expect(
        "a head that skips the sweep must still assert it inherits its base's proof",
        workflow_error(
            EXPECTED_WORKFLOW,
            EXPECTED_MUTATION_WORKFLOW.replace(
                "      - name: assert this head inherits its base's proof\n", "", 1),
        ) is not None,
    )
    expect(
        "mutation workflow binds its head on every event it accepts",
        workflow_error(
            EXPECTED_WORKFLOW,
            EXPECTED_MUTATION_WORKFLOW.replace("|| github.sha ", "", 1),
        ) is not None,
    )
    expect(
        "mutation aggregator must run even when a shard fails",
        workflow_error(
            EXPECTED_WORKFLOW,
            EXPECTED_MUTATION_WORKFLOW.replace("    if: always()\n", "", 1),
        ) is not None,
    )
    expect(
        "workflow source-bound bootstrap removal fails",
        workflow_error(EXPECTED_WORKFLOW.replace(
            "          python3 hooks/harness_check.py --ci\n", "", 1)) is not None,
    )
    expect("workflow gate command mutation fails", workflow_error(EXPECTED_WORKFLOW.replace(
        "python3 tools/ci-gate.py", "python3 hooks/harness_check.py --ci", 1
    )) is not None)
    expect(
        "workflow source-bound bootstrap must precede the complete gate",
        workflow_error(EXPECTED_WORKFLOW.replace(
            "          python3 hooks/harness_check.py --ci\n"
            "          python3 tools/ci-gate.py\n",
            "          python3 tools/ci-gate.py\n"
            "          python3 hooks/harness_check.py --ci\n",
            1)) is not None,
    )
    expect("workflow unknown feature fails", workflow_error(EXPECTED_WORKFLOW + "permissions: {}\n") is not None)
    expect(
        "workflow permission widening fails",
        workflow_error(
            EXPECTED_WORKFLOW.replace("permissions:\n  contents: read", "permissions: write-all", 1)
        ) is not None,
    )
    expect(
        "workflow credential persistence fails",
        workflow_error(
            EXPECTED_WORKFLOW.replace("persist-credentials: false", "persist-credentials: true", 1)
        ) is not None,
    )

    expect(
        "gate floors agree with harness_check's imported registry",
        floor_registry_error() == "",
    )
    expect(
        "the executed harness matches its reviewed source digest",
        harness_source_error() == "",
    )
    expect(
        "changing the executed harness invalidates its source digest",
        harness_source_error(
            source_bytes=HARNESS_SOURCE.read_bytes() + b"# planted mutation\n") != "",
    )
    source_registry = _json_without_duplicate_keys(SUITE_SOURCE_GOLDEN)
    without_harness = dict(source_registry)
    without_harness["suites"] = {
        name: value for name, value in source_registry["suites"].items()
        if name != "harness_check"
    }
    expect(
        "removing the harness source digest is not permission to skip the binding",
        harness_source_error(golden_data=without_harness) != "",
    )
    expect(
        "the mutation generator matches its reviewed source digest",
        mutation_generator_source_error() == "",
    )
    expect(
        "editing the mutation generator invalidates its source digest",
        mutation_generator_source_error(
            source_bytes=(ROOT / "tools/write-mutation-receipt.py").read_bytes()
            + b"# planted mutation\n") != "",
    )
    without_generator = dict(source_registry)
    without_generator["suites"] = {
        name: value for name, value in source_registry["suites"].items()
        if name != "write-mutation-receipt"
    }
    expect(
        "removing the generator source digest is not permission to skip the binding",
        mutation_generator_source_error(golden_data=without_generator) != "",
    )
    expect("hook timeout and internal budget contract matches", hook_budget_error() == "")
    def retime_bash_hook(data: dict, seconds: int) -> int:
        """Set the Bash guard hook's timeout by identity, not by list position.

        Indexing PreToolUse[0] assumed the Bash matcher comes first: reordering
        settings.json so Agent|Task leads mutated the spawn guard instead, the contract
        saw no change, and this check went red on an edit that changed nothing about the
        hook it names.
        """
        touched = 0
        for entry in data.get("hooks", {}).get("PreToolUse", []):
            for hook in entry.get("hooks", []):
                if "bash_command_guard.py" in hook.get("command", ""):
                    hook["timeout"] = seconds
                    touched += 1
        return touched

    settings_fixture = json.loads((ROOT / "settings.json").read_text(encoding="utf-8"))
    settings_touched = retime_bash_hook(settings_fixture, 4)
    expect(
        "hook budget contract rejects a Claude timeout mutation",
        settings_touched == 1 and hook_budget_error(settings_data=settings_fixture) != "",
    )
    codex_fixture = json.loads((ROOT / "hooks/hooks.json").read_text(encoding="utf-8"))
    codex_touched = retime_bash_hook(codex_fixture, 4)
    expect(
        "hook budget contract rejects a Codex timeout mutation",
        codex_touched == 1 and hook_budget_error(codex_data=codex_fixture) != "",
    )
    reordered = json.loads((ROOT / "settings.json").read_text(encoding="utf-8"))
    reordered["hooks"]["PreToolUse"].reverse()
    expect(
        "hook budget contract is indifferent to PreToolUse ordering",
        hook_budget_error(settings_data=reordered) == ""
        and retime_bash_hook(reordered, 4) == 1
        and hook_budget_error(settings_data=reordered) != "",
    )
    timed_out = run_command([sys.executable, "-c",
                             "import time; time.sleep(0.3)"])
    expect("a child that runs to completion is not reported as a timeout",
           timed_out.returncode == 0 and "exceeded" not in timed_out.stderr)
    original_child_timeout = CHILD_TIMEOUT_SECONDS
    globals()["CHILD_TIMEOUT_SECONDS"] = 0.2
    try:
        slow = run_command([sys.executable, "-c", "import time; time.sleep(3)"])
    finally:
        globals()["CHILD_TIMEOUT_SECONDS"] = original_child_timeout
    expect(
        "a child that exceeds its timeout becomes a receipt failure, not a traceback",
        slow.returncode != 0 and "exceeded" in slow.stderr,
    )
    expect("recorded guard decisions match the guards", decision_golden_error() == "")
    decision_contract = {
        "schema_version": 1,
        "generated_by": "probe-writer",
        "note": "probe-note",
        "corpus": "probe-corpus",
        "top_level_keys": (
            "schema_version", "generated_by", "note", "corpus", "exclusions",
            "decisions",
        ),
        "exclusion_keys": (
            "max_command_chars", "oversized", "computed_at_import",
        ),
    }
    decision_snapshot = {
        "commands": ("git status --short",),
        "exclusions": {
            "max_command_chars": 2000,
            "oversized": [],
            "computed_at_import": [],
        },
    }
    decision_probe = {
        "schema_version": 1,
        "generated_by": "probe-writer",
        "note": "probe-note",
        "corpus": "probe-corpus",
        "exclusions": decision_snapshot["exclusions"],
        "decisions": {"git status --short": "allow"},
    }
    decision_args = {
        "snapshot": decision_snapshot,
        "contract": decision_contract,
        "decide": lambda _command: ("allow", ""),
    }
    expect(
        "an exact synthetic decision golden clears",
        decision_golden_error(golden_data=decision_probe, **decision_args) == "",
    )
    expect(
        "a matching nonempty decision corpus below its independent floor fails",
        decision_golden_error(
            golden_data=decision_probe, minimum_commands=2, **decision_args) != "",
    )
    expect(
        "an empty decision golden is a failure, not a clean verdict",
        decision_golden_error(
            golden_data=dict(decision_probe, decisions={}), **decision_args) != "",
    )
    expect(
        "a reversed verdict in the golden is reported with both sides",
        "deny -> allow" in decision_golden_error(
            golden_data=dict(
                decision_probe, decisions={"git status --short": "deny"}),
            **decision_args),
    )
    for field in decision_contract["top_level_keys"]:
        without = {key: value for key, value in decision_probe.items() if key != field}
        expect(
            f"decision golden rejects a missing {field} field",
            decision_golden_error(golden_data=without, **decision_args) != "",
        )
    expect(
        "decision golden rejects an unexpected top-level field",
        decision_golden_error(
            golden_data=dict(decision_probe, invented=True), **decision_args) != "",
    )
    expect(
        "decision golden rejects a command missing from the recorded corpus",
        decision_golden_error(
            golden_data=dict(decision_probe, decisions={}), **decision_args) != "",
    )
    expect(
        "decision golden rejects a command foreign to the generated corpus",
        decision_golden_error(
            golden_data=dict(decision_probe, decisions={
                "git status --short": "allow", "git invented": "allow"}),
            **decision_args) != "",
    )
    expect(
        "decision golden rejects a non-outcome verdict",
        decision_golden_error(
            golden_data=dict(
                decision_probe, decisions={"git status --short": "maybe"}),
            **decision_args) != "",
    )
    expect(
        "decision golden rejects altered exclusion metadata",
        decision_golden_error(
            golden_data=dict(decision_probe, exclusions=dict(
                decision_snapshot["exclusions"], max_command_chars=1999)),
            **decision_args) != "",
    )
    with tempfile.TemporaryDirectory(prefix="z-harness-json-keys-") as raw:
        duplicate_json = Path(raw) / "duplicate.json"
        duplicate_json.write_text('{"decisions": {}, "decisions": {}}\n',
                                  encoding="utf-8")
        try:
            _json_without_duplicate_keys(duplicate_json)
            duplicate_rejected = False
        except ValueError:
            duplicate_rejected = True
        expect("duplicate JSON object keys are rejected", duplicate_rejected)
    expect(
        "hook budget contract rejects a sub-second margin",
        hook_budget_error(budget=4.01) != "",
    )

    set_mutation = {
        "version": 1, "kind": "set-element", "module": "guard-a.py",
        "name": "TOKENS", "collection_kind": "set", "element": "x", "id": "set-id",
    }
    site_mutation = {
        "version": 1, "kind": "site", "module": "guard-b.py", "label": "site probe",
        "anchor_sha256": "a" * 64, "replacement_sha256": "b" * 64,
        "allowed_statuses": [], "id": "site-id",
    }
    addition_mutation = {
        "version": 1, "kind": "set-addition", "module": "guard-a.py",
        "name": "TOKENS", "collection_kind": "set", "element": "z",
        "label": "probe addition", "allowed_statuses": [], "id": "add-id",
    }
    mutation_plan_probe = [set_mutation, site_mutation, addition_mutation]
    mutation_contract = {
        "schema_version": 3,
        "generated_by": "tools/write-mutation-receipt.py --aggregate",
        "note": "probe-note", "generator_sha256": "c" * 64,
        "plan_sha256": "d" * 64,
        "keys": (
            "schema_version", "generated_by", "note", "generator_sha256",
            "source_digests", "plan_sha256", "baseline", "sweep_exclusions",
            "results", "survivors", "unasserted_kills", "caught", "total",
        ),
        "guards": ("guard-a.py", "guard-b.py", "guard-c.py"),
        "kill_reasons": frozenset({
            "suite-failure", "exact-check-count", "survived", "invalid-receipt",
            "timeout",
        }),
        "unasserted_reason": "exact-check-count",
        "unasserted_ceiling": 1,
    }
    mutation_sources = {name: str(index) * 64 for index, name in enumerate(
        mutation_contract["guards"], 1)}
    set_result = dict(set_mutation, outcome="survived", reason="survived")
    site_result = {key: value for key, value in site_mutation.items()
                   if key != "allowed_statuses"}
    site_result["outcome"] = "caught"
    site_result["reason"] = "suite-failure"
    addition_result = {key: value for key, value in addition_mutation.items()
                       if key != "allowed_statuses"}
    addition_result["outcome"] = "caught"
    addition_result["reason"] = "suite-failure"
    mutation_probe = {
        "schema_version": 3,
        "generated_by": mutation_contract["generated_by"],
        "note": "probe-note",
        "generator_sha256": "c" * 64,
        "source_digests": mutation_sources,
        "plan_sha256": "d" * 64,
        "baseline": {name: "passed" for name in mutation_contract["guards"]},
        "sweep_exclusions": {"guard-a.py::FIXTURES": "fixture corpus"},
        "results": {"set-id": set_result, "site-id": site_result,
                    "add-id": addition_result},
        "survivors": ["set-id"], "unasserted_kills": [], "caught": 2, "total": 3,
    }
    mutation_args = {
        "plan": mutation_plan_probe,
        "exclusions": mutation_probe["sweep_exclusions"],
        "contract": mutation_contract,
        "current_sources": mutation_sources,
        "ceiling": 1,
        "unasserted_ceiling": 1,
        "unasserted_identities": set(),
        "policy": {
            "collections": {("guard-a.py", "TOKENS"): 1},
            "sites": {("guard-b.py", "site probe")},
            "site_digest": mutation_site_policy_digest([site_mutation]),
            "exclusions": mutation_probe["sweep_exclusions"],
            "additions": {
                ("guard-a.py", "TOKENS", "set", "z", "probe addition", ()),
            },
            "floor": 3,
        },
    }
    writer_spec = importlib.util.spec_from_file_location(
        "_ci_gate_mutation_writer_selftest",
        ROOT / "tools/write-mutation-receipt.py")
    assert writer_spec is not None and writer_spec.loader is not None
    writer = importlib.util.module_from_spec(writer_spec)
    writer_spec.loader.exec_module(writer)
    original_writer_which = writer.shutil.which
    writer.shutil.which = (
        lambda name: None if name == "zsh" else original_writer_which(name))
    try:
        try:
            writer.baseline_results(ROOT)
            missing_zsh_rejected = False
        except ValueError as exc:
            missing_zsh_rejected = "zsh is required" in str(exc)
    finally:
        writer.shutil.which = original_writer_which
    expect(
        "mutation baselines reject a host that skipped the zsh runtime probes",
        missing_zsh_rejected,
    )
    raw_baseline = {
        relative: {
            "status": "completed", "returncode": 0,
            "checks": 10, "failures": 0,
        }
        for relative in writer.GUARDS
    }
    raw_descriptor = {
        "id": "raw-probe", "kind": "set-element", "module": writer.GREP,
        "allowed_statuses": ["invalid-receipt"],
    }
    raw_survivor = {
        "owner": raw_baseline[writer.GREP],
        "merged": raw_baseline[writer.BASH],
        "outcome": "survived", "reason": "survived",
    }
    expect(
        "fragment aggregation independently recomputes a truthful raw outcome",
        writer.recompute_raw_result(
            raw_survivor, raw_descriptor, raw_baseline) == ("survived", "survived"),
    )
    try:
        writer.recompute_raw_result(
            dict(raw_survivor, outcome="caught", reason="suite-failure"),
            raw_descriptor, raw_baseline)
        forged_raw_rejected = False
    except ValueError:
        forged_raw_rejected = True
    expect(
        "fragment aggregation rejects a forged self-reported outcome",
        forged_raw_rejected,
    )
    malformed_owner = dict(raw_baseline[writer.GREP], invented=True)
    try:
        writer.recompute_raw_result(
            dict(raw_survivor, owner=malformed_owner), raw_descriptor, raw_baseline)
        malformed_raw_rejected = False
    except ValueError:
        malformed_raw_rejected = True
    expect(
        "fragment aggregation rejects an extra raw suite field",
        malformed_raw_rejected,
    )
    invalid_receipt = {
        "status": "invalid-receipt", "returncode": 1,
        "receipt_count": 0, "stderr_tail": "mutated receipt",
    }
    expect(
        "a declared set mutation may be killed by an invalid terminal receipt",
        writer.recompute_raw_result(
            {
                "owner": invalid_receipt, "merged": None,
                "outcome": "caught", "reason": "invalid-receipt",
            },
            raw_descriptor, raw_baseline,
        ) == ("caught", "invalid-receipt"),
    )
    original_apply_mutation = writer.apply_mutation
    original_run_suite = writer.run_suite
    with tempfile.TemporaryDirectory(prefix="z-harness-merged-kill-") as raw:
        target = Path(raw) / "guard.py"
        target.write_text("pristine\n", encoding="utf-8")
        writer.apply_mutation = lambda _tree, _descriptor: (target, "pristine\n")
        writer.run_suite = lambda _tree, relative: (
            raw_baseline[writer.GREP] if relative == writer.GREP else invalid_receipt)
        try:
            try:
                propagated_kill = writer.execute_mutation(
                    Path(raw), raw_descriptor, raw_baseline)
            except ValueError:
                propagated_kill = None
        finally:
            writer.apply_mutation = original_apply_mutation
            writer.run_suite = original_run_suite
        expect(
            "declared kill modes propagate to the merged public-envelope suite",
            propagated_kill is not None
            and propagated_kill["outcome"] == "caught"
            and propagated_kill["reason"] == "invalid-receipt"
            and propagated_kill["merged"] == invalid_receipt,
        )
    expect(
        "aggregation preserves declared kill modes for the merged suite",
        writer.recompute_raw_result(
            {
                "owner": raw_baseline[writer.GREP],
                "merged": invalid_receipt,
                "outcome": "caught", "reason": "invalid-receipt",
            },
            raw_descriptor, raw_baseline,
        ) == ("caught", "invalid-receipt"),
    )
    context_fragment = {"head_sha": "head-a", "baseline": raw_baseline}
    expect(
        "aggregate context accepts the exact head and fresh baseline",
        writer.aggregate_context_error(
            context_fragment, "head-a", raw_baseline) == "",
    )
    expect(
        "aggregate context rejects a foreign fragment head",
        writer.aggregate_context_error(
            context_fragment, "head-b", raw_baseline) != "",
    )
    changed_baseline = dict(raw_baseline)
    changed_baseline[writer.GREP] = dict(
        raw_baseline[writer.GREP], checks=9)
    expect(
        "aggregate context rejects a shard-only baseline",
        writer.aggregate_context_error(
            context_fragment, "head-a", changed_baseline) != "",
    )
    assignment_plan = [{"id": name} for name in ("a", "b", "c")]
    assignment_fragment = {
        "shard": {"index": 0, "count": 2},
        "results": {"a": {}, "c": {}},
    }
    expect(
        "a deterministic shard assignment clears",
        writer.shard_assignment_error(
            assignment_fragment, assignment_plan, 2) == "",
    )
    expect(
        "a same-union fragment with the wrong shard assignment fails",
        writer.shard_assignment_error(
            dict(assignment_fragment, results={"a": {}}),
            assignment_plan, 2) != "",
    )
    with tempfile.TemporaryDirectory(prefix="z-harness-fragment-json-") as raw:
        duplicate_fragment = Path(raw) / "fragment.json"
        duplicate_fragment.write_text(
            '{"results": {}, "results": {}}\n', encoding="utf-8")
        try:
            writer.load_json(duplicate_fragment)
            duplicate_fragment_rejected = False
        except ValueError:
            duplicate_fragment_rejected = True
        expect(
            "fragment JSON rejects duplicate object keys",
            duplicate_fragment_rejected,
        )
    # The receipt is compared across hosts, and whether an assertion fires can differ by
    # environment, so the comparison runs on a projection that drops the observed reason and
    # its tally. That projection must stay blind to exactly those two fields and to nothing
    # else, or a real regression rides through the same hole.
    import copy as _copy
    stable_probe = {
        "schema_version": writer.SCHEMA_VERSION, "generated_by": "x", "note": "n",
        "generator_sha256": "c" * 64, "source_digests": {}, "plan_sha256": "d" * 64,
        "baseline": {}, "sweep_exclusions": {},
        "results": {
            "a": {"outcome": "caught", "reason": "suite-failure", "kind": "set-element",
                  "module": "guard-a.py", "name": "T", "element": "x"},
            "b": {"outcome": "survived", "reason": "survived", "kind": "set-element",
                  "module": "guard-a.py", "name": "T", "element": "y"}},
        "survivors": ["b"], "unasserted_kills": [], "caught": 1, "total": 2,
    }
    # The receipt and its summary are compared byte for byte against a CI re-measurement, so
    # neither may depend on a value only one host can observe. These pin the RULE rather than
    # the two fields that broke it: every declared host-observed field must be invisible to
    # both comparisons, and nothing else may be.
    expect(
        "the host-observed field sets are declared and non-empty",
        bool(writer.HOST_OBSERVED_RESULT_FIELDS) and bool(writer.HOST_OBSERVED_RECEIPT_KEYS),
    )
    observed_invisible = True
    for _key in writer.HOST_OBSERVED_RECEIPT_KEYS:
        _probe = _copy.deepcopy(stable_probe)
        _probe[_key] = ["a"] if _probe.get(_key) == [] else []
        observed_invisible &= (
            writer.platform_stable(stable_probe) == writer.platform_stable(_probe)
            and writer.summary_text(stable_probe) == writer.summary_text(_probe))
    for _field in writer.HOST_OBSERVED_RESULT_FIELDS:
        _probe = _copy.deepcopy(stable_probe)
        _probe["results"]["a"][_field] = "exact-check-count"
        observed_invisible &= (
            writer.platform_stable(stable_probe) == writer.platform_stable(_probe)
            and writer.summary_text(stable_probe) == writer.summary_text(_probe))
    expect(
        "every declared host-observed field is invisible to both cross-host comparisons",
        observed_invisible,
    )
    _under_ceiling = _copy.deepcopy(stable_probe)
    _under_ceiling["results"]["a"]["reason"] = writer.UNASSERTED_KILL_REASON
    _under_ceiling["unasserted_kills"] = ["a"]
    _over_ceiling = _copy.deepcopy(_under_ceiling)
    _over_ceiling["results"]["b"]["outcome"] = "caught"
    _over_ceiling["results"]["b"]["reason"] = writer.UNASSERTED_KILL_REASON
    _over_ceiling["survivors"] = []
    _over_ceiling["unasserted_kills"] = ["a", "b"]
    _over_ceiling["caught"] = 2
    expect(
        "fresh host-observed kills are derived and bounded before projection",
        writer.fresh_observation_error(_under_ceiling) == ""
        and writer.fresh_observation_error(_over_ceiling) != "",
    )
    _saved_receipt = writer.RECEIPT
    _saved_summary = writer.SUMMARY
    _saved_normalized_receipt = writer.normalized_receipt
    with tempfile.TemporaryDirectory(prefix="z-harness-fresh-observation-") as raw:
        writer.RECEIPT = Path(raw) / "receipt.json"
        writer.SUMMARY = Path(raw) / "summary.md"
        writer.RECEIPT.write_text(
            json.dumps(_over_ceiling, indent=1) + "\n", encoding="utf-8")
        writer.SUMMARY.write_text(
            writer.summary_text(_over_ceiling), encoding="utf-8")
        writer.normalized_receipt = lambda _fragments: _over_ceiling
        try:
            _fresh_aggregate_rc = writer.aggregate([], False)
        finally:
            writer.RECEIPT = _saved_receipt
            writer.SUMMARY = _saved_summary
            writer.normalized_receipt = _saved_normalized_receipt
    expect(
        "fresh aggregation enforces the kill ceiling before a stable projection can pass",
        _fresh_aggregate_rc == 2,
    )
    # The dual: the projection must not quietly stop comparing something real. Any field it
    # drops beyond the declared set would be a regression nobody could see.
    _projected = writer.platform_stable(stable_probe)
    expect(
        "the projection drops the declared host-observed keys and nothing else",
        set(stable_probe) - set(_projected) == set(writer.HOST_OBSERVED_RECEIPT_KEYS)
        and all(set(stable_probe["results"][k]) - set(_projected["results"][k])
                == set(writer.HOST_OBSERVED_RESULT_FIELDS) for k in _projected["results"]),
    )
    _real_changes = []
    _flip = _copy.deepcopy(stable_probe); _flip["results"]["a"]["outcome"] = "survived"
    _real_changes.append(("a flipped outcome", _flip))
    _drop = _copy.deepcopy(stable_probe); _drop["results"].pop("a")
    _real_changes.append(("a dropped result", _drop))
    _surv = _copy.deepcopy(stable_probe); _surv["survivors"] = []
    _real_changes.append(("a shortened survivor list", _surv))
    _elem = _copy.deepcopy(stable_probe); _elem["results"]["a"]["element"] = "z"
    _real_changes.append(("a changed mutation element", _elem))
    for _label, _changed in _real_changes:
        expect(
            f"the cross-host comparison still sees {_label}",
            writer.platform_stable(stable_probe) != writer.platform_stable(_changed),
        )
    # The sweep-scope decision gates an hour of CI and the assertion that replaces it, so
    # both arms need a red case. A runner stands in for git so the cases are exact rather
    # than dependent on this checkout's history.
    def _diff_runner(names):
        def run(argv, **kwargs):
            class Done:
                returncode = 0
                stdout = "".join(f"{n}\n" for n in names)
                stderr = ""
            return Done()
        return run

    def _broken_diff(argv, **kwargs):
        class Done:
            returncode = 128
            stdout = ""
            stderr = "fatal: bad revision"
        return Done()

    expect(
        "a head touching nothing the sweep observes needs no resweep",
        writer.resweep_needed("base", runner=_diff_runner([])) is False,
    )
    for _observed in ("hooks/guards/git_grep_engine_guard.py",
                      "tools/write-mutation-receipt.py",
                      "contracts/goldens/mutation-receipt.json",
                      "hooks/bash_command_guard.py",
                      ".github/workflows/mutation-proof.yml"):
        expect(
            f"a head touching {_observed} needs a resweep",
            writer.resweep_needed("base", runner=_diff_runner([_observed])) is True,
        )
    expect(
        "an unreadable base is an error, never a silent no-resweep",
        _raises(lambda: writer.resweep_needed("base", runner=_broken_diff), ValueError),
    )
    expect(
        "inheritance is refused when an observed input changed",
        writer.inherited_proof_error(
            "base", runner=_diff_runner(["hooks/guards/zsh_rev_modifier_guard.py"])) != "",
    )
    expect(
        "inheritance is granted only when nothing observed changed",
        writer.inherited_proof_error("base", runner=_diff_runner([])) == "",
    )
    expect(
        "inheritance is refused when the base cannot be read",
        _raises(lambda: writer.inherited_proof_error("base", runner=_broken_diff),
                ValueError),
    )
    expect("recorded mutation evidence matches the guards", mutation_receipt_error() == "")
    expect(
        "an exact synthetic mutation receipt clears",
        mutation_receipt_error(mutation_probe, **mutation_args) == "",
    )
    # A kill scored only by a moved check count inflates `caught` without any assertion
    # having failed. The receipt records those separately so the distinction survives into
    # the artifact; these probe that the tally is derived, bounded, and cannot be forged.
    unasserted_site = dict(site_result, reason="exact-check-count")
    unasserted_probe = dict(
        mutation_probe,
        results={"set-id": set_result, "site-id": unasserted_site,
                 "add-id": addition_result},
        unasserted_kills=["site-id"],
    )
    expect(
        "a kill scored only by a moved check count is recorded as unasserted",
        mutation_receipt_error(
            unasserted_probe,
            **dict(mutation_args,
                   unasserted_identities={("guard-b.py", None, None)})) == "",
    )
    expect(
        "an unasserted kill outside the reviewed set fails",
        mutation_receipt_error(unasserted_probe, **mutation_args) != "",
    )
    expect(
        "an unasserted kill omitted from the tally fails",
        mutation_receipt_error(
            dict(unasserted_probe, unasserted_kills=[]), **mutation_args) != "",
    )
    expect(
        "an unasserted tally naming a mutation that asserted fails",
        mutation_receipt_error(
            dict(mutation_probe, unasserted_kills=["site-id"]), **mutation_args) != "",
    )
    expect(
        "unasserted kills above the reviewed ceiling fail",
        mutation_receipt_error(
            unasserted_probe, **dict(mutation_args, unasserted_ceiling=0)) != "",
    )
    expect(
        "a result carrying a reason outside the generator vocabulary fails",
        mutation_receipt_error(
            dict(mutation_probe,
                 results={"set-id": set_result, "add-id": addition_result,
                          "site-id": dict(site_result, reason="looks-fine")}),
            **mutation_args) != "",
    )
    expect(
        "a caught result claiming the survived reason fails",
        mutation_receipt_error(
            dict(mutation_probe,
                 results={"set-id": set_result, "add-id": addition_result,
                          "site-id": dict(site_result, reason="survived")}),
            **mutation_args) != "",
    )
    expect(
        "a survived result claiming a kill reason fails",
        mutation_receipt_error(
            dict(mutation_probe,
                 results={"set-id": dict(set_result, reason="suite-failure"),
                          "add-id": addition_result, "site-id": site_result}),
            **mutation_args) != "",
    )
    expect(
        "a crash status the plan never allowed fails",
        mutation_receipt_error(
            dict(mutation_probe,
                 results={"set-id": set_result, "add-id": addition_result,
                          "site-id": dict(site_result, reason="timeout")}),
            **mutation_args) != "",
    )
    expect(
        "a result missing its reason entirely fails",
        mutation_receipt_error(
            dict(mutation_probe,
                 results={"set-id": set_result, "add-id": addition_result,
                          "site-id": {k: v for k, v in site_result.items()
                                      if k != "reason"}}),
            **mutation_args) != "",
    )
    # result_kill can return any status the plan tolerates, so a new allowed_statuses entry
    # that nobody added to the vocabulary would make every result carrying it unvalidatable.
    planned_statuses = set()
    for _descriptor in writer.mutation_plan()[0]:
        planned_statuses.update(_descriptor.get("allowed_statuses", ()) or ())
    expect(
        "every status the plan tolerates is a reason the gate can validate",
        planned_statuses <= set(writer.KILL_REASONS),
    )
    expect(
        "the unasserted reason is one the generator can actually emit",
        writer.UNASSERTED_KILL_REASON in writer.KILL_REASONS,
    )
    shrunk_contract = dict(mutation_contract, plan_sha256="e" * 64)
    shrunk_probe = dict(
        mutation_probe,
        plan_sha256="e" * 64,
        results={"set-id": set_result},
        survivors=["set-id"], caught=0, total=1,
    )
    expect(
        "a self-consistently regenerated but shrunken plan remains a failure",
        mutation_receipt_error(
            shrunk_probe,
            **dict(mutation_args, plan=[set_mutation], contract=shrunk_contract),
        ) != "",
    )
    expect(
        "a foreign site identity fails the independent closed inventory",
        mutation_policy_error(
            [set_mutation, dict(site_mutation, label="foreign")],
            mutation_probe["sweep_exclusions"], mutation_args["policy"],
        ) != "",
    )
    expect(
        "a duplicate site identity fails the independent closed inventory",
        mutation_policy_error(
            [set_mutation, site_mutation, dict(site_mutation, id="duplicate-site")],
            mutation_probe["sweep_exclusions"], mutation_args["policy"],
        ) != "",
    )
    expect(
        "changing a site anchor fails the independent semantic digest",
        mutation_policy_error(
            [set_mutation, dict(
                site_mutation, anchor_sha256="c" * 64, id="changed-site")],
            mutation_probe["sweep_exclusions"], mutation_args["policy"],
        ) != "",
    )
    expect(
        "changing a declared addition's allowed kill modes fails closed",
        mutation_policy_error(
            [set_mutation, site_mutation,
             dict(addition_mutation, allowed_statuses=["timeout"])],
            mutation_probe["sweep_exclusions"], mutation_args["policy"],
        ) != "",
    )
    duplicate_target = dict(
        site_mutation, label="site twin", id="duplicate-target")
    duplicate_target_policy = dict(
        mutation_args["policy"],
        sites={("guard-b.py", "site probe"), ("guard-b.py", "site twin")},
        site_digest=mutation_site_policy_digest(
            [site_mutation, duplicate_target]),
        floor=3,
    )
    expect(
        "two labels cannot execute the same semantic site mutation",
        mutation_policy_error(
            [set_mutation, site_mutation, duplicate_target],
            mutation_probe["sweep_exclusions"], duplicate_target_policy,
        ) != "",
    )
    for field in mutation_contract["keys"]:
        expect(
            f"mutation receipt rejects a missing {field} field",
            mutation_receipt_error(
                {key: value for key, value in mutation_probe.items() if key != field},
                **mutation_args) != "",
        )
    expect(
        "mutation receipt rejects an unexpected top-level field",
        mutation_receipt_error(dict(mutation_probe, invented=True), **mutation_args) != "",
    )
    expect(
        "mutation receipt rejects a missing planned result",
        mutation_receipt_error(
            dict(mutation_probe, results={"site-id": site_result}), **mutation_args) != "",
    )
    expect(
        "mutation receipt rejects a foreign result",
        mutation_receipt_error(
            dict(mutation_probe, results=dict(mutation_probe["results"], foreign={})),
            **mutation_args) != "",
    )
    expect(
        "mutation receipt rejects an extra nested evidence field",
        mutation_receipt_error(
            dict(mutation_probe, results=dict(
                mutation_probe["results"],
                **{"set-id": dict(set_result, failures=999)})),
            **mutation_args) != "",
    )
    expect(
        "mutation receipt recomputes survivors instead of trusting the list",
        mutation_receipt_error(dict(mutation_probe, survivors=[]), **mutation_args) != "",
    )
    expect(
        "mutation receipt recomputes caught and total",
        mutation_receipt_error(
            dict(mutation_probe, caught=999, total=999), **mutation_args) != "",
    )
    site_survived = dict(site_result, outcome="survived", reason="survived")
    caught_set = dict(set_result, outcome="caught", reason="suite-failure")
    expect(
        "a surviving site mutation is always a failure",
        mutation_receipt_error(
            dict(mutation_probe,
                 results={"set-id": caught_set, "site-id": site_survived,
                          "add-id": addition_result},
                 survivors=["site-id"], caught=2),
            **mutation_args) != "",
    )
    compensated_addition = dict(
        addition_result, outcome="survived", reason="survived")
    compensated_set = dict(set_result, outcome="caught", reason="suite-failure")
    expect(
        "a declared addition survivor fails even when ordinary debt falls by one",
        mutation_receipt_error(
            dict(
                mutation_probe,
                results={"set-id": compensated_set, "site-id": site_result,
                         "add-id": compensated_addition},
                survivors=["add-id"], caught=2,
            ),
            **mutation_args,
        ) != "",
    )
    expect(
        "survivor debt above the closed ceiling is a failure",
        mutation_receipt_error(mutation_probe, **dict(mutation_args, ceiling=0)) != "",
    )
    recorded_receipt = _json_without_duplicate_keys(MUTATION_RECEIPT)
    expect(
        "the tracked survivor debt exactly fills the reviewed ceiling",
        (len(recorded_receipt["survivors"])
         == MUTATION_SURVIVOR_DEBT_CEILING),
    )
    regressed_receipt = json.loads(json.dumps(recorded_receipt))
    regression_id = next(
        mutation_id for mutation_id, result in regressed_receipt["results"].items()
        if result["kind"] == "set-element" and result["outcome"] == "caught")
    regressed_receipt["results"][regression_id]["outcome"] = "survived"
    regressed_receipt["survivors"] = sorted(
        mutation_id for mutation_id, result in regressed_receipt["results"].items()
        if result["outcome"] == "survived")
    regressed_receipt["caught"] -= 1
    expect(
        "one additional set-element survivor exceeds the production ceiling",
        mutation_receipt_error(regressed_receipt) != "",
    )
    expect(
        "a receipt missing the Bash baseline is not evidence over all guards",
        mutation_receipt_error(
            dict(mutation_probe, baseline={
                "guard-a.py": "passed", "guard-b.py": "passed"}),
            **mutation_args) != "",
    )
    expect(
        "a stale guard digest invalidates the mutation receipt",
        mutation_receipt_error(
            dict(mutation_probe, source_digests={
                **mutation_sources, "guard-a.py": "0" * 64}),
            **mutation_args) != "",
    )
    expect(
        "the canonical mutation summary is derived from the strict receipt",
        mutation_summary_error() == "",
    )
    forged_summary = MUTATION_SUMMARY.read_bytes() + b"\nforged summary bytes\n"
    expect(
        "changing the summary and its outbound copies cannot bypass receipt derivation",
        mutation_summary_error(
            receipt_data=recorded_receipt, summary_bytes=forged_summary) != "",
    )
    handoff_sources = {
        relative: (ROOT / relative).read_text(encoding="utf-8")
        for relative in HANDOFF_DOCTRINE
    }
    expect(
        "every skill's own eval corpus meets its floor",
        eval_corpus_distribution_error() == "",
    )
    expect(
        "a skill whose eval corpus is emptied fails even when the total is restored",
        eval_corpus_distribution_error(
            counts=dict({k: v for k, v in EVAL_SCENARIO_FLOORS.items()},
                        **{"outbound-drafts": 0, "craft-prompt": 6})) != "",
    )
    expect(
        "review handoff doctrine requires append-only exact-head comments",
        review_handoff_policy_error(source_texts=handoff_sources) == "",
    )
    missing_append_only = dict(handoff_sources)
    missing_append_only["skills/outbound-drafts/SKILL.md"] = (
        missing_append_only["skills/outbound-drafts/SKILL.md"].replace(
            "Review handoffs are append-only, one exact head per comment.",
            "Review handoffs summarize the current state.",
            1,
        )
    )
    expect(
        "removing the append-only rule turns the doctrine check red",
        review_handoff_policy_error(source_texts=missing_append_only) != "",
    )
    mutable_comment_rule = dict(handoff_sources)
    mutable_comment_rule["skills/outbound-drafts/SKILL.md"] += (
        "\nOne roll-up comment per PR, edited in place across rounds.\n"
    )
    expect(
        "reintroducing the edit-in-place rule turns the doctrine check red",
        review_handoff_policy_error(source_texts=mutable_comment_rule) != "",
    )
    with tempfile.TemporaryDirectory(prefix="z-harness-handoff-policy-") as raw:
        retired_review_root = Path(raw)
        (retired_review_root / "pr-8").mkdir()
        (retired_review_root / "pr-8/rollup.md").write_text(
            "# mutable handoff\n", encoding="utf-8")
        expect(
            "a tracked mutable handoff artifact turns the doctrine check red",
            review_handoff_policy_error(
                source_texts=handoff_sources,
                review_root=retired_review_root,
            ) != "",
        )
    expect("outbound review text matches the sources it includes", review_include_error() == "")
    with tempfile.TemporaryDirectory(prefix="z-harness-review-") as raw:
        review = Path(raw)
        document = review / "doc.md"
        # Any tracked file with no include markers of its own. README.md cannot serve here:
        # it DOCUMENTS the close marker, so it would terminate the block it is embedded in.
        source_name = "contracts/goldens/digests.json"
        body = (ROOT / source_name).read_text(encoding="utf-8").strip("\n")

        def review_doc(text: str) -> str:
            document.write_text(text, encoding="utf-8")
            return review_include_error(review)

        live = f"{INCLUDE_OPEN}{source_name} -->\n{body}\n{INCLUDE_CLOSE}\n"
        expect(
            "an include block byte-identical to its source clears",
            review_doc(f"# outbound\n\n{live}") == "",
        )
        expect(
            "an included copy that drifted from its source is caught",
            "stale copy" in review_doc(f"# outbound\n\n{live}".replace(body, body + "\nx")),
        )
        expect(
            "extra blank lines inside an include are not byte-identical",
            "stale copy" in review_doc(live.replace(
                f"\n{INCLUDE_CLOSE}", f"\n\n{INCLUDE_CLOSE}")),
        )
        crlf_body = (ROOT / source_name).read_bytes().replace(b"\n", b"\r\n")
        document.write_bytes(
            f"{INCLUDE_OPEN}{source_name} -->\n".encode()
            + crlf_body + f"{INCLUDE_CLOSE}\n".encode())
        expect(
            "CRLF normalization cannot satisfy a byte-identical include",
            "stale copy" in review_include_error(review),
        )
        with tempfile.NamedTemporaryFile(
                dir=ROOT, prefix=".ci-gate-no-final-", suffix=".md",
                delete=False) as temporary_source:
            temporary_source.write(b"one line without newline")
            no_final_path = Path(temporary_source.name)
        try:
            no_final_name = str(no_final_path.relative_to(ROOT))
            expect(
                "a source without a final newline cannot be line-normalized into place",
                "stale copy" in review_doc(
                    f"{INCLUDE_OPEN}{no_final_name} -->\n"
                    f"one line without newline\n{INCLUDE_CLOSE}\n"),
            )
        finally:
            no_final_path.unlink()
        expect(
            "an include cannot read a source outside the repository",
            "outside the repository" in review_doc(
                f"{INCLUDE_OPEN}/etc/passwd -->\nx\n{INCLUDE_CLOSE}\n"),
        )
        expect(
            "an include naming a file that does not exist is caught",
            "does not exist" in review_doc(
                f"{INCLUDE_OPEN}contracts/goldens/absent.md -->\nx\n{INCLUDE_CLOSE}\n"),
        )
        expect(
            "an include with no closing marker is caught",
            "unterminated" in review_doc(f"{INCLUDE_OPEN}{source_name} -->\n{body}\n"),
        )
        # The convention's own README has to document this syntax, and the only way to show
        # it is inside a fence. A scanner blind to fences reads that example as a live
        # include and fails on a file the example never claimed to copy, so the rule's
        # documentation could never satisfy the rule. This pins that it can.
        fenced = ("# outbound\n\n```\n"
                  f"{INCLUDE_OPEN}contracts/goldens/absent.md -->\n"
                  f"...a byte-identical copy of that file...\n{INCLUDE_CLOSE}\n```\n")
        expect(
            "an include shown as a fenced example is not read as a live include",
            review_doc(fenced) == "",
        )
        expect(
            "a live include after a fenced example is still checked",
            "stale copy" in review_doc(fenced + "\n" + live.replace(body, "drifted")),
        )
        # A block whose BODY carries a fence -- a generated table may. Walking back into the
        # body instead of resuming past the close marker toggles fence state on that line
        # and goes blind to every include after it, so the later block must still be seen.
        # The first block is stale either way; only the SECOND one discriminates.
        carries_fence = (f"{INCLUDE_OPEN}{source_name} -->\n"
                         f"drifted\n```\nstill inside the body\n{INCLUDE_CLOSE}\n")
        expect(
            "a fence inside included content does not hide a later include",
            "does not exist" in review_doc(
                carries_fence + "\n"
                + f"{INCLUDE_OPEN}contracts/goldens/absent.md -->\nx\n{INCLUDE_CLOSE}\n"),
        )
        review_doc(f"# outbound\n\n{live}")
        expect(
            "an exact required include inventory clears",
            review_include_error(
                review, required_inventory={"doc.md": (source_name,)}) == "",
        )
        expect(
            "removing every required include is not a clean verdict",
            review_include_error(
                review, required_inventory={
                    "doc.md": (source_name,), "missing.md": (source_name,)}) != "",
        )
        expect(
            "an unregistered live include is rejected by the exact inventory",
            review_include_error(review, required_inventory={}) != "",
        )
        document.unlink()
        expect(
            "a review directory holding no markdown is a failure, not a clean verdict",
            review_include_error(review) != "",
        )
    expect(
        "a missing review directory is a failure, not a clean verdict",
        review_include_error(review) != "",
    )

    env_line = gated_environment()
    expect(
        "the gate names both interpreters its verdicts were measured against",
        env_line.startswith("CI-GATE-ENV ")
        and "git=" in env_line and "zsh=" in env_line,
    )
    expect(
        "an absent interpreter is recorded as absent rather than omitted",
        "zsh=absent" in gated_environment(
            which=lambda name: None if name == "zsh" else f"/usr/bin/{name}",
            runner=lambda *a, **k: subprocess.CompletedProcess(
                a[0], 0, "git version 9.9.9\n", "")),
    )

    fake_calls: List[Sequence[str]] = []
    def fake_runner(argv: Sequence[str]) -> Result:
        fake_calls.append(argv)
        joined = " ".join(argv)
        if "harness_check.py --ci" in joined:
            return Result(0, "HARNESS-SUMMARY mode=ci checks=1 failures=0 exit=0\n")
        if "harness_check.py --selftest" in joined:
            return Result(0, f"SELFTEST-SUMMARY suite=harness_check checks={SUITE_FLOORS['harness_check']} failures=0\n")
        if "render-packages.py --selftest" in joined:
            return Result(0, f"SELFTEST-SUMMARY suite=render-packages checks={SUITE_FLOORS['render-packages']} failures=0\n")
        if "bash_command_guard.py" in joined:
            return Result(0, f"SELFTEST-SUMMARY suite=bash_command_guard checks={SUITE_FLOORS['bash_command_guard']} failures=0\n")
        if "git_grep_engine_guard.py" in joined:
            return Result(0, f"SELFTEST-SUMMARY suite=git_grep_engine_guard checks={expected_selftest_checks('git_grep_engine_guard')} failures=0\n")
        if "zsh_rev_modifier_guard.py" in joined:
            return Result(0, f"SELFTEST-SUMMARY suite=zsh_rev_modifier_guard checks={expected_selftest_checks('zsh_rev_modifier_guard')} failures=0\n")
        if "run-skill-evals.py" in joined:
            return Result(0, f"EVAL-VALIDATE-SUMMARY scenarios={EVAL_SCENARIO_FLOOR} "
                          f"skills={EVAL_SKILL_FLOOR} failures=0 scope=shape-only exit=0\n")
        if "--output" in argv:
            return Result(0, "RENDER-SUMMARY action=render targets=5 failures=0 exit=0\n")
        return Result(0, "RENDER-SUMMARY action=verify targets=5 failures=0 exit=0\n")

    expect(
        "fake runner covers the production command registry",
        gate(fake_runner, emit_child_output=False) == 0,
    )
    expect("production registry is non-empty", len(fake_calls) == 9)
    # The fake runner above emits the very constants the production check compares against,
    # so a floor change can never redden it -- the comparison is FLOOR < FLOOR. These arms
    # emit a corpus one below each floor instead, so the error path executes at least once.
    def shrunken_scenario_runner(argv):
        if "run-skill-evals.py" in " ".join(argv):
            return Result(0, f"EVAL-VALIDATE-SUMMARY scenarios={EVAL_SCENARIO_FLOOR - 1} "
                          f"skills={EVAL_SKILL_FLOOR} failures=0 scope=shape-only exit=0\n")
        return fake_runner(argv)

    def shrunken_skill_runner(argv):
        if "run-skill-evals.py" in " ".join(argv):
            return Result(0, f"EVAL-VALIDATE-SUMMARY scenarios={EVAL_SCENARIO_FLOOR} "
                          f"skills={EVAL_SKILL_FLOOR - 1} failures=0 scope=shape-only exit=0\n")
        return fake_runner(argv)

    expect(
        "production gate turns red when the eval corpus falls below its scenario floor",
        gate(shrunken_scenario_runner, emit_child_output=False) != 0,
    )
    expect(
        "production gate turns red when the eval corpus falls below its skill floor",
        gate(shrunken_skill_runner, emit_child_output=False) != 0,
    )
    recorded_harness_floor = SUITE_FLOORS["harness_check"]
    SUITE_FLOORS["harness_check"] = recorded_harness_floor - 1
    try:
        expect(
            "production gate turns red when its harness floor drifts",
            gate(fake_runner, emit_child_output=False) != 0,
        )
    finally:
        SUITE_FLOORS["harness_check"] = recorded_harness_floor
    original_handoff_policy = review_handoff_policy_error
    globals()["review_handoff_policy_error"] = lambda: "planted handoff-policy failure"
    try:
        expect(
            "production gate adopts the review handoff policy result",
            gate(fake_runner, emit_child_output=False) != 0,
        )
    finally:
        globals()["review_handoff_policy_error"] = original_handoff_policy
    def invalid_child_runner(argv: Sequence[str]) -> Result:
        result = fake_runner(argv)
        if "harness_check.py --ci" in " ".join(argv):
            return Result(
                0,
                "HARNESS-SUMMARY mode=ci checks=0 failures=0 exit=0\n",
            )
        return result
    expect(
        "production gate turns red when receipt validation rejects one child",
        gate(invalid_child_runner, emit_child_output=False) != 0,
    )
    print(f"SELFTEST-SUMMARY suite=ci-gate checks={checks} failures={failures}")
    return 1 if failures else 0


def main(argv: Sequence[str]) -> int:
    if len(argv) == 2 and argv[1] == "--selftest":
        return selftest()
    if len(argv) == 2 and argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0
    if len(argv) == 2 and argv[1] == "--version":
        print(f"ci-gate {VERSION}")
        return 0
    if len(argv) != 1:
        print("usage: ci-gate.py [--selftest|--version]", file=sys.stderr)
        return 2
    return gate()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
