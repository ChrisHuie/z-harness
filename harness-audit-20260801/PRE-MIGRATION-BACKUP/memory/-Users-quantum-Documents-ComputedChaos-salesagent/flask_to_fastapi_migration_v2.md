---
name: Flask to FastAPI v2.0.0 migration reference
description: v2.0.0 Flask→FastAPI migration is PAUSED (user confirmed 2026-06-11) after L0 completed 2026-04-19. Branch `feat/v2.0.0-flask-to-fastapi`. If it resumes — verify branch currency vs main AND check `.claude/notes/fastapi-unification-proposal.md` + the `refactor-fastapi-migration` branch first (approach may have shifted while paused).
type: reference
originSessionId: 6c161058-c104-4251-ac31-f7ebe095a7be
---
**STATUS: PAUSED — user confirmed 2026-06-11.** L0 completed 2026-04-19; no layers landed since. Do not treat this as active work; the plan below is the resume-state snapshot. All planning docs live in `.claude/notes/flask-to-fastapi/`.

**Start here:** `.claude/notes/flask-to-fastapi/CLAUDE.md` — entry-point document with 6 critical invariants, 8-layer (L0-L7) strategic layering table, and reading order.

**Source of truth for implementation readiness:** `.claude/notes/flask-to-fastapi/implementation-checklist.md`
**Execution plan:** `.claude/notes/flask-to-fastapi/execution-plan.md` — canonical layer-by-layer work breakdown.

**L0 STATUS: COMPLETE 2026-04-19 at tip `a2d3b350`** (33 work items landed, L0-00..L0-32 across commit range `d2841632..a2d3b350`). Next up: L1a (middleware cutover + session rename).

**v2.0 INCLUDES FULL ASYNC (2026-04-14 decision).** Breaking changes are OK on this branch as long as they don't impact AdCP schema or buyer agent interaction. The work is strategically layered across 8 layers (L0-L7):

| Layer | Status | What changes | Gate |
|---|---|---|---|
| L0 Foundation | **COMPLETE 2026-04-19** (`a2d3b350`) | Foundation modules §11.1-11.15 scaffolded, AdCP boundary protective tests, OAuth byte-immutability constants, test harness, fingerprint baselines, guards | 33/33 items landed |
| L1a Middleware cutover + session rename | **NEXT** | Session cookie rename, CSRF/Approximated middleware order, initial FastAPI middleware stack (version=7) | `MIDDLEWARE_STACK_VERSION == 7` |
| L1b OAuth/OIDC cutover | pending | Port 3-4 OAuth callback handlers (async def for Authlib); OIDC path `/admin/auth/oidc/callback` (NO tenant_id) | All byte-immutable URIs verified |
| L1c Legacy-admin redirect + first router ports | pending | `LegacyAdminRedirectMiddleware` INSIDE UnifiedAuth (D1 2026-04-16); first batch of sync router ports; version=8 | First waves of routers live |
| L1d Remaining router ports | pending | All remaining 22+ blueprints ported to sync APIRouter; `rg -w flask src/` trending to 0 | Flask imports only in deletable shims |
| L2 Flask removal + breaking env-var renames | pending | Delete Flask from pyproject/requirements; TrustedHost + SecurityHeaders (version=10); breaking env rename wave | `rg -w flask src/` = 0 |
| L3 Observability + release engineering | pending | structlog wiring, RequestID middleware (version=11), logfire instrumentation scaffolding, release prep | All middleware=11 |
| L4 Polish + v2.0.0 ship | pending | Sync SessionDep, DTO boundary, pydantic-settings extension, `render()` wrapper deletion, ContextManager refactor, v2.0.0 tag | v2.0.0 tagged |
| L5-L7 | deferred within v2.0 | Async SessionDep alias flip (L5b), mechanical `await` conversion (L5c-e), native refinements (L6), ship (L7) | — |

**Key insight:** Through L0-L4, admin handlers stay sync `def` with sync SQLAlchemy. Layer 5 (not Layer 4) introduces `SessionDep = Annotated[AsyncSession, Depends(get_session)]` — the alias flip is a 1-file change at L5b.

**18-agent pre-implementation audit (2026-04-14):** Two rounds of 6 parallel deep-think subagents verified all 12 technical assumptions, identified 4 critical gaps (integration conftest module-level create_app(), google_ad_manager.py top-level Flask import, pyproject.toml contradiction, check_route_conflicts.py hook), 9 document contradictions fixed, complete Flask dependency inventory (38+ production files, 32+ test files, 14 adapter/service Flask routes outside src/admin/).

**Active branch:** `feat/v2.0.0-flask-to-fastapi` (L0 complete at tip `a2d3b350`).

**AdCP boundary (FROZEN):** 16 MCP tools, 12 REST routes, A2A JSON-RPC, schema discovery, webhook payloads — all unchanged throughout all layers. 9 AdCP protective tests locked in at L0-02 (`745c920e`).

**Six critical invariants** (numbering matches `.claude/notes/flask-to-fastapi/CLAUDE.md` §Critical Invariants):
1. Templates use `{{ url_for('name', **params) }}` exclusively — for admin routes AND static assets. Admin routes have `name="admin_..."`; static mount is `name="static"`. L0-L4 use sync `def` handlers with `with get_db_session()` (bare `sessionmaker`, NO `scoped_session` — Decision D2). L5b flips SessionDep alias to `AsyncSession`.
2. Middleware order: Approximated BEFORE CSRF. Canonical stack grows by layer — L1a=7 → L1c=8 → L2=10 → L4+=11 via `MIDDLEWARE_STACK_VERSION` assertion (foundation-modules.md §11.36).
3. Templates use `{{ url_for('name', **params) }}` exclusively. `name="admin_<blueprint>_<endpoint>"`.
4. `APIRouter(redirect_slashes=True, include_in_schema=False)` for all admin routers.
5. `AdCPError` handler is Accept-aware (HTML for admin, JSON for API).
6. OAuth redirect URIs are byte-immutable contracts: `/admin/auth/google/callback`, `/admin/auth/oidc/callback` (NO `{tenant_id}`), `/admin/auth/gam/callback` (WITH `/admin` prefix). Byte-immutability verified at L0-11 (`ee99874d`).

**Derivative-audit reports** in `.claude/notes/flask-to-fastapi/async-audit/` — now L5+ implementation roadmap (not "v2.1 reference").
