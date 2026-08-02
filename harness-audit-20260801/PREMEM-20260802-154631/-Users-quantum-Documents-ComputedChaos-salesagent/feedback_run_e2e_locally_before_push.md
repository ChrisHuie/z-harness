---
name: feedback-run-e2e-locally-before-push
description: "When fixing an E2E test failure, run the full E2E suite locally via Docker before pushing — never iterate fixes through CI"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 5a27824e-a931-40cb-86b5-2266f74a3c56
---

When CI reports an E2E (or integration) test failure on a public PR, **start Docker and run the test locally before pushing each fix**. Do NOT iterate fixes through CI ("push, wait for CI, fix the next layer, repeat") on a public PR — every red run is visible and embarrassing for the user.

**Why:** On PR #1307 (error-emission architecture cleanup), one rotted E2E test had 5 distinct hidden bugs, each masked by an earlier short-circuit. I shipped 5 separate "fix" commits to CI, each red, because I only fixed one layer at a time and trusted unit tests to be sufficient. The user said: *"This is embarrassing because the PR is in public."* The first local Docker run after the 5th failure took ~3 minutes and surfaced the actual last layer cleanly — turning 5 public red CIs into 1 green push.

**How to apply:**
1. When the first E2E failure arrives on a PR, **stop pushing speculative fixes**. Don't push the next attempt until you've reproduced the failure locally and verified the fix passes the full E2E suite locally.
2. Use:
   ```bash
   make test-stack-up
   source .test-stack.env
   uv run pytest tests/e2e/ -v --tb=short --timeout=300
   make test-stack-down
   ```
3. The Docker stack takes ~10s to start, the full E2E suite ~3 min. Way cheaper than a CI cycle (4 min + queue + public visibility).
4. CLAUDE.md's `Test Infrastructure Decision Tree` says exactly this: *"When in doubt, use `./run_all_tests.sh`. It starts Docker, runs all suites, saves JSON results, and tears down."* I should default to this for any error-emission / boundary-shape / response-shape refactoring — not unit tests alone.
5. Generalize: for any refactoring that touches a transport boundary (MCP/A2A/REST), schema shape, or `_impl` return contract, run **integration + E2E** locally before push, not just `make quality`.

**Trigger pattern to remember:** If CI on a public PR fails twice on the same test file with different errors each time, that's the signal — you're peeling layers of rot; switch to local Docker immediately.

**Don't skip the unit suite "because integration passed" either.** Same PR, same session: after fixing a typed-raise site (`917cb1e59`), I ran integration + E2E locally and skipped re-running unit tests, assuming mypy clean + integration green was sufficient. CI failed on `test_architecture_no_model_dump_in_impl` because adding 7 lines shifted a `model_dump` allowlist entry from line 1249 → 1254. Any line-shifting change in `src/core/tools/` or `src/adapters/` can stale a per-line allowlist (`KNOWN_VIOLATIONS` in `tests/unit/test_architecture_no_model_dump_in_impl.py`, type-ignore baseline, etc.). The full unit suite catches these instantly and costs ~60s locally. **Run `make quality` after any production-code line shift, even if unit tests "shouldn't" be affected by the logic change.**

Related: [[ci_refactor_rollout_state]], [[flask_to_fastapi_migration_v2]] (similar boundary-shape work where this discipline matters).
