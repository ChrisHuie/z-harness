---
name: norbert-skills-temporal-design
description: norbert-skills organizes agent skills into 7 temporal groups; research reports live in docs/research/
metadata: 
  node_type: memory
  type: project
  originSessionId: 7b516ca9-eebb-4001-862f-a803cd7034ba
---

<!-- audit-2026-08-01 -->
> **SUPERSEDED as of 2026-08-01.** Duplicates `/Users/quantum/.claude/projects/-Users-quantum-Documents-GitHub-norbert-skills/memory/temporal-backbone-design.md`, which is kept as the canonical version. Kept for history.
> Rationale: A strict subset of temporal-backbone-design.md, which is far more specific and better evidenced. Keep that one. Not indexed by MEMORY.md, which suggests it was already superseded.


norbert-skills (as of 2026-07-04) is a skills library + agentic-harness backbone organized by temporal ABOUTNESS into 7 groups: FUTURE, PRESENT, PAST states; FUTURE→PRESENT, PRESENT→PAST, PAST→FUTURE transitions; plus atemporal ALWAYS (standing doctrine, "axle of the wheel"). Grouping is by what a skill reads/writes (plans vs telemetry vs episodes vs playbooks), not when it runs. Design is harness-agnostic, first binding to Claude Code. Domain research reports are written to `docs/research/NN-<domain>.md` (01 = skills ecosystem). Key ecosystem constraint found in research: Claude Code only scans flat `skills/<name>/SKILL.md` — grouped subdirectories require a plugin manifest `skills` array or symlink installs.
