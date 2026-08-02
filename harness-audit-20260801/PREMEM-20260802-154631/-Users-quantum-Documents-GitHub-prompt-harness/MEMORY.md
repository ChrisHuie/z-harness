# Memory Index

- [prompt-harness goal & direction](prompt-harness-goal.md) — cross-harness prompting engine; 2026-07-14 arc complete: MVP → audit → fix plan → mcp-server v0 → Phase 2 gate 9/9 (4 skills, 5 TS packages, CI, corpus 26/26); retros + plans in docs/; M2 next
- [Installed skills are frozen snapshots](installed-skills-are-frozen-snapshots.md) — `Skill(craft-prompt)` loads the stale ~/.claude/skills copy, not the working tree; read repo canon when reviewing a branch
- [How to review PRs here](prompt-harness-pr-review-method.md) — owner wants craft-prompt-authored subagent prompts, parallel read-only agents per dimension, deterministic suites run directly
- [Corpus contradictions are cross-file](corpus-contradictions-are-cross-file-and-untooled.md) — a stance rule lives in 4+ places with no source of truth; PR #11's lintCorpus guards review/action-default (semantic + fail-loud); every other invariant is still grep-it-yourself
