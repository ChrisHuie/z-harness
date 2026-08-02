---
name: feedback-no-internal-dialogue-in-public-artifacts
description: "Anything destined for GitHub (PR descriptions, PR comments, issue bodies, code comments, committed docs) contains ONLY strict technical detail — never internal strategy, framing, motivation, troll positioning, or dialogue. Internal dialogue lives only in private memory and local-only files."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: acdcab63-786c-4cc7-9c58-54f2c30d2c24
---

NEVER include internal dialogue, strategy, framing, or motivation in anything pushed to GitHub:
- PR descriptions
- PR comments
- Issue bodies (upstream or internal)
- Code comments
- Documentation files committed to the repo (README, CHANGELOG, docs/, etc.)
- Drafted artifacts handed to the user for paste (filter BEFORE drafting)

Public artifacts contain ONLY strict technical detail: observable facts, file paths, function signatures, expected behavior, reproduction steps, technical contract. No "we want X," no "the strategy is Y," no editorializing about upstream maintainers' discipline, governance, motives, or release cadence. No troll framing. No "this matters because we strategically..."

**Why:** Public artifacts speak for themselves and are permanent. Once in GitHub they're seen by upstream maintainers, reviewers, future contributors, and competitors. Internal dialogue reveals process; technical detail reveals fact. Mixing them undermines the artifact and exposes positioning that should stay private.

**How to apply:**
- Before drafting ANY content destined for GitHub, filter sentence-by-sentence: "is this an observable fact / technical contract / reproduction step?" If not, cut it.
- Issue bodies: state the technical gap, current observable behavior, expected behavior. No "this matters because of our broader plan."
- PR descriptions: scope, files changed, technical behavior changes, test coverage. No strategic framing.
- Drafted artifacts (in chat for user to paste): same filter applies. Don't put internal dialogue into a code-block-formatted "issue body to paste."
- Internal dialogue, strategy, adversarial framing relative to upstream — these live ONLY in `/Users/quantum/.claude/projects/.../memory/` and local files explicitly not staged for push.

**Internal quality-bar vocabulary is a leak too — and echoing the USER's own request framing does NOT exempt it.** Terms like "gold standard" (the internal quality bar), "meets our bar", "gold-standard pass", or any internal verdict-label name the harness's private assessment scale, not a technical fact. Even when the user phrases the request that way ("make sure it meets our gold standard"), the PUBLIC artifact must report the CONCRETE state — 0 blocker / 0 should-fix, all prior feedback addressed at `<sha>`, CI green, invariants mutation-verified — never the internal label. The request's wording is context for YOU to act on, not text to echo outward. **Mechanized:** the `disposition_ledger.py` INTERNAL-VOCAB gate scans an outbound artifact for "gold standard", the review-workings terms below, and detector names; run it on the artifact (and on any draft handed to the user for paste) before it ships, and resolve to 0. (PR #1575: "gold standard" came from the request wording and was drafted straight into a posted PR comment; the pre-ship gate had no §1.9 vocab check, so it waved it through.) See [[feedback_no_ready_claims]] — "gold standard" is the same class of unearned verdict-label as "ready/clean".

**Also never disclose the review WORKINGS/process — a distinct category from strategy/motive.** Public artifacts (and any draft handed to the user for paste) must NOT reveal how the review was produced: no mention of the personal review harness, specialist sub-agents / fan-out ("I ran 8 reviewers", "code-patterns re-opened each"), detector names (recovery_audit, citation_freshness, disposition_ledger, …), mutation-testing framed as OUR tooling ("my mutation matrix / harness caught this"), memory files, the reviewer charter, or internal nomenclature ("gotcha #8", "masking-gotcha doctrine", severity/disposition jargon lifted from the charter). No meta-scorekeeping either ("6 rounds missed this; our tooling caught it"). Present every finding as a first-person review CONCLUSION grounded in `file:line` + observable behavior and technique that any reviewer could state — the empirical *result* is fair game (e.g. "reverting `_bump_revision` to a read-modify-write leaves the suite green"), the *provenance/tooling* is not. Strip any "Harness learning / what we learned" section entirely from the deliverable; that belongs in private memory only.

**Specific examples that violate the rule:**
- "We need to fix this because Scope3's release discipline is poor" → strip to: "SDK ↔ spec version mapping is not currently published."
- "The validator exists because the upstream runner is Node-only" → strip to: "Python implementations currently lack a native AdCP wire-shape validator."
- "Filing upstream as a troll to surface the gap" → just file the technical request; don't articulate the troll motivation anywhere it can be seen.
- "My recovery_audit detector flagged the CONFLICT recovery divergence that 6 rounds missed" → strip to: "The revision CONFLICT emits `recovery=correctable`; the pinned spec documents `CONFLICT` recovery as `transient` (`error-code.json`)."
- "I mutation-tested this in an isolated worktree with my harness" → strip to the observable result: "reverting the server-side increment leaves the full revision suite green, so no test fails when it regresses."
- "This final version meets our gold standard" / "Gold-standard pass:" (echoing the request's "gold standard" framing) → strip to the concrete state: "No blocker or should-fix; all prior review feedback is addressed at `<sha>`; CI is green; the load-bearing invariants redden under mutation."
