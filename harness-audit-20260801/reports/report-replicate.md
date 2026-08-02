Both experiments are complete and scored. Final report:

---

# Replication of the two flagship experiments

**Bottom line: both replicate in direction; one replicates in magnitude, the other is smaller than filed on new material. Neither is a fluke. But the original A/B experiment's ground truth is not reproducible as filed, and the anchor-tolerance choice — undocumented in the audit — moves the capped arms by 38 points.**

All material and scripts: `/private/tmp/claude-501/-Users-quantum-Documents-GitHub-agenticads-sim-plan/e2367c8b-0c8b-43ae-a5d4-98ce3fbcecea/scratchpad/rep2/`. Nothing outside that directory was written. salesagent was read-only (`git show` only).

## Setup

**Subjects (exp 1)** — three new files, `git show 6881e8da4:<path>`, each copied to `rep2/sN/subject.py`:

| | path | lines | GT rule (stated, mechanical) | n |
|---|---|---|---|---|
| s1 | `tests/unit/test_update_media_buy_behavioral.py` | 2,882 | `^\s*with MediaBuyUpdateEnv\(` | 73 |
| s2 | `tests/integration/test_create_media_buy_behavioral.py` | 2,015 | `^\s*with _env\(` | 37 |
| s3 | `tests/integration/test_creative_sync_behavioral.py` | 1,847 | `^\s*with CreativeSyncEnv\(` | 66 |

Ground truth is the regex match set, zero curation (`rep2/truth1.py`). Arms verified programmatically to differ by **exactly one line** in all three pairwise diffs (`rep2/gen_arms.py` asserts it). Paragraph text copied verbatim from the originals. All nine arms read **100%** of their file.

**Matcher** — the harness's own `disposition_ledger.site_tokens`, imported, not reimplemented. Reported at two strengths: `strict` (no range expansion, no bare-ref) and `listy` (expand ranges + resolve bare + standalone ints on lines that already carry a citation). Anchor window ±3 lines, **calibrated on the original arms** (see §3).

## 1. Experiment 1 — the enumeration mandate

Recall of ground-truth sites, `strict / listy`:

| subject | GT | capped | nocap (cap deleted) | **enum mandate** |
|---|---|---|---|---|
| **original** `test_delivery_poll_behavioral.py` | 59 | 10% / 30% | 8% / 35% | **100% / 100%** |
| s1 | 73 | 2% / 39% | 10% / 13% | **46% / 76%** |
| s2 | 37 | 2% / 48% | 0% / 2% | **97% / 100%** |
| s3 | 66 | 3% / 53% | 6% / 18% | **93% / 100%** |
| **mean** | | 4% / 42% | 6% / 17% | **84% / 94%** |

**Last-quartile recall (strict), the audit's headline claim:**

```
            capped        nocap         enum
original     1/14          3/14        14/14
s1           0/21          0/21        13/21
s2           0/ 7          0/ 7         7/ 7
s3           0/16          0/16        16/16
```

The depth-collapse and its repair replicate on **3 of 3** new files. The capped arms recover **1 of 58** last-quartile sites across all four subjects under the strict matcher; the enum arms recover **50 of 58**.

**"Deleting the cap is a null edit" replicates 4/4** — and is consistently *negative*, not merely null: nocap < capped on every subject.

**Where it did not fully replicate: s1.** The enum arm reached 46%/76%, not 100%, for a nameable reason. It found the target family and wrote it up as a NIT **in the exact prose the mandate bans**, listing zero of the 72 sites:

> `## [NIT] MediaBuyUpdateEnv(principal_id="principal_test", tenant_id="tenant_test") literal repeated 72×`
> **Evidence:** `grep -c '...' subject.py` → **72**.

Its s1 recall comes from 22 *other* findings it did enumerate exhaustively. So the mandate's failure mode is not partial enumeration — it is the family being routed to a severity tier where the "Sites" discipline is skipped. This is the same leak `report-ret47.md` §4 identified ("the ban on count-in-prose is scoped to the Sites block and leaks in Evidence/Claim prose"), now shown to cost 54 points of recall on one file rather than 13 unanchored sites.

Measured across all nine arms — findings that state a count but list fewer sites than they state:

| arm | findings | with a count claim | count > sites listed |
|---|---|---|---|
| capped | 29 | 10 | 5 (50%) |
| nocap | 30 | 7 | 7 (100%) |
| enum | 69 | 14 | 4 (28%) |

The mandate cuts the violation rate roughly in half but does not eliminate it.

## 2. Does the mandate cause false positives? No.

Three independent precision measures, none of which the original ran:

**Out-of-file citations:** 0 in 8 of 9 arms; 1 in `s2 capped`. The enum arms cited **zero** nonexistent lines despite emitting 775 / 978 / 1,112 distinct line references.

**Precision of the enumeration itself** — the finding block that best covers the GT family, all listed sites checked against the rule:

| | sites listed | within GT±3 | precision |
|---|---|---|---|
| s2 enum | 43 | 42 | **97%** |
| s3 enum | 116 | 113 | **97%** |

I inspected all four misses. Every one is a legitimate near-variant the arm itself labelled as such: `s3:1824-1826` is the tail of a multi-line `TenantFactory(...)` call the arm listed under "near-variants with an extra tenant kwarg"; `s2:1575` is `env.setup_product_chain(tenant, currency="EUR")`, listed under "near-variants". **Zero fabrications.** Adjusted precision is 100%.

**Cost is the real price**, not precision: enum reports run 22.5–29.3 KB vs 8.0–10.9 KB for capped — **2.4× to 2.9× longer output**.

## 3. Two method defects in the original experiment

**(a) The ground-truth rule was never persisted.** `experiments/ab/` holds the subject and a scorer that computes no recall. `FINDINGS.md` and the source tool-result record only `n=52` and `span 48–2925`. No mechanical rule I could construct yields 52. `^\s*with DeliveryPollEnv\(` yields **59**, spanning **exactly 48–2925**; the next-closest (`principal = PrincipalFactory(tenant=tenant`) yields 53. **The published 100% is not independently re-derivable at the site level.** I re-scored the original arms under the n=59 rule and reproduced the published 27% and 100% (§3b), so the effect is real — but as filed, the experiment cannot be checked.

**(b) Anchor tolerance is undocumented and does most of the work.** Re-scoring the original enum arm against the `with`-anchored rule:

```
window     capped    nocap    enum
exact       0/59     16/59   17/59  = 28%
±2          0/59     16/59   17/59  = 28%
[-3,0]     16/59     20/59   59/59  = 100%
±3         18/59     21/59   59/59  = 100%
```

At line-exact matching the original's headline is **28%, not 100%** — because that arm anchored 43 of its 59 scaffold rows at the *import* line three rows above the `with`. My new subjects anchor *below* it (s3 cited `237-238`, the `TenantFactory` lines). Any replication of this experiment must state its anchor tolerance; the audit does not.

Relatedly: **the nocap arm's published 23% is largely range-expansion.** Under the strict matcher it is 3%; it cited ranges up to 361 lines wide (`subject.py:2061-2422`). The `capped`/`nocap` numbers are matcher-sensitive (4% → 42% mean across matchers); the `enum` numbers are not (84% → 94%).

## 4. Experiment 2 — ledger-at-receipt

New material: 8 first-round lens reports from salesagent session `19e2139f-fbec-46df-9212-9e41f0fc4925` (PR #1567), one per lens type, selected mechanically (`rep2/build_reports2.py`), 102,618 B vs the original's 94,799 B. Arm prompts are **byte-identical to the originals except the Input line**.

**Ground-truth classifier (`rep2/truth2.py`):** a finding anchor is a site token on a `####` heading that (i) sits inside a `## Findings…` section, (ii) begins with `[BLOCKER]`/`[SHOULD-FIX]`/`[NIT]`, (iii) is not marked PASS/CONFIRMED/CLEARED/REFUTED/no-defect, extracted with the harness matcher at `resolve_bare=True, expand_ranges=False`. Sites appearing only in Claim/Evidence/Why/Fix bullets are bare evidence citations and are excluded; so is everything in Summary, Verified-clean, Hypotheses-refuted, and What-I-could-not-verify sections. Yield: **36 anchors** vs 103 raw `path:line` strings — the same 3:1 ratio as the original (21 vs 77).

| arm | **finding anchors** | all-sites (the broken denominator) | artifact | visible output | chars/anchor |
|---|---|---|---|---|---|
| normal | 22/36 = **61%** | 24/103 = 23% | 14,439 | 14,479 | 656 |
| ledger | 35/36 = **97%** | 45/103 = 43% | 24,172 | 34,297 | 691 |
| combined | 36/36 = **100%** | 74/103 = 71% | 55,396 | 70,734 | 1,539 |

*Original, re-scored on anchors (`report-ret47.md`): 29% / 100% / 100%. Original, published on the broken denominator: 7% / 29% / 53%.*

**The ordering and the ceiling replicate.** The ledger arm reaches 97% of finding anchors at **44% of the combined arm's output**. The one miss (`_base.py:279`) is the first half of a two-range heading whose second half it did ship. The audit's re-scored conclusion holds on new material: **ledger-at-receipt is the load-bearing fix; the enumeration mandate on top of it buys evidence-trail coverage (43% → 71% of all sites) at 2.2× the cost per finding anchor.**

Two differences from the original worth recording:
- **The normal arm did much better here (61% vs 29%).** It still loses 14 anchors, all from the `also:` tail of the cap — but the gap the ledger closes is 36 points on this material, not 71.
- **The Report-8 ledger skip did not recur.** Both ledger arms ledgered all 8 reports (headers verified in the transcripts). The original's 5 never-captured sites were attributed entirely to that skip; it is a real but non-deterministic defect, not a structural property of the arm.

## 5. What I would not claim

- **Still n=1 per cell.** Three files × three arms, one run each. No within-cell variance; the s1/s2 gap (76% vs 100%) could be run-to-run noise as easily as subject effect.
- **My GT family choice interacts with arm judgment.** On s1 the enum arm classed the target family as a NIT. The rule was fixed before the runs and stated in `truth1.py`, but a different family on the same file would have scored differently — that is itself the finding, not a controlled variable.
- **Delivery channel differs.** The originals arrived wrapped in `<teammate-message>`; mine arrived as Agent-tool prompts. Constant within each experiment, so within-experiment comparisons are clean; cross-experiment absolute levels are not strictly comparable to the audit's.
- **Two of 38 exp-2 findings carry no site token in their heading** and contribute zero anchors, so the 36-anchor denominator slightly under-counts findings.
- **I did not re-verify any exp-2 citation against the salesagent tree** — the anchors are the lenses' own, taken as given, exactly as the arms had to.

## 6. What this changes for the audit

1. **§5's emission table should be restated.** "27% / 23% / 100%" is one subject, one matcher, one undocumented anchor window. The defensible claim across four subjects is: *capped ≈ 4% (strict) / 42% (permissive); cap-deletion alone is null-to-negative; the enumeration mandate is 84% / 94% and closes the last-quartile collapse in 4 of 4 subjects.* The 100% is not the expected value.
2. **The recommendation survives and strengthens on the precision test** — no false positives, so the only cost is ~2.5× output length. Moving §4b.0 into §3 is still the right edit.
3. **Add the missing clause.** The mandate leaks through severity tiering and count-prose (28% of counted findings still under-list under the mandate). The fix is one sentence scoping the site-list rule to *every* finding regardless of severity, and banning the count in Claim/Evidence, not only in the Sites block.
4. **§5's retention table should be replaced with the anchor-scored one**, and the recommendation should be **ledger-at-receipt alone**. Two independent report sets now agree: 97–100% of finding anchors at under half the cost of the combined arm.
5. **File the ground-truth rule with the experiment.** The A/B experiment's flagship number cannot be re-derived from what was saved. That is a reproducibility defect of the same class as §8's "use the harness's own matcher, or state that you did not."