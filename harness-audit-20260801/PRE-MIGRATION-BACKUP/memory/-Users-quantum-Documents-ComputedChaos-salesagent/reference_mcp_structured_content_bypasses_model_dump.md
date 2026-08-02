---
name: reference-mcp-structured-content-bypasses-model-dump
description: "MCP raw-model ToolResult path serializes via pydantic_core.to_jsonable_python — honors Field(exclude=True) but BYPASSES method-level model_dump() overrides (Pattern #4). MCP wire ≠ model_dump output; A2A/REST call model_dump. Verified empirically 2026-06-10 on PR #1399."
metadata: 
  node_type: memory
  type: reference
  originSessionId: 2b4955a3-e7f1-4a7a-a570-d0d3e578732c
---

Most MCP tool wrappers pass the **raw response model** to `ToolResult(structured_content=response)`; fastmcp (3.2.0) serializes it with `pydantic_core.to_jsonable_python`, which:

- HONORS `Field(exclude=True)` and core-level `@model_serializer`
- BYPASSES method-level `def model_dump()` overrides (CLAUDE.md Pattern #4)
- does NOT exclude None → MCP wire carries `null` keys that A2A/REST drop

A2A (`_serialize_for_a2a`) and REST (`api_v1.py`) call `response.model_dump(mode="json")` → method overrides DO apply there. Exceptions: get_products pre-dumps; create_media_buy routes through a core-level wrap serializer.

**Consequences:**
1. Any field "excluded" only inside a `model_dump()` override still ships on the MCP wire (this is how per-item `status` leaked on MCP-only sync_creatives under adcp 4.3 — found in PR #1399 review).
2. Pattern-#4 nested-serialization fixes and empty-list stripping differ per transport (P5 divergence by construction).
3. "Wire verified via model_dump" claims are only valid for A2A/REST; for MCP, verify with `to_jsonable_python(model)` or real ToolResult bytes.

**How to apply:** when reviewing wire shape changes, check both serialization paths; to remove a field from ALL wires use `Field(exclude=True)`, never only a model_dump override. Ties [[wire_envelope_policy]], [[feedback_mock_only_tests_dont_prove_wiring]].
