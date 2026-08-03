---
name: Storyboard compliance run methodology + Q-006 patch location
description: How to run @adcp/sdk storyboards against salesagent (worktree + docker + npm runner), where the Q-006 local-only patch lives, and how the framework absorbs empirical run findings.
type: project
originSessionId: b20ae879-7b4d-4db0-b610-d3da63c2f4da
---
A repeatable methodology was proven out 2026-05-10 for running AdCP
compliance storyboards against the prebid salesagent. Captured here so
fresh sessions don't have to re-derive it.

## Reproducing a storyboard run

Full recipe in `findings/2026-05-10-storyboard-run-against-4.3/README.md`
(at `/Users/quantum/Documents/GitHub/agentic-advertising/`). Six-step
shape:

1. Create a worktree of `prebid/salesagent` at `origin/main` so the
   bokelley branch isn't disturbed:
   `cd /Users/quantum/Documents/ComputedChaos/salesagent && git worktree add /tmp/salesagent-main origin/main`
2. Apply the Q-006 compat patch (see "Q-006 patch" section below).
3. `cp .env /tmp/salesagent-main/.env && set CONDUCTOR_PORT=8001` (avoid
   port collisions with other worktrees).
4. `cd /tmp/salesagent-main && docker compose up -d`. Wait for
   adcp-server to become healthy.
5. Seed a test principal directly via psql (manage_auth.py is broken —
   see catalog gap #34):
   `docker compose exec postgres psql -U adcp_user -d adcp -c
   "INSERT INTO principals (principal_id, tenant_id, name, access_token,
   platform_mappings, created_at, updated_at) VALUES ('storyboard_test',
   'default', 'Storyboard Compliance Test', 'storyboard_test_token_xyz',
   '{}', NOW(), NOW());"`
6. Install the npm storyboard runner (Node 22+ required):
   `nvm install 22 && nvm use 22 && mkdir -p /tmp/storyboard-runner &&
   cd /tmp/storyboard-runner && npm init -y && npm install @adcp/sdk@6.18.0`
7. Run: `node node_modules/@adcp/sdk/bin/adcp.js storyboard run
   http://localhost:8001 --protocol a2a --auth storyboard_test_token_xyz
   --allow-http --summary-output ./full-assessment.json --timeout 240`

Results land in `./full-assessment.json` per the runner's stable
`schema_version: 1` shape.

**How to apply.** When asked to run AdCP storyboards against the
salesagent, point at the findings README. Don't re-derive the recipe.

## Q-006 patch — where it lives

The agent-card discovery shim that lets `@adcp/sdk@6.18.0` connect to
`a2a-sdk>=1.0` salesagent is a 28-line patch to `src/app.py`.
**It is captured verbatim** in
`questions/Q-006-a2a-card-schema-version.md` under the "Workaround diff
(verbatim)" subsection. The patch is local-only — do NOT propose it
upstream as-is; it's a compat shim pending Q-006 resolution by the
AdCP committee. The `/tmp/salesagent-main` worktree where it was
originally applied may be wiped on macOS reboot — always re-apply from
the question doc, not from `/tmp`.

## Framework's reactive pattern (worked once, will work again)

When an empirical compliance run produces findings, the framework
absorbs them via this pattern. Documented by example in the commits
b25bc45 / b5dc16a / 53803eb:

1. **Open committee questions** for each protocol-ambiguity surfaced
   (e.g., Q-006 from this run was about A2A 0.x ↔ 1.0 card schema
   gap). Land in `questions/Q-NNN-<slug>.md`.
2. **Update overlays** when the run touches code-level claims —
   `implementations/python/_atom-overlays/<atom_id>.md` for verified
   file:line citations.
3. **Update implementation status** in
   `implementations/python/<repo>.md` for things like "salesagent is
   on adcp 4.3, not the unsatisfiable 3.12 we incorrectly claimed
   earlier."
4. **Write a run dossier** under
   `findings/<date>-<run-name>/` containing: README (setup + headline
   numbers), JSON artifacts (the runner's stable summary), gaps
   catalog (every unique gap with severity + buyer impact + spec
   citation + code location + existing prior art).
5. **Cross-reference** atoms blocked by new questions and questions
   answering atoms — the bidirectional graph stays consistent.
6. **Round 2 verification pass** if the catalog will be load-bearing
   for issue creation: spawn parallel Opus subagents (versions,
   per-gap technical claims, completeness, issue currency) and apply
   corrections inline with `[r2]` markers.

The pattern is the framework's "reactive discipline" working as
designed (per `genesis/04-framework.md` lines 80-91, "don't classify
the whole codebase upfront"). Real work touched an area → produced
classifications.

**Don't do**: pre-emptively classify atoms for areas not touched by
real work. The framework explicitly avoids this.
