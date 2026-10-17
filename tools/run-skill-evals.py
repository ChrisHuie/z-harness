#!/usr/bin/env python3
"""run-skill-evals — the authoring skills' contract evals.

Corpus: `skills/<name>/evals/*.json`, schema per craft-skill Step 2:
  {"skills": [...], "query": "...", "files": [{"path","content"}], "expected_behavior": [...]}

Coverage manifest: `release/evals.json` lists EVERY skill as tested or exempt. A skill that is
absent from it is an unlisted item; an exempt skill carries a reason and has no scenarios; a
tested skill has scenarios and the doctrine's three shapes. The manifest, not SKILL.md
frontmatter, carries coverage because the renderer rejects unknown frontmatter keys.

Shrink-only baseline: `contracts/worklists.json` records the unlisted skills deliberately left
open (its `C13` list; its `C12` list serves the gate's claim-binding check). Validation is
green while the live unlisted set equals or is a subset of the baseline, red on any unlisted
skill not in it, and red when the baseline names a skill that is no longer unlisted, so the
baseline can only shrink by a deliberate edit in the same change that fixes the item. The
items still print, as a worklist. Every other manifest defect is a plain failure.

Two modes, deliberately separated by cost:

  --validate   OFFLINE, free. Schema-checks every scenario, asserts each named skill
               exists, each scenario has >=1 expected behavior, each skill has the
               doctrine's three shapes (happy / failure / near-miss), and the coverage
               manifest lists every skill. Safe for CI.
  --run        SPENDS API BUDGET. Validates the manifest and corpus first and executes
               nothing when that fails. Then runs each scenario headless (`claude -p` in a
               temp cwd with the scenario's files materialized) and greps the result for the
               MECHANICAL markers only (contract section headers). Everything beyond a
               header grep is judgment: those rows print CHECK-MANUALLY with the expected
               behavior, never PASS. A scenario grades only when its child exited 0 and
               every marker is present. A scenario the manifest marks `required` must grade;
               any CHECK-MANUALLY on it, a failed child, or a required scenario the runner
               did not complete (reconciled after the loop) makes --run exit non-zero, as
               does a runner error on any scenario. Manual, never scheduled.

Known measurement bound (recorded in the harness record, report-trigger Part 3): isolated
single-prompt runs score description ROUTING in a regime that does not predict embedded
work — 24/24 isolated vs 0/78 embedded. These evals therefore pin the OUTPUT CONTRACT
(what a fired skill must emit), not real-world firing rates; firing is measured organically
by harness_report.

Exit codes: 0 validate/run completed · 1 validation, grading, or selftest failure · 2 usage
error or an empty corpus.
"""
import glob
import json
import os
import re
import subprocess
import sys
import tempfile

VERSION = "1.3.0"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REQUIRED_SHAPES = {"happy", "failure", "near-miss"}
SECTION_RX = re.compile(r"^## [A-Z]", re.M)
MANIFEST = "release/evals.json"
MANIFEST_SCHEMA_VERSION = 1
MANIFEST_TOP_LEVEL_KEYS = {"schema_version", "note", "skills"}
MANIFEST_STATUSES = {"tested", "exempt"}
MANIFEST_ENTRY_KEYS = {"status", "required", "reason"}
WORKLISTS = "contracts/worklists.json"
WORKLIST_SCHEMA_VERSION = 2
# Schema 1 differs only in the C12 item shape; it loads, and its items meet the same
# shape rule, so a schema 1 file with legacy text keys fails on the first key.
WORKLIST_SCHEMA_VERSIONS = (1, 2)
WORKLIST_KEYS = {"schema_version", "note", "C12", "C13"}
WORKLIST_C12_ITEM_KEYS = {"file", "kind", "key", "display"}
WORKLIST_KEY_SHAPE = re.compile(r"sha256:[0-9a-f]{64}")


def load_corpus(root):
    corpus = {}
    for path in sorted(glob.glob(os.path.join(root, "skills", "*", "evals", "*.json"))):
        skill = path.split(os.sep)[-3]
        corpus.setdefault(skill, []).append((path, json.load(open(path))))
    return corpus


def skill_names(root):
    skills_dir = os.path.join(root, "skills")
    if not os.path.isdir(skills_dir):
        return []
    return sorted(name for name in os.listdir(skills_dir)
                  if os.path.isfile(os.path.join(skills_dir, name, "SKILL.md")))


def load_manifest(root):
    """-> (manifest dict or None, error string or None). A missing file is an error."""
    path = os.path.join(root, MANIFEST)
    try:
        raw = open(path, "rb").read()
    except OSError as exc:
        return None, f"{MANIFEST}: unreadable ({exc.strerror or exc})"

    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f"duplicate key {key!r}")
            value[key] = item
        return value

    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=unique)
    except (UnicodeDecodeError, ValueError) as exc:
        return None, f"{MANIFEST}: not valid JSON ({exc})"
    if not isinstance(data, dict):
        return None, f"{MANIFEST}: top level is not an object"
    return data, None


def load_worklists(root):
    """-> (baseline dict or None, error). The shrink-only baseline of items deliberately open.

    `C12` holds claim-binding findings as {file, kind, key, display} objects: key is
    "sha256:" plus the digest of the whole whitespace-collapsed claim text, never a line
    number or a prefix, so line drift keeps an item's identity and any edit to the text is
    a new item; display is the readable form and carries no identity. A key of any other
    shape is refused, so a hand-edited or legacy key fails loudly. `C13` holds the names of
    skills left unlisted in the coverage manifest. A missing or malformed file is an error,
    never an empty baseline.
    """
    path = os.path.join(root, WORKLISTS)
    try:
        raw = open(path, "rb").read()
    except OSError as exc:
        return None, f"{WORKLISTS}: unreadable ({exc.strerror or exc})"

    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f"duplicate key {key!r}")
            value[key] = item
        return value

    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=unique)
    except (UnicodeDecodeError, ValueError) as exc:
        return None, f"{WORKLISTS}: not valid JSON ({exc})"
    if not isinstance(data, dict):
        return None, f"{WORKLISTS}: top level is not an object"
    if set(data) != WORKLIST_KEYS:
        return None, (f"{WORKLISTS}: keys {sorted(data)} differ from {sorted(WORKLIST_KEYS)}")
    if data.get("schema_version") not in WORKLIST_SCHEMA_VERSIONS:
        return None, (f"{WORKLISTS}: schema_version {data.get('schema_version')!r} is not one of "
                      f"{WORKLIST_SCHEMA_VERSIONS}")
    if not isinstance(data.get("note"), str) or not data["note"].strip():
        return None, f"{WORKLISTS}: note must be a non-empty string"
    c12 = data.get("C12")
    if not isinstance(c12, list):
        return None, f"{WORKLISTS}: C12 is not a list"
    seen = set()
    for index, item in enumerate(c12):
        if (not isinstance(item, dict) or set(item) != WORKLIST_C12_ITEM_KEYS
                or not all(isinstance(item[k], str) and item[k] for k in WORKLIST_C12_ITEM_KEYS)):
            return None, (f"{WORKLISTS}: C12[{index}] must be an object with non-empty string "
                          f"keys {sorted(WORKLIST_C12_ITEM_KEYS)}")
        if not WORKLIST_KEY_SHAPE.fullmatch(item["key"]):
            return None, (f"{WORKLISTS}: C12[{index}] key {item['key'][:40]!r} is not sha256: plus "
                          f"64 hex characters; a hand-edited or legacy key is refused")
        identity = (item["file"], item["kind"], item["key"])
        if identity in seen:
            return None, f"{WORKLISTS}: C12 repeats {identity!r}"
        seen.add(identity)
    c13 = data.get("C13")
    if not isinstance(c13, list) or not all(isinstance(n, str) and n for n in c13):
        return None, f"{WORKLISTS}: C13 must be a list of skill names"
    if len(set(c13)) != len(c13):
        return None, f"{WORKLISTS}: C13 repeats a skill"
    return data, None


def ratchet(live, baseline):
    """-> (new, stale): live items absent from the baseline; baseline items no longer live.

    Either list non-empty is red. New items need a deliberate baseline edit in the same
    change; stale items mean the baseline was not shrunk when its item was fixed.
    """
    live, baseline = set(live), set(baseline)
    return sorted(live - baseline), sorted(baseline - live)


def coverage_verdict(root, corpus=None):
    """-> the coverage check's full verdict with the C13 ratchet applied.

    hard            manifest defects that are never ratcheted
    unlisted        every skill absent from the manifest (the live worklist)
    in_baseline     unlisted skills the baseline deliberately leaves open
    new             unlisted skills the baseline does not carry (red)
    stale           baseline skills that are no longer unlisted (red)
    baseline_error  why the baseline could not be read (red)
    """
    problems, summary = validate_coverage(root, corpus)
    hard = [p for p in problems if not p.startswith("unlisted skill ")]
    worklists, error = load_worklists(root)
    baseline = worklists["C13"] if worklists else []
    new, stale = ratchet(summary["unlisted"], baseline)
    return {
        "hard": hard, "unlisted": list(summary["unlisted"]),
        "in_baseline": sorted(set(summary["unlisted"]) & set(baseline)),
        "new": new, "stale": stale, "baseline_error": error, "summary": summary,
    }


def validate_coverage(root, corpus=None):
    """-> (problems, summary). Every skill is listed; every entry is well-formed.

    `problems` is the worklist: one line per defect, each naming the skill or key it is
    about. `summary` counts tested, exempt, unlisted, and unknown entries. Later phases may
    only shrink the unlisted list; this function never widens an exemption on its own.
    """
    corpus = load_corpus(root) if corpus is None else corpus
    names = skill_names(root)
    problems = []
    summary = {"tested": 0, "exempt": 0, "unlisted": [], "unknown": [], "required": 0}
    manifest, error = load_manifest(root)
    if error or manifest is None:
        problems.append(error or f"{MANIFEST}: unreadable")
        summary["unlisted"] = list(names)
        return problems, summary
    extra = sorted(set(manifest) - MANIFEST_TOP_LEVEL_KEYS)
    missing = sorted(MANIFEST_TOP_LEVEL_KEYS - set(manifest))
    if extra:
        problems.append(f"{MANIFEST}: unknown top-level key(s) {extra}")
    if missing:
        problems.append(f"{MANIFEST}: missing top-level key(s) {missing}")
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        problems.append(f"{MANIFEST}: schema_version {manifest.get('schema_version')!r} "
                        f"is not {MANIFEST_SCHEMA_VERSION}")
    entries = manifest.get("skills")
    if not isinstance(entries, dict):
        problems.append(f"{MANIFEST}: skills is not an object")
        summary["unlisted"] = list(names)
        return problems, summary
    for skill in names:
        if skill not in entries:
            summary["unlisted"].append(skill)
            problems.append(f"unlisted skill {skill}: add a tested or exempt entry to {MANIFEST}")
    for skill, entry in sorted(entries.items()):
        if skill not in names:
            summary["unknown"].append(skill)
            problems.append(f"{MANIFEST}: entry {skill!r} names no skill under skills/")
            continue
        if not isinstance(entry, dict):
            problems.append(f"{MANIFEST}: entry {skill!r} is not an object")
            continue
        unknown_keys = sorted(set(entry) - MANIFEST_ENTRY_KEYS)
        if unknown_keys:
            problems.append(f"{MANIFEST}: entry {skill!r} has unknown key(s) {unknown_keys}")
        status = entry.get("status")
        scenarios = corpus.get(skill, [])
        if status not in MANIFEST_STATUSES:
            problems.append(f"{MANIFEST}: entry {skill!r} status {status!r} is not one of "
                            f"{sorted(MANIFEST_STATUSES)}")
            continue
        if status == "tested":
            summary["tested"] += 1
            if not scenarios:
                problems.append(f"{MANIFEST}: {skill} is listed tested but has no "
                                f"skills/{skill}/evals/*.json scenario")
            if "reason" in entry:
                problems.append(f"{MANIFEST}: {skill} is tested; a reason belongs only on "
                                f"an exempt entry")
            required = entry.get("required")
            if not isinstance(required, list) or not all(
                    isinstance(item, str) and item for item in required):
                problems.append(f"{MANIFEST}: {skill}.required must be a list of scenario "
                                f"file names")
            else:
                present = {os.path.basename(path) for path, _ in scenarios}
                if len(set(required)) != len(required):
                    problems.append(f"{MANIFEST}: {skill}.required repeats a scenario")
                for item in required:
                    if item not in present:
                        problems.append(f"{MANIFEST}: {skill}.required names {item!r}, "
                                        f"which is not under skills/{skill}/evals/")
                summary["required"] += len(required)
        else:
            summary["exempt"] += 1
            reason = entry.get("reason")
            if not isinstance(reason, str) or not reason.strip():
                problems.append(f"{MANIFEST}: {skill} is exempt without a reason")
            if "required" in entry:
                problems.append(f"{MANIFEST}: {skill} is exempt; required applies only to "
                                f"a tested entry")
            if scenarios:
                problems.append(f"{MANIFEST}: {skill} is listed exempt but has "
                                f"{len(scenarios)} scenario(s); list it tested")
    return problems, summary


def required_scenarios(root):
    """-> {skill: set(basenames)} the manifest marks required; {} when the manifest is unusable."""
    manifest, error = load_manifest(root)
    if error or manifest is None:
        return {}
    entries = manifest.get("skills")
    if not isinstance(entries, dict):
        return {}
    out = {}
    for skill, entry in entries.items():
        if isinstance(entry, dict) and isinstance(entry.get("required"), list):
            out[skill] = {item for item in entry["required"] if isinstance(item, str)}
    return out


def validate_shapes(root, corpus, out=sys.stdout):
    """-> shape failure count. Prints one line per scenario and per missing shape."""
    p = lambda *a: print(*a, file=out)
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
            # A list holding only blanks is not an expectation. Truthiness accepts [""].
            if not [b for b in (s.get("expected_behavior") or []) if str(b).strip()]:
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
    return bad


def validate(root, out=sys.stdout):
    p = lambda *a: print(*a, file=out)
    corpus = load_corpus(root)
    if not corpus:
        p("ZERO SCENARIOS FOUND — error, not a clean validation")
        p("EVAL-VALIDATE-SUMMARY scenarios=0 skills=0 failures=1 scope=shape-and-coverage exit=2")
        return 2
    bad = validate_shapes(root, corpus, out=out)
    verdict = coverage_verdict(root, corpus)
    summary = verdict["summary"]
    p(f"\n  coverage: {summary['tested']} tested, {summary['exempt']} exempt, "
      f"{len(verdict['unlisted'])} unlisted ({len(verdict['in_baseline'])} in the shrink-only "
      f"baseline {WORKLISTS}), {len(summary['unknown'])} unknown, "
      f"{summary['required']} required scenario(s)")
    for name in verdict["in_baseline"]:
        p(f"  coverage WORKLIST unlisted skill {name}: add a tested or exempt entry to "
          f"{MANIFEST} and remove it from {WORKLISTS}")
    for problem in verdict["hard"]:
        p(f"  coverage FAIL {problem}")
    for name in verdict["new"]:
        p(f"  coverage FAIL unlisted skill {name}: not in the baseline {WORKLISTS}")
    for name in verdict["stale"]:
        p(f"  coverage FAIL stale baseline: {WORKLISTS} C13 lists {name}, which is no longer "
          f"unlisted; shrink the baseline in the same change")
    if verdict["baseline_error"]:
        p(f"  coverage FAIL cannot apply the ratchet: {verdict['baseline_error']}")
    bad += (len(verdict["hard"]) + len(verdict["new"]) + len(verdict["stale"])
            + (1 if verdict["baseline_error"] else 0))
    scenario_count = sum(len(v) for v in corpus.values())
    p(f"\n  {scenario_count} scenarios, {bad} failure(s)")
    code = 1 if bad else 0
    # Shape and coverage, not content: nothing above reads what an expectation asserts, so a
    # scenario whose expectation is inverted still validates. This receipt is evidence that
    # the corpus is well-formed, complete, and accounted for in the manifest, never that any
    # behaviour was graded. Said in the receipt so a green line is not mistaken for
    # behavioural coverage.
    p(
        f"EVAL-VALIDATE-SUMMARY scenarios={scenario_count} skills={len(corpus)} "
        f"failures={bad} scope=shape-and-coverage exit={code}"
    )
    return code


def headless_claude(query, cwd):
    """-> (returncode, result text) from `claude -p`, or (None, '') when the binary is absent."""
    try:
        r = subprocess.run(
            ["claude", "-p", query, "--output-format", "json"],
            capture_output=True, text=True, cwd=cwd)
    except FileNotFoundError:
        return None, ""
    text = r.stdout
    try:
        parsed = json.loads(text)
        text = parsed.get("result", text) if isinstance(parsed, dict) else text
    except Exception:
        pass
    return r.returncode, text


def grade(expected_behavior, text):
    """-> list of (graded: bool, expectation). Only a contract header grep grades."""
    rows = []
    for eb in expected_behavior:
        marker = re.search(r"## \w[\w ]*", eb)
        rows.append((bool(marker and marker.group(0) in text), eb))
    return rows


RUN_RECEIPT = ("EVAL-RUN-SUMMARY scenarios={scenarios} graded={graded} "
               "ungraded_required={ungraded_required} ungraded_optional={ungraded_optional} "
               "missing_required={missing_required} errors={errors} exit={code}")


def run(root, budget_note=True, runner=None, out=sys.stdout):
    """-> 0 when the tree validates and every required scenario executed and graded; else 1.

    Validation runs first, to the same output, and a failure ends the run before the runner
    is invoked, so a missing manifest or an absent required scenario is a failure, never an
    empty required set. A scenario grades only when its child exited 0 and every
    expectation's marker is present. After the loop the manifest's required set is
    reconciled against the scenarios that executed: a required scenario the runner did not
    complete is printed as MISSING REQUIRED and counted as ungraded. A runner that raises is
    an error and makes the run red whatever the scenario's status. `runner(query, cwd) ->
    (returncode, text)` is injectable so these rules can be proven without the CLI.
    """
    p = lambda *a: print(*a, file=out)
    runner = headless_claude if runner is None else runner
    if validate(root, out=out) != 0:
        p("\n  validation failed: nothing executed")
        p(RUN_RECEIPT.format(scenarios=0, graded=0, ungraded_required=0, ungraded_optional=0,
                             missing_required=0, errors=0, code=1) + " reason=invalid-corpus")
        return 1
    corpus = load_corpus(root)
    required = required_scenarios(root)
    if budget_note:
        p("NOTE: --run spends API budget (one headless session per scenario).")
    scenarios_run = graded_scenarios = ungraded_required = ungraded_optional = errors = 0
    executed = set()
    for skill, scenarios in sorted(corpus.items()):
        for path, s in scenarios:
            rel = os.path.relpath(path, root)
            name = os.path.basename(path)
            is_required = name in required.get(skill, set())
            scenarios_run += 1
            with tempfile.TemporaryDirectory() as td:
                for f in s.get("files", []):
                    fp = os.path.join(td, f["path"])
                    os.makedirs(os.path.dirname(fp) or td, exist_ok=True)
                    open(fp, "w").write(f["content"])
                p(f"\n=== {rel}{'  [required]' if is_required else ''}")
                try:
                    code, text = runner(s["query"], td)
                except Exception as exc:
                    errors += 1
                    p(f"  ERROR: runner raised {exc!r}; not executed")
                    continue
            executed.add((skill, name))
            if code is None:
                p("  FAIL: `claude` binary not on PATH")
                rows = [(False, eb) for eb in s["expected_behavior"]]
            else:
                headers = SECTION_RX.findall(text)
                p(f"  exit={code}  contract-section headers found: {len(headers)}")
                if code != 0:
                    p(f"  child exit {code}: not graded")
                rows = grade(s["expected_behavior"], text)
            for ok, eb in rows:
                p(f"  {'PASS (header grep)' if ok else 'CHECK-MANUALLY    '} {eb[:90]}")
            fully_graded = code == 0 and bool(rows) and all(ok for ok, _ in rows)
            graded_scenarios += fully_graded
            if not fully_graded:
                if is_required:
                    ungraded_required += 1
                    p("  UNGRADED REQUIRED: this scenario must grade every expectation mechanically")
                else:
                    ungraded_optional += 1
    missing = sorted((skill, name) for skill, names in required.items() for name in names
                     if (skill, name) not in executed)
    for skill, name in missing:
        ungraded_required += 1
        p(f"\n  MISSING REQUIRED skills/{skill}/evals/{name}: named by {MANIFEST}, not executed")
    code = 1 if (ungraded_required or errors) else 0
    p("\n" + RUN_RECEIPT.format(scenarios=scenarios_run, graded=graded_scenarios,
                                ungraded_required=ungraded_required,
                                ungraded_optional=ungraded_optional,
                                missing_required=len(missing), errors=errors, code=code))
    return code


def selftest():
    bad = 0
    checks = 0

    def chk(label, ok):
        nonlocal bad, checks
        checks += 1
        bad += (not ok)
        print(f"  {'PASS' if ok else 'FAIL'} {label}")

    def reproduction(thread_id, expected_line):
        """Run a reviewer's reproduction script verbatim; it exits 0 only at the expected outcome."""
        path = os.path.join(ROOT, "instruments", "reproductions", "pr-36", f"{thread_id}.py")
        done = subprocess.run([sys.executable, path], cwd=ROOT, capture_output=True, text=True,
                              timeout=600, env=dict(os.environ, ZH_REVIEW_REPRODUCTIONS="nested"))
        return done.returncode == 0 and expected_line in done.stdout

    import io
    corpus = load_corpus(ROOT)
    shape_failures = validate_shapes(ROOT, corpus, out=io.StringIO())
    chk(f"real corpus shape-validates (shape failures={shape_failures})", shape_failures == 0)
    problems, summary = validate_coverage(ROOT, corpus)
    # The real corpus's coverage is a worklist later phases shrink, not a pass/fail of this
    # suite: the gate (harness_check C13) owns that verdict. Printed as an observation so
    # the receipt is not mistaken for coverage.
    print(f"  OBSERVATION real corpus coverage: tested={summary['tested']} "
          f"exempt={summary['exempt']} unlisted={summary['unlisted']} problems={len(problems)}")
    chk("real manifest parses with every listed entry well-formed",
        not [p for p in problems if not p.startswith("unlisted skill")])

    with tempfile.TemporaryDirectory() as td:
        d = os.path.join(td, "skills", "ghost", "evals")
        os.makedirs(d)
        json.dump({"skills": ["no-such-skill"], "query": "", "files": []},
                  open(os.path.join(d, "001-happy.json"), "w"))
        rc = validate(td, out=open(os.devnull, "w"))
        chk(f"planted-bad corpus goes red (exit {rc})", rc == 1)
        rc = validate(os.path.join(td, "empty-root"), out=open(os.devnull, "w"))
        chk(f"zero scenarios exits 2 (exit {rc})", rc == 2)

        # --- coverage manifest: a planted tree with one tested and one exempt skill
        root = os.path.join(td, "coverage")
        for skill in ("alpha", "beta"):
            os.makedirs(os.path.join(root, "skills", skill))
            open(os.path.join(root, "skills", skill, "SKILL.md"), "w").write(
                f"---\nname: {skill}\ndescription: ok\n---\nbody\n")
        evals = os.path.join(root, "skills", "alpha", "evals")
        os.makedirs(evals)
        scenario = {"skills": ["alpha"], "query": "do the thing",
                    "files": [{"path": "x.txt", "content": "x"}],
                    "expected_behavior": ["emits ## Files", "emits ## Validation"]}
        for name in ("001-happy.json", "002-failure.json", "003-near-miss.json"):
            json.dump(scenario, open(os.path.join(evals, name), "w"))
        os.makedirs(os.path.join(root, "release"))
        os.makedirs(os.path.join(root, "contracts"))
        manifest_path = os.path.join(root, MANIFEST)
        baseline_path = os.path.join(root, WORKLISTS)

        def write_manifest(entries, **top):
            data = {"schema_version": MANIFEST_SCHEMA_VERSION, "note": "fixture", "skills": entries}
            data.update(top)
            open(manifest_path, "w").write(json.dumps(data))

        def write_baseline(c13, c12=None, **top):
            data = {"schema_version": WORKLIST_SCHEMA_VERSION, "note": "fixture",
                    "C12": [] if c12 is None else c12, "C13": c13}
            data.update(top)
            open(baseline_path, "w").write(json.dumps(data))

        write_baseline([])

        def coverage():
            return validate_coverage(root)

        good = {"alpha": {"status": "tested", "required": ["001-happy.json"]},
                "beta": {"status": "exempt", "reason": "no behavioural contract to pin"}}
        write_manifest(good)
        problems, summary = coverage()
        chk("coverage control: every skill listed and well-formed is green",
            not problems and summary["tested"] == 1 and summary["exempt"] == 1
            and summary["required"] == 1)
        chk("--validate is green on the control tree", validate(root, out=io.StringIO()) == 0)

        write_manifest({"alpha": good["alpha"]})
        problems, summary = coverage()
        chk("coverage names an unlisted skill as the worklist",
            summary["unlisted"] == ["beta"] and any("unlisted skill beta" in p for p in problems))
        buf = io.StringIO()
        chk("--validate goes red on an unlisted skill the baseline does not carry",
            validate(root, out=buf) == 1 and "FAIL unlisted skill beta: not in the baseline" in buf.getvalue())

        # --- the shrink-only ratchet
        write_baseline(["beta"])
        buf = io.StringIO()
        chk("ratchet: an unlisted skill carried by the baseline is green and still printed",
            validate(root, out=buf) == 0 and "WORKLIST unlisted skill beta" in buf.getvalue()
            and "EVAL-VALIDATE-SUMMARY scenarios=3 skills=1 failures=0" in buf.getvalue())
        verdict = coverage_verdict(root)
        chk("ratchet verdict separates in-baseline, new, and stale",
            verdict["in_baseline"] == ["beta"] and verdict["new"] == [] and verdict["stale"] == []
            and verdict["hard"] == [] and verdict["baseline_error"] is None)
        write_baseline(["beta", "alpha"])
        buf = io.StringIO()
        chk("ratchet: a baseline naming a skill that is no longer unlisted is red (stale)",
            validate(root, out=buf) == 1 and "stale baseline" in buf.getvalue()
            and "lists alpha" in buf.getvalue())
        write_baseline(["beta"])
        write_manifest(good)
        buf = io.StringIO()
        chk("ratchet: fixing the item without shrinking the baseline is red",
            validate(root, out=buf) == 1 and "stale baseline" in buf.getvalue())
        write_baseline([])
        chk("ratchet: the shrunk baseline matching the shrunk (empty) list is green",
            validate(root, out=io.StringIO()) == 0)
        os.remove(os.path.join(root, "skills", "alpha", "evals", "003-near-miss.json"))
        write_manifest({})
        write_baseline(["beta"])
        buf = io.StringIO()
        chk("ratchet: a second unlisted skill outside the baseline is red and named",
            validate(root, out=buf) == 1 and "FAIL unlisted skill alpha: not in the baseline" in buf.getvalue()
            and "WORKLIST unlisted skill beta" in buf.getvalue())
        json.dump(scenario, open(os.path.join(root, "skills", "alpha", "evals", "003-near-miss.json"), "w"))
        write_manifest({"alpha": good["alpha"]})
        open(baseline_path, "w").write("{not json")
        buf = io.StringIO()
        chk("ratchet: a malformed baseline is red, never an empty baseline",
            validate(root, out=buf) == 1 and "cannot apply the ratchet" in buf.getvalue()
            and "not valid JSON" in buf.getvalue())
        os.remove(baseline_path)
        buf = io.StringIO()
        chk("ratchet: a missing baseline is red",
            validate(root, out=buf) == 1 and "cannot apply the ratchet" in buf.getvalue()
            and "unreadable" in buf.getvalue())
        write_baseline(["beta"], c12=[{"file": "x.md", "kind": "stale quote"}])
        chk("baseline loader rejects a C12 item without the file/kind/key/display shape",
            "C12[0]" in (load_worklists(root)[1] or ""))
        write_baseline(["beta"], c12=[{"file": "x.md", "kind": "stale quote", "key": "build the gate",
                                       "display": "build the gate"}])
        chk("baseline loader rejects a C12 key that is not sha256: plus 64 hex characters",
            "is not sha256: plus 64 hex" in (load_worklists(root)[1] or ""))
        write_baseline(["beta"], c12=[{"file": "x.md", "kind": "stale quote",
                                       "key": "sha256:" + "0" * 64, "display": "build the gate"}])
        chk("baseline loader accepts a well-formed digest key",
            load_worklists(root)[1] is None)
        write_baseline(["beta", "beta"])
        chk("baseline loader rejects a repeated C13 skill", "repeats" in (load_worklists(root)[1] or ""))
        write_baseline(["beta"], extra=1)
        chk("baseline loader rejects an unknown top-level key", "differ from" in (load_worklists(root)[1] or ""))
        write_baseline(["beta"], schema_version=3)
        chk("baseline loader rejects a foreign schema version", "schema_version 3 is not one of" in (load_worklists(root)[1] or ""))
        write_baseline(["beta"], schema_version=1)
        chk("baseline loader accepts schema 1 with no C12 items: the item shape, not the number, is the contract",
            load_worklists(root)[1] is None)
        write_baseline(["beta"], schema_version=1, c12=[{"file": "x.md", "kind": "stale quote", "key": "build the gate",
                                                          "display": "build the gate"}])
        chk("baseline loader refuses a schema 1 file carrying a legacy text key",
            "is not sha256: plus 64 hex" in (load_worklists(root)[1] or ""))
        chk("ratchet helper: new and stale are the two set differences",
            ratchet(["a", "b"], ["b", "c"]) == (["a"], ["c"]) and ratchet([], []) == ([], []))
        write_baseline(["beta"])
        write_manifest({"alpha": good["alpha"]})

        write_baseline([])
        write_manifest(dict(good, gamma={"status": "exempt", "reason": "ghost"}))
        problems, summary = coverage()
        chk("coverage rejects an entry naming no skill",
            summary["unknown"] == ["gamma"] and any("names no skill" in p for p in problems))

        write_manifest(dict(good, beta={"status": "exempt"}))
        chk("coverage rejects an exempt entry without a reason",
            any("exempt without a reason" in p for p in coverage()[0]))
        buf = io.StringIO()
        chk("--validate exits red on a hard coverage defect the ratchet never carries",
            validate(root, out=buf) == 1 and "coverage FAIL" in buf.getvalue()
            and "exempt without a reason" in buf.getvalue())

        write_manifest(dict(good, beta={"status": "exempt", "reason": ""}))
        chk("coverage rejects a blank reason",
            any("exempt without a reason" in p for p in coverage()[0]))

        write_manifest(dict(good, alpha={"status": "exempt", "reason": "has scenarios"}))
        chk("coverage rejects an exempt skill that has scenarios",
            any("listed exempt but has 3 scenario(s)" in p for p in coverage()[0]))

        write_manifest(dict(good, beta={"status": "tested", "required": []}))
        chk("coverage rejects a tested skill without scenarios",
            any("listed tested but has no" in p for p in coverage()[0]))

        write_manifest(dict(good, alpha={"status": "tested", "required": ["009-missing.json"]}))
        chk("coverage rejects a required scenario that does not exist",
            any("009-missing.json" in p for p in coverage()[0]))

        write_manifest(dict(good, alpha={"status": "tested", "required": ["001-happy.json", "001-happy.json"]}))
        chk("coverage rejects a repeated required scenario",
            any("repeats a scenario" in p for p in coverage()[0]))

        write_manifest(dict(good, alpha={"status": "tested", "required": [], "extra": 1}))
        chk("coverage rejects an unknown entry key",
            any("unknown key(s) ['extra']" in p for p in coverage()[0]))

        write_manifest(dict(good, alpha={"status": "verified", "required": []}))
        chk("coverage rejects an unknown status",
            any("status 'verified' is not one of" in p for p in coverage()[0]))

        write_manifest(good, schema_version=2)
        chk("coverage rejects a foreign schema version",
            any("schema_version 2 is not 1" in p for p in coverage()[0]))

        write_manifest(good, generated_by="tool")
        chk("coverage rejects an unknown top-level key",
            any("unknown top-level key(s) ['generated_by']" in p for p in coverage()[0]))

        open(manifest_path, "w").write("{not json")
        problems, summary = coverage()
        chk("coverage fails loud on a malformed manifest and lists every skill unlisted",
            any("not valid JSON" in p for p in problems) and summary["unlisted"] == ["alpha", "beta"])

        os.remove(manifest_path)
        problems, summary = coverage()
        chk("coverage fails loud on a missing manifest, never as a clean scan",
            any("unreadable" in p for p in problems) and summary["unlisted"] == ["alpha", "beta"])

        # --- --run: a required scenario that does not grade makes the run red
        write_manifest(good)
        ungraded = lambda _query, _cwd: (0, "prose with no contract headers")
        graded = lambda _query, _cwd: (0, "## Files\nx\n## Validation\ny\n")
        chk("--run exits non-zero when a required scenario is ungraded",
            run(root, budget_note=False, runner=ungraded, out=io.StringIO()) == 1)
        chk("--run exits zero when the required scenario grades every expectation",
            run(root, budget_note=False, runner=graded, out=io.StringIO()) == 0)
        write_manifest(dict(good, alpha={"status": "tested", "required": []}))
        buf = io.StringIO()
        chk("--run with no required scenario reports ungraded rows and still exits zero",
            run(root, budget_note=False, runner=ungraded, out=buf) == 0
            and "ungraded_optional=3" in buf.getvalue())
        write_manifest(good)
        absent = lambda _query, _cwd: (None, "")
        chk("--run counts an absent CLI as ungraded for a required scenario",
            run(root, budget_note=False, runner=absent, out=io.StringIO()) == 1)
        chk("grade passes only a header the result actually contains",
            grade(["emits ## Files", "emits ## Gone"], "## Files\n") == [(True, "emits ## Files"), (False, "emits ## Gone")])

        # --- --run validates first, grades only after a child exit of 0, and reconciles the
        # required set against what executed
        happy = os.path.join(evals, "001-happy.json")
        failure = os.path.join(evals, "002-failure.json")
        json.dump(dict(scenario, query="the required thing"), open(happy, "w"))
        json.dump(dict(scenario, query="the optional thing"), open(failure, "w"))
        buf = io.StringIO()
        chk("--run control: the required scenario is present, every child exits 0 with every marker, "
            "exit 0",
            run(root, budget_note=False, runner=graded, out=buf) == 0
            and "EVAL-RUN-SUMMARY scenarios=3 graded=3 ungraded_required=0 ungraded_optional=0 "
                "missing_required=0 errors=0 exit=0" in buf.getvalue())
        calls = []

        def counting(query, _cwd):
            calls.append(query)
            return 0, "## Files\nx\n## Validation\ny\n"

        os.remove(happy)
        buf = io.StringIO()
        rc = run(root, budget_note=False, runner=counting, out=buf)
        chk("--run refuses a tree whose required scenario is absent before invoking the runner",
            rc == 1 and not calls and "exit=1 reason=invalid-corpus" in buf.getvalue()
            and "001-happy.json" in buf.getvalue())
        json.dump(dict(scenario, query="the required thing"), open(happy, "w"))
        os.remove(manifest_path)
        buf = io.StringIO()
        rc = run(root, budget_note=False, runner=counting, out=buf)
        chk("--run with no manifest is a validation failure with the runner never invoked, not an "
            "empty required set",
            rc == 1 and not calls and "exit=1 reason=invalid-corpus" in buf.getvalue()
            and "unreadable" in buf.getvalue())
        write_manifest(good)

        def failing_child(query, _cwd):
            return (1 if query == "the required thing" else 0), "## Files\nx\n## Validation\ny\n"

        buf = io.StringIO()
        rc = run(root, budget_note=False, runner=failing_child, out=buf)
        chk("--run does not grade a required scenario whose child exited 1, even with every marker "
            "present",
            rc == 1 and "child exit 1: not graded" in buf.getvalue()
            and "scenarios=3 graded=2 ungraded_required=1 ungraded_optional=0 missing_required=0 "
                "errors=0 exit=1" in buf.getvalue())

        def raising(query, _cwd):
            if query == "the required thing":
                raise RuntimeError("transport down")
            return 0, "## Files\nx\n## Validation\ny\n"

        buf = io.StringIO()
        rc = run(root, budget_note=False, runner=raising, out=buf)
        chk("--run reconciles the required set against executed scenarios: one the runner did not "
            "complete is MISSING REQUIRED and counted as ungraded",
            rc == 1 and "MISSING REQUIRED skills/alpha/evals/001-happy.json" in buf.getvalue()
            and "scenarios=3 graded=2 ungraded_required=1 ungraded_optional=0 missing_required=1 "
                "errors=1 exit=1" in buf.getvalue())

        def raising_optional(query, _cwd):
            if query == "the optional thing":
                raise RuntimeError("transport down")
            return 0, "## Files\nx\n## Validation\ny\n"

        buf = io.StringIO()
        rc = run(root, budget_note=False, runner=raising_optional, out=buf)
        chk("--run is red on a runner error for an optional scenario: an error is not a pass",
            rc == 1 and "missing_required=0 errors=1 exit=1" in buf.getvalue())
        json.dump(scenario, open(happy, "w"))
        json.dump(scenario, open(failure, "w"))

        chk("review reproduction 4294811785: a required scenario absent from the corpus makes --run red",
            reproduction(4294811785, "validate_exit= 1 run_exit= 1"))
        chk("review reproduction 4294811795: the three child controls exit 0, 1, 1",
            reproduction(4294811795, "child_exit= 1 EVAL-RUN-SUMMARY scenarios=3 graded=0 "
                                     "ungraded_required=1 ungraded_optional=2 missing_required=0 "
                                     "errors=0 exit=1"))

    print(f"\n  selftest: {bad} failure(s)")
    print(f"SELFTEST-SUMMARY suite=run-skill-evals checks={checks} failures={bad}")
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
