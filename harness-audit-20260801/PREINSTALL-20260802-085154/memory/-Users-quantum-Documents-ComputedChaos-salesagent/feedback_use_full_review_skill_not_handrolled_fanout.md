---
name: use-full-review-skill-not-handrolled-fanout
description: "For salesagent PR reviews, invoke the full-review SKILL (the in-house harness), never a hand-rolled fan-out of the review-* agents"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: f48f0684-7d8f-435b-bbd4-7d9e7be1b5d2
  modified: 2026-07-20T18:28:44.994Z
---

When asked to review or re-review a PR in this repo — or to "use our review harness / in-house review / gold-standard review" — invoke the `full-review` **skill** (`Skill(full-review, args="PR #N …")`). Do NOT approximate it by hand-launching the `review-*` specialist agents through the Agent tool.

**Why:** The `full-review` skill IS the in-house harness. It carries the tuned tree-provisioning, the lane-selection table, the SSOT-synthesis consolidation (charter §4b/§5), the readiness gate (§4c), and the disposition-ledger gate (§7). Hand-launching the same specialist agent *types* reproduces the fan-out but drops the consolidation discipline and can silently skip lanes (I skipped admin-ui and used my own briefing). On 2026-07-20, asked to "thoroughly and rigorously rereview" PR #1605, I hand-rolled a 7-agent fan-out; the user caught it immediately ("you didn't use our personal review harness — WTF") and had me stop and re-run through the skill.

**How to apply:** PR-review request → run `Skill(full-review, …)` from the main session (it fans out from there). Scouting inline first (head SHA, CI status, prior review notes, whether the head moved) is good prep, but the review itself goes through the skill, not a bespoke Agent fan-out. Same rule for the other packaged in-house skills — reach for the skill the house built, don't reconstruct it. [[no_agent_fanout_by_default]] [[project_review_harness_share_repo]]
