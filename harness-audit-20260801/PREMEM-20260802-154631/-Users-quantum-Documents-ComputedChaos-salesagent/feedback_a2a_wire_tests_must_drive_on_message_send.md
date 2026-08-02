---
name: feedback-a2a-wire-tests-must-drive-on-message-send
description: "A2A wire tests must drive handler.on_message_send and assert on result.artifacts[0] (DataPart), not call _handle_explicit_skill directly — handler-internal calls never exercise the production envelope construction (_build_error_envelope). P28 refinement."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: eea6a61f-fb14-405a-8a08-b5c73900ce1c
---

(Mechanism re-verified 2026-06-11: the old translation layer `_adcp_to_a2a_error` has been DELETED; the production A2A error path is now `AdCPRequestHandler._build_error_envelope` → `build_two_layer_error_envelope`, called from `on_message_send`. The rule survives the refactor — only the reason evolved.)

A2A wire-level tests must drive `handler.on_message_send(params, ServerCallContext(...))` and assert on `result.artifacts[0]` (the DataPart). Tests calling `handler._handle_explicit_skill(...)` directly verify only the handler's raise behavior — they never exercise the envelope construction that buyers actually receive.

**Why (current mechanics):** envelope assembly happens in `on_message_send`'s error handling via `_build_error_envelope`. A handler-internal test cannot observe what lands on the wire — historically this masked a real production loss (the deleted `_adcp_to_a2a_error` dropped `field`/`suggestion`, and handler-level tests stayed green through it). The class of bug is "translation/assembly layer between handler and wire" — only driving the real entry point covers it.

**Recurring violation shape (P28+P29):** a test with "wire" / "boundary" / "end-to-end" in its name or docstring that calls `_handle_explicit_skill` directly. Fix: extend to drive `on_message_send` and assert on the artifact DataPart — or rename so the docstring matches what's actually verified (e.g. `TestA2AHandlerExplicitSkillReraises`).

**Gold standard:** `tests/integration/test_a2a_error_responses.py::test_create_media_buy_validation_error_includes_errors_field` (by name; line citations drift).

Related: [[wire_envelope_policy]], [[feedback_a2a_harness_real_auth_chain]] (run the real auth chain too), [[feedback_mock_only_tests_dont_prove_wiring]], [[reference_review_patterns]] (P28, P29).
