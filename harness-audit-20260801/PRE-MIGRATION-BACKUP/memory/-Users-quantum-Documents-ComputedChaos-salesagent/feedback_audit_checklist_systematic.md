---
name: feedback-audit-checklist-systematic
description: "Cross-PR systematic audit checklist — 8 dimensions × every open PR. Don't claim \"clean/ready\" until every box is checked. Supersedes ad-hoc sweeps."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: acdcab63-786c-4cc7-9c58-54f2c30d2c24
---

# Systematic Cross-PR Audit Checklist

Before claiming any PR is "ready", "clean", or "fully addressed", run this 8-dimension checklist against EVERY open PR. Write the findings down. Re-sweep after every commit.

**Why:** I have repeatedly claimed PRs were "complete" only to discover (a) missed review comments (PR #1276 R8 missed), (b) missed patterns in sister PRs (#1313/14/15 needed same Path B), (c) fresh upstream drift (get-products-request fields appeared after our "clean" claim). Every miss had the same root cause: ad-hoc sweep with no written checklist, no symmetric verification, no post-fix re-sweep.

**How to apply:** Run before any "ready for handoff" / "all addressed" / "compaction-ready" claim. Run again immediately after every commit on any PR. Use subagents in parallel — one per PR — each running the full 8 dimensions and reporting structured findings.

---

## Dimension A — Review Feedback Completeness

Per PR, ALL THREE endpoints (a single one is insufficient):

1. `gh api repos/{owner}/{repo}/pulls/{pr}/reviews` — formal reviews
2. `gh api repos/{owner}/{repo}/issues/{pr}/comments` — top-level discussion
3. `gh api repos/{owner}/{repo}/pulls/{pr}/comments` — inline review comments

For every comment:
- Posted after our last commit? → unaddressed by definition
- Posted before? → diff-check that it's actually addressed in code
- Resolved/outdated marker ≠ proof of fix

See [[pr_review_audit_workflow]].

## Dimension B — CI / Failing Checks

Per PR:
- List FAILURE checks
- For each: peek the actual log line (not just check name)
- Classify: upstream drift / our regression / flaky / infrastructure
- Drift: confirm it's a known drift; if newer, add allowlist
- Regression: fix or report

## Dimension C — Code Patterns

For every diff hunk:
- Lazy imports inside function bodies (especially `src.core.exceptions`, `adcp.types`, `AdCPError` subclasses)
- Raw `dict` literals in `list[Error]` — must be `Error()` Pydantic model
- Redundant `recovery=` kwarg on typed `AdCPError` subclasses (defaults exist)
- Hardcoded `status_code=500` for codes that have mappings
- Inline issue refs in comments (`# fixes #1234`, `# per PR #...`, `(#1041)`)
- `list[Any]` for collections that should be `list[Error]` or other typed list
- Tautology asserts (`assert isinstance(x, T)` where `x: T` already, `assert True`)
- Vacuous `pytest.raises((A, B))` unions — narrow to the actual expected type
- Bare `except Exception: pass` — should be typed
- `except Exception` + `isinstance` chain — should be `except SpecificError`
- `ValueError` at boundary — should be `AdCPError` subclass (UNLESS inside Pydantic `@model_validator` — see [[feedback_valueerror_boundary_vs_internal]])
- Copy-paste structurally-similar blocks (DRY)
- `to_dict()` / `to_adcp_error()` divergent context serialization (must call `_serialize_context`)
- Honesty pattern violations: declaring `feature=True` for unimplemented features

## Dimension D — Architecture Guards (CLAUDE.md table)

Run `tox -e unit -- tests/unit/test_architecture_*` per PR branch. Or grep for known violations:
- `_impl` accepts `ResolvedIdentity` (not `Context`/`ToolContext`)
- `_impl` raises `AdCPError` (not `ToolError`)
- `_impl` has zero `fastmcp|a2a|starlette|fastapi` imports
- `_impl` returns models (no `.model_dump()` calls)
- Schemas extend `Library*` with inheritance (not duplicated)
- Transport wrappers forward every `_impl` parameter
- DB queries use repositories (not raw `select()`)
- Migrations have non-empty `upgrade()` AND `downgrade()`
- BDD: Then steps assert; not no-ops; not trivial; Given uses factories
- DRY ratchet doesn't grow (`.duplication-baseline`)
- Single migration head
- Workflow tenant isolation (`DBContext` join)
- Mock assertions use `assert_called_once_with()`
- Line-keyed allowlists in guard tests match actual file state (line shifts after refactor)

## Dimension E — Schema Drift

For EVERY schema cached in `schemas/v1/`:
- Fetch live `https://adcontextprotocol.org/schemas/latest/...`
- Diff field set against cached version
- Identify NEW fields not in `KNOWN_SCHEMA_LIBRARY_MISMATCHES` allowlist
- Identify REMOVED fields still in allowlist (stale)
- Compare `adcp` library version: `pyproject.toml` pin vs pre-commit mypy hook pin (must match per [[precommit_mypy_adcp_pin]])

## Dimension F — Cross-Transport Completeness

For every tool changed in PR:
- MCP wrapper exists, forwards all `_impl` params
- A2A `_raw` wrapper exists, forwards all params
- REST route exists (if applicable), forwards all params
- Error envelope shape symmetric across MCP/A2A/REST (status_code, error_code, recovery, message structure)
- `resolve_identity()` called in EVERY wrapper before `_impl`

## Dimension G — Local Quality Gates

Per branch, before claiming clean:
- `make quality` passes (format, lint, mypy, unit tests)
- Pre-commit ran twice with no diff on second run (black + ruff format converged per [[feedback_black_ruff_format_disagreement]])
- Integration tests pass IF refactor touched shared `_impl` or moved code
- Line-keyed allowlists re-derived AFTER pre-commit ran (per [[feedback_precommit_black_shifts_line_allowlists]])

## Dimension H — Process Discipline

- PR title uses conventional commits prefix (`feat:`/`fix:`/`refactor:`/`chore:`/`docs:`/`perf:`)
- Commit subjects ≤ 72 chars
- No new `# FIXME(salesagent-xxxx)` without ticket
- Existing FIXME counts only shrink (never grow)
- No `# removed for X` placeholder comments
- No issue/PR numbers in code comments (per [[feedback_no_issue_refs_in_comments]])

---

## Symmetric Agent Verification (per [[feedback_complete_claim_requires_full_pattern_enumeration]])

When dispatching subagents:
- An agent saying "found violations" → verify each finding (line numbers shift, agents hallucinate locations)
- An agent saying "clean / nothing found" → ALSO verify by sampling its claimed-scanned files
- Re-run after any commit; previously-clean sites can be reintroduced

## Post-Fix Re-Sweep

After ANY fix commit on ANY PR, immediately:
1. Re-run Dimensions A + B + G on that PR
2. Re-run Dimensions C + D for the workspace (new violations can leak in)
3. Update task list with anything new surfaced

## Stop Conditions

Do NOT use these to short-circuit the checklist:
- "Path B / scope decision" — that's about THIS fix, not investigation
- "Already verified by another agent" — verify agent verdicts symmetrically
- "Looks clean" — visual scan ≠ checklist completion
- "Same as last time" — drift is silent

Linked: [[feedback_complete_claim_requires_full_pattern_enumeration]], [[feedback_ready_claim_requires_fresh_pr_audit]], [[pr_review_audit_workflow]]
