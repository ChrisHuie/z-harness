---
name: feedback_review_consolidation_drops_findings
description: "A review can FIND a real defect and still DROP it — rated NIT, split across agents, filed \"optional\"; mechanize with the disposition-ledger detector + SSOT-synthesis pass"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: d5498f5a-455e-4cf8-be67-af6765b95aeb
---

The specialist reviewers can surface a genuine defect and the CONSOLIDATION still loses it. The failure is not severity — it is **disposition**: a finding rated NIT, raised as separate shards by two agents, filed under "optional / non-gating," and never surfaced (it stayed in a gitignored note). A human colleague raised exactly those sites — unified, with a fix path — a day later. Two compounding blind spots:
1. The **textual DRY guard** (`check_code_duplication.py`, R0801 + ratcheting baseline) is blind to SEMANTIC duplication — one concept implemented N ways below the token threshold or spread across files. The baseline can ratchet DOWN (e.g. 89→88) while a "one read, three implementations" dup persists → false comfort. [[feedback_semantic_ssot_defect_class]]
2. **De-dup by `(path, line)` is not synthesis.** It collapses the same finding raised twice; it leaves same-concept findings at different paths as separate low-severity items — which is precisely the drop channel.

**Why:** this is the third instance of the consolidation-discipline class (inflation, memory-before-verify, and now DROP). Recall ≠ enforcement — the charter already said "never optional / sweep siblings" in prose (§3, §11); prose didn't fire. Escalate a ≥2×-violated lesson to a mechanism, not more prose. [[feedback_escalate_recurring_lessons_to_guards]], [[feedback_claimed_invariant_needs_failing_oracle]]

**How to apply:**
- Consolidation runs **de-dup → SSOT-synthesis → symmetric-verify** (charter §4b.0, `/full-review` Step 5.2): walk EVERY finding incl. NITs across ALL agents, unify any group naming one concept in N places into a single finding at max member severity, then sweep for the Nth site the agents didn't reach.
- Every finding ends in a resolved disposition (done | folded-in | tracked(link) | won't-fix(reason)); the report carries an Actions ledger (§4b.5). Run the T1 backstop on the artifact before it ships: `python3 .claude/rules/private/detectors/disposition_ledger.py <report>` — exit 1 = a finding has no resolved next-action, the ledger is absent, or an "optional/non-gating" bucket launders a drop. A clean exit means "nothing dropped," NOT "nothing missed" (unification is Step 5.2's job, a judgment pass the detector can't check). [[reference_harness_freshness_mechanisms]]
