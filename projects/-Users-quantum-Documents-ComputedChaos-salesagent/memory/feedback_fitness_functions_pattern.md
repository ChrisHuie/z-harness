---
name: Architectural fitness functions for repo invariants; external tools for workflow security
description: User adopts AST/YAML pytest "fitness function" tests for project-specific invariants AND zizmor/pinact/Scorecard for workflow/supply-chain security
type: feedback
originSessionId: e00ee904-0012-465b-87c9-3c8478b4835d
---
The salesagent codebase calls AST-walking pytest tests in `tests/unit/test_architecture_*.py` "structural guards" but the published industry name is "architectural fitness functions" (Ford/Parsons/Kua, *Building Evolutionary Architectures*, O'Reilly). Use the published term in ADRs and commit messages where appropriate; "structural guard" is fine for casual references.

**Why:** The user explicitly chose to expand the pattern to ~50+ guards across the CI/pre-commit refactor. Validated as Fortune-50 standard for repo invariants — Salesforce, Shopify, pydantic, Django ecosystems all use it. Internal evidence: the project already has 27 such guards.

**How to apply:**
- **Pytest fitness function** for: Python code-shape invariants (no banned APIs, layering, AST patterns), project-specific YAML invariants (CLAUDE.md table consistency, hook coverage map validity, ADR existence with `## Status`), cross-file anchor consistency (.python-version ↔ mypy.ini ↔ Dockerfile), governance-file existence with content checks
- **External tools** for workflow/supply-chain security: zizmor (workflow security linter), pinact (action SHA-pinning enforcement), OpenSSF Scorecard (composite signal), CodeQL (Python SAST), pip-audit (CVE check). These run as CI workflows; bespoke pytest re-implementation is a path-dependence anti-pattern
- **Verify-scripts** ONLY for: admin-scope `gh api` calls (branch protection, repo settings), runtime timing benchmarks (latency assertions), integration-suite regression (PG17 cross-version), one-shot bootstrap validation

When in doubt: if the invariant is statically checkable from local files, it's a fitness function. If it depends on external state or requires a real subprocess (zizmor, pinact), it's a CI tool. If it depends on admin scope or runtime measurement, it's a verify-script.
