---
name: installed-skills-are-frozen-snapshots
description: "Invoking a prompt-harness skill loads the installed ~/.claude/skills snapshot, not the repo working tree — read repo canon when reviewing a branch"
metadata: 
  node_type: memory
  type: project
  originSessionId: aaf8bd21-cf1d-4635-84ff-109def16105a
---

Invoking a prompt-harness skill (`Skill(craft-prompt)`, `/craft-prompt`) loads the **installed copy** under `~/.claude/skills/<name>/`, which is a copy frozen at install time. It does not track the working tree, and nothing auto-syncs it. Observed live 2026-07-15: the installed `craft-prompt/SKILL.md` was dated Jul 14 13:14 and still carried the pre-PR-11 Step-4 row (`explore/plan/review stance where the task might still act`) while the repo branch had already narrowed it to `explore/plan`.

The installed bundle also has a **flattened** reference layout (`references/action-default.md`, `references/stance-review.md`, `references/model-claude.md`, `references/audit-rigor.yaml`) versus the repo's nested canon (`references/policy-blocks/`, `references/stances/`, `references/model-profiles/`, `styles/profiles/`). That flattening is the emitter's manifest bundling, so installed paths never match repo paths.

**Why:** distribution is copy-based (`install.sh`, transitional; `ph-emit --install` is the path forward). An install is a point-in-time emit of the corpus.

**How to apply:** when dogfooding or reviewing a branch that changes a skill, treat `skills/<name>/SKILL.md` and `references/**` **in the repo** as the doctrine under review, and treat anything the Skill tool loads as a possibly-stale artifact. Say which one you used. If a dogfood run behaves like the old doctrine, suspect the snapshot before suspecting the change. Related: [[prompt-harness-pr-review-method]], [[prompt-harness-goal]].
