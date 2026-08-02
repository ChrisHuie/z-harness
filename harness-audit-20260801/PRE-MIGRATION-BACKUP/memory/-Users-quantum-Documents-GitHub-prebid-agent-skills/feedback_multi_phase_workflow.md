---
name: multi-phase-execution-workflow
description: For multi-phase implementation tasks on this project, follow this pre-flight sequence after plan approval: recommend /compact, then create a new git branch, then start execution. User explicitly stated this on the read-skill plan.
type: feedback
originSessionId: a5f0807e-b696-4762-a9d9-6f3975c50d85
---
For multi-phase implementation tasks (e.g., refresh skills, build new skill suites), follow this pre-flight sequence:

1. Plan thoroughly via opus subagents (Phase 1 explore + Phase 2 design + Phase 3 stress-test if scope is large).
2. Get user plan approval (user manually approves; do not assume auto-approve).
3. After approval, recommend `/compact` to free context before starting execution. The plan file persists, but the conversation history can be compacted.
4. Create a new git branch (`git checkout -b <name>`) BEFORE any file edits begin — keeps execution work isolated and reviewable.
5. Then start Phase A execution.

**Why:** Long execution phases consume large context. Compacting after planning keeps the working context lean for the actual edits. Branching keeps the change reviewable as a single unit. User stated verbatim during read-skill plan approval: "we probably need to compact memory before we start and lets create a new branch for our new changes."

**How to apply:** When the user approves a multi-phase plan, ask: "Want to /compact first? And what branch name should I use for the implementation?" before kicking off Phase A. Do not start file edits on `main`/`master` for multi-phase work.

**Manual edit approval:** User also said "im going to manually approve edits" — they may be running with manual approval mode for this work. Do not assume auto-accept; expect each edit to need approval. Plan tool calls accordingly (batch where possible to reduce approval prompts).
