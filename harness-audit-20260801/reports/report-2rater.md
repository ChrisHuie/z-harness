## Verdict: the DUP+VAC headline survives. Kappa 0.82. And the human's findings check out.

---

## 1. Method

**Frame.** All 864 rows from `all864.pkl`, extracted with a field whitelist (`url, pr, path, line, body, ts, idx, login`) that deliberately excluded the `klass` column — I did not see a single first-grader label until all 150 of mine were written to disk. Verified the frame against a fresh independent pull: `gh api repos/prebid/salesagent/pulls/comments --paginate` returned 2,617 comments, 1,419 by `KonstantinMirin`; **all 864 frame rows matched the live API byte-for-byte**, 0 body mismatches. All rows are `KonstantinMirin`; `ChrisHuie` excluded.

**Sample.** Sorted by comment URL for determinism, then `random.Random(20260801).sample(range(864), 150)`. **Seed 20260801, n=150, simple random sample without replacement.** Covers 27 of 28 PRs (only 1616 missed); 47 `src/`, 87 `tests/`, 16 other.

**Definitions written before reading any comment.** The one that did the most work: for DUP, *"if this code appeared exactly once, would the comment vanish?"* Plus a declared tie-break order — repetition-is-the-complaint beats ARCH/VAC/TYP/NAM; two named sibling transports beats VAC; TYP only when annotations are the subject.

**Verification.** 76 distinct `original_commit_id` SHAs, **all 76 resolve locally**; checks via `git show <sha>:<path>` and `git grep <sha>`. Read-only throughout — no fetch, no checkout, no working-tree write.

---

## 2. Agreement

| | |
|---|---|
| Raw agreement | **130/150 = 86.7%** |
| Cohen's kappa | **0.821**, bootstrap 95% CI **[0.748, 0.888]** |
| Chance agreement Pe | 0.257 |

Per-class, over all 150:

| class | g1 n | my n | both | recall | prec | kappa |
|---|---:|---:|---:|---:|---:|---:|
| **DUP** | 68 | 71 | 65 | **95.6%** | **91.5%** | **0.88** |
| **VAC** | 20 | 21 | 19 | **95.0%** | **90.5%** | **0.92** |
| TYP | 15 | 15 | 15 | 100% | 100% | 1.00 |
| NAM | 11 | 12 | 9 | 81.8% | 75.0% | 0.76 |
| DEAD | 8 | 7 | 6 | 75.0% | 85.7% | 0.79 |
| PAR | 5 | 5 | 4 | 80.0% | 80.0% | 0.79 |
| SPEC | 5 | 5 | 4 | 80.0% | 80.0% | 0.79 |
| ARCH | 5 | 8 | 4 | 80.0% | 50.0% | 0.60 |
| ERR | 6 | 3 | 2 | 33.3% | 66.7% | 0.43 |
| LOGIC | 4 | 2 | 1 | 25.0% | 50.0% | 0.32 |
| SEC | 2 | 0 | 0 | 0% | — | 0.00 |

**The two classes the headline rests on are the two most reliable.** The unreliable classes — ERR (0.43), LOGIC (0.32), SEC (0.00), ARCH (0.60) — are all tail classes carrying 1–4% of misses each. Nothing downstream depends on them.

---

## 3. The headline question

Miss-only subset (77 of my 150, using grader 1's `cls` column, which I did not re-rate):

| | DUP | VAC | DUP+VAC |
|---|---:|---:|---:|
| published (448 misses) | 46.4% | 19.6% | **66.0%** |
| grader 1, on my 77 | 45.5% | 15.6% | 61.0% |
| **me, independent, on my 77** | **46.8%** | **16.9%** | **63.6%** |
| adjudicated | 45.5% | 16.9% | **62.3%** [51.9, 72.7] |

**66.0% sits inside my CI.** DUP is the modal class in **7,998 of 8,000** bootstrap resamples of the adjudicated miss set. Every "attack DUP first" recommendation in the audit is correctly aimed.

Two honest caveats:

- **My sample under-drew VAC** — 20 observed vs 29.9 expected, one-sided binomial p = 0.024. Proof it's sampling and not rating: *grader 1's own labels* on my 77 misses give VAC 15.6%, below their published 19.6%. Same rater, different subsample. Their published 19.6% remains the better corpus estimate; my 16.9% is low by draw.
- **VAC and TYP are not separable at this n.** Adjudicated misses: VAC 16.9% [9.1, 26.0], TYP 14.3% [6.5, 22.1]; VAC−TYP = +2.6 pp [−10.4, +14.3], P(VAC>TYP) = 0.63. **The rank-2 slot is undetermined by my sample.** I am reporting that rather than the noise. Rank 1 is not in doubt.

---

## 4. The 20 disagreements, adjudicated

**8 mine better, 7 theirs better, 5 genuine ties.** Balanced — no directional bias.

### Where grader 1 is wrong (8)

- **#4** `test_create_media_buy_behavioral.py:459` — g1 **ERR**, me **VAC**. *"`except Exception: pass` around the call under test swallows any regression … the only surviving signal is `mock_upload.called`."* The swallow is **in the test**; the harm is the test can't redden. ERR would be right if this were production error-handling. **VAC.**
- **#22** `workflows.py:345` — g1 **DUP**, me **NAM**. *"left on the old form inside a function whose other log lines this PR swept to the canonical … idiom."* Nothing is repeated. It's convention divergence with no behavior change. g1 keyed on "one idiom" phrasing that reads like DRY. **NAM.**
- **#35** `operations.py:431` — g1 **PAR**, me **DUP**. *"third copy of the `execute_approved_media_buy(...)` → branch → `finalize_*` sequence (also `workflows.py:263` and `creatives.py:656`), and the three have already drifted."* Three admin routes are not transports; g1's own PAR gloss is "cross-transport/cross-surface" with a2a/mcp/rest exemplars. **DUP.**
- **#61** `test_list_creatives_statuses_filter.py:12` — g1 **SPEC**, me **NAM**. *"Cites PR `#1493`; the convention is the durable issue number."* A GitHub issue number is not spec-citation or version grounding. **NAM.**
- **#125** `uc019_query_media_buys.py:1378` — g1 **ARCH**, me **DEAD**. Two defects (a third novel writer reaching into `env._last_wire_response`, and *"Both steps are dead: no `.feature` binds…"*). The remedy is **delete both**; if they're unbound the layering breach is moot. **DEAD.**
- **#127** `BR-UC-019…feature:1229` — g1 **LOGIC**, me **NAM**. `@br-rule-294` vs `@BR-RULE-294`; the fix is a pure rename. g1 keyed on the consequence ("silently misses"). **NAM.**
- **#137** `creatives.py:612` — g1 **ERR**, me **ARCH**. *"the only `._session` access in `src/` outside the repository layer."* The comment itself says the `-O` assert hazard *"disappear[s] once the predicate takes `uow.assignments`"* — the layering fix subsumes it. **ARCH.**
- **#30** `test_a2a_skill_invocation.py:1103` — g1 **DUP**, me **VAC** (slight edge). *"copy 1 of 4 … using the loose `extract_data_from_artifact` … so it never pins the `processing_error` artifact-name / single-DataPart shape."* Under my DUP test, a single copy using the loose reader would still draw this comment. The DUP is the vehicle; the weak oracle is the defect.

### Where I am wrong (7)

- **#11** `adcp_a2a_server.py:1560` — I said **DUP**, g1 **NAM**. *"Function-local import, but the module already imports from `src.core.schema_helpers` at top level."* Import placement is convention, not duplicated logic. **I caught this by my own inconsistency**: I labeled the near-identical #103 (`test_a2a_brand_manifest.py:109`, function-local import vs sibling file's module-top) **NAM**. Two labels for one shape. g1 is right.
- **#70** `check_dormant_scenarios.py:103` — I said **LOGIC**, g1 **ERR**. *"`_git` returns only stdout with `check=False` … Guard the empty string here and bail loudly."* The mechanism *and* the remedy are error-handling. I over-weighted the consequence. g1 is right.
- **#80** `audit_xfails.py:557` and **#86** `graduate_pending.py:75` — I said **DUP**, g1 **LOGIC**. Both are "classifiers of one decision disagree; share `grade_base()`." I applied a rule that drifted copies → DUP. But #80 carries an *independent* correctness argument (*"`conftest.py` marks `e2e_rest` xfails non-strict for exactly that reason"*), and #86's actual defect is `analyze()` never loading the ledger — a missing input producing a wrong answer. g1 is right on both. **This is the error direction that inflates DUP, and it was mine, not theirs.**
- **#109** `test_rest_api_products.py:68` — I said **PAR**, g1 **VAC**. *"Retype the field `Literal[...]` and every REST test here stays green while a spec-valid `refine` 400s."* That is the mutation-survives signature. My rule 2 ("names two sibling surfaces → PAR") over-fired: the remedy strengthens this test's oracle, it does not add a transport. **The correct discriminator is whether the fix adds a surface or strengthens an oracle** — not whether two surfaces are named. g1 is right.
- **#111** `exceptions.py:1101` and **#116** `account_helpers.py:41` — I said **ERR**/**ARCH**, g1 **SEC** both times. An internal `host:port` reaching the buyer wire, and a credential persisted because *"The persistence boundary doesn't enforce it."* **I have a systematic bias: I routed security consequences to the structural class of the site.** g1 is right on both. This is why my SEC recall is 0/2.

### Genuine ties — the taxonomy forces one label onto two-defect comments (5)

**#17** `_base.py:961` (*"Two drift points in the new seam"* — g1 took the error-materialization, I took the ownership); **#62** `:18` (five copies **and** the schema grounding is wrong — *"'array/`minItems:1` shape' does not entail match-any"*); **#108** `product.py:48` (false justifying comment **and** hand-copied field list); **#142** `media_buy_creative_readiness.py:23` (unused re-exports **and** a second public home); **#149** `adcp_a2a_server.py:351` (hand-maintained copy **and** functionally inert).

### One soft boundary neither of us flagged

Grader 1 named DUP↔ARCH and VAC↔PAR. The live one in my data is **DUP↔VAC**: comments where N copies share one weak oracle (#30, #42, #43, #92). Grader 1's tie-break ("the finding's own stated emphasis") sends these to DUP because they *open* with the copy count; mine sends them to VAC because the oracle would still be weak at n=1. **This boundary moves mass from DUP toward VAC — the only mechanism I found that could shift the split, and it is worth perhaps 2–4 points, not a reordering.**

---

## 5. Are the human's findings actually true? (18 verified, not 15)

Graded at the reviewed SHA. **18 of 18 are substantively correct. Zero fabricated defects.**

Exact to the line number: **#19** Barrier skeleton at exactly `:880/:931/:1096`; **#40** `_DAILY_WEBHOOK` at exactly `73/124/256/295/351/401/452/520` (8 sites, all 8 numbers right); **#98** `split("#", 1)` at exactly `89/98/107`; **#120** exactly 9 `sanitize_webhook_url_for_log(...) or UNPARSEABLE…` sites, cited one included ("the ninth"); **#127** lowercase at 1212/1229 and uppercase at exactly 955/970/982/994; **#149** all six map values are byte-identical to `operation.replace("_", " ")`; **#82** `grade_base` returns `tuple[bool, set[str], set[str], int, bool]` — positions 0 and 4 both bool, both classifiers unpack positionally; **#73** the phrase *"reaches the buyer as a real"* has **0** hits under `tests/bdd/features/` and exactly one repo-wide (the step definition itself); **#87** **0** references to `graduate_pending` under `tests/`; **#108** both cited evidence lines exact (`_base.py:944` = `from src.app import app`, `app.py:54` = `from src.routes.api_v1 import…`) and `_BODY_FIELDS` matches `GetProductsBody`'s field order exactly; **#142** `operations.py:398-404` and `workflows.py:202-208` do import from the admin facade and then from `src.services` **in the literally next statement**. Also correct: **#110**, **#124**, **#126** (the SQLAlchemy semantics are right — `pkg_row.package_config = config` at `:675` is a full reassignment, so `flag_modified` at `:676` is redundant), **#134**.

**Three defects in the findings, all minor, none load-bearing:**

1. **#8** (PR1534) — *"This two-line leak-negative pair now appears six times across four files in this PR."* Four files: correct. Six: **wrong**. The exact `input_value`+`errors.pydantic.dev` pair appears **5** times across **3** files; counting the `buyer-input` variant in `test_exception_normalization.py` gives **7** across **4**. Six matches neither reading. (The PR added all 7.) Notably, their own follow-up #9 calls `test_mcp_compat_middleware.py:225` *"Fifth copy"* — which is exactly right under the strict reading.
2. **#142** — *"re-exports six pure domain symbols."* It re-exports **seven** (`__all__` has 8 entries, 7 imported + 1 local).
3. **#136** — *"asserts the constant contains what it is defined to contain — it can't fail on drift."* `FINALIZE_READY_CREATIVE_STATUSES = frozenset({"approved", "active"})`, so the assert *would* fail if `active` were removed. "Can't fail" is overstated; the drift class they name (allowlist vs `CreativeStatusEnum`) is correctly identified and genuinely uncovered.

Both count errors are **undercounts** ("six" when the truth is seven). The findings are conservative, not inflated.

**Implication for the miss rate:** 0/18 substantively false. Rule of three gives a 95% upper bound of ~16.7% on the false-finding rate; point estimate 0%. **The panel's 39.6% / 37.1% miss rate is not materially overstated by human error.** This closes the open item that grader 1 explicitly could not test.

---

## 6. What I could not determine

- **Miss/caught status is inherited, not re-rated.** The miss-only distribution uses grader 1's `cls` and `opp2` columns. I re-rated the taxonomy only. Their `git blame` opportunity correction is unaudited by me.
- **Rank 2 among misses.** VAC vs TYP is not separable at n=77 (P(VAC>TYP)=0.63). Reporting the ordering would be noise.
- **ERR / LOGIC / SEC / ARCH boundaries are unreliable** (kappa 0.43 / 0.32 / 0.00 / 0.60) — but they carry 1–4% of misses each, so nothing rests on them. If a future recommendation targets one of these classes, re-rate it first; the current numbers cannot support it.
- **18 verifications is not a claim-accuracy estimate.** I selected for mechanically checkable claims (counts, line numbers, greps), which are the *most* falsifiable kind. Prose-judgment findings ("this is the wrong layer") are not gradeable this way and are unrepresented.

---

**Files (all absolute):** frame `/private/tmp/claude-501/-Users-quantum-Documents-GitHub-agenticads-sim-plan/e2367c8b-0c8b-43ae-a5d4-98ce3fbcecea/scratchpad/rater2/frame864.json`; sample `…/rater2/sample150.json`; my labels `…/rater2/mylabels.txt`; joined comparison `…/rater2/compare.json`; SHA-resolved rows `…/rater2/withsha.json`; disagreements `…/rater2/disagree.txt`. Nothing written outside the scratchpad; `/Users/quantum/Documents/ComputedChaos/salesagent` untouched (the 4 modified files and 1 untracked note in its working tree predate this session).