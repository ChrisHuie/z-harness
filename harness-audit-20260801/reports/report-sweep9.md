Tree restored exactly — same SHA, same 4 pre-existing modifications, zero files of mine remaining.

# Detector verification by execution — dtest4 (the nine untested)

**Verdicts: 8 CONFIRMED-DEFECT, 1 effectively CLEAN.** Every run used `out=$(…2>&1); rc=$?` with no pipe. Artifacts: `/private/tmp/claude-501/-Users-quantum-Documents-GitHub-agenticads-sim-plan/e2367c8b-0c8b-43ae-a5d4-98ce3fbcecea/scratchpad/dtest4/`

Two of my own test bugs were caught by controls before they became verdicts: zsh does not word-split unquoted `$args` (a "detector ignores extra roots" claim I nearly filed — it was my shell), and a hand-built drift fixture that wasn't the shape I assumed. Both fixed and re-run.

**Live access**: I ran SDK-dependent detectors read-only via `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python` rather than `uv run` (no venv sync, no writes). Four `.pyc` files did land in salesagent's gitignored `__pycache__` from early imports before I set that variable; I removed them. Final state verified identical to session start: same HEAD `6881e8d`, same four pre-existing modified test files, zero files of mine remaining.

---

## 1. `bump_check` — CONFIRMED-DEFECT (highest value; the failure is *shipped*)

Its exit-1 arm is **unreachable**, and the one command the harness prescribes for an `adcp` bump prints a false all-clear.

```
cd .../dtest4/ra/root; PATH=<uv-shim>:$PATH PYTHONPATH=<fake-pin>
out=$(python3 bump_check.py 2>&1); rc=$?
```

| scenario | rc | decisive output |
|---|--:|---|
| POS CONTROL — a self-test genuinely fails | **2** | `FAIL recovery_audit` … `STOP (exit 2)` |
| NEG CONTROL — pin 3.1.1 == both snapshots | **0** | `…both spec snapshots are fresh` (correct) |
| **EXPLOIT — pin moved to 3.2.0, both snapshots stale** | **0** | `Self-tests pass and both spec snapshots are fresh against the current pin.` |

In the exploit run `bump_check` **printed the moved pin itself** (`bump-check — pinned adcp/spec: 6.6.0 3.2.0`), then ran `recovery_audit` and `sdk_spec_drift`, both of which exited 2 with their full `STALE SNAPSHOT (hard fail)` text — and displayed `ctx recovery_audit: (no output)` before asserting freshness.

Two independent causes, both verified at the operand level:

- **`bump_check.py:76`** — `is_stale = "WARNING" in out and "stale" in out.lower()`. `grep -rn 'WARNING'` across all 13 detectors returns **nothing** — no detector ever emits that token. The first operand is permanently false, so `stale` is always `[]`, `:83` is never entered and `return 1` at `:86` is dead code. The docstring's `Exit: 1 = a snapshot is stale` cannot occur.
- **`bump_check.py:73-80`** — the scan loop discards `r.returncode` entirely. Both detectors returned 2; invisible. `_headline` reads only `r.stdout`, but both write the stale message to **stderr**, so the sentence naming the problem is collected into `out` (used only by the dead string test) and never shown.

**This is quoted as reassurance in shipped artifacts.** `/Users/quantum/Documents/ComputedChaos/salesagent/.claude/notes/pr1682-rereview-2026-07-29-round4.md:23` — "`bump_check`: 4/4 self-tests pass; both spec snapshots FRESH vs pin adcp 6.6.0 / spec 3.1.1"; also `.claude/notes/pr1575-rereview-2026-07-20.md:46`, `.claude/reports/full-review-pr1650-rereview-20260721.md:84`, `.claude/reports/full-review-pr1546-20260720_1314.md:131`, `.claude/notes/pr1682-rereview-2026-07-22.md:109`. And `.claude/rules/private/harness-upgrade-spec.md:72` prescribes exactly the unreachable arm: "ACTIONABLE signals are a self-test failure (exit 2) or **a stale-snapshot warning after a pin move (exit 1)** … the drill to run on every `adcp` bump."

*Honest caveat*: at today's pin those quoted verdicts are true — 3.1.1 matches both snapshots. The defect is that the sentence prints identically when they are stale, so it is not evidence.

**Fix** — key on the exit code the detectors already document (`2` = stale/error), and read the headline from both streams:
```python
r = _run(name, uv, args)
out = r.stdout + r.stderr
if r.returncode == 2:
    stale.append(name); print(f"  STALE {name}: {_headline(out)}"); continue
```
Drop the `"WARNING" in out` operand. Also fix `main()` (`:47`, `:94`) to take `argv` — already confirmed by dtest3, not re-derived here.

---

## 2. `changed_field_grading_coverage` — CONFIRMED-DEFECT (three independent)

Controls: `pos` (graded, unbound, no step def) → **rc=1** `✗ DORMANT GRADER`; `neg` (bound + step def) → **rc=0**.

**(a) An unresolvable base ref produces a confident green.** `changed_fields` (`:109-114`) calls `subprocess.run` **without `check=True`**, so git's exit 128 raises nothing, `.stdout` is empty, `fields=[]`.

```
cd .../dtest4/cfgc/gitrepo          # origin/main genuinely absent
python3 changed_field_grading_coverage.py                      -> rc=0
   "No BDD-graded changed field found via diff origin/main...HEAD …
    (Either no protocol field changed, or none is asserted in a .feature.)"
python3 changed_field_grading_coverage.py --base basemain       -> rc=1  ✗ DORMANT GRADER
```
Identical wording to a real clean run, and the default base is `origin/main` — absent in shallow clones, fork clones with a differently-named remote, and `fetch-depth: 1` checkouts. `--base=REF` and `--fields=a,b` (equals form) are silently dropped and fall back to the same default: also rc=0.

**(b) A mention marks a feature "bound"; a comment marks a field "referenced".** Both halves of the AND fail at once, and the detector reports the opposite of the truth:

```
.../dtest4/cfgc/x_mention/   -> rc=0
  "• likely-live — `widget_count` graded in ['BR-UC-900.feature'] (bound + step-def-referenced)"
```
The only occurrence of the filename is inside a docstring reading *"this scenario is not wired up yet — still need to bind"*, and the only occurrence of the field is a `#` comment reading *"still TODO — no step implements it"*. `bound_feature_names` (`:159-162`) accepts any `.feature` string literal in a file containing the substring `scenario`; `stepdef_referenced_fields` (`:178-181`) greps a raw concatenated blob. This is the #1677 miss-class the detector exists for, passing green.

**(c) The field regex misses the common wire forms.** `FIELD_ON_ADDED_LINE` (`:52`) requires the identifier at line start and ≥4 characters:

| added line | extracted |
|---|---|
| `+    widget_count: int = 0` | ✓ |
| `+        return {"widget_count": self.widget_count}` | ✗ |
| `+        return Envelope(cpm=self.cpm, …)` | ✗ |
| `+    cpm: float = 0.0` / `url` / `ids` | ✗ (≤3 chars) |
| `+    resp = MediaBuyResponse(widget_count=5)` | extracts `resp`, not the field |

`url` (3×), `cpm` (2×) and `key` (1×) are real ≤4-space-indent schema fields in live `src/core/schemas/` — unextractable even in the exact Pydantic form the regex targets.

**Also (latent)**: `scenarios("features")` — pytest-bdd's directory-binding form — yields a **false positive** (`x_dirbind` → rc=1 `no scenarios() binding`). Not live: all 20 live bindings use the explicit-file form, and no phantom bind exists in the live tree.

**Fix**: pass `check=True` (or test `returncode`) in `changed_fields` and return `2` on a bad base; parse `--base=`/`--fields=`; match `scenarios(...)`/`@scenario(...)` **call nodes** via AST rather than any quoted string, and resolve directory arguments; require the field token in a step-def *decorator or body* rather than the raw blob; drop the `{3,}` floor and match `["']field["']\s*:` and `\bfield\s*=` anywhere on an added line.

---

## 3. `recovery_audit` — CONFIRMED-DEFECT (the hard-fail gate is silently skippable)

`main()` (`:259`) is `if pin and pin != SNAPSHOT_SPEC_VERSION:` — a compound guard whose second operand is never evaluated when `pin` is falsy, and `pin` comes from a bare `except Exception: pin = None` (`:248-253`).

| fake `adcp` (snapshot = 3.1.1) | rc | result |
|---|--:|---|
| returns `"3.1.1"`, no divergence | 0 | clean (NEG CONTROL) |
| returns `"3.1.1"`, divergence injected | 1 | `BadErr: SERVICE_UNAVAILABLE recovery=terminal (spec: transient)` (POS CONTROL) |
| returns `"3.2.0"` | **2** | `STALE SNAPSHOT (hard fail)` (POS CONTROL — gate works) |
| **accessor renamed** (spec really 3.2.0) | **0** | full CLEAN text, no mention of the pin |
| **returns `""`** | **0** | full CLEAN text |
| **accessor raises** | **0** | full CLEAN text |
| renamed accessor **+ divergence present** | **1** | divergence reported against a snapshot never verified |

The docstring says the detector "self-checks against the installed SDK's spec version and **HARD-FAILS** if the pin moved … a warning that audits anyway is one the pin-bump ignored, which is exactly how this snapshot went stale once." An accessor rename is *most likely precisely on a bump* — the moment the gate matters. The skip is silent: nothing in the CLEAN output says the pin check did not run.

**`scope_vacuity` matcher gaps** (`:228`) — positive control `raise TaskNotFoundError(…)` reported; all of these missed: `raise errors.TaskNotFoundError(…)` (dotted module prefix — and the a2a module is literally `a2a.utils.errors`), `raise InternalError` (bare class), `raise exc` (variable), line-continuation. `--scope=path` (equals form) is silently ignored and prints no probe line at all.

**Live: accurate.** `--scope src` reports 25 A2AError raise sites; an exhaustive matcher finds only 3 more, all prose in comments/docstrings — correctly excluded. No live undercount; the gaps are latent.

**Fix**: replace `if pin and …` with an explicit three-way — if `pin` is falsy, print and `return 2` ("could not derive the pin; the freshness gate did not run"). Extend the regex to `(?:[A-Za-z_]\w*\.)*` prefixes and make the trailing `\(` optional. Parse `--scope=`.

---

## 4. `github_workflow_duplication` — CONFIRMED-DEFECT (blind to its own stated defect class)

The docstring exists for "copy-paste-then-**drift** in workflow/composite `run:` bodies — exactly where a divergence between two verifiers is most dangerous." Drift is what breaks it.

```
bodies rebuilt deterministically at .../dtest4/gwd/
pos       two verbatim 10-line bodies      longest-contiguous=10  -> rc=1  [10 lines]
x_drift   same two, ONE line inserted mid-block   longest-contiguous=5  -> rc=0
          "no cross-body duplicated blocks at/above threshold."
x_reorder same two, one line changed at the END   longest-contiguous=9  -> rc=1
```

9 of 10 lines identical — a 90% clone between two signature verifiers — reported clean. `_longest_common_block` (`:94`) scores only the single longest *contiguous* run and never accumulates matched lines across a gap, so one inserted line halves the score below `min_lines`. `x_reorder` isolates the mechanism: end-drift survives, mid-drift does not.

**Scan-set gap**: `_iter_run_bodies` (`:66-91`) reads only `jobs[].steps[].run` and `runs.steps[].run`. The identical clone expressed as two `actions/github-script` `with: script:` bodies gives `0 run-bodies scanned` → rc=0. Also `roots = [r for r in roots if r.exists()] or roots` (`:270`) means a typo'd path yields `0 run-bodies scanned` → rc=0.

**Live: genuinely clean.** 41 run-bodies; I swept all pairs with `difflib.SequenceMatcher` for *total* identical lines regardless of contiguity — max is 4, and **0 pairs** share ≥6 identical lines while falling under the contiguous threshold. The #1669 duplication was single-sourced (composite actions `_install-uv`, `_postgres`, `_pytest`, `_setup-env` exist); no `github-script` blocks exist. The defect is latent here.

**Fix**: score on `sum(bl.size for bl in SequenceMatcher(None,a,b).get_matching_blocks())` (and/or `.ratio()`), keeping `min_lines` on the aggregate; report the longest contiguous run only as detail. Add `step.with.script` to the body extractor. Make a nonexistent root `return 2`.

---

## 5. `fixme_format` — CONFIRMED-DEFECT (three silent false-green paths)

Matcher controls pass: `# FIXME(salesagent-9f2)` → flagged, `# FIXME(#1566)` → clean, `--selftest` 4/4 + 0/0.

```
cd .../dtest4/ff/repo   (src/pos.py holds a real violation)
python3 fixme_format.py srcc          -> rc=0  "No non-compliant FIXME markers found."
cd repo/sub && python3 fixme_format.py -> rc=0  "No non-compliant FIXME markers found."   # SILENT
cd /a/non-git/dir && python3 …         -> rc=0  same line (git's fatal leaks to stderr)
```
`scan()` (`:74`) hardcodes `repo = Path.cwd()`; `_git_tracked_py` returns `[]` on `CalledProcessError` (`:68-69`); `main` then prints the all-clear. The subdirectory case is fully silent — no error, no file count. Both `ssot_docstring_duplication` and `pr_import_cycle` print `ERROR: … (run from repo root)` and return 2 in the same situation; `fixme_format` has no such guard.

**Matcher gap**: `# FIXME (salesagent-9f2)` — one space before the paren — is invisible (`:52` `body.startswith("FIXME(")`). So is lowercase `fixme(`. My hypothesis that a syntax/token error silently drops markers was **wrong** — `tokenize` handled both fixtures and flagged the markers; I withdraw it.

**argv**: `--selftests` (typo) and `--bogus-flag` are silently ignored and run a full scan (`:111`, `:113`). On a clean tree a typo'd `--selftests` returns rc=0 with "No non-compliant FIXME markers found." — indistinguishable to a caller from a passing self-test.

**Live: scan set is complete.** 87 non-compliant markers across 16 files, **0 outside `src/` + `tests/`**, and `git grep` for `#\s*FIXME\s+\(` in `.py` returns nothing. No live analogue of the dtest3 `CLAUDE.md` finding here. (Note the standing rc=1: like `citation_freshness`, its exit code carries no per-run information on the live tree.)

**Fix**: resolve the repo root with `git rev-parse --show-toplevel` instead of `cwd`, and `return 2` when zero files are scanned. Accept `FIXME\s*\(` and match case-insensitively. Reject unrecognized `-`-prefixed argv.

---

## 6. `pr_import_cycle` — CONFIRMED-DEFECT (relative imports are invisible)

Controls: `pos` (the #1534 shape) → **rc=1** with the exact edge pair; `neg` → **rc=0**.

| fixture | rc | result |
|---|--:|---|
| `x_rel` — **the identical cycle** written `from .b import thing` / `from .a import other` | **0** | `No first-party import cycles found.` |
| `x_3cycle` — a→b→c→a held by one lazy edge | **0** | `No first-party import cycles found.` |
| `x_importlib` — lazy edge via `importlib.import_module("src.core.a")` | **0** | `No first-party import cycles found.` |
| `x_typecheck` — `if TYPE_CHECKING:` import (never executes) | 0 | reported as a MODULE-LEVEL CYCLE (false positive) |

The positive control and its relative-import rewrite differ only in rc — 1 vs 0. Cause: `pr_import_cycle.py:104` — `isinstance(node, ast.ImportFrom) and node.level == 0`. Every `node.level > 0` import is dropped from the graph. The 2-module scope is disclosed in the docstring, but the **output line is an unqualified absolute claim**.

**Live: latent, with real exposure.** The default run scans 282 modules → rc=1, 2 papered-over + 3 module-level cycles. **62 relative imports across 17 files in `src/` never enter the graph** (11 in `src/adapters/__init__.py`, 8 in `src/core/tools/creatives/__init__.py`, 4 in `src/core/tools/creatives/_sync.py`). I resolved all of them properly and re-ran the cycle detection: 57 edges added, **0 new cycles** — so the blindness is real but currently costs nothing.

**Fix**: resolve `node.level > 0` against the module's package (`__init__.py` modules are their own package); replace the pairwise scan with Tarjan SCC so cycles of any length are found, marking any SCC containing a lazy edge; skip imports under an `if TYPE_CHECKING:` guard; change the clean line to name the scope actually searched.

---

## 7. `suggestion_audit` — CONFIRMED-DEFECT (two false docstring claims; no live violation found)

**(a) Its ground truth is a deliberately frozen snapshot, and it has no staleness check.** The docstring: *"Grounds against the repo's pinned error-code.json enumMetadata … **moves with the repo pin, no separate snapshot to rot**."* Executed:

```
fixture tests/fixtures/adcp_schemas_pinned/enums/error-code.json : 64 codes
recovery_audit / sdk_spec_drift snapshots @ pin 3.1.1            : 92 codes each (identical to each other)
missing from the fixture                                          : 28 codes
```
`tests/fixtures/adcp_schemas_pinned/_refresh.py:4-11` states the source is adcp commit `04f59d2d5` (tag v3.1-04f59d2d5, 2026-05-13) and that "This commit is an INTENTIONAL, frozen reference point … we deliberately do NOT track it." Its last commit is `9ac08dad3` — "canonical error-code reconciliation **on adcp 5.7**". The live pin is adcp 6.6.0 / spec 3.1.1. So the fixture does not move with the pin, and unlike its two sibling detectors `suggestion_audit` has **no `SNAPSHOT_SPEC_VERSION` and no hard-fail** — because it believes it needs none. Any suggestion for one of the 28 codes is auto-classified `UNGROUND`, and CROSS-contamination cannot fire for those codes' canonical texts at all.

**(b) "reaches the wire two ways, and BOTH are audited here" is false.** The detector audits **3** `*_SUGGESTION` constants + **2** class defaults. An AST sweep of `src/` finds **48 inline `suggestion="…"` literals at raise sites** across 10 files (`src/core/tools/media_buy_create.py` ×11, `src/core/schemas/_base.py` ×5, `src/core/helpers/account_helpers.py` ×6, `src/core/database/repositories/media_buy.py`, …), audited by neither surface and mentioned nowhere. `recovery_audit` explicitly documents its analogous blind spot; this one asserts completeness instead.

**No live violation in the gap** — I applied the CROSS check to all 48 unscanned sites: **0** hold another code's canonical enum text. And all 3 codes currently in use fall inside the fixture's 64, so the stale ground truth is not producing a wrong verdict today.

Live baseline: rc=1, 3 DIVERGE findings (all `AUTH_REQUIRED` text); 0 NO-WIRE-ORACLE.

**Fix**: add a pin self-check — compare `adcp.get_adcp_spec_version()` against a version recorded alongside the fixture and hard-fail on drift, as the two siblings do; or ground against the same 92-code snapshot. Extend surface coverage to inline `suggestion=` kwargs at raise sites (AST, resolving the enclosing exception class's wire code), or state the limit in the docstring. Separately, `_has_wire_oracle` (`:163`) greps raw text for `pinned_error_code_suggestion("CODE")`, so a commented-out or `@pytest.mark.skip`-ed occurrence counts as an oracle — I did not find a live instance.

---

## 8. `ssot_docstring_duplication` — CONFIRMED-DEFECT (precision; over-reports, does not false-green)

The index (`:80-83`) keys on bare `node.name` with no class qualification, so any two same-named methods on unrelated classes collide. Live run: rc=1, `✗ SSOT-CONTRADICTED (7)`. Resolving each to its enclosing scope:

| symbol | verdict |
|---|---|
| `record_success` | **spurious** — `IdempotencyAttemptRepository.record_success` vs `CircuitBreaker.record_success`, unrelated domains |
| `identity_for` | collision — `BaseTestEnv` vs `AccountSyncEnv` (likely a legitimate override) |
| `_create_kwargs`, `_make_identity`, `make_identity` | cross-scope collisions (module-level defs mixed with `TestX` class methods) |
| `_assert_error_outcome`, `given_tenant_auto_approval` | same scope — plausible genuine twins |

Five of seven involve cross-scope collisions. Check A is labelled "high precision" and "close to mechanical" and is the only check that sets rc=1. The docstring does concede "even A can fire on a legitimately-overridden name", so this is partly self-disclosed — and it over-reports, which is the safe direction. I rank it below the false greens. (`_make_identity` at 25 definition sites is a genuine DRY finding regardless.)

dtest3's N5/N6/N8 stand; I did not re-derive them.

**Fix**: index on qualified name (`Class.method`) and treat a bare-name match as a separate lower-confidence bucket; skip names whose definitions are in a subclass relationship.

---

## 9. `sdk_spec_drift` — effectively CLEAN

Same `if pin and pin != SNAPSHOT_SPEC_VERSION` line (`:211`), but materially more robust because the accessor call sits inside the same `try` as the import (`:196-204`):

| fake `adcp` | rc | result |
|---|--:|---|
| `"3.1.1"` | 0 | clean (NEG CONTROL) |
| `"3.2.0"` | **2** | `STALE SNAPSHOT (hard fail)` (POS CONTROL) |
| accessor **renamed** | **2** | `ERROR: could not import the adcp SDK: module 'adcp' has no attribute…` — **loud** |
| returns `""` | 0 | gate silently skipped |

Only the empty-string path defeats it — the least plausible of the three that defeat `recovery_audit`. Its snapshot is consistent with `recovery_audit`'s (92 codes, identical sets, both at 3.1.1). Live: rc=0, 92 spec / 38 SDK, 3 FORCED codes. Unrecognized flags are silently ignored (`:194`), same class as the others. **Fix**: same explicit falsy-pin branch; reject unknown argv.

---

## What I could not test

- **`bump_check` against the real venv end-to-end.** Proving the stale path required a moved pin, so I used a hermetic fake `adcp` plus a `uv` shim that forwards to `python3`. The real detectors ran unmodified; only the pin source was faked.
- **Whether the 87 live `fixme_format` markers, the 143 `citation_freshness` hits, or the 3 live `suggestion_audit` DIVERGE findings are individually correct.** I established baselines, not adjudications.
- **`ssot`'s `identity_for`** — I confirmed the two classes differ but did not check whether `AccountSyncEnv` subclasses `BaseTestEnv`, which would make it a legitimate override rather than a collision.
- **Whether any shipped artifact was materially misled by one of the false greens.** The `bump_check` freshness line is quoted in five artifacts, but at today's pin it happens to be true — I found no artifact whose conclusion was wrong because of it. The `recovery_audit` vacuity quotes I checked went the *right* way: `.claude/notes/pr1719-ledger-2026-07-28.md:68` and `.claude/reports/full-review-pr1720-rereview-20260728.md:100` both name the vacuity instead of quoting CLEAN as reassurance.