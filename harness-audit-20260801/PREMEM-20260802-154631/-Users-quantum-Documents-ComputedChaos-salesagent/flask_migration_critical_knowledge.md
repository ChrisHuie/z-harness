---
name: Flask→FastAPI migration critical knowledge
description: 18 key insights from the v2.0.0 deep-think planning + 3-round verification audit. Updated 2026-04-19 for 8-layer (L0-L7) scoping. Items 9, 13, 14, 15 are L5+ scope. L0 complete 2026-04-19 — items 2, 4, 6, 16 annotated with L0 landing commits.
type: project
originSessionId: 37f29673-26b8-4709-8bfb-07dab080266a
---
Critical knowledge from the v2.0.0 Flask→FastAPI migration planning (2026-04-11) and 3-round verification audit (2026-04-12). These are non-obvious facts discovered via 27+ subagent deep-think analyses and 14-subagent verification that would waste days if re-discovered.

**Why:** Every item below contradicts what a naive reading of the codebase or plan files would suggest. A fresh session that doesn't know these will implement the wrong thing.

**How to apply:** Before making any migration decision, check this list. If the decision touches databases, auth, templates, testing, or dependencies, one of these applies.

**L0 status (2026-04-19):** L0 complete at tip `a2d3b350` (33 items L0-00..L0-32). Items annotated below indicate which L0 work item addressed them. Items still applicable to L1a+ also noted.

1. **Fork-safety is the real rationale for Decision 2 (DatabaseConnection KEEP), NOT event-loop collision.** `run_all_services.py` uses `subprocess.Popen` (not `os.fork()`), so parent/child have independent interpreters — no shared event loop to collide with. The actual danger is SQLAlchemy pooled connection FD inheritance.

2. **OIDC callback path is `/admin/auth/oidc/callback` (NO tenant_id in URL).** Plan docs originally said `{tenant_id}` — WRONG. Tenant context comes from the session. GAM callback is `/admin/auth/gam/callback` (WITH `/admin` prefix), not `/auth/gam/callback`. **[VERIFIED at L0]** — L0-11 byte-immutable constants (`ee99874d`) codify all 3 paths; guard at `tests/unit/test_oauth_redirect_uris_immutable.py`.

3. **Factory-boy async shim overrides `_save`, NOT `_create`.** Overriding `_create` breaks `AccountFactory`'s existing `_create` override at `tests/factories/account.py:28-30`. [L5+ scope]

4. **FastAPI `RedirectResponse` defaults to 307 (not 302).** Flask's `redirect()` defaults to 302. 338 admin redirects would cause duplicate form submissions if not explicitly set to 302. **[MITIGATED at L0]** — L0-32 landed `admin_redirect()` helper (`4a4cbbf4`) at `src/admin/helpers/redirects.py` with 302 default. Still applies to L1a+ — every new redirect must use the helper, not raw `RedirectResponse`.

5. **CSRF is currently NOT enforced at all in Flask.** `CSRFProtect` is never initialized. `getCsrfToken()` is defined but never called. Adding any CSRF = behavioral change that breaks forms/fetches. Still applies to L1a (middleware cutover) — CSRFOriginMiddleware (§11.7) lands then; behavioral change risk is live.

6. **`tojson` Jinja filter does NOT exist in Starlette.** 30+ template expressions use it. Must register manually with `indent` kwarg support. **[DONE at L0]** — registered at L0-05 (`0c9ff48c`) in `src/admin/templating.py`.

7. **psycopg2-binary is the SOLE DB driver through L0-L4 (asyncpg enters at L5)** for Decisions 1 (Path B sync factory), 2 (pre-fork orchestrator), 9 (sync-bridge). Any plan reference to "remove psycopg2" before L5 is stale.

8. **Keep Alembic env.py sync with psycopg2.** DB-4 audit verified all 161 migrations are safe under greenlet bridge. Async rewrite adds risk for zero benefit. [Stays sync through L4+; L5 may rewrite if Spike 6 passes.]

9. **[L5+] Statement timeout event listener at database_session.py:139 uses `dbapi_conn.cursor()` — crashes under asyncpg.** Must use `connect_args={"server_settings": {"statement_timeout": "30000"}}` for async engine. Not relevant for L0-L4 sync handlers.

10. **SSE `/events` route is orphan code — DELETE, don't migrate.** Template says "use polling instead of EventSource". Zero `new EventSource(` in templates. Any plan reference to "port SSE" is stale. Applies to L1d router-port wave.

11. **`gam_inventory_service.py` has 8 Flask routes registered directly on the app** (not via blueprints) at lines 1484-1680, called from `src/admin/app.py:391`. NOT in the "22 blueprints" wave scope — must be explicitly ported in L1d's service-route sub-wave.

12. **6 files outside `src/admin/` import Flask:** `background_sync_service.py`, `gam_inventory_service.py` (8 sites), `gam_inventory_discovery.py`, `gam_reporting_api.py`, `mock_ad_server.py`, `google_ad_manager.py`. These must be addressed before Flask can be removed from dependencies at L2.

13. **[L5+] Product model has 5 `@property` methods that trigger lazy loads on 3 relationships** (`inventory_profile`, `tenant`, `adapter_config`). These are the highest-risk silent failures under async — tests pass with eager-loading code paths but production paths using different repo methods raise `MissingGreenlet`. Not relevant for L0-L4 sync handlers (lazy loads work fine in sync).

14. **[L5+] `asyncpg` bypasses SQLAlchemy's `json_serializer` parameter entirely** — uses its own native JSONB codec. Must register custom codec via `asyncpg.Connection.set_type_codec()`. Not relevant for L0-L4 (psycopg2 retained).

15. **[L5+] `onupdate=func.now()` columns (e.g., `updated_at`) become permanently stale after UPDATE+commit with `expire_on_commit=False`.** Cannot be fixed with ORM-side `default=` (that's INSERT only). Requires application-level timestamp or explicit `refresh()`. Only a concern with `expire_on_commit=False` in async sessions.

16. **`request.form.getlist()` has 20+ call sites for multi-value form fields.** FastAPI `Form()` returns only the LAST value. Must use `List[str] = Form()`. **[GUARDED at L0]** — SB-2 structural guard landed at the L0-01 batch scaffolding multi-value form handling. Still applies per-port at L1d: every router port must use `List[str] = Form()` for multi-value fields.

17. **`SameSite=None` is currently SET in production** (`src/admin/app.py:117`). Changing to `Lax` may break OIDC `form_post` callbacks. Needs investigation per-provider. **Still applies to L1a** — session cookie rename at L1a must preserve `SameSite=None` for OIDC compatibility.

18. **v2.0 includes full async, strategically layered across L0-L7 (2026-04-19 with L0 COMPLETE).** L0 foundation + L1a-d Flask removal + L2 native shape + L3 observability + L4 polish use sync `def` admin handlers with `with get_db_session()` (bare `sessionmaker`, NO `scoped_session` — Decision D2). L5b re-aliases `SessionDep` from sync `Session` to `AsyncSession` as a 1-file flip. L5c-L5e does mechanical `await` conversion. L6-L7 is native refinement + v2.0.0 ship. Items 9, 13, 14, 15 above are L5+ scope. Breaking changes OK on v2.0 branch as long as AdCP schema/buyer agent interaction is unchanged. L0 complete at `a2d3b350` — 33 items landed.
