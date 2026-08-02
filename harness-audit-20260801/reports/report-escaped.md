Verified: exactly 29 refs fetched (+9.5 MB), working tree untouched, nothing pushed.

---

# The harness's true miss rate is measurable, and it is high

**Headline: the false-positive rate is now decided and it is excellent (0.098%). The false-*negative* rate is the problem. Against the one genuinely independent human reviewer, the panel missed 52% of the sites he flagged and under-called another 16% — and 87% of those misses were in files a lens had opened.**

---

## 0. A method correction that invalidates part of the prior "human corroboration" result

`report-step0.md` axis 3 graded the panel against 1,730 "human inline comments." Those comments are four different things, and one of them is the panel itself.

| author | n | median len | carries panel's `[BLOCKER]/[SHOULD-FIX]/[NIT]` | median lag after nearest lens run | what it actually is |
|---|---|---|---|---|---|
| KonstantinMirin | 985 | 425 | **0.0%** | **4,019 min (2.8 d)** | independent review findings |
| ChrisHuie | 133 | 1,073 | **61.7%** | **53 min** (84% within 6 h) | **the panel, relayed** |
| mkostromin-sigma | 433 | 186 | 0.0% | 2,634 min | dispositions ("Addressed in `e4ea4d0`… closing") — 363/433 |
| pmezzich | 118 | 475 | 0.0% | 9,210 min | author responses ("Good catch — done") |

Verbatim 9-gram overlap between ChrisHuie's comments and the panel's reports is low (median 0.068) — the orchestrator **rewrites** rather than pastes, which is why a text-similarity detector misses it. The severity vocabulary and the 53-minute lag give it away. Grading the panel against ChrisHuie's comments is grading the panel against itself; it inflates recall. All numbers below exclude them.

Script: `/private/tmp/claude-501/-Users-quantum-Documents-GitHub-agenticads-sim-plan/e2367c8b-0c8b-43ae-a5d4-98ce3fbcecea/scratchpad/esc/build.py`

---

## Q4 — False positives: decided

All 29 missing PR heads fetched (only those 29; +9.5 MB; `refs/pull/**` count = 29, not the 1,214 glob). **All 1,334 referenced SHAs now resolve locally.** I also found and fixed a second confound prior work did not flag: **`gh pr view --json` silently caps `commits` and `files` at 100.** PR1399's file list was 100 of **393**; PR1430's commit list 100 of **376**. Rebuilt both from git.

| tier | definition | n | phantom |
|---|---|---|---|
| **1 (headline, no inference)** | cite gives a full path the PR touched; line beyond EOF at *every* PR commit | 3,059 | **3 = 0.098%** |
| 2 | bare basename; best over *all* same-named files in the tree | 6,532 | 18 = 0.276% |
| combined | | 9,591 | 21 = **0.219%** |

By lens (tiers 1+2): security 0.000%, admin-ui 0.000%, code-patterns 0.105%, architecture-guards 0.109%, spec-conformance 0.246%, bdd 0.273%, error-wire 0.302%, test-integrity 0.499%. Charter READ 0.217% vs NOT 0.226% — still null.

5 of the 21 are off-by-≤2 (`:44 > 43`, `:58 > 57`, `:217 > 215`) — "append at end of file," not hallucination. Prior work's ≤0.5% bound holds and tightens to **0.1–0.2%**.

Two caveats. My first pass produced 31 phantoms including 15 on `tests/harness/product.py:250` — **that was my basename-guesser, not the agents**; tier-2 tree resolution cleared all 15. And this test only asks *does the line exist*. **It cannot tell you whether the claim about that line is true.** Section Q1 has a case where every cite resolves and the conclusion is still wrong.

Script: `.../esc/fp_strict2.py`

---

## Q2 — The human comparison: the harness's real misses

864 KonstantinMirin findings, on 28 PRs, all raised **after** the panel had already run on that PR (so the panel had its chance).

```
CAUGHT (panel had it at >= SHOULD-FIX)   276 = 31.9%
UNDER-CALLED (panel had it as NIT/untagged) 140 = 16.2%
MISS (panel never cited the site)        448 = 51.9%
```

Bootstrap over PRs (n=28): miss rate 95% CI **[41.8%, 60.9%]**.

**Of the 448 misses, 391 (87.3%) were in files a lens had explicitly opened, grepped, or diffed.** Only 46 (10.3%) were files no lens touched. **100% of missed sites were inside the PR's own diff.** This is a capability gap, not a coverage gap.

Line-tolerance sensitivity (my ±12 is a judgement call, so here is the whole curve):

| tolerance | ±0 | ±3 | ±6 | **±12** | ±25 | ±50 |
|---|---|---|---|---|---|---|
| MISS | 72.3% | 64.9% | 60.3% | **51.9%** | 43.1% | 31.9% |

The tolerance-free statement: **at file level the panel cited the same file 91.6% of the time — it was reading the right code — yet it landed on the specific site only 48% of the time with ±12 lines of slack.**

**The DRY class confirms Chris's memory.** 117 DRY/duplication findings: **57% missed, 12% under-called (10 of 14 as NIT), 31% caught.** `review-code-patterns` lists "DRY/duplication" as the *first* item in its own catalog (`/Users/quantum/Documents/ComputedChaos/salesagent/.claude/agents/review-code-patterns.md:5`), and it had opened the file in 35 of the 67 DRY misses. Worst PRs for missed/under-called DRY: 1575 (13), **1547 (10)** — the exact PR the memory names.

**The #1312 case is not a harness miss.** PR #1312 was **never reviewed by the panel** (confirmed: not in the 64-PR set; `feat(idempotency): success-cache replay (#1312)` merged 2026-06-16). Its three review rounds were human. The harness cannot be charged with it — but it *is* evidence for the one real architecture gap: nothing decides which PRs get a panel.

Scripts: `.../esc/q2.py`, `.../esc/q2b.py`, `.../esc/access.py`

---

## Q1 — Escaped defects

**Structural limit first, stated plainly:** only **32 of 64** reviewed PRs merged; 28 are still open. The clone is **shallow at 2026-03-14**, excluding PR945 (merged 2026-01-14) — **31 analysable**. `origin/main` tip *is* the last reviewed merge (#1697), so the median merged PR has only ~30 subsequent main commits. The post-merge window is small; I enumerated all 185 main commits rather than sampling.

**Attribution method.** A later commit touching the same file proves nothing. I required: commit C modifies lines whose `git blame` at `C^` attributes to the reviewed PR's own landed commit M. That yielded 71 (PR, commit) pairs, only 14 fix-shaped — and inspection showed most are incidental (`uv.lock`, `.duplication-baseline`, import lines). **Commit archaeology is the wrong instrument here** — squash-merge plus a short window destroys the signal.

The instrument that works is the repo's own `(#issue) (#pr)` convention. **18 issues were filed against a reviewed PR after it merged; 11 are genuine defects.**

| issue | PR | gap | panel effort | what the panel did |
|---|---|---|---|---|
| **#1775** | 1585 | 12 d | 14 runs / 2 r | **cited `:703` as NIT and cleared it** — see below |
| #1711 | 1585 | 6 d | 14 runs / 2 r | spec-conformance opened `media_buy_delivery.py`; **0 of 14 runs ever name `time_granularity`** |
| #1800 | 1417 | 15 d | 72 runs / 3 r | all 5 sites opened, none cited |
| #1680 | 1417 | 4 d | 72 runs / 3 r | spec-conformance domain, unraised |
| #1740 | 1545 | 19 d | 8 runs / 2 r | cited `conftest.py` 8×; the 2,376-line-function structure never raised |
| #1467 | 1390 | 2 d | 3 runs / 1 r | "Pre-existing since #1390"; architecture-guards domain |
| #1773 | 1430 | 14 d | 16 runs / 2 r | mixed: 2 opened-not-cited, 3 never opened |
| #1778 | 1417 | 15 d | 72 runs / 3 r | **cited `conftest.py:2940` [SHOULD-FIX] — shipped anyway** |
| #1782 | 1417 | 15 d | 72 runs / 3 r | **cited `ledger_fitness.py:34` [SHOULD-FIX] — shipped anyway** |
| #1785 | 1399 | 43 d | 10 runs / 1 r | **cited `products.py:714` [SHOULD-FIX] — shipped anyway** |
| **#1637 (P0)** | 1417 | 0 d | 72 runs / 3 r | **out of scope — `media_buy_completion.py` not in the diff** |

Excluded as not-defects: 2 enhancements (labelled `enhancement`), 3 chores, 1 CI disk issue, 1 maintainer descope (#1683). Six of 31 merged PRs have ≥1 post-merge defect issue.

**Three distinct failure modes, and they need different fixes:**
- **7 in-scope misses** — capability gap.
- **3 flagged-and-shipped-anyway** — the review worked; the *process* didn't. Not a harness defect.
- **1 out-of-scope (the P0)** — diff-scoped review structurally cannot see it.

### The single most damning artifact

Issue #1775 (PR1585): *"A2A submitted-detection is gated on `res["success"]`, so a submitted response carrying advisory errors is never classified as submitted."*

`review-error-wire`, round 2, on that exact line:

> **Crux verified (the prior-review concern):** the A2A submitted-detection is **robust** to a non-empty advisory `errors` list. `[observed]` The detection at `adcp_a2a_server.py:703` reads the OUTER `res["success"]` (set literal `True` on no-exception at line 662), not the errors-derived inner flag.

And `review-spec-conformance` on the same site: **"Not inverse."** Both tagged NIT.

The lens read the right file, found the right line, identified the exact mechanism, and **concluded the opposite of the truth — under an `[observed]` evidence tag**. Twelve days later it was filed as a defect. This is worse than an omission: a positive clearance discharges the concern and stops anyone else looking. It is also invisible to every metric in `report-step0.md` — the cite resolves, the severity is calibrated, the could-not-verify section is present.

Scripts: `.../esc/q1.py`, `.../esc/q1b.py`, `.../esc/prfacts.py`

---

## Q3 — Which lens should have caught it

Every miss topic falls inside some lens's declared domain. **There is no capability that all eight lenses collectively lack.**

| topic | lens that owns it | n | miss+under |
|---|---|---|---|
| security/isolation | security | 40 | **80.0%** |
| architecture/layering | architecture-guards | 52 | **78.8%** |
| DRY/duplication | code-patterns | 117 | 69.2% |
| typing/API contract | code-patterns | 114 | 67.5% |
| error handling | error-wire | 110 | 67.3% |
| test proves nothing | test-integrity | 65 | 66.2% |
| spec/wire conformance | spec-conformance | 81 | 55.6% |
| naming/docs | *(none)* | 45 | 62.2% |

**Capability gap: 9 of 11 escaped defects and ~90% of the missed human findings.** The lens that owns the domain had the file open and did not raise it. Adding lenses will not fix this.

**Architecture gaps — exactly two, both real:**
1. **Diff scope.** The P0 (#1637) sits in a file PR1417 never touched. Nothing in the eight-lens design looks at code the diff doesn't reach.
2. **Panel invocation.** PR #1312 shipped the inverse of its spec with no panel at all. There is no gate deciding which PRs get reviewed.

`naming/docs` (45 findings, 62% missed) is genuinely unowned, but it is the lowest-value class.

---

## Q5 — Does more review find more?

Later rounds do cover new ground — and the ground gets steadily thinner.

Within the 13 PRs that got ≥3 rounds:

| round | panels | % sites new | BLOCKER | SHOULD-FIX | NIT | Mcost/panel | new sites a human later confirmed |
|---|---|---|---|---|---|---|---|
| 1 | 13 | 100.0% | **75** | 674 | 784 | 7.2 | 6.58% |
| 2 | 13 | 89.2% | 16 | 374 | 539 | 4.0 | 13.11% |
| 3 | 13 | 87.4% | 11 | 461 | 568 | 5.1 | 7.85% |
| 4 | 7 | 83.9% | 4 | 180 | 297 | 4.2 | 5.96% |
| 5 | 3 | 79.5% | 6 | 87 | 173 | 5.8 | 13.16% |
| 6 | 1 | 92.9% | 0 | 24 | 54 | 8.7 | 6.52% |
| 7 | 1 | 98.1% | 29 | 176 | 83 | **22.1** | **0.00%** |

Corpus-wide, BLOCKER **density** decays ~5×: round 1 = 3.3% of cites, round 3 = 0.9%, round 4 = 0.6%.

**Verdict: diminishing, not zero.** The independent-human confirmation rate of newly-cited sites stays flat at 6–13% through round 5 — so late rounds are not drifting into noise, they are finding real-but-smaller things. What collapses is severity. Round 7 cost 22.1M units (3× a round-1 panel), emitted 29 BLOCKERs, and **not one** of its 260 new sites was independently confirmed. Rounds 1–3 are the value; 4–5 are marginal; 6–7 are not supported by any evidence I can construct.

Script: `.../esc/q5.py`

---

## What I could not determine

- **Whether the 52% miss rate generalises.** It is measured against one reviewer on 28 PRs, 26 of which are still open. KonstantinMirin is an unusually thorough reviewer; a less demanding baseline would show a lower miss rate. The *direction* is solid; the level is specific to this comparator.
- **The true escaped-defect rate.** 31 analysable merged PRs, median ~30 commits of post-merge history, and `main`'s tip is the last reviewed merge. Recently-merged PRs have had almost no time to fail. **11 defects is a floor, not an estimate.**
- **Blame-based commit attribution is near-useless here** (14 fix-shaped pairs, nearly all incidental) because of squash-merge plus the short window. The issue-reference convention carried the analysis; a repo without that convention would leave this question unanswerable.
- **How many misses are the *same* finding at a different line.** My identifier-overlap probe returned median 0.67 — but the panel and the human read the same diff, so shared identifiers mean "read the same code," not "raised the same issue." The probe cannot separate them; I report site-level miss rates only, and the file-level figure (91.6% same file) as the counterweight.
- **False positives of *judgement*.** Q4 proves cited lines exist. The #1775 case proves that is not the same as being right, and I have no way to grade correctness at scale.
- **Whether the 3 "flagged and shipped anyway" cases were consciously accepted.** They may be deliberate risk decisions, not process failures.

**Repo state:** read-only throughout. 29 `refs/pull/*/head` fetched (never the glob), `.git` 121,096 → 130,648 KB. No checkout, no push, working tree byte-identical to session start. All scripts in `/private/tmp/claude-501/-Users-quantum-Documents-GitHub-agenticads-sim-plan/e2367c8b-0c8b-43ae-a5d4-98ce3fbcecea/scratchpad/esc/`.