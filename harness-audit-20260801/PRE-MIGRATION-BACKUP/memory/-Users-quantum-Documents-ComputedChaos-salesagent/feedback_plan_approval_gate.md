---
name: feedback-plan-approval-gate
description: "Research-complete ≠ authorization to implement — present the consolidated plan + decision points and WAIT for approval before any code edit, even in auto/accept-edits mode"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 050812b2-2a71-4d1d-b5a4-69de34924975
---

After research/triage on any substantive task (multi-file change, PR feedback round, anything with design decisions), STOP and present the work program with every [DECISION] point flagged — then wait for the user's approval before the first code edit. Violated on PR #1389 (2026-06-10): went straight from research synthesis into a large Pattern A/B implementation with ~6 unilateral design calls; user: "That isn't how this works even in auto mode."

**Why:** Auto-accept on edits is not plan approval. Phrases like "address the feedback" or "make sure X flows through" authorize the *work*, not skipping the gate. This project's precedent is explicit approved-scope plans (the #1389 June-7 plan was literally headed "APPROVED SCOPE"). Related: [[feedback-no-code-in-planning-stage]], [[feedback-session-workflow-rules]] (W1: smaller atomic actions; restate contract before executing).

**How to apply:** Trigger = about to make the first Edit/Write to repo code in a session whose scope wasn't already explicitly approved. Use EnterPlanMode for big work, or end the turn with the plan + decision points and an explicit ask. Mechanical/verbatim items (e.g. "rebase onto main" demanded by a reviewer) are the only low-discretion exceptions, and even those get stated as "I'll do X first" before doing X.
