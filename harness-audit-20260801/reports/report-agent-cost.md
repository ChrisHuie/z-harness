Analysis complete. Report follows.

---

# Where the 851 dispatches go, and what can be mechanized

## Headline

**86.7% of all dispatches (738/851) are one fixed artifact: an 8-lens review panel re-run per PR, per round.** The judgment inside those agents is real and mostly not mechanizable. But each of the 738 pays a **~14,500–24,300 token fixed entry cost** re-reading the same two files before it does any thinking. That preamble — not the review work — is the dominant recoverable cost, and it is **~11x larger than the 1.32M parent-side figure you measured**, because it burns inside the subagent where the parent-side tool-traffic accounting never sees it.

---

## 1. Cluster counts (all 851)

| Cluster | n | % | Parent-side tokens (@1,551/dispatch) |
|---|---:|---:|---:|
| **LENS panel — first pass** | 532 | 62.5% | 825,132 |
| **LENS panel — re-review** | 206 | 24.2% | 319,506 |
| Investigate / map / trace | 32 | 3.8% | 49,632 |
| Adversarial / independent-verify | 21 | 2.5% | 32,571 |
| Misc review / audit | 21 | 2.5% | 32,571 |
| Uncategorized sweeps & traces | 23 | 2.7% | 35,673 |
| Spec grounding | 11 | 1.3% | 17,061 |
| Issue batch summarize (map-reduce) | 5 | 0.6% | 7,755 |
| **Total** | **851** | | **1,320,000** |

The lens panel decomposes into 8 fixed roles, each backed by a real agent definition in `/Users/quantum/Documents/ComputedChaos/salesagent/.claude/agents/`:

| Lens | first-pass | re-review | total | Step-0 fixed read (bytes) | tok/agent |
|---|---:|---:|---:|---:|---:|
| architecture-guards | 93 | 27 | 120 | 70,822 | 19,141 |
| test-integrity | 85 | 37 | 122 | 65,013 | 17,571 |
| code-patterns | 83 | 34 | 117 | 89,962 | **24,314** |
| spec-conformance | 71 | 29 | 100 | 66,569 | 17,992 |
| error-wire | 64 | 28 | 92 | 85,240 | 23,038 |
| security | 64 | 21 | 85 | 72,349 | 19,554 |
| bdd | 58 | 28 | 86 | 72,524 | 19,601 |
| admin-ui | 14 | 2 | 16 | 53,494 | 14,458 |
| | **532** | **206** | **738** | | **14.78M total** |

---

## 2. What is deterministic retrieval dressed as judgment

### 2a. The big one: 10.7M tokens re-reading two unchanging files

Every lens agent is required to read `review-charter.md` (39,867 B) and `reviewer-tooling.md` (13,627 B) before any work. That is **53,494 B ≈ 14,458 tokens × 738 dispatches = 10,670,004 tokens** spent transmitting **53 KB of text that did not change**. Redundancy factor: **738x**.

Two subsets are not merely redundant but **wrong to send at all**:

- **§4b "Consolidation calibration (orchestrator — before ANY public-facing artifact)"** and **§4c "Readiness-verdict gate (before ANY 'ready / approve / meets-the-bar' claim)"** — 11,651 B combined. These are labelled *orchestrator* work in the charter's own headings. A lens subagent never consolidates and never issues a readiness verdict. Cost: **2,323,902 tokens** delivered to agents structurally unable to act on it.
- **§5 "Mandatory Step-0 reads (every agent, before catalog work)"** — 831 B. A read-list, *inside the file you are reading because of that read-list*. Cost: **165,750 tokens**, purely self-referential.

**Mechanism:** move charter + tooling into the 8 agent definitions' system prompts (they are already `.md` files the harness loads), or into a single cached preamble block. Split §4b/§4c into an orchestrator-only file. This removes ~10.7M tokens **without touching a single line of review judgment** — 3.6% of all billed input across the 159 sessions.

### 2b. PR state the parent already holds

The dispatcher knows the head SHA — it put it in the prompt. Yet **182 dispatches (21.4%)** additionally instruct the agent to re-verify state itself, and **185 (21.7%)** to recompute the diff:

> `git rev-parse HEAD          # MUST equal d1db21bdda2912bce9304b5e1eeb6f1fdbd2928c — ABORT on mismatch`
> `git status --porcelain      # MUST be empty`
> — appears **10x** and **17x** respectively, verbatim

> "FIRST: `cd .../salesagent && git rev-parse HEAD` — MUST equal `3c7d6131f5623439bd97e536311c6c1045f564e9`; abort if not." — `[459] review-spec-conformance PR1544`

Each agent burns a Bash round-trip plus reasoning on a precondition one preflight script could assert once for the whole batch.

**Mechanism:** a `preflight.sh` that emits `{head, base, merge_base, porcelain_clean, changed_files[], diffstat}` as JSON once per fan-out; interpolate the JSON, drop the per-agent verification prose. Kills the abort-check from 182 prompts.

### 2c. Retrieval-shaped non-lens dispatches — 28 total

| Sub-cluster | n | Example | Replacement |
|---|---:|---|---|
| Doc-accuracy audit | 8 | `[451]` "For EVERY row: confirm the named test file actually exists (use: `find ...`)" over a ~35-row guard table | A test that globs the table and asserts each path exists. This is a CI check, not an agent. |
| GitHub metadata sweep | 6 | `[423]` "Dedup search… `gh search issues --repo prebid/salesagent`"; `[738]` milestone sweep; `[577]` scan all open PRs | `gh` + `jq` script. Zero judgment in the enumeration; judgment only in the final DUPLICATE/ADJACENT verdict. |
| Coverage-gap sweep | 6 | `[212]`, `[839]` — see §5 below | Eliminated by file-partitioned dispatch. |
| Code inventory | 7 | `[418]` "List EVERY column with its type and nullability" | AST/introspection dump (`sqlalchemy` metadata reflection). |
| Empirical suite runner | 1 | `[214]` "verify the PR's '4874 passed, 13 skipped, 26 xfailed' claim" | `pytest --json-report` + diff vs baseline. The *counts* are mechanical; only "is this xfail honest?" needs a model. |

**~28 dispatches ≈ 43,400 parent-side tokens**, plus their own subagent-side reads. Small next to §2a, but each is a clean, total replacement.

---

## 3. What genuinely needs a model — and I am not arguing otherwise

**The lens panel's core work is not mechanizable.** `review-bdd` exists to catch *semantic* circularity that the AST guard provably cannot see — its own definition says so: *"The structural guard catches STRUCTURAL weakness via AST; **you catch what it cannot see — semantic circularity.**"* A script cannot decide whether a `Then` step asserts the production behavior or echoes its own fixture. Same for `review-code-patterns` judging "is this a missing abstraction or a legitimate second site", and `review-spec-conformance` reading spec prose against an implementation.

Keep, in full:

- **All 738 lens agents' review reasoning.** Only their preamble is the target. The right change is cheaper agents, not fewer.
- **Adversarial / independent-verify — 21 dispatches.** `[102]` "Adversarially refute findings", `[753]` "Refute the top findings on PR 1728", `[362]` "Adversarial refutation of PR 1481 findings". Independence is the *point*; a script cannot disagree. This is also the cluster that directly implements your own CLAUDE.md rule — *"Subagent output gets the same scrutiny Chris gives mine… falsify it before it enters an artifact."* Cutting it would be the hidden downgrade your rules name as the cardinal sin.
- **Spec grounding — 11 dispatches.** Reading AdCP spec prose and mapping it to an implementation is exactly the `prebid-adcp` skill's remit.
- **Mechanism tracing — most of the 32 investigate/map/trace.** `[115]` "Two-sender exactly-once trace", `[574]` "Trace #1311 ↔ #1378 webhook chain". Following a value across async boundaries is judgment.
- **Issue batch summarize — 5.** A genuine map-reduce over disjoint chunk files. Correctly parallel; each agent gets its own `chunk_aa`…`chunk_ae`, no overlap. This is the one fan-out in the corpus with no redundancy at all.

Honest split: **~90% of dispatches contain irreducible model work.** The recoverable cost is almost entirely in *what every dispatch carries*, not in *which dispatches exist*.

---

## 4. Prompt bloat — the duplication is mandated by CLAUDE.md itself

**Measured within the 700-char prompt heads** (so these are floors — full prompts are longer):

| Signal | count | % |
|---|---:|---:|
| Restates `review-charter.md` absolute path | 327 | 38% |
| Restates `reviewer-tooling.md` absolute path | 255 | 30% |
| Contains a "Step 0" marker | 687 | 81% |
| Contains "MANDATORY" in caps | 536 | 63% |
| Cites charter §/section | 664 | 78% |

Lines repeated ≥5x account for **28.3%** of visible prompt text. The single most-repeated line — the charter path — appears **327 times**, 89 chars each.

**Every one of those 327 restatements is redundant**, because all 8 agent definitions already open with the identical block. From `review-bdd.md:20-25`:

```
## Step 0 — MANDATORY: read these FIRST (full absolute paths). Do not skip any.
Charter:
- `/Users/quantum/Documents/ComputedChaos/salesagent/.claude/rules/private/review-charter.md`
Tooling reference:
- `/Users/quantum/Documents/ComputedChaos/salesagent/.claude/rules/private/reviewer-tooling.md`
Catalog (…/memory/):
- `reference_bdd_harness_patterns.md` — the 24-pattern catalog
- `reference_bdd_harness_pitfalls.md` — the 8 pitfalls; your PRIMARY source
```

And dispatch `[747] review-bdd on PR 1728` re-sends **the same list, including the same catalog filenames**:

> "STEP 0 — MANDATORY. Read these in full with the Read tool before any catalog work: 1. …/review-charter.md 2. …/reviewer-tooling.md 3. Your agent-specific Step-0 memory reads … **including reference_bdd_harness_patterns.md, reference_bdd_harness_pitfalls.md**, reference_bdd_negative_scenario_vacuous_on_empty.md…"

**The root cause is a rule.** `~/.claude/CLAUDE.md:56-58` mandates exactly this:

> "Open every prompt with a **MANDATORY Step 0 Read list** of absolute paths; citing filenames does not make a subagent read them."

That rule is a workaround for an *unreliable mechanism*, and the charter documents the failure rate that produced it — `review-charter.md:51`:

> "[surfaced pr1547-rereview 2026-07-16: **3/8 agents hit the stale Read**; 2 detectors were unrunnable from the worktree]"

So: 3 of 8 agents ignored a charter section, and the response was to restate it in every prompt forever. The Step-0 blocks total **155,472 chars ≈ 42,019 tokens** across 458 prompts.

**The same fact is now paid twice per dispatch.** The worktree-Read gotcha lives in the charter (§2 item 9, 1,004 B) *and* is re-stated inline in the prompt — **52** prompts cite "CHARTER §2 GOTCHA 9" by name, **31** restate it in prose, **76** spell out the `git show HEAD:<path>` remedy:

> "CHARTER §2 GOTCHA 9: a bare `Read` in a worktree can serve MAIN-checkout content. Cite every load-bearing line via `git show …`" — `[94] Code patterns review PR 1719`

**Mechanism — and this is the highest-leverage fix in the report.** Your CLAUDE.md already names it: *"Never promise to remember — build the gate. Leverage runs `soft memory < turn instruction < CLAUDE.md < a mechanical gate that FAILS`."* The gotcha is that `Read` in a worktree serves main-checkout content. A `PreToolUse` hook that rejects a bare `Read` when cwd is under a worktree path, with the message *"use `git show HEAD:<path>`"*, makes the failure **impossible** rather than merely warned-against. Then: delete the warning from 103 prompts, delete §2 item 9 from the charter, and retire the CLAUDE.md rule that mandates restating read lists — because the agent definitions already carry them and the gate now enforces what the prose was begging for.

---

## 5. Redundant fan-out — two distinct kinds, both confirmed

### 5a. A full 7-lens panel re-run at an unchanged head SHA — in one session

PR #1605, head `c323bfc572feb8e2c08844156386fb03672c5366`. All seven lenses dispatched **twice**, at the **identical** SHA, from the **same session** (both prompts name the same scratchpad worktree `…/f48f0684-7d8f-435b-bbd4-7d9e7be1b5d2/scratchpad/wt-pr1605`):

| lens | dispatch 1 | dispatch 2 |
|---|---|---|
| spec | `[801] Re-review spec conformance PR1605` | `[808] Spec conformance review PR1605` |
| test | `[802]` | `[809]` |
| wire | `[803]` | `[810]` |
| patterns | `[804]` | `[811]` |
| security | `[805]` | `[812]` |
| bdd | `[806]` | `[813]` |
| guards | `[807]` | `[814]` |

**7 redundant dispatches ≈ 10,857 parent-side tokens + ~135,000 subagent-side Step-0 tokens.** This is a floor: only 464/851 prompts expose a 40-hex SHA in the first 700 chars, so same-SHA duplicates elsewhere are invisible to this scan.

**Fair-test note:** I checked the superficially similar case at `[178-182]` vs `[186-190]` (PR 1671, same 5 lenses, near-adjacent) and it is **legitimate** — head moved from `a142845…` to `e9e6d2c…`, and the second prompt says *"force-pushed since prior review at `a142845`"*. Not counted.

**Mechanism:** a dispatch ledger keyed on `(pr, lens, head_sha)`. Refuse a repeat; the operator must pass an explicit override. Cheap, and it turns "did I already run this?" from a memory question into a lookup.

### 5b. The panel is known to miss files, so a 9th agent is sent to cover the gap

This is the structural one. `[212] Wave 2: full-diff completeness sweep`:

> "The first wave's **8 specialists each sampled their surface**; YOUR job is the **completeness sweep** — read the files **NO specialist deeply reviewed** and surface anything missed."

`[839] Complete file-coverage sweep`:

> "A prior multi-agent review already covered the core production Go files and the headline findings. YOUR job is to read the files **NOT yet personally read**."

**6 dispatches** exist solely to patch coverage holes the fan-out left. Lens-partitioned dispatch gives no coverage guarantee — 8 agents each sampling "their surface" of a 163-file diff leaves a residue nobody read, and the residue is discovered only by spending a 9th agent. It also means the panel's implicit claim ("8 lenses covered this PR") was never true, which is precisely the *"CLEAN result over the wrong surface is a true sentence that reads as an all-clear"* failure your `pr-review-method` skill warns about.

**Mechanism:** partition the changed-file list deterministically before dispatch and hand each agent an explicit file set, then assert `union(sets) == changed_files` as a script-level check. Coverage becomes provable at dispatch time and the completeness-sweep agent disappears. Bonus: it makes each lens prompt *shorter*, since the file list replaces the "go find your surface" prose.

---

## 6. Session-level corroboration

From `token-measurements.json` (159 sessions, 293.6M billed input, 851 spawns):

| agents spawned | sessions | median billed input | median total ctx |
|---:|---:|---:|---:|
| 0 | 29 | 413,662 | 3.7M |
| 1–3 | 29 | 888,925 | 17.3M |
| 4–7 | 70 | 1,126,150 | 37.3M |
| 8–15 | 27 | 2,143,456 | 65.2M |
| 16+ | 4 | **10,340,672** | **292.6M** |

**95% of all billed input comes from the 82% of sessions that spawn agents.** Median context grows **79x** from the 0-agent to the 16+-agent bucket, against a 25x growth in billed input — consistent with your ~90x result-reread multiplier: fan-out inflates the *resident* context far faster than it inflates fresh input, and every subsequent turn re-reads it.

The worst session (`b5382f8e…`, 64 agents, 29.3M billed, 395M ctx) spent **175 Bash calls and 64 Agent spawns against 22 Reads** — it dispatched agents nearly 3x more often than it read a file itself.

---

## Ranked recommendations

| # | Change | Tokens recovered | Risk to review quality |
|---|---|---:|---|
| 1 | Hoist charter+tooling into the 8 agent definitions / cached preamble | **10.67M** | None — same text, same agents |
| 2 | Split §4b/§4c into an orchestrator-only file | 2.32M (subset of #1) | None — subagents can't use it |
| 3 | `PreToolUse` hook forbidding bare `Read` in a worktree | ~103 prompts shrink; removes a real 3/8 failure mode | **Improves** it — gate beats prose |
| 4 | Drop the CLAUDE.md "restate the Step-0 list in every prompt" rule (after #1 and #3) | 42K + shorter prompts | None once the list lives in the definition |
| 5 | `preflight.sh` emitting PR state as JSON, once per fan-out | Removes abort-checks from 182 prompts | None — same assertion, run once |
| 6 | Deterministic file-partition + `union == changed_files` assert | Eliminates 6 sweep dispatches | **Improves** it — coverage becomes provable |
| 7 | Dispatch ledger on `(pr, lens, head_sha)` | ≥7 dispatches (floor) | None |
| 8 | Script the 8 doc-accuracy audits + 6 gh metadata sweeps | ~14 dispatches | None — pure enumeration |

Items 1–5 touch **zero review judgment** and recover **~10.7M tokens, 3.6% of all billed input**, while making three documented failure modes structurally impossible.

**Not examined:** I could see only the first 700 chars of each prompt, so all prompt-bloat percentages are floors and same-SHA duplicate detection covers only the 464/851 prompts exposing a 40-hex SHA in that window. I did not measure subagent *result* sizes or the actual per-agent cache-hit behavior, so the 14.78M subagent-side read figure assumes each mandated read is a genuine uncached fetch — true on first read in a fresh subagent context, but it would overstate cost for any agent that re-reads within its own session.