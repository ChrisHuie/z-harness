---
name: feedback_ci_optimization_silent_noop
description: "A conditional CI optimization (build cache, fast-path, skip-gate) can silently no-op via a working fallback while CI stays green — verify it ENGAGED from the job's runtime log, never from the check's pass/fail"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 74c7fe1b-89cd-4675-86d1-409bc93a1dfd
---

When reviewing a CI/infra PR that adds a **conditionally-gated optimization** — a build cache, a fast-path, a "skip if X" — a green pipeline does NOT prove the optimization works. If the gate is false at runtime, control falls through to a fallback (the `else`/plain path) that still succeeds, so every check passes while the feature is a **silent no-op**. The headline claim ("reuses layers", "warm build <30s") is unfulfilled and the green check masks it.

**Why:** gates often key on runtime state that isn't actually satisfied. Canonical example: `docker buildx build --cache-to type=gha` in a raw `run:` step gated on `[ -n "$ACTIONS_CACHE_URL" ] && [ -n "$ACTIONS_RUNTIME_TOKEN" ]` — those vars are GitHub-internal and are NOT exposed to plain `run:` steps (only JS actions see them, which is why `docker/build-push-action` works and a shell `docker buildx` does not). You must expose them via `crazy-max/ghaction-github-runtime`. Compounding: the GHA cache moved to **service v2** (v1 API sunset 2025-04-15, buildx ≥0.21), so the live var is `ACTIONS_RESULTS_URL`, not the v1 `ACTIONS_CACHE_URL` — gating on the v1 name fails even after the runtime is exposed.

**How to apply:**
1. Find the gate condition and the **distinct log marker each branch prints** (the `echo` before the real work).
2. Read the actual job runtime log (`gh api repos/O/R/actions/jobs/<id>/logs`) and see WHICH branch ran — the marker is decisive and [observed], unlike the green check.
3. Confirm the expected side effects, not just branch entry: for a cache, `importing cache`/`exporting cache`/`CACHED` lines and a reduced step time; their absence + an unchanged step duration = no-op.
4. The acceptance criterion that proves it ("run CI twice on an unchanged input, second run is faster") is usually an UNCHECKED test-plan box — that gap is the finding.

**Engagement ≠ benefit (the failure mode past the no-op).** Even after you confirm the optimization ENGAGED (cache imported, all stages `CACHED`), measure the WALL-CLOCK against the no-optimization baseline — a confirmed cache HIT can still deliver zero net speedup if a per-run tax dominates. Canonical: a `docker buildx` (`docker-container` driver) + `--cache-to type=gha` + `--load` setup, used to cache an image you then RUN, pays an image-materialization tax every run (`#NN exporting to docker image format` / `sending tarball`) that is ~equal to the compile the cache eliminates — so warm ≈ baseline while cold (the populate run, `mode=max`) is several× slower AND the cache (GBs) can blow the repo's 10 GB GHA budget, LRU-evicting other caches. This tax is unavoidable for "run-the-image" workloads (the plain `docker` driver writes straight to the daemon but can't do `type=gha`); the escalation is pre-building + pushing the image to a registry and `docker pull`-ing it (no buildx, no npm, no load tax). Lesson: build-CACHE patterns borrowed from a build-only job (e.g. `build-push-action` with no `--load`) do NOT transfer to a build-then-run job. Always compare warm-step time to the CURRENT no-PR step time, not just to the PR's own cold run.

This is the CI-feature instance of [[feedback_claimed_invariant_needs_failing_oracle]] (a prose claim with no mechanism that goes red) and of the masking-gotcha doctrine in [[run_all_tests_congratulations_masks_failures]]; verdicts come from running/reading the branch, per [[feedback_empirical_over_static_guard_assessment]].
