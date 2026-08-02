All measurements are in. Here is the report.

---

# Does each of the 8 lenses earn its cost?

**Verdict up front: yes, all eight — and the 8-lens shape is the right shape.** I went looking for redundancy and the data refuses to produce it. The largest site-overlap between any pair of lenses is 5.0% Jaccard; removing *any* lens, including admin-ui, costs 15–24% of the panel's finding-site coverage on the turns where it ran. The real inefficiency is not the lens count — it is the fixed per-dispatch floor, and merging lenses recovers only ~2% of corpus cost while forfeiting a fifth of coverage per lens removed.

Scripts: `/private/tmp/claude-501/-Users-quantum-Documents-GitHub-agenticads-sim-plan/e2367c8b-0c8b-43ae-a5d4-98ce3fbcecea/scratchpad/lensval/` (`cost.py`, `yield.py`, `findings.py`, `overlap2.py`, `shipped.py`, `severity.py`, `econ.py`, `novelty.py`, `scaling.py`, `fp2.py`, `startup.py`). 759 dispatches from `agentType`, dedup by `requestId`, joined to fan-out turns via `meta.json:toolUseId` → main-transcript `requestId`.

## The ranked table

Ranked by cost per unique finding (cheapest first). "Unique" = the finding's cited `path:line` set was raised by no other lens on the same fan-out turn. "LOO" = share of the panel's finding-sites lost if this lens is removed.

| lens | disp | M units | % lens spend | units/disp | findings | unique | uniq % | B/S/N | **k units per unique** | LOO % lost | sites → artifact | sole raiser | detectors/disp | suspect cites |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| architecture-guards | 119 | 85.4 | 13.6% | 718k | 387 | 305 | 78.8 | 16/166/205 | **280** | 16.7 | 187 | 107 | 0.46 | 3.33% |
| code-patterns | 121 | 88.8 | 14.2% | 734k | 426 | 304 | 71.4 | 9/190/227 | **292** | 23.9 | 327 | 188 | 0.56 | 2.63% |
| admin-ui | 19 | 9.4 | 1.5% | 495k | 42 | 31 | 73.8 | 0/24/18 | **303** | 15.0 | 39 | 27 | 0.00 | 0.00% |
| spec-conformance | 112 | 93.7 | 14.9% | 836k | 383 | 297 | 77.5 | 17/210/156 | **315** | 20.8 | 208 | 127 | 1.68 | 5.47% |
| test-integrity | 128 | 108.1 | 17.2% | 844k | 438 | 322 | 73.5 | 15/205/218 | **336** | 24.2 | 285 | 177 | 0.63 | 2.46% |
| security | 85 | 66.1 | 10.5% | 777k | 232 | 182 | 78.4 | 6/124/102 | **363** | 18.0 | 164 | 112 | 0.02 | 1.46% |
| bdd | 85 | 83.1 | 13.3% | 978k | 265 | 226 | 85.3 | 9/113/143 | **368** | 21.5 | 176 | 129 | 0.05 | 1.02% |
| error-wire | 90 | 92.5 | 14.8% | 1028k | 300 | 217 | 72.3 | 17/151/132 | **426** | 22.2 | 237 | 133 | 0.58 | 3.17% |
| **total** | **759** | **627.1** | 100% | 826k | **2,473** | **1,884** | **76.2** | **89/1183/1201** | 333 | — | 1,263 | 1,000 | 0.59 | 2.80% |

The spread from best to worst is **1.5x** (280k → 426k). For eight independently-scoped reviewers that is a remarkably tight band — there is no outlier to cut.

## 1. Cost

627.1M units over 759 dispatches, **54.5% of the 1.15B corpus**. Sensitivity to the output-token treatment (the brief is right that `output_tokens` is a stub — median 3):

| treatment | total | share ordering |
|---|---:|---|
| stub `output_tokens` | 595M | unchanged |
| visible text + tool_use JSON ÷ 3.8 (used above) | 627M | unchanged |
| + stripped reasoning (visible × 5, per FACTS' 75–84%) | 811M | unchanged |

Per-lens **shares move by at most 0.6pp** across all three, and the cost-per-unique ranking is stable. Every conclusion below is invariant to how output is counted.

Per-dispatch cost is driven by dispatch length, not by lens identity: error-wire and bdd are the expensive ones (1,028k / 978k per dispatch) purely because they run longer (46.8 and 45.2 API calls vs 23.2 for admin-ui).

## 2. Unique yield — the key metric

This is where the redundancy hypothesis dies. Pairwise Jaccard on finding-sites, same fan-out turn, corpus-aggregated:

```
code-patterns / test-integrity   5.0%      spec / test-integrity        3.1%
arch-guards   / code-patterns    5.0%      error-wire / security        3.0%
arch-guards   / test-integrity   4.5%      bdd / test-integrity         2.8%
admin-ui      / code-patterns    4.2%      ... 20 more pairs all < 3%
code-patterns / error-wire       4.0%      admin-ui / bdd, admin/spec   0.0%
```

The obvious redundancy candidates are the *least* redundant: `bdd`↔`test-integrity` is 2.8%, `security`↔`code-patterns` 2.4%, `error-wire`↔`spec-conformance` 2.6%. The lens definitions carry explicit handoff protocols (`review-test-integrity.md:82-83`, `review-error-wire.md:87-88`, `review-security.md:75-76`) and the handoffs demonstrably work.

The obvious objection is that most turns are small panels, so lenses have few peers to collide with. Restricting to real panels kills that objection:

| panel size | turns | test | patt | arch | spec | wire | bdd | secu | admin |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ≥2 lenses | 221 | 73.0 | 70.6 | 77.8 | 76.5 | 71.6 | 84.3 | 75.0 | 73.8 |
| ≥5 lenses | 44 | 63.6 | 60.2 | 70.2 | 68.9 | 62.9 | 81.2 | 65.5 | 79.2 |
| **≥7 lenses** | **21** | 72.0 | 64.6 | 79.7 | 77.3 | 60.6 | **92.5** | 70.4 | 78.9 |

(values = % of that lens's findings whose sites no other lens on the same turn cited)

Even with 7–8 lenses all reviewing the same diff simultaneously, **60–93% of each lens's findings are sites nobody else touched.** No lens is a duplicate of another.

**Leave-one-out** is the direct test of "would we lose anything." On turns where the lens ran:

| lens | turns | panel sites | lost if removed | % lost |
|---|---:|---:|---:|---:|
| test-integrity | 124 | 6,047 | 1,464 | 24.2 |
| code-patterns | 117 | 5,799 | 1,386 | 23.9 |
| error-wire | 89 | 4,906 | 1,091 | 22.2 |
| bdd | 81 | 4,257 | 914 | 21.5 |
| spec-conformance | 101 | 5,415 | 1,127 | 20.8 |
| security | 75 | 4,474 | 804 | 18.0 |
| architecture-guards | 113 | 5,574 | 932 | 16.7 |
| admin-ui | 19 | 1,384 | 207 | 15.0 |

**Survival to the shipped artifact** (81 reports, 31 PRs) is the strongest form: of 1,776 `path:line` sites in shipped consolidations on PRs where the panel ran, 1,263 (71.1%) trace to a lens finding — and **1,000 of those 1,263 (79%) had exactly one lens raising them.** The raiser-count distribution is `{1: 1000, 2: 198, 3: 41, 4: 18, 5: 5, 7: 1}`. Sole-raiser rate per lens on its own shipped sites: bdd 73%, admin-ui 69%, security 68%, test-integrity 62%, spec 61%, arch 57%, patterns 57%, wire 56%.

## 3. False positives

2.80% of 9,765 finding-level citations are suspect: 26 `LINE-OVER` (line beyond the file's maximum length across all 17,453 blob versions in `git rev-list --all`) and 247 `path-unknown`. By severity: BLOCKER 7.01%, SHOULD-FIX 2.64%, NIT 2.43%.

I hand-adjudicated all 273. **Nearly all are my oracle's limits, not the lenses':**
- 163 of 247 `path-unknown` are bare-basename shorthand my regex lifted out of prose (`create.py`, `update.py`).
- 25 are AdCP **spec-repo** paths (`dist/compliance/3.1.0-beta.3/universal/error-compliance.yaml:359`) — correctly cited, out of this repo. All spec-conformance's, which is why its 5.47% is the highest and is not a defect.
- 44 are repo-relative files this clone never fetched: `src/core/adcp_version.py`, `tests/unit/test_check_dormant_scenarios.py`, `tests/integration/test_list_creatives_filter_cap.py`. The checkout is at `6881e8da4` / 2026-07-16; reviews run to 2026-07-30. These are files the reviewed PRs *added*.
- Of 26 `LINE-OVER`, most are 2–20 lines over (`src/core/logging_config.py:266` vs max 264; `src/core/mcp_compat_middleware.py:226,240` vs 214) — the PR under review added lines. A handful are genuinely large overshoots (`tests/utils/a2a_helpers.py:725` vs 240; `test_mcp_typeadapter_validation_envelope.py:558` vs 106).

**Defensible statement: citation-level false positives are bounded above by 2.8%, and the adjudicated residual after removing clone-staleness, spec-repo paths, and prose shorthand is well under 0.5%.** I could not close it further — the oracle for "contradicted by the code at that SHA" requires the PR branches, and 23 of ~31 reviewed PRs have no local ref.

## 4. Severity honesty

Lenses raised **89 BLOCKERs**; artifacts covering the same PRs declared **20**. On the 15 PRs where both are measurable: 68 lens BLOCKERs → 20 artifact BLOCKERs.

| lens | BLOCKERs | reached artifact | kept BLOCKER | downgraded | dropped |
|---|---:|---:|---:|---:|---:|
| error-wire | 17 | 13 | 5 | 5 | 2 |
| test-integrity | 15 | 6 | 2 | 0 | 4 |
| bdd | 9 | 4 | 2 | 0 | 4 |
| architecture-guards | 16 | 2 | 1 | 1 | 5 |
| code-patterns | 9 | 2 | 1 | 0 | 4 |
| security | 6 | 2 | 1 | 1 | 1 |
| spec-conformance | 17 | 5 | 1 | 0 | 7 |

Two readings, and I think the second is right:

- **Over-calling.** 89 → 20 is 4.5x attrition and BLOCKER is the most-suspect severity in the FP probe (7.01% vs 2.4% for NIT).
- **Consolidation attrition, not lens inflation.** BLOCKER density is *low* — 89 of 2,473 findings is 3.6%, and every lens sits between 2.1% (code-patterns) and 5.7% (error-wire). That is not a suite crying wolf. The charter's own §4b.0 documents this exact drop channel twice (the unsynthesized-NIT drop, and the #1534 SF3 site drop), and §4b.1 exists because the consolidator was inflating. My data shows the opposite failure now dominating: **spec-conformance loses 7 of 17 BLOCKERs with no trace in any artifact; architecture-guards 5 of 16, and 4 more had no `path:line` anchor at all** — which §3 warns is precisely the finding that gets lost.

Caveat I cannot remove: a round-1 BLOCKER fixed before the consolidated artifact was written legitimately does not appear. My matcher is `(basename, line)`, forgiving of the reports' `:657` shorthand but not of line drift between rounds. Treat these as an echo rate, not a fix rate.

The one clear honesty signal: **architecture-guards has 4 BLOCKERs with no site anchor at all** (25% of its BLOCKERs) — the highest of any lens, and the charter names unanchored findings as the ones that vanish.

## 5. The architectural question: would fewer, deeper lenses outperform eight?

No. Three independent lines of evidence.

**(a) Panel breadth buys coverage roughly linearly; it does not saturate.**

| panel size | turns | mean distinct sites/turn | sites per lens | findings/turn |
|---:|---:|---:|---:|---:|
| 1 | 39 | 9.4 | 9.4 | 2.8 |
| 2 | 112 | 17.7 | 8.8 | 5.5 |
| 3 | 48 | 34.4 | 11.5 | 9.6 |
| 4 | 17 | 70.9 | 17.7 | 15.3 |
| 6 | 10 | 98.9 | 16.5 | 27.1 |
| 7 | 10 | 99.5 | 14.2 | 26.0 |
| 8 | 11 | 81.6 | 10.2 | 25.4 |

Sites-per-lens stays flat at 9–18 all the way out to 8. If lenses substituted for each other, per-lens yield would collapse as the panel grew. It doesn't. (The 8-panel dip is n=11 on different PRs, not saturation.)

**(b) The lenses are not spread too thin — the back half of a dispatch is doing new work.** Splitting each dispatch's tool calls into quarters and counting first-time targets:

| lens | Q1 new% | Q2 | Q3 | Q4 | Q4/Q1 new targets |
|---|---:|---:|---:|---:|---:|
| test-integrity | 98.9 | 93.7 | 92.2 | 91.4 | 0.88 |
| bdd | 99.2 | 90.5 | 86.3 | 87.3 | 0.84 |
| spec-conformance | 99.3 | 95.6 | 95.1 | 93.9 | 0.90 |
| (all others) | ~99 | 90–96 | 89–95 | 92–96 | 0.88–0.89 |

In the final quarter of a dispatch, 87–96% of tool calls still hit a target the agent has not touched. There is no exhaustion signal anywhere. A merged, "deeper" lens would not be finding more per unit — it would be doing the same work with a longer context.

**(c) There *is* diminishing return, but it is between dispatches, not within — and it argues against merging.** Comparing shortest-quartile to longest-quartile dispatches:

| lens | Q1 findings/100k units | Q4 | marginal rate Q1→Q4 | marginal / base |
|---|---:|---:|---:|---:|
| test-integrity | 0.678 | 0.273 | 0.123 | 0.18 |
| code-patterns | 0.760 | 0.347 | 0.190 | 0.25 |
| bdd | 0.486 | 0.268 | 0.180 | 0.37 |
| error-wire | 0.481 | 0.275 | 0.193 | 0.40 |
| security | 0.492 | 0.271 | 0.199 | 0.40 |
| architecture-guards | 0.578 | 0.358 | 0.263 | 0.45 |
| spec-conformance | 0.498 | 0.380 | 0.322 | 0.65 |

Marginal yield on the extra spend in a long dispatch is 18–65% of the base rate. **A merged lens is by construction a long dispatch.** Merging two lenses moves their combined work from two Q1-shaped dispatches into one Q4-shaped one — onto the worst part of this curve.

**(d) The saving from merging is tiny.** The only cost a merge actually removes is the fixed per-dispatch startup. Median first-call prefix is 52.0k–56.8k tokens (62.8k–70.6k units) and is nearly identical across all 8 lenses — it is the harness's floor, not the lens's. **Total first-call cost across all 759 dispatches: 51.5M units = 8.2% of lens spend, 4.5% of corpus.** Halving the panel eliminates ~380 startups ≈ 26M units ≈ **4.1% of lens spend, 2.3% of corpus** — and costs 15–24% of site coverage per lens removed. That trade is indefensible, and it is exactly the "hidden downgrade" the standing constraint names.

The lever that *is* available without touching capability: the Step-0 preamble is 13.8 MB of identical text delivered across 759 dispatches (≈3.6M tokens at visible rates), loaded in only 546 of them. That is a caching/dispatch-prompt problem, not a lens-count problem.

**Is admin-ui a vestige?** No — it is a correctly gated conditional lens, and the artifacts prove the gating is deliberate and logged. Of 20 artifacts naming run/skipped specialists, **admin-ui is run 1 time and skipped 19**, each time with a stated reason (`"skipped: admin-ui (no admin/templates/routes) — logged, not silent"`). Its 19 dispatches cost 9.4M units — **1.5% of lens spend** — and produced 42 findings at 303k/unique, third-cheapest of all eight, with a **0.00% suspect-citation rate** (the only lens with zero) and 27 sole-raiser sites in shipped artifacts. Its findings are things no other lens owns: `route-conflict-guard-scope-vacuity — check_route_conflicts.py:33`, `pattern-6-matcher-gap — hardcoded /admin/ fetch escapes the hook even though the file is in-glob`, `ssot-partial-copy — FINALIZE_READY_CREATIVE_STATUSES`. Its own definition states the two hooks guarding Patterns #2 and #6 are weak and fail-open; it is the only reviewer of that surface. Retiring it saves 1.5% and blinds the harness to two of seven critical patterns.

**Do the three near-zero-detector lenses compensate?** Yes — and the "no detectors" framing understates them, because they use different empirical instruments:

| lens | detectors/disp | pytest invocations/disp | `git grep`/disp | guard refs/disp |
|---|---:|---:|---:|---:|
| bdd | 0.05 | **7.3** | 6.9 | 5.6 |
| security | 0.02 | 1.7 | **12.5** | 0.7 |
| admin-ui | 0.00 | 0.7 | 11.2 | 0.9 |
| test-integrity | 0.63 | 9.7 | 8.9 | 4.0 |
| spec-conformance | **1.68** | 1.0 | 6.5 | 0.4 |

bdd runs the second-highest pytest rate in the panel (7.3/dispatch) — it is empirical via the suite, exactly as `review-bdd.md:48,65` instructs ("RUN the specific scenario and read PASS vs XFAIL — never infer from an aggregate count"). Security runs the highest `git grep` rate (12.5/dispatch), which is what `review-security.md:45` prescribes. They are not idle; they are instrumented differently. And they have the **highest unique-yield rates in the panel** (bdd 85.3% / 92.5% on full panels; security 78.4%) and the **lowest suspect-citation rates** (1.02% / 1.46%).

**Security, argued both ways.** Against: 6 BLOCKERs across 85 dispatches at 66.1M units is the thinnest BLOCKER yield in the panel, and it runs 2 detectors total. For: those 6 are `cross-principal-leak+FK-500`, `credential-persistence-seam-absent` (request bearer credentials reaching 4 persistent sinks), `S6-residual fail-open` on natural-key scoping, `untyped-leak-on-explicit-skill-path`, `incomplete-cap-coverage`, and `cosign-no-registry-auth`. Its SHOULD-FIX stream carries `dns-rebinding-toctou`, `redirect-ssrf-sibling`, `weak-secret-fail-open`. 68% of its shipped sites had no other raiser; removing it costs 18% of panel coverage. **The evidence points to keep.** This is a cheap insurance policy on a catastrophic class: 10.5% of lens spend, 5.7% of corpus, buying the only reviewer of the authz/tenant/SSRF surface. One qualifier worth naming: `review-security.md:20` instructs deferring generic CWE to the built-in `/security-review`, and I found no evidence in the transcripts that that second pass is actually being run — so the generic half of the security surface may be uncovered in practice, which is an argument for *more* security capability, not less.

## 6. Recommendation per lens

| lens | recommendation | evidence |
|---|---|---|
| **architecture-guards** | **KEEP** | Cheapest per unique finding (280k). But **4 of 16 BLOCKERs carry no `path:line` anchor** (25%, worst in panel) and only 2 of 16 reached an artifact. Fix the anchoring, not the lens — §3 says an unanchored finding is the one that gets lost. |
| **code-patterns** | **KEEP** | 2nd cheapest (292k), most shipped sites (327) and most sole-raiser sites (188) of any lens. Its 5.0% overlap with test-integrity and arch-guards is the panel maximum and is still negligible. |
| **admin-ui** | **KEEP** (conditional, already gated) | 1.5% of spend, 3rd cheapest per unique (303k), 0.00% suspect citations, 15% LOO loss, sole owner of Patterns #2/#6 where both hooks fail open. Skipped 19/20 with a logged reason — the gating already works. |
| **spec-conformance** | **KEEP + DEEPEN** | Only lens whose detectors actually run (1.68/disp, 50% of runs). Highest BLOCKER count (17, tied). **But 7 of 17 BLOCKERs vanish before the artifact** — worst attrition in the panel. Deepen the consolidation handoff, not the detection. Its 5.47% suspect rate is spec-repo citations, not error. |
| **test-integrity** | **KEEP** | Largest lens (128 disp, 17.2%), most findings (438), most unique (322). Highest empirical rate (9.7 pytest/disp). Its 24.2% LOO loss is the largest in the panel. |
| **security** | **KEEP** (insurance, argued above) | 6 BLOCKERs but all in the catastrophic class; 78.4% unique, 68% sole-raiser on shipped sites, 18% LOO. Separately: **verify the deferred `/security-review` pass is actually being run** — I found no trace of it. |
| **bdd** | **KEEP + DEEPEN** | **Highest unique yield in the panel** (85.3%; 92.5% on 7+ panels), lowest suspect-citation rate (1.02%), 21.5% LOO. Highest cost per unique of the cheap group (368k) because it runs 7.3 pytest/dispatch — that is the point, not waste. Deepen = give it detectors for the dormant-scenario class it currently finds by hand (9 of its 9 BLOCKERs are dormant-grader / spec-conflict findings). |
| **error-wire** | **KEEP** (tighten) | Most expensive per unique (426k) and lowest unique share on full panels (60.6%), overlapping code-patterns (4.0%) and test-integrity (3.9%). **But the best BLOCKER survival in the panel** (13 of 17 reached the artifact, 5 kept at BLOCKER). Its two handoff clauses (`:87-88` with test-integrity, `:80` with code-patterns) are the right mechanism — tighten those rather than merge. |

**MERGE-WITH-X: none. RETIRE: none.** No pair exceeds 5% site overlap; no lens falls below 60% unique on a full panel; no lens can be removed for less than 15% of panel coverage. The burden of proof for removal is high and nothing here comes close to meeting it.

## What I could not measure

- **"Fixed before merge" for most PRs.** The local checkout is `6881e8da4` / 2026-07-16; reviews run to 2026-07-30, and 23 of ~31 reviewed PRs have no merge commit or fetched ref locally. Severity honesty is therefore measured as *echo into the shipped artifact*, not as *fixed before merge*. A `git fetch --all` + PR-ref fetch would let this be redone properly.
- **"Contradicted by the code at that SHA."** Same cause. I could test path existence and line-in-range against 17,453 blob versions, but not semantic contradiction.
- **Per-finding agent attribution in artifacts** exists in only 3 of 81 reports (the §4b.4 ledger is recent). Everything else is `(basename, line)` matching, which is forgiving of the reports' `:657` shorthand but blind to line drift between rounds.
- **Stripped reasoning tokens.** My output reconstruction counts visible assistant text + tool_use JSON at 3.8 chars/token. FACTS says reasoning is 75–84% of output, so true output is ~4–5x my figure. I ran all three treatments; shares move ≤0.6pp and no ranking changes, but the absolute 627M would be ~811M with reasoning included.
- **Whether "unique by site" equals "unique by defect."** Two lenses can find the same *defect class* at different sites and my measure calls both unique. I checked the inverse via normalized pattern-ids and found the vocabularies largely disjoint (arch-guards is dominated by `guard`/`matcher`/`scan`, bdd by `dormant`/`pitfall`/`vacuous`, spec by `spec`/`stale`/`recovery`), but I did not build a semantic clusterer.
- **The panel-size ≥7 rows are n=21 turns.** The full-panel overlap numbers are the most decision-relevant and the thinnest; they should be re-run as the corpus grows.
- **One incidental finding worth flagging:** the `review-charter.md` content in transcripts is 25,258 B / 133 lines, while the file on disk is now 39,867 B / 154 lines. That is file growth over the corpus window, not truncation — but it means any Step-0 cost figure derived from the *current* file size overstates what was historically delivered.