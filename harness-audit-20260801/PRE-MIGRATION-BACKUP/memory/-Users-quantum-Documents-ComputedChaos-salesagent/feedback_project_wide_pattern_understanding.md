---
name: feedback-project-wide-pattern-understanding
description: "Understand and explain patterns PROJECT-WIDE, not in single areas. A pattern grasped in one tool/transport/adapter is a hypothesis about the rest — map where it holds, where it intentionally diverges, and what enforces it, across all 3 transports, all adapters, all entity tools, all 5 test suites."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: eea6a61f-fb14-405a-8a08-b5c73900ce1c
---

(User directive, 2026-06-11: the harness must be focused on "understanding and explanation of patterns throughout the project not just single areas.")

This codebase is built on repeated cross-cutting shapes: every tool = MCP wrapper + A2A raw + REST route over one `_impl`; every adapter implements the same base interface; every entity has create/update/get/list/sync siblings; ~50 structural guards pin the invariants. A pattern understood in ONE cell of that matrix is a hypothesis about the other cells — and the cells genuinely diverge (MCP serializes via pydantic-core and bypasses `model_dump()` overrides while A2A/REST call it ([[reference_mcp_structured_content_bypasses_model_dump]]); harness wire capture differs per transport ([[harness_error_wire_per_transport_mechanics]]); adapters drift on capability messaging — P42).

**How to apply:**
- **When explaining "how X works":** first enumerate where X appears (`git grep`, the guards table in CLAUDE.md), then read 2-3 representative sites across DIFFERENT areas (a transport pair, two adapters, create+update siblings). The explanation should teach the project-wide shape: where the pattern holds, where it intentionally diverges and WHY, and which guard/test enforces it. "In media_buy_create it works like this" is a single-cell answer to a matrix question.
- **When learning a pattern from a fix or review:** the comprehension question is "where else does this project make this same decision?" — before the remedial question "where else is this bug?" ([[feedback_pattern_extraction]] is the remedial sweep; this memory is the comprehension default that should precede it).
- **When designing:** check how the sibling implementations already shape the pattern (working sibling test, sibling tool, sibling adapter) before inventing a variant — divergence is a decision to justify, not an accident to ship ([[feedback_wire_shape_change_systematic_sweep]] step 2).
- **When writing memory/docs:** record the pattern's SCOPE explicitly ("all three transports", "GAM only", "create+update but not sync") so the next reader inherits the map, not a single data point.

Provenance: the #1306/#1307 error-emission rework was exactly this — cross-transport normalization parity as a single project-wide pattern rather than per-transport fixes; #1389's honest-declaration boundary applied one capability-contract pattern across every adapter at once.

Related: [[feedback_root_cause_first]] (2nd derivative = the pattern's interaction surface), [[feedback_pattern_extraction]], [[feedback_complete_claim_requires_full_pattern_enumeration]].
