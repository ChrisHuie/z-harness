---
name: pre-commit-mypy-adcp-pin
description: "RESOLVED by #1370: the mypy hook now runs `uv run mypy` from the project's uv.lock — no isolated venv, no additional_dependencies, no adcp pin to sync. Durable lesson: any ISOLATED-env hook with stub-providing deps must pin exactly to the runtime version, or mypy flags phantom errors."
metadata: 
  node_type: memory
  type: project
  originSessionId: eea6a61f-fb14-405a-8a08-b5c73900ce1c
---

<!-- audit-2026-08-01 -->
> **STALE as of 2026-08-01.** Verified no longer accurate during the memory-consolidation audit. Kept for history; do not act on it.
> Evidence: `.pre-commit-config.yaml` has no mirrors-mypy repo and no additional_dependencies mypy hook; line 166 reads 'Per ADR-001: mypy runs via `uv run` from uv.lock (PR 2 #1234)'. `gh pr view 1370` -> MERGED


**STATUS: RESOLVED — verified 2026-06-11 against `.pre-commit-config.yaml` (mypy hook: `entry: uv run mypy`, `language: system`).** PR #1370 (PR 2 of #1234) replaced mirrors-mypy + `additional_dependencies` with `uv run mypy`, so pre-commit mypy resolves adcp/sqlalchemy/fastmcp from the SAME uv.lock as the runtime venv. The config's own comment states this eliminated the version-drift class. There is no pin to synchronize anymore.

**Historical trap (the durable, transferable lesson):** when a type-checking hook runs in an ISOLATED env with its own dependency declaration, any drift between the hook's pin and the runtime pin produces phantom mypy errors — "attribute X not found", "missing required argument", "unused type: ignore" — fanning out from the mismatched stubs. Observed at scale: hook `adcp==3.2.0` vs runtime `adcp>=3.12.0` → 249 phantom errors; a `>=` pin then floated to a version with a restructured enum, breaking different sites. Exact `==` matching the installed runtime version was the only stable state.

**How to apply now:**
- Phantom mypy errors after branch switches or dep bumps → FIRST verify the env itself ([[uv_venv_corruption_reinstall]]); the isolated-env cause is gone, venv corruption is the remaining suspect.
- If anyone reintroduces an isolated-env hook with stub-providing deps: pin exactly (`==X.Y.Z`), update it in the same change as any pyproject bump, and `uv run pre-commit clean` after changing it.

Ties [[uv_frozen_for_commit_drift]] (same #1370 fix, lock side), [[reference_adcp_sdk_spec_mapping]].
