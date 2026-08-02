All measurements are in. Here is the report.

---

# Why the panel misses: it is not a blind spot, it is a stopping rule

**First, the headline number needs a correction, and it moves in the panel's favour.** Then: the misses are overwhelmingly a *depth* failure, the panel has a written catalog entry for almost every class it misses, and the single strongest predictor of a miss is not what kind of defect it is but **how many findings the panel has already raised in that file**.

Scripts and data: `/private/tmp/claude-501/-Users-quantum-Documents-GitHub-agenticads-sim-plan/e2367c8b-0c8b-43ae-a5d4-98ce3fbcecea/scratchpad/esc/` (`all864.pkl` carries every row with my hand label, `seq.pkl` the ordered per-dispatch tool log, `readwin.pkl` every lens Read window). All 864 rows are KonstantinMirin only; ChrisHuie excluded as instructed.

---

## 0. The denominator was wrong, and it inflates the miss rate by ~15 points

The brief asked me to be rigorous about opportunity. The prior denominator required only that *a panel round ran on that PR before the comment*. That is too weak: these PRs run 2–7 rounds over weeks, and the human reviews the newest push. A finding on code pushed after the last panel round is not a miss.

I resolved this with `git blame -L n,n --porcelain <original_commit_id> -- <path>` — the commit that actually wrote the cited line — and required that a panel run timestamp fall between that commit and the human's comment.

| | n | MISS | UNDER | CAUGHT |
|---|---:|---:|---:|---:|
| **OPPORTUNITY — a panel round ran after the line was written** | **372** | **37.1%** | 20.4% | 42.5% |
| NO OPPORTUNITY — line written after the last panel round | 285 | 69.1% | 10.2% | 20.7% |
| unresolvable (commit not in this clone) | 207 | 54.6% | 16.9% | 28.5% |

**Corrected miss rate: 37.1%, bootstrap 95% CI over 24 PRs [25.2%, 47.9%].** The 285 excluded rows are spread across 24 PRs (top: 1575=46, 1547=40, 1544=34), not concentrated at one rebase, so this is not a rebase-timestamp artifact. The 207 unresolvable rows sit at 54.6%, so the true corpus figure is bounded between ~37% and ~52% depending how they split.

Two notes on the earlier field choices: `commit_id` tracks the PR head and is useless here; `original_commit_id` is the *review* head, not the blame commit — I tried both and both are wrong instruments. Only blame answers the question.

**Every qualitative conclusion below survives the correction, and most strengthen.** I give both denominators throughout.

---

## 1. The taxonomy — hand-graded, all 864 findings read

I read all 864 comment bodies and assigned one primary class each. This is one grader with no second rater; the soft boundaries are DUP↔ARCH (is re-implementing a helper duplication or a layering breach?) and VAC↔PAR (is a one-transport test a weak oracle or a parity gap?). I resolved those toward the finding's own stated emphasis.

### Ranked blind spots — the 448 misses

| # | class | n | % of misses | miss rate (all) | miss rate (opportunity-confirmed) |
|---|---|---:|---:|---:|---:|
| 1 | **DUP** — duplicated logic; *extract-then-skip-a-sibling* | **208** | 46.4% | 56.7% | 42.0% |
| 2 | **VAC** — test proves nothing (mutation-survivable, tautological, vacuous-by-construction) | **88** | 19.6% | 51.2% | 38.5% |
| 3 | **TYP** — type erosion (`Any`, bare `dict`/`list`, positional same-typed tuples) | 43 | 9.6% | 55.8% | 26.9% |
| 4 | **PAR** — cross-transport / cross-surface parity gap | 22 | 4.9% | 73.3% | 60.0% |
| 5 | **NAM** — docstring/comment contradicts code; convention divergence | 22 | 4.9% | 37.3% | 43.8% |
| 6 | **ARCH** — layering / SSOT / bypass of the owning seam | 15 | 3.3% | 45.5% | 16.7% |
| 7 | **SPEC** — spec-citation and version grounding | 13 | 2.9% | 37.1% | 31.8% |
| 8 | **ERR** — error handling / envelope construction | 12 | 2.7% | 50.0% | 33.3% |
| 9 | **LOGIC** — plain functional defect (wrong condition, missing case) | 10 | 2.2% | 28.6% | 9.1% |
| 10 | **DEAD** — dead / unreachable / no-op code | 9 | 2.0% | 42.9% | 30.0% |
| 11 | **SEC** — tenant isolation, SSRF, credential/secret exposure | 5 | 1.1% | 50.0% | — |
| 12 | **PERF** | 1 | 0.2% | — | — |

**The classes the brief named as candidates are almost absent.** Concurrency: zero findings are about a race, lock, or ordering hazard — the only concurrency-adjacent items are *duplication of* a `threading.Barrier` test scaffold (`test_delivery_poll_behavioral.py:880/931/1096`). Resource lifecycle: one (`adcp_a2a_server.py:657`, a task registered before auth leaves an unpollable orphan). Async data-flow: two. Performance: one. **The human is not finding a class of defect the panel is blind to; he is finding the same classes the panel finds, in far greater numbers.**

**The miss rate is nearly flat across classes.** DUP 42.0%, NAM 43.8%, VAC 38.5%, ERR 33.3%, SPEC 31.8%, DEAD 30.0%, TYP 26.9% on the corrected denominator — the bootstrap CIs overlap heavily (DUP [45.1, 66.2] vs VAC [41.0, 61.3] on the full set). Only PAR is distinctly worse and LOGIC/ARCH distinctly better. **There is no categorical blind spot. Whether a defect is caught barely depends on what kind of defect it is.**

### Two structural facts about the misses

**342 of 448 (76.3%) are in test files.** The panel's miss rate is 62.9% in `tests/` vs 30.8% in `src/` — a 2.0x split — and it is not an attention gap: the panel's own path-qualified cites on these 28 PRs are 1,304 in `tests/` vs 1,258 in `src/`. It looks at tests as much as source and performs half as well there.

**23 of the 448 are the same finding re-raised at a new URL** (425 distinct sites). Those are re-raises because the earlier one was never fixed — evidence of persistence, not double-counting.

### The finding that reframes the whole thing

Every dominant miss class already has a numbered entry in the panel's own catalog at `/Users/quantum/.claude/projects/-Users-quantum-Documents-ComputedChaos-salesagent/memory/reference_review_patterns.md`:

- **P13** "Find existing helper before adding inline copy" and **P25** "Helpers introduced but bypassed at call sites — audit ALL call sites in the same PR" → the DUP class, 46% of misses, and P25 names the *extract-then-skip-a-sibling* shape exactly.
- **P7** "Narrow Any / list[Any]" → the TYP class.
- **P2** "No vacuous/tautological asserts" and **P14** "mutation-test mentally: change line N → does any test go red?" → the VAC class.
- **P5 / P26 / P36** cross-transport symmetry → the PAR class.
- **P21** "Docstring claims match code", **P37** uniform naming → the NAM class.

`review-code-patterns.md:5` lists "DRY/duplication" as the **first** item in its own description. The panel is not missing these for want of knowing to look. **This is an application failure, not a knowledge failure — which is why adding lenses or catalog entries will not fix it.**

---

## 2. Depth vs coverage vs architecture — depth dominates, and more so after the correction

Owner assignment follows each lens's declared scope: DUP/TYP/DEAD/NAM/PERF → `code-patterns`; VAC → `bdd` under `tests/bdd/`, else `test-integrity`; PAR → `error-wire` **and** `test-integrity` (both claim it); SPEC → `spec-conformance`; ERR → `error-wire`; ARCH → `architecture-guards`; SEC → `security`; LOGIC → no lens.

| | all 448 misses | opportunity-confirmed (138) |
|---|---:|---:|
| **(a) DEPTH — the owning lens had opened the file** | 61.6% | **73.9%** |
| **(a′) DEPTH-ADJ — some lens opened it, not the owner** | 23.4% | 21.7% |
| (b) COVERAGE — no lens touched the file | 10.3% | 2.9% |
| (b′) COVERAGE-WEAK — file seen in output, never opened | 2.5% | 0% |
| **(c) ARCHITECTURE — no lens owns the class** | 2.2% | 1.4% |

**Confirmed: (a)+(a′) = 85.0% on the full set, 95.6% on the corrected denominator.** Coverage is a rounding error once opportunity is enforced. The only genuine architecture gap is the LOGIC class — 10 findings (2.2%) that are plain functional defects ("this condition is wrong", "this branch never fires", "the escape set is wrong in both directions" at `isolated_batch.py:22`). No lens's charter says "is this code correct?"; all eight are scoped to a pattern catalog. That is real but small, and the panel catches 91% of them anyway when it has the chance.

---

## 3. What the depth failure looks like — the panel had the defect on screen

This is the strongest evidence I produced.

**66.7% of in-window misses were in a Read window from which the same run drew a different finding.** Concretely: 96 of the 144 misses where a lens Read a window covering the cited line — that same dispatch cited a *different* line inside that *same* window and did not raise this one. It had the defect in the tool result it was actively reading, and moved on.

**Median distance from a missed line to the panel's own nearest cite in that same file: 61 lines.** Of the 375 misses in files the panel cited at all, 250 (67% of those, 56% of all 448) sit within 100 lines of a line the panel itself flagged in the same round.

Fifteen cases, quoting the lens's own tool calls against the human's finding. Every one is (a)-class — the owning lens read a window containing the exact line.

**Stopping at the first finding in a window it fully read:**

- **`src/core/tools/creatives/_sync.py:117`** (PR1697, DUP). `code-patterns` Read `offset=88 limit=60` → lines 88–147. It cited **:102 and :103**. Fourteen lines below its own cite, inside the same tool result, the human found: *"Same coalesce idiom as the other eight log sites. Route through the total `webhook_url_for_log()` helper."*
- **`tests/integration/test_a2a_error_responses.py:337`** (PR1534, VAC). `test-integrity` Read lines 250–349, cited **:280**, missed :337 in the same window: *"`greater than or equal to 0` also appears in a raw `str(ValidationError)`, so this no longer distinguishes the sanitized envelope from the leak it replaced."*
- **`tests/integration/test_delivery_webhook_behavioral.py:60`** (PR1605, VAC). `test-integrity` Read `offset=60 limit=45`. It cited :96 and :98 — and missed **line 60, the first line of its own read window**: *"Presence-only: asserts the header keys exist but not the `sha256=` prefix or unix-seconds format."*
- **`tests/harness/media_buy_dual.py:157`** (PR1544, PAR). `error-wire` Read lines 140–269, cited **:99** — outside its own read window — and missed :157 inside it: *"this a2a arm calls `update_media_buy_raw` directly, bypassing `_handle_update_media_buy_skill` … every wired `[a2a]` revision variant never observes the skill-handler layer."*
- **`tests/integration/test_creative_sync_behavioral.py:477`** (PR1650, PAR). `error-wire` Read 474–513, cited **:370**, missed :477: *"the only real-wire grade for the changed `errors[].code`/`.recovery` contract, and it crosses REST + MCP only."* The human re-raised this at :477 four separate times.
- **`.github/workflows/ipr-agreement.yml:179`** (PR1669, DUP). `code-patterns` Read 50–199 — a deliberate, narrow window — cited :16/:27/:54/:60/:66, and missed the two duplicated `python3 -c 'json.load(...)'` one-liners at :179 and :184 inside it.

**Full-file read, four cites, moved on:**

- **`tests/unit/test_claude_bdd_audit_scripts.py:194`** (PR1665, VAC). `test-integrity` Read 1–2000 (the whole file). Cited :1, :20, :21, :112, :282 — five findings — then stopped. The human found 12 more in that file, including :194: *"passing example first, failing last, so a last-wins revert leaves `graduate == set()` unchanged and green."*
- **`src/core/adcp_version.py:3`** (PR1546, NAM). `code-patterns` Read 1–2000, cited exactly one line, **:71**, and missed the module docstring at **line 3** teaching the inverse of the constant nine lines below it.
- **`tests/unit/test_a2a_error_routing.py:309`** (PR1547, DUP). `code-patterns` Read 1–2000 then narrowed to 173–205 and 224–277 — it cited :173 and :224, the two windows it narrowed to — and missed :309, the second copy of the same block.
- **`tests/unit/test_architecture_bdd_no_dormant_scenario_xfail.py:62`** (PR1673, VAC) and **`tests/bdd/steps/domain/uc003_update_media_buy.py:2409`** (PR1544, VAC): the owning lens Read a window covering the line and cited **nothing at all** in that file.

**The reach failure, separately:**

- **`tests/integration/test_delivery_poll_behavioral.py`** (PR1575, ~3,900 lines) is the cleanest exhibit. Eleven lens Read windows, all inside lines 1–749. The panel's deepest cite is :718. Everything it caught (:359, :401, :409) is inside that band. **Every one of the 12 human findings past line 749 — 811, 819, 861, 958, 971, 1062, 3770, 3823, 3866, 3873, 3895 — is a MISS.**
- **`tests/bdd/steps/domain/uc019_query_media_buys.py`** (PR1698, ~3,000 lines): three Read windows, max upper bound 1,729. Twenty-nine human findings, twenty-two of them past line 2,500. Every one missed or under-called.
- Counter-case that proves reading is necessary but not sufficient: **`uc019_query_media_buys.py` in PR1544** — 8 of the human's 11 findings *were* inside a Read window, and all 11 are misses.

---

## 4. The positional signature — real, strong, and mechanical

Every test the brief proposed shows a signal.

**Saturation within a file is the strongest effect.** Ordering each file's human findings by line:

| finding's rank within its (PR, file) | n | miss rate (all) | n | miss rate (opportunity-confirmed) |
|---|---:|---:|---:|---:|
| 1st | 243 | 45.7% | | |
| 2nd | 143 | 43.4% | 274 (1st–3rd) | **33.6%** |
| 3rd | 105 | 40.0% | | |
| 4th–7th | 212 | 51.4% | 72 | 30.6% |
| **8th+** | **161** | **77.0%** | **26** | **92.3%** |

And by density: files where the human raised 16+ findings are missed **76.7%** of the time vs 39.8% for 4–7. **The panel raises three-to-five findings per file and stops.** That is the stopping rule.

**Read windows.** Of 13,935 Read calls by lens agents, **76.5% use no offset at all** and only **2.79% have an upper bound past line 2000**. The share of findings whose line ever fell inside a Read window collapses with depth: 41.5% for lines <500 → 25.4% for 1000–2000 → **4.3% for lines 3000+**.

| | all 864 | corrected (372) |
|---|---:|---:|
| line inside a Read window | 43.5% miss | **37.7%** |
| file Read, line **outside** every window | **76.5% miss** | **66.7%** |

Same file, different region: a 1.8x effect. This measure is not circular — Read tool inputs and report cites are independent signals, and the panel demonstrably cites lines it never Read (in PR1547 `exceptions.py` its deepest Read window ends at 1094 but it cites line 1661, reached via `grep -n` and `git show | sed -n`).

**Position within the dispatch.** Taking the median run that opened the file: Q1 32.1% miss → Q2 37.9% → Q3 54.1% → **Q4 63.8%**. Monotone. On the earliest-run measure the last quartile is 89.5% (n=19).

**Absolute line number:** <200 → 44.6%; 200–600 → 51.7%; 600–1500 → 57.3%; **1500–2500 → 75.0%**; 2500+ → 69.5%.

**File size:** flat at 36–43% up to 1,500 lines, then **74.4% for 1,500–3,000-line files**.

**Repeated attention helps but saturates:** files opened by 1 lens run → 77.8% miss; 4–6 runs → 54.3%; **11+ runs → 35.4%.** Ten runs does not close the gap.

**One metric I built and then discarded:** "is the missed line beyond the panel's deepest cite in that file" looked powerful (75.7% vs 42.0%) but is circular — 79% of those rows are >12 lines beyond the deepest cite and are therefore MISS by construction of the ±12 matcher. Reported here so it is not re-derived.

---

## 5. Yes — the lenses miss the same sites, together

| lenses that had the missed file explicitly open | all 448 | corrected (138) |
|---|---:|---:|
| ≥1 | 87.3% | **97%** |
| ≥2 | 79.7% | **91%** |
| ≥4 | 52.5% | 65% |
| ≥6 | 24.1% | 25% |
| 8 (all) | 2.2% | — |

Per lens, over the 448 misses: `test-integrity` had the file open for 70% of them, `code-patterns` 57%, `architecture-guards` 55%, `bdd` 50%, `error-wire` 50%, `spec-conformance` 42%, `security` 34%.

**A quarter of missed sites were in files six or more independent reviewers had open.** That settles it: this is systemic, not lens quality. It is consistent with `report-lens.md`'s finding that pairwise site overlap never exceeds 5% Jaccard — eight lenses each raise 3–5 things per file and the union still leaves most of the file unexamined.

Corroborating: at sites the panel *did* catch, 103 of 276 had exactly one lens raising them, and at under-called sites 115 of 140 had exactly one. The panel converges rarely.

---

## 6. Severity — the misses are not trivia, but they skew that way

Using the reply thread as the oracle (`mkostromin-sigma` posts dispositions, `pmezzich` author responses; 55% of findings drew a reply):

| | all 864 | miss rate | corrected 372 | miss rate |
|---|---:|---:|---:|---:|
| **ACTED ON** (reply says addressed/fixed) | 370 | 48.1% | 138 | **23.9%** |
| no reply | 390 | 50.5% | | |
| replied, ambiguous | 91 | 72.5% | | |
| declined / deferred | 13 | 53.8% | | |

**178 of the 448 misses (39.7%) were subsequently confirmed fixed by the author or maintainer** — 33 of them on the corrected denominator. Only 13 findings in the entire corpus were declined, so "the human was over-reaching" does not explain the gap.

But on the corrected denominator the acted-on miss rate (23.9%) is *below* the overall rate (37.1%), which reverses what the uncorrected numbers show. **The honest reading: the panel does skew toward missing the less consequential findings — but it still missed 33 things a maintainer then went and fixed, and 140 of the 178 acted-on misses are in test files.** The human's own severity tags are too sparse to use (only 45 of 864 carry `Required`/`Should fix`/`Nice to have`); 38 misses carry an explicit `↩ still open` re-raise marker, meaning the human had to raise them more than once.

---

## What I could not determine

- **The corpus-wide miss rate.** 37.1% [25.2, 47.9] is defensible only on the 372 rows where blame resolves and opportunity is provable. 207 rows (24%) reference commits absent from this clone; they sit at 54.6%, so the corpus figure is somewhere in 37–52%. Fetching the missing PR refs would close this.
- **Inter-rater reliability on the taxonomy.** One grader, no second rater. I built a regex classifier to check myself and it agreed with my hand labels only 64% of the time — which is why I read all 864 rather than trusting it. Treat class boundaries as ±1 category, especially DUP↔ARCH and VAC↔PAR.
- **Whether the stopping rule is a budget, a prompt effect, or a model effect.** I can show the panel stops after 3–5 findings per file and that the 8th+ finding is missed 92% of the time. I cannot show *why* — nothing in the charter or agent definitions sets a per-file cap, and I did not test whether an explicit "enumerate every instance" instruction changes it. That is the experiment this diagnosis points at.
- **Whether the Read-window effect is causal.** It is correlational and confounded with file size. The clean natural experiment would be re-running one lens on PR1575 with a mandated full-file read of `test_delivery_poll_behavioral.py` and comparing.
- **Why `tests/` is 2x worse than `src/`.** I established the split and ruled out the obvious explanation (it is not that the panel looks at tests less). Test files here are much larger and much more repetitive, so this may be entirely the size/saturation effect rather than a separate phenomenon — I could not separate them.
- **`git blame` and squash-merge.** For the 28 PRs still open, blame on the PR branch is reliable. For merged PRs it would not be, but only 2 of the 28 PRs in this comparison are merged, so the correction is not materially affected.

**Repo state:** read-only throughout. No fetch, no checkout, no push, no writes outside the scratchpad.