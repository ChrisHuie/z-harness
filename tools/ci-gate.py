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
WORKFLOW_DIR = ROOT / ".github/workflows"
# The contract pinned one file byte-for-byte and nothing enumerated the directory, so a
# SECOND workflow -- `permissions: write-all`, `pull_request_target`, arbitrary steps --
# ran on every push with the gate reporting the workflow contract satisfied. A CI
# configuration is the set of files, not the one file we happen to name.
EXPECTED_WORKFLOW_FILES = ("check.yml",)
# Every selftest suite carries a numeric floor; the eval corpus was floored only at zero,
# so cutting 22 scenarios across 6 skills down to a single semantically empty one left the
# whole gate green. Lower these in the commit that removes the scenarios.
EVAL_SCENARIO_FLOOR = 22
EVAL_SKILL_FLOOR = 6

# One floor per suite, read by both the production spec table and the selftest's fake
# runner. Two hand-maintained copies had already drifted -- render-packages was floored at
# 165 here and 178 in harness_check -- and a fake that hardcodes its own number tests the
# literal rather than the contract.
SUITE_FLOORS = {
    "harness_check": 77,
    "render-packages": 192,
    "bash_command_guard": 1100,
    "git_grep_engine_guard": 603,
    "zsh_rev_modifier_guard": 240,
}
EXPECTED_WORKFLOW = """name: harness-check
on:
  push:
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
      - uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97
        with:
          python-version: 3.13.14
      - name: install zsh where the runner image omits it
        if: runner.os == 'Linux'
        run: sudo apt-get update && sudo apt-get install -y zsh && zsh --version
      - name: complete offline gate
        run: python3 tools/ci-gate.py

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


def workflow_error(data: str) -> Optional[str]:
    if data != EXPECTED_WORKFLOW:
        return (
            "workflow differs from the closed contract: two explicit OS targets, Python "
            "3.13.14, full action SHAs, read-only permissions, non-persisted checkout "
            "credentials, a Linux-only zsh install whose own version call proves it "
            "landed, one ci-gate command, and one conformance command"
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
                    r"exit=(?P<exit>\d+)$"
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
# The golden was floored only at zero: 752 commands and 1 command both read as a clean
# verdict, and `752` appeared nowhere in this repository. `write-decision-golden.py` unions
# fixture commands across every revision in `rev-list BASE..HEAD`, so the corpus does not
# shrink on the normal regeneration path -- but that protection lives in the generator,
# where this gate cannot see it, and the gate validates whatever golden it is handed. The
# eval corpus earned EVAL_SCENARIO_FLOOR for exactly this shape. Lower this only in the
# commit that retires the commands.
DECISION_CORPUS_FLOOR = 752


def decision_golden_error(golden_data=None, decide=None, corpus_floor=None) -> str:
    """Return drift between the recorded guard verdicts and what the guards now return.

    Source digests pin bytes and floors ratchet counts; neither notices a DECISION
    reversal, because a fixture and the code it grades move together. Forty-three fixture
    expectations were rewritten on this branch with every suite green. A verdict change
    now has to appear here too, one reviewable line per command.
    """
    try:
        # A caller supplying its own golden is probing this function's logic, not the tree;
        # only the real invocation can meaningfully compare the corpus against its floor.
        synthetic = golden_data is not None
        floor = (corpus_floor if corpus_floor is not None
                 else (None if synthetic else DECISION_CORPUS_FLOOR))
        if golden_data is None:
            golden_data = json.loads(DECISION_GOLDEN.read_text(encoding="utf-8"))
        recorded = golden_data.get("decisions") or {}
        if not recorded:
            return "the decision golden records no commands, which is not a clean verdict"
        if floor is not None and len(recorded) < floor:
            return (f"the decision corpus shrank to {len(recorded)} commands, below the "
                    f"recorded floor of {floor}; a smaller corpus reads as the same clean "
                    f"verdict while pinning fewer verdicts")
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
    drift = []
    for command, expected in recorded.items():
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
# Every element of a guarded set should be held by at least this many checks: at a margin of
# one, deleting the element is a silent fail-open the suites still pass; at zero it is not
# even a fail-open the suites could notice.
ELEMENT_MARGIN_TARGET = 2

# A set is exempt only when removing an element cannot change a DECISION, and the reason
# names what its elements feed instead. Both entries were settled by reading every Load
# reference to the name, not by how the set looked. Adding to this dict is a claim that
# must be re-established the same way.
MARGIN_EXEMPT_SETS = {
    "MOD_MEANING": "read only by _deny_hits, through .get(mod, mod), so a missing entry "
                   "changes reason text and no decision",
    "_CLOSED_LIMITS": "read only by selftest, where the entry IS the drift check, so "
                      "removing it removes the check that would redden",
}

# Flooring each set at its own measured minimum would write `0` twenty times over, and a
# floor of zero asserts nothing -- it reads as a guarantee while permitting everything. So
# the ratchet is the DEBT ITSELF, and the debt is the total SHORTFALL rather than a count of
# elements below target: `sum(target - margin)`. Counting elements instead hid real work --
# twelve PCRE_ESCAPE_LETTERS fixtures moved twelve elements from a margin of zero to one and
# left an element count unchanged at 172, so a contributor closing genuine gaps saw the gate
# register nothing. Shortfall moves with every improvement. It may shrink and never grow: a
# new set element with no coverage raises it by the full target and fails here.
ELEMENT_MARGIN_DEBT_CEILING = 275


def mutation_receipt_error(receipt_data=None, declared=None, ceiling=None,
                           exempt=None) -> str:
    """Return drift between recorded mutation evidence and the sets the guards declare.

    `tools/write-mutation-receipt.py` measures the receipt by running every mutation, which
    is far too slow to repeat on every gate run. What this proves instead is the property
    that actually failed on this branch: every element the guards declare RIGHT NOW carries
    recorded evidence, nothing recorded is stale, no site mutation survives, no mutation
    moved the check count, and no more elements sit below the margin target than the
    recorded ceiling allows. Adding a name to a guarded set without regenerating fails here,
    because the new element has no recorded margin -- which is what makes the slow tool
    unskippable.
    """
    if ceiling is None:
        ceiling = ELEMENT_MARGIN_DEBT_CEILING
    if exempt is None:
        exempt = MARGIN_EXEMPT_SETS
    # A caller supplying its own declaration is probing this function's arithmetic, not
    # the tree; only the real invocation can meaningfully compare source bytes.
    synthetic = declared is not None
    try:
        if receipt_data is None:
            receipt_data = json.loads(MUTATION_RECEIPT.read_text(encoding="utf-8"))
        if declared is None:
            spec = importlib.util.spec_from_file_location(
                "_ci_gate_mutation", ROOT / "tools/write-mutation-receipt.py")
            if spec is None or spec.loader is None:
                return "cannot load write-mutation-receipt.py for the mutation receipt"
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            declared = {}
            for relative in module.GUARDS:
                for name, (_kind, elements) in module.declared_sets(relative).items():
                    if name not in module.SWEEP_EXCLUSIONS:
                        declared[name] = set(elements)
    except Exception as exc:
        return f"cannot verify the mutation receipt: {exc!r}"
    recorded = receipt_data.get("sets") or {}
    if not recorded or not declared:
        return "the mutation receipt records no swept sets, which is not a clean verdict"
    problems, debt = [], 0
    missing_sets = sorted(set(declared) - set(recorded))
    stale_sets = sorted(set(recorded) - set(declared))
    if missing_sets:
        problems.append(f"declared but never swept: {missing_sets}")
    if stale_sets:
        problems.append(f"swept but no longer declared: {stale_sets}")
    for name in sorted(set(declared) & set(recorded)):
        margins = recorded[name].get("margins") or {}
        missing = sorted(declared[name] - set(margins))
        stale = sorted(set(margins) - declared[name])
        if missing:
            problems.append(f"{name} elements with no recorded margin: {missing}")
        if stale:
            problems.append(f"{name} recorded margins for absent elements: {stale}")
        # A non-integer failure count means removing the element stopped the module
        # importing or ran past its bound. Both are caught harder than any check count,
        # so they clear the target rather than failing a numeric comparison against it.
        if name not in exempt:
            debt += sum(ELEMENT_MARGIN_TARGET - entry["failures"]
                        for element, entry in margins.items()
                        if element in declared[name]
                        and isinstance(entry.get("failures"), int)
                        and entry["failures"] < ELEMENT_MARGIN_TARGET)
    if debt > ceiling:
        problems.append(
            f"margin shortfall against a target of {ELEMENT_MARGIN_TARGET} is {debt}, above "
            f"the recorded ceiling of {ceiling}; coverage of the guarded sets got thinner. "
            f"Lower the ceiling only in a commit that raises the coverage")
    stale_exemptions = sorted(set(exempt) - set(declared))
    if stale_exemptions:
        problems.append(
            f"margin-exempt sets the guards no longer declare: {stale_exemptions}")
    if not synthetic:
        measured = receipt_data.get("measured_against") or {}
        if not measured:
            problems.append(
                "the receipt records no source digests, so a receipt describing an older "
                "guard cannot be told from a current one; regenerate it")
        moved = sorted(
            relative for relative, digest in measured.items()
            if not (ROOT / relative).is_file()
            or hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != digest)
        if moved:
            problems.append(
                f"guards changed since the receipt was measured: {moved}; every recorded "
                "margin describes the older source, so rerun tools/write-mutation-receipt.py")
    survivors = receipt_data.get("site_survivors") or []
    if survivors:
        problems.append(f"site mutations no check catches: {survivors}")
    drift = receipt_data.get("selector_drift") or []
    if drift:
        problems.append(f"mutations that moved the check COUNT: {drift[:4]}")
    for suite, floor in SUITE_FLOORS.items():
        for relative, counts in (receipt_data.get("baseline") or {}).items():
            if relative.endswith(f"{suite}.py") and counts.get("checks", 0) < floor:
                problems.append(
                    f"receipt baseline for {suite} records {counts.get('checks')} checks, "
                    f"below the floor of {floor}; the receipt predates the current suite")
    if not problems:
        return ""
    return ("mutation receipt does not match the guards as they stand: "
            + "; ".join(problems[:6])
            + ("; ..." if len(problems) > 6 else "")
            + ". If the change is intended, run tools/write-mutation-receipt.py in the "
              "same commit and review that diff")


REVIEW_ROOT = ROOT / "contracts/review"
INCLUDE_OPEN = "<!-- include: "
INCLUDE_CLOSE = "<!-- end include -->"
FENCE_MARKERS = ("```", "~~~")


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


def review_include_error(review_root=None) -> str:
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
    if not root.is_dir():
        return (f"{REVIEW_ROOT.name}/ does not exist, so no outbound review text is gated; "
                "this check asserts nothing without it")
    documents = sorted(root.rglob("*.md"))
    if not documents:
        return (f"no markdown under {root}, so the review-include check scanned nothing, "
                "which is not a clean verdict")
    problems, blocks = [], 0
    for document in documents:
        lines = document.read_text(encoding="utf-8").splitlines()
        for header, close, name in include_blocks(lines):
            blocks += 1
            if close is None:
                problems.append(f"{review_path_label(document)}: unterminated include")
                continue
            if not name:
                problems.append(f"{review_path_label(document)}: include names no file")
                continue
            source = ROOT / name
            if not source.is_file():
                problems.append(f"{review_path_label(document)} includes {name}, "
                                "which does not exist")
                continue
            embedded = "\n".join(lines[header + 1:close])
            if embedded.strip("\n") != source.read_text(encoding="utf-8").strip("\n"):
                problems.append(
                    f"{review_path_label(document)} has a stale copy of {name}; "
                    "regenerate it before posting")
    if problems:
        return (f"outbound review text drifted from its sources "
                f"(scanned {len(documents)} files, {blocks} include blocks under "
                f"{root}): " + "; ".join(problems[:5]))
    return ""


def gated_environment(which=None, runner=None) -> str:
    """Name the interpreters this run's verdicts were measured against.

    Two guard probes reduce to a skip when zsh is missing -- the 52-letter modifier
    enumeration and nine shell-boundary probe groups -- and both hold their check counts
    fixed on purpose, so the shrink-only floor does not read a zsh-less host as a gutted
    suite. A suite's receipt is therefore byte-identical whether those probes ran or were
    skipped wholesale, and only a child's LAST line survives this gate, which drops the
    printed SKIP. Without this line nothing in the record distinguishes the two, so a
    claim about zsh could go unverified on a runner with no zsh and read as proven.

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
    problem = workflow_error(workflow)
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
    review_problem = review_include_error()
    print(f"  {'FAIL' if review_problem else 'PASS'} review-includes")
    if review_problem:
        failures.append(review_problem)
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
    expect("workflow baseline matches exact contract", workflow_error(EXPECTED_WORKFLOW) is None)
    expect("workflow command mutation fails", workflow_error(EXPECTED_WORKFLOW.replace(
        "python3 tools/ci-gate.py", "python3 hooks/harness_check.py --ci", 1
    )) is not None)
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
    expect(
        "an empty decision golden is a failure, not a clean verdict",
        decision_golden_error(golden_data={"decisions": {}}) != "",
    )
    expect(
        "a shrunken decision corpus is a failure, not the same clean verdict",
        "corpus shrank" in decision_golden_error(
            golden_data={"decisions": {"git status --short": "allow"}},
            decide=lambda _command: ("allow", ""), corpus_floor=5),
    )
    expect(
        "a corpus at its recorded floor clears",
        decision_golden_error(
            golden_data={"decisions": {"git status --short": "allow"}},
            decide=lambda _command: ("allow", ""), corpus_floor=1) == "",
    )
    expect(
        "a reversed verdict in the golden is reported with both sides",
        "deny -> allow" in decision_golden_error(
            golden_data={"decisions": {"git status --short": "deny"}},
            decide=lambda _command: ("allow", "")),
    )
    expect(
        "hook budget contract rejects a sub-second margin",
        hook_budget_error(budget=4.01) != "",
    )

    declared_probe = {"PROBE": {"a", "b"}}
    receipt_probe = {
        "sets": {"PROBE": {"margins": {"a": {"failures": 3}, "b": {"failures": 2}}}},
        "baseline": {}, "site_survivors": [], "selector_drift": [],
    }
    expect("recorded mutation evidence matches the guards", mutation_receipt_error() == "")
    expect(
        "a receipt covering every declared element clears",
        mutation_receipt_error(receipt_probe, declared_probe, exempt={}) == "",
    )
    expect(
        "an empty mutation receipt is a failure, not a clean verdict",
        mutation_receipt_error({"sets": {}}, declared_probe) != "",
    )
    expect(
        "an element added to a guarded set without regenerating is named",
        "no recorded margin" in mutation_receipt_error(
            {"sets": {"PROBE": {"margins": {"a": {"failures": 3}}}}}, declared_probe),
    )
    expect(
        "a recorded margin for an element the source no longer declares is named",
        "absent elements" in mutation_receipt_error(
            {"sets": {"PROBE": {"margins": {
                "a": {"failures": 3}, "b": {"failures": 2}, "gone": {"failures": 9}}}}},
            declared_probe),
    )
    expect(
        "margin shortfall above the recorded ceiling is a failure",
        "above the recorded ceiling" in mutation_receipt_error(
            {"sets": {"PROBE": {"margins": {
                "a": {"failures": 1}, "b": {"failures": 0}}}}},
            declared_probe, ceiling=2),
    )
    expect(
        "margin shortfall at the recorded ceiling clears",
        mutation_receipt_error(
            {"sets": {"PROBE": {"margins": {
                "a": {"failures": 1}, "b": {"failures": 0}}}},
             "site_survivors": [], "selector_drift": []},
            declared_probe, ceiling=3, exempt={}) == "",
    )
    expect(
        "an exempt set contributes no debt, so its zeros cannot fail the ceiling",
        mutation_receipt_error(
            {"sets": {"MOD_MEANING": {"margins": {
                "a": {"failures": 0}, "b": {"failures": 0}}}},
             "site_survivors": [], "selector_drift": []},
            {"MOD_MEANING": {"a", "b"}}, ceiling=0,
            exempt={"MOD_MEANING": "probe"}) == "",
    )
    expect(
        "an exemption for a set the guards no longer declare is named",
        "no longer declare" in mutation_receipt_error(
            dict(receipt_probe, sets={"PROBE": {"margins": {
                "a": {"failures": 3}, "b": {"failures": 2}}}}),
            declared_probe),
    )
    expect(
        "an element whose removal breaks the import clears the target",
        mutation_receipt_error(
            {"sets": {"PROBE": {"margins": {
                "a": {"failures": 3},
                "b": {"failures": "module failed to load: KeyError"}}}},
             "site_survivors": [], "selector_drift": []},
            declared_probe, exempt={}) == "",
    )
    expect(
        "a declared set that was never swept is named",
        "never swept" in mutation_receipt_error(
            {"sets": {"OTHER": {"margins": {"x": {"failures": 9}}}}},
            {"PROBE": {"a"}, "OTHER": {"x"}}),
    )
    expect(
        "a site mutation no check catches is a failure",
        "no check catches" in mutation_receipt_error(
            dict(receipt_probe, site_survivors=["budget wrap deleted"]), declared_probe),
    )
    expect(
        "a mutation that moved the check COUNT rather than a verdict is a failure",
        "moved the check" in mutation_receipt_error(
            dict(receipt_probe, selector_drift=["PROBE.a: 571 -> 570"]), declared_probe),
    )

    real_receipt = json.loads(MUTATION_RECEIPT.read_text(encoding="utf-8"))
    expect(
        "a receipt measured against different guard bytes is stale, not clean",
        "changed since the receipt was measured" in mutation_receipt_error(
            dict(real_receipt, measured_against={"hooks/bash_command_guard.py": "0" * 64})),
    )
    expect(
        "a receipt recording no source digests is not a clean verdict",
        "no source digests" in mutation_receipt_error(
            {k: v for k, v in real_receipt.items() if k != "measured_against"}),
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
            return Result(0, f"SELFTEST-SUMMARY suite=git_grep_engine_guard checks={SUITE_FLOORS['git_grep_engine_guard']} failures=0\n")
        if "zsh_rev_modifier_guard.py" in joined:
            return Result(0, f"SELFTEST-SUMMARY suite=zsh_rev_modifier_guard checks={SUITE_FLOORS['zsh_rev_modifier_guard']} failures=0\n")
        if "run-skill-evals.py" in joined:
            return Result(0, f"EVAL-VALIDATE-SUMMARY scenarios={EVAL_SCENARIO_FLOOR} "
                          f"skills={EVAL_SKILL_FLOOR} failures=0 exit=0\n")
        if "--output" in argv:
            return Result(0, "RENDER-SUMMARY action=render targets=5 failures=0 exit=0\n")
        return Result(0, "RENDER-SUMMARY action=verify targets=5 failures=0 exit=0\n")

    expect(
        "fake runner covers the production command registry",
        gate(fake_runner, emit_child_output=False) == 0,
    )
    expect("production registry is non-empty", len(fake_calls) == 9)
    recorded_harness_floor = SUITE_FLOORS["harness_check"]
    SUITE_FLOORS["harness_check"] = recorded_harness_floor - 1
    try:
        expect(
            "production gate turns red when its harness floor drifts",
            gate(fake_runner, emit_child_output=False) != 0,
        )
    finally:
        SUITE_FLOORS["harness_check"] = recorded_harness_floor
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
