---
name: ci-pre-commit-refactor-rollout-state
description: "CI/pre-commit refactor (issue #1234) in flight. 2026-06-11: #1370 (PR2 uv.lock) + #1372 (PR3 pipeline) MERGED; #1379 (BDD shards) + #1390 (PR4 hook relocation) OPEN. Planning corpus ONLY on branch docs/ci-refactor-planning."
metadata: 
  node_type: memory
  type: project
  originSessionId: eea6a61f-fb14-405a-8a08-b5c73900ce1c
---

<!-- audit-2026-08-01 -->
> **STALE as of 2026-08-01.** Verified no longer accurate during the memory-consolidation audit. Kept for history; do not act on it.
> Evidence: gh pr view: #1379 MERGED 2026-06-12, #1390 MERGED 2026-06-16 (memory says both OPEN); #1370 and #1372 merged as stated; gh issue view 1234 = CLOSED. Nothing is in flight.


Issue #1234 CI/pre-commit refactor — status verified 2026-06-11 via `gh pr view`:

- **MERGED:** #1370 = PR 2 (uv.lock single source of truth; adds `pytest-xdist`+`pytest-randomly` to dev group; REMOVES psf/black pre-commit repo + adds `id: ruff-format`; black kept in deps only as a CVE pin) — on main at fd6899446. #1372 = PR 3 (authoritative CI pipeline with frozen required checks; composite actions `_pytest`/`_setup-env`/`_postgres`; touches tox.ini + both workflows).
- **OPEN:** #1379 = PR 3.2 (parallel BDD CI shards, `pytest -n auto --dist=loadfile`, stacked on PR 3). #1390 = PR 4 (relocate pre-commit hooks to appropriate layers; touches `tests/unit/_architecture_helpers.py` — a distinct file from `_ast_helpers.py`).
- **Do NOT carve side fixes** for the bdd `-n auto`/missing-xdist breakage or the SKIP=black/formatter duality — they are covered by #1370+#1379 and a side fix conflicts.
- **The planning corpus lives ONLY on branch `docs/ci-refactor-planning`** (+origin), NOT in feature working trees. Read via `git show docs/ci-refactor-planning:<path>` — RESUME-HERE.md, EXECUTIVE-SUMMARY.md, pr1–pr6 briefings, verify scripts.
- Executor reminders that still bind: harden-runner uses `disable-sudo-and-containers: true` (CVE-2025-32955 mitigation), never `disable-sudo: true`; the mirrors-mypy migration is an isolated-env import-resolution fix, not a "deprecation"; user owns push / `gh pr create` / branch-protection flips ([[feedback_user_owns_git_push]]).

(Condensed 2026-06-11 from the 2026-04-25 planning snapshot — full history lives on the planning branch.)
