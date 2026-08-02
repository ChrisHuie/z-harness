---
name: feedback-ground-protocol-work-in-spec-not-assumptions
description: "Protocol/AdCP behavior MUST be grounded in the spec text for the pinned version BEFORE implementing — not SDK codes, not internal contract items, not assumptions. PR"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: f05442f8-8f3d-4746-a9f7-7a5971e6b984
---

PR #1312 ("cache rejection envelopes for replay", #1303 contract item 7) was built **inverse to the AdCP idempotency spec**: it caches + replays REJECTIONS, but AdCP 3.0.1 mandates caching **successes only**, NEVER caching errors, and **re-executing** on retry-after-error (missing key → `INVALID_REQUEST`). The spec rule was in 3.0.0 (2026-04-26) and 3.0.1 (2026-04-28), ~3 weeks BEFORE #1303 was filed, with the project ALREADY pinned to 3.0.1 — so it was never stale, just never consulted. Two reviewers + 3 review rounds polished the wrong feature without questioning the premise.

**Why:** the root cause was grounding in ASSUMPTIONS and downstream artifacts (an internal contract item; the existence of an SDK error code) instead of the spec prose. An SDK shipping `IDEMPOTENCY_CONFLICT` does NOT tell you the caching model. An internal "contract item" is NOT the spec — it can itself be wrong.

**How to apply:**
- Before implementing/reviewing ANY AdCP/protocol behavior, READ the spec section for the pinned version and cite section+version. See [[reference_adcp_spec_grounding]] for where/how.
- Treat internal contract items (#1247/#1303-style gap lists) as REQUIRING a spec cross-check, never as ground truth.
- When verifying a foundational/inverting finding, go beyond one independent source: confirm against version-pinned snapshots + dates + the conformance storyboard before acting (this finding was confirmed across 3.0.0/3.0.1 doc snapshots, pin history, CHANGELOG, 2 WebFetches, 2 subagent reads).
- This is a recurring class of miss → escalate per [[feedback_escalate_recurring_lessons_to_guards]]: propose a CLAUDE.md gate requiring protocol-behavior PRs to cite spec section+version before implementation. Memory alone is the weakest lever.

Related: [[reference_adcp_sdk_spec_mapping]], [[feedback_root_cause_first]], [[feedback_verify_before_asserting]], [[feedback_detecting_subagent_overconfidence]].
