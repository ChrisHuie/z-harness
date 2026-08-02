---
name: feedback_author_artifacts_with_investigation_rigor
description: "Issues/artifacts authored for OTHERS (esp. good-first for interns) must be code-traced at HEAD with the same rigor as investigating a bug; compaction-summary / prior-session facts are CLAIMS to re-verify, not ground truth."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ce4d0c81-eb0d-403a-a061-646b112ab16a
---

When AUTHORING or CURATING GitHub artifacts that others will act on — new issues, issue splits, closing comments, and especially `good first issue`s an intern picks up cold — apply the SAME code-tracing rigor used to INVESTIGATE a bug. Verify every claim against current HEAD before publishing: spec version, the enclosing function / handler NAME (not just the line number), the file:line, the type shape (introspect the model), the provenance (`git log -S` pickaxe), and the proposed fix's correctness. A published artifact carrying an unverified fact transfers the error to the implementer, who builds on it in good faith — worse than no issue.

**Why:** In the #1259 decomposition I inherited two wrong facts from a compaction summary — "main is at adcp 5.7.0" (it was 4.3.0 / spec 3.0.1; the 5.7.0 bump was an OPEN PR) and "the line-1634 sibling that does account-coercion right is create_media_buy" (it is `_handle_sync_creatives_skill`; `_handle_create_media_buy_skill` forwards no `account` at all) — and propagated both into THREE new issues + a posted closing comment without re-tracing. The version error survived only by luck (the field also existed at 4.3.0); the sibling error would have sent an intern to the wrong handler. The user halted the session: "we are hurting the project and the implementers if we aren't approaching this with the same rigor we do investigating an issue initially ... actually trace the code so we are concise and help implementers not hurt them."

**How to apply:** Treat compaction summaries, prior-session assertions, and recalled [[feedback_trace_flows_not_claims]] memory as CLAIMS, not ground truth — re-open the file at HEAD and confirm the enclosing `def`, the line, the type (introspect: `uv run python -c "...model_fields..."`), and the provenance. For protocol/behavior issues, ground in the pinned-spec PROSE + storyboard via the spec-conformance harness BEFORE adding any spec citation — never fabricate grounding. A `good first issue` in a complex repo must have every design decision pre-made and a named copy-paste template test, or it is a hard issue wearing a good-first label. See [[feedback_verify_before_asserting]], [[feedback_final_reports_must_be_contributor_actionable]], [[reference_adcp_spec_grounding]].
