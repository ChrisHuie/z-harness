---
name: No `ruff --unsafe-fixes` or bulk linter auto-rewrites without per-site review
description: Never run `ruff --fix --unsafe-fixes`, `mypy --strict` mass-fixes, or any bulk auto-rewriter on source code during a migration or without explicit per-site approval. Linter warnings are signals to analyze, not mandates to auto-apply.
type: feedback
originSessionId: 1a81e02d-b77f-4875-831c-116906aee29d
---
**Rule:** do not run `ruff check --fix --unsafe-fixes`, `ruff check --fix` on new rules that touch source semantics (e.g. `UP040`, `UP046`, `UP047` on type aliases/generics), or any bulk auto-rewriter (e.g. `pyupgrade`, `black` with new target-version, `isort` with first-run config) against `src/` without hand-reviewing each site first.

**Why:** On 2026-04-14 during the v2.0 Flask→FastAPI migration, a scope-locked "TODAY defects" PR (3 small text edits: crontab path, fly-set-secrets.sh additions, ruff `target-version` bump) cascaded into unwanted rewrites of 3 production schema files because I ran `uv run ruff check . --fix --unsafe-fixes` to "clean up" 7 UP040/UP046/UP047 violations the py312 bump surfaced. The `type X = Y` rewrite (UP040) broke runtime: py312's `type` statement creates a non-subclassable, non-callable `TypeAliasType` — but `LibraryPackage` is subclassed in production code and `Property` is called as a constructor in 15+ tests. One unit test failed with `TypeError: 'typing.TypeAliasType' object is not callable`. I started reverting one-by-one while still touching source code, further expanding scope, until the user interrupted.

**How to apply:**
- **PR scope is a contract.** If the PR description says "3 defects, zero src/ changes," new lint violations surfaced by a config bump are NOT part of the scope. Either (a) add a targeted `extend-ignore`/`# noqa` with a FIXME pointing to a follow-up ticket, OR (b) defer the triggering config change (e.g. `target-version` bump) entirely to a separate follow-up PR where the new rules can be triaged.
- **`--unsafe-fixes` is opt-in for a reason.** Ruff marks fixes unsafe when they can change runtime semantics. For this codebase, UP040 (`TypeAlias` → `type`) is always unsafe on re-exports that participate in subclassing, constructor calls, or `is` identity checks — all common patterns for library-alias re-exports.
- **Before any bulk auto-fix in the migration window:** enumerate call-sites first (`grep "\bName\b" src/ tests/`), categorize each as annotation-only / subclassed / called / isinstance-checked, then apply the fix by hand to sites that are actually safe. Never trust the linter's "safe/unsafe" heuristic for library re-exports.
- **If a lint rule would rewrite 3+ files in source, STOP and ask.** That's a sign the rule adoption is a separate PR, not a drive-by cleanup.
- **TDD applies to linter-driven changes too.** Run the affected test files BEFORE committing any auto-fix. In this incident `tests/unit/test_adcp_36_schema_upgrade.py` would have caught the `TypeAliasType` break in seconds if I had run it before moving on.
- **Scope recovery protocol:** if caught mid-cascade, `git checkout -- <unwanted files>` (never `git reset --hard`) to revert only the out-of-scope files, leave intentional edits in place, verify `make quality` green on the reverted state, and commit only the originally-scoped changes.
