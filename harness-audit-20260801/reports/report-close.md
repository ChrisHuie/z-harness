All four settled; repo untouched (0 working-tree writes, no refs created, .git +5 MB from 23 exact-SHA fetches).

---

# Q1 — the §5 anomaly: the charter is not the delivery channel, and probably never was

**Reproduced first:** 759 lens runs, 303 all-nine (39.9%), 255 in §5 order. The "95" is all-nine-without-charter in *any* order; **83** of those are in exact §5 order.

**Every candidate is falsified.**

| candidate | verdict | evidence |
|---|---|---|
| Orchestrator dispatch prompt enumerates them | **dead** | Full `Agent` tool_use `input.prompt` from the main transcript (not a prefix): **0 of 9 named in all 83**. 77 say "Step 0", 82 say "charter", 16 name `review-charter.md` — none names a memory file |
| `MEMORY.md` index | **dead** | Read by **0 of 759** lens runs. Its ordering of the nine *is* §5's exactly (lines 4,5,6,8,9,37,37,53,73) |
| `settings.json` / hook injection | **dead** | Only hook is a `SessionStart` echo about `.agent-index` |
| Agent definitions | **dead** | No lens definition names any of the nine — current files and the 2026-06-16 backup. They name only the charter path, tooling path, and 2–9 agent-specific catalog files |
| `CLAUDE.md` (project + global) | **dead** | No charter reference, no `@`-imports, none of the nine |
| Alphabetical / mtime glob | **dead** | §5 order is not alphabetical; ~0 runs list the memory dir |
| Chaining via memory cross-links | **dead** | **39 of 95 runs emit all nine Reads in ONE API response**, before any result returns |
| Charter inlined in the system prompt | **dead** | 0 of 95 charter-less runs quote any of **155 charter-unique phrases** (baseline: 1.0% among charter-readers) |
| MEMORY.md auto-injected into context | **dead** | 1 of 95 emits a MEMORY.md-only short label vs 0.4% baseline — noise |
| Harness version artifact | **dead** | Spans 11 versions, 37 sessions, June and July; no cliff |

A filesystem-wide scan found only `review-charter.md` (5 copies) and `MEMORY.md` (4 copies) carrying ≥5 of the nine — plus two offloaded `tool-results/*.txt` from a *main-thread* Bash that `cat`s them. Nothing a subagent reads.

**The decisive statistic — it points the other way from the premise.** Among all-nine runs, in-§5-order is **87.4% without the charter (83/95)** versus **82.7% with it (172/208)**. If §5 supplied the order, readers would be *more* ordered, not less. And partial runs read **ragged subsets 90.7% of the time (214/236)**, not prefixes — selection behaviour, not list-copying.

**Conclusion: the nine are reconstructed, not copied.** §5's order coincides with MEMORY.md's Tier-0 order because both encode the same natural priority ordering the model independently produces. The control settles that the *instruction* is lens-specific, not the channel: main threads (0/159), `general-purpose` (0/76) and `Explore` (0/24) never do this, because only lens prompts say "do your charter + catalog Step-0 reads."

**This changes the compliance model — but not in the direction the brief anticipated.** The orchestrator is *not* the delivery channel (it names none of the nine). Instead, **§5 all-nine "compliance" is not a charter-adherence measurement at all** — it measures convergent reconstruction, which is why it is *higher* among charter-skippers. It should be dropped as evidence of charter compliance. Charter load rate (71.8%) remains the real metric.

One correction to my own intermediate output: an early pass reported 474 failed memory reads (390 for `feedback_verify_reviewer_fixes_against_code.md`). That was a false positive — the memory's own prose contains the string "does not exist". **True failures: 3 of 7,800 (0.04%)** — near-perfect filename accuracy over a 169-file namespace.

**What would settle the residual unknown** (how the model names 169 files with no Read and no visible list): capture the *assembled system prompt* for one lens dispatch — `claude --debug`, `ANTHROPIC_LOG=debug`, or a logging proxy. One dispatch is enough. The JSONL never persists system prompts, so no amount of transcript analysis can close this.

Scripts: `/private/tmp/claude-501/-Users-quantum-Documents-GitHub-agenticads-sim-plan/e2367c8b-0c8b-43ae-a5d4-98ce3fbcecea/scratchpad/q1/` (`q1_route.py`, `q1_control.py`, `q1_quote.py`, `q1_memlabels.py`, `q1_channel.py`).

---

# Q2 — the 207 resolved; the band collapses to a point estimate

23 commits were missing across 7 PRs (1534, 1665, 1669, 1697, 1698, 1699, 1718). Fetched by **exact SHA** (`git fetch origin <sha> --no-tags --no-write-fetch-head`) — no `refs/pull/*` glob, no refs created, `.git` 127 M → 132 M.

I also found and fixed a pairing bug: `original_line` pairs with `original_commit_id`; using `line` (the current-head line) produced 17 blame failures. With correct pairing, **all 864 rows resolve — zero unresolvable.**

| | n | MISS | UNDER | CAUGHT |
|---|---:|---:|---:|---:|
| **OPPORTUNITY** | **503** | **39.6%** | 21.5% | 39.0% |
| NO OPPORTUNITY | 361 | 69.0% | 8.9% | 22.2% |
| *of the former 207:* OPPORTUNITY | 89 | 44.9% | 27.0% | 28.1% |
| *of the former 207:* NO OPPORTUNITY | 118 | 61.9% | 9.3% | 28.8% |

**Point estimate: 39.6% miss, bootstrap 95% CI over 28 PRs [29.1%, 49.0%].**

The 37–52% band collapses to **39.6%** — near the bottom, close to the prior 37.1%. The 207 were not systematically worse; they split 43/57 between opportunity and no-opportunity. My method agrees with the prior classification on **89.0%** of rows both resolved (the 63 `NO OPPORTUNITY→OPPORTUNITY` flips come from broader panel-run attribution: 728 of 759 runs attributed to a primary PR).

Scripts: `.../scratchpad/q2/` (`fetch_comments.py`, `panel_ts.py`, `blame_all.py`); data `rows_blamed.pkl`.

---

# Q3 — 143 standing hits: real backlog is ~19, the rest is annotation debt

Reproduced exactly: exit 1, 143 hits, pin `spec=3.1.1 sdk=6.6.0`, 27 in `media_buy_create.py`, 22 in `schemas/_base.py`. Adjudicated a systematic 1-in-4 sample (n=36) by hand plus a mechanical pass over all 143.

| class | n | verdict |
|---|---:|---|
| **Genuinely stale** | **~19** | actionable now |
| Bare provenance tag ("(adcp 2.12.0)") | 78 | legitimate, needs `# spec-introduced:` |
| Introduction form `X+` ("2.14.0+") | 24 | legitimate — mechanically exemptable |
| Historical change note ("removed in 3.2.0") | 12 | legitimate |
| Normative authority cite (`.mdx`, rule N) | 7 | legitimate |
| **Literal value, not a citation** | **11** | false positive |

**Real stale count: 19 confirmed by direct inspection (~13%).** Extrapolating the hand sample (6/36) gives ~24, 95% CI [9, 47].

**Highest-value finds — both genuinely stale, both never adjudicated:**

- `src/services/protocol_webhook_service.py:40,42,79` — the FIXME reads *"salesagent is pinned to adcp 4.3.0, which predates that public seam"* and *"Delete this block and call `adcp.to_wire_dict()` directly once salesagent bumps adcp to the version that ships it."* `pyproject.toml:10` pins **`adcp==6.6.0`**, which is past 5.4.0. **The stated deletion precondition is already met** — this is live backport code carrying an unexecuted removal instruction.
- `.claude/skills/verify-spec/SKILL.md:46,78,148` — the spec-grounding skill directs reviewers to `dist/schemas/3.0.0-beta.3/core/` while the pin is 3.1.1. This is precisely miss-mode #9 ("the harness's OWN artifacts going stale") that the detector's docstring names. It caught it; nobody read it.
- `src/core/signals_agent_registry.py:13,24` — module header `Schema Version: AdCP v2.2.0` and `Migration Note: Now uses official adcp library (v1.0.1)`.

**Why the exit code carries no per-run information:** ~124 of 143 hits are **permanent by construction**. Provenance, historical and normative citations will never be "fixed" — they need a one-time `# spec-introduced:` marker sweep. Until that happens the detector exits 1 forever, and charter §4c precondition 1 tells agents to read a nonzero exit as a worklist, which trains them to skim it. So: a real backlog, but **87% of it is annotation debt, not staleness.**

Two structural defects in the detector itself:
- It compares every token against **both** pins, so it cannot distinguish an SDK-version citation (26 hits cite `3.6.0`, an old SDK) from a spec-version citation. This is the main noise driver.
- 11 hits in `src/routes/api_v1.py` are `adcp_version: str = "1.0.0"` — a **runtime default value**, not a citation. Out of class for this detector. (Separately worth someone's attention: 11 API request models default `adcp_version` to `1.0.0` while the spec pin is 3.1.1.)

Output and hit list: `.../scratchpad/q3/cf_out.txt`, `hits.json`.

---

# Q4 — severity inflation: confirmed, and roughly 3× stronger than reported

Re-measured by joining **per-finding blocks** on `disposition_ledger.site_tokens(expand_ranges=True, resolve_bare=True)`, segmenting both sides into severity-tagged blocks and recognising the `### Cluster A (BLOCKER)` header form the bracket-only regex is blind to. 81 artifacts → 804 findings; 759 lens reports → 3,660 findings.

**Strict join** (exact line, ties dropped), rows = lens, cols = artifact:

| | BLOCKER | SHOULD-FIX | NIT | tot |
|---|---:|---:|---:|---:|
| **BLOCKER** | 59 | 27 | 13 | 99 |
| **SHOULD-FIX** | **71** | 316 | 31 | 418 |
| **NIT** | **58** | **133** | 169 | 360 |

| join | n | inflated | deflated | ratio |
|---|---:|---:|---:|---:|
| range-expanded, ties kept | 1,165 | 427 (36.7%) | 96 (8.2%) | **4.45:1** |
| range-expanded, ties dropped | 910 | 297 (32.6%) | 77 (8.5%) | **3.86:1** |
| **strict exact-line, ties dropped** | **877** | **262 (29.9%)** | **71 (8.1%)** | **3.69:1** |

**The inflation claim is confirmed.** Against a within-session permutation null that preserves *both* marginals: null median **2.23:1** [2.12, 2.36], observed **3.69:1**, **p < 0.0001**. Not concentrated — 262 inflated pairs across 45 sessions, top 5 sessions = 32%.

Population level over the 877 joined pairs: lens severity is 11.3% BLOCKER / 47.7% SHOULD-FIX / 41.0% NIT; artifact severity is **21.4% / 54.3% / 24.3%**. BLOCKER share nearly doubles, NIT share nearly halves, between the lens report and the shipped artifact.

**The proximity method was wrong in both directions**, which is why the prior 1.2:1 understated it: `BLOCKER→SHOULD-FIX` goes 4 → 51, and `SHOULD-FIX→NIT` goes 84 → 41. Proximity was over-counting deflation and under-counting promotion.

One honest caveat: the null is **2.23:1, not 1:1**, so a bare "inflation outnumbers deflation" is partly a marginals effect. The claim survives because the observed ratio sits decisively outside the marginal-preserving null.

Scripts: `.../scratchpad/q4/drift.py`, `drift_robust.py`.

---

**Repo state:** read-only apart from 23 exact-SHA object fetches. No working-tree file modified (0 files newer than 2 h), no checkout, no push, no refs created, branch and HEAD unchanged (`feature/pin-validation-suggestion-wire-oracle` @ `6881e8da4`). The 55 modified / 51 untracked files in `git status` and the `refs/pull/*` entries (created 19:10, before this session) were all pre-existing.