---
name: substrate-prs-need-production-callers
description: New helpers in substrate PRs must have at least one production caller in the same PR — unit tests + aspirational docstrings without a caller mean the helper has nothing to enforce and the next layer up can drift.
metadata: 
  node_type: memory
  type: feedback
  originSessionId: acdcab63-786c-4cc7-9c58-54f2c30d2c24
---

A "substrate" PR (foundation for follow-up work) that introduces a new helper — boundary translator, single-source-of-truth function, canonical persistence path — must wire **at least one production caller** in the same PR. Shipping helper + unit tests + aspirational docstring + zero `src/` callers means: future readers can't tell what the contract actually is, the byte-identical-by-construction claim has nothing to enforce, and the layer above stacks on a fiction.

**Why:** A PR review (#1306 items #4, #11) found two cases: `_adcp_to_a2a_error` and `ContextManager.fail_step` both shipped with unit tests, aspirational docstrings ("Boundary translators AND ContextManager.fail_step both call this"), and zero live callers. Production failed-workflow persistence in `order_approval_service.py` and GAM background polling **still flow through the old path**. The byte-identical claim cannot be verified because there's no production caller to compare bytes against. Cross-cutting theme from that review: "substrate shipped ahead of its production callers in two places."

**How to apply:**
- When writing a substrate PR: after defining a new helper, grep `src/` (not `tests/`) for its name. If the only hit is the definition, you have homework — wire one real caller before shipping.
- When reviewing a substrate PR: `git grep -c <new_helper_name> src/` should return ≥ 2 (definition + at least one caller). If only 1, push back with "ship one production caller in this PR; otherwise the contract has nothing to enforce."
- Exceptions are rare and should be explicit: a helper that's deliberately staged for a follow-up PR should carry a `# FIXME(salesagent-...): wire production caller in <PR>` comment so the gap is visible in code review.
- Architecture / structural guards that pin a helper as "the production path" are particularly dangerous when there's no production caller — the guard is checking dead code (#1306 item #4).
