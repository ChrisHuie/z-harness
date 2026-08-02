---
name: run-all-tests-congratulations-masks-failures
description: "Terminal-tail output of test runs is NOT the verdict. tox prints its own 'congratulations :)' banner when ITS envs exit 0 (e.g. the coverage env) regardless of suite failures; the authoritative record is per-suite JSON in test-results/<ts>/*.json. Corollaries: uv-secure failures often transient; caplog assertions flaky in-suite — assert behavior, not logs."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: eea6a61f-fb14-405a-8a08-b5c73900ce1c
---

(Mechanism corrected 2026-06-11: the `congratulations :)` string appears in NO repo file — it is **tox's own built-in success banner**, printed whenever the tox invocation's envs exit 0. The coverage-combine env succeeds as long as coverage data exists, regardless of test failures in other suites, so a tail-reading eye sees "congratulations" over a failed run. This session's verified state: `run_all_tests.sh` itself now parses the per-suite JSON and prints `ALL PASSED` or `FAILED:<list>` — better, but the principle is unchanged.)

**Never judge pass/fail from the terminal tail of any test runner.** The authoritative record is the per-suite JSON: `test-results/<ddmmyy_HHmm>/{unit,integration,e2e,admin,bdd}.json` (newest dir: `ls -dt test-results/*/ | head -1`). Parse each file's `summary` AND enumerate any test whose `outcome` is not in {passed, skipped, xfailed, xpassed}. This nearly masked 6 real failures once (3 mine). Reinforces [[feedback_run_full_suite_before_every_push]] — "make quality green ≠ suite green".

**Corollaries (still current):**
- `tox security` (uv-secure CVE scan) failures are often **transient/environmental** — a tooling crash (`Error: jiter raised exception`), not a CVE finding; it cleared on re-run with no dep change. Re-run before owning a non-CVE security-audit failure; if you changed no deps, it is not yours.
- **`caplog` log-assertion tests pass in isolation but fail in the full suite** — other tests leave global logging state behind (logging.disable, logger.disabled, propagation), so capture silently sees `[]`. The robust fix is to **assert on behavior, not captured logs** (spy the conversion ran; check the result). Ties [[feedback_mock_only_tests_dont_prove_wiring]].
