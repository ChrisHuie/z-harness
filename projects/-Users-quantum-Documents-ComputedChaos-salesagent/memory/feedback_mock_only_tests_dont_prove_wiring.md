---
name: feedback-mock-only-tests-dont-prove-wiring
description: "Tests that patch the transport/dispatcher verify the mock, not the code. Every new error path needs ≥1 test per affected transport (REST TestClient, A2A on_message_send, MCP env.call_via) exercising the actual wire. Gold standard: tests/integration/test_a2a_error_responses.py::test_create_media_buy_validation_error_includes_errors_field."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: eea6a61f-fb14-405a-8a08-b5c73900ce1c
---

When a PR introduces a new error path (handler raising AdCPError, advisory `errors[]` on a success envelope, typed-error wrapping at a boundary), the reviewer bar is tests that exercise the **actual transport wire** end-to-end. Tests that mock the dispatcher / transport / handler-internals only verify that the mock returns what was configured — they do NOT prove the wiring between handler and transport works.

**The smell:** `patch('src.core.tools.X._impl')`, `mock.return_value = SomeError(...)`, then assert the mock was called. A wiring bug between wrapper and dispatcher passes green.

**The bar (gold standard):** `tests/integration/test_a2a_error_responses.py::test_create_media_buy_validation_error_includes_errors_field` (cite by NAME — the old line-164 citation drifted):
- Real `handler.on_message_send(params, ServerCallContext())` — the actual A2A entry point
- Real `Task` returned with `result.artifacts`; data extracted from the real artifact structure (TextPart + DataPart)
- Asserts wire shape: `success` False, `errors[]` present, `errors[0].code`, `errors[0].field`
- Auth/identity-resolution IS mocked (out of scope for an error-path test); the transport handler is NOT.

**Required for review readiness** — per new error path, ≥1 test per affected transport hitting the actual wire:
- **REST:** Starlette/FastAPI `TestClient`
- **A2A:** `handler.on_message_send(...)`
- **MCP:** `env.call_via(Transport.MCP, ...)`

**Detection (pre-review):** count NEW occurrences of `on_message_send(` / `call_via(Transport.MCP` / `TestClient(` in the diff vs. NEW error-path tests. Zero real-transport hits on an error-path PR = the gap is real. False-positive guard: helper/schema/business-logic unit tests legitimately don't need wire coverage — apply this to ERROR PATHS and HANDLER WIRING.

**Review feedback:** "Those tests verify that your mock returns what you configured it to return — they don't prove the path actually works."

Related: [[wire_envelope_policy]] (what to assert), [[feedback_a2a_wire_tests_must_drive_on_message_send]] (A2A specifics), P5/P9/P15 in [[reference_review_patterns]].
