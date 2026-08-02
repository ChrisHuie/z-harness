---
name: feedback-black-ruff-format-disagreement
description: "RESOLVED by #1370 (merged 2026-06-10): black removed from pre-commit; ruff-format (via uv run, from uv.lock) is the single formatter, idempotent with make quality. Historical: black↔ruff oscillated on >120-char asserts, aborting commits."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: eea6a61f-fb14-405a-8a08-b5c73900ce1c
---

**STATUS: RESOLVED — verified 2026-06-11 against `.pre-commit-config.yaml`.** PR #1370 (PR 2 of #1234) removed the psf/black pre-commit repo and added a local `ruff-format` hook running `uv run ruff format` from uv.lock — the exact same binary+config `make quality` checks. One formatter, no disagreement, idempotent. black remains in dev deps ONLY as a CVE pin (GHSA-3936-cmfr-pm3m); `[tool.black]` in pyproject is vestigial.

**What this obsoletes:** `SKIP=black`, "run `uv run black --check` before every commit", and two-commit converge cycles. If a formatter aborts a commit now, it's ruff-format itself reformatting the staged file: `uv run ruff format <files>`, re-stage, recommit — converges in one pass.

**Historical trap (kept for recognition if a second formatter ever returns):** black and ruff-format genuinely oscillated on `assert <long_cond>, "msg"` over 120 chars — black wrapped the condition, ruff parenthesized the message; neither was idempotent on the other's output, and black reformatted PRE-EXISTING asserts in any touched file, aborting commits mid-hook (~5× in one #1307 session). The construct-level fix that satisfied both: restructure to a sub-120 single statement (`msg = ...; assert cond, msg` or hoist the condition to a local). Durable lesson: **two formatters with overlapping scope is a config defect — converge on one, in lockstep with the checker.**

Unverified residue: the old claim that CI ran `ruff format --check || true` (swallowing drift) predates #1372's pipeline rework — verify in `.github/workflows/test.yml` if formatting drift reappears on main.

Ties [[uv_frozen_for_commit_drift]], [[feedback_precommit_black_shifts_line_allowlists]] (line-shift trap survives, formatter-agnostic), [[backgrounded_commit_exit_code_masks_failure]].
