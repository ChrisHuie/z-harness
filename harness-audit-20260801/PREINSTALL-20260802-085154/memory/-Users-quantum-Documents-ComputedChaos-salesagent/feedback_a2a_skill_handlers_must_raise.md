---
name: a2a-skill-handlers-must-raise
description: "A2A skill handlers must raise typed AdCPError, never return custom error dicts — the boundary envelope builder runs at dispatch, not at the handler."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: acdcab63-786c-4cc7-9c58-54f2c30d2c24
---

A2A `_handle_*_skill` functions in `src/a2a_server/adcp_a2a_server.py` must raise typed `AdCPError` subclasses (e.g., `AdCPValidationError`) on every error path. Never `return` a custom error dict, even one built with the SDK's `adcp_error(...)` helper. The outer dispatcher (`_handle_explicit_skill` → `_build_failed_skill_result` → `_build_error_envelope`) is the single place the two-layer envelope gets assembled.

**Why:** `_serialize_for_a2a` derives `success` from `errors[]` presence on the returned object. A flat dict like `{"success": False, "message": ...}` gets classified as a successful Task carrying a fake "success" artifact. A dict spread of `**adcp_error(...)` emits the `errors[]` half but not the envelope-level `adcp_error` key — the storyboard runner then synthesizes `MCP_ERROR` and erases the real code. Both bypasses make buyers unable to see the real wire code. A PR review (item #1, Critical) found 5 such bypass paths.

**How to apply:** Reviewing a new `_handle_*_skill` or a new validation branch inside one:
- `return {...}` on an error path → **fail review**; rewrite as `raise AdCPValidationError(...)` (or the right typed subclass)
- The only legitimate return shape from a skill handler is the **success** payload; errors leave via `raise`
- If a missing-params check needs an early return, raise instead — the outer try/except routes correctly
- Cross-check by grepping `_handle_.*_skill` for the pattern `return {.*success.*False` or `return {.*adcp_error\(`
