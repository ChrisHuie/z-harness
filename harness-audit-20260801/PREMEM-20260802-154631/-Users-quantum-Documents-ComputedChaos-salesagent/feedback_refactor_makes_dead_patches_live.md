---
name: feedback-refactor-makes-dead-patches-live
description: "Moving a call into a helper in another module makes previously-DEAD mock.patch targets live; their stale return values then take effect. Run the FULL integration suite after such refactors, not just unit + a few targeted files."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 8377e960-8e7a-4aba-8c4d-4aedb89a6629
---

When a refactor moves a function call into a helper that lives in a **different module** (changing where the callee is resolved), `mock.patch` targets at the *new* resolution site become effective — **including patches that were previously dead (no-ops)**, and their return values (possibly the wrong type) now take effect.

**Why:** PR #1307 added `resolve_principal_or_raise` in `auth.py` and routed `_update_media_buy_impl`'s principal lookup through it. Five integration tests had `patch("src.core.auth.get_principal_object", return_value=<ORM Principal>)`. Before the refactor that patch was a **no-op** for the update path (update.py used `from src.core.auth import get_principal_object` — its own module-level reference, not `auth.get_principal_object`), so the tests actually resolved the principal via the real DB lookup (which returns a Pydantic `schemas.Principal`). After the refactor the lookup went through `auth.get_principal_object` (the patched attribute) → the patch went **live** → returned a session-detached ORM instance → `DetachedInstanceError`. Unit suite (4722) + 3 targeted integration files were green locally; only the **full integration suite** (CI: Integration creative + media-buy) caught it.

**How to apply:**
1. **`from x import y` binds a reference at import time.** Patching `x.y` does NOT affect a module that did `from x import y` (it holds the original object). Patching `module_that_imported.y` does. When you move a call into a helper in module `x`, patches now resolve against `x.y`, not the caller's namespace. Grep for patches of the function at BOTH the old caller-module site AND the definition-module site; verify each patch's return value matches the real contract (e.g., Pydantic schema vs detached ORM).
2. **Run the full integration suite locally before any push-ready claim** — not just unit + a handful of files. A test that "passes" may be passing via a dead patch falling back to the real call; the refactor flips that. Use the agent-db (see [[reference_agentdb_port_mismatch]]); creative-agent `*_live`/generative tests ERROR locally without the agent stack — that's environmental, not a regression.
3. Ties [[feedback_run_full_suite_before_every_push]] and [[feedback_mock_only_tests_dont_prove_wiring]].
