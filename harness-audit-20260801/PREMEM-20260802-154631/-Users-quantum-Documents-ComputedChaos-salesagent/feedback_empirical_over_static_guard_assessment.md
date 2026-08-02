---
name: empirical-over-static-guard-assessment
description: "Assessing whether OPEN PRs violate a structural guard via static line-counting is unreliable and nearly self-burned me twice in one session: it over-counts each file's INHERITED (to-be-drained) violation population against the guard's tightened caps, and can't distinguish moved/re-indented code from genuinely-new. The authoritative check is EMPIRICAL: rebase the PR onto target main + run make quality (the guard runs in the required Unit Tests job). Static analysis (mine OR a subagent's) is TRIAGE only."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 8377e960-8e7a-4aba-8c4d-4aedb89a6629
---

When deciding which open PRs will fail a structural guard after a tightening PR lands, **do not trust static violation-counting** — produce a triage with it, then verify empirically.

**Why (one session, three methods, three answers):**
- A guard's cap tightens over its lifecycle (e.g. a Pattern-A `Error(code=)` cap drained to empty by a later PR; `no_value_error` 21→12 files). Open PRs branch from a base where the cap was looser and the files still carry the full UN-drained population.
- **Scanning a PR-head file with the guard's NEW (tight) cap counts the entire inherited population as "violations"** — my first scan flagged a known-clean PR (#1313, verified typed-raise) with 21 Pattern-A sites + identity guards that were all inherited and would be drained on rebase. Flat wrong.
- **Intersecting guard-hits with the PR's added lines** (git diff `+`) is closer but still over-reports: moved/re-indented existing code shows as `+added`. 
- **Net count delta (merge-base vs head)** distinguishes genuinely-added from moved at the count level, but a far-back merge-base folds in intervening rebases, and it still can't tell whether a `+N` is new logic or the author's conflict-resolution re-adding a drained site.
- Net: for one PR the three methods disagreed (clean / +identity+ValueError / ambiguous). The SET (which PRs to look at) was reliable across methods; the exact per-site fix-list was not.

**The gold standard:** the only artifact-free check is **rebase the PR onto the target main, then `make quality`** — the guard executes in the required Unit Tests job and prints exactly the surviving violations, immune to inherited-population, moved-code, and merge-base artifacts. For DIRTY PRs you can't rebase without resolving conflicts first, so the verification *is* the rebase.

**How to apply:**
1. Use static scans (and subagents) to TRIAGE: which PRs touch error/identity/Error-construction code → worth budgeting work. Treat counts as approximate.
2. Never hand the user (or yourself) a "do exactly these N edits" list derived purely from static analysis — say "rebase + make quality settles it."
3. Re-verify any subagent's per-PR violation list the same way (they hit the identical inherited-population/moved-code traps). Ties [[feedback_detecting_subagent_overconfidence]], [[feedback_run_full_suite_before_every_push]] (make quality ≠ full suite), [[feedback_complete_claim_requires_full_pattern_enumeration]] (verify "clean" symmetrically), [[feedback_verify_before_asserting]].

**Adjacent merge-order trap (same session):** a CLEAN/MERGEABLE PR can be turned DIRTY by merging a *different* PR — verify with `git merge-tree --write-tree <to-be-merged-head> <pr-head>`, not just against current main. And DIRTY ≠ uniformly CI-frozen: distinguish stale-green (ran weeks ago vs old base) from absent-checks (truly gated). [[gh_actions_dirty_merge_skips_pull_request_workflows]]
