---
name: feedback-valueerror-boundary-vs-internal
description: ValueError migration rule for salesagent — boundary-facing migrates to typed AdCPError; internal-helper contracts stay as ValueError
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 5a27824e-a931-40cb-86b5-2266f74a3c56
---

When migrating `raise ValueError(...)` in salesagent (e.g., for the error-emission architecture work), apply this rule:

**Migrate to typed `AdCPError`** if the raise can escape to a transport boundary (MCP, A2A, or REST). Specifically:
- Function is `_impl`-suffixed, OR
- Function is directly callable from an MCP tool / A2A skill / REST route, OR
- Function is in `src/core/tools/` and called from `_impl` without an intervening try/except.

**Keep as `ValueError`** if the raise is a programmer-error invariant (an "internal contract"):
- "session is required for _validate_creatives_before_adapter_call" (param enforcement)
- "principal_id is required but was None - authentication invariant"
- "Adapter did not return package_id for package {i}" (adapter contract)
- "Identity is required for update_X" (auth invariant at boundary the wrapper enforces)

**Why:** Programmer-contract assertions should crash with a stack trace, not be wire-shaped into `VALIDATION_ERROR` (which would mis-classify a code bug as a buyer-fault). The boundary translator's `_translate_to_tool_error` wraps any escaped `ValueError` as a synthetic `AdCPValidationError` — that's the safety net for accidental misclassification.

**How to apply:** Before migrating a ValueError site, check the function's call graph. If only salesagent code calls it (and the call site already handles the error appropriately), it's internal. If a buyer-visible operation flows through it, it's boundary.

**Site distribution (PR 2 baseline):** 44 ValueErrors in `src/core/tools/` — 31 boundary, 13 internal. 82 in `src/adapters/` — estimate ~24 boundary, ~58 internal (per-file audit in sub-batch 5).

Captured architecturally in `.claude/notes/error-emission-architecture/PLAN-PR-2.md` D17 + §6.
