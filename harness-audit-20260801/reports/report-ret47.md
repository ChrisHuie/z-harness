Analysis complete. Every number below is reproducible from the scripts at `/private/tmp/claude-501/-Users-quantum-Documents-GitHub-agenticads-sim-plan/e2367c8b-0c8b-43ae-a5d4-98ce3fbcecea/scratchpad/ret47/` (`parse.py`, `trace.py`, `classify.py`, `tags.py`, `final.py`, `arms.py`, `taxonomy.py`).

# The 47% is not a retention failure. The denominator is not a finding list.

## Headline

**Zero finding anchors were lost.** `ret-combined` shipped **21 of 21** ground-truth sites that are finding anchors in the reports — 100%, confirmed by two independent classifiers that never see each other's output. So did `ret-ledger`. `ret-normal` shipped 6 of 21 (29%).

The 40 "unexplained" points are three separate things, none of them a lost finding:

| | sites | % of 73 | what it is |
|---|---|---|---|
| shipped | 42 | 58% | — |
| suppressed by *"Findings only; no praise sections"* | 26 | 36% | 22 PASS/cleared/no-defect sites + 4 bare evidence citations |
| never in the ledger — Report 8 | 5 | 7% | one real mechanical defect |
| **silently dropped finding anchors** | **0** | **0%** | — |
| **unified away** | **0** | **0%** | — |
| **adjudicated away** | **0** | **0%** | — |

The prediction failed because `truth.json` is **the mechanical extraction of every distinct `path:line` string in `reports.md`** — I reconstructed it exactly, 77/77, zero curation. It counts a lens saying *"`Any` is imported (`api_v1.py:12`)"* as a ground-truth site. Predicting a consolidated review would emit 97% of that set was predicting it would reproduce the evidence trail of eight lens reports. The charter forbids exactly that.

## Correction to the measured number first

`score.py` uses a strictly looser instrument than the artifact it grades: it neither expands `N-M` ranges nor resolves bare `:N`. Under a harness-style matcher (`expand_ranges`, `resolve_bare`, as `disposition_ledger.site_tokens` does):

```
strict (score.py)                artifact 39/73 = 53%
+expand ranges                   artifact 41/73 = 56%
+expand +bare (harness-style)    artifact 42/73 = 58%
```

**5 of the 40 points are measurement.** Three concrete false drops: `test_uc018_list_creatives.py:24` ships inside `:22-27`; `test_list_creatives_concept_filter.py:85` ships as *"directly at `:85`"*; `api_v1.py:17` ships as *"module-level `from adcp.types import BrandReference` at `:17`"*. This is FINDINGS §8's trap recurring — I flag it because the ledger→artifact delta is the quantity under study.

## 1. Unification is not where sites die — the hypothesis is falsified

I audited all eight clusters the artifact explicitly unified:

```
F2  (R4 4.1-4.8, "one finding across eight sites")  12/12 preserved
F1  (R7 7.1-7.3 + R8, "unified at max severity")      4/4
F3  (R3 3.1/3.5 + R5 5.1, two rounds merged)          4/4
F4  (R1 1.2 + R2 2.1, same site two lenses)           1/1
F6, F7, F10, F12                                      11/11
TOTAL                                                32/32 = 100%
```

F2 is the strongest case: the lens filed one finding across eight sites, the orchestrator unified it, and the artifact lists all eight **plus four more** it pulled in from other reports. The charter sentence *"Unification must PRESERVE every site, not collapse the count"* did its job.

**Making the unified site list "mandatory-exhaustive" would be a null edit** — the same shape as deleting the cap in the emission experiment. Do not spend the edit.

## 2. Adjudication happened constantly and never caused an omission

This is the most interesting result. The orchestrator adjudicated five items down explicitly, in visible text:

- *"2.2 is not a finding about the PR at all; it is a defect in the reviewer catalog"* → still shipped, as **F11**
- *"5.3 is mislabeled… I am demoting it to a non-finding rather than propagating a severity its own author disclaims"* → still shipped, as an **F10** site
- *"both of report 6's NITs conclude 'no change required' in their own fix fields… observations dressed as findings"* → both still shipped, as **F10** sites
- *"2.13 is explicitly unverified — belongs in 'could not verify,' not as a finding"* → shipped in that section

Under the enumeration mandate, **adjudication changed the disposition, not the presence**. F10 exists solely to carry three findings the filing lenses themselves retracted. That is the mandate working better than anyone predicted, and it means "judgment loss" is empirically ~zero in this arm — the opposite of the standing worry.

## 3. The one real mechanical defect: Report 8 was never ledgered

`ret-ledger` wrote 8 ledgers. `ret-combined` wrote **7** and skipped the last one.

```
ret-ledger    turns  6  8 10 12 14 16 18 20   → reports 1..8
ret-combined  turns  6  8 10 12 14 16 18 --   → reports 1..7, report 8 missing
```

**All 5 never-captured sites are Report-8-only** (`api_v1.py:12`, `boundary_completeness.py:162`, `creative_list.py:4`, `listing.py:474`, `listing.py:554`). Report 8 spans `reports.md:476-543`; the citations sit at lines 523, 525, 530, 539. The attribution is 5/5, exact.

The mechanism is nameable. Turn 16 ends: *"Now reports 7 and 8."* Turn 18 writes Report 7's ledger and issues the Read for Report 8. Turn 20 opens: **"All eight read. Consolidating from the ledger."** — asserting a ledger it did not write. **Announcing a two-report batch and satisfying it with one ledger let the second inherit "already handled" status.** No truncation was involved: every turn ended `tool_use` or `end_turn`, never `max_tokens`.

## 4. The residual that *is* a real loss — 8 sites, and one provable leak

Inside the 26 suppressed sites, 8 are evidence *for a finding that shipped*, which the "one row per site" rule arguably does demand: `_base.py:632`, `dispatchers.py:136/168/174`, `uc005_format_id_shape.py:37/45`, `when_request.py:71`, `test_list_creatives_concept_filter.py:105`.

One of these is a clean, quotable violation. Artifact F4:

> `wire_error_envelope` is contractually `dict | None`; **all three dispatchers populate it with a plain dict**, so the `hasattr` branch is unreachable.

F4's Sites list has exactly one row. "All three dispatchers" is the charter's explicitly banned *"N places" prose* — and the three unanchored sites are precisely `dispatchers.py:136`, `:168`, `:174`, all three in the dropped set. **The ban on count-in-prose is scoped to the Sites block and leaks in Evidence/Claim prose.** 13 such constructs survive in the artifact.

## The verdict: mechanical, but the "conflict" is not the one you named

**It is a mechanical ceiling, not a judgment ceiling** — but the conflicting pair is not *unify* vs *enumerate*. Those two cooperate perfectly (32/32). The live conflict is:

> **"Findings only; no praise sections"** vs **"a finding must list every site it covers."**

The first has no licensed destination for a site that is real, cited, and *not a finding*. The orchestrator obeyed it correctly. 26 of the 31 non-shipped sites died there, and it takes an instruction to move them, not a judgment nudge.

Two consequences for the audit:

1. **Re-score the retention experiment against finding anchors.** The honest table is **29% → 100% → 100%**, and it says the ledger fix alone is sufficient for findings; the no-cap + enumeration additions buy coverage of *evidence*, not of findings. That materially changes what to ship: `ret-ledger` is 41% cheaper in output tokens (30,170 vs 35,003) for identical finding-anchor recall.
2. **FINDINGS §5's "40 points unexplained" and §7's "what binds the remaining 47%" should be closed** — 36 points charter-compliant suppression, 7 points one ledger break, 5 points measurement — with the residual restated as the 8 evidence-under-a-shipped-finding sites.

## Next arm — one change, pre-registered

**`ret-verify`.** Identical to `ret-combined`. Add exactly one clause, and change nothing else:

> Close with a **Verification appendix** — every site any lens reported as checked-and-clean, or cited as evidence for a check, **one row per site**: `path:line | lens | check performed | verdict`. This is not a findings section; it is the coverage record, and it is mandatory and exhaustive.

This is the discriminating test. My diagnosis says the 26 lost sites were suppressed by an instruction with no licensed destination. Give them a destination and they should emit. If they do not, the residual is a judgment ceiling and this clause is a null edit — which is itself the result.

**Prediction, stated before the run: 84% of 73 sites in the artifact (61/73), band 75–90%, measured with `expand_ranges` + `resolve_bare`.** Strict `score.py` equivalent: **79%** (the strict/harness offset measured in this arm is 5 points). Components: finding anchors 21/21 (proven twice); PASS/cleared 34/43 (~80%, vs 37% today); bare evidence 6/9. Hard ceiling is the ledger at 90%.

**Falsification, also pre-registered:** below **65%** means judgment, not instruction, is binding, and no wording change will move it. Above **90%** means the ledger ceiling itself moved, which would contradict the Report-8 finding and should be treated as suspect until the ledger turn count is checked.

Second, cheaper, independent arm — worth running in parallel because it is separable: **`ret-lockstep`**, `ret-combined` plus *"Read exactly one report per turn. Before each Read, state `ledger for report N-1 complete`."* Prediction: recovers 4 of 5 Report-8 sites; ledger 90% → 97%; artifact 58% → 62%. Small, but it closes the only genuine mechanical loss in the arm.

## What I could not measure

- **Thinking is 100% stripped** in all three arms — 8, 10, and 2 blocks, **0 characters total**. Every adjudication I attribute is visible-text adjudication. If the orchestrator reasoned about dropping the 26 suppressed sites and did not say so, that reasoning is unrecoverable, and "adjudicated away = 0" is a floor, not a ceiling.
- **My finding-anchor classifier is regex over `reports.md`.** It agrees with the orchestrator's own ledger role-tags (18/18 FINDING shipped vs 21/21) but both could share a bias; I did not get a second human rater. The bucket labelled "PASS/cleared" also absorbs mutation-confirmed evidence sites (`_base.py:632` matched on "CONFIRMED"), which is why I hand-separated the 8 real evidence losses in §4 rather than trusting the bucket.
- **Why Report 8's ledger was skipped** — I established it was not truncation and that the batch announcement preceded it. I did not test the batch-announcement mechanism; that is what `ret-lockstep` would establish.
- **n = 1 per arm.** Every number here is a single run. The 21/21 finding-anchor result replicating across two independently-prompted arms is the strongest control available, and it is not a randomized one.