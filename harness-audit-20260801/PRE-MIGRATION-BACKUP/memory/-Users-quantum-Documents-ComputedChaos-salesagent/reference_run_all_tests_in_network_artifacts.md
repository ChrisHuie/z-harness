---
name: reference_run_all_tests_in_network_artifacts
description: "run_all_tests.sh in-network runs unit tests IN-CONTAINER where .github/ + docs/ are dockerignored, so doc/workflow-scanning architecture anchor tests + bdd [e2e_rest] variants fail there but pass on host/CI — branch-independent runner artifacts, not regressions"
metadata: 
  node_type: memory
  type: reference
  originSessionId: edce156d-2e5c-413c-8531-dfb06f4e5323
---

`./run_all_tests.sh` (default in-network mode) builds a Docker image and runs the suites INSIDE the container. `.dockerignore` strips `docs/` (line 85) and `.github/` (line 98) from the build context, so any test that scans those paths sees an empty tree in-container. This produces a stable set of ~16 failures that are runner artifacts, NOT real failures — they pass on host `tox -e unit` and in CI (which have the full tree):

- **Architecture anchor / obligation tests** that glob `docs/**` or `.github/workflows/*`. Verified examples: `test_architecture_obligation_coverage.py:27,72` globs `docs/test-obligations/*.md`; `test_architecture_postgres_image_anchor.py`, `test_architecture_uv_version_anchor.py`, `test_architecture_bdd_obligation_sync.py` scan `.github/workflows`. In-container the glob returns empty → the guard fails.
- **bdd `[e2e_rest]` variants** fail on their own live-server auth/tenant harness setup, while the **`[mcp]` / `[rest]` / `[a2a]` variants of the SAME scenario PASS**. The passing sibling transports are the discriminator: only `[e2e_rest]` failing ⇒ harness, not behavior.
- **~1 integration `caplog` test** (logfire↔caplog capture) shows empty captured logs while the underlying behavior passes.

Triage rule for a `run_all_tests.sh` non-zero exit: diff the failing set against these known artifacts; only NEW failures beyond them are real. Confirm each is branch-independent by BOTH provenance (`git log --oneline origin/main..HEAD -- <path>` shows the branch never touched the code) AND environment-specificity (passes on host `tox -e unit` or via a sibling transport). Do NOT rationalize — prove both, per [[feedback_verify_branch_runs_assert_head]]. The runner tail/exit lies about totals; per-suite JSON in `test-results/<tag>/` is authoritative — see [[run_all_tests_congratulations_masks_failures]]. Distinct from the fresh-DB gap in [[agentdb_persistent_schema_masks_fresh_db_failures]].
