---
name: corpus-contradictions-are-cross-file-and-untooled
description: "prompt-harness's characteristic defect is one canonical file contradicting another; PR"
metadata: 
  node_type: memory
  type: project
  originSessionId: aaf8bd21-cf1d-4635-84ff-109def16105a
---

The characteristic defect in this repo is **one canonical file contradicting another**. A stance rule lives in at least four places — the stance envelope (`references/stances/`), the policy block (`references/policy-blocks/`), the style axis (`references/style-axes/`), and the skill's selector table (`skills/*/SKILL.md`) — plus the design doc. No single source of truth links them.

Demonstrated live on PR #11 (2026-07-15): `references/stances/review.md` changed to render neither action-default side while four unchanged locations still said the opposite. `lint:prompts` reported 0 findings and `npm test` was green, because standalone rules judge one artifact at a time and the changed files were self-consistent.

**The guard that now exists (PR #11, `packages/lint/src/corpus.ts`):** `lintCorpus(artifacts)` runs `row-21-review-action-default-consistency` across the whole supplied set. CI lints `references/ styles/ skills/craft-prompt/SKILL.md docs/design/modes-and-composition.md` in **one process** and fails on that `ruleId` even though it is warn-level. Verified by injection at `555b279` — it catches the explicit map, the **semantic** map (a broad "asks a question / describes a problem / requests analysis without requesting changes → Side B" rule that never says "review"), and `initiative.md`'s pinned I0 row. It joins soft-wrapped prose into semantic units, so a contradiction spanning two lines is caught. It **fails loud** — if `review.md` loses its `Initiative I0` / read-only / neither-side markers, it emits "cannot safely enforce the review action boundary" rather than silently disabling.

**What it still does not cover:** only the review/action-default invariant, and only `action-default.md`, non-review stance files, `craft-prompt/SKILL.md`, `modes-and-composition.md`, plus `initiative.md`'s I0 row. Not `references/patterns/`, not other skills, and no other stance's invariant. The broad-entry detection is scoped to `action-default.md` alone.

**How to apply:** for the review/action-default rule, trust the lint. For **any other** cross-file invariant, a green suite plus clean lint still proves nothing — grep the corpus yourself. Sweep twice: once on the identifier (`do_not_act_before_instructions`, `action-default`, `Side B`), then again on the *semantic* claim ("report-only", "latent", "escalation"), since files disagree without using the identifier. Trace the skill's steps against the profile: `styles/profiles/*.yaml` pins an axis level and craft-prompt Step 3 collects that axis file's fragment unless the row is marked `(none)`. Exclude `evals/measurement/**/input-snapshots/**` — deliberately frozen, legitimately stale.

Related: [[prompt-harness-pr-review-method]], [[installed-skills-are-frozen-snapshots]], [[prompt-harness-goal]].
