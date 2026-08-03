#!/usr/bin/env python3
"""codex-cost — token accounting over local Codex session JSONL.

Codex writes cumulative `total_token_usage` alongside per-request `last_token_usage`. The
cumulative value spans turns, so taking one maximum per turn and then summing turns overcounts the
session. This tool sums each valid `last_token_usage` record once, deduplicates copied/replayed
records across transcript files, and walks every session file so subagent sessions remain in the
scan set.

The output is token accounting, not dollars. Cached input and reasoning output are reported as
subsets of input/output and are not added to `total_tokens` again.

  codex-cost.py                       last 7 days
  codex-cost.py --since 30d|24h|all   window
  codex-cost.py --project <substr>    restrict to turn cwd containing substring
  codex-cost.py --selftest            prove cross-turn cumulative and replay traps close

Exit codes: 0 report printed; 1 selftest failure; 2 usage error or zero accounted turns.
"""
import argparse
from datetime import datetime
import glob
import json
import os
import re
import sys
import tempfile
import time

VERSION = "1.2.0"
USAGE_FIELDS = (
    "input_tokens",
    "cached_input_tokens",
    "cache_write_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
    "total_tokens",
)


def default_root():
    codex_home = os.environ.get("CODEX_HOME", os.path.expanduser("~/.codex"))
    return os.path.join(codex_home, "sessions")


def parse_since(value):
    if value in (None, "all"):
        return 0.0
    match = re.fullmatch(r"(\d+)([dhw])", value)
    if not match:
        raise ValueError(f"bad --since {value!r}; use 7d, 24h, 2w or all")
    amount, unit = int(match.group(1)), match.group(2)
    return time.time() - amount * {"h": 3600, "d": 86400, "w": 604800}[unit]


def source_class(source, originator):
    text = json.dumps(source, sort_keys=True).lower() if source is not None else ""
    if "subagent" in text or "sub-agent" in text or "subagent" in str(originator).lower():
        return "subagent"
    return "main"


def record_time(value):
    """Parse an RFC 3339 transcript timestamp to epoch seconds, or return None."""
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def empty_usage():
    return {field: 0 for field in USAGE_FIELDS}


def scan(root, cutoff, project_filter=None):
    files = sorted(glob.glob(os.path.join(root, "**", "*.jsonl"), recursive=True))
    scanset = {
        "root": root,
        "files_found": len(files),
        "files_in_window": 0,
        "records": 0,
        "malformed_records": 0,
        "usage_snapshots": 0,
        "accounted_usage_records": 0,
        "missing_last_usage_snapshots": 0,
        "orphan_usage_snapshots": 0,
        "orphan_usage_raw_total_tokens": 0,
        "orphan_excluded_usage_records": 0,
        "orphan_excluded_total_tokens": 0,
        "replayed_usage_snapshots": 0,
        "turns_without_timestamps": 0,
        "turns": 0,
    }
    turns = {}
    seen_usage_records = set()
    observed_usage_records = {}
    accounted_request_keys = set()
    orphan_request_keys = set()

    for path in files:
        try:
            if os.stat(path).st_mtime < cutoff:
                continue
        except OSError:
            continue
        scanset["files_in_window"] += 1
        session_id = None
        session_class = "main"
        current_turn = None
        try:
            handle = open(path, encoding="utf-8", errors="replace")
        except OSError:
            continue
        with handle:
            for line in handle:
                scanset["records"] += 1
                try:
                    record = json.loads(line)
                except Exception:
                    scanset["malformed_records"] += 1
                    continue
                kind = record.get("type")
                payload = record.get("payload") or {}
                observed_at = record_time(record.get("timestamp"))
                if kind == "session_meta":
                    # Fork transcripts embed the parent transcript, including its session_meta.
                    # The first session_meta describes this file; later ones are copied history.
                    if session_id is None:
                        session_id = payload.get("session_id") or payload.get("id")
                        session_class = source_class(
                            payload.get("source"), payload.get("originator")
                        )
                    continue
                if kind == "event_msg" and payload.get("type") == "task_started":
                    current_turn = payload.get("turn_id")
                    continue
                if kind == "turn_context":
                    current_turn = payload.get("turn_id") or current_turn
                    if current_turn:
                        row = turns.setdefault(current_turn, {
                            "usage": empty_usage(),
                            "class": session_class,
                            "model": payload.get("model") or "unknown",
                            "cwd": payload.get("cwd") or "",
                            "session_id": session_id,
                            "last_usage_at": None,
                            "requests": 0,
                            "classes_seen": {session_class},
                        })
                        row["classes_seen"].add(session_class)
                        row["model"] = payload.get("model") or row["model"]
                        row["cwd"] = payload.get("cwd") or row["cwd"]
                    continue
                if kind != "event_msg" or payload.get("type") != "token_count":
                    continue
                info = payload.get("info") or {}
                cumulative = info.get("total_token_usage")
                if not isinstance(cumulative, dict):
                    continue
                scanset["usage_snapshots"] += 1
                usage = info.get("last_token_usage")
                if not isinstance(usage, dict):
                    scanset["missing_last_usage_snapshots"] += 1
                    continue
                if cutoff and (observed_at is None or observed_at < cutoff):
                    continue
                normalized_usage = {
                    field: value if isinstance(value := usage.get(field, 0), int)
                    and not isinstance(value, bool) and value >= 0 else 0
                    for field in USAGE_FIELDS
                }
                cumulative_key = tuple(cumulative.get(field) for field in USAGE_FIELDS)
                usage_key = tuple(normalized_usage[field] for field in USAGE_FIELDS)
                request_key = (session_id or f"file:{path}", cumulative_key, usage_key)
                observed_usage_records.setdefault(request_key, normalized_usage)
                if not current_turn:
                    scanset["orphan_usage_snapshots"] += 1
                    scanset["orphan_usage_raw_total_tokens"] += normalized_usage["total_tokens"]
                    orphan_request_keys.add(request_key)
                    continue
                accounted_request_keys.add(request_key)
                row = turns.setdefault(current_turn, {
                    "usage": empty_usage(),
                    "class": session_class,
                    "model": "unknown",
                    "cwd": "",
                    "session_id": session_id,
                    "last_usage_at": None,
                    "requests": 0,
                    "classes_seen": {session_class},
                })
                row["classes_seen"].add(session_class)
                fingerprint = (current_turn, cumulative_key, usage_key)
                if fingerprint in seen_usage_records:
                    scanset["replayed_usage_snapshots"] += 1
                    continue
                seen_usage_records.add(fingerprint)
                if observed_at is not None:
                    row["last_usage_at"] = max(row["last_usage_at"] or 0, observed_at)
                row["requests"] += 1
                scanset["accounted_usage_records"] += 1
                for field in USAGE_FIELDS:
                    row["usage"][field] += normalized_usage[field]

    excluded_orphan_keys = orphan_request_keys - accounted_request_keys
    scanset["orphan_excluded_usage_records"] = len(excluded_orphan_keys)
    scanset["orphan_excluded_total_tokens"] = sum(
        observed_usage_records[key]["total_tokens"] for key in excluded_orphan_keys
    )
    for row in turns.values():
        # A parent turn copied into a fork is still a main turn when its source transcript exists.
        row["class"] = "main" if "main" in row["classes_seen"] else "subagent"
    scanset["turns_without_timestamps"] = sum(
        row["usage"]["total_tokens"] > 0 and row["last_usage_at"] is None
        for row in turns.values()
    )
    turns = {
        turn_id: row for turn_id, row in turns.items()
        if row["usage"]["total_tokens"] > 0
        and (not project_filter or project_filter in row["cwd"])
    }
    scanset["turns"] = len(turns)
    return turns, scanset


def totals_by_class(turns):
    totals = {
        name: {"turns": 0, "requests": 0, **empty_usage()}
        for name in ("main", "subagent")
    }
    for row in turns.values():
        bucket = totals[row["class"]]
        bucket["turns"] += 1
        bucket["requests"] += row["requests"]
        for field in USAGE_FIELDS:
            bucket[field] += row["usage"][field]
    return totals


def report(turns, scanset, out=sys.stdout):
    write = lambda *args: print(*args, file=out)
    write(f"\nSCAN SET  root={scanset['root']}")
    write(
        f"          {scanset['files_found']} transcript files found, "
        f"{scanset['files_in_window']} in window, {scanset['records']} records, "
        f"{scanset['usage_snapshots']} usage snapshots, "
        f"{scanset['accounted_usage_records']} accounted requests"
    )
    write(
        f"          {scanset['malformed_records']} malformed, "
        f"{scanset['missing_last_usage_snapshots']} missing per-request usage, "
        f"{scanset['replayed_usage_snapshots']} replayed/copy snapshots, "
        f"{scanset['turns_without_timestamps']} timestamp-less turns"
    )
    write(
        f"          {scanset['orphan_usage_snapshots']} orphan usage snapshots total "
        f"{scanset['orphan_usage_raw_total_tokens']:,} raw tokens; after replay "
        f"reconciliation, {scanset['orphan_excluded_usage_records']} requests / "
        f"{scanset['orphan_excluded_total_tokens']:,} tokens remain unattributed and excluded"
    )
    if not turns:
        write("\nZERO ACCOUNTED TURNS — that is an error, not a zero-cost verdict.")
        return 2

    totals = totals_by_class(turns)
    write("\nTOKEN ACCOUNTING  per-request last usage records summed once")
    write(
        f"  {'class':<10}{'turns':>8}{'requests':>10}{'input':>14}{'cached':>14}{'cache write':>14}"
        f"{'output':>12}{'reasoning':>12}{'total':>14}"
    )
    for name in ("main", "subagent"):
        row = totals[name]
        write(
            f"  {name:<10}{row['turns']:>8,}{row['requests']:>10,}{row['input_tokens']:>14,}"
            f"{row['cached_input_tokens']:>14,}{row['cache_write_input_tokens']:>14,}"
            f"{row['output_tokens']:>12,}{row['reasoning_output_tokens']:>12,}"
            f"{row['total_tokens']:>14,}"
        )
    combined = {field: sum(totals[name][field] for name in totals) for field in USAGE_FIELDS}
    write(
        f"  {'TOTAL':<10}{len(turns):>8,}{sum(row['requests'] for row in totals.values()):>10,}"
        f"{combined['input_tokens']:>14,}"
        f"{combined['cached_input_tokens']:>14,}{combined['cache_write_input_tokens']:>14,}"
        f"{combined['output_tokens']:>12,}{combined['reasoning_output_tokens']:>12,}"
        f"{combined['total_tokens']:>14,}"
    )
    write("\n  cached input is included in input; reasoning output is included in output")
    return 0


def write_fixture(path, records):
    with open(path, "w", encoding="utf-8") as handle:
        for record in records:
            if isinstance(record, str):
                handle.write(record + "\n")
            else:
                handle.write(json.dumps(record) + "\n")


def selftest():
    checks = failures = 0

    def check(label, condition):
        nonlocal checks, failures
        checks += 1
        failures += not condition
        print(f"  {'PASS' if condition else 'FAIL'} {label}")

    cumulative_1 = {
        field: value for field, value in zip(USAGE_FIELDS, (100, 60, 0, 10, 4, 110))
    }
    cumulative_2 = {
        field: value for field, value in zip(USAGE_FIELDS, (180, 120, 0, 20, 8, 200))
    }
    request_1 = cumulative_1.copy()
    request_2 = {field: value for field, value in zip(USAGE_FIELDS, (80, 60, 0, 10, 4, 90))}
    usage_3 = {field: value for field, value in zip(USAGE_FIELDS, (50, 0, 0, 5, 2, 55))}
    orphan_usage = {field: value for field, value in zip(USAGE_FIELDS, (25, 0, 0, 5, 1, 30))}

    with tempfile.TemporaryDirectory() as tmp:
        now = datetime.now().astimezone().isoformat()
        main_path = os.path.join(tmp, "main.jsonl")
        copy_path = os.path.join(tmp, "copy.jsonl")
        orphan_path = os.path.join(tmp, "orphan.jsonl")
        sub_path = os.path.join(tmp, "sub.jsonl")
        write_fixture(main_path, [
            {"timestamp": now, "type": "session_meta", "payload": {"id": "s1", "source": "vscode"}},
            {"timestamp": now, "type": "event_msg", "payload": {"type": "task_started", "turn_id": "t1"}},
            {"timestamp": now, "type": "turn_context", "payload": {"turn_id": "t1", "cwd": "/repo/a", "model": "gpt-test"}},
            {"timestamp": now, "type": "event_msg", "payload": {"type": "token_count", "info": {"total_token_usage": cumulative_1, "last_token_usage": request_1}}},
            {"timestamp": now, "type": "event_msg", "payload": {"type": "task_started", "turn_id": "t2"}},
            {"timestamp": now, "type": "turn_context", "payload": {"turn_id": "t2", "cwd": "/repo/a", "model": "gpt-test"}},
            {"timestamp": now, "type": "event_msg", "payload": {"type": "token_count", "info": {"total_token_usage": cumulative_2, "last_token_usage": request_2}}},
            {"timestamp": now, "type": "event_msg", "payload": {"type": "token_count", "info": {"total_token_usage": {"total_tokens": 999}}}},
            "not-json",
        ])
        write_fixture(copy_path, [
            {"timestamp": now, "type": "session_meta", "payload": {"id": "copy", "session_id": "s1", "forked_from_id": "s1", "source": "vscode"}},
            {"timestamp": now, "type": "event_msg", "payload": {"type": "token_count", "info": {"total_token_usage": cumulative_1, "last_token_usage": request_1}}},
            {"timestamp": now, "type": "event_msg", "payload": {"type": "task_started", "turn_id": "t1"}},
            {"timestamp": now, "type": "event_msg", "payload": {"type": "token_count", "info": {"total_token_usage": cumulative_1, "last_token_usage": request_1}}},
        ])
        write_fixture(orphan_path, [
            {"timestamp": now, "type": "session_meta", "payload": {"id": "s3", "source": "vscode"}},
            {"timestamp": now, "type": "event_msg", "payload": {"type": "token_count", "info": {"total_token_usage": orphan_usage, "last_token_usage": orphan_usage}}},
        ])
        write_fixture(sub_path, [
            {"timestamp": now, "type": "session_meta", "payload": {"id": "s2", "source": {"subagent": {"thread_id": "x"}}}},
            {"timestamp": now, "type": "event_msg", "payload": {"type": "task_started", "turn_id": "t3"}},
            {"timestamp": now, "type": "turn_context", "payload": {"turn_id": "t3", "cwd": "/repo/b", "model": "gpt-test"}},
            {"timestamp": now, "type": "event_msg", "payload": {"type": "token_count", "info": {"total_token_usage": usage_3, "last_token_usage": usage_3}}},
        ])

        turns, scanset = scan(tmp, 0)
        check("two cumulative turns sum request deltas, not cumulative maxima",
              turns["t1"]["usage"]["total_tokens"] + turns["t2"]["usage"]["total_tokens"] == 200)
        check("copied request is deduplicated across files", len(turns) == 3)
        check("copy/replay is observed in the scan report", scanset["replayed_usage_snapshots"] == 1)
        check("raw orphan token mass is visible", scanset["orphan_usage_snapshots"] == 2
              and scanset["orphan_usage_raw_total_tokens"] == 140)
        check("orphan copy already accounted in-turn is reconciled",
              scanset["orphan_excluded_usage_records"] == 1)
        check("unique unattributed orphan token mass remains explicit",
              scanset["orphan_excluded_total_tokens"] == 30)
        check("subagent source is classified separately", turns["t3"]["class"] == "subagent")
        check("malformed record is counted", scanset["malformed_records"] == 1)
        check("snapshot missing last_token_usage is counted and skipped",
              scanset["missing_last_usage_snapshots"] == 1)
        filtered, _ = scan(tmp, 0, project_filter="/repo/b")
        check("project filter uses persisted turn cwd", set(filtered) == {"t3"})
        totals = totals_by_class(turns)
        check("main total sums last usage once across two turns", totals["main"]["total_tokens"] == 200)
        check("main request count excludes replay and missing-last records",
              totals["main"]["requests"] == 2)
        check("subagent total is independently retained", totals["subagent"]["total_tokens"] == 55)

        old_path = os.path.join(tmp, "recently-copied-old-turn.jsonl")
        write_fixture(old_path, [
            {"timestamp": "2020-01-01T00:00:00Z", "type": "session_meta",
             "payload": {"id": "old", "source": "vscode"}},
            {"timestamp": "2020-01-01T00:00:01Z", "type": "event_msg",
             "payload": {"type": "task_started", "turn_id": "old-turn"}},
            {"timestamp": "2020-01-01T00:00:02Z", "type": "event_msg",
             "payload": {"type": "token_count", "info": {
                 "total_token_usage": usage_3, "last_token_usage": usage_3}}},
        ])
        recent, _ = scan(tmp, time.time() - 3600)
        check("--since filters by record timestamp, not copied-file mtime",
              "old-turn" not in recent and set(recent) == {"t1", "t2", "t3"})

        import io
        buffer = io.StringIO()
        rc = report({}, {key: 0 for key in scanset} | {"root": tmp}, out=buffer)
        check("zero accounted turns exits two", rc == 2)
        check("zero accounted turns is stated", "ZERO ACCOUNTED TURNS" in buffer.getvalue())

    print(f"\n  {checks} checks, {failures} failures")
    return 1 if failures else 0


def main(argv):
    parser = argparse.ArgumentParser(description="account for Codex transcript tokens")
    parser.add_argument("--since", default="7d", help="7d | 24h | 2w | all")
    parser.add_argument("--all", action="store_true", help="scan the full corpus")
    parser.add_argument("--project", help="only turn cwd values containing this substring")
    parser.add_argument("--root", default=default_root(), help="Codex sessions root")
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--version", action="store_true")
    try:
        args = parser.parse_args(argv[1:])
    except SystemExit as exc:
        return int(exc.code)
    if args.version:
        print(f"codex-cost {VERSION}")
        return 0
    if args.selftest:
        return selftest()
    try:
        cutoff = parse_since("all" if args.all else args.since)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    turns, scanset = scan(args.root, cutoff, project_filter=args.project)
    return report(turns, scanset)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
