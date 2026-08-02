---
name: feedback_dependency_widen_pr_frozen_lock_masks
description: "A dependabot constraint-widening PR shows green CI but tested the OLD version — frozen lock + uv keep-locked masks the newly-permitted version; verify the TARGET version's actual import paths against the codebase before removing a deliberate ceiling pin"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 0b280b57-da1a-434b-9738-626587391c1d
---

A Dependabot PR that only widens a version constraint in `pyproject.toml` (e.g. `fastmcp <3.3.0` → `<3.5.0`) is almost always masked, and green CI proves nothing about the newly-permitted version.

**Why green is misleading:** this repo installs with `uv sync --frozen` (Dockerfile, Dockerfile.test) → installs exactly `uv.lock`. `uv` does NOT eagerly upgrade a locked version that still satisfies a widened range, and no CI job runs `uv lock --locked`/`--upgrade`. So a widened-only PR leaves the lock (and every test) on the OLD version. CI green = "the old version still works," which was never in question. The detonation is latent: the next `uv lock --upgrade` / dependabot lock refresh silently jumps to the new version.

**Why a deliberate ceiling pin exists:** the `<X` ceiling with a rationale comment is a guardrail against a known-incompatible upstream version. Widening it without doing the migration the ceiling protected = removing the guardrail. The comment going self-contradictory ("stay on 3.2.x" under a `<3.5.0` ceiling) is the tell.

**How to verify a dep bump with authority (do this, every time) — INSTALL, don't infer:**
1. Read the ceiling comment + `git log -S` the pin to recover WHY it was capped. (The comment's stated reason may be stale or never have been fully true — verify it, don't repeat it.)
2. Check whether a transitive consumer caps the package (e.g. does `adcp` require `fastmcp`?) — if capped, the widen may be moot.
3. **Resolve empirically in an isolated copy:** copy `pyproject.toml`+`uv.lock` to a scratch dir, apply the widen, run `uv lock --upgrade-package <pkg>` (allow builds; `timeout` is absent on this macOS). This proves (a) widen-alone is a NO-OP — uv keeps the locked version that still satisfies; only `--upgrade-package` moves it — and (b) whether the target resolves without transitive conflict.
4. **Install the target version in a throwaway venv and RUN the actual import lines** (`uv pip install '<pkg>==<target>'`; `from x.y import z` for every site). Do NOT trust a source-tree 404 at the git tag — built wheels ship DEPRECATION SHIM modules that don't appear in the obvious source path (a `fastmcp.tools.tool` 404 at the tag still imported fine on the installed 3.4.2 via a `__getattr__` shim returning identical objects). Source-tag existence is INFERENCE; the installed package is the OBSERVATION. A confident "breaks imports" claim from a tag 404 is a false BLOCKER.
5. Imports succeeding ≠ compatible. The real gate for a multi-minor jump is BEHAVIORAL: re-lock to the target and run the FULL suite un-frozen. A widen without re-lock does nothing.
6. Justify the upgrade against OUR usage, not the changelog: a touted CVE/feature fix may not apply (we were already on `starlette 1.3.1` ≥ the CVE floor; we use no `JWTVerifier`/`OAuthProxy`). Set a floor only if it captures something we actually need.

**Why:** dependency PRs are rare here and look trivial; "just update the package" is the trap — widening alone no-ops, and the safety question is answered by installing + running, never by reading the source tree. [[feedback_trace_flows_not_claims]] [[feedback_verify_before_asserting]] [[feedback_detecting_subagent_overconfidence]] [[uv_frozen_for_commit_drift]] [[run_all_tests_congratulations_masks_failures]]
