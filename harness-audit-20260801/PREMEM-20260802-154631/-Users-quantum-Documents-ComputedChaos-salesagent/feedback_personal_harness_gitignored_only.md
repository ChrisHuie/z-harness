---
name: feedback-personal-harness-gitignored-only
description: "The personal review harness is gitignored tooling that REVIEWS others' code — it must never mutate the shared repo or gate other contributors' CI. Convention enforcement lives in gitignored detectors the agent runs, never in repo guards."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 6c7592c2-6414-462e-9f1d-503db93b6bbf
---

When improving the personal review harness, ALL artifacts stay gitignored (`.claude/agents/`, `.claude/rules/private/`, the memory dir). Enforcement of a convention (FIXME-format, citation-freshness, etc.) belongs in a gitignored DETECTOR the review agent runs — NEVER in a `tests/unit/test_architecture_*.py` repo guard, which runs on every contributor's `make quality` and CI.

**Why:** 2026-07-09, asked to strengthen the harness ("enforce GH-issue, ratchet down"), I read "enforce" as "repo guard" and built + staged `tests/unit/test_architecture_fixme_format.py` on a feature branch. Chris halted it: "We are impacting others?? That isn't the goal of a personal harness." Correct — a repo guard fails other contributors' builds and is a shared-repo/project decision, out of bounds for personal tooling. Nothing was committed or pushed; fully reverted; the logic became a gitignored detector (`.claude/rules/private/detectors/fixme_format.py`) instead.

**How to apply:** Harness work = gitignored only. Before creating ANY file under `tests/`, `src/`, or another git-tracked path as part of harness work, STOP and run `git check-ignore <path>` — if it's tracked, that's a shared-repo change needing explicit, separate opt-in (normal PR + project buy-in), not a personal-harness task. "Strongest enforcement tier" for a personal harness = a gitignored detector wired into the agent (mirror `detectors/citation_freshness.py`), not a repo guard. The reviewer tier is the ceiling; it reviews, it never mutates or gates. See [[reference_harness_freshness_mechanisms]], [[feedback_user_owns_git_push]].
