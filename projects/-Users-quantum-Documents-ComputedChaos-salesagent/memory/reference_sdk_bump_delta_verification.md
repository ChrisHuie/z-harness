---
name: reference_sdk_bump_delta_verification
description: "How to verify an adcp/SDK BUMP PR completely: introspect the model+enum surface in BOTH old and new versions, diff field-by-field, and trace every UN-handled change against src/ — a 'fix-what-broke' bump silently misses non-breaking schema changes that no test catches."
metadata: 
  node_type: memory
  type: reference
  originSessionId: 19e2139f-fbec-46df-9212-9e41f0fc4925
---

A dependency/SDK **bump** PR (distinct from a constraint *widen* — see [[feedback_dependency_widen_pr_frozen_lock_masks]]) is typically scoped "fix every failure the bump introduced." That scope is blind to changes that don't break a test: new optional fields, a field going Optional, a removed field, an enum renamed/re-valued, a response's nested type swapped. Green CI + green unit only prove the touched paths; the authoritative check is a **full model-surface delta**.

**The technique (do this for any adcp bump review):**
1. Extract the SDK symbols the codebase imports: `grep -rhoE "from adcp[a-z_.]* import.*" src/ | ...` → dedupe.
2. Introspect the wire-bearing types + enums in BOTH versions and diff. Old version via an ephemeral env: `uv run --no-project --with "adcp==<old>" python introspect.py`; new via the project `uv run --frozen`. For each model dump `{field: (is_required, annotation)}`; for each enum dump `{members, base-mro}`. Diff → per type: `+fields / -fields / REQ-changed / TYPE-changed / enum member+base changes`.
3. For EVERY change the PR did **not** explicitly handle, trace codebase exposure (each is a hypothesis to falsify):
   - **removed field** → `grep -rn "<field>" src/` (AttributeError risk if read).
   - **enum rename/swap** (e.g. `SignalCatalogType`→`SignalAvailabilityType`) → compare member VALUES in both versions; identical values ⇒ `.value` comparisons still work (benign, comment may be stale). Different values ⇒ real break.
   - **new required field** → the construction sites must supply it (or a defaulted subclass must).
   - **type change on a response/nested field** (e.g. `accounts: list[Account]`→`list[AccountWithAuthorization]`) → check whether a local subclass REDECLARES that field (absorbs it) or relies on the parent (exposed).
   - **field went Optional** → grep reads; add `or []`/None-guards where iterated.
   - **new optional field** → forward-compat passthrough is fine, but confirm the wrapper doesn't ADVERTISE behavior it doesn't implement (the accept-and-ignore-with-promising-docstring trap).
4. Execute the offline gate yourself (`uv run --frozen pytest tests/unit/ -q` + the spec-version/contract/inheritance guards) — don't infer from CI.

**Two gotchas this technique surfaced (both generalize):**
- **SDK codegen can DIVERGE from the spec and FORCE a value.** adcp made a spec-OPTIONAL, deprecated `status` field REQUIRED and narrowed it to `Literal['completed']`; made a spec-NULLABLE `confirmed_at` non-nullable. The codebase is then forced to code to the SDK (only one value constructs), even though the spec says otherwise — so the wire can carry a spec-questionable value that no local choice can fix. Ground severity in whether a conformance storyboard GRADES it (often graded-silent: only async storyboards gated on a `comply_test_controller` the impl doesn't implement). SDK is the cross-check, spec is the authority ([[reference_adcp_spec_grounding]]).
- **Container git behavior is not reproducible with a throwaway image.** A "test-infra" change that silently falls back from `git ls-files` to a filesystem walk makes structural-guard scans depend on UNTRACKED local files (stale worktrees, reports, gitignored dirs). A quick `docker run --rm -v "$PWD:/app" alpine/git ls-files` may SUCCEED while the real `Dockerfile.test` container FAILS `git ls-files` (dubious-ownership; `safe.directory` unset) and triggers the fallback — verify in the ACTUAL flow (`./run_all_tests.sh` → read per-suite JSON), where the false failures (version-anchor guards scanning `.claude/worktrees/*/pyproject.toml`) actually appear. Prefer `git config --global --add safe.directory /app` over an unsound walk; guard-infra changes need a self-test ([[feedback_guard_matcher_completeness]], [[feedback_empirical_over_static_guard_assessment]]).
