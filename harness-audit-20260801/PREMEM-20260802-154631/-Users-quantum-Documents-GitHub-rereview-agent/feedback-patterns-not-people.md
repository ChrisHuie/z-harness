---
name: feedback-patterns-not-people
description: "User feedback — never name individuals in project docs; describe roles and universal patterns; single-repo dynamics are one manifestation, not the spec"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 8edeb0be-b944-4779-89d3-d35d287f239d
  modified: 2026-07-24T13:34:36.185Z
---

The user (2026-07-24, on [[rereview-agent-goal-and-decisions]]): "we shouldn't be including individuals names? These are concepts that are universally applied to anyone and the reality of development in 2026. This is just a single repo and a single way agentic development manifests... shows up in a lot of different ways."

**Why:** Design docs that characterize named people (especially speculating whether someone is an agent) are inappropriate, and heuristics keyed to one repo's specifics don't generalize — agentic development manifests as multi-bot swarms, single systematic agent-assisted reviewers, agent-authored PRs, tool-bot streams, and more.

**How to apply:** In authored docs, artifacts, and memory, use roles ("systematic reviewer", "author", "maintainer") and clearly generic handles in mocks (`@reviewer-a`, `your-account`); raw API fixture dumps may keep real public data as evidence. Frame each observed repo dynamic as one manifestation of a universal pattern; key heuristics to patterns with pluggable lexicons, never to an individual or a repo quirk.
