---
name: run-full-suite-before-every-push
description: "HARD RULE — `make quality` (unit suite) before EVERY push; AND the AUTHORITATIVE `./run_all_tests.sh ci` (creative-agent stack + admin + harness + fresh DB) before ANY done/ready/\"zero failures\" claim about a PR. make quality is NOT the full suite — it skips tests/harness, tests/admin, tests/e2e, and creative-agent integration. Treating make-quality-green as suite-green has burned the user repeatedly (PR #1274 guards, PR #1307 — 7 reviewer-found failures in skipped suites)."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: acdcab63-786c-4cc7-9c58-54f2c30d2c24
---

**HARD STOP RULE. NO EXCEPTIONS.**

Before any push (or before announcing a commit is ready to push), run **`make quality`** locally. The full unit suite. Not:
- "the test I wrote for this change"
- "the test file touching this code"
- "the test in the area I edited"
- "the integration tests in the same dir"

The full unit suite. Every time. Even when the change "feels local".

## Why this rule has teeth

Architecture guards (`tests/unit/test_architecture_*.py`) scan the WHOLE source tree on every run. They catch:
- New raw `select(Model)` outside repository allowlist
- New `session.add()` in integration test files (factory rule)
- New `# type: ignore` not in baseline
- New duplicate-step BDD code
- ~25 other AST-scanning invariants per CLAUDE.md "Structural Guards" table

A change to **one file** can introduce **one violation** that fails the structural guard in **a completely different test file**. Running the per-file test won't catch it. Only the full suite does.

Specific PR #1274 case (this rule exists because of this):
- Edited `src/core/config_loader.py` to add `_ensure_default_principal` with `select(Principal)`.
- Edited `tests/integration/test_default_tenant_principal_seed.py` with `session.add(Tenant(...))`.
- Ran `pytest tests/integration/test_default_tenant_principal_seed.py` — 5/5 pass.
- Did NOT run `make quality`.
- Pushed.
- CI failed: `test_architecture_no_raw_select`, `test_violation_count_matches`, `test_architecture_repository_pattern.test_no_new_session_add_in_tests`.

All three were catchable in **64 seconds** by running `make quality`.

### make quality is NOT the full suite — PR #1307 case (the worse recurrence)

`make quality` runs `pytest tests/unit/` only. It does NOT run:
- `tests/harness/` (harness-contract tests — collected under tox's unit env, not `tests/unit/`)
- `tests/admin/` (admin Flask suite)
- `tests/e2e/`
- integration tests that need the live creative-agent stack or a FRESH DB
- **network-gated unit tests** — even inside `tests/unit/`, tests that fetch live data are silently skipped offline. `test_pydantic_schema_alignment.py` downloads `/schemas/latest/...` from adcontextprotocol.org (cache-first); offline → `pytest.skip`, so make quality collected ~120 fewer unit tests than the networked `ci` run. When the live AdCP schema drifts ahead of the pinned SDK (e.g. get-products-request gained `push_notification_config`), these fail in the full run but are invisible to make quality. (Fix when it's a real spec-vs-library mismatch: add the field to `KNOWN_SCHEMA_LIBRARY_MISMATCHES`.)
- the **security audit** — `./run_all_tests.sh` runs `scripts/security-audit.sh` (uv-secure dependency-CVE scan) as a separate `FAILURES` gate; NO pytest run (make quality OR CI) shows it. It surfaced aiohttp 3.13.5 + authlib 1.6.11 CVEs that were red on the branch base. Dep-vuln failures are pre-existing/external by nature (verify at base; not your code) — fix by bumping to the advisory's named patch version (prefer the minimal patch over a minor jump on auth-critical libs like authlib). BUT uv-secure ALSO fails TRANSIENTLY with a tooling crash (`Error: jiter raised exception`, NOT a CVE finding) — that clears on re-run (PR #1274: red one `ci` pass, "262 deps safe" the very next, no dep change). RE-RUN the security audit before owning a non-CVE uv-secure failure; don't fix what was a flake.

On PR #1307 I ran `make quality` + targeted/`tox -e integration` against the **persistent agent-db**, saw ~1974 pass, and declared the PR "code-complete / gold-standard / zero code-attributable failures." The reviewer then ran the authoritative `./run_all_tests.sh ci` (which brings up the creative-agent stack via `scripts/creative-agent-stack.sh up`, then runs admin + harness) and found **7 real failures** — 2 harness-contract, 2 integration (fresh-DB `creative_agents` UndefinedTable, masked by my persistent agent-db — see [[agentdb_persistent_schema_masks_fresh_db_failures]]), 3 admin retroactive-push. Every one lived in a suite my partial runs skipped. The architecture work itself also created real second-order debt the same authoritative pass surfaced.

This is worse than #1274 because I *had this rule already* and still equated "make quality green" with "done." The sharpening: `make quality` before every push (cheap, catches unit + guards), but before ANY "done / ready-for-review / code-complete / zero failures" claim about a PR, run **`./run_all_tests.sh ci`** — the only invocation that exercises all five suites + the live stack + a fresh DB. "make quality is green" is NOT "the suite is green," and "zero code-attributable failures" from a suite subset is itself a banned ready-claim ([[feedback_no_ready_claims]]).

**CI is ALSO not the green gate (PR #1307, verified in `.github/workflows/test.yml`):** CI runs smoke + unit + integration + bdd + e2e but **does NOT run `tests/admin/` at all**, and its unit job runs `pytest tests/unit/` **without `tests/harness/`** (local `tox -e unit` runs both). So admin-suite and harness-contract failures are invisible to CI — the PR can show all-green while `./run_all_tests.sh ci` (the only invocation that runs admin + harness + a fresh-migrated stack DB) is red. A green PR check rollup is NOT evidence the suite passes; verify with the local authoritative runner. Corollary: BDD contracts can be present-but-unenforced — `tests/bdd/conftest.py` auto-xfails any scenario with missing step definitions, so a written `.feature` scenario (e.g. UC-004 adapter-partial-degrade) sits in the xfail pile (2756 xfailed on one run) and gates nothing until its steps are implemented.

## The right flow

```bash
# Make changes
# Edit files...

# REQUIRED before any push
make quality

# If green, commit + push
# If red, fix and re-run. Repeat until green.
```

For changes that touch integration paths (DB, transport, harness), also run:
```bash
eval $(.claude/skills/agent-db/agent-db.sh up)
tox -e integration
```

For changes that touch BDD:
```bash
eval $(.claude/skills/agent-db/agent-db.sh up)
uv run pytest tests/bdd/ --tb=no -q  # ~15min
```

## When you feel the pull to skip

You will feel "this change is small, just my tests cover it, skip the full suite." That feeling is the exact failure mode this rule exists to block. ALL the historical failures of this pattern felt that way at the time. The cost of running `make quality` is ~60 seconds. The cost of pushing broken code is:
- Burning the user's trust
- Triggering 8-15 min of CI
- Forcing the user to come back and ask you to fix it
- Adding noise to the PR's check rollup that reviewers see

Always pay the 60 seconds.

## Verification phrasing

Before claiming a change is ready or asking the user to push, the only valid statement is:

> "Ran `make quality` locally — N passed, 0 failed."

Anything else (including "tests I added pass", "no errors in my changes", "looks good locally") is NOT the standard.

## See also

- [[feedback_truth_over_optimism]] — meta rule on hedged-correct vs confident-wrong
- [[feedback_verify_before_asserting]] — observe before claiming
- [[feedback_run_e2e_locally_before_push]] — E2E-specific corollary for live-stack changes
- [[feedback_no_ready_claims]] — replace "ready" with raw state observation
