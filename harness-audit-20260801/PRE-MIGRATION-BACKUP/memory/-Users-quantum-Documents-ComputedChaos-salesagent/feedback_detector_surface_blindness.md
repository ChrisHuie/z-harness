---
name: feedback_detector_surface_blindness
description: "A detector's scan set is part of its claim — a CLEAN verdict over the wrong surface is a true sentence that reads as an all-clear; ask \"over which surface?\" before trusting it."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: d15e20da-0c34-4049-87cf-159a68530a4b
  modified: 2026-07-29T23:10:35.350Z
---

When a detector prints CLEAN, ask **over which surface** before treating it as an all-clear. A scan that is complete and correct over the files it read still says nothing about the place the requirement actually lives.

**Why:** a version-citation detector scanned source trees and reported "no candidate-stale citations" for a PR's changed files — true, and useless, because the spec-grounding requirement puts the citation in the **PR description**, which had cited a superseded pin for an entire review round. The detector was structurally incapable of seeing it. This is distinct from a detector auditing *nothing* in scope (that failure at least smells wrong); here the audit is real, the sentence is true, and it is read as coverage.

The same shape recurs whenever the artifact of record is not code: PR/issue bodies, review comments, docs, generated files, config outside the scanned roots.

**How to apply:** for each detector, state its scan set out loud alongside its verdict, and check that the set includes wherever the obligation is written. When prose is the artifact of record, prose is in scope — add the surface rather than adjudicating by hand forever. Make surfaces share one matcher so they cannot drift apart, and print a caveat on each that a clean verdict on one says nothing about the other. Corollary for detectors that *are* wrong rather than blind: verify a detector's verdict in **both** directions before repeating it — one grading detector produced a false DORMANT (via a substring collision with an unrelated concept) and a false LIVE (by conflating request-side with response-side hits) in the same run, and the prior round had repeated its verdict unchecked. Related: [[feedback_guard_matcher_completeness]], [[feedback_empirical_over_static_guard_assessment]], [[feedback_recovery_audit_coherence_blind_to_condition]], [[reference_harness_freshness_mechanisms]].
