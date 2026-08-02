I've read FINDINGS.md in full plus 14 reports end-to-end (sysprompt, cluster28, ret47, orch, method, subout, close, step0, consol, 2rater, claims, detector-exec, lens, adversarial), partial sweep9/general, and grepped all 32. Here is what is still wrong.

---

# The audit's biggest defect is not a wrong number. It is four missing recommendations.

`FINDINGS.md` contains **zero occurrences** of `FINDING_TAG`, `Disposition`, `ledger-builder`, or `round-scoped`. Verified by grep. That means the settled document drops:

1. **`disposition_ledger.py:74` `FINDING_TAG` is blind to the format the corpus actually uses.** `report-orch.md:60-77`: the regex requires a bracketed `[BLOCKER]`, but `/full-review` Step 7 prescribes cluster headers and artifacts write `### Cluster A (BLOCKER)`. Reproduced by execution: `full-review-pr1720-20260726.md` → `findings (severity-tagged): 0 … EXIT=0 … Contract met`, while its own line 9 reads `## Summary: 1 BLOCKER / 10 SHOULD-FIX / 8 NIT`. **8 artifacts declare 161 findings the detector counts as zero; 3 exit 0 "Contract met" vacuously** because `_is_clean` (`:204`) treats zero findings as clean. Corpus-wide the detector sees 632 of 2,750 raised findings, so `deficit` is near-zero *by construction* — only 1 of 81 artifacts shows any deficit. Independently confirmed by `report-detector-exec.md:168-181` (N2, unbracketed severity → rc=0 on three findings with no ledger). Its author calls it "the single highest-value fix in this report and it is a one-line regex change." **It is absent from §4, §5, and §6.**

   What §4 *does* report (`FINDINGS.md:121-126`) is the weaker, narrower mechanism — the document-wide count collapse — on a single artifact. The bigger, better-evidenced defect got dropped in consolidation. **The audit reproduced the exact failure mode it spent §3 documenting.**

2. **The "Disposition" dispatch-prompt lever** (`report-orch.md:151-160`). Present in 43.6% of prompts. P(lens emits a `Disposition:` line) 91.8% vs 31.3% — **2.9x**. Absent-from-artifact rate 1.7% vs 14.6% — **8.6x reduction**. Zero token cost, one word. The report explicitly notes the 91.8%/31.3% link is a direct behavioral measurement *not* subject to the richer-prompt confound it flags for the survival deltas. Nothing in §5.

3. **The mechanical ledger-builder** (`report-orch.md:179-191`, prototyped, 46 rows in 0.03s), which `report-consol.md:78-88` endorses *and strengthens* by naming the load-bearing constraint the prototype satisfies by accident: it must re-read the 859 subagent JSONLs from disk at write time, because those survive compaction and eviction. Nothing in §5.

4. **Round-scoped consolidation** (`report-consol.md:88`) — "cheaper than all of it," and the direct exploitation of §3's own decay curve: consolidate at Δ<25k where BLOCKER loss is 0.0%, instead of at 910k where `b5382f8e` lost 100%. This addresses the 55% displacement bucket that §3 identifies as the dominant loss mechanism, and **§5 offers nothing that touches it.**

Worse, `FINDINGS.md:104` states "**This is why `disposition_ledger.py` cannot match even when its logic is fixed**" — which reads as an argument against fixing it. `report-consol.md:90` says the opposite half out loud: "fixing `FINDING_TAG` remains correct and cheap … It restores the gate on 8 artifacts; it does not restore the join." FINDINGS kept the discouraging clause and discarded the recommendation.

**Changes recommendations. This is the largest single defect in the audit.**

---

# 1. Claims still standing on evidence the JSONL cannot see

Wave 9 proved the transcript strips injected `<system-reminder>` content (11,308 B on wire → 1,878 B in JSONL, zero occurrences of `MEMORY.md`). Here is the enumeration you asked for.

**(a) `FINDINGS.md:249-250` commits the identical error, inside the section reporting wave 9.** It states: "zero anchors were silently dropped, unified away, or **adjudicated away** … that hypothesis is **falsified**." But `report-ret47.md:114` — the source — says: "**Thinking is 100% stripped** in all three arms — 8, 10, and 2 blocks, **0 characters total**. Every adjudication I attribute is visible-text adjudication. If the orchestrator reasoned about dropping the 26 suppressed sites and did not say so, that reasoning is unrecoverable, and **'adjudicated away = 0' is a floor, not a ceiling.**" FINDINGS upgraded a floor to a falsification, using a channel the audit's own §0 trap 3 says is blank. *Changes a claim: "falsified" must become "not observed in visible text; the thinking channel is empty."*

**(b) `FINDINGS.md:199` "Every delivery channel was falsified."** Of the ten channels in `report-close.md:11-22`, one (`MEMORY.md auto-injected`) is now known false, and a second — "charter inlined in the system prompt: 0 of 95 charter-less runs quote any of 155 charter-unique phrases" — has essentially **no power**: the stated baseline among confirmed charter *readers* is **1.0%**, so the expected count under the alternative is ~1 quote in 95 runs. Observing 0 discriminates nothing, and the JSONL cannot see system prompts by construction. The other eight (dispatch-prompt text, `settings.json`, agent definitions, `CLAUDE.md`, alphabetical/mtime, cross-link chaining, version cliff, filesystem scan) rest on files-on-disk or on *positive* transcript evidence and survive. *Changes a claim: "every channel" → "eight of ten; one falsified, one untested."*

**(c) `FINDINGS.md:207-212` overstates what wave 9 proved, in three ways.**
- **Scope.** `report-sysprompt.md:78`: "**No capture inside salesagent.**" The mechanism was captured live in `agenticads-sim-plan`; salesagent's byte counts were read off disk. FINDINGS states it as measured fact about salesagent.
- **Version.** `report-sysprompt.md:79`: captures are 2.1.220 (2026-07-25); the lens corpus spans **11 versions across June–July**. "Auto-memory injection was live in every one of those versions is **inferred, not measured**." FINDINGS drops this and says "**unconditional**" — a word the report earned only w.r.t. tools, agent definition, and CLAUDE.md, not w.r.t. version.
- **What "copied" explains.** The nine sit at MEMORY.md lines 4,5,6,8,9,**37,37**,53,73 out of 118. Two share a line, and the sequence skips lines 10–36 and 38–52. So the *names* are copied — which does discharge the zero-Read puzzle and the 99.96% filename accuracy — but *selecting nine of 118 entries and no others* is still convergent selection. `FINDINGS.md:207-208`'s "copied, not reconstructed … the prior answer was backwards" overcorrects a claim that was half right. *Changes a claim, not a number.*

**(d) `FINDINGS.md:41` "every component MEASURED, none estimated" is contradicted by `FINDINGS.md:274`**, which concedes the compaction summarization call "is absent from the transcript **entirely**." At least one class of billed call produces no JSONL record. 1,376.1M is a **lower bound**, not a measurement. And `FINDINGS.md:54-55` — "blind replication … 0.17% apart. The measurement was never the unstable part" — does not repair this: the replicating agent used the same instrument on the same files, so it replicates the blind spot rather than testing for it. A blind replication establishes transcription fidelity, not validity. *Changes a claim's strength.*

**(e) Not affected, and worth saying:** the cost model itself. `usage` counters are billing totals returned by the API, so stripped *content* does not remove *tokens* from the ledger. The MEMORY.md bytes were always inside the 1,376.1M. `FINDINGS.md:221`'s "**NEW COST LINE**" is an attribution, not an addition — but the phrasing invites double-counting, and the "2.2% of corpus" framing is the only thing that makes it unambiguous.

---

# 2. Internal contradictions FINDINGS.md carries in both directions

**(a) §6b says the never-detected band is solved; §7 says it has no mechanism.** `FINDINGS.md:226-233` ("NOT a distinct failure class … position … a proximity-matched null reproduces the band exactly") versus `FINDINGS.md:271` ("Sized, **no mechanism, no defensible proposal**. The one failure no state fix touches"). §7 is `report-humanmethod.md:146,185` verbatim; §6b is `report-cluster28.md`, which was written to overturn it. Both are in the settled document.

**(b) §6b says the nine-files question is answered; §7 says it is unreachable.** `FINDINGS.md:207-215` versus `FINDINGS.md:268-270` ("**Unreachable from transcripts**"). `report-sysprompt.md:72` explicitly instructs: "`FINDINGS.md:208-210` … is answered and **should move out of §7**." It was not moved.

Both §7 items are under a heading that reads "**do not claim these are settled**." *Cosmetic in isolation; together they show §7 was never re-read after wave 9 — which is why the §5 recommendation errors below survived.*

**(c) `FINDINGS.md:241-243` contradicts the report it summarizes.** It asserts: "Saturation, depth falloff, and the never-detected band are **one mechanism**, and the per-finding enumeration mandate **closes all three**." `report-cluster28.md:74`: "in all six slices ALL is over-represented and SOME under-represented … But **it never moves mass out of NONE. Which is exactly why the enumeration fix leaves this band untouched.**" And `:149`: "§4b.0's enumeration rule is *finding-scoped* … it converts SOME into ALL and **cannot touch NONE**. The never-detected band needs the same rule *file-scoped*." The evidence FINDINGS cites for "closes all three" (`:238-240`) is the ab-capped/ab-uncapped pair on a **2,953-line file with 52 mechanically enumerable sites** — a different corpus from the band, which is defined over human comments across 28 PRs. The report's own arm C, the intervention designed to test this, is a **pre-registered prediction that has not run**. *Changes a recommendation: §6b currently retires an open problem on the strength of an experiment on a different corpus and a prediction from an unexecuted arm.*

**(d) The lead-named tensions, adjudicated:**
- **738/756/759** — settled correctly. `report-method.md:26-28`: four independent methods agree on 759 with a perfect 859↔859 join and zero orphans; 738/756 "do not reproduce under any method." **Solid, no action.**
- **72/73/79/89%** — settled correctly and with a named mechanism (mention-vs-content). 78.8% is the `"review-charter.md"`-anywhere detector; 89% is a biased 301-run subsample whose charter *and* tooling rates both exceed corpus truth. Note `report-adversarial.md:61` reached ~79% by a *different* route ("allowing for cat/relative/inlined"), and `report-method.md:58-60` measured those exact channels: inlined **0**, via `cat` **1**. **Solid, no action.**
- **178.7M vs 193–229M vs 179.7M** — `FINDINGS.md:286-288` is right, and for the right reason. `report-subout.md:161` calls final-call output "unrecoverable in principle" because it never re-enters context — true of the *reconstruction*, but the billing counter is present, and max-`output_tokens`-per-`requestId` recovers it. Reconstruction (178.7M) and billing (179.7M) agreeing to 0.6% is a genuine cross-validation. **Solid.** Minor unnoted residue: `report-subout.md:26` puts main-thread reasoning at 63.5%, `FINDINGS.md:37` says 62.7%; nothing depends on it.
- **28.6% vs 36.1%** — the caveat is present (`:232-233`) but the headline (`:226`) and §7 (`:271`) both keep using 28.6%, against `report-cluster28.md:215`'s explicit instruction: "My numbers should **replace, not be averaged with**, the earlier ones." Across 16 cluster definitions the band runs **16.0%–55.1%**; the original 133-cluster rule is not recoverable from any surviving artifact. *Changes a number: the band should be quoted as a range with the primary at 36.1%.*

**(e) Two corpus denominators, silently mixed.** `report-step0.md:113`, `report-corpus-autopsy.md:9`, `report-adversarial.md:7`, `report-attack2.md:7`, and `report-lens.md:31` all compute against **1,148.5M**. `FINDINGS.md:47` settles on **1,376.1M** (the correction adds subagent output 3.3M→35.9M and splits main cache-write to 2.0x). Every "% of corpus" imported from those five reports is therefore **19.8% too high**:

| FINDINGS.md | as quoted | correct denominator |
|---|---|---|
| `:193` nine §5 files | 1.90% | **1.58%** |
| `:187` `--index` ceiling | 0.285% | **0.238%** |
| `:188` `ci_failure.py` | 0.054% | **0.045%** |
| `:191` PR #1417 | 9.0% | **7.5%** |
| `:222` MEMORY.md | 2.2% | 2.2% (already correct) |

This is not cosmetic, because §6 and §6b are read side by side: under a consistent denominator **MEMORY.md (30.8M) costs 1.4x the nine §5 files (21.8M) that §6 recommends cutting**, and the doc cuts the smaller item while merely noting the larger. *Changes numbers and the priority ordering of §6.*

**(f) `FINDINGS.md:27-28` says the cache TTL split is "universal, exceptionless."** `report-general.md` records that the 13 `fork` subagent threads in hermes-plan and norbert-skills "are also **the only subagents in the corpus that write `ephemeral_1h` cache**." salesagent has zero forks so no salesagent number moves, but "exceptionless" is falsified by the audit's own cross-project pass. *Changes a scope word in a §0 trap presented as universal.*

---

# 3. Load-bearing numbers with exactly one measurement and no replication

Ranked by how much rides on them.

1. **The emission experiment (27% / 23% / 100%), `FINDINGS.md:149-164`.** n=1 per arm. The entire §5 headline. **The ground truth and the scorer are not archived**: `experiments/ab/` holds only `subject.py` (the 2,953-line file) and `measure_arm.py`, which computes Read coverage, report length, `[SEVERITY]` counts and distinct line-refs — **it does not compute recall**. There is no `truth.json` for the 52 sites. Contrast: the retention experiment's ground truth *was* archived (`experiments/ret/truth.json`), and when wave 9 finally examined it, **roughly half the entries turned out to be PASS/cleared sites** and the experiment's headline number was wrong. Nobody applied that scrutiny to the 52. Two further concerns: `measure_arm.py:39` counts findings with `re.findall(r"\[(BLOCKER|SHOULD-FIX|NIT)\b")` — **the same bracket-only pattern the audit proved defective in `disposition_ledger.py`** — so arms A and B (5 and 8 findings) may be undercounted if they used cluster-header or bold-dash severity. And `subject.py` contains 59 identical `TenantFactory(` / `from tests.factories` / `Env(` constructs in 2,953 lines; a "mechanically enumerated" 52-site ground truth in that file is almost certainly a repeated-construct (DUP) enumeration, on which "list every site, one per line" wins nearly by definition. `report-cluster28.md:202` says exactly this: "C is discounted well below the §5 experiment's 100% **because that ground truth was mechanically enumerable** and this one needs judgment." FINDINGS carries the 100% with no such qualifier and then generalizes it in §6b.

2. **The context-decay curve, `FINDINGS.md:86-95`.** One agent (`report-consol.md:23-34`), observational, never replicated. Its BLOCKER cells run to **n=4** and `report-consol.md:95` says so; the `<25k` cell that anchors "77.0% kept" is **n=12**. The SHOULD-FIX/NIT curves carry the weight and have the same shape, which is the real support — but §3's headline quotes the BLOCKER row. `report-general.md` names the fix: randomise consolidation timing within salesagent. Not run.

3. **`FINDINGS.md:106` severity inflation 3.7:1.** One agent, one method (`report-close.md:92-116`). Note it *replaced* an earlier 1.2:1 from `report-orch.md:54`, whose author flagged it as "the weakest number in this report." The replacement is better (per-finding blocks on the harness's own matcher, marginal-preserving permutation null at p<0.0001) — but `report-close.md:116` states the null is **2.23:1, not 1:1**, so a bare "inflation outnumbers deflation" is partly a marginals artifact. FINDINGS quotes 3.7:1 without the null. *Changes how the number should be quoted.*

4. **`FINDINGS.md:64` claim accuracy 94.5% / 0 FALSE (n=55).** One grader. `report-claims.md:158` states the frame limitation FINDINGS omits: "55 of 363 units, and the frame is **single-line-extractable findings only**. A multi-paragraph finding whose severity and cite sit on different lines never entered the frame. The reports' longest prose findings are **systematically under-sampled**." Also unreported in §2: `report-claims.md:91` measured **18.2% cite drift** (10 of 55 cites land off the code they describe while the substance holds) — invisible to the phantom-line test, and by the same author's argument the same mechanism that puts you 4 lines off is what put §2's one real defect in the wrong file entirely.

5. **`FINDINGS.md:83` "716 lens reports."** I grepped all 32 reports: **716 appears nowhere.** The canonical denominator is 759; `report-subout.md:115` has 721 parseable-summary dispatches. 716 is unsourced — likely a transcription of 721. *Cosmetic, but it is the denominator on the "~13 sites, ~3 findings" claim that opens §3.*

6. **`FINDINGS.md:99` "758 of 759 reports arrived."** `report-consol.md:11` (meta.json `toolUseId` join) is the better instrument and supersedes `report-subout.md:75` ("89 of 120 probed; 20 as user records; **10 not located**"). FINDINGS adopts it without noting the conflict. The adoption is correct; the silence is the pattern.

---

# 4. Recommendations whose experiment does not test the recommendation

**(a) The §5 emission fix recommends the one cell the 2x2 never tested.** The arms are A={cap, no mandate}, B={no cap, no mandate}, C={no cap, mandate}. `FINDINGS.md:162-164` recommends: "move it into the lens-facing §3, **not to delete §3's cap**" — i.e. **{cap, mandate}**, the missing fourth cell. The experiment shows the cap is inert *in the low-yield regime where no instruction competes with it*. A cap binds precisely when yield is high: arm C emitted **24 findings and 155 cites**. Whether a retained cap truncates that was never measured. This is the same shape as the null edit §8 congratulates itself for catching, rotated 90 degrees: there, a two-arm design would have shipped a change that did nothing; here, a three-arm design ships a configuration that was never run.

To be fair to the design: arm B *does* disambiguate the A→C contrast, so attributing the 27%→100% jump to the mandate rather than to cap-removal is sound, and `FINDINGS.md:238-240`'s quartile decomposition is a legitimate read of it. The defect is specifically in the recommended configuration, not in the causal attribution.

**(b) The §5 retention recommendation is contradicted by §6b of the same document and was not updated.** `FINDINGS.md:166-178` recommends the combined arm (ledger + no cap + enumeration) at 53%, "**41% CHEAPER per site shipped**." `report-ret47.md:95`, which §6b endorses: "The honest table is **29% → 100% → 100%**, and it says **the ledger fix alone is sufficient for findings**; the no-cap + enumeration additions buy coverage of *evidence*, not of findings. That materially changes what to ship: **`ret-ledger` is 41% cheaper in output tokens (30,170 vs 35,003) for identical finding-anchor recall.**" Two opposite "41% cheaper" claims are in play, and §5's rests on chars-per-*site* where "site" is the 73-entry denominator §6b just discredited — roughly half of which are PASS/cleared sites the charter forbids reproducing. §6b acknowledges the rescoring at `:245-252` and then leaves §5's recommendation and its efficiency argument standing verbatim. *Changes a recommendation and a number: ship the ledger; the other two clauses are unpaid-for on findings.*

**(c) §6's Step-0 rejection is priced from files that were smaller during the corpus window.** `report-lens.md:205`, never retracted and never carried forward: "the `review-charter.md` content **in transcripts is 25,258 B / 133 lines**, while the file on disk is now **39,867 B / 154 lines** … any Step-0 cost figure derived from the *current* file size **overstates what was historically delivered**." The charter alone is overstated by **58%**. `FINDINGS.md:186`'s "100,010 B Step-0 payload," `:193`'s 21.8M for the nine files, and `report-adversarial.md:95`'s 62.4k units/dispatch all use current on-disk sizes.

The same error is in wave 9's new cost line. `FINDINGS.md:221-222` computes 7,353 tok × 41,859 dispatches = 30.8M from MEMORY.md's **terminal** size. I checked the live file: **19,633 B today**, up from the 19,355 B wave 9 measured on Aug 1 — it grew *during the audit*. The memory directory holds 169 files with mtimes spanning **March 29 → Aug 1**, of which 75 fall in June and 67 in July, i.e. the index was still being appended to throughout the corpus window. mtime is a soft proxy (a rewrite bumps an old file forward, which biases toward *overstating* growth), so I will not put a number on it — but the direction is certain: **30.8M is an upper bound computed from a terminal file size applied uniformly across a two-month window, presented with no band.** *Changes a number in the direction of the audit's most-cited new finding.*

**(d) §6's `--index` rejection measures a proxy.** `FINDINGS.md:187` rejects it on "Ceiling **0.285%** of corpus" — an accounting ceiling derived in `report-attack2.md:178` from the script's own output plus displaced `gh api` pulls. That is a cost ceiling, not the quantity at issue. The reason to reject it is `report-adversarial.md:74-83`: it discards 78–88% of *reviewer prose*, destroying the input to charter §1.7b ("verify each inherited item's premise") and §7d ("the because-Y is a hypothesis"), on the readiness gate. FINDINGS lists both, cost first. The conclusion is right; the lead argument is the proxy.

---

# 5. Orchestrator instrument errors that still contaminate standing text

Four of the five are correctly quarantined; one is not, and one is understated.

- **Mention-vs-content grep (x2)** — fully corrected and mechanised at `report-method.md:32-43`. The wrong values (79%, 95.3%, 99.5%) are reported *as traps*, which is the right disposal. **Clean.**
- **Wrong denominator unit** ("27k floor" = Step-0 document volume, not per-call prefix) — corrected at `report-method.md:49`. **Clean.**
- **Content-block splitting** — corrected, promoted to §0 trap 1, and independently reproduced across 12 projects. **Clean.**
- **Too-loose scorer** (retention) — corrected in `report-ret47.md:24-32` (5 of 40 points were measurement) and reflected at `FINDINGS.md:251-252`. **Clean, but see 4(b): the correction landed in §6b and the §5 recommendation it invalidates was left in place.**
- **The one that is still live:** the bracket-only severity regex. The orchestrator's own `measure_arm.py:39` uses `r"\[(BLOCKER|SHOULD-FIX|NIT)\b"` to count findings in the A/B arms — the identical pattern that `report-detector-exec.md:168-181` and `report-orch.md:60-77` proved silently zeroes on the corpus's real formats. `FINDINGS.md:291-296` states the rule ("Use the harness's own matcher, or state that you did not") and the audit's flagship experiment does neither. It is a plausibility problem, not a demonstrated one — arms A and B returned 5 and 8, so the pattern matched *something* — but the finding counts in `FINDINGS.md:155-157` are unverified against a format-robust matcher, and nothing in the archive lets a reader check.

Also worth recording under §8's own standard: `report-orch.md:9` reconciles to `9,791 calls / 506.8M units` for the main thread against `FINDINGS.md:45`'s `9,799 / 571.0M`. The call gap (8) is trivial; the unit gap is the cache-TTL correction, correctly applied later. Not an error — but it means every downstream figure in `report-orch` (the 274.7M consolidation phase, 60.3% of main) is on the old scale and would need restating if quoted.

---

# 6. The premise no wave questioned

**That a lens finding reaching the shipped artifact is the outcome worth maximising.**

Every measurement downstream of §2 is anchored on artifact survival: §3's decay curve, §3's 22.6% slug survival, §4's gate defects, §5's retention arms, §6's ledger reasoning. Two reports name the gap and neither was followed:

- `report-subout.md:164`: "**'Quality' here is finding counts and citation density, not validated defect discovery.** I did not check whether any finding was correct, or whether it survived to the merged PR. A dispatch that reports 5 NITs scores above one that reports 1 true BLOCKER."
- `report-lens.md:199`: "'Fixed before merge' for most PRs" is unmeasurable — 23 of ~31 reviewed PRs have no local ref — so severity honesty is measured as "echo into the shipped artifact, **not as fixed before merge**."

`report-step0.md:38-42` is the one place anyone tested against an outcome oracle ("acted-on," a later commit touching the cited site), and there the result was **null** — and, against a random-line baseline, the *non-compliant* arm was marginally more precise (2.64x vs 2.44x lift). Nobody generalised that instrument. So the audit's entire loss-accounting rests on artifact presence as a stand-in for value, while the only measurement that reached past the artifact found no relationship between the harness's compliance machinery and whether anything changed in the code.

This matters concretely for §5. Both experiments optimise site count in a document. `report-ret47.md:60` records the outcome: under the enumeration mandate, findings the *filing lenses themselves retracted* — "observations dressed as findings," "I am demoting it to a non-finding" — still shipped, as F10 rows, three of them. FINDINGS reads that as "the mandate working better than anyone predicted." It is equally consistent with the mandate raising the count of things in the artifact without raising the count of things worth fixing. **Nothing in nine waves distinguishes those two readings.**

---

# 7. What is solid, so you do not re-litigate it

- **759 lens dispatches** — four independent methods, perfect 859↔859 join, zero orphans (`report-method.md:26-28`).
- **71.8% charter load rate** — path-based (544) and content-based (545) agree; every leakage channel checked and quantified; measurement band ±0.1pp with an honest ICC-corrected sampling interval of 65.1–78.5% (`report-method.md:51-63`).
- **The four measurement traps and the correct method** (`FINDINGS.md:19-25`) — reproduced across 12 projects / 187 dirs; trap 4 was only visible *because* of the cross-project contrast (`report-general.md`). Best work in the audit.
- **12 of 13 detectors carry a confirmed false-green, proved by execution.** I checked the claim's scope: `report-detector-exec.md` ran pos/neg controls on 4, `report-sweep9.md` on the remaining 9 (8 confirmed, 1 clean), including the end-to-end `bump_check` exploit that dtest3 explicitly declined to run — pin moved to 3.2.0, both children exit 2 with `STALE SNAPSHOT (hard fail)` on stderr, and the runner prints "both spec snapshots are fresh." §4's "proved by execution" is earned.
- **Cohen's kappa 0.821** on the taxonomy, with the frame verified **byte-for-byte against a fresh API pull** (864/864, 0 mismatches), the `klass` column whitelisted out before rating, and disagreements adjudicated 8/7/5 with no directional bias (`report-2rater.md:7,67`). The self-reported error direction (`:84`, "this is the error direction that inflates DUP, and it was **mine**") is the strongest signal of rater honesty in the corpus.
- **18/18 human findings substantively true**, with three minor errors, both count errors **undercounts** (`report-2rater.md:100-110`). Closes the miss-rate-inflation worry cleanly.
- **All 8 lenses earn their cost** — max 5.0% pairwise Jaccard, 60–93% unique yield even on 7+ panels, 15–24% leave-one-out loss, and the merge saving priced at 2.3% of corpus against a 1/8 coverage cut (`report-lens.md`). The admin-ui defence (19 dispatches, 1.5% of spend, 0.00% suspect cites, sole owner of two fail-open patterns) is the most thoroughly argued single conclusion in the audit.
- **The §5-compliance-is-not-charter-compliance conclusion** survives wave 9's reversal of its mechanism. Both the "reconstructed" and "copied" stories yield the same operational verdict, which is exactly the property a robust conclusion should have — and `report-sysprompt.md:73` says so.

---

## Priority for repair

1. Put `FINDING_TAG`, the Disposition prompt word, the ledger-builder, and round-scoped consolidation into §5. They are the cheapest fixes in the audit and the best-evidenced, and they are missing.
2. Fix §5's retention recommendation to ledger-only, per §6b's own rescoring.
3. Restate §5's emission recommendation as **untested at the recommended setting**, or run the `{cap, mandate}` arm.
4. Reconcile §6/§6b to one denominator; restate the nine-files cut at 1.58% and MEMORY.md at 2.2%, noting the latter is now the larger item.
5. Delete the two §7 entries that §6b settles; restate the never-detected band as 16.0–55.1% with 36.1% primary; strike "closes all three" from `:243`.
6. Add error bands to every Step-0 and MEMORY.md cost figure derived from current file sizes, and say the direction of the bias.
7. Downgrade `:250` from "falsified" to "not observed in visible text; the thinking channel is empty."

Everything above is read-only; no file in `/Users/quantum/.claude/harness-audit-20260801/` or in the salesagent repo was modified.