#!/usr/bin/env python3
"""Enumerate single-operand mutants without treating instrument failure as a kill.

The target's pristine ``--selftest`` must emit one terminal green receipt before any
mutation runs. The mutation scope is every top-level function except the selftest and CLI
``main`` runner: corrupting the runner can erase its receipt, which is instrument failure,
not evidence that the behavioral suite caught a mutant. A mutant is killed only when the
same complete suite emits one terminal receipt with the same check count, a positive
failure count, and assertion-failure exit 1. Syntax, import, setup, receipt, timeout, and count
failures are instrument errors and make this command non-zero.

JSON is written to stdout; progress and the terminal summary are written to stderr. The
instrument never writes into the checkout it reviews.
"""
from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


RECEIPT = re.compile(
    r"^SELFTEST-SUMMARY suite=(?P<suite>[a-z0-9_-]+) "
    r"checks=(?P<checks>\d+) failures=(?P<failures>\d+)$",
    re.M,
)
SCHEMA_VERSION = 1
EXCLUDED_FUNCTIONS = frozenset({"selftest", "main"})


class InstrumentError(RuntimeError):
    """The measurement failed before it produced a semantic verdict."""


@dataclass(frozen=True)
class Site:
    kind: str
    node: ast.expr
    replacements: tuple[str, ...]


@dataclass(frozen=True)
class ExtraCopy:
    path: Path
    sha256: str


def production_functions(tree: ast.Module):
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and node.name not in EXCLUDED_FUNCTIONS:
            yield node


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def artifact_digest(path: Path) -> str:
    """Bind a copied file or directory tree, rejecting ambiguous symlink inputs."""
    if path.is_symlink():
        raise InstrumentError(f"extra copy path is a symlink: {path}")
    if path.name == "__pycache__" or path.suffix == ".pyc":
        raise InstrumentError(f"extra copy contains executable bytecode cache: {path}")
    if path.is_file():
        return sha256_bytes(path.read_bytes())
    if not path.is_dir():
        raise InstrumentError(f"cannot digest non-file extra copy path: {path}")
    digest = hashlib.sha256()
    for child in sorted(path.rglob("*")):
        relative = child.relative_to(path).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        if child.is_symlink():
            raise InstrumentError(f"extra copy tree contains a symlink: {child}")
        if child.name == "__pycache__" or child.suffix == ".pyc":
            raise InstrumentError(
                f"extra copy tree contains executable bytecode cache: {child}")
        if child.is_file():
            payload = child.read_bytes()
            kind = b"file"
        elif child.is_dir():
            payload = b""
            kind = b"dir"
        else:
            raise InstrumentError(f"unsupported extra copy entry: {child}")
        digest.update(kind)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def mutation_sites(tree: ast.Module) -> list[Site]:
    sites = []
    for function in production_functions(tree):
        for node in ast.walk(function):
            if isinstance(node, ast.If):
                sites.append(Site("if", node.test, ("False",)))
            elif isinstance(node, ast.BoolOp):
                identity = "True" if isinstance(node.op, ast.And) else "False"
                sites.extend(Site("boolop", value, (identity,)) for value in node.values)
            elif (isinstance(node, ast.Return) and node.value is not None
                  and not isinstance(node.value, ast.Constant)):
                sites.append(Site("return", node.value, ("True", "False")))
    return sites


def line_starts(source: bytes) -> list[int]:
    starts = [0]
    for index, byte in enumerate(source):
        if byte == 10:
            starts.append(index + 1)
    return starts


def byte_offset(starts: list[int], lineno: int, column: int) -> int:
    """Translate CPython's one-based line and UTF-8 byte column to a byte index."""
    try:
        return starts[lineno - 1] + column
    except IndexError as exc:
        raise InstrumentError(f"AST location {lineno}:{column} is outside the source") from exc


def mutate(source: bytes, starts: list[int], node: ast.expr, replacement: str) -> bytes:
    begin = byte_offset(starts, node.lineno, node.col_offset)
    end = byte_offset(starts, node.end_lineno, node.end_col_offset)
    changed = source[:begin] + f"({replacement})".encode("utf-8") + source[end:]
    if changed == source:
        raise InstrumentError("mutation left the source byte-identical")
    try:
        compile(changed.decode("utf-8"), "<mutant>", "exec")
    except (SyntaxError, UnicodeDecodeError) as exc:
        raise InstrumentError(
            f"constructed mutant does not compile at {node.lineno}:{node.col_offset}: {exc}"
        ) from exc
    return changed


def copy_extra(item: ExtraCopy, work: Path) -> ExtraCopy:
    # The destination is the execution boundary. Hashing the source again before copy is
    # redundant and still leaves a race; hashing the completed private copy proves the
    # bytes the subprocess can actually read.
    destination = work / item.path.name
    if destination.exists():
        raise InstrumentError(
            f"extra copy basename collides in private tree: {item.path.name}")
    if item.path.is_dir():
        shutil.copytree(item.path, destination)
    else:
        shutil.copy2(item.path, destination)
    copied = artifact_digest(destination)
    if copied != item.sha256:
        raise InstrumentError(
            f"private extra copy digest differs for {item.path}: "
            f"expected {item.sha256}, got {copied}")
    return ExtraCopy(destination, copied)


def completed_verdict(done: subprocess.CompletedProcess[str], *,
                      suite: str | None = None, checks: int | None = None) -> dict:
    receipts = list(RECEIPT.finditer(done.stdout))
    final = done.stdout.rstrip().splitlines()[-1] if done.stdout.rstrip() else ""
    if len(receipts) != 1 or final != (receipts[0].group(0) if receipts else ""):
        return {
            "status": "instrument-error",
            "reason": "invalid-receipt",
            "returncode": done.returncode,
            "receipt_count": len(receipts),
        }
    receipt = receipts[0]
    observed_suite = receipt.group("suite")
    observed_checks = int(receipt.group("checks"))
    failures = int(receipt.group("failures"))
    if observed_checks < 1:
        return {"status": "instrument-error", "reason": "zero-checks"}
    if suite is not None and observed_suite != suite:
        return {"status": "instrument-error", "reason": "suite-drift",
                "expected": suite, "actual": observed_suite}
    if checks is not None and observed_checks != checks:
        return {"status": "instrument-error", "reason": "check-count-drift",
                "expected": checks, "actual": observed_checks}
    if done.returncode == 0 and failures == 0:
        return {"status": "survived", "suite": observed_suite,
                "checks": observed_checks, "failures": failures}
    if done.returncode == 1 and failures > 0:
        return {"status": "killed", "suite": observed_suite,
                "checks": observed_checks, "failures": failures}
    return {"status": "instrument-error", "reason": "exit-receipt-disagreement",
            "returncode": done.returncode, "failures": failures}


def run_source(source: bytes, target_name: str, extras: list[ExtraCopy], timeout: float,
               *, suite: str | None = None, checks: int | None = None) -> dict:
    with tempfile.TemporaryDirectory(prefix="survivor-enum-") as raw:
        work = Path(raw)
        target = work / target_name
        try:
            compile(source.decode("utf-8"), str(target), "exec")
        except (SyntaxError, UnicodeDecodeError) as exc:
            return {"status": "instrument-error", "reason": "invalid-mutant",
                    "detail": str(exc)}
        target.write_bytes(source)
        if sha256_bytes(target.read_bytes()) != sha256_bytes(source):
            return {"status": "instrument-error", "reason": "setup-failure",
                    "detail": "private target bytes differ from captured source"}
        private_extras = []
        try:
            for item in extras:
                private_extras.append(copy_extra(item, work))
        except (OSError, InstrumentError) as exc:
            return {"status": "instrument-error", "reason": "setup-failure",
                    "detail": str(exc)}
        environment = dict(os.environ)
        environment.pop("ANNOUNCED_WORK_GUARD", None)
        environment.pop("PYTHONHOME", None)
        environment.pop("PYTHONPATH", None)
        environment.pop("PYTHONPYCACHEPREFIX", None)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        try:
            done = subprocess.run(
                [sys.executable, "-E", "-s", "-B", str(target), "--selftest"],
                capture_output=True,
                stdin=subprocess.DEVNULL,
                text=True,
                timeout=timeout,
                cwd=work,
                env=environment,
            )
        except subprocess.TimeoutExpired:
            return {"status": "instrument-error", "reason": "timeout",
                    "timeout_seconds": timeout}
        except OSError as exc:
            return {"status": "instrument-error", "reason": "execution-failure",
                    "detail": str(exc)}
        try:
            target_after = sha256_bytes(target.read_bytes())
            extras_after = [artifact_digest(item.path) for item in private_extras]
        except (OSError, InstrumentError) as exc:
            return {"status": "instrument-error", "reason": "execution-drift",
                    "detail": str(exc)}
        if (target_after != sha256_bytes(source)
                or extras_after != [item.sha256 for item in private_extras]):
            return {"status": "instrument-error", "reason": "execution-drift",
                    "detail": "private target or extra changed during execution"}
        return completed_verdict(done, suite=suite, checks=checks)


def enumerate_module(source_path: Path, extras: list[Path], timeout: float) -> dict:
    instrument_path = Path(__file__).resolve()
    if source_path.is_symlink():
        raise InstrumentError(f"target source path is a symlink: {source_path}")
    try:
        source_path = source_path.resolve(strict=True)
    except OSError as exc:
        raise InstrumentError(f"cannot resolve target source: {exc}") from exc
    try:
        instrument_sha256 = sha256_bytes(instrument_path.read_bytes())
    except OSError as exc:
        raise InstrumentError(f"cannot bind instrument source: {exc}") from exc
    try:
        source = source_path.read_bytes()
        text = source.decode("utf-8")
        tree = ast.parse(text, filename=str(source_path))
    except (OSError, UnicodeDecodeError, SyntaxError) as exc:
        raise InstrumentError(f"cannot load target source: {exc}") from exc
    sites = mutation_sites(tree)
    if not sites:
        raise InstrumentError("no production mutation sites found")
    source_sha256 = sha256_bytes(source)
    bound_extras = [ExtraCopy(path, artifact_digest(path)) for path in extras]
    extra_digests = [
        {"path": str(item.path.resolve()), "sha256": item.sha256}
        for item in bound_extras
    ]
    plan = [
        {
            "kind": site.kind,
            "line": site.node.lineno,
            "column_bytes": site.node.col_offset,
            "source": ast.get_source_segment(text, site.node) or "",
            "replacements": site.replacements,
        }
        for site in sites
    ]
    plan_sha256 = sha256_bytes(json.dumps(
        plan, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8"))
    baseline = run_source(source, source_path.name, bound_extras, timeout)
    if baseline.get("status") != "survived":
        raise InstrumentError(f"pristine baseline is not green: {baseline}")
    starts = line_starts(source)
    results = []
    for index, site in enumerate(sites):
        outcomes = []
        for replacement in site.replacements:
            try:
                mutant = mutate(source, starts, site.node, replacement)
            except InstrumentError as exc:
                outcome = {"status": "instrument-error", "reason": "invalid-mutant",
                           "detail": str(exc)}
            else:
                outcome = run_source(
                    mutant,
                    source_path.name,
                    bound_extras,
                    timeout,
                    suite=baseline["suite"],
                    checks=baseline["checks"],
                )
            outcomes.append(outcome)
        source_segment = ast.get_source_segment(text, site.node) or ""
        result = {
            "index": index,
            "kind": site.kind,
            "line": site.node.lineno,
            "column_bytes": site.node.col_offset,
            "source": source_segment,
            "outcomes": outcomes,
        }
        results.append(result)
        states = [outcome["status"] for outcome in outcomes]
        print(f"{index:3} {site.kind:6} L{site.node.lineno:<4} {states} "
              f"{source_segment[:70]!r}", file=sys.stderr, flush=True)
    errors = sum(
        outcome["status"] == "instrument-error"
        for result in results for outcome in result["outcomes"]
    )
    killed_mutants = sum(
        outcome["status"] == "killed"
        for result in results for outcome in result["outcomes"]
    )
    killed_sites = sum(
        all(outcome["status"] == "killed" for outcome in result["outcomes"])
        for result in results
    )
    by_kind = {}
    for result in results:
        counts = by_kind.setdefault(result["kind"], {"sites": 0, "killed_sites": 0})
        counts["sites"] += 1
        counts["killed_sites"] += int(
            all(outcome["status"] == "killed" for outcome in result["outcomes"])
        )
    try:
        after_source = sha256_bytes(source_path.read_bytes())
        after_extras = [artifact_digest(path) for path in extras]
        after_instrument = sha256_bytes(instrument_path.read_bytes())
    except (OSError, InstrumentError) as exc:
        raise InstrumentError(f"reviewed source changed or disappeared: {exc}") from exc
    if (after_source != source_sha256
            or after_extras != [item["sha256"] for item in extra_digests]
            or after_instrument != instrument_sha256):
        raise InstrumentError(
            "instrument, reviewed source, or copied fixture changed during enumeration")
    return {
        "schema_version": SCHEMA_VERSION,
        "instrument_sha256": instrument_sha256,
        "target": {"path": str(source_path.resolve()), "sha256": source_sha256},
        "extra_copies": extra_digests,
        "scope": {
            "included": "top-level functions",
            "excluded_functions": sorted(EXCLUDED_FUNCTIONS),
        },
        "plan_sha256": plan_sha256,
        "baseline": baseline,
        "summary": {
            "sites": len(results),
            "mutants": sum(len(result["outcomes"]) for result in results),
            "killed_mutants": killed_mutants,
            "killed_sites": killed_sites,
            "surviving_sites": sum(
                not any(outcome["status"] == "instrument-error"
                        for outcome in result["outcomes"])
                and not all(outcome["status"] == "killed"
                            for outcome in result["outcomes"])
                for result in results
            ),
            "instrument_errors": errors,
            "by_kind": by_kind,
        },
        "results": results,
    }


def selftest() -> int:
    checks = failures = 0

    def check(label: str, condition: bool) -> None:
        nonlocal checks, failures
        checks += 1
        failures += int(not condition)
        print(f"  {'PASS' if condition else 'FAIL'} {label}")

    source = (
        "import sys\n"
        "def verdict(separator):\n"
        "    if any(mark in separator for mark in (';', '—')):\n"
        "        return True\n"
        "    return False\n"
        "def selftest():\n"
        "    failures = 0 if verdict('—') else 1\n"
        "    print(f'SELFTEST-SUMMARY suite=probe checks=1 failures={failures}')\n"
        "    return failures == 0\n"
        "if __name__ == '__main__': sys.exit(0 if selftest() else 1)\n"
    ).encode("utf-8")
    tree = ast.parse(source.decode("utf-8"))
    site = mutation_sites(tree)[0]
    changed = mutate(source, line_starts(source), site.node, "False")
    check("UTF-8 byte offsets construct compilable mutants", bool(compile(changed, "x", "exec")))
    baseline = run_source(source, "probe.py", [], 2)
    check("a terminal green pristine receipt is accepted", baseline["status"] == "survived")
    killed = run_source(changed, "probe.py", [], 2,
                        suite=baseline.get("suite"), checks=baseline.get("checks"))
    check("a complete red receipt is a semantic kill", killed["status"] == "killed")
    broken = source.replace(b"failures = 0 if verdict('\xe2\x80\x94') else 1",
                            b"failures = 1")
    check("a complete red receipt is distinguishable from instrument failure",
          run_source(broken, "probe.py", [], 2)["status"] == "killed")
    invalid = subprocess.CompletedProcess(["probe"], 1, "", "traceback")
    check("a crash without a receipt is an instrument error",
          completed_verdict(invalid)["status"] == "instrument-error")
    disagreement = subprocess.CompletedProcess(
        ["probe"], 0, "SELFTEST-SUMMARY suite=probe checks=1 failures=1\n", "")
    check("exit and receipt disagreement is an instrument error",
          completed_verdict(disagreement)["status"] == "instrument-error")
    for invalid_exit in (2, -9):
        invalid_red = subprocess.CompletedProcess(
            ["probe"], invalid_exit,
            "SELFTEST-SUMMARY suite=probe checks=1 failures=1\n", "")
        check(f"exit {invalid_exit} cannot turn a red receipt into a semantic kill",
              completed_verdict(invalid_red).get("reason")
              == "exit-receipt-disagreement")
    drift = completed_verdict(
        subprocess.CompletedProcess(
            ["probe"], 0, "SELFTEST-SUMMARY suite=probe checks=2 failures=0\n", ""),
        suite="probe", checks=1)
    check("check-count drift is an instrument error", drift.get("reason") == "check-count-drift")
    timeout_source = (
        "import time\n"
        "if __name__ == '__main__': time.sleep(0.2)\n"
    ).encode("utf-8")
    timeout = run_source(timeout_source, "slow.py", [], 0.01)
    check("a timeout is an instrument error", timeout.get("reason") == "timeout")
    with tempfile.TemporaryDirectory(prefix="enumerator-selftest-") as raw:
        target = Path(raw) / "probe.py"
        target.write_bytes(source)
        report = enumerate_module(target, [], 2)
        target_link = Path(raw) / "probe-link.py"
        target_link.symlink_to(target)
        try:
            enumerate_module(target_link, [], 2)
            rejected_target_symlink = False
        except InstrumentError:
            rejected_target_symlink = True
        check("enumeration rejects a symlinked target source", rejected_target_symlink)
        red_target = Path(raw) / "red.py"
        red_target.write_bytes(broken)
        try:
            enumerate_module(red_target, [], 2)
            rejected_red_baseline = False
        except InstrumentError as exc:
            rejected_red_baseline = "pristine baseline is not green" in str(exc)
        check("enumeration rejects a red pristine baseline", rejected_red_baseline)
        check("enumeration retains a green baseline", report["baseline"]["checks"] == 1)
        check("enumeration reports zero instrument errors",
              report["summary"]["instrument_errors"] == 0)
        check("enumeration emits the UTF-8 condition as a killed site",
              any(item["line"] == site.node.lineno
                  and all(outcome["status"] == "killed" for outcome in item["outcomes"])
                  for item in report["results"]))
        check("enumeration does not create a result beside the instrument",
              not (Path(__file__).with_name("probe.py.results.json")).exists())
        fixture = Path(raw) / "fixture.txt"
        fixture.write_text("bound bytes\n", encoding="utf-8")
        link = Path(raw) / "fixture-link.txt"
        link.symlink_to(fixture)
        try:
            artifact_digest(link)
            rejected_symlink = False
        except InstrumentError:
            rejected_symlink = True
        check("extra-copy digests reject symlink roots before copy", rejected_symlink)
        tree_fixture = Path(raw) / "fixture-tree"
        tree_fixture.mkdir()
        (tree_fixture / "value.txt").write_text("bound tree bytes\n", encoding="utf-8")
        (tree_fixture / "value-link.txt").symlink_to(tree_fixture / "value.txt")
        try:
            artifact_digest(tree_fixture)
            rejected_descendant_symlink = False
        except InstrumentError:
            rejected_descendant_symlink = True
        check("extra-copy digests reject descendant symlinks",
              rejected_descendant_symlink)
        expected_fixture = ExtraCopy(fixture, artifact_digest(fixture))
        fixture.write_text("changed bytes\n", encoding="utf-8")
        changed_run = run_source(source, "changed_probe.py", [expected_fixture], 2)
        fixture.write_text("bound bytes\n", encoding="utf-8")
        check("the execution seam rejects transient source bytes outside the recorded digest",
              changed_run.get("reason") == "setup-failure")
        mutating_source = (
            "import sys\n"
            "from pathlib import Path\n"
            "def selftest():\n"
            "    Path('fixture.txt').write_text('changed during execution\\n')\n"
            "    print('SELFTEST-SUMMARY suite=mutating-probe checks=1 failures=0')\n"
            "    return True\n"
            "if __name__ == '__main__': sys.exit(0 if selftest() else 1)\n"
        ).encode("utf-8")
        mutating_run = run_source(
            mutating_source, "mutating_probe.py", [expected_fixture], 2)
        check("a suite cannot persistently change a bound private extra",
              mutating_run.get("reason") == "execution-drift")
        corrupt_work = Path(raw) / "corrupt-copy"
        corrupt_work.mkdir()
        original_copy2 = shutil.copy2

        def corrupt_copy(_source, destination):
            Path(destination).write_text("different private bytes\n", encoding="utf-8")

        shutil.copy2 = corrupt_copy
        try:
            try:
                copy_extra(expected_fixture, corrupt_work)
                rejected_corrupt_copy = False
            except InstrumentError:
                rejected_corrupt_copy = True
        finally:
            shutil.copy2 = original_copy2
        check("copy rejects private bytes that differ from the recorded digest",
              rejected_corrupt_copy)
        bytecode_tree = Path(raw) / "bytecode-tree"
        (bytecode_tree / "__pycache__").mkdir(parents=True)
        (bytecode_tree / "module.py").write_text("VALUE = 'source'\n", encoding="utf-8")
        (bytecode_tree / "__pycache__" / "module.pyc").write_bytes(b"stale bytecode")
        try:
            artifact_digest(bytecode_tree)
            rejected_bytecode_cache = False
        except InstrumentError:
            rejected_bytecode_cache = True
        check("extra-copy digests reject executable bytecode caches",
              rejected_bytecode_cache)
        pyc_root = Path(raw) / "direct.pyc"
        pyc_root.write_bytes(b"direct stale bytecode")
        cache_root = Path(raw) / "__pycache__"
        cache_root.mkdir()
        try:
            artifact_digest(pyc_root)
            rejected_pyc_root = False
        except InstrumentError:
            rejected_pyc_root = True
        try:
            artifact_digest(cache_root)
            rejected_cache_directory = False
        except InstrumentError:
            rejected_cache_directory = True
        check("extra-copy digests reject direct pyc roots", rejected_pyc_root)
        check("extra-copy digests reject direct cache-directory roots",
              rejected_cache_directory)
        scope_source = (
            "def outer(left, right):\n"
            "    def nested(value):\n"
            "        return value or False\n"
            "    return left and nested(right)\n"
        )
        scope_sites = mutation_sites(ast.parse(scope_source))
        check("and/or operands receive their distinct identity replacements",
              sum(item.kind == "boolop" and item.replacements == ("True",)
                  for item in scope_sites) == 2
              and sum(item.kind == "boolop" and item.replacements == ("False",)
                      for item in scope_sites) == 2)
        check("the top-level function walk includes a nested nonconstant return",
              any(item.kind == "return" and item.node.lineno == 3
                  and item.replacements == ("True", "False")
                  for item in scope_sites))
        return_source = (
            "import sys\n"
            "def flip(value): return not value\n"
            "def selftest():\n"
            "    failures = int(flip(True) is not False) + int(flip(False) is not True)\n"
            "    print(f'SELFTEST-SUMMARY suite=return-probe checks=2 failures={failures}')\n"
            "    return failures == 0\n"
            "if __name__ == '__main__': sys.exit(0 if selftest() else 1)\n"
        ).encode("utf-8")
        return_target = Path(raw) / "return_probe.py"
        return_target.write_bytes(return_source)
        return_report = enumerate_module(return_target, [], 2)
        check("a return site is killed only when both constant replacements fail",
              return_report["summary"]["sites"] == 1
              and return_report["summary"]["mutants"] == 2
              and return_report["summary"]["killed_mutants"] == 2
              and return_report["summary"]["killed_sites"] == 1)
        check("the report binds source, plan, instrument, and exclusions",
              report["target"]["sha256"] == sha256_bytes(source)
              and len(report["plan_sha256"]) == 64
              and len(report["instrument_sha256"]) == 64
              and report["scope"]["excluded_functions"] == ["main", "selftest"])
    print(f"SELFTEST-SUMMARY suite=enumerate-survivors checks={checks} failures={failures}")
    return failures


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", nargs="?", type=Path)
    parser.add_argument("extra_copy", nargs="*", type=Path)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--selftest", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.selftest:
        return 1 if selftest() else 0
    if args.source is None:
        print("source is required unless --selftest is used", file=sys.stderr)
        return 2
    if args.timeout <= 0:
        print("--timeout must be positive", file=sys.stderr)
        return 2
    try:
        report = enumerate_module(args.source, args.extra_copy, args.timeout)
    except InstrumentError as exc:
        print(f"ENUM-ERROR {exc}", file=sys.stderr)
        return 2
    json.dump(report, sys.stdout, sort_keys=True, indent=2)
    sys.stdout.write("\n")
    summary = report["summary"]
    exit_code = 2 if summary["instrument_errors"] else 0
    print(
        f"ENUM-SUMMARY file={args.source.name} sites={summary['sites']} "
        f"killed_sites={summary['killed_sites']} "
        f"surviving_sites={summary['surviving_sites']} "
        f"instrument_errors={summary['instrument_errors']} exit={exit_code}",
        file=sys.stderr,
    )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
