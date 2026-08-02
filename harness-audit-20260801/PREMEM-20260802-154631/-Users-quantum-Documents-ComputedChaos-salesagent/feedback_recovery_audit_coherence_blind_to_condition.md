---
name: feedback_recovery_audit_coherence_blind_to_condition
description: recovery_audit checks code↔recovery COHERENCE only — blind to whether the code+recovery fit the actual error CONDITION; ground condition→recovery in spec prose
metadata: 
  node_type: memory
  type: feedback
  originSessionId: d72c06fb-9dda-461c-acd4-ef41ebf80a46
  modified: 2026-07-23T23:41:24.241Z
---

A code-coherent `recovery` value can still be CONDITION-wrong, and both `recovery_audit` AND a strong human reviewer will pass it.

On PR #1698 (targeting-rehydration advisory), a PERMANENT seller-repair-required corruption was labeled `recovery="transient"`. `SERVICE_UNAVAILABLE↔transient` is the canonical pair, so `recovery_audit` reported CLEAN (41 classes) — it only validates the code↔recovery PAIR against the pinned `CODE_RECOVERY` table. It cannot see whether the CODE (and thus its coherent recovery) fits the CONDITION. The reviewer also missed it across TWO rounds — he REQUESTED `transient`, grounding in code-coherence + "matches the sibling advisory." Only spec-PROSE condition→recovery grounding caught it: the pinned `error.json` recovery enum says `terminal = "requires human action"`, `transient = "retry after delay"`; a corrupt persisted row never self-heals on retry → terminal. The cited sibling (`creatives/_processing.py`) actually uses `terminal` for server-side DEFECTS (:435/716) and `transient` only for temporary OUTAGES (:447/728) — so "matches the sibling" was a false premise (surface match, not condition match).

**Why:** this is the founding harness miss-class — validate against a PROXY (the coherence table / an SDK code / a sibling's surface use) instead of the SOURCE (spec condition semantics). A "clean" `recovery_audit` means *coherent*, NOT *correct*.

**How to apply:**
- A CLEAN `recovery_audit` (or CODE_RECOVERY-table match) never closes the recovery question — always run the condition→recovery spec-PROSE check (review-spec-conformance reading `error.json` enum descriptions + `error-handling.mdx`/`transport-errors.mdx §Recovery Behavior`) for any new/changed error emission.
- When a sibling is cited as precedent for a recovery/code value, match the CONDITION to the sibling's SPECIFIC branch, not "the sibling uses this value somewhere." An error-wire/surface reviewer will confirm the surface match and be wrong.
- If the coherent recovery is spec-wrong, the ROOT is usually the CODE (here `SERVICE_UNAVAILABLE` framed a permanent defect as a transient outage); fixing recovery cleanly means reclassifying the code (`CONFIGURATION_ERROR`/terminal or a platform code).
- Candidate harness upgrade: `recovery_audit` should print a standing caveat that it is coherence-only and does not grade condition-appropriateness, so a CLEAN run is never mistaken for "recovery is correct."

Links: [[reference_adcp_spec_grounding]], [[feedback_claimed_invariant_needs_failing_oracle]], [[reference_harness_freshness_mechanisms]], [[feedback_trace_flows_not_claims]].
