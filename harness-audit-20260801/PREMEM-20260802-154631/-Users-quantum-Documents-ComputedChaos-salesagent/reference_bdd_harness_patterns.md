---
name: reference-bdd-harness-patterns
description: Catalog of 24 BDD/harness patterns codified in PR
metadata: 
  node_type: memory
  type: reference
  originSessionId: acdcab63-786c-4cc7-9c58-54f2c30d2c24
---

PR #1335 (`feature/media-buy-refactoring-v3`) is the source of truth for BDD harness architecture. 1,477 passed + 5,372 xfailed + 0 failed at audit time. Apply these patterns when touching `tests/bdd/`, `tests/harness/`, or adding new use cases. Source: `pr/1335` ref.

**Core harness architecture:**

1. **BaseTestEnv single entrypoint** — `tests/harness/_base.py`. New tests subclass `IntegrationEnv`; use `EXTERNAL_PATCHES: dict`, `_configure_mocks()`. Detect violation: `grep "patch(" tests/<new>` > 2.
2. **`ctx["env"]` set by `_harness_env` autouse fixture** — `tests/bdd/conftest.py`. New UC needs branch in `_detect_uc()`. Missing UC → auto-xfail, not runtime error.
3. **`pytest_generate_tests` parametrizes `ctx` across 4 transports** — IMPL/A2A/MCP/REST. Never call `env.call_impl()` directly in When step (false-positive coverage).
4. **`dispatch_request(ctx, **kwargs)` is the transport-agnostic When primitive** — `tests/bdd/steps/generic/_dispatch.py`. Reads `ctx["transport"]`, handles error path.
5. **`_dispatch_partition` vs `_dispatch_resolution` are NOT interchangeable** — `_dispatch_partition` passes `{field: value}` raw; `_dispatch_resolution` translates partition names ("media_buy_ids_only", "partial", etc.) to concrete request params.
6. **`_STATUSLESS_SUCCESS_ATTRS` for response types without `.status`** — `tests/bdd/steps/generic/then_success.py:16-20`. Tuple (`formats`, `media_buy_deliveries`, `aggregated_totals`); extend when adding new UC success-collections (e.g., `products` for UC-001).
7. **Stacked `@then(parsers.re(...))` decorators map many phrasings to one function** — losing a decorator during merge breaks unrelated scenarios.

**xfail discipline (HIGH VALUE — most BDD failures avoided by this):**

8. **`pytest_runtest_makereport` auto-xfails `StepDefinitionNotFoundError` + `NotImplementedError`** — `tests/bdd/conftest.py:61-80`. Inline `pytest.xfail()` in step bodies is redundant.
9. **`_XFAIL_TAGS` (strict=True default) for scenario-level production gaps** — `tests/bdd/conftest.py:112-268`. Move per-scenario xfails here, keyed by `@T-UC-XXX-...` tag.
10. **Transport-aware selective xfails** — `is_mcp = "[mcp]" in nodeid or "[mcp-" in nodeid`. No scattered `pytest.mark.xfail` outside conftest.
11. **`BDD_E2E_ENABLED` opt-in** for 5th transport — must NOT be unconditionally true in tox/CI.
12. **`BDD_ALL_TRANSPORTS` deselects redundant strict-xfail duplicates** — speed optimization; strict-xfail nodes skip MCP/A2A/REST variants and keep IMPL.
13. **Tag markers auto-registered from feature files** — `pytest_configure` walks `tests/bdd/features/**/*.feature`. Don't list scenario tags in pyproject.toml.

**Identity + dispatch:**

14. **`identity_for(transport)` single identity source** — `tests/harness/_base.py:268-322`. No direct `ResolvedIdentity(...)` construction outside factories.
15. **MCP dispatch: patch `get_http_headers` in BOTH `src.core.transport_helpers` AND `src.core.mcp_auth_middleware`** — different import sites, both must be patched.
16. **REST dispatch: override `_require_auth_dep` per request** — `TestClient(app)` doesn't run real auth middleware path; must use FastAPI dependency override.
17. **A2A dispatch: patch `_resolve_a2a_identity` AND `_get_auth_token`** — both must return non-None or handler rejects pre-resolution.

**Factory + parallelism:**

18. **Factory-bound session enforced by `__enter__` assert** — no nested envs.
19. **`_register_media_buy_label` + UUID-suffix IDs for parallel safety** — never hardcode `mb-001`/`mb-002`; xdist runs scenarios in parallel.

**Tox / CI:**

20. **BDD tox env: 60s thread-based timeout + `--dist loadfile`** — NOT 120s signal-based (deadlocks xdist).
21. **`_account_resolution.py` shared helpers** — `ensure_tenant_principal()`, `validate_account_ref()`, `resolve_account_or_error()`. DRY across UC-002 + UC-006.

**Outcome dispatch + feature files:**

22. **Outcome dispatch with `Unknown outcome` sentinel** — `if outcome == X: ... elif ...: else: raise ValueError(f"Unknown outcome: {outcome}")`. The ValueError IS the failure-loud mechanism for feature/step drift.
23. **Feature files auto-generated** — `# DO NOT EDIT -- re-run: python scripts/compile_bdd.py`. Hand-edits without adcp-req SHA bump are violations.
24. **`pytest_plugins` registers step modules explicitly** — `tests/bdd/conftest.py:35-50`. Adding a domain step file without registering → `StepDefinitionNotFoundError`.

**Key cross-cutting lesson:** Every BDD test either passes or xfails — never just fails at runtime. If you see runtime failures in BDD, the root cause is usually one of: missing `_XFAIL_TAGS` entry, missing `_detect_uc` branch, missing `pytest_plugins` registration, or `_STATUSLESS_SUCCESS_ATTRS` doesn't include the response type's success collection.

**Common new-UC mistakes** (from #1274 BDD audit):
- New `given_*` step sets `ctx["tenant"]` without `ctx["principal"]` → cascades to `KeyError: 'principal'` downstream
- New Then step doesn't add elif branches to outcome dispatcher → `Unknown outcome` ValueError
- New `_STATUSLESS_SUCCESS_ATTRS` entry missing for new response type → `Status-less response X exposes none of expected success collections`
- Hardcoded media buy IDs collide under xdist parallel — use `_register_media_buy_label` + UUID

---
**Currency note (2026-06-11 drift audit):** core mechanisms verified live on main — auto-xfail hook (`tests/bdd/conftest.py::pytest_runtest_makereport`), `pytest_plugins` step-module registration, 13 harness env classes. PR #1384 (BDD 3.1: UC-011/019/026 re-rendered to AdCP 3.1, `scripts/compare_bdd_runs.py`) post-dates this catalog — re-verify feature-file specifics against the migrated files.
