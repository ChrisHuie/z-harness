---
name: single-source-of-truth-requires-deleting-duplicates
description: "A \"single source of truth\" or \"consolidation\" PR must delete the duplicates in the same commit — otherwise the consolidation is fictional and the next person uses the wrong path."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: acdcab63-786c-4cc7-9c58-54f2c30d2c24
---

Claims like "single source of truth via `build_two_layer_error_envelope()`" or "extracted shared helper" or "consolidated boundary translation" require the duplicate sources to be **removed in the same PR**. If `_assert_mcp_envelope`, `_assert_a2a_envelope`, `_assert_rest_envelope` still exist as 2-line wrappers around `assert_envelope_shape`, the canonical helper's "Replaces the per-boundary helpers" docstring is not yet true. Similarly for table-vs-class duplication: `_ERROR_CODE_TO_STATUS` declaring `AUTH_REQUIRED→401` while `AdCPAuthorizationError.status_code=403` is a silent contradiction that wins at the table at runtime.

**Why:** A PR review (#1306 items #6, #7, #8, #17 — the "duplicate sources of truth" cross-cutting theme) showed that "consolidation" claims without deletion mislead future readers and reviewers, and let drift accumulate (the AUTH_REQUIRED conflict was a real bug — `AdCPAuthorizationError` raises surface as 401 instead of 403).

**How to apply:**
- When writing: if a PR title says "extract", "consolidate", "single source of truth", "DRY" — delete the deprecated paths in the same commit. Don't ship parallel implementations.
- When reviewing: grep for the old helper name across `src/` and `tests/` after a consolidation PR. If it's still referenced, the consolidation is incomplete. Use `git grep -c "<old_helper_name>"` — should be 1 (the definition) or 0 (also deleted).
- For wire-code tables: prefer **generating them from class attributes at module load** (`{cls.error_code: cls.status_code for cls in AdCPError.__subclasses__()}`) over manual maintenance. Eliminates drift potential.
- For runtime allowlists that duplicate `Literal[...]` types: use `typing.get_args(MyLiteral)` instead of hard-coded tuples.
