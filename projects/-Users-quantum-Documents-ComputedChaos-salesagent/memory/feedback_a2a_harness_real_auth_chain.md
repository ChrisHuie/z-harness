---
name: feedback_a2a_harness_real_auth_chain
description: "A2A wire tests run the REAL token→DB→identity chain by populating ServerCallContext.state[AUTH_CONTEXT_STATE_KEY] with a real AuthContext — not by patching _resolve_a2a_identity/_get_auth_token. STATUS: pattern lives on the OPEN #1312 branch; main's harness _run_a2a_handler still uses the patch fallback until it merges."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: eea6a61f-fb14-405a-8a08-b5c73900ce1c
---

<!-- audit-2026-08-01 -->
> **STALE as of 2026-08-01.** Verified no longer accurate during the memory-consolidation audit. Kept for history; do not act on it.
> Evidence: gh pr view 1312 = MERGED 2026-06-16 (memory says OPEN). tests/harness/_base.py:665-678 now builds ServerCallContext(state={AUTH_CONTEXT_STATE_KEY: AuthContext(...)}) for the integration path; the lamb


(Status verified 2026-06-11: commit `cfe172cdf` ("drive the real A2A auth chain in _run_a2a_handler") is NOT on main — PR #1312 is still open. On main, `tests/harness/_base.py::_run_a2a_handler` still constructs a bare `ServerCallContext()` and patches the identity seams. The helper `tests/a2a_helpers.py::make_a2a_context` exists on main and the handler reads `context.state` — so individual tests can already use the real chain; the harness-wide adoption arrives with #1312. Don't re-implement it — that would conflict.)

For A2A wire tests, run the **real** token→DB→identity chain instead of patching `_resolve_a2a_identity` + `_get_auth_token` (the two seams reviewers flag). In integration mode (identity carries a real `auth_token`, persisted by `PrincipalFactory`), build the `AuthContext` the SDK call-context builder would have built:

```python
from src.core.auth_context import AUTH_CONTEXT_STATE_KEY, AuthContext
server_context = ServerCallContext(state={AUTH_CONTEXT_STATE_KEY: AuthContext(
    auth_token=auth_token,
    headers={"x-adcp-auth": auth_token, "x-adcp-tenant": tid},
)})
await handler.on_message_send(params, server_context)   # NO lambda patches
```

`on_message_send` reads `context.state[AUTH_CONTEXT_STATE_KEY]` via `_get_auth_token` / `_resolve_a2a_identity`, so the real `resolve_identity()` (token→DB→ResolvedIdentity) runs. This is the A2A analogue of MCP's `get_http_headers` seam. The lambda-patch path remains the unit-mode fallback (no real token).

**Adjacent gotcha:** the `test_architecture_wrapper_typed_params` guard requires A2A raw-wrapper params to be pure SDK types (no `| dict` unions); in the REST route, coerce dicts explicitly with `LibraryType.model_validate(body.field)` before the call.

Related: [[feedback_a2a_wire_tests_must_drive_on_message_send]], [[feedback_mock_only_tests_dont_prove_wiring]].
