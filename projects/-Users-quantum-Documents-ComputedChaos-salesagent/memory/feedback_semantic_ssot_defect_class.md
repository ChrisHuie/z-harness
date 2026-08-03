---
name: feedback_semantic_ssot_defect_class
description: Semantic single-source-of-truth is a defect class distinct from textual-clone DRY; our structural guards are blind to it; the fix commit is the least-reviewed code
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 4f291949-c81e-4b42-b7d9-7f886d58db14
---

**Semantic SSOT** — one *concept* materialized in two places — is a first-class defect category, NOT covered by the textual-clone DRY guard (pylint R0801) or any AST guard. The structural guards model *shape* (layer imports, clone blocks, migration heads, param forwarding); they are blind to: one constant defined as two literals, one invariant computed two ways, one concept named three ways, one shared-signature change not swept across callers, one decision duplicated across two exception handlers with its detection coupled to a driver's message text in both (R0801 sees two blocks that are semantically identical but textually different — different `create()` args in the middle — exactly its blind spot). The fix is one home for the decision; the failing-oracle counterpart is [[feedback_claimed_invariant_needs_failing_oracle]].

**Why:** #1312's entire round-4 finding cluster was semantic-SSOT, and every guard + `make quality` passed it:
- 1a — replay-window expiry computed two ways (stored `expires_at` vs recompute from a *different row's* `created_at`).
- 1b/1c — `86400` TTL as two independent literals; the `[1,3600]` clamp written twice.
- 2 — a new `account_id=None` default silently re-scoped an existing caller (signature change, blast radius unswept).
- 6 — one wire-payload concept named `raw_arguments`/`raw_wire_parameters`/`raw_wire_body` across MCP/A2A/REST.
R0801 misses these because they are not textually similar (1a/1b/6) or fall under its line threshold (1c). The `.duplication-baseline` even *dropped* while 1c was introduced.

**Two compounding process facts from the same PR:**
1. **The fix commit is the least-reviewed, highest-risk code.** The "genuinely clean" multi-agent verdict was rendered ~3h *before* the commit that introduced half the round-4 findings existed. Fixes relocate logic into new files/seams (move-policy-out → new `idempotency_policy.py` with the doubled clamp), so they re-introduce the same class one file over. A "clean/addressed" verdict must be **re-earned on the actual final head**, never inherited across a new commit.
2. **"Addressed" ≠ `make quality`.** This session's own fix had a real semantic bug (a media_buys→accounts FK the test setup didn't seed) that unit + every structural guard passed — only the **full integration suite** caught it. `make quality` is the floor; `./run_all_tests.sh ci` (or the targeted integration subset) is the gate before any addressed/ready claim.

**How to apply:**
- When a finding is semantic-SSOT (constant / invariant / name / swept-callers), **sweep for siblings** — the guard won't, and the same concept usually recurs across transports/paths/files. Then [[feedback_escalate_recurring_lessons_to_guards]]: if AST-detectable (e.g. a magic-number registry, a schema-derived allowlist), it becomes a guard; if not (one-invariant-two-ways), it becomes a standing review lens.
- After fixing a review round, re-run the FULL review (not just the cited site) on the final head, and the full suite — before claiming addressed. [[feedback_run_full_suite_before_every_push]] [[feedback_ready_claim_requires_fresh_pr_audit]]
- Prefer **deriving** guard allowlists from the source of truth (e.g. `CREATE_SPEC_FIELDS = model_fields − documented_exclusions`) over hand-lists, so a new field is required-until-justified instead of silently uncovered. [[feedback_guard_matcher_completeness]]
- Keep this discipline in LOCAL tooling (`.claude/rules/private/`, memory) — NOT the shared repo `CLAUDE.md`, which is for all contributors, not one harness setup. [[feedback_agent_team_execution_model]]
