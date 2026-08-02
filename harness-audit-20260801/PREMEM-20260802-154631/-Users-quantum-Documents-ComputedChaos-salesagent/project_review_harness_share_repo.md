---
name: project-review-harness-share-repo
description: "Shareable review-harness repo at ../salesagent-review-harness — refreshed+scrubbed 2026-07-17 (commit 80719b3), still no remote/push"
metadata: 
  node_type: memory
  type: project
  originSessionId: afb24d91-f2af-48a0-b4bb-b0b81595dd1b
---

The colleague-shareable review harness lives at `/Users/quantum/Documents/ComputedChaos/salesagent-review-harness/` — an overlay repo (install.sh copies into a salesagent checkout's `.claude/`; the salesagent repo's own .gitignore already ignores every installed path, so installs leave the target tree clean).

State as of 2026-07-17: **PUBLISHED at https://github.com/ChrisHuie/salesagent-review-harness (PUBLIC, Apache-2.0)** — history REWRITTEN + force-pushed same day to purge the behavioral-memory layer: now `f8ed8bf` (GitHub LICENSE init) → `06775d1` (single harness commit). The user drew the sharing line at the feedback diary: all 53 `feedback_*` memories DELETED from the bundle (their operative rules live inline in charter/agents); the 17 reference-class files kept (P1–P42 catalog, wire-envelope policy, BDD patterns/pitfalls, spec-grounding, infra gotchas), each audited + scrubbed (originSessionId frontmatter stripped, reviewer-quote decoding removed, "reviewer's own PR" attribution generalized, dangling links resolved). Charter §0 now defines bracket citations as pattern IDs (files intentionally absent); §5 is a distilled inline posture block. Pre-rewrite SHAs (763809c/80719b3/edd4e49, containing the scrubbed-but-diary-flavored 70-file corpus) are unreachable but may stay fetchable by SHA on GitHub until gc — zero-trace would need GitHub Support or delete+recreate.

The 2026-07-17 refresh brought it to parity with the live harness: 8 agents + charter (§4b/§4c, gotcha 9) + tooling (§H) + full-review (re-review gate, tree provisioning, SSOT synthesis, ledger gate) + **all 10 detectors** (self-tests verified passing from bundle copies) + 70 memories (rule: every memory the shipped docs cite; June's 65 + 5 new). Sharability scrub applied: no machine paths, names/handles, `bd`/beads action commands (target-repo beads DESCRIPTIONS kept — publicly documented), internal finding labels (SF1/NTH2-4), "miss-mode #N" taxonomy (private harness-upgrade-spec is NOT shipped), session-diary phrasing, or "gold standard" as harness voice ("Reference example:" now). Intentional residuals: charter §1.9 + [[feedback_no_internal_dialogue_in_public_artifacts]] + disposition_ledger.py name the banned vocabulary as rule-objects/fixtures; `ARCH-SF1` in disposition_ledger is the report finding-ID format example. Verbatim "The user said:" quotes largely kept (anonymous, instructional) except the overconfidence quote (rewritten neutral).

On future refreshes: re-run the same pipeline — copy live files, sed the two path rewrites (personal memory dir → `.claude/rules/private/memory/`, absolute repo path → relative), revert agent Step-0 headers to "(paths relative to the repo root)", re-derive the doc-cited memory set, scrub-grep (patterns incl. colleague, gold standard, this session, SF[0-9], miss-mode), run detector self-tests via bundle `bump_check.py` + `--selftest` flags, install.sh dry-run. Note adcp pin was 6.6.0/spec 3.1.1 at refresh; recovery_audit/sdk_spec_drift snapshots were current.

Related: [[feedback_personal_harness_gitignored_only]] (this repo is the sanctioned share vehicle; detectors never gate others' CI), [[reference_harness_freshness_mechanisms]], [[feedback_generalize_memories_and_skills]] (the scrub standard).
