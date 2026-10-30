---
name: swamp-getting-started
description: Redirect; Swamp onboarding lives in the swamp skill. Triggers on "getting started", "new to swamp", "first behavior", "walkthrough", "quickstart", a swamp start brief, or /swamp-getting-started. Load the swamp skill and follow its brief entry point and first-run runbook. Not a separate flow.
metadata:
  version: 0.1.0
---

# swamp-getting-started

This name is kept so that `swamp start` launches, and the managed instructions that
`swamp repo init` writes into a repository, still resolve to a skill. There is no separate
onboarding state machine.

Load the `swamp` skill now. If a brief under tasks/ was named, follow its brief entry point;
otherwise follow the first-run runbook it routes to. Do not run `swamp repo init` or
`swamp auth login` unless that skill's checks show they are needed.
