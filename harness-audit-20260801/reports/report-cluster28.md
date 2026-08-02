All measurements are in. Repo untouched — read-only throughout (`git show` / `git diff` against already-fetched objects only; no fetch, checkout, or write).

---

# The 28.6% is not a distinct failure class. It is the stopping rule, measured at cluster scope.

**The prior agent's conclusion is half right and it matters which half.** There is no shape catalog that closes this band — I tested it and shapes carry *zero* discriminative signal. But the claim that no mechanism exists is wrong. The never-detected clusters are separated from the found ones by **position**, and position alone explains the entire band. A proximity-matched null reproduces the never-detected fraction exactly (p = 0.14–0.79 across four null constructions and six slices). There is nothing left over for "a retrieval index the panel lacks" to explain.

Scripts and data: `/private/tmp/claude-501/-Users-quantum-Documents-GitHub-agenticads-sim-plan/e2367c8b-0c8b-43ae-a5d4-98ce3fbcecea/scratchpad/nd/` — `sites.py` (site extractor), `panel.py` (the harness matcher, TOL=12), `build_clusters.py` → `cl.pkl`, `charac.py`, `indep.py`/`indep2.py`/`indep3.py` (nulls), `diffreach.py` → `added.pkl`, `shapes.py`, `yield.py`, `sens.py`.

---

## 0. The rebuild, and a reproduction failure I could not close

**I could not reproduce 133 / 37.6 / 33.8 / 28.6.** No script survives in the scratchpad that produces it (`km/clusters.py` computes different quantities), and I tried 16 cluster definitions. The percentages are internally consistent with n=133 (they give 50 / 44.95 / 38.04), so the set was real; I just cannot recover its rule.

My rebuild: a cluster is a connected component over the human's own comments, linked when one comment's enumerated site set (anchor + `path:NNN` + bare `:NNN` + slash-runs like `73/124/256` + "lines A, B and C") lands within ±12 of another comment's anchor. **158 clusters, 587 sites, 28 PRs.** "Found a site" = the panel cited it within ±12, before the human's comment, per the harness's own matcher.

| | ALL sites found | SOME | **NONE** |
|---|---|---|---|
| panel cited the site at any severity (**primary**) | 59 (37.3%) | 42 (26.6%) | **57 (36.1%)** |
| panel cited it at ≥SHOULD-FIX (strict, = the CAUGHT definition) | 40 (25.3%) | 31 (19.6%) | **87 (55.1%)** |

Across all 16 definitions the NONE band ranges **16.0%–55.1%**. The reported 28.6% sits inside that; the block is real and if anything was understated. Everything below is reported on the primary band and re-tested on the strict one.

---

## 1. What separates them — and what conspicuously does not

**Does not separate them (this is the important list):**

| tested | NONE | FOUND | p |
|---|---|---|---|
| defect class DUP | 49.1% | 50.5% | 1.000 |
| defect class VAC | 15.8% | 16.8% | 1.000 |
| *every* one of 11 classes | — | — | all ≥ 0.12 |
| **defect shape** (16-shape induced catalog) | — | — | **χ²=19.92, df=15, p=0.175** |
| ≥1 site inside a lens Read window | 40.4% | 46.5% | 0.507 |
| file was Read by some lens | 59.6% | 53.5% | 0.507 |
| opportunity-confirmed (blame-gated) | 35.1% | 43.6% | 0.316 |
| human's comment length / names a helper / proposes a mutation / symbol density | identical | identical | 0.24–0.92 |

**Does separate them:**

| | NONE | FOUND | p |
|---|---|---|---|
| median site line | **376** | 189 | 0.0003 |
| first site line | **318** | 115 | 0.0002 |
| in `tests/` | **73.7%** | 50.5% | 0.007 |
| in `src/` | 19.3% | **38.6%** | 0.013 |
| single-file cluster | **91.2%** | 73.3% | 0.007 |
| cluster size (human comments) | 2 | 3 | 0.0002 |
| lenses that opened the file | 4 | 5 | 0.0002 |
| file ≥1500 lines | **36.8%** | 15.8% | — |

So: same defects, same shapes, same prose, same lens attention at file granularity — **different place in the file**.

### The decisive test

Detection inside a cluster is strongly all-or-nothing. Against a naive shuffle it looks like a distinct phenomenon: observed NONE 36.1% vs 13.5% expected, p < 0.0001. But sites in one cluster share a file and a line band, which induces that correlation for free. Three progressively tighter nulls:

| null | observed NONE | null NONE | P(null ≥ obs) |
|---|---|---|---|
| free shuffle across all clustered sites | 36.1% | 13.5% | **0.0000** |
| redrawn from the **same file** | 36.1% | 30.3% | 0.0061 |
| same file **+ same line-span window** | 36.1% | 37.0% | **0.792** |
| same file **+ contiguous run of n comments in line order** | 36.1% | 35.2% | **0.391** |
| same file + contiguous run **starting within ±2 ranks of the real one** | 36.1% | 34.0% | 0.140 |

Holds on every slice — strict band (55.1% vs 54.9%, p=0.53), single-file clusters (p=0.24), ≥3-comment clusters (p=0.46), opportunity-confirmed only (p=0.29), `tests/` only (p=0.52).

**Once you know which file a cluster is in and which line band it occupies, knowing that it is a cluster tells you nothing more about whether the panel found it.** The underlying gradient is the one `report-misstax.md` already named: detection by rank within a file runs 53.8% → 61.0% → … → **17.4% at rank 10+**, and by absolute line 55.4% (<200) → **25.0% (1500–2500)**.

One thing the nulls *do* show: in all six slices ALL is over-represented and SOME under-represented (37.3% vs 29.3%, 26.6% vs 35.5%). That is the enumeration effect, and it is real — but it only moves mass between SOME and ALL. **It never moves mass out of NONE.** Which is exactly why the enumeration fix leaves this band untouched, and exactly why that is not evidence the band is unreachable.

---

## 2. Are they findable from the diff? Yes — indistinguishably so

Reconstructed added-line sets for all 28/28 PRs from `merge-base...head`:

| site sits… | NONE | SOME | ALL |
|---|---|---|---|
| **ON a line the PR added** | **83.7%** | 81.9% | 81.2% |
| within 3 lines of a change | 7.1% | 6.9% | 8.8% |
| within 25 lines | 7.8% | 6.5% | 7.1% |
| >100 lines from any change | 1.4% | 1.1% | 1.8% |
| in a file the PR did not change | **0%** | 0% | 0% |

Median distance to the nearest changed line is **0 for all three bands**; p90 is 3 lines for NONE. **This is not a scope problem and the fix is not a scope change.** The 20-cluster hand sample says the same thing qualitatively: PR1622 `:436` "Second copy of the scripts-dir path plus the `spec_from_file_location`/`module_from_spec`/`exec_module` load block from `:34-37`, character-for-character"; PR1669 `test_architecture_ci_suite_coverage.py:89/98/107` "`line.split("#", 1)[0]` — the comment-strip rule — is copied here and in `_shell_flag_value` and `_shell_has_non_comment_substr`." These are in-file, in-diff, textually adjacent DUP shapes with the sibling line numbers written out.

Where they are *not* reachable is by the panel's own footprint:

- **93.0%** (53/57) of never-detected clusters are in a file the panel explicitly opened **and cited something else in**.
- Median distance from a never-detected site to the panel's own nearest cite in the same file: **28 lines** (q25 15, q75 72). ±13 is the floor by construction of the matcher, so the meaningful read is the reach curve below.
- **47%** of never-detected sites sit past the panel's deepest cite in that file; the panel's deepest cite lands at a median **59% of file length**. The other 53% are inside the worked range, in a low-cite-density band.

---

## 3. The shape catalog — built, and it does not discriminate

Built from all 985 KonstantinMirin comments across 29 PRs (cached at `dtest4/gh/rc*.json`; `ChrisHuie` excluded).

**Explicitly named shapes are thin.** Mining hyphenated nominals + `shape|class|pattern` yields ~50 total mentions, almost all n=1–2: `silent-drift shape` (4), `extract-a-helper-then-copy shape` (4), `extract-then-skip-a-sibling shape` (2), `partial-copy shape` (1), `single-terminal-commit shape` (2). The named taxonomy is a stylistic flourish over a formulaic prose structure, not a carried index.

Inducing shapes from that structure (defect predicate × remedy) gives **16 shapes covering 77.8%**, with a 22.2% long tail. Top six carry 74%:

| shape | share of 985 |
|---|---|
| S3 re-implements an existing helper / bypasses the seam | 19.5% |
| S1 Nth-copy-of-a-block (byte-for-byte, "third copy", "repeats 8×") | 15.3% |
| S11 type erosion / wrong annotation | 9.3% |
| S4 the copies have already drifted | 7.9% |
| S5 test cannot redden (mutation-survivable) | 7.2% |
| S16 spec/version citation wrong or ungrounded | 5.0% |

**So the answer to "how many distinct shapes are there" is: about six that matter, plus a heterogeneous quarter. And the answer to "do the never-detected clusters reduce to a small number of them" is yes — but so do the detected ones, in the same proportions.**

| shape | NONE | FOUND | p |
|---|---|---|---|
| S1 Nth-copy-of-a-block | 26.3% | 16.8% | 0.216 |
| S3 re-implements a helper | 15.8% | 24.8% | 0.229 |
| S17 unclassified | 14.0% | 16.8% | 0.821 |
| S4 already drifted | 8.8% | 7.9% | 1.000 |
| S5 cannot redden | 5.3% | 9.9% | 0.379 |

χ² = 19.92, df = 15, **p = 0.175**. At site level over all 864 rows the miss rate by shape is flat at 33–60%, mirroring the flat-across-classes result in `report-misstax.md`.

**A shape checklist fires equally on the defects the panel already catches.** It cannot separate the bands, so its expected yield on this failure mode is zero. And the shapes are already in the harness — `review-charter.md` §1.5b ("COUNT THE COPIES BEFORE PROPOSING THE FIX"), §1.5c (adoption completeness, `N adopted / M eligible`), §4c.3 ("sibling-swept — enumerated, not asserted"), §11 (semantic SSOT), plus `reference_review_patterns.md` P13, P19, P25, P39, P42. Arm B below is close to a null edit by construction, which is precisely why it needs the third arm that FINDINGS §8 says a two-arm design would have missed.

**Verdict on the prior conclusion: it holds for the shape-catalog proposal, and for a better reason than the one given.** Not "the panel holds the index as a 39,867-byte document read once" — the panel holds those shapes fine and applies them constantly. The shapes simply do not predict which clusters get found.

---

## 4. What the prior agent said did not exist

A mechanism does exist, it is positional, and it is priceable. Yield against the 57 never-detected clusters:

| rule | reach |
|---|---|
| sweep ±25 lines of every existing panel cite | 40.4% |
| sweep ±100 lines | **75.4%** |
| sweep ±400 lines | 86.0% |
| **any file the panel cites in at all, swept end to end** | **93.0%** |
| trigger only on files ≥1500 lines | 36.8% of NONE (and 15.8% of FOUND — poor selectivity) |

The size and depth triggers are weak filters. The cite-anchored sweep is strong, and it needs no model capability the panel lacks: it is a coverage obligation, not a recognition one.

**The precise statement of the gap.** §4b.0's enumeration rule is *finding-scoped*: "a unified SSOT finding carries one ledger row per site." It can only fire once a finding exists — which is why it converts SOME into ALL and cannot touch NONE. The never-detected band needs the same rule *file-scoped*: **a file you cited in is not closed until you have swept it end to end and said so.** That is a different sentence in a different place, and the audit's own §5 experiment is the evidence that positive coverage instructions are the lever (27% → 100% on a 2,953-line file; deleting the cap was the null edit).

---

## 5. The experiment that settles it

### Target

`tests/unit/test_check_dormant_scenarios.py` at PR **1622** head `71f1d2241` — **642 lines, 641 of them added by the PR.**

This file is the sharpest exhibit in the corpus and it removes every confound at once:

- Small enough to read whole — "didn't read deep enough" is not available as an explanation.
- **All 14 human sites are on added lines.** Scope is not available either.
- **All 14 were inside a lens Read window.** Four lenses opened it: `architecture-guards`, `bdd`, `code-patterns`, `test-integrity`.
- The panel emitted **104 cites** in this file — and **69% of them (72/104) fall in lines 200–299.** Its deepest cite is **:412**. Lines 413–642 got nothing.
- Panel recall: **3 of 14** (2 at ≥SHOULD-FIX). Four never-detected clusters live here.

### Ground truth — the 14 sites, exactly

| line | class | panel | line | class | panel |
|---|---|---|---|---|---|
| 34 | DUP | miss | 344 | VAC | miss |
| 146 | VAC | miss | 351 | DUP | miss |
| **243** | LOGIC | **SHOULD-FIX** | 354 | VAC | miss |
| **251** | DUP | **SHOULD-FIX** | 436 | DUP | miss |
| **300** | VAC | NIT (under) | 444 | DUP | miss |
| 318 | TYP | miss | 479 | DUP | miss |
| | | | 486 | DUP | miss |
| | | | 494 | DUP | miss |

Grade a site recovered when a report cites it within ±12 — the harness's own matcher, so the instrument is not looser than the thing it checks. Primary metric: recall over all 14. Secondary: recall over the 9 `code-patterns`-owned sites (8 DUP + 1 TYP).

### Arms — one lens (`review-code-patterns`), one file, 5 runs each

| arm | prompt difference from control |
|---|---|
| **A control** | charter and lens as-is |
| **B shape catalog** | + the six induced shapes above, each with its detection recipe, as an explicit "check each against this file" list |
| **C positional sweep** | + *"Before emitting any finding, walk lines 1–642 in order and emit a coverage ledger: one row per 100-line band recording what you examined. A band you cited in is not closed until you have named every site in it. Never stop at N findings."* No shape content. |
| **D both** | B + C |

### Predicted recall, stated before it runs

| arm | prediction (of 14) | 90% interval |
|---|---|---|
| **A** | **3 (21%)** | 1–5 |
| **B** | **3 (21%)** | 1–6 |
| **C** | **9 (64%)** | 6–13 |
| **D** | **9–10 (64–71%)** | 6–13 |

**Predicted A→B difference: 0 ± 2 sites. Predicted A→C difference: +6.**

C is discounted well below the §5 experiment's 100% because that ground truth was mechanically enumerable and this one needs judgment (a VAC finding at `:344` about `pytest_runtest_makereport` emitting three unguarded reason classes is not pattern-matchable).

**Falsifiers, named in advance:**
- **B ≥ A + 4 sites** ⇒ my "shapes carry no signal" conclusion is wrong and the shape catalog is the proposal after all.
- **C ≤ A + 2 sites** ⇒ the positional mechanism is wrong too, and the prior agent's "no proposal closes this honestly" survives intact on both counts.
- **Mechanism discriminator:** the sites C recovers should concentrate at **436 / 444 / 479 / 486 / 494** — the five past the panel's deepest cite — because C's lever is coverage, not recognition. If C recovers only low-line sites and still misses those five, the lever is recognition after all and both my proposal and the prior's are wrong.

**Replication target, different profile:** PR1699 `tests/unit/test_e2e_stack_readiness_behavior.py` at 406 lines — 13 human sites, **all 13 missed, and the panel emitted zero cites in the file**. Pure coverage, no anchor to sweep from; predicted A = 1/13, C = 6/13. If C fails here but works on PR1622, the rule needs an existing cite to anchor on, and its reach is the 93% figure, not 100%.

---

## What I could not determine

- **The original 133-cluster set.** Not reproducible from surviving artifacts; 16 definitions bracket the NONE band at 16.0–55.1%. My numbers should replace, not be averaged with, the earlier ones.
- **Whether cluster-level detection is causally positional or merely predicted by position.** The nulls establish that position is sufficient to reproduce the band. They cannot rule out an unmeasured variable that co-varies with line number (Read-window mechanics and per-file finding budget both do). Arm C is the intervention that separates them.
- **Whether `tests/` is a separate effect or the size/depth effect.** Same limitation `report-misstax.md` recorded; the tests/src split survives in my data (73.7% vs 19.3%) but so does the confound.
- **One grader.** The 16-shape catalog is regex-induced by me and inherits `klass` labels from a single hand grader with no second rater. The 22.2% unclassified tail I sampled is genuinely heterogeneous (a log-key mismatch across two files, `line[3:]` on a porcelain rename entry, a broad catch demoting a DB outage) — not a missed coherent class, but I read 12 of 219.
- **Whether arm C's cost is acceptable.** I predict ~2x arm A in output tokens and did not price it. Per FINDINGS §6, per-PR cost budget is the binding lever, so a rule that doubles per-file output needs that number before it ships.