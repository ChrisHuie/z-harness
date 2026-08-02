---
name: structural-guards-pin-production-paths
description: "AST-walking structural guards must pin functions actually called from production — pinning a dead-code helper makes the guard false confidence. Verify with `git grep \"<name>(\"` (open-paren = call sites). The original incident is FIXED in the guard; the principle is permanent."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: eea6a61f-fb14-405a-8a08-b5c73900ce1c
---

(Incident status verified 2026-06-11: `BOUNDARY_FUNCTIONS` in `tests/unit/test_architecture_error_envelope_two_layer.py` now correctly lists the three live production paths — `_translate_to_tool_error` (MCP), `AdCPRequestHandler._build_error_envelope` (A2A), `adcp_error_handler` (REST) — and the dead `_adcp_to_a2a_error` entry is gone (the function itself was deleted). The principle below is what this memory carries.)

When adding a `BOUNDARY_FUNCTIONS`, `MIGRATION_TARGETS`, or similar allowlist to a structural guard, every entry must point at a function **reachable from production code**. A guard pinning a function whose own docstring admits it's unused provides false confidence — a refactor breaking the REAL production path passes CI silently.

**Original incident (#1306 item #4, High):** the guard pinned `_adcp_to_a2a_error` (docstring: "currently unused by production code paths") while the real A2A envelope path, `AdCPRequestHandler._build_error_envelope` (called from `on_message_send`), was unguarded. Theme: "substrate shipped ahead of its production callers" — see [[feedback_substrate_prs_need_production_callers]].

**How to apply:**
- Adding a guard entry: trace the function backwards — `git grep "<function_name>(" src/` (open-paren finds CALL sites, not import lines). If the only hit is the definition, the function is dead; pinning it is meaningless.
- Reviewing a guard entry: same check; each allowlist entry needs ≥1 production call site outside `tests/`.
- Class methods: ensure the guard's AST walker indexes `FunctionDef` nodes inside `ClassDef`, not just module level — module-only walkers make "we can't pin this" look true when it's a 5-line fix.
- A helper that's "documented API for future call sites" with no current caller: delete it (dead code) or wire a production caller in the same PR.
