---
name: feedback_oracle_decay_from_redundant_mechanism
description: A test that once discriminated the fix from the bug can silently STOP discriminating when a later co-located change adds a second mechanism that also covers the case — re-mutation-test the oracle after any change to its guarded path
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 239c764c-d655-46e3-bf1a-2ff36c1c2e31
---

A failing oracle is not permanent. A test written to prove invariant X (mutation-verified red-when-broken at authoring time) can be **silently neutered by a LATER commit** that adds a redundant mechanism covering the same case — so reverting the ORIGINAL fix no longer reddens it. This is distinct from [[feedback_claimed_invariant_needs_failing_oracle]] (no oracle at all): here the oracle exists, passes, and looks strong, but guards nothing.

Concrete shape observed: a two-thread concurrent test proved a server-side atomic increment prevented a lost update. A later commit added `populate_existing=True` to the locked re-read on the SAME path; that alone prevents the collision, so a full mutation matrix showed **either mechanism alone suffices** — reverting the original increment leaves the entire suite green. Worse, a strong human reviewer had asserted "verified red-at-2/green-at-3" — a **verification claim about test discrimination that was itself never mutation-tested and was false.**

**Why:** ratcheting/defense-in-depth naturally accretes redundant protections on a hot path. Each is individually good, but collectively they mean no single test isolates any one — and the one path where a given mechanism is the SOLE protection (here: the unlocked `apply_status_transition` seam) often has no test at all. Docstrings then credit the wrong mechanism.

**How to apply:**
- When a change touches a path guarded by a "core guarantee" test, RE-mutation-test: revert the specific line the invariant names and confirm the oracle still reddens. Don't trust that it did once.
- Mutation-test the SPECIFIC claimed line, and run a small matrix when two mechanisms co-exist (each × on/off) to find which is actually load-bearing and whether the sole-protection path is tested.
- Treat any "I verified this test is discriminating" claim (yours or a reviewer's) as a hypothesis until mutation-run — see [[feedback_empirical_over_static_guard_assessment]], [[feedback_detecting_subagent_overconfidence]].
- Isolate the mutation in a throwaway worktree + its own DB so background reviewers on the shared tree are unaffected ([[feedback_no_mutation_agents_on_shared_worktree]]).

Related mechanizable gap: BDD "gotcha #8" (auto-xfail masks dormant) recurred — a tag added to a `_*_WIRED` set whose scenario step-texts have NO matching `@then` handler auto-xfails and grades nothing while reading as "wired". Candidate personal detector (gitignored, [[feedback_personal_harness_gitignored_only]]): parse the WIRED sets, resolve each scenario's step texts, flag any with no registered handler.
