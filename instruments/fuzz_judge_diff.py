#!/usr/bin/env python3
"""Reproducible differential fuzzing over isolated Stop-guard judge processes.

The complete machine-readable report is written to stdout. Verdict direction is separate
from block-reason drift, every generated case is retained, and the report binds the seed,
grammar, generated messages, and both compared sources by SHA-256.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import types


SCHEMA_VERSION = 1
MAX_CASES = 100_000
OPENERS = (
    "Starting the", "Running the", "Proceeding with the", "Continuing on the",
    "Beginning a", "Kicking off the", "Let me check", "I'll now run",
    "Let me now start", "On it", "Doing that now", "Firing off the",
)
WORDS = (
    "audit", "sweep", "tests", "checks", "migration", "script", "run", "prior",
    "three", "3", "second", "remaining", "failed", "completed", "passed",
    "finished", "already", "previously", "recently", "of", "for", "with", "the",
    "a", "whether", "why", "where", "how", "into", "it", "quickly", "all",
    "both", "no", "will", "being", "never", "produced", "took", "landed",
    "showed", "found", "x-failed", "re/completed", "don't", "v1.2.3", "12:04",
    "https://x.test", "image:v1",
)
JOINERS = (
    " ", " ", " ", " ", ". ", "; ", ", ", ": ", " — ", " -- ", " and ",
    " because ", " after ", " that ", " which ", " then ", "  ", "\n", ",", ";",
    ".", "?", "!",
)
TAILS = (
    "", ".", "?", " in 4m.", " took four minutes.", " successfully.",
    " the migration.", " all checks.", " tests.", " checks completed.", ";failed",
    ",failed now.",
)
GROUPS = (
    ("parenthetical", "(", ")"),
    ("bracketed", "[", "]"),
    ("braced", "{", "}"),
    ("curly-double", "“", "”"),
    ("curly-single", "‘", "’"),
    ("straight-double", '"', '"'),
    ("straight-single", "'", "'"),
    ("inline-code", "`", "`"),
    ("double-inline-code", "``", "``"),
)
PRODUCTIONS = (
    "flat",
    "adjective-group-noun",
    "colon-group-predicate",
    "predicate-group-result",
    "outer-break-group",
    "nested-group",
    "url-ending-punctuation",
    "empty-group",
    "post-group-modifier",
    "colon-group-result-tail",
)
GROUP_PRODUCTIONS = frozenset({
    "adjective-group-noun",
    "colon-group-predicate",
    "predicate-group-result",
    "outer-break-group",
    "nested-group",
    "empty-group",
    "post-group-modifier",
    "colon-group-result-tail",
})
POSTGROUP_MODIFIERS = (
    "finally", "gracefully", "locally", "quickly", "reliably", "silently",
    "unexpectedly",
)
POSTGROUP_RESULT_TAILS = (
    ("after", "4m"),
    ("at", "12:04"),
    ("with", "a traceback"),
)
# Every production runs once, and every recorded group is rendered in the message.
# The last two cases close the delimiter inventory left by the production inventory.
MANDATORY_CASES = (
    ("flat", None),
    ("adjective-group-noun", "parenthetical"),
    ("colon-group-predicate", "bracketed"),
    ("predicate-group-result", "braced"),
    ("outer-break-group", "curly-double"),
    ("nested-group", "curly-single"),
    ("url-ending-punctuation", None),
    ("empty-group", "straight-double"),
    ("post-group-modifier", "straight-single"),
    ("post-group-modifier", "inline-code"),
    ("post-group-modifier", "double-inline-code"),
    ("colon-group-result-tail", "parenthetical"),
)
MIN_CASES = len(MANDATORY_CASES)
GROUP_BY_NAME = {group[0]: group for group in GROUPS}


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def source_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_bytes_digest(source: bytes) -> str:
    return hashlib.sha256(source).hexdigest()


def grammar_payload() -> dict:
    return {
        "openers": OPENERS,
        "words": WORDS,
        "joiners": JOINERS,
        "tails": TAILS,
        "groups": GROUPS,
        "productions": PRODUCTIONS,
        "group_productions": sorted(GROUP_PRODUCTIONS),
        "postgroup_modifiers": POSTGROUP_MODIFIERS,
        "postgroup_result_tails": POSTGROUP_RESULT_TAILS,
        "mandatory_cases": MANDATORY_CASES,
    }


def flat_message(rng: random.Random) -> str:
    parts = [rng.choice(OPENERS)]
    for _ in range(rng.randint(1, 14)):
        parts.append(rng.choice(JOINERS))
        parts.append(rng.choice(WORDS))
    return "".join(parts) + rng.choice(TAILS)


def generated_case(rng: random.Random, production: str, group=None) -> dict:
    if production in GROUP_PRODUCTIONS:
        group_name, opened, closed = rng.choice(GROUPS) if group is None else group
    else:
        group_name, opened, closed = None, "", ""
    activity = rng.choice(("audit", "sweep", "checks", "tests", "migration"))
    counted = rng.choice(("three", "3", "remaining", "second"))
    result = rng.choice(("failed", "completed", "passed", "finished"))
    modifier = rng.choice(("quarantined", "nightly", "slow", "archived"))
    if production == "flat":
        message = flat_message(rng)
    elif production == "adjective-group-noun":
        message = f"Running the {counted} {result} {opened}{modifier}{closed} {activity}."
    elif production == "colon-group-predicate":
        message = (f"Running the {activity}: {opened}{counted} {activity}{closed} "
                   f"{result}, returning errors.")
    elif production == "predicate-group-result":
        message = f"Running the {activity} {result} {opened}{counted} errors{closed}."
    elif production == "outer-break-group":
        break_mark = rng.choice(("—", ";", ","))
        message = (f"Starting the {activity} {break_mark} {opened}nightly{closed} "
                   f"{result} earlier.")
    elif production == "nested-group":
        _inner_name, inner_open, inner_close = rng.choice(GROUPS[:3])
        message = (f"Running the {activity} {opened}{counted} {inner_open}slow{inner_close} "
                   f"{activity}{closed} {result}, returning errors.")
    elif production == "url-ending-punctuation":
        punctuation = rng.choice((",", ".", ";", ":"))
        message = (f"Starting the {activity} at https://x.test{punctuation} "
                   f"{result} checks were found earlier.")
    elif production == "empty-group":
        message = f"Running the {activity} {opened}{closed} {result}."
    elif production == "post-group-modifier":
        adverb = rng.choice(POSTGROUP_MODIFIERS)
        message = (f"Running the {activity} {opened}{modifier}{closed} "
                   f"{adverb} {result}.")
    elif production == "colon-group-result-tail":
        introducer, tail_object = rng.choice(POSTGROUP_RESULT_TAILS)
        message = (f"Running the {activity}: {result} "
                   f"{opened}{counted} errors{closed} "
                   f"{introducer} {tail_object}.")
    else:
        raise ValueError(f"unknown production {production}")
    return {"production": production, "group": group_name, "message": message}


def generate(seed: int, count: int) -> list[dict]:
    rng = random.Random(seed)
    cases = []
    for index in range(count):
        if index < len(MANDATORY_CASES):
            production, group_name = MANDATORY_CASES[index]
            group = GROUP_BY_NAME[group_name] if group_name is not None else None
        else:
            production = rng.choice(PRODUCTIONS)
            group = None
        case = generated_case(rng, production, group)
        case["index"] = index
        cases.append(case)
    return cases


def load_guard(path: Path, expected_sha256: str, logical_path: Path | None = None):
    source = path.read_bytes()
    observed_sha256 = source_bytes_digest(source)
    if observed_sha256 != expected_sha256:
        raise RuntimeError(
            f"guard source digest differs: expected {expected_sha256}, "
            f"got {observed_sha256}")
    name = f"fuzz_guard_{observed_sha256[:16]}"
    module = types.ModuleType(name)
    logical_path = path if logical_path is None else logical_path
    # The compile filename remains the user-facing logical path for tracebacks. Runtime
    # source reads through ``__file__`` must instead resolve to the captured private copy;
    # exposing the logical path lets the guard bypass the bytes this report hashes.
    module.__file__ = str(path)
    exec(compile(source, str(logical_path), "exec"), module.__dict__)
    if not callable(getattr(module, "judge", None)):
        raise RuntimeError(f"{path} has no callable judge(payload)")
    return module


def worker(path: Path, expected_sha256: str, logical_path: Path) -> int:
    try:
        guard = load_guard(path, expected_sha256, logical_path)
        messages = json.load(sys.stdin)
        if not isinstance(messages, list) or any(not isinstance(item, str) for item in messages):
            raise RuntimeError("worker input is not a list of strings")
        results = []
        for index, message in enumerate(messages):
            value = guard.judge({"hook_event_name": "Stop", "last_assistant_message": message})
            if value is not None and (not isinstance(value, str) or not value):
                raise RuntimeError(
                    f"judge result {index} is {type(value).__name__}, expected None/nonempty str")
            results.append(value)
        json.dump({"status": "completed", "source_sha256": expected_sha256,
                   "results": results}, sys.stdout,
                  ensure_ascii=False, separators=(",", ":"))
        return 0
    except Exception as exc:
        json.dump({"status": "instrument-error", "reason": type(exc).__name__,
                   "detail": str(exc)}, sys.stdout, ensure_ascii=False,
                  separators=(",", ":"))
        return 2


def run_worker(instrument: Path, path: Path, expected_sha256: str,
               messages: list[str], timeout: float,
               logical_path: Path) -> list[str | None]:
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    environment.pop("PYTHONHOME", None)
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONPYCACHEPREFIX", None)
    try:
        done = subprocess.run(
            [sys.executable, "-E", "-s", "-B", str(instrument), "--worker", str(path),
             "--expected-sha256", expected_sha256,
             "--logical-path", str(logical_path)],
            input=json.dumps(messages, ensure_ascii=False),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=environment,
            cwd=instrument.parent,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"worker timed out after {timeout}s: {path}") from exc
    try:
        payload = json.loads(done.stdout)
    except ValueError as exc:
        raise RuntimeError(f"worker emitted invalid JSON for {path}") from exc
    if (done.returncode != 0 or not isinstance(payload, dict)
            or set(payload) != {"status", "source_sha256", "results"}
            or payload.get("status") != "completed"
            or payload.get("source_sha256") != expected_sha256):
        raise RuntimeError(f"worker failed for {path}: {payload}")
    results = payload.get("results")
    if not isinstance(results, list) or len(results) != len(messages):
        raise RuntimeError(f"worker result inventory differs for {path}")
    return results


def run_snapshot_worker(label: str, instrument_source: bytes,
                        instrument_sha256: str, guard_source: bytes,
                        guard_sha256: str, logical_path: Path,
                        messages: list[str], timeout: float) -> list[str | None]:
    """Run one trust domain in a fresh snapshot and reject persistent rewrites."""
    with tempfile.TemporaryDirectory(prefix=f"fuzz-judge-{label}-") as raw:
        snapshot = Path(raw)
        instrument_copy = snapshot / "fuzz_worker.py"
        guard_copy = snapshot / "guard.py"
        instrument_copy.write_bytes(instrument_source)
        guard_copy.write_bytes(guard_source)
        if (source_digest(instrument_copy) != instrument_sha256
                or source_digest(guard_copy) != guard_sha256):
            raise RuntimeError(f"private {label} snapshot differs from captured bytes")
        results = run_worker(
            instrument_copy, guard_copy, guard_sha256, messages, timeout,
            logical_path)
        if (source_digest(instrument_copy) != instrument_sha256
                or source_digest(guard_copy) != guard_sha256):
            raise RuntimeError(
                f"private worker or guard changed during {label} execution")
        return results


def classify(oracle: str | None, candidate: str | None) -> str:
    oracle_blocks = oracle is not None
    candidate_blocks = candidate is not None
    if oracle_blocks and not candidate_blocks:
        return "block-to-allow"
    if not oracle_blocks and candidate_blocks:
        return "allow-to-block"
    if oracle_blocks and candidate_blocks and oracle != candidate:
        return "block-reason-change"
    return "agreement"


def compare(oracle_path: Path, candidate_path: Path, seed: int, count: int,
            timeout: float) -> dict:
    if oracle_path.is_symlink() or candidate_path.is_symlink():
        raise RuntimeError("oracle and candidate source paths must not be symlinks")
    oracle_path = oracle_path.resolve(strict=True)
    candidate_path = candidate_path.resolve(strict=True)
    instrument_path = Path(__file__).resolve()
    instrument_source = instrument_path.read_bytes()
    instrument_before = source_bytes_digest(instrument_source)
    oracle_source = oracle_path.read_bytes()
    candidate_source = candidate_path.read_bytes()
    before = {
        "oracle": source_bytes_digest(oracle_source),
        "candidate": source_bytes_digest(candidate_source),
    }
    cases = generate(seed, count)
    messages = [case["message"] for case in cases]
    oracle_results = run_snapshot_worker(
        "oracle", instrument_source, instrument_before,
        oracle_source, before["oracle"], oracle_path, messages, timeout)
    candidate_results = run_snapshot_worker(
        "candidate", instrument_source, instrument_before,
        candidate_source, before["candidate"], candidate_path, messages, timeout)
    after = {
        "oracle": source_digest(oracle_path),
        "candidate": source_digest(candidate_path),
    }
    if before != after:
        raise RuntimeError("compared source changed while fuzzing")
    if source_digest(instrument_path) != instrument_before:
        raise RuntimeError("fuzz instrument changed while workers were running")
    counts = {name: 0 for name in (
        "agreement", "block-to-allow", "allow-to-block", "block-reason-change")}
    results = []
    for case, oracle_result, candidate_result in zip(
            cases, oracle_results, candidate_results):
        classification = classify(oracle_result, candidate_result)
        counts[classification] += 1
        results.append({
            **case,
            "oracle": oracle_result,
            "candidate": candidate_result,
            "classification": classification,
        })
    return {
        "schema_version": SCHEMA_VERSION,
        "instrument_sha256": instrument_before,
        "seed": seed,
        "requested_count": count,
        "generated_count": len(cases),
        "oracle": {"path": str(oracle_path.resolve()), "sha256": before["oracle"]},
        "candidate": {"path": str(candidate_path.resolve()), "sha256": before["candidate"]},
        "grammar_sha256": digest(grammar_payload()),
        "generated_messages_sha256": digest(messages),
        "production_counts": {
            production: sum(case["production"] == production for case in cases)
            for production in PRODUCTIONS
        },
        "group_counts": {
            group[0]: sum(case["group"] == group[0] for case in cases)
            for group in GROUPS
        },
        "counts": counts,
        "results": results,
    }


def selftest() -> int:
    checks = failures = 0

    def check(label: str, condition: bool) -> None:
        nonlocal checks, failures
        checks += 1
        failures += int(not condition)
        print(f"  {'PASS' if condition else 'FAIL'} {label}")

    check("block-to-allow is isolated", classify("Starting the", None) == "block-to-allow")
    check("allow-to-block is isolated", classify(None, "Starting the") == "allow-to-block")
    check("reason drift is not a verdict divergence",
          classify("Starting the", "Running the") == "block-reason-change")
    check("matching verdicts agree", classify(None, None) == "agreement")
    first = generate(17, MIN_CASES + 8)
    second = generate(17, MIN_CASES + 8)
    check("the same seed generates byte-identical cases", first == second)
    check("every mandatory production is generated before random remainder",
          {case["production"] for case in first[:MIN_CASES]} == set(PRODUCTIONS))
    check("the mandatory prefix exercises every supported group spelling",
          {case["group"] for case in first[:MIN_CASES] if case["group"] is not None}
          == {group[0] for group in GROUPS})
    check("every recorded mandatory group is rendered in its generated message",
          all(case["group"] is None
              or (GROUP_BY_NAME[case["group"]][1] in case["message"]
                  and GROUP_BY_NAME[case["group"]][2] in case["message"])
              for case in first[:MIN_CASES]))
    with tempfile.TemporaryDirectory(prefix="fuzz-selftest-") as raw:
        root = Path(raw)
        guard = root / "guard.py"
        guard.write_text(
            "def judge(payload):\n"
            "    return 'Starting the' if payload['last_assistant_message'].startswith('Starting') else None\n",
            encoding="utf-8",
        )
        report = compare(guard, guard, 9, MIN_CASES, 5)
        check("isolated workers preserve identical verdicts",
              report["counts"]["block-to-allow"] == 0
              and report["counts"]["allow-to-block"] == 0)
        check("the report retains every generated case",
              len(report["results"]) == report["generated_count"] == MIN_CASES)
        check("instrument, source, and grammar digests are recorded",
              report["oracle"]["sha256"] == source_digest(guard)
              and len(report["instrument_sha256"]) == 64
              and len(report["grammar_sha256"]) == 64)
        check("the report records nonzero production and group coverage",
              all(report["production_counts"].values())
              and all(report["group_counts"].values()))
        guard_link = root / "guard-link.py"
        guard_link.symlink_to(guard)
        try:
            compare(guard_link, guard, 9, MIN_CASES, 5)
            rejected_source_link = False
        except RuntimeError:
            rejected_source_link = True
        check("comparison rejects symlinked source paths", rejected_source_link)
        path_guard = root / "path-guard.py"
        path_guard.write_text(
            "import hashlib\n"
            "from pathlib import Path\n"
            "def judge(payload):\n"
            "    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()\n",
            encoding="utf-8")
        pristine_path_guard = path_guard.read_bytes()
        expected_path_digest = source_bytes_digest(pristine_path_guard)
        original_run_worker = run_worker

        def run_while_logical_source_changes(
                instrument, path, expected_sha256, messages, timeout, logical_path):
            logical_path.write_text(
                "def judge(payload): return 'unbound-original'\n", encoding="utf-8")
            try:
                return original_run_worker(
                    instrument, path, expected_sha256, messages, timeout, logical_path)
            finally:
                logical_path.write_bytes(pristine_path_guard)

        globals()["run_worker"] = run_while_logical_source_changes
        try:
            path_report = compare(path_guard, path_guard, 9, MIN_CASES, 5)
        finally:
            globals()["run_worker"] = original_run_worker
            path_guard.write_bytes(pristine_path_guard)
        check("runtime __file__ reads stay bound to the captured private guard",
              path_report["counts"]["block-reason-change"] == 0
              and path_report["counts"]["agreement"] == MIN_CASES
              and all(item["oracle"] == expected_path_digest
                      and item["candidate"] == expected_path_digest
                      for item in path_report["results"]))
        cwd_guard = root / "cwd-path-guard.py"
        cwd_guard.write_text(
            "import hashlib, os\n"
            "from pathlib import Path\n"
            "def judge(payload):\n"
            "    os.chdir(Path(judge.__code__.co_filename).parent)\n"
            "    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()\n",
            encoding="utf-8")
        expected_cwd_digest = source_digest(cwd_guard)
        cwd_report = compare(cwd_guard, cwd_guard, 9, MIN_CASES, 5)
        check("runtime __file__ stays bound after a guard changes cwd",
              cwd_report["counts"]["agreement"] == MIN_CASES
              and all(item["oracle"] == expected_cwd_digest
                      and item["candidate"] == expected_cwd_digest
                      for item in cwd_report["results"]))
        try:
            load_guard(guard, "0" * 64)
            rejected_digest_drift = False
        except RuntimeError:
            rejected_digest_drift = True
        check("a worker refuses source bytes outside its expected digest",
              rejected_digest_drift)
        pristine_guard = guard.read_bytes()
        original_run_worker = run_worker

        def run_during_transient_change(
                instrument, path, expected_sha256, messages, timeout, logical_path):
            guard.write_text("def judge(payload): return 'transient'\n", encoding="utf-8")
            try:
                return original_run_worker(
                    instrument, path, expected_sha256, messages, timeout, logical_path)
            finally:
                guard.write_bytes(pristine_guard)

        globals()["run_worker"] = run_during_transient_change
        try:
            transient_report = compare(guard, guard, 9, MIN_CASES, 5)
        finally:
            globals()["run_worker"] = original_run_worker
            guard.write_bytes(pristine_guard)
        check("workers execute captured snapshots across transient source changes",
              transient_report["counts"]["agreement"] == MIN_CASES
              and transient_report["oracle"]["sha256"]
              == source_bytes_digest(pristine_guard)
              and any(item["oracle"] == "Starting the"
                      for item in transient_report["results"])
              and all(item["oracle"] != "transient"
                      and item["candidate"] != "transient"
                      for item in transient_report["results"]))
        fake_worker = (
            "import json, sys\n"
            "expected = sys.argv[sys.argv.index('--expected-sha256') + 1]\n"
            "messages = json.load(sys.stdin)\n"
            "json.dump({'status': 'completed', 'source_sha256': expected, "
            "'results': [None] * len(messages)}, sys.stdout)\n"
        )
        poison_guard = root / "poison-worker.py"
        poison_guard.write_text(
            "import sys\n"
            "from pathlib import Path\n"
            f"Path(sys.argv[0]).write_text({fake_worker!r}, encoding='utf-8')\n"
            "def judge(payload): return 'Starting the'\n",
            encoding="utf-8",
        )
        try:
            compare(poison_guard, guard, 9, MIN_CASES, 5)
            rejected_worker_rewrite = False
        except RuntimeError as exc:
            rejected_worker_rewrite = (
                "private worker or guard changed during oracle execution" in str(exc))
        check("an oracle cannot rewrite the worker later used for the candidate",
              rejected_worker_rewrite)
        seam_mutant = root / "seam-mutant.py"
        seam_mutant.write_text(
            "def judge(payload):\n"
            "    message = payload['last_assistant_message']\n"
            "    return 'Running the' if any(f' {word} ' in message for word in "
            "('finally', 'gracefully', 'locally', 'quickly', 'reliably', "
            "'silently', 'unexpectedly')) else None\n",
            encoding="utf-8",
        )
        seam_report = compare(guard, seam_mutant, 9, MIN_CASES, 5)
        check("the grammar exposes a post-group modifier bridge regression",
              seam_report["counts"]["allow-to-block"] > 0
              and any(item["production"] == "post-group-modifier"
                      and item["classification"] == "allow-to-block"
                      for item in seam_report["results"]))
        tail_mutant = root / "tail-mutant.py"
        tail_mutant.write_text(
            "def judge(payload):\n"
            "    message = payload['last_assistant_message']\n"
            "    return 'Running the' if any(f') {word} ' in message for word in "
            "('after', 'at', 'with')) else None\n",
            encoding="utf-8",
        )
        tail_report = compare(guard, tail_mutant, 9, MIN_CASES, 5)
        check("the grammar exposes a grouped-result tail regression",
              tail_report["counts"]["allow-to-block"] > 0
              and any(item["production"] == "colon-group-result-tail"
                      and item["classification"] == "allow-to-block"
                      for item in tail_report["results"]))
        fail_open = root / "fail-open.py"
        fail_open.write_text("def judge(payload): return None\n", encoding="utf-8")
        fail_open_report = compare(guard, fail_open, 9, MIN_CASES, 5)
        check("the worker and grammar retain fail-open verdict divergences",
              fail_open_report["counts"]["block-to-allow"] > 0
              and any(item["classification"] == "block-to-allow"
                      for item in fail_open_report["results"]))
        main_stdout, main_stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(main_stdout), contextlib.redirect_stderr(main_stderr):
            fail_open_exit = main([
                str(guard), str(fail_open), "9", str(MIN_CASES), "--timeout", "5",
            ])
        check("the CLI exits one when a fail-open divergence is retained",
              fail_open_exit == 1 and "block_to_allow=" in main_stderr.getvalue()
              and "exit=1" in main_stderr.getvalue())
        invalid = root / "invalid.py"
        invalid.write_text("def judge(payload): return False\n", encoding="utf-8")
        try:
            compare(invalid, guard, 1, MIN_CASES, 5)
            rejected = False
        except RuntimeError:
            rejected = True
        check("an invalid judge return is an instrument error", rejected)
        retained = compare(guard, guard, 11, 30, 5)
        check("machine output has no twenty-five-case truncation",
              retained["requested_count"] == retained["generated_count"]
              == len(retained["results"]) == 30)
        check("private compilation leaves no bytecode beside compared sources",
              not (root / "__pycache__").exists())
    check("the case-count cap bounds one worker allocation", MAX_CASES == 100_000)
    print(f"SELFTEST-SUMMARY suite=fuzz-judge-diff checks={checks} failures={failures}")
    return failures


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("oracle", nargs="?", type=Path)
    parser.add_argument("candidate", nargs="?", type=Path)
    parser.add_argument("seed", nargs="?", type=int)
    parser.add_argument("count", nargs="?", type=int)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--worker", type=Path)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--logical-path", type=Path)
    parser.add_argument("--selftest", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.worker is not None:
        if args.expected_sha256 is None or args.logical_path is None:
            print("--worker requires --expected-sha256 and --logical-path", file=sys.stderr)
            return 2
        return worker(args.worker, args.expected_sha256, args.logical_path)
    if args.selftest:
        return 1 if selftest() else 0
    if None in (args.oracle, args.candidate, args.seed, args.count):
        print("oracle, candidate, seed, and count are required", file=sys.stderr)
        return 2
    if not 0 <= args.seed < 2 ** 64:
        print("seed must be an unsigned 64-bit integer", file=sys.stderr)
        return 2
    if not MIN_CASES <= args.count <= MAX_CASES:
        print(f"count must be between {MIN_CASES} and {MAX_CASES}", file=sys.stderr)
        return 2
    if args.timeout <= 0:
        print("--timeout must be positive", file=sys.stderr)
        return 2
    try:
        report = compare(args.oracle, args.candidate, args.seed, args.count, args.timeout)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"FUZZ-ERROR {exc}", file=sys.stderr)
        return 2
    json.dump(report, sys.stdout, sort_keys=True, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    counts = report["counts"]
    exit_code = 1 if counts["block-to-allow"] else 0
    print(
        f"FUZZ-SUMMARY seed={args.seed} count={args.count} "
        f"block_to_allow={counts['block-to-allow']} "
        f"allow_to_block={counts['allow-to-block']} "
        f"reason_changes={counts['block-reason-change']} exit={exit_code}",
        file=sys.stderr,
    )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
