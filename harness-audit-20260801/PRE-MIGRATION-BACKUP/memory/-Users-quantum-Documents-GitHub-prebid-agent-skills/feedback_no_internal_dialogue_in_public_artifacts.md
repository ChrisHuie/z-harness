---
name: feedback-no-internal-dialogue-in-public-artifacts
description: "Anything destined for GitHub (PR descriptions/comments, issue bodies, code comments, committed docs, drafts handed over for paste) contains ONLY strict technical detail — never internal strategy, framing, motivation, or editorializing about maintainers."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: aa049dfd-aa09-4a10-a1e2-61f821d8e096
---

<!-- audit-2026-08-01 -->
> **SUPERSEDED as of 2026-08-01.** Duplicates `/Users/quantum/.claude/projects/-Users-quantum-Documents-ComputedChaos-salesagent/memory/feedback_no_internal_dialogue_in_public_artifacts.md`, which is kept as the canonical version. Kept for history.
> Rationale: Identically-named HIGH-trust twin in salesagent, and the rule is ALREADY promoted verbatim into ~/.claude/CLAUDE.md. This copy self-declares as a port. Nothing left to promote.


NEVER include internal dialogue, strategy, framing, or motivation in anything bound for GitHub: PR descriptions, PR comments, issue bodies (upstream or internal), code comments, committed docs, and drafts handed to the user for paste (filter BEFORE drafting).

Public artifacts contain ONLY strict technical detail: observable facts, file paths, function signatures, expected behavior, reproduction steps, the technical contract. No "we want X," no "the strategy is Y," no editorializing about upstream maintainers' discipline/motives/cadence, no troll framing, no "this matters because we strategically…".

**Why:** Public artifacts are permanent and seen by maintainers, reviewers, future contributors, competitors. Technical detail reveals fact; internal dialogue reveals process and exposes positioning that should stay private. (General working-style preference; was siloed in the salesagent project — ported.)

**How to apply:** Before drafting any GitHub-bound content, filter sentence-by-sentence: "is this an observable fact / technical contract / repro step?" If not, cut it.
- Issue bodies: technical gap, current observable behavior, expected behavior. No broader-plan framing.
- PR descriptions/comments: scope, files changed, behavior change, test coverage. No strategic framing, no self-deprecation about how the code came to be.
- Strip examples: "shouldn't have shipped" → "non-standard file, removed"; "so the two implementations re-align deliberately" → "for parity".
- Internal dialogue / strategy lives ONLY in this `memory/` dir and local-only files, never staged for push.

Related: [[feedback-no-blockquote-for-pasteable-text]], [[feedback-no-pr-specifics-in-memory]].
