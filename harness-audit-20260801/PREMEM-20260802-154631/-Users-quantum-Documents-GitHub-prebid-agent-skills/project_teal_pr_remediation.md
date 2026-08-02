---
name: project-teal-pr-remediation
description: "Teal adapter PR #4765 (Java→Go port) — durable two-workstream state + the lesson. Per-PR specifics live in the PR/chat, not here."
metadata:
  node_type: memory
  type: project
  originSessionId: aa049dfd-aa09-4a10-a1e2-61f821d8e096
---

prebid/prebid-server PR #4765 ("New Adapter: Teal") is our Java→Go port (branch `feat/new-adapter-teal`, author ChrisHuie), reviewed by `przemkaczmarek`. Two-workstream remediation:

- **Workstream A — fix the PR:** address all reviewer threads. DONE: non-standard files removed, getBidType→`(BidType,error)`+impsByID, audio branch removed, mixed-account error-on-divergence, tests slimmed toward JSON fixtures. FOLLOW-UP (2026-06-30, reviewer `postindustria-code`): the earlier getBidType fix was INCOMPLETE — it fixed the fallback (error-on-miss) + perf (impsByID) but kept resolution IMP-based; for a `multiformat-supported` adapter that mis-types co-present formats (every bid→banner). Fixed by switching on `bid.MType` FIRST, imp lookup as fallback, `BadServerResponse` on miss, + a multi-format-imp fixture with mtype-tagged bids. Shipped 2026-07-01 (all CI green). Status/diffs belong in the PR comment, not here (per [[feedback-no-pr-specifics-in-memory]]).
- **Workstream B — harden the skills so future ports don't repeat it:** PENDING. B1 stop emitting non-standard files (doc.go/fuzz/bench); B2 fidelity-boundary precedence rule; B3 fix `bidder.go.j2` getBidType→error-on-miss + impsByID; B4 review-skill dispositions→blocking + add perf / first-wins / non-standard-file checks; B5 mandatory pre-submission review gate; B6 reframe quality model; B7 fix stale `endpointCompression` GZIP-casing prose.

ROOT CAUSE / the lesson: our review did NOT miss the original 8 — it caught ~6/8 and resolved them toward Java fidelity + "more artifacts = quality," against the Go target repo's lean-conformance bar (genuine detection gaps were only perf + mixed-account). The later multiformat⇒mtype miss (postindustria-code) WAS a true harness gap: we checked bid-type *coverage* + *fallback silence* but never linked `multiformat-supported` to a mandatory per-bid `bid.MType`. Closed in the hardening program (see [[project-port-skills-hardening]] — Go+Java review + both port templates, shipped 2026-07-01). Generalizable rules captured in [[reference-port-fidelity-vs-target-norms]].

Workflow constraints: user manually approves edits; never push without explicit per-action authorization ([[feedback-push-policy]]); verify each finding against live code before asserting ([[feedback-review-rigor]]).
