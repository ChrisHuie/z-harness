## Bottom line

Two of the six proposals rest on claims the audit's own later waves already reversed, and the one change that costs real money is the only one nobody priced. I measured it.

I replayed the three A/B arm transcripts still on disk (`/Users/quantum/.claude/projects/-Users-quantum-Documents-GitHub-agenticads-sim-plan/e2367c8b-.../subagents/agent-aab-*.jsonl`), deduped by `message.id`, unioned content blocks, took max `output_tokens`, dropped `<synthetic>` — FACTS.md's own method — and billed at subagent rates:

```
ab-capped    calls=14  out=15,013  cache_rd=  849,818  units=252,293   report  9,521B   5 findings /  32 cites
ab-nocap     calls=17  out=17,369  cache_rd=  725,130  units=223,996   report  8,875B   8 findings /  38 cites
ab-uncapped  calls=18  out=28,953  cache_rd=1,312,493  units=401,017   report 29,287B  24 findings / 155 cites
```

**The enumeration mandate costs 1.59x per lens dispatch** (1.93x output, 3.08x report bytes). Delta 148,724 units × 738 panel dispatches (FACTS.md) = **109.8M units ≈ 8.0% of the 1,376.1M corpus**, subagent side only. The 3.08x-larger report also lands in main context as a task-notification: +7.4k tokens × (2.0 cache-write + 28.7×0.10 re-read) × 738 ≈ **26.6M more ≈ 1.9%**.

Cutting the other way: the subject was 52 mechanically-enumerated sites in one file; the median lens report is 3 findings / 13 sites, and the mandate cannot invent sites. Honest band: **2–10% of corpus, point estimate ~8%.**

Now the ledger. #5 buys +3.0–5.9% (attack2, ±1% self-declared model error). #6a buys 1.90%. #6b buys 2.2%. **Total savings 7.1–10.0%. Fix #1 spends 2–10%.** The program is cost-neutral at best — and every saving was measured while the single cost item was not.

---

## 1. The enumeration mandate — real effect, wrong justification, untested configuration

**The retention half of its case is dead.** `/Users/quantum/.claude/harness-audit-20260801/reports/report-ret47.md:95`:

> The honest table is **29% → 100% → 100%**, and it says the ledger fix alone is sufficient for findings; the no-cap + enumeration additions buy coverage of *evidence*, not of findings.

FINDINGS.md §5 still says "the two fixes compound, neither works alone" and prints 7% → 29% → 53%. The proposal inherited the superseded framing. **#1 contributes nothing to retention once #2 ships.** Its case is lens emission alone — which is real and large (Q4 1/11 → 11/11, all arms reading 100% of the file). Sell it as that or not at all. (Minor: ret47:95's "41% cheaper (30,170 vs 35,003)" is 13.8%; 41% is FINDINGS §5's chars-per-site number pasted onto the wrong pair.)

**The configuration you intend to ship was never run.** Arms are A = cap/no-mandate (27%), B = no-cap/no-mandate (23%), C = no-cap + mandate (100%). There is no cell D = cap + mandate. I grepped the whole audit for a fourth arm or 2×2 — none. "Deleting the cap is a null edit" is established *at mandate=OFF only*, and the proposal explicitly keeps the cap, so it ships cell D.

**Cell D is self-contradictory in prose.** `review-charter.md:98`: *"Cap the body at the top ~5 findings by severity; list the rest as one-line `also:` entries. Each finding ≤6 lines."* Arm C produced 24 findings — 19 become one-line `also:` entries, and a one-line entry cannot carry "every site it covers, one per line." Worse, §3's own mandatory template (`:63-70`) is header + 6 bullets = **7 lines, already over its own ≤6-line cap**. Add N site lines and it is arithmetically impossible. Which side the model resolves to is unmeasured, and 27%-vs-100% rides on it.

**"Move §4b.0" is the wrong verb.** ret47 §1 measured the orchestrator's unification at **32/32 sites preserved across all 8 unified clusters**, driven by §4b.0's *"carries one ledger row per site (never 'N homes' prose)"*. Moving it out removes a control that is proven working. Copy it.

**The mandate as worded is incomplete.** ret47 §4: the ban on count-in-prose is scoped to the Sites block and leaks into Claim/Evidence — artifact F4 wrote *"all three dispatchers"* with one Sites row, dropping `dispatchers.py:136/168/174`. **13 such constructs survive.** Bind the rule to Claim and Evidence prose too.

**Nobody checked the outbound end.** 24 findings/lens × 8 lenses ≈ 190 findings. Charter §3:90 posts each as an inline thread, and the documented #1616 remediation behavior is that authors track the thread list. 190 threads is not a review. #1 needs a stated consolidation ratio before it goes wide.

---

## 2. Ledger-at-receipt — the best fix here, and the experiment measured the wrong path

ret-normal 164,851 units / ret-ledger 304,550 (1.85x) / ret-combined 311,226 (1.89x). The 1.85x is an **artifact of the setup**: the arms `Read` 8 reports from a file (calls 5→12). In production, `report-consol.md:11` — 671 of 759 dispatches are async and the report arrives as a `<task-notification>`, **already in context**. No Read turn needed. Real cost ≈ the ledger text (46 rows × ~200B ≈ 3.4k tokens) plus one turn. Cheap.

The flip side is that the experiment never exercised async, interleaved, out-of-order arrival — and ret47's one real mechanical defect was exactly a batching failure ("Now reports 7 and 8" → 7 ledgers for 8 reports, all 5 never-captured sites attributable 5/5 to Report 8). Async arrival makes batching *more* likely.

**Required modifications:**
- **The ledger must be a file, not context.** An in-context ledger is destroyed by compaction like everything else — 3 of 5 real summaries preserved **zero** severity labels (`report-attack2.md:60`). #2's entire job is surviving distance; leaving it in the same medium that loses things defeats it.
- **Gitignored path.** `git check-ignore` + `git ls-files` confirm `.claude/reports/` and `.claude/notes/` are **tracked** (28 files in HEAD). Charter §3:96 flags this; it is live.
- **One report per turn**, with an explicit "ledger for report N−1 complete" acknowledgment (ret47's pre-registered `ret-lockstep`).
- **Point `disposition_ledger.py --notes` at the ledger file.** That is the real join — and it is on `path:line`, which the detector actually matches.

---

## 3. Preserve the lens slug — do not ship

**The stated rationale is falsified against the code.** FINDINGS §3 says slug loss "is why `disposition_ledger.py` cannot match even when its logic is fixed." It isn't. `dropped_sites()` (`disposition_ledger.py:161`) → `site_tokens()` (`:111`) matches on `(basename, line)` only. The disposition channel (`:189`) is a document-wide count with no identifier join at all. Neither uses slugs.

**The 75% relabel rate is mandated behavior, not drift.** `/Users/quantum/Documents/ComputedChaos/salesagent/.claude/commands/full-review.md:81` requires "each finding carrying a stable ID (A1/B3/C8…), a `[dimension]` tag". The 22.6% survival is the *non-compliance* rate, inverted. #3 contradicts the orchestrator's own instruction and will not happen without also editing that line.

**Relabeling is what currently produces §1.9 compliance.** Measured: the internal `full-review-*.md` artifacts carry **296 dimension-tag occurrences across 37 of 60**; the 15 outbound `pr*comment*.md` drafts carry **0 dimension tags and 0 lens slugs**. The strip works today, and it works *because* the artifact is re-authored under local IDs.

**And the mechanized §1.9 gate is blind to the replacement.** I ran the live `INTERNAL_VOCAB` regex (`disposition_ledger.py:85-93`) against realistic forms:

```
MISS  '[SHOULD-FIX · code-patterns] CP1 helper dup'      MISS  'ARCH-SF1 guard allowlist'
MISS  '#### [BLOCKER] P34 — synthesize (…:12)'           MISS  '[BLOCKER · error-wire] EW-B2'
MISS  '[NIT · bdd] BDD1 dispatch dup'                    MISS  'raised by review-security'
MISS  'TI1 rated SHOULD-FIX on a second oracle'          HIT   'per the review harness'
```

Eight of nine miss. #3 removes a working strip and hands the job to a gate that cannot see the leak.

**It also collides with an explicit charter rule.** §3:90: *"never reuse a finding ID across rounds — a reused label silently merges two different items"*, written for #1616 where "our A2 was remediated under the label 'A3', and the real A3 vanished." Lens slugs are per-lens, per-round stable by construction (`CP1` every round). Preserving them verbatim reintroduces that exact collision.

**The version worth building:** slug survives into the internal ledger and the saved artifact; local ID at the outbound comment; one mapping row in the artifact. Extend `INTERNAL_VOCAB` with `\b(?:CP|EW|TI|ARCH|BDD|SEC|SC)-?\d+\b` and the eight `review-*` agent names **first**, and prove it fires.

---

## 4. Detector repair — correct, but it is a migration

I ran the current counters over all 60 shipped artifacts: **deficit == 0 in 39 of 40** artifacts that carry findings, with dispositions outnumbering findings 2–5x (36/97, 12/72, 5/78). The gate isn't marginally vacuous — it has multiples of slack almost everywhere. Repairing `:189` to per-finding attribution turns nearly the whole historical corpus red on first run.

Confirmed independently: the token `WARNING` appears **exactly once** in the entire detector suite — at `bump_check.py:76` itself. Repairing it makes `harness-upgrade-spec.md:72`'s prescribed drill start failing and retroactively voids reassurance quoted in 5 shipped artifacts.

The risk is the one the harness's own authors already wrote down, at `disposition_ledger.py:100-103`: *"a gate with a high false-positive rate stops being read, and then the ONE real drop slips."* `citation_freshness` already runs permanently non-zero (143 hits, ~19 real). Repairing detectors without fixing the noise floor converts silent false-greens into ignored reds.

**Modification:** run each repaired detector over the 60 historical artifacts and publish the hit-count delta; add a dated baseline with expiry for the 124 permanent-by-construction `citation_freshness` hits; land `disposition_ledger:189` as warn-only for one PR cycle before it becomes the ship gate at `full-review.md:87`. And ship #4 **before** #1 — at 5x findings the count-based deficit absorbs everything.

---

## 5. autoCompactWindow — not yet

attack2 priced 400k at 63 events/48 sessions, net +3.0–5.9%. Two gaps it declares itself:

**It never measured mid-panel firing at 400k.** From its own "what I could not measure": *"Whether a 400k cap also lands mid-panel (I measured that only at 300k)."* At 300k it found **15 of 84** lens-running sessions crossing before their last lens dispatch — 17.9%. Apply that to 400k's 48 crossing sessions and ~8–9 sessions fire compaction mid-panel. The consequence is measured and total: where compaction lands between arrival and write it is **100% BLOCKER loss, 1.2% site retention**. "400-500k is safe" rests on an unrun measurement.

**The simulation used today's growth curve, and #1 changes it.** A panel's report delivery is 8 × 12,172 B ≈ 36k tokens today. At the measured 3.08x it becomes ≈112k — **28% of a 400k window versus 9% today**. Rounds per compaction drop from ~11 to ~3.5. #1 and #5 together roughly triple the compaction rate per round of review work, and each event has a ~60% chance of preserving zero severity labels.

Two more: `autoCompactWindow` sits at `/Users/quantum/.claude/settings.json:64` — **user-global**, lowered for every project on the machine, justified by evidence FINDINGS §7 confines to salesagent. And compaction's own billing remains FINDINGS §7's open item: the saving is bounded, not measured.

**#5 attacks the one loss mechanism #2 cannot defend against.** Land #2 with a disk ledger first; a durable ledger changes the risk calculus entirely, because compaction stops being able to destroy the finding record. Then revisit.

---

## 6. The memory cuts — split them

The evidence licensing #6a — *"the 'what I could not verify' section appears in 96–99% of reports regardless of what was read"* — was measured **with MEMORY.md still auto-injected**. FINDINGS §6b proves the nine files' names and hooks reach every agent verbatim through that channel, unconditionally. #6a was validated in a world where the second channel was intact; **#6b removes it.** Shipping both at once removes both delivery paths in one step and invalidates the null result that licenses #6a.

#6b is also the one irreversible change here: `/Users/quantum/.claude/projects/-Users-quantum-Documents-ComputedChaos-salesagent/memory/` is **not a git repository** (no `.git`, `git rev-parse` fails). MEMORY.md is 118 lines / 19,633 B indexing 168 files. No undo.

---

## Rollback: nothing in the harness would notice

- Miss rate vs human: 39.6%, CI **[29.1, 49.0]** — half-width ±10 points. A change costing 10 points of recall lands *inside* the existing CI.
- Claim accuracy 94.5%, n=55 — a drop to 88% is not distinguishable.
- The detector layer certifies losses as clean by construction, and `deficit` is 0 in 39/40 artifacts today.

The only instrument sensitive enough is the mechanically-enumerated-ground-truth replay, and it measures emission on one file, not artifact survival. **Detection has to be built before the changes, not after.**

**Pre-registration, minimum:** #1 → run cell D (one dispatch), then price the mandate on a *median-density* real panel with the FACTS.md method; record baseline lens-report bytes (median 12,172 B) and artifact bytes (median 24,680 B). #2 → ledgers-written / reports-received per round, under async arrival. #3 → prove the extended `INTERNAL_VOCAB` fires before touching the join. #4 → hit-count delta across the 60 historical artifacts. #5 → mid-panel crossing rate at 400k, re-run against #1's report-size curve. #6b → back up MEMORY.md; require two panels of #6a-only data.

---

## Verdict

| Fix | Call |
|---|---|
| **#6a** cut nine §5 reads | **Ship as-is.** Six quality axes null or reversed, delivery channels falsified, effect delivered by the agent definitions. Simply correct and low-risk. Only condition: not alongside #6b. |
| **#2** ledger-at-receipt | **Ship, modified.** Best fix on the table (29%→100%, replicated across two arms). Must be a **file** in a gitignored path, one report per turn with explicit acknowledgment, and wired to `disposition_ledger.py --notes`. |
| **#4** detector repair | **Ship, modified.** Treat as a migration: historical-corpus delta published, dated baseline with expiry, `:189` warn-only for one cycle. Ship **before** #1. |
| **#1** enumeration mandate | **Ship, modified, and last.** Run cell D first — or delete both §3 caps along with adding the mandate. **Copy** §4b.0, don't move it. Bind the rule to Claim/Evidence prose. State a consolidation ratio for the outbound end. Justify on emission, never retention. |
| **#3** preserve lens slug | **Do not ship.** Rationale falsified against the code; contradicts `full-review.md:81`; removes the mechanism producing a clean outbound record (0 leaks in 15/15 drafts); §1.9 gate blind to the replacement (8/9 forms miss); collides with §3's never-reuse-an-ID rule. Build the two-namespace version instead. |
| **#5** autoCompactWindow | **Do not ship yet.** Saving bounded not measured; safety verdict rests on a measurement attack2 explicitly skipped at 400k; user-global change on salesagent-only evidence; and it attacks the exact mechanism #2 cannot defend. Revisit after #2's disk ledger lands. |
| **#6b** trim MEMORY.md | **Hold.** Removes the channel under which #6a was validated. Irreversible — memory dir is not version-controlled. |

**Order:** (0) version-control the harness — `review-charter.md`, `review-security.md`, `full-review.md`, and `disposition_ledger.py` are all **gitignored and untracked**, so there is currently no diff, revert, or bisect for any of these six changes; and decide on `.gitignore` for `.claude/reports/` + `.claude/notes/`, which charter §3:96 correctly calls the user's call. → (1) #6a → (2) #4 warn-only → (3) #2 → measure → (4) #1 → then re-evaluate #5 and #6b.