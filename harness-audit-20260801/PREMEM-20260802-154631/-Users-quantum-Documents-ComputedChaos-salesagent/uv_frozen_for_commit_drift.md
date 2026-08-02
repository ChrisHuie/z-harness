---
name: uv-frozen-for-commit-drift
description: "Pre-commit hooks with `entry: uv run ...` re-resolve uv.lock mid-commit → 'files were modified by this hook' aborts the commit. Fix: `UV_FROZEN=1 git commit`. (SKIP=black and the ruff-pin-ahead gotchas are obsolete since #1370 — all hooks now run from uv.lock.)"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: eea6a61f-fb14-405a-8a08-b5c73900ce1c
---

(Drift-audited 2026-06-11 against post-#1370 `.pre-commit-config.yaml`.)

When a `git commit` aborts and a pre-commit hook whose `entry` starts with `uv run` reports **"files were modified by this hook"** with no obvious code change, the modified file is almost always **uv.lock** — the hook's `uv run` prefix re-resolved it (newer dev-dep patch versions; pyproject unchanged). pre-commit fails any hook that modifies tracked files → the commit aborts. The FIRST uv-run hook in the sequence trips it.

**Diagnosis tells:** the staged diff is unrelated to the failing hook, and `git status` shows ` M uv.lock`. Confirm the drift is benign: CVE-pinned deps (aiohttp/authlib) are NOT in the version-change set — only dev/transitive patch bumps.

**Fix — commit with `UV_FROZEN=1`:**
```
git checkout origin/main -- uv.lock     # reset any existing drift first
UV_FROZEN=1 git commit -F - <<'EOF'
...message...
EOF
```
`UV_FROZEN=1` makes every `uv run` in the hooks use the lock as-is → no re-resolve → commit proceeds. Sanity-check first: `UV_FROZEN=1 uv run python -c "pass"`. Post-hoc `git checkout -- uv.lock` cannot unblock the commit — the abort happens mid-hook. pyproject is the source of truth; main's committed lock is authoritative — don't commit the dev-dep churn.

**Verify the commit landed** (backgrounded commits report the last stage's exit, not the commit's): `git rev-parse HEAD` shows a NEW sha + `git status` clean. [[backgrounded_commit_exit_code_masks_failure]]

**Obsolete since #1370 (kept for recognition):** the old advice appended `SKIP=black` — there is no black hook anymore (psf/black repo removed; `ruff-format` is the sole formatter hook, running via `uv run` from uv.lock). The sibling "pre-commit ruff pinned ahead of project ruff flags UP042" gotcha is likewise gone — the ruff hooks no longer have an independent pin. If "files were modified" cites a FORMATTER now, it's ruff-format actually reformatting your staged file: run `uv run ruff format <files>`, re-stage, recommit.

Ties [[feedback_run_full_suite_before_every_push]], [[precommit_mypy_adcp_pin]] (same #1370 fix, mypy side), [[feedback_black_ruff_format_disagreement]] (resolved era).
