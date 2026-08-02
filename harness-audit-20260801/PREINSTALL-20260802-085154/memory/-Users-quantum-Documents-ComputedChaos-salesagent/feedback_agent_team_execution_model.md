---
name: Agent-team execution model, not human-team process
description: User implements entirely with agents — strip human-team ownership scaffolding from process docs
type: feedback
originSessionId: d60497c1-fead-4fed-98f5-fa7578895c2f
---
Migration and process docs must NOT use human-team ownership scaffolding. The user is solo + a team of agents (implementation, review, refactor, evaluation).

**Why:** When asked on 2026-04-18 whether the Flask→FastAPI v2.0 migration was ready to implement, I flagged an "Ownership & Bus-Factor Policy" section with [TO BE ASSIGNED] lead/reviewer/commander roles as a hard gate. User clarified: "We are implementing entirely with a team of agents" — human ownership roles are dead weight. The scaffolding was scrubbed from the live docs (CLAUDE.md §Ownership removed, checklist §6.5 on-call table replaced, all "signed off by primary lead" / "reviewer rotation" / "platform team" / "release manager" rows rewritten).

**How to apply:**

When authoring or editing process docs, plans, runbooks, or checklists, do NOT write:
- Named roles (primary lead, backup lead, security reviewer, incident commander, release manager, product owner, platform team, ops staff, operators)
- Handoff protocols between humans ("outgoing lead shadows incoming lead")
- Reviewer rotation rules ("no single reviewer approves >3 consecutive PRs")
- On-call rosters / pager policies / escalation chains
- Vacation / time-off / blackout windows
- "Team announcements" or "team freezes"
- Sign-off language tied to human roles

Instead, map the underlying engineering concern to an agent-workflow equivalent:
- **Pattern drift across long sequences** → fresh-agent review pass (cold context, no prior session history) on every layer-exit PR
- **Security-critical gates** → `/security-review` skill pass on the PR branch
- **Irreversible cut safety** → rollback runbooks executable from cold context (the docs ARE the bus-factor protection)
- **Incident response during bakes** → user is the incident commander; agents assist with log triage / dashboard queries on request
- **Handoff between sessions** → docs are the handoff (agent sessions are stateless)
- **Calendar blackouts** → user schedules bake windows for their own availability only

Customer comms / downstream consumer notifications are still real (external humans exist) — keep those, but replace "team announcement" framing with a named audience doc (e.g., `docs/migration/customer-comms-audience.md`).

Engineer-day estimates are fine as effort units; they proxy scope, not calendar ownership.
