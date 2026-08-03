#!/usr/bin/env python3
"""cc-cost — token accounting over Claude Code transcripts, with the four traps closed.

Method per `harness-audit-20260801/FINDINGS.md` §0, verified across 12 projects /
187 dirs. The four traps this tool exists to close (each shipped a wrong figure
when done in prose):

  T1  one API call writes MULTIPLE JSONL records, each with a COPY of `usage`
      -> dedupe by requestId (naive summing inflates ~3x)
  T2  records sharing a requestId carry DIFFERENT output_tokens (provisional on
      the first block, final on the last) -> take the MAX per requestId
      (keeping the first undercounts subagent output by 90.8%)
  T3  subagent transcripts live at <session-id>/subagents/, one level down
      -> walk recursively (missing them drops 56-85% of calls)
  T4  synthetic records (`model == "<synthetic>"`) and session-resume replays
      (repeat `uuid`) are not API calls -> drop both

Cache-TTL split (measured, exceptionless in the corpus): main-thread cache
writes bill 2.0x (`ephemeral_1h`), subagent writes 1.25x (`ephemeral_5m`).
Output is token accounting, not dollars — pricing changes; the token method
does not.

  cc-cost.py                      last 7 days, all projects
  cc-cost.py --since 30d|24h|all  window
  cc-cost.py --project <substr>   restrict to project dirs matching substring
  cc-cost.py --selftest           prove each trap-closure on planted fixtures

Exit codes: 0 report printed · 1 selftest failure · 2 usage error or zero
transcripts in window (zero inputs is an error, never a clean verdict).
"""
import glob
import json
import os
import re
import sys
import time

VERSION = "1.0.0"
ROOT = os.path.expanduser("~/.claude/projects")


def parse_since(s):
    if s in (None, "all"):
        return 0.0
    m = re.fullmatch(r"(\d+)([dhw])", s)
    if not m:
        raise ValueError(f"bad --since {s!r}; use 7d, 24h, 2w or all")
    n, u = int(m.group(1)), m.group(2)
    return time.time() - n * {"h": 3600, "d": 86400, "w": 604800}[u]


def scan(root, cutoff, project_filter=None):
    """-> (per_class totals, scanset). Class = 'main' | 'subagent' (T3)."""
    files = glob.glob(root + "/**/*.jsonl", recursive=True)
    if project_filter:
        files = [f for f in files if project_filter in f]
    scanset = {"root": root, "files_found": len(files), "files_in_window": 0,
               "records": 0, "synthetic_dropped": 0, "replay_dropped": 0,
               "requests": 0}
    per_req = {}          # requestId -> dict(usage-max, cls)
    seen_uuid = set()
    for f in files:
        try:
            if os.stat(f).st_mtime < cutoff:
                continue
        except OSError:
            continue
        scanset["files_in_window"] += 1
        cls = "subagent" if "/subagents/" in f else "main"
        try:
            fh = open(f, errors="replace")
        except OSError:
            continue
        with fh:
            for ln in fh:
                if '"usage"' not in ln:
                    continue
                try:
                    d = json.loads(ln)
                except Exception:
                    continue
                msg = d.get("message") or {}
                usage = msg.get("usage")
                rid = d.get("requestId")
                if not usage or not rid:
                    continue
                scanset["records"] += 1
                if msg.get("model") == "<synthetic>":                 # T4
                    scanset["synthetic_dropped"] += 1
                    continue
                u = d.get("uuid")
                if u and u in seen_uuid:                              # T4 replay
                    scanset["replay_dropped"] += 1
                    continue
                if u:
                    seen_uuid.add(u)
                cur = per_req.get(rid)
                if cur is None:                                       # T1 dedupe
                    per_req[rid] = {
                        "cls": cls,
                        "input": usage.get("input_tokens", 0),
                        "cache_wr": usage.get("cache_creation_input_tokens", 0),
                        "cache_rd": usage.get("cache_read_input_tokens", 0),
                        "output": usage.get("output_tokens", 0),
                    }
                else:                                                 # T2 max
                    cur["output"] = max(cur["output"], usage.get("output_tokens", 0))
                    cur["input"] = max(cur["input"], usage.get("input_tokens", 0))
                    cur["cache_wr"] = max(cur["cache_wr"],
                                          usage.get("cache_creation_input_tokens", 0))
                    cur["cache_rd"] = max(cur["cache_rd"],
                                          usage.get("cache_read_input_tokens", 0))
    scanset["requests"] = len(per_req)
    totals = {c: {"calls": 0, "input": 0, "cache_wr": 0, "cache_rd": 0, "output": 0}
              for c in ("main", "subagent")}
    for r in per_req.values():
        t = totals[r["cls"]]
        t["calls"] += 1
        for k in ("input", "cache_wr", "cache_rd", "output"):
            t[k] += r[k]
    return totals, scanset


def report(totals, scanset, out=sys.stdout):
    p = lambda *a: print(*a, file=out)
    p(f"\nSCAN SET  root={scanset['root']}")
    p(f"          {scanset['files_found']} transcript files, "
      f"{scanset['files_in_window']} in window; {scanset['records']} usage records "
      f"-> {scanset['requests']} API calls after requestId dedupe; "
      f"dropped {scanset['synthetic_dropped']} synthetic, "
      f"{scanset['replay_dropped']} replays")
    if scanset["files_in_window"] == 0:
        p("\nZERO TRANSCRIPTS IN WINDOW — error, not a clean result.")
        return 2
    p(f"\n  {'class':<10}{'calls':>8}{'input':>12}{'cache_wr':>14}{'cache_rd':>14}{'output':>12}")
    for cls in ("main", "subagent"):
        t = totals[cls]
        p(f"  {cls:<10}{t['calls']:>8}{t['input']:>12,}{t['cache_wr']:>14,}"
          f"{t['cache_rd']:>14,}{t['output']:>12,}")
    p("\n  cache-write billing multipliers (measured, exceptionless): main 2.0x "
      "(ephemeral_1h) · subagent 1.25x (ephemeral_5m)")
    wu = (totals["main"]["cache_wr"] * 2.0 + totals["subagent"]["cache_wr"] * 1.25)
    p(f"  weighted cache-write units: {wu:,.0f}")
    return 0


def selftest():
    import tempfile
    bad = checks = 0

    def chk(label, got, want):
        nonlocal bad, checks
        checks += 1
        ok = got == want
        bad += (not ok)
        print(f"  {'PASS' if ok else 'FAIL'} {label:<58} got={got!r}")

    with tempfile.TemporaryDirectory() as td:
        os.makedirs(os.path.join(td, "proj", "sess", "subagents"))
        rec = lambda rid, out_, model="m", uuid=None, extra=0: json.dumps(
            {"requestId": rid, "uuid": uuid or f"u-{rid}-{out_}",
             "message": {"model": model,
                         "usage": {"input_tokens": 10 + extra,
                                   "cache_creation_input_tokens": 100,
                                   "cache_read_input_tokens": 1000,
                                   "output_tokens": out_}}})
        main = os.path.join(td, "proj", "sess", "t.jsonl")
        open(main, "w").write("\n".join([
            rec("r1", 5), rec("r1", 50),          # T1+T2: same request, max wins
            rec("r2", 7, model="<synthetic>"),    # T4: synthetic dropped
            rec("r3", 9), rec("r3", 9, uuid="u-r3-9"),  # T4: replay uuid dropped
        ]) + "\n")
        sub = os.path.join(td, "proj", "sess", "subagents", "a.jsonl")
        open(sub, "w").write(rec("r4", 21) + "\n")  # T3: nested path found

        totals, ss = scan(td, 0.0)
        chk("T1 dedupe: r1 counted once", totals["main"]["calls"], 2)   # r1 + r3
        chk("T2 max: r1 output is 50 not 5", totals["main"]["output"], 50 + 9)
        chk("T4 synthetic dropped", ss["synthetic_dropped"], 1)
        chk("T4 replay dropped", ss["replay_dropped"], 1)
        chk("T3 subagent file found one level down", totals["subagent"]["calls"], 1)
        chk("T3 subagent output counted", totals["subagent"]["output"], 21)
        # zero-input arm
        import io
        buf = io.StringIO()
        rc = report({c: {"calls": 0, "input": 0, "cache_wr": 0, "cache_rd": 0,
                         "output": 0} for c in ("main", "subagent")},
                    {"root": td, "files_found": 0, "files_in_window": 0,
                     "records": 0, "synthetic_dropped": 0, "replay_dropped": 0,
                     "requests": 0}, out=buf)
        chk("zero transcripts exits 2, not 0", rc, 2)
        chk("zero transcripts says so out loud",
            "ZERO TRANSCRIPTS" in buf.getvalue(), True)

    print(f"\n  selftest: {bad} failure(s)")
    print(f"SELFTEST-SUMMARY checks={checks} failures={bad}")
    return 1 if bad else 0


def main(argv):
    args = argv[1:]
    since, project = "7d", None
    while args:
        a = args.pop(0)
        if a in ("-h", "--help"):
            print(__doc__)
            return 0
        if a == "--version":
            print(f"cc-cost {VERSION}")
            return 0
        if a == "--selftest":
            return selftest()
        if a == "--since" and args:
            since = args.pop(0)
        elif a == "--all":
            since = "all"
        elif a == "--project" and args:
            project = args.pop(0)
        else:
            sys.stderr.write(f"unknown argument: {a!r}\nrun --help\n")
            return 2
    try:
        cutoff = parse_since(since)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    totals, scanset = scan(ROOT, cutoff, project)
    return report(totals, scanset)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
