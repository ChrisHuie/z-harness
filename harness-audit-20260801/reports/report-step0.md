I have the answer. Consolidating.

## Verdict: **SHRINK** — cut the nine §5 doctrine files (1.90% of corpus). Do not pay to guarantee delivery. The charter's own value is bounded, not established.

All figures below come from scripts I wrote and ran in `/private/tmp/claude-501/-Users-quantum-Documents-GitHub-agenticads-sim-plan/e2367c8b-0c8b-43ae-a5d4-98ce3fbcecea/scratchpad/dtest4/`. My extraction reproduces every canonical number in `report-method.md` exactly before I graded anything: **759** lens runs, **545 / 71.8%** charter, **383 / 50.5%** tooling, **303 / 39.9%** all-nine, **220 / 29.0%** zero, **3,597 / 52.7%** file-level, 120 sessions (`extract_runs.py`).

---

## What I built that prior passes did not

| ground truth | volume |
|---|---|
| lens runs mapped to a PR | 702 / 759, 64 PRs |
| runs with a locally resolvable head SHA | 685 / 759 (90.2%) |
| `path:line` citations parsed | 11,932 (10,729 gradeable) |
| human inline review comments (bots excluded) | 1,730 on 32 PRs |
| shipped artifacts in `.claude/reports/` | 81 |
| cites gradeable on "was it acted on" | 6,815 across 454 runs |

---

## Six quality axes. All null or reversed.

**1. False positives — NULL, and my first measurement was wrong.**

A loose detector reproduced a headline gap (READ 2.82%, NOT 5.51%). It does not survive. Dropping PR1417 alone collapses it to +1.02pp, CI [-0.94, +3.02] (`loo.py`). Worse, the detector over-counts: bare basenames, cross-repo AdCP spec cites, and *proposed* new files all score as phantoms.

The defensible test — cite resolves to a file the PR touched, existing at the reviewed SHA, line beyond EOF at **every** commit on the PR (`fp_final.py`):

```
charter READ   13 / 2,125 = 0.61%
charter NOT     0 /   464 = 0.00%
FULL step-0     0 /   508      ZERO step-0   0 / 97
```

Then I checked the 13 survivors by hand and **at least 4 are my error, not the agent's.** Four lenses cite `tests/bdd/steps/domain/uc006_sync_creatives.py:7058–7089` on PR1806; the file has 7,016 lines at the SHA I resolved. `git grep -n "def then_buyer_can_poll_task" 307c4d20b` returns **line 7077 exactly** — a commit on the same work that `gh pr view 1806 --json commits` does not list. Seven more are PR1547, whose head `7e3c9e174` fails `git cat-file -e` locally. **29 of 64 PR head commits are missing from this clone.** The FP rate is ≤0.5% in both arms and the difference is unmeasurable at the precision the repo supports.

**2. Acted-on — NULL once the confound is removed.**

Pooled: READ 32.3%, NOT 28.9%. The driver is runway, not quality — charter-READ runs have a median of **2** remaining PR commits, charter-NOT runs **0** (`confound.py`). Stratified by runway: 32.0% vs 29.6% (−2.4pp). Stratified by runway × effort: 32.6% vs 30.7% (−1.9pp), with per-stratum deltas swinging +20.9 to −15.8pp (`domain2.py`). Within-session −1.1pp against between-session −11.0pp — the gap lives entirely at session level.

Against a chance baseline (5 random lines per file, same diff): real cites hit a later-changed site **58.1%** vs **23.5%** for random lines — lift **2.47×**. By arm: READ 2.44×, NOT **2.64×**. Relative to what was actually churning, the non-compliant runs are marginally *more* precise.

**3. Human corroboration — NULL.**

Raw recall of human-flagged sites looks monotone (35.5% / 32.3% / 27.4% by panel compliance) but is pure volume confound: high-compliance panels emit 94 cites against 66 and cover PRs with 92 human sites against 34. Normalised to **hits per 100 cites emitted: 22.28 / 21.46 / 21.39** — flat (`recall2.py`). Within-PR paired across panels of differing compliance: low compliance recalls less in **4 of 8** PRs, p=0.64.

**4. Severity honesty — the panel is well calibrated, and compliance does not explain it.**

```
BLOCKER    43.0% acted on (74/172)
SHOULD-FIX 37.3%
NIT        29.3%
untagged   27.3%
```

A clean monotone ordering — the severity labels carry real information. But it holds in both arms (BLOCKER: READ 41.7%, NOT 56.2%). BLOCKER survival into the shipped artifact: READ 46% (21/46), NOT 38% (6/16).

**5. The mechanism — NULL, and I nearly reported a bogus signal.**

§5's doctrine claims to change *how* the agent reasons. Every signature I can measure is at parity (`mechanism.py`):

| | charter READ | charter NOT | sec5=9 | sec5=0 | FULL | ZERO |
|---|---|---|---|---|---|---|
| "what I could not verify" section | 97.6% | 96.7% | 98.3% | 96.4% | 99.3% | 98.2% |
| first-person evidence claim | 84.4% | 83.2% | 85.1% | 81.8% | 86.4% | 87.3% |
| `[observed]`/`[verified]` tag | 96.7% | 96.3% | 97.4% | 95.9% | 98.0% | 96.4% |
| hedges per 10k chars | 0.2 | 0.2 | 0.2 | 0.2 | 0.2 | 0.2 |
| median verify-shaped Bash calls | 29 | 26 | 26 | **38** | 28 | 29 |

Runs that read `feedback_verify_before_asserting.md` ran a median of **25** verification commands; runs that skipped it ran **32**.

One apparent exception — "ready claims" at 2.0% among readers vs 7.2% among non-readers — is my detector catching quoted tool output. Sampling the matches (`ready.py`): 20 of 22 are `mypy … "Success: no issues found in N source files"`. Not a ready claim. Signal deleted.

**6. Survival into the shipped artifact — the only consistently-signed effect, and it is weak.**

Whether the orchestrator carried a lens finding into the artifact in `.claude/reports/` (`artifacts.py`): READ 40.4%, NOT 31.1%. Paired on (PR, lens): 35.4% vs 31.5%, NOT-lower in **41/70** cells, mean −4.7pp, sign p=0.094. Within-session −7.0pp against between-session −6.9pp — the two agree, so this is not purely orchestrator-quality confound. But p=0.15 within session, and **the nine §5 files reverse it**: sec5=0 survives at 47.6% against sec5=9 at 32.6%.

---

## The non-compliant arm was not compensated

The obvious escape hatch — "skippers got the content restated in their prompt" — is false (`substitute.py`). Charter-NOT dispatches got **less** instruction, not more: median prompt 3,223 B vs 3,577 B, naming Step-0 in **26.2%** of cases vs **89.7%**, naming memory files in 13.6% vs 40.9%. They were under-briefed and produced work I cannot distinguish from the fully compliant arm.

Meanwhile the operative discipline is already resident. Every one of the 8 `.claude/agents/review-*.md` definitions carries the could-not-verify mandate and a Step-0 block; 6 carry the severity vocabulary; 6 the `path:line` requirement; 3 the evidence/claim tagging. Those files are always in the system prompt. That is why the output signature is at 96–99% regardless of what was read.

---

## Where the signal actually is: the small per-catalog files, not the charter

The one contrast that moved (`domain.py`, `domain2.py`) is **catalog-specific** memory — the per-lens files named in the dispatch prompt, which are *not* the §5 nine:

```
acted-on, doubly standardised by runway x effort
  domain memory >=5 files : 35.7%
  domain memory <=1 file  : 23.6%     delta -12.1pp   CI [-22.1, +6.3]  P(>=0)=0.066

same treatment, charter READ vs NOT: delta -1.9pp
```

Underpowered (13 runs in the zero arm) and not significant — but it is 6× the doctrine effect and points at the cheap, specific files rather than the 39,867 B charter.

---

## The bill

Recomputed independently from per-run reads and actual call counts, charging residency for the rest of each run (`substitute.py`, breakdown script):

```
Step-0 document set: 11 files, 100,010 B (~26,318 tok); median run loads 53%
  cache-write   11.9M tok x 1.25 = 14.8M units
  residency    445.3M tok x 0.10 = 44.5M units
  TOTAL                            59.7M units = 5.20% of the 1,148.5M corpus

  review-charter.md    30.1M   2.62%   (39,867 B)
  the nine §5 files    21.8M   1.90%   (46,516 B, 47% of payload bytes)
  reviewer-tooling.md   7.8M   0.68%   (13,627 B)
```

`report-attack2.md`'s 46.0M is the same quantity on a thinner residency model. Band: **46–60M units, 4.0–5.2% of corpus.**

---

## Recommendation

**Cut the nine §5 doctrine files from the mandatory Step-0 list — 21.8M units, 1.90% of corpus, 47% of the payload bytes.** This is the strongest-supported cut: six axes null, three reversed (artifact survival 47.6% vs 32.6%, acted-on 33.2% vs 30.4%, verify-shaped Bash 38 vs 26 median), and their claimed mechanism is measurably delivered by the always-present agent definitions instead. This is not merely absence of evidence — the mechanism is identified and it is not these files.

**Keep `review-charter.md` and `reviewer-tooling.md`, but do not pay to guarantee them.** Plan item #2 (relocate into the 8 system prompts, +16.8M to +35.2M) rests entirely on non-compliance being a correctness defect. I tested that against ground truth on six axes and could not find it. Spending +35M to reliably deliver a payload whose measured effect is bounded below ~5pp on every metric I could ground is the worst move on the table. The charter's own value is **not established and not excluded** — the survival signal is consistently signed at −5 to −7pp but p≈0.09–0.15.

**Keep the per-catalog memory reads.** The only candidate signal is there, and it is the cheap part.

## What I could not determine

- **Power.** MDE at 80%/α=.05 with a design effect of 2 for session clustering: **5.45pp** on acted-on, **1.43pp** on strict FP, **4.82pp** on human-site hits. I rule out large effects, not small ones.
- **The false-positive axis is under-determined by this repo.** 29 of 64 PR heads are absent locally and `gh` omits relevant commits (307c4d20b on PR1806). A full `git fetch origin '+refs/pull/*/head:refs/pull/*'` would make this test decisive; without it, every "hallucinated line" is confounded with "commit I don't have."
- **`reviewer-tooling.md`'s masking-gotcha recipes are ungradeable here.** They exist to prevent a class of false-green. A prevented false-green leaves no trace in a transcript. I cannot price them either way, which is why I did not recommend cutting them.
- **Observational, not experimental.** Compliance clusters hard by session (ICC 0.64 per `report-method.md`); I controlled with within-session pairing, runway stratification, effort stratification, and (PR, lens) cells, but 4 of 8 lenses cannot be paired at (PR, lens, round) because each lens runs once per round.
- Scripts: `extract_runs.py`, `parse_findings.py`, `resolve_sha.py`, `fp_check2.py`, `actedon.py`, `analyze.py`, `paired.py`, `probe.py`, `confound.py`, `shacheck.py`, `loo.py`, `human.py`, `recall2.py`, `mechanism.py`, `ready.py`, `fp_strict.py`, `fp_final.py`, `substitute.py`, `domain.py`, `domain2.py`, `artifacts.py` — all in the `dtest4/` directory above.