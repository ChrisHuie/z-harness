#!/usr/bin/env python3
"""run-skill-evals — the authoring skills' contract evals.

Corpus: `skills/<name>/evals/*.json`, schema per craft-skill Step 2:
  {"skills": [...], "query": "...", "files": [{"path","content"}], "expected_behavior": [...]}

Two modes, deliberately separated by cost:

  --validate   OFFLINE, free. Schema-checks every scenario, asserts each named skill
               exists, each scenario has >=1 expected behavior, and each skill has the
               doctrine's three shapes (happy / failure / near-miss). Safe for CI.
  --run        SPENDS API BUDGET. Executes each scenario headless (`claude -p` in a temp
               cwd with the scenario's files materialized) and greps the result for the
               MECHANICAL markers only (contract section headers). Everything beyond a
               header grep is judgment: those rows print CHECK-MANUALLY with the expected
               behavior, never PASS. Manual, never scheduled.

Known measurement bound (recorded in the harness record, report-trigger Part 3): isolated
single-prompt runs score description ROUTING in a regime that does not predict embedded
work — 24/24 isolated vs 0/78 embedded. These evals therefore pin the OUTPUT CONTRACT
(what a fired skill must emit), not real-world firing rates; firing is measured organically
by harness_report.

Exit codes: 0 validate/run completed · 1 validation or selftest failure · 2 usage error.
"""
import glob
import json
import os
import re
import subprocess
import sys
import tempfile

VERSION = "1.1.0"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REQUIRED_SHAPES = {"happy", "failure", "near-miss"}
SECTION_RX = re.compile(r"^## [A-Z]", re.M)


def load_corpus(root):
    corpus = {}
    for path in sorted(glob.glob(os.path.join(root, "skills", "*", "evals", "*.json"))):
        skill = path.split(os.sep)[-3]
        corpus.setdefault(skill, []).append((path, json.load(open(path))))
    return corpus


def validate(root, out=sys.stdout):
    p = lambda *a: print(*a, file=out)
    corpus = load_corpus(root)
    if not corpus:
        p("ZERO SCENARIOS FOUND — error, not a clean validation")
        return 2
    bad = 0
    for skill, scenarios in sorted(corpus.items()):
        shapes = set()
        for path, s in scenarios:
            rel = os.path.relpath(path, root)
            errs = []
            for key in ("skills", "query", "files", "expected_behavior"):
                if key not in s:
                    errs.append(f"missing key {key!r}")
            for named in s.get("skills", []):
                if not os.path.isdir(os.path.join(root, "skills", named)):
                    errs.append(f"names unknown skill {named!r}")
            if not s.get("expected_behavior"):
                errs.append("empty expected_behavior")
            if not s.get("query", "").strip():
                errs.append("empty query")
            base = os.path.basename(path)
            for shape, needles in (("happy", ("happy",)), ("failure", ("failure",)),
                                   ("near-miss", ("near-miss", "clean"))):
                if any(n in base for n in needles):
                    shapes.add(shape)
            status = "ok" if not errs else "FAIL: " + "; ".join(errs)
            bad += bool(errs)
            p(f"  {rel}: {status}")
        missing = REQUIRED_SHAPES - shapes
        if missing:
            bad += 1
            p(f"  {skill}: FAIL missing scenario shape(s) {sorted(missing)}")
    p(f"\n  {sum(len(v) for v in corpus.values())} scenarios, {bad} failure(s)")
    return 1 if bad else 0


def run(root, budget_note=True):
    corpus = load_corpus(root)
    if budget_note:
        print("NOTE: --run spends API budget (one headless session per scenario).")
    for _skill, scenarios in sorted(corpus.items()):
        for path, s in scenarios:
            rel = os.path.relpath(path, root)
            with tempfile.TemporaryDirectory() as td:
                for f in s.get("files", []):
                    fp = os.path.join(td, f["path"])
                    os.makedirs(os.path.dirname(fp) or td, exist_ok=True)
                    open(fp, "w").write(f["content"])
                print(f"\n=== {rel}")
                try:
                    r = subprocess.run(
                        ["claude", "-p", s["query"], "--output-format", "json"],
                        capture_output=True, text=True, cwd=td)
                except FileNotFoundError:
                    print("  FAIL: `claude` binary not on PATH")
                    continue
                text = r.stdout
                try:
                    parsed = json.loads(text)
                    text = parsed.get("result", text) if isinstance(parsed, dict) else text
                except Exception:
                    pass
                headers = SECTION_RX.findall(text)
                print(f"  exit={r.returncode}  contract-section headers found: {len(headers)}")
                for eb in s["expected_behavior"]:
                    marker = re.search(r"## \w[\w ]*", eb)
                    if marker and marker.group(0) in text:
                        print(f"  PASS (header grep) {eb[:90]}")
                    else:
                        print(f"  CHECK-MANUALLY     {eb[:90]}")
    return 0


def selftest():
    bad = 0
    checks = 0
    rc = validate(ROOT, out=open(os.devnull, "w"))
    ok = rc == 0
    checks += 1
    bad += (not ok)
    print(f"  {'PASS' if ok else 'FAIL'} real corpus validates (exit {rc})")
    with tempfile.TemporaryDirectory() as td:
        d = os.path.join(td, "skills", "ghost", "evals")
        os.makedirs(d)
        json.dump({"skills": ["no-such-skill"], "query": "", "files": []},
                  open(os.path.join(d, "001-happy.json"), "w"))
        rc = validate(td, out=open(os.devnull, "w"))
        ok = rc == 1
        checks += 1
        bad += (not ok)
        print(f"  {'PASS' if ok else 'FAIL'} planted-bad corpus goes red (exit {rc})")
        rc = validate(os.path.join(td, "empty-root"), out=open(os.devnull, "w"))
        ok = rc == 2
        checks += 1
        bad += (not ok)
        print(f"  {'PASS' if ok else 'FAIL'} zero scenarios exits 2 (exit {rc})")
    print(f"\n  selftest: {bad} failure(s)")
    print(f"SELFTEST-SUMMARY checks={checks} failures={bad}")
    return 1 if bad else 0


def main(argv):
    args = argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0 if args else 2
    if args[0] == "--version":
        print(f"run-skill-evals {VERSION}")
        return 0
    if args[0] == "--selftest":
        return selftest()
    if args[0] == "--validate":
        return validate(ROOT)
    if args[0] == "--run":
        return run(ROOT)
    sys.stderr.write(f"unknown argument: {args[0]!r}\nrun --help\n")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
