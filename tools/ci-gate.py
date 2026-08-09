#!/usr/bin/env python3
"""Run the complete offline z-harness gate and validate each terminal receipt."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
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
    "harness_check": 72,
    "render-packages": 192,
    "bash_command_guard": 190,
    "git_grep_engine_guard": 102,
    "zsh_rev_modifier_guard": 68,
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
            "credentials, one ci-gate command, and one conformance command"
        )
    return None


def run_command(argv: Sequence[str]) -> Result:
    completed = subprocess.run(
        list(argv),
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
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

    # SUITE_FLOORS and harness_check's SELFTEST_SUITES are two tables describing one
    # contract. They had already drifted before this assertion existed, so bind them.
    import importlib.util as _il
    _spec = _il.spec_from_file_location("_hc", ROOT / "hooks/harness_check.py")
    _hc = _il.module_from_spec(_spec)
    _spec.loader.exec_module(_hc)
    _harness_floors = {name: floor for name, _cmd, floor in _hc.SELFTEST_SUITES}
    _drift = {
        suite: (floor, _harness_floors.get(suite))
        for suite, floor in SUITE_FLOORS.items()
        if suite != "harness_check" and _harness_floors.get(suite) != floor
    }
    expect(
        f"gate floors agree with harness_check's registry (drift: {_drift or 'none'})",
        not _drift,
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
