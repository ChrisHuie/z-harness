---
name: reference-salesagent-python-in-legacy
description: "CORRECTED 2026-07-20: the _legacy/ TS-top-level layout belongs to a diverged StellarPOC fork, NOT github.com/prebid/salesagent (which is top-level Python and ships src/core/exceptions.py). Mining-path map for both."
metadata: 
  node_type: memory
  type: reference
  originSessionId: 019ecd8b-d86f-4aad-810a-5d90043858ef
  modified: 2026-07-20T17:08:47.277Z
---

**CORRECTION (2026-07-20 audit, findings F47/F48 — verified via GitHub API + local origin):** the earlier version of this memory conflated two repos.

- The local clone at `/Users/quantum/Documents/GitHub/salesagent` has origin `StellarPOC/SalesAgent.git` (404/private as of 2026-07-20), last commit 2026-03-09. **It is a diverged fork**: top level is a TypeScript rewrite (package.json/tsconfig.json/packages/, BullMQ/Redis, PM2), with the Python impl under `_legacy/`. It contains **no** `exceptions.py` and does NOT contain the mining SHA c30e86e42.
- The real **`github.com/prebid/salesagent` is pure Python at top level** (`src/...`, 282 .py files, FastAPI since #1066 / 2026-03-02). It **never had** `_legacy/`, `packages/`, BullMQ, or Redis, and it **ships `src/core/exceptions.py`** (~41 typed error classes with recovery classification) continuously since 2026-03-02 — present at the docs' own mining SHA c30e86e42 (2026-07-07).
- Consequence for agentic-prebid docs: `durable-execution.md`, `BUILD-PLAN.md` (copy manifest `_legacy/src/...` paths), `STATE.md`, `EXECUTION.md` T7, and `surface-map.md`'s "exceptions.py CONFIRMED ABSENT" correction were grounded against the **fork**; `native-proto.md` mined the **real repo**. Flagged in the 2026-07-20 audit report — re-ground before any harvest.

Fork-path spine (valid inside the LOCAL FORK only; upstream equivalents live under top-level `src/` without the `_legacy/` prefix — re-verify upstream before use):
- HITL/state model: `_legacy/src/core/context_manager.py` + `_legacy/src/core/database/models.py` (`Context` / `WorkflowStep` / `ObjectWorkflowMapping`).
- FastMCP entry: `_legacy/src/core/main.py`; A2A server: `_legacy/src/a2a_server/adcp_a2a_server.py`; Flask HITL admin: `_legacy/src/admin/blueprints/workflows.py`.
- Neutral-core pattern: one async `_create_media_buy_impl` with thin MCP/A2A wrappers in `_legacy/src/core/tools/media_buy_create.py`.
- Conformance seed: `_legacy/src/core/testing_hooks.py`; mock ad server `_legacy/src/adapters/mock_ad_server.py`.

See [[project-substrate-ownership-strategy]], [[project-salesagent-lessons]].
