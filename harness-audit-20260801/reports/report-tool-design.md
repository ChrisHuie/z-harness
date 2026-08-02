I have everything I need. Here is the design.

---

# Collapsing git/GitHub state queries in the salesagent review harness

## 1. What the corpus actually shows

I re-counted independently and got the same ranking as the brief (`git show` 1,056 occurrences / 780 calls, `gh pr` 995/827, `gh api` 965/695, `git rev-parse` 703/588 …). Two structural facts matter more than the totals:

- **Compound composition is the real unit.** 6,022 of the 7,344 unique commands are compound (≥2 `&&` or multiline). 2,024 git/gh-bearing calls contain **two or more** git/gh commands: 1,439 have 2, 467 have 3, 118 have 4+. The model is hand-assembling a composite state report every time, with `echo "=== SECTION ==="` separators. That composite is the thing to own, not the individual commands.
- **The repetition is in the render, not the query.** 258 calls are literally the same orientation ritual with different separator text. The `--jq` filters over review endpoints vary constantly, but always project the same 4-5 fields.

**Re-read multiplier calibration.** From `token-measurements.json`: 285.5M cache-creation vs 7,501M cache-read across 159 sessions — **26.3x mean, 22.8x median, 39.1x for the 51 sessions over 200 turns**. The brief's 90x matches the long-session tail rather than the corpus aggregate. I report savings at all four multipliers below so the conclusion doesn't depend on which one you take. Cache reads are 72% of billed input either way.

---

## 2. The tools

All five follow the existing house pattern: module docstring with `Usage:`, `from __future__ import annotations`, `argparse`, `main() -> int`, exit **0** clean / **1** findings-or-drift / **2** usage-or-`gh`-error, `--repo` defaulting to `prebid/salesagent`, `_gh_json()` subprocess wrapper lifted from `review_completeness.py:56`.

### T3 first — it is 61% of the total win

**`review_completeness.py --index`** — extend `/Users/quantum/Documents/ComputedChaos/salesagent/.claude/rules/private/detectors/review_completeness.py`

**The gap:** the detector already fetches all four review surfaces (`review_completeness.py:112-128`) and then **throws the content away** — it prints only a verdict plus `events[-8:]` as `ts / kind / who / path` tuples. So after running the gate, the model runs the same four network calls again by hand to actually read the feedback. That second pull is the 460-800 `gh api` calls in the corpus.

```
review_completeness.py <pr> [--repo O/R] [--since ISO|SHA] [--head SHA]
                            [--index] [--expand T3,T7,REV2] [--unresolved] [--author LOGIN]
```

`--index` costs **zero additional network calls** — it renders what lines 112-128 already fetched.

Output (`--index`), one line per thread, prototyped and measured on live PRs:

```
T1   OPEN-OUTDATED src/core/tools/creatives/listing.py:214 @KonstantinMirin n=1 | `return coerced or None` is the docstring-claimed empty…
T2   OPEN-OUTDATED src/core/tools/creatives/listing.py:198 @KonstantinMirin n=1 | Generically-named and generically-documented helper, bu…
REV  CHANGES_REQ   @KonstantinMirin 2026-07-28T14:50:02Z | Several should-fix items below…
DISC               @ChrisHuie 2026-07-28T15:02:11Z | Folded in as 8963c4a…
```

| PR | raw 3-endpoint + GraphQL | `--index` | reduction |
|---|---|---|---|
| 1616 (21 threads) | 105,638 ch / **26,409 tok** | 5,186 ch / **1,296 tok** | **95.1%** |
| 1720 (59 threads) | 346,971 ch / **86,742 tok** | 15,474 ch / **3,868 tok** | **95.5%** |

Raw un-jq'd, PR 1720's three REST endpoints alone are **891,489 ch / 222,872 tokens** — larger than a context window.

**Why a script owns it deterministically.** I decomposed the payloads:

| | PR 1616 | PR 1720 |
|---|---|---|
| body prose (the judgment content) | 36.9% | **22.4%** |
| JSON envelope (`node_id`, `_links`, avatars, reactions, `author_association`, html urls) | 33.5% | **47.2%** |
| `diff_hunk`, redundant copies across thread replies | 0 | **135,263 ch (50% of hunk bytes)** |

Envelope stripping and hunk dedup are lossless on signal. Thread grouping is a verified join: **GraphQL `reviewThreads` covered 118/118 REST inline comments by `databaseId`** on PR 1720 — no heuristic matching. Resolution state (`isResolved`/`isOutdated`) exists only in GraphQL and is what makes the index actionable; it is also the exact axis of the #1616 false green documented at `review_completeness.py:16-24`.

**What stays with the model.** Reading thread bodies and deciding whether feedback is addressed. `--expand T3,T7` pulls full bodies for named threads. The index carries a 90-char gist precisely so the model chooses *which* to expand — that choice is judgment. The existing exit-1 gate semantics are untouched.

**One implementation note:** request `line` **and** `originalLine` on the thread. My prototype printed `?` for line numbers because `line` is null on outdated threads — and outdated is the majority state (43 of 59 on PR 1720).

**Collapses ~533 calls** (`pulls/N/reviews` 190, `pulls/N/comments` 131, `issues/N/comments` 140, `graphql` 72). **~2.5M raw tokens.**

---

### T4 — `ci_failure.py`

`/Users/quantum/Documents/ComputedChaos/salesagent/.claude/scripts/ci_failure.py`

```
ci_failure.py <pr> | --run <id> [--repo O/R] [--context N=25] [--all-jobs] [--full-job <id>]
```

**Verified finding: `gh run view --job N --log-failed` returns byte-identical output to `--log`** — 90,229 bytes both, `cmp` says identical, on run 30690323410 job 91343761801. The built-in reduction flag does nothing on this repo's logs. That is why 43 calls in the corpus each drag ~22,553 tokens.

Two deterministic transforms, measured on that real failing job:

1. **Strip the per-line prefix.** Every one of 668 lines carries `GAM E2E (requires_gam)\tUNKNOWN STEP\t2026-08-01T07:44:55.5857869Z`. That is **43,173 of 90,213 ch = 47.9% pure envelope**, removable before any filtering.
2. **Window on failure anchors** (`##[error]`, `^FAILED`, `^E  `, `^assert `, `Process completed with exit code [1-9]`), 25 lines before / 5 after.

Result: **668 lines / 22,386 tok → 32 lines / 507 tok, 97.7% reduction** — and the window contains the actual cause (`GAM_SERVICE_ACCOUNT_JSON is not configured … exit 1`). Only 2 anchor lines existed in 668.

**Why deterministic.** Anchors are GitHub Actions' own markers plus pytest's own failure grammar. There is no judgment in "which lines did the runner label as errors".

**What stays with the model.** Diagnosing the failure, and deciding whether it is the PR's fault or infra. `--full-job` escapes to the whole log when the window misses.

**Collapses ~100 calls** at very high unit cost. **~930k raw tokens.**

---

### T1 — `repo_state.py`

`/Users/quantum/Documents/ComputedChaos/salesagent/.claude/scripts/repo_state.py`

```
repo_state.py [--root PATH] [--fetch] [--json]
```

Collapses the 258-call orientation ritual and its single-purpose fragments: `git rev-parse --short HEAD` (248), `git rev-parse HEAD` (148), `git status --porcelain` (413), `git rev-parse --abbrev-ref HEAD` (75), `git worktree list` (100), `git fetch origin main` (~85), `git log --oneline -1/-5` (~80).

Measured today: **4,569 ch / 1,142 tok** for the full composite. Target output ~110 tok:

```
repo   salesagent @ /Users/quantum/Documents/ComputedChaos/salesagent
head   8963c4a73  branch fix/validation-envelope  upstream origin/main
ahead  3  behind  0        dirty  2 files (1 staged)
origin/main  6854f6fce  (fetched 4s ago)
worktrees  3 other: pr-1616@8963c4a73  review-1417@cd3391f12  validation-remediation@6854f6fce
```

**Why deterministic.** There is exactly one correct answer to "what SHA, what branch, dirty?, ahead/behind, is origin/main stale, which worktrees exist". The `git-workflow` skill's confirm-a-commit-actually-landed rule and the CLAUDE.md "report raw state — origin head, `git log @{u}..HEAD` for local-only commits" rule both become one call that cannot be partially performed.

**What stays with the model.** What to do about the state.

**Collapses ~700 calls. ~284k raw tokens.**

---

### T2 — `pr_state.py`

`/Users/quantum/Documents/ComputedChaos/salesagent/.claude/scripts/pr_state.py`

```
pr_state.py <pr>... [--repo O/R] [--files] [--body] [--commits] [--json]
```

The corpus shows 567 `gh pr view` calls requesting **wildly varying subsets of the same 12 fields** — `headRefOid` 291 times, `state` 275, `mergeStateStatus` 250, `mergeable` 220 — in 60+ distinct `--json` permutations, each with a bespoke `--jq`. Plus `gh pr checks` 165.

Measured today: 15-field view 554 tok, `gh pr checks` 843 tok, `--json statusCheckRollup` **2,238 tok**, `--json commits` 772 tok. Typical orientation runs 2-3 of these.

Target ~200 tok:

```
#1812 OPEN  fix: principal-scope durable get_task / get_by_step
  head 8963c4a73  base main  branch fix/principal-scope  @chrishuie  draft=false
  mergeable MERGEABLE / BLOCKED   reviewDecision CHANGES_REQUESTED
  +412 -87 across 9 files
  checks 14 ✓  2 ✗  1 ⏳   FAILING: gam-e2e (job 91343761801), integration-py312
```

Accepts multiple PR numbers — the corpus has loops re-invoking `gh pr view $n` per PR.

**Why deterministic.** Field selection and rollup summarization are mechanical. `mergeStateStatus` in particular is a documented footgun in the `git-workflow` skill (it causes GitHub to skip workflow runs) and is currently fetched inconsistently.

**What stays with the model.** Whether the PR is ready — which CLAUDE.md bans claiming without raw state anyway. The failing-check names hand straight to `ci_failure.py`.

**Collapses ~750 calls. ~330k raw tokens.**

---

### T5 — `pr_worktree.py`

`/Users/quantum/Documents/ComputedChaos/salesagent/.claude/scripts/pr_worktree.py`

```
pr_worktree.py <pr> [--repo O/R] [--sha SHA] [--suffix TAG] [--list] [--remove]
```

The corpus shows the same three-step ritual ~250 times: `git fetch origin pull/N/head:refs/pr/N` → `git worktree add --detach ../salesagent-wt-prN refs/pr/N` → `cd && git rev-parse HEAD` to verify. Naming is ad-hoc (`salesagent-wt-pr1669`, `salesagent-rc-pr1720`, `salesagent-wt-pr1622-mut`), and `git worktree remove` 132 / `add` 125 / `prune` 29 shows the cleanup is manual and lossy.

**I am flagging this one honestly: the token saving is modest (~72k raw). Its value is correctness.** CLAUDE.md states `isolation: "worktree"` may branch from main rather than the launching HEAD — *"pass the target SHA and have the agent verify"* — and that mutation agents whose revert discards uncommitted work need isolation. A tool that fetches, creates, and **fails exit 1 if `rev-parse HEAD != --sha`** makes that rule mechanical instead of remembered. Per the CLAUDE.md memory rule, that is the gate rather than the restatement.

This is the only tool in the set that mutates. It creates worktrees; `--remove` deletes only paths it created (recorded in a sidecar), and refuses a worktree with a dirty status.

**Collapses ~250 calls. ~72k raw tokens.**

---

## 3. Aggregate

| tool | calls | now/call | new/call | raw tokens saved |
|---|---:|---:|---:|---:|
| `review_completeness.py --index` | 533 | 6,000 | 1,300 | **2,505,100** |
| `ci_failure.py` | 100 | 9,700 | 400 | **930,000** |
| `pr_state.py` | 750 | 640 | 200 | 330,000 |
| `repo_state.py` | 700 | 515 | 110 | 283,500 |
| `pr_worktree.py` | 250 | 350 | 60 | 72,500 |
| **total** | **2,333** | | | **4,121,100** |

That is **81% of the 5.10M tokens these clusters emit today**, from **2,333 of the 5,945 calls (39%)**.

With the re-read multiplier:

| multiplier | context avoided | billed-equivalent units |
|---|---:|---:|
| corpus median 22.8x | 98.1M | 13.5M |
| corpus mean 26.3x | 112.5M | 15.0M |
| >200-turn sessions 39.1x | 165.3M | 20.2M |
| brief's 90x | 375.0M | 41.2M |

Against 1,035.7M total billed-input units measured across the 159 sessions, that is **1.3% to 4.0%** of total spend — concentrated in exactly the long review sessions where context exhaustion, not money, is the binding constraint.

**Per-invocation unit costs, all measured live, not estimated:** orientation composite 1,142 tok · `gh pr checks` 843 · `--json statusCheckRollup` 2,238 · `gh pr diff` 12,026 · failing job log 22,553 · three-endpoint raw 54,681 (PR 1616) and 222,872 (PR 1720).

---

## 4. What will not collapse — roughly 60% of the 5,945

**Genuinely exploratory (~1,900 calls, ~32%). Do not build tools for these:**

- **`git grep` (361 calls).** 287 `-n`, 94 `-nE`, 39 `-rn`. The pattern *is* the thinking — `pr-review-method` makes "grep the repo for the pattern and count the copies" the core act of finding a defect. A tool here would only hide which pattern was searched, which is the evidence.
- **`git show REF:path` (759 calls).** Reading a file at a non-HEAD ref. There is visible repetition (`HEAD:src/a2a_server/adcp_a2a_server.py` 19 times, `tests/bdd/conftest.py` 17), but *which* file to read is judgment. At most ~15% would collapse into a "read these N files at the PR head" batch, and batching would defeat the point of reading one file to decide the next.
- **`git diff` (494) and `gh pr diff` (106).** The diff is the artifact under review — irreducible. Only *range selection* is mechanical, and it is a real footgun: 37 calls use `origin/main...HEAD`, 33 use `SHA..SHA`, 9 use `$(git merge-base …)`, and `pr-review-method` requires two-dot against current main **as well as** three-dot. That is worth a one-line `--range` helper inside `pr_state.py`, not its own tool.
- **`gh issue` read paths (~180).** Issue bodies are prose to be read. The write paths (`comment` 24, `create` 18, `edit` 5, `close` 5) are forbidden on my own initiative by CLAUDE.md and must stay manual.

**Long-tail and low-value (~1,700 calls, ~29%).** One-off `gh api` paths — `repos/.../branches/main/protection` (4), `rulesets` (5), `search/code` (2), `gh api user` (22), and the cross-repo `adcontextprotocol/adcp` tree/contents reads (~40) that serve the `prebid-adcp` skill. Each shape appears 2-8 times. Building for these is speculative; their unit cost is small and their shapes do not repeat enough to amortize.

---

## 5. Sequencing

**Build T3 alone first.** It is 61% of the total win, it is an extension of an existing 218-line file rather than a new script, it adds zero network calls, and it closes a gap that is already the documented cause of two harness misses (`review_completeness.py:6-24`). If nothing else ships, ship that.

Then T4 (930k tokens, ~100 lines, no dependencies). T1 and T2 are cheap and mostly ergonomic. T5 last, and only for the correctness gate.

---

**Not tested:** I did not run any tool — none exist yet; all figures are measurements of the *current* commands' output plus in-memory prototypes of the two headline renders (thread index, CI failure window), which I ran against live PRs 1616/1720 and run 30690323410. I did not verify the `--index` reduction holds on a PR with very long individual review bodies (PR 1720's 64 review bodies total 200k ch; a PR with a few enormous ones would index well but expand poorly). I did not measure `gh` API latency, so wall-clock effects are unquantified. The 2,333-call collapse estimate assigns corpus calls to clusters by command shape; calls that mix an orientation ritual with an exploratory grep in one compound invocation are counted in the collapsible column even though only part of them collapses — that biases the estimate optimistically by an amount I did not bound.