---
name: reference_lazy_imports_load_bearing
description: Most function-local (lazy) imports in this codebase are load-bearing — verify before hoisting; hoisting commonly breaks tests/imports
metadata: 
  node_type: memory
  type: reference
  originSessionId: 8377e960-8e7a-4aba-8c4d-4aedb89a6629
---

In salesagent, most function-local ("lazy") imports are NOT removable style debt — they are load-bearing. Before hoisting one to module scope, check WHY it's lazy. Three common reasons here, each of which breaks if hoisted:

1. **Test-patch strategy (most common).** The unit suite patches dependencies at their *source module* — e.g. `patch("src.core.database.repositories.uow.ProductUoW")`, `patch("src.core.database.database_session.get_db_session")`. This only works if the *consumer* imports lazily (re-resolved per call). Hoisting binds the name at module-load, so the source patch no longer takes effect → tests fail. Proven on PR #1307: hoisting `ProductUoW` broke 10 tests, broadstreet `get_db_session`/`MediaBuyRepository` broke 4. **Verify first:** `grep -rn 'patch.*<source.module>\.<Name>' tests/` — if any hit, keep it lazy.
2. **Circular-import avoidance.** e.g. `src.admin.blueprints.creatives` imported lazily inside `src.core.tools.*` (core→admin is a cycle). Hoisting → ImportError at load.
3. **Heavy/optional-dependency deferral.** `src.services.dynamic_products`, `src.services.ai.*` — lazy keeps startup fast and optional deps optional. Hoisting forces eager load.

Cleanly hoistable: stdlib (`asyncio`, `concurrent.futures`) and pure transport helpers with no patch/cycle/perf coupling (`resolve_identity_from_context` — hoisted across 5 tool files in #1307, verified safe).

**Also:** hoisting shifts line numbers, which breaks line-keyed guard allowlists. After any hoist, regenerate `test_architecture_no_model_dump_in_impl.py` KNOWN_VIOLATIONS from the current AST (its finder `_find_model_dump_in_impl()`), don't hand-edit.

Ruff config IGNORES F821 ([[reference_ruff_f821_ignored]]) so a genuinely-broken hoist won't fail lint — only tests/import-checks catch it. Always import-test (`uv run python -c "import <module>"`) + run the patch-affected tests after hoisting.
