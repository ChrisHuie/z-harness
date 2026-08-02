---
name: feedback-planning-doc-location
description: "Plans default to CHAT-ONLY. When a file is warranted: .claude/notes/<slug>/ (never docs/plans/). That dir holds TRACKED content — git ls-files before rm. Session notes stay local; never push them to feature PRs."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: eea6a61f-fb14-405a-8a08-b5c73900ce1c
---

(Absorbs feedback_no_planning_artifact_for_small_tasks + repo_tracks_claude_notes, 2026-06-11.)

Three converged rules about planning/working notes:

**1. Whether to create a file: default NO — plans live in chat.** Confirmed twice (PR #1249 finalization: "don't need this artifact. We are fixing ourselves."; issue #1246, even at 12-file scope: "don't want an md file added to the pr"). The bar is "has the user explicitly requested a written plan?", not "is this big enough to need one?". For multi-session work where context loss is a real risk, ask before creating an artifact.

**2. Where, when a file is warranted:** working notes → `.claude/notes/<project-slug>/`; finalized ADRs → `docs/decisions/adr-NNN-<slug>.md`; developer-facing docs → `docs/development/`; never `docs/plans/`. The committed-notes precedent (#1221 flask-to-fastapi corpus) was a multi-month migration program, not a per-PR norm.

**3. Tracked-status trap + push scope (user feedback 2026-06-10):**
- The repo COMMITS much of `.claude/notes/` (proposals, handoffs, migration docs). `git status` flags only the `??` untracked ones; `ls` shows many more. Run `git ls-files .claude/notes/` before rm-ing anything there or you delete committed content (hit 2026-06-02; `D ` status was the tell; recovered via `git restore`). Deleting a tracked note is a real change that appears in the PR diff.
- Tracked ≠ push-your-session-archive: committing 11 working files (plans, baselines, review rounds, resume docs) on one PR nearly doubled main's entire notes footprint and was called out as clutter ("WTF you are cluttering the project") — all 11 were git-rm'd. Session notes stay LOCAL/untracked by default. When the spec-grounding gate needs a recorded citation, prefer the PR description. Commit at most ONE concise maintainer-facing doc per PR, only if genuinely durable.

Related: [[feedback_no_code_in_planning_stage]] (planning produces no code edits).
