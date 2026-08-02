---
name: feedback-confession-marker-grep-before-ready
description: "Self-flagged debt (keep-in-sync comments, setup-only docstring admissions, unverified defensive rationales) survives audits invisibly. Grep for the codebase's own confessions before any ready claim — a keep-in-sync comment IS a deferred DRY violation, fix it, don't document it."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: f2e0a5cd-a513-47b6-a919-ef16c0c2431d
---

Review-response audits verify reviewer-named items and structural-guard
patterns, but miss debt WE flagged ourselves in prose. Three confession
classes let PR #1389 collect avoidable re-review feedback:

1. **Co-change ("keep in sync") comments.** During a hygiene pass we found the
   response-variant decision duplicated across the A2A reconstructor and the
   idempotency replay path — and wrote "keep the two in sync" comments on both
   instead of extracting the classifier. CLAUDE.md's DRY invariant forbids
   exactly this ("NEVER cite avoiding over-engineering to justify leaving
   duplicated logic in place"). A sync comment is a written confession of a
   deferred DRY violation; the reviewer called it "the signal to extract".
   The two sites discriminating on DIFFERENT signals (live status vs stored
   shape) made it look like two operations — it was one decision rule with
   two projections, and the extraction picked the signal valid at both homes.

2. **Docstring admissions in tests.** Obligation-tagged tests whose docstrings
   said "this test verifies the setup for subsequent rejection handling" —
   i.e. admitted not testing the tagged behavior. They'd pass with the
   behavior fully broken.

3. **Unverified defensive rationales.** A helper docstring claimed a shape
   "can arrive as a bare string after some deserialization paths" — never
   verified, empirically impossible, and it made dead defensive code look
   purposeful (and even earned a test pinning the dead branch via
   SimpleNamespace). Same disease as the no-defensive-RootModel guard.

**How to apply:** Before any "addressed all feedback / ready" claim on a PR,
grep the DIFF (and on hygiene passes, the touched subsystems) for confessions:

```bash
git grep -inE "keep .{0,20}in sync|kept in sync|must (also )?update|remember to (update|change)|co-change" -- src/
git grep -inE "verifies the .*(setup|state is set)|only (checks|verifies)|does not (actually|yet)" -- tests/
git grep -inE "can arrive as|may be a bare|defensive(ly)? (handle|guard)|just in case" -- src/
```

For each hit: extract/fix now, or verify the claim empirically and delete the
dead guard, or (tests) make the test observe the behavior. Prose notes about
tracking an EXTERNAL source ("in sync with the AdCP spec") are fine — the
defect is two CODE sites promising manual co-change.

If a hit can't be fixed in-PR, say so in the PR description explicitly — the
reviewer deciding scope beats the reviewer discovering the comment.

Escalation note (per [[feedback_escalate_recurring_lessons_to_guards]]): if
sync-comments recur, propose a structural guard banning `keep .* in sync`
comments in src/ (allowlist spec-tracking phrasings).

Related: [[feedback_semantic_ssot_defect_class]],
[[feedback_merge_creates_duplication_sweep_ssot]],
[[feedback_claimed_invariant_needs_failing_oracle]].
