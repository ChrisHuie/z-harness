---
name: reference_release_jobs_invisible_to_pr_ci
description: Release/publish workflow jobs gated on release_created never run in PR CI — green CI ≠ working release pipeline; source-trace registry auth + per-job permissions
metadata: 
  node_type: memory
  type: reference
  originSessionId: ea34d4fe-2dab-42a4-aeb6-8ef378888d48
---

On a CI/supply-chain PR, jobs gated on `if: ${{ needs.release-please.outputs.release_created }}` (build-and-push, sign-and-attest, publish) run ONLY on a release-PR merge to main — **never on a pull_request**. So a fully green PR check-list (verified via `gh pr checks`) does NOT exercise them. "CI green" is no evidence the release pipeline works. The check list having zero release-pipeline entries is the tell.

Verify these jobs by SOURCE-TRACING, not CI status:
- **Registry-push auth**: `cosign sign` and `actions/attest-build-provenance --push-to-registry` BOTH need registry write creds (a `docker/login-action` step) even when `packages: write` + `id-token: write` are granted. OIDC covers the *signing identity* (Fulcio/Rekor), not the registry push. cosign uses go-containerregistry `DefaultKeychain` (reads `~/.docker/config.json` only); `actions/attest` → `@sigstore/oci` `getRegistryCredentials()` throws without docker config. A job that signs/attests but has no login is broken. cosign's failure can be SILENT if wrapped in `cmd && break` under `set -e` (errexit is exempt inside `&&` lists — proven). attest fails loudly.
- **Per-job permissions sufficiency**: `github/codeql-action/upload-sarif` requires `security-events: write`. Trivy/CodeQL/zizmor SARIF uploads all need it. Cross-check: grep every `upload-sarif` use and confirm each job grants it — the lone exception is the bug.
- **Gate ordering**: a Trivy "gate" in a job that `needs:` the push job runs AFTER the image (incl `:latest`) is published → it detects-after-ship, does not gate. Scan before push (build with `push:false`/`load:true`, scan, then push).
- **D47-style CI-green gates**: a poll-for-CI-conclusion loop must budget more than the real CI wall-clock (pull actual durations via `gh api .../runs`); a 3-min budget vs 13-27-min CI times out every release.
- **Self-modifying workflows**: `GITHUB_TOKEN` CANNOT push changes to `.github/workflows/*.yml` (no grantable `workflows` permission; needs a PAT/App token with workflow scope). A workflow that seds workflow files + `gh pr create`s with GITHUB_TOKEN is dead. Also watch a `sed 's/X/Y/'` that matches its OWN pattern literal.

A presence-only structural guard (`assert "cosign sign" in text`) passes green through every one of these — it asserts a string exists, not that the job is wired/permitted. See [[feedback_claimed_invariant_needs_failing_oracle]], [[feedback_fitness_functions_pattern]], [[reference_adcp_spec_grounding]].
