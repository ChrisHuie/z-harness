#!/usr/bin/env python3
"""Reproducible differential fuzzing over isolated Stop-guard judge processes.

The complete machine-readable report is written to stdout. Verdict direction is separate
from block-reason drift, every generated case is retained, and the report binds the seed,
grammar, generated messages, and both compared sources by SHA-256.
"""
from __future__ import annotations

import argparse
import ast
import copy
import contextlib
import hashlib
import io
import json
import math
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import types


# 2: the report gained oracle_blocks, the count that says whether a clean verdict was
# measured or merely entailed. Additive, but the shape changed, so the version does too.
SCHEMA_VERSION = 2
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
    "post-group-context",
    "colon-bridge-report",
    "post-group-near-miss",
    "colon-context-near-miss",
    "report-term-near-miss",
    "grouped-historical-subject",
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
    "post-group-context",
    "post-group-near-miss",
    "grouped-historical-subject",
})
POSTGROUP_MODIFIERS = (
    "finally", "gracefully", "locally", "quickly", "reliably", "silently",
    "unexpectedly",
)
# The guard admits a bounded environment adjunct between a closed aside and the activity's
# predicate, and ten completed-work verbs that are NOT prenominal adjectives. The context
# adjunct had no production at all. The verbs fared differently: four reached only `flat`,
# five reached no production, and `found` was spelled into the url-ending-punctuation
# string -- but none of them landed where a bridged predicate is read, which is the position
# that matters. Generating an in-table token detects that table NARROWING.
#
# The near-miss tuples below give the WIDENING direction for REPORT_POSTGROUP_MODIFIERS,
# REPORT_POSTGROUP_CONTEXTS and REPORT_TERMS: each token is pinned, so admitting one of them
# diverges at the minimum case count. That is a guarantee for those three tables and those
# tokens, and it is the only guarantee here. Widening anything else may or may not diverge,
# depending on whether some grammar string happens to spell the admitted token into a
# position the guard reads -- measured, `REPORT_ACTIVITY_HEADS` widened with `three` is
# caught that way, and `REPORT_TERMS` widened with a non-near-miss token is too. Do not read
# a clean run over an unpinned table as coverage.
POSTGROUP_CONTEXTS = (
    ("in", "CI"), ("in", "production"), ("in", "staging"),
    ("on", "GitHub"), ("on", "macos"),
)
# The tokens these contribute -- the adverbs, the context OBJECTS, the report verbs -- sit
# outside every uppercase collection in the guard on purpose, not merely outside the table
# each probes, because a token carrying meaning in a sibling table can block for that reason
# instead and score a control that cannot fail. The context PREPOSITIONS (`in`, `on`) are
# necessarily the guard's own: they are the keys its context table is indexed by. A grammar seeded only from
# the tables it tests can detect a narrowed table (a generated token stops being admitted)
# but never a widened one, because it never emits the token a widening would newly admit --
# the same blind spot a deletion-only mutation operator has. These near-misses are the allow-direction
# control: each must block today, and starts allowing the moment its table grows to cover it.
NEAR_MISS_TERMS = ("emitted", "surfaced", "yielded")
NEAR_MISS_MODIFIERS = ("hastily", "briskly", "loudly", "oddly", "wearily")
NEAR_MISS_CONTEXTS = (("in", "qa"), ("in", "docker"), ("on", "sandbox"), ("on", "disk"))
NONADJECTIVAL_TERMS = (
    "found", "landed", "produced", "ran", "reproduced",
    "returned", "showed", "stayed", "took", "wrote",
)
# Maps each near-miss production to the tuple its `pin` indexes, so the prefix-coverage
# check reads the same pairing `generated_case` does rather than a second copy of it.
MANDATORY_VOCABULARIES = {
    "post-group-near-miss": NEAR_MISS_MODIFIERS,
    "colon-context-near-miss": NEAR_MISS_CONTEXTS,
    "report-term-near-miss": NEAR_MISS_TERMS,
}
POSTGROUP_RESULT_TAILS = (
    ("after", "4m"),
    ("at", "12:04"),
    ("with", "a traceback"),
)
GROUPED_HISTORICAL_SUFFIXES = ("", " unexpectedly", " in CI")
# Every production runs once, and every recorded group is rendered in the message.
# The three post-group-modifier entries close the delimiter inventory the production
# inventory leaves open; the near-miss entries after them pin vocabulary, not delimiters.
MANDATORY_CASES = (
    ('flat', None, None),
    ('adjective-group-noun', 'parenthetical', None),
    ('colon-group-predicate', 'bracketed', None),
    ('predicate-group-result', 'braced', None),
    ('outer-break-group', 'curly-double', None),
    ('nested-group', 'curly-single', None),
    ('url-ending-punctuation', None, None),
    ('empty-group', 'straight-double', None),
    ('post-group-modifier', 'straight-single', None),
    ('post-group-modifier', 'inline-code', None),
    ('post-group-modifier', 'double-inline-code', None),
    ('colon-group-result-tail', 'parenthetical', None),
    ('post-group-context', 'parenthetical', None),
    ('colon-bridge-report', None, None),
    ('post-group-near-miss', 'parenthetical', 0),
    ('post-group-near-miss', 'parenthetical', 1),
    ('post-group-near-miss', 'parenthetical', 2),
    ('post-group-near-miss', 'parenthetical', 3),
    ('post-group-near-miss', 'parenthetical', 4),
    ('colon-context-near-miss', None, 0),
    ('colon-context-near-miss', None, 1),
    ('colon-context-near-miss', None, 2),
    ('colon-context-near-miss', None, 3),
    ('report-term-near-miss', None, 0),
    ('report-term-near-miss', None, 1),
    ('report-term-near-miss', None, 2),
) + tuple(
    ('grouped-historical-subject', group_name, suffix_index)
    for group_name, _opened, _closed in GROUPS
    for suffix_index in range(len(GROUPED_HISTORICAL_SUFFIXES))
)
FLAT_SHARE = 0.35
# Drawing the non-flat case from PRODUCTIONS re-drew `flat`, so the realized share was
# FLAT_SHARE + (1 - FLAT_SHARE)/len(PRODUCTIONS) and still shrank as productions were
# added -- a floor, not the pin the share is meant to be.
STRUCTURED_PRODUCTIONS = tuple(p for p in PRODUCTIONS if p != "flat")
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
        "postgroup_contexts": POSTGROUP_CONTEXTS,
        "nonadjectival_terms": NONADJECTIVAL_TERMS,
        "near_miss_modifiers": NEAR_MISS_MODIFIERS,
        "near_miss_contexts": NEAR_MISS_CONTEXTS,
        "near_miss_terms": NEAR_MISS_TERMS,
        "grouped_historical_suffixes": GROUPED_HISTORICAL_SUFFIXES,
        "mandatory_cases": MANDATORY_CASES,
        "flat_share": FLAT_SHARE,
    }


def flat_message(rng: random.Random) -> str:
    parts = [rng.choice(OPENERS)]
    for _ in range(rng.randint(1, 14)):
        parts.append(rng.choice(JOINERS))
        parts.append(rng.choice(WORDS))
    return "".join(parts) + rng.choice(TAILS)


def generated_case(rng: random.Random, production: str, group=None,
                   pin: int | None = None) -> dict:
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
    elif production == "post-group-context":
        preposition, obj = rng.choice(POSTGROUP_CONTEXTS)
        message = (f"Running the {activity} {opened}{modifier}{closed} "
                   f"{preposition} {obj} {result}.")
    elif production == "colon-bridge-report":
        adverb = rng.choice(POSTGROUP_MODIFIERS)
        term = rng.choice(NONADJECTIVAL_TERMS)
        message = (f"Starting the {activity}: {adverb} {term} {counted} "
                   f"{activity} are listed.")
    elif production == "post-group-near-miss":
        adverb = (MANDATORY_VOCABULARIES["post-group-near-miss"][pin] if pin is not None
                  else rng.choice(MANDATORY_VOCABULARIES["post-group-near-miss"]))
        message = (f"Running the {activity} {opened}{modifier}{closed} "
                   f"{adverb} {result}.")
    elif production == "report-term-near-miss":
        term = (MANDATORY_VOCABULARIES["report-term-near-miss"][pin] if pin is not None else rng.choice(MANDATORY_VOCABULARIES["report-term-near-miss"]))
        message = f"Running the {activity} {term} {counted} errors."
    elif production == "colon-context-near-miss":
        preposition, obj = (MANDATORY_VOCABULARIES["colon-context-near-miss"][pin] if pin is not None
                            else rng.choice(MANDATORY_VOCABULARIES["colon-context-near-miss"]))
        message = f"Starting the {activity}: {preposition} {obj} {result}."
    elif production == "grouped-historical-subject":
        suffix = (GROUPED_HISTORICAL_SUFFIXES[pin] if pin is not None
                  else rng.choice(GROUPED_HISTORICAL_SUFFIXES))
        message = (f"Starting the {activity}: {opened}the prior run{closed}"
                   f"{suffix} {result}.")
    else:
        raise ValueError(f"unknown production {production}")
    return {"production": production, "group": group_name, "message": message}


def generate(seed: int, count: int) -> list[dict]:
    rng = random.Random(seed)
    cases = []
    for index in range(count):
        if index < len(MANDATORY_CASES):
            production, group_name, pin = MANDATORY_CASES[index]
            group = GROUP_BY_NAME[group_name] if group_name is not None else None
        else:
            # `flat` is the only arm that emits tokens no structured production spells, so
            # its share is pinned rather than left to shrink each time a production is
            # added. Adding one used to shrink that share silently; whether any past
            # addition cost detection was neither measured nor established.
            production = ("flat" if rng.random() < FLAT_SHARE
                          else rng.choice(STRUCTURED_PRODUCTIONS))
            group, pin = None, None
        case = generated_case(rng, production, group, pin)
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
    exit_code = 0
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
        payload = {"status": "completed", "source_sha256": expected_sha256,
                   "results": results}
    except BaseException as exc:
        payload = {"status": "instrument-error", "reason": type(exc).__name__,
                   "detail": str(exc)}
        exit_code = 2
    emitted, _output_error = emit_report(sys.stdout, payload, pretty=False)
    return exit_code if emitted else 2


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


def guard_table_literal(tree: ast.Module, table_name: str,
                        context_key: str | None = None) -> ast.Set:
    """Return one parsed frozenset literal owned by a named guard table."""
    assignments = [
        node for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == table_name
                for target in node.targets)
    ]
    if len(assignments) != 1:
        raise RuntimeError(f"expected one assignment for {table_name}, got {len(assignments)}")
    value = assignments[0].value
    if context_key is not None:
        if not isinstance(value, ast.Dict):
            raise RuntimeError(f"{table_name} is not a literal dictionary")
        matches = [item for key, item in zip(value.keys, value.values)
                   if isinstance(key, ast.Constant) and key.value == context_key]
        if len(matches) != 1:
            raise RuntimeError(
                f"expected one {table_name}[{context_key!r}] entry, got {len(matches)}")
        value = matches[0]
    if (not isinstance(value, ast.Call) or not isinstance(value.func, ast.Name)
            or value.func.id != "frozenset" or len(value.args) != 1
            or not isinstance(value.args[0], ast.Set)):
        raise RuntimeError(f"{table_name} target is not a literal frozenset")
    return value.args[0]


def widen_guard_table(source: bytes, table_name: str, token: str,
                      context_key: str | None = None) -> bytes:
    """Add one literal to one shipped guard table using its parsed source span."""
    text = source.decode("utf-8")
    tree = ast.parse(text)
    literal_set = guard_table_literal(tree, table_name, context_key)
    members = [item.value for item in literal_set.elts
               if isinstance(item, ast.Constant) and isinstance(item.value, str)]
    if len(members) != len(literal_set.elts) or token in members:
        raise RuntimeError(f"{table_name} cannot be widened with {token!r}")
    lines = text.splitlines(keepends=True)
    line_index = literal_set.end_lineno - 1
    closing = literal_set.end_col_offset - 1
    if lines[line_index][closing] != "}":
        raise RuntimeError(f"{table_name} parsed span does not end at its set closer")
    offset = sum(len(line) for line in lines[:line_index]) + closing
    separator = "" if text[:offset].rstrip().endswith(",") else ","
    widened = text[:offset] + f"{separator} {token!r}," + text[offset:]
    widened_tree = ast.parse(widened)
    widened_set = guard_table_literal(widened_tree, table_name, context_key)
    added = [item for item in widened_set.elts
             if isinstance(item, ast.Constant) and item.value == token]
    if len(added) != 1 or len(widened_set.elts) != len(literal_set.elts) + 1:
        raise RuntimeError(f"{table_name} widening did not add exactly one literal")
    normalized = copy.deepcopy(widened_tree)
    normalized_set = guard_table_literal(normalized, table_name, context_key)
    normalized_set.elts = [item for item in normalized_set.elts
                           if not (isinstance(item, ast.Constant)
                                   and item.value == token)]
    if ast.dump(normalized, include_attributes=False) != ast.dump(
            tree, include_attributes=False):
        raise RuntimeError(f"{table_name} widening changed more than one AST literal")
    return widened.encode("utf-8")


def silence_failed_stream(stream) -> None:
    """Prevent interpreter-shutdown retries from turning a handled pipe fault into 120."""
    try:
        descriptor = stream.fileno()
        replacement = os.open(os.devnull, os.O_WRONLY)
        try:
            os.dup2(replacement, descriptor)
        finally:
            os.close(replacement)
    except (AttributeError, OSError, ValueError):
        pass


def write_all(stream, content: str) -> None:
    """Write and flush one prebuilt payload, honoring short-write semantics."""
    offset = 0
    while offset < len(content):
        written = stream.write(content[offset:])
        remaining = len(content) - offset
        if (not isinstance(written, int) or isinstance(written, bool)
                or written <= 0 or written > remaining):
            raise OSError(f"stream accepted invalid character count {written!r}")
        offset += written
    stream.flush()


def emit_line(stream, message: str) -> bool:
    if stream is None or getattr(stream, "closed", False):
        return False
    try:
        write_all(stream, message + "\n")
        return True
    except (OSError, UnicodeError, ValueError):
        silence_failed_stream(stream)
        return False


def emit_report(stream, report: dict,
                pretty: bool = True) -> tuple[bool, Exception | None]:
    if stream is None or getattr(stream, "closed", False):
        return False, RuntimeError("stdout is unavailable")
    try:
        serialized = json.dumps(
            report,
            sort_keys=pretty,
            indent=2 if pretty else None,
            ensure_ascii=False,
            separators=None if pretty else (",", ":"),
        ) + "\n"
        write_all(stream, serialized)
        return True, None
    except (OSError, UnicodeError, ValueError, TypeError, AttributeError) as exc:
        silence_failed_stream(stream)
        return False, exc


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
    oracle_blocks = 0
    results = []
    for case, oracle_result, candidate_result in zip(
            cases, oracle_results, candidate_results):
        classification = classify(oracle_result, candidate_result)
        counts[classification] += 1
        oracle_blocks += oracle_result is not None
        results.append({
            **case,
            "oracle": oracle_result,
            "candidate": candidate_result,
            "classification": classification,
        })
    if not oracle_blocks:
        # Without one oracle block every classification collapses to agreement or
        # allow-to-block, so "no block-to-allow divergence" is entailed by the run rather
        # than measured by it. The `counts` block is then identical to a real clean
        # comparison, so before this check existed the summary line could not tell them
        # apart even though the full reports differed elsewhere. The sibling instrument refuses a non-green
        # baseline for the same reason. Fail as an instrument error, not as a verdict.
        raise RuntimeError(
            f"oracle blocked none of {len(cases)} generated cases, so this run has no "
            "power to detect a block-to-allow divergence")
    return {
        "schema_version": SCHEMA_VERSION,
        "instrument_sha256": instrument_before,
        "oracle_blocks": oracle_blocks,
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

    # First, because every later check calls generate(), which indexes this map. A dropped
    # entry raised KeyError out of the first comparison with no receipt line printed at all.
    check("the vocabulary map covers exactly the near-miss productions",
          set(MANDATORY_VOCABULARIES) ==
          {production for production in PRODUCTIONS if production.endswith("near-miss")})
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
        # A widened table is the fail-open direction, and it is invisible unless the grammar
        # emits a token from OUTSIDE that table WHERE that table is read. This shipped
        # broken once: off-table words existed in the vocabulary but never landed in a
        # predicate position, so widening read clean at any case count. The
        # oracle blocks everything and the candidate admits the off-table report verbs, which
        # is what a table widened by one token does; the divergence proves the grammar puts
        # such a token where a report predicate is read.
        # Both properties the near-miss tuples rest on are structural, so assert them
        # structurally: a token that is not pinned is emitted only by chance, and a token
        # that also lives in an in-table vocabulary probes nothing. Without these, adding a
        # near-miss without its pin, or copying one from the table it is meant to sit
        # outside, leaves a control that cannot fail and a suite that still reports green.
        pinned = {(production, MANDATORY_VOCABULARIES[production][pin])
                  for production, _group, pin in MANDATORY_CASES
                  if pin is not None and production in MANDATORY_VOCABULARIES}
        unpinned = {(production, token)
                    for production, tokens in MANDATORY_VOCABULARIES.items()
                    for token in tokens} - pinned
        check("every near-miss token is pinned in the deterministic prefix", not unpinned)
        # Pins index their vocabulary, so a desync is an IndexError at generation time. Assert
        # the exact pin set per production: this reddens on a shrunk vocabulary, a grown one,
        # and a dropped pin, where a one-directional check would miss two of the three.
        pins = {}
        for production, _group, pin in MANDATORY_CASES:
            if production in MANDATORY_VOCABULARIES and pin is not None:
                pins.setdefault(production, []).append(pin)
        check("each near-miss vocabulary is pinned by exactly its own index range",
              all(sorted(pins.get(name, [])) == list(range(len(tokens)))
                  for name, tokens in MANDATORY_VOCABULARIES.items()))
        # A pin that is accepted and then ignored leaves the prefix looking covered while the
        # token it names never appears.
        # generate() indexes the vocabularies, so a desync raises here rather than failing a
        # check. The range assertion above runs first so the suite reports the cause.
        prefix = generate(9, MIN_CASES)
        honoured = []
        for index, (production, _group, pin) in enumerate(MANDATORY_CASES):
            if production not in MANDATORY_VOCABULARIES or pin is None:
                continue
            token = MANDATORY_VOCABULARIES[production][pin]
            wanted = token if isinstance(token, str) else token[1]
            honoured.append(wanted in prefix[index]["message"])
        check("each pinned mandatory case renders the token its pin names", all(honoured))
        # Two assertions, because comparing the realized share against FLAT_SHARE alone
        # grades the code against the very constant a mutation moves: at 0.0 and at 1.0 the
        # measurement tracks the constant perfectly and the check passes while the random
        # arm is gone. Pin the constant to a band first, then pin the code to the constant.
        check("FLAT_SHARE leaves both the random and structured arms represented",
              0.2 <= FLAT_SHARE <= 0.5)
        # The floor's effect is (1 - FLAT_SHARE)/len(PRODUCTIONS), which was SMALLER than
        # the sampling tolerance below -- so the statistical arm alone passed on the exact
        # defect it names. Assert the structure that makes the floor unreachable.
        check("the structured draw cannot re-draw the random arm",
              "flat" not in STRUCTURED_PRODUCTIONS
              and set(STRUCTURED_PRODUCTIONS) | {"flat"} == set(PRODUCTIONS))
        share = generate(11, 20000)[MIN_CASES:]
        realized = sum(case["production"] == "flat" for case in share) / len(share)
        check("the random tail honours FLAT_SHARE rather than a floor or a takeover",
              abs(realized - FLAT_SHARE) < 0.02)
        check("the report schema version tracks the report shape",
              SCHEMA_VERSION == 2 and "oracle_blocks" in report)

        in_table = {token for tokens in (POSTGROUP_MODIFIERS, NONADJECTIVAL_TERMS, WORDS,
                                         OPENERS, JOINERS, TAILS)
                    for token in tokens}
        in_table |= {obj for _prep, obj in POSTGROUP_CONTEXTS}
        in_table |= {obj for _intro, obj in POSTGROUP_RESULT_TAILS}
        near_miss = {t for t in NEAR_MISS_MODIFIERS} | {t for t in NEAR_MISS_TERMS}
        near_miss |= {obj for _prep, obj in NEAR_MISS_CONTEXTS}
        overlap = sorted({t for t in near_miss if t.casefold() in
                          {v.casefold() for v in in_table}})
        check("no near-miss token also appears in an in-table vocabulary", not overlap)
        # Every check above grades this file against its own constants. The near-miss
        # tuples are only worth anything relative to the GUARD's tables, and this file
        # carries partial copies of those -- 7 of 24 modifiers, 10 of 14 terms, 5 of 15
        # context pairs. A near-miss token drawn from the 17 modifiers this file does not
        # copy passes every self-referential check and is a permanently dead control. Bind
        # the claim to the artifact: each near-miss case must actually block under the
        # shipped guard. Skipped, with the reason recorded, when the guard is not beside us,
        # so the instrument still runs against an arbitrary pair of judges.
        shipped_guard = Path(__file__).resolve().parent.parent / "hooks/announced_work_guard.py"
        widening_results = {"modifiers": [], "contexts": [], "terms": []}
        grouped_historical_blocks = []
        grouped_historical_mutant_exposed = False
        if shipped_guard.exists():
            judged = load_guard(shipped_guard, source_digest(shipped_guard))
            near_miss_cases = [
                case for index, case in enumerate(generate(9, MIN_CASES))
                if MANDATORY_CASES[index][0] in MANDATORY_VOCABULARIES]
            blocked = [judged.judge({"last_assistant_message": case["message"]}) is not None
                       for case in near_miss_cases]
            check("every near-miss case blocks under the shipped guard",
                  len(blocked) == sum(len(v) for v in MANDATORY_VOCABULARIES.values())
                  and all(blocked))
            grouped_historical = [
                case for index, case in enumerate(generate(9, MIN_CASES))
                if MANDATORY_CASES[index][0] == "grouped-historical-subject"
            ]
            grouped_historical_blocks = [
                judged.judge({"last_assistant_message": case["message"]}) is not None
                for case in grouped_historical
            ]

            shipped_source = shipped_guard.read_bytes()

            def exercises_actual_widening(table, token, production, context_key=None):
                # Mutation power and worker isolation are separate contracts. The worker
                # path is exercised below; loading each private one-literal mutant here
                # avoids two fresh interpreter starts per token while retaining the exact
                # generated-case and block-to-allow classification used by the report.
                candidate = root / f"widened-{table.lower()}-{token}.py"
                candidate_source = widen_guard_table(
                    shipped_source, table, token, context_key)
                candidate.write_bytes(candidate_source)
                candidate_sha256 = source_bytes_digest(candidate_source)
                widened = load_guard(candidate, candidate_sha256, shipped_guard)
                exposed = any(
                    case["production"] == production
                    and token.casefold() in case["message"].casefold()
                    and classify(
                        judged.judge({"last_assistant_message": case["message"]}),
                        widened.judge({"last_assistant_message": case["message"]}),
                    ) == "block-to-allow"
                    for case in prefix
                )
                if source_digest(candidate) != candidate_sha256:
                    raise RuntimeError(f"widened guard changed during {table} evaluation")
                return exposed

            widening_results["modifiers"] = [
                exercises_actual_widening(
                    "REPORT_POSTGROUP_MODIFIERS", token, "post-group-near-miss")
                for token in NEAR_MISS_MODIFIERS
            ]
            widening_results["contexts"] = [
                exercises_actual_widening(
                    "REPORT_POSTGROUP_CONTEXTS", obj, "colon-context-near-miss", prep)
                for prep, obj in NEAR_MISS_CONTEXTS
            ]
            widening_results["terms"] = [
                exercises_actual_widening(
                    "REPORT_TERMS", token, "report-term-near-miss")
                for token in NEAR_MISS_TERMS
            ]
            historical_anchor = (
                b"        if word in REPORT_TERMS:\n"
                b"            if grouped_historical_subject:\n"
                b"                return False"
            )
            historical_replacement = (
                b"        if word in REPORT_TERMS:\n"
                b"            if False and grouped_historical_subject:\n"
                b"                return False"
            )
            if shipped_source.count(historical_anchor) == 1:
                historical_mutant = root / "grouped-historical-subject-mutant.py"
                historical_source = shipped_source.replace(
                    historical_anchor, historical_replacement, 1)
                historical_mutant.write_bytes(historical_source)
                historical_sha256 = source_bytes_digest(historical_source)
                historical_judge = load_guard(
                    historical_mutant, historical_sha256, shipped_guard)
                grouped_historical_mutant_exposed = any(
                    classify(
                        judged.judge({"last_assistant_message": case["message"]}),
                        historical_judge.judge(
                            {"last_assistant_message": case["message"]}),
                    ) == "block-to-allow"
                    for case in grouped_historical
                )
                if source_digest(historical_mutant) != historical_sha256:
                    raise RuntimeError("historical guard changed during evaluation")
        else:
            # Fail rather than skip. A silent pass here would report the binding as verified
            # in exactly the copied-tree setup a reviewer uses to mutate this file, which is
            # where a dead control most needs to be visible.
            check("the shipped guard is beside this file, so the near-miss binding is"
                  " verifiable", False)
        check("grouped historical-subject productions block under the shipped guard",
              len(grouped_historical_blocks)
              == len(GROUPS) * len(GROUPED_HISTORICAL_SUFFIXES)
              and all(grouped_historical_blocks))
        check("grouped historical-subject productions expose the ownership mutant",
              grouped_historical_mutant_exposed)
        for token, exposed in zip(NEAR_MISS_MODIFIERS,
                                  widening_results["modifiers"]):
            check(f"actual modifier-table widening exposes {token!r}", exposed)
        for (_prep, obj), exposed in zip(NEAR_MISS_CONTEXTS,
                                         widening_results["contexts"]):
            check(f"actual context-table widening exposes {obj!r}", exposed)
        for token, exposed in zip(NEAR_MISS_TERMS, widening_results["terms"]):
            check(f"actual report-table widening exposes {token!r}", exposed)
        fail_open = root / "fail-open.py"
        fail_open.write_text("def judge(payload): return None\n", encoding="utf-8")
        fail_open_report = compare(guard, fail_open, 9, MIN_CASES, 5)
        check("the worker and grammar retain fail-open verdict divergences",
              fail_open_report["counts"]["block-to-allow"] > 0
              and any(item["classification"] == "block-to-allow"
                      for item in fail_open_report["results"]))
        blind_oracle = root / "blind-oracle.py"
        blind_oracle.write_text("def judge(payload): return None\n", encoding="utf-8")
        try:
            compare(blind_oracle, fail_open, 9, MIN_CASES, 5)
            refused_blind_oracle = False
        except RuntimeError as exc:
            refused_blind_oracle = "no power to detect" in str(exc)
        check("a comparison whose oracle never blocks is an instrument error",
              refused_blind_oracle)
        blind_stdout, blind_stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(blind_stdout), contextlib.redirect_stderr(blind_stderr):
            blind_exit = main([
                str(blind_oracle), str(fail_open), "9", str(MIN_CASES), "--timeout", "5",
            ])
        check("the CLI exits two rather than green when the oracle blocked nothing",
              blind_exit == 2 and "FUZZ-ERROR" in blind_stderr.getvalue()
              and "block_to_allow=0" not in blind_stderr.getvalue())
        main_stdout, main_stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(main_stdout), contextlib.redirect_stderr(main_stderr):
            fail_open_exit = main([
                str(guard), str(fail_open), "9", str(MIN_CASES), "--timeout", "5",
            ])
        check("the CLI exits one when a fail-open divergence is retained",
              fail_open_exit == 1 and "block_to_allow=" in main_stderr.getvalue()
              and "exit=1" in main_stderr.getvalue())
        instrument = Path(__file__).resolve()
        cli = [str(instrument), str(guard), str(guard), "9", str(MIN_CASES),
               "--timeout", "5"]
        nonfinite = [
            subprocess.run(
                [sys.executable, str(instrument), str(guard), str(guard), "9",
                 str(MIN_CASES), f"--timeout={value}"],
                capture_output=True, text=True, timeout=10)
            for value in ("inf", "nan", "-inf")
        ]
        check("non-finite worker timeouts are usage errors, never safety findings",
              all(done.returncode == 2 and not done.stdout
                  and "positive finite" in done.stderr
                  and "Traceback" not in done.stderr for done in nonfinite))

        descriptor_probe = root / "descriptor-probe.py"
        descriptor_probe.write_text(
            "import os, sys\n"
            "mode, descriptor, command = sys.argv[1], int(sys.argv[2]), sys.argv[3:]\n"
            "if mode == 'close':\n"
            "    os.close(descriptor)\n"
            "else:\n"
            "    read_fd, write_fd = os.pipe()\n"
            "    os.close(read_fd)\n"
            "    os.dup2(write_fd, descriptor)\n"
            "    if write_fd != descriptor:\n"
            "        os.close(write_fd)\n"
            "os.execv(sys.executable, [sys.executable, *command])\n",
            encoding="utf-8",
        )

        def probe_descriptor(mode, descriptor, command=None, input_text=None):
            return subprocess.run(
                [sys.executable, str(descriptor_probe), mode, str(descriptor),
                 *(cli if command is None else command)],
                input=input_text, capture_output=True, text=True, timeout=15)

        def complete_json(raw):
            try:
                payload = json.loads(raw)
            except (TypeError, ValueError):
                return False
            return (isinstance(payload, dict)
                    and payload.get("generated_count") == MIN_CASES)

        closed_stdout = probe_descriptor("close", 1)
        check("a closed stdout is an instrument error without a traceback or exit one",
              closed_stdout.returncode == 2 and not closed_stdout.stdout
              and "FUZZ-ERROR" in closed_stdout.stderr
              and "Traceback" not in closed_stdout.stderr)
        closed_stderr = probe_descriptor("close", 2)
        check("a closed stderr cannot redirect the summary into machine output",
              closed_stderr.returncode == 2 and not closed_stderr.stderr
              and complete_json(closed_stderr.stdout)
              and "FUZZ-SUMMARY" not in closed_stderr.stdout)
        broken_stdout = probe_descriptor("broken", 1)
        check("a broken stdout pipe remains an instrument error rather than exit 120",
              broken_stdout.returncode == 2 and not broken_stdout.stdout
              and "FUZZ-ERROR" in broken_stdout.stderr
              and "Traceback" not in broken_stdout.stderr)
        broken_stderr = probe_descriptor("broken", 2)
        check("a broken stderr pipe preserves one JSON report and exits two",
              broken_stderr.returncode == 2 and not broken_stderr.stderr
              and complete_json(broken_stderr.stdout)
              and "FUZZ-SUMMARY" not in broken_stderr.stdout)

        divergent_cli = [str(instrument), str(guard), str(fail_open), "9",
                         str(MIN_CASES), "--timeout", "5"]
        healthy_divergence = subprocess.run(
            [sys.executable, *divergent_cli],
            capture_output=True, text=True, timeout=15)
        try:
            healthy_divergence_report = json.loads(healthy_divergence.stdout)
        except ValueError:
            healthy_divergence_report = None
        divergent_faults = {
            (mode, descriptor): probe_descriptor(
                mode, descriptor, divergent_cli)
            for mode in ("close", "broken") for descriptor in (1, 2)
        }
        check("output faults outrank a real block-to-allow verdict",
              healthy_divergence.returncode == 1
              and isinstance(healthy_divergence_report, dict)
              and healthy_divergence_report.get("counts", {}).get("block-to-allow", 0) > 0
              and all(done.returncode == 2 for done in divergent_faults.values())
              and all(not divergent_faults[(mode, 1)].stdout
                      for mode in ("close", "broken"))
              and all(complete_json(divergent_faults[(mode, 2)].stdout)
                      and not divergent_faults[(mode, 2)].stderr
                      for mode in ("close", "broken")))

        def probe_both(mode, command):
            return probe_descriptor(
                mode, 1,
                [str(descriptor_probe), mode, "2", *command])

        both_faults = [
            probe_both(mode, command)
            for mode in ("close", "broken")
            for command in (cli, divergent_cli)
        ]
        check("simultaneous stdout and stderr faults remain instrument errors",
              all(done.returncode == 2 and not done.stdout and not done.stderr
                  for done in both_faults))

        worker_cli = [
            str(instrument), "--worker", str(guard),
            "--expected-sha256", source_digest(guard),
            "--logical-path", str(guard),
        ]
        worker_input = json.dumps(["Starting the audit."])
        broken_worker = probe_descriptor(
            "broken", 1, worker_cli, worker_input)
        check("a worker's broken stdout exits two rather than 120 or partial JSON",
              broken_worker.returncode == 2 and not broken_worker.stdout
              and "Traceback" not in broken_worker.stderr)

        exceptional_workers = []
        for exception in ("SystemExit(1)", "KeyboardInterrupt('planted')"):
            exceptional_guard = root / f"worker-{exception.split('(')[0].lower()}.py"
            exceptional_guard.write_text(
                "def judge(payload):\n"
                f"    raise {exception}\n",
                encoding="utf-8",
            )
            done = subprocess.run(
                [sys.executable, str(instrument), "--worker", str(exceptional_guard),
                 "--expected-sha256", source_digest(exceptional_guard),
                 "--logical-path", str(exceptional_guard)],
                input=worker_input, capture_output=True, text=True, timeout=10)
            try:
                worker_payload = json.loads(done.stdout)
            except ValueError:
                worker_payload = None
            exceptional_workers.append(
                done.returncode == 2 and not done.stderr
                and isinstance(worker_payload, dict)
                and worker_payload.get("status") == "instrument-error"
                and worker_payload.get("reason") == exception.split("(")[0]
            )
        check("worker BaseException faults are instrument errors, never reserved exit one",
              all(exceptional_workers))

        class ShortWriter:
            def __init__(self):
                self.parts = []

            def write(self, value):
                accepted = max(1, len(value) // 2)
                self.parts.append(value[:accepted])
                return accepted

            def flush(self):
                return None

        short_writer = ShortWriter()
        short_ok, short_error = emit_report(short_writer, {"value": "abc"})
        check("pre-serialized report output completes across explicit short writes",
              short_ok and short_error is None
              and json.loads("".join(short_writer.parts)) == {"value": "abc"})
        short_summary = ShortWriter()
        check("summary output completes across explicit short writes",
              emit_line(short_summary, "FUZZ-SUMMARY planted")
              and "".join(short_summary.parts) == "FUZZ-SUMMARY planted\n")

        class ZeroWriter:
            def __init__(self):
                self.content = ""

            def write(self, value):
                self.content += value[:0]
                return 0

            def flush(self):
                return None

        zero_writer = ZeroWriter()
        zero_ok, _zero_error = emit_report(zero_writer, {"value": "abc"})
        unserializable_writer = io.StringIO()
        serial_ok, _serial_error = emit_report(
            unserializable_writer, {"bad": object()})
        check("invalid write counts and serialization faults fail before a false verdict",
              not zero_ok and not zero_writer.content
              and not serial_ok and not unserializable_writer.getvalue())
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
    stdout, stderr = sys.stdout, sys.stderr
    if args.worker is not None:
        if args.expected_sha256 is None or args.logical_path is None:
            emit_line(stderr, "--worker requires --expected-sha256 and --logical-path")
            return 2
        if stdout is None or getattr(stdout, "closed", False):
            emit_line(stderr, "FUZZ-ERROR RuntimeError: stdout is unavailable")
            return 2
        return worker(args.worker, args.expected_sha256, args.logical_path)
    if args.selftest:
        return 1 if selftest() else 0
    if None in (args.oracle, args.candidate, args.seed, args.count):
        emit_line(stderr, "oracle, candidate, seed, and count are required")
        return 2
    if not 0 <= args.seed < 2 ** 64:
        emit_line(stderr, "seed must be an unsigned 64-bit integer")
        return 2
    if not MIN_CASES <= args.count <= MAX_CASES:
        emit_line(stderr, f"count must be between {MIN_CASES} and {MAX_CASES}")
        return 2
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        emit_line(stderr, "--timeout must be a positive finite number")
        return 2
    if stdout is None or getattr(stdout, "closed", False):
        emit_line(stderr, "FUZZ-ERROR RuntimeError: stdout is unavailable")
        return 2
    try:
        report = compare(args.oracle, args.candidate, args.seed, args.count, args.timeout)
    except (OSError, RuntimeError, ValueError, IndexError, KeyError,
            TypeError, AttributeError) as exc:
        # Exit 1 is reserved for a block-to-allow verdict. An instrument fault that
        # escaped as a bare traceback exited 1 through the interpreter, reporting a
        # crash as a safety finding -- a desynced vocabulary/pin pair did exactly that.
        emit_line(stderr, f"FUZZ-ERROR {type(exc).__name__}: {exc}")
        return 2
    emitted, output_error = emit_report(stdout, report)
    if not emitted:
        # Writing the report is not a verdict. Under an ascii stdout the grammar's own
        # em dash and curly quotes raised here, outside the try above, and exited 1 --
        # the reserved block-to-allow code -- for an encoding fault.
        emit_line(
            stderr,
            f"FUZZ-ERROR {type(output_error).__name__}: {output_error}",
        )
        return 2
    counts = report["counts"]
    exit_code = 1 if counts["block-to-allow"] else 0
    summary = (
        f"FUZZ-SUMMARY seed={args.seed} count={args.count} "
        f"block_to_allow={counts['block-to-allow']} "
        f"allow_to_block={counts['allow-to-block']} "
        f"reason_changes={counts['block-reason-change']} "
        f"oracle_blocks={report['oracle_blocks']}/{report['generated_count']} "
        f"exit={exit_code}"
    )
    if not emit_line(stderr, summary):
        return 2
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
