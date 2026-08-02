---
name: feedback-verify-branch-currency-before-rebuild
description: "Before implementing a plan-grounded rebuild/refactor on a feature branch, verify divergence from origin/main FIRST (behind/ahead + did main already change the TARGET files). A plan grounded against stale code is itself stale; detect 'synced' empirically, never wait to be told."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: f05442f8-8f3d-4746-a9f7-7a5971e6b984
---

Before writing ANY code for a plan-grounded rebuild/refactor on a long-lived feature branch, FIRST verify the branch's currency against `origin/main`: `git fetch origin main`; behind/ahead via `git rev-list --count HEAD..origin/main` (and reverse); `git merge-base --is-ancestor origin/main HEAD`; and crucially `git diff --stat HEAD...origin/main -- <files the plan targets>`.

**Why:** a planning/grounding doc is only valid if the branch it was written against is current. If main is many commits ahead and has ALREADY restructured the exact files the plan targets, then (a) the plan's line numbers / "which machinery still exists" are stale, (b) rebuilding on the stale base is partly throwaway, (c) syncing main afterward becomes a brutal merge on the most-churned files. This was caught only AFTER starting the first commit — it should have been step 0. Sibling of [[reference_adcp_spec_grounding]]: ground against the CURRENT authoritative state (origin/main for code; the pinned/target version for spec), never a stale snapshot.

**How to apply:**
- Make "branch currency check vs origin/main" the literal first action of any plan-grounded implementation, before re-reading target files. If behind AND main touched the target files → recommend sync-first, then RE-GROUND the plan against post-sync code before coding.
- Detect "synced" empirically (`merge-base --is-ancestor origin/main HEAD` flips to YES); never passively wait to be *told* a git state you can observe yourself. Don't assert sync/merge state you haven't checked — [[feedback_verify_before_asserting]].
- To enable a clean user-run merge, clear only the real blockers: the user's modified files that main also changed (`git diff --stat HEAD...origin/main -- <my modified files>`); set those aside, leave the rest.
