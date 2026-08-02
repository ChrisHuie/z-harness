I have everything. Scripts are in `/private/tmp/claude-501/-Users-quantum-Documents-GitHub-agenticads-sim-plan/e2367c8b-0c8b-43ae-a5d4-98ce3fbcecea/scratchpad/mech/`.

---

# How review findings die in consolidation

**Headline: they die by distance.** Not by judgment, not by delivery failure, and only sometimes by compaction. A finding's survival is governed by how much context accumulates between the moment its report lands and the moment the orchestrator writes — and that function is *identical* for BLOCKERs and NITs. The severity ladder buys a finding no protection at all.

## 0. Two corrections to the prior measurement, first

**(a) 758 of 759 lens reports were delivered.** Mechanism 4 is ruled out — but the prior work could not have seen this, because the report does not arrive as the Agent tool_result. 671 of 759 lens dispatches are **async**: the tool_result is a 779–1,082 B launch stub (`"Async agent launched successfully… The agent is working in the background"`), and the report arrives later as a separate `<task-notification>` user record (median 12,172 B). Joining subagent→main via `meta.json`'s `toolUseId`, delivery is 683 via notification + 76 synchronous = 759, minus one. The `remove` queue-ops are post-delivery cleanup, not drops.

**(b) The "30 panel sessions produced no artifact" figure is mostly a detector blind spot.** 16 of the 30 posted to GitHub; only **one** (`2bd3e619`, 3 BLOCKERs) ended right after the last report. Two causes:
- **111 of 113 `gh` posts that carry a body use `--body-file`** — only 2 use inline `--body`. The prior artifact detector required the body inline in the command string.
- The `.md` bodies *were* written with the Write tool, but `looks_like_report()` requires `[BLOCKER]`/`## Summary`/`BLOCKER`. **36 review documents in those sessions — 11,819 B, 12,801 B, 15,007 B — contain none of that vocabulary and were classified as chat.**

That second point is circular: an artifact only counted as an artifact if it kept the severity ladder. So the real finding is not "nothing was consolidated" — it is **30 of 113 sessions consolidated into a review that abandons the severity vocabulary entirely.** The §1.8 erasure the prior report found in `b5382f8e` is not an extreme case; it is 30 sessions.

## 1. The dominant mechanism: positional decay

Tokens added to the orchestrator's context between a report landing and the artifact write, vs. survival of that finding's `path:line` anchors (matcher: `disposition_ledger.site_tokens(expand_ranges=True, resolve_bare=True)`):

| Δcontext | BLOCKER kept / gone | SHOULD-FIX kept / gone | NIT kept / gone |
|---|---|---|---|
| **<25k** | **77.0% / 0.0%** (n=12) | 60.1% / 4.8% (n=314) | 43.0% / 18.6% (n=382) |
| 25–75k | 54.1% / 4.5% (n=22) | 55.4% / 10.3% (n=416) | 42.5% / 22.4% (n=465) |
| 75–150k | 31.9% / 50.0% (n=10) | 30.5% / 46.2% (n=104) | 15.6% / 56.7% (n=104) |
| 150–300k | 5.0% / 75.0% (n=4) | 6.0% / 86.4% (n=22) | 1.2% / 95.5% (n=44) |
| **300k+** | **1.5% / 90.0%** (n=10) | 1.3% / 94.4% (n=54) | 2.0% / 92.5% (n=53) |
| context *shrank* (eviction) | 9.1% / 66.7% | 7.7% / 78.8% | 8.1% / 82.1% |

Monotonic, and **the three severity rows are the same curve**. Half-life is roughly 75–100k tokens of intervening context. This holds *within* sessions (controlling for session-level confounds): of 12 sessions with ≥40 findings spanning ≥2 buckets, 9 decline monotonically — `48bde98b` 91.7%→60.9%, `c8e07030` 55.0%→30.3%, `ef1e7b25` 60.6%→46.2%→40.6%, `5c4e18f8` 70.0%→59.8%→58.3%.

A second, independent axis compounds it — absolute context at the write. At 200–350k, BLOCKER sites keep 63.6%; at **500k+, 3.8%**. In a 2-way table both effects survive: within 500k+, displacement still drives 12.3%→6.9%→0.7%; within displacement 0–3, context still drives 49.3%→47.9%→12.3%.

## 2. Attribution of the 20 lost BLOCKERs

| | share | |
|---|---|---|
| A. **False drop** — finding *is* in the artifact, anchors rewritten | 3 (15%) | measurement artifact |
| B. **Eviction / compaction** between arrival and write | 6 (30%) | real |
| C. **Displacement ≥150k tokens** | 9 (45%) | real |
| D. **Displacement 75–150k** | 2 (10%) | real |
| E. **Lost with no context pressure** | **0 (0%)** | — |

**Not one genuinely-lost BLOCKER was lost under low context pressure.** Every one had either an eviction or ≥75k tokens accumulate first.

Compaction (mechanism 2) is real but rare and confined: 6 tracked events in 5 sessions, plus **one silent 696,491-token contraction** in `b5382f8e` (rec 892→908, 891,144→194,653, no `compact_boundary` record). Where it lands between arrival and write it is total — 100% BLOCKER loss, 1.2% site retention. But it explains 30% of losses from 5 of 113 sessions. Your strong prior was directionally right and quantitatively too narrow.

**Deliberate triage (mechanism 3) is not the cause.** Triage language ("out of scope", "already covered", "not a blocker", "follow-up") appears within ±1,200 chars of dropped BLOCKERs at 53% and of *kept* BLOCKERs at 57%. It is ambient — the orchestrator adjudicates constantly — and does not discriminate. Judged drops exist but are not the mechanism.

## 3. Two secondary mechanisms the brief did not list

**Summarization at receipt.** After each report lands, the orchestrator writes a prose recap: median **11,729 B in → 1,710 B out (14.1%)**, and 11.7% of deliveries get no recap at all. Recap membership only weakly predicts survival (BLOCKER 35.3% vs 45.0% gone) — because the report is still in context and can be re-read. That is precisely why distance, not compression, is the binding constraint.

**Identifier re-indexing.** The orchestrator relabels findings into its own scheme. **75% of artifacts use local IDs (B1/S2/V3/F4), 44% use `Cluster X` headers, and only 22.6% of the 1,271 lens finding-slugs survive verbatim into any artifact.** The one stable join key that exists is discarded four times in five. This is what makes 15% of "drops" false and makes every downstream audit — including `disposition_ledger.py` — unable to match.

## 4. Eight end-to-end traces

**1. `then_dual_emit_media_buy_status` [BLOCKER] error-wire, `b5382f8e`** — delivered rec 989 (ctx 259,178), artifact rec 1476 (ctx 698,957); 21 reports between. Orchestrator saw it, rec 994: *"error-wire … raised the `media_buy_status` dual-emit issue to **BLOCKER**"*. Rec 1013: *"spec-conformance landed (3/7) — and it directly **resolves the dual-emit severity tension** I flagged"*. It ships as *"### Should-fix **1. Dual-emit oracle asserts off-wire** — `then_dual_emit_media_buy_status` (`…uc002_create_media_buy.py:1608-1609`)"* — **demoted and re-anchored** from `:1592`. Verdict: adjudicated, but no ledger row and a changed anchor.

**2. `xfail→fail-via-new-elif` [BLOCKER] bdd, `b5382f8e`** — delivered rec 152, artifact rec 1476. **45 reports and an eviction between.** Zero mentions of the slug or `conftest.py:2603` in anything the orchestrator ever said or thought. The next turn (rec 157) reads *"All 8 specialists returned with substantial, cross-validating findings"* and moves to other items. Pure displacement.

**3. `cosign-no-registry-auth` [BLOCKER] security, `ea34d4fe`** — delivered rec 186 (ctx 255,332), 5 reports between. The substance *was* engaged, rec 154: *"under `set -euo pipefail`, `cosign sign … && break` is exempt from `errexit` … That's a quiet failure … **on top of the missing auth**."* But rec 190 enumerates *"B1, S1, S2, S4, S5"* — the orchestrator's own taxonomy. The slug appears 0 times. Re-indexed out of existence.

**4. `guard-matcher-completeness` [BLOCKER] arch-guards, `ea34d4fe`** — rec 150: *"Both agents are done and converge strongly. The architecture-guards agent confirms: **full `arch_guard` suite passes (306 passed…) — no regression**, and the new guard checks *counts not per-job tiering*"*. The BLOCKER survives as a subordinate clause inside a reassuring summary, then vanishes. The lens had proved it with two reverted mutations.

**5. `stale-premise-version` [BLOCKER] spec-conformance, `c38325cd`** — the cleanest low-pressure case: ctx 139,516, **zero** intervening reports, no eviction, artifact 132 records later. Next turn, rec 110: *"The spec agent's grounded report locks the picture. It confirms … that language/device/geo are all **package-scoped `TargetingOverlay` fields that already exist**"* — it summarized a different section and dropped the BLOCKER silently. (Δ96k puts it in bucket D.)

**6. `orphaned-subsystem / merge-regression` [BLOCKER] arch-guards, `a7f9a58b`** — **a false drop.** Rec 160 thinking: *"The architecture review flagged a critical blocker … Merging risks duplicate bookings"*; rec 161: *"**architecture-guards found a BLOCKER** — and corrected two of my premises"*; it independently re-verified. `IdempotencyAttemptRepository`, `enforce_insert_ceiling`, `create_media_buy` all reach the artifact. Only the six `path:line` anchors changed. Δ68k, 2 reports between.

**7. `spec-code-conflict-1604` [BLOCKER] bdd, `670a5ade`** — delivered rec 257 (ctx 285,047). **Auto-compaction at rec 1320: 954,472 → 9,379 tokens.** Artifact written at rec 1427 with ctx 156,069. The orchestrator had engaged with it (*"There's a critical blocker with spec-code-conflict-1604: inv-015-6 already grades for INVALID_REQUEST, but #1534's boundary emits VALIDATION_ERROR"*) — before the compaction. Textbook mechanism 2.

**8. `TestBrandPersistence` [BLOCKER] test-integrity, `8a5e2635`** — the most damning. **15 mentions.** Rec 241: *"**Test-integrity specialist ✓ (3/6)** … **BLOCKER — `TestBrandPersistence` asserts a shape the code doesn't produce** (confirmed my analysis)"*; rec 245 records symmetric verification. Delivered rec 237 at ctx 251,501; artifact rec 952 at ctx **682,232** — **430k tokens later**. All 11 anchors gone. Maximum engagement, maximum distance, total loss.

## 5. Does the proposed ledger-builder fix this?

**Yes — but only under a constraint the prior proposal did not state, and it fails on two of the four problems.**

**The constraint.** You are right that a ledger built from the same context fails too. The fix survives only because the input does not live in the orchestrator's context: **859 subagent transcripts persist at `~/.claude/projects/…/<session>/subagents/agent-*.jsonl`**, independent of compaction, eviction, and distance. (The `tasks/*.output` files the notification points at are session-scoped tmp and are already gone; the JSONL is the durable source.) So the ledger-builder must **re-read from disk at write time** — not be reconstructed from what the orchestrator remembers, and not be a model instruction. `orch/ledger_builder.py` already satisfies this, via `lens_reports.pkl` built from those files. That property is load-bearing and should be stated as a requirement, not left as an accident.

**Why it works mechanically.** It attacks distance by compression. Eight lens reports ≈ 96,000 B ≈ 24k tokens — squarely in the 75–150k decay band by the time a second round lands. Forty-six ledger rows at ~200 B ≈ 9,200 B ≈ 2.3k tokens — the **<25k bucket, where BLOCKER retention is 77.0% and loss is 0.0%.** It also restores the join key that re-indexing destroys, which is what makes 15% of measured "drops" false and what blinds `disposition_ledger.py`.

**What it does not fix:**
- **The 30 ladder-less sessions.** A ledger cannot force the orchestrator to keep the severity vocabulary in the posted body. `disposition_ledger.py` should be run against the **`--body-file` contents**, which is where 111 of 113 posts actually put the review — today it is run, when run at all, against `.claude/reports/*.md`.
- **Compaction (30% of loss).** A ledger regenerated *after* a compaction recovers the rows; one generated before and left in context does not. It must be re-emitted at every artifact write, and the T1 gate must refuse to pass if the ledger is older than the last compaction boundary.

**One thing to add that is cheaper than all of it:** the decay curve says the orchestrator should write the artifact *while the reports are near*. Sessions that consolidate at Δ<25k lose 0% of BLOCKERs; `b5382f8e` ran 8 rounds to 910k tokens and lost 100%. Round-scoped consolidation — write the ledger and the artifact at the end of each round, then let the next round start from the ledger rather than the transcript — addresses the 55% displacement bucket directly, which no detector change can touch.

**On the prior report's ranked recommendations:** fixing `FINDING_TAG` (`disposition_ledger.py:74`) remains correct and cheap, but note it treats a *symptom of re-indexing* — cluster headers are the orchestrator's label scheme, not the lens's. It restores the gate on 8 artifacts; it does not restore the join.

## What I could not measure

- **Causality.** The decay curve is observational. Displacement co-varies with session structure (multi-round re-reviews accumulate both context and reports). The within-session replication (9 of 12) is the strongest control I could run; it is not a randomized one.
- **BLOCKER n is small** — 61 analyzable, 20 lost. Bucket cells run to n=4. The SHOULD-FIX (n=1,013) and NIT (n=1,144) curves carry the statistical weight and have the same shape.
- **`ctx_art`** is the context of the nearest preceding API call, not the exact prompt at the Write.
- **Attribution buckets are priority-ordered and mutually exclusive** (false-drop → eviction → displacement). A finding could belong to several; I assigned the earliest-acting cause.
- **Whether the 30 ladder-less reviews were adequate** — I established they exist, were posted, and lack the vocabulary. I did not grade their content against the findings they should have carried.
- **The one undelivered lens report** (of 759) I did not chase to root cause.