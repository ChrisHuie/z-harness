---
name: salesagent-wire-vs-engine-control
description: "salesagent governance doctrine — conform at the wire, own the engine; PR 1546 idempotency-reversal case study + the control mechanisms (ADR, CI inversion, CODEOWNERS, design-of-record)"
metadata: 
  node_type: memory
  type: project
  originSessionId: 4f7d24c5-ad8f-4a20-ac96-f0ff197d4767
  modified: 2026-07-20T20:09:25.285Z
---

**The situation (as of 2026-07-20).** prebid/salesagent PR #1546 (Sigma Software collaborators: numarasSigmaSoftware author, KonstantinMirin reviewer) is a large AdCP 3.1.1 conformance PR (version negotiation, envelope tolerance, bearer normalization). Late in the branch it REVERSED main's live idempotency: severed all 4 `create_media_buy` → `IdempotencyAttemptRepository` call-sites, flipped capabilities to `idempotency.supported=false`, made required keys inert (replay re-books), left the engine schema as dead code. ChrisHuie's 2026-07-20 review flagged this as the merge BLOCKER demanding an explicit call. The concurrency rebuild lives on a fork branch (`feat/adcp-idempotency-concurrency` — 404 on the main repo).

**Status:** the decision was FILED 2026-07-20 as a CHANGES_REQUESTED review under ChrisHuie (`#pullrequestreview-4738590828`): restore = merge-base behavior (replay stored success / reject conflicting payload) proven by the replay BDD scenario going live in-PR; `supported=true` restored; + 2 new punch-list items (invert SDK-derived advertisement to `ADVERTISED_ADCP_VERSIONS` constant with pin as cross-check test; open the fork rebuild as a draft PR, design-doc-first). Still pending: the ADR PR + CODEOWNERS (awaiting ChrisHuie's go — do not start unprompted).

**The doctrine (now stated publicly in that review):** conform at the WIRE (pinned vendored AdCP schemas, schema-derived BDD scenarios), own the ENGINE (idempotency/replay, holds, transitions, auth resolution, error taxonomy — specified by in-repo design docs + real-Postgres probe tests). SDK = "cross-check, not authority" (phrase harvested from the PR thread itself). Conformance may extend the engine, never weaken/inert/delete it; declaration-honesty problems are fixed in the declaration, not by disabling the mechanism.

**Why:** idempotency is a Tier-1 owned primitive ([[neutral-primitives-charter]]); the real motive (not ceding the money-path mechanism to the adcp SDK / Scope3 orbit, [[scope3-interchange-posture]]) is INTERNAL-only. The depersonalized engineering version is true, sufficient, and self-binding (it also binds us to the pinned wire), so it reads neutral, not protectionist.

**How to apply:** (1) BLOCKER resolution = restore wiring + keep `supported=true`; close partial-coverage honesty gaps by EXTENDING dedupe (#1607 on the existing repository), never by descoping. (2) Install authority in-repo so control is citable law, not per-PR argument: ADR "authority boundaries: pinned spec / SDK / engine"; invert SDK-derived advertised values to in-repo constants + CI cross-check ("advertise what the agent implements, not what its dependency ships"); CODEOWNERS on engine paths; require the fork rebuild as an early draft PR with a maintainer-authored design-of-record first. (3) Offense: once design doc + probes exist, optionally upstream our replay semantics to AdCP as the non-normative reference — can't be downstream of text we wrote. Contractors follow the most legible authority; today only the pinned spec is legible in-repo, so reviews converge on spec-shape — the fix is a second, equally legible in-repo authority. [[salesagent-lessons]]
