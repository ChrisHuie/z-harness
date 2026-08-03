---
name: feedback-no-optional-disposition
description: "Never label a finding/suggestion 'optional' or 'non-blocking' — split severity (how wrong) from disposition (what happens next); default to doing the work; deferral must be tracked, never floating."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ef82ad4d-a7bf-4d1e-bb63-c1157a5c3477
---

"Optional / non-blocking / nice-to-have / consider" is a banned disposition. It collapses two independent axes and answers neither, leaving work undone-and-untracked. In an agentic world where applying a fix is cheap, that drops value and pushes an unstated decision onto the reader.

**Split the axes:**
- **Severity** = how wrong the code is (BLOCKER/SHOULD-FIX/NIT) — about the code.
- **Disposition** = what happens next — about the action. Closed enum, always resolves to an action:
  - **FIX-NOW** — apply in this change (default for small/safe/in-scope).
  - **FOLD-IN** — trivially adjacent; do it here.
  - **FOLLOW-UP** — genuinely separate scope → MUST be filed (issue / `bd create` / spawn_task) with rationale + link. Deferred WITH an owner, never floating.
  - **WON'T-FIX** — declined with a concrete reason (spec mandates it / false premise / accepted trade-off).

**Why:** a low-severity item is not a reason to defer — only *scope* (→ FOLLOW-UP) or *correctness* (→ WON'T-FIX) is. A NIT that takes 30 seconds is FIX-NOW. The invariant that kills the ambiguity: **no finding is left undone AND untracked.** "Optional" was the exact failure — a review PR comment listed real fixes as "optional/non-blocking," leaving cheap value on the table and the decision unmade.

**How to apply:** every finding/suggestion I surface carries a disposition, and I RESOLVE it — do FIX-NOW/FOLD-IN, file FOLLOW-UPs — rather than hand the user an "optional" list. Present *decisions* ("doing X; filing Y as follow-up"), not ambiguity. Remote actions stay gated ([[feedback_user_owns_git_push]]): on an external contributor's PR a FIX-NOW I can't apply becomes an exact instruction to the author, still never "optional". This preserves scope discipline — FOLLOW-UP is the valve so you don't cram everything into one PR ([[feedback_principled_scope_expansion]]), but the work is captured, not dropped. Enforced in the review harness (review-charter §1.8 banned-language, §3 Disposition field, §4b.5 Actions ledger) — the charter is the lever, not this memory ([[feedback_escalate_recurring_lessons_to_guards]]). Sibling of [[feedback_final_reports_must_be_contributor_actionable]] (adds the action-resolution axis) and [[feedback_lean_toward_quality_not_smaller_option]] (bias toward the fuller end state).
