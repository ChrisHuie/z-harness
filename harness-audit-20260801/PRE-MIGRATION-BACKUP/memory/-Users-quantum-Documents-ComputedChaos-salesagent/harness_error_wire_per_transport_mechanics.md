---
name: harness-error-wire-per-transport-mechanics
description: "MediaBuyCreateEnv.call_via captures REAL error wire only for REST. MCP's call_mcp calls the tool fn directly so a raised AdCPError propagates un-translated (no ToolError → wire_error_envelope is None); pin MCP via a real fastmcp Client + json.loads(str(ToolError)) + assert_envelope_shape. A2A's call_a2a routes through *_raw which raises, so the dispatcher SYNTHESIZES the envelope (build_two_layer_error_envelope) — it does NOT exercise on_message_send/_serialize_for_a2a framing; to pin field/suggestion survival drive handler.on_message_send and assert on the failed-Task artifact. In-memory MCP Client tests must patch get_http_headers at ALL 4 bind sites (auth, transport_helpers, testing_hooks, mcp_auth_middleware) — testing_hooks is the one that turns x-test-session-id into testing_ctx.test_session_id (the setup-checklist bypass)."
metadata: 
  node_type: memory
  type: reference
  originSessionId: 8377e960-8e7a-4aba-8c4d-4aedb89a6629
---

For **error-envelope wire tests** (asserting the two-layer `UNSUPPORTED_FEATURE` /
any AdCPError envelope reaches the buyer), the canonical harness does NOT uniformly
capture real wire across transports. Verified on PR #1389 (cost ~30 tool calls):

- **REST** — `MediaBuyCreateEnv.call_via(Transport.REST)` → `RestDispatcher` returns
  `wire_error_envelope = response.json()` (the real HTTP body). ✓ Use the harness.
- **MCP** — `call_mcp` does `create_media_buy(ctx=...)` **directly**; the wrapper only
  catches `ValidationError`, so an `AdCPError` (e.g. `AdCPCapabilityNotSupportedError`)
  **propagates raw**. `McpDispatcher._envelope_from_mcp_error` only handles `ToolError`
  → `wire_error_envelope` is **None**. The AdCPError→ToolError translation lives at the
  FastMCP **server** layer, which the direct call bypasses. Pin MCP via a real
  `async with Client(mcp)` + `pytest.raises(ToolError)` + `json.loads(str(exc))` +
  `assert_envelope_shape` (structural, not `str(exc)` substring — the request body alone
  can satisfy substrings).
- **A2A** — `call_a2a` routes through `create_media_buy_raw`, which **raises**;
  `A2ADispatcher` then `_wire_envelope_from_exception` finds no stashed
  `_wire_error_envelope` and falls back to **synthesized** `build_two_layer_error_envelope`.
  That pins envelope *content* but NOT the `on_message_send` → failed-`Task` → artifact
  `DataPart` framing (where `_serialize_for_a2a` can drop `field`/`suggestion`). To pin
  framing, drive `handler.on_message_send(SendMessageRequest, ServerCallContext)` and
  assert on `result.artifacts[0]` via `extract_data_from_artifact`.

**In-memory MCP Client header injection:** four modules each `from fastmcp.server.dependencies
import get_http_headers` (`src.core.auth`, `transport_helpers`, `testing_hooks`,
`mcp_auth_middleware`) — patch ALL four (a `from..import` binds the name locally; patching
the source misses them). `testing_hooks.get_http_headers` is the one that reads
`x-test-session-id` into `testing_ctx.test_session_id`, which `_create_media_buy_impl`
checks to **skip `validate_setup_complete`** (media_buy_create.py: `if not testing_ctx.dry_run
and not testing_ctx.test_session_id:`). Miss it → `VALIDATION_ERROR "Setup incomplete"`
instead of your target error. A2A populates the same via `AuthContext(headers=...)`.

`assert_envelope_shape(target, code, *, recovery, message_substr, check_mcp_tool_error)`
has **no `field=` param** — pin `field`/`suggestion` on `errors[0]` separately. Ties
[[wire_envelope_policy]], [[feedback_verify_reviewer_fixes_against_code]] (a reviewer's
"just use call_via for all transports" rests on a false premise for MCP/A2A error wire).
