I have everything. Writing up.

---

# Orchestrator audit — where the findings die, and what 506.8M units buys

All scripts are in `/private/tmp/claude-501/-Users-quantum-Documents-GitHub-agenticads-sim-plan/e2367c8b-0c8b-43ae-a5d4-98ce3fbcecea/scratchpad/orch/`. Read-only throughout; nothing in `/Users/quantum/Documents/ComputedChaos/salesagent` was modified.

**Reproduction of the canonical anchors first:** `scan_main.py` yields `9,791 calls / 506.8M units` for the main thread and `759` lens runs — exact matches to `report-method.md`. My finding-parse gives 87 BLOCKERs corpus-wide (arch-guards 14, spec-conformance 17); the brief's "16" for arch-guards is within heuristic drift of my 14, and spec-conformance matches exactly.

---

## 1. Where findings die — the deliverable

### 1a. The instrument, and a methodology correction I had to make

My first pass matched anchors with a naive `file.py:NNN` regex and reported ~55% of BLOCKERs "dropped." Hand-checking `full-review-pr1720-20260726.md` showed **5 of 6 of those flags were false**: the artifact cites bare-line continuations (`` `:1096` ``, `` `:1106` ``) and ranges, which a naive matcher reads as absences. The fix already exists in the repo — `disposition_ledger.py:111-153` (`site_tokens(expand_ranges=True, resolve_bare=True)`), written for exactly this precision problem. **All numbers below use the harness's own matcher.**

### 1b. Survival of the finding's canonical §3 header anchor

Denominator: findings whose §3 header carries a `.py` anchor, raised in sessions that produced a report-shaped artifact (`trace5.py` + header-anchor pass).

| severity | n | anchor reaches the artifact | appears only in the orchestrator's chat/notes | appears nowhere it wrote |
|---|---|---|---|---|
| **BLOCKER** | 53 | **60.4%** | 17.0% | 22.6% |
| SHOULD-FIX | 811 | 64.1% | 12.6% | 23.3% |
| NIT | 939 | 55.5% | 7.3% | 37.2% |

Site-level, counting every `path:line` inside a severity-tagged finding block: **BLOCKER sites 40.7% kept (200 of 337 dropped), SHOULD-FIX 47.1%, NIT 34.9%.** A finding routinely arrives with three sites and ships with one — the §4b.0 "one ledger row per site" rule, unenforced.

Per lens, BLOCKER+SHOULD-FIX kept: code-patterns 75.4%, admin-ui 75.0%, security 71.6%, test-integrity 63.6%, error-wire 60.8%, bdd 60.7%, spec-conformance 57.2%, **architecture-guards 55.3%**. Architecture-guards and spec-conformance — the two lenses the brief flagged — are the two worst-served.

### 1c. Loss classified

**(i) No artifact at all — 30 of 113 panel sessions.** 451 findings including 6 BLOCKERs were raised in sessions that never wrote a report-shaped `.md` and never posted a review body. The panel ran; nothing was consolidated into a durable surface.

**(ii) Never mentioned — 21 named BLOCKERs.** Full list at `trace5.py` output. The 12 flagged `GONE` (nowhere in anything the orchestrator wrote):

- `review-architecture-guards` · `guard-matcher-incompleteness — verify_feature_error_codes.py:49,52 matcher misses live forms IN the gated scope` (PR #1417)
- `review-spec-conformance` · `media_buy_status never emitted — media_buy_create.py:3978, base.py:330` (PR #1417)
- `review-spec-conformance` · `spec-conformance-inversion — dual-emit vs pinned beta.3, _base.py:398-401` (PR #1417)
- `review-bdd` · `xfail→fail-via-new-elif — tests/bdd/conftest.py:2603` (PR #1417)
- `review-error-wire` · `then_dual_emit_media_buy_status claims a wire invariant its oracle cannot fail — uc002_create_media_buy.py:1592` (PR #1417)
- `review-test-integrity` · `TestBrandPersistence asserts a shape the code does not produce — test_creative_sync_processing.py:844` (PR #1482)
- `review-spec-conformance` · `spec-must-format-id-canonicalization — _processing.py:54` (PR #1482)
- `review-bdd` · `dormant-scenario — _UC019_WIRED tags with no binding steps, conftest.py:2608`
- `review-architecture-guards` · `guard-matcher-completeness — test_architecture_image_supply_chain.py:17-36`
- `review-architecture-guards` · `ratchet-not-enforced — test_architecture_no_raw_select.py:381` (PR #1718)
- `review-architecture-guards` · `orphaned-subsystem/merge-regression — media_buy_create.py:1709`
- `review-spec-conformance` · `contradicts-wire-placement-must — media_buy_list.py:248`

**(iii) Severity erased at the public boundary.** Session `b5382f8e` (PR #1417) is the extreme case: **64 lens dispatches across 8 rounds**, 8 BLOCKERs raised. The posted comment (recovered from the `Write` of `pr1417_comment_v9.md`, 6,856 B) contains **zero occurrences of `BLOCKER`, `SHOULD-FIX`, or `NIT`** and one each of `optional` and `non-blocking` — the exact §1.8 vocabulary `disposition_ledger.py:78` exists to catch. The orchestrator's own closing message describes shipping "**Three optional nits**." The session edited only `src/routes/api_v1.py` and `tests/bdd/conftest.py` in the repo, so the other six BLOCKERs were neither fixed nor handed over. This is not the norm — 13 of 15 on-disk comment drafts do carry the ladder — but it is the failure mode at its full extent.

**(iv) Severity drift.** On anchor-exact survivors: **SHOULD-FIX→BLOCKER 66, NIT→BLOCKER 34** versus BLOCKER→SHOULD-FIX 4, SHOULD-FIX→NIT 84. Inflation outnumbers deflation ~1.2:1. §4b.1 bans promotion without quoting the raising agent's basis. *Caveat: this rests on nearest-preceding-severity-tag proximity in heterogeneous artifacts and is the weakest number in this report.*

**(v) Deferred without a ledger row.** 18 of 81 artifacts carry `optional / non-blocking / non-gating / nice-to-have` (34 lines). Only **5 of 81** carry the §4b.4 provenance table.

### 1d. The mechanism: the gate cannot see the findings

`disposition_ledger.py:74` — `FINDING_TAG = re.compile(r"\[(BLOCKER|SHOULD-FIX|NIT)\b")`. It counts **bracketed** severity tags. But `/full-review` Step 7 (`.claude/commands/full-review.md:81`) prescribes the cluster format, and artifacts in that format write `### Cluster A (BLOCKER)`. Reproduced:

```
$ python3 .claude/rules/private/detectors/disposition_ledger.py \
      .claude/reports/full-review-pr1720-20260726.md
findings (severity-tagged): 0
dispositions resolved:      25
Actions ledger present:     True
Contract met: every finding resolves to an action; no banned disposition; no dropped site.
EXIT=0
```

That artifact's own line 9 reads `## Summary: 1 BLOCKER / 10 SHOULD-FIX / 8 NIT / 10 FOLLOW-UP`.

- **8 artifacts declare 161 findings in their Summary line while the detector counts zero.** Three of them (`full-review-pr1719-20260725.md`, `full-review-pr1720-20260726.md`, `full-review-1669-20260722_1654.md` — 55 declared findings) exit **0, "Contract met"**, because `_is_clean` (line 204) treats zero findings as vacuously clean.
- Corpus-wide the detector counts **632** severity-tagged findings across 81 artifacts against **2,750** raised by the lenses. `deficit = n_findings - n_dispositions` is therefore near-zero by construction: **only 1 of 81 artifacts shows any disposition deficit.**

The prior "we proved by execution it passes a shipped `[BLOCKER]` clean" test used a bracketed tag. On the format the corpus actually uses, the gate is blind. **This is the single highest-value fix in this report and it is a one-line regex change** — extend `FINDING_TAG` to `[\[(]` and add `^#{2,4}.*\b(BLOCKER|SHOULD-FIX|NIT)\b` as a header alternative.

---

## 2. What the 506.8M buys

`cost.py`. Panel sessions carry 455.3M of 506.8M (89.8%).

**By phase** (P0 = before first lens dispatch; P1 = dispatch→last lens return; P2 = after):

| phase | units | share | calls |
|---|---|---|---|
| P0 pre-dispatch (Dimensions A/B/G) | 73.5M | 16.1% | 1,899 |
| P1 fan-out + wait | 107.1M | 23.5% | 1,392 |
| **P2 consolidation** | **274.7M** | **60.3%** | 5,317 |

**By activity, whole main thread:** Bash **276.2M (54.5%)**, text-only drafting 66.3M (13.1%), Edit 48.8M (9.6%), Write 36.0M (7.1%), Read 35.3M (7.0%), **Agent dispatch 20.9M (4.1%)**.

**P2 alone:** Bash 145.8M (53.1%, 3,015 calls), drafting 42.9M (15.6%), Edit 35.1M (12.8% — applying FIX-NOW), Write 24.8M (9.0%), Read 16.7M (6.1%).

**What it reads.** Of 24.8 MB ingested: Bash results 14.9 MB (60.1%), Read 7.5 MB (30.5%), **all lens returns 1.6 MB (6.3%)**. The orchestrator's consolidation input is 6% of its reading.

**Is it re-derivation?** P2's 3,394 Bash commands: **git 40.0% + gh 17.7% = 58% repo/GitHub state re-query**, grep 14.9%, sed/head/cat 9.3%, detectors 8.5%, tests 6.5%. Zero are byte-identical to an earlier command in the same session, but **26.2% re-query an endpoint family already queried before the lenses returned**. Dispatch prompts total 2.88 MB across all 759 runs (median 3,436 B) — negligible.

**Answer:** the biggest line item is consolidation-phase shell work, and the majority of it is re-establishing repo/GitHub state rather than processing lens output.

---

## 3. Verify or trust — Charter §4b.1-4

`verify.py`. Of 2,774 distinct files the lenses cited, the orchestrator re-opened **982 (35.4%)** after the last lens returned. Median per-session re-open rate **0.39**. Four sessions re-opened nothing; only **6 of 113** re-opened >80%.

**Does re-verification cost more than dispatch?** No. P2 (274.7M) is 46% of the 595.4M the 8 lenses consume — but it is **2.6× the entire fan-out phase** and **13× the Agent-dispatch calls themselves (20.9M)**. Consolidation is not a cheap post-step; it is the largest single thing the orchestrator does.

It also does not delegate the work: of 92 non-lens dispatches (68 `general-purpose`, 20 `Explore`), only **17 fire after the last lens returned**. P2 runs in the main thread at an 86,743-token floor per call.

**Against Chris's CORE rule** — subagent output gets the same scrutiny as the model's — the measured answer is *partial trust*: about a third of cited files re-opened, while 58% of the phase's shell budget goes to state the lenses were not responsible for. §4b.4's "ledger before prose, provenance visible to the referent first" is satisfied in **5 of 81** artifacts (6.2%).

---

## 4. `/full-review` — read in full, and measured

`.claude/commands/full-review.md`, 16,796 B, 92 lines. It is not dead prose: its body appears in **80 of 159 sessions** — 49 times as an expanded prompt, 35 via a `Read` tool_result. (No `<command-name>` record exists for it anywhere; only `/compact`, 8 times. So it arrives, but not through the slash-command path.) 76 of 120 panel sessions have it; **44 ran a panel without it.**

Where it names an exact command string, the lift is large (n=76 with / n=44 without):

| step | with | without |
|---|---|---|
| `./run_all_tests.sh ci` | 77.6% | 13.6% |
| sibling worktree `../salesagent-wt-prN` | 57.9% | 4.5% |
| `ssot_docstring_duplication.py` | 38.2% | 0.0% |
| `review_completeness.py --since` | 50.0% | 13.6% |
| `disposition_ledger.py` (T1 gate) | 72.4% | 27.3% |
| writes `.claude/reports/full-review-*.md` | 76.3% | 6.8% |

**Universally skipped even when the command is loaded — these are unenforced gates:**

| prescription | compliance |
|---|---|
| **Step 4** — run **all five** whole-tree detectors centrally | **3.9%** (3 of 76) |
| **Step 0** — the orchestrator's own `reviewer-tooling.md` read | **6.6%** |
| **Tooling-PR mode** — the cardinal-invariant adversarial probe | **7.9%** |
| **Step 0** — all 7 named memory files | **9.2%** |
| **Step 4** — `recovery_audit.py --scope` (the #1720 vacuous-CLEAN trap) | **11.8%** |
| **Step 0** — the orchestrator's own `review-charter.md` read | **13.2%** |
| **Step 4** — `compound_guard_operands.py` | 17.1% |
| **Step 3** — verdict from `test-results/<ts>/*.json`, never stdout | 19.7% |

The Step-0 numbers are the sharpest irony available: the orchestrator dispatches 8 lenses that each load the 39,867 B charter — including §4b and §4c, which only the orchestrator can act on — and reads it itself in **13% of runs**. §4b is read by ~545 agents that structurally cannot execute it and by the one agent that must, one time in eight.

---

## 5. What else the dispatch prompt controls

`prompt_props.py`, joined 1:1 lens-run → its own dispatch prompt (n=759 runs, 2,299 findings in artifact-producing sessions). Same shape as the known 91.3%/0.6% path result:

**The unnoticed lever is the word "Disposition."** Present in **43.6%** of dispatch prompts.

- P(lens emits a §3 `Disposition:` line | prompt says it) = **91.8%**, vs **31.3%** when silent — **2.9×**.
- Findings from those runs reach the artifact **83.5%** vs **54.5%**.
- Absent-from-artifact rate: **1.7%** vs **14.6%** — an **8.6× reduction**.
- BLOCKERs specifically: 89.3% vs 58.8%.

The mechanism is clean: a finding carrying a resolved disposition is exactly what §4b.5 and `disposition_ledger.py` can track. The orchestrator suppresses more than half of its own gate's input by omitting one word.

Two more with the same shape:

- **"cite via `git show HEAD:`"** (21.6% of prompts): survival 88.0% vs 60.6%; absent 1.7% vs 10.7%.
- **passing detector output into the prompt** (25.7%): 83.9% vs 63.3%.

And one **saturated** lever worth knowing: asking for `path:line` anchors (51.9% of prompts) has **no effect** — 72.4% vs 68.5% — because lenses anchor 96.9% of findings regardless. Emphasis spent there is wasted; the same emphasis on "Disposition" is not.

*Confound: richer prompts co-vary across all these features and cluster by session template. I did not disentangle them. The Disposition→emission link (91.8% vs 31.3%) is a direct behavioral measurement and is not subject to that confound; the survival deltas are.*

---

## 6. Is a mechanical ledger-builder warranted? — Yes

**First, a correction to the brief's premise.** It is not 3 of 81 artifacts with agent attribution. **55 of 81** carry ≥3 lines pairing a severity with an agent name; **5 of 81** carry the full §4b.4 table (`{finding, agent, agent-severity, mitigation, disposition}`). Attribution is common; the *structured ledger* is what is rare.

**The lens output already contains five of the six columns.** Across 2,750 findings: severity **100%**, `path:line` anchor **96.9%**, `Confidence:` **88.6%**, explicit §3 `Disposition:` **55.4%** (FIX-NOW 535, FOLD-IN 493, FOLLOW-UP 391, WON'T-FIX 104). Only the *resolved* state requires judgment. Asking a model to remember what it can instead be handed is the whole defect.

**Prototype** — `orch/ledger_builder.py`, no model in the loop:

```
$ python3 ledger_builder.py 26966a37-80fe-470c-ad21-e05bf2c35581 \
      .claude/reports/full-review-pr1720-20260726.md
# mechanical ledger — session 26966a37  (7 lens runs, 46 rows after dedup, 0.03s)
| ID | Site | Finding | Raised by (agent-severity) | Lens disposition | Disposition |
| L20 | `adcp_a2a_server.py:657` | P23-write-half — owner recording at create has ZERO coverage | test-integrity · BLOCKER | FIX-NOW | **UNRESOLVED** |
...
## Unaccounted for in full-review-pr1720-20260726.md: 21 of 46
```

0.03 s against a 274.7M-unit consolidation phase. It emits the §4b.4 table the charter mandates and 94% of artifacts lack, pre-filled with the raising agent, the agent's severity, and the lens's own recommended disposition — leaving the orchestrator with one column to fill.

**Two honest caveats.** My prototype's site matcher is naive and produced ~5 false "unaccounted" flags out of 6 on the PR1720 check; the correct matcher is `disposition_ledger.site_tokens(expand_ranges=True, resolve_bare=True)` and should be imported, not rewritten. And a ledger-builder catches *drops*, not *un-unification* — `disposition_ledger.py:26` says so explicitly, and Step 5.2 semantic-SSOT synthesis remains a judgment pass.

**Recommended order, cheapest first:**

1. **Fix `FINDING_TAG`** in `disposition_ledger.py:74` to also match cluster headers. Restores the gate on 8 known-blind artifacts and unblocks the deficit check corpus-wide. One line.
2. **Add "Disposition" to the dispatch-prompt template.** 8.6× reduction in the absent-from-artifact rate, zero token cost.
3. **Ship the ledger-builder** as a T1 step feeding `disposition_ledger.py --notes` with the structured ledger rather than freeform notes — which is precisely the input the detector's docstring (`:38-41`) says gives it the best signal-to-noise.

A second *model* consolidation pass is not warranted. The orchestrator already re-derives at 274.7M units and still loses 40% of BLOCKER anchors; a second pass of the same kind buys another 274.7M for the same class of error. The lossy step is mechanical bookkeeping, and it should be done mechanically.

---

## What I could not measure

- **Drop vs. resolution.** An absent anchor can mean "dropped" or "fixed in-session, correctly absent." I adjudicated one session by hand (`b5382f8e` edited only 2 repo files, so its 6 missing BLOCKERs were genuinely not resolved). The other 20 named BLOCKERs are not individually adjudicated — treat the list as a worklist, which is the same standing the harness gives its own detectors.
- **Finding extraction is heuristic** (a severity tag on a header-shaped line). It yields 87 BLOCKERs where the brief cites figures implying ~90; per-lens counts differ by ≤2.
- **Severity drift** rests on nearest-preceding-tag proximity across heterogeneous artifact formats. It is directionally reported and should not be quoted as a precise count.
- **P2 attribution is by timestamp** — "everything after the last lens returned." Sessions that continue into unrelated implementation work inflate P2. The 12.8% Edit share inside P2 is legitimate FIX-NOW application per Step 7, not waste.
- **The 30 no-artifact sessions**: I could not determine whether their reviews were delivered verbally and accepted, or abandoned. Scratchpad drafts were recovered from `Write` tool_use inputs; the files themselves are gone from disk.
- **No causal claim** on the prompt-property deltas — session-level template clustering is the obvious confound and I did not control for it.