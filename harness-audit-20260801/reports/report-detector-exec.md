All tests run. Here is the report.

---

# Detector verification by execution — dtest3

**Scope caveat up front.** Every verdict below comes from a run with `out=$(…); rc=$?` — no pipes between the detector and `$?`. My first selftest sweep returned `rc=127` for all 13 detectors; that was **my** bug (`timeout` does not exist on this macOS), caught by a sanity control before I judged anything. Artifacts: `/private/tmp/claude-501/-Users-quantum-Documents-GitHub-agenticads-sim-plan/e2367c8b-0c8b-43ae-a5d4-98ce3fbcecea/scratchpad/dtest3/`.

Two environment facts I established rather than assumed, because several tests depend on them:
- **Live pin = spec `3.1.1` / sdk `6.6.0`** — read from `/Users/quantum/Documents/ComputedChaos/salesagent/tests/unit/test_adcp_spec_version.py:5` and `pyproject.toml:10`.
- For every run needing `derive_pins()` I put a **`uv` shim that exits 127** on `PATH`, forcing `citation_freshness.derive_pins()` down its own documented file fallback (`citation_freshness.py:78-90`). This yielded `Derived pin: spec=3.1.1 sdk=6.6.0` — identical to the live values — and guaranteed **nothing wrote into the salesagent repo or its venv.** The only salesagent writes possible from anything I ran are `__pycache__` entries that already existed.

---

## Claim 1 — `disposition_ledger.py:90` INTERNAL_VOCAB is stale — **CONFIRMED (both halves)**

```
DET=/Users/quantum/Documents/ComputedChaos/salesagent/.claude/rules/private/detectors/disposition_ledger.py
out=$(python3 $DET <file>); rc=$?     # dir: .../dtest3/c1/
```

| file | rc | decisive line |
|---|--:|---|
| `pos_control.md` ("gold standard") | **1** | `✗ INTERNAL-VOCAB (1 line(s)) — §1.9 …` `L4: This change meets the gold standard…` |
| `neg_control.md` (technical, no vocab) | **0** | `Contract met: every finding resolves to an action…` |
| `x1_missing_detector_names.md` | **0** | `Contract met: …` |
| `x2_meets_our_bar.md` | **0** | `Contract met: …` |

Controls behave: the check fires on the word it was built for and is quiet on clean text. The exploits pass.

Coverage computed by **executing the regex**, not reading it:
```
detectors on disk: 13
NOT matched by INTERNAL_VOCAB (4): ['changed_field_grading_coverage', 'compound_guard_operands',
                                    'github_workflow_duplication', 'suggestion_audit']
'meets our bar' matched? False
```

The charter text this is supposed to mechanize is `/Users/quantum/Documents/ComputedChaos/salesagent/.claude/rules/private/review-charter.md:33`, which bans `"gold standard" (and any "meets our bar" quality-verdict framing) … and detector names` and then states: **`Mechanized: disposition_ledger.py INTERNAL-VOCAB gate — run it on the artifact before it ships and resolve to 0.`** An artifact naming four real detectors resolves to 0 today.

---

## Claim 2 — `citation_freshness.py:58` CONTEXT must share a line with the version — **CONFIRMED**

Hermetic root at `.../dtest3/c2/root/` reproducing the live pin through the detector's own fallback.

```
cd .../dtest3/c2/root && PATH=<shim>:$PATH
out=$(python3 $DET_CF cases/<f>.md); rc=$?
```

| file | rc | decisive line |
|---|--:|---|
| `pos_control.md` — `Authoritative version: AdCP **3.1.0-beta.3**` | **1** | `cases/pos_control.md:1: stale ['3.1.0-beta.3'] (pin spec=3.1.1 sdk=6.6.0)` |
| `neg_control.md` — `AdCP **3.1.1** (pinned \`adcp==6.6.0\`)` | **0** | `No candidate-stale version citations found.` |
| `x_split_line.md` — `## Spec grounding` ⏎⏎ `Authoritative version: **3.1.0-beta.3** (pinned \`6.6.0\`)` | **0** | `No candidate-stale version citations found.` |

**Sharper proof, on the detector's own regression corpus** (`.../dtest3/c2/regression_minimal_edit.py`, imports `scan_text_blocks` and replays the verbatim `stale_body` from `citation_freshness.py:253-259` — the #1616 case the selftest asserts *must* flag):

```
verbatim regression corpus   -> 1 hit(s)  [['3.1.0-beta.3', '5.7.0']]
one-token edit               -> 0 hit(s)  []
```

The single edit was `**AdCP 3.1.0-beta.3** (pinned \`adcp==5.7.0\`` → `**3.1.0-beta.3** (pinned \`5.7.0\``. Same heading, same document, same trailing `docs/adcp-spec-version.md` line, same stale claim. The regression case passes because the fixture happens to put `adcp` on the version line.

---

## Claim 3 — `compound_guard_operands.py:94` negation/dict/bare-Expr — **CONFIRMED, all four sub-parts**

```
out=$(python3 $DET_CGO --all <file>); rc=$?    # dir: .../dtest3/c3/
```

| fixture | rc | hits |
|---|--:|--:|
| `pos_control.py` — `if task is None or owners.get(task_id) != expected_owner:` | **1** | 1 (`:2 in gate() [or] — 2 operands`) |
| `neg_control.py` — `if task is None:` | **0** | 0 |
| `x1_not_paren.py` — `if not (task is not None and owners.get(task_id) == expected_owner):` (exact De Morgan equivalent of the positive control) | **0** | **0** |
| `x1b_not_or.py` — `if not (a or b):` | **0** | **0** |
| `x2_demorgan_expanded.py` — `if not a or not b:` | **1** | 1 |
| `x3_dict_value.py` — `policy = {'deny': a or b}` | **0** | **0** |
| `x4_bare_expr.py` — bare `a or b` statement | **0** | **0** |

The positive control and its logically-identical De Morgan rewrite differ only in `rc` — 1 vs 0.

### Extended matrix (22 forms, `.../dtest3/c3/matrix/`) — three additional unclaimed gaps

Reported: `if a or b` · `elif a or b` · `if a or b` inside `except` · walrus `if (m := a) or b` · `x: bool = a or b` · `if a or b: raise`.

**Not reported (rc=0, 0 hits):**

| form | why it matters |
|---|---|
| `x = bool(a or b)` | **This is one character away from the detector's own motivating case.** `compound_guard_operands.py:116-124` documents the SCOPE FIX for `return bool(getattr(exc, "connection_invalidated", False)) or isinstance(exc, DisconnectionError)` — BoolOp at the *top* of the value. Move the parenthesis inward and it vanishes. |
| `return not (a or b)` | the negated form of a case the selftest explicitly covers (`:245` "returned BoolOp IS a hit") |
| `g = lambda: a or b` | `visit_Assign` records `node.value`, which is a `Lambda`. This is exactly the "named predicate other code delegates its branch to" the SCOPE FIX comment argues is *more* load-bearing. |
| `x \|= a or b` | no `visit_AugAssign` |
| `yield a or b`, `t = (a or b, 1)`, `m[a or b]`, `[x for x in xs if a or b]`, `f"{a or b}"`, `with cm(a or b)` | miscellaneous |

`g(a or b)` (call argument) is the one **documented** limit (`:249-251`). None of the above are stated anywhere — which is `[31]`'s failure mode, as the prior report put it.

---

## Claim 4 — every detector's `--selftest`

Run from the salesagent repo root, `out=$(python3 $DET <flag>); rc=$?`. Outputs saved per detector in `.../dtest3/c4/`.

| detector | flag | rc | result |
|---|---|--:|---|
| `changed_field_grading_coverage` | `--selftest` | 0 | 7/7 passed |
| `citation_freshness` | `--selftest` | 0 | 22/22 passed |
| `compound_guard_operands` | `--self-test` | 0 | 15/15 passed |
| `disposition_ledger` | `--selftest` | 0 | PASS |
| `fixme_format` | `--selftest` | 0 | PASS |
| `github_workflow_duplication` | `--selftest` | 0 | SELFTEST PASS |
| `pr_import_cycle` | `--selftest` | 0 | PASS |
| `recovery_audit` | `--selftest` | 0 | PASS |
| `sdk_spec_drift` | `--selftest` | 0 | PASS |
| `ssot_docstring_duplication` | `--selftest` | 0 | PASS |
| `suggestion_audit` | `--selftest` | 0 | PASS |
| **`review_completeness`** | `--selftest` | **2** | `error: the following arguments are required: pr` — **no selftest exists** |
| **`bump_check`** | n/a | — | **parses no argv at all** (below) |

11 real self-tests, all pass. Two exceptions:

**`review_completeness.py`** has no `--selftest`; argparse rejects the flag and demands the `pr` positional. It fails *loudly* (rc=2), which is better than the prior report's framing implied — nobody can be fooled into thinking it ran. Confirms Part 4 item 5.

**`bump_check.py`** — `main()` at `:47` takes no arguments and `:94` is `raise SystemExit(main())`; `sys.argv` is never read. Executed (with the uv shim, from a scratch cwd) with three different flags:

```
=== bump_check.py --help              rc=2  -> "bump-check — pinned adcp/spec: (could not derive)"
=== bump_check.py --selftest          rc=2  -> identical
=== bump_check.py --totally-bogus-flag rc=2 -> identical
```

`--help` does not print help. This is the exact defect `disposition_ledger.py:324-331` diagnosed and fixed *in itself* ("an UNRECOGNISED flag used to be silently ignored… a false green in the one tool whose job is catching false greens") — the fix was never applied to the meta-runner.

*(The `rc=2` and the two `FAIL` lines in that run are my shim making `uv` unavailable to `recovery_audit`/`sdk_spec_drift`. Both pass under plain `python3`, rc=0, as the table shows. I am not reporting them as failures.)*

---

## Beyond the claims — unclaimed false-greens found by execution

### N1 (highest value) — a **live, real** stale spec pin sits outside `citation_freshness`'s default scan set

`/Users/quantum/Documents/ComputedChaos/salesagent/CLAUDE.md:127`:

```
This project targets AdCP spec **3.1.0-beta.3** via the `adcp==5.7.0` Python SDK. See
```

That is the **verbatim** stale pair from miss-mode #12 / PR #1616 (`3.1.0-beta.3` + `adcp==5.7.0`), against a live pin of 3.1.1 / 6.6.0. `CLAUDE.md` is git-tracked (`git ls-files --error-unmatch CLAUDE.md` → rc=0) and is auto-loaded into every session in that repo.

```
$ cd <salesagent> && python3 $DET_CF                     # DEFAULT roots
rc=1   Scanning: src, .claude/agents, .claude/rules/private, .claude/skills, tests/bdd/features
       hits mentioning CLAUDE.md: 0        (143 hits total, none in CLAUDE.md)

$ python3 $DET_CF CLAUDE.md                              # POSITIVE CONTROL, same detector
rc=1   CLAUDE.md:127: stale ['3.1.0-beta.3', '5.7.0'] (pin spec=3.1.1 sdk=6.6.0)
```

The matcher is fine; the **scan set** is the defect — the detector's own named miss-mode, unresolved on a second surface. Neither prescribed invocation reaches it: `citation_freshness.py:327-331` default roots exclude the repo root and `docs/`, and `review-charter.md:127` prescribes only `citation_freshness.py --pr <N>` (the PR prose surface). `docs/adcp-spec-version.md` — the doc `CLAUDE.md:128` links to as the version mapping — is likewise never scanned (82 version-token lines in adcp/spec context under `docs/`; I did not adjudicate which are legitimately historical).

Operational note on the same detector: the default-root run returns **rc=1 with 143 standing hits** (27 in `media_buy_create.py`, 22 in `schemas/_base.py`, …). Sampled hits look like normative/historical citations missing a `# spec-introduced:` marker — I did not adjudicate them. But the consequence is structural: on its default surface the exit code carries no per-run information, while the one flatly-stale citation lives on a surface it never sees.

### N2 — `disposition_ledger`: unbracketed severity zeroes the entire gate

`FINDING_TAG` (`:74`) requires a `[` before the severity. `_is_clean` (`:204-205`) short-circuits when `n_findings == 0`.

```
pos_control.md   3 bracketed findings, no dispositions, no ledger  -> rc=1  ✗ LEDGER-ABSENT + ✗ DISPOSITION-DEFICIT: 3
a1_unbracketed_severity.md  **BLOCKER — P1 …** (same 3 findings)   -> rc=0
                            findings (severity-tagged): 0
                            dispositions resolved:      0
                            Actions ledger present:     False
                            Contract met: every finding resolves to an action…
```

Three findings, zero dispositions, no ledger, and the gate prints "Contract met". This is a *broader* defeat than the clustered-token one already confirmed: it needs no clustering, only a formatting variant, and it silences LEDGER-PRESENT, DISPOSITION-COVERAGE and BANNED-AS-DISPOSITION at once.

### N3 — `disposition_ledger`: LEDGER-PRESENT satisfied by a sentence denying the ledger

`LEDGER_HEADING` (`:76`) is `^#{1,4}\s*Actions\b|Actions\s+ledger|Actions\s*\(charter` — only the **first** alternative is anchored; `Actions\s+ledger` matches anywhere.

```
a2_prose_ledger.md — whose only occurrence of the phrase is:
    "No Actions ledger was produced for this round."
-> rc=0   Actions ledger present:     True
```

### N4 — `disposition_ledger`: an ordinary summary line pads the document-wide count while every real disposition is charter-banned

```
a4_summary_line_pads_count.md
  "Summary: 1 FIX-NOW, 1 FOLD-IN, 1 FOLLOW-UP."     <- supplies all 3 tokens
  [BLOCKER] … Disposition: consider tightening the owner compare
  [SHOULD-FIX] … Disposition: you might want to extract a shared helper
  [NIT] … Disposition: could rename later
-> rc=0   findings: 3   dispositions: 3   ledger: True   "Contract met"
```

Two compounding causes: the already-confirmed document-wide count (a *summary line* is a realistic trigger, not a contrived one), and `BANNED` (`:78`) covering only `optional|non-blocking|non-gating|nice-to-have` while `review-charter.md:33` §1.8 also bans **`consider`** and **`could/might want to`** as dispositions.

**Negative-control note / one REFUTED sub-case:** `a3_hedge_disposition.md` (hedges, *without* the padding summary line) returned **rc=1** — the deficit check caught it. So the hedge gap is only exploitable when the token count is padded. Reporting that because it is what stops me from claiming the BANNED regex is defeatable on its own.

### N5 — `ssot_docstring_duplication`: two same-named defs in **one file** are reported as "unique-named"

`audit()` (`:89`) gates check A on `len(files_with) >= 2`, so intra-file duplication falls to the `elif` on `:92`.

```
pos/  canonical in src/a.py, twin in tests/b.py   -> rc=1  ✗ SSOT-CONTRADICTED (1)
x1/   BOTH defs in src/a.py (one claims SSOT)     -> rc=0
      "· SSOT-CLAIMS-TO-VERIFY (1) — unique-named 'canonical' claims."
```

It does not merely miss this — it **positively asserts the name is unique** when the file defines it twice, and at import the second definition shadows the first, making the "single source of truth" body dead code. The selftest's precision arm never exercises intra-file duplication.

### N6 — `ssot_docstring_duplication`: `--base` prints `✗` and exits 0

Scratch git repo at `.../dtest3/adv/ssot/x3/`, feature branch whose diff vs base contains no `.py` files:

```
python3 $DET_SSOT              -> rc=1   ✗ SSOT-CONTRADICTED (1) …
python3 $DET_SSOT --base master -> rc=0  ✗ SSOT-CONTRADICTED (1) …   (identical ✗ line)
```

The PR-relevance scoping at `:232-235` is deliberate, but the `✗` marker still prints while `rc` flips to 0 and the explanatory "Worklist:" line is suppressed. Any caller keying on the exit code — a `&&` chain, a wrapper, a CI step — reads green over a printed violation.

### N7 — nothing automatic runs any detector's self-test

```
$ grep -rlE 'detectors/|--selftest|--self-test' .github/ Makefile tests/ scripts/
(no matches)
```

The only aggregate runner is `bump_check.py`, whose `DETECTORS` list (`:30-35`) contains **4 of 13**: `citation_freshness`, `recovery_audit`, `sdk_spec_drift`, `fixme_format`. Nine detectors' self-tests — including `disposition_ledger` and `ssot_docstring_duplication`, the #1 and #3 most-invoked — run only when a human types the flag.

### N8 — weaker `ssot` scope gaps (reported for completeness, both partly self-disclosed)

- SSOT claim written as a `#` comment above the def instead of a docstring → `rc=0`, `"No SSOT claims and no duplicated test helpers found"`. The detector's *name* discloses the docstring scope; its output does not.
- Twin in `scripts/` (outside default roots `src`, `tests`) → `rc=0`. Self-reported via `scanned 1 files under src, tests`.

---

## Resolved from the prior report's "could not verify"

`review-charter.md:96`'s claim, re-checked today with the exit code captured directly (no pipe):

```
.claude/reports        check-ignore rc=1  (NOT ignored)
.claude/notes          check-ignore rc=1  (NOT ignored)
.claude/rules/private  check-ignore rc=0  (IGNORED)
CLAUDE.md              check-ignore rc=1  (NOT ignored)
```

Still true.

---

## What I did **not** test

- **`bump_check`'s real end-to-end run.** Executing it for real means `uv run python`, which can sync the salesagent venv — a write into a repo I was told not to touch. I proved only that it ignores `argv` and that its `DETECTORS` list covers 4 of 13.
- **`review_completeness.py`'s `--since` lexical-compare defect** (prior report item 6) and its **41% `--since` omission rate** (item 7). Both need live `gh` calls against `prebid/salesagent` — outbound network against a real repo, outside what I'd do unasked. Unverified either way.
- **Whether any shipped artifact under `.claude/reports/` actually passed through one of these false greens.** All exploits here are synthetic — except **N1**, which is a live file in the repo.
- **Adjudication of the 143 default-root `citation_freshness` hits.** I sampled four; I did not decide which are genuinely stale versus historical citations owed a `# spec-introduced:` marker.
- **Rule-to-detector coverage claims** from the prior report's Part 2. Out of scope here; I neither confirmed nor challenged them.